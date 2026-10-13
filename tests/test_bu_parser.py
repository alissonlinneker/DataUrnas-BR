import pytest

from dataurnas.models import SpecVersion, TipoVoto
from dataurnas.parsers.bu import BUParseError, BUParser, _parse_tipo_voto


@pytest.fixture
def bu_file(tmp_path, bu_bytes):
    path = tmp_path / "o00406-0229100050010.bu"
    path.write_bytes(bu_bytes)
    return path


def test_parse_bu_v1(bu_file):
    bu = BUParser().parse(bu_file)
    assert (bu.municipio, bu.zona, bu.secao) == (2291, 5, 10)
    assert bu.spec_version is SpecVersion.V1
    assert bu.tipo_urna == "secao"
    assert bu.versao_votacao.startswith("8.26")
    assert bu.numero_serie == 256
    assert bu.qtd_eleitores_lib_codigo == 5
    assert bu.qtd_eleitores_comp_biometrico == 230
    assert bu.hora_abertura == "20221002T070000"

    (eleicao,) = bu.resultados_por_eleicao
    assert eleicao.id_eleicao == 544
    assert eleicao.eleitores_aptos == 300
    cargos = {r.nome_cargo: r for r in eleicao.resultados}
    assert set(cargos) == {"Presidente", "Governador"}
    pres = cargos["Presidente"]
    assert pres.codigo_cargo == 1
    assert pres.comparecimento == 235
    nominais = [v for v in pres.votos if v.tipo_voto is TipoVoto.NOMINAL]
    assert [(v.codigo_votavel, v.partido, v.quantidade) for v in nominais] == [
        (13, 13, 120), (22, 22, 100),
    ]
    assert bu.total_votos == 235 + 235


def test_parse_to_dict(bu_file):
    data = BUParser().parse_to_dict(bu_file)
    assert data["spec_version"] == "v1"
    assert "resultadosVotacaoPorEleicao" in data["bu"]


@pytest.mark.parametrize("raw,esperado", [
    ("nominal", TipoVoto.NOMINAL),
    ("branco", TipoVoto.BRANCO),
    ("cargoSemCandidato", TipoVoto.CARGO_SEM_CANDIDATO),
    (3, TipoVoto.NULO),
    (("legenda", 4), TipoVoto.LEGENDA),
])
def test_tipo_voto_conhecido(raw, esperado):
    assert _parse_tipo_voto({"tipoVoto": raw}) is esperado


@pytest.mark.parametrize("vv", [{"tipoVoto": "anulado"}, {"tipoVoto": 99}, {}])
def test_tipo_voto_desconhecido_ou_ausente_nao_vira_nominal(vv):
    with pytest.raises(BUParseError):
        _parse_tipo_voto(vv)


def test_resultado_com_tipo_desconhecido_levanta_erro():
    res = {
        "idEleicao": 544,
        "qtdEleitoresAptos": 10,
        "resultadosVotacao": [{
            "qtdComparecimento": 5,
            "totaisVotosCargo": [{
                "codigoCargo": ("cargoConstitucional", "presidente"),
                "votosVotaveis": [{"tipoVoto": "votoEmTransito", "quantidadeVotos": 5}],
            }],
        }],
    }
    with pytest.raises(BUParseError):
        BUParser()._parse_resultado_eleicao(res, SpecVersion.V1)
