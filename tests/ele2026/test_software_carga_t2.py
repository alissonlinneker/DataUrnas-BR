"""Software e carga das urnas no 2º turno de 2026 (software_carga_t2.py), sem rede."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

RAIZ = Path(__file__).resolve().parents[2]
FIX = Path(__file__).parent / "fixtures"
BU_FIX = FIX / "bu_ac_m01066_z0004_s0077.bin"
VSC_FIX = FIX / "vsc_ac_m01066_z0004_s0077.bin"


@pytest.fixture(scope="module")
def sw():
    p = RAIZ / "scripts" / "ele2026" / "software_carga_t2.py"
    spec = importlib.util.spec_from_file_location("software_carga_t2", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _bu(**kw):
    base = {"uf": "ba", "cd_mun": "38490", "zona": "0001", "secao": "0001",
            "origem": "t2", "coletado_em": "2026-10-25T20:00:00-0300",
            "hash": "h1", "sha512": "s1",
            "versao_votacao": "10.23.0.0 - Praia da Barra do Cahy",
            "codigo_carga": "111", "qtd_codigos_carga": 1,
            "numero_interno_urna": 2046316, "tipo_urna": "secao",
            "fase": "oficial", "hora_encerramento": "20261025T170000", "bu_erro": None}
    base.update(kw)
    return base


def _vsc(**kw):
    base = {"uf": "ba", "cd_mun": "38490", "zona": "0001", "secao": "0001",
            "origem": "t2", "coletado_em": "2026-10-25T20:00:00-0300",
            "hash": "h1", "sha512": "v1", "tipo_assinatura": "vota",
            "modelo_vsc_cod": 20, "modelo_vsc": "UE2020",
            "cert_cn": "UEAO02046316", "cert_numero": 2046316, "cert_serial": "2d8fc",
            "cert_emissor": "AC UE2020", "cert_sha256": "ab", "assinatura_usuario":
            "UEAO02046316", "vsc_erro": None}
    base.update(kw)
    return base


# --- funções puras -----------------------------------------------------------

@pytest.mark.parametrize("cn,esperado", [
    ("UEAO02046316", 2046316), ("ueao00000001", 1), ("UEAO123", None),
    ("XYZ02046316", None), (None, None)])
def test_numero_de_cn(sw, cn, esperado):
    assert sw.numero_de_cn(cn) == esperado


def test_cn_de_dn(sw):
    dn = "L=Brasilia,OU=STI,O=TSE,C=BR,ST=DF,CN=AC UE2020"
    assert sw.cn_de_dn(dn) == "AC UE2020"
    assert sw.cn_de_dn(None) is None


@pytest.mark.parametrize("enc,minutos", [
    ("2026-10-25 17:31:00", 31.0), ("2026-10-25 16:59:00", -1.0),
    ("2026-10-25T19:00:00", 120.0), ("", None), (None, None), ("lixo", None)])
def test_minutos_apos_17h(sw, enc, minutos):
    assert sw.minutos_apos_17h(enc) == minutos


# --- extração com o parser do projeto ----------------------------------------

def test_extrair_bu_fixture(sw):
    d = sw.extrair_bu(BU_FIX.read_bytes())
    assert d["bu_erro"] is None
    assert d["versao_votacao"].startswith("10.23.0.0")
    assert isinstance(d["numero_interno_urna"], int)
    assert d["qtd_codigos_carga"] >= 1
    assert d["codigo_carga"]
    assert d["fase"] == "oficial"


def test_extrair_bu_ilegivel(sw):
    d = sw.extrair_bu(b"\x00\x01lixo")
    assert d["bu_erro"]


def test_extrair_vsc_fixture(sw):
    pytest.importorskip("cryptography")
    d = sw.extrair_vsc(bytearray(VSC_FIX.read_bytes()))
    assert d["vsc_erro"] is None
    assert d["modelo_vsc"] in {"UE2009", "UE2010", "UE2011", "UE2013", "UE2015",
                               "UE2020", "UE2022"}
    assert d["cert_numero"] == sw.numero_de_cn(d["cert_cn"])
    assert d["cert_emissor"].startswith("AC ")


def test_extrair_vsc_cn_bate_com_bu_da_mesma_secao(sw):
    pytest.importorskip("cryptography")
    b = sw.extrair_bu(BU_FIX.read_bytes())
    v = sw.extrair_vsc(VSC_FIX.read_bytes())
    assert v["cert_numero"] == b["numero_interno_urna"]


def test_extrair_vsc_erro_de_leitura(sw):
    def falha(_raw):
        raise ValueError("quebrado")
    d = sw.extrair_vsc(b"\x30\x00", info_fn=falha)
    assert d["vsc_erro"].startswith("ValueError")


# --- consolidação ------------------------------------------------------------

def test_consolidar_usa_ultima_versao_e_conta_mudancas(sw):
    bus = pd.DataFrame([
        _bu(sha512="s1", hash="h1", codigo_carga="111"),
        _bu(sha512="s2", hash="h2", codigo_carga="222",
            coletado_em="2026-10-25T21:00:00-0300"),
    ])
    vscs = pd.DataFrame([_vsc(hash="h1"), _vsc(hash="h2", sha512="v2",
                                               cert_numero=999, cert_cn="UEAO00000999")])
    df = sw.consolidar(bus, vscs)
    assert len(df) == 1
    r = df.iloc[0]
    assert r["codigo_carga"] == "222"
    assert r["n_versoes_bu"] == 2
    assert r["n_codigos_carga_versoes"] == 2
    assert r["n_versoes_software"] == 1
    assert r["vsc_mesmo_hash"] == True  # noqa: E712
    assert r["cn_difere_numero_interno"] == True  # noqa: E712


def test_consolidar_vsc_de_outra_versao_e_sem_vsc(sw):
    bus = pd.DataFrame([_bu(hash="h2"), _bu(secao="0002", numero_interno_urna=5)])
    vscs = pd.DataFrame([_vsc(hash="h1")])
    df = sw.consolidar(bus, vscs).set_index("secao")
    assert df.loc["0001", "vsc_mesmo_hash"] == False  # noqa: E712
    assert df.loc["0001", "modelo_vsc"] == "UE2020"
    assert df.loc["0001", "cn_difere_numero_interno"] == False  # noqa: E712
    assert df.loc["0002", "vsc_mesmo_hash"] is None
    assert df.loc["0002", "cn_difere_numero_interno"] is None


def test_consolidar_sem_assinaturas(sw):
    df = sw.consolidar(pd.DataFrame([_bu()]), pd.DataFrame())
    assert df.iloc[0]["cn_difere_numero_interno"] is None


def test_juntar_encerramento_coluna_pronta_e_calculada(sw):
    df = sw.consolidar(pd.DataFrame([_bu(), _bu(secao="0002")]), pd.DataFrame())
    enc = pd.DataFrame([{"uf": "ba", "cd_mun": "38490", "zona": "0001", "secao": "0001",
                         "minutos_apos_17h_bsb": 45.0},
                        {"uf": "ba", "cd_mun": "38490", "zona": "0001", "secao": "0002",
                         "minutos_apos_17h_bsb": 30.0}])
    out = sw.juntar_encerramento(df, enc).set_index("secao")
    assert out.loc["0001", "tardia"] == True  # noqa: E712
    assert out.loc["0002", "tardia"] == False  # noqa: E712  (17:30 exato não é tardia)
    enc2 = enc.drop(columns="minutos_apos_17h_bsb").assign(
        encerramento_bsb=["2026-10-25 18:10:00", "2026-10-25 17:05:00"])
    out2 = sw.juntar_encerramento(df, enc2).set_index("secao")
    assert out2.loc["0001", "minutos_apos_17h_bsb"] == 70.0
    assert out2.loc["0002", "tardia"] == False  # noqa: E712


def test_juntar_t1(sw):
    df = sw.consolidar(pd.DataFrame([_bu(), _bu(secao="0002"), _bu(secao="0003")]),
                       pd.DataFrame())
    t1 = pd.DataFrame([
        {"uf": "ba", "cd_mun": "38490", "zona": "0001", "secao": "0001",
         "numero_interno_urna": 2046316, "versao_votacao": "10.23.0.0 - Praia da Barra do Cahy",
         "codigo_carga": "111", "tipo_urna": "secao", "modelo_urna": "UE2020"},
        {"uf": "ba", "cd_mun": "38490", "zona": "0001", "secao": "0002",
         "numero_interno_urna": 1, "versao_votacao": "x", "codigo_carga": "9",
         "tipo_urna": "secao", "modelo_urna": "UE2020"}])
    out = sw.juntar_t1(df, t1).set_index("secao")
    assert out.loc["0001", "mesma_urna_t1"] == True  # noqa: E712
    assert out.loc["0002", "mesma_urna_t1"] == False  # noqa: E712
    assert out.loc["0003", "mesma_urna_t1"] is None


# --- resumo ------------------------------------------------------------------

def _df_resumo(sw):
    bus = pd.DataFrame([
        _bu(),
        _bu(secao="0002", qtd_codigos_carga=2, codigo_carga="333",
            tipo_urna="reservaSecao", numero_interno_urna=7),
        _bu(secao="0003", versao_votacao="9.9.9.9 - Outra", codigo_carga="111"),
    ])
    vscs = pd.DataFrame([_vsc(), _vsc(secao="0002", cert_numero=8, cert_cn="UEAO00000008")])
    df = sw.consolidar(bus, vscs)
    enc = pd.DataFrame([{"uf": "ba", "cd_mun": "38490", "zona": "0001", "secao": s,
                         "minutos_apos_17h_bsb": m}
                        for s, m in [("0001", 5.0), ("0002", 90.0), ("0003", 31.0)]])
    df = sw.juntar_encerramento(df, enc)
    t1 = pd.DataFrame([{"uf": "ba", "cd_mun": "38490", "zona": "0001", "secao": "0001",
                        "numero_interno_urna": 2046316,
                        "versao_votacao": "10.23.0.0 - Praia da Barra do Cahy",
                        "codigo_carga": "111", "tipo_urna": "secao",
                        "modelo_urna": "UE2020"}])
    return sw.juntar_t1(df, t1)


def test_resumir(sw):
    r = sw.resumir(_df_resumo(sw))
    assert r["secoes"] == 3
    assert r["versao_modal"].startswith("10.23.0.0")
    assert r["secoes_versao_diferente_da_modal"]["n"] == 1
    assert r["secoes_mais_de_um_codigo_carga"]["n"] == 1
    assert r["codigo_carga_em_mais_de_uma_secao"] == {
        "codigos": 1, "secoes": 2, "exemplos": r["codigo_carga_em_mais_de_uma_secao"]["exemplos"]}
    assert r["cn_x_numero_interno"]["comparadas"] == 2
    assert r["cn_x_numero_interno"]["divergentes"] == 1
    assert r["cn_x_numero_interno"]["divergentes_por_tipo_urna"] == {"reservaSecao": 1}
    assert r["comparacao_t1"]["mesma_urna"] == 1
    assert r["comparacao_t1"]["codigo_carga_igual_t1"] == 1
    assert r["comparacao_t1"]["mesma_urna_codigo_carga_diferente"] == 0
    json.dumps(r)  # serializável


def test_montar_resumo_recorte_tardias(sw):
    out = sw.montar_resumo(_df_resumo(sw), {"parcial": True})
    rec = out["recorte_encerramento"]
    assert rec["tardias"]["secoes"] == 2
    assert rec["demais"]["secoes"] == 1
    assert rec["tardias_por_uf"] == {"ba": 2}
    json.dumps(out, default=str)


def test_resumir_vazio(sw):
    assert sw.resumir(pd.DataFrame()) == {"secoes": 0}


# --- ponta a ponta com parquet sintético --------------------------------------

def _parte(path: Path, linhas: list[dict]) -> None:
    cols = ["coletado_em", "uf", "cd_mun", "zona", "secao", "tipo", "hash", "st_secao",
            "sha512", "conteudo"]
    tb = pa.table({c: [r.get(c) for r in linhas] for c in cols},
                  schema=pa.schema([(c, pa.binary() if c == "conteudo" else pa.string())
                                    for c in cols]))
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(tb, path)


def test_main_ponta_a_ponta(sw, tmp_path):
    pytest.importorskip("cryptography")
    ident = {"uf": "ac", "cd_mun": "01066", "zona": "0004", "secao": "0077",
             "coletado_em": "2026-10-25T20:00:00-0300", "hash": "h1", "st_secao": "Recebida"}
    d1 = tmp_path / "t2" / "bus" / "parts"
    d2 = tmp_path / "t2-sseco" / "bus" / "parts"
    _parte(d1 / "versoes-1.parquet", [
        {**ident, "tipo": "bu", "sha512": "a", "conteudo": BU_FIX.read_bytes()},
        {**ident, "tipo": "vota", "sha512": "b", "conteudo": VSC_FIX.read_bytes()},
        {**ident, "tipo": "aux", "sha512": "c", "conteudo": b"{}"},
    ])
    _parte(d2 / "versoes-1.parquet", [
        {**ident, "secao": "0078", "tipo": "bu", "sha512": "d", "conteudo": b"ruim"},
    ])
    (d2 / "versoes-2.parquet").write_bytes(b"incompleto")
    saida = tmp_path / "out"
    rc = sw.main(["--dir", str(d1), "--dir", str(d2), "--saida", str(saida),
                  "--encerramento", str(tmp_path / "nao_existe.parquet"),
                  "--t1", str(tmp_path / "nao_existe.parquet")])
    assert rc == 0
    df = pd.read_parquet(saida / "secoes_software.parquet")
    assert len(df) == 2
    ok = df[df["secao"] == "0077"].iloc[0]
    assert ok["origem"] == "t2"
    assert ok["cn_difere_numero_interno"] == False  # noqa: E712
    res = json.loads((saida / "resumo.json").read_text(encoding="utf-8"))
    assert res["bus_lidos"] == 2
    assert res["todas"]["bu_ilegivel"] == 1
    assert len(res["partes_com_erro"]) == 1
    assert "recorte_encerramento" not in res


def test_main_sem_partes(sw, tmp_path):
    assert sw.main(["--dir", str(tmp_path), "--saida", str(tmp_path / "o")]) == 1
