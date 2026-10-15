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
    EleicaoRDV,
    RDVParseError,
    RegistroDigitalVoto,
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


# ------------------------------------------------- RDV do SA em blocos repetidos

IDENT_SA = {"uf": "mg", "cd_mun": "41238", "zona": "0039", "secao": "0168"}


def _rdv_sa(blocos: list[dict[int, list[tuple[str, str | None]]]],
            origem: str = "sa") -> RegistroDigitalVoto:
    """RDV com uma eleição (6257) repetida em vários blocos, como no SA."""
    eleicoes = [EleicaoRDV(6257, origem, [CargoRDV(cod, "Presidente" if cod == 1 else "Senador",
                                                    1 if cod == 1 else 2, votos)
                                           for cod, votos in b.items()])
                for b in blocos]
    return RegistroDigitalVoto(
        data_geracao=None, id_pleito_cabecalho=None, pleito=3220, fase="oficial",
        municipio=41238, zona=39, local=0, secao=168, tipo_urna=None, tipo_arquivo=None,
        versao_votacao=None, numero_interno_urna=None, codigo_carga=None,
        historico_codigos_carga=[], eleicoes=eleicoes)


def _votos(**n) -> list[tuple[str, str | None]]:
    out = []
    for k, q in n.items():
        out += [("branco", None)] * q if k == "branco" else [("nominal", k[1:])] * q
    return out


def _bu_sa(comparecimento: int, pres: dict, sen: dict) -> dict:
    return {(6257, 1): {"comparecimento": comparecimento, "votos": Counter(pres)},
            (6257, 5): {"comparecimento": comparecimento, "votos": Counter(sen)}}


# mg/41238/0039/0168 (BU do SA): bloco de 20 + bloco de 261 = 281 comparecimento
BLOCOS_SA = [
    {1: _votos(branco=1, n13=12, n22=6, n30=1), 5: _votos(n131=20, n222=20)},
    {1: _votos(branco=3, n13=118, n22=111, n30=29), 5: _votos(n131=261, n222=261)},
]
BU_SA = _bu_sa(281, {("branco", None): 4, ("nominal", 13): 130, ("nominal", 22): 117,
                     ("nominal", 30): 30},
               {("nominal", 131): 281, ("nominal", 222): 281})


def test_rdv_sa_blocos_repetidos_somados_conferem():
    rdv = _rdv_sa(BLOCOS_SA)
    assert validar(rdv, pleito=3220, ident=IDENT_SA) == []
    r = R.comparar_rdv_bu(rdv, BU_SA, IDENT_SA, origem_bu="busa", pleito=3220)
    assert r["achados"] == []
    assert len(r["linhas"]) == 2
    assert all(ln["confere"] for ln in r["linhas"])
    pres = next(ln for ln in r["linhas"] if ln["codigo_cargo"] == 1)
    assert pres["registros_rdv"] == 281
    assert json.loads(pres["detalhes"]) == {"blocos_sa": 2}
    sen = next(ln for ln in r["linhas"] if ln["codigo_cargo"] == 5)
    assert sen["registros_rdv"] == 562
    assert r["presidente"][("nominal", 13)] == 130


def test_rdv_sa_blocos_que_nao_fecham_marcam_estrutura():
    bu = _bu_sa(282, {**BU_SA[(6257, 1)]["votos"], ("nominal", 13): 131},
                BU_SA[(6257, 5)]["votos"])
    r = R.comparar_rdv_bu(_rdv_sa(BLOCOS_SA), bu, IDENT_SA, origem_bu="busa", pleito=3220)
    cats = [a["categoria"] for a in r["achados"]]
    assert cats[0] == "rdv_estrutura"
    assert "rdv_bu_diverge_sa" in cats
    assert any("blocos do SA" in p for p in r["achados"][0]["detalhes"])


def test_rdv_urna_com_eleicao_repetida_continua_estrutura():
    rdv = _rdv_sa(BLOCOS_SA, origem="vota")
    assert any("repetida" in p for p in validar(rdv, pleito=3220, ident=IDENT_SA))
    r = R.comparar_rdv_bu(rdv, BU_SA, IDENT_SA, pleito=3220)
    assert r["achados"][0]["categoria"] == "rdv_estrutura"


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


