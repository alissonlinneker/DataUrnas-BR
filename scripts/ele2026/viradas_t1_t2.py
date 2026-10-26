#!/usr/bin/env python3
"""Viradas de liderança entre o 1º e o 2º turno por seção (2026 e linha de base 2022).

Pergunta: em quantas seções o candidato que liderou no 1º turno (13 ou 22)
perdeu a liderança no 2º turno, e isso foge do que se observa normalmente entre
turnos? A referência é a eleição de 2022 (13 x 22, 02/10 e 30/10/2022), medida
com exatamente as mesmas regras.

Definições (por seção, só 13 e 22; "outros" = demais votos nominais do 1º turno):
  lider               13, 22 ou empate, pelos votos nominais de cada turno.
  virada              líder do 1º turno diferente do líder do 2º turno, sem empate
                      em nenhum dos dois (sentidos 22->13 e 13->22).
  margem_t1           |v13 - v22| no 1º turno (votos).
  fatia_13            v13 / (v13 + v22); delta_fatia = fatia_13 no 2º - no 1º.
  troca_min_X         mínimo de eleitores do adversário que precisariam ter passado
                      para X, se os votos de X só pudessem vir de: outros do 1º
                      turno, queda de brancos e nulos (se houve) e aumento de
                      comparecimento (se houve). Fórmula:
                        max(0, ganho de X - (outros_1 + max(0, BN_1 - BN_2)
                                             + max(0, comp_2 - comp_1)))
  troca_estrita_X     o mesmo, mas aceitando qualquer rotatividade: todos os
                      brancos e nulos do 1º turno e todos os ausentes do 1º turno
                      (até o comparecimento do 2º) podem ter votado em X. É o
                      mínimo logicamente obrigatório de trocas diretas.
  troca_minima        troca_min do vencedor do 2º turno, só nas seções que viraram.

Esperado: regressão logística ajustada em 2022 (seções com líder no 1º turno),
com a margem do 1º turno, o movimento do município entre turnos (calculado sem a
própria seção), o volume de outros + brancos + nulos e o tamanho da seção. O
modelo é aplicado a 2026 com o movimento observado em 2026, e as viradas
observadas são comparadas com a soma das probabilidades por UF. Também há uma
tabela por faixas de margem e de reserva (taxa de 2022 aplicada a 2026).

Atípicos (mesma régua em 2022 e 2026, simétrica entre 13 e 22):
  troca       troca_max = max(troca_min_13, troca_min_22) >= LIMIAR_TROCA_VOTOS
              e >= LIMIAR_TROCA_FRACAO do comparecimento do 2º turno; o
              esperado vem da taxa de 2022 por faixa do movimento do município
              e faixa de reserva (outros + brancos + nulos do 1º turno);
  estrita     max(troca_estrita_13, troca_estrita_22) > 0 (mudança direta
              obrigatória mesmo com rotatividade total de brancos, nulos e
              ausentes);
  desvio      |z| > 4, com z = (delta_fatia - mediana do município) /
              (1,4826 x MAD do município); município com menos de
              MIN_SECOES_MUN seções usa a UF. Só seções com pelo menos
              MIN_VOTOS_FATIA votos em 13 + 22 nos dois turnos.

Entradas (só leitura):
  2026  data/parquet/2026/t2/encerramento/secoes_encerramento.parquet (2º turno)
        data/parquet/2026/secoes_2026.parquet, votos_presidente_2026.parquet (1º)
        data/parquet/2026/t2/software/secoes_software.parquet (urna e carga do 2º)
        data/versoes/2026/t2*/bus/parts (BU dos atípicos sem linha de software)
  2022  data/parquet/secoes.parquet, votos_t1_a/b.parquet, votos_t2.parquet

Saída em data/parquet/2026/t2/viradas/ (ignorada pelo git):
  secoes_2026.parquet, secoes_2022.parquet   seções pareadas com as métricas
  atipicos_2026.parquet/.csv, atipicos_2022.parquet/.csv
  resumo_uf.parquet       métricas por ano e UF/região/Brasil
  faixas.parquet          taxa de virada por faixa de margem e reserva
  grupos.parquet          somas do 1º e do 2º turno por grupo de virada (Brasil,
                          região e UF): seções, aptos, comparecimento, abstenção,
                          13, 22, outros, brancos e nulos
  resumo.json             tudo acima resumido, coeficientes e calibração

Uso:
  nice -n 20 python3 scripts/ele2026/viradas_t1_t2.py
  python3 scripts/ele2026/viradas_t1_t2.py --sem-bu   # não lê BU dos atípicos
  # país inteiro, com o 2º turno exportado do ClickHouse (viradas_t2_ch.sql):
  python3 scripts/ele2026/viradas_t1_t2.py --t2 t2.parquet --software t2.parquet --sem-bu
"""

from __future__ import annotations

