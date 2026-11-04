#!/usr/bin/env python3
"""Zero-votes report ("zerésima") check in every voting machine log, 2026 rounds.

Before polls open, each voting machine prints the zerésima, a report showing
that no vote is stored. The VOTA application writes it to the machine log
(-log.jez). Strings found by sampling the 2026 logs (AC, 2nd round package):

  Aguardando data e hora para emissão da zerésima      machine booted before the
                                                        day/time that unlocks it
  Aguardando confirmação para emissão da zerésima      unlocked, waiting for the
                                                        presiding officer
  Gerando relatório [ZERÉSIMA] [INÍCIO] / [TÉRMINO]     zerésima generated
  Gerando relatório [RESUMO DA ZERÉSIMA] [INÍCIO] / [TÉRMINO]
  Imprimindo relatório [ZERÉSIMA] via nº [N]           printed copy N
  Imprimindo relatório [RESUMO DA ZERÉSIMA] via nº [N]

Every other message containing "zerésima" is also counted (catalog), so new
variants show up in the summary instead of being silently ignored.

Per section and round, only lines dated on the round day count for the main
checks (the 2nd round log carries the 1st round events). Checks:

  - no zerésima generated on the round day;
  - zerésima after the first vote (by time and, per machine, by file order);
  - zerésima after "Urna pronta para receber votos" of the same machine;
  - zerésima dated on a day other than the two round days;
  - more than one zerésima on the round day, and votes before a later one;
  - votes before the first zerésima of the section;
  - machines with votes but no zerésima of their own (contingency swaps:
    the replacement machine receives the voting media of the failed one and
    continues the count, so it is not expected to print a new zerésima).

Times are the machine's local time. Brasilia time = local - offset hours
(analyzer/timezones.get_tz_offset); abroad (zz) keeps local time.

Download: only the -log.jez members are needed. The zip central directory is
read through HTTP Range requests; consecutive log members are fetched in one
range request (chunks up to --chunk-mb, joining members whose gap is under
--gap-kb), which also brings the small bu/rdv/imgbu/vsc members in between but
is much faster than one request per member. At most --conexoes requests run at
the same time (TSE limit: 4). Each member is checked against the CRC-32 of the
central directory.

Subcommands:
  volume      central directories only: log bytes and bytes to read per zip
  processar   one parquet per UF and round in --saida (zer_<uf>_<t>.parquet)
              plus the message catalog (catalogo_<uf>_<t>.parquet); pairs
              already done are skipped
  relatorio   national summary, anomalies and cross-check with the existing
              per-section results of pacote_nacional.py

Usage (analysis server):
  uv run python scripts/ele2026/zeresima.py volume --saida ~/dataurnas-zeresima
  uv run python scripts/ele2026/zeresima.py processar --saida ~/dataurnas-zeresima
  uv run python scripts/ele2026/zeresima.py relatorio --saida ~/dataurnas-zeresima \\
      --pacote ~/dataurnas-pacote-nacional --repo ~/dataurnas-zeresima/repo
"""

from __future__ import annotations

import argparse
import json
import re
import struct
import sys
import threading
import time
import urllib.error
import urllib.request
import zipfile
import zlib
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT / "src"), str(ROOT / "scripts" / "ele2026")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from confronto_pacote_t2 import HttpRangeFile  # noqa: E402

URL = ("https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2026/arqurnatot/"
       "bu_imgbu_logjez_rdv_vscmr_2026_{t}t_{uf}.zip")
UFS = ("AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO ZZ"
       .split())
DATA = {1: "04/10/2026", 2: "25/10/2026"}
NOME_RE = re.compile(r"^o0322([01])([a-z]{2})(\d{5})(\d{4})(\d{4})-log\.jez$")

