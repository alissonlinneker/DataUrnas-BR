"""Viradas de liderança entre turnos: definições, trocas mínimas, movimento e modelo."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parents[2]


def _carregar():
    p = RAIZ / "scripts" / "ele2026" / "viradas_t1_t2.py"
    spec = importlib.util.spec_from_file_location("viradas_t1_t2", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


M = _carregar()


def _turno(linhas):
    cols = ["uf", "cd_mun", "zona", "secao", "aptos", "comparecimento",
            "v13", "v22", "outros", "brancos", "nulos"]
    return pd.DataFrame(linhas, columns=cols)


def test_lider():
    assert list(M.lider([10, 5, 7], [5, 10, 7])) == ["13", "22", "empate"]


def test_troca_minima_usa_so_reserva_liquida():
    # 13 ganhou 30; outros 10, BN caiu 5, comparecimento subiu 5: faltam 10
    assert M.troca_minima([30], [10], [8], [3], [200], [205])[0] == 10
    # BN subiu e comparecimento caiu: não contam como reserva
    assert M.troca_minima([30], [10], [3], [8], [205], [200])[0] == 20
    # ganho coberto pela reserva
    assert M.troca_minima([5], [10], [0], [0], [100], [100])[0] == 0
    # perda não gera troca negativa
    assert M.troca_minima([-7], [0], [0], [0], [100], [100])[0] == 0


def test_troca_estrita_aceita_rotatividade():
    # ganho 30; outros 10, BN do 1º turno 8, ausentes 50 (limitados a comp_2=200)
    assert M.troca_estrita([30], [10], [8], [200], [200], [250], [250])[0] == 0
    # seção sem ausentes: 30 - 10 - 8 = 12 trocas obrigatórias
    assert M.troca_estrita([30], [10], [8], [200], [200], [200], [200])[0] == 12
    # aptos maior no 2º turno (agregação) amplia os possíveis novos eleitores
    assert M.troca_estrita([30], [10], [8], [200], [200], [200], [205])[0] == 7


def test_metricas_virada_e_trocas():
    t1 = _turno([
        ("ac", "01", "1", "1", 300, 200, 90, 100, 5, 3, 2),     # 22 lidera
        ("ac", "01", "1", "2", 300, 200, 120, 70, 5, 3, 2),     # 13 lidera
        ("ac", "01", "1", "3", 300, 200, 95, 95, 5, 3, 2),      # empate
    ])
    t2 = _turno([
        ("ac", "01", "1", "1", 300, 200, 110, 85, 0, 3, 2),     # virou para 13
        ("ac", "01", "1", "2", 300, 200, 125, 70, 0, 3, 2),     # manteve
        ("ac", "01", "1", "3", 300, 200, 120, 75, 0, 3, 2),     # saiu do empate
    ])
    d = M.metricas(M.parear(t1, t2))
    assert list(d["virada"]) == ["22->13", "", ""]
    assert list(d["margem_t1"]) == [10, 50, 0]
    # seção 1: 13 ganhou 20, reserva = outros 5 -> troca 15
    assert d.loc[0, "troca_min_13"] == 15
    assert d.loc[0, "troca_minima"] == 15
    assert d.loc[1, "troca_minima"] == 0
    assert d.loc[0, "troca_max"] == 15 and d.loc[0, "troca_max_cand"] == "13"
    assert d.loc[0, "delta_fatia"] == pytest.approx(110 / 195 - 90 / 190)
    assert d["regiao"].unique().tolist() == ["Norte"]
    assert not d["aptos_mudou"].any()


def test_parear_preserva_municipio():
    t1 = _turno([("ce", "02", "1", "1", 10, 10, 5, 5, 0, 0, 0)]).assign(municipio="X")
    t2 = _turno([("ce", "02", "1", "1", 10, 10, 6, 4, 0, 0, 0),
                 ("ce", "02", "1", "9", 10, 10, 6, 4, 0, 0, 0)]).assign(municipio="X")
    d = M.parear(t1, t2)
    assert len(d) == 1
    assert d.loc[0, "municipio"] == "X"
    assert {"v13_1", "v13_2", "aptos_1", "aptos_2"} <= set(d.columns)


def test_swing_municipal_exclui_a_propria_secao():
    d = pd.DataFrame({
        "uf": ["ba"] * 3, "cd_mun": ["1", "1", "1"],
        "v13_1": [50, 50, 50], "v22_1": [50, 50, 50],
        "v13_2": [60, 60, 100], "v22_2": [40, 40, 0],
    })
    s = M.swing_municipal(d)
    # sem a seção 3 o município foi de 0,5 para 0,6
    assert s[2] == pytest.approx(0.1)
    # sem a seção 1: (60+100)/200 - 0,5 = 0,3
    assert s[0] == pytest.approx(0.3)


def test_swing_municipio_pequeno_usa_uf():
    d = pd.DataFrame({
        "uf": ["ba"] * 3, "cd_mun": ["1", "2", "2"],
        "v13_1": [10, 100, 100], "v22_1": [10, 100, 100],
        "v13_2": [12, 120, 120], "v22_2": [8, 80, 80],
    })
    s = M.swing_municipal(d)
    # seção 0 está sozinha no município 1: cai para a UF sem ela (0,6 - 0,5)
    assert s[0] == pytest.approx(0.1)


def test_z_robusto_destaca_seção_fora_do_municipio():
    n = 40
    rng = np.random.default_rng(1)
    delta = rng.normal(0.02, 0.01, n)
    delta[0] = 0.30
    d = pd.DataFrame({"uf": ["pi"] * n, "cd_mun": ["7"] * n,
                      "v13_1": [100] * n, "v22_1": [100] * n,
                      "v13_2": [100] * n, "v22_2": [100] * n,
                      "delta_fatia": delta})
    z = M.z_robusto(d)
    assert z.loc[0, "z_delta"] > 4
    assert (z["z_delta"].abs().iloc[1:] < 4).all()
    assert set(z["z_ref"]) == {"municipio"}


def test_z_robusto_ignora_secao_pequena():
    d = pd.DataFrame({"uf": ["pi"] * 3, "cd_mun": ["7"] * 3,
                      "v13_1": [5, 100, 100], "v22_1": [5, 100, 90],
                      "v13_2": [5, 100, 110], "v22_2": [5, 100, 90],
                      "delta_fatia": [0.5, 0.0, 0.03]})
    z = M.z_robusto(d)
    assert np.isnan(z.loc[0, "z_delta"])
    assert z.loc[1, "z_ref"] == "uf"


def test_logistica_recupera_coeficientes():
    rng = np.random.default_rng(7)
    x = rng.normal(size=20000)
    X = np.column_stack([np.ones_like(x), x])
    p = 1 / (1 + np.exp(-(-1.0 + 2.0 * x)))
    y = (rng.random(len(x)) < p).astype(float)
    beta = M.ajustar_logistica(X, y)
    assert beta[0] == pytest.approx(-1.0, abs=0.1)
    assert beta[1] == pytest.approx(2.0, abs=0.1)
    assert M.prever(X[:3], beta).shape == (3,)


def test_features_orienta_movimento_para_o_segundo_colocado():
    d = pd.DataFrame({
        "v13_1": [40, 60], "v22_1": [60, 40], "lider_1": ["22", "13"],
        "margem_t1": [20, 20], "swing": [0.05, 0.05], "reserva_frac": [0.1, 0.1],
        "virada": ["22->13", ""],
    })
    X, y, mask = M.features(d)
    assert mask.all()
    # gap = movimento a favor do 2º colocado - meia margem (0,1)
    assert X[0, 2] == pytest.approx(0.05 - 0.1)
    assert X[1, 2] == pytest.approx(-0.05 - 0.1)
    assert list(y) == [1.0, 0.0]


def test_marcar_atipicos_regua():
    d = pd.DataFrame({
        "troca_max": [9, 10, 10, 0], "comparecimento_2": [100, 100, 300, 100],
        "troca_estrita_max": [0, 0, 0, 1], "z_delta": [0.0, 1.0, np.nan, -4.5],
    })
    a = M.marcar_atipicos(d)
    assert list(a["atip_troca"]) == [False, True, False, False]
    assert list(a["atip_estrita"]) == [False, False, False, True]
    assert list(a["atip_desvio"]) == [False, False, False, True]
    assert list(a["atipico"]) == [False, True, False, True]


def test_faixa_swing():
    assert list(M.faixa_swing([0.004, -0.015, 0.07])) == ["0-0,5", "1-2", ">6"]


def test_comparar_urna():
    at = pd.DataFrame({"numero_interno_urna_1": [1, 2, None],
                       "numero_interno_urna_2": pd.array([1, 3, 4], dtype="Int64"),
                       "codigo_carga_1": ["a", "b", "c"], "codigo_carga_2": ["a", "b", None]})
    r = M.comparar_urna(at)
    assert list(r["mesma_urna"]) == [True, False, None]
    assert list(r["mesma_carga"]) == [True, True, None]


@pytest.mark.parametrize("f,entrada,saida", [
    ("_hora_compacta", "20261004T150706", "2026-10-04 15:07:06"),
    ("_hora_compacta", None, None),
    ("_hora_2022", "02/10/2022 15:05:33", "2022-10-02 15:05:33"),
    ("_hora_2022", None, None),
])
def test_horas(f, entrada, saida):
    assert getattr(M, f)(entrada) == saida


def test_resumir_grupo_taxas_e_esperado():
    g = pd.DataFrame({
        "lider_1": ["22", "22", "13", "13"], "virada": ["22->13", "", "13->22", ""],
        "margem_t1": [2, 30, 4, 50], "delta_fatia": [0.05, 0.01, -0.04, 0.0],
        "troca_minima": [0, 0, 3, 0], "troca_vencedor": [0, 0, 3, 0],
        "troca_max": [0, 0, 3, 0], "p_virada": [0.6, 0.1, 0.5, 0.05],
        "p_faixa": [0.5, 0.1, 0.5, 0.0], "p_troca": [0.0] * 4,
        "atip_troca": [False] * 4, "atip_estrita": [False] * 4,
        "atip_desvio": [False, False, True, False], "atipico": [False, False, True, False],
        "aptos_mudou": [False] * 4,
    })
    r = M.resumir_grupo(g)
    assert r["viradas_22_13"] == 1 and r["viradas_13_22"] == 1
    assert r["taxa_22_13"] == 0.5
    assert r["esperado_22_13"] == pytest.approx(0.7)
    assert r["esperado_22_13_dp"] == pytest.approx(np.sqrt(0.6 * 0.4 + 0.1 * 0.9), abs=0.05)
    assert r["margem_viradas_media"] == 3.0
    assert r["troca_viradas_zero"] == 1
    assert r["atipicos"] == 1


def test_tabela_grupos_soma_por_grupo_e_fecha_com_todas():
    t1 = _turno([
        ("ac", "01", "1", "1", 300, 200, 90, 100, 5, 3, 2),     # 22 lidera
        ("ac", "01", "1", "2", 300, 200, 120, 70, 5, 3, 2),     # 13 lidera
        ("ba", "02", "1", "1", 100, 80, 40, 30, 6, 2, 2),       # 13 lidera
    ])
    t2 = _turno([
        ("ac", "01", "1", "1", 300, 210, 110, 95, 0, 2, 3),     # vira 22->13
        ("ac", "01", "1", "2", 300, 195, 80, 110, 0, 3, 2),     # vira 13->22
        ("ba", "02", "1", "1", 100, 82, 45, 33, 0, 2, 2),       # sem virada
    ])
    d = M.metricas(M.parear(t1, t2))
    t = M.tabela_grupos(d, 2026)
    br = t[(t["nivel"] == "brasil")].set_index("grupo_virada")
    assert br.loc["22 para 13", "secoes"] == 1
    assert br.loc["22 para 13", "v13_var"] == 20
    assert br.loc["22 para 13", "abstencao_1"] == 100
    assert br.loc["22 para 13", "abstencao_var"] == -10
    assert br.loc["13 para 22", "v22_var"] == 40
    assert br.loc["sem virada", "invalidos_var"] == 0
    assert br.loc["todas", "secoes"] == 3
    soma = br.drop(index="todas")[["v13_var", "v22_var", "outros_var", "abstencao_var"]].sum()
    assert (soma == br.loc["todas", ["v13_var", "v22_var", "outros_var", "abstencao_var"]]).all()
    nordeste = t[(t["nivel"] == "regiao") & (t["grupo"] == "Nordeste")
                 & (t["grupo_virada"] == "todas")].iloc[0]
    assert nordeste["comparecimento_var"] == 2
