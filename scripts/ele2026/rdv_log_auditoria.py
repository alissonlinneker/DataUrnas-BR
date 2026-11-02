#!/usr/bin/env python3
"""Conferência independente RDV x BU x log da urna e padrões de votação no log
(Presidente, 2026, 1º turno 04/10 e 2º turno 25/10).

Amostra (fixa, gravada em amostra.parquet):
  1. as 2.997 seções da amostra de biometria (logs dos dois turnos já baixados
     em ~/dataurnas-t2/biometria/brutos/, ver docs/biometria-1t-2t-2026.md);
  2. seções que fecharam depois das 17:30 de Brasília no 2º turno, com log já
     lido (data/parquet/2026/t2/impacto/amostra_logs.parquet, papel "tardia"),
     das mais tardias para as menos tardias, até 8.000 seções no total.

Etapas (subcomandos):
  amostra    monta amostra.parquet a partir dos Parquet locais (Mac).
  baixar     baixa -rdv.dat, -bu.dat (ou -busa.dat) e -vota.vsc de cada seção e
             turno (2º turno de toda a amostra; 1º turno da parte de biometria),
             num único processo, no máximo 3 req/s; o nome do arquivo segue o
             padrão do TSE e, em 404, é lido do aux.json da seção. Os brutos
             ficam em --brutos (servidor de análise).
  processar  (a) recontagem do RDV x BU por cargo (analyzer.rdv_recontagem, o
             mesmo código da recontagem nacional do 1º turno) e o resultado de
             Presidente do BU por bu_to_rows(raw, eleição, 1); (b) SHA-512 do
             RDV, do BU e do log contra o hash assinado no .vsc e a assinatura
             do .vsc (parsers.signature.verificar_vsc); (c) leitura eleitor a
             eleitor dos logs da amostra de biometria nos dois turnos.
  relatorio  resumo.json e tabelas.md a partir dos Parquet de processar.

Saída (--saida, padrão data/parquet/2026/t2/rdv_log/):
  amostra.parquet          seções e origem na amostra
  rdv_secoes.parquet       uma linha por seção e turno: RDV x BU, hashes, .vsc
  rdv_cargos.parquet       uma linha por seção, turno e cargo (recontagem)
  logs_secoes.parquet      uma linha por seção e turno: métricas do log
  logs_horas.parquet       votos computados por hora de Brasília, seção e turno
  resumo.json, tabelas.md

Uso (servidor de análise):
  python3 scripts/ele2026/rdv_log_auditoria.py amostra            # no Mac
  python3 -I scripts/ele2026/rdv_log_auditoria.py baixar --brutos ~/dataurnas-t2/rdv_log/brutos
  python3 -I scripts/ele2026/rdv_log_auditoria.py processar --brutos ... \
      --brutos-log ~/dataurnas-t2/biometria/brutos
  python3 -I scripts/ele2026/rdv_log_auditoria.py relatorio
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import random
import re
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[2]
SRC = str(ROOT / "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

log = logging.getLogger("rdv_log")

SAIDA = ROOT / "data" / "parquet" / "2026" / "t2" / "rdv_log"
AMOSTRA_BIO = ROOT / "data" / "parquet" / "2026" / "t2" / "biometria" / "amostra.parquet"
AMOSTRA_IMPACTO = ROOT / "data" / "parquet" / "2026" / "t2" / "impacto" / "amostra_logs.parquet"
LIMITE_SECOES = 8000

CICLO = "ele2026"
PLEITO = {1: 3220, 2: 3221}
ELEICAO = {1: 6257, 2: 6258}  # cargo 1 (Presidente); ver parametros_turno
DATA = {1: "04/10/2026", 2: "25/10/2026"}
SUFIXO = {"rdv": "rdv.dat", "bu": "bu.dat", "vota": "vota.vsc"}

# Municípios do Amazonas em UTC-5 que analyzer/timezones.py ainda trata como UTC-4
# (Ipixuna e vizinhos já constam lá); a mesma lista é usada nos outros relatórios
# do 2º turno (docs/encerramento-tardio-2turno-2026.md). Só afeta as horas de
# Brasília calculadas aqui; votos_antes_8h vem de analisar_log_tempo, sem a correção.
AM_UTC5_EXTRA = {2496, 2755, 2917, 98370}

# Ciclo mínimo plausível do eleitor (habilitação -> voto computado), em segundos
LIMIAR_CURTO_S = (5, 10, 15)


# ---------------------------------------------------------------------------
# Amostra
# ---------------------------------------------------------------------------

def cmd_amostra(args: argparse.Namespace) -> None:
    import pandas as pd

    bio = pd.read_parquet(AMOSTRA_BIO)
    imp = pd.read_parquet(AMOSTRA_IMPACTO)
    b = bio[["uf", "cd_mun", "zona", "secao", "chave", "hash_1", "hash_2"]].copy()
    b["origem"] = "biometria"
    b["minutos_apos_17h_bsb"] = None
    t = imp[(imp.papel == "tardia") & imp.t2_apos_17h30.fillna(False).astype(bool)]
    t = t[~t.chave.isin(set(b.chave))]
    t = t.sort_values(["minutos_apos_17h_bsb", "chave"], ascending=[False, True])
    vagas = max(0, LIMITE_SECOES - len(b))
    n_tardias = len(t)
    t = t.head(vagas)
    t2 = t[["uf", "cd_mun", "zona", "secao", "chave", "hash", "minutos_apos_17h_bsb"]].rename(
        columns={"hash": "hash_2"})
    t2["hash_1"] = None
    t2["origem"] = "tardia"
    a = pd.concat([b, t2[b.columns]], ignore_index=True)
    a["minutos_apos_17h_bsb"] = a["minutos_apos_17h_bsb"].astype("float64")
    out = Path(args.saida)
    out.mkdir(parents=True, exist_ok=True)
    a.to_parquet(out / "amostra.parquet", index=False)
    meta = {"biometria": int(len(b)), "tardias_elegiveis_fora_biometria": int(n_tardias),
            "tardias_incluidas": int(len(t2)), "total": int(len(a)),
            "corte_minutos_apos_17h": float(t2.minutos_apos_17h_bsb.min()) if len(t2) else None}
    (out / "amostra_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    log.info("amostra: %s", meta)


def pedidos(a) -> list[dict]:
    """(seção, turno) a baixar: 2º turno de todas, depois 1º turno da biometria."""
    out = []
    for r in a.to_dict("records"):
        out.append({**r, "turno": 2, "hash": r["hash_2"]})
    for r in a.to_dict("records"):
        if r["origem"] == "biometria" and r.get("hash_1"):
            out.append({**r, "turno": 1, "hash": r["hash_1"]})
    return out


def dir_bruto(brutos: Path, r: dict) -> Path:
    return brutos / f"t{r['turno']}" / r["uf"] / f"{r['cd_mun']}-{r['zona']}-{r['secao']}-{r['hash'][:16]}"


def nome_padrao(r: dict, tp: str) -> str:
    return (f"o{PLEITO[r['turno']]:05d}{r['uf']}{r['cd_mun']}{r['zona']}{r['secao']}"
            f"-{SUFIXO[tp]}")


# ---------------------------------------------------------------------------
# Download (um processo, no máximo 3 req/s)
# ---------------------------------------------------------------------------

async def _baixar(a, brutos: Path, rate: float) -> None:
    from dataurnas.downloader import ele2026 as E

    todos = pedidos(a)
    pend = [r for r in todos if not (dir_bruto(brutos, r) / "ok.json").exists()]
    log.info("%d pares seção x turno, %d pendentes", len(todos), len(pend))
    f = E.HttpFetcher(concurrency=3, retries=8, rate=rate, rate_max=rate, http2=False)
    erros = brutos / "erros.jsonl"
    feitos = 0
    t0 = time.time()

    async def um(r: dict) -> None:
        nonlocal feitos
        d = dir_bruto(brutos, r)
        url = lambda nm, h=r["hash"]: E.url_arquivo(  # noqa: E731
            r["uf"], r["cd_mun"], r["zona"], r["secao"], h, nm,
            pleito=str(PLEITO[r["turno"]]), ciclo=CICLO)
        try:
            nomes = {tp: nome_padrao(r, tp) for tp in SUFIXO}
            corpos = {}
            aux_usado = False
            for tp, nm in nomes.items():
                corpos[tp] = await f.get(url(nm))
            if any(v is None for v in corpos.values()):
                aux_usado = True
                aux = await f.get_json(E.url_aux(r["uf"], r["cd_mun"], r["zona"], r["secao"],
                                                 pleito=str(PLEITO[r["turno"]]), ciclo=CICLO))
                hs = [x for x in (aux or {}).get("hashes") or [] if x.get("hash") == r["hash"]]
                arq = {a_["tp"]: a_["nm"] for a_ in (hs[0].get("arq") if hs else []) or []}
                mapa = {"rdv": arq.get("rdv"), "bu": arq.get("bu") or arq.get("busa"),
                        "vota": arq.get("vota") or arq.get("vscmr") or arq.get("vsc")}
                for tp, v in corpos.items():
                    if v is None and mapa.get(tp):
                        nomes[tp] = mapa[tp]
                        corpos[tp] = await f.get(url(mapa[tp]))
            d.mkdir(parents=True, exist_ok=True)
            for tp, b in corpos.items():
                if b is not None:
                    tmp = d / f"{nomes[tp]}.tmp"
                    tmp.write_bytes(b)
                    tmp.rename(d / nomes[tp])
            meta = {"chave": r["chave"], "turno": r["turno"], "hash": r["hash"],
                    "nomes": {tp: nomes[tp] for tp in SUFIXO if corpos[tp] is not None},
                    "ausentes": [tp for tp in SUFIXO if corpos[tp] is None],
                    "aux_usado": aux_usado}
            (d / "ok.json").write_text(json.dumps(meta), encoding="utf-8")
        except Exception as e:  # noqa: BLE001  refeito na próxima execução
            with erros.open("a", encoding="utf-8") as fe:
                fe.write(json.dumps({"chave": r["chave"], "turno": r["turno"],
                                     "erro": f"{type(e).__name__}: {e}"[:300]}) + "\n")
        feitos += 1
        if feitos % 250 == 0:
            el = time.time() - t0
            log.info("%d/%d (%.1f/min) %s %s", feitos, len(pend), feitos / el * 60,
                     f.rate_info(), f.stats)

    try:
        for i in range(0, len(pend), 12):
            await asyncio.gather(*[um(r) for r in pend[i:i + 12]])
    finally:
        await f.close()
    log.info("download concluído: %s", f.stats)


def cmd_baixar(args: argparse.Namespace) -> None:
    import pandas as pd

    if args.taxa > 3.0:
        raise SystemExit("taxa máxima permitida: 3 req/s")
    a = pd.read_parquet(Path(args.saida) / "amostra.parquet")
    brutos = Path(args.brutos).expanduser()
    brutos.mkdir(parents=True, exist_ok=True)
    asyncio.run(_baixar(a, brutos, args.taxa))


# ---------------------------------------------------------------------------
# RDV x BU x .vsc (executado no pool)
# ---------------------------------------------------------------------------

def _rdv_um(tarefa: tuple) -> dict:
    import hashlib

    from dataurnas.analyzer import rdv_recontagem as R
    from dataurnas.downloader.ele2026 import bu_to_rows
    from dataurnas.parsers.signature import verificar_vsc

    r, d, log_path = tarefa
    d = Path(d)
    ident = {k: r[k] for k in ("uf", "cd_mun", "zona", "secao")}
    turno = r["turno"]
    base = {**ident, "chave": r["chave"], "turno": turno, "origem": r["origem"], "hash": r["hash"]}
    ok = d / "ok.json"
    if not ok.exists():
        return {"secao": {**base, "status": "nao_baixado"}, "cargos": []}
    meta = json.loads(ok.read_text(encoding="utf-8"))
    nomes = meta["nomes"]
    raw = {tp: (d / nm).read_bytes() for tp, nm in nomes.items()}
    sec = {**base, "status": "ok", "ausentes": ",".join(meta["ausentes"]) or None,
           "nome_rdv": nomes.get("rdv"), "nome_bu": nomes.get("bu")}
    tipo_bu = "busa" if (nomes.get("bu") or "").endswith("-busa.dat") else "bu"
    arquivos = {}
    if "rdv" in raw:
        arquivos["rdv"] = (nomes["rdv"], raw["rdv"])
    if "bu" in raw:
        arquivos[tipo_bu] = (nomes["bu"], raw["bu"])
    res = R.processar_secao(ident, arquivos, None, PLEITO[turno], DATA[turno], False,
                            None, turno, ())
    s = res["secao"]
    sec.update({"status": s["status"], "motivo": s.get("motivo"), "origem_bu": tipo_bu,
                "comparecimento_bu": s.get("comparecimento_bu"),
                "registros_rdv": s.get("registros_rdv"), "n_cargos": s.get("n_cargos"),
                "estrutura_ok": s.get("estrutura_ok"), "rdv_confere": s.get("rdv_confere"),
                "tipo_urna_rdv": s.get("tipo_urna_rdv"),
                "achados_rdv": json.dumps([a["categoria"] for a in res["achados"]],
                                          ensure_ascii=False)})
    pres = res["presidente"]
    for k, campo in (("nominal:13", "rdv_13"), ("nominal:22", "rdv_22"),
                     ("branco", "rdv_brancos"), ("nulo", "rdv_nulos")):
        sec[campo] = int(pres.get(k, 0)) if pres else None
    sec["rdv_outros_nominais"] = (sum(v for k, v in pres.items() if k.startswith("nominal:")
                                      and k not in ("nominal:13", "nominal:22"))
                                  if pres else None)
    sec["rdv_legenda"] = sum(v for k, v in pres.items() if k.startswith("legenda")) if pres else None
    sec["rdv_presidente_total"] = sum(pres.values()) if pres else None
    # BU de Presidente pela leitura usada no resto do projeto
    if "bu" in raw:
        try:
            sb, votos = bu_to_rows(raw["bu"], ELEICAO[turno], 1)
            por = Counter()
            for v in votos:
                if v["tipo_voto"] == "nominal":
                    por[f"nom_{v['numero']}"] += v["votos"]
                else:
                    por[v["tipo_voto"]] += v["votos"]
            sec.update({"bu_13": por.get("nom_13", 0), "bu_22": por.get("nom_22", 0),
                        "bu_brancos": por.get("branco", 0), "bu_nulos": por.get("nulo", 0),
                        "bu_outros_nominais": sum(v for k, v in por.items() if k.startswith("nom_")
                                                  and k not in ("nom_13", "nom_22")),
                        "bu_legenda": por.get("legenda", 0),
                        "bu_presidente_total": sb["votos_total"],
                        "bu_comparecimento_presidente": sb["comparecimento"],
                        "bu_aptos": sb["aptos"], "bu_codigo_carga": str(sb["codigo_carga"])
                        if sb["codigo_carga"] is not None else None,
                        "bu_hora_abertura": str(sb["hora_abertura"]) if sb["hora_abertura"] else None,
                        "bu_hora_encerramento": str(sb["hora_encerramento"])
                        if sb["hora_encerramento"] else None,
                        "bu_numero_interno_urna": sb["numero_interno_urna"],
                        "bu_hab_bio": sb["habilitados_biometria"],
                        "bu_hab_biog": sb["habilitados_biografia"],
                        "bu_sem_bio": sb["comp_sem_biometria"]})
        except Exception as e:  # noqa: BLE001
            sec["motivo"] = (sec.get("motivo") or "") + f" bu_to_rows: {e!r}"[:200]
    if sec.get("rdv_presidente_total") is not None and sec.get("bu_presidente_total") is not None:
        sec["presidente_confere"] = all(
            sec.get(f"rdv_{k}") == sec.get(f"bu_{k}")
            for k in ("13", "22", "brancos", "nulos", "outros_nominais", "legenda",
                      "presidente_total"))
    # .vsc: hash assinado do RDV, do BU e do log; assinatura
    if "vota" in raw:
        log_raw = None
        if log_path and Path(log_path).exists():
            log_raw = Path(log_path).read_bytes()
        try:
            v = verificar_vsc(raw["vota"], None)
            hs = {nm: h.hex() for nm, h in v["hashes"].items()}
            sec["vsc_assinatura_valida"] = v["assinatura_valida"]
            sec["vsc_algoritmo"] = v["algoritmo"]
            sec["vsc_falhas"] = "; ".join(v["falhas"]) or None
            sec["vsc_motivos"] = "; ".join(v["motivos"]) or None
            sec["vsc_arquivos_listados"] = ",".join(sorted(hs))
            sec["vsc_lista_rdv"] = nomes.get("rdv") in hs
            for tp in ("rdv", "bu"):
                nm = nomes.get(tp)
                if nm and nm in hs:
                    sec[f"hash_{tp}_confere"] = hashlib.sha512(raw[tp]).hexdigest() == hs[nm]
                    sec[f"assinatura_{tp}_ok"] = v["assinaturas_arquivos"].get(nm)
            if log_raw is not None:
                nm_log = [nm for nm in hs if nm.endswith(("-log.jez", "-logsa.jez"))]
                if nm_log:
                    sec["hash_log_confere"] = hashlib.sha512(log_raw).hexdigest() == hs[nm_log[0]]
                    sec["assinatura_log_ok"] = v["assinaturas_arquivos"].get(nm_log[0])
        except Exception as e:  # noqa: BLE001
            sec["vsc_falhas"] = f"leitura: {e!r}"[:200]
    cargos = [{**{k: ln[k] for k in ln if k != "_lote"}, "chave": r["chave"], "turno": turno}
              for ln in res["linhas"]]
    return {"secao": sec, "cargos": cargos}


# ---------------------------------------------------------------------------
# Log eleitor a eleitor (executado no pool)
# ---------------------------------------------------------------------------

RE_TIPO = re.compile(r"Tipo de habilitação do eleitor \[(.*)\]")
RE_CARGA = re.compile(r"Código de carga ([\d.]+) gravado")
RE_TURNO_UE = re.compile(r"Turno da UE: (\d)")


def _seg(h: str) -> int:
    return int(h[0:2]) * 3600 + int(h[3:5]) * 60 + int(h[6:8])


def _maior_seq(seq: list[bool]) -> int:
    m = c = 0
    for x in seq:
        c = c + 1 if x else 0
        m = max(m, c)
    return m


def _p_seq(seq: list[bool], obs: int, n_perm: int = 400, seed: int = 0) -> Optional[float]:
    """P(maior sequência >= obs) embaralhando a ordem dos eleitores da seção."""
    k = sum(seq)
    if k == 0 or obs <= 1:
        return None
    rnd = random.Random(seed)
    s = list(seq)
    ge = 0
    for _ in range(n_perm):
        rnd.shuffle(s)
        if _maior_seq(s) >= obs:
            ge += 1
    return (ge + 1) / (n_perm + 1)


def analisar_log(texto: str, uf: str, cd_mun: str, turno: int, comp_bu: Optional[int]) -> dict:
    from dataurnas.analyzer.rdv_recontagem import analisar_log_tempo
    from dataurnas.analyzer.timezones import get_tz_offset

    dia = DATA[turno]
    anteriores = (DATA[1],) if turno == 2 else ()
    base = analisar_log_tempo(texto, uf, cd_mun, comp_bu, dia, anteriores)
    offset = 0 if uf == "zz" else get_tz_offset(uf, cd_mun)
    if uf == "am" and int(cd_mun) in AM_UTC5_EXTRA:
        offset = -2
    m: Counter = Counter()
    erros_msg: Counter = Counter()
    eleitores: list[tuple[int, str, Optional[int], int]] = []  # (t, classe, dur, confirmacoes)
    cargas_todas: set[str] = set()
    datas_carga: set[str] = set()
    turnos_dia: set[str] = set()
    ligadas: list[int] = []
    prontas: list[int] = []
    encerramentos: list[int] = []
    cur = {"tipo": None, "manual": False, "digital": 0}
    hab_t: Optional[int] = None
    hab_classe: Optional[str] = None
    conf = 0
    suspenso = False
    por_hora_local: Counter = Counter()
    for ln in texto.split("\n"):
        p = ln.split("\t")
        if len(p) < 5:
            continue
        data, hora = p[0][:10], p[0][11:19]
        nivel, app, msg = p[1], p[3], p[4]
        mc = RE_CARGA.search(msg)
        if mc:
            cargas_todas.add(mc.group(1).replace(".", ""))
            datas_carga.add(data)
        if data != dia:
            continue
        try:
            t = _seg(hora)
        except ValueError:
            continue
        if nivel == "ERRO":
            m["erros"] += 1
            erros_msg[re.sub(r"\d+", "N", msg)[:120]] += 1
        elif nivel == "ALERTA":
            m["alertas"] += 1
        mt = RE_TURNO_UE.search(msg)
        if mt:
            turnos_dia.add(mt.group(1))
        if msg.startswith("Urna ligada em"):
            ligadas.append(t)
            continue
        if msg.startswith("Data e hora atualizada"):
            m["data_hora_atualizada"] += 1
        if "Urna pronta para receber votos" in msg:
            prontas.append(t)
        elif msg.startswith(("Inicio do Encerramento", "Início do Encerramento")):
            encerramentos.append(t)
        if app != "VOTA":
            continue
        if msg.startswith("Identificador do eleitor digitado pelo mesário"):
            cur = {"tipo": None, "manual": False, "digital": 0}
        elif msg.startswith("Solicita digital. Tentativa"):
            cur["digital"] += 1
        elif msg.startswith("Tipo de habilitação do eleitor"):
            mt2 = RE_TIPO.search(msg)
            cur["tipo"] = mt2.group(1) if mt2 else msg
        elif re.match(r"Mesário \d+ habilitou o eleitor", msg):
            cur["manual"] = True
        elif msg.startswith("Solicitação de dado pessoal do eleitor para habilitação manual"):
            m["pedido_hab_manual"] += 1
        elif msg == "Eleitor foi habilitado":
            if hab_t is not None:
                m["habilitado_sem_voto"] += 1  # habilitação anterior sem voto computado
            hab_t = t
            if cur["tipo"] and "biom" in cur["tipo"]:
                hab_classe = "biometrica"
            elif cur["manual"]:
                hab_classe = "manual_mesario"
            elif cur["digital"] == 0:
                hab_classe = "sem_digital"
            else:
                hab_classe = "outra"
            conf = 0
            cur = {"tipo": None, "manual": False, "digital": 0}
        elif msg.startswith("Voto confirmado para ["):
            conf += 1
        elif msg.startswith("Eleitor foi suspenso"):
            # o eleitor suspenso volta depois e conclui o voto sem nova habilitação
            m["suspensoes"] += 1
            suspenso = True
        elif msg == "O voto do eleitor foi computado":
            por_hora_local[t // 3600] += 1
            if hab_t is None:
                m["voto_sem_habilitacao"] += 1
                eleitores.append((t, "sem_habilitacao", None, conf))
            else:
                eleitores.append((t, hab_classe or "outra",
                                  None if suspenso else t - hab_t, conf))
            hab_t = None
            conf = 0
            suspenso = False
    n = len(eleitores)
    durs = sorted(e[2] for e in eleitores if e[2] is not None)
    classes = Counter(e[1] for e in eleitores)
    confs = Counter(e[3] for e in eleitores)
    moda_conf = confs.most_common(1)[0][0] if confs else None
    # Habilitação manual: houve pedido de digital e a habilitação não foi biométrica
    # (com ou sem mesário identificado). Sem digital: eleitor sem biometria
    # cadastrada, habilitado só pelo documento (o caminho mais simples para votar
    # no lugar de um ausente sem biometria).
    manual = [e[1] in ("manual_mesario", "outra") for e in eleitores]
    semdig = [e[1] == "sem_digital" for e in eleitores]
    nao_bio = [e[1] != "biometrica" for e in eleitores]
    seqs = {}
    for nome, seq in (("manual", manual), ("sem_digital", semdig), ("nao_biometrica", nao_bio)):
        mx = _maior_seq(seq)
        seqs[f"maior_seq_{nome}"] = mx
        seqs[f"p_seq_{nome}"] = _p_seq(seq, mx) if sum(seq) >= 2 and mx >= 2 else None
        cauda = 0
        for x in reversed(seq):
            if not x:
                break
            cauda += 1
        seqs[f"cauda_{nome}"] = cauda
    # horário (local) do início e do fim da maior sequência de habilitação manual
    best = (0, None, None)
    ini = None
    for i, x in enumerate(manual):
        if x:
            ini = i if ini is None else ini
            if i - ini + 1 > best[0]:
                best = (i - ini + 1, ini, i)
        else:
            ini = None
    fmt = lambda v: f"{v // 3600:02d}:{v % 3600 // 60:02d}:{v % 60:02d}"  # noqa: E731
    seqs["seq_manual_inicio"] = fmt(eleitores[best[1]][0]) if best[1] is not None else None
    seqs["seq_manual_fim"] = fmt(eleitores[best[2]][0]) if best[2] is not None else None
    # na última hora antes do fim oficial (17h de Brasília em hora local)
    fim_local = (17 + offset) * 3600
    ult = [e for e in eleitores if fim_local - 3600 <= e[0]]
    seqs.update({
        "votos_ultima_hora": len(ult),
        "manual_ultima_hora": sum(1 for e in ult if e[1] in ("manual_mesario", "outra")),
        "sem_digital_ultima_hora": sum(1 for e in ult if e[1] == "sem_digital"),
        "votos_apos_fim_oficial": sum(1 for e in eleitores if e[0] >= fim_local),
        "manual_apos_fim_oficial": sum(1 for e in eleitores if e[0] >= fim_local
                                       and e[1] in ("manual_mesario", "outra")),
        "sem_digital_apos_fim_oficial": sum(1 for e in eleitores if e[0] >= fim_local
                                            and e[1] == "sem_digital"),
    })
    # janelas: máximo de votos em 10 min e em 60 min
    ts = sorted(e[0] for e in eleitores)
    def max_janela(w: int) -> int:
        best = j = 0
        for i in range(len(ts)):
            while ts[i] - ts[j] >= w:
                j += 1
            best = max(best, i - j + 1)
        return best
    primeira_pronta = min(prontas) if prontas else None
    ligadas_votacao = sum(1 for x in ligadas if primeira_pronta is not None and x > primeira_pronta
                          and (not encerramentos or x < max(encerramentos)))
    q = lambda p: durs[min(len(durs) - 1, int(p * len(durs)))] if durs else None  # noqa: E731
    out = {
        "votos_log": base["votos_log"], "comparecimento_bu": comp_bu,
        "diferenca_log_bu": base["diferenca_log_bu"],
        "votos_outras_datas": base["votos_outras_datas"],
        "votos_turno_anterior": base["votos_turno_anterior"],
        "n_urnas_log": base["n_urnas_log"], "aberturas": base["aberturas"],
        "hora_pronta": base["hora_pronta"], "hora_encerramento": base["hora_encerramento"],
        "primeiro_voto": base["primeiro_voto"], "ultimo_voto": base["ultimo_voto"],
        "votos_antes_8h": base["votos_antes_8h"], "votos_apos_17h": base["votos_apos_17h"],
        "votos_antes_pronta": base["votos_antes_pronta"],
        "votos_apos_encerramento": base["votos_apos_encerramento"],
        "max_votos_minuto": base["max_votos_minuto"], "minuto_pico": base["minuto_pico"],
        "intervalo_min_s": base["intervalo_min_s"],
        "intervalo_mediana_s": base["intervalo_mediana_s"],
        "intervalos_lt_10s": base["intervalos_lt_10s"], "intervalos_lt_5s": base["intervalos_lt_5s"],
        "maior_lacuna_min": base["maior_lacuna_min"], "lacunas_60min": base["lacunas_60min"],
        "inversoes_relogio": base["inversoes_relogio"], "ajustes_hora": base["ajustes_hora"],
        "hist_intervalos": base["hist_intervalos"], "flags_base": base["flags"],
        "votos_apos_17h_bsb": base["votos_log_apos_17h_brasilia"],
        "fuso_offset": offset,
        "eleitores": n,
        "hab_biometrica": classes.get("biometrica", 0),
        "hab_manual_mesario": classes.get("manual_mesario", 0),
        "hab_sem_digital": classes.get("sem_digital", 0),
        "hab_outra": classes.get("outra", 0),
        "voto_sem_habilitacao": m.get("voto_sem_habilitacao", 0),
        "habilitado_sem_voto": m.get("habilitado_sem_voto", 0),
        "suspensoes": m.get("suspensoes", 0),
        "pedido_hab_manual": m.get("pedido_hab_manual", 0),
        "dur_min_s": durs[0] if durs else None, "dur_p01_s": q(0.01),
        "dur_mediana_s": q(0.5), "dur_p99_s": q(0.99),
        "dur_lt_5s": sum(1 for d in durs if d < 5),
        "dur_lt_10s": sum(1 for d in durs if d < 10),
        "dur_lt_15s": sum(1 for d in durs if d < 15),
        # ciclo por cargo confirmado: menos de 2 s ou 3 s por confirmação
        "dur_lt_2s_por_cargo": sum(1 for e in eleitores if e[2] is not None
                                   and e[2] < 2 * max(e[3], 1)),
        "dur_lt_3s_por_cargo": sum(1 for e in eleitores if e[2] is not None
                                   and e[2] < 3 * max(e[3], 1)),
        "dur_hist": [sum(1 for d in durs if lo <= d < hi) for lo, hi in
                     ((0, 5), (5, 10), (10, 15), (15, 20), (20, 30), (30, 45), (45, 60),
                      (60, 120), (120, 300), (300, 10**9))],
        "moda_confirmacoes": moda_conf,
        "votos_menos_confirmacoes": sum(c for k, c in confs.items()
                                        if moda_conf is not None and k < moda_conf),
        "votos_zero_confirmacoes": confs.get(0, 0),
        **seqs,
        "max_votos_10min": max_janela(600), "max_votos_60min": max_janela(3600),
        "ligadas_dia": len(ligadas), "religadas_durante_votacao": ligadas_votacao,
        "erros": m.get("erros", 0), "alertas": m.get("alertas", 0),
        "erros_top": json.dumps(dict(erros_msg.most_common(5)), ensure_ascii=False),
        "data_hora_atualizada": m.get("data_hora_atualizada", 0),
        "turno_ue_dia": ",".join(sorted(turnos_dia)) or None,
        "codigos_carga_log": ",".join(sorted(cargas_todas)) or None,
        "datas_carga_log": ",".join(sorted(datas_carga)) or None,
        "votos_por_hora_bsb": {str(h - offset): c for h, c in sorted(por_hora_local.items())},
    }
    return out


def _log_um(tarefa: tuple) -> dict:
    from dataurnas.analyzer.rdv_recontagem import texto_log

    chave, uf, cd_mun, turno, caminho, comp = tarefa
    base = {"chave": chave, "turno": turno}
    try:
        txt = texto_log(Path(caminho).read_bytes())
    except Exception as e:  # noqa: BLE001
        return {**base, "erro": f"{type(e).__name__}: {e}"[:200]}
    if not txt:
        return {**base, "erro": "ilegivel"}
    try:
        return {**base, **analisar_log(txt, uf, cd_mun, turno, comp)}
    except Exception as e:  # noqa: BLE001
        return {**base, "erro": f"analise: {type(e).__name__}: {e}"[:200]}


def caminho_log_bio(brutos_log: Path, r: dict, turno: int) -> Path:
    h = r[f"hash_{turno}"]
    return brutos_log / f"t{turno}" / r["uf"] / f"{r['cd_mun']}-{r['zona']}-{r['secao']}-{h[:16]}.jez"


def cmd_processar(args: argparse.Namespace) -> None:
    import pandas as pd

    out = Path(args.saida)
    a = pd.read_parquet(out / "amostra.parquet")
    brutos = Path(args.brutos).expanduser()
    brutos_log = Path(args.brutos_log).expanduser()
    tarefas = []
    for r in pedidos(a):
        lp = caminho_log_bio(brutos_log, r, r["turno"]) if r["origem"] == "biometria" else None
        tarefas.append((r, str(dir_bruto(brutos, r)), str(lp) if lp else None))
    log.info("RDV: %d pares seção x turno", len(tarefas))
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        res = list(ex.map(_rdv_um, tarefas, chunksize=16))
    secs = pd.DataFrame([x["secao"] for x in res])
    cargos = pd.DataFrame([c for x in res for c in x["cargos"]])
    secs.to_parquet(out / "rdv_secoes.parquet", index=False)
    if len(cargos):
        cargos.to_parquet(out / "rdv_cargos.parquet", index=False)
    log.info("RDV gravado: %d seções, %d linhas de cargo", len(secs), len(cargos))

    # Logs da biometria, dois turnos; comparecimento do BU baixado
    comp = {(s["chave"], s["turno"]): s.get("comparecimento_bu")
            for s in secs.to_dict("records")}
    lt = []
    for r in a[a.origem == "biometria"].to_dict("records"):
        for t in (1, 2):
            c = caminho_log_bio(brutos_log, r, t)
            if c.exists():
                cb = comp.get((r["chave"], t))
                cb = None if cb is None or pd.isna(cb) else int(cb)
                lt.append((r["chave"], r["uf"], r["cd_mun"], t, str(c), cb))
    log.info("logs: %d arquivos", len(lt))
    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        lidos = list(ex.map(_log_um, lt, chunksize=8))
    horas = []
    for x in lidos:
        for h, c in (x.pop("votos_por_hora_bsb", None) or {}).items():
            horas.append({"chave": x["chave"], "turno": x["turno"], "hora_bsb": int(h),
                          "votos": int(c)})
    pd.DataFrame(lidos).to_parquet(out / "logs_secoes.parquet", index=False)
    pd.DataFrame(horas).to_parquet(out / "logs_horas.parquet", index=False)
    log.info("logs gravados: %d", len(lidos))


# ---------------------------------------------------------------------------
# Relatório
# ---------------------------------------------------------------------------

def _md(df, floatfmt: str = "{:,.4f}") -> str:
    cols = list(df.columns)
    linhas = ["| " + " | ".join(str(c) for c in cols) + " |",
              "|" + "|".join("---" for _ in cols) + "|"]
    for r in df.itertuples(index=False):
        cel = []
        for v in r:
            if isinstance(v, float):
                cel.append(floatfmt.format(v).replace(",", "X").replace(".", ",").replace("X", "."))
            elif isinstance(v, int):
                cel.append(f"{v:,}".replace(",", "."))
            else:
                cel.append(str(v))
        linhas.append("| " + " | ".join(cel) + " |")
    return "\n".join(linhas)


def cmd_relatorio(args: argparse.Namespace) -> None:
    import numpy as np
    import pandas as pd

    out = Path(args.saida)
    a = pd.read_parquet(out / "amostra.parquet")
    s = pd.read_parquet(out / "rdv_secoes.parquet")
    c = pd.read_parquet(out / "rdv_cargos.parquet") if (out / "rdv_cargos.parquet").exists() else None
    lg = pd.read_parquet(out / "logs_secoes.parquet")
    hr = pd.read_parquet(out / "logs_horas.parquet")
    R: dict = {"gerado_em": time.strftime("%Y-%m-%dT%H:%M:%S"),
               "amostra": json.loads((out / "amostra_meta.json").read_text())}
    md: list[str] = []

    # --- RDV x BU
    rdv = {}
    for t in (1, 2):
        x = s[s.turno == t]
        ok = x[x.status == "ok"]
        d = {
            "pares": int(len(x)),
            "status": {k: int(v) for k, v in x.status.value_counts().items()},
            "rdv_confere_todos_cargos": int(ok.rdv_confere.fillna(False).sum()),
            "rdv_diverge": int((ok.rdv_confere == False).sum()),  # noqa: E712
            "presidente_confere": int(ok.presidente_confere.fillna(False).sum()),
            "presidente_diverge": int((ok.presidente_confere == False).sum()),  # noqa: E712
            "estrutura_invalida": int((ok.estrutura_ok == False).sum()),  # noqa: E712
            "vsc_lista_rdv": int(x.get("vsc_lista_rdv", pd.Series(dtype=bool)).fillna(False).sum()),
            "hash_rdv_confere": int(x.get("hash_rdv_confere", pd.Series(dtype=bool)).fillna(False).sum()),
            "hash_rdv_diverge": int((x.get("hash_rdv_confere") == False).sum()),  # noqa: E712
            "hash_bu_confere": int(x.get("hash_bu_confere", pd.Series(dtype=bool)).fillna(False).sum()),
            "hash_bu_diverge": int((x.get("hash_bu_confere") == False).sum()),  # noqa: E712
            "hash_log_confere": int(x.get("hash_log_confere", pd.Series(dtype=bool)).fillna(False).sum()),
            "hash_log_diverge": int((x.get("hash_log_confere") == False).sum()),  # noqa: E712
            "vsc_assinatura_valida": {str(k): int(v) for k, v in
                                      x.vsc_assinatura_valida.value_counts(dropna=False).items()},
            "assinatura_rdv_ok": {str(k): int(v) for k, v in
                                  x.get("assinatura_rdv_ok", pd.Series(dtype=object))
                                  .value_counts(dropna=False).items()},
            "registros_rdv": int(ok.registros_rdv.fillna(0).sum()),
            "comparecimento_bu": int(ok.comparecimento_bu.fillna(0).sum()),
        }
        for k in ("13", "22", "brancos", "nulos", "outros_nominais", "legenda", "presidente_total"):
            d[f"rdv_{k}"] = int(ok[f"rdv_{k}"].fillna(0).sum())
            d[f"bu_{k}"] = int(ok[f"bu_{k}"].fillna(0).sum())
        d["por_origem"] = {o: {"pares": int(len(g)),
                               "presidente_confere": int(g.presidente_confere.fillna(False).sum()),
                               "rdv_confere": int(g.rdv_confere.fillna(False).sum())}
                           for o, g in ok.groupby("origem")}
        div = ok[(ok.rdv_confere == False) | (ok.presidente_confere == False)]  # noqa: E712
        d["divergencias"] = div[["chave", "turno", "origem"] + [f"{p}_{k}" for k in (
            "13", "22", "brancos", "nulos", "presidente_total") for p in ("rdv", "bu")]
                                ].to_dict("records")
        if c is not None:
            cc = c[c.turno == t]
            d["linhas_cargo"] = int(len(cc))
            d["linhas_cargo_confere"] = int(cc.confere.sum())
            d["cargos"] = {k: {"linhas": int(len(g)), "confere": int(g.confere.sum())}
                           for k, g in cc.groupby("cargo")}
        rdv[f"t{t}"] = d
    R["rdv"] = rdv
    # 1º turno nacional (recontagem completa já publicada) para as mesmas seções
    nac = ROOT / "data" / "parquet" / "2026" / "rdv" / "recontagem_secoes.parquet"
    if nac.exists():
        n1 = pd.read_parquet(nac, columns=["uf", "cd_mun", "zona", "secao", "codigo_cargo",
                                           "confere", "votos_rdv", "votos_bu"])
        n1 = n1[n1.codigo_cargo == 1]
        n1["chave"] = n1.uf + "/" + n1.cd_mun + "/" + n1.zona + "/" + n1.secao
        m1 = n1[n1.chave.isin(set(a.chave))]
        R["rdv_t1_nacional_mesmas_secoes"] = {"secoes": int(len(m1)),
                                              "confere": int(m1.confere.sum())}

    # --- Log
    ok = lg[lg["erro"].isna()] if "erro" in lg else lg
    est = pd.read_parquet(AMOSTRA_BIO, columns=["chave", "estrato", "modelo_urna_1"])
    ok = ok.merge(est, on="chave", how="left")
    bu = s[["chave", "turno", "bu_hab_bio", "bu_hab_biog", "bu_sem_bio"]]
    ok = ok.merge(bu, on=["chave", "turno"], how="left")
    ok["hab_manual"] = ok.hab_manual_mesario + ok.hab_outra
    soma = lambda x, c: int(x[c].fillna(0).sum())  # noqa: E731
    mx = lambda ser: int(ser.max()) if ser.notna().any() else None  # noqa: E731
    L = {}
    for t in (1, 2):
        x = ok[ok.turno == t]
        dh = np.array(x.dur_hist.tolist()).sum(axis=0).tolist() if len(x) else []
        d = {
            "logs": int(len(x)),
            "votos_log": soma(x, "votos_log"), "comparecimento_bu": soma(x, "comparecimento_bu"),
            "secoes_log_diverge_bu": int((x.diferenca_log_bu.fillna(0) != 0).sum()),
            "votos_antes_pronta": soma(x, "votos_antes_pronta"),
            "votos_apos_encerramento": soma(x, "votos_apos_encerramento"),
            "secoes_voto_antes_8h": int((x.votos_antes_8h > 0).sum()),
            "votos_antes_8h": soma(x, "votos_antes_8h"),
            "secoes_voto_antes_8h_lista": x[x.votos_antes_8h > 0][
                ["chave", "votos_antes_8h", "hora_pronta", "primeiro_voto", "fuso_offset"]
            ].to_dict("records"),
            "votos_outras_datas": soma(x, "votos_outras_datas"),
            "eleitores": soma(x, "eleitores"),
            "hab_biometrica": soma(x, "hab_biometrica"),
            "hab_manual": soma(x, "hab_manual"),
            "hab_manual_mesario_identificado": soma(x, "hab_manual_mesario"),
            "hab_sem_digital": soma(x, "hab_sem_digital"),
            "bu_hab_bio": soma(x, "bu_hab_bio"), "bu_hab_biog": soma(x, "bu_hab_biog"),
            "bu_sem_bio": soma(x, "bu_sem_bio"),
            "voto_sem_habilitacao": soma(x, "voto_sem_habilitacao"),
            "secoes_voto_sem_habilitacao": int((x.voto_sem_habilitacao > 0).sum()),
            "habilitado_sem_voto": soma(x, "habilitado_sem_voto"),
            "suspensoes": soma(x, "suspensoes"),
            "moda_confirmacoes": {str(k): int(v) for k, v in
                                  x.moda_confirmacoes.value_counts().items()},
            "votos_zero_confirmacoes": soma(x, "votos_zero_confirmacoes"),
            "votos_menos_confirmacoes_que_a_moda": soma(x, "votos_menos_confirmacoes"),
            "dur_lt_5s": soma(x, "dur_lt_5s"), "dur_lt_10s": soma(x, "dur_lt_10s"),
            "dur_lt_15s": soma(x, "dur_lt_15s"),
            "dur_lt_2s_por_cargo": soma(x, "dur_lt_2s_por_cargo"),
            "dur_lt_3s_por_cargo": soma(x, "dur_lt_3s_por_cargo"),
            "secoes_dur_lt_3s_por_cargo": int((x.dur_lt_3s_por_cargo > 0).sum()),
            "dur_min_s": int(x.dur_min_s.min()),
            "dur_mediana_s_mediana_secoes": float(x.dur_mediana_s.median()),
            "dur_hist_faixas_s": ["[0,5)", "[5,10)", "[10,15)", "[15,20)", "[20,30)", "[30,45)",
                                  "[45,60)", "[60,120)", "[120,300)", "[300,inf)"],
            "dur_hist": dh,
            "intervalo_min_s": int(x.intervalo_min_s.min()),
            "intervalo_mediana_s_mediana_secoes": float(x.intervalo_mediana_s.median()),
            "intervalos_lt_10s": soma(x, "intervalos_lt_10s"),
            "intervalos_lt_5s": soma(x, "intervalos_lt_5s"),
            "max_votos_minuto_max": int(x.max_votos_minuto.max()),
            "max_votos_10min_max": int(x.max_votos_10min.max()),
            "max_votos_60min_max": int(x.max_votos_60min.max()),
            "max_votos_60min_p99": float(x.max_votos_60min.quantile(0.99)),
            "votos_ultima_hora": soma(x, "votos_ultima_hora"),
            "manual_ultima_hora": soma(x, "manual_ultima_hora"),
            "sem_digital_ultima_hora": soma(x, "sem_digital_ultima_hora"),
            "votos_apos_fim_oficial": soma(x, "votos_apos_fim_oficial"),
            "manual_apos_fim_oficial": soma(x, "manual_apos_fim_oficial"),
            "sem_digital_apos_fim_oficial": soma(x, "sem_digital_apos_fim_oficial"),
            "secoes_mais_de_uma_abertura": int((x.aberturas > 1).sum()),
            "secoes_mais_de_uma_urna": int((x.n_urnas_log > 1).sum()),
            "secoes_religada_durante_votacao": int((x.religadas_durante_votacao > 0).sum()),
            "secoes_com_erro": int((x.erros > 0).sum()), "erros": soma(x, "erros"),
            "secoes_data_hora_atualizada": int((x.data_hora_atualizada > 0).sum()),
            "secoes_ajuste_hora": int((x.ajustes_hora > 0).sum()),
            "secoes_inversao_relogio": int((x.inversoes_relogio > 0).sum()),
            "turno_ue_dia": {str(k): int(v) for k, v in
                             x.turno_ue_dia.value_counts(dropna=False).items()},
            "secoes_lacuna_60min": int((x.lacunas_60min > 0).sum()),
        }
        # sequências: teste de permutação (p < 0,01 esperado em ~1% sob ordem aleatória)
        seq = {}
        for nome in ("manual", "sem_digital", "nao_biometrica"):
            for rot, g in (("extremo_bu", x[x.estrato == "extremo_bu"]),
                           ("demais", x[x.estrato != "extremo_bu"])):
                pv = g[f"p_seq_{nome}"]
                seq[f"{nome}/{rot}"] = {
                    "testadas": int(pv.notna().sum()), "p_lt_0_05": int((pv < 0.05).sum()),
                    "p_lt_0_01": int((pv < 0.01).sum()),
                    "maior_seq_max": mx(g[f"maior_seq_{nome}"]),
                    "cauda_ge5": int((g[f"cauda_{nome}"] >= 5).sum())}
        d["sequencias"] = seq
        top_err: Counter = Counter()
        for e in x.erros_top.dropna():
            top_err.update(json.loads(e))
        d["erros_mensagens_top"] = dict(top_err.most_common(10))
        L[f"t{t}"] = d
    R["log"] = L
    # carga: código de carga do log x BU, e 1º x 2º turno
    sb = s[["chave", "turno", "bu_codigo_carga", "bu_numero_interno_urna"]]
    lc = ok[["chave", "turno", "codigos_carga_log", "datas_carga_log"]].merge(
        sb, on=["chave", "turno"], how="left")
    lc["carga_bu_no_log"] = [
        (b in (cl or "").split(",")) if isinstance(b, str) and b not in ("None", "") else None
        for b, cl in zip(lc.bu_codigo_carga, lc.codigos_carga_log, strict=True)]
    R["carga"] = {f"t{t}": {"logs": int(len(g)),
                            "carga_bu_no_log": {str(k): int(v) for k, v in
                                                g.carga_bu_no_log.value_counts(dropna=False).items()},
                            "secoes_sem_codigo_no_log": int(g.codigos_carga_log.isna().sum()),
                            "secoes_carga_no_dia": int(g.datas_carga_log.fillna("").str.contains(
                                DATA[t]).sum())}
                  for t, g in lc.groupby("turno")}
    R["carga"]["carga_bu_fora_do_log"] = lc[lc.carga_bu_no_log == False][  # noqa: E712
        ["chave", "turno", "bu_codigo_carga", "codigos_carga_log"]].to_dict("records")
    p12 = lc.pivot_table(index="chave", columns="turno", values="bu_codigo_carga", aggfunc="first")
    if 1 in p12 and 2 in p12:
        R["carga"]["mesmo_codigo_bu_t1_t2"] = int((p12[1] == p12[2]).sum())
        R["carga"]["codigo_bu_diferente_t1_t2"] = int((p12[1] != p12[2]).sum())
    # horas de Brasília
    hh = hr.groupby(["turno", "hora_bsb"]).votos.sum().unstack(0).fillna(0).astype(int)
    R["votos_por_hora_bsb"] = {f"t{t}": {str(h): int(v) for h, v in hh[t].items()}
                               for t in hh.columns}
    # pares 1T x 2T
    p = ok.pivot_table(index="chave", columns="turno",
                       values=["hab_manual", "hab_sem_digital", "eleitores", "dur_mediana_s",
                               "erros", "religadas_durante_votacao"], aggfunc="first").dropna()
    p.columns = [f"{a_}_{b_}" for a_, b_ in p.columns]
    p["tx_man_1"] = p.hab_manual_1 / p.eleitores_1.clip(lower=1)
    p["tx_man_2"] = p.hab_manual_2 / p.eleitores_2.clip(lower=1)
    R["pares_t1_t2"] = {
        "secoes": int(len(p)),
        "corr_tx_manual_t1_t2": float(p.tx_man_1.corr(p.tx_man_2)),
        "tx_manual_t1": float(p.hab_manual_1.sum() / p.eleitores_1.sum()),
        "tx_manual_t2": float(p.hab_manual_2.sum() / p.eleitores_2.sum()),
        "tx_sem_digital_t1": float(p.hab_sem_digital_1.sum() / p.eleitores_1.sum()),
        "tx_sem_digital_t2": float(p.hab_sem_digital_2.sum() / p.eleitores_2.sum()),
        "secoes_tx_manual_sobe_20pp": int(((p.tx_man_2 - p.tx_man_1) >= 0.20).sum()),
        "secoes_tx_manual_cai_20pp": int(((p.tx_man_2 - p.tx_man_1) <= -0.20).sum()),
        "dur_mediana_t1": float(p.dur_mediana_s_1.median()),
        "dur_mediana_t2": float(p.dur_mediana_s_2.median()),
    }
    # extremos para inspeção
    cols_seq = ["chave", "turno", "estrato", "modelo_urna_1", "eleitores", "hab_manual",
                "maior_seq_manual", "p_seq_manual", "seq_manual_inicio", "seq_manual_fim",
                "cauda_manual", "n_urnas_log"]
    ext = ok[ok.estrato != "extremo_bu"].sort_values(["p_seq_manual", "maior_seq_manual"],
                                                     ascending=[True, False]).head(20)[cols_seq]
    ext_bu = ok[ok.estrato == "extremo_bu"].sort_values("maior_seq_manual",
                                                        ascending=False).head(10)[cols_seq]
    sd = ok.sort_values(["p_seq_sem_digital", "maior_seq_sem_digital"],
                        ascending=[True, False]).head(15)[
        ["chave", "turno", "estrato", "eleitores", "hab_sem_digital", "maior_seq_sem_digital",
         "p_seq_sem_digital", "cauda_sem_digital", "sem_digital_ultima_hora"]]
    rap = ok[ok.dur_lt_3s_por_cargo > 0].sort_values("dur_min_s")[
        ["chave", "turno", "eleitores", "dur_min_s", "dur_lt_3s_por_cargo", "dur_mediana_s",
         "moda_confirmacoes", "intervalo_min_s"]]
    R["extremos_seq_manual"] = ext.to_dict("records")
    R["extremos_seq_sem_digital"] = sd.to_dict("records")
    R["extremos_ritmo"] = rap.to_dict("records")
    (out / "resumo.json").write_text(json.dumps(R, indent=2, ensure_ascii=False, default=str),
                                     encoding="utf-8")
    md.append("# Tabelas (gerado por rdv_log_auditoria.py relatorio)\n")
    md.append("## Sequências de habilitação manual, fora do estrato extremo_bu\n")
    md.append(_md(ext))
    md.append("\n## Sequências de habilitação manual, estrato extremo_bu (leitor de digitais)\n")
    md.append(_md(ext_bu))
    md.append("\n## Sequências de eleitores sem digital (sem biometria cadastrada)\n")
    md.append(_md(sd))
    md.append("\n## Eleitores com ciclo menor que 3 s por cargo confirmado\n")
    md.append(_md(rap))
    md.append("\n## Votos computados por hora de Brasília (amostra de biometria)\n")
    md.append(_md(hh.reset_index().rename(columns={1: "t1", 2: "t2"})))
    (out / "tabelas.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    log.info("relatório gravado em %s", out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("comando", choices=["amostra", "baixar", "processar", "relatorio"])
    ap.add_argument("--saida", default=str(SAIDA))
    ap.add_argument("--brutos", default="~/dataurnas-t2/rdv_log/brutos")
    ap.add_argument("--brutos-log", default="~/dataurnas-t2/biometria/brutos")
    ap.add_argument("--taxa", type=float, default=3.0)
    ap.add_argument("--workers", type=int, default=min(48, os.cpu_count() or 4))
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    {"amostra": cmd_amostra, "baixar": cmd_baixar, "processar": cmd_processar,
     "relatorio": cmd_relatorio}[args.comando](args)


if __name__ == "__main__":
    main()