ZER_RE = re.compile(r"zer[ée]sima", re.IGNORECASE)
RE_NUM = re.compile(r"\d+")
MSG_ZER_GERA = "Gerando relatório [ZERÉSIMA] [INÍCIO]"
MSG_ZER_IMPRIME = "Imprimindo relatório [ZERÉSIMA] via"
MSG_RESUMO_GERA = "Gerando relatório [RESUMO DA ZERÉSIMA] [INÍCIO]"
MSG_AGUARDA_CONF = "Aguardando confirmação para emissão da zerésima"
EVENTO_PRONTA = "Urna pronta para receber votos"
EVENTO_VOTO = "O voto do eleitor foi computado"
EVENTOS_ENC = ("Inicio do Encerramento", "Início do Encerramento")

LOCAL_HEADER = struct.Struct("<4s2B4HL2L2H")   # zipfile.structFileHeader


def _log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def _seg(hora: str) -> int:
    return int(hora[0:2]) * 3600 + int(hora[3:5]) * 60 + int(hora[6:8])


def _hms(s: Optional[int]) -> Optional[str]:
    if s is None:
        return None
    s %= 86400
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


# ---------------------------------------------------------------------------
# Log analysis (runs in the process pool)
# ---------------------------------------------------------------------------

def analisar_log(texto: str, turno: int, offset: Optional[int]) -> tuple[dict, Counter]:
    """Zerésima, opening and first vote figures of one section log.

    offset: local time minus Brasilia time in hours, None abroad.
    Returns (row fields, catalog) where catalog counts every message that
    contains "zerésima" by (application, message with digits as N, day class)
    and day class is "dia" (round day), "outro_turno" (the other round day)
    or "outra_data".
    """
    dia = DATA[turno]
    outro = DATA[2 if turno == 1 else 1]
    catalogo: Counter = Counter()
    zer_datas: Counter = Counter()          # zerésima generated, by date (whole log)
    # round-day events, in file order: (kind, seconds, machine)
    ev: list[tuple[str, int, str]] = []
    aguarda_conf: list[int] = []
    resumo = imprime = 0
    for ln in texto.split("\n"):
        p = ln.split("\t")
        if len(p) < 5 or len(p[0]) < 19:
            continue
        data, msg, app, urna = p[0][:10], p[4], p[3], p[2]
        if ZER_RE.search(msg):
            classe = "dia" if data == dia else ("outro_turno" if data == outro else "outra_data")
            catalogo[(app, RE_NUM.sub("N", msg)[:200], classe)] += 1
            if msg == MSG_ZER_GERA:
                zer_datas[data] += 1
        if data != dia:
            continue
        if msg == MSG_ZER_GERA:
            ev.append(("zer", _seg(p[0][11:19]), urna))
        elif msg.startswith(MSG_ZER_IMPRIME):
            imprime += 1
        elif msg == MSG_RESUMO_GERA:
            resumo += 1
        elif msg == MSG_AGUARDA_CONF:
            aguarda_conf.append(_seg(p[0][11:19]))
        elif msg == EVENTO_VOTO:
            ev.append(("voto", _seg(p[0][11:19]), urna))
        elif msg == EVENTO_PRONTA:
            ev.append(("pronta", _seg(p[0][11:19]), urna))
        elif msg in EVENTOS_ENC:
            ev.append(("enc", _seg(p[0][11:19]), urna))

    zer = [t for k, t, _ in ev if k == "zer"]
    votos = [t for k, t, _ in ev if k == "voto"]
    prontas = [t for k, t, _ in ev if k == "pronta"]
    encs = [t for k, t, _ in ev if k == "enc"]
    zer_prim = min(zer) if zer else None
    voto_prim = min(votos) if votos else None

    # per machine, file order: votes before each zerésima, zerésima after pronta
    por_urna: dict[str, list[tuple[str, int]]] = {}
    for k, t, u in ev:
        por_urna.setdefault(u, []).append((k, t))
    zer_apos_pronta_ordem = zer_apos_voto_ordem = zer_posterior_com_votos = 0
    votos_antes_zer_ordem = 0
    zer_apos_enc_ordem = 0
    urnas_voto_sem_zer: list[str] = []
    for u, seq in por_urna.items():
        vistos = Counter()
        tem_zer = any(k == "zer" for k, _ in seq)
        for k, _ in seq:
            if k == "zer":
                if vistos["pronta"]:
                    zer_apos_pronta_ordem += 1
                if vistos["enc"]:
                    zer_apos_enc_ordem += 1
                if vistos["voto"]:
                    zer_apos_voto_ordem += 1
                    if vistos["zer"]:
                        zer_posterior_com_votos += 1
            elif k == "voto" and tem_zer and not vistos["zer"]:
                votos_antes_zer_ordem += 1
            vistos[k] += 1
        if vistos["voto"] and not tem_zer:
            urnas_voto_sem_zer.append(u)
    # a machine with votes and no zerésima whose first vote came before any
    # zerésima of the section (by time) has no zerésima behind it at all
    sem_antecessor = 0
    for u in urnas_voto_sem_zer:
        pv = min(t for k, t in por_urna[u] if k == "voto")
        if zer_prim is None or pv < zer_prim:
            sem_antecessor += 1

    datas_erradas = {d: n for d, n in zer_datas.items()
                     if d not in (DATA[1], DATA[2]) or (turno == 1 and d == DATA[2])}
    row = {
        "zer_n": len(zer),
        "zer_urnas": len({u for k, _, u in ev if k == "zer"}),
        "zer_imprime_n": imprime,
        "zer_resumo_n": resumo,
        "zer_prim": _hms(zer_prim),
        "zer_ult": _hms(max(zer)) if zer else None,
        "zer_prim_bsb": (_hms(zer_prim - offset * 3600)
                         if zer_prim is not None and offset is not None else None),
        "aguarda_conf_prim": _hms(min(aguarda_conf)) if aguarda_conf else None,
        "aguarda_conf_prim_bsb": (_hms(min(aguarda_conf) - offset * 3600)
                                  if aguarda_conf and offset is not None else None),
        "pronta_n": len(prontas),
        "pronta_prim": _hms(min(prontas)) if prontas else None,
        "enc_n": len(encs),
        "voto_n": len(votos),
        "voto_prim": _hms(voto_prim),
        "urnas_dia": len(por_urna),
        "votos_antes_zer_hora": (sum(1 for t in votos if t < zer_prim)
                                 if zer_prim is not None else None),
        "zer_apos_voto_hora": bool(zer and votos and max(zer) > voto_prim),
        "zer_apos_pronta_hora": bool(zer and prontas and zer_prim > min(prontas)),
        "zer_apos_voto_ordem": zer_apos_voto_ordem,
        "zer_apos_pronta_ordem": zer_apos_pronta_ordem,
        "zer_apos_enc_ordem": zer_apos_enc_ordem,
        "zer_posterior_com_votos": zer_posterior_com_votos,
        "votos_antes_zer_ordem": votos_antes_zer_ordem,
        "urnas_voto_sem_zer": len(urnas_voto_sem_zer),
        "urnas_voto_sem_zer_sem_antecessor": sem_antecessor,
        "zer_datas": json.dumps(dict(sorted(zer_datas.items()))) if zer_datas else None,
        "zer_data_errada_n": sum(datas_erradas.values()),
        "zer_outro_turno_n": zer_datas.get(DATA[1], 0) if turno == 2 else 0,
    }
    return row, catalogo


