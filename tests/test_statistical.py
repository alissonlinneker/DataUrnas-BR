from dataurnas.analyzer.statistical import (
    StatisticalAnalyzer,
    VoteAggregator,
    compute_outlier_scores,
    escopo_candidatura,
)
from dataurnas.models import (
    BoletimUrna,
    ResultadoCargo,
    ResultadoEleicao,
    TipoVoto,
    VotoTupla,
)


def _bu(cargo=(3, "Governador"), votos=None, aptos=100, comp=80, lib=0, bio=80):
    votos = votos or [VotoTupla(TipoVoto.NOMINAL, 50, 44, 44),
                      VotoTupla(TipoVoto.BRANCO, 10), VotoTupla(TipoVoto.NULO, 20)]
    return BoletimUrna(
        uf="", municipio=1, zona=1, secao=1,
        qtd_eleitores_lib_codigo=lib, qtd_eleitores_comp_biometrico=bio,
        resultados_por_eleicao=[ResultadoEleicao(
            id_eleicao=544, eleitores_aptos=aptos,
            resultados=[ResultadoCargo(cargo[0], cargo[1], comp, votos)],
        )],
    )


def test_escopo():
    assert escopo_candidatura(1, "sp") == "BR"
    assert escopo_candidatura(3, "SP") == "sp"
    assert escopo_candidatura(6, "") == "??"
    assert escopo_candidatura(13, "sp", "71072") == "sp/71072"


def test_agregador_nao_mistura_ufs_nem_turnos():
    agg = VoteAggregator()
    agg.add_bu(_bu(), uf="sp", turno=1)
    agg.add_bu(_bu(), uf="rj", turno=1)
    agg.add_bu(_bu(), uf="sp", turno=2)
    pres = [VotoTupla(TipoVoto.NOMINAL, 7, 13, 13)]
    agg.add_bu(_bu(cargo=(1, "Presidente"), votos=pres), uf="sp", turno=1)
    agg.add_bu(_bu(cargo=(1, "Presidente"), votos=pres), uf="rj", turno=1)

    res = agg.get_results()
    cand = res["votos_por_candidato"]
    assert cand[1]["sp"]["Governador"][0]["votos"] == 50
    assert cand[1]["rj"]["Governador"][0]["votos"] == 50
    assert cand[2]["sp"]["Governador"][0]["votos"] == 50
    # Presidente soma entre UFs, mas só dentro do turno
    assert cand[1]["BR"]["Presidente"][0]["votos"] == 14
    assert 2 not in cand or "BR" not in cand[2]
    assert res["totais_por_cargo"][1]["Governador"]["nominais"] == 100
    assert res["totais_por_cargo"][2]["Governador"]["brancos"] == 10


def test_analise_estatistica_limiares():
    codigos = {i.codigo for i in StatisticalAnalyzer().analyze_bu(_bu(aptos=200, lib=40, bio=40))}
    # nulos 25% (>15), brancos 12.5% (>10), abstencao 60% (>40), sem biometria 50% (>30)
    assert codigos == {"I03", "I04", "I05", "M06"}


def test_outlier_scores():
    assert compute_outlier_scores([1, 2]) == [0.0, 0.0]
    assert compute_outlier_scores([5, 5, 5, 5]) == [0.0] * 4
    z = compute_outlier_scores([0, 0, 0, 0, 10])
    assert z[-1] == max(z) and z[-1] > 1.9
