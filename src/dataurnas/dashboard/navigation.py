"""Registro das páginas do dashboard e o invólucro comum das páginas de 2022."""

from __future__ import annotations

from collections.abc import Callable

import streamlit as st

from dataurnas.dashboard.components import ui
from dataurnas.dashboard.components.errors import safe_section
from dataurnas.dashboard.components.kpis import render_kpis
from dataurnas.dashboard.filters import render_sidebar
from dataurnas.dashboard.pages import (
    a03,
    benford,
    biometria,
    eleicoes_2026,
    estados,
    explorador,
    geografia,
    inconsistencias,
    integridade_2026,
    modelos,
    outliers,
    reboots,
    reserva,
    timing,
    turnos,
    veredicto,
    votacao,
)
from dataurnas.dashboard.state import clear_caches, get_store


def pagina_2022(render_fn: Callable, nome: str) -> Callable[[], None]:
    """Envolve uma análise de 2022: banco, filtros, cabeçalho, KPIs e isolamento de erros."""

    def run() -> None:
        store = get_store()
        if store is None:
            ui.header("Auditoria Eleitoral: Eleições 2022", "Banco de dados da auditoria indisponível",
                      eyebrow="Auditoria 2022")
            ui.empty_state(
                "Banco de 2022 não encontrado",
                "Gere o banco com: python scripts/build_db.py --no-live (leva alguns minutos e usa cerca "
                "de 2 GB). A página de 2026 funciona sem ele.",
                image="empty-database.svg",
            )
            return
        filtros = render_sidebar(store)
        if st.sidebar.button("Limpar cache e recarregar", help="Descarta resultados em cache e refaz as consultas"):
            clear_caches()
            st.rerun()
        ui.header(
            "Auditoria Eleitoral: Eleições 2022",
            f"{nome} · {filtros.turno_label if filtros.turno else 'Ambos os turnos'}",
            eyebrow="Auditoria 2022",
        )
        if not render_kpis(store, filtros):
            return
        with safe_section(nome.lower()):
            render_fn(store, filtros)

    run.__name__ = f"page_{render_fn.__name__}"
    return run


def _page(render_fn: Callable, titulo: str, slug: str, icon: str) -> st.Page:
    return st.Page(pagina_2022(render_fn, titulo), title=titulo, url_path=slug, icon=icon)


def build_navigation() -> dict[str, list]:
    return {
        "Eleições 2026": [
            st.Page(eleicoes_2026.render, title="Presidente 1º turno", url_path="eleicoes-2026",
                    icon=":material/how_to_vote:", default=True),
            st.Page(integridade_2026.render, title="Integridade dos arquivos (2026)", url_path="integridade-2026",
                    icon=":material/verified_user:"),
        ],
        "Auditoria 2022: visão geral": [
            _page(veredicto.tab_veredicto, "Veredicto final", "veredicto", ":material/gavel:"),
            _page(inconsistencias.tab_inconsistencias, "Inconsistências", "inconsistencias", ":material/report:"),
            _page(estados.tab_estados, "Por estado", "estados", ":material/table_chart:"),
            _page(estados.tab_ranking_estados, "Ranking de risco", "ranking-risco", ":material/leaderboard:"),
        ],
        "Auditoria 2022: estatística": [
            _page(benford.tab_benford_v2, "Lei de Benford", "benford", ":material/functions:"),
            _page(outliers.tab_outliers, "Outliers estatísticos", "outliers", ":material/scatter_plot:"),
            _page(votacao.tab_votacao, "Votação", "votacao", ":material/ballot:"),
            _page(votacao.tab_nulos_brancos, "Nulos e brancos", "nulos-brancos", ":material/block:"),
            _page(votacao.tab_distribuicao_candidato, "Distribuição por candidato", "distribuicao-candidato",
                  ":material/bar_chart:"),
        ],
        "Auditoria 2022: urnas e logs": [
            _page(reboots.tab_reboots_impact, "Impacto de reboots", "reboots", ":material/restart_alt:"),
            _page(a03.tab_a03, "Análise A03", "a03", ":material/compare_arrows:"),
            _page(biometria.tab_biometria_timing, "Biometria e segurança", "biometria", ":material/fingerprint:"),
            _page(timing.tab_timing, "Horários e duração", "timing", ":material/schedule:"),
            _page(modelos.tab_modelos, "Modelos e hardware", "modelos", ":material/memory:"),
            _page(reserva.tab_reserva, "Seções reserva", "reserva", ":material/swap_horiz:"),
            _page(reserva.tab_substituicoes_erros, "Substituições e erros", "substituicoes", ":material/bug_report:"),
            _page(inconsistencias.tab_integridade, "Integridade (hash)", "integridade", ":material/verified:"),
        ],
        "Auditoria 2022: geografia e turnos": [
            _page(geografia.tab_mapa, "Mapa do Brasil", "mapa", ":material/map:"),
            _page(geografia.tab_geographic, "Anomalias geográficas", "anomalias-geograficas", ":material/public:"),
            _page(turnos.tab_comparacao_turnos, "1º x 2º turno", "turnos", ":material/sync_alt:"),
        ],
        "Auditoria 2022: dados": [
            _page(explorador.tab_drilldown, "Explorador de seção", "explorador", ":material/search:"),
            _page(explorador.tab_dados_brutos_v2, "Dados brutos", "dados-brutos", ":material/dataset:"),
        ],
    }
