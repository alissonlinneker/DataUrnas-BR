"""Modelos de urna e hardware."""

import streamlit as st
import plotly.graph_objects as go

from dataurnas.dashboard.state import analysis
from dataurnas.dashboard.components.charts import C_BLUE, C_ORANGE, C_VERMILLION, show_chart
from dataurnas.dashboard.components.errors import show_error
from dataurnas.dashboard.components.tables import show_df


def tab_modelos(store, f):
    """Aba de Modelos de Urna."""
    st.subheader("Distribuição por Modelo")

    modelo_df = store.query_df(f"""
        SELECT
            'UE' || s.modelo_urna as modelo,
            COUNT(*) as secoes,
            ROUND(AVG(s.reboots), 2) as media_reboots,
            SUM(s.reboots) as total_reboots,
            ROUND(AVG(s.pct_biometria), 1) as media_biometria,
            SUM(CASE WHEN s.has_issues THEN 1 ELSE 0 END) as com_issues,
            ROUND(SUM(CASE WHEN s.has_issues THEN 1.0 ELSE 0 END) / COUNT(*) * 100, 1) as pct_issues
        FROM secoes s
        WHERE {f['where']} AND s.modelo_urna IS NOT NULL
        GROUP BY s.modelo_urna
        ORDER BY s.modelo_urna
    """, f["params"])

    if not modelo_df.empty:
        show_df(modelo_df, width="stretch")

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Reboots por Modelo")
            st.bar_chart(modelo_df[["modelo", "media_reboots"]].set_index("modelo"))

        with col2:
            st.subheader("% Seções com Issues por Modelo")
            st.bar_chart(modelo_df[["modelo", "pct_issues"]].set_index("modelo"))
    else:
        st.info("Nenhum dado de modelo disponível.")

    st.subheader("Issues por Modelo de Urna")
    modelo_issues = store.query_df(f"""
        SELECT
            'UE' || s.modelo_urna as modelo,
            i.codigo,
            COUNT(*) as total
        FROM issues i JOIN secoes s ON i.secao_id = s.id
        WHERE {f['issue_where']} AND s.modelo_urna IS NOT NULL
        GROUP BY s.modelo_urna, i.codigo
        ORDER BY s.modelo_urna, total DESC
    """, f["issue_params"])
    if not modelo_issues.empty:
        pivot = modelo_issues.pivot_table(
            index="modelo", columns="codigo", values="total", fill_value=0
        )
        show_df(pivot, width="stretch")

    # Enhanced: Model vote pattern
    st.subheader("Padrão de Votação por Modelo")
    try:
        vote_pattern_df = analysis.model_vote_pattern(store, f)
        if not vote_pattern_df.empty:
            show_df(vote_pattern_df, width="stretch", hide_index=True)

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=vote_pattern_df["modelo"],
                y=vote_pattern_df["pct_lula"],
                name="Lula (%)",
                marker_color=C_VERMILLION,
            ))
            fig.add_trace(go.Bar(
                x=vote_pattern_df["modelo"],
                y=vote_pattern_df["pct_bolso"],
                name="Bolsonaro (%)",
                marker_color=C_BLUE,
            ))
            fig.update_layout(
                barmode="group",
                xaxis_title="Modelo",
                yaxis_title="Percentual (%)",
                title="Votação para Presidente por Modelo de Urna",
                height=400,
            )
            show_chart(fig)

            st.caption(
                "Variações entre modelos refletem distribuição geográfica. "
                "Modelos mais antigos predominam no Norte/Nordeste; mais novos no Sul/Sudeste."
            )
        else:
            st.info("Sem dados de padrão de votação por modelo.")
    except Exception as e:
        show_error("Erro ao carregar padrão de votação por modelo", e)

    # Enhanced: Model issue rate normalized
    st.subheader("Taxa de Issues por Modelo (Normalizada)")
    try:
        issue_rate_df = analysis.model_issue_rate(store, f)
        if not issue_rate_df.empty:
            show_df(issue_rate_df, width="stretch", hide_index=True)

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=issue_rate_df["modelo"],
                y=issue_rate_df["rate"],
                name="Taxa Total",
                marker_color=C_BLUE,
            ))
            if "rate_critica" in issue_rate_df.columns:
                fig.add_trace(go.Bar(
                    x=issue_rate_df["modelo"],
                    y=issue_rate_df["rate_critica"],
                    name="Taxa Crítica",
                    marker_color=C_VERMILLION,
                ))
            if "rate_alta" in issue_rate_df.columns:
                fig.add_trace(go.Bar(
                    x=issue_rate_df["modelo"],
                    y=issue_rate_df["rate_alta"],
                    name="Taxa Alta",
                    marker_color=C_ORANGE,
                ))
            fig.update_layout(
                barmode="group",
                xaxis_title="Modelo",
                yaxis_title="Issues / Seção",
                title="Taxa de Issues Normalizada por Modelo",
                height=400,
            )
            show_chart(fig)
        else:
            st.info("Sem dados de taxa de issues por modelo.")
    except Exception as e:
        show_error("Erro ao carregar taxa de issues por modelo", e)
