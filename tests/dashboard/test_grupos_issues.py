"""Grupos de leitura dos códigos de inconsistência (reference.GRUPOS)."""

import json
import re
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from dataurnas.analyzer.integrity import CATEGORIAS_DIVERGENCIA  # noqa: E402
from dataurnas.dashboard import integridade2026 as ig  # noqa: E402
from dataurnas.dashboard.filters import Filters  # noqa: E402
from dataurnas.dashboard.reference import (  # noqa: E402
    ANALISES_ESTATISTICAS,
    GRUPO_ADULTERACAO,
    GRUPO_INVESTIGAR,
    GRUPO_OPERACIONAL,
    GRUPOS,
    GRUPOS_ORDEM,
    INTEGRIDADE_CATEGORIAS,
    ISSUE_CATALOGO,
    ISSUE_DESCRICOES,
    ISSUE_GRUPOS,
    ISSUE_MOTIVOS,
    codigos_do_grupo,
    contar_por_grupo,
    grupo_label,
    grupo_nome,
)

ANALYZER = ROOT / "src" / "dataurnas" / "analyzer"

ESPERADO = {
    GRUPO_ADULTERACAO: {"C01", "C05", "A02", "A06"},
    GRUPO_INVESTIGAR: {"A01", "A03", "E02", "E03", "M03"},
    GRUPO_OPERACIONAL: {"C06", "A04", "A05", "M01", "M02", "M04", "M05", "M06",
                        "I01", "I02", "I03", "I04", "I05", "I06", "E01"},
}


def _codigos_emitidos() -> set[str]:
    """Códigos que o analisador emite (literal codigo="X99" ou constante CODIGO_* = "X99")."""
    achados: set[str] = set()
    for py in ANALYZER.glob("*.py"):
        texto = py.read_text(encoding="utf-8")
        achados |= set(re.findall(r'codigo="([A-Z]\d{2})"', texto))
        achados |= set(re.findall(r'^CODIGO_\w+\s*=\s*"([A-Z]\d{2})"', texto, flags=re.M))
    return achados


def test_tres_grupos_em_ordem_com_nome_e_resumo():
    assert GRUPOS_ORDEM == (GRUPO_ADULTERACAO, GRUPO_INVESTIGAR, GRUPO_OPERACIONAL)
    assert [GRUPOS[g]["nome"] for g in GRUPOS_ORDEM] == [
        "Indício direto de adulteração", "Inconsistência a investigar", "Operacional ou estatístico",
    ]
    for g in GRUPOS_ORDEM:
        assert GRUPOS[g]["resumo"].endswith(".")


def test_todo_codigo_emitido_pelo_analisador_tem_grupo():
    emitidos = _codigos_emitidos()
    assert {"C01", "E01", "A03", "C06"} <= emitidos  # o regex encontra os códigos
    assert emitidos <= set(ISSUE_GRUPOS), emitidos - set(ISSUE_GRUPOS)


def test_classificacao_de_cada_codigo():
    assert set(ISSUE_CATALOGO) == set().union(*ESPERADO.values())
    for grupo, codigos in ESPERADO.items():
        assert set(codigos_do_grupo([grupo])) == codigos


def test_catalogo_derivado_e_motivo_preenchido():
    assert set(ISSUE_DESCRICOES) == set(ISSUE_GRUPOS) == set(ISSUE_MOTIVOS)
    for codigo, motivo in ISSUE_MOTIVOS.items():
        assert len(motivo) > 20, codigo


def test_categorias_de_integridade_2026_classificadas():
    assert set(CATEGORIAS_DIVERGENCIA) <= set(INTEGRIDADE_CATEGORIAS)
    for cat in CATEGORIAS_DIVERGENCIA:
        assert INTEGRIDADE_CATEGORIAS[cat][1] == GRUPO_ADULTERACAO
    assert INTEGRIDADE_CATEGORIAS["votos_divergem"][1] == GRUPO_INVESTIGAR
    for _nome, grupo, _motivo in ANALISES_ESTATISTICAS.values():
        assert grupo == GRUPO_OPERACIONAL


def test_rotulo_do_grupo_traz_numero_e_nome():
    assert grupo_nome(GRUPO_ADULTERACAO) == "1. Indício direto de adulteração"
    assert grupo_label("A03") == "2. Inconsistência a investigar"
    assert grupo_label("C06") == "3. Operacional ou estatístico"
    assert grupo_label("Z99") == "Não classificado"


def test_contar_por_grupo():
    cont = contar_por_grupo({"C01": 1, "A06": 2, "A03": 5, "C06": 7, "I04": 3, "Z99": 100,
                             "hash_diverge": 4, "votos_divergem": 1})
    assert cont == {GRUPO_ADULTERACAO: 7, GRUPO_INVESTIGAR: 6, GRUPO_OPERACIONAL: 10}
    assert contar_por_grupo({}) == {g: 0 for g in GRUPOS_ORDEM}


