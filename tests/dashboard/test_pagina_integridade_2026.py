"""Auditoria de integridade de 2026: carregadores, página e relatório com dados sintéticos."""

import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import integridade_sintetica as sint  # noqa: E402

from dataurnas.dashboard import integridade2026 as ig  # noqa: E402

TRAVESSOES = (chr(0x2014), chr(0x2013))


@pytest.fixture
def pasta(tmp_path):
    return sint.gerar(tmp_path / "integridade")


# ----------------------------------------------------------------------
# Carregadores
# ----------------------------------------------------------------------
def test_pasta_ausente_nao_quebra(tmp_path):
    dados = ig.load_secoes(tmp_path / "nao_existe")
    assert dados.vazio and dados.origem == ""
    t = ig.totais(dados.secoes, sint.res_uf_sintetico())
    assert t["verificadas"] == 0 and t["cobertura_pct"] == 0 and t["instaladas"] == 9
    tab = ig.por_uf(dados.secoes, sint.res_uf_sintetico())
    assert len(tab) == 4 and (tab["verificadas"] == 0).all()
    assert ig.divergencias(dados.secoes).empty
    assert ig.load_resumo(tmp_path) == {}
    assert ig.files_signature(tmp_path / "nao_existe") == ()


def test_load_secoes_ignora_arquivo_em_gravacao(pasta):
    dados = ig.load_secoes(pasta)
    assert dados.origem == "secoes.parquet"
    assert dados.ignorados == 1  # arquivos_rr.parquet incompleto
    assert len(dados.arquivos) == 4  # ac, zz, sp_1, sp_2
    assert not dados.secoes.duplicated(["uf", "cd_mun", "zona", "secao"]).any()


def test_totais_e_cobertura(pasta):
    t = ig.totais(ig.load_secoes(pasta).secoes, sint.res_uf_sintetico())
    assert t["verificadas"] == 6 and t["agregadas"] == 1 and t["nao_instaladas"] == 1
    assert t["arquivos"] == 36
    assert t["hash_confere"] == 17 and t["hash_diverge"] == 1 and t["sem_hash"] == 18
    assert t["assinaturas_validas"] == 6 and t["secoes_divergentes"] == 1
    assert t["cobertura_pct"] == pytest.approx(6 / 9 * 100)


def test_por_uf_inclui_ufs_sem_dados(pasta):
    tab = ig.por_uf(ig.load_secoes(pasta).secoes, sint.res_uf_sintetico()).set_index("uf")
    assert tab.loc["ac", "completa"] and tab.loc["ac", "secoes_divergentes"] == 1
    assert tab.loc["sp", "cobertura_pct"] == 50 and not tab.loc["sp", "completa"]
    assert tab.loc["rr", "verificadas"] == 0 and tab.loc["rr", "nome"] == "Roraima"
    assert tab.loc["sp", "arquivos"] == 12  # as duas partes de SP


def test_divergencias(pasta):
    div = ig.divergencias(ig.load_secoes(pasta).secoes)
    assert len(div) == 1
    assert div.loc[0, "secao"] == "0002" and "hash" in div.loc[0, "problemas"]


def test_sem_divergencia(tmp_path):
    p = sint.gerar(tmp_path / "integridade", divergente=False)
    assert ig.divergencias(ig.load_secoes(p).secoes).empty


def test_assinatura_invalida_conta_como_divergencia(pasta):
    secoes = ig.load_secoes(pasta).secoes.copy()
    secoes.loc[0, "assinatura_valida"] = False
    div = ig.divergencias(secoes)
    assert "assinatura inválida" in " ".join(div["problemas"])
    assert ig.totais(secoes)["assinaturas_invalidas"] == 1


def test_fallback_para_catalogo_sem_secoes_parquet(tmp_path):
    p = sint.gerar(tmp_path / "integridade", com_secoes=False)
    dados = ig.load_secoes(p)
    assert dados.origem == "catalogo" and len(dados.secoes) == 6
    t = ig.totais(dados.secoes)
    assert t["hash_diverge"] == 1 and t["assinaturas_nao_verificadas"] == 6


def test_arquivos_da_secao(pasta):
    a = ig.arquivos_da_secao("ac", "01007", "0009", "0002", pasta).set_index("tipo")
    assert len(a) == 6
    assert a.loc["bu", "situacao_hash"] == "Diverge"
    assert a.loc["log", "situacao_hash"] == "Confere"
    assert a.loc["imgbu", "situacao_hash"] == "Não coberto pela assinatura"
    assert len(a.loc["rdv", "sha512"]) == 128 and len(a.loc["rdv", "md5"]) == 32
    assert ig.arquivos_da_secao("ac", "99999", "0009", "0002", pasta).empty
    assert ig.arquivos_da_secao("mg", "1", "1", "1", pasta).empty


def test_catalogo_csv_e_contagem(pasta):
    assert ig.contar_catalogo("sp", pasta=pasta) == 12
    assert ig.contar_catalogo("ac", apenas_divergentes=True, pasta=pasta) == 1
    assert ig.contar_catalogo("ac", cd_mun="01120", pasta=pasta) == 6
    csv = ig.catalogo_csv("ac", apenas_divergentes=True, pasta=pasta).decode("utf-8-sig")
    linhas = csv.strip().splitlines()
    assert linhas[0].startswith("uf;cd_mun;zona;secao;tipo")
    assert len(linhas) == 2 and ";bu;" in linhas[1]