import argparse
import json
import logging
import math
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[2]
SRC = str(ROOT / "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

log = logging.getLogger("viradas_t1_t2")

P = ROOT / "data" / "parquet"
ENC_T2 = P / "2026" / "t2" / "encerramento" / "secoes_encerramento.parquet"
SECOES_T1 = P / "2026" / "secoes_2026.parquet"
VOTOS_T1 = P / "2026" / "votos_presidente_2026.parquet"
SOFTWARE_T2 = P / "2026" / "t2" / "software" / "secoes_software.parquet"
PARTS_T2 = [ROOT / "data" / "versoes" / "2026" / "t2" / "bus" / "parts",
            ROOT / "data" / "versoes" / "2026" / "t2-sseco" / "bus" / "parts"]
SECOES_2022 = P / "secoes.parquet"
VOTOS_2022_T1 = [P / "votos_t1_a.parquet", P / "votos_t1_b.parquet"]
VOTOS_2022_T2 = P / "votos_t2.parquet"
SAIDA = P / "2026" / "t2" / "viradas"

ELEICAO_2022_T1 = 544
ELEICAO_2022_T2 = 545
ELEICAO_2026_T2 = 6258

CHAVE = ["uf", "cd_mun", "zona", "secao"]

LIMIAR_TROCA_VOTOS = 10
LIMIAR_TROCA_FRACAO = 0.05
LIMIAR_Z = 4.0
MIN_SECOES_MUN = 30
MIN_VOTOS_FATIA = 20
MIN_VOTOS_SWING = 100
COBERTURA_MIN_UF = 0.9

REGIAO = {
    **dict.fromkeys(("ac", "am", "ap", "pa", "ro", "rr", "to"), "Norte"),
    **dict.fromkeys(("al", "ba", "ce", "ma", "pb", "pe", "pi", "rn", "se"), "Nordeste"),
    **dict.fromkeys(("df", "go", "ms", "mt"), "Centro-Oeste"),
    **dict.fromkeys(("es", "mg", "rj", "sp"), "Sudeste"),
    **dict.fromkeys(("pr", "rs", "sc"), "Sul"),
}

FAIXAS_MARGEM = [-1, 0, 2, 5, 10, 20, 40, 80, 10**9]
ROTULOS_MARGEM = ["0", "1-2", "3-5", "6-10", "11-20", "21-40", "41-80", ">80"]
FAIXAS_RESERVA = [-0.01, 0.05, 0.10, 0.15, 0.20, 10.0]
ROTULOS_RESERVA = ["<=5%", "5-10%", "10-15%", "15-20%", ">20%"]
FAIXAS_SWING = [-0.01, 0.5, 1, 2, 3, 4, 6, 100]
ROTULOS_SWING = ["0-0,5", "0,5-1", "1-2", "2-3", "3-4", "4-6", ">6"]


# ---------------------------------------------------------------------------
# Carga
# ---------------------------------------------------------------------------

def _q(sql: str, params: Optional[list] = None) -> pd.DataFrame:
    import duckdb
    con = duckdb.connect()
    try:
        con.execute("SET threads TO 3")
        return con.execute(sql, params or []).df()
    finally:
        con.close()


def carregar_2026_t1(secoes: Path = SECOES_T1, votos: Path = VOTOS_T1) -> pd.DataFrame:
    """1º turno de 2026: uma linha por seção com BU (status ok) e votos para presidente."""
    df = _q(f"""
        WITH v AS (
          SELECT uf, cd_mun, zona, secao,
                 SUM(CASE WHEN tipo_voto='nominal' AND numero=13 THEN votos ELSE 0 END) AS v13,
                 SUM(CASE WHEN tipo_voto='nominal' AND numero=22 THEN votos ELSE 0 END) AS v22,
                 SUM(CASE WHEN tipo_voto='nominal' AND numero NOT IN (13,22)
                          THEN votos ELSE 0 END) AS outros,
                 SUM(CASE WHEN tipo_voto='branco' THEN votos ELSE 0 END) AS brancos,
                 SUM(CASE WHEN tipo_voto='nulo' THEN votos ELSE 0 END) AS nulos
          FROM read_parquet('{votos}') GROUP BY ALL)
        SELECT s.uf, s.cd_mun, s.nm_mun AS municipio, s.zona, s.secao,
               s.aptos, s.comparecimento, s.tipo_urna, s.modelo_urna,
               CAST(s.numero_interno_urna AS BIGINT) AS numero_interno_urna,
               CAST(s.codigo_carga AS VARCHAR) AS codigo_carga,
               s.hora_encerramento AS encerramento_local,
               v.v13, v.v22, v.outros, v.brancos, v.nulos
        FROM read_parquet('{secoes}') s
        JOIN v USING (uf, cd_mun, zona, secao)
        WHERE s.status = 'ok' AND s.tem_presidente""")
    df["encerramento_local"] = df["encerramento_local"].map(_hora_compacta)
    return df


def _hora_compacta(v) -> Optional[str]:
    """20261004T150706 -> 2026-10-04 15:07:06 (horário local da urna)."""
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    s = str(v)
    if len(s) == 15 and s[8] == "T":
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]} {s[9:11]}:{s[11:13]}:{s[13:15]}"
    return s


def carregar_2026_t2(enc: Path = ENC_T2) -> pd.DataFrame:
    """2º turno de 2026: seções do Brasil com BU decodificado e cargo presidente."""
    cols = ["uf", "cd_mun", "municipio", "zona", "secao", "tipo_urna", "aptos",
            "comparecimento", "votos_13", "votos_22", "votos_outros_nominais",
            "votos_brancos", "votos_nulos", "encerramento_local", "encerramento_bsb",
            "minutos_apos_17h_bsb", "erro_decodificacao", "tem_presidente",
            "hash", "sha512", "nome_arquivo", "n_versoes_bu"]
    df = pd.read_parquet(enc, columns=cols)
    df = df[df["erro_decodificacao"].isna() & df["tem_presidente"].fillna(False)]
    df = df.rename(columns={"votos_13": "v13", "votos_22": "v22",
                            "votos_outros_nominais": "outros",
                            "votos_brancos": "brancos", "votos_nulos": "nulos"})
    return df.drop(columns=["erro_decodificacao", "tem_presidente"]).reset_index(drop=True)


def carregar_2022() -> tuple[pd.DataFrame, pd.DataFrame]:
    """1º e 2º turnos de 2022 (secoes.parquet e votos_*.parquet), presidente."""
    def votos(arqs: list[Path], eleicao: int) -> str:
        lista = ", ".join(f"'{a}'" for a in arqs)
        return f"""
          SELECT secao_id,
                 SUM(CASE WHEN tipo_voto='nominal' AND codigo_candidato=13 THEN quantidade ELSE 0 END) AS v13,
                 SUM(CASE WHEN tipo_voto='nominal' AND codigo_candidato=22 THEN quantidade ELSE 0 END) AS v22,
                 SUM(CASE WHEN tipo_voto='nominal' AND codigo_candidato NOT IN (13,22)
                          THEN quantidade ELSE 0 END) AS outros,
                 SUM(CASE WHEN tipo_voto='branco' THEN quantidade ELSE 0 END) AS brancos,
                 SUM(CASE WHEN tipo_voto='nulo' THEN quantidade ELSE 0 END) AS nulos
          FROM read_parquet([{lista}])
          WHERE codigo_cargo = 1 AND eleicao_id = {eleicao}
          GROUP BY secao_id"""

    out = []
    for turno, arqs, el in ((1, VOTOS_2022_T1, ELEICAO_2022_T1),
                            (2, [VOTOS_2022_T2], ELEICAO_2022_T2)):
        df = _q(f"""
            WITH v AS ({votos(arqs, el)})
            SELECT s.uf, s.municipio AS cd_mun, s.zona, s.secao,
                   s.eleitores_aptos AS aptos, s.comparecimento, s.tipo_urna,
                   s.modelo_urna, s.hora_encerramento AS encerramento_local,
                   v.v13, v.v22, v.outros, v.brancos, v.nulos
            FROM read_parquet('{SECOES_2022}') s JOIN v ON v.secao_id = s.id
            WHERE s.turno = {turno}""")
        df["encerramento_local"] = df["encerramento_local"].map(_hora_2022)
        out.append(df)
    return out[0], out[1]


