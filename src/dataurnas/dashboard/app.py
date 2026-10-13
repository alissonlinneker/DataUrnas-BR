"""DataUrnas-BR: dashboard de auditoria eleitoral (ponto de entrada).

Execução: ``streamlit run src/dataurnas/dashboard/app.py``

Estrutura:
- ``pages/``: uma função de renderização por análise; só a página escolhida roda
  (``st.navigation``), ao contrário das 22 abas antigas que executavam tudo a
  cada interação.
- ``filters.py``: filtros da auditoria 2022 (barra lateral).
- ``state.py``: conexão DuckDB compartilhada e cache de consultas/análises.
- ``components/``: formatação pt-BR, gráficos, tabelas, erros e identidade visual.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import streamlit as st

# Permite `streamlit run` sem instalar o pacote (src/ no sys.path)
_SRC = Path(__file__).resolve().parents[2]
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from dataurnas.dashboard.components import ui  # noqa: E402
from dataurnas.dashboard.filters import persist_widget_state  # noqa: E402
from dataurnas.dashboard.navigation import build_navigation  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

ASSETS = Path(__file__).resolve().parent / "assets"

st.set_page_config(
    page_title="DataUrnas-BR | Auditoria Eleitoral",
    page_icon=str(ASSETS / "logo.svg"),
    layout="wide",
    initial_sidebar_state="auto",
    menu_items={
        "Get help": ui.REPO_URL,
        "Report a bug": f"{ui.REPO_URL}/issues",
        "About": "DataUrnas-BR: auditoria independente de dados públicos das urnas eletrônicas (TSE).",
    },
)


def main() -> None:
    persist_widget_state()
    ui.inject_css()
    st.logo(str(ASSETS / "logo.svg"), size="large", link=ui.REPO_URL)
    page = st.navigation(build_navigation(), position="sidebar", expanded=False)
    page.run()
    ui.footer()


main()
