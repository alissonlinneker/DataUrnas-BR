#!/usr/bin/env python3
"""End-to-end test of the hypothesis "votes were inserted without fingerprint".

A vote cast without fingerprint is either from a voter with no biometric
record (BU field comp_sem_biometria) or from a voter with a record who was
enabled by birth year after the fingerprint failed (habilitados_biografia).
If poll workers voted for absent voters, or software added votes, those votes
would have to enter through these two counts, because a voter with a
fingerprint on file is only enabled without it after four failed reads.

Tests, all on the BU of every section present in both rounds:

  1. National totals of digital and non-digital votes in each round.
  2. Impossible values. The biometric roll is closed months before the
     election, so a voter enabled by fingerprint or by birth year in one round
     (both mean "has a fingerprint on file") cannot be "without biometric
     record" in the other. Hence, per section:
         sem_bio_2 <= aptos - (hab_bio_1 + hab_biog_1)
         sem_bio_1 <= aptos - (hab_bio_2 + hab_biog_2)
     Any violation is a count that cannot happen with a fixed roll.
  3. Excess non-digital votes per section. Under no manipulation the share of
     non-digital votes in round 2 follows the section's own round 1 share
     (adjusted by the national drift) with binomial noise. z-scores, tail
     counts and their spread are compared with 2022, measured the same way.
  4. Who the extra non-digital voters voted for. Within each municipality,
     the change in 13 and 22 votes is regressed on the change in digital and
     non-digital voters; the share of each extra voter going to 13 is compared
     between the two kinds, with a cluster bootstrap by municipality. Same in
     2022 as control.
  5. Sections with a strong excess of non-digital votes: does the vote move
     to one candidate there more than in the rest of their municipality?
  6. Power: votes for 13 are injected as non-digital votes into random
     sections of the real data, in growing amounts, to find the smallest
     injection that tests 4 and 5 would flag, and that is compared with the
     4,430,191 margin.

Inputs: Parquet from sem_biometria_ch.sql (2026) and sem_biometria_2022_ch.sql.

Usage:
  python3 scripts/ele2026/sem_biometria_probabilidade.py \
      --d2026 sem_bio_2026.parquet --d2022 sem_bio_2022.parquet --saida out.json
"""

from __future__ import annotations

import argparse
import json
from math import erfc, sqrt

import numpy as np
import pandas as pd

SEED = 20261025
MARGIN = 4_430_191


def gaussian_tail(k: float) -> float:
    """Two-sided P(|Z| > k) for a standard normal."""
    return erfc(k / sqrt(2))


def demean(df: pd.DataFrame, cols: list[str], by: str = "cd_mun") -> pd.DataFrame:
    return df[cols] - df.groupby(by)[cols].transform("mean")


def excess_z(nd1, c1, nd2, c2) -> np.ndarray:
    """z of round-2 non-digital count against the section's round-1 share."""
    drift = (nd2.sum() / c2.sum()) / (nd1.sum() / c1.sum())
    # half-count pseudo-observation: a section with 0 in round 1 must not get
    # an expected value of zero, which turns any round-2 voter into a huge z
    p = np.clip((nd1 + 0.5) / (c1 + 1) * drift, 1e-4, 1 - 1e-4)
    exp = c2 * p
    var = c2 * p * (1 - p) + c2**2 * p * (1 - p) / c1
    return ((nd2 - exp) / np.sqrt(var)).to_numpy()


def tail_stats(z: np.ndarray) -> dict:
    n = len(z)
    out = {"secoes": n, "dp_z": round(float(np.std(z)), 3)}
    for k in (4, 6):
        out[f"z_maior_{k}"] = int((z > k).sum())
        out[f"z_menor_menos_{k}"] = int((z < -k).sum())
        out[f"esperado_normal_cada_lado_{k}"] = round(n * gaussian_tail(k) / 2, 2)
    return out


