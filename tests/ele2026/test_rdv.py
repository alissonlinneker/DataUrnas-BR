"""Testes da recontagem do RDV e da linha do tempo do log (sem rede).

Fixtures reais do 1º turno de 2026, mesma seção AC 01066/0004/0077:
  - rdv_ac_m01066_z0004_s0077.bin  -rdv.dat (EntidadeResultadoRDV, spec v2)
  - bu_ac_m01066_z0004_s0077.bin   -bu.dat do mesmo conjunto de arquivos
"""

import importlib.util
import io
import json
import zipfile
from collections import Counter
from pathlib import Path

import pytest

from dataurnas.analyzer import rdv_recontagem as R
from dataurnas.parsers.bu import BUParser
from dataurnas.parsers.rdv import (
    CargoRDV,
    RDVParseError,
    parse_rdv_bytes,
    recontar,
    validar,
)

FIX = Path(__file__).parent / "fixtures"
RDV_AC = FIX / "rdv_ac_m01066_z0004_s0077.bin"
BU_AC = FIX / "bu_ac_m01066_z0004_s0077.bin"
IDENT = {"uf": "ac", "cd_mun": "01066", "zona": "0004", "secao": "0077"}


@pytest.fixture(scope="module")
def rdv_raw() -> bytes:
    return RDV_AC.read_bytes()


@pytest.fixture(scope="module")
def rdv(rdv_raw):
    return parse_rdv_bytes(rdv_raw)


@pytest.fixture(scope="module")
def bu_cont():
    return R.contagens_bu(BUParser().parse_bytes(BU_AC.read_bytes()))


# ---------------------------------------------------------------- parser

def test_fixture_pequena(rdv_raw):
    assert len(rdv_raw) < 100 * 1024


def test_cabecalho_e_identificacao(rdv):
    assert rdv.pleito == 3220
    assert rdv.id_pleito_cabecalho == 3220
    assert rdv.fase == "oficial"
    assert (rdv.municipio, rdv.zona, rdv.secao) == (1066, 4, 77)
    assert rdv.tipo_urna == "secao"
    assert rdv.tipo_arquivo == "votacaoUE"
    assert rdv.versao_votacao.startswith("10.23.0.0")
    assert rdv.historico_codigos_carga == [rdv.codigo_carga]


def test_eleicoes_e_cargos(rdv):
    assert [e.id_eleicao for e in rdv.eleicoes] == [6257, 6259]
    assert all(e.origem == "vota" for e in rdv.eleicoes)
    cargos = {c.nome_cargo: c for _, c in rdv.cargos()}
    assert set(cargos) == {"Presidente", "Governador", "Senador", "Deputado Federal",
                           "Deputado Estadual"}
    assert cargos["Senador"].qtd_escolhas == 2
    assert cargos["Senador"].n_registros == 2 * 234
    assert all(c.n_registros == 234 for n, c in cargos.items() if n != "Senador")


def test_recontagem_presidente(rdv):
    pres = next(c for _, c in rdv.cargos() if c.codigo_cargo == 1)
    cont = recontar(pres)
    assert cont[("nominal", 22)] == 103
    assert cont[("nominal", 13)] == 99
    assert cont[("branco", None)] == 4
    # nulo (12) + nuloAposSuspensao (1)
    assert cont[("nulo", None)] == 13
    assert sum(cont.values()) == 234


def test_estrutura_integra(rdv):
    assert validar(rdv, pleito=3220, ident=IDENT) == []


def test_validar_aponta_problemas(rdv):
    outro = {**IDENT, "secao": "0078"}
    assert any("secao" in p for p in validar(rdv, pleito=3220, ident=outro))
    assert any("pleito" in p for p in validar(rdv, pleito=9999))


def test_recontar_e_validar_registros_invalidos():
    c = CargoRDV(1, "Presidente", 1, [("nominal", "13"), ("nominal", None),
                                      ("legenda", "1512"), ("branco", "5"),
                                      ("xyz", None), ("nuloCargoSemCandidato", None)])
    cont = recontar(c)
    assert cont[("nominal", 13)] == 1
    assert cont[("legenda", 15)] == 1
    assert cont[("invalido", "nominal")] == 1
    assert cont[("invalido", "xyz")] == 1
    assert cont[("cargoSemCandidato", None)] == 1


