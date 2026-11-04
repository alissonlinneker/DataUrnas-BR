"""Historical base rate of first-round leaders losing Brazilian runoffs.

Builds one row per runoff contest (president, governor and mayor) from the
TSE open-data files ``votacao_candidato_munzona_<YEAR>.zip`` and
``detalhe_votacao_munzona_<YEAR>.zip`` published at
https://cdn.tse.jus.br/estatistica/sead/odsele/, then fits logistic
regressions of P(first-round leader loses the runoff) on the first-round
margin and related features.

Usage (heavy step, meant to run on the remote node):

    python viradas_segundo_turno.py build --zip-dir ZIPS --out-dir OUT
    python viradas_segundo_turno.py model --out-dir OUT

``build`` writes ``disputas_2t.parquet``/``.csv`` (one row per contest).
``model`` writes ``modelo_logistico.json`` and ``presidente_estoque.csv``.
"""

from __future__ import annotations

import argparse
import io
import json
import math
import tempfile
import unicodedata
import zipfile
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

# 2026 is built too, but kept out of every model fit: it is the case under test.
YEARS = list(range(1994, 2028, 2))
TEST_YEAR = 2026
# TSE office codes for the offices that can go to a runoff.
CARGOS = {1: "presidente", 3: "governador", 11: "prefeito"}

# State capitals by UF, matched against the unaccented upper-case NM_UE.
CAPITALS = {
    "AC": "RIO BRANCO", "AL": "MACEIO", "AM": "MANAUS", "AP": "MACAPA",
    "BA": "SALVADOR", "CE": "FORTALEZA", "ES": "VITORIA", "GO": "GOIANIA",
    "MA": "SAO LUIS", "MG": "BELO HORIZONTE", "MS": "CAMPO GRANDE",
    "MT": "CUIABA", "PA": "BELEM", "PB": "JOAO PESSOA", "PE": "RECIFE",
    "PI": "TERESINA", "PR": "CURITIBA", "RJ": "RIO DE JANEIRO", "RN": "NATAL",
    "RO": "PORTO VELHO", "RR": "BOA VISTA", "RS": "PORTO ALEGRE",
    "SC": "FLORIANOPOLIS", "SE": "ARACAJU", "SP": "SAO PAULO", "TO": "PALMAS",
}

# 2026 presidential profile used for predictions (shares of valid votes).
# Keys match the model feature columns; eh_prefeito=0 because it is not a mayoral race.
PROFILE_2026 = {"margem_pp": 1.87, "lider_pct_t1": 47.03, "outros_pct_t1": 7.81,
                "eh_prefeito": 0.0}


def _strip(text: str) -> str:
    """Upper-case and remove accents so capital names compare reliably."""
    norm = unicodedata.normalize("NFKD", str(text))
    return "".join(c for c in norm if not unicodedata.combining(c)).upper().strip()


def _members(zip_path: Path) -> list[str]:
    """Pick the CSV members that hold every contest exactly once.

    The national ``_BRASIL.csv`` file already contains all states and the
    presidential rows; older packages without it are read state by state
    plus the ``_BR`` (president) and ``_ZZ`` (abroad) files.
    """
    names = [n for n in zipfile.ZipFile(zip_path).namelist() if n.lower().endswith(".csv")]
    brasil = [n for n in names if n.upper().endswith("_BRASIL.CSV")]
    return brasil or names


def _extract(zip_path: Path, dest: Path) -> list[str]:
    """Extract the selected members to ``dest`` as UTF-8 and return their paths.

    TSE packages are mostly cp1252 (not strict latin-1: some years carry bytes
    in 0x80-0x9F that DuckDB's latin-1 reader rejects), while a few are already
    UTF-8. A member whose first MiB decodes as strict UTF-8 is copied as is;
    any other is transcoded from cp1252, replacing undefined bytes.
    """
    out = []
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        for name in _members(zip_path):
            target = dest / Path(name).name
            with zf.open(name) as src:
                head = src.read(1 << 20)
            try:
                head.decode("utf-8")
                enc = "utf-8"
            except UnicodeDecodeError:
                enc = "cp1252"
            with zf.open(name) as src, open(target, "w", encoding="utf-8") as dst:
                reader = io.TextIOWrapper(src, encoding=enc, errors="replace")
                while chunk := reader.read(1 << 24):
                    dst.write(chunk)
            out.append(str(target))
    return out