def membro(buf: bytes, base: int, info: tuple) -> bytes:
    """Bytes of one stored/deflated member taken from a range buffer."""
    nome, off, csize, crc, ctype = info
    i = off - base
    h = LOCAL_HEADER.unpack_from(buf, i)
    if h[0] != b"PK\x03\x04":
        raise ValueError("bad local header")
    ini = i + LOCAL_HEADER.size + h[10] + h[11]
    dados = buf[ini:ini + csize]
    if len(dados) != csize:
        raise ValueError("member past the range")
    if ctype == zipfile.ZIP_DEFLATED:
        dados = zlib.decompress(dados, -15)
    elif ctype != zipfile.ZIP_STORED:
        raise ValueError(f"compression {ctype}")
    if zlib.crc32(dados) != crc:
        raise ValueError("CRC mismatch")
    return dados


def processar_chunk(args: tuple) -> tuple[list[dict], Counter]:
    """All sections of one downloaded range."""
    from dataurnas.analyzer.rdv_recontagem import texto_log
    from dataurnas.analyzer.timezones import get_tz_offset

    uf, turno, base, buf, infos = args
    linhas, cat = [], Counter()
    for info in infos:
        m = NOME_RE.match(info[0])
        _, u, mun, zona, secao = m.groups()
        row = {"uf": u, "cd_mun": mun, "zona": zona, "secao": secao, "turno": turno,
               "membro": info[0], "erro_log": None}
        try:
            raw = membro(buf, base, info) if buf is not None else None
            if raw is None:   # range fallback failed upstream
                raise ValueError("member not downloaded")
            texto = texto_log(raw)
            if not texto:
                raise ValueError("unreadable log")
            offset = None if u == "zz" else get_tz_offset(u, mun)
            r, c = analisar_log(texto, turno, offset)
            row.update(r)
            for k, n in c.items():
                cat[k] += n
                cat[("secoes",) + k] += 1
        except Exception as e:  # noqa: BLE001
            row["erro_log"] = f"{type(e).__name__}: {e}"[:200]
        linhas.append(row)
    return linhas, cat


