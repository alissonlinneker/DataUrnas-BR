"""Impacto de reinicializações (reboots) na votação."""

import streamlit as st
import plotly.graph_objects as go

from dataurnas.dashboard.state import analysis
from dataurnas.dashboard.components.charts import show_chart
from dataurnas.dashboard.components.errors import show_error
from dataurnas.dashboard.components.formatting import fmt_num
from dataurnas.dashboard.components.tables import show_df


def tab_reboots_impact(store, f):
    """Aba Impacto de Reboots na votação."""
    st.subheader("Impacto de Reboots na Votação")
    st.caption("Análise comparativa entre seções com e sem reinicializações")

    # Distribuição de votos: reboot vs não-reboot
    st.markdown("### Distribuição de Votos: Com Reboot vs Sem Reboot")
    try:
        dist_df = analysis.reboot_vote_distribution(store, f)
        if not dist_df.empty:
            fig = go.Figure()
            grupos = dist_df["grupo"].unique()
            for grupo in grupos:
                grp_data = dist_df[dist_df["grupo"] == grupo]
                fig.add_trace(go.Bar(
                    x=grp_data["candidato"].astype(str),
                    y=grp_data["pct"],
                    name=str(grupo),
                ))
            fig.update_layout(
                barmode="group",
                xaxis_title="Candidato",
                yaxis_title="Percentual (%)",
                height=400,
            )
            show_chart(fig)

            show_df(dist_df, width="stretch", hide_index=True)
        else:
            st.info("Sem dados suficientes para comparação.")
    except Exception as e:
        show_error("Erro ao carregar distribuição de votos por reboot", e)

    # Teste Qui-Quadrado de correlação
    st.markdown("### Teste de Correlação Estatística")
    try:
        corr = analysis.reboot_candidate_correlation(store, f)
        if corr:
            p_val = corr.get("p_value", 1.0)
            chi2_val = corr.get("chi2", 0)
            conclusion = corr.get("conclusion", "")

            col1, col2 = st.columns(2)
            col1.metric("Chi-Quadrado", f"{fmt_num(chi2_val, 4)}")
            col2.metric("P-Valor", f"{fmt_num(p_val, 4)}")

            if p_val > 0.05:
                st.success(f"Resultado: {conclusion}")
            elif p_val > 0.01:
                st.warning(f"Resultado: {conclusion}")
            else:
                st.error(f"Resultado: {conclusion}")
    except Exception as e:
        show_error("Erro ao carregar teste de correlação", e)

    # Impacto por estado
    st.markdown("### Impacto por Estado")
    try:
        state_df = analysis.reboot_by_state(store, f)
        if not state_df.empty:
            show_df(state_df, width="stretch", hide_index=True)
        else:
            st.info("Sem dados por estado.")
    except Exception as e:
        show_error("Erro ao carregar impacto por estado", e)

    # Padrões por modelo
    st.markdown("### Padrões de Reboot por Modelo de Urna")
    try:
        patterns_df = analysis.reboot_patterns(store, f)
        if not patterns_df.empty:
            show_df(patterns_df, width="stretch", hide_index=True)
        else:
            st.info("Sem dados de padrões.")
    except Exception as e:
        show_error("Erro ao carregar padrões de reboot", e)
