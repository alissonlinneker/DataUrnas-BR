#!/usr/bin/env python3
"""How large and how shaped would a fraud have to be to invert the 2026 2nd round?

The official margin is 4,430,191 votes (13 over 22). The smallest change that
inverts it is moving 2,215,096 votes from 13 to 22 (every moved vote changes the
margin by two). This script asks whether a manipulation of that size, applied
to a subset of sections, would leave a visible footprint in the section-level
swing (share of 13 among 13 + 22 in the 2nd round minus the same share in the
1st round), compared with the footprint actually observed.

Method: start from the observed sections and add a hypothetical swap of votes
from 22 to 13 in a chosen subset (random sections, the strongest 13 sections
of the 1st round, only the Northeast, only small sections, or every section),
always totalling 2,215,096 votes and never taking more votes from 22 than the
section has. For each scenario the same detection statistics are computed:
residual swing after removing the municipality mean, robust z-scores (median
and MAD), the count of sections beyond |z| > 4 and |z| > 6, and the excess
kurtosis of the residuals. If a scenario multiplies those counts, a real fraud
with that shape would have shown up in the published data, which it did not.

Input: a Parquet exported from ClickHouse view v_comparacao_t1_t2 with columns
uf, cd_mun, votos_13_t1, votos_22_t1, votos_13_t2, votos_22_t2.

Usage:
  python3 scripts/ele2026/simulacao_inversao.py --entrada t1t2.parquet --saida out.json
"""

from __future__ import annotations

import argparse
import json

import numpy as np
import pandas as pd

NORDESTE = {"al", "ba", "ce", "ma", "pb", "pe", "pi", "rn", "se"}
SWAP_NEEDED = 2_215_096  # half of the 4,430,191 margin, rounded up
SEED = 20261025


def detection_stats(df: pd.DataFrame, v13: np.ndarray, v22: np.ndarray) -> dict:
    """Swing statistics used to spot sections with abnormal changes."""
    p1 = df["v13_1"] / (df["v13_1"] + df["v22_1"])
    p2 = v13 / (v13 + v22)
    swing = pd.Series((p2 - p1) * 100, index=df.index)
    resid = swing - swing.groupby(df["cd_mun"]).transform("mean")
    med = resid.median()
    mad = 1.4826 * (resid - med).abs().median()
    z = (resid - med) / mad
    c = resid - resid.mean()
    kurt = float((c**4).mean() / (c**2).mean() ** 2 - 3)
    return {"swing_medio_pp": round(float(swing.mean()), 3),
            "swing_dp_pp": round(float(swing.std()), 3),
            "secoes_z_maior_4": int((z.abs() > 4).sum()),
            "secoes_z_maior_6": int((z.abs() > 6).sum()),
            "curtose_excesso": round(kurt, 2)}


def apply_swap(df: pd.DataFrame, mask: np.ndarray, total: int) -> tuple[np.ndarray, np.ndarray, int]:
    """Move `total` votes from 22 to 13 across masked sections, proportional to
    each section's 22 votes and capped at what the section has."""
    v13 = df["v13_2"].to_numpy(dtype=float).copy()
    v22 = df["v22_2"].to_numpy(dtype=float).copy()
    cap = np.where(mask, v22, 0.0)
    if cap.sum() < total:
        return v13, v22, -1  # the subset does not hold enough 22 votes
    take = np.minimum(cap, cap * total / cap.sum())
    v13 += take
    v22 -= take
    return v13, v22, int(round(take.sum()))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--entrada", required=True)
    ap.add_argument("--saida", required=True)
    a = ap.parse_args()

    df = pd.read_parquet(a.entrada).rename(columns={
        "votos_13_t1": "v13_1", "votos_22_t1": "v22_1",
        "votos_13_t2": "v13_2", "votos_22_t2": "v22_2"})
    df = df[(df["uf"] != "zz") & (df["v13_1"] + df["v22_1"] > 0)
            & (df["v13_2"] + df["v22_2"] > 0)].reset_index(drop=True)
    n = len(df)
    rng = np.random.default_rng(SEED)
    share1 = df["v13_1"] / (df["v13_1"] + df["v22_1"])
    size = df["v13_2"] + df["v22_2"]

    out = {"secoes": n, "votos_a_mover": SWAP_NEEDED,
           "observado": detection_stats(df, df["v13_2"].to_numpy(float),
                                        df["v22_2"].to_numpy(float)),
           "cenarios": []}

    scenarios: list[tuple[str, np.ndarray]] = [("todas as seções (uniforme)", np.ones(n, bool))]
    for frac in (0.5, 0.25, 0.10, 0.05, 0.01):
        m = np.zeros(n, bool)
        m[rng.choice(n, int(n * frac), replace=False)] = True
        scenarios.append((f"{frac:.0%} das seções, sorteadas", m))
    for frac in (0.25, 0.10):
        scenarios.append((f"{frac:.0%} das seções mais favoráveis ao 13 no 1º turno",
                          (share1 >= share1.quantile(1 - frac)).to_numpy()))
    scenarios.append(("só o Nordeste", df["uf"].isin(NORDESTE).to_numpy()))
    scenarios.append(("25% menores seções", (size <= size.quantile(0.25)).to_numpy()))

    for name, mask in scenarios:
        v13, v22, moved = apply_swap(df, mask, SWAP_NEEDED)
        row = {"cenario": name, "secoes_alteradas": int(mask.sum())}
        if moved < 0:
            row["viavel"] = False
        else:
            row.update({"viavel": True, "votos_movidos": moved,
                        "votos_por_secao_alterada": round(moved / mask.sum(), 1),
                        **detection_stats(df, v13, v22)})
        out["cenarios"].append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)

    with open(a.saida, "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    print(json.dumps(out["observado"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