# ---------------------------------------------------------------------------
# Download planning
# ---------------------------------------------------------------------------

def membros_log(uf: str, turno: int) -> tuple[int, int, list[tuple]]:
    """(zip size, member count, log members) from the zip central directory."""
    z = zipfile.ZipFile(HttpRangeFile(URL.format(t=turno, uf=uf)))
    infos = z.infolist()
    logs = sorted(((i.filename, i.header_offset, i.compress_size, i.CRC, i.compress_type)
                   for i in infos if NOME_RE.match(i.filename)
                   and int(NOME_RE.match(i.filename).group(1)) == turno - 1),
                  key=lambda x: x[1])
    return z.fp.size, len(infos), logs


def planejar(logs: list[tuple], chunk: int, gap: int) -> list[tuple[int, int, list[tuple]]]:
    """Group log members into (start, end, members) ranges."""
    folga = 1024   # local header name + extra, bounded generously
    out: list[tuple[int, int, list[tuple]]] = []
    for info in logs:
        ini, fim = info[1], info[1] + 30 + len(info[0]) + folga + info[2]
        if out and ini - out[-1][1] <= gap and fim - out[-1][0] <= chunk:
            s, _, ms = out[-1]
            out[-1] = (s, fim, ms + [info])
        else:
            out.append((ini, fim, [info]))
    return out


def baixar_range(url: str, ini: int, fim: int, tamanho: int) -> bytes:
    """One HTTP range with retries; backs off on 403/429 (never bypasses limits)."""
    fim = min(fim, tamanho) - 1
    espera = 5
    for tentativa in range(12):
        try:
            req = urllib.request.Request(url, headers={"Range": f"bytes={ini}-{fim}"})
            with urllib.request.urlopen(req, timeout=180) as r:
                d = r.read()
            if len(d) == fim - ini + 1:
                return d
            raise OSError(f"short read {len(d)}")
        except urllib.error.HTTPError as e:
            if e.code not in (403, 429, 500, 502, 503, 504):
                raise
            _log(f"HTTP {e.code} at {url.rsplit('_', 2)[-2:]}, waiting {espera * 6}s")
            time.sleep(espera * 6)
        except OSError as e:
            if tentativa == 11:
                raise
            _log(f"{type(e).__name__} {e}, retrying in {espera}s")
            time.sleep(espera)
        espera = min(espera * 2, 120)
    raise OSError("range failed")


# ---------------------------------------------------------------------------
# volume
# ---------------------------------------------------------------------------

