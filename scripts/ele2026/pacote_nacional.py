#!/usr/bin/env python3
"""National audit of the TSE bulk package, 1st and 2nd rounds of 2026.

The TSE published one zip per UF and round with every file of every section:
  bu_imgbu_logjez_rdv_vscmr_2026_<1t|2t>_<UF>.zip
with flat member names o0322<0|1><uf><mun5><zone4><section4>-<kind>
(kinds bu.dat, rdv.dat, imgbu.dat, log.jez, vota.vsc).

Two analyses per section and round:

A. Printed BU image (-imgbu.dat, parsers/imgbu.py) against the binary BU
   (-bu.dat, parsers/bu.py): President votes per candidate, blank, null,
   nominal total, total counted, eligible voters, turnout, the three
   enablement counts (biometric, biographic, without biometrics) and the
   voting machine id. Every field that differs is recorded.

B. Voter by voter log (-log.jez, parsers/log.py). Only lines dated on the
   round day count (the 2nd round log carries the 1st round events). Each
   voter episode starts at "Identificador do eleitor digitado pelo mesário"
   and ends at "Eleitor foi habilitado"; the episode class (same rules as
   biometria_t1_t2.py) is attached to the next "O voto do eleitor foi
   computado". From the vote timeline: votes against BU turnout, votes per
   enablement class, rapid runs (5 or more consecutive votes on the same
   machine with every gap under 30 s), non-biometric votes in the last hour
   and after 17h (Brasilia time), votes out of hours, restarts, machine
   swaps and non-INFO events.

Subcommands:
  processar   download each UF zip into RAM (/dev/shm), process it with a
              process pool and delete it. One parquet per UF and round in
              --saida (secoes_<uf>_<t>.parquet, eventos_<uf>_<t>.parquet).
              UF/round pairs already done are skipped.
  relatorio   national summary, 1st x 2nd round comparison, swing test with
              municipality fixed effects and extreme sections. Small outputs
              go to --repo (default data/parquet/2026/pacote_nacional).

Usage (analysis server):
  uv run python scripts/ele2026/pacote_nacional.py processar --ufs AC,RR \\
      --saida ~/dataurnas-pacote-nacional --tmp /dev/shm/pacote-nacional
  uv run python scripts/ele2026/pacote_nacional.py relatorio \\
      --saida ~/dataurnas-pacote-nacional
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
import threading
import time
import urllib.request
import zipfile
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT / "src"),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

URL = ("https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2026/arqurnatot/"
       "bu_imgbu_logjez_rdv_vscmr_2026_{t}t_{uf}.zip")
UFS = ("AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO ZZ"
       .split())
DATA = {1: "04/10/2026", 2: "25/10/2026"}
NOME_RE = re.compile(r"^o0322([01])([a-z]{2})(\d{5})(\d{4})(\d{4})-(.+)$")
CHAVES = ["uf", "cd_mun", "zona", "secao"]
CARGO_PRESIDENTE = 1

JANELA_RAJADA_S = 30   # gap under this joins two votes in a rapid run
MIN_RAJADA = 5         # votes in a run to count it
SEM_BIO = ("biog", "manual_sem_digital", "sem_digital", "outro", "desconhecido")

RE_NUM = re.compile(r"\d+")
RE_TIPO = re.compile(r"Tipo de habilitação do eleitor \[(.*)\]")
RE_MESARIO = re.compile(r"Mesário \d+ habilitou o eleitor")
EVENTO_VOTO = "O voto do eleitor foi computado"
EVENTO_ID = "Identificador do eleitor digitado pelo mesário"


def _log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


# ---------------------------------------------------------------------------
# A. BU and BU image
# ---------------------------------------------------------------------------

def dados_bu(raw: bytes) -> dict:
    """President figures and enablement counts of a binary BU (spec v2)."""
    from dataurnas.models import SpecVersion, TipoVoto
    from dataurnas.parsers.asn1_helper import decode_envelope
    from dataurnas.parsers.bu import BUParser

    env, bu = decode_envelope(raw, "EntidadeBoletimUrna", SpecVersion.V2)
    b = BUParser()._build_bu(env, bu, SpecVersion.V2)
    det = bu.get("detalhamentoComparecimento") or {}
    out = {"bu_hab_biometrica": det.get("qtdEleitoresHabilitadosPorBiometria"),
           "bu_hab_biografica": det.get("qtdEleitoresHabilitadosPorBiografia"),
           "bu_hab_sem_biometria": det.get("qtdEleitoresCompareceramSemBiometria"),
           "bu_codigo_ue": b.numero_interno, "bu_tipo_urna": b.tipo_urna,
           "bu_tipo_arquivo": b.tipo_arquivo, "bu_candidatos": None}
    for res in b.resultados_por_eleicao:
        for rc in res.resultados:
            if rc.codigo_cargo != CARGO_PRESIDENTE:
                continue
            cand: Counter = Counter()
            br = nu = outros = 0
            for v in rc.votos:
                q = int(v.quantidade or 0)
                if v.tipo_voto == TipoVoto.NOMINAL:
                    cand[int(v.codigo_votavel)] += q
                elif v.tipo_voto == TipoVoto.BRANCO:
                    br += q
                elif v.tipo_voto == TipoVoto.NULO:
                    nu += q
                else:
                    outros += q
            out.update({"bu_aptos": int(res.eleitores_aptos or 0),
                        "bu_comparecimento": int(rc.comparecimento or 0),
                        "bu_candidatos": {k: v for k, v in cand.items() if v},
                        "bu_nominais": sum(cand.values()), "bu_brancos": br, "bu_nulos": nu,
                        "bu_outros_votos": outros})
    return out


def dados_imgbu(raw: bytes) -> dict:
    """President figures and header counts of the printed BU image."""
    from dataurnas.parsers.imgbu import parse_imgbu

    r = parse_imgbu(raw)
    cab, blocos = r["cabecalho"], r["cargos"].get("PRESIDENTE") or []
    out = {f"img_cab_{k}": cab.get(k) for k in
           ("aptos", "comparecimento", "hab_biometrica", "hab_biografica",
            "hab_sem_biometria", "faltosos", "codigo_ue")}
    out["img_hora_fechamento"] = cab.get("hora_fechamento")
    out["img_blocos_presidente"] = len(blocos)
    p = blocos[0] if blocos else {}
    out["img_candidatos"] = {k: v for k, v in p.get("candidatos", {}).items() if v} or None
    for k in ("aptos", "nominais", "brancos", "nulos", "total_apurado"):
        out[f"img_{k}"] = p.get(k)
    return out


# (BU image field, binary BU field) pairs compared in A.
PARES_A = [
    ("img_candidatos", "bu_candidatos"),
    ("img_brancos", "bu_brancos"),
    ("img_nulos", "bu_nulos"),
    ("img_nominais", "bu_nominais"),
    ("img_total_apurado", "bu_comparecimento"),
    ("img_aptos", "bu_aptos"),
    ("img_cab_aptos", "bu_aptos"),
    ("img_cab_comparecimento", "bu_comparecimento"),
    ("img_cab_hab_biometrica", "bu_hab_biometrica"),
    ("img_cab_hab_biografica", "bu_hab_biografica"),
    ("img_cab_hab_sem_biometria", "bu_hab_sem_biometria"),
    ("img_cab_codigo_ue", "bu_codigo_ue"),
]


def comparar_a(img: dict, bu: dict) -> list[str]:
    """Names of the A fields whose two sides differ (or are missing on one side)."""
    out = []
    for a, b in PARES_A:
        va, vb = img.get(a), bu.get(b)
        if va is None and vb is None:
            continue
        if a == "img_candidatos":
            va, vb = dict(va or {}), dict(vb or {})
        elif va is not None and vb is not None:
            va, vb = int(va), int(vb)
        if va != vb:
            out.append(a.removeprefix("img_"))
    return out


# ---------------------------------------------------------------------------
# B. Voter by voter log
# ---------------------------------------------------------------------------

def _seg(hora: str) -> int:
    return int(hora[0:2]) * 3600 + int(hora[3:5]) * 60 + int(hora[6:8])


def _classe(ep: dict) -> str:
    """Enablement class of a closed episode (rules of biometria_t1_t2.ler_log)."""
    if ep["tipo"] is not None and "biom" in ep["tipo"]:
        return "bio"
    if ep["manual"] or ep["mesario"]:
        return "biog" if ep["solicita"] else "manual_sem_digital"
    if ep["solicita"] == 0:
        return "sem_digital"
    return "outro"


def metricas_log(texto: str, data: str, offset: int) -> tuple[dict, Counter]:
    """Per-voter metrics of one log on one day.

    offset: local time minus Brasilia time, in hours (timezones.get_tz_offset);
    local seconds - offset * 3600 gives Brasilia seconds.

    Returns (metrics, events) where events counts non-INFO lines of the day by
    (level, application, message with digits replaced by N).
    """
    # every count column exists even when zero, so UF files share one schema
    m: Counter = Counter({k: 0 for k in (
        "rajadas", "rajadas_votos", "rajadas_sem_bio", "rajadas_so_sem_bio", "rajadas_sb",
        "rajadas_sb_votos", "rajadas_sb_sem_bio", "rajadas_sb_so_sem_bio", "maior_rajada",
        "votos_ultima_hora", "sem_bio_ultima_hora", "votos_apos_17h", "sem_bio_apos_17h",
        "linhas_erro", "suspensos", "mesario_indagado", "ep_nao_habilitado",
        *(f"{p}_{c}" for p in ("hab", "votos") for c in ("bio", *SEM_BIO)))})
    eventos: Counter = Counter()
    votos: list[tuple[int, str, str]] = []   # (local seconds, machine, class)
    ep: Optional[dict] = None
    pendente: Optional[str] = None
    urna_atual: Optional[str] = None
    for ln in texto.split("\n"):
        if not ln.startswith(data):
            continue
        p = ln.split("\t")
        if len(p) < 5:
            continue
        nivel, urna, app, msg = p[1], p[2], p[3], p[4]
        if nivel != "INFO":
            m["linhas_" + nivel.lower()] += 1
            eventos[(nivel, app, RE_NUM.sub("N", msg)[:200])] += 1
        if app != "VOTA":
            continue
        if urna != urna_atual:      # machine swap: episodes do not cross machines
            ep, pendente, urna_atual = None, None, urna
        if msg.startswith(EVENTO_ID):
            if ep is not None:
                m["ep_nao_habilitado"] += 1
            ep = {"solicita": 0, "tipo": None, "manual": False, "mesario": False}
            continue
        if msg == EVENTO_VOTO:
            votos.append((_seg(p[0][11:19]), urna, pendente or "desconhecido"))
            pendente = None
            continue
        if msg.startswith("Eleitor foi suspenso"):
            m["suspensos"] += 1
        elif msg.startswith("Mesário indagado se eleitor está votando"):
            m["mesario_indagado"] += 1
        if ep is None:
            continue
        if msg.startswith("Solicita digital. Tentativa"):
            ep["solicita"] += 1
        elif msg.startswith("Tipo de habilitação do eleitor"):
            t = RE_TIPO.search(msg)
            ep["tipo"] = t.group(1) if t else msg
        elif msg.startswith("Solicitação de dado pessoal do eleitor para habilitação manual"):
            ep["manual"] = True
        elif RE_MESARIO.match(msg):
            ep["mesario"] = True
        elif msg == "Eleitor foi habilitado":
            pendente = _classe(ep)
            m["hab_" + pendente] += 1
            ep = None
    if ep is not None:
        m["ep_nao_habilitado"] += 1

    n = len(votos)
    m["votos_log"] = n
    for _, _, c in votos:
        m["votos_" + c] += 1
    m["votos_sem_bio"] = sum(1 for _, _, c in votos if c != "bio")
    # windows in Brasilia time
    ult_ini, fim = 16 * 3600, 17 * 3600
    for t, _, c in votos:
        b = t - offset * 3600
        sb = c != "bio"
        if ult_ini <= b < fim:
            m["votos_ultima_hora"] += 1
            m["sem_bio_ultima_hora"] += sb
        elif b >= fim:
            m["votos_apos_17h"] += 1
            m["sem_bio_apos_17h"] += sb
    # rapid runs: consecutive votes on the same machine, each gap < JANELA_RAJADA_S
    gaps: list[int] = []

    def fechar_corrida(corrida: list[str], prefixo: str) -> None:
        if len(corrida) < MIN_RAJADA:
            return
        sb = sum(1 for c in corrida if c != "bio")
        m[prefixo] += 1
        m[prefixo + "_votos"] += len(corrida)
        m[prefixo + "_sem_bio"] += sb
        if sb == len(corrida):
            m[prefixo + "_so_sem_bio"] += 1
        m["maior_rajada"] = max(m["maior_rajada"], len(corrida))

    corrida: list[str] = []
    corrida_sb: list[str] = []
    seq_sb = maior_seq_sb = 0
    for i, (t, u, c) in enumerate(votos):
        if i == 0 or u != votos[i - 1][1]:
            fechar_corrida(corrida, "rajadas")
            fechar_corrida(corrida_sb, "rajadas_sb")
            corrida, corrida_sb, seq_sb = [], [], 0
            rapido = False
        else:
            d = t - votos[i - 1][0]
            gaps.append(d)
            rapido = 0 <= d < JANELA_RAJADA_S
        if not rapido:
            fechar_corrida(corrida, "rajadas")
            corrida = []
        corrida.append(c)
        if c != "bio":
            seq_sb += 1
            if not rapido:
                fechar_corrida(corrida_sb, "rajadas_sb")
                corrida_sb = []
            corrida_sb.append(c)
        else:
            seq_sb = 0
            fechar_corrida(corrida_sb, "rajadas_sb")
            corrida_sb = []
        maior_seq_sb = max(maior_seq_sb, seq_sb)
    fechar_corrida(corrida, "rajadas")
    fechar_corrida(corrida_sb, "rajadas_sb")
    m["maior_seq_sem_bio"] = maior_seq_sb
    m["gaps_lt_30s"] = sum(1 for d in gaps if 0 <= d < JANELA_RAJADA_S)
    m["gaps_lt_10s"] = sum(1 for d in gaps if 0 <= d < 10)
    gs = sorted(d for d in gaps if d >= 0)
    m["gap_mediana_s"] = gs[len(gs) // 2] if gs else -1
    return dict(m), eventos


# ---------------------------------------------------------------------------
# Section worker
# ---------------------------------------------------------------------------

_ZIPS: dict[str, zipfile.ZipFile] = {}


def _zip(path: str) -> zipfile.ZipFile:
    # Close handles of zips already deleted: an open handle keeps the file in RAM.
    for k in [k for k in _ZIPS if k != path and not os.path.exists(k)]:
        _ZIPS.pop(k).close()
    z = _ZIPS.get(path)
    if z is None:
        z = _ZIPS[path] = zipfile.ZipFile(path)
    return z


def processar_secao(args: tuple) -> tuple[dict, Counter]:
    """All A and B figures of one section and round."""
    from dataurnas.analyzer.rdv_recontagem import analisar_log_tempo, texto_log
    from dataurnas.analyzer.timezones import get_tz_offset

    path, turno, chave, membros = args
    uf, mun, zona, secao = chave
    z = _zip(path)
    row: dict = {"uf": uf, "cd_mun": mun, "zona": zona, "secao": secao, "turno": turno,
                 "tem_bu": "bu.dat" in membros, "tem_imgbu": "imgbu.dat" in membros,
                 "tem_log": "log.jez" in membros}
    eventos: Counter = Counter()
    bu: dict = {}
    img: dict = {}
    if row["tem_bu"]:
        try:
            bu = dados_bu(z.read(membros["bu.dat"]))
        except Exception as e:  # noqa: BLE001
            row["erro_bu"] = f"{type(e).__name__}: {e}"[:200]
    if row["tem_imgbu"]:
        try:
            img = dados_imgbu(z.read(membros["imgbu.dat"]))
        except Exception as e:  # noqa: BLE001
            row["erro_imgbu"] = f"{type(e).__name__}: {e}"[:200]
    row.update(bu)
    row.update(img)
    for k in ("bu_candidatos", "img_candidatos"):
        if row.get(k) is not None:
            row[k] = json.dumps({str(a): b for a, b in sorted(row[k].items())})
    cand = bu.get("bu_candidatos") or {}
    row["bu_v13"], row["bu_v22"] = cand.get(13, 0), cand.get(22, 0)
    if bu and img:
        div = comparar_a(img, bu)
        row["a_divergencias"] = ",".join(div)
        row["a_confere"] = not div
    if row["tem_log"]:
        try:
            texto = texto_log(z.read(membros["log.jez"]))
        except Exception as e:  # noqa: BLE001
            texto = None
            row["erro_log"] = f"{type(e).__name__}: {e}"[:200]
        if texto:
            offset = 0 if uf == "zz" else get_tz_offset(uf, mun)
            met, eventos = metricas_log(texto, DATA[turno], offset)
            row.update({f"log_{k}": v for k, v in met.items()})
            t = analisar_log_tempo(texto, uf, mun, bu.get("bu_comparecimento"),
                                   data_eleicao=DATA[turno],
                                   datas_anteriores=(DATA[1],) if turno == 2 else ())
            for k in ("aberturas", "n_urnas_log", "votos_antes_8h", "votos_apos_17h",
                      "votos_antes_pronta", "votos_apos_encerramento", "votos_outras_datas",
                      "lacunas_60min", "inversoes_relogio", "ajustes_hora", "hora_pronta",
                      "hora_encerramento", "primeiro_voto", "ultimo_voto",
                      "ultimo_voto_brasilia", "max_votos_minuto"):
                row[f"tempo_{k}"] = t.get(k)
        elif "erro_log" not in row:
            row["erro_log"] = "ilegivel"
    return row, eventos


# ---------------------------------------------------------------------------
# processar
# ---------------------------------------------------------------------------

def baixar(uf: str, turno: int, destino: Path) -> Path:
    """Stream one UF zip into destino (RAM disk), resuming on errors."""
    url = URL.format(t=turno, uf=uf)
    alvo = destino / Path(url).name
    parcial = alvo.with_suffix(".part")
    with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=60) as r:
        total = int(r.headers["Content-Length"])
    espera = 5
    while True:
        feito = parcial.stat().st_size if parcial.exists() else 0
        if feito >= total:
            break
        req = urllib.request.Request(url, headers={"Range": f"bytes={feito}-"})
        try:
            with urllib.request.urlopen(req, timeout=120) as r, open(parcial, "ab") as f:
                while True:
                    bloco = r.read(8 << 20)
                    if not bloco:
                        break
                    f.write(bloco)
            espera = 5
        except urllib.error.HTTPError as e:
            if e.code in (403, 429):
                _log(f"{uf} {turno}t: HTTP {e.code}, waiting {espera * 6}s")
                time.sleep(espera * 6)
            else:
                raise
            espera = min(espera * 2, 120)
        except OSError as e:
            _log(f"{uf} {turno}t: {type(e).__name__} {e}, resuming in {espera}s")
            time.sleep(espera)
            espera = min(espera * 2, 120)
    parcial.rename(alvo)
    return alvo


def velocidade(uf: str, turno: int, n: int = 4 << 20) -> float:
    """MB/s of a 4 MB range taken from the middle of the zip (one connection)."""
    url = URL.format(t=turno, uf=uf)
    try:
        with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=60) as r:
            meio = int(r.headers["Content-Length"]) // 2
        t0 = time.time()
        req = urllib.request.Request(url, headers={"Range": f"bytes={meio}-{meio + n - 1}"})
        with urllib.request.urlopen(req, timeout=60) as r:
            got = len(r.read())
        return got / 1e6 / max(time.time() - t0, 1e-3)
    except OSError:
        return 0.0


def tarefas_zip(path: Path, turno: int) -> list[tuple]:
    secoes: dict[tuple, dict] = defaultdict(dict)
    with zipfile.ZipFile(path) as z:
        for nome in z.namelist():
            m = NOME_RE.match(nome)
            if m and int(m.group(1)) == turno - 1:
                secoes[m.group(2, 3, 4, 5)][m.group(6)] = nome
    return [(str(path), turno, k, v) for k, v in sorted(secoes.items())]


def processar_uf(uf: str, turno: int, saida: Path, tmp: Path, ex: ProcessPoolExecutor,
                 sem_download: threading.Semaphore) -> None:
    import pandas as pd

    final = saida / f"secoes_{uf.lower()}_{turno}.parquet"
    if final.exists():
        _log(f"{uf} {turno}t: already done")
        return
    t0 = time.time()
    with sem_download:
        path = baixar(uf, turno, tmp)
    mb = path.stat().st_size / 1e6
    _log(f"{uf} {turno}t: downloaded {mb:.0f} MB in {time.time() - t0:.0f}s")
    try:
        tarefas = tarefas_zip(path, turno)
        linhas, ev_ocorr, ev_secoes = [], Counter(), Counter()
        t1 = time.time()
        for i, (row, ev) in enumerate(ex.map(processar_secao, tarefas, chunksize=16), 1):
            linhas.append(row)
            ev_ocorr.update(ev)
            ev_secoes.update(ev.keys())
            if i % 20000 == 0:
                _log(f"{uf} {turno}t: {i}/{len(tarefas)} sections")
        ev_rows = [{"uf": uf.lower(), "turno": turno, "nivel": k[0], "aplicacao": k[1],
                    "mensagem": k[2], "ocorrencias": n, "secoes": ev_secoes[k]}
                   for k, n in ev_ocorr.items()]
        pd.DataFrame(ev_rows).to_parquet(saida / f"eventos_{uf.lower()}_{turno}.parquet",
                                         index=False)
        pd.DataFrame(linhas).to_parquet(final.with_suffix(".tmp"), index=False)
        final.with_suffix(".tmp").rename(final)
        div = sum(1 for r in linhas if r.get("a_confere") is False)
        dlog = sum(1 for r in linhas if r.get("log_votos_log") is not None
                   and r.get("bu_comparecimento") is not None
                   and r["log_votos_log"] != r["bu_comparecimento"])
        _log(f"{uf} {turno}t: {len(linhas)} sections in {time.time() - t1:.0f}s; "
             f"imgbu x bu divergent {div}; log x bu votes divergent {dlog}")
    finally:
        path.unlink(missing_ok=True)


def cmd_sa(a: argparse.Namespace) -> None:
    """A for the counting system sections (paper or mixed ballots).

    These sections have -busa.dat and -imgbusa.dat instead of -bu.dat and
    -imgbu.dat (and no voting machine log of the day). They are few, so the two
    members are read through HTTP Range requests from the published zip.
    """
    import pandas as pd

    sys.path.insert(0, str(ROOT / "scripts" / "ele2026"))
    from confronto_pacote_t2 import HttpRangeFile

    saida = Path(a.saida).expanduser()
    linhas = []
    for arq in sorted(saida.glob("secoes_*_*.parquet")):
        d = pd.read_parquet(arq, columns=CHAVES + ["turno", "tem_bu"])
        d = d[~d["tem_bu"]]
        if d.empty:
            continue
        uf, turno = d["uf"].iloc[0], int(d["turno"].iloc[0])
        z = zipfile.ZipFile(HttpRangeFile(URL.format(t=turno, uf=uf.upper())))
        nomes = set(z.namelist())
        for r in d.to_dict("records"):
            base = f"o0322{turno - 1}{r['uf']}{r['cd_mun']}{r['zona']}{r['secao']}-"
            row = {**{k: r[k] for k in CHAVES}, "turno": turno,
                   "tem_busa": base + "busa.dat" in nomes,
                   "tem_imgbusa": base + "imgbusa.dat" in nomes}
            bu = dados_bu(z.read(base + "busa.dat")) if row["tem_busa"] else {}
            img = dados_imgbu(z.read(base + "imgbusa.dat")) if row["tem_imgbusa"] else {}
            row.update({k: v for k, v in bu.items() if k != "bu_candidatos"})
            row.update({k: v for k, v in img.items() if k != "img_candidatos"})
            row["bu_candidatos"] = json.dumps({str(k): v for k, v in
                                               sorted((bu.get("bu_candidatos") or {}).items())})
            row["img_candidatos"] = json.dumps({str(k): v for k, v in
                                                sorted((img.get("img_candidatos") or {}).items())})
            cand = bu.get("bu_candidatos") or {}
            row["bu_v13"], row["bu_v22"] = cand.get(13, 0), cand.get(22, 0)
            # the counting system print has no turnout or enablement lines in the
            # header: only fields the image actually prints are compared
            div = ([x for x in comparar_a(img, bu) if img.get("img_" + x) is not None]
                   if bu and img else ["arquivo_ausente"])
            row["a_divergencias"], row["a_confere"] = ",".join(div), not div
            linhas.append(row)
        _log(f"sa {uf} {turno}t: {len(d)} sections")
    pd.DataFrame(linhas).to_parquet(saida / "sa_secoes.parquet", index=False)
    _log(f"sa: {len(linhas)} sections, divergent "
         f"{sum(1 for r in linhas if not r['a_confere'])}")


def cmd_processar(a: argparse.Namespace) -> None:
    saida = Path(a.saida).expanduser()
    tmp = Path(a.tmp)
    saida.mkdir(parents=True, exist_ok=True)
    tmp.mkdir(parents=True, exist_ok=True)
    ufs = [u.strip().upper() for u in a.ufs.split(",")] if a.ufs else UFS
    turnos = [int(t) for t in a.turnos.split(",")]
    # big UFs first so they do not end up alone at the tail
    peso = {"SP": 0, "MG": 1, "RJ": 2, "BA": 3, "RS": 4, "PR": 5, "PE": 6, "CE": 7}
    jobs = sorted(((u, t) for u in ufs for t in turnos), key=lambda j: (peso.get(j[0], 99), j))
    if a.por_velocidade:
        # Files already in the CDN cache come at tens of MB/s, the others at
        # about 0.6 MB/s per connection: fetch the fast ones first.
        vel = {j: velocidade(*j) for j in jobs
               if not (saida / f"secoes_{j[0].lower()}_{j[1]}.parquet").exists()}
        _log("speed MB/s: " + " ".join(f"{u}{t}:{v:.1f}" for (u, t), v in vel.items()))
        jobs = sorted(jobs, key=lambda j: -vel.get(j, 0))
    sem = threading.Semaphore(a.downloads)
    with ProcessPoolExecutor(a.workers) as ex, ThreadPoolExecutor(a.paralelo) as th:
        futs = [th.submit(processar_uf, u, t, saida, tmp, ex, sem) for u, t in jobs]
        for f in futs:
            try:
                f.result()
            except Exception as e:  # noqa: BLE001
                _log(f"job failed: {type(e).__name__}: {e}")
    _log("processar: done")


# ---------------------------------------------------------------------------
# relatorio
# ---------------------------------------------------------------------------

def _r(x, n: int = 4):
    if x is None:
        return None
    try:
        x = float(x)
    except (TypeError, ValueError):
        return x
    if math.isnan(x) or math.isinf(x):
        return None
    return round(x, n)


def ols_fe(df, y: str, xs: list[str], grupo: str) -> dict:
    """OLS of y on xs with group fixed effects (within transform) and
    standard errors clustered by group."""
    import numpy as np

    d = df[[y, *xs, grupo]].dropna()
    g = d[grupo]
    Y = (d[y] - d.groupby(grupo)[y].transform("mean")).to_numpy(float)
    X = np.column_stack([(d[x] - d.groupby(grupo)[x].transform("mean")).to_numpy(float)
                         for x in xs])
    XtX_inv = np.linalg.pinv(X.T @ X)
    beta = XtX_inv @ X.T @ Y
    e = Y - X @ beta
    meat = np.zeros((len(xs), len(xs)))
    codes = g.astype("category").cat.codes.to_numpy()
    S = np.zeros((codes.max() + 1, len(xs)))
    np.add.at(S, codes, X * e[:, None])
    meat = S.T @ S
    G, n, k = codes.max() + 1, len(Y), len(xs)
    c = G / (G - 1) * (n - 1) / (n - k) if G > 1 and n > k else 1.0
    V = c * XtX_inv @ meat @ XtX_inv
    se = np.sqrt(np.diag(V))
    out = {"n": int(n), "grupos": int(G), "coef": {}}
    for i, x in enumerate(xs):
        t = beta[i] / se[i] if se[i] > 0 else float("nan")
        p = math.erfc(abs(t) / math.sqrt(2)) if not math.isnan(t) else None
        out["coef"][x] = {"beta": _r(beta[i], 6), "ep": _r(se[i], 6), "t": _r(t, 3),
                          "p": _r(p, 6)}
    return out


def md_tabela(df) -> str:
    cols = list(df.columns)
    linhas = ["| " + " | ".join(map(str, cols)) + " |", "|" + "---|" * len(cols)]
    for r in df.itertuples(index=False):
        linhas.append("| " + " | ".join("" if v is None else str(v) for v in r) + " |")
    return "\n".join(linhas)


def cmd_relatorio(a: argparse.Namespace) -> None:
    import numpy as np
    import pandas as pd

    saida = Path(a.saida).expanduser()
    repo = Path(a.repo).expanduser()
    repo.mkdir(parents=True, exist_ok=True)
    df = pd.concat([pd.read_parquet(p) for p in sorted(saida.glob("secoes_*_*.parquet"))],
                   ignore_index=True)
    ev = pd.concat([pd.read_parquet(p) for p in sorted(saida.glob("eventos_*_*.parquet"))],
                   ignore_index=True)
    df["chave"] = df["uf"] + "/" + df["cd_mun"] + "/" + df["zona"] + "/" + df["secao"]
    lido = df["log_votos_log"].notna()
    for c in [c for c in df.columns if c.startswith("log_") and c != "log_gap_mediana_s"]:
        df[c] = df[c].fillna(0)   # metrics absent from a read log are zero counts
    df.loc[~lido, "log_votos_log"] = np.nan
    res: dict = {"secoes_por_turno": {}, "A": {}, "B": {}}
    ext: dict[str, pd.DataFrame] = {}

    for t, g in df.groupby("turno"):
        t = int(t)
        res["secoes_por_turno"][t] = int(len(g))
        # ---- A
        comp = g[g["a_confere"].notna()]
        div = comp[comp["a_confere"] == False]  # noqa: E712
        cont = Counter(x for s in div["a_divergencias"] for x in s.split(",") if x)
        res["A"][t] = {
            "secoes": int(len(g)), "com_bu": int(g["tem_bu"].sum()),
            "com_imgbu": int(g["tem_imgbu"].sum()),
            "erro_bu": int(g.get("erro_bu", pd.Series(dtype=str)).notna().sum()),
            "erro_imgbu": int(g.get("erro_imgbu", pd.Series(dtype=str)).notna().sum()),
            "imgbu_sem_bloco_presidente": int((g["img_blocos_presidente"] == 0).sum()),
            "comparadas": int(len(comp)), "divergentes": int(len(div)),
            "divergencias_por_campo": dict(cont),
            "soma_bu_v13": int(g["bu_v13"].sum()), "soma_bu_v22": int(g["bu_v22"].sum()),
            "soma_bu_brancos": int(g["bu_brancos"].sum()),
            "soma_bu_nulos": int(g["bu_nulos"].sum()),
            "soma_bu_comparecimento": int(g["bu_comparecimento"].sum()),
            # image sums only over the compared sections (both files present)
            "soma_img_v13": int(sum(json.loads(s).get("13", 0) for s in comp["img_candidatos"])),
            "soma_img_v22": int(sum(json.loads(s).get("22", 0) for s in comp["img_candidatos"])),
            "soma_img_brancos": int(comp["img_brancos"].sum()),
            "soma_img_nulos": int(comp["img_nulos"].sum()),
            "soma_img_total_apurado": int(comp["img_total_apurado"].sum()),
            "imgbu_sem_bu": int((g["tem_imgbu"] & ~g["tem_bu"]).sum()),
        }
        ext[f"a_divergentes_t{t}"] = div
        if (saida / "sa_secoes.parquet").exists():
            sa = pd.read_parquet(saida / "sa_secoes.parquet")
            sa = sa[sa["turno"] == t]
            res["A"][t]["sa"] = {
                "secoes": int(len(sa)), "com_busa_e_imgbusa":
                int((sa["tem_busa"] & sa["tem_imgbusa"]).sum()),
                "divergentes": int((~sa["a_confere"]).sum()),
                "divergencias": sa.loc[~sa["a_confere"], "a_divergencias"].tolist(),
                "soma_v13": int(sa["bu_v13"].sum()), "soma_v22": int(sa["bu_v22"].sum()),
                "soma_brancos": int(sa["bu_brancos"].fillna(0).sum()),
                "soma_nulos": int(sa["bu_nulos"].fillna(0).sum()),
                "soma_comparecimento": int(sa["bu_comparecimento"].fillna(0).sum())}
            res["A"][t]["total_v13_com_sa"] = res["A"][t]["soma_bu_v13"] + int(sa["bu_v13"].sum())
            res["A"][t]["total_v22_com_sa"] = res["A"][t]["soma_bu_v22"] + int(sa["bu_v22"].sum())
        # ---- B
        lg = g[g["log_votos_log"].notna()].copy()
        votos = lg["log_votos_log"].astype(int)
        compb = lg["bu_comparecimento"]
        dlog = lg[votos != compb]
        hb = ((lg["log_hab_bio"] == lg["bu_hab_biometrica"])).sum()
        soma = {k: int(lg[k].sum()) for k in lg.columns if k.startswith("log_")
                and k not in ("log_gap_mediana_s", "log_maior_rajada", "log_maior_seq_sem_bio")
                and not k.removeprefix("log_linhas_").isdigit()}  # malformed level column
        res["B"][t] = {
            "secoes_com_log": int(g["tem_log"].sum()),
            "logs_lidos": int(len(lg)),
            "erro_log": int(g.get("erro_log", pd.Series(dtype=str)).notna().sum()),
            "votos_log_igual_comparecimento": int((votos == compb).sum()),
            "votos_log_diferente": int(len(dlog)),
            "soma_votos_log": int(votos.sum()), "soma_comparecimento_bu": int(compb.sum()),
            "hab_bio_log_igual_bu": int(hb),
            "soma_bu_hab_biometrica": int(lg["bu_hab_biometrica"].sum()),
            "soma_bu_hab_biografica": int(lg["bu_hab_biografica"].sum()),
            "soma_bu_hab_sem_biometria": int(lg["bu_hab_sem_biometria"].sum()),
            "somas_log": soma,
            "pct_votos_sem_bio": _r(100 * soma["log_votos_sem_bio"] / max(1, votos.sum())),
            "secoes_com_rajada": int((lg["log_rajadas"] > 0).sum()),
            "secoes_com_rajada_so_sem_bio": int((lg["log_rajadas_so_sem_bio"] > 0).sum()),
            "secoes_com_rajada_sb": int((lg["log_rajadas_sb"] > 0).sum()),
            "secoes_reinicio": int((lg["tempo_aberturas"] > 1).sum()),
            "secoes_troca_urna": int((lg["tempo_n_urnas_log"] > 1).sum()),
            "secoes_voto_antes_8h": int((lg["tempo_votos_antes_8h"] > 0).sum()),
            "secoes_voto_apos_encerramento": int((lg["tempo_votos_apos_encerramento"] > 0).sum()),
            "secoes_voto_antes_pronta": int((lg["tempo_votos_antes_pronta"] > 0).sum()),
            "secoes_voto_outras_datas": int((lg["tempo_votos_outras_datas"] > 0).sum()),
            "secoes_relogio_inverso": int((lg["tempo_inversoes_relogio"] > 0).sum()),
            "secoes_com_linha_erro": int((lg.get("log_linhas_erro", 0) > 0).sum()),
            "maior_rajada": int(lg["log_maior_rajada"].max()),
            "maior_seq_sem_bio": int(lg["log_maior_seq_sem_bio"].max()),
        }
        ext[f"b_votos_log_diferente_t{t}"] = dlog
        ext[f"arquivo_faltando_t{t}"] = g[~(g["tem_bu"] & g["tem_imgbu"] & g["tem_log"])]

    # events vocabulary (non-INFO lines)
    voc = (ev.groupby(["turno", "nivel", "aplicacao", "mensagem"], as_index=False)
           [["ocorrencias", "secoes"]].sum().sort_values(["turno", "ocorrencias"],
                                                         ascending=[True, False]))
    voc.to_csv(repo / "eventos_nao_info.csv", index=False)
    res["eventos_erro_top"] = {
        int(t): g[g["nivel"] == "ERRO"].head(15)[["aplicacao", "mensagem", "ocorrencias",
                                                  "secoes"]].to_dict("records")
        for t, g in voc.groupby("turno")}

    # ---- pairing 1st x 2nd round
    cols = ["chave", "uf", "cd_mun", "bu_v13", "bu_v22", "bu_comparecimento", "log_votos_log",
            "log_votos_sem_bio", "log_rajadas_votos", "log_rajadas_sem_bio",
            "log_rajadas_so_sem_bio", "log_rajadas_sb_votos", "log_sem_bio_ultima_hora",
            "log_sem_bio_apos_17h", "log_votos_apos_17h", "log_votos_ultima_hora",
            "log_maior_seq_sem_bio", "tempo_n_urnas_log", "tempo_aberturas"]
    p1 = df[df["turno"] == 1][cols].set_index("chave")
    p2 = df[df["turno"] == 2][cols].set_index("chave")
    p = p1.join(p2.drop(columns=["uf", "cd_mun"]), lsuffix="_1", rsuffix="_2", how="inner")
    p = p[(p["log_votos_log_1"] > 0) & (p["log_votos_log_2"] > 0)]
    for k in (1, 2):
        s = p[f"bu_v13_{k}"] + p[f"bu_v22_{k}"]
        p[f"fatia13_{k}"] = np.where(s > 0, p[f"bu_v13_{k}"] / s.where(s > 0, 1), np.nan)
        v = p[f"log_votos_log_{k}"]
        p[f"tx_sem_bio_{k}"] = p[f"log_votos_sem_bio_{k}"] / v
        p[f"tx_rajada_{k}"] = p[f"log_rajadas_votos_{k}"] / v
        p[f"tx_rajada_sb_{k}"] = p[f"log_rajadas_sb_votos_{k}"] / v
        p[f"tx_sb_tarde_{k}"] = (p[f"log_sem_bio_ultima_hora_{k}"]
                                 + p[f"log_sem_bio_apos_17h_{k}"]) / v
    p["swing"] = p["fatia13_2"] - p["fatia13_1"]
    for x in ("sem_bio", "rajada", "rajada_sb", "sb_tarde"):
        p[f"d_{x}"] = p[f"tx_{x}_2"] - p[f"tx_{x}_1"]
    p["mun"] = p["uf"] + p["cd_mun"]
    p["peso"] = p["bu_comparecimento_2"]
    base = p[(p["bu_comparecimento_1"] >= 20) & (p["bu_comparecimento_2"] >= 20)
             & p["swing"].notna()]
    reg = {}
    for x in ("d_sem_bio", "d_rajada", "d_rajada_sb", "d_sb_tarde"):
        reg[x] = ols_fe(base, "swing", [x], "mun")
    reg["conjunto"] = ols_fe(base, "swing", ["d_sem_bio", "d_rajada", "d_rajada_sb",
                                             "d_sb_tarde"], "mun")
    # top-1% increase vs the rest, within municipality; when the 99th percentile
    # is zero (rare event), the marker is "any increase"
    for x in ("d_sem_bio", "d_rajada", "d_rajada_sb"):
        lim = base[x].quantile(0.99)
        marca = base[x] >= lim if lim > 0 else base[x] > 0
        base = base.assign(**{f"top_{x}": marca.astype(float)})
        reg[f"top1pct_{x}"] = {**ols_fe(base, "swing", [f"top_{x}"], "mun"),
                               "limiar": _r(lim, 6), "secoes_marcadas": int(marca.sum())}
    dec = []
    # swing minus the municipality mean, so deciles compare sections of one place
    base = base.assign(swing_dm=base["swing"] - base.groupby("mun")["swing"].transform("mean"))
    for x in ("d_sem_bio", "d_rajada"):
        q = pd.qcut(base[x].rank(method="first"), 10, labels=False)
        for i, g in base.groupby(q):
            w = g["swing_dm"]
            dec.append({"variavel": x, "decil": int(i) + 1, "secoes": int(len(g)),
                        "x_media_pp": _r(100 * g[x].mean(), 3),
                        "swing_medio_pp": _r(100 * g["swing"].mean(), 3),
                        "swing_vs_municipio_pp": _r(100 * w.mean(), 3)})
    res["pareamento"] = {
        "secoes_pareadas": int(len(p)), "base_regressao": int(len(base)),
        "municipios": int(base["mun"].nunique()),
        "media_tx_sem_bio_1": _r(p["tx_sem_bio_1"].mean()),
        "media_tx_sem_bio_2": _r(p["tx_sem_bio_2"].mean()),
        "media_tx_rajada_1": _r(p["tx_rajada_1"].mean()),
        "media_tx_rajada_2": _r(p["tx_rajada_2"].mean()),
        "swing_medio_pp": _r(100 * base["swing"].mean(), 3),
        "regressoes": reg, "decis": dec,
        "votos_sem_bio_1": int(p["log_votos_sem_bio_1"].sum()),
        "votos_sem_bio_2": int(p["log_votos_sem_bio_2"].sum()),
        "votos_rajadas_so_sem_bio_secoes_2": int((p["log_rajadas_so_sem_bio_2"] > 0).sum()),
    }
    pq_cols = ["swing", "fatia13_1", "fatia13_2", "tx_sem_bio_1", "tx_sem_bio_2", "d_sem_bio",
               "tx_rajada_1", "tx_rajada_2", "d_rajada", "d_rajada_sb", "d_sb_tarde",
               "bu_comparecimento_1", "bu_comparecimento_2", "log_maior_seq_sem_bio_2",
               "log_rajadas_so_sem_bio_2", "log_sem_bio_apos_17h_2"]
    # per-section pairing (about 20 MB) stays next to the per-section files
    p[pq_cols].reset_index().to_parquet(saida / "pareamento_t1_t2.parquet", index=False)

    # ---- extreme sections
    lst = []
    sel = {
        "maior_aumento_sem_bio": base.nlargest(25, "d_sem_bio"),
        "maior_aumento_rajada_sb": base.nlargest(25, "d_rajada_sb"),
        "maior_seq_sem_bio_t2": p.nlargest(25, "log_maior_seq_sem_bio_2"),
        "mais_sem_bio_apos_17h_t2": p.nlargest(25, "log_sem_bio_apos_17h_2"),
        "maior_swing_abs": base.reindex(base["swing"].abs()
                                        .sort_values(ascending=False).index).head(25),
    }
    for nome, g in sel.items():
        for chave, r in g.iterrows():
            lst.append({"lista": nome, "chave": chave,
                        **{c: _r(r[c], 4) for c in pq_cols}})
    for nome, g in ext.items():
        for r in g.head(500).to_dict("records"):
            lst.append({"lista": nome, "chave": r["chave"],
                        **{k: r.get(k) for k in (
                            "tem_bu", "tem_imgbu", "tem_log",
                            "a_divergencias", "bu_candidatos", "img_candidatos",
                            "bu_comparecimento", "img_total_apurado", "img_cab_comparecimento",
                            "bu_brancos", "img_brancos", "bu_nulos", "img_nulos",
                            "bu_aptos", "img_aptos", "bu_hab_biometrica",
                            "img_cab_hab_biometrica", "bu_hab_biografica",
                            "img_cab_hab_biografica", "bu_hab_sem_biometria",
                            "img_cab_hab_sem_biometria", "bu_codigo_ue", "img_cab_codigo_ue",
                            "log_votos_log", "tempo_n_urnas_log", "tempo_aberturas",
                            "erro_log")}})
    pd.DataFrame(lst).to_csv(repo / "secoes_conferencia.csv", index=False)

    # per-UF table
    por_uf = (df.groupby(["turno", "uf"]).agg(
        secoes=("chave", "size"), a_divergentes=("a_confere", lambda s: int((s == False).sum())),  # noqa: E712
        votos_log=("log_votos_log", "sum"), comparecimento=("bu_comparecimento", "sum"),
        votos_sem_bio=("log_votos_sem_bio", "sum"), rajadas=("log_rajadas", "sum"),
        rajadas_votos=("log_rajadas_votos", "sum"),
        rajadas_so_sem_bio=("log_rajadas_so_sem_bio", "sum"),
        sem_bio_apos_17h=("log_sem_bio_apos_17h", "sum")).reset_index())
    por_uf["pct_sem_bio"] = (100 * por_uf["votos_sem_bio"] / por_uf["votos_log"]).round(3)
    por_uf["pct_em_rajada"] = (100 * por_uf["rajadas_votos"] / por_uf["votos_log"]).round(3)
    por_uf.to_csv(repo / "por_uf.csv", index=False)
    (repo / "resumo.json").write_text(json.dumps(res, indent=2, ensure_ascii=False,
                                                 default=str))
    (repo / "tabelas.md").write_text("## Por UF\n\n" + md_tabela(por_uf) + "\n\n## Decis\n\n"
                                     + md_tabela(pd.DataFrame(dec)) + "\n")
    _log("relatorio: done")
    print(json.dumps({k: v for k, v in res.items() if k != "eventos_erro_top"}, indent=1,
                     ensure_ascii=False, default=str)[:20000])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    pp = sub.add_parser("processar")
    pp.add_argument("--ufs", default="")
    pp.add_argument("--turnos", default="1,2")
    pp.add_argument("--saida", default="~/dataurnas-pacote-nacional")
    pp.add_argument("--tmp", default="/dev/shm/pacote-nacional")
    pp.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 6))
    pp.add_argument("--paralelo", type=int, default=3, help="UF jobs at the same time")
    pp.add_argument("--downloads", type=int, default=2, help="simultaneous downloads")
    pp.add_argument("--por-velocidade", action="store_true",
                    help="probe each zip and fetch the cached (fast) ones first")
    pr = sub.add_parser("relatorio")
    pr.add_argument("--saida", default="~/dataurnas-pacote-nacional")
    pr.add_argument("--repo", default=str(ROOT / "data" / "parquet" / "2026" / "pacote_nacional"))
    ps = sub.add_parser("sa")
    ps.add_argument("--saida", default="~/dataurnas-pacote-nacional")
    a = ap.parse_args()
    {"processar": cmd_processar, "relatorio": cmd_relatorio, "sa": cmd_sa}[a.cmd](a)


if __name__ == "__main__":
    main()
