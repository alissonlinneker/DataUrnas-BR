"""Carregadores de 2026 contra os arquivos reais e com coleta parcial sintética."""

import json
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from dataurnas.dashboard import data2026 as d26  # noqa: E402

REAL = d26.base_dir()
tem_dados_reais = pytest.mark.skipif(
    not (REAL / "resultado_uf.parquet").exists(), reason="data/parquet/2026 ausente"
)


@tem_dados_reais
def test_resultado_oficial_real_consistente():
    resumo = d26.load_resumo()
    cand = d26.load_candidatos()
    res_uf = d26.load_resultado_uf()
    res_mun = d26.load_resultado_municipio()

    assert resumo["cargo"] == "Presidente" and resumo["turno"] == 1
    assert cand["votos"].is_monotonic_decreasing
    assert {"rotulo", "numero", "pct_validos"} <= set(cand.columns)
    # colunas v_<numero> de todos os candidatos
    assert {f"v_{int(n)}" for n in cand["numero"]} == set(d26.vote_columns(res_uf))
    # somas por UF e por município batem com o total nacional
    total = resumo["totais"]["votos_validos"]
    assert int(res_uf["votos_validos"].sum()) == total
    assert int(res_mun["votos_validos"].sum()) == total
    assert int(res_uf[d26.vote_columns(res_uf)].sum().sum()) == total


@tem_dados_reais
def test_add_leader_real():
    cand = d26.load_candidatos()
    uf = d26.add_leader(d26.load_resultado_uf(), cand)
    assert uf["lider"].notna().all()
    assert ((uf["pct_lider"] > 0) & (uf["pct_lider"] <= 100)).all()
    assert (uf["margem_pp"] >= 0).all()
    linha = uf.iloc[0]
    maior = max(d26.vote_columns(uf), key=lambda c: linha[c])
    assert linha["lider_numero"] == int(maior[2:])


@tem_dados_reais
def test_secoes_reais_parciais_ou_ausentes():
    dados = d26.load_secoes()
    res_uf = d26.load_resultado_uf()
    cov = d26.coverage_by_uf(dados.secoes, res_uf)
    assert len(cov) == len(res_uf)
    assert 0.0 <= d26.overall_coverage(cov) <= 100.0
    if dados.vazio:
        return
    # sem duplicatas de seção após unir lotes e consolidado
    assert not dados.secoes.duplicated(d26.CHAVE_SECAO).any()
    rec = d26.reconcile_by_uf(dados.secoes, dados.votos, res_uf, d26.load_candidatos())
    resumo = d26.reconcile_summary(rec)
    # toda UF com coleta completa precisa conferir exatamente com o TSE
    completas = resumo[resumo["completa"]]
    assert (completas["situacao"] == "Confere").all(), completas


@tem_dados_reais
def test_comparacao_2022_real():
    t1 = d26.load_2022_t1_by_uf()
    if t1.empty:
        pytest.skip("Parquet de 2022 ausente")
    comp = d26.compare_2022_2026(d26.load_resultado_uf(), t1)
    assert len(comp) >= 27
    assert comp["comparecimento_pct_2022"].between(50, 100).all()
    assert comp["comparecimento_pct_2026"].between(30, 100).all()


@tem_dados_reais
def test_benford_real():
    dados = d26.load_secoes()
    if dados.vazio:
        pytest.skip("coleta de seções ainda não iniciada")
    bf = d26.benford_first_digit(dados.votos, [int(n) for n in d26.load_candidatos()["numero"].head(2)])
    assert set(bf["digito"]) <= set(range(1, 10))
    for _, g in bf.groupby("numero"):
        assert abs(g["observado_pct"].sum() - 100) < 1e-6


# ----------------------------------------------------------------------
# Coleta parcial sintética (lotes + consolidado + arquivo em gravação)
# ----------------------------------------------------------------------
def _secao(uf, sec, comp, lote=None, status="ok"):
    row = {"uf": uf, "cd_mun": "00001", "zona": "0001", "secao": sec, "status": status,
           "comparecimento": float(comp), "votos_brancos": 1.0, "votos_nulos": 1.0,
           "votos_nominais": float(comp - 2), "modelo_urna": "UE2020",
           "hora_abertura": "20261004T080000", "hora_encerramento": "20261004T170000"}
    if lote is not None:
        row["_lote"] = lote
    return row


