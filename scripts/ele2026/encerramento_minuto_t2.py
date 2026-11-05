#!/usr/bin/env python3
"""Does the minute a voting machine was closed change who it counted for?

A public claim (late October 2026) says the 2nd round voting machines ran a
hidden routine from 17:01 on that moved votes already cast from 22 (Flávio
Bolsonaro) to 13 (Lula), so machines closed later show more votes for 13. The
evidence offered is a table: all sections sorted by closing time, cut into ten
groups of ~50 thousand, with the share of 13 rising from the first group to the
last.

This script reproduces that table from the BUs and then runs the checks that
separate "the machine changed votes after 17:01" from "the sections that close
later are different places":

  1. Reproduction: deciles of 2nd round closing time (Brasília), share of 13
     over 13 + 22, for Brazil, the state of São Paulo and the city of São Paulo.
  2. Placebo with the 1st round: the same sections, still sorted by their 2nd
     round closing time, but counting their 1st round votes (04/10). A time
     routine in the 2nd round cannot reach votes counted three weeks earlier, so
     if the 1st round shows the same rise, the rise comes from the places.
  3. Change from the 1st to the 2nd round in each section (share of 13 over
     13 + 22), by decile. The claim predicts a growing change for late deciles.
  4. Within the same polling place (same municipality, zone and local de
     votação): each section's share minus the mean of its polling place. Sections
     in the same building share the electorate profile, so the polling place
     removes geography. The claim predicts the rise survives this.
  5. Cut at 17:01:00: sections closed in [17:00:00, 17:01:00) against
     [17:01:00, 17:02:00) in the same polling place, for the 2nd round share and
     for the 1st to 2nd round change.
  6. 2022 2nd round (Lula x Bolsonaro, other software version): the same
     deciles. If the same rise appears, the pattern is older than 2026.
  7. Profile of each decile: region, voters per section, turnout.

Inputs (repository data, outside git):
  data/parquet/2026/t2/impacto/secoes_t1_t2.parquet   (one row per section,
      2nd and 1st round votes and closing times, Brasília)
  data/parquet/2026/secoes_2026.parquet                (local_votacao)
  data/parquet/secoes.parquet, data/parquet/votos_t2.parquet   (2022)

Outputs in --out: resumo.json and tabelas.md.

Usage:
  uv run python scripts/ele2026/encerramento_minuto_t2.py --data data/parquet \\
      --out data/parquet/2026/t2/encerramento_minuto
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

KEY = ["uf", "cd_mun", "zona", "secao"]
LOCAL = ["uf", "cd_mun", "zona", "local_votacao"]
SP_CAPITAL = "71072"


def share(a: float, b: float) -> float:
    """Share of 13 over 13 + 22, in percent."""
    return round(100.0 * a / (a + b), 2) if a + b else float("nan")


def deciles(df: pd.DataFrame, tcol: str, n: int = 10) -> pd.Series:
    """Group number 1..n with roughly equal section counts, by closing time."""
    rank = df[tcol].rank(method="first")
    return np.ceil(rank * n / len(df)).astype(int).clip(1, n)


def decile_table(df: pd.DataFrame, tcol: str, n: int = 10) -> list[dict]:
    """Per closing-time group: range, sections, share of 13 in both rounds."""
    d = df.assign(g=deciles(df, tcol, n))
    rows = []
    for g, x in d.groupby("g"):
        row = {
            "grupo": int(g),
            "inicio": str(x[tcol].min())[-8:],
            "fim": str(x[tcol].max())[-8:],
            "secoes": len(x),
            "pct13_t2": share(x.v13.sum(), x.v22.sum()),
        }
        if "v13_t1" in x:
            row["pct13_t1"] = share(x.v13_t1.sum(), x.v22_t1.sum())
            row["variacao"] = round(row["pct13_t2"] - row["pct13_t1"], 2)
        if "res_t2" in x:
            w = x.val_t2
            row["residuo_local_t2"] = round(float(np.average(x.res_t2, weights=w)), 2)
            row["residuo_local_var"] = round(float(np.average(x.res_d, weights=w)), 2)
        if "regiao" in x:
            # 2026 tables use "Nordeste", the 2022 table uses "nordeste".
            row["pct_nordeste"] = round(100.0 * (x.regiao.str.lower() == "nordeste").mean(), 1)
            row["aptos_medio"] = round(float(x.aptos.mean()), 1)
        rows.append(row)
    return rows


def load_2026(data: Path) -> pd.DataFrame:
    """Sections of the 2nd round with 1st round votes and polling place."""
    t = pd.read_parquet(data / "2026/t2/impacto/secoes_t1_t2.parquet")
    loc = pd.read_parquet(data / "2026/secoes_2026.parquet", columns=KEY + ["local_votacao", "status"])
    loc = loc[loc.status == "ok"].drop(columns="status")
    t = t.merge(loc, on=KEY, how="left")
    t["enc"] = pd.to_datetime(t.encerramento_bsb)
    t = t.rename(columns={"votos_13": "v13", "votos_22": "v22", "votos_13_t1": "v13_t1", "votos_22_t1": "v22_t1"})
    t = t[(t.v13 + t.v22) > 0].copy()
    t["val_t2"] = t.v13 + t.v22
    t["p2"] = 100.0 * t.v13 / t.val_t2
    val1 = t.v13_t1 + t.v22_t1
    t["p1"] = np.where(val1 > 0, 100.0 * t.v13_t1 / val1.where(val1 > 0, 1), np.nan)
    t["d"] = t.p2 - t.p1
    # Residual against the polling place mean (only places with 2+ sections).
    g = t.groupby(LOCAL, dropna=False)
    t["n_local"] = g.p2.transform("size")
    t["res_t2"] = t.p2 - g.p2.transform("mean")
    t["res_d"] = t.d - g.d.transform("mean")
    return t


def cut_1701(t: pd.DataFrame) -> dict:
    """Sections closed in the minute before 17:01:00 against the minute after,
    compared inside the same polling place."""
    m = t.enc.dt.hour * 60 + t.enc.dt.minute
    a = t[m == 17 * 60].assign(lado="antes")
    b = t[m == 17 * 60 + 1].assign(lado="depois")
    x = pd.concat([a, b])
    both = x.groupby(LOCAL).lado.transform("nunique") == 2
    x = x[both & x.d.notna()]
    per = x.groupby(LOCAL + ["lado"])[["p2", "d"]].mean().unstack("lado")
    diff_p2 = per["p2"]["depois"] - per["p2"]["antes"]
    diff_d = per["d"]["depois"] - per["d"]["antes"]
    rng = np.random.default_rng(2026)
    vals = diff_p2.to_numpy()
    boot = [rng.choice(vals, len(vals)).mean() for _ in range(2000)]
    return {
        "locais_com_os_dois_lados": int(len(per)),
        "secoes_antes": int((x.lado == "antes").sum()),
        "secoes_depois": int((x.lado == "depois").sum()),
        "pct13_t2_brasil_antes": share(a.v13.sum(), a.v22.sum()),
        "pct13_t2_brasil_depois": share(b.v13.sum(), b.v22.sum()),
        "dif_mesmo_local_pct13_t2": round(float(diff_p2.mean()), 3),
        "ic95_dif_mesmo_local_pct13_t2": [round(float(np.percentile(boot, q)), 3) for q in (2.5, 97.5)],
        "dif_mesmo_local_variacao_t1_t2": round(float(diff_d.mean()), 3),
    }


def slope_per_minute(t: pd.DataFrame, col: str) -> float:
    """Within polling place slope of a section measure on closing minute
    (sections closed until 17:10, where the claim says the effect builds up)."""
    x = t[(t.minutos_apos_17h_bsb <= 10) & t[col].notna()].copy()
    gm = x.groupby(LOCAL)
    xm = x.minutos_apos_17h_bsb - gm.minutos_apos_17h_bsb.transform("mean")
    ym = x[col] - gm[col].transform("mean")
    return round(float((xm * ym).sum() / (xm * xm).sum()), 4)


def load_2022(data: Path) -> pd.DataFrame:
    """2022 2nd round sections with closing time in Brasília and 13/22 votes."""
    s = pd.read_parquet(data / "secoes.parquet",
                        columns=["id", "turno", "uf", "municipio", "fuso_offset", "hora_encerramento", "regiao", "eleitores_aptos"])
    s = s[(s.turno == 2) & s.hora_encerramento.notna()]
    v = pd.read_parquet(data / "votos_t2.parquet")
    v = v[(v.codigo_cargo == 1) & v.codigo_candidato.isin([13, 22])]
    p = v.pivot_table(index="secao_id", columns="codigo_candidato", values="quantidade", aggfunc="sum").fillna(0)
    p.columns = ["v13", "v22"]
    s = s.merge(p, left_on="id", right_index=True)
    local = pd.to_datetime(s.hora_encerramento, format="%d/%m/%Y %H:%M:%S", errors="coerce")
    s["enc"] = local - pd.to_timedelta(s.fuso_offset, unit="h")
    s = s[s.enc.notna() & (s.enc.dt.date == pd.Timestamp("2022-10-30").date())]
    return s.rename(columns={"eleitores_aptos": "aptos"})


def md_table(rows: list[dict]) -> str:
    cols = list(rows[0])
    out = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    out += ["| " + " | ".join(str(r[c]) for c in cols) + " |" for r in rows]
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", type=Path, default=Path("data/parquet"))
    ap.add_argument("--out", type=Path, default=Path("data/parquet/2026/t2/encerramento_minuto"))
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)

    t = load_2026(a.data)
    sp = t[t.uf == "sp"]
    spc = sp[sp.cd_mun == SP_CAPITAL]
    multi = t[t.n_local >= 2]
    ate = t[t.enc < pd.Timestamp("2026-10-25 17:01:00")]
    dep = t[t.enc >= pd.Timestamp("2026-10-25 17:01:00")]

    r = {
        "secoes": len(t),
        "secoes_com_local": int(t.local_votacao.notna().sum()),
        "secoes_em_locais_com_2_ou_mais": len(multi),
        "ate_17h01": {"secoes": len(ate), "v13": int(ate.v13.sum()), "v22": int(ate.v22.sum()),
                      "pct13": share(ate.v13.sum(), ate.v22.sum()),
                      "pct13_mesmas_secoes_1t": share(ate.v13_t1.sum(), ate.v22_t1.sum())},
        "depois_17h01": {"secoes": len(dep), "v13": int(dep.v13.sum()), "v22": int(dep.v22.sum()),
                         "pct13": share(dep.v13.sum(), dep.v22.sum()),
                         "pct13_mesmas_secoes_1t": share(dep.v13_t1.sum(), dep.v22_t1.sum())},
        "brasil": decile_table(t, "enc"),
        "brasil_mesmo_local": decile_table(multi, "enc"),
        "sp_estado": decile_table(sp, "enc"),
        "sp_capital": decile_table(spc, "enc", 7),
        "corte_17h01_mesmo_local": cut_1701(multi),
        "inclinacao_por_minuto_mesmo_local": {
            "pct13_t2": slope_per_minute(multi, "p2"),
            "variacao_t1_t2": slope_per_minute(multi, "d"),
        },
    }
    t1 = t[t.encerramento_bsb_t1.notna()].assign(enc1=pd.to_datetime(t.encerramento_bsb_t1))
    r["primeiro_turno_por_horario_do_1t"] = [
        {k: v for k, v in row.items() if k in ("grupo", "inicio", "fim", "secoes", "pct13_t1")}
        for row in decile_table(t1, "enc1")
    ]
    s22 = load_2022(a.data)
    r["ano_2022"] = {
        "secoes": len(s22),
        "brasil": decile_table(s22, "enc"),
        "sp_estado": decile_table(s22[s22.uf == "sp"], "enc"),
    }

    (a.out / "resumo.json").write_text(json.dumps(r, ensure_ascii=False, indent=1))
    parts = []
    for name in ("brasil", "brasil_mesmo_local", "sp_estado", "sp_capital", "primeiro_turno_por_horario_do_1t"):
        parts += [f"## {name}", "", md_table(r[name]), ""]
    for name in ("brasil", "sp_estado"):
        parts += [f"## 2022 {name}", "", md_table(r["ano_2022"][name]), ""]
    (a.out / "tabelas.md").write_text("\n".join(parts))
    print(json.dumps({k: r[k] for k in ("secoes", "ate_17h01", "depois_17h01", "corte_17h01_mesmo_local",
                                        "inclinacao_por_minuto_mesmo_local")}, ensure_ascii=False, indent=1))
    print("\n".join(parts))


if __name__ == "__main__":
    main()
