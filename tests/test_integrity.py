import hashlib

import pytest

from dataurnas.analyzer.integrity import ConsistencyAnalyzer, IntegrityAnalyzer
from dataurnas.models import (
    BoletimUrna,
    IssueSeverity,
    ResultadoCargo,
    ResultadoEleicao,
    TipoVoto,
    VotoTupla,
)
from dataurnas.parsers.signature import SignatureParser, _resolve_signed_file


@pytest.fixture
def secao(tmp_path):
    d = tmp_path / "secao"
    d.mkdir()
    (d / "o00406-1.vscmr").write_bytes(b"assinatura")
    (d / "o00406-1.bu").write_bytes(b"conteudo do bu")
    return d


def _patch_hashes(monkeypatch, hashes):
    monkeypatch.setattr(SignatureParser, "extract_file_hashes", lambda self, p: hashes)


def test_falha_de_parse_nao_e_hash_invalido(secao, monkeypatch):
    def boom(self, p):
        raise ValueError("BER malformado")

    monkeypatch.setattr(SignatureParser, "extract_file_hashes", boom)
    issues = IntegrityAnalyzer().verify_section_hashes(secao)
    assert [i.codigo for i in issues] == ["E01"]
    assert issues[0].severidade is IssueSeverity.INFO
    assert "não verificável" in issues[0].descricao


def test_arquivo_ausente_e_nao_verificavel(secao, monkeypatch):
    _patch_hashes(monkeypatch, {"o00406-1.rdv": b"\x01" * 64})
    issues = IntegrityAnalyzer().verify_section_hashes(secao)
    assert [i.codigo for i in issues] == ["E01"]
    assert issues[0].severidade is IssueSeverity.INFO


def test_hash_divergente_e_c01(secao, monkeypatch):
    _patch_hashes(monkeypatch, {"o00406-1.bu": b"\x00" * 64})
    issues = IntegrityAnalyzer().verify_section_hashes(secao)
    assert [i.codigo for i in issues] == ["C01"]
    assert issues[0].severidade is IssueSeverity.CRITICAL


def test_hash_correto_sem_issues(secao, monkeypatch):
    ok = hashlib.sha512(b"conteudo do bu").digest()
    _patch_hashes(monkeypatch, {"o00406-1.bu": ok})
    assert IntegrityAnalyzer().verify_section_hashes(secao) == []


@pytest.mark.parametrize("nome", ["../segredo.txt", "a/b.bu", "..", "", "x\x00y"])
def test_nome_assinado_com_path_traversal_e_rejeitado(secao, nome):
    (secao.parent / "segredo.txt").write_text("fora da seção")
    assert _resolve_signed_file(secao, nome) is None


def test_nome_com_metacaractere_de_glob_nao_casa_por_padrao(secao):
    assert _resolve_signed_file(secao, "*") is None
    assert _resolve_signed_file(secao, "1.bu") == secao / "o00406-1.bu"


def _bu(aptos=100, comps=(80, 80), votos=80):
    resultados = [
        ResultadoCargo(
            codigo_cargo=c, nome_cargo=n, comparecimento=comp,
            votos=[VotoTupla(TipoVoto.NOMINAL, votos, 13, 13)],
        )
        for (c, n), comp in zip([(1, "Presidente"), (3, "Governador")], comps, strict=True)
    ]
    return BoletimUrna(
        uf="sp", municipio=1, zona=1, secao=1,
        resultados_por_eleicao=[ResultadoEleicao(id_eleicao=544, eleitores_aptos=aptos,
                                                 resultados=resultados)],
    )


def test_consistencia_ok():
    assert ConsistencyAnalyzer().full_analysis(_bu()) == []


def test_votos_acima_de_aptos_e_comparecimento():
    codigos = {i.codigo for i in ConsistencyAnalyzer().full_analysis(_bu(aptos=50, votos=90))}
    assert {"C05", "A02"} <= codigos


def test_comparecimento_divergente_entre_cargos():
    codigos = {i.codigo for i in ConsistencyAnalyzer().full_analysis(_bu(comps=(80, 79)))}
    assert "A06" in codigos


def test_urna_reserva_informativa():
    bu = _bu()
    bu.tipo_urna = "reservaSecao"
    issues = ConsistencyAnalyzer().check_tipo_urna(bu)
    assert [i.codigo for i in issues] == ["I06"]
