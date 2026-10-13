"""Biometria e segurança da identificação do eleitor."""

import streamlit as st
import plotly.graph_objects as go

from dataurnas.dashboard.state import analysis
from dataurnas.dashboard.components.charts import C_BLUE, C_GREEN, C_VERMILLION, show_chart
from dataurnas.dashboard.components.errors import show_error
from dataurnas.dashboard.components.formatting import fmt_int
from dataurnas.dashboard.components.tables import show_df


def tab_biometria_timing(store, f):
    """Aba de Biometria & Timing."""
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Biometria por Estado")
        bio_df = store.query_df(f"""
            SELECT
                UPPER(s.uf) as estado,
                SUM(s.comp_biometrico) as biometria,
                SUM(s.lib_codigo) as codigo,
                ROUND(SUM(s.comp_biometrico)*100.0/NULLIF(SUM(s.comp_biometrico)+SUM(s.lib_codigo),0), 1) as pct_bio
            FROM secoes s
            WHERE {f['where']}
            GROUP BY s.uf
            ORDER BY pct_bio
        """, f["params"])
        if not bio_df.empty:
            show_df(bio_df, width="stretch")
            st.bar_chart(bio_df.set_index("estado")[["pct_bio"]])

    with col2:
        st.subheader("Duração da Votação")
        timing_df = store.query_df(f"""
            SELECT
                UPPER(s.uf) as estado,
                ROUND(AVG(s.duracao_min), 0) as media_min,
                MIN(s.duracao_min) as min_min,
                MAX(s.duracao_min) as max_min
            FROM secoes s
            WHERE {f['where']} AND s.duracao_min IS NOT NULL
            GROUP BY s.uf
            ORDER BY media_min
        """, f["params"])
        if not timing_df.empty:
            show_df(timing_df, width="stretch")
            st.bar_chart(timing_df.set_index("estado")[["media_min"]])

    st.subheader("Seções com Reinicializações")
    reboot_df = store.query_df(f"""
        SELECT
            s.id,
            UPPER(s.uf) as uf,
            s.municipio,
            s.zona,
            s.secao,
            'UE' || s.modelo_urna as modelo,
            s.reboots,
            s.hora_abertura,
            s.hora_encerramento,
            s.comparecimento,
            s.votos_log
        FROM secoes s
        WHERE {f['where']} AND s.reboots > 0
        ORDER BY s.reboots DESC
    """, f["params"])
    if not reboot_df.empty:
        show_df(reboot_df, width="stretch")
    else:
        st.info("Nenhum reboot detectado nos filtros atuais.")

    # Enhanced: Zero-biometry sections
    st.subheader("Seções com Biometria Zero")
    try:
        zero_bio_df = analysis.zero_biometry_sections(store, f)
        if not zero_bio_df.empty:
            st.metric("Seções com 0% Biometria", f"{fmt_int(len(zero_bio_df))}")
            show_df(zero_bio_df, width="stretch", hide_index=True)
        else:
            st.info("Nenhuma seção com biometria zero encontrada.")
    except Exception as e:
        show_error("Erro ao carregar seções com biometria zero", e)

    # Enhanced: Biometry vs vote correlation
    st.subheader("Biometria vs Padrão de Votação")
    try:
        bio_vote_df = analysis.biometry_vs_vote(store, f)
        if not bio_vote_df.empty:
            show_df(bio_vote_df, width="stretch", hide_index=True)

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=bio_vote_df["quartil"],
                y=bio_vote_df["pct_lula"],
                name="Lula (%)",
                marker_color=C_VERMILLION,
            ))
            fig.add_trace(go.Bar(
                x=bio_vote_df["quartil"],
                y=bio_vote_df["pct_bolso"],
                name="Bolsonaro (%)",
                marker_color=C_BLUE,
            ))
            fig.update_layout(
                barmode="group",
                xaxis_title="Quartil de Biometria",
                yaxis_title="Percentual de Votos (%)",
                title="Votação por Quartil de Biometria",
                height=400,
            )
            show_chart(fig)

            st.caption(
                "Se a proporção de biometria não tiver correlação com o resultado, "
                "isso indica que a liberação por código não está associada a manipulação."
            )
        else:
            st.info("Sem dados de biometria vs votação.")
    except Exception as e:
        show_error("Erro ao carregar biometria vs votação", e)

    # Extensão: histograma de biometria
    extend_tab_biometria(store, f)


def extend_tab_biometria(store, f):
    """Seção adicional para tab_biometria: Histograma de biometria."""
    st.markdown("---")
    st.markdown("### Histograma de Biometria")
    st.caption("Distribuição do percentual de biometria em faixas de 5%")

    try:
        hist_df = analysis.biometry_histogram_data(store, f)
        if not hist_df.empty:
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=hist_df["faixa"],
                y=hist_df["quantidade"],
                marker_color=C_GREEN,
                text=hist_df["quantidade"],
                textposition="auto",
            ))
            fig.update_layout(
                xaxis_title="Faixa de Biometria (%)",
                yaxis_title="Quantidade de Seções",
                title="Distribuição do Percentual de Biometria",
                height=450,
                xaxis_tickangle=-45,
            )
            show_chart(fig)

            show_df(hist_df, width="stretch", hide_index=True)
        else:
            st.info("Sem dados para o histograma de biometria.")
    except Exception as e:
        show_error("Erro ao carregar histograma de biometria", e)