def test_rdv_corrompido():
    with pytest.raises(RDVParseError):
        parse_rdv_bytes(b"\x30\x03\x02\x01")


# ---------------------------------------------------------------- RDV x BU

def test_rdv_confere_com_bu(rdv, bu_cont):
    r = R.comparar_rdv_bu(rdv, bu_cont, IDENT, pleito=3220)
    assert r["achados"] == []
    assert len(r["linhas"]) == 5
    assert all(ln["confere"] for ln in r["linhas"])
    sen = next(ln for ln in r["linhas"] if ln["cargo"] == "Senador")
    assert sen["votos_rdv"] == sen["votos_bu"] == 468
    assert sen["comparecimento_bu"] == 234


def test_divergencia_detectada(rdv, bu_cont):
    adulterado = {k: {"comparecimento": v["comparecimento"], "votos": Counter(v["votos"])}
                  for k, v in bu_cont.items()}
    votos = adulterado[(6257, 1)]["votos"]
    votos[("nominal", 22)] += 1
    votos[("nominal", 13)] -= 1
    r = R.comparar_rdv_bu(rdv, adulterado, IDENT, pleito=3220)
    cats = [a["categoria"] for a in r["achados"]]
    assert cats == ["rdv_bu_diverge"]
    assert r["achados"][0]["grupo"] == 1
    assert r["achados"][0]["detalhes"] == {"nominal:13": [99, 98], "nominal:22": [103, 104]}
    pres = next(ln for ln in r["linhas"] if ln["codigo_cargo"] == 1)
    assert pres["confere"] is False
    assert json.loads(pres["detalhes"])["diferencas"]["nominal:22"] == [103, 104]


def test_registros_diferentes_do_comparecimento(rdv, bu_cont):
    alterado = dict(bu_cont)
    alterado[(6257, 1)] = {**bu_cont[(6257, 1)], "comparecimento": 235}
    r = R.comparar_rdv_bu(rdv, alterado, IDENT, pleito=3220)
    assert "rdv_registros_diverge" in [a["categoria"] for a in r["achados"]]


def test_cargo_ausente_no_rdv(rdv, bu_cont):
    extra = {**bu_cont, (6259, 8): {"comparecimento": 234,
                                    "votos": Counter({("nominal", 1234): 3})}}
    r = R.comparar_rdv_bu(rdv, extra, IDENT, pleito=3220)
    assert any(a["detalhes"] == {"cargo_ausente_no_rdv": [0, 3]} for a in r["achados"])


# ---------------------------------------------------------------- log

def _linha(data_hora, desc, urna="02293919", app="VOTA"):
    return f"{data_hora}\tINFO\t{urna}\t{app}\t{desc}\tABCDEF0123456789"


def _log(eventos) -> str:
    return "\n".join(_linha(*e) for e in eventos) + "\n"


def test_log_tempo_basico():
    txt = _log([
        ("23/09/2026 13:39:15", "Mídia de votação gerada pelo computador"),
        ("04/10/2026 06:06:53", "Urna pronta para receber votos"),
        ("04/10/2026 06:10:00", "O voto do eleitor foi computado"),
        ("04/10/2026 06:10:05", "O voto do eleitor foi computado"),
        ("04/10/2026 07:30:00", "O voto do eleitor foi computado"),
        ("04/10/2026 15:39:09", "O voto do eleitor foi computado"),
        ("04/10/2026 15:44:08", "Inicio do Encerramento"),
    ])
    r = R.analisar_log_tempo(txt, "ac", "01066", 4)
    assert r["fuso_offset"] == -2
    assert r["votos_log"] == 4
    assert r["diferenca_log_bu"] == 0
    assert r["votos_antes_8h"] == 0          # 06:10 no AC = 08:10 em Brasília
    assert r["votos_apos_17h"] == 1          # 15:39 no AC = 17:39 em Brasília
    assert r["votos_apos_encerramento"] == 0
    assert r["intervalo_min_s"] == 5
    assert r["intervalos_lt_10s"] == 1
    assert r["lacunas_60min"] == 2           # 06:10 a 07:30 e 07:30 a 15:39
    assert r["max_votos_minuto"] == 2
    assert r["hora_pronta"] == "06:06:53"
    assert r["hora_encerramento"] == "15:44:08"
    assert sum(r["hist_intervalos"]) == 3
    assert set(r["flags"]) == {"log_intervalo_curto", "log_lacuna_60min"}
    assert r["grupo"] == 3