def test_horarios_e_mascara(pasta):
    h = ig.horarios_coleta(ig.load_resumo(pasta))
    assert h == {"inicio": "2026-10-13T08:00:00", "atualizado_em": "2026-10-13T10:30:00"}
    assert ig.mascarar_hash("a" * 128) == "a" * 12 + "..." + "a" * 8
    assert ig.mascarar_hash(None) == "-" and ig.mascarar_hash("abc") == "abc"


def test_resumo_json_invalido(tmp_path):
    (tmp_path / "resumo.json").write_text("{quebrado", encoding="utf-8")
    assert ig.load_resumo(tmp_path) == {}


def test_signature_muda_com_novo_arquivo(pasta):
    antes = ig.files_signature(pasta)
    pd.DataFrame([{"uf": "rn"}]).to_parquet(pasta / "arquivos_rn.parquet")
    assert ig.files_signature(pasta) != antes


# ----------------------------------------------------------------------
# Página (AppTest)
# ----------------------------------------------------------------------
AppTest = pytest.importorskip("streamlit.testing.v1").AppTest


def _script(pasta_dados: Path) -> str:
    return (
        "import sys\n"
        "from pathlib import Path\n"
        f"sys.path.insert(0, {str(SRC)!r})\n"
        "from dataurnas.dashboard import integridade2026 as ig\n"
        f"ig.integ_dir = lambda base=None: Path({str(pasta_dados)!r})\n"
        "from dataurnas.dashboard.pages import integridade_2026\n"
        "integridade_2026.render()\n"
    )


def _sem_erros(at):
    assert not at.exception, [e.value for e in at.exception]
    assert not [w.value for w in at.warning if "Não foi possível" in w.value]


def test_pagina_sem_dados(tmp_path):
    at = AppTest.from_string(_script(tmp_path / "vazio"), default_timeout=120)
    at.run()
    _sem_erros(at)
    textos = " ".join(m.value for m in at.markdown)
    assert "SHA-512" in textos and "ainda não disponível" in textos


def test_pagina_com_divergencia_e_consulta(pasta):
    at = AppTest.from_string(_script(pasta), default_timeout=120)
    at.run()
    _sem_erros(at)
    textos = " ".join(m.value for m in at.markdown)
    assert "Seções verificadas" in textos and "Assinaturas válidas" in textos
    assert any("divergência" in w.value for w in at.warning)

    at.selectbox(key="integ_uf").set_value("ac").run()
    at.selectbox(key="integ_mun").set_value("01007").run()
    at.selectbox(key="integ_zona").set_value("0009").run()
    at.selectbox(key="integ_secao").set_value("0002").run()
    _sem_erros(at)
    codigos = " ".join(c.value for c in at.code)
    assert "SHA-512 calculado" in codigos and "MD5" in codigos
    assert any("zona 0009, seção 0002" in m.value for m in at.markdown)

    at.button(key="integ_csv_preparar").click().run()
    _sem_erros(at)


def test_pagina_sem_divergencia_mostra_estado_vazio(tmp_path):
    p = sint.gerar(tmp_path / "integridade", divergente=False)
    at = AppTest.from_string(_script(p), default_timeout=120)
    at.run()
    _sem_erros(at)
    assert any("Nenhuma divergência encontrada nas 6 seções verificadas" in m.value for m in at.markdown)


def test_navegacao_registra_pagina():
    script = (
        "import sys\n"
        f"sys.path.insert(0, {str(SRC)!r})\n"
        "from dataurnas.dashboard.navigation import build_navigation\n"
        "import streamlit as st\n"
        "nav = build_navigation()\n"
        "st.write('|'.join(p.title for p in nav['Eleições 2026']))\n"
    )
    at = AppTest.from_string(script, default_timeout=60)
    at.run()
    assert not at.exception
    assert any("Integridade dos arquivos (2026)" in m.value for m in at.markdown)


# ----------------------------------------------------------------------
# Relatório
# ----------------------------------------------------------------------
def _relatorio_mod():
    path = ROOT / "scripts" / "docs" / "gerar_relatorio_integridade.py"
    spec = importlib.util.spec_from_file_location("gerar_relatorio_integridade", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_relatorio_dados_parciais(pasta, tmp_path):
    mod = _relatorio_mod()
    md = tmp_path / "relatorio.md"
    svg = tmp_path / "grafico.svg"
    mod.gerar(pasta=pasta, res_uf=sint.res_uf_sintetico(), saida_md=md, saida_svg=svg)
    texto = md.read_text(encoding="utf-8")
    assert "Cobertura" in texto and "66,67%" in texto
    assert "0002" in texto  # seção divergente listada
    assert "hashlib.sha512" in texto  # receita de verificação manual
    assert not any(t in texto for t in TRAVESSOES)
    conteudo = svg.read_text(encoding="utf-8")
    assert conteudo.startswith("<svg") and "Integridade" in conteudo


def test_relatorio_sem_dados(tmp_path):
    mod = _relatorio_mod()
    md = tmp_path / "relatorio.md"
    svg = tmp_path / "grafico.svg"
    mod.gerar(pasta=tmp_path / "vazio", res_uf=sint.res_uf_sintetico(), saida_md=md, saida_svg=svg)
    assert "ainda não" in md.read_text(encoding="utf-8")
    assert svg.read_text(encoding="utf-8").startswith("<svg")