def _hora_2022(v) -> Optional[str]:
    """02/10/2022 15:05:33 -> 2022-10-02 15:05:33 (horário local da urna)."""
    if not isinstance(v, str) or len(v) < 19 or v[2] != "/":
        return v if isinstance(v, str) else None
    return f"{v[6:10]}-{v[3:5]}-{v[0:2]} {v[11:19]}"


# ---------------------------------------------------------------------------
# Métricas por seção
# ---------------------------------------------------------------------------

INTEIROS = ["aptos", "comparecimento", "v13", "v22", "outros", "brancos", "nulos"]


def parear(t1: pd.DataFrame, t2: pd.DataFrame) -> pd.DataFrame:
    """Junta os turnos pela seção; colunas com sufixo _1 e _2."""
    a = t1.copy()
    b = t2.copy()
    for d in (a, b):
        for c in INTEIROS:
            d[c] = pd.to_numeric(d[c], errors="coerce").fillna(0).astype("int64")
    a = a.rename(columns={c: f"{c}_1" for c in a.columns if c not in CHAVE and c != "municipio"})
    b = b.rename(columns={c: f"{c}_2" for c in b.columns if c not in CHAVE and c != "municipio"})
    if "municipio" in a.columns and "municipio" in b.columns:
        b = b.rename(columns={"municipio": "municipio_t2"})
    df = a.merge(b, on=CHAVE, how="inner")
    if "municipio_t2" in df.columns:
        df["municipio"] = df["municipio"].fillna(df["municipio_t2"])
        df = df.drop(columns=["municipio_t2"])
    df["regiao"] = df["uf"].map(REGIAO)
    return df


def lider(v13, v22) -> np.ndarray:
    v13 = np.asarray(v13)
    v22 = np.asarray(v22)
    return np.where(v13 > v22, "13", np.where(v22 > v13, "22", "empate"))


def troca_minima(ganho, outros_1, bn_1, bn_2, comp_1, comp_2) -> np.ndarray:
    """Mínimo de eleitores do adversário que passaram para o candidato que ganhou
    `ganho` votos, contando como fonte só outros, queda de BN e aumento de comparecimento."""
    reserva = (np.asarray(outros_1) + np.maximum(0, np.asarray(bn_1) - np.asarray(bn_2))
               + np.maximum(0, np.asarray(comp_2) - np.asarray(comp_1)))
    return np.maximum(0, np.asarray(ganho) - reserva)


def troca_estrita(ganho, outros_1, bn_1, comp_1, comp_2, aptos_1, aptos_2) -> np.ndarray:
    """Mínimo logicamente obrigatório: todos os outros, todos os BN do 1º turno e
    todos os ausentes do 1º turno (limitados ao comparecimento do 2º) podem ter
    ido para o candidato."""
    ausentes = np.maximum(0, np.maximum(np.asarray(aptos_1), np.asarray(aptos_2))
                          - np.asarray(comp_1))
    novos = np.minimum(np.asarray(comp_2), ausentes)
    return np.maximum(0, np.asarray(ganho) - np.asarray(outros_1) - np.asarray(bn_1) - novos)


def metricas(df: pd.DataFrame) -> pd.DataFrame:
    """Líderes, virada, margem, fatia do 13 e trocas mínimas."""
    d = df.copy()
    d["lider_1"] = lider(d["v13_1"], d["v22_1"])
    d["lider_2"] = lider(d["v13_2"], d["v22_2"])
    vir = (d["lider_1"] != "empate") & (d["lider_2"] != "empate") & (d["lider_1"] != d["lider_2"])
    d["virada"] = np.where(vir, d["lider_1"] + "->" + d["lider_2"], "")
    d["margem_t1"] = (d["v13_1"] - d["v22_1"]).abs()
    d["margem_t2"] = (d["v13_2"] - d["v22_2"]).abs()
    dois1 = d["v13_1"] + d["v22_1"]
    dois2 = d["v13_2"] + d["v22_2"]
    d["fatia13_1"] = np.where(dois1 > 0, d["v13_1"] / dois1.where(dois1 > 0, 1), np.nan)
    d["fatia13_2"] = np.where(dois2 > 0, d["v13_2"] / dois2.where(dois2 > 0, 1), np.nan)
    d["delta_fatia"] = d["fatia13_2"] - d["fatia13_1"]
    bn1 = d["brancos_1"] + d["nulos_1"]
    bn2 = d["brancos_2"] + d["nulos_2"]
    d["reserva_t1"] = d["outros_1"] + bn1
    d["reserva_frac"] = np.where(d["comparecimento_1"] > 0,
                                 d["reserva_t1"] / d["comparecimento_1"].clip(lower=1), np.nan)
    for x in ("13", "22"):
        ganho = d[f"v{x}_2"] - d[f"v{x}_1"]
        d[f"troca_min_{x}"] = troca_minima(ganho, d["outros_1"], bn1, bn2,
                                           d["comparecimento_1"], d["comparecimento_2"])
        d[f"troca_estrita_{x}"] = troca_estrita(ganho, d["outros_1"], bn1, d["comparecimento_1"],
                                                d["comparecimento_2"], d["aptos_1"], d["aptos_2"])
    venc13 = d["lider_2"] == "13"
    d["troca_minima"] = np.where(vir, np.where(venc13, d["troca_min_13"], d["troca_min_22"]), 0)
    d["troca_estrita"] = np.where(vir, np.where(venc13, d["troca_estrita_13"],
                                                d["troca_estrita_22"]), 0)
    # troca do vencedor do 2º turno em qualquer seção (não só viradas)
    d["troca_vencedor"] = np.where(venc13, d["troca_min_13"],
                                   np.where(d["lider_2"] == "22", d["troca_min_22"], 0))
    d["troca_estrita_vencedor"] = np.where(venc13, d["troca_estrita_13"],
                                           np.where(d["lider_2"] == "22",
                                                    d["troca_estrita_22"], 0))
    # régua simétrica: a maior troca exigida por qualquer dos dois candidatos
    d["troca_max"] = np.maximum(d["troca_min_13"], d["troca_min_22"])
    d["troca_max_cand"] = np.where(d["troca_min_13"] >= d["troca_min_22"], "13", "22")
    d["troca_estrita_max"] = np.maximum(d["troca_estrita_13"], d["troca_estrita_22"])
    d["aptos_mudou"] = d["aptos_1"] != d["aptos_2"]
    return d


