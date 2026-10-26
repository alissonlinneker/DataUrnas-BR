#!/usr/bin/env python3
"""Impacto possível da prorrogação da votação no 2º turno de 2026 (25/10/2026).

Contexto: a Rcl 101.673/BA (STF) prorrogou o recebimento de votos até as 19h
de Brasília; o esclarecimento limitou a ordem aos locais onde as urnas ainda
não tinham sido fechadas (ver docs/prorrogacao-votacao-2turno-2026.md). Este
script descreve as seções que encerraram depois do horário padrão e mede, com
os arquivos públicos, quanto essas seções poderiam pesar na diferença final
entre 13 e 22. É descritivo: não estima efeito causal.

Entradas (só leitura):
  data/parquet/2026/t2/encerramento/secoes_encerramento.parquet  (analisar_encerramento_t2.py)
  data/parquet/2026/secoes_2026.parquet, votos_presidente_2026.parquet (1º turno)
  data/versoes/2026/t2/totais/indice.jsonl (totais oficiais versionados do 2º turno)
  -log.jez das seções da amostra (baixado do TSE com --baixar-logs; só as
  contagens ficam em disco, o arquivo bruto é descartado depois de lido)

Saída em data/parquet/2026/t2/impacto/ (ignorada pelo git):
  secoes_t1_t2.parquet     seções do 2º turno com encerramento, limiares e o 1º turno da mesma seção
  logs_contagens.jsonl     contagens do log por seção (cache incremental do download)
  amostra_logs.parquet     amostra (tardias depois de 17:30 + controles pareados) com contagens
  resumo.json              inventário, comparações, cenários de impacto e testes
  tabelas.md               tabelas prontas para o relatório

Uso:
  python3 scripts/ele2026/impacto_prorrogacao_t2.py                   # só análise (usa cache de logs)
  nice -n 20 python3 scripts/ele2026/impacto_prorrogacao_t2.py --baixar-logs
  python3 scripts/ele2026/impacto_prorrogacao_t2.py --total-oficial br.json
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import json
import logging
import math
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Optional

ROOT = Path(__file__).resolve().parents[2]
SRC = str(ROOT / "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

log = logging.getLogger("impacto_prorrogacao_t2")

PLEITO_T2 = "3221"
CICLO = "ele2026"
DATA_T1 = "04/10/2026"
DATA_T2 = "25/10/2026"
DIA_T1 = "20261004"
DIA_T2 = "20261025"

ENCERRAMENTO = ROOT / "data" / "parquet" / "2026" / "t2" / "encerramento" / "secoes_encerramento.parquet"
SECOES_T1 = ROOT / "data" / "parquet" / "2026" / "secoes_2026.parquet"
VOTOS_T1 = ROOT / "data" / "parquet" / "2026" / "votos_presidente_2026.parquet"
LOG_T1 = ROOT / "data" / "parquet" / "2026" / "rdv" / "log_tempo_secoes.parquet"
RESUMO_T1 = ROOT / "data" / "parquet" / "2026" / "resumo_br.json"
INDICE_TOTAIS = ROOT / "data" / "versoes" / "2026" / "t2" / "totais" / "indice.jsonl"
SAIDA_PADRAO = ROOT / "data" / "parquet" / "2026" / "t2" / "impacto"

# Limiares de encerramento em Brasília, pelo minuto truncado depois de 17:00
# (mesma regra das faixas de analisar_encerramento_t2.py): "depois de 17:10"
# quer dizer 17:11:00 ou mais tarde.
LIMIARES = (("apos_17h10", 11), ("apos_17h30", 31), ("apos_18h00", 61), ("apos_19h00", 121))
ROTULO_LIMIAR = {"apos_17h10": "depois de 17:10", "apos_17h30": "depois de 17:30",
                 "apos_18h00": "depois de 18:00", "apos_19h00": "depois de 19:00"}
LIMITE_CONTROLE = 10  # controle: encerrou até 17:10 (minuto truncado <= 10)
LIMITE_TARDIA = 31    # tardia: encerrou depois de 17:30

# Cortes (minutos depois de 17:00 de Brasília) para contar votos no log
CORTES_LOG = (("apos_17h00", 0), ("apos_17h10", 10), ("apos_17h30", 30),
              ("apos_18h00", 60), ("apos_18h30", 90))

REGIAO = {
    **dict.fromkeys(("ac", "am", "ap", "pa", "ro", "rr", "to"), "Norte"),
    **dict.fromkeys(("al", "ba", "ce", "ma", "pb", "pe", "pi", "rn", "se"), "Nordeste"),
    **dict.fromkeys(("df", "go", "ms", "mt"), "Centro-Oeste"),
    **dict.fromkeys(("es", "mg", "rj", "sp"), "Sudeste"),
    **dict.fromkeys(("pr", "rs", "sc"), "Sul"),
}


def _carregar_encerramento():
    p = ROOT / "scripts" / "ele2026" / "analisar_encerramento_t2.py"
    spec = importlib.util.spec_from_file_location("analisar_encerramento_t2", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ENC = _carregar_encerramento()


# ---------------------------------------------------------------------------
# Horários
# ---------------------------------------------------------------------------

def minuto_truncado(bsb: Optional[str], dia: str) -> Optional[int]:
    """Minutos inteiros entre 17:00 de Brasília do dia e o horário dado
    ('AAAA-MM-DD HH:MM:SS'), com os segundos desprezados. None se vazio."""
    if not bsb or (isinstance(bsb, float) and math.isnan(bsb)):
        return None
    dt = datetime.strptime(str(bsb)[:19], "%Y-%m-%d %H:%M:%S")
    ref = datetime.strptime(dia, "%Y%m%d").replace(hour=17)
    return int((dt.replace(second=0) - ref).total_seconds() // 60)


def marcar_limiares(minuto: Optional[int]) -> dict[str, Optional[bool]]:
    return {nome: (None if minuto is None else minuto >= lim) for nome, lim in LIMIARES}


def encerramento_t1_bsb(hora_local: Optional[str], uf: str, cd_mun: str) -> Optional[str]:
    """Hora de encerramento do BU do 1º turno ('20261004T150706', horário local
    da urna) convertida para Brasília, no formato 'AAAA-MM-DD HH:MM:SS'."""
    dt = ENC.parse_hora_urna(hora_local)
    bsb = ENC.para_brasilia(dt, ENC.fuso_utc(uf, cd_mun))
    return ENC.fmt(bsb)


def grupo_t2(minuto: Optional[int]) -> str:
    if minuto is None:
        return "sem_horario"
    if minuto <= LIMITE_CONTROLE:
        return "no_horario"
    if minuto < LIMITE_TARDIA:
        return "intermediaria"
    return "tardia"


# ---------------------------------------------------------------------------
# Log da urna
# ---------------------------------------------------------------------------

def nome_log(nome_bu: Optional[str]) -> Optional[str]:
    """o03221ba3849000010001-bu.dat -> o03221ba3849000010001-log.jez"""
    if not nome_bu or "-" not in nome_bu:
        return None
    base, suf = nome_bu.rsplit("-", 1)
    return f"{base}-logsa.jez" if suf.startswith("busa") else f"{base}-log.jez"


def votos_por_corte_bsb(texto: str, uf: str, cd_mun: str, data: str = DATA_T2,
                        cortes: Iterable[tuple[str, int]] = CORTES_LOG) -> dict[str, int]:
    """Votos computados na data dada (eventos 'O voto do eleitor foi computado')
    a partir de cada corte (minutos depois de 17:00 de Brasília, inclusive).
    A hora do log é a local da urna; converte pelo fuso do município. Conta como
    analisar_log_tempo (rdv_recontagem): todo voto do dia, de qualquer urna."""
    from dataurnas.analyzer.rdv_recontagem import EVENTO_VOTO
    from dataurnas.analyzer.timezones import get_tz_offset

    offset = get_tz_offset(uf, cd_mun)
    cortes = tuple(cortes)
    out = dict.fromkeys((n for n, _ in cortes), 0)
    base = 17 * 3600
    for ln in texto.split("\n"):
        if len(ln) < 30 or EVENTO_VOTO not in ln:
            continue
        p = ln.split("\t")
        if len(p) < 5 or EVENTO_VOTO not in p[4] or p[0][:10] != data:
            continue
        h = p[0][11:19]
        try:
            seg = int(h[0:2]) * 3600 + int(h[3:5]) * 60 + int(h[6:8]) - offset * 3600
        except ValueError:
            continue
        for nome, minutos in cortes:
            if seg >= base + minutos * 60:
                out[nome] += 1
    return out


def contagens_log(raw: bytes, uf: str, cd_mun: str, comparecimento: Optional[int]) -> dict:
    """Contagens que interessam do -log.jez do 2º turno (o bruto não é guardado)."""
    from dataurnas.analyzer.rdv_recontagem import analisar_log_tempo, texto_log

    texto = texto_log(raw)
    if not texto:
        return {"erro": "log_ilegivel"}
    r = analisar_log_tempo(texto, uf, cd_mun, comparecimento, data_eleicao=DATA_T2,
                           datas_anteriores=(DATA_T1,))
    out = {k: r[k] for k in ("votos_log", "diferenca_log_bu", "votos_turno_anterior",
                             "votos_outras_datas", "n_urnas_log", "aberturas",
                             "hora_encerramento", "ultimo_voto_brasilia",
                             "votos_log_apos_17h_brasilia", "votos_apos_encerramento")}
    out["hora_encerramento_log_local"] = out.pop("hora_encerramento")
    out["flags_log"] = ",".join(r["flags"])
    out.update({f"votos_{k}": v for k, v in votos_por_corte_bsb(texto, uf, cd_mun).items()})
    return out


# ---------------------------------------------------------------------------
# Amostra e pareamento
# ---------------------------------------------------------------------------

def _ordem(seed: int, k: str) -> str:
    """Ordem pseudoaleatória estável de uma seção (não muda quando chegam
    seções novas à coleta, o que preserva o cache de logs entre execuções)."""
    return hashlib.sha256(f"{seed}/{k}".encode()).hexdigest()


def escolher_controles(df: pd.DataFrame, seed: int = 2026,
                       frac_aleatoria: float = 0.01) -> pd.DataFrame:
    """Para cada seção tardia (depois de 17:30), um controle da mesma UF,
    município e zona que encerrou até 17:10, sem reposição, na ordem
    pseudoaleatória de _ordem. Zonas com menos controles que tardias usam todos
    os controles disponíveis. As seções intermediárias (17:11 a 17:30) entram
    inteiras, com papel 'intermediaria'. Mais uma fração `frac_aleatoria` das
    demais seções que fecharam até 17:10 (papel 'aleatoria_horario'): medem a
    fila normal depois das 17h no país coletado, comparada com o 1º turno.
    Devolve a amostra com as colunas 'papel' e 'estrato'."""
    chaves = df["uf"] + "/" + df["cd_mun"] + "/" + df["zona"] + "/" + df["secao"]
    ordem = chaves.map(lambda k: _ordem(seed, k))
    tard = df[df["grupo_t2"] == "tardia"]
    cont = df[df["grupo_t2"] == "no_horario"]
    por_estrato = {k: g.index for k, g in cont.groupby(["uf", "cd_mun", "zona"], sort=True)}
    escolhidos: list = []
    for k, g in tard.groupby(["uf", "cd_mun", "zona"], sort=True):
        idx = por_estrato.get(k)
        if idx is None or len(idx) == 0:
            continue
        escolhidos.extend(sorted(idx, key=lambda i: ordem[i])[:len(g)])
    a = tard.assign(papel="tardia")
    b = df.loc[sorted(escolhidos)].assign(papel="controle")
    c = df[df["grupo_t2"] == "intermediaria"].assign(papel="intermediaria")
    limite = int(frac_aleatoria * 16 ** 8)
    ja = set(escolhidos)
    resto = [i for i in cont.index if i not in ja and int(ordem[i][:8], 16) < limite]
    e = df.loc[sorted(resto)].assign(papel="aleatoria_horario")
    out = pd.concat([a, b, c, e], ignore_index=True)
    out["estrato"] = out["uf"] + "/" + out["cd_mun"] + "/" + out["zona"]
    return out


def chave(r) -> str:
    return f"{r['uf']}/{r['cd_mun']}/{r['zona']}/{r['secao']}"


def ler_cache(caminho: Path) -> dict[str, dict]:
    out: dict[str, dict] = {}
    if not caminho.exists():
        return out
    for ln in caminho.read_text(encoding="utf-8").splitlines():
        try:
            d = json.loads(ln)
        except json.JSONDecodeError:
            continue  # linha truncada por interrupção
        # resultado com erro de rede não fica: será refeito
        if d.get("erro") and d["erro"].startswith("rede"):
            continue
        out[d["chave"]] = d
    return out


async def baixar_logs(amostra: pd.DataFrame, cache_path: Path, rate: float = 3.0) -> None:
    """Baixa o -log.jez de cada seção da amostra ainda sem contagem no cache,
    no máximo `rate` req/s (com backoff em 429 do HttpFetcher), e grava só as
    contagens, uma linha JSON por seção."""
    from dataurnas.downloader import ele2026 as E

    cache = ler_cache(cache_path)
    pend = [r for r in amostra.to_dict("records") if chave(r) not in cache]
    log.info("amostra %d seções, %d no cache, %d a baixar", len(amostra), len(cache), len(pend))
    if not pend:
        return
    f = E.HttpFetcher(concurrency=3, retries=8, rate=rate, rate_max=rate, http2=False)
    loop = asyncio.get_running_loop()
    feitos = 0
    with cache_path.open("a", encoding="utf-8") as saida:
        async def uma(r: dict) -> None:
            nonlocal feitos
            k = chave(r)
            reg = {"chave": k, "hash": r["hash"]}
            try:
                nm = nome_log(r["nome_arquivo"])
                raw = None
                if nm:
                    raw = await f.get(E.url_arquivo(r["uf"], r["cd_mun"], r["zona"], r["secao"],
                                                    r["hash"], nm, pleito=PLEITO_T2, ciclo=CICLO))
                if raw is None:  # nome fora do padrão: pergunta ao aux.json
                    aux = await f.get_json(E.url_aux(r["uf"], r["cd_mun"], r["zona"], r["secao"],
                                                     pleito=PLEITO_T2, ciclo=CICLO))
                    h = [h for h in (aux or {}).get("hashes") or [] if h.get("hash") == r["hash"]]
                    arq = [a["nm"] for a in (h[0].get("arq") if h else []) or []
                           if a.get("tp") in ("log", "logsa")]
                    if arq:
                        nm = arq[0]
                        raw = await f.get(E.url_arquivo(r["uf"], r["cd_mun"], r["zona"],
                                                        r["secao"], r["hash"], nm,
                                                        pleito=PLEITO_T2, ciclo=CICLO))
                if raw is None:
                    reg["erro"] = "log_nao_publicado"
                else:
                    reg["bytes_log"] = len(raw)
                    reg["nome_log"] = nm
                    comp = None if pd.isna(r["comparecimento"]) else int(r["comparecimento"])
                    reg.update(await loop.run_in_executor(
                        None, contagens_log, raw, r["uf"], r["cd_mun"], comp))
                    del raw
            except Exception as e:  # noqa: BLE001  rede: fica fora do cache e é refeita
                reg["erro"] = f"rede: {type(e).__name__}: {e}"[:300]
            saida.write(json.dumps(reg, ensure_ascii=False) + "\n")
            saida.flush()
            feitos += 1
            if feitos % 200 == 0:
                log.info("%d/%d logs (%s) %s", feitos, len(pend), f.rate_info(), f.stats)

        try:
            # lotes pequenos: o semáforo e o limitador do HttpFetcher seguram a taxa
            for i in range(0, len(pend), 60):
                await asyncio.gather(*[uma(r) for r in pend[i:i + 60]])
        finally:
            await f.close()
    log.info("download concluído: %s", f.stats)


# ---------------------------------------------------------------------------
# Montagem das tabelas
# ---------------------------------------------------------------------------

def carregar_t2(caminho: Path = ENCERRAMENTO) -> pd.DataFrame:
    cols = ["uf", "cd_mun", "municipio", "zona", "secao", "tipo_arquivo", "nome_arquivo",
            "hash", "tipo_urna", "fuso_utc", "encerramento_local", "encerramento_bsb",
            "recebimento_bsb", "minutos_apos_17h_bsb", "faixa", "aptos", "comparecimento",
            "votos_13", "votos_22", "votos_outros_nominais", "votos_brancos", "votos_nulos",
            "inconsistencias"]
    df = pd.read_parquet(caminho, columns=cols)
    df = df[df["uf"] != "zz"].copy()
    df["regiao"] = df["uf"].map(REGIAO)
    df["minuto_t2"] = [minuto_truncado(v, DIA_T2) for v in df["encerramento_bsb"]]
    df["minuto_t2"] = df["minuto_t2"].astype("Int64")
    df["grupo_t2"] = [grupo_t2(None if pd.isna(m) else int(m)) for m in df["minuto_t2"]]
    for nome, lim in LIMIARES:
        df[f"t2_{nome}"] = df["minuto_t2"] >= lim
    df["validos_t2"] = df["votos_13"] + df["votos_22"] + df["votos_outros_nominais"]
    return df


def carregar_t1(secoes: Path = SECOES_T1, votos: Path = VOTOS_T1) -> pd.DataFrame:
    s = pd.read_parquet(secoes, columns=["uf", "cd_mun", "zona", "secao", "status",
                                         "hora_encerramento", "aptos", "comparecimento"])
    s = s[(s["status"] == "ok") & (s["uf"] != "zz")].drop(columns="status")
    v = pd.read_parquet(votos)
    v = v[v["tipo_voto"] == "nominal"]
    piv = v.assign(c=np.where(v["numero"] == 13, "votos_13",
                              np.where(v["numero"] == 22, "votos_22", "votos_outros")))
    piv = piv.groupby(["uf", "cd_mun", "zona", "secao", "c"])["votos"].sum().unstack("c",
                                                                                     fill_value=0)
    piv = piv.reset_index()
    t1 = s.merge(piv, on=["uf", "cd_mun", "zona", "secao"], how="left")
    for c in ("votos_13", "votos_22", "votos_outros"):
        t1[c] = t1[c].fillna(0).astype("int64")
    t1["validos"] = t1["votos_13"] + t1["votos_22"] + t1["votos_outros"]
    t1["encerramento_bsb"] = [encerramento_t1_bsb(h, u, m) for h, u, m in
                              zip(t1["hora_encerramento"], t1["uf"], t1["cd_mun"], strict=True)]
    t1["minuto"] = pd.array([minuto_truncado(b, DIA_T1) for b in t1["encerramento_bsb"]],
                            dtype="Int64")
    for nome, lim in LIMIARES:
        t1[nome] = t1["minuto"] >= lim
    t1["regiao"] = t1["uf"].map(REGIAO)
    if LOG_T1.exists():
        lg = pd.read_parquet(LOG_T1, columns=["uf", "cd_mun", "zona", "secao", "votos_log",
                                              "votos_apos_17h"])
        lg = lg.rename(columns={"votos_log": "votos_log", "votos_apos_17h": "votos_log_17h"})
        t1 = t1.merge(lg, on=["uf", "cd_mun", "zona", "secao"], how="left")
    else:
        t1["votos_log"] = np.nan
        t1["votos_log_17h"] = np.nan
    return t1


def juntar(t2: pd.DataFrame, t1: pd.DataFrame) -> pd.DataFrame:
    t1r = t1.rename(columns={c: f"{c}_t1" for c in t1.columns
                             if c not in ("uf", "cd_mun", "zona", "secao")})
    df = t2.merge(t1r.drop(columns=["regiao_t1"]), on=["uf", "cd_mun", "zona", "secao"],
                  how="left")
    df["tem_t1"] = df["validos_t1"].notna() & (df["validos_t1"] > 0)
    df["pct13_t2"] = 100 * df["votos_13"] / df["validos_t2"].where(df["validos_t2"] > 0)
    df["pct22_t2"] = 100 * df["votos_22"] / df["validos_t2"].where(df["validos_t2"] > 0)
    df["pct13_t1"] = 100 * df["votos_13_t1"] / df["validos_t1"].where(df["validos_t1"] > 0)
    df["pct22_t1"] = 100 * df["votos_22_t1"] / df["validos_t1"].where(df["validos_t1"] > 0)
    dois = (df["votos_13_t1"] + df["votos_22_t1"])
    df["pct13_2p_t1"] = 100 * df["votos_13_t1"] / dois.where(dois > 0)
    df["comp_t2"] = 100 * df["comparecimento"] / df["aptos"].where(df["aptos"] > 0)
    df["comp_t1"] = 100 * df["comparecimento_t1"] / df["aptos_t1"].where(df["aptos_t1"] > 0)
    df["d_pct13"] = df["pct13_t2"] - df["pct13_t1"]
    df["d_pct22"] = df["pct22_t2"] - df["pct22_t1"]
    df["d_pct13_2p"] = df["pct13_t2"] - df["pct13_2p_t1"]
    df["d_comp"] = df["comp_t2"] - df["comp_t1"]
    return df


# ---------------------------------------------------------------------------
# Estatística simples
# ---------------------------------------------------------------------------

def dif_medias(x: Iterable[float], y: Iterable[float]) -> dict:
    """Diferença de médias (x - y) com IC de 95% de Welch."""
    from scipy import stats

    x = np.asarray([v for v in x if v is not None and not pd.isna(v)], dtype=float)
    y = np.asarray([v for v in y if v is not None and not pd.isna(v)], dtype=float)
    out = {"n_x": int(x.size), "n_y": int(y.size),
           "media_x": float(x.mean()) if x.size else None,
           "media_y": float(y.mean()) if y.size else None}
    if x.size < 2 or y.size < 2:
        return {**out, "diferenca": None, "ic95": None, "p_welch": None}
    vx, vy = x.var(ddof=1) / x.size, y.var(ddof=1) / y.size
    se = math.sqrt(vx + vy)
    gl = (vx + vy) ** 2 / ((vx ** 2) / (x.size - 1) + (vy ** 2) / (y.size - 1)) if se else 1.0
    t = stats.t.ppf(0.975, gl)
    d = float(x.mean() - y.mean())
    p = float(stats.ttest_ind(x, y, equal_var=False).pvalue) if se else None
    return {**out, "diferenca": d, "ic95": [d - t * se, d + t * se], "p_welch": p}


def did_estratos(df: pd.DataFrame, col: str, grupo_col: str = "grupo_t2",
                 tratado: str = "tardia", controle: str = "no_horario",
                 estrato: Iterable[str] = ("uf", "cd_mun", "zona"),
                 n_boot: int = 2000, seed: int = 2026) -> dict:
    """Diferença em diferenças por estrato (mesma UF, município e zona).

    Em cada estrato com ao menos uma seção de cada grupo, toma a média de `col`
    (variação 1º -> 2º turno de cada seção) nas tratadas menos a média nos
    controles; a estimativa é a média dessas diferenças ponderada pelo número
    de tratadas. IC de 95% por bootstrap das seções dentro de cada estrato."""
    d = df[df[grupo_col].isin([tratado, controle]) & df[col].notna()]
    blocos = []
    for _k, g in d.groupby(list(estrato), sort=True):
        xt = g.loc[g[grupo_col] == tratado, col].to_numpy(float)
        xc = g.loc[g[grupo_col] == controle, col].to_numpy(float)
        if xt.size and xc.size:
            blocos.append((xt, xc))
    if not blocos:
        return {"estratos": 0, "tratadas": 0, "controles": 0, "estimativa": None, "ic95": None}
    w = np.array([b[0].size for b in blocos], float)
    est = float(np.sum(w * np.array([b[0].mean() - b[1].mean() for b in blocos])) / w.sum())
    rng = np.random.default_rng(seed)
    boots = np.zeros(n_boot)
    for xt, xc in blocos:
        mt = rng.choice(xt, size=(n_boot, xt.size), replace=True).mean(axis=1)
        mc = rng.choice(xc, size=(n_boot, xc.size), replace=True).mean(axis=1)
        boots += xt.size * (mt - mc)
    boots /= w.sum()
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return {"estratos": len(blocos), "tratadas": int(w.sum()),
            "controles": int(sum(b[1].size for b in blocos)),
            "estimativa": est, "ic95": [float(lo), float(hi)]}


def residuos_estrato(df: pd.DataFrame, col: str = "d_pct13") -> pd.DataFrame:
    """Para cada tardia, o desvio de `col` em relação à média dos controles do
    mesmo estrato, em desvios-padrão dos controles (z). Estratos com menos de
    5 controles ficam sem z."""
    d = df[df[col].notna()]
    cont = d[d["grupo_t2"] == "no_horario"].groupby(["uf", "cd_mun", "zona"])[col].agg(
        ["mean", "std", "count"])
    t = d[d["grupo_t2"] == "tardia"].join(cont, on=["uf", "cd_mun", "zona"])
    t["esperado"] = t["mean"]
    t["residuo"] = t[col] - t["mean"]
    t["z"] = np.where(t["count"] >= 5, t["residuo"] / t["std"].where(t["std"] > 0), np.nan)
    return t.drop(columns=["mean", "std", "count"])


# ---------------------------------------------------------------------------
# Cenários de impacto
# ---------------------------------------------------------------------------

def cenarios_impacto(am: pd.DataFrame, diferenca_oficial: int) -> dict:
    """Cenários de quanto os votos depois das 17h das seções tardias poderiam
    mover a diferença 13 - 22 (positivo = a favor do 13). `am` tem as tardias
    com contagem do log (votos_apos_17h00), votos_13, votos_22, comparecimento,
    validos_t2 e o 1º turno da seção (votos_13_t1, votos_22_t1).

    (a) extremo: todos os votos depois das 17h foram para um só candidato; se
        fossem retirados, a diferença mudaria no máximo pelo total deles.
    (b) fatia da seção: cada voto depois das 17h dividido como o total da
        seção no 2º turno (13 - 22 sobre o comparecimento).
    (c) fatia do 1º turno da mesma seção: divisão do 1º turno entre 13 e 22
        (dois candidatos), aplicada à fração de votos válidos do 2º turno.
        Não há como saber a fatia dos votos antes das 17h: o RDV é embaralhado
        e o log não registra o candidato."""
    a = am[am["votos_apos_17h00"].notna()]
    v17 = a["votos_apos_17h00"].astype(float)
    comp = a["comparecimento"].astype(float).where(a["comparecimento"] > 0)
    margem_t2 = (a["votos_13"] - a["votos_22"]) / comp
    dois_t1 = (a["votos_13_t1"] + a["votos_22_t1"]).astype(float)
    margem_t1 = ((a["votos_13_t1"] - a["votos_22_t1"]) / dois_t1.where(dois_t1 > 0)
                 * a["validos_t2"] / comp)
    total = int(v17.sum())
    b = float((v17 * margem_t2).sum())
    c_ok = margem_t1.notna()
    c = float((v17[c_ok] * margem_t1[c_ok]).sum())
    sem_t1 = int(v17[~c_ok].sum())
    lim = abs(diferenca_oficial)
    return {
        "diferenca_oficial_13_menos_22": diferenca_oficial,
        "secoes_com_log": int(len(a)),
        "votos_apos_17h": total,
        "a_extremo_todos_para_um": {"desloca_ate": total,
                                    "diferenca_se_todos_fossem_do_13_e_retirados":
                                        diferenca_oficial - total,
                                    "diferenca_se_todos_fossem_do_22_e_retirados":
                                        diferenca_oficial + total,
                                    "altera_resultado": total >= lim},
        "b_fatia_da_secao_no_t2": {"saldo_13_menos_22": round(b, 1),
                                   "diferenca_sem_eles": round(diferenca_oficial - b, 1),
                                   "altera_resultado": abs(b) >= lim and np.sign(b) == np.sign(
                                       diferenca_oficial)},
        "c_fatia_da_secao_no_t1": {"saldo_13_menos_22": round(c, 1),
                                   "votos_sem_t1": sem_t1,
                                   "diferenca_sem_eles": round(diferenca_oficial - c, 1),
                                   "altera_resultado": abs(c) >= lim and np.sign(c) == np.sign(
                                       diferenca_oficial)},
    }


def _inverter(dif: int, votos: float, saldo: float) -> dict:
    """Margem recalculada e votos necessários para inverter, retirando `votos`
    (com saldo 13 - 22 igual a `saldo` quando retirados na fatia de cada seção)."""
    m = saldo / votos if votos else 0.0
    nec_13 = abs(dif) + 1
    nec_prop = (abs(dif) + 1) / m if m > 0 else None
    return {
        "votos_retirados": round(votos, 1),
        "margem_se_todos_retirados_do_13": round(dif - votos, 1),
        "margem_se_retirados_na_fatia_da_secao": round(dif - saldo, 1),
        "saldo_13_menos_22_retirado_na_fatia": round(saldo, 1),
        "margem_media_por_voto": round(m, 5),
        "necessarios_para_inverter_todos_do_13": nec_13,
        "vezes_o_observado_todos_do_13": round(nec_13 / votos, 2) if votos else None,
        "necessarios_para_inverter_na_fatia": None if nec_prop is None else round(nec_prop),
        "vezes_o_observado_na_fatia": (None if nec_prop is None or not votos
                                       else round(nec_prop / votos, 2)),
        "altera_resultado_todos_do_13": votos >= abs(dif),
        "altera_resultado_na_fatia": saldo >= abs(dif),
    }


def cenario_descarte(df: pd.DataFrame, am: pd.DataFrame, t1: pd.DataFrame, dif: int,
                     frac_validos: float = 0.966) -> dict:
    """Cenário "descartar os votos dados depois das 17:00:00 de Brasília" no país.

    Componentes (votos depois das 17h, por seção):
      exato_log         seções da amostra com log do 2º turno lido (contagem exata)
      teto_sem_log      tardias e intermediárias sem log: teto = comparecimento
      estimado_horario  seções que fecharam até 17:10 sem log: o próprio 1º
                        turno (log) vezes a razão 2º/1º turno medida na
                        amostra aleatória de seções no horário
      estimado_nao_coletadas  seções do país sem BU coletado no 2º turno: o
                        1º turno da seção vezes a mesma razão (fila normal)
    Corte "além do normal", em duas versões: desconta de cada tardia ou
    intermediária (a) o que a mesma seção teve depois das 17h no 1º turno ou
    (b) a taxa de votos depois das 17h dos controles pareados do 2º turno vezes
    o comparecimento; seções no horário e não coletadas contam zero. Teto
    "fila do 1º turno": o número de votos depois das 17h do 1º turno em todas
    as seções do país (como se a fila do 2º turno tivesse sido igual). Saldo 13 - 22
    de cada voto retirado: fatia da seção no 2º turno; não coletadas usam a
    fatia de dois candidatos do 1º turno vezes `frac_validos`."""
    chaves_am = dict(zip(am["chave"], am["votos_apos_17h00"], strict=True))
    d = df.copy()
    d["chave"] = d["uf"] + "/" + d["cd_mun"] + "/" + d["zona"] + "/" + d["secao"]
    d["v17_log"] = d["chave"].map(chaves_am)
    ctrl = am[(am["papel"] == "controle") & am["votos_apos_17h00"].notna()]
    taxa_ctrl = float(ctrl["votos_apos_17h00"].sum() / max(1, ctrl["comparecimento"].sum()))
    alea = am[(am["papel"] == "aleatoria_horario") & am["votos_apos_17h00"].notna()
              & am["votos_log_17h_t1"].notna()]
    razao = (float(alea["votos_apos_17h00"].sum() / alea["votos_log_17h_t1"].sum())
             if len(alea) and alea["votos_log_17h_t1"].sum() > 0 else 1.0)
    comp = d["comparecimento"].fillna(0).astype(float)
    normal_t1 = d["votos_log_17h_t1"].astype(float)
    normal = normal_t1.fillna(comp * taxa_ctrl)
    atrasada = d["grupo_t2"].isin(["tardia", "intermediaria"])
    tem_log = d["v17_log"].notna()
    comp_ = "exato_log"
    d["componente"] = np.select(
        [tem_log, atrasada & ~tem_log],
        [comp_, "teto_sem_log"], default="estimado_horario")
    d["v17"] = np.where(tem_log, d["v17_log"],
                        np.where(atrasada, comp, normal_t1.fillna(comp * taxa_ctrl) * razao))
    d["v17_extra"] = np.where(atrasada, np.clip(d["v17"] - normal, 0, None), 0.0)
    d["v17_extra_ctrl"] = np.where(atrasada, np.clip(d["v17"] - comp * taxa_ctrl, 0, None), 0.0)
    marg = ((d["votos_13"] - d["votos_22"]) / comp.where(comp > 0)).fillna(0)
    d["saldo"] = d["v17"] * marg
    d["saldo_extra"] = d["v17_extra"] * marg
    d["saldo_extra_ctrl"] = d["v17_extra_ctrl"] * marg

    cob = set(d["chave"])
    t = t1.copy()
    t["chave"] = t["uf"] + "/" + t["cd_mun"] + "/" + t["zona"] + "/" + t["secao"]
    nc = t[~t["chave"].isin(cob)]
    dois = (nc["votos_13"] + nc["votos_22"]).astype(float)
    m_nc = ((nc["votos_13"] - nc["votos_22"]) / dois.where(dois > 0)).fillna(0) * frac_validos
    v_nc = nc["votos_log_17h"].fillna(0).astype(float) * razao

    comps = {}
    for nome, g in d.groupby("componente"):
        comps[nome] = {"secoes": int(len(g)), "votos_apos_17h": round(float(g["v17"].sum()), 1),
                       "votos_alem_do_normal": round(float(g["v17_extra"].sum()), 1)}
    comps["estimado_nao_coletadas"] = {"secoes": int(len(nc)),
                                       "votos_apos_17h": round(float(v_nc.sum()), 1),
                                       "votos_alem_do_normal": None}
    total = float(d["v17"].sum() + v_nc.sum())
    saldo = float(d["saldo"].sum() + (v_nc * m_nc).sum())
    extra = float(d["v17_extra"].sum())
    saldo_extra = float(d["saldo_extra"].sum())
    so_tardias = d[atrasada]
    return {
        "diferenca_oficial_13_menos_22": dif,
        "taxa_controles_apos_17h": round(taxa_ctrl, 5),
        "razao_t2_t1_fila_normal": round(razao, 4),
        "secoes_amostra_aleatoria": int(len(alea)),
        "componentes": comps,
        "corte_17h00": _inverter(dif, total, saldo),
        "corte_17h00_so_tardias_e_intermediarias": _inverter(
            dif, float(so_tardias["v17"].sum()), float(so_tardias["saldo"].sum())),
        "corte_alem_do_normal": _inverter(dif, extra, saldo_extra),
        "corte_alem_do_normal_controles": _inverter(
            dif, float(d["v17_extra_ctrl"].sum()), float(d["saldo_extra_ctrl"].sum())),
        "teto_fila_do_t1_em_todo_o_pais": _inverter(
            dif, float(t["votos_log_17h"].fillna(0).sum()),
            float((t["votos_log_17h"].fillna(0) * (
                (t["votos_13"] - t["votos_22"]) / (t["votos_13"] + t["votos_22"]).where(
                    (t["votos_13"] + t["votos_22"]) > 0)).fillna(0) * frac_validos).sum())),
        "maximo_votos_apos_17h_numa_secao_com_log": int(d["v17_log"].max())
        if tem_log.any() else None,
        "referencia_t1_votos_apos_17h_brasil": int(t1["votos_log_17h"].fillna(0).sum()),
    }


# ---------------------------------------------------------------------------
# Resumos
# ---------------------------------------------------------------------------

def _soma(df: pd.DataFrame, cols: Iterable[str]) -> dict:
    return {c: int(df[c].fillna(0).sum()) for c in cols}


def agregado_votos(df: pd.DataFrame) -> dict:
    s = _soma(df, ["aptos", "comparecimento", "votos_13", "votos_22", "validos_t2",
                   "votos_13_t1", "votos_22_t1", "validos_t1", "aptos_t1", "comparecimento_t1"])
    s["secoes"] = int(len(df))

    def pct(a, b):
        return round(100 * a / b, 3) if b else None
    s["pct13_t2"] = pct(s["votos_13"], s["validos_t2"])
    s["pct22_t2"] = pct(s["votos_22"], s["validos_t2"])
    s["pct13_t1"] = pct(s["votos_13_t1"], s["validos_t1"])
    s["pct22_t1"] = pct(s["votos_22_t1"], s["validos_t1"])
    s["comp_t2"] = pct(s["comparecimento"], s["aptos"])
    s["comp_t1"] = pct(s["comparecimento_t1"], s["aptos_t1"])
    s["saldo_13_menos_22_t2"] = s["votos_13"] - s["votos_22"]
    s["saldo_13_menos_22_t1"] = s["votos_13_t1"] - s["votos_22_t1"]
    return s


def inventario(df: pd.DataFrame, por: list[str], prefixo: str) -> pd.DataFrame:
    cols = [f"{prefixo}{n}" for n, _ in LIMIARES]
    g = df.groupby(por, dropna=False)
    out = g.size().rename("secoes").to_frame()
    for c in cols:
        out[c.removeprefix(prefixo)] = g[c].sum().astype(int)
    return out.reset_index()


def total_oficial(indice: Path = INDICE_TOTAIS, arquivo: Optional[Path] = None) -> dict:
    """Totais do Brasil no 2º turno: arquivo -u.json do TSE (se dado) ou a
    última versão 'br' do índice versionado."""
    if arquivo and arquivo.exists():
        d = json.loads(arquivo.read_text(encoding="utf-8"))
        cand = {}
        for c in d["carg"][0]["agr"]:
            for p in c["par"]:
                for k in p["cand"]:
                    cand[k["n"]] = int(k["vap"])
        return {"fonte": str(arquivo.name), "dg": d.get("dg"), "hg": d.get("hg"),
                "secoes_totalizadas": int(d["s"]["st"]), "secoes_total": int(d["s"]["ts"]),
                "votos_13": cand.get("13"), "votos_22": cand.get("22"),
                "comparecimento": int(d["e"]["c"])}
    ult = None
    for ln in indice.read_text(encoding="utf-8").splitlines():
        r = json.loads(ln)
        if r.get("abr") == "br" and (ult is None or r["coletado_em"] >= ult["coletado_em"]):
            ult = r
    return {"fonte": "indice.jsonl", "dg": ult["dg"], "hg": ult["hg"],
            "secoes_totalizadas": ult["st"], "secoes_total": ult["ts"],
            "votos_13": ult["cand"]["13"], "votos_22": ult["cand"]["22"],
            "comparecimento": None}


def _num(x) -> str:
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return "n/d"
    if isinstance(x, float):
        return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{x:,}".replace(",", ".")


def tabela_md(df: pd.DataFrame, colunas: Optional[list[str]] = None) -> str:
    colunas = colunas or list(df.columns)
    linhas = ["| " + " | ".join(colunas) + " |", "|" + "---|" * len(colunas)]
    for r in df[colunas].itertuples(index=False):
        linhas.append("| " + " | ".join(_num(v) if not isinstance(v, str) else v
                                        for v in r) + " |")
    return "\n".join(linhas)


def montar(args) -> dict:
    saida = Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)
    t2 = carregar_t2(Path(args.encerramento))
    t1 = carregar_t1()
    df = juntar(t2, t1)
    log.info("2º turno: %d seções; com 1º turno: %d", len(df), int(df["tem_t1"].sum()))

    amostra = escolher_controles(df)
    cache_path = saida / "logs_contagens.jsonl"
    if args.baixar_logs:
        asyncio.run(baixar_logs(amostra, cache_path, rate=args.rate))
    cache = ler_cache(cache_path)
    amostra["chave"] = amostra.apply(chave, axis=1)
    chaves = set(amostra["chave"])
    cont = pd.DataFrame([v for k, v in cache.items() if k in chaves])
    if not cont.empty:
        cont = cont[cont["hash"].isin(amostra["hash"])]  # BU trocou de versão: refazer
        am = amostra.merge(cont.drop(columns=["hash"]), on="chave", how="left")
    else:
        am = amostra.copy()
    for c in ("votos_apos_17h00", "votos_log", "erro"):
        if c not in am.columns:
            am[c] = np.nan
    am.to_parquet(saida / "amostra_logs.parquet", index=False)
    df.to_parquet(saida / "secoes_t1_t2.parquet", index=False)

    # Cobertura por UF
    secoes_t1_uf = t1.groupby("uf").size()
    cobertura = (df.groupby("uf").size().rename("secoes_t2_coletadas").to_frame()
                 .join(secoes_t1_uf.rename("secoes_t1"), how="right").fillna(0).astype(int))
    cobertura["pct"] = (100 * cobertura["secoes_t2_coletadas"] / cobertura["secoes_t1"]).round(1)
    cobertura = cobertura.reset_index()
    cobertura["regiao"] = cobertura["uf"].map(REGIAO)

    # Inventário 2º turno e 1º turno (todas as seções e só as já coletadas no 2º)
    inv_uf_t2 = inventario(df, ["regiao", "uf"], "t2_")
    inv_reg_t2 = inventario(df, ["regiao"], "t2_")
    inv_mun_t2 = inventario(df, ["uf", "cd_mun", "municipio"], "t2_")
    inv_mun_t2 = inv_mun_t2[inv_mun_t2["apos_17h30"] > 0].sort_values("apos_17h30",
                                                                       ascending=False)
    t1c = t1.rename(columns={n: f"t1_{n}" for n, _ in LIMIARES})
    inv_uf_t1 = inventario(t1c, ["regiao", "uf"], "t1_")
    cobertos = df.loc[df["tem_t1"], ["uf", "cd_mun", "zona", "secao"]]
    t1_cob = t1c.merge(cobertos, on=["uf", "cd_mun", "zona", "secao"])
    inv_uf_t1_cob = inventario(t1_cob, ["regiao", "uf"], "t1_")
    inv_reg_t1_cob = inventario(t1_cob, ["regiao"], "t1_")
    inv_mun_t1_cob = inventario(t1_cob, ["uf", "cd_mun"], "t1_")
    inv_mun = inv_mun_t2.merge(inv_mun_t1_cob, on=["uf", "cd_mun"], how="left",
                               suffixes=("", "_t1"))

    # Mesma seção nos dois turnos: tardia no 2º e no 1º?
    tard = df[df["grupo_t2"] == "tardia"]
    cruz = pd.crosstab(df["grupo_t2"], df["apos_17h30_t1"].fillna(False).astype(bool))

    # Comparação 1º x 2º turno
    grupos = {g: agregado_votos(df[df["grupo_t2"] == g]) for g in
              ("no_horario", "intermediaria", "tardia")}
    por_uf_tard = {uf: {"tardia": agregado_votos(g[g["grupo_t2"] == "tardia"]),
                        "no_horario": agregado_votos(g[g["grupo_t2"] == "no_horario"])}
                   for uf, g in df.groupby("uf") if (g["grupo_t2"] == "tardia").any()}
    por_reg_tard = {rg: {"tardia": agregado_votos(g[g["grupo_t2"] == "tardia"]),
                         "no_horario": agregado_votos(g[g["grupo_t2"] == "no_horario"])}
                    for rg, g in df.groupby("regiao")}
    estratos_tard = df[df["grupo_t2"] == "tardia"][["uf", "cd_mun", "zona"]].drop_duplicates()
    mesmo_estrato = df.merge(estratos_tard, on=["uf", "cd_mun", "zona"])
    controles_estrato = agregado_votos(mesmo_estrato[mesmo_estrato["grupo_t2"] == "no_horario"])

    dd = {}
    for col in ("d_pct13", "d_pct22", "d_pct13_2p", "d_comp"):
        dd[col] = {"brasil": did_estratos(df, col)}
        for uf in sorted(por_uf_tard):
            dd[col][uf] = did_estratos(df[df["uf"] == uf], col)
        for rg in sorted(df.loc[df["grupo_t2"] == "tardia", "regiao"].unique()):
            dd[col][rg] = did_estratos(df[df["regiao"] == rg], col)
    # fora da BA (para ver se o padrão é só da BA)
    fora_ba = df[df["uf"] != "ba"]
    for col in ("d_pct13", "d_comp"):
        dd[col]["fora_da_ba"] = did_estratos(fora_ba, col)
        dd[col]["salvador_feira_lauro"] = did_estratos(
            df[df["cd_mun"].isin(["38490", "35157", "36854"])], col)

    # Distribuição da fatia do 13 (tardias x controles do mesmo estrato)
    ctrl_mesmo = mesmo_estrato[mesmo_estrato["grupo_t2"] == "no_horario"]
    dist = {}
    for nome, serie in (("tardia", tard["pct13_t2"]), ("controle_mesmo_estrato",
                                                        ctrl_mesmo["pct13_t2"]),
                        ("tardia_t1", tard["pct13_t1"]), ("controle_t1", ctrl_mesmo["pct13_t1"])):
        s = serie.dropna()
        dist[nome] = {"n": int(s.size), "media": float(s.mean()) if s.size else None,
                      "quartis": [float(q) for q in s.quantile([0.1, 0.25, 0.5, 0.75, 0.9])]
                      if s.size else None}
    testes = {
        "pct13_t2_tardia_vs_controle": dif_medias(tard["pct13_t2"], ctrl_mesmo["pct13_t2"]),
        "pct13_t1_tardia_vs_controle": dif_medias(tard["pct13_t1"], ctrl_mesmo["pct13_t1"]),
        "d_pct13_tardia_vs_controle": dif_medias(tard["d_pct13"], ctrl_mesmo["d_pct13"]),
        "d_comp_tardia_vs_controle": dif_medias(tard["d_comp"], ctrl_mesmo["d_comp"]),
    }
    hist = {}
    bins = list(range(0, 101, 10))
    for nome, serie in (("tardia", tard["pct13_t2"]), ("controle", ctrl_mesmo["pct13_t2"])):
        h, _ = np.histogram(serie.dropna(), bins=bins)
        hist[nome] = [int(x) for x in h]

    res = residuos_estrato(df)
    extremos = res[res["z"].abs() >= 3].sort_values("z", key=abs, ascending=False)
    cols_ext = ["uf", "municipio", "zona", "secao", "encerramento_bsb", "comparecimento",
                "pct13_t1", "pct13_t2", "d_pct13", "esperado", "residuo", "z"]

    # Log: votos depois das 17h
    ok = am[am["votos_apos_17h00"].notna()]
    log_res = {}
    for papel, g in ok.groupby("papel"):
        log_res[papel] = {
            "secoes": int(len(g)),
            "comparecimento": int(g["comparecimento"].sum()),
            **{f"votos_{n}": int(g[f"votos_{n}"].sum()) for n, _ in CORTES_LOG},
            "media_votos_apos_17h": float(g["votos_apos_17h00"].mean()),
            "pct_comparecimento_apos_17h": round(100 * g["votos_apos_17h00"].sum()
                                                 / g["comparecimento"].sum(), 3),
            "secoes_log_diverge_bu": int((g["diferenca_log_bu"].fillna(0) != 0).sum()),
        }
    erros_log = am["erro"].dropna().astype(str).str.split(":").str[0].value_counts().to_dict()
    log_uf = []
    for (uf, papel), g in ok.groupby(["uf", "papel"]):
        log_uf.append({"uf": uf, "papel": papel, "secoes": len(g),
                       "comparecimento": int(g["comparecimento"].sum()),
                       **{f"votos_{n}": int(g[f"votos_{n}"].sum()) for n, _ in CORTES_LOG}})
    log_uf = pd.DataFrame(log_uf)

    # Excesso sobre o normal: votos depois das 17h além do que os controles
    # pareados (fila normal) tiveram, proporcional ao comparecimento
    tard_log = ok[ok["papel"] == "tardia"]
    ctrl_log = ok[ok["papel"] == "controle"]
    taxa_ctrl = (ctrl_log.groupby("estrato")["votos_apos_17h00"].sum()
                 / ctrl_log.groupby("estrato")["comparecimento"].sum())
    esperado = tard_log["comparecimento"] * tard_log["estrato"].map(taxa_ctrl).fillna(
        ctrl_log["votos_apos_17h00"].sum() / max(1, ctrl_log["comparecimento"].sum()))
    excesso = float((tard_log["votos_apos_17h00"] - esperado).sum())

    oficial = total_oficial(arquivo=Path(args.total_oficial) if args.total_oficial else None)
    dif = int(oficial["votos_13"]) - int(oficial["votos_22"])
    cen = {"brasil": cenarios_impacto(tard_log, dif)}
    for uf, g in tard_log.groupby("uf"):
        cen[uf] = cenarios_impacto(g, dif)
    # Limites que não dependem do log: anular todas as seções tardias
    cen["anular_todas_as_tardias"] = {
        "secoes": int(len(tard)),
        "saldo_13_menos_22": int((tard["votos_13"] - tard["votos_22"]).sum()),
        "comparecimento": int(tard["comparecimento"].sum()),
        "diferenca_sem_elas": int(dif - (tard["votos_13"] - tard["votos_22"]).sum()),
    }
    # Tardias sem contagem de log: extrapola pela razão votos 17h / comparecimento
    sem_log = tard[~tard.apply(chave, axis=1).isin(set(tard_log["chave"]))]
    razao = tard_log["votos_apos_17h00"].sum() / max(1, tard_log["comparecimento"].sum())
    frac = (oficial["comparecimento"] and
            (int(oficial["votos_13"]) + int(oficial["votos_22"])) / oficial["comparecimento"])
    cen["descarte_apos_horario"] = cenario_descarte(df, am, t1, dif, frac or 0.966)
    cen["tardias_sem_log"] = {"secoes": int(len(sem_log)),
                              "votos_apos_17h_estimados": round(float(
                                  sem_log["comparecimento"].sum() * razao), 1)}

    resumo = {
        "gerado_em": datetime.now().astimezone().isoformat(timespec="seconds"),
        "observacao": ("Descritivo. 2º turno com cobertura parcial (BUs coletados até a "
                       "execução de analisar_encerramento_t2.py). Encerramento em Brasília "
                       "pelo minuto truncado. Tardia = depois de 17:30; controle = até 17:10 "
                       "no mesmo município e zona. Votos depois das 17h contados no log "
                       "da urna (data 25/10/2026, hora local convertida)."),
        "limiares": ROTULO_LIMIAR,
        "total_oficial_t2": {**oficial, "diferenca_13_menos_22": dif},
        "cobertura_por_uf": cobertura.to_dict("records"),
        "secoes_t2": int(len(df)), "secoes_t2_com_t1": int(df["tem_t1"].sum()),
        "inventario_t2_por_regiao": inv_reg_t2.to_dict("records"),
        "inventario_t2_por_uf": inv_uf_t2.to_dict("records"),
        "inventario_t1_por_uf_todas": inv_uf_t1.to_dict("records"),
        "inventario_t1_por_uf_cobertas": inv_uf_t1_cob.to_dict("records"),
        "inventario_t1_por_regiao_cobertas": inv_reg_t1_cob.to_dict("records"),
        "inventario_municipios_t2_vs_t1": inv_mun.head(60).to_dict("records"),
        "grupo_t2_x_tardia_t1": {str(k): {str(c): int(v) for c, v in r.items()}
                                 for k, r in cruz.to_dict("index").items()},
        "votos_por_grupo": grupos,
        "votos_controles_mesmo_estrato": controles_estrato,
        "votos_por_uf_tardias": por_uf_tard,
        "votos_por_regiao": por_reg_tard,
        "diferenca_em_diferencas": dd,
        "distribuicao_pct13": dist, "histograma_pct13_t2": {"bins": bins, **hist},
        "testes": testes,
        "extremos_z3": extremos[cols_ext].head(40).to_dict("records"),
        "n_extremos_z3": int(len(extremos)),
        "n_tardias_com_z": int(res["z"].notna().sum()),
        "amostra_logs": {"tardias": int((amostra["papel"] == "tardia").sum()),
                         "controles": int((amostra["papel"] == "controle").sum()),
                         "tardias_sem_controle": int(len(tard) - (am["papel"] == "tardia").sum()),
                         "com_contagem": int(len(ok)), "erros": erros_log},
        "log_votos_apos_17h": log_res,
        "excesso_votos_apos_17h_sobre_controles": round(excesso, 1),
        "cenarios_impacto": cen,
    }
    (saida / "resumo.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=1,
                                                  default=_json_default), encoding="utf-8")

    # Tabelas em Markdown
    partes = ["# Tabelas geradas por impacto_prorrogacao_t2.py", ""]
    partes += ["## Cobertura por UF", tabela_md(cobertura, ["regiao", "uf", "secoes_t1",
                                                            "secoes_t2_coletadas", "pct"]), ""]
    partes += ["## Inventário 2º turno por UF", tabela_md(inv_uf_t2), ""]
    partes += ["## Inventário 1º turno por UF (só seções já coletadas no 2º)",
               tabela_md(inv_uf_t1_cob), ""]
    partes += ["## Inventário 1º turno por UF (todas as seções)", tabela_md(inv_uf_t1), ""]
    partes += ["## Municípios com seções depois de 17:30 no 2º turno",
               tabela_md(inv_mun.head(40)), ""]
    if not log_uf.empty:
        partes += ["## Votos no log depois dos cortes, por UF e papel", tabela_md(log_uf), ""]
    if len(extremos):
        partes += ["## Tardias com |z| >= 3 na variação da fatia do 13",
                   tabela_md(extremos[cols_ext].head(40)), ""]
    (saida / "tabelas.md").write_text("\n".join(partes) + "\n", encoding="utf-8")
    log.info("resumo gravado em %s", saida)
    return resumo


def _json_default(o):
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return None if math.isnan(o) else float(o)
    if isinstance(o, (np.bool_,)):
        return bool(o)
    if o is pd.NA or o is pd.NaT:
        return None
    if isinstance(o, (datetime, timedelta)):
        return str(o)
    raise TypeError(type(o))


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--encerramento", default=str(ENCERRAMENTO))
    ap.add_argument("--saida", default=str(SAIDA_PADRAO))
    ap.add_argument("--baixar-logs", action="store_true",
                    help="baixa o -log.jez da amostra que ainda não está no cache")
    ap.add_argument("--rate", type=float, default=3.0, help="req/s no download (máximo 3)")
    ap.add_argument("--total-oficial", help="br-c0001-e006258-u.json local (resultado do TSE)")
    args = ap.parse_args(argv)
    args.rate = min(args.rate, 3.0)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    montar(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