def vote_split(df: pd.DataFrame, x_nd: str, x_d: str, reps: int, rng) -> dict:
    """Within-municipality OLS of d13 and d22 on d(non-digital) and d(digital);
    returns the share of each extra voter that went to 13, with bootstrap CI."""
    d = df.assign(d13=df["v13_2"] - df["v13_1"], d22=df["v22_2"] - df["v22_1"])
    dm = demean(d, ["d13", "d22", x_nd, x_d])
    muns = d["cd_mun"].to_numpy()

    def fit(idx: np.ndarray) -> tuple[float, float]:
        X = dm[[x_nd, x_d]].to_numpy()[idx]
        b13 = np.linalg.lstsq(X, dm["d13"].to_numpy()[idx], rcond=None)[0]
        b22 = np.linalg.lstsq(X, dm["d22"].to_numpy()[idx], rcond=None)[0]
        return b13[0] / (b13[0] + b22[0]), b13[1] / (b13[1] + b22[1])

    full = np.arange(len(d))
    s_nd, s_d = fit(full)
    groups = pd.Series(full).groupby(muns).apply(np.array).to_list()
    diffs = []
    for _ in range(reps):
        pick = rng.integers(0, len(groups), len(groups))
        idx = np.concatenate([groups[i] for i in pick])
        a, b = fit(idx)
        diffs.append(a - b)
    lo, hi = np.percentile(diffs, [2.5, 97.5])
    return {"fatia_13_extra_sem_digital": round(float(s_nd), 4),
            "fatia_13_extra_com_digital": round(float(s_d), 4),
            "diferenca": round(float(s_nd - s_d), 4),
            "ic95_diferenca": [round(float(lo), 4), round(float(hi), 4)]}


