"""Encerramento das seções no 2º turno de 2026: fusos, conversão e faixas."""

from __future__ import annotations

import importlib.util
from datetime import datetime
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]


def _carregar():
    p = RAIZ / "scripts" / "ele2026" / "analisar_encerramento_t2.py"
    spec = importlib.util.spec_from_file_location("analisar_encerramento_t2", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


M = _carregar()


@pytest.mark.parametrize("uf,cd,esperado", [
    ("ac", "01066", -5),     # Acre inteiro
    ("am", "02550", -4),     # Manaus
    ("am", "98477", -5),     # Tabatinga
    ("am", "02291", -5),     # Eirunepé
    ("am", "02151", -4),     # Boca do Acre
    ("mt", "90670", -4),
    ("ms", "90514", -4),
    ("ro", "00035", -4),
    ("rr", "03018", -4),
    ("pe", "30015", -2),     # Fernando de Noronha
    ("pe", "25313", -3),     # Recife
    ("ba", "38490", -3),     # Salvador
    ("pa", "04200", -3),     # Pará inteiro em UTC-3
    ("SP", "71072", -3),     # UF em maiúscula
])
def test_fuso_utc(uf, cd, esperado):
    assert M.fuso_utc(uf, cd) == esperado


def test_fuso_exterior_nao_convertido():
    assert M.fuso_utc("zz", "29254") is None
    local = datetime(2026, 10, 25, 17, 0)
    assert M.para_brasilia(local, None) is None


def test_codigo_sem_zeros_a_esquerda():
    assert M.fuso_utc("am", "2020") == -5


@pytest.mark.parametrize("hora_local,utc,hora_bsb", [
    ("20261025T150612", -5, "2026-10-25 17:06:12"),
    ("20261025T160000", -4, "2026-10-25 17:00:00"),
    ("20261025T170000", -3, "2026-10-25 17:00:00"),
    ("20261025T180000", -2, "2026-10-25 17:00:00"),
    ("20261025T230500", -3, "2026-10-25 23:05:00"),
    ("20261025T230500", -2, "2026-10-25 22:05:00"),
    ("20261025T223000", -5, "2026-10-26 00:30:00"),   # vira o dia
])
def test_para_brasilia(hora_local, utc, hora_bsb):
    bsb = M.para_brasilia(M.parse_hora_urna(hora_local), utc)
    assert M.fmt(bsb) == hora_bsb


def test_parse_hora_urna_invalida():
    assert M.parse_hora_urna(None) is None
    assert M.parse_hora_urna("") is None
    assert M.parse_hora_urna("lixo") is None


def _bsb(hms: str) -> datetime:
    return datetime.strptime(f"20261025 {hms}", "%Y%m%d %H:%M:%S")


@pytest.mark.parametrize("hms,faixa", [
    ("16:59:59", "ate_17h10"),
    ("17:00:00", "ate_17h10"),
    ("17:10:59", "ate_17h10"),
    ("17:11:00", "17h11_17h30"),
    ("17:30:59", "17h11_17h30"),
    ("17:31:00", "17h31_18h00"),
    ("18:00:59", "17h31_18h00"),
    ("18:01:00", "18h01_19h00"),
    ("19:00:59", "18h01_19h00"),
    ("19:01:00", "depois_19h00"),
    ("21:15:00", "depois_19h00"),
])
def test_faixas(hms, faixa):
    assert M.faixa_encerramento(_bsb(hms)) == faixa


def test_faixa_sem_horario():
    assert M.faixa_encerramento(None) is None
    assert M.grupo_horario(None) == "sem_horario"


def test_grupos():
    assert M.grupo_horario("ate_17h10") == "no_horario"
    assert M.grupo_horario("17h11_17h30") == "intermediario"
    for f in ("17h31_18h00", "18h01_19h00", "depois_19h00"):
        assert M.grupo_horario(f) == "tarde"


def test_minutos_apos_17h():
    assert M.minutos_apos_17h(_bsb("17:00:00")) == 0
    assert M.minutos_apos_17h(_bsb("18:30:30")) == 90.5
    assert M.minutos_apos_17h(_bsb("16:58:00")) == -2
    assert M.minutos_apos_17h(None) is None


def _campos(**kw):
    base = {"hora_abertura": "20261025T080001", "hora_encerramento": "20261025T150612",
            "data_hora_emissao": "20261025T151111", "tipo_urna": "secao",
            "aptos": 285, "comparecimento": 193, "votos_brancos": 5, "votos_nulos": 9,
            "votos_total": 193, "tem_presidente": True}
    base.update(kw)
    return base


VOTOS = [{"tipo_voto": "nominal", "numero": 13, "votos": 102},
         {"tipo_voto": "nominal", "numero": 22, "votos": 77},
         {"tipo_voto": "branco", "numero": None, "votos": 5},
         {"tipo_voto": "nulo", "numero": None, "votos": 9}]


def _reg(**kw):
    base = {"uf": "ac", "cd_mun": "01066", "zona": "0004", "secao": "0164", "tipo": "bu",
            "nome": "x-bu.dat", "hash": "h1", "sha512": "s1",
            "coletado_em": "2026-10-25T19:39:53-0300", "dt_recebimento": "25/10/2026",
            "hr_recebimento": "19:32:29"}
    base.update(kw)
    return base


def test_montar_linha_acre():
    ln = M.montar_linha(_reg(), _campos(), VOTOS, None, {"01066": "RIO BRANCO"})
    assert ln["fuso_utc"] == -5
    assert M.fmt(ln["encerramento_bsb_dt"]) == "2026-10-25 17:06:12"
    assert ln["faixa"] == "ate_17h10"
    assert ln["votos_13"] == 102 and ln["votos_22"] == 77
    assert ln["municipio"] == "RIO BRANCO"
    assert ln["inconsistencias"] == ""
    out = M.finalizar(ln)
    assert out["encerramento_local"] == "2026-10-25 15:06:12"
    assert out["encerramento_bsb"] == "2026-10-25 17:06:12"


def test_inconsistencias_apontadas():
    c = _campos(hora_encerramento="20261025T070000", comparecimento=300, votos_total=290)
    ln = M.montar_linha(_reg(hr_recebimento="09:00:00"), c, VOTOS, None, {})
    inc = ln["inconsistencias"].split(",")
    assert "encerramento_antes_abertura" in inc
    assert "comparecimento_maior_que_aptos" in inc
    assert "soma_votos_difere_comparecimento" in inc
    assert "recebimento_antes_emissao" in inc


def test_bu_ilegivel_nao_some():
    ln = M.montar_linha(_reg(), None, None, "ValueError: x", {})
    assert ln["inconsistencias"] == "bu_ilegivel"
    assert ln["faixa"] is None


def test_deduplicar_mesmo_bu_em_dois_diretorios_e_versoes():
    a = M.montar_linha(_reg(), _campos(), VOTOS, None, {})
    a_copia = M.montar_linha(_reg(coletado_em="2026-10-25T20:00:00-0300"),
                             _campos(), VOTOS, None, {})
    b = M.montar_linha(_reg(sha512="s2", hash="h2", coletado_em="2026-10-25T21:00:00-0300"),
                       _campos(hora_encerramento="20261025T170000"), VOTOS, None, {})
    outra = M.montar_linha(_reg(secao="0165"), _campos(), VOTOS, None, {})
    principal, multiplas = M.deduplicar([a, a_copia, b, outra])
    assert len(principal) == 2
    sec = next(p for p in principal if p["secao"] == "0164")
    assert sec["n_versoes_bu"] == 2 and sec["sha512"] == "s2"
    assert [m["versao"] for m in multiplas] == [1, 2]
    assert multiplas[0]["coletado_em"] == "2026-10-25T19:39:53-0300"


def test_verificar_fusos_acusa_mediana_fora():
    ok = [{"uf": "ac", "cd_mun": "1", "minutos_apos_17h_bsb": 2.0}] * 5
    ruim = [{"uf": "am", "cd_mun": "2", "minutos_apos_17h_bsb": -58.0}] * 5
    alertas = M.verificar_fusos(ok + ruim)
    assert [a["cd_mun"] for a in alertas] == ["2"]
