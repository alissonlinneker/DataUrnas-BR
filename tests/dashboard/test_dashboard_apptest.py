"""Smoke test do app com streamlit.testing (página inicial de 2026 e páginas leves de 2022)."""

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest

APP = SRC / "dataurnas" / "dashboard" / "app.py"


def test_app_inicial_2026_roda_sem_excecao():
    at = AppTest.from_file(str(APP), default_timeout=180)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    textos = " ".join(m.value for m in at.markdown)
    assert "Eleições 2026" in textos
    # nenhuma mensagem de erro amigável disparada por exceção interna
    assert not [w.value for w in at.warning if "Não foi possível" in w.value]


def _db_disponivel() -> bool:
    from dataurnas.dashboard.state import candidate_db_paths

    return any(p.exists() for p in candidate_db_paths())


@pytest.mark.skipif(not _db_disponivel(), reason="banco de 2022 não construído (scripts/build_db.py)")
@pytest.mark.parametrize(
    ("modulo", "funcao"),
    [
        ("inconsistencias", "tab_inconsistencias"),
        ("estados", "tab_estados"),
        ("estados", "tab_ranking_estados"),
        ("a03", "tab_a03"),
        ("inconsistencias", "tab_integridade"),
        ("geografia", "tab_mapa"),
        ("turnos", "tab_comparacao_turnos"),
        ("explorador", "tab_drilldown"),
        ("explorador", "tab_dados_brutos_v2"),
    ],
)
def test_paginas_2022_rodam_sem_excecao(modulo, funcao):
    script = (
        "import sys\n"
        f"sys.path.insert(0, {str(SRC)!r})\n"
        "from dataurnas.dashboard.navigation import pagina_2022\n"
        f"from dataurnas.dashboard.pages import {modulo}\n"
        f"pagina_2022({modulo}.{funcao}, 'teste')()\n"
    )
    at = AppTest.from_string(script, default_timeout=300)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert not [w.value for w in at.warning if "Não foi possível" in w.value]


def test_pagina_2022_sem_banco_mostra_estado_vazio(monkeypatch, tmp_path):
    script = (
        "import sys\n"
        f"sys.path.insert(0, {str(SRC)!r})\n"
        "from dataurnas.dashboard import state\n"
        "state.candidate_db_paths = lambda: []\n"
        "import dataurnas.dashboard.navigation as nav\n"
        "from dataurnas.dashboard.pages import estados\n"
        "nav.pagina_2022(estados.tab_estados, 'teste')()\n"
    )
    at = AppTest.from_string(script, default_timeout=60)
    at.run()
    assert not at.exception
    assert any("Banco de 2022 não encontrado" in m.value for m in at.markdown)