def _read(con: duckdb.DuckDBPyConnection, files: list[str]) -> str:
    """Return a SQL relation string reading the UTF-8 copies of TSE CSVs (';')."""
    lst = ", ".join(f"'{f}'" for f in files)
    return (
        f"read_csv([{lst}], delim=';', quote='\"', header=true, all_varchar=true, "
        f"union_by_name=true)"
    )


# Contest unit: the TSE packages of some years (e.g. 2002, 2010) put the
# municipality code in SG_UE even on presidential and governor rows, which
# would split one national or state contest into thousands. Normalise it:
# president -> 'BR', governor -> the state, mayor -> the municipality.
_UNIDADE = ("CASE CAST(CD_CARGO AS INT) WHEN 1 THEN 'BR' "
            "WHEN 3 THEN SG_UF ELSE SG_UE END")


def build_year(con: duckdb.DuckDBPyConnection, zip_dir: Path, year: int, tmp: Path):
    """Aggregate candidate votes and turnout per contest and round for one year."""
    cand_zip = zip_dir / f"votacao_candidato_munzona_{year}.zip"
    det_zip = zip_dir / f"detalhe_votacao_munzona_{year}.zip"
    if not cand_zip.exists() or not det_zip.exists():
        return None, None
    cargos = ",".join(str(c) for c in CARGOS)
    work = tmp / str(year)
    cand_files = _extract(cand_zip, work / "cand")
    cols = {r[0] for r in con.execute(f"DESCRIBE SELECT * FROM {_read(con, cand_files)}").fetchall()}
    # Packages before 2016 have no QT_VOTOS_NOMINAIS_VALIDOS; there the nominal
    # total is used, and contests whose runoff pair differs from the top two
    # (e.g. annulled candidacies) are flagged by ``mesmo_par`` downstream.
    vcol = "QT_VOTOS_NOMINAIS_VALIDOS" if "QT_VOTOS_NOMINAIS_VALIDOS" in cols else "QT_VOTOS_NOMINAIS"
    cand = con.execute(
        f"""
        SELECT CAST(ANO_ELEICAO AS INT) ano, CAST(NR_TURNO AS INT) turno,
               CAST(CD_CARGO AS INT) cd_cargo, SG_UF sg_uf_row, {_UNIDADE} sg_ue,
               any_value(NM_UE) nm_ue, NR_CANDIDATO nr_candidato,
               any_value(NM_URNA_CANDIDATO) nm_urna, any_value(SG_PARTIDO) sg_partido,
               sum(CAST({vcol} AS BIGINT)) votos
        FROM {_read(con, cand_files)}
        WHERE CAST(CD_CARGO AS INT) IN ({cargos})
          AND NM_TIPO_ELEICAO ILIKE '%ordin%'
        GROUP BY ALL
        """
    ).df()
    for f in cand_files:
        Path(f).unlink()
    det_files = _extract(det_zip, work / "det")
    det = con.execute(
        f"""
        SELECT CAST(ANO_ELEICAO AS INT) ano, CAST(NR_TURNO AS INT) turno,
               CAST(CD_CARGO AS INT) cd_cargo, {_UNIDADE} sg_ue,
               sum(CAST(QT_APTOS AS BIGINT)) aptos,
               sum(CAST(QT_COMPARECIMENTO AS BIGINT)) comparecimento,
               sum(CAST(QT_VOTOS_BRANCOS AS BIGINT)) brancos,
               -- Older packages leave the QT_TOTAL_* columns at zero, so take the
               -- largest of the total and the sum of its parts.
               greatest(sum(CAST(QT_TOTAL_VOTOS_NULOS AS BIGINT)),
                        sum(CAST(QT_VOTOS_NULOS AS BIGINT)
                            + CAST(QT_VOTOS_NULOS_TECNICOS AS BIGINT))) nulos,
               sum(CAST(QT_TOTAL_VOTOS_VALIDOS AS BIGINT)) validos_det
        FROM {_read(con, det_files)}
        WHERE CAST(CD_CARGO AS INT) IN ({cargos})
          AND NM_TIPO_ELEICAO ILIKE '%ordin%'
        GROUP BY ALL
        """
    ).df()
    for f in det_files:
        Path(f).unlink()
    # Presidential rows carry the state in SG_UF; collapse to the national contest.
    cand = (
        cand.groupby(["ano", "turno", "cd_cargo", "sg_ue", "nr_candidato"], as_index=False)
        .agg(nm_ue=("nm_ue", "first"), sg_uf=("sg_uf_row", "first"),
             nm_urna=("nm_urna", "first"), sg_partido=("sg_partido", "first"),
             votos=("votos", "sum"))
    )
    return cand, det