def swing_municipal(d: pd.DataFrame) -> np.ndarray:
    """Movimento da fatia do 13 entre turnos no município, sem a própria seção.
    Município com menos de MIN_VOTOS_SWING votos (13+22) nas outras seções usa a UF."""
    cols = ["v13_1", "v22_1", "v13_2", "v22_2"]
    out = np.full(len(d), np.nan)
    resto = np.ones(len(d), dtype=bool)
    for nivel in (["uf", "cd_mun"], ["uf"]):
        soma = d.groupby(nivel)[cols].transform("sum")
        loo = soma - d[cols]
        den1 = loo["v13_1"] + loo["v22_1"]
        den2 = loo["v13_2"] + loo["v22_2"]
        ok = (den1 >= MIN_VOTOS_SWING) & (den2 >= MIN_VOTOS_SWING)
        s = loo["v13_2"] / den2.where(den2 > 0) - loo["v13_1"] / den1.where(den1 > 0)
        usar = resto & ok.to_numpy()
        out[usar] = s.to_numpy()[usar]
        resto &= ~usar
    return out


def z_robusto(d: pd.DataFrame) -> pd.DataFrame:
    """z da variação de fatia do 13 em relação ao município (ou UF)."""
    ok = ((d["v13_1"] + d["v22_1"]) >= MIN_VOTOS_FATIA) & \
         ((d["v13_2"] + d["v22_2"]) >= MIN_VOTOS_FATIA)
    base = d.loc[ok, ["uf", "cd_mun", "delta_fatia"]]
    med = np.full(len(d), np.nan)
    esc = np.full(len(d), np.nan)
    ref = np.array([""] * len(d), dtype=object)

    def estat(g):
        m = g.median()
        return pd.Series({"med": m, "mad": 1.4826 * (g - m).abs().median(), "n": len(g)})

    mun = base.groupby(["uf", "cd_mun"])["delta_fatia"].apply(estat).unstack()
    uf = base.groupby("uf")["delta_fatia"].apply(estat).unstack()
    k_mun = pd.MultiIndex.from_frame(d[["uf", "cd_mun"]])
    em = mun.reindex(k_mun)
    eu = uf.reindex(d["uf"])
    usar_mun = (em["n"].to_numpy() >= MIN_SECOES_MUN) & (em["mad"].to_numpy() > 0)
    med = np.where(usar_mun, em["med"].to_numpy(), eu["med"].to_numpy())
    esc = np.where(usar_mun, em["mad"].to_numpy(), eu["mad"].to_numpy())
    ref = np.where(usar_mun, "municipio", "uf")
    esc = np.where(esc > 0, esc, np.nan)
    z = (d["delta_fatia"].to_numpy() - med) / esc
    return pd.DataFrame({"delta_esperado": med, "delta_escala": esc,
                         "z_delta": np.where(ok, z, np.nan), "z_ref": np.where(ok, ref, "")},
                        index=d.index)


# ---------------------------------------------------------------------------
# Modelo de esperado
# ---------------------------------------------------------------------------

