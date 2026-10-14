"""Outliers estatísticos (z-score global e por UF)."""

import streamlit as st
import plotly.express as px

from dataurnas.dashboard.state import analysis
from dataurnas.dashboard.components.charts import show_chart
from dataurnas.dashboard.components.errors import show_error
from dataurnas.dashboard.components.formatting import fmt_int
from dataurnas.dashboard.components.tables import show_df
from dataurnas.dashboard.components.ui import nota_grupo_analise


def tab_outliers(store, f):
    """Aba Outliers Estatísticos."""
    st.subheader("Outliers Estatísticos")
    st.caption("Seções com valores extremos (z-score > 3) em abstenção, biometria e duração")
    nota_grupo_analise("outliers")

    # Métricas resumo
    try:
        summary_df = analysis.outlier_summary(store, f)
        if not summary_df.empty:
            total_outliers = int(summary_df["total"].sum()) if "total" in summary_df.columns else 0
            st.metric("Total de Outliers Detectados", f"{fmt_int(total_outliers)}")

            st.markdown("### Resumo por Estado")
            show_df(summary_df, width="stretch", hide_index=True)
        else:
            st.info("Nenhum outlier detectado.")
    except Exception as e:
        show_error("Erro ao carregar resumo de outliers", e)

    # Detalhes dos outliers
    st.markdown("### Seções Outliers (detalhes)")
    try:
        outliers_df = analysis.zscore_outliers(store, f, threshold=3.0)
        if not outliers_df.empty:
            col1, col2, col3 = st.columns(3)
            metrics = outliers_df["metric"].value_counts()
            with col1:
                st.metric("Outliers Abstenção", int(metrics.get("abstencao", 0)))
            with col2:
                st.metric("Outliers Biometria", int(metrics.get("biometria", 0)))
            with col3:
                st.metric("Outliers Duração", int(metrics.get("duracao", 0)))

            # Scatter plot por métrica
            limited_df = outliers_df.head(200)
            fig = px.scatter(
                limited_df,
                x="zscore",
                y="value",
                color="metric",
                hover_data=["uf", "municipio", "zona", "secao"],
                title="Distribuição dos Outliers por Métrica",
                labels={"zscore": "Z-Score", "value": "Valor", "metric": "Métrica"},
            )
            fig.update_layout(height=450)
            show_chart(fig)

            st.markdown("### Tabela de Outliers (limite: 200)")
            show_df(limited_df, width="stretch", hide_index=True)
        else:
            st.info("Nenhum outlier detectado para o threshold atual.")
    except Exception as e:
        show_error("Erro ao carregar detalhes de outliers", e)

    # Extensão: outliers por estado (z-score local)
    extend_tab_outliers(store, f)


def extend_tab_outliers(store, f):
    """Seção adicional para tab_outliers: Outliers por Estado (z-score local)."""
    st.markdown("---")
    st.markdown("### Outliers por Estado (z-score local)")
    st.caption(
        "Z-score calculado por UF (média e desvio padrão locais), "
        "detectando seções atípicas dentro de cada estado"
    )

    try:
        state_outliers_df = analysis.zscore_outliers_by_state(store, f, threshold=3.0)
        if not state_outliers_df.empty:
            total_state_outliers = len(state_outliers_df)
            st.metric("Total de Outliers (por estado)", f"{fmt_int(total_state_outliers)}")

            resumo = state_outliers_df.groupby(["uf", "metrica"]).size().unstack(fill_value=0)
            if not resumo.empty:
                st.markdown("**Resumo por UF e Métrica**")
                show_df(resumo, width="stretch")

            limited = state_outliers_df.head(200)
            fig = px.scatter(
                limited,
                x="zscore",
                y="valor",
                color="metrica",
                facet_col="uf",
                facet_col_wrap=6,
                hover_data=["secao_id", "media_uf", "std_uf"],
                title="Outliers por Estado e Métrica",
                labels={
                    "zscore": "Z-Score (local)",
                    "valor": "Valor",
                    "metrica": "Métrica",
                },
            )
            fig.update_layout(height=600)
            show_chart(fig)

            st.markdown("### Tabela de Outliers por Estado (limite: 200)")
            show_df(limited, width="stretch", hide_index=True)
        else:
            st.info(
                "Nenhum outlier detectado com z-score local (por estado) > 3.0."
            )
    except Exception as e:
        show_error("Erro ao carregar outliers por estado", e)
