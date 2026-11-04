#!/usr/bin/env python3
"""Compare the 2026 electorate of each municipality with its adult population.

The registered electorate of a municipality should not exceed its resident
population aged 16 or over (voting is allowed from 16). Exceeding it is a known
phenomenon (people keep their registration in their home town after moving),
but a large or growing excess is a classic sign of an inflated voter roll,
which is where votes in the name of absent voters could come from.

Inputs:
  - IBGE Census 2022, table 9514 (resident population by age), saved from
    https://apisidra.ibge.gov.br/values/t/9514/n6/all/v/93/p/2022/c2/6794/
    c287/100362,93070,93084,93085,6572/c286/113635/f/c
  - data/parquet/2026/resultado_municipio.parquet (1st round, electorate and
    votes) and data/parquet/2026/t2/resultado_municipio.parquet (2nd round)
  - data/parquet/secoes.parquet (2022 sections, electorate per section)

Output: JSON summary and a per-municipality Parquet.

A second download of the same table with c287/6567,6568 (ages 10 and 11)
gives the population aged 12+ in 2022, the proxy for voting age in 2026.

Usage:
  python3 scripts/ele2026/eleitorado_populacao.py --sidra pop.json \
      --sidra-10-11 pop1011.json --saida data/parquet/2026/t2/eleitorado_populacao
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
UNDER_16 = {"93070", "93084", "93085", "6572"}  # 0-4, 5-9, 10-14 and 15 years


def adult_population(sidra_json: str, sidra_10_11: str) -> pd.DataFrame:
    """Population aged 16+ in 2022 and aged 12+ in 2022 per IBGE municipality.

    People aged 12 or more at the 2022 Census are 16 or more at the 2026
    election, so pop_12_mais is the proxy for the 2026 voting-age population
    (it ignores deaths and migration in the four years, which lower it)."""
    rows = json.load(open(sidra_json))[1:] + json.load(open(sidra_10_11))[1:]
    df = pd.DataFrame(rows)[["D1C", "D5C", "V"]]
    df["V"] = pd.to_numeric(df["V"], errors="coerce").fillna(0).astype(int)
    by_age = df.pivot_table(index="D1C", columns="D5C", values="V", aggfunc="sum").fillna(0)
    total = by_age["100362"]
    under_16 = by_age[list(UNDER_16)].sum(axis=1)
    under_12 = by_age[["93070", "93084", "6567", "6568"]].sum(axis=1)  # 0-9, 10 and 11
    return pd.DataFrame({"pop_total": total, "pop_16_mais": total - under_16,
                         "pop_12_mais": total - under_12}).reset_index(names="cd_ibge")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sidra", required=True)
    ap.add_argument("--sidra-10-11", required=True,
                    help="same table, ages 10 and 11 only (c287/6567,6568)")
    ap.add_argument("--saida", required=True)
    a = ap.parse_args()
    out = Path(a.saida)
    out.mkdir(parents=True, exist_ok=True)

    pop = adult_population(a.sidra, a.sidra_10_11)
    con = duckdb.connect()
    con.register("pop", pop)
    p = ROOT / "data" / "parquet"
    df = con.sql(f"""
        WITH t1 AS (SELECT * FROM '{p}/2026/resultado_municipio.parquet' WHERE uf <> 'zz'),
             t2 AS (SELECT * FROM '{p}/2026/t2/resultado_municipio.parquet' WHERE uf <> 'zz'),
             e22 AS (SELECT municipio AS cd_mun, sum(eleitores_aptos) AS eleitorado_2022
                     FROM '{p}/secoes.parquet' WHERE turno = 2 GROUP BY 1)
        SELECT t1.uf, t1.cd_mun, t1.cd_ibge, t1.nome, t1.eleitorado AS eleitorado_2026,
               e22.eleitorado_2022, pop.pop_total, pop.pop_16_mais, pop.pop_12_mais,
               t1.comparecimento AS comp_t1, t2.comparecimento AS comp_t2,
               t1.v_13 AS v13_t1, t1.v_22 AS v22_t1, t2.v_13 AS v13_t2, t2.v_22 AS v22_t2
        FROM t1 JOIN t2 USING (cd_mun)
        LEFT JOIN pop ON pop.cd_ibge = t1.cd_ibge
        LEFT JOIN e22 ON e22.cd_mun = t1.cd_mun
    """).df()

    # 2026 electorate against the 2026 voting-age proxy; 2022 against 2022 adults
    df["razao"] = df["eleitorado_2026"] / df["pop_12_mais"]
    df["razao_2022"] = df["eleitorado_2022"] / df["pop_16_mais"]
    df["swing_13_pp"] = 100 * (df["v13_t2"] / (df["v13_t2"] + df["v22_t2"])
                               - df["v13_t1"] / (df["v13_t1"] + df["v22_t1"]))
    df["delta_comp_pp"] = 100 * (df["comp_t2"] - df["comp_t1"]) / df["eleitorado_2026"]
    df["acima"] = df["razao"] > 1
    df.to_parquet(out / "municipios.parquet", index=False)

    ok = df.dropna(subset=["razao"])
    w = ok["v13_t1"] + ok["v22_t1"]

    def wmean(x: pd.Series, m: pd.Series) -> float:
        return float(np.average(x[m], weights=w[m])) if m.any() else float("nan")

    faixas = pd.cut(ok["razao"], [0, 0.8, 0.9, 1.0, 1.1, 1.2, np.inf])
    por_faixa = []
    for f, g in ok.groupby(faixas, observed=True):
        m = ok.index.isin(g.index)
        por_faixa.append({"faixa_razao": str(f), "municipios": len(g),
                          "eleitorado": int(g["eleitorado_2026"].sum()),
                          "swing_13_pp_ponderado": round(wmean(ok["swing_13_pp"], m), 2),
                          "delta_comparecimento_pp": round(wmean(ok["delta_comp_pp"], m), 2)})
    excesso = (ok["eleitorado_2026"] - ok["pop_12_mais"]).clip(lower=0)
    resumo = {
        "municipios": len(df), "sem_populacao": int(df["razao"].isna().sum()),
        "eleitorado_total": int(ok["eleitorado_2026"].sum()),
        "pop_12_mais_2022_total": int(ok["pop_12_mais"].sum()),
        "municipios_eleitorado_acima_pop_12_mais": int(ok["acima"].sum()),
        "municipios_acima_em_2022": int((ok["razao_2022"] > 1).sum()),
        "excesso_somado": int(excesso.sum()),
        "correlacao_razao_swing": round(float(ok["razao"].corr(ok["swing_13_pp"])), 3),
        "correlacao_razao_delta_comparecimento": round(
            float(ok["razao"].corr(ok["delta_comp_pp"])), 3),
        # same correlations after removing each UF's mean (regional composition)
        "correlacao_dentro_uf_razao_swing": round(float(
            (ok["razao"] - ok.groupby("uf")["razao"].transform("mean")).corr(
                ok["swing_13_pp"] - ok.groupby("uf")["swing_13_pp"].transform("mean"))), 3),
        "correlacao_dentro_uf_razao_delta_comparecimento": round(float(
            (ok["razao"] - ok.groupby("uf")["razao"].transform("mean")).corr(
                ok["delta_comp_pp"] - ok.groupby("uf")["delta_comp_pp"].transform("mean"))), 3),
        "swing_acima_x_resto_pp": [round(wmean(ok["swing_13_pp"], ok["acima"]), 2),
                                   round(wmean(ok["swing_13_pp"], ~ok["acima"]), 2)],
        "por_faixa": por_faixa,
        "maiores_razoes": ok.nlargest(15, "razao")[
            ["uf", "nome", "eleitorado_2026", "eleitorado_2022", "pop_12_mais", "razao",
             "swing_13_pp"]].round(3).to_dict("records"),
    }
    (out / "resumo.json").write_text(json.dumps(resumo, indent=2, ensure_ascii=False))
    print(json.dumps({k: v for k, v in resumo.items() if k != "maiores_razoes"},
                     indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
