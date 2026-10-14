"""Anomalias geográficas e mapa do Brasil por UF."""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

from dataurnas.dashboard.state import analysis
from dataurnas.dashboard.components.charts import C_BLUE, C_ORANGE, C_VERMILLION, show_chart
from dataurnas.dashboard.components.errors import show_error
from dataurnas.dashboard.components.geo import FONTE_GEOJSON, brazil_geojson
from dataurnas.dashboard.components.tables import show_df


def tab_geographic(store, f):
    """Aba Anomalias Geográficas."""
    st.subheader("Anomalias Geográficas")
    st.caption("Análise da concentração de issues por estado e correlação com resultado eleitoral")

    # Densidade de issues por estado
    st.markdown("### Densidade de Issues por Estado")
    try:
        density_df = analysis.issue_density_by_state(store, f)
        if not density_df.empty:
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=density_df["uf"],
                y=density_df["density"],
                marker_color=density_df["z_density"].apply(
                    lambda z: C_VERMILLION if abs(z) > 2 else C_ORANGE if abs(z) > 1 else C_BLUE
                ),
                text=density_df["density"].round(2),
                textposition="auto",
            ))
            fig.update_layout(
                xaxis_title="UF",
                yaxis_title="Densidade (issues/seção)",
                title="Densidade de Issues por Estado",
                height=400,
            )
            show_chart(fig)

            show_df(density_df, width="stretch", hide_index=True)
        else:
            st.info("Sem dados de densidade.")
    except Exception as e:
        show_error("Erro ao carregar densidade de issues", e)

    # Correlação issues vs resultado
    st.markdown("### Densidade de Issues vs Resultado Eleitoral")
    try:
        corr_df = analysis.geographic_issue_vs_result(store, f)
        if not corr_df.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=corr_df["density"],
                y=corr_df["pct_lula"],
                mode="markers+text",
                text=corr_df["uf"],
                textposition="top center",
                name="% Lula",
                marker=dict(size=10, color=C_VERMILLION),
            ))
            fig.add_trace(go.Scatter(
                x=corr_df["density"],
                y=corr_df["pct_bolso"],
                mode="markers+text",
                text=corr_df["uf"],
                textposition="bottom center",
                name="% Bolsonaro",
                marker=dict(size=10, color=C_BLUE),
            ))
            fig.update_layout(
                xaxis_title="Densidade de Issues (issues/seção)",
                yaxis_title="Percentual de Votos (%)",
                title="Correlação: Densidade de Issues vs Resultado",
                height=500,
            )
            show_chart(fig)

            show_df(corr_df, width="stretch", hide_index=True)

            st.caption(
                "Se a densidade de issues não apresentar correlação com o resultado eleitoral, "
                "isso indica que as issues são de natureza operacional e não direcionadas."
            )
        else:
            st.info("Sem dados para correlação.")
    except Exception as e:
        show_error("Erro ao carregar correlação geográfica", e)


def tab_mapa(store, f):
    """Tab Mapa Choropleth do Brasil colorido por métrica selecionada."""
    import numpy as np

    st.subheader("Mapa do Brasil: Métricas por Estado")
    st.caption(
        "Visualização geográfica das métricas eleitorais. "
        "Selecione a métrica desejada para colorir o mapa."
    )

    geojson = brazil_geojson()

    # Obter dados
    try:
        metrics_df = analysis.map_state_metrics(store, f)
        votes_df = analysis.map_state_votes(store, f)
    except Exception as e:
        show_error("Erro ao carregar métricas do mapa", e)
        return

    if metrics_df.empty:
        st.info("Sem dados disponíveis para os filtros selecionados.")
        return

    # Merge métricas e votos
    if not votes_df.empty:
        df = metrics_df.merge(votes_df[["uf", "pct_lula", "pct_bolso"]], on="uf", how="left")
    else:
        df = metrics_df.copy()
        df["pct_lula"] = np.nan
        df["pct_bolso"] = np.nan

    # Criar coluna UF maiúscula para match com GeoJSON (propriedade "sigla")
    df["uf_upper"] = df["uf"].str.upper()

    # Seletor de métrica
    metric_options = {
        "Reboots (%)": "pct_reboots",
        "Issues por seção": "density_issues",
        "Abstenção (%)": "pct_abstencao",
        "Biometria (%)": "media_biometria",
        "% Lula": "pct_lula",
    }

    metric_label = st.selectbox("Métrica para coloração", list(metric_options.keys()))
    metric_col = metric_options[metric_label]

    if metric_col not in df.columns or df[metric_col].dropna().empty:
        st.info(f"Sem dados para a métrica '{metric_label}'.")
        return

    # Escala de cores
    if metric_col == "media_biometria":
        color_scale = "Cividis"
    elif metric_col == "pct_lula":
        color_scale = "RdBu_r"
    else:
        color_scale = "YlOrRd"

    # Criar mapa choropleth
    fig = px.choropleth(
        df,
        geojson=geojson,
        locations="uf_upper",
        featureidkey="properties.sigla",
        color=metric_col,
        color_continuous_scale=color_scale,
        title=f"Mapa: {metric_label}",
        hover_name="uf_upper",
        hover_data={
            "uf_upper": False,
            "secoes": True,
            "pct_reboots": ":.2f",
            "pct_issues": ":.2f",
            "pct_abstencao": ":.2f",
            "media_biometria": ":.2f",
            "density_issues": ":.4f",
        },
        labels={
            "pct_reboots": "Reboots (%)",
            "density_issues": "Issues/seção",
            "pct_abstencao": "Abstenção (%)",
            "media_biometria": "Biometria (%)",
            "pct_lula": "% Lula",
            "secoes": "Seções",
        },
    )
    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(height=560, margin=dict(l=0, r=0, t=40, b=0))

    show_chart(fig, caption=f"Malha territorial: {FONTE_GEOJSON}.")

    # Tabela de dados por UF
    st.markdown("### Dados por Estado")

    display_df = df.copy()
    display_df["uf"] = display_df["uf"].str.upper()
    display_cols = [
        "uf", "secoes", "pct_reboots", "pct_issues", "pct_abstencao",
        "media_biometria", "density_issues",
    ]
    if "pct_lula" in display_df.columns:
        display_cols.extend(["pct_lula", "pct_bolso"])

    display_cols = [c for c in display_cols if c in display_df.columns]

    show_df(
        display_df[display_cols].sort_values("uf").reset_index(drop=True),
        width="stretch",
        hide_index=True,
    )

    st.caption(
        "z_density: z-score da densidade de issues. "
        "Valores > 2 indicam estados com concentração atípica de issues."
    )