def contests(cand: pd.DataFrame, det: pd.DataFrame) -> pd.DataFrame:
    """Build one row per contest that had a runoff."""
    rows = []
    det_idx = det.set_index(["ano", "turno", "cd_cargo", "sg_ue"])
    for (ano, cd_cargo, sg_ue), g in cand.groupby(["ano", "cd_cargo", "sg_ue"]):
        t1 = g[g.turno == 1].sort_values("votos", ascending=False)
        t2 = g[g.turno == 2].sort_values("votos", ascending=False)
        if t2.empty or len(t1) < 2:
            continue
        val1 = t1.votos.sum()
        val2 = t2.votos.sum()
        a, b = t1.iloc[0], t1.iloc[1]
        t2v = dict(zip(t2.nr_candidato, t2.votos, strict=True))
        same_pair = set(t2.nr_candidato[t2.votos > 0]) == {a.nr_candidato, b.nr_candidato}
        d1 = det_idx.loc[(ano, 1, cd_cargo, sg_ue)] if (ano, 1, cd_cargo, sg_ue) in det_idx.index else None
        d2 = det_idx.loc[(ano, 2, cd_cargo, sg_ue)] if (ano, 2, cd_cargo, sg_ue) in det_idx.index else None
        a2, b2 = t2v.get(a.nr_candidato, 0), t2v.get(b.nr_candidato, 0)
        uf = "BR" if cd_cargo == 1 else a.sg_uf
        row = {
            "ano": int(ano), "cargo": CARGOS[int(cd_cargo)], "uf": uf, "sg_ue": sg_ue,
            # NM_UE on governor rows of some years is a municipality name; use the state.
            "nm_ue": uf if cd_cargo == 3 else a.nm_ue,
            "capital": bool(cd_cargo == 11 and CAPITALS.get(uf) == _strip(a.nm_ue)),
            "lider_nr": a.nr_candidato, "lider": a.nm_urna, "lider_partido": a.sg_partido,
            "segundo_nr": b.nr_candidato, "segundo": b.nm_urna,
            "segundo_partido": b.sg_partido,
            "n_candidatos_t1": int((t1.votos > 0).sum()),
            "validos_t1": int(val1), "lider_votos_t1": int(a.votos),
            "segundo_votos_t1": int(b.votos),
            "lider_pct_t1": 100 * a.votos / val1, "segundo_pct_t1": 100 * b.votos / val1,
            "validos_t2": int(val2), "lider_votos_t2": int(a2), "segundo_votos_t2": int(b2),
            "lider_pct_t2": 100 * a2 / val2 if val2 else np.nan,
            "segundo_pct_t2": 100 * b2 / val2 if val2 else np.nan,
            "mesmo_par": bool(same_pair),
        }
        row["margem_pp"] = row["lider_pct_t1"] - row["segundo_pct_t1"]
        row["outros_pct_t1"] = 100 - row["lider_pct_t1"] - row["segundo_pct_t1"]
        row["outros_votos_t1"] = int(val1 - a.votos - b.votos)
        row["lider_perdeu"] = bool(b2 > a2)
        row["vencedor_t2"] = row["segundo"] if row["lider_perdeu"] else row["lider"]
        row["delta_lider_pp"] = row["lider_pct_t2"] - row["lider_pct_t1"]
        row["delta_segundo_pp"] = row["segundo_pct_t2"] - row["segundo_pct_t1"]
        for k, d in (("t1", d1), ("t2", d2)):
            for col in ("aptos", "comparecimento", "brancos", "nulos", "validos_det"):
                row[f"{col}_{k}"] = int(d[col]) if d is not None else np.nan
        # A mayoral runoff only exists above 200,000 voters (CF art. 29, II).
        # Smaller municipalities with round-2 rows are other ballots the TSE
        # files under NR_TURNO = 2 (e.g. Cerro Grande/RS in 2020), not runoffs.
        if cd_cargo == 11 and not (row["aptos_t1"] >= 200_000):
            continue
        row["delta_comparecimento"] = row["comparecimento_t2"] - row["comparecimento_t1"]
        row["delta_comparecimento_pp"] = 100 * (
            row["comparecimento_t2"] / row["aptos_t2"] - row["comparecimento_t1"] / row["aptos_t1"]
        )
        # Pool of votes available to the two finalists in the runoff:
        # other candidates' first-round votes + drop in non-valid votes + turnout gain.
        # Non-valid = turnout minus valid nominal votes, which also counts votes
        # cast for candidates whose votes were annulled, and keeps the identity
        # estoque == (valid runoff votes) - (finalists' first-round votes) exact.
        bn1 = row["comparecimento_t1"] - val1
        bn2 = row["comparecimento_t2"] - val2
        row["nao_validos_t1"], row["nao_validos_t2"] = bn1, bn2
        row["estoque"] = row["outros_votos_t1"] + (bn1 - bn2) + row["delta_comparecimento"]
        gain_b = row["segundo_votos_t2"] - row["segundo_votos_t1"]
        row["segundo_ganho"] = gain_b
        row["lider_ganho"] = row["lider_votos_t2"] - row["lider_votos_t1"]
        row["fracao_estoque_segundo"] = gain_b / row["estoque"] if row["estoque"] else np.nan
        rows.append(row)
    return pd.DataFrame(rows)