def excess_vs_swing(df: pd.DataFrame, z: np.ndarray, thr: float = 4.0) -> dict:
    """Swing to 13 in sections with excess non-digital votes, relative to
    their municipality, against the same relative swing in the other sections."""
    sw = 100 * (df["v13_2"] / (df["v13_2"] + df["v22_2"])
                - df["v13_1"] / (df["v13_1"] + df["v22_1"]))
    rel = sw - sw.groupby(df["cd_mun"]).transform("mean")
    m = z > thr
    return {"secoes_excesso": int(m.sum()),
            "swing_relativo_excesso_pp": round(float(rel[m].mean()), 3) if m.any() else None,
            "swing_relativo_resto_pp": round(float(rel[~m].mean()), 3),
            "dp_swing_relativo_pp": round(float(rel.std()), 3)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--d2026", required=True)
    ap.add_argument("--d2022", required=True)
    ap.add_argument("--saida", required=True)
    ap.add_argument("--bootstrap", type=int, default=200)
    a = ap.parse_args()
    rng = np.random.default_rng(SEED)

    df = pd.read_parquet(a.d2026)
    num = [c for c in df.columns if c not in ("uf", "cd_mun", "zona", "secao")]
    df = df.dropna(subset=num)
    df[num] = df[num].astype("int64")
    df = df[(df["comp_1"] > 0) & (df["comp_2"] > 0)
            & (df["v13_1"] + df["v22_1"] > 0) & (df["v13_2"] + df["v22_2"] > 0)].copy()
    for t in ("1", "2"):
        df[f"nd_{t}"] = df[f"sem_bio_{t}"] + df[f"hab_biog_{t}"]
    df["dnd"] = df["nd_2"] - df["nd_1"]
    df["dd"] = df["hab_bio_2"] - df["hab_bio_1"]
    out: dict = {"secoes_2026": len(df)}

    # 1. national totals
    nat = {}
    for t in ("1", "2"):
        c = int(df[f"comp_{t}"].sum())
        nat[f"turno_{t}"] = {
            "comparecimento": c,
            "sem_biometria_cadastrada": int(df[f"sem_bio_{t}"].sum()),
            "habilitados_ano_nascimento": int(df[f"hab_biog_{t}"].sum()),
            "habilitados_digital": int(df[f"hab_bio_{t}"].sum()),
            "sem_digital_total": int(df[f"nd_{t}"].sum()),
            "pct_sem_digital": round(100 * df[f"nd_{t}"].sum() / c, 3)}
    nat["variacao_sem_digital"] = nat["turno_2"]["sem_digital_total"] - nat["turno_1"]["sem_digital_total"]
    nat["variacao_digital"] = nat["turno_2"]["habilitados_digital"] - nat["turno_1"]["habilitados_digital"]
    out["totais"] = nat

    # 2. impossible values with a closed biometric roll. The inequality only
    # holds when the section has the same voters in both rounds; sections whose
    # roll changed (transit voters, merged sections) are counted apart.
    eq = df[df["aptos_1"] == df["aptos_2"]]
    i1 = eq["sem_bio_2"] > eq["aptos_1"] - (eq["hab_bio_1"] + eq["hab_biog_1"])
    i2 = eq["sem_bio_1"] > eq["aptos_1"] - (eq["hab_bio_2"] + eq["hab_biog_2"])
    out["impossiveis"] = {
        "secoes_mesmos_aptos": len(eq),
        "aptos_diferentes_entre_turnos": int((df["aptos_1"] != df["aptos_2"]).sum()),
        "sem_bio_2_acima_do_possivel": int(i1.sum()),
        "sem_bio_1_acima_do_possivel": int(i2.sum()),
        "comparecimento_acima_aptos": int(((df["comp_1"] > df["aptos_1"])
                                           | (df["comp_2"] > df["aptos_2"])).sum()),
        "exemplos": eq.loc[i1 | i2, ["uf", "cd_mun", "zona", "secao", "aptos_1",
                                     "sem_bio_1", "hab_bio_1", "hab_biog_1", "sem_bio_2",
                                     "hab_bio_2", "hab_biog_2"]].head(30).to_dict("records"),
    }

    # 3. excess non-digital per section, with 2022 control
    z26 = excess_z(df["nd_1"], df["comp_1"], df["nd_2"], df["comp_2"])
    d22 = pd.read_parquet(a.d2022)
    d22 = d22[(d22["comp_1"] > 0) & (d22["comp_2"] > 0) & (d22["v13_1"] + d22["v22_1"] > 0)
              & (d22["v13_2"] + d22["v22_2"] > 0)].copy()
    d22["nd_1"] = d22["comp_1"] - d22["bio_1"]
    d22["nd_2"] = d22["comp_2"] - d22["bio_2"]
    d22 = d22[(d22["nd_1"] >= 0) & (d22["nd_2"] >= 0)]
    z22 = excess_z(d22["nd_1"], d22["comp_1"], d22["nd_2"], d22["comp_2"])
    # the 2022 BU (spec v1) only separates "enabled by fingerprint" from the
    # rest, so the comparable 2026 series is digital vs everything else
    z26_sem_cad = excess_z(df["sem_bio_1"], df["comp_1"], df["sem_bio_2"], df["comp_2"])
    z26_biog = excess_z(df["hab_biog_1"], df["comp_1"], df["hab_biog_2"], df["comp_2"])
    out["excesso_por_secao"] = {"2026": tail_stats(z26), "2022": tail_stats(z22),
                                "2026_so_sem_cadastro": tail_stats(z26_sem_cad),
                                "2026_so_ano_nascimento": tail_stats(z26_biog),
                                "pct_sem_digital_2022": [
                                    round(100 * d22["nd_1"].sum() / d22["comp_1"].sum(), 3),
                                    round(100 * d22["nd_2"].sum() / d22["comp_2"].sum(), 3)]}

    # 4. who the extra non-digital voters voted for
    d22["dnd"] = d22["nd_2"] - d22["nd_1"]
    d22["dd"] = d22["bio_2"] - d22["bio_1"]
    out["divisao_do_voto_extra"] = {
        "2026": vote_split(df, "dnd", "dd", a.bootstrap, rng),
        "2022": vote_split(d22, "dnd", "dd", a.bootstrap, rng)}

    # 5. swing in sections with excess non-digital votes
    out["excesso_x_swing"] = {"2026": excess_vs_swing(df, z26), "2022": excess_vs_swing(d22, z22)}

    # 6. power: inject non-digital votes for 13 into random sections
    power = []
    for total in (50_000, 150_000, 500_000, 1_500_000, MARGIN):
        sim = df.copy()
        k = max(1, int(len(sim) * 0.2))
        idx = rng.choice(len(sim), k, replace=False)
        room = (sim["aptos_2"] - sim["comp_2"]).clip(lower=0).to_numpy()[idx]
        add = np.minimum(room, np.ceil(total / k)).astype(int)
        col = sim.columns
        sim.iloc[idx, col.get_loc("v13_2")] += add
        sim.iloc[idx, col.get_loc("sem_bio_2")] += add
        sim.iloc[idx, col.get_loc("comp_2")] += add
        sim["nd_2"] = sim["sem_bio_2"] + sim["hab_biog_2"]
        sim["dnd"] = sim["nd_2"] - sim["nd_1"]
        zs = excess_z(sim["nd_1"], sim["comp_1"], sim["nd_2"], sim["comp_2"])
        split = vote_split(sim, "dnd", "dd", 50, rng)
        power.append({"votos_injetados": int(add.sum()), "secoes_com_injecao": k,
                      "pct_sem_digital_t2": round(100 * sim["nd_2"].sum() / sim["comp_2"].sum(), 3),
                      "z_maior_4": int((zs > 4).sum()),
                      "fatia_13_extra_sem_digital": split["fatia_13_extra_sem_digital"],
                      "ic95_diferenca": split["ic95_diferenca"],
                      "detectado": bool(split["ic95_diferenca"][0] > 0 or (zs > 4).sum()
                                        > 3 * max(1, out["excesso_por_secao"]["2026"]["z_maior_4"]))})
        print(json.dumps(power[-1], ensure_ascii=False), flush=True)
    out["poder_de_deteccao"] = power

    with open(a.saida, "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False, default=int)
    print(json.dumps({k: v for k, v in out.items() if k not in ("poder_de_deteccao",)},
                     indent=1, ensure_ascii=False, default=int)[:6000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
