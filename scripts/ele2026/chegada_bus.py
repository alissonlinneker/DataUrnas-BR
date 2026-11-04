"""Arrival order of the BUs at the tally and the 1st-to-2nd round swing.

Question: does the order and time at which the section reports (BUs) reached the
tally show a pattern that would point to vote injection or manipulation, in
particular around the moment the cumulative lead flipped to candidate 13?

Steps (all run on the processing server, never on the laptop):

1. ``export``: runs each block of ``chegada_bus.sql`` through ``ch.sh`` and writes
   one Parquet per block (2026 2nd round, 2026 1st round, 2022, municipalities).
2. ``analyze``: computes
   - the cumulative 13-minus-22 margin against real arrival time and the moment
     the result became mathematically settled (margin larger than the whole
     electorate of the sections still missing);
   - the main test: section swing (13 share in the 2nd round minus 13 share in
     the 1st round, 13 and 22 only) against arrival order, after removing
     municipality (or UF) fixed effects and 1st-round share bins; observed versus
     expected per arrival decile, with a permutation test that shuffles arrival
     only inside each municipality; 2022 as control;
   - arrival by region over time and a counterfactual cumulative curve (1st-round
     share plus the mean swing of the UF);
   - delay between BU emission (machine clock) and reception, and the swing of
     sections with long delays;
   - profile of the last 1% and 0.1% of sections to arrive.
3. ``placebo``: adds to ``resultado.json`` the same decile test run on the 2022
   swing of the same sections ordered by the 2026 arrival time, which calibrates
   how many "significant" deciles geography alone produces.
4. ``figures``: draws the SVGs in ``docs/assets/2026-chegada-*.svg`` from the
   small outputs (this step is light and can run anywhere).

2022 has no reception time in the project database: its order is the BU emission
time converted to Brasília time, which is a proxy for closing, not for arrival.

Usage on the server:
    uv run python chegada_bus.py export  --sql chegada_bus.sql --out /dev/shm/chegada
    uv run python chegada_bus.py analyze --data /dev/shm/chegada --out /dev/shm/chegada/out
    uv run python chegada_bus.py placebo --data /dev/shm/chegada --out /dev/shm/chegada/out
Locally:
    uv run python scripts/ele2026/chegada_bus.py figures --res data/parquet/2026/t2/chegada
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from multiprocessing import Pool
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from analisar_encerramento_t2 import fuso_utc  # noqa: E402

CH = os.path.expanduser("~/dataurnas-ch/app/scripts/ch/ch.sh")

REGIAO = {
    **dict.fromkeys(["ac", "am", "ap", "pa", "ro", "rr", "to"], "Norte"),
    **dict.fromkeys(["al", "ba", "ce", "ma", "pb", "pe", "pi", "rn", "se"], "Nordeste"),
    **dict.fromkeys(["df", "go", "ms", "mt"], "Centro-Oeste"),
    **dict.fromkeys(["es", "mg", "rj", "sp"], "Sudeste"),
    **dict.fromkeys(["pr", "rs", "sc"], "Sul"),
    "zz": "Exterior",
}
# Election day, used as the 17:00 (Brasília) origin of the time axis.
DIA = {"2026_t2": "2026-10-25", "2026_t1": "2026-10-04",
       "2022_t2": "2022-10-30", "2022_t1": "2022-10-02"}
KEY = ["uf", "cd_mun", "zona", "secao"]
N_PERM = 2000
SHARE_BINS = 50  # 2-point bins of the 1st-round 13 share


# ----------------------------------------------------------------------
# Export
# ----------------------------------------------------------------------
def export(sql_path: Path, out: Path) -> None:
    """Run each ``-- @name`` block of the SQL file and save ``<name>.parquet``."""
    out.mkdir(parents=True, exist_ok=True)
    blocos: dict[str, list[str]] = {}
    atual = None
    for linha in sql_path.read_text(encoding="utf-8").splitlines():
        if linha.startswith("-- @"):
            atual = linha[4:].strip()
            blocos[atual] = []
        elif atual:
            blocos[atual].append(linha)
    for nome, linhas in blocos.items():
        destino = out / f"{nome}.parquet"
        with open(destino, "wb") as f:
            subprocess.run([CH], input="\n".join(linhas).encode(), stdout=f, check=True)
        print(nome, destino.stat().st_size)


# ----------------------------------------------------------------------
# Loading
# ----------------------------------------------------------------------
def _brasilia(local: pd.Series, uf: pd.Series, cd_mun: pd.Series) -> pd.Series:
    """Machine local time to Brasília time (NaT abroad, whose zone is unknown)."""
    pares = pd.DataFrame({"uf": uf, "cd": cd_mun}).drop_duplicates()
    pares["off"] = [fuso_utc(u, c) for u, c in zip(pares.uf, pares.cd, strict=True)]
    off = pd.DataFrame({"uf": uf, "cd": cd_mun}).merge(pares, how="left")["off"].to_numpy()
    horas = (-3 - pd.to_numeric(off, errors="coerce")).astype(float)
    return pd.to_datetime(local, errors="coerce") + pd.to_timedelta(horas, unit="h")


def load(data: Path) -> dict[str, pd.DataFrame]:
    t2 = pd.read_parquet(data / "t2_2026.parquet")
    t2["rec"] = pd.to_datetime(t2["rec"], errors="coerce")
    t2["emi"] = _brasilia(t2["emi_local"], t2["uf"], t2["cd_mun"]).to_numpy()
    t1 = pd.read_parquet(data / "t1_2026.parquet")
    t1["rec"] = pd.to_datetime(t1["rec"], format="%d/%m/%Y %H:%M:%S", errors="coerce")
    t1["emi"] = _brasilia(t1["emi_local"], t1["uf"], t1["cd_mun"]).to_numpy()
    y = pd.read_parquet(data / "y2022.parquet")
    # 2022 has only the emission time; offset is local minus Brasília, in hours.
    y["rec"] = (pd.to_datetime(y["emissao"], format="%Y%m%dT%H%M%S", errors="coerce")
                - pd.to_timedelta(y["fuso_offset"].astype(float), unit="h"))
    y.loc[y["uf"] == "zz", "rec"] = pd.NaT
    y["emi"] = y["rec"]
    y["tipo_urna"] = np.where(y["is_reserva"], "reservaSecao", y["tipo_urna"])
    mun = pd.read_parquet(data / "municipios.parquet")
    out = {"2026_t2": t2, "2026_t1": t1,
           "2022_t2": y[y.turno == 2].drop(columns="turno"),
           "2022_t1": y[y.turno == 1].drop(columns="turno")}
    for k, df in out.items():
        df = df.copy()
        df["aptos"] = df["aptos"].fillna(0).astype(np.int64)
        df["v13"] = df["v13"].fillna(0).astype(np.int64)
        df["v22"] = df["v22"].fillna(0).astype(np.int64)
        df["regiao"] = df["uf"].map(REGIAO)
        df = df.merge(mun[["uf", "cd_mun", "capital"]], on=["uf", "cd_mun"], how="left")
        df["capital"] = df["capital"].fillna(False).astype(bool)
        out[k] = df
    return out


# ----------------------------------------------------------------------
# 1. Cumulative margin against time
# ----------------------------------------------------------------------
def curve(df: pd.DataFrame, chave: str) -> tuple[dict, pd.DataFrame]:
    """Cumulative 13-minus-22 margin in arrival order and the settling moment.

    Sections with no arrival time go to the end (they are counted in the
    electorate still missing until the very end).
    """
    d = df.sort_values(["rec", *KEY], na_position="last").reset_index(drop=True)
    diff = np.cumsum((d.v13 - d.v22).to_numpy())
    aptos = d.aptos.to_numpy()
    restante = aptos.sum() - np.cumsum(aptos)
    ok = np.abs(diff) > restante
    # first index from which the condition holds until the end
    falhas = np.nonzero(~ok)[0]
    i_def = int(falhas[-1] + 1) if len(falhas) else 0
    sinal = np.sign(diff)
    trocas = np.nonzero(sinal[1:] * sinal[:-1] < 0)[0]
    n = len(d)
    t0 = pd.Timestamp(DIA[chave] + " 17:00:00")
    minutos = ((d["rec"] - t0).dt.total_seconds() / 60).to_numpy()
    res = {
        "secoes": n, "secoes_com_horario": int(d["rec"].notna().sum()),
        "margem_final": int(diff[-1]), "aptos_total": int(aptos.sum()),
        "primeiro": str(d["rec"].iloc[0]), "ultimo": str(d["rec"].dropna().iloc[-1]),
        "trocas_de_lider": len(trocas),
        "ultima_troca": None if not len(trocas) else {
            "secao_n": int(trocas[-1] + 1), "hora": str(d["rec"].iloc[trocas[-1] + 1]),
            "pct_secoes": round(100 * (trocas[-1] + 1) / n, 2)},
        "definido": None if i_def >= n else {
            "secao_n": i_def + 1, "hora": str(d["rec"].iloc[i_def]),
            "pct_secoes": round(100 * (i_def + 1) / n, 2),
            "margem": int(diff[i_def]), "aptos_restantes": int(restante[i_def])},
    }
    passo = max(n // 3000, 1)
    idx = np.unique(np.r_[np.arange(0, n, passo), n - 1, i_def if i_def < n else n - 1,
                          trocas + 1 if len(trocas) else []].astype(int))
    pts = pd.DataFrame({"eleicao": chave, "i": idx, "pct_secoes": 100 * (idx + 1) / n,
                        "minutos": minutos[idx], "margem": diff[idx],
                        "aptos_restantes": restante[idx]})
    return res, pts


# ----------------------------------------------------------------------
# 2. Swing against arrival order
# ----------------------------------------------------------------------
def paired(t1: pd.DataFrame, t2: pd.DataFrame, exterior: bool) -> pd.DataFrame:
    """Sections present in both rounds with valid 13+22 votes in both."""
    a = t1[[*KEY, "v13", "v22"]].rename(columns={"v13": "a13", "v22": "a22"})
    p = t2.merge(a, on=KEY, how="inner")
    p = p[(p.a13 + p.a22 > 0) & (p.v13 + p.v22 > 0) & p.rec.notna()]
    if not exterior:
        p = p[p.uf != "zz"]
    p = p.sort_values(["rec", *KEY]).reset_index(drop=True)
    p["s1"] = p.a13 / (p.a13 + p.a22)
    p["s2"] = p.v13 / (p.v13 + p.v22)
    p["swing"] = p.s2 - p.s1
    p["w"] = (p.v13 + p.v22).astype(float)
    p["u"] = (np.arange(len(p)) + 0.5) / len(p)  # arrival quantile
    p["decil"] = np.minimum((p.u * 10).astype(int), 9)
    p["mun"] = pd.factorize(p.uf + p.cd_mun)[0]
    p["ufc"] = pd.factorize(p.uf)[0]
    p["zon"] = pd.factorize(p.uf + p.cd_mun + p.zona)[0]
    p["bin1"] = np.minimum((p.s1 * SHARE_BINS).astype(int), SHARE_BINS - 1)
    return p


def residualize(y: np.ndarray, w: np.ndarray, groups: list[np.ndarray]) -> np.ndarray:
    """Weighted residual of ``y`` after additive fixed effects (alternating projections)."""
    r = y.astype(float).copy()
    for _ in range(200):
        maior = 0.0
        for g in groups:
            sw = np.bincount(g, w)
            m = np.bincount(g, w * r) / np.where(sw > 0, sw, 1)
            r -= m[g]
            maior = max(maior, float(np.abs(m).max()))
        if maior < 1e-12:
            break
    return r


_G: dict[str, np.ndarray] = {}


def _perm_worker(args: tuple[int, int]) -> np.ndarray:
    """Shuffle labels inside each municipality and return per-label weighted means."""
    seed, n = args
    g = _G
    rng = np.random.default_rng(seed)
    nb = int(g["nb"][0])
    out = np.empty((n, nb + 1))
    for k in range(n):
        ordem = np.lexsort((rng.random(len(g["mun_sorted"])), g["mun_sorted"]))
        lab = np.empty_like(g["lab"])
        lab[g["idx_sorted"]] = g["lab"][g["idx_sorted"]][ordem]
        u = np.empty_like(g["u"])
        u[g["idx_sorted"]] = g["u"][g["idx_sorted"]][ordem]
        sw = np.bincount(lab, g["w"], nb)
        out[k, :nb] = np.bincount(lab, g["w"] * g["r"], nb) / np.where(sw > 0, sw, 1)
        out[k, nb] = _slope(u, g["r"], g["w"])
    return out


def _slope(u: np.ndarray, r: np.ndarray, w: np.ndarray) -> float:
    """Weighted least-squares slope of r on u (pp of swing per whole arrival span)."""
    um = np.average(u, weights=w)
    return float(np.sum(w * (u - um) * r) / np.sum(w * (u - um) ** 2))


def perm_test(p: pd.DataFrame, r: np.ndarray, lab: np.ndarray, nb: int, grupo: str) -> dict:
    """Observed per-label residual means and their within-group permutation null.

    Labels (and the arrival quantile used by the trend) are shuffled only among
    sections of the same group, the same group used as fixed effect, so the null
    keeps the geography fixed and only breaks the link with arrival order.
    The worker pool is created after filling ``_G`` so the forked workers inherit
    the arrays without pickling them.
    """
    mun = p[grupo].to_numpy()
    idx_sorted = np.argsort(mun, kind="stable")
    w = p.w.to_numpy()
    _G.clear()
    _G.update(mun_sorted=mun[idx_sorted], idx_sorted=idx_sorted, lab=lab.astype(np.int64),
              u=p.u.to_numpy(), w=w, r=r, nb=np.array([nb]))
    sw = np.bincount(lab, w, nb)
    obs = np.bincount(lab, w * r, nb) / np.where(sw > 0, sw, 1)
    obs_slope = _slope(p.u.to_numpy(), r, w)
    blocos = [(s, N_PERM // 50) for s in range(50)]
    with Pool(50) as pool:
        null = np.vstack(pool.map(_perm_worker, blocos))
    pv = (1 + (np.abs(null[:, :nb]) >= np.abs(obs)).sum(0)) / (1 + len(null))
    return {
        "obs": obs, "sw": sw, "lo": np.percentile(null[:, :nb], 2.5, 0),
        "hi": np.percentile(null[:, :nb], 97.5, 0), "p": pv,
        "slope": obs_slope,
        "slope_p": float((1 + (np.abs(null[:, nb]) >= abs(obs_slope)).sum()) / (1 + len(null))),
        "slope_lo": float(np.percentile(null[:, nb], 2.5)),
        "slope_hi": float(np.percentile(null[:, nb], 97.5)),
    }


def swing_by_label(p: pd.DataFrame, lab: np.ndarray, nomes: list[str],
                   modelo: str = "mun") -> tuple[list[dict], dict]:
    """Observed and expected mean swing per label, with the permutation interval.

    ``modelo`` picks the geographic fixed effect (and permutation group):
    ``mun`` municipality, ``uf`` state, ``zona`` electoral zone.
    """
    grupo = {"mun": "mun", "uf": "ufc", "zona": "zon"}[modelo]
    fe = [p[grupo].to_numpy(), p.bin1.to_numpy()]
    y = p.swing.to_numpy()
    w = p.w.to_numpy()
    r = residualize(y, w, fe)
    t = perm_test(p, r, lab, len(nomes), grupo)
    linhas = []
    for b, nome in enumerate(nomes):
        m = lab == b
        if not m.any():
            continue
        wb = w[m]
        linhas.append({
            "faixa": nome, "secoes": int(m.sum()), "votos_validos": int(wb.sum()),
            "inicio": str(p.rec[m].min()), "fim": str(p.rec[m].max()),
            "swing_obs_pp": round(100 * float(np.average(y[m], weights=wb)), 3),
            "swing_esperado_pp": round(100 * float(np.average(y[m] - r[m], weights=wb)), 3),
            "desvio_pp": round(100 * float(t["obs"][b]), 3),
            "ic95_perm_pp": [round(100 * float(t["lo"][b]), 3), round(100 * float(t["hi"][b]), 3)],
            "p_perm": round(float(t["p"][b]), 4),
            # net votes moved toward 13 relative to the model; margin moves twice that
            "votos_liquidos_13": int(round(float(t["obs"][b]) * float(t["sw"][b]))),
            "efeito_na_margem": int(round(2 * float(t["obs"][b]) * float(t["sw"][b]))),
        })
    return linhas, {"inclinacao_pp_por_periodo_inteiro": round(100 * t["slope"], 4),
                    "ic95_perm_pp": [round(100 * t["slope_lo"], 4), round(100 * t["slope_hi"], 4)],
                    "p_perm": round(t["slope_p"], 4)}


def swing_tests(p: pd.DataFrame) -> dict:
    nomes = [f"D{i + 1}" for i in range(10)]
    dec = p.decil.to_numpy()
    out = {"secoes": len(p), "votos_validos": int(p.w.sum()),
           "swing_medio_pp": round(100 * float(np.average(p.swing, weights=p.w)), 3)}
    for modelo in ("mun", "uf", "zona"):
        linhas, tend = swing_by_label(p, dec, nomes, modelo)
        out[f"decis_{modelo}"] = linhas
        out[f"tendencia_{modelo}"] = tend
    # tail of the arrival order: last 1% and last 0.1%
    for nome, corte in (("ultimos_1pct", 0.99), ("ultimos_0_1pct", 0.999)):
        lab = (p.u.to_numpy() >= corte).astype(np.int64)
        for modelo in ("mun", "zona"):
            linhas, _ = swing_by_label(p, lab, ["resto", nome], modelo)
            out[f"{nome}_{modelo}"] = linhas[-1]
    return out


def placebo(dados: dict[str, pd.DataFrame]) -> dict:
    """Calibrate the arrival test with an outcome 2026 could not have touched.

    The 2022 swing of each section (same uf, municipality, zone and section number)
    is ordered by the 2026 2nd-round arrival time and run through the same decile
    test. Any "significant" decile there comes from geography and from sections
    of the same polling place arriving together, not from 2026. The real 2026
    swing is tested on exactly the same sections for comparison.
    """
    rec26 = dados["2026_t2"][[*KEY, "rec"]]
    t2p = dados["2022_t2"].drop(columns="rec").merge(rec26, on=KEY, how="inner")
    p22 = paired(dados["2022_t1"], t2p, exterior=False)
    p26 = paired(dados["2026_t1"], dados["2026_t2"], exterior=False)
    comuns = p22[KEY].merge(p26[KEY], on=KEY)
    out = {"secoes_comuns": len(comuns)}
    nomes = [f"D{i + 1}" for i in range(10)]
    for nome, p in (("swing_2022_na_ordem_de_2026", p22), ("swing_2026_mesmas_secoes", p26)):
        p = paired_subset(p, comuns)
        for modelo in ("mun", "zona"):
            linhas, tend = swing_by_label(p, p.decil.to_numpy(), nomes, modelo)
            out[f"{nome}_{modelo}"] = {
                "decis": linhas, "tendencia": tend,
                "decis_p_menor_0_05": sum(ln["p_perm"] < 0.05 for ln in linhas),
                "soma_abs_efeito_na_margem": sum(abs(ln["efeito_na_margem"]) for ln in linhas)}
    return out


def paired_subset(p: pd.DataFrame, comuns: pd.DataFrame) -> pd.DataFrame:
    """Restrict a paired frame to ``comuns`` and recompute order-dependent columns."""
    q = p.merge(comuns, on=KEY).sort_values(["rec", *KEY]).reset_index(drop=True)
    q["u"] = (np.arange(len(q)) + 0.5) / len(q)
    q["decil"] = np.minimum((q.u * 10).astype(int), 9)
    for col, chave in (("mun", q.uf + q.cd_mun), ("ufc", q.uf), ("zon", q.uf + q.cd_mun + q.zona)):
        q[col] = pd.factorize(chave)[0]
    return q


def analyze_placebo(data: Path, out: Path) -> None:
    """Add the placebo block to an existing resultado.json."""
    arq = out / "resultado.json"
    res = json.loads(arq.read_text(encoding="utf-8"))
    res["placebo"] = placebo(load(data))
    arq.write_text(json.dumps(res, ensure_ascii=False, indent=1, default=_json_safe),
                   encoding="utf-8")
    print("ok placebo", res["placebo"]["secoes_comuns"])


# ----------------------------------------------------------------------
# 3. Regions and counterfactual curve
# ----------------------------------------------------------------------
def regions(t2: pd.DataFrame, chave: str) -> pd.DataFrame:
    d = t2.dropna(subset=["rec"]).copy()
    t0 = pd.Timestamp(DIA[chave] + " 17:00:00")
    d["faixa"] = ((d.rec - t0).dt.total_seconds() // 300 * 5).astype(int)
    g = d.groupby(["regiao", "faixa"]).size().rename("secoes").reset_index()
    g["acum"] = g.groupby("regiao").secoes.cumsum()
    g["pct"] = 100 * g.acum / g.groupby("regiao").secoes.transform("sum")
    g["eleicao"] = chave
    return g


def region_summary(t2: pd.DataFrame) -> list[dict]:
    d = t2.dropna(subset=["rec"])
    n = len(d)
    ordem = d.rec.rank(method="first") / n
    linhas = []
    for reg, g in d.assign(u=ordem).groupby("regiao"):
        q = g.rec.quantile([0.1, 0.5, 0.9])
        linhas.append({"regiao": reg, "secoes": len(g),
                       "pct_13_validos": round(100 * g.v13.sum() / max((g.v13 + g.v22).sum(), 1), 2),
                       "margem": int((g.v13 - g.v22).sum()),
                       "chegada_p10": str(q.iloc[0]), "chegada_mediana": str(q.iloc[1]),
                       "chegada_p90": str(q.iloc[2]),
                       "posicao_media_pct": round(100 * float(g.u.mean()), 1)})
    return linhas


def counterfactual(t1: pd.DataFrame, t2: pd.DataFrame, chave: str) -> tuple[dict, pd.DataFrame]:
    """Cumulative margin if each section had its 1st-round share plus its UF mean swing.

    Sections with no usable 1st-round pair keep their real margin.
    """
    p = paired(t1, t2, exterior=True)
    uf_sw = p.groupby("uf").apply(lambda g: np.average(g.swing, weights=g.w),
                                  include_groups=False)
    d = t2.sort_values(["rec", *KEY], na_position="last").reset_index(drop=True)
    d = d.merge(p[[*KEY, "s1"]], on=KEY, how="left")
    s_hat = np.clip(d.s1 + d.uf.map(uf_sw), 0, 1)
    real = (d.v13 - d.v22).to_numpy(float)
    cf = np.where(s_hat.notna(), (2 * s_hat - 1) * (d.v13 + d.v22), real)
    cr, cc = np.cumsum(real), np.cumsum(cf)
    n = len(d)
    t0 = pd.Timestamp(DIA[chave] + " 17:00:00")
    minutos = ((d.rec - t0).dt.total_seconds() / 60).to_numpy()

    def troca(c: np.ndarray) -> dict | None:
        s = np.sign(c)
        k = np.nonzero(s[1:] * s[:-1] < 0)[0]
        if not len(k):
            return None
        return {"secao_n": int(k[-1] + 1), "hora": str(d.rec.iloc[k[-1] + 1]),
                "pct_secoes": round(100 * (k[-1] + 1) / n, 2)}

    gap = cr - cc
    res = {"secoes_com_par": int(s_hat.notna().sum()), "secoes": n,
           "margem_real_final": int(cr[-1]), "margem_contrafactual_final": int(round(cc[-1])),
           "maior_diferenca_real_menos_cf": int(round(gap[np.argmax(np.abs(gap))])),
           "maior_diferenca_pct_secoes": round(100 * (int(np.argmax(np.abs(gap))) + 1) / n, 2),
           "ultima_troca_real": troca(cr), "ultima_troca_contrafactual": troca(cc),
           "swing_uf_pp": {k: round(100 * float(v), 2) for k, v in uf_sw.items()}}
    idx = np.unique(np.r_[np.arange(0, n, max(n // 2000, 1)), n - 1])
    pts = pd.DataFrame({"eleicao": chave, "pct_secoes": 100 * (idx + 1) / n,
                        "minutos": minutos[idx], "real": cr[idx], "contrafactual": cc[idx]})
    return res, pts


# ----------------------------------------------------------------------
# 4. Emission-to-reception delay
# ----------------------------------------------------------------------
# In the 2026 2nd round voting was extended to 19:00 and the tally paused from about
# 17:06 to 19:03, so most delays fall between 2 and 4 hours; the bands follow that.
FAIXAS_ATRASO = [(-1e9, 60, "até 1 h"), (60, 120, "1 a 2 h"), (120, 150, "2 a 2,5 h"),
                 (150, 180, "2,5 a 3 h"), (180, 210, "3 a 3,5 h"), (210, 240, "3,5 a 4 h"),
                 (240, 1e9, "mais de 4 h")]


def delay(df: pd.DataFrame) -> pd.Series:
    return (df.rec - df.emi).dt.total_seconds() / 60


def delay_summary(df: pd.DataFrame) -> dict:
    a = delay(df).dropna()
    hist = np.histogram(np.clip(a, -5, 360), bins=np.arange(-5, 366, 5))
    return {"secoes": len(a), "negativos": int((a < 0).sum()),
            "quantis_min": {str(q): round(float(a.quantile(q)), 1)
                            for q in (0.01, 0.1, 0.25, 0.5, 0.75, 0.9, 0.99, 0.999)},
            "max_min": round(float(a.max()), 1),
            "faixas": {n: int(((a >= lo) & (a < hi)).sum()) for lo, hi, n in FAIXAS_ATRASO},
            "hist_5min": {"inicio": hist[1][:-1].tolist(), "secoes": hist[0].tolist()}}


def delay_swing(p: pd.DataFrame, modelo: str) -> list[dict]:
    a = delay(p).to_numpy()
    q = p[~np.isnan(a)].reset_index(drop=True)
    a = a[~np.isnan(a)]
    lab = np.zeros(len(q), np.int64)
    for b, (lo, hi, _) in enumerate(FAIXAS_ATRASO):
        lab[(a >= lo) & (a < hi)] = b
    linhas, _ = swing_by_label(q, lab, [n for _, _, n in FAIXAS_ATRASO], modelo)
    return linhas


# ----------------------------------------------------------------------
# 5. Last sections to arrive
# ----------------------------------------------------------------------
def tail_profile(df: pd.DataFrame, frac: float) -> dict:
    d = df.dropna(subset=["rec"]).sort_values(["rec", *KEY]).reset_index(drop=True)
    k = max(int(round(len(d) * frac)), 1)
    t = d.iloc[-k:]
    margem_total = int((d.v13 - d.v22).sum())
    margem = int((t.v13 - t.v22).sum())
    a = delay(t)
    tipos = t.tipo_urna.fillna("?").value_counts()
    return {
        "secoes": k, "desde": str(t.rec.iloc[0]), "ate": str(t.rec.iloc[-1]),
        "ufs": {u: int(c) for u, c in t.uf.value_counts().head(8).items()},
        "regioes": {u: int(c) for u, c in t.regiao.value_counts().items()},
        "pct_exterior": round(100 * float((t.uf == "zz").mean()), 2),
        "pct_capital": round(100 * float(t.capital.mean()), 2),
        "pct_capital_geral": round(100 * float(d.capital.mean()), 2),
        "tipos_urna": {str(u): int(c) for u, c in tipos.items()},
        "tipos_urna_geral_pct": {str(u): round(100 * c / len(d), 3)
                                 for u, c in d.tipo_urna.fillna("?").value_counts().items()},
        "atraso_mediano_min": None if a.isna().all() else round(float(a.median()), 1),
        "aptos": int(t.aptos.sum()), "votos_13": int(t.v13.sum()), "votos_22": int(t.v22.sum()),
        "pct_13_validos": round(100 * t.v13.sum() / max((t.v13 + t.v22).sum(), 1), 2),
        "margem": margem, "margem_total": margem_total,
        "pct_da_margem": round(100 * margem / margem_total, 3),
    }


# ----------------------------------------------------------------------
# Driver
# ----------------------------------------------------------------------
def _json_safe(o):
    if isinstance(o, np.integer | np.floating):
        return o.item()
    return str(o)


def analyze(data: Path, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    dados = load(data)
    res: dict = {"curvas": {}, "swing": {}, "regioes": {}, "contrafactual": {},
                 "atraso": {}, "atraso_swing": {}, "cauda": {}}
    pontos, regs, cfs = [], [], []
    for chave, df in dados.items():
        r, pts = curve(df, chave)
        res["curvas"][chave] = r
        pontos.append(pts)
        regs.append(regions(df, chave))
        res["regioes"][chave] = region_summary(df)
        res["cauda"][chave] = {"1pct": tail_profile(df, 0.01), "0_1pct": tail_profile(df, 0.001)}
        print("curve", chave, r["definido"], flush=True)
    for ano in ("2026", "2022"):
        t1, t2 = dados[f"{ano}_t1"], dados[f"{ano}_t2"]
        p = paired(t1, t2, exterior=(ano == "2026"))
        res["swing"][ano] = swing_tests(p)
        print("swing", ano, res["swing"][ano]["tendencia_mun"], flush=True)
        r, pts = counterfactual(t1, t2, f"{ano}_t2")
        res["contrafactual"][ano] = r
        cfs.append(pts)
    for chave in ("2026_t2", "2026_t1"):
        res["atraso"][chave] = delay_summary(dados[chave])
    p = paired(dados["2026_t1"], dados["2026_t2"], exterior=False)
    res["atraso_swing"]["2026_t2"] = delay_swing(p, "mun")
    res["atraso_swing"]["2026_t2_zona"] = delay_swing(p, "zona")
    pd.concat(pontos).to_parquet(out / "curvas.parquet", index=False)
    pd.concat(regs).to_parquet(out / "regioes.parquet", index=False)
    pd.concat(cfs).to_parquet(out / "contrafactual.parquet", index=False)
    (out / "resultado.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=1, default=_json_safe), encoding="utf-8")
    print("ok", out)


# ----------------------------------------------------------------------
# Figures (SVG written by hand, same visual identity as scripts/docs/gerar_ilustracoes.py)
# ----------------------------------------------------------------------
def _primitives():
    """Import the drawing helpers lazily: the server steps do not need them."""
    sys.path.insert(0, str(HERE.parent / "docs"))
    import gerar_ilustracoes as gi

    return gi


def _hora(minutos: float) -> str:
    """Minutes after 17:00 to an 'HHhMM' label."""
    t = 17 * 60 + int(round(minutos))
    return f"{t // 60}h{t % 60:02d}" if t % 60 else f"{t // 60}h"


def _eixos(gi, corpo: list[str], caixa: tuple[float, float, float, float],
           xlim: tuple[float, float], ylim: tuple[float, float],
           xticks: list[tuple[float, str]], yticks: list[tuple[float, str]],
           xlabel: str = "", ylabel: str = ""):
    """Grid, ticks and labels; returns the data-to-pixel mapping functions."""
    x0, y0, w, h = caixa

    def px(x: float) -> float:
        return x0 + (x - xlim[0]) / (xlim[1] - xlim[0]) * w

    def py(y: float) -> float:
        return y0 + h - (y - ylim[0]) / (ylim[1] - ylim[0]) * h

    for v, rot in yticks:
        corpo.append(f'<line x1="{x0:.1f}" y1="{py(v):.1f}" x2="{x0 + w:.1f}" y2="{py(v):.1f}" '
                     f'stroke="{gi.GRID}" stroke-width="{1.6 if v == 0 else 1}"/>')
        corpo.append(gi.text(x0 - 8, py(v) + 4, rot, size=12, fill=gi.MUTED, anchor="end"))
    for v, rot in xticks:
        corpo.append(f'<line x1="{px(v):.1f}" y1="{y0 + h:.1f}" x2="{px(v):.1f}" y2="{y0 + h + 5:.1f}" '
                     f'stroke="{gi.MUTED}" stroke-width="1"/>')
        corpo.append(gi.text(px(v), y0 + h + 20, rot, size=12, fill=gi.MUTED, anchor="middle"))
    corpo.append(f'<line x1="{x0:.1f}" y1="{y0 + h:.1f}" x2="{x0 + w:.1f}" y2="{y0 + h:.1f}" '
                 f'stroke="{gi.MUTED}" stroke-width="1"/>')
    if xlabel:
        corpo.append(gi.text(x0 + w / 2, y0 + h + 40, xlabel, size=12.5, fill=gi.MUTED,
                             anchor="middle"))
    if ylabel:
        corpo.append(gi.text(x0, y0 - 12, ylabel, size=12.5, fill=gi.MUTED))
    return px, py


def _linha(xs, ys, px, py, cor: str, largura: float = 2.2, tracejado: str = "") -> str:
    pts = " ".join(f"{px(x):.1f},{py(y):.1f}" for x, y in zip(xs, ys, strict=True))
    dash = f' stroke-dasharray="{tracejado}"' if tracejado else ""
    return (f'<polyline points="{pts}" fill="none" stroke="{cor}" stroke-width="{largura}" '
            f'stroke-linejoin="round"{dash}/>')


def _legenda(gi, corpo: list[str], x: float, y: float, itens: list[tuple[str, str, str]]) -> None:
    for cor, rot, dash in itens:
        d = f' stroke-dasharray="{dash}"' if dash else ""
        corpo.append(f'<line x1="{x:.1f}" y1="{y - 4:.1f}" x2="{x + 26:.1f}" y2="{y - 4:.1f}" '
                     f'stroke="{cor}" stroke-width="3"{d}/>')
        corpo.append(gi.text(x + 32, y, rot, size=12.5))
        x += 46 + gi.largura_texto(rot, 12.5)


def _mi(v: float) -> str:
    """Millions with sign, using the typographic minus sign."""
    return (f"{v / 1e6:+.0f} mi" if v else "0").replace("-", "−")


def fig_curva(gi, res: dict, curvas: pd.DataFrame) -> str:
    W, H = 1000, 660
    corpo: list[str] = []
    xlim = (-20, 400)
    xt = [(m, _hora(m)) for m in range(0, 400, 60)]
    series = [("2026_t2", gi.BLUE, "", "2026, 2º turno (recebimento)"),
              ("2026_t1", gi.ORANGE, "", "2026, 1º turno (recebimento)"),
              ("2022_t2", gi.MUTED, "6 4", "2022, 2º turno (emissão do BU)")]
    yt = [(v * 1e6, _mi(v * 1e6)) for v in range(-6, 7, 2)]
    # 2nd round 2026: tally paused while voting was extended (no reception 17:09 to 19:03)
    for y0, h in ((150, 240), (450, 110)):
        x1 = 90 + (9 - xlim[0]) / (xlim[1] - xlim[0]) * 860
        x2 = 90 + (123 - xlim[0]) / (xlim[1] - xlim[0]) * 860
        corpo.append(gi.rect(x1, y0, x2 - x1, h, gi.SOFT))
    corpo.append(gi.text(90 + (66 - xlim[0]) / (xlim[1] - xlim[0]) * 860, 168,
                         "2º turno de 2026: pausa", size=11.5, fill=gi.MUTED, anchor="middle"))
    corpo.append(gi.text(90 + (66 - xlim[0]) / (xlim[1] - xlim[0]) * 860, 183,
                         "(votação prorrogada até 19h)", size=11.5, fill=gi.MUTED, anchor="middle"))
    px, py = _eixos(gi, corpo, (90, 150, 860, 240), xlim, (-6.5e6, 6.5e6), xt, yt,
                    ylabel="Diferença acumulada: votos do 13 menos votos do 22")
    for chave, cor, dash, _ in series:
        c = curvas[(curvas.eleicao == chave) & curvas.minutos.between(*xlim)]
        corpo.append(_linha(c.minutos, c.margem, px, py, cor, tracejado=dash))
        d = res["curvas"][chave]["definido"]
        if d:
            m = (pd.Timestamp(d["hora"]) - pd.Timestamp(DIA[chave] + " 17:00")).total_seconds() / 60
            if xlim[0] <= m <= xlim[1]:
                corpo.append(f'<circle cx="{px(m):.1f}" cy="{py(d["margem"]):.1f}" r="5.5" '
                             f'fill="{gi.CARD}" stroke="{cor}" stroke-width="2.5"/>')
    _legenda(gi, corpo, 90, 100, [(c, r, d) for _, c, d, r in series])
    px2, py2 = _eixos(gi, corpo, (90, 450, 860, 110), xlim, (0, 100), xt,
                      [(v, f"{v}%") for v in (0, 50, 100)],
                      xlabel="Horário de Brasília no dia da eleição",
                      ylabel="Seções já recebidas")
    for chave, cor, dash, _ in series:
        c = curvas[(curvas.eleicao == chave) & curvas.minutos.between(*xlim)]
        corpo.append(_linha(c.minutos, c.pct_secoes, px2, py2, cor, tracejado=dash))
    d2 = res["curvas"]["2026_t2"]["definido"]
    titulo = "Ordem de chegada dos BUs e a diferença acumulada"
    subt = (f"Círculo: diferença maior que todo o eleitorado ainda não recebido (2º turno de 2026: "
            f"{d2['hora'][11:16].replace(':', 'h')}, com {gi.fmt_num(d2['pct_secoes'], 1)}% das seções)")
    desc = ("Linhas da diferença acumulada entre os votos do 13 e do 22 conforme os boletins chegam, "
            "no 1º e 2º turno de 2026 e no 2º turno de 2022, e painel com a porcentagem de seções recebidas.")
    return gi.documento(W, H, titulo, desc, corpo, subt,
                        "Fonte: TSE, BUs e aux.json de 2026; BUs de 2022 (compilação DataUrnas-BR)")


def _painel_faixas(gi, corpo: list[str], caixa, linhas_por_ano: list[tuple[str, str, list[dict]]],
                   ymax: float, rotulos: list[str]) -> None:
    """Observed deviation (dot) and permutation 95% band (bar) per arrival band."""
    x0, y0, w, h = caixa
    passo = next(s for s in (0.02, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0) if ymax / s <= 4)
    casas = 2 if passo < 0.1 else 1
    ymax = float(np.ceil(ymax / passo - 1e-9) * passo)
    yt = [(v, f"{v:+.{casas}f}".replace(".", ",").replace("-", "−") if abs(v) > 1e-9 else "0")
          for v in np.arange(-ymax, ymax + 1e-9, passo)]
    n = len(rotulos)
    px, py = _eixos(gi, corpo, caixa, (0, n), (-ymax, ymax),
                    [(i + 0.5, r) for i, r in enumerate(rotulos)], yt)
    k = len(linhas_por_ano)
    for j, (_, cor, linhas) in enumerate(linhas_por_ano):
        for i, ln in enumerate(linhas):
            xc = i + 0.5 + (j - (k - 1) / 2) * 0.26
            lo, hi = ln["ic95_perm_pp"]
            corpo.append(gi.rect(px(xc) - 7, py(min(hi, ymax)), 14,
                                 py(max(lo, -ymax)) - py(min(hi, ymax)), gi.SOFT, rx=3,
                                 extra=f' stroke="{gi.CARD_STROKE}"'))
            v = max(min(ln["desvio_pp"], ymax), -ymax)
            corpo.append(f'<circle cx="{px(xc):.1f}" cy="{py(v):.1f}" r="5" fill="{cor}"/>')


def fig_swing(gi, res: dict) -> str:
    W, H = 1000, 560
    corpo: list[str] = []
    a26 = res["swing"]["2026"]["decis_mun"]
    a22 = res["swing"]["2022"]["decis_mun"]
    plac = res["placebo"]["swing_2022_na_ordem_de_2026_mun"]["decis"]
    vals = [abs(x) for ln in a26 + a22 + plac for x in (*ln["ic95_perm_pp"], ln["desvio_pp"])]
    ymax = max(vals) * 1.15
    _painel_faixas(gi, corpo, (100, 160, 850, 270),
                   [("2026", gi.BLUE, a26), ("placebo", gi.MUTED, plac), ("2022", gi.ORANGE, a22)],
                   ymax, [f"{i}º" for i in range(1, 11)])
    corpo.append(gi.text(525, 470, "Décimo da ordem de chegada (1º = primeiros 10% das seções a chegar)",
                         size=12.5, fill=gi.MUTED, anchor="middle"))
    corpo.append(gi.text(100, 146, "Swing observado menos esperado (pontos percentuais)", size=12.5,
                         fill=gi.MUTED))
    _legenda(gi, corpo, 100, 100, [(gi.BLUE, "2026", ""),
                                   (gi.MUTED, "placebo: swing de 2022 na ordem de chegada de 2026", ""),
                                   (gi.ORANGE, "2022 na ordem de emissão", "")])
    corpo.append(gi.rect(100, 112, 14, 14, gi.SOFT, rx=3, extra=f' stroke="{gi.CARD_STROKE}"'))
    corpo.append(gi.text(122, 124, "95% do acaso, supondo seções independentes (2.000 permutações "
                         "dentro do município)", size=12.5))
    titulo = "Swing do 1º para o 2º turno por ordem de chegada"
    subt = ("Desvio do swing médio em cada décimo da chegada, depois de controlar município "
            "e fatia do 13 no 1º turno")
    desc = ("Para cada décimo da ordem de chegada, o desvio entre o swing observado e o esperado por um "
            "modelo sem horário, em 2026 e 2022, com a faixa de 95% obtida embaralhando a ordem dentro do município.")
    return gi.documento(W, H, titulo, desc, corpo, subt,
                        "Fonte: TSE, BUs dos dois turnos de 2026 e de 2022 (compilação DataUrnas-BR)")


def fig_regioes(gi, res: dict, regs: pd.DataFrame) -> str:
    W, H = 1000, 560
    corpo: list[str] = []
    xlim = (-20, 400)
    cores = {"Sul": gi.GREEN, "Sudeste": gi.BLUE, "Centro-Oeste": gi.LIGHT_BLUE,
             "Norte": gi.NAVY, "Nordeste": gi.ORANGE, "Exterior": "#CC79A7"}
    px, py = _eixos(gi, corpo, (90, 160, 860, 270), xlim, (0, 100),
                    [(m, _hora(m)) for m in range(0, 400, 60)],
                    [(v, f"{v}%") for v in range(0, 101, 25)],
                    xlabel="Horário de Brasília, 25/10/2026",
                    ylabel="Seções da região já recebidas")
    r = regs[regs.eleicao == "2026_t2"]
    for reg, cor in cores.items():
        g = r[r.regiao == reg].sort_values("faixa")
        xs = np.r_[g.faixa.to_numpy(float) + 5]
        ys = g.pct.to_numpy()
        ok = (xs >= xlim[0]) & (xs <= xlim[1])
        corpo.append(_linha(xs[ok], ys[ok], px, py, cor))
    resumo = {x["regiao"]: x for x in res["regioes"]["2026_t2"]}
    itens = []
    for reg, cor in cores.items():
        z = resumo[reg]
        itens.append((cor, f"{reg} ({gi.fmt_num(z['pct_13_validos'], 1)}% no 13)", ""))
    _legenda(gi, corpo, 90, 102, itens[:3])
    _legenda(gi, corpo, 90, 126, itens[3:])
    titulo = "Quando cada região chegou: 2º turno de 2026"
    subt = "Seções de cada região com BU recebido, a cada 5 minutos; entre parênteses, a fatia do 13 nos válidos"
    desc = "Curvas de chegada acumulada por região; mostram a ordem geográfica em que os boletins foram recebidos."
    return gi.documento(W, H, titulo, desc, corpo, subt,
                        "Fonte: TSE, aux.json e BUs do 2º turno de 2026 (coleta DataUrnas-BR)")


def fig_contrafactual(gi, res: dict, cf: pd.DataFrame) -> str:
    W, H = 1000, 540
    corpo: list[str] = []
    c = cf[cf.eleicao == "2026_t2"]
    lo = float(min(c.real.min(), c.contrafactual.min()))
    hi = float(max(c.real.max(), c.contrafactual.max()))
    passo = 1e6
    yt = [(v, _mi(v)) for v in np.arange(np.floor(lo / passo) * passo, hi + passo, passo)]
    px, py = _eixos(gi, corpo, (100, 130, 850, 280), (0, 100), (yt[0][0], yt[-1][0]),
                    [(v, f"{v}%") for v in range(0, 101, 10)], yt,
                    xlabel="Seções recebidas, na ordem real de chegada",
                    ylabel="Diferença acumulada: 13 menos 22")
    corpo.append(_linha(c.pct_secoes, c.contrafactual, px, py, gi.ORANGE, 2.6, "7 4"))
    corpo.append(_linha(c.pct_secoes, c.real, px, py, gi.BLUE, 2.2))
    _legenda(gi, corpo, 520, 112, [(gi.BLUE, "real", ""),
                                   (gi.ORANGE, "1º turno da seção + swing médio da UF", "7 4")])
    r = res["contrafactual"]["2026"]
    tr, tc = r["ultima_troca_real"], r["ultima_troca_contrafactual"]
    titulo = "A virada da curva é reproduzida pela ordem de chegada"
    subt = (f"Última troca de liderança: real em {gi.fmt_num(tr['pct_secoes'], 1)}% das seções, "
            f"contrafactual em {gi.fmt_num(tc['pct_secoes'], 1)}%; mesma ordem de chegada nas duas curvas")
    desc = ("Diferença acumulada real e a que se teria se cada seção repetisse a fatia do 13 do 1º turno "
            "somada ao swing médio do seu estado, na mesma ordem de chegada.")
    return gi.documento(W, H, titulo, desc, corpo, subt,
                        "Fonte: TSE, BUs dos dois turnos de 2026 (compilação DataUrnas-BR)")


def fig_atraso(gi, res: dict) -> str:
    W, H = 1000, 560
    corpo: list[str] = []
    hst = res["atraso"]["2026_t2"]["hist_5min"]
    xs = np.array(hst["inicio"], float)
    ys = np.array(hst["secoes"], float)
    ymax = float(ys.max()) * 1.08
    passo = 10 ** np.floor(np.log10(ymax / 4))
    passo *= 2 if ymax / passo > 8 else 1
    yt = [(v, gi.fmt_int(v)) for v in np.arange(0, ymax, passo)]
    px, py = _eixos(gi, corpo, (100, 130, 340, 290), (-5, 365), (0, ymax),
                    [(m, f"{m // 60}h" if m else "0") for m in range(0, 361, 60)], yt,
                    xlabel="Recebimento menos emissão do BU", ylabel="Seções por faixa de 5 min")
    for x, y in zip(xs, ys, strict=True):
        corpo.append(gi.rect(px(x) + 0.5, py(y), px(x + 5) - px(x) - 1, py(0) - py(y), gi.BLUE))
    linhas = res["atraso_swing"]["2026_t2"]
    vals = [abs(v) for ln in linhas for v in (*ln["ic95_perm_pp"], ln["desvio_pp"])]
    _painel_faixas(gi, corpo, (530, 130, 440, 290), [("2026", gi.BLUE, linhas)],
                   max(vals) * 1.15,
                   [ln["faixa"].replace(" h", "").replace("mais de ", ">").replace("até ", "<")
                    for ln in linhas])
    corpo.append(gi.text(530, 116, "Swing observado menos esperado (pp)", size=12.5, fill=gi.MUTED))
    corpo.append(gi.text(750, 460, "Faixa de atraso (horas)", size=12.5,
                         fill=gi.MUTED, anchor="middle"))
    q = res["atraso"]["2026_t2"]["quantis_min"]
    titulo = "Da emissão do BU ao recebimento: 2º turno de 2026"
    subt = (f"Atraso mediano de {gi.fmt_num(q['0.5'] / 60, 1)} h (pausa da totalização até 19h03); "
            "à direita, o swing por faixa de atraso, controlado como no teste principal")
    desc = ("Histograma do intervalo entre a emissão do BU e o recebimento publicado, e desvio do swing "
            "por faixa de atraso com a faixa de 95% de permutações dentro do município.")
    return gi.documento(W, H, titulo, desc, corpo, subt,
                        "Fonte: TSE, BUs e aux.json do 2º turno de 2026 (coleta DataUrnas-BR)")


def figures(pasta: Path) -> None:
    gi = _primitives()
    res = json.loads((pasta / "resultado.json").read_text(encoding="utf-8"))
    curvas = pd.read_parquet(pasta / "curvas.parquet")
    regs = pd.read_parquet(pasta / "regioes.parquet")
    cf = pd.read_parquet(pasta / "contrafactual.parquet")
    gi.salvar("2026-chegada-curva.svg", fig_curva(gi, res, curvas))
    gi.salvar("2026-chegada-swing-decis.svg", fig_swing(gi, res))
    gi.salvar("2026-chegada-regioes.svg", fig_regioes(gi, res, regs))
    gi.salvar("2026-chegada-contrafactual.svg", fig_contrafactual(gi, res, cf))
    gi.salvar("2026-chegada-atraso.svg", fig_atraso(gi, res))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export")
    e.add_argument("--sql", type=Path, default=HERE / "chegada_bus.sql")
    e.add_argument("--out", type=Path, required=True)
    a = sub.add_parser("analyze")
    a.add_argument("--data", type=Path, required=True)
    a.add_argument("--out", type=Path, required=True)
    pl = sub.add_parser("placebo")
    pl.add_argument("--data", type=Path, required=True)
    pl.add_argument("--out", type=Path, required=True)
    f = sub.add_parser("figures")
    f.add_argument("--res", type=Path, required=True)
    args = ap.parse_args()
    if args.cmd == "export":
        export(args.sql, args.out)
    elif args.cmd == "analyze":
        analyze(args.data, args.out)
    elif args.cmd == "placebo":
        analyze_placebo(args.data, args.out)
    else:
        figures(args.res)


if __name__ == "__main__":
    main()
