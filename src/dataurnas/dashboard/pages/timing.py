"""Duração e horários da votação."""

import streamlit as st
import plotly.graph_objects as go

from dataurnas.dashboard.state import analysis
from dataurnas.dashboard.components.charts import C_BLUE, C_VERMILLION, show_chart
from dataurnas.dashboard.components.errors import show_error
from dataurnas.dashboard.components.formatting import fmt_int
from dataurnas.dashboard.components.tables import show_df


def tab_timing(store, f):
    """Aba Timing Detalhado: duração da votação."""
    st.subheader("Timing Detalhado: Duração da Votação")
    st.caption("Análise detalhada da duração de votação por estado e detecção de anomalias")

    # Distribuição por estado
    st.markdown("### Distribuição de Duração por Estado")
    try:
        dur_df = analysis.duration_distribution(store, f)
        if not dur_df.empty:
            show_df(dur_df, width="stretch", hide_index=True)

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=dur_df["uf"],
                y=dur_df["media_min"],
                name="Média (min)",
                marker_color=C_BLUE,
            ))
            fig.add_trace(go.Bar(
                x=dur_df["uf"],
                y=dur_df["mediana_min"],
                name="Mediana (min)",
                marker_color=C_VERMILLION,
            ))
            fig.update_layout(
                barmode="group",
                xaxis_title="UF",
                yaxis_title="Duração (minutos)",
                height=400,
            )
            show_chart(fig)
        else:
            st.info("Sem dados de duração.")
    except Exception as e:
        show_error("Erro ao carregar distribuição de duração", e)

    # Seções com duração anormal
    st.markdown("### Seções com Duração Anormal")
    try:
        abnormal_df = analysis.abnormal_duration_sections(store, f)
        if not abnormal_df.empty:
            st.metric("Seções com Duração Anormal", f"{fmt_int(len(abnormal_df))}")
            show_df(abnormal_df, width="stretch", hide_index=True)
        else:
            st.info("Nenhuma seção com duração anormal detectada.")
    except Exception as e:
        show_error("Erro ao carregar seções com duração anormal", e)

    # Duração vs votação
    st.markdown("### Duração vs Padrão de Votação")
    try:
        dvote_df = analysis.duration_vs_vote(store, f)
        if not dvote_df.empty:
            show_df(dvote_df, width="stretch", hide_index=True)

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=dvote_df["quartil"],
                y=dvote_df["pct_lula"],
                name="Lula (%)",
                marker_color=C_VERMILLION,
            ))
            fig.add_trace(go.Bar(
                x=dvote_df["quartil"],
                y=dvote_df["pct_bolso"],
                name="Bolsonaro (%)",
                marker_color=C_BLUE,
            ))
            fig.update_layout(
                barmode="group",
                xaxis_title="Quartil de Duração",
                yaxis_title="Percentual de Votos (%)",
                title="Votação por Quartil de Duração",
                height=400,
            )
            show_chart(fig)

            st.caption(
                "Se houver correlação entre duração da votação e resultado, "
                "pode indicar fatores geográficos ou demográficos, não necessariamente irregularidade."
            )
        else:
            st.info("Sem dados de duração vs votação.")
    except Exception as e:
        show_error("Erro ao carregar duração vs votação", e)

    # Extensão: histograma de duração
    extend_tab_timing(store, f)


def extend_tab_timing(store, f):
    """Seção adicional para tab_timing: Histograma de duração."""
    st.markdown("---")
    st.markdown("### Histograma de Duração da Votação")
    st.caption("Distribuição da duração em faixas de 30 minutos")

    try:
        hist_df = analysis.duration_histogram_data(store, f)
        if not hist_df.empty:
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=hist_df["faixa"],
                y=hist_df["quantidade"],
                marker_color=C_BLUE,
                text=hist_df["quantidade"],
                textposition="auto",
            ))
            fig.update_layout(
                xaxis_title="Faixa de Duração",
                yaxis_title="Quantidade de Seções",
                title="Distribuição da Duração da Votação",
                height=450,
                xaxis_tickangle=-45,
            )
            show_chart(fig)

            show_df(hist_df, width="stretch", hide_index=True)
        else:
            st.info("Sem dados para o histograma de duração.")
    except Exception as e:
        show_error("Erro ao carregar histograma de duração", e)