def test_log_fora_de_sequencia_e_contagem():
    txt = _log([
        ("04/10/2026 07:59:00", "O voto do eleitor foi computado"),
        ("04/10/2026 08:00:00", "Urna pronta para receber votos"),
        ("04/10/2026 08:05:00", "O voto do eleitor foi computado"),
        ("04/10/2026 17:10:00", "Inicio do Encerramento"),
        ("04/10/2026 17:12:00", "O voto do eleitor foi computado"),
        ("05/10/2026 08:00:00", "O voto do eleitor foi computado"),
    ])
    r = R.analisar_log_tempo(txt, "sp", "71072", 4)
    assert r["votos_log"] == 3
    assert r["votos_antes_pronta"] == 1
    assert r["votos_apos_encerramento"] == 1
    assert r["votos_antes_8h"] == 1
    assert r["votos_outras_datas"] == 1
    assert {"log_votos_diverge", "log_voto_fora_sequencia", "log_voto_outra_data",
            "log_voto_antes_8h"} <= set(r["flags"])
    assert r["grupo"] == 2


def test_log_troca_de_urna_e_relogio():
    txt = _log([
        ("04/10/2026 08:00:00", "Urna pronta para receber votos", "1"),
        ("04/10/2026 09:00:00", "O voto do eleitor foi computado", "1"),
        ("04/10/2026 08:59:00", "O voto do eleitor foi computado", "1"),
        ("04/10/2026 10:00:00", "Urna pronta para receber votos", "2"),
        ("04/10/2026 10:00:01", "O voto do eleitor foi computado", "2"),
    ])
    r = R.analisar_log_tempo(txt, "sp", None, 3)
    assert r["n_urnas_log"] == 2
    assert r["inversoes_relogio"] == 1
    assert r["intervalo_min_s"] is None      # a troca de urna não conta como intervalo
    assert "log_relogio_inverso" in r["flags"]


def test_texto_log_zip():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("logd.dat", _log([("04/10/2026 08:00:00", "Urna pronta para receber votos")])
                   .encode("latin-1"))
    assert "Urna pronta" in R.texto_log(buf.getvalue())