def cmd_volume(a: argparse.Namespace) -> None:
    out = Path(a.saida).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    pares = [(uf, t) for t in (1, 2) for uf in UFS]

    def um(par):
        uf, t = par
        size, n, logs = membros_log(uf, t)
        plano = planejar(logs, a.chunk_mb << 20, a.gap_kb << 10)
        return {"uf": uf, "turno": t, "zip_bytes": size, "membros": n, "logs": len(logs),
                "log_bytes": sum(i[2] for i in logs),
                "ler_bytes": sum(e - s for s, e, _ in plano), "ranges": len(plano)}

    with ThreadPoolExecutor(a.conexoes) as ex:
        rows = list(ex.map(um, pares))
    tot = {k: sum(r[k] for r in rows) for k in ("zip_bytes", "membros", "logs", "log_bytes",
                                                  "ler_bytes", "ranges")}
    (out / "volume.json").write_text(json.dumps({"total": tot, "por_zip": rows}, indent=1))
    print(json.dumps(tot, indent=1))


# ---------------------------------------------------------------------------
# processar
# ---------------------------------------------------------------------------

def processar_par(uf: str, turno: int, a: argparse.Namespace, saida: Path,
                  pool: ProcessPoolExecutor) -> None:
    import pandas as pd

    final = saida / f"zer_{uf.lower()}_{turno}.parquet"
    if final.exists():
        _log(f"{uf} {turno}t: already done")
        return
    t0 = time.time()
    url = URL.format(t=turno, uf=uf)
    size, _, logs = membros_log(uf, turno)
    plano = planejar(logs, a.chunk_mb << 20, a.gap_kb << 10)
    vagas = threading.Semaphore(a.em_voo)
    futs, lido = [], [0]
    lock = threading.Lock()

    def um(rng):
        ini, fim, infos = rng
        vagas.acquire()
        try:
            buf = baixar_range(url, ini, fim, size)
        except Exception as e:  # noqa: BLE001
            _log(f"{uf} {turno}t: range {ini} failed: {e}")
            buf = None
        with lock:
            lido[0] += fim - ini
        f = pool.submit(processar_chunk, (uf.lower(), turno, ini, buf, infos))
        f.add_done_callback(lambda _f: vagas.release())
        return f

    with ThreadPoolExecutor(a.conexoes) as ex:
        futs = list(ex.map(um, plano))
    linhas, cat = [], Counter()
    for f in futs:
        ls, c = f.result()
        linhas.extend(ls)
        cat.update(c)
    # members that did not fit their range or whose range failed: fetch each
    # one alone (exact local header) and parse it again
    porn = {i[0]: i for i in logs}
    for idx, r in enumerate(linhas):
        if r["erro_log"] and ("past the range" in r["erro_log"]
                              or "not downloaded" in r["erro_log"]):
            info = porn[r["membro"]]
            ini = info[1]
            h = LOCAL_HEADER.unpack(baixar_range(url, ini, ini + LOCAL_HEADER.size, size))
            fim = ini + LOCAL_HEADER.size + h[10] + h[11] + info[2]
            ls, c = processar_chunk((uf.lower(), turno, ini,
                                     baixar_range(url, ini, fim, size), [info]))
            linhas[idx] = ls[0]
            cat.update(c)
    cat_rows = []
    for k, n in cat.items():
        if k[0] == "secoes":
            continue
        cat_rows.append({"uf": uf.lower(), "turno": turno, "aplicacao": k[0], "mensagem": k[1],
                         "classe_data": k[2], "ocorrencias": n,
                         "secoes": cat[("secoes",) + k]})
    pd.DataFrame(cat_rows).to_parquet(saida / f"catalogo_{uf.lower()}_{turno}.parquet",
                                      index=False)
    pd.DataFrame(linhas).to_parquet(final.with_suffix(".tmp"), index=False)
    final.with_suffix(".tmp").rename(final)
    dt = time.time() - t0
    _log(f"{uf} {turno}t: {len(linhas)} logs, {lido[0] / 1e6:.0f} MB in {dt:.0f}s "
         f"({lido[0] / 1e6 / max(dt, 1):.1f} MB/s); errors "
         f"{sum(1 for r in linhas if r['erro_log'])}; no zerésima "
         f"{sum(1 for r in linhas if not r['erro_log'] and not r.get('zer_n'))}")


