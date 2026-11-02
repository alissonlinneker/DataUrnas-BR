"""Auditoria de certificados e assinaturas do 2º turno (certificados_t2.py), sem rede.

Usa o BU e o .vsc reais de uma seção (fixtures) gravados numa parte no
formato do versionamento do 2º turno, mais uma seção com o BU alterado.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("cryptography")

RAIZ = Path(__file__).resolve().parents[2]
FIX = Path(__file__).parent / "fixtures"
VSC = FIX / "vsc_ac_m01066_z0004_s0077.bin"
BU = FIX / "bu_ac_m01066_z0004_s0077.bin"
AC_DIR = RAIZ / "data" / "certificados" / "ac"
NOME_BU = "o03220ac0106600040077-bu.dat"
PROIBIDOS = (chr(0x2014), chr(0x2013))


@pytest.fixture(scope="module")
def ct():
    p = RAIZ / "scripts" / "ele2026" / "certificados_t2.py"
    spec = importlib.util.spec_from_file_location("certificados_t2_teste", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _linha(secao, tipo, nome, raw, hash_="h1"):
    return {"coletado_em": "2026-10-25T20:00:00-0300", "uf": "ac", "cd_mun": "01066",
            "zona": "0004", "secao": secao, "tipo": tipo, "hash": hash_, "st_secao": "x",
            "st_hash": "Recebido", "dt_recebimento": None, "hr_recebimento": None,
            "nome": nome, "sha512": hashlib.sha512(raw).hexdigest(),
            "tamanho": len(raw), "conteudo": raw}


@pytest.fixture()
def versoes(tmp_path):
    d = tmp_path / "t2" / "bus" / "parts"
    d.mkdir(parents=True)
    vsc, bu = VSC.read_bytes(), BU.read_bytes()
    alterado = bytearray(bu)
    alterado[-1] ^= 0x01
    linhas = [
        _linha("0077", "bu", NOME_BU, bu),
        _linha("0077", "vota", "o03220ac0106600040077-vota.vsc", vsc),
        _linha("0077", "aux", None, b"{}"),
        _linha("0078", "bu", NOME_BU, bytes(alterado)),
        _linha("0078", "vota", "o03220ac0106600040077-vota.vsc", vsc),
        _linha("0079", "bu", NOME_BU, bu),  # BU ainda sem .vsc
    ]
    pd.DataFrame(linhas).to_parquet(d / "versoes-20261025-1-00001.parquet", index=False)
    # parte de votos (outro esquema) deve ser ignorada
    pd.DataFrame([{"uf": "ac", "cd_mun": "01066", "zona": "0004", "secao": "0077",
                   "votos": 1}]).to_parquet(d / "versoes-20261025-1-00002.parquet")
    return d


def _t1(tmp_path, cert_sha):
    cat = tmp_path / "t1_secoes.parquet"
    pd.DataFrame([{"uf": "ac", "cd_mun": "01066", "zona": "0004", "secao": "0077",
                   "cert_sha256": cert_sha, "cert_subject": "O=TSE,C=BR,CN=UEAO02293919",
                   "cert_issuer": "C=BR,CN=AC UE2022", "cert_serial": "1",
                   "assinatura_valida": True, "assinatura_algoritmo": "Ed521",
                   "modelo_urna": "UE2022"}]).to_parquet(cat)
    bu = tmp_path / "t1_bu.parquet"
    pd.DataFrame([{"uf": "ac", "cd_mun": "01066", "zona": "0004", "secao": "0077",
                   "numero_interno_urna": 2293919}]).to_parquet(bu)
    enc = tmp_path / "enc.parquet"
    pd.DataFrame([{"uf": "ac", "cd_mun": "01066", "zona": "0004", "secao": s,
                   "minutos_apos_17h_bsb": m, "encerramento_bsb": "x", "faixa": "f"}
                  for s, m in (("0077", 45.0), ("0078", 5.0))]).to_parquet(enc)
    return cat, bu, enc


def test_listar_partes_ignora_partes_de_votos(ct, versoes):
    partes = ct.listar_partes([("t2", versoes)])
    assert [p.name for _, p in partes] == ["versoes-20261025-1-00001.parquet"]


def test_dirs_rotulos(ct, tmp_path):
    a, b = tmp_path / "x" / "bus" / "parts", tmp_path / "y" / "bus" / "parts"
    assert ct._dirs([str(a), f"londres={b}"]) == [("x", a), ("londres", b)]
    assert ct._dirs([str(a), str(a)])[1][0] == "x2"


def test_extrair_campos_do_vsc_e_do_bu(ct, versoes):
    vscs, bus = ct.extrair_parte("t2", str(versoes / "versoes-20261025-1-00001.parquet"))
    assert len(vscs) == 2 and len(bus) == 3
    v = vscs[0]
    assert "erro" not in v
    assert v["modelo"] == "UE2022" and v["emissor"] == "AC UE2022"
    assert v["alg_chave"] == "Ed521" and v["curva"] == "E-521"
    assert v["hw_conteudo_ok"] and v["sw_conteudo_ok"] and v["sw_hw_hashes_iguais"]
    assert v["bu_nome_vsc"] == NOME_BU and v["cn_confere_usuario"]
    assert v["extensoes_incomuns"] is None and v["basic_ca"] is False
    assert v["sha512_coleta_confere"] is True
    b = bus[0]
    assert b["numero_interno"] == 2293919 and b["sha512_coleta_confere"] is True
    assert b["data_hora_carga"] and b["tipo_urna"]


def test_verificar_linha_assinatura_e_cadeia(ct, versoes):
    ct._ACS.clear()
    ct._init_acs(str(AC_DIR))
    vscs, _ = ct.extrair_parte("t2", str(versoes / "versoes-20261025-1-00001.parquet"))
    r = ct.verificar_linha(vscs[0], todas_fracao=1)
    assert r["assinatura_conteudo_ok"] is True and r["assinatura_bu_ok"] is True
    assert r["todas_verificadas"] is True and r["n_assinaturas_falha"] == 0
    assert r["n_assinaturas_ok"] == len(vscs[0]["arq_nomes"])
    assert r["cadeia_ok"] is True and r["ac_cn"] == "AC UE2022"
    adulterada = dict(vscs[0])
    sig = bytearray(adulterada["hw_assinatura"])
    sig[10] ^= 0xFF
    adulterada["hw_assinatura"] = bytes(sig)
    assert ct.verificar_linha(adulterada)["assinatura_conteudo_ok"] is False
    s = bytearray(adulterada["arq_assinaturas"][0])
    s[5] ^= 0xFF
    adulterada["arq_assinaturas"] = [bytes(s)] + list(adulterada["arq_assinaturas"][1:])
    r2 = ct.verificar_linha(adulterada)
    assert r2["assinatura_bu_ok"] is False and r2["arquivos_assinatura_invalida"] == NOME_BU


def test_tudo_ponta_a_ponta(ct, versoes, tmp_path):
    saida = tmp_path / "saida"
    ct._ACS.clear()
    assert ct.extrair([("t2", versoes)], saida, 0, log=lambda *_: None)["vsc"] == 2
    assert ct.verificar(saida, AC_DIR, 0, 1.0, log=lambda *_: None)["linhas"] == 2
    cert_sha = ct.extrair_parte("t2", str(versoes / "versoes-20261025-1-00001.parquet"))[0][0][
        "cert_sha256"]
    cat, bu, enc = _t1(tmp_path, cert_sha)
    rel = tmp_path / "rel.md"
    res = ct.analisar(saida, enc, cat, bu, AC_DIR, rel, {}, log=lambda *_: None)
    c, v = res["cobertura"], res["verificacoes"]
    assert c["secoes"] == 3 and c["par_bu_vsc"] == 2 and c["bu_sem_vsc"] == 1
    assert v["bu_hash_confere"] == {"True": 1, "False": 1}
    assert v["assinatura_conteudo_ok"] == {"True": 2} and v["cadeia_ok"] == {"True": 2}
    assert v["cn_igual_numero_interno"] == {"True": 2}
    assert [s["secao_id"] for s in res["falhas"]["bu_hash_diverge"]["secoes"]] == \
        ["AC/01066/0004/0078"]
    assert res["falhas"]["assinatura_bu_invalida"]["n"] == 0
    tt = res["padroes"]["tarde_x_demais"]
    assert tt["secoes_tarde"] == 1 and tt["secoes_demais"] == 1
    tu = res["padroes"]["turnos"]
    assert tu["secoes_comparadas"] == 1 and tu["mesmo_certificado"] == 1
    # 0078 usa o mesmo .vsc: mesmo certificado em duas seções
    assert res["padroes"]["certificado_em_mais_de_uma_secao"]["secoes"] == 2
    df = pd.read_parquet(saida / "secoes.parquet")
    assert len(df) == 3 and int(df["fechou_tarde"].fillna(False).sum()) == 1
    assert json.loads((saida / "resumo.json").read_text(encoding="utf-8"))["pleito"] == "3221"
    md = rel.read_text(encoding="utf-8")
    assert "Atenção" in md and "`AC/01066/0004/0078`" in md
    assert not any(ch in md for ch in PROIBIDOS)
    # segunda execução: nada a refazer
    assert ct.extrair([("t2", versoes)], saida, 0, log=lambda *_: None)["processadas"] == 0
    assert ct.verificar(saida, AC_DIR, 0, 1.0, log=lambda *_: None)["processados"] == 0


def test_sorteio_deterministico(ct):
    a = ct.sorteio("ac", "01066", "0004", "0077")
    assert a == ct.sorteio("ac", "01066", "0004", "0077") and 0 <= a < 1