def _voto(uf, sec, numero, votos, lote=None):
    row = {"uf": uf, "cd_mun": "00001", "zona": "0001", "secao": sec, "tipo_voto": "nominal",
           "numero": numero, "partido": numero, "votos": votos}
    if lote is not None:
        row["_lote"] = lote
    return row


def test_load_secoes_sem_arquivos(tmp_path):
    dados = d26.load_secoes(tmp_path)
    assert dados.vazio and dados.arquivos == 0
    cov = d26.coverage_by_uf(dados.secoes, pd.DataFrame(
        {"uf": ["ac"], "secoes_total": [2], "secoes_instaladas": [2]}))
    assert cov.loc[0, "com_bu"] == 0 and cov.loc[0, "cobertura_pct"] == 0


def test_load_secoes_lotes_e_consolidado(tmp_path):
    parts = tmp_path / "secoes_parts"
    parts.mkdir()
    # consolidado antigo com a seção 0001 (será substituída pelo lote mais novo)
    pd.DataFrame([_secao("ac", "0001", 50)]).to_parquet(tmp_path / "secoes_2026.parquet")
    pd.DataFrame([_voto("ac", "0001", 13, 48)]).to_parquet(tmp_path / "votos_presidente_2026.parquet")
    pd.DataFrame([_secao("ac", "0001", 100, "L2"), _secao("ac", "0002", 80, "L2")]).to_parquet(
        parts / "secoes-L2.parquet")
    pd.DataFrame([_voto("ac", "0001", 13, 60, "L2"), _voto("ac", "0001", 22, 38, "L2"),
                  _voto("ac", "0002", 13, 78, "L2")]).to_parquet(parts / "votos-L2.parquet")
    (parts / "secoes-L3.parquet").write_bytes(b"PAR1 em gravacao")  # ilegível: ignorado

    dados = d26.load_secoes(tmp_path)
    assert dados.ignorados == 1
    assert len(dados.secoes) == 2
    s1 = dados.secoes.set_index("secao").loc["0001"]
    assert s1["comparecimento"] == 100  # lote mais recente vence o consolidado
    assert int(dados.votos["votos"].sum()) == 60 + 38 + 78  # votos do consolidado descartados

    res_uf = pd.DataFrame([{
        "uf": "ac", "secoes_total": 2, "secoes_instaladas": 2, "comparecimento": 180,
        "votos_brancos": 2, "votos_nulos": 2, "votos_nulos_tecnicos": 0, "votos_nominais": 176,
        "v_13": 138, "v_22": 38,
    }])
    cand = pd.DataFrame({"numero": [13, 22], "rotulo": ["A (X)", "B (Y)"]})
    rec = d26.reconcile_by_uf(dados.secoes, dados.votos, res_uf, cand)
    assert rec["confere"].all()
    assert d26.reconcile_summary(rec).loc[0, "situacao"] == "Confere"
    cov = d26.coverage_by_uf(dados.secoes, res_uf)
    assert cov.loc[0, "completa"] and cov.loc[0, "cobertura_pct"] == 100


def test_reconcile_coleta_parcial_e_nulo_tecnico(tmp_path):
    secoes = pd.DataFrame([_secao("ac", "0001", 10)])
    votos = pd.DataFrame([_voto("ac", "0001", 13, 5), _voto("ac", "0001", 99, 3)])  # 99 não é candidato
    res_uf = pd.DataFrame([{
        "uf": "ac", "secoes_total": 2, "secoes_instaladas": 2, "comparecimento": 20,
        "votos_brancos": 2, "votos_nulos": 2, "votos_nulos_tecnicos": 3, "votos_nominais": 12,
        "v_13": 12,
    }])
    rec = d26.reconcile_by_uf(secoes, votos, res_uf, pd.DataFrame({"numero": [13]}))
    item = rec.set_index("item")
    assert item.loc["Nulos técnicos", "soma_bu"] == 3
    assert item.loc["Nominais válidos", "soma_bu"] == 5
    assert d26.reconcile_summary(rec).loc[0, "situacao"] == "Coleta parcial"


def test_files_signature_muda_com_novo_lote(tmp_path):
    antes = d26.files_signature(tmp_path)
    (tmp_path / "resumo_br.json").write_text(json.dumps({"a": 1}), encoding="utf-8")
    assert d26.files_signature(tmp_path) != antes


def test_parse_hora():
    h = d26.parse_hora(pd.Series(["20261004T080512", "invalido", None]))
    assert h.iloc[0].hour == 8 and h.iloc[0].minute == 5
    assert pd.isna(h.iloc[1]) and pd.isna(h.iloc[2])