def test_textos_sem_travessao():
    proibidos = (chr(0x2014), chr(0x2013))
    textos = [g["nome"] + g["resumo"] for g in GRUPOS.values()]
    textos += [" ".join(v) for v in ISSUE_CATALOGO.values()]
    textos += [" ".join(v) for v in INTEGRIDADE_CATEGORIAS.values()]
    textos += [" ".join(v) for v in ANALISES_ESTATISTICAS.values()]
    assert not [t for t in textos if any(p in t for p in proibidos)]


# ----------------------------------------------------------------------
# Filtro por grupo
# ----------------------------------------------------------------------
def test_filtro_por_grupo_vira_lista_de_codigos():
    f = Filters.build(grupos=[GRUPO_ADULTERACAO])
    assert f["issue_where"] == "1=1 AND i.codigo IN (?,?,?,?)"
    assert f["issue_params"] == ["A02", "A06", "C01", "C05"]


def test_filtro_grupo_e_codigo_faz_intersecao():
    f = Filters.build(grupos=[GRUPO_INVESTIGAR], codigos=["A03", "C06"])
    assert f["issue_params"] == ["A03"]
    vazio = Filters.build(grupos=[GRUPO_ADULTERACAO], codigos=["C06"])
    assert "FALSE" in vazio["issue_where"]
    assert vazio["issue_params"] == []


def test_filtro_por_grupo_no_duckdb():
    duckdb = pytest.importorskip("duckdb")
    con = duckdb.connect()
    con.execute("CREATE TABLE secoes (id INTEGER, turno INTEGER)")
    con.execute("CREATE TABLE issues (secao_id INTEGER, codigo VARCHAR)")
    con.execute("INSERT INTO secoes VALUES (1, 1), (2, 1)")
    con.execute("INSERT INTO issues VALUES (1, 'C06'), (1, 'A03'), (2, 'C01'), (2, 'I04')")
    for grupos, esperado in (([GRUPO_ADULTERACAO], ["C01"]), ([GRUPO_INVESTIGAR, GRUPO_OPERACIONAL],
                                                                ["A03", "C06", "I04"])):
        f = Filters.build(turno=1, grupos=grupos)
        got = con.execute(f"SELECT i.codigo FROM issues i JOIN secoes s ON i.secao_id = s.id "
                          f"WHERE {f['issue_where']} ORDER BY 1", f["issue_params"]).fetchall()
        assert [r[0] for r in got] == esperado
    f = Filters.build(grupos=[GRUPO_ADULTERACAO], codigos=["C06"])
    assert con.execute(f"SELECT COUNT(*) FROM issues i JOIN secoes s ON i.secao_id = s.id "
                       f"WHERE {f['issue_where']}", f["issue_params"]).fetchone()[0] == 0


# ----------------------------------------------------------------------
# Contagens de 2026
# ----------------------------------------------------------------------
def test_contagens_2026(tmp_path):
    integ = tmp_path / "integridade"
    integ.mkdir()
    linha = {"uf": "ac", "cd_mun": "1", "zona": "1", "secao": "1", "arquivo": "x-log.jez",
             "categoria": "arquivo_ausente_tse", "token_tse": "t"}
    (integ / "divergencias.jsonl").write_text(
        "\n".join([json.dumps(linha), json.dumps(linha),  # repetida: conta uma vez
                   json.dumps({**linha, "categoria": "hash_assinado_ausente", "arquivo": "y-bu.dat"}),
                   json.dumps({**linha, "categoria": "hash_diverge"}),  # vem de totais, não do jsonl
                   '{"uf": "ac", "categ']),  # linha em gravação
        encoding="utf-8",
    )
    aud = tmp_path / "auditoria"
    aud.mkdir()
    pd.DataFrame({"secao_id": ["a", "b", "c"], "codigo": ["C06", "C06", "A03"]}).to_parquet(
        aud / "issues_2026.parquet")
    t = {"hash_diverge": 2, "assinaturas_invalidas": 1, "votos_divergem": 3}
    cont = ig.contagens_2026(t, pasta=integ, base=tmp_path)
    assert cont == {"hash_diverge": 2, "assinatura_invalida": 1, "votos_divergem": 3,
                    "hash_assinado_ausente": 1, "arquivo_ausente_tse": 1, "C06": 2, "A03": 1}
    assert contar_por_grupo(cont) == {GRUPO_ADULTERACAO: 5, GRUPO_INVESTIGAR: 4, GRUPO_OPERACIONAL: 2}


def test_contagens_2026_sem_arquivos(tmp_path):
    cont = ig.contagens_2026({}, pasta=tmp_path / "nada", base=tmp_path)
    assert contar_por_grupo(cont) == {g: 0 for g in GRUPOS_ORDEM}
