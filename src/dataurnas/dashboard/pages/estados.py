"""Métricas e ranking de risco por estado."""

import streamlit as st
import plotly.graph_objects as go

from dataurnas.dashboard.state import analysis
from dataurnas.dashboard.components.charts import C_GREEN, C_ORANGE, C_VERMILLION, show_chart
from dataurnas.dashboard.components.errors import show_error
from dataurnas.dashboard.components.tables import show_df


def tab_estados(store, f):
    """Aba por Estado."""
    st.subheader("Métricas por Estado")

    estado_df = store.query_df(f"""
        SELECT
            UPPER(s.uf) as estado,
            s.regiao,
            COUNT(*) as secoes,
            SUM(s.eleitores_aptos) as eleitores,
            SUM(s.comparecimento) as comparecimento,
            ROUND((1 - SUM(s.comparecimento)*1.0 / NULLIF(SUM(s.eleitores_aptos), 0)) * 100, 1) as abstencao_pct,
            SUM(s.reboots) as reboots,
            SUM(CASE WHEN s.has_issues THEN 1 ELSE 0 END) as com_issues,
            ROUND(AVG(s.pct_biometria), 1) as biometria_pct,
            ROUND(AVG(s.duracao_min), 0) as duracao_media
        FROM secoes s
        WHERE {f['where']}
        GROUP BY s.uf, s.regiao
        ORDER BY s.uf
    """, f["params"])

    if not estado_df.empty:
        show_df(estado_df, width="stretch")

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Abstenção por Estado")
            st.bar_chart(estado_df[["estado", "abstencao_pct"]].set_index("estado"))

        with col2:
            st.subheader("Reboots por Estado")
            st.bar_chart(estado_df[["estado", "reboots"]].set_index("estado"))
    else:
        st.info("Nenhum dado disponível.")


def tab_ranking_estados(store, f):
    """Tab Ranking de Risco por estado."""
    st.subheader("Ranking de Risco por Estado")
    st.caption(
        "Score de risco agregado por UF, baseado em reboots, issues e biometria zero"
    )

    try:
        ranking_df = analysis.state_risk_ranking(store, f)
    except Exception as e:
        show_error("Erro ao calcular ranking de risco", e)
        return

    if ranking_df.empty:
        st.info("Sem dados para calcular o ranking de risco.")
        return

    # ---- Tabela de ranking ----
    st.markdown("### Tabela de Ranking")
    show_df(ranking_df, width="stretch", hide_index=True)

    # ---- Gráfico de barras horizontal por score ----
    st.markdown("### Score de Risco por Estado")
    fig_bar = go.Figure()
    fig_bar.add_trace(go.Bar(
        x=ranking_df["score_risco"],
        y=ranking_df["uf"],
        orientation="h",
        marker_color=ranking_df["score_risco"].apply(
            lambda s: C_VERMILLION if s >= 60 else C_ORANGE if s >= 30 else C_GREEN
        ),
        text=ranking_df["score_risco"].round(1),
        textposition="auto",
    ))
    fig_bar.update_layout(
        xaxis_title="Score de Risco (0-100)",
        yaxis_title="UF",
        yaxis=dict(autorange="reversed"),
        height=max(400, len(ranking_df) * 25),
        margin=dict(l=10),
    )
    show_chart(fig_bar)

    # ---- Heatmap: UFs x métricas ----
    st.markdown("### Heatmap: UFs x Métricas de Risco")

    heatmap_data = ranking_df[["uf", "pct_reboots", "pct_issues", "pct_zero_bio"]].copy()
    heatmap_data = heatmap_data.set_index("uf")
    heatmap_data.columns = ["% Reboots", "% Issues", "% Bio Zero"]

    fig_heat = go.Figure(data=go.Heatmap(
        z=heatmap_data.values,
        x=heatmap_data.columns.tolist(),
        y=heatmap_data.index.tolist(),
        colorscale="YlOrRd",
        text=heatmap_data.values.round(2),
        texttemplate="%{text}",
        textfont={"size": 10},
        hovertemplate="UF: %{y}<br>Métrica: %{x}<br>Valor: %{z:.2f}%<extra></extra>",
    ))
    fig_heat.update_layout(
        title="Distribuição de Métricas de Risco por Estado",
        xaxis_title="Métrica",
        yaxis_title="UF",
        height=max(500, len(ranking_df) * 22),
    )
    show_chart(fig_heat)
