"""Closing minute x share of 13: decile cut, share and the 17:01 comparison."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[2]


def _carregar():
    p = RAIZ / "scripts" / "ele2026" / "encerramento_minuto_t2.py"
    spec = importlib.util.spec_from_file_location("encerramento_minuto_t2", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


M = _carregar()


def test_share_two_candidates():
    assert M.share(1, 1) == 50.0
    assert M.share(3, 1) == 75.0
    assert pd.isna(M.share(0, 0))


def test_deciles_equal_sizes_and_order():
    df = pd.DataFrame({"t": pd.date_range("2026-10-25 17:00", periods=100, freq="s")[::-1]})
    g = M.deciles(df, "t")
    assert g.value_counts().tolist() == [10] * 10
    # The earliest closing falls in group 1, the latest in group 10.
    assert g[df.t.idxmin()] == 1 and g[df.t.idxmax()] == 10


def _secoes(efeito: float) -> pd.DataFrame:
    """Two polling places, each with sections closing at 17:00 and 17:01.
    `efeito` adds points to the share of 13 of sections closed at 17:01."""
    rows = []
    for local, base in ((1, 40.0), (2, 60.0)):
        for i, minuto in enumerate(("17:00:30", "17:01:30") * 2):
            p2 = base + (efeito if minuto.startswith("17:01") else 0.0)
            rows.append({"uf": "sp", "cd_mun": "71072", "zona": "0001", "local_votacao": local,
                         "secao": f"{local}{i}", "enc": pd.Timestamp(f"2026-10-25 {minuto}"),
                         "v13": p2, "v22": 100 - p2, "p2": p2, "d": 3.0})
    return pd.DataFrame(rows)


def test_cut_1701_no_effect_inside_place():
    r = M.cut_1701(_secoes(0.0))
    assert r["locais_com_os_dois_lados"] == 2
    assert r["dif_mesmo_local_pct13_t2"] == 0.0


def test_cut_1701_detects_planted_effect():
    r = M.cut_1701(_secoes(5.0))
    assert r["dif_mesmo_local_pct13_t2"] == 5.0
    assert r["ic95_dif_mesmo_local_pct13_t2"][0] > 0