def _zip(arquivos: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for nome, dados in arquivos.items():
            z.writestr(nome, dados)
    return buf.getvalue()


def _log_contingencia() -> bytes:
    """-log.jez de troca de urna: log da urna substituída aninhado como .jez."""
    antiga = _log([("04/10/2026 08:00:00", "Urna pronta para receber votos", "111"),
                   ("04/10/2026 08:10:00", "O voto do eleitor foi computado", "111")])
    nova = _log([("04/10/2026 09:00:00", "Urna pronta para receber votos", "222"),
                 ("04/10/2026 09:05:00", "O voto do eleitor foi computado", "222"),
                 ("04/10/2026 17:05:00", "Inicio do Encerramento", "222")])
    aninhado = _zip({"logd.dat": antiga.encode("latin-1")})
    return _zip({"0000011104102026085000-01.jez": aninhado, "logd.dat": nova.encode("latin-1")})


def test_texto_log_com_log_aninhado_de_contingencia():
    txt = R.texto_log(_log_contingencia())
    r = R.analisar_log_tempo(txt, "sp", None, 2)
    assert r["votos_log"] == 2
    assert r["n_urnas_log"] == 2
    assert r["aberturas"] == 2
    assert r["flags"] == []
    assert txt.index("\t111\t") < txt.index("\t222\t")


def test_log_parser_le_os_dois_logs_na_troca_de_urna():
    from dataurnas.parsers.log import LogParser

    entradas = LogParser().parse_bytes(_log_contingencia())
    assert [e.id_urna for e in entradas] == ["111", "111", "222", "222", "222"]
    ev = LogParser().extract_events(entradas, turno_date="04/10/2026")
    assert ev["votos_computados"] == 2
    assert ev["abertura"].hora == "08:00:00"
    assert ev["encerramento"].hora == "17:05:00"


def test_processar_secao_com_auditoria_de_log(rdv_raw):
    bu_raw = BU_AC.read_bytes()
    arquivos = {"rdv": ("x-rdv.dat", rdv_raw), "bu": ("x-bu.dat", bu_raw),
                "log": ("x-log.jez", _log_contingencia())}
    r = R.processar_secao(IDENT, arquivos, None, 3220, auditar=True, modelo_cod=22)
    assert r["secao"]["rdv_confere"] is True
    sl = r["secao_log"]
    assert sl["secao_id"] == "1T/ac/01066/0004/0077"
    assert sl["votos_log"] == 2
    assert sl["modelo_urna"] == "2022"
    assert sl["tem_log"] is True
    codigos = {i[1] for i in r["issues"]}
    assert "A03" in codigos  # 2 votos no log x 234 no BU


# ---------------------------------------------------------------- seção inteira

def test_processar_secao(rdv_raw):
    bu_raw = BU_AC.read_bytes()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("logd.dat", _log(
            [("04/10/2026 06:06:53", "Urna pronta para receber votos")]
            + [("04/10/2026 07:00:00", "O voto do eleitor foi computado")] * 234
        ).encode("latin-1"))
    arquivos = {"rdv": ("x-rdv.dat", rdv_raw), "bu": ("x-bu.dat", bu_raw),
                "log": ("x-log.jez", buf.getvalue())}
    sha = {"rdv": R.sha512(rdv_raw), "bu": "0" * 128}
    r = R.processar_secao(IDENT, arquivos, sha, 3220)
    assert r["secao"]["rdv_confere"] is True
    assert r["secao"]["hash_confere"] is False
    assert [a["categoria"] for a in r["achados"]] == ["rdv_hash_diverge"]
    assert r["tempo"]["votos_log"] == 234
    assert r["presidente"]["nominal:22"] == 103


def test_categorias_no_catalogo_de_referencia():
    from dataurnas.dashboard.reference import GRUPOS_ORDEM, RDV_CATEGORIAS

    for cat, grupo in R.CATEGORIAS.items():
        assert RDV_CATEGORIAS[cat][1] == GRUPOS_ORDEM[grupo - 1]


# ---------------------------------------------------------------- script

def _script():
    path = Path(__file__).parents[2] / "scripts" / "ele2026" / "fetch_rdv.py"
    spec = importlib.util.spec_from_file_location("fetch_rdv", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_secoes_do_catalogo_escolhe_conjunto_com_rdv():
    pa = pytest.importorskip("pyarrow")
    mod = _script()
    tok_a, tok_b = "AAAA", "BBBB"
    linhas = [
        ("ac", "01066", "0004", "0077", "bu", "a-bu.dat", "h1", tok_a, "04/10/2026 18:00:00"),
        ("ac", "01066", "0004", "0077", "bu", "b-bu.dat", "h2", tok_b, "04/10/2026 19:00:00"),
        ("ac", "01066", "0004", "0077", "rdv", "b-rdv.dat", "h3", tok_b, "04/10/2026 19:00:00"),
        ("ac", "01066", "0004", "0077", "vota", "b-vota.vsc", "h4", tok_b, "04/10/2026 19:00:00"),
        ("ac", "01066", "0004", "0078", "bu", "c-bu.dat", "h5", tok_a, "04/10/2026 18:00:00"),
    ]
    cols = ["uf", "cd_mun", "zona", "secao", "tipo", "nome", "sha512", "token_tse",
            "data_hora_tse"]
    t = pa.table({c: [ln[i] for ln in linhas] for i, c in enumerate(cols)})
    t = t.append_column("disponivel", pa.array([True] * len(linhas)))
    secoes = {s["secao"]: s for s in mod.secoes_do_catalogo(t)}
    s77 = secoes["0077"]
    assert s77["hash"] == tok_b.encode().hex()
    assert s77["arquivos"] == {"bu": ("b-bu.dat", "h2"), "rdv": ("b-rdv.dat", "h3")}
    assert s77["n_conjuntos"] == 2
    assert "rdv" not in secoes["0078"]["arquivos"]
