"""2nd round of 2026 and audit verdict: loaders, helpers and the two new pages."""

import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from dataurnas.dashboard import data2026 as d26  # noqa: E402

T2 = d26.base_dir(2)
tem_t2 = pytest.mark.skipif(not (T2 / "resultado_uf.parquet").exists(), reason="data/parquet/2026/t2 ausente")


def test_base_dir_por_turno():
    assert d26.base_dir() == d26.base_dir(1)
    assert d26.base_dir(2) == d26.base_dir(1) / "t2"


# ----------------------------------------------------------------------
# Synthetic data
# ----------------------------------------------------------------------
def _uf(uf, eleitorado, comparecimento, v13, v22, outros=0):
    return {"uf": uf, "eleitorado": eleitorado, "comparecimento": comparecimento,
            "votos_validos": v13 + v22 + outros, "v_13": v13, "v_22": v22}


def test_compare_turnos_by_uf():
    t1 = pd.DataFrame([_uf("ac", 100, 80, 30, 40, outros=10)])
    t2 = pd.DataFrame([_uf("ac", 100, 90, 45, 45)])
    linha = d26.compare_turnos_by_uf(t1, t2, [13, 22]).iloc[0]
    assert linha["pct_13_t1"] == pytest.approx(37.5)  # 30 of 80 valid votes, eliminated candidates included
    assert linha["pct_13_t2"] == pytest.approx(50.0)
    assert linha["pct_13_var_pp"] == pytest.approx(12.5)
    assert linha["comparecimento_var_pp"] == pytest.approx(10.0)
    assert linha["nome"] == "Acre"
    assert d26.compare_turnos_by_uf(pd.DataFrame(), t2, [13]).empty


def test_soma_e_conferencia_dos_bus(tmp_path):
    secoes = pd.DataFrame({
        "uf": ["ac", "ac", "al"], "comparecimento": [10, 20, 5], "v13": [4, 9, 2], "v22": [5, 10, 2],
        "brancos": [1, 0, 0], "nulos": [0, 1, 1],
    })
    path = tmp_path / "secoes_t2.parquet"
    secoes.to_parquet(path)
    soma = d26.soma_bus_por_uf(path)
    assert soma.set_index("uf").loc["ac", "v_13"] == 13
    oficial = pd.DataFrame([
        {"uf": "ac", "secoes_instaladas": 2, "comparecimento": 30, "v_13": 13, "v_22": 15,
         "votos_brancos": 1, "votos_nulos_total": 1},
        {"uf": "al", "secoes_instaladas": 1, "comparecimento": 5, "v_13": 2, "v_22": 3,  # 1 vote off
         "votos_brancos": 0, "votos_nulos_total": 1},
    ])
    rec = d26.reconcile_bus_t2(soma, oficial)
    assert len(rec) == 2 * len(d26.ITENS_CONFERENCIA_T2)
    ruins = rec[~rec["confere"]]
    assert list(zip(ruins["uf"], ruins["item"], ruins["diferenca"], strict=True)) == [("al", "Candidato 22", -1)]
    assert d26.soma_bus_por_uf(tmp_path / "nao_existe.parquet").empty


def test_verificacoes_e_rdv_df():
    v = {"verificacoes": [{"n": 2, "situacao": "ressalva", "documento": "docs/b.md"},
                          {"n": 1, "situacao": "confere", "documento": "docs/a.md"}]}
    df = d26.verificacoes_df(v)
    assert list(df["n"]) == [1, 2]
    assert list(df["situacao_label"]) == [d26.SITUACAO_VERIFICACAO["confere"], d26.SITUACAO_VERIFICACAO["ressalva"]]
    assert d26.verificacoes_df({}).empty
    rdv = d26.rdv_totais_df({"totais": {"13": {"rdv": 5, "bu": 5}, "nulos": {"rdv": 2, "bu": 3}}})
    assert list(rdv["item"]) == ["Candidato 13", "Nulos"]
    assert list(rdv["confere"]) == [True, False]


# ----------------------------------------------------------------------
# Real files
# ----------------------------------------------------------------------
@tem_t2
def test_resultado_t2_real_e_soma_dos_bus():
    base = d26.base_dir(2)
    resumo, cand, res_uf = d26.load_resumo(base), d26.load_candidatos(base), d26.load_resultado_uf(base)
    assert resumo["turno"] == 2 and list(cand["numero"]) == [13, 22]
    assert int(res_uf["votos_validos"].sum()) == resumo["totais"]["votos_validos"]
    rec = d26.reconcile_bus_t2(d26.soma_bus_por_uf(base / "secoes_t2.parquet"), res_uf)
    assert len(rec) == 28 * len(d26.ITENS_CONFERENCIA_T2)
    assert rec["confere"].all(), rec[~rec["confere"]]


@tem_t2
def test_veredicto_json_coerente_com_os_dados():
    v = d26.load_veredicto()
    assert len(v["verificacoes"]) == v["indicadores"]["verificacoes"] == 26
    assert len(v["pendencias"]) == v["indicadores"]["pendencias"] == 13
    assert len(v["nao_verificavel"]) == 3
    assert set(d26.verificacoes_df(v)["situacao"]) <= set(d26.SITUACAO_VERIFICACAO)
    oficial = {c["numero"]: c["votos"] for c in d26.load_resumo(d26.base_dir(2))["candidatos"]}
    assert {c["numero"]: c["votos"] for c in v["resultado_oficial_2t"]["candidatos"]} == oficial
    assert v["resultado_oficial_2t"]["margem"] == oficial[13] - oficial[22]
    rdv = d26.rdv_totais_df(d26.load_rdv_resumo())
    assert rdv["confere"].all()
    texto = (T2 / "veredicto_2026.json").read_text(encoding="utf-8")
    assert chr(0x2014) not in texto and chr(0x2013) not in texto


# ----------------------------------------------------------------------
# Pages render without exceptions
# ----------------------------------------------------------------------
@tem_t2
@pytest.mark.parametrize(("modulo", "titulo"), [
    ("eleicoes_2026_t2", "Eleições 2026: Presidente, 2º turno"),
    ("veredicto_2026", "Veredicto da auditoria 2026"),
    ("eleicoes_2026", "Eleições 2026: Presidente, 1º turno"),
])
def test_paginas_2026_rodam_sem_excecao(modulo, titulo):
    AppTest = pytest.importorskip("streamlit.testing.v1").AppTest
    script = (
        "import sys\n"
        f"sys.path.insert(0, {str(SRC)!r})\n"
        f"from dataurnas.dashboard.pages import {modulo}\n"
        f"{modulo}.render()\n"
    )
    at = AppTest.from_string(script, default_timeout=300)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert titulo in " ".join(m.value for m in at.markdown)
    assert not [w.value for w in at.warning if "Não foi possível" in w.value]