def features(d: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Matriz X, alvo y (virou) e máscara das seções com líder no 1º turno."""
    dois1 = (d["v13_1"] + d["v22_1"]).to_numpy(dtype=float)
    mask = (d["lider_1"] != "empate").to_numpy() & (dois1 > 0) & \
        np.isfinite(d["swing"].to_numpy(dtype=float))
    lead = d["margem_t1"].to_numpy(dtype=float) / np.where(dois1 > 0, dois1, 1)
    sinal = np.where(d["lider_1"].to_numpy() == "22", 1.0, -1.0)  # movimento a favor do 2º colocado
    sw = sinal * d["swing"].to_numpy(dtype=float)
    gap = sw - lead / 2.0  # quanto o movimento do município excede a meia margem
    raiz = np.sqrt(np.maximum(dois1, 1.0))
    res = d["reserva_frac"].to_numpy(dtype=float)
    res = np.where(np.isfinite(res), res, 0.0)
    X = np.column_stack([np.ones(len(d)), gap * raiz, gap, lead * raiz, res,
                         np.log(np.maximum(dois1, 1.0))])
    y = (d["virada"].to_numpy() != "").astype(float)
    return X, y, mask


def ajustar_logistica(X: np.ndarray, y: np.ndarray, iters: int = 50,
                      ridge: float = 1e-6) -> np.ndarray:
    """Regressão logística por IRLS (Newton), com pequena regularização."""
    beta = np.zeros(X.shape[1])
    for _ in range(iters):
        eta = np.clip(X @ beta, -30, 30)
        p = 1.0 / (1.0 + np.exp(-eta))
        w = p * (1 - p)
        H = X.T @ (X * w[:, None]) + ridge * np.eye(X.shape[1])
        g = X.T @ (y - p) - ridge * beta
        passo = np.linalg.solve(H, g)
        beta = beta + passo
        if np.max(np.abs(passo)) < 1e-8:
            break
    return beta


def prever(X: np.ndarray, beta: np.ndarray) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(X @ beta, -30, 30)))


def aplicar_modelo(d: pd.DataFrame, beta: np.ndarray) -> np.ndarray:
    X, _, mask = features(d)
    p = np.full(len(d), np.nan)
    p[mask] = prever(X[mask], beta)
    return p


def faixas(d: pd.DataFrame) -> pd.Series:
    fm = pd.cut(d["margem_t1"], FAIXAS_MARGEM, labels=ROTULOS_MARGEM)
    fr = pd.cut(d["reserva_frac"].fillna(0), FAIXAS_RESERVA, labels=ROTULOS_RESERVA)
    return fm.astype(str) + " | " + fr.astype(str)


# ---------------------------------------------------------------------------
# Atípicos e resumos
# ---------------------------------------------------------------------------

def troca_alta(troca, comparecimento_2) -> np.ndarray:
    t = np.asarray(troca)
    return (t >= LIMIAR_TROCA_VOTOS) & (t >= LIMIAR_TROCA_FRACAO * np.asarray(comparecimento_2))


def faixa_swing(swing) -> pd.Series:
    """Faixa do movimento do município (em pontos de fatia, sem sinal)."""
    a = np.abs(np.asarray(swing, dtype=float)) * 100
    return pd.Series(pd.cut(a, FAIXAS_SWING, labels=ROTULOS_SWING)).astype(str)


def faixa_troca(d: pd.DataFrame) -> np.ndarray:
    """Faixa do movimento do município combinada com a faixa de reserva."""
    fr = pd.cut(d["reserva_frac"].fillna(0), FAIXAS_RESERVA, labels=ROTULOS_RESERVA)
    return (faixa_swing(d["swing"]).to_numpy().astype(object) + " | "
            + fr.astype(str).to_numpy().astype(object))


def marcar_atipicos(d: pd.DataFrame) -> pd.DataFrame:
    d = d.copy()
    d["atip_troca"] = troca_alta(d["troca_max"], d["comparecimento_2"])
    d["atip_estrita"] = d["troca_estrita_max"] > 0
    d["atip_desvio"] = d["z_delta"].abs() > LIMIAR_Z
    d["atipico"] = d["atip_troca"] | d["atip_estrita"] | d["atip_desvio"]
    return d


def _pct(s: pd.Series, q: float) -> Optional[float]:
    s = s.dropna()
    return None if s.empty else float(np.percentile(s, q))


def _r(x, n=4):
    if x is None:
        return None
    try:
        if not np.isfinite(x):
            return None
    except TypeError:
        return x
    return round(float(x), n)


def _dp(p: pd.Series) -> float:
    """Desvio padrão da soma de Bernoullis independentes."""
    p = p.dropna()
    return float(np.sqrt((p * (1 - p)).sum()))


def resumir_grupo(g: pd.DataFrame) -> dict:
    n = len(g)
    lid22 = int((g["lider_1"] == "22").sum())
    lid13 = int((g["lider_1"] == "13").sum())
    v2213 = g["virada"] == "22->13"
    v1322 = g["virada"] == "13->22"
    vir = g[g["virada"] != ""]
    out = {
        "secoes": n,
        "lider_t1_22": lid22, "lider_t1_13": lid13,
        "viradas_22_13": int(v2213.sum()), "viradas_13_22": int(v1322.sum()),
        "taxa_22_13": _r(v2213.sum() / lid22 if lid22 else None, 5),
        "taxa_13_22": _r(v1322.sum() / lid13 if lid13 else None, 5),
        "taxa_virada": _r(len(vir) / n if n else None, 5),
        "esperado_22_13": _r(g.loc[g["lider_1"] == "22", "p_virada"].sum(), 1),
        "esperado_13_22": _r(g.loc[g["lider_1"] == "13", "p_virada"].sum(), 1),
        "esperado_22_13_dp": _r(_dp(g.loc[g["lider_1"] == "22", "p_virada"]), 1),
        "esperado_13_22_dp": _r(_dp(g.loc[g["lider_1"] == "13", "p_virada"]), 1),
        "esperado_faixa_22_13": _r(g.loc[g["lider_1"] == "22", "p_faixa"].sum(), 1),
        "esperado_faixa_13_22": _r(g.loc[g["lider_1"] == "13", "p_faixa"].sum(), 1),
        "margem_viradas_media": _r(vir["margem_t1"].mean() if len(vir) else None, 2),
        "margem_viradas_p50": _r(_pct(vir["margem_t1"], 50), 1),
        "margem_viradas_p90": _r(_pct(vir["margem_t1"], 90), 1),
        "margem_viradas_max": int(vir["margem_t1"].max()) if len(vir) else None,
        "viradas_margem_ate_10": int((vir["margem_t1"] <= 10).sum()),
        "margem_todas_p50": _r(_pct(g["margem_t1"], 50), 1),
        "delta_fatia_media": _r(g["delta_fatia"].mean(), 5),
        "delta_fatia_desvio": _r(g["delta_fatia"].std(), 5),
        "delta_fatia_p01": _r(_pct(g["delta_fatia"], 1), 5),
        "delta_fatia_p05": _r(_pct(g["delta_fatia"], 5), 5),
        "delta_fatia_p50": _r(_pct(g["delta_fatia"], 50), 5),
        "delta_fatia_p95": _r(_pct(g["delta_fatia"], 95), 5),
        "delta_fatia_p99": _r(_pct(g["delta_fatia"], 99), 5),
        "troca_viradas_zero": int((vir["troca_minima"] == 0).sum()),
        "troca_viradas_p50": _r(_pct(vir["troca_minima"], 50), 1),
        "troca_viradas_p90": _r(_pct(vir["troca_minima"], 90), 1),
        "troca_viradas_p99": _r(_pct(vir["troca_minima"], 99), 1),
        "troca_viradas_max": int(vir["troca_minima"].max()) if len(vir) else None,
        "troca_vencedor_pos": int((g["troca_vencedor"] > 0).sum()),
        "troca_vencedor_p99": _r(_pct(g["troca_vencedor"], 99), 1),
        "troca_vencedor_p999": _r(_pct(g["troca_vencedor"], 99.9), 1),
        "troca_max_pos": int((g["troca_max"] > 0).sum()),
        "troca_max_p999": _r(_pct(g["troca_max"], 99.9), 1),
        "troca_max_max": int(g["troca_max"].max()) if n else None,
        "atip_troca": int(g["atip_troca"].sum()),
        "esperado_atip_troca": _r(g["p_troca"].sum(), 1) if "p_troca" in g else None,
        "atip_estrita": int(g["atip_estrita"].sum()),
        "atip_desvio": int(g["atip_desvio"].sum()),
        "atipicos": int(g["atipico"].sum()),
        "atipicos_por_10mil": _r(10000 * g["atipico"].sum() / n if n else None, 2),
        "aptos_mudou": int(g["aptos_mudou"].sum()),
    }
    for k in ("22_13", "13_22"):
        e = out[f"esperado_{k}"]
        out[f"obs_esp_{k}"] = _r(out[f"viradas_{k}"] / e if e else None, 3)
    return out


def resumir(d: pd.DataFrame, ano: int, ufs_comparaveis: Optional[set] = None) -> pd.DataFrame:
    linhas = []
    for uf, g in d.groupby("uf"):
        linhas.append({"ano": ano, "nivel": "uf", "grupo": uf, **resumir_grupo(g)})
    for rg, g in d.groupby("regiao"):
        linhas.append({"ano": ano, "nivel": "regiao", "grupo": rg, **resumir_grupo(g)})
    linhas.append({"ano": ano, "nivel": "brasil", "grupo": "BR", **resumir_grupo(d)})
    if ufs_comparaveis:
        g = d[d["uf"].isin(ufs_comparaveis)]
        if len(g):
            linhas.append({"ano": ano, "nivel": "comparavel", "grupo": "UFs comparáveis",
                           **resumir_grupo(g)})
    return pd.DataFrame(linhas)


COLS_ATIPICOS = [
    "ano", "uf", "regiao", "cd_mun", "municipio", "zona", "secao", "virada",
    "atip_troca", "atip_estrita", "atip_desvio",
    "v13_1", "v22_1", "outros_1", "brancos_1", "nulos_1", "comparecimento_1", "aptos_1",
    "v13_2", "v22_2", "brancos_2", "nulos_2", "comparecimento_2", "aptos_2",
    "margem_t1", "delta_fatia", "delta_esperado", "z_delta", "z_ref", "swing",
    "troca_max", "troca_max_cand", "troca_estrita_max",
    "troca_vencedor", "troca_estrita_vencedor", "p_virada",
    "tipo_urna_1", "tipo_urna_2", "modelo_urna_1", "modelo_urna_2",
    "numero_interno_urna_1", "numero_interno_urna_2", "mesma_urna",
    "codigo_carga_1", "codigo_carga_2", "mesma_carga",
    "encerramento_local_1", "encerramento_local_2", "encerramento_bsb_2",
    "minutos_apos_17h_bsb_2", "n_versoes_bu_2", "hash_2",
]


def juntar_software(d: pd.DataFrame, software: Path = SOFTWARE_T2) -> pd.DataFrame:
    """Número interno e código de carga do 2º turno (secoes_software.parquet)."""
    d = d.copy()
    d["numero_interno_urna_2"] = pd.array([pd.NA] * len(d), dtype="Int64")
    d["codigo_carga_2"] = pd.Series([None] * len(d), dtype=object, index=d.index)
    if not software.exists():
        return d
    sw = pd.read_parquet(software, columns=CHAVE + ["numero_interno_urna", "codigo_carga"])
    sw = sw.drop_duplicates(CHAVE, keep="last").rename(
        columns={"numero_interno_urna": "_ni", "codigo_carga": "_cc"})
    m = d[CHAVE].merge(sw, on=CHAVE, how="left")
    d["numero_interno_urna_2"] = pd.array(m["_ni"].to_numpy(), dtype="Int64")
    d["codigo_carga_2"] = m["_cc"].astype(object).where(m["_cc"].notna(), None).to_numpy()
    return d


def completar_por_bu(at: pd.DataFrame, dirs: list[Path] = PARTS_T2) -> pd.DataFrame:
    """Para atípicos sem linha de software, lê o BU (só leitura) e extrai urna e carga."""
    import pyarrow.parquet as pq
    from dataurnas.downloader.ele2026 import bu_to_rows

    at = at.copy()
    falta = at["numero_interno_urna_2"].isna() & at["hash_2"].notna()
    if not falta.any():
        return at
    alvo = {str(h): i for i, h in at.loc[falta, "hash_2"].items()}
    ufs = sorted(set(at.loc[falta, "uf"]))
    for d in dirs:
        for f in sorted(Path(d).glob("versoes-*.parquet")):
            if not alvo:
                return at
            try:
                t = pq.read_table(f, columns=["hash", "tipo", "conteudo"],
                                  filters=[("tipo", "in", ["bu", "busa"]),
                                           ("hash", "in", list(alvo))])
            except Exception as e:  # part em gravação
                log.warning("ignorado %s: %s", f.name, e)
                continue
            for r in t.to_pylist():
                i = alvo.pop(str(r["hash"]), None)
                if i is None:
                    continue
                try:
                    sec, _ = bu_to_rows(bytes(r["conteudo"]), ELEICAO_2026_T2, 1)
                except Exception as e:  # BU ilegível: fica sem a informação
                    log.warning("BU ilegível %s: %s", r["hash"], e)
                    continue
                num = sec.get("numero_interno_urna")
                at.at[i, "numero_interno_urna_2"] = None if num is None else int(num)
                cc = sec.get("codigo_carga")
                at.at[i, "codigo_carga_2"] = None if cc is None else str(cc)
    log.info("BU lido para atípicos sem software; UFs %s; não encontrados %d", ufs, len(alvo))
    return at


def _norm(v) -> str:
    """Texto comparável: 1, 1.0 e "1" viram "1"."""
    if isinstance(v, (float, np.floating)) and float(v).is_integer():
        return str(int(v))
    return str(v).strip()


def comparar_urna(at: pd.DataFrame) -> pd.DataFrame:
    at = at.copy()
    for a, b, c in (("numero_interno_urna_1", "numero_interno_urna_2", "mesma_urna"),
                    ("codigo_carga_1", "codigo_carga_2", "mesma_carga")):
        if a in at.columns and b in at.columns:
            x = at[a].astype(object).where(at[a].notna(), None)
            y = at[b].astype(object).where(at[b].notna(), None)
            at[c] = [None if (p is None or q is None) else _norm(p) == _norm(q)
                     for p, q in zip(x, y, strict=True)]
        else:
            at[c] = None
    return at


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def preparar(t1: pd.DataFrame, t2: pd.DataFrame) -> pd.DataFrame:
    d = metricas(parear(t1, t2))
    d["swing"] = swing_municipal(d)
    d = pd.concat([d, z_robusto(d)], axis=1)
    return marcar_atipicos(d)


def calibracao(d: pd.DataFrame) -> list[dict]:
    """Observado x esperado por decil de probabilidade (no ano do ajuste)."""
    g = d[d["p_virada"].notna()].copy()
    g["decil"] = pd.qcut(g["p_virada"].rank(method="first"), 10, labels=False)
    out = []
    for k, x in g.groupby("decil"):
        out.append({"decil": int(k), "secoes": len(x),
                    "p_media": _r(x["p_virada"].mean(), 5),
                    "observado": int((x["virada"] != "").sum()),
                    "esperado": _r(x["p_virada"].sum(), 1)})
    return out


def tabela_faixas(d22: pd.DataFrame, d26: pd.DataFrame) -> pd.DataFrame:
    linhas = []
    for ano, d in ((2022, d22), (2026, d26)):
        g = d[d["lider_1"] != "empate"]
        for (fm, fr), x in g.groupby([pd.cut(g["margem_t1"], FAIXAS_MARGEM, labels=ROTULOS_MARGEM),
                                      pd.cut(g["reserva_frac"].fillna(0), FAIXAS_RESERVA,
                                             labels=ROTULOS_RESERVA)], observed=True):
            linhas.append({"ano": ano, "faixa_margem": str(fm), "faixa_reserva": str(fr),
                           "secoes": len(x), "viradas": int((x["virada"] != "").sum()),
                           "taxa": _r((x["virada"] != "").mean(), 5)})
    return pd.DataFrame(linhas)


def tabela_swing(d22: pd.DataFrame, d26: pd.DataFrame) -> list[dict]:
    out = []
    for ano, d in ((2022, d22), (2026, d26)):
        for k, x in d.groupby(faixa_swing(d["swing"]).to_numpy()):
            out.append({"ano": ano, "faixa_swing_pp": k, "secoes": len(x),
                        "troca_alta": int(x["atip_troca"].sum()),
                        "taxa_por_10mil": _r(1e4 * x["atip_troca"].mean(), 2)})
    return out


GRUPOS_VIRADA = (("22->13", "22 para 13"), ("13->22", "13 para 22"), ("", "sem virada"))


def tabela_grupos(d: pd.DataFrame, ano: int) -> pd.DataFrame:
    """Somas do 1º e do 2º turno por grupo de virada (22 para 13, 13 para 22, sem
    virada e todas), no Brasil, por região e por UF: seções, aptos, comparecimento,
    abstenção (aptos - comparecimento), 13, 22, outros, brancos e nulos."""
    x = d.copy()
    x["grupo_virada"] = x["virada"].map(dict(GRUPOS_VIRADA)).fillna("sem virada")
    for t in ("1", "2"):
        x[f"abstencao_{t}"] = x[f"aptos_{t}"] - x[f"comparecimento_{t}"]
    soma = [f"{c}_{t}" for c in ("aptos", "comparecimento", "abstencao", "v13", "v22",
                                  "outros", "brancos", "nulos") for t in ("1", "2")]
    niveis = (("brasil", None), ("regiao", "regiao"), ("uf", "uf"))
    partes = []
    for nivel, col in niveis:
        chave = x[col] if col else pd.Series("BR", index=x.index)
        for todos in (False, True):
            gr = [chave, pd.Series("todas", index=x.index) if todos else x["grupo_virada"]]
            g = x.groupby(gr)[soma].sum()
            g["secoes"] = x.groupby(gr).size()
            g = g.reset_index()
            g.columns = ["grupo", "grupo_virada"] + list(g.columns[2:])
            g.insert(0, "nivel", nivel)
            partes.append(g)
    t = pd.concat(partes, ignore_index=True)
    t.insert(0, "ano", ano)
    for c in ("aptos", "comparecimento", "abstencao", "v13", "v22", "outros", "brancos", "nulos"):
        t[f"{c}_var"] = t[f"{c}_2"] - t[f"{c}_1"]
    for tt in ("1", "2"):
        t[f"invalidos_{tt}"] = t[f"brancos_{tt}"] + t[f"nulos_{tt}"]
    t["invalidos_var"] = t["invalidos_2"] - t["invalidos_1"]
    return t.sort_values(["nivel", "grupo", "grupo_virada"]).reset_index(drop=True)


def principais(at: pd.DataFrame, n: int = 40) -> list[dict]:
    if at.empty:
        return []
    ordem = at.assign(_k=at["troca_estrita_max"] * 1000 + at["troca_max"] * 10
                      + at["z_delta"].abs().fillna(0))
    ordem = ordem.sort_values("_k", ascending=False).head(n)
    cols = [c for c in COLS_ATIPICOS if c in ordem.columns]
    return json.loads(ordem[cols].to_json(orient="records", force_ascii=False))


def executar(saida: Path = SAIDA, ler_bu: bool = True, enc_t2: Path = ENC_T2,
             software_t2: Path = SOFTWARE_T2) -> dict:
    saida.mkdir(parents=True, exist_ok=True)
    log.info("carregando 2022")
    a22, b22 = carregar_2022()
    d22 = preparar(a22, b22)
    log.info("2022: %d seções pareadas", len(d22))
    log.info("carregando 2026")
    t1 = carregar_2026_t1()
    t2 = carregar_2026_t2(enc_t2)
    d26 = preparar(t1, t2)
    log.info("2026: %d seções do 2º turno, %d pareadas com o 1º", len(t2), len(d26))

    # nomes de município de 2022 pelo código TSE (o mesmo em 2026)
    nomes = t1.drop_duplicates("cd_mun").set_index("cd_mun")["municipio"]
    d22["municipio"] = d22["cd_mun"].map(nomes)

    X, y, mask = features(d22)
    beta = ajustar_logistica(X[mask], y[mask])
    d22["p_virada"] = aplicar_modelo(d22, beta)
    d26["p_virada"] = aplicar_modelo(d26, beta)
    # tabela por faixas: taxa de 2022 aplicada a 2026
    taxa_f = d22[d22["lider_1"] != "empate"].assign(f=faixas).groupby("f")["virada"].apply(
        lambda s: (s != "").mean())
    for d in (d22, d26):
        f = faixas(d)
        d["p_faixa"] = np.where(d["lider_1"] != "empate", f.map(taxa_f).fillna(0), np.nan)
    # troca alta esperada pelo movimento do município e pela reserva (taxa de 2022)
    taxa_s = d22.groupby(faixa_troca(d22))["atip_troca"].mean()
    for d in (d22, d26):
        d["p_troca"] = pd.Series(faixa_troca(d)).map(taxa_s).fillna(0).to_numpy()

    cobertura = (d26.groupby("uf").size() / t1.groupby("uf").size()).dropna()
    comparaveis = set(cobertura[cobertura >= COBERTURA_MIN_UF].index)
    res = pd.concat([resumir(d22, 2022, comparaveis), resumir(d26, 2026, comparaveis)],
                    ignore_index=True)
    res.to_parquet(saida / "resumo_uf.parquet", index=False)
    tf = tabela_faixas(d22, d26)
    tf.to_parquet(saida / "faixas.parquet", index=False)
    tg = pd.concat([tabela_grupos(d22, 2022), tabela_grupos(d26, 2026)], ignore_index=True)
    tg.to_parquet(saida / "grupos.parquet", index=False)

    d22["ano"] = 2022
    d26["ano"] = 2026
    at26 = d26[d26["atipico"]].copy()
    at26 = juntar_software(at26, software_t2)
    if ler_bu:
        at26 = completar_por_bu(at26)
    at26 = comparar_urna(at26)
    at22 = comparar_urna(d22[d22["atipico"]].copy())
    for nome, at in (("2026", at26), ("2022", at22)):
        cols = [c for c in COLS_ATIPICOS if c in at.columns]
        at = at[cols].sort_values(["uf", "cd_mun", "zona", "secao"])
        at.to_parquet(saida / f"atipicos_{nome}.parquet", index=False)
        at.to_csv(saida / f"atipicos_{nome}.csv", index=False)
    d22.to_parquet(saida / "secoes_2022.parquet", index=False)
    d26.to_parquet(saida / "secoes_2026.parquet", index=False)

    nomes_beta = ["intercepto", "gap_x_raiz_n", "gap", "margem_frac_x_raiz_n",
                  "reserva_frac", "log_n"]
    resumo = {
        "secoes_t2_2026": int(len(t2)), "pareadas_2026": int(len(d26)),
        "pareadas_2022": int(len(d22)),
        "cobertura_uf_2026": {k: _r(v, 4) for k, v in cobertura.sort_index().items()},
        "ufs_comparaveis": sorted(comparaveis),
        "limiares": {"troca_votos": LIMIAR_TROCA_VOTOS, "troca_fracao": LIMIAR_TROCA_FRACAO,
                     "z": LIMIAR_Z, "min_secoes_mun": MIN_SECOES_MUN,
                     "min_votos_fatia": MIN_VOTOS_FATIA, "min_votos_swing": MIN_VOTOS_SWING},
        "troca_por_faixa_swing": tabela_swing(d22, d26),
        "modelo": {"coeficientes": dict(zip(nomes_beta, [_r(b, 6) for b in beta], strict=True)),
                   "calibracao_2022": calibracao(d22), "calibracao_2026": calibracao(d26)},
        "resumo": json.loads(res.to_json(orient="records", force_ascii=False)),
        "grupos": json.loads(tg[tg["nivel"] != "uf"].to_json(orient="records",
                                                               force_ascii=False)),
        "principais_atipicos_2026": principais(at26),
        "principais_atipicos_2022": principais(at22),
        "atipicos_2026_urna": {
            "total": int(len(at26)),
            "mesma_urna": int((at26["mesma_urna"] == True).sum()),  # noqa: E712
            "urna_diferente": int((at26["mesma_urna"] == False).sum()),  # noqa: E712
            "sem_informacao": int(at26["mesma_urna"].isna().sum()),
            "mesma_carga": int((at26["mesma_carga"] == True).sum()),  # noqa: E712
            "contingencia_ou_reserva_t2": int(at26["tipo_urna_2"].isin(
                ["contingencia", "reservaSecao", "reservaEncerrandoSecao"]).sum()),
        },
    }
    (saida / "resumo.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=1),
                                       encoding="utf-8")
    return resumo


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--saida", default=str(SAIDA))
    ap.add_argument("--t2", default=str(ENC_T2),
                    help="seções do 2º turno no formato de secoes_encerramento.parquet "
                         "(por exemplo, a exportação de viradas_t2_ch.sql)")
    ap.add_argument("--software", default=str(SOFTWARE_T2),
                    help="número interno da urna e código de carga do 2º turno")
    ap.add_argument("--sem-bu", action="store_true",
                    help="não lê BU dos atípicos sem linha de software")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    r = executar(Path(args.saida), ler_bu=not args.sem_bu, enc_t2=Path(args.t2),
                 software_t2=Path(args.software))
    for linha in r["resumo"]:
        if linha["nivel"] in ("brasil", "comparavel"):
            log.info("%s %s: viradas 22->13 %s (esp %s), 13->22 %s (esp %s), atípicos %s",
                     linha["ano"], linha["grupo"], linha["viradas_22_13"],
                     linha["esperado_22_13"], linha["viradas_13_22"],
                     linha["esperado_13_22"], linha["atipicos"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
