"""Catálogo de hashes por arquivo de 2026 publicado como anexos (sem rede).

Os ``arquivos_<uf>.parquet`` não ficam no git: o painel baixa só a UF consultada,
confere o SHA-256 contra ``catalogo_manifest.json`` e guarda em cache. Aqui o
"servidor" é uma pasta local e a rede é substituída em ``ig._abrir_url``.
"""

import importlib.util
import json
import sys
import urllib.error
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import integridade_sintetica as sint  # noqa: E402

from dataurnas.dashboard import integridade2026 as ig  # noqa: E402


def _publicar_mod():
    path = ROOT / "scripts" / "ele2026" / "publicar_catalogo.py"
    spec = importlib.util.spec_from_file_location("publicar_catalogo", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def publicado(tmp_path, monkeypatch):
    """Pasta de integridade sem os catálogos locais, com manifesto e anexos num "servidor"."""
    pasta = sint.gerar(tmp_path / "integridade", arquivo_corrompido=False)
    servidor = tmp_path / "servidor"
    manifesto = _publicar_mod().montar(pasta, servidor, "v9.9.9", "exemplo/repo")
    for p in pasta.glob("arquivos_*.parquet"):
        p.unlink()
    pedidos: list[str] = []

    def _abrir(url, timeout):
        pedidos.append(url)
        return (servidor / url.rsplit("/", 1)[1]).open("rb")

    monkeypatch.setattr(ig, "_abrir_url", _abrir)
    monkeypatch.setenv("DATAURNAS_CATALOGO_CACHE", str(tmp_path / "cache"))
    monkeypatch.setenv("DATAURNAS_CATALOGO_URL", "https://exemplo.invalid/anexos")
    ig._VERIFICADOS.clear()
    return pasta, servidor, manifesto, pedidos


# ----------------------------------------------------------------------
# Script de publicação
# ----------------------------------------------------------------------
def test_publicar_gera_sums_e_manifesto(publicado):
    pasta, servidor, manifesto, _ = publicado
    nomes = [e["arquivo"] for e in manifesto["arquivos"]]
    assert nomes == ["arquivos_ac.parquet", "arquivos_sp_1.parquet", "arquivos_sp_2.parquet",
                     "arquivos_zz.parquet"]
    assert [e["uf"] for e in manifesto["arquivos"]] == ["ac", "sp", "sp", "zz"]
    assert manifesto["total_linhas"] == 36 and manifesto["versao"] == "v9.9.9"
    assert "sha512" in manifesto["arquivos"][0]["colunas"]
    sums = (servidor / "SHA256SUMS").read_text(encoding="utf-8").splitlines()
    assert sums[0] == f"{manifesto['arquivos'][0]['sha256']}  arquivos_ac.parquet"
    assert json.loads((pasta / ig.MANIFESTO).read_text(encoding="utf-8")) == manifesto
    cmd = _publicar_mod().comando_upload(servidor, "v9.9.9", "exemplo/repo")
    assert cmd.startswith("gh release upload v9.9.9 ") and "SHA256SUMS" in cmd


# ----------------------------------------------------------------------
# Download sob demanda
# ----------------------------------------------------------------------
def test_indicadores_nao_precisam_do_catalogo(publicado):
    pasta, _, _, pedidos = publicado
    dados = ig.load_secoes(pasta)
    t = ig.totais(dados.secoes, sint.res_uf_sintetico())
    assert dados.origem == "secoes.parquet" and t["arquivos"] == 36 and t["hash_diverge"] == 1
    assert ig.contagens_2026(t, pasta)["hash_diverge"] == 1
    assert ig.contar_pelas_secoes(dados.secoes, "sp") == 12
    assert ig.contar_pelas_secoes(dados.secoes, "ac", apenas_divergentes=True) == 1
    assert ig.contar_catalogo("ac", pasta=pasta) == 0  # contar não baixa nada
    assert pedidos == []


def test_consulta_baixa_so_a_uf_e_reaproveita_o_cache(publicado):
    pasta, _, _, pedidos = publicado
    assert not ig.catalogo_local("ac", pasta)
    a = ig.arquivos_da_secao("ac", "01007", "0009", "0002", pasta).set_index("tipo")
    assert a.loc["bu", "situacao_hash"] == "Diverge"
    assert pedidos == ["https://exemplo.invalid/anexos/arquivos_ac.parquet"]
    ig._VERIFICADOS.clear()  # nova sessão: confere o SHA-256 do cache sem baixar de novo
    assert len(ig.arquivos_da_secao("ac", "01007", "0009", "0001", pasta)) == 6
    assert len(pedidos) == 1
    csv = ig.catalogo_csv("sp", pasta=pasta).decode("utf-8-sig").strip().splitlines()
    assert len(csv) == 13  # cabeçalho + 12 arquivos das duas partes de SP
    assert sorted(u.rsplit("/", 1)[1] for u in pedidos[1:]) == ["arquivos_sp_1.parquet", "arquivos_sp_2.parquet"]


def test_url_modelo_por_variavel(monkeypatch):
    monkeypatch.setenv("DATAURNAS_CATALOGO_URL", "https://espelho.invalid/c/{arquivo}?dl=1")
    assert ig.url_catalogo("arquivos_ac.parquet") == "https://espelho.invalid/c/arquivos_ac.parquet?dl=1"
    monkeypatch.delenv("DATAURNAS_CATALOGO_URL")
    assert ig.url_catalogo("arquivos_ac.parquet") == f"{ig.CATALOGO_URL_PADRAO}/arquivos_ac.parquet"
    assert "releases/download/v0.2.1" in ig.CATALOGO_URL_PADRAO


def test_cache_corrompido_e_baixado_de_novo(publicado, tmp_path):
    pasta, _, _, pedidos = publicado
    caminho = ig.catalogo_uf("zz", pasta)[0]
    caminho.write_bytes(b"x" * caminho.stat().st_size)
    ig._VERIFICADOS.clear()
    assert ig.catalogo_uf("zz", pasta)[0] == caminho
    assert len(pedidos) == 2 and len(ig.arquivos_da_secao("zz", "29998", "0001", "0001", pasta)) == 6


def test_sha256_divergente_descarta(publicado, monkeypatch, tmp_path):
    pasta, _, _, _ = publicado
    import io

    monkeypatch.setattr(ig, "_abrir_url", lambda url, timeout: io.BytesIO(b"conteudo trocado"))
    with pytest.raises(ig.CatalogoIndisponivel, match="não confere com o SHA-256"):
        ig.catalogo_uf("zz", pasta)
    assert not list((tmp_path / "cache").glob("*"))


def test_sem_rede_mensagem_amigavel(publicado, monkeypatch):
    pasta, _, _, _ = publicado

    def _falha(url, timeout):
        raise urllib.error.URLError("sem conexão")

    monkeypatch.setattr(ig, "_abrir_url", _falha)
    with pytest.raises(ig.CatalogoIndisponivel, match="não pôde ser baixado agora .sem conexão.") as exc:
        ig.arquivos_da_secao("ac", "01007", "0009", "0002", pasta)
    assert "https://exemplo.invalid/anexos/arquivos_ac.parquet" in str(exc.value)


def test_limite_de_tamanho_impede_download(publicado, monkeypatch):
    pasta, _, _, pedidos = publicado
    monkeypatch.setenv("DATAURNAS_CATALOGO_MAX_MB", "0")
    with pytest.raises(ig.CatalogoIndisponivel, match="acima do limite"):
        ig.catalogo_uf("ac", pasta)
    assert pedidos == []


def test_limpeza_do_cache_respeita_o_limite(publicado, monkeypatch, tmp_path):
    pasta, _, _, _ = publicado
    monkeypatch.setenv("DATAURNAS_CATALOGO_CACHE_MB", "0")
    ig.catalogo_uf("ac", pasta)
    ultimo = ig.catalogo_uf("zz", pasta)[0]
    assert [p.name for p in (tmp_path / "cache").glob("*.parquet")] == [ultimo.name]


def test_sem_manifesto_nao_tenta_rede(tmp_path, monkeypatch):
    pasta = sint.gerar(tmp_path / "integridade", arquivo_corrompido=False)
    for p in pasta.glob("arquivos_*.parquet"):
        p.unlink()
    monkeypatch.setattr(ig, "_abrir_url", lambda url, timeout: pytest.fail("não deveria acessar a rede"))
    assert ig.arquivos_da_secao("ac", "01007", "0009", "0002", pasta).empty


def test_catalogo_local_tem_prioridade(tmp_path, monkeypatch):
    pasta = sint.gerar(tmp_path / "integridade", arquivo_corrompido=False)
    _publicar_mod().montar(pasta, tmp_path / "servidor", "v9.9.9", "exemplo/repo")
    monkeypatch.setattr(ig, "_abrir_url", lambda url, timeout: pytest.fail("não deveria acessar a rede"))
    assert ig.catalogo_local("ac", pasta)
    assert len(ig.arquivos_da_secao("ac", "01007", "0009", "0002", pasta)) == 6


# ----------------------------------------------------------------------
# Página (AppTest) sem os catálogos locais
# ----------------------------------------------------------------------
AppTest = pytest.importorskip("streamlit.testing.v1").AppTest


def _script(pasta: Path, servidor: Path | None, cache: Path) -> str:
    rede = (f"ig._abrir_url = lambda url, timeout: (Path({str(servidor)!r}) / url.rsplit('/', 1)[1]).open('rb')\n"
            if servidor else
            "def _falha(url, timeout):\n"
            "    raise urllib.error.URLError('sem conexão')\n"
            "ig._abrir_url = _falha\n")
    return (
        "import os, sys, urllib.error\n"
        "from pathlib import Path\n"
        f"sys.path.insert(0, {str(SRC)!r})\n"
        f"os.environ['DATAURNAS_CATALOGO_CACHE'] = {str(cache)!r}\n"
        "from dataurnas.dashboard import integridade2026 as ig\n"
        f"ig.integ_dir = lambda base=None: Path({str(pasta)!r})\n"
        + rede +
        "from dataurnas.dashboard.pages import integridade_2026\n"
        "integridade_2026.render()\n"
    )


def _consultar(at, secao="0002"):
    at.selectbox(key="integ_uf").set_value("ac").run()
    at.selectbox(key="integ_mun").set_value("01007").run()
    at.selectbox(key="integ_zona").set_value("0009").run()
    at.selectbox(key="integ_secao").set_value(secao).run()


def test_pagina_baixa_catalogo_sob_demanda(publicado, tmp_path):
    pasta, servidor, _, _ = publicado
    at = AppTest.from_string(_script(pasta, servidor, tmp_path / "cache_app"), default_timeout=120)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    textos = " ".join(m.value for m in at.markdown)
    assert "Seções verificadas" in textos
    assert not list((tmp_path / "cache_app").glob("*.parquet"))  # nada baixado só para abrir a página
    _consultar(at)
    assert not at.exception, [e.value for e in at.exception]
    assert "SHA-512 calculado" in " ".join(c.value for c in at.code)
    at.button(key="integ_csv_preparar").click().run()
    assert not at.exception
    assert not [w.value for w in at.warning if "baixado" in w.value]


def test_pagina_sem_rede_mostra_aviso(publicado, tmp_path):
    pasta, _, _, _ = publicado
    at = AppTest.from_string(_script(pasta, None, tmp_path / "cache_app"), default_timeout=120)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert "Seções verificadas" in " ".join(m.value for m in at.markdown)  # indicadores seguem
    _consultar(at, "0001")  # outra seção: a consulta do teste anterior pode estar no st.cache_data
    assert not at.exception, [e.value for e in at.exception]
    assert any("não pôde ser baixado agora" in w.value for w in at.warning)
    at.button(key="integ_csv_preparar").click().run()
    assert not at.exception
    assert not [w.value for w in at.warning if "Não foi possível" in w.value]