def _votos_de(urna: str, inicio: int, n: int) -> list[tuple]:
    """Abertura e n votos de uma urna, um por minuto a partir de 08:<inicio>."""
    ev = [(f"04/10/2026 08:{inicio:02d}:00", "Urna pronta para receber votos", urna)]
    ev += [(f"04/10/2026 08:{inicio + 1 + i:02d}:00", "O voto do eleitor foi computado", urna)
           for i in range(n)]
    return ev


def test_textos_zip_sem_duplicar_copias_mi_e_me_do_log_corrompido():
    """Log corrompido guardado em dupla (01MI e 02ME): é o mesmo log, a cópia MI
    truncada; os votos contam uma vez só e a ME acrescenta só o que falta."""
    antigo = _votos_de("111", 0, 4)
    mi = _log(antigo[:-1])                 # MI truncada: perdeu o último voto
    me = _log(antigo)
    nova = _log(_votos_de("111", 30, 2))   # logd.dat da mesma urna depois do reinício
    raw = _zip({"0000011104102026083000" "01MI.jez": _zip({"logd.dat": mi.encode("latin-1")}),
                "0000011104102026083000" "02ME.jez": _zip({"logd.dat": me.encode("latin-1")}),
                "logd.dat": nova.encode("latin-1")})
    r = R.analisar_log_tempo(R.texto_log(raw), "sp", None, 6)
    assert r["votos_log"] == 6
    assert r["diferenca_log_bu"] == 0
    assert r["aberturas"] == 2
    assert r["inversoes_relogio"] == 0
    assert "log_relogio_inverso" not in r["flags"]


def test_textos_zip_sem_duplicar_a_mesma_me_copiada_por_duas_urnas():
    """Duas urnas de contingência copiam a mesma ME: duas cópias iguais no pacote."""
    me = _log(_votos_de("111", 0, 3)).encode("latin-1")
    nova = _log(_votos_de("333", 40, 2)).encode("latin-1")
    raw = _zip({"0000022204102026090000" "01ME.jez": _zip({"logd.dat": me}),
                "0000033304102026093900-01.jez": _zip({"logd.dat": me}),
                "logd.dat": nova})
    r = R.analisar_log_tempo(R.texto_log(raw), "sp", None, 5)
    assert r["votos_log"] == 5
    assert r["aberturas"] == 2
    assert r["inversoes_relogio"] == 0


def test_textos_zip_ordena_aninhados_pela_data_e_hora_do_nome():
    """O nome começa pelo número da urna; a ordem é a da data e hora embutida."""
    from dataurnas.parsers.log import textos_zip

    cedo = _log(_votos_de("999", 0, 1)).encode("latin-1")
    tarde = _log(_votos_de("111", 30, 1)).encode("latin-1")
    raw = _zip({"1111111104102026120000-01.jez": _zip({"logd.dat": tarde}),
                "9999999904102026080000-01.jez": _zip({"logd.dat": cedo}),
                "logd.dat": b""})
    textos = textos_zip(raw)
    assert "\t999\t" in textos[0] and "\t111\t" in textos[1]


def test_textos_zip_preserva_eventos_repetidos_legitimos():
    """Linha igual só é duplicata se tudo coincide (data, hora, urna, evento,
    código). Eventos iguais de urnas diferentes e linhas repetidas dentro do
    mesmo log ficam; a cópia do log não acrescenta nada."""
    mesmo_seg = [("04/10/2026 08:00:00", "Urna pronta para receber votos", "111"),
                 ("04/10/2026 08:01:00", "Voto confirmado para [Senador]", "111"),
                 ("04/10/2026 08:01:00", "Voto confirmado para [Senador]", "111"),
                 ("04/10/2026 08:01:00", "O voto do eleitor foi computado", "111")]
    log_a = _log(mesmo_seg).encode("latin-1")
    log_b = _log([(d, e, "222") for d, e, _ in mesmo_seg]).encode("latin-1")
    raw = _zip({"0000011104102026090000" "01MI.jez": _zip({"logd.dat": log_a}),
                "0000011104102026090000" "02ME.jez": _zip({"logd.dat": log_a}),
                "logd.dat": log_b})
    txt = R.texto_log(raw)
    assert txt.count("Voto confirmado para [Senador]") == 4
    assert txt.count("\t111\t") == 4 and txt.count("\t222\t") == 4
    assert R.analisar_log_tempo(txt, "sp", None, 2)["votos_log"] == 2


