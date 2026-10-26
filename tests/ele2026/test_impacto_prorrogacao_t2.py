"""Impacto da prorrogação no 2º turno de 2026: horários, log, pareamento e cenários."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parents[2]


def _carregar():
    p = RAIZ / "scripts" / "ele2026" / "impacto_prorrogacao_t2.py"
    spec = importlib.util.spec_from_file_location("impacto_prorrogacao_t2", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


M = _carregar()


@pytest.mark.parametrize("bsb,esperado", [
    ("2026-10-25 17:00:00", 0),
    ("2026-10-25 17:10:59", 10),
    ("2026-10-25 17:11:00", 11),
    ("2026-10-25 19:00:59", 120),
    ("2026-10-25 16:59:59", -1),
    (None, None),
])
def test_minuto_truncado(bsb, esperado):
    assert M.minuto_truncado(bsb, "20261025") == esperado


def test_limiares_e_grupo():
    assert M.marcar_limiares(10) == {"apos_17h10": False, "apos_17h30": False,
                                     "apos_18h00": False, "apos_19h00": False}
    assert M.marcar_limiares(61) == {"apos_17h10": True, "apos_17h30": True,
                                     "apos_18h00": True, "apos_19h00": False}
    assert M.marcar_limiares(None)["apos_17h10"] is None
    assert M.grupo_t2(10) == "no_horario"
    assert M.grupo_t2(11) == "intermediaria"
    assert M.grupo_t2(30) == "intermediaria"
    assert M.grupo_t2(31) == "tardia"
    assert M.grupo_t2(None) == "sem_horario"


@pytest.mark.parametrize("uf,cd,local,esperado", [
    ("ac", "01007", "20261004T150706", "2026-10-04 17:07:06"),  # UTC-5
    ("am", "02550", "20261004T160000", "2026-10-04 17:00:00"),  # Manaus, UTC-4
    ("am", "98477", "20261004T150000", "2026-10-04 17:00:00"),  # Tabatinga, UTC-5
    ("ba", "38490", "20261004T171500", "2026-10-04 17:15:00"),
    ("pe", "30015", "20261004T180000", "2026-10-04 17:00:00"),  # Noronha, UTC-2
])
def test_encerramento_t1_bsb(uf, cd, local, esperado):
    assert M.encerramento_t1_bsb(local, uf, cd) == esperado


def test_encerramento_t1_vazio():
    assert M.encerramento_t1_bsb(None, "ba", "38490") is None


def test_nome_log():
    assert M.nome_log("o03221ba3849000010001-bu.dat") == "o03221ba3849000010001-log.jez"
    assert M.nome_log("o03221ba3849000010001-busa.dat") == "o03221ba3849000010001-logsa.jez"
    assert M.nome_log(None) is None


def _linha(data_hora, desc, urna="1234567"):
    return f"{data_hora}\tINFO\t{urna}\tVOTA\t{desc}\tABCDEF0123456789"


def test_votos_por_corte_bsb_converte_fuso_e_filtra_data():
    voto = "O voto do eleitor foi computado"
    texto = "\n".join([
        _linha("04/10/2026 16:30:00", voto),      # 1º turno acumulado: fora
        _linha("25/10/2026 14:59:59", voto),      # AC: 16:59:59 em Brasília
        _linha("25/10/2026 15:00:00", voto),      # 17:00:00
        _linha("25/10/2026 15:10:00", voto),      # 17:10:00
        _linha("25/10/2026 15:31:00", voto),      # 17:31
        _linha("25/10/2026 16:00:00", voto),      # 18:00
        _linha("25/10/2026 16:45:00", voto),      # 18:45
        _linha("25/10/2026 16:50:00", "Urna pronta para receber votos"),
    ])
    r = M.votos_por_corte_bsb(texto, "ac", "01007")
    assert r == {"apos_17h00": 5, "apos_17h10": 4, "apos_17h30": 3,
                 "apos_18h00": 2, "apos_18h30": 1}
    # em UTC-3 a hora local já é a de Brasília: nenhum voto depois das 17h
    r2 = M.votos_por_corte_bsb(texto, "ba", "38490")
    assert r2["apos_17h00"] == 0


def _df_secoes():
    linhas = []
    # estrato A: 2 tardias, 3 no horário; estrato B: 1 tardia, 0 controles
    for i, (g, mun) in enumerate([("tardia", "1"), ("tardia", "1"), ("no_horario", "1"),
                                  ("no_horario", "1"), ("no_horario", "1"),
                                  ("tardia", "2"), ("intermediaria", "1"),
                                  ("no_horario", "3")]):
        linhas.append({"uf": "ba", "cd_mun": mun, "zona": "0001", "secao": f"{i:04d}",
                       "grupo_t2": g})
    return pd.DataFrame(linhas)


def test_escolher_controles_mesmo_estrato_sem_reposicao():
    am = M.escolher_controles(_df_secoes(), frac_aleatoria=1.0)
    tard = am[am["papel"] == "tardia"]
    ctrl = am[am["papel"] == "controle"]
    assert len(tard) == 3
    assert len(ctrl) == 2                      # estrato B não tem controle
    assert set(ctrl["cd_mun"]) == {"1"}
    assert ctrl["secao"].is_unique
    assert (am["papel"] == "intermediaria").sum() == 1
    alea = am[am["papel"] == "aleatoria_horario"]
    assert len(alea) == 2                      # sobram 1 do estrato A e o do mun 3
    assert not set(alea["secao"]) & set(ctrl["secao"])
    # determinístico com a mesma semente
    am2 = M.escolher_controles(_df_secoes(), frac_aleatoria=1.0)
    assert am["secao"].tolist() == am2["secao"].tolist()


def test_did_estratos_efeito_constante():
    rng = np.random.default_rng(1)
    linhas = []
    for e in range(5):
        base = rng.normal(0, 3)
        for _j in range(20):
            linhas.append({"uf": "ba", "cd_mun": str(e), "zona": "1", "grupo_t2": "no_horario",
                           "d": base + rng.normal(0, 0.1)})
        for _j in range(4):
            linhas.append({"uf": "ba", "cd_mun": str(e), "zona": "1", "grupo_t2": "tardia",
                           "d": base + 2.0 + rng.normal(0, 0.1)})
    r = M.did_estratos(pd.DataFrame(linhas), "d", n_boot=300)
    assert r["estratos"] == 5 and r["tratadas"] == 20 and r["controles"] == 100
    assert r["estimativa"] == pytest.approx(2.0, abs=0.1)
    assert r["ic95"][0] < 2.0 < r["ic95"][1]


def test_did_sem_estrato_comum():
    df = pd.DataFrame([{"uf": "ba", "cd_mun": "1", "zona": "1", "grupo_t2": "tardia", "d": 1.0}])
    assert M.did_estratos(df, "d")["estimativa"] is None


def test_dif_medias():
    r = M.dif_medias([1, 2, 3, 4], [0, 1, 2, 3])
    assert r["diferenca"] == pytest.approx(1.0)
    assert r["ic95"][0] < 1.0 < r["ic95"][1]
    assert M.dif_medias([1], [2])["diferenca"] is None


def test_cenarios_impacto():
    am = pd.DataFrame([
        {"votos_apos_17h00": 10, "votos_13": 60, "votos_22": 40, "comparecimento": 100,
         "validos_t2": 100, "votos_13_t1": 50, "votos_22_t1": 50},
        {"votos_apos_17h00": 20, "votos_13": 30, "votos_22": 70, "comparecimento": 100,
         "validos_t2": 100, "votos_13_t1": 20, "votos_22_t1": 60},
    ])
    r = M.cenarios_impacto(am, 1000)
    assert r["votos_apos_17h"] == 30
    assert r["a_extremo_todos_para_um"]["desloca_ate"] == 30
    assert not r["a_extremo_todos_para_um"]["altera_resultado"]
    # (b) 10*0.2 + 20*(-0.4) = -6
    assert r["b_fatia_da_secao_no_t2"]["saldo_13_menos_22"] == pytest.approx(-6.0)
    # (c) 10*0 + 20*(-40/80) = -10
    assert r["c_fatia_da_secao_no_t1"]["saldo_13_menos_22"] == pytest.approx(-10.0)
    assert M.cenarios_impacto(am, 25)["a_extremo_todos_para_um"]["altera_resultado"]


def test_inverter():
    r = M._inverter(1000, 200.0, 50.0)
    assert r["margem_se_todos_retirados_do_13"] == 800
    assert r["margem_se_retirados_na_fatia_da_secao"] == 950
    assert r["necessarios_para_inverter_todos_do_13"] == 1001
    assert r["vezes_o_observado_todos_do_13"] == pytest.approx(5.0, abs=0.01)
    assert r["necessarios_para_inverter_na_fatia"] == 4004   # 1001 / 0.25
    assert not r["altera_resultado_todos_do_13"]
    # saldo negativo: retirar na fatia aumenta a margem do 13, nunca inverte
    assert M._inverter(1000, 200.0, -50.0)["necessarios_para_inverter_na_fatia"] is None


def test_residuos_estrato():
    linhas = [{"uf": "ba", "cd_mun": "1", "zona": "1", "grupo_t2": "no_horario",
               "d_pct13": float(v)} for v in (0, 1, 2, 3, 4)]
    linhas.append({"uf": "ba", "cd_mun": "1", "zona": "1", "grupo_t2": "tardia",
                   "d_pct13": 12.0})
    r = M.residuos_estrato(pd.DataFrame(linhas))
    assert len(r) == 1
    assert r["residuo"].iloc[0] == pytest.approx(10.0)
    assert r["z"].iloc[0] == pytest.approx(10.0 / np.std([0, 1, 2, 3, 4], ddof=1))


def test_cenario_descarte_estima_atrasadas_sem_log_pela_taxa_do_grupo():
    base = {"uf": "ba", "cd_mun": "1", "zona": "1"}
    df = pd.DataFrame([
        {**base, "secao": "A", "grupo_t2": "tardia", "comparecimento": 100,
         "votos_13": 60, "votos_22": 40, "votos_log_17h_t1": 50.0},
        {**base, "secao": "B", "grupo_t2": "tardia", "comparecimento": 200,
         "votos_13": 120, "votos_22": 80, "votos_log_17h_t1": 40.0},
        {**base, "secao": "C", "grupo_t2": "no_horario", "comparecimento": 100,
         "votos_13": 50, "votos_22": 50, "votos_log_17h_t1": 20.0},
        {**base, "secao": "D", "grupo_t2": "no_horario", "comparecimento": 100,
         "votos_13": 70, "votos_22": 30, "votos_log_17h_t1": 100.0},
        {**base, "secao": "E", "grupo_t2": "no_horario", "comparecimento": 100,
         "votos_13": 50, "votos_22": 50, "votos_log_17h_t1": 50.0},
    ])
    am = pd.DataFrame([
        {"chave": "ba/1/1/A", "votos_apos_17h00": 10, "papel": "tardia",
         "comparecimento": 100, "votos_log_17h_t1": 50.0},
        {"chave": "ba/1/1/C", "votos_apos_17h00": 1, "papel": "controle",
         "comparecimento": 100, "votos_log_17h_t1": 20.0},
        {"chave": "ba/1/1/D", "votos_apos_17h00": 2, "papel": "aleatoria_horario",
         "comparecimento": 100, "votos_log_17h_t1": 100.0},
    ])
    t1 = df[["uf", "cd_mun", "zona", "secao", "votos_13", "votos_22"]].assign(
        votos_log_17h=df["votos_log_17h_t1"])
    r = M.cenario_descarte(df, am, t1, 1000)
    assert r["taxa_atrasadas_apos_17h_log"]["tardia"] == pytest.approx(0.1)
    assert r["razao_t2_t1_fila_normal"] == pytest.approx(0.02)
    comp = r["componentes"]
    assert comp["exato_log"]["votos_apos_17h"] == pytest.approx(13.0)
    # B, tardia sem log: 200 x 0,1
    assert comp["estimado_atrasada_sem_log"]["votos_apos_17h"] == pytest.approx(20.0)
    # E, no horário sem log: 50 (1º turno) x 0,02
    assert comp["estimado_horario"]["votos_apos_17h"] == pytest.approx(1.0)
    assert r["corte_17h00"]["votos_retirados"] == pytest.approx(34.0)
    assert r["corte_17h00"]["saldo_13_menos_22_retirado_na_fatia"] == pytest.approx(6.8)
    assert r["corte_17h00_so_contagem_exata_do_log"]["votos_retirados"] == pytest.approx(13.0)
    # teto: B com o comparecimento inteiro (200) no lugar da estimativa (20)
    teto = r["teto_atrasadas_sem_log"]
    assert teto["secoes"] == 1 and teto["comparecimento"] == 200
    assert teto["votos_retirados"] == pytest.approx(214.0)
    assert teto["saldo_13_menos_22_retirado_na_fatia"] == pytest.approx(42.8)
    # sensibilidade: razão 2º/1º turno da tardia com log (10/50) aplicada a B (40)
    sens = r["sensibilidade_atrasadas_sem_log_razao_t1"]["tardia"]
    assert sens["razao_t2_t1"] == pytest.approx(0.2)
    assert sens["estimativa"] == pytest.approx(8.0)
