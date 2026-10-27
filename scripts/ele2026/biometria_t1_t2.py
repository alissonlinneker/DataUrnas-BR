#!/usr/bin/env python3
"""Biometria por seção: 1º turno (04/10/2026) x 2º turno (25/10/2026), Presidente.

Duas fontes, as duas públicas:

1. BU (nacional). O BU da spec v2 traz, em DetalhamentoComparecimento
   (spec/v2/bu.asn1), três contagens que somam o comparecimento:
     comp_sem_biometria     qtdEleitoresCompareceramSemBiometria: compareceram e
                            NÃO tinham biometria cadastrada
     habilitados_biometria  qtdEleitoresHabilitadosPorBiometria: habilitados com
                            reconhecimento biométrico
     habilitados_biografia  qtdEleitoresHabilitadosPorBiografia: tinham biometria
                            cadastrada e foram habilitados por ano de nascimento
                            (habilitação manual depois de a digital não bater)
   A tabela pareada sai do ClickHouse com biometria_t1_t2_ch.sql
   (ref_secoes_2026_t1 x v_bu_ultima) e é cruzada com
   data/parquet/2026/t2/viradas/secoes_2026.parquet (votos 13/22 dos dois
   turnos, encerramento em Brasília, seções atípicas de viradas_t1_t2.py).

2. Log da urna (amostra). O -log.jez é um ZIP com logd.dat (texto latin-1,
   colunas data/hora, nível, id da urna, aplicação, mensagem, hash). Os eventos
   de habilitação do eleitor são da aplicação VOTA. Uma amostra estratificada
   de seções (no máximo 3.000) tem o log dos DOIS turnos baixado do TSE a no
   máximo 3 req/s, num único processo; o bruto fica em --brutos (no servidor de
   análise, fora do git). Só os eventos do dia de cada turno entram (o log do
   2º turno acumula o do 1º).

Saída em --saida (padrão data/parquet/2026/t2/biometria/, ignorada pelo git):
  secoes_biometria.parquet  seções pareadas com taxas e variações
  amostra.parquet           amostra dos logs (estrato e chaves)
  logs_secoes.parquet       métricas do log por seção e turno
  logs_vocabulario.csv      mensagens da VOTA ligadas à habilitação, com contagens
  extremos.csv              seções extremas (BU), com marcas de atípico e tardia
  resumo.json               todos os números do relatório
  tabelas.md                tabelas prontas

Uso (no servidor de análise; o Mac só orquestra):
  ch.sh < scripts/ele2026/biometria_t1_t2_ch.sql > /dev/shm/bio_in/secoes_biometria.parquet
  python3 scripts/ele2026/biometria_t1_t2.py --bu /dev/shm/bio_in/secoes_biometria.parquet \\
      --viradas /dev/shm/bio_in/viradas_secoes_2026.parquet --saida /dev/shm/bio_out \\
      --brutos ~/dataurnas-t2/biometria/brutos [--baixar-logs]
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import math
import re
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[2]
SRC = str(ROOT / "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

log = logging.getLogger("biometria_t1_t2")

CICLO = "ele2026"
PLEITO = {1: "3220", 2: "3221"}
DATA = {1: "04/10/2026", 2: "25/10/2026"}
DIA_T2 = "2026-10-25"
CHAVES = ["uf", "cd_mun", "zona", "secao"]
LIMITE_TARDIA = 31  # tardia: encerrou 17:31:00 de Brasília ou depois (mesma regra do impacto)
MIN_COMP = 20       # comparecimento mínimo para listar seção extrema
TAMANHO_AMOSTRA = 3000
SEED = 2026

REGIAO = {
    **dict.fromkeys(("ac", "am", "ap", "pa", "ro", "rr", "to"), "Norte"),
    **dict.fromkeys(("al", "ba", "ce", "ma", "pb", "pe", "pi", "rn", "se"), "Nordeste"),
    **dict.fromkeys(("df", "go", "ms", "mt"), "Centro-Oeste"),
    **dict.fromkeys(("es", "mg", "rj", "sp"), "Sudeste"),
    **dict.fromkeys(("pr", "rs", "sc"), "Sul"),
    "zz": "Exterior",
}

SAIDA_PADRAO = ROOT / "data" / "parquet" / "2026" / "t2" / "biometria"


def _r(x, n: int = 4):
    if x is None:
        return None
    try:
        if isinstance(x, (float, np.floating)) and (math.isnan(x) or math.isinf(x)):
            return None
    except TypeError:
        return None
    if isinstance(x, (np.integer,)):
        return int(x)
    return round(float(x), n) if isinstance(x, (float, np.floating)) else x


def _ordem(k: str) -> str:
    """Ordem pseudoaleatória estável de uma seção."""
    return hashlib.sha256(f"{SEED}/biometria/{k}".encode()).hexdigest()


# ---------------------------------------------------------------------------
# BU
# ---------------------------------------------------------------------------

def minuto_bsb(v) -> Optional[int]:
    """Minutos inteiros (segundos desprezados) entre 17:00 de Brasília de 25/10 e v."""
    if v is None or (isinstance(v, float) and math.isnan(v)) or v is pd.NA:
        return None
    dt = datetime.strptime(str(v)[:19], "%Y-%m-%d %H:%M:%S")
    ref = datetime.strptime(DIA_T2, "%Y-%m-%d").replace(hour=17)
    return int((dt.replace(second=0) - ref).total_seconds() // 60)


def carregar(bu: Path, viradas: Path) -> pd.DataFrame:
    df = pd.read_parquet(bu)
    for c in CHAVES:
        df[c] = df[c].astype(str)
    v = pd.read_parquet(viradas, columns=CHAVES + [
        "v13_1", "v22_1", "v13_2", "v22_2", "fatia13_1", "fatia13_2", "delta_fatia",
        "virada", "atipico", "encerramento_bsb_2", "codigo_carga_1"])
    for c in CHAVES:
        v[c] = v[c].astype(str)
    df = df.merge(v, on=CHAVES, how="left", validate="one_to_one")
    df["regiao"] = df["uf"].map(REGIAO)
    df["chave"] = df["uf"] + "/" + df["cd_mun"] + "/" + df["zona"] + "/" + df["secao"]
    for k in (1, 2):
        comp = df[f"comp_{k}"].astype("float")
        sem = df[f"sem_bio_{k}"].astype("float")
        hb = df[f"hab_bio_{k}"].astype("float")
        hg = df[f"hab_biog_{k}"].astype("float")
        ok = sem.notna() & (comp > 0)
        df[f"tem_det_{k}"] = ok
        df[f"tx_sem_{k}"] = np.where(ok, sem / comp.where(comp > 0, 1), np.nan)
        df[f"tx_bio_{k}"] = np.where(ok, hb / comp.where(comp > 0, 1), np.nan)
        cad = hb + hg
        df[f"tx_biog_{k}"] = np.where(ok & (cad > 0), hg / cad.where(cad > 0, 1), np.nan)
    df["pareada"] = df["tem_det_1"] & df["tem_det_2"]
    df["d_sem"] = df["tx_sem_2"] - df["tx_sem_1"]
    df["d_bio"] = df["tx_bio_2"] - df["tx_bio_1"]
    df["d_biog"] = df["tx_biog_2"] - df["tx_biog_1"]
    df["mesma_urna"] = (df["numero_interno_urna_1"].notna()
                        & (df["numero_interno_urna_1"] == df["numero_interno_urna_2"]))
    df["minuto_t2"] = [minuto_bsb(x) for x in df["encerramento_bsb_2"]]
    df["minuto_t2"] = df["minuto_t2"].astype("Int64")
    df["tardia"] = (df["minuto_t2"] >= LIMITE_TARDIA).fillna(False).astype(bool)
    df["atipico"] = df["atipico"].fillna(False).astype(bool)
    df["sentido_virada"] = df["virada"]  # "13->22", "22->13" ou vazio
    df["virada"] = (df["virada"].notna() & (df["virada"].astype(str).str.len() > 0)
                    & (df["virada"].astype(str) != "nan"))
    return df


def agregar(g: pd.DataFrame, k: int) -> dict:
    """Totais de um turno num recorte (só seções com detalhamento)."""
    g = g[g[f"tem_det_{k}"]]
    comp = int(g[f"comp_{k}"].sum())
    sem = int(g[f"sem_bio_{k}"].sum())
    hb = int(g[f"hab_bio_{k}"].sum())
    hg = int(g[f"hab_biog_{k}"].sum())
    return {
        "secoes": int(len(g)), "comparecimento": comp, "sem_biometria": sem,
        "hab_biometria": hb, "hab_biografia": hg,
        "pct_sem_biometria": _r(100 * sem / comp if comp else None),
        "pct_hab_biometria": _r(100 * hb / comp if comp else None),
        "pct_hab_biografia": _r(100 * hg / comp if comp else None),
        "pct_biografia_entre_cadastrados": _r(100 * hg / (hb + hg) if hb + hg else None),
        "secoes_100pct_sem_biometria": int(((g[f"sem_bio_{k}"] == g[f"comp_{k}"])
                                            & (g[f"comp_{k}"] >= MIN_COMP)).sum()),
        "secoes_zero_hab_biometria": int(((g[f"hab_bio_{k}"] == 0)
                                          & (g[f"comp_{k}"] >= MIN_COMP)).sum()),
    }


def tabela_por(df: pd.DataFrame, col: str, so_pareadas: bool = True) -> pd.DataFrame:
    base = df[df["pareada"]] if so_pareadas else df
    linhas = []
    for nome, g in base.groupby(col, dropna=False, sort=True):
        a, b = agregar(g, 1), agregar(g, 2)
        linhas.append({
            col: nome, "secoes": len(g),
            "pct_sem_bio_t1": a["pct_sem_biometria"], "pct_sem_bio_t2": b["pct_sem_biometria"],
            "pct_biog_cad_t1": a["pct_biografia_entre_cadastrados"],
            "pct_biog_cad_t2": b["pct_biografia_entre_cadastrados"],
            "pct_hab_bio_t1": a["pct_hab_biometria"], "pct_hab_bio_t2": b["pct_hab_biometria"],
            "comp_t1": a["comparecimento"], "comp_t2": b["comparecimento"],
            "hab_biog_t1": a["hab_biografia"], "hab_biog_t2": b["hab_biografia"],
        })
    t = pd.DataFrame(linhas)
    t["d_pp_sem_bio"] = t["pct_sem_bio_t2"] - t["pct_sem_bio_t1"]
    t["d_pp_biog_cad"] = t["pct_biog_cad_t2"] - t["pct_biog_cad_t1"]
    return t


def correl(x: pd.Series, y: pd.Series) -> dict:
    """Pearson e Spearman, com p bilateral aproximado (transformação de Fisher)."""
    m = x.notna() & y.notna()
    x, y = x[m].astype(float), y[m].astype(float)
    n = int(m.sum())
    if n < 10:
        return {"n": n}

    def p_fisher(r: float) -> Optional[float]:
        if abs(r) >= 1:
            return 0.0
        z = math.atanh(r) * math.sqrt(n - 3)
        return math.erfc(abs(z) / math.sqrt(2))

    rp = float(np.corrcoef(x, y)[0, 1])
    rs = float(np.corrcoef(x.rank(), y.rank())[0, 1])
    return {"n": n, "pearson": _r(rp, 5), "p_pearson": _r(p_fisher(rp), 6),
            "spearman": _r(rs, 5), "p_spearman": _r(p_fisher(rs), 6)}


def correl_dentro(df: pd.DataFrame, x: str, y: str, grupo: str) -> dict:
    """Correlação depois de tirar a média de cada grupo (efeito fixo de UF ou município)."""
    m = df[x].notna() & df[y].notna()
    d = df.loc[m, [grupo, x, y]].copy()
    d[x] = d[x] - d.groupby(grupo)[x].transform("mean")
    d[y] = d[y] - d.groupby(grupo)[y].transform("mean")
    return correl(d[x], d[y])


def comparar_grupos(df: pd.DataFrame, marca: str, cols: list[str]) -> dict:
    """Média, mediana e erro padrão de cada coluna dentro e fora do grupo."""
    out = {}
    for c in cols:
        a = df.loc[df[marca], c].dropna().astype(float)
        b = df.loc[~df[marca], c].dropna().astype(float)
        if len(a) < 2 or len(b) < 2:
            continue
        ep = math.sqrt(a.var() / len(a) + b.var() / len(b))
        dif = a.mean() - b.mean()
        out[c] = {"n_grupo": len(a), "n_resto": len(b),
                  "media_grupo": _r(a.mean(), 5), "media_resto": _r(b.mean(), 5),
                  "mediana_grupo": _r(a.median(), 5), "mediana_resto": _r(b.median(), 5),
                  "diferenca": _r(dif, 5), "z": _r(dif / ep if ep else None, 2)}
    return out


def decis(df: pd.DataFrame, x: str, y: str) -> list[dict]:
    d = df[[x, y]].dropna()
    q = pd.qcut(d[x].rank(method="first"), 10, labels=False)
    out = []
    for i, g in d.groupby(q):
        out.append({"decil": int(i) + 1, "n": len(g), f"{x}_min": _r(g[x].min(), 5),
                    f"{x}_max": _r(g[x].max(), 5), f"{x}_media": _r(g[x].mean(), 5),
                    f"{y}_media": _r(g[y].mean(), 5)})
    return out


COLS_EXT = ["chave", "regiao", "modelo_urna_1", "tipo_urna_1", "tipo_urna_2", "mesma_urna",
            "comp_1", "sem_bio_1", "hab_bio_1", "hab_biog_1",
            "comp_2", "sem_bio_2", "hab_bio_2", "hab_biog_2",
            "tx_sem_1", "tx_sem_2", "tx_biog_1", "tx_biog_2", "d_sem", "d_biog",
            "fatia13_1", "fatia13_2", "delta_fatia", "virada", "atipico", "tardia",
            "minuto_t2", "encerramento_local_2"]


def extremos(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    p = df[df["pareada"] & (df["uf"] != "zz")
           & (df["comp_1"] >= MIN_COMP) & (df["comp_2"] >= MIN_COMP)]
    ex = {
        "biog_sobe": p.sort_values("d_biog", ascending=False).head(40),
        "biog_cai": p.sort_values("d_biog").head(40),
        "sem_bio_sobe": p.sort_values("d_sem", ascending=False).head(40),
        "sem_bio_cai": p.sort_values("d_sem").head(40),
        "bio_alta_para_quase_zero": p[(p["tx_bio_1"] >= 0.7) & (p["tx_bio_2"] <= 0.1)]
        .sort_values("d_bio").head(200),
        "cem_pct_sem_bio_t2": p[p["sem_bio_2"] == p["comp_2"]]
        .sort_values("comp_2", ascending=False).head(200),
        "cem_pct_sem_bio_t1": p[p["sem_bio_1"] == p["comp_1"]]
        .sort_values("comp_1", ascending=False).head(200),
    }
    return {k: v[COLS_EXT] for k, v in ex.items()}


def analisar_bu(df: pd.DataFrame) -> tuple[dict, dict]:
    br = df[df["uf"] != "zz"]
    res: dict = {"nacional": {}, "exterior": {}}
    for nome, base in (("todas", br), ("pareadas", br[br["pareada"]])):
        res["nacional"][nome] = {"t1": agregar(base, 1), "t2": agregar(base, 2)}
    zz = df[(df["uf"] == "zz") & df["pareada"]]
    res["exterior"] = {"t1": agregar(zz, 1), "t2": agregar(zz, 2)}
    res["cobertura"] = {
        "secoes_t2": int(len(df)), "secoes_t2_sem_detalhamento": int((~df["tem_det_2"]).sum()),
        "secoes_t2_sem_detalhamento_por_tipo_arquivo":
            {str(k): int(v) for k, v in df.loc[~df["tem_det_2"], "tipo_arquivo_2"]
             .value_counts(dropna=False).items()},
        "secoes_sem_t1_detalhamento": int((~df["tem_det_1"]).sum()),
        "pareadas_brasil": int(br["pareada"].sum()),
        "pareadas_mesma_urna": int((br["pareada"] & br["mesma_urna"]).sum()),
    }
    p = br[br["pareada"]]
    tabs = {
        "uf": tabela_por(br, "uf"),
        "regiao": tabela_por(br, "regiao"),
        "modelo_mesma_urna": tabela_por(br[br["mesma_urna"]], "modelo_urna_1"),
        "tipo_urna_t2": tabela_por(br, "tipo_urna_2"),
    }
    qs = [0.001, 0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99, 0.999]
    pc = p[(p["comp_1"] >= MIN_COMP) & (p["comp_2"] >= MIN_COMP)]
    res["distribuicao"] = {
        "n_secoes": int(len(pc)),
        "d_sem_pp_quantis": {str(q): _r(100 * pc["d_sem"].quantile(q), 3) for q in qs},
        "d_biog_pp_quantis": {str(q): _r(100 * pc["d_biog"].quantile(q), 3) for q in qs},
        "d_sem_pp_media": _r(100 * pc["d_sem"].mean(), 4),
        "d_sem_pp_desvio": _r(100 * pc["d_sem"].std(), 4),
        "d_biog_pp_media": _r(100 * pc["d_biog"].mean(), 4),
        "d_biog_pp_desvio": _r(100 * pc["d_biog"].std(), 4),
        "faixas_d_sem_pp": {
            f">= {lim}": int((pc["d_sem"].abs() >= lim / 100).sum()) for lim in (5, 10, 20, 50)},
        "faixas_d_biog_pp_sobe": {
            f">= {lim}": int((pc["d_biog"] >= lim / 100).sum()) for lim in (10, 20, 30, 50)},
        "faixas_d_biog_pp_cai": {
            f"<= -{lim}": int((pc["d_biog"] <= -lim / 100).sum()) for lim in (10, 20, 30, 50)},
        "tx_biog_t2_ge_50pct": int((pc["tx_biog_2"] >= 0.5).sum()),
        "tx_biog_t1_ge_50pct": int((pc["tx_biog_1"] >= 0.5).sum()),
        "bio_alta_para_quase_zero": int(((pc["tx_bio_1"] >= 0.7) & (pc["tx_bio_2"] <= 0.1)).sum()),
        "bio_quase_zero_para_alta": int(((pc["tx_bio_2"] >= 0.7) & (pc["tx_bio_1"] <= 0.1)).sum()),
        "cem_pct_sem_bio_t1": int((pc["sem_bio_1"] == pc["comp_1"]).sum()),
        "cem_pct_sem_bio_t2": int((pc["sem_bio_2"] == pc["comp_2"]).sum()),
        "cem_pct_sem_bio_os_dois": int(((pc["sem_bio_1"] == pc["comp_1"])
                                        & (pc["sem_bio_2"] == pc["comp_2"])).sum()),
        "mesma_urna_entre_extremos_d_biog_ge_30pp": int(
            pc.loc[pc["d_biog"].abs() >= 0.30, "mesma_urna"].sum()),
        "extremos_d_biog_ge_30pp": int((pc["d_biog"].abs() >= 0.30).sum()),
    }
    # correlação com o voto e com as marcas
    res["correlacoes"] = {
        "d_biog_x_delta_fatia": correl(pc["d_biog"], pc["delta_fatia"]),
        "d_biog_x_delta_fatia_dentro_uf": correl_dentro(pc, "d_biog", "delta_fatia", "uf"),
        "d_biog_x_delta_fatia_dentro_municipio": correl_dentro(
            pc.assign(mun=pc["uf"] + pc["cd_mun"]), "d_biog", "delta_fatia", "mun"),
        "d_sem_x_delta_fatia": correl(pc["d_sem"], pc["delta_fatia"]),
        "d_sem_x_delta_fatia_dentro_uf": correl_dentro(pc, "d_sem", "delta_fatia", "uf"),
        "d_sem_x_delta_fatia_dentro_municipio": correl_dentro(
            pc.assign(mun=pc["uf"] + pc["cd_mun"]), "d_sem", "delta_fatia", "mun"),
        "tx_biog_2_x_fatia13_2_dentro_municipio": correl_dentro(
            pc.assign(mun=pc["uf"] + pc["cd_mun"]), "tx_biog_2", "fatia13_2", "mun"),
        "tx_sem_2_x_fatia13_2_dentro_municipio": correl_dentro(
            pc.assign(mun=pc["uf"] + pc["cd_mun"]), "tx_sem_2", "fatia13_2", "mun"),
    }
    res["decis_d_biog_x_delta_fatia"] = decis(pc, "d_biog", "delta_fatia")
    res["decis_d_sem_x_delta_fatia"] = decis(pc, "d_sem", "delta_fatia")
    cols = ["d_sem", "d_biog", "tx_sem_1", "tx_sem_2", "tx_biog_1", "tx_biog_2"]
    res["grupos"] = {m: comparar_grupos(pc, m, cols) for m in ("atipico", "tardia", "virada")}
    res["grupos_contagem"] = {m: int(pc[m].sum()) for m in ("atipico", "tardia", "virada")}
    # perfil das seções extremas: modelo, troca de urna e voto
    ext = pc[pc["d_biog"].abs() >= 0.30]

    def contagem(s: pd.Series) -> dict:
        return {str(k): int(v) for k, v in s.value_counts(dropna=False).items()}

    n_mod = pc["modelo_urna_1"].value_counts()
    res["perfil_extremos_d_biog_30pp"] = {
        "n": int(len(ext)), "sobe": int((ext["d_biog"] > 0).sum()),
        "cai": int((ext["d_biog"] < 0).sum()),
        "modelo_urna_1": contagem(ext["modelo_urna_1"]),
        "mesma_urna": contagem(ext["mesma_urna"]),
        "tipo_urna_1": contagem(ext["tipo_urna_1"]), "tipo_urna_2": contagem(ext["tipo_urna_2"]),
        "atipicos": int(ext["atipico"].sum()), "tardias": int(ext["tardia"].sum()),
        "viradas": int(ext["virada"].sum()),
        "delta_fatia_media": _r(ext["delta_fatia"].mean(), 5),
        "delta_fatia_media_resto": _r(pc.loc[pc["d_biog"].abs() < 0.30, "delta_fatia"].mean(), 5),
        "corr_d_biog_x_delta_fatia": correl(ext["d_biog"], ext["delta_fatia"]),
    }
    # "leitor que não reconhece": mais da metade dos cadastrados habilitados por ano de nascimento
    res["biografia_maioria"] = {}
    for k in (1, 2):
        s = pc[pc[f"tx_biog_{k}"] >= 0.5]
        res["biografia_maioria"][f"t{k}"] = {
            "n": int(len(s)), "modelo_urna_1": contagem(s["modelo_urna_1"]),
            "por_10mil_secoes_do_modelo": {
                str(m): _r(1e4 * c / n_mod[m], 2)
                for m, c in s["modelo_urna_1"].value_counts().items() if m in n_mod},
            "tipo_urna": contagem(s[f"tipo_urna_{k}"]),
        }
    a1, a2 = pc["tx_biog_1"] >= 0.5, pc["tx_biog_2"] >= 0.5
    res["biografia_maioria"]["nos_dois_turnos"] = int((a1 & a2).sum())
    res["biografia_maioria"]["so_t1_e_urna_trocada"] = int((a1 & ~a2 & ~pc["mesma_urna"]).sum())
    res["biografia_maioria"]["so_t1_mesma_urna"] = int((a1 & ~a2 & pc["mesma_urna"]).sum())
    res["biografia_maioria"]["so_t2_e_urna_trocada"] = int((a2 & ~a1 & ~pc["mesma_urna"]).sum())
    res["biografia_maioria"]["so_t2_mesma_urna"] = int((a2 & ~a1 & pc["mesma_urna"]).sum())
    res["modelo_secoes_pareadas"] = contagem(pc["modelo_urna_1"])
    # |d_biog| >= 10 pontos nos grupos, contra o esperado pelo tamanho da seção
    # (seção pequena tem taxa mais ruidosa; os atípicos são menores que a média)
    q = pc.copy()
    q["cad"] = np.minimum(q["hab_bio_1"] + q["hab_biog_1"], q["hab_bio_2"] + q["hab_biog_2"])
    q["faixa"] = pd.cut(q["cad"], [0, 25, 50, 100, 150, 200, 250, 300, 10_000])
    q["ext10"] = q["d_biog"].abs() >= 0.10
    taxa = q.groupby("faixa", observed=True)["ext10"].mean()
    res["extremos_10pp_por_grupo"] = {"todas": {"n": int(len(q)), "observado": int(q["ext10"].sum())}}
    for m in ("atipico", "tardia", "virada"):
        g = q[q[m]]
        res["extremos_10pp_por_grupo"][m] = {
            "n": int(len(g)), "observado": int(g["ext10"].sum()),
            "esperado_pelo_tamanho": _r(g["faixa"].map(taxa).astype(float).sum(), 1),
            "comparecimento_medio": _r(g["comp_2"].mean(), 1)}
    res["extremos_10pp_por_grupo"]["comparecimento_medio_todas"] = _r(q["comp_2"].mean(), 1)
    res["atipicos_total_na_base"] = int(df["atipico"].sum())
    res["atipicos_pareados_comp20"] = int(pc["atipico"].sum())
    return res, tabs


# ---------------------------------------------------------------------------
# Amostra de logs
# ---------------------------------------------------------------------------

def escolher_amostra(df: pd.DataFrame, n: int = TAMANHO_AMOSTRA) -> pd.DataFrame:
    """Estratos, sem repetição (cada seção entra no primeiro estrato que a pega):
    extremos do BU (até 400), atípicos de viradas (até 300), tardias (até 300)
    e o resto em amostra aleatória proporcional às seções de cada UF."""
    p = df[df["pareada"] & (df["uf"] != "zz") & (df["tipo_arquivo_2"] == "bu")
           & df["hash_1"].notna() & df["hash_2"].notna()
           & (df["comp_1"] >= MIN_COMP) & (df["comp_2"] >= MIN_COMP)].copy()
    p["ordem"] = p["chave"].map(_ordem)
    escolhidos: dict[str, str] = {}

    def pega(chaves, estrato, limite):
        c = 0
        for k in chaves:
            if c >= limite:
                break
            if k not in escolhidos:
                escolhidos[k] = estrato
                c += 1

    ext = pd.concat([
        p.sort_values("d_biog", ascending=False).head(120),
        p.sort_values("d_biog").head(120),
        p.sort_values("d_sem", ascending=False).head(60),
        p.sort_values("d_sem").head(60),
        p[p["sem_bio_2"] == p["comp_2"]].sort_values("ordem").head(40),
    ])
    pega(ext["chave"], "extremo_bu", 400)
    pega(p[p["atipico"]].sort_values("ordem")["chave"], "atipico", 300)
    pega(p[p["tardia"]].sort_values("ordem")["chave"], "tardia", 300)
    resto = n - len(escolhidos)
    livres = p[~p["chave"].isin(escolhidos)]
    cota = (livres.groupby("uf").size() / len(livres) * resto).round().astype(int)
    for uf, g in livres.sort_values("ordem").groupby("uf"):
        pega(g["chave"], "aleatoria", int(cota.get(uf, 0)))
    a = p[p["chave"].isin(escolhidos)].copy()
    a["estrato"] = a["chave"].map(escolhidos)
    return a.drop(columns=["ordem"]).sort_values(["estrato", "chave"]).reset_index(drop=True)


def nome_log(uf: str, mun: str, zona: str, secao: str, turno: int) -> str:
    return f"o{int(PLEITO[turno]):05d}{uf.lower()}{mun}{zona}{secao}-log.jez"


def caminho_bruto(brutos: Path, r: dict, turno: int) -> Path:
    h = r[f"hash_{turno}"]
    return brutos / f"t{turno}" / r["uf"] / f"{r['cd_mun']}-{r['zona']}-{r['secao']}-{h[:16]}.jez"


async def baixar_logs(amostra: pd.DataFrame, brutos: Path, rate: float = 3.0) -> None:
    """Baixa o -log.jez dos dois turnos de cada seção da amostra que ainda não
    está em disco. Um processo, no máximo `rate` req/s, backoff em 429."""
    from dataurnas.downloader import ele2026 as E

    pend = []
    for r in amostra.to_dict("records"):
        for t in (1, 2):
            if not caminho_bruto(brutos, r, t).exists():
                pend.append((r, t))
    log.info("amostra %d seções, %d logs a baixar", len(amostra), len(pend))
    if not pend:
        return
    f = E.HttpFetcher(concurrency=3, retries=8, rate=rate, rate_max=rate, http2=False)
    erros = brutos / "erros.jsonl"
    feitos = 0

    async def uma(r: dict, t: int) -> None:
        nonlocal feitos
        uf, mun, zona, sec, h = r["uf"], r["cd_mun"], r["zona"], r["secao"], r[f"hash_{t}"]
        try:
            raw = await f.get(E.url_arquivo(uf, mun, zona, sec, h, nome_log(uf, mun, zona, sec, t),
                                            pleito=PLEITO[t], ciclo=CICLO))
            if raw is None:  # nome fora do padrão: pergunta ao aux.json
                aux = await f.get_json(E.url_aux(uf, mun, zona, sec, pleito=PLEITO[t], ciclo=CICLO))
                hs = [x for x in (aux or {}).get("hashes") or [] if x.get("hash") == h]
                arq = [a["nm"] for a in (hs[0].get("arq") if hs else []) or []
                       if a.get("tp") in ("log", "logsa")]
                if arq:
                    raw = await f.get(E.url_arquivo(uf, mun, zona, sec, h, arq[0],
                                                    pleito=PLEITO[t], ciclo=CICLO))
            if raw is None:
                raise FileNotFoundError("log_nao_publicado")
            dest = caminho_bruto(brutos, r, t)
            dest.parent.mkdir(parents=True, exist_ok=True)
            tmp = dest.with_suffix(".tmp")
            tmp.write_bytes(raw)
            tmp.rename(dest)
        except Exception as e:  # noqa: BLE001  fica sem arquivo e é refeito na próxima
            with erros.open("a", encoding="utf-8") as fe:
                fe.write(json.dumps({"chave": r["chave"], "turno": t,
                                     "erro": f"{type(e).__name__}: {e}"[:300]}) + "\n")
        feitos += 1
        if feitos % 200 == 0:
            log.info("%d/%d logs (%s) %s", feitos, len(pend), f.rate_info(), f.stats)

    try:
        for i in range(0, len(pend), 30):
            await asyncio.gather(*[uma(r, t) for r, t in pend[i:i + 30]])
    finally:
        await f.close()
    log.info("download concluído: %s", f.stats)


# ---------------------------------------------------------------------------
# Leitura do log
# ---------------------------------------------------------------------------

RE_NUM = re.compile(r"\d+")
RE_TENT = re.compile(r"Tentativa \[(\d+)\] de \[(\d+)\]")
RE_TIPO = re.compile(r"Tipo de habilitação do eleitor \[(.*)\]")
# mensagens da VOTA ligadas à identificação e habilitação do eleitor e do mesário
RE_REL = re.compile(r"digital|biometr|biométr|dedo|habilit|nascimento|dado pessoal|"
                    r"dado digitado|reconhec|batimento|identificador|foto do eleitor|"
                    r"eleitor não encontrado|mesário", re.IGNORECASE)


def normalizar(msg: str) -> str:
    return RE_NUM.sub("N", msg)


def ler_log(caminho: str, turno: int) -> dict:
    """Métricas de habilitação do log de uma seção, só com eventos do dia do turno."""
    from dataurnas.analyzer.rdv_recontagem import texto_log

    try:
        texto = texto_log(Path(caminho).read_bytes())
    except Exception as e:  # noqa: BLE001
        return {"erro": f"ilegivel: {type(e).__name__}"}
    if not texto:
        return {"erro": "ilegivel"}
    dia = DATA[turno]
    vocab: Counter = Counter()
    tipos: Counter = Counter()
    m = Counter()
    tent_bio: Counter = Counter()   # número de solicitações de digital até a habilitação biométrica
    urnas = set()
    ep: Optional[dict] = None

    def fechar(e: Optional[dict], habilitado: bool) -> None:
        if e is None:
            return
        if not habilitado:
            m["ep_nao_habilitado"] += 1
            if e["solicita"]:
                m["ep_nao_hab_com_digital"] += 1
            return
        m["ep_habilitado"] += 1
        if e["tipo"] is not None and "biom" in e["tipo"]:
            m["hab_biometrica"] += 1
            tent_bio[min(e["solicita"], 9)] += 1
        elif e["manual"] or e["mesario"]:
            if e["solicita"]:
                m["hab_manual_apos_digital"] += 1
            else:
                m["hab_manual_sem_digital"] += 1
            if e["solicita"] >= e["max_tent"] > 0 or e["timeout_ultima"]:
                m["hab_manual_esgotou_tentativas"] += 1
        elif e["solicita"] == 0:
            m["hab_sem_digital"] += 1
        else:
            m["hab_outro"] += 1

    for linha in texto.splitlines():
        if not linha.startswith(dia):
            continue
        partes = linha.split("\t")
        if len(partes) < 5:
            continue
        urna, app, msg = partes[2], partes[3], partes[4]
        if app != "VOTA":
            continue
        urnas.add(urna)
        if RE_REL.search(msg):
            vocab[(partes[1], normalizar(msg))] += 1
        if msg.startswith("Identificador do eleitor digitado pelo mesário"):
            fechar(ep, False)
            ep = {"solicita": 0, "max_tent": 0, "tipo": None, "manual": False,
                  "mesario": False, "timeout_ultima": False}
            continue
        if msg == "O voto do eleitor foi computado":
            m["votos_computados"] += 1
            continue
        if ep is None:
            if msg.startswith("Solicita digital. Tentativa"):
                m["digital_fora_de_episodio"] += 1
            continue
        if msg.startswith("Solicita digital. Tentativa"):
            ep["solicita"] += 1
            m["solicita_digital"] += 1
            t = RE_TENT.search(msg)
            if t:
                ep["max_tent"] = int(t.group(2))
            ep["timeout_ultima"] = False
        elif msg.startswith("Capturada a digital"):
            m["digital_capturada"] += 1
        elif msg.startswith("Número de tentativas de reconhecimento do dedo"):
            m["digital_nao_reconhecida"] += 1
        elif msg.startswith("Timeout de reconhecimento do dedo"):
            m["timeout_digital"] += 1
            ep["timeout_ultima"] = True
        elif msg.startswith("Tipo de habilitação do eleitor"):
            t = RE_TIPO.search(msg)
            ep["tipo"] = t.group(1) if t else msg
            tipos[ep["tipo"]] += 1
        elif msg.startswith("Solicitação de dado pessoal do eleitor para habilitação manual"):
            ep["manual"] = True
            m["pedido_habilitacao_manual"] += 1
        elif msg.startswith("Ano de nascimento digitado"):
            m["ano_nascimento_" + ("igual" if "igual" in msg else "outro")] += 1
        elif msg == "Dado digitado confere":
            m["dado_confere"] += 1
        elif re.match(r"Mesário \d+ habilitou o eleitor", msg):
            ep["mesario"] = True
            m["mesario_habilitou"] += 1
        elif msg.startswith("Habilitação cancelada"):
            m["habilitacao_cancelada"] += 1
        elif msg.startswith("Batimento de digitais retornou o score"):
            m["batimento_score"] += 1
        elif msg == "Eleitor foi habilitado":
            m["eleitor_habilitado"] += 1
            fechar(ep, True)
            ep = None
    fechar(ep, False)
    out = dict(m)
    out["n_urnas_vota"] = len(urnas)
    out["tent_bio"] = {str(k): v for k, v in sorted(tent_bio.items())}
    out["tipos_habilitacao"] = dict(tipos)
    out["vocab"] = {f"{lv}\t{msg}": c for (lv, msg), c in vocab.items()}
    return out


def _ler_um(args):
    chave, turno, caminho = args
    r = ler_log(caminho, turno)
    r["chave"], r["turno"] = chave, turno
    return r


def ler_logs(amostra: pd.DataFrame, brutos: Path) -> list[dict]:
    tarefas = []
    for r in amostra.to_dict("records"):
        for t in (1, 2):
            c = caminho_bruto(brutos, r, t)
            if c.exists():
                tarefas.append((r["chave"], t, str(c)))
    with ProcessPoolExecutor(max_workers=32) as ex:
        return list(ex.map(_ler_um, tarefas, chunksize=20))


METRICAS = ["eleitor_habilitado", "votos_computados", "hab_biometrica",
            "hab_manual_apos_digital", "hab_manual_sem_digital", "hab_manual_esgotou_tentativas",
            "hab_sem_digital", "hab_outro", "ep_nao_habilitado", "ep_nao_hab_com_digital",
            "solicita_digital", "digital_capturada", "digital_nao_reconhecida",
            "timeout_digital", "pedido_habilitacao_manual", "ano_nascimento_igual",
            "ano_nascimento_outro", "dado_confere", "mesario_habilitou",
            "habilitacao_cancelada", "batimento_score", "digital_fora_de_episodio",
            "n_urnas_vota"]


def analisar_logs(amostra: pd.DataFrame, lidos: list[dict]) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    linhas, vocab = [], Counter()
    sec_vocab: Counter = Counter()
    for r in lidos:
        if "erro" in r:
            linhas.append({"chave": r["chave"], "turno": r["turno"], "erro": r["erro"]})
            continue
        d = {"chave": r["chave"], "turno": r["turno"]}
        for k in METRICAS:
            d[k] = int(r.get(k, 0))
        for k in range(1, 10):
            d[f"bio_tent_{k}"] = int(r["tent_bio"].get(str(k), 0))
        d["tipos_habilitacao"] = json.dumps(r["tipos_habilitacao"], ensure_ascii=False)
        linhas.append(d)
        for k, c in r["vocab"].items():
            vocab[(r["turno"], k)] += c
            sec_vocab[(r["turno"], k)] += 1
    L = pd.DataFrame(linhas)
    if "erro" not in L.columns:
        L["erro"] = None
    v = sorted({k for _, k in vocab})
    V = pd.DataFrame([{
        "nivel": k.split("\t")[0], "mensagem": k.split("\t")[1],
        "ocorrencias_t1": vocab.get((1, k), 0), "secoes_t1": sec_vocab.get((1, k), 0),
        "ocorrencias_t2": vocab.get((2, k), 0), "secoes_t2": sec_vocab.get((2, k), 0),
    } for k in v]).sort_values("ocorrencias_t1", ascending=False)

    A = amostra.set_index("chave")
    ok = L[L["erro"].isna()].copy()
    for c in ["estrato", "uf", "regiao", "comp_1", "comp_2", "sem_bio_1", "sem_bio_2",
              "hab_bio_1", "hab_bio_2", "hab_biog_1", "hab_biog_2", "delta_fatia",
              "atipico", "tardia", "modelo_urna_1", "mesma_urna"]:
        ok[c] = ok["chave"].map(A[c])
    for k in (1, 2):
        s = ok["turno"] == k
        ok.loc[s, "bu_comp"] = ok.loc[s, f"comp_{k}"]
        ok.loc[s, "bu_sem"] = ok.loc[s, f"sem_bio_{k}"]
        ok.loc[s, "bu_hb"] = ok.loc[s, f"hab_bio_{k}"]
        ok.loc[s, "bu_hg"] = ok.loc[s, f"hab_biog_{k}"]

    res: dict = {"logs_lidos": int(len(ok)), "logs_com_erro": int(L["erro"].notna().sum()),
                 "secoes_amostra": int(len(amostra)),
                 "secoes_com_dois_logs": int((ok.groupby("chave").size() == 2).sum()),
                 "estratos": {str(k): int(v) for k, v in amostra["estrato"].value_counts().items()}}

    # conferência log x BU
    conf = {}
    for k in (1, 2):
        s = ok[ok["turno"] == k]
        conf[f"t{k}"] = {
            "n": int(len(s)),
            "votos_computados_igual_comparecimento": int((s["votos_computados"] == s["bu_comp"]).sum()),
            "hab_biometrica_igual_bu": int((s["hab_biometrica"] == s["bu_hb"]).sum()),
            "manual_apos_digital_igual_biografia": int(
                (s["hab_manual_apos_digital"] == s["bu_hg"]).sum()),
            "sem_digital_mais_manual_sem_digital_igual_sem_biometria": int(
                ((s["hab_sem_digital"] + s["hab_manual_sem_digital"]) == s["bu_sem"]).sum()),
            "soma_log": {c: int(s[c].sum()) for c in ("votos_computados", "hab_biometrica",
                                                      "hab_manual_apos_digital",
                                                      "hab_manual_sem_digital",
                                                      "hab_sem_digital", "hab_outro")},
            "soma_bu": {"comparecimento": int(s["bu_comp"].sum()), "hab_biometria": int(s["bu_hb"].sum()),
                        "hab_biografia": int(s["bu_hg"].sum()), "sem_biometria": int(s["bu_sem"].sum())},
            "tipos_habilitacao": dict(sum((Counter(json.loads(x)) for x in s["tipos_habilitacao"]),
                                          Counter())),
        }
    res["conferencia_log_bu"] = conf

    def indicadores(s: pd.DataFrame) -> dict:
        hab = s["eleitor_habilitado"].sum()
        hb = s["hab_biometrica"].sum()
        cad = hb + s["hab_manual_apos_digital"].sum()
        tent_hb = sum(k * s[f"bio_tent_{k}"].sum() for k in range(1, 10))
        return {
            "secoes": int(s["chave"].nunique()), "habilitados": int(hab),
            "solicitacoes_digital_por_habilitado": _r(s["solicita_digital"].sum() / hab if hab else None),
            "nao_reconhecida_por_habilitado": _r(s["digital_nao_reconhecida"].sum() / hab if hab else None),
            "timeouts_por_mil_habilitados": _r(1000 * s["timeout_digital"].sum() / hab if hab else None, 2),
            "pct_biometrica": _r(100 * hb / hab if hab else None, 3),
            "pct_manual_apos_digital_entre_cadastrados": _r(
                100 * s["hab_manual_apos_digital"].sum() / cad if cad else None, 3),
            "pct_sem_digital": _r(100 * s["hab_sem_digital"].sum() / hab if hab else None, 3),
            "pct_bio_na_1a_tentativa": _r(100 * s["bio_tent_1"].sum() / hb if hb else None, 3),
            "tentativas_por_habilitado_biometrico": _r(tent_hb / hb if hb else None),
            "cancelamentos_por_mil": _r(1000 * s["habilitacao_cancelada"].sum() / hab if hab else None, 2),
            "nao_habilitados_por_mil": _r(1000 * s["ep_nao_habilitado"].sum() / hab if hab else None, 2),
        }

    res["indicadores"] = {}
    for estrato in ["aleatoria", "atipico", "tardia", "extremo_bu", "todas"]:
        base = ok if estrato == "todas" else ok[ok["estrato"] == estrato]
        res["indicadores"][estrato] = {f"t{k}": indicadores(base[base["turno"] == k]) for k in (1, 2)}
    al = ok[ok["estrato"] == "aleatoria"]
    res["indicadores_regiao_aleatoria"] = {
        reg: {f"t{k}": indicadores(g[g["turno"] == k]) for k in (1, 2)}
        for reg, g in al.groupby("regiao")}
    res["indicadores_modelo_aleatoria"] = {
        str(mod): {f"t{k}": indicadores(g[g["turno"] == k]) for k in (1, 2)}
        for mod, g in al[al["mesma_urna"]].groupby("modelo_urna_1")}

    # pareado por seção: tentativas falhas por habilitado, 1º x 2º
    w = ok.pivot_table(index="chave", columns="turno",
                       values=["digital_nao_reconhecida", "eleitor_habilitado",
                               "hab_manual_apos_digital", "solicita_digital"], aggfunc="sum")
    w = w.dropna()
    w.columns = [f"{a}_{b}" for a, b in w.columns]
    w = w[(w["eleitor_habilitado_1"] > 0) & (w["eleitor_habilitado_2"] > 0)]
    w["falhas_por_hab_1"] = w["digital_nao_reconhecida_1"] / w["eleitor_habilitado_1"]
    w["falhas_por_hab_2"] = w["digital_nao_reconhecida_2"] / w["eleitor_habilitado_2"]
    w["d_falhas_por_hab"] = w["falhas_por_hab_2"] - w["falhas_por_hab_1"]
    w = w.join(A[["estrato", "delta_fatia", "atipico", "tardia", "uf", "d_biog"]])
    res["pareado_log"] = {
        "n": int(len(w)),
        "d_falhas_por_hab_media": _r(w["d_falhas_por_hab"].mean()),
        "d_falhas_por_hab_quantis": {str(q): _r(w["d_falhas_por_hab"].quantile(q))
                                     for q in (0.01, 0.05, 0.5, 0.95, 0.99)},
        "d_falhas_x_d_biog_bu": correl(w["d_falhas_por_hab"], w["d_biog"]),
        "d_falhas_x_delta_fatia": correl(w["d_falhas_por_hab"], w["delta_fatia"]),
        "d_falhas_x_delta_fatia_dentro_uf": correl_dentro(w.reset_index(), "d_falhas_por_hab",
                                                          "delta_fatia", "uf"),
        "por_estrato": {str(e): {"n": int(len(g)), "media": _r(g["d_falhas_por_hab"].mean()),
                                 "mediana": _r(g["d_falhas_por_hab"].median())}
                        for e, g in w.groupby("estrato")},
    }
    return res, L, V


# ---------------------------------------------------------------------------
# Relatório
# ---------------------------------------------------------------------------

def md_tabela(df: pd.DataFrame) -> str:
    cols = list(df.columns)
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for r in df.itertuples(index=False):
        cel = []
        for x in r:
            if isinstance(x, (float, np.floating)):
                cel.append("" if math.isnan(x) else f"{x:.3f}")
            else:
                cel.append(str(x))
        out.append("| " + " | ".join(cel) + " |")
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--bu", type=Path, required=True,
                    help="Parquet de biometria_t1_t2_ch.sql")
    ap.add_argument("--viradas", type=Path, required=True,
                    help="data/parquet/2026/t2/viradas/secoes_2026.parquet")
    ap.add_argument("--saida", type=Path, default=SAIDA_PADRAO)
    ap.add_argument("--brutos", type=Path, default=None,
                    help="pasta dos -log.jez da amostra (sem ela, só o BU)")
    ap.add_argument("--baixar-logs", action="store_true")
    ap.add_argument("--taxa", type=float, default=3.0)
    ap.add_argument("--amostra", type=int, default=TAMANHO_AMOSTRA)
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    args.saida.mkdir(parents=True, exist_ok=True)

    df = carregar(args.bu, args.viradas)
    res, tabs = analisar_bu(df)
    df.drop(columns=["hash_1", "hash_2"]).to_parquet(args.saida / "secoes_biometria.parquet",
                                                     index=False)
    ex = extremos(df)
    pd.concat([v.assign(lista=k) for k, v in ex.items()]).to_csv(
        args.saida / "extremos.csv", index=False)
    for k, t in tabs.items():
        t.to_parquet(args.saida / f"tab_{k}.parquet", index=False)

    amostra_p = args.saida / "amostra.parquet"
    if amostra_p.exists():
        amostra = pd.read_parquet(amostra_p)
    else:
        amostra = escolher_amostra(df, args.amostra)
        amostra.to_parquet(amostra_p, index=False)
    res["amostra_estratos"] = {str(k): int(v) for k, v in amostra["estrato"].value_counts().items()}

    if args.brutos is not None:
        args.brutos.mkdir(parents=True, exist_ok=True)
        if args.baixar_logs:
            asyncio.run(baixar_logs(amostra, args.brutos, args.taxa))
        lidos = ler_logs(amostra, args.brutos)
        if lidos:
            rl, L, V = analisar_logs(amostra, lidos)
            res["logs"] = rl
            L.to_parquet(args.saida / "logs_secoes.parquet", index=False)
            V.to_csv(args.saida / "logs_vocabulario.csv", index=False)

    (args.saida / "resumo.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    partes = [f"## {k}\n\n{md_tabela(t)}\n" for k, t in tabs.items()]
    partes += [f"## extremos: {k}\n\n{md_tabela(v.head(25))}\n" for k, v in ex.items()]
    (args.saida / "tabelas.md").write_text("\n".join(partes), encoding="utf-8")
    log.info("pronto: %s", args.saida)


if __name__ == "__main__":
    main()