def cmd_build(zip_dir: Path, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute("SET threads TO 32")
    frames = []
    with tempfile.TemporaryDirectory(dir="/dev/shm") as tmp:
        for year in YEARS:
            cand, det = build_year(con, zip_dir, year, Path(tmp))
            if cand is None:
                print(f"{year}: missing files, skipped", flush=True)
                continue
            df = contests(cand, det)
            print(f"{year}: {len(df)} runoff contests", flush=True)
            frames.append(df)
    allc = pd.concat(frames, ignore_index=True)
    allc.to_parquet(out_dir / "disputas_2t.parquet", index=False)
    allc.to_csv(out_dir / "disputas_2t.csv", index=False)


def fit_logit(x: np.ndarray, y: np.ndarray, iters: int = 100):
    """Logistic regression by Newton-Raphson (IRLS); returns (beta, covariance)."""
    x1 = np.column_stack([np.ones(len(x)), x])
    beta = np.zeros(x1.shape[1])
    for _ in range(iters):
        p = 1 / (1 + np.exp(-x1 @ beta))
        w = p * (1 - p)
        hess = x1.T @ (x1 * w[:, None])
        step = np.linalg.solve(hess, x1.T @ (y - p))
        beta += step
        if np.max(np.abs(step)) < 1e-10:
            break
    p = 1 / (1 + np.exp(-x1 @ beta))
    cov = np.linalg.inv(x1.T @ (x1 * (p * (1 - p))[:, None]))
    ll = float(np.sum(y * np.log(p) + (1 - y) * np.log(1 - p)))
    return beta, cov, ll


def predict(beta, cov, xnew):
    """Predicted probability with a 95% Wald interval on the logit scale."""
    v = np.concatenate([[1.0], xnew])
    eta = float(v @ beta)
    se = float(math.sqrt(v @ cov @ v))
    f = lambda z: 1 / (1 + math.exp(-z))  # noqa: E731
    return f(eta), f(eta - 1.96 * se), f(eta + 1.96 * se)


def wilson(k: int, n: int, z: float = 1.96):
    """Wilson score interval for a binomial proportion."""
    if n == 0:
        return (np.nan, np.nan, np.nan)
    p = k / n
    den = 1 + z * z / n
    c = (p + z * z / (2 * n)) / den
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / den
    return (p, max(0.0, c - h), min(1.0, c + h))


def cmd_model(out_dir: Path) -> None:
    df = pd.read_parquet(out_dir / "disputas_2t.parquet")
    ok = df[df.mesmo_par & (df.validos_t2 > 0) & (df.ano < TEST_YEAR)].copy()
    # Comebacks closest to the 2026 profile (governor and state-capital mayor).
    near = ok[ok.lider_perdeu & ((ok.cargo != "prefeito") | ok.capital)].copy()
    near["distancia"] = np.hypot(near.margem_pp - PROFILE_2026["margem_pp"],
                                 near.outros_pct_t1 - PROFILE_2026["outros_pct_t1"])
    near.sort_values("distancia").to_csv(out_dir / "viradas_proximas.csv", index=False)
    df[df.ano == TEST_YEAR].to_csv(out_dir / "disputas_2t_2026.csv", index=False)
    specs = {
        "margem": ["margem_pp"],
        "lider_pct": ["lider_pct_t1"],
        "margem_outros": ["margem_pp", "outros_pct_t1"],
        # leader share + others is the same model as margin + others
        # (leader = (100 - others + margin) / 2), so the office dummy is tested instead.
        "margem_outros_cargo": ["margem_pp", "outros_pct_t1", "eh_prefeito"],
    }
    ok["eh_prefeito"] = (ok.cargo == "prefeito").astype(float)
    samples = {
        "todas": ok,
        "presidente_governador": ok[ok.cargo != "prefeito"],
        "prefeito": ok[ok.cargo == "prefeito"],
        "prefeito_capital": ok[ok.capital],
    }
    res = {"perfil_2026": PROFILE_2026, "n_total": int(len(df)),
           "n_modelo": int(len(ok)), "excluidas_par_diferente": int((~df.mesmo_par).sum()),
           "modelos": {}, "empirico": {}}
    for sname, s in samples.items():
        ys = s.lider_perdeu.astype(float).to_numpy()
        for mname, cols in specs.items():
            if any(s[c].nunique() < 2 for c in cols):
                continue  # constant feature in this subsample (office dummy)
            beta, cov, ll = fit_logit(s[cols].to_numpy(float), ys)
            pr = predict(beta, cov, np.array([PROFILE_2026[c] for c in cols]))
            res["modelos"][f"{sname}:{mname}"] = {
                "n": int(len(s)), "viradas": int(ys.sum()), "coef": beta.round(5).tolist(),
                "se": np.sqrt(np.diag(cov)).round(5).tolist(), "loglik": round(ll, 3),
                "aic": round(-2 * ll + 2 * len(beta), 2),
                "p_2026": round(pr[0], 4), "ic95": [round(pr[1], 4), round(pr[2], 4)],
            }
    # Empirical rates by margin band and in the neighbourhood of the 2026 profile.
    bands = [0, 1, 2, 3, 5, 7.5, 10, 15, 20, 100]
    for sname, s in samples.items():
        tab = []
        for lo, hi in zip(bands[:-1], bands[1:], strict=True):
            b = s[(s.margem_pp >= lo) & (s.margem_pp < hi)]
            p, lo_ci, hi_ci = wilson(int(b.lider_perdeu.sum()), len(b))
            tab.append({"faixa": f"{lo}-{hi}", "n": len(b), "viradas": int(b.lider_perdeu.sum()),
                        "taxa": _r(p), "ic95": [_r(lo_ci), _r(hi_ci)]})
        near = s[(s.margem_pp < 3) & (s.outros_pct_t1 < 15)]
        p, lo_ci, hi_ci = wilson(int(near.lider_perdeu.sum()), len(near))
        res["empirico"][sname] = {
            "por_faixa": tab,
            "perfil_margem_lt3_outros_lt15": {"n": len(near),
                                              "viradas": int(near.lider_perdeu.sum()),
                                              "taxa": _r(p), "ic95": [_r(lo_ci), _r(hi_ci)]},
            "total": {"n": len(s), "viradas": int(s.lider_perdeu.sum())},
        }
    res["contagem_por_cargo"] = (
        ok.groupby("cargo").lider_perdeu.agg(["count", "sum"]).rename(
            columns={"count": "disputas", "sum": "viradas"}).astype(int).to_dict("index")
    )
    res["contagem_por_cargo_ano"] = {
        f"{c}:{a}": {"disputas": int(n), "viradas": int(v)}
        for (c, a), (n, v) in ok.groupby(["cargo", "ano"]).lider_perdeu.agg(["count", "sum"])
        .iterrows()
    }
    (out_dir / "modelo_logistico.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    pres = df[df.cargo == "presidente"].sort_values("ano")
    pres.to_csv(out_dir / "presidente_estoque.csv", index=False)
    print(json.dumps({k: v for k, v in res.items() if k != "contagem_por_cargo_ano"},
                     ensure_ascii=False)[:4000])


def _r(v):
    return None if v is None or (isinstance(v, float) and math.isnan(v)) else round(v, 4)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--zip-dir", type=Path, required=True)
    b.add_argument("--out-dir", type=Path, required=True)
    m = sub.add_parser("model")
    m.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()
    if args.cmd == "build":
        cmd_build(args.zip_dir, args.out_dir)
    else:
        cmd_model(args.out_dir)


if __name__ == "__main__":
    main()