def test_log_parser_sem_duplicar_logs_aninhados():
    """A auditoria por seção (LogParser.parse_bytes) usa a mesma leitura."""
    from dataurnas.parsers.log import LogParser

    me = _log(_votos_de("111", 0, 3)).encode("latin-1")
    raw = _zip({"0000011104102026083000" "01MI.jez": _zip({"logd.dat": me}),
                "0000011104102026083000" "02ME.jez": _zip({"logd.dat": me}),
                "logd.dat": _log(_votos_de("111", 30, 1)).encode("latin-1")})
    ev = LogParser().extract_events(LogParser().parse_bytes(raw), turno_date="04/10/2026")
    assert ev["votos_computados"] == 4
    assert ev["reboots"] == 1
    assert ev["abertura"].hora == "08:00:00"


def test_processar_secao_log_do_sa_nao_entra_na_comparacao_com_bu():
    """BU do Sistema de Apuração: o -logsa.jez é o log da digitação e não tem
    eventos de voto; log x BU não se aplica (não é divergência)."""
    logsa = _log([("04/10/2026 17:33:00", "Tipo de apuração selecionada (DIGITAÇÃO DE BUEx)",
                   "01808076")]).encode("latin-1")
    arquivos = {"busa": ("x-busa.dat", BU_AC.read_bytes()),
                "logsa": ("x-logsa.jez", _zip({"logd.dat": logsa}))}
    r = R.processar_secao(IDENT, arquivos, None, 3220)
    t = r["tempo"]
    assert t["origem_log"] == "logsa"
    assert t["votos_log"] is None
    assert t["diferenca_log_bu"] is None
    assert t["comparecimento_bu"] == r["secao"]["comparecimento_bu"]
    assert "log_votos_diverge" not in t["flags"]
    assert not [a for a in r["achados"] if a["categoria"].startswith("log_")]


def test_processar_secao_log_do_sa_pelo_nome_do_arquivo():
    """O catálogo de integridade normaliza o tipo logsa para log; o nome
    (-logsa.jez) preserva a origem."""
    logsa = _log([("04/10/2026 17:33:00", "Tipo de apuração selecionada (DIGITAÇÃO DE BUEx)",
                   "01808076")]).encode("latin-1")
    arquivos = {"busa": ("o03220zz2946700010010-busa.dat", BU_AC.read_bytes()),
                "log": ("o03220zz2946700010010-logsa.jez", _zip({"logd.dat": logsa}))}
    t = R.processar_secao(IDENT, arquivos, None, 3220)["tempo"]
    assert t["origem_log"] == "logsa"
    assert t["diferenca_log_bu"] is None
    assert "log_votos_diverge" not in t["flags"]


def test_processar_secao_log_da_urna_marca_origem():
    arquivos = {"bu": ("x-bu.dat", BU_AC.read_bytes()), "log": ("x-log.jez", _log_contingencia())}
    t = R.processar_secao(IDENT, arquivos, None, 3220)["tempo"]
    assert t["origem_log"] == "log"
    assert t["votos_log"] == 2


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


def test_ler_lista_secoes(tmp_path):
    mod = _script()
    p = tmp_path / "lista.txt"
    p.write_text("# seções a refazer\nRS/89036/0083/0044\n\nzz/29467/0001/0010  # SA\n",
                 encoding="utf-8")
    assert mod.ler_lista_secoes(p) == {"rs/89036/0083/0044", "zz/29467/0001/0010"}
    p.write_text("rs/89036/0083\n", encoding="utf-8")
    with pytest.raises(ValueError):
        mod.ler_lista_secoes(p)


def test_parse_args_secoes():
    mod = _script()
    assert mod.parse_args(["--secoes", "x.txt"]).secoes == "x.txt"
    assert mod.parse_args([]).secoes is None