def cmd_processar(a: argparse.Namespace) -> None:
    saida = Path(a.saida).expanduser()
    saida.mkdir(parents=True, exist_ok=True)
    ufs = [u.upper() for u in a.ufs.split(",")] if a.ufs else UFS
    turnos = [int(t) for t in a.turnos.split(",")]
    t0 = time.time()
    with ProcessPoolExecutor(a.workers) as pool:
        for t in turnos:
            for uf in ufs:
                processar_par(uf, t, a, saida, pool)
    _log(f"done in {(time.time() - t0) / 3600:.2f} h")


# ---------------------------------------------------------------------------
# relatorio
# ---------------------------------------------------------------------------

def cmd_relatorio(a: argparse.Namespace) -> None:
    import pandas as pd

    saida = Path(a.saida).expanduser()
    repo = Path(a.repo).expanduser()
    repo.mkdir(parents=True, exist_ok=True)
    df = pd.concat([pd.read_parquet(p) for p in sorted(saida.glob("zer_*_*.parquet"))],
                   ignore_index=True)
    cat = pd.concat([pd.read_parquet(p) for p in sorted(saida.glob("catalogo_*_*.parquet"))],
                    ignore_index=True)
    chave = ["uf", "cd_mun", "zona", "secao"]
    df["id"] = (df.uf.str.upper() + "/" + df.cd_mun + "/" + df.zona + "/" + df.secao)
    ok = df[df.erro_log.isna()]
    res: dict = {"pacote_volume": json.loads((saida / "volume.json").read_text())["total"]
                 if (saida / "volume.json").exists() else None}

    def seg(s):
        return s.map(lambda x: _seg(x) if isinstance(x, str) else None).astype("float")

    anomalias = []

    def marca(mask, tipo, d):
        sub = d[mask]
        anomalias.append(sub.assign(anomalia=tipo))
        return int(mask.sum())

    for t in (1, 2):
        d = ok[ok.turno == t]
        com_voto = d.voto_n > 0
        r = {
            "logs_no_pacote": int((df.turno == t).sum()),
            "logs_ilegiveis": int(((df.turno == t) & df.erro_log.notna()).sum()),
            "logs_lidos": len(d),
            "secoes_com_voto": int(com_voto.sum()),
            "secoes_sem_voto": int((~com_voto).sum()),
            "secoes_sem_voto_sem_zeresima": int(((~com_voto) & (d.zer_n == 0)).sum()),
            "zer_n_distribuicao": {str(k): int(v) for k, v in
                                   d.zer_n.value_counts().sort_index().items()},
            "zer_urnas_distribuicao": {str(k): int(v) for k, v in
                                       d.zer_urnas.value_counts().sort_index().items()},
            "urnas_dia_distribuicao": {str(k): int(v) for k, v in
                                       d.urnas_dia.value_counts().sort_index().items()},
            "zer_imprime_total": int(d.zer_imprime_n.sum()),
            "zer_resumo_total": int(d.zer_resumo_n.sum()),
            "secoes_zer_sem_resumo": int((d.zer_resumo_n < d.zer_n).sum()),
            "secoes_zer_sem_impressao": int(((d.zer_n > 0) & (d.zer_imprime_n == 0)).sum()),
        }
        r["sem_zeresima_com_voto"] = marca(com_voto & (d.zer_n == 0), "sem_zeresima_com_voto", d)
        r["zer_apos_voto_hora"] = marca(d.zer_apos_voto_hora, "zer_apos_voto_hora", d)
        r["zer_apos_voto_ordem"] = marca(d.zer_apos_voto_ordem > 0, "zer_apos_voto_ordem", d)
        r["zer_apos_pronta_hora"] = marca(d.zer_apos_pronta_hora, "zer_apos_pronta_hora", d)
        r["zer_apos_pronta_ordem"] = marca(d.zer_apos_pronta_ordem > 0, "zer_apos_pronta_ordem",
                                           d)
        r["zer_apos_encerramento_ordem"] = marca(d.zer_apos_enc_ordem > 0, "zer_apos_enc_ordem",
                                                 d)
        r["mais_de_uma_zer"] = marca(d.zer_n > 1, "mais_de_uma_zer", d)
        r["zer_posterior_com_votos"] = marca(d.zer_posterior_com_votos > 0,
                                             "zer_posterior_com_votos", d)
        r["votos_antes_zer_hora_secoes"] = marca(d.votos_antes_zer_hora.fillna(0) > 0,
                                                 "votos_antes_zer_hora", d)
        r["votos_antes_zer_hora_votos"] = int(d.votos_antes_zer_hora.fillna(0).sum())
        r["votos_antes_zer_ordem_secoes"] = marca(d.votos_antes_zer_ordem > 0,
                                                  "votos_antes_zer_ordem", d)
        r["zer_data_errada"] = marca(d.zer_data_errada_n > 0, "zer_data_errada", d)
        r["urnas_voto_sem_zer_secoes"] = int((d.urnas_voto_sem_zer > 0).sum())
        r["urnas_voto_sem_zer_total"] = int(d.urnas_voto_sem_zer.sum())
        r["urnas_voto_sem_zer_sem_antecessor"] = marca(
            d.urnas_voto_sem_zer_sem_antecessor > 0, "urna_voto_sem_zer_sem_antecessor", d)
        r["sem_pronta_com_voto"] = int((com_voto & (d.pronta_n == 0)).sum())
        if t == 2:
            r["log_t2_com_zer_do_1t"] = int((d.zer_outro_turno_n > 0).sum())
        # times
        zs = seg(d.zer_prim).dropna()
        br = d[d.uf != "zz"]
        zb = seg(br.zer_prim_bsb).dropna()
        ab = seg(br.aguarda_conf_prim_bsb).dropna()
        q = [0, 0.001, 0.01, 0.5, 0.99, 0.999, 1]
        r["zer_prim_local_quantis"] = {str(k): _hms(int(v)) for k, v in zs.quantile(q).items()}
        r["zer_prim_brasilia_quantis"] = {str(k): _hms(int(v))
                                          for k, v in zb.quantile(q).items()}
        r["aguarda_conf_brasilia_quantis"] = {str(k): _hms(int(v))
                                              for k, v in ab.quantile(q).items()}
        r["zer_antes_7h_brasilia"] = marca(
            (d.uf != "zz") & (seg(d.zer_prim_bsb).fillna(99999) < 7 * 3600),
            "zer_antes_7h_brasilia", d)
        r["zer_apos_8h_brasilia"] = int(((d.uf != "zz") &
                                         (seg(d.zer_prim_bsb).fillna(-1) >= 8 * 3600)).sum())
        r["aguarda_conf_antes_7h_brasilia"] = int(((d.uf != "zz") & (
            seg(d.aguarda_conf_prim_bsb).fillna(99999) < 7 * 3600)).sum())
        # minutes between zerésima and opening
        dz = (seg(d.pronta_prim) - seg(d.zer_prim)).dropna() / 60
        r["min_zer_ate_pronta_quantis"] = {str(k): round(float(v), 1)
                                          for k, v in dz.quantile(q).items()}
        res[f"turno_{t}"] = r

    # cross-check with pacote_nacional.py outputs (same package, other parser)
    if a.pacote:
        pn = []
        for p in sorted(Path(a.pacote).expanduser().glob("secoes_*_*.parquet")):
            pn.append(pd.read_parquet(p, columns=chave + ["turno", "tem_log",
                                                          "tempo_hora_pronta",
                                                          "tempo_primeiro_voto",
                                                          "log_votos_log"]))
        pn = pd.concat(pn, ignore_index=True)
        m = df.merge(pn, on=chave + ["turno"], how="outer", indicator=True)
        cc = {}
        for t in (1, 2):
            x = m[m.turno == t]
            both = x[x._merge == "both"]
            okb = both[both.erro_log.isna()]
            cc[f"turno_{t}"] = {
                "secoes_pacote_nacional": int((x._merge != "left_only").sum()),
                "pacote_nacional_tem_log": int(x.tem_log.fillna(False).astype(bool).sum()),
                "logs_lidos_aqui": int((x._merge != "right_only").sum()),
                "so_aqui": int((x._merge == "left_only").sum()),
                "so_pacote_nacional_com_log": int(((x._merge == "right_only") &
                                                   x.tem_log.fillna(False).astype(bool)).sum()),
                "pronta_difere": int((okb.pronta_prim.fillna("") !=
                                      okb.tempo_hora_pronta.fillna("")).sum()),
                "primeiro_voto_difere": int((okb.voto_prim.fillna("") !=
                                             okb.tempo_primeiro_voto.fillna("")).sum()),
                "votos_difere": int((okb.voto_n.fillna(-1) !=
                                     okb.log_votos_log.fillna(-1)).sum()),
            }
        res["confronto_pacote_nacional"] = cc

    # message catalog
    cg = (cat.groupby(["turno", "aplicacao", "mensagem", "classe_data"], as_index=False)
          [["ocorrencias", "secoes"]].sum()
          .sort_values(["turno", "secoes"], ascending=[True, False]))
    cg.to_csv(repo / "catalogo_mensagens.csv", index=False)
    res["catalogo_formas"] = int(len(cg))

    an = pd.concat(anomalias, ignore_index=True) if anomalias else pd.DataFrame()
    cols = ["anomalia", "turno", "id", "zer_n", "zer_urnas", "zer_prim", "zer_ult",
            "zer_prim_bsb", "aguarda_conf_prim", "pronta_n", "pronta_prim", "voto_n",
            "voto_prim", "urnas_dia", "votos_antes_zer_hora", "votos_antes_zer_ordem",
            "zer_apos_voto_ordem", "zer_apos_pronta_ordem", "zer_apos_enc_ordem",
            "zer_posterior_com_votos", "urnas_voto_sem_zer",
            "urnas_voto_sem_zer_sem_antecessor", "zer_datas", "membro"]
    if len(an):
        an = an[cols].sort_values(["anomalia", "turno", "id"])
        an.to_csv(repo / "anomalias.csv", index=False)
    erros = df[df.erro_log.notna()][["turno", "id", "membro", "erro_log"]]
    erros.to_csv(repo / "logs_ilegiveis.csv", index=False)
    # sections present in both rounds: did the same section miss a zerésima twice?
    piv = ok.pivot_table(index="id", columns="turno", values="zer_n", aggfunc="first")
    res["sem_zer_nos_dois_turnos"] = int(((piv.get(1) == 0) & (piv.get(2) == 0)).sum())
    (repo / "resumo.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    print(json.dumps(res, indent=1, ensure_ascii=False))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for nome in ("volume", "processar"):
        p = sub.add_parser(nome)
        p.add_argument("--saida", required=True)
        p.add_argument("--conexoes", type=int, default=4, help="max concurrent requests (TSE: 4)")
        p.add_argument("--chunk-mb", type=int, default=8)
        p.add_argument("--gap-kb", type=int, default=256)
        if nome == "processar":
            p.add_argument("--ufs", default="")
            p.add_argument("--turnos", default="1,2")
            p.add_argument("--workers", type=int, default=48)
            p.add_argument("--em-voo", type=int, default=128,
                           help="ranges downloaded but not yet parsed")
    p = sub.add_parser("relatorio")
    p.add_argument("--saida", required=True)
    p.add_argument("--pacote", default="")
    p.add_argument("--repo", required=True)
    a = ap.parse_args()
    {"volume": cmd_volume, "processar": cmd_processar, "relatorio": cmd_relatorio}[a.cmd](a)


if __name__ == "__main__":
    main()
