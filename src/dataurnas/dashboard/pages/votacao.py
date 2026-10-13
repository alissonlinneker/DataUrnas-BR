"""Votação, nulos e brancos e distribuição por candidato."""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

from dataurnas.dashboard.state import analysis
from dataurnas.dashboard.components.charts import C_BLUE, C_GREY, C_VERMILLION, show_chart
from dataurnas.dashboard.components.errors import show_error
from dataurnas.dashboard.components.formatting import fmt_int, fmt_pct
from dataurnas.dashboard.components.tables import show_df


def tab_votacao(store, f):
    """Aba de Votação."""
    st.subheader("Resultado da Votação")

    cargo_sel = st.selectbox("Cargo", [
        "Presidente", "Governador", "Senador",
        "Deputado Federal", "Deputado Estadual",
    ])

    votos_df = analysis.votos_por_candidato(store, f, cargo_sel)

    if not votos_df.empty:
        total_nominais = votos_df["votos"].sum()
        if total_nominais > 0:
            votos_df["pct"] = (votos_df["votos"] / total_nominais * 100).round(1)
        show_df(votos_df, width="stretch")

        st.bar_chart(
            votos_df.head(10).set_index("candidato")[["votos"]]
        )
    else:
        st.info(f"Nenhum voto nominal encontrado para {cargo_sel}.")

    st.subheader("Nulos e Brancos por Cargo")
    nb_df = store.query_df(f"""
        SELECT
            t.cargo,
            SUM(t.nominais) as nominais,
            SUM(t.brancos) as brancos,
            SUM(t.nulos) as nulos,
            SUM(t.total) as total,
            ROUND(SUM(t.brancos)*100.0/NULLIF(SUM(t.total),0), 1) as pct_brancos,
            ROUND(SUM(t.nulos)*100.0/NULLIF(SUM(t.total),0), 1) as pct_nulos
        FROM totais_cargo t JOIN secoes s ON t.secao_id = s.id
        WHERE {f['where']}
        GROUP BY t.cargo
        ORDER BY t.cargo
    """, f["params"])
    if not nb_df.empty:
        show_df(nb_df, width="stretch")


def tab_nulos_brancos(store, f):
    """Aba Nulos & Brancos - Análise de outliers em nulos e brancos."""
    st.subheader("Nulos & Brancos")
    st.caption("Detecção de seções com proporção anormal de votos nulos ou brancos (z-score > 3)")

    # ----------------------------------------------------------
    # Seção 1: KPIs
    # ----------------------------------------------------------
    try:
        summary_df = analysis.null_blank_summary(store, f)
        if not summary_df.empty:
            total_outliers_nulos = int(summary_df["outliers_nulos"].sum())
            total_outliers_brancos = int(summary_df["outliers_brancos"].sum())

            col1, col2 = st.columns(2)
            col1.metric("Total de Outliers de Nulos", f"{fmt_int(total_outliers_nulos)}")
            col2.metric("Total de Outliers de Brancos", f"{fmt_int(total_outliers_brancos)}")
        else:
            st.info("Nenhum outlier de nulos/brancos detectado.")
    except Exception as e:
        show_error("Erro ao carregar KPIs de nulos/brancos", e)

    # ----------------------------------------------------------
    # Seção 2: Resumo por estado
    # ----------------------------------------------------------
    st.markdown("### Resumo por Estado")
    try:
        summary_df = analysis.null_blank_summary(store, f)
        if not summary_df.empty:
            show_df(summary_df, width="stretch", hide_index=True)
        else:
            st.info("Sem dados de resumo por estado.")
    except Exception as e:
        show_error("Erro ao carregar resumo por estado", e)

    # ----------------------------------------------------------
    # Seção 3: Scatter plot pct_nulos vs pct_brancos
    # ----------------------------------------------------------
    st.markdown("### Dispersão: % Nulos vs % Brancos por Seção")
    try:
        scatter_df = store.query_df(f"""
            SELECT
                t.secao_id,
                s.uf,
                ROUND(t.nulos * 100.0 / NULLIF(t.total, 0), 2) AS pct_nulos,
                ROUND(t.brancos * 100.0 / NULLIF(t.total, 0), 2) AS pct_brancos
            FROM totais_cargo t
            JOIN secoes s ON t.secao_id = s.id
            WHERE {f['where']}
                AND t.cargo = 'Presidente'
                AND t.total > 0
            ORDER BY RANDOM()
            LIMIT 2000
        """, f["params"])

        if not scatter_df.empty:
            fig = px.scatter(
                scatter_df,
                x="pct_nulos",
                y="pct_brancos",
                color="uf",
                hover_data=["secao_id"],
                title="% Nulos vs % Brancos (Presidente, amostra de 2.000 seções)",
                labels={
                    "pct_nulos": "% Nulos",
                    "pct_brancos": "% Brancos",
                    "uf": "UF",
                },
                opacity=0.6,
            )
            fig.update_layout(height=500)
            show_chart(fig)
        else:
            st.info("Sem dados para o gráfico de dispersão.")
    except Exception as e:
        show_error("Erro ao carregar scatter de nulos/brancos", e)

    # ----------------------------------------------------------
    # Seção 4: Correlação nulos vs resultado
    # ----------------------------------------------------------
    st.markdown("### Correlação: Nulos vs Resultado Eleitoral")
    try:
        nb_result_df = analysis.null_blank_vs_result(store, f)
        if not nb_result_df.empty:
            show_df(nb_result_df, width="stretch", hide_index=True)

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=nb_result_df["quartil"],
                y=nb_result_df["pct_lula"],
                name="Lula (%)",
                marker_color=C_VERMILLION,
            ))
            fig.add_trace(go.Bar(
                x=nb_result_df["quartil"],
                y=nb_result_df["pct_bolso"],
                name="Bolsonaro (%)",
                marker_color=C_BLUE,
            ))
            fig.update_layout(
                barmode="group",
                xaxis_title="Quartil de % Nulos",
                yaxis_title="Percentual de Votos (%)",
                title="Votação por Quartil de Nulos (Presidente)",
                height=400,
            )
            show_chart(fig)

            st.caption(
                "Se a proporção de votos nulos não tiver correlação com o resultado, "
                "isso indica que os nulos refletem o comportamento do eleitor, "
                "não uma manipulação direcionada."
            )
        else:
            st.info("Sem dados de correlação nulos vs resultado.")
    except Exception as e:
        show_error("Erro ao carregar correlação nulos vs resultado", e)

    # ----------------------------------------------------------
    # Seção 5: Tabela de seções outliers
    # ----------------------------------------------------------
    st.markdown("### Seções Outliers de Nulos/Brancos")
    try:
        outliers_df = analysis.null_blank_by_section(store, f)
        if not outliers_df.empty:
            st.metric("Total de Seções Outliers", f"{fmt_int(len(outliers_df))}")
            show_df(outliers_df, width="stretch", hide_index=True)
        else:
            st.info("Nenhuma seção outlier detectada para os filtros atuais.")
    except Exception as e:
        show_error("Erro ao carregar seções outliers", e)


def tab_distribuicao_candidato(store, f):
    """Aba Distribuição por Candidato - Análise da votação Lula x Bolsonaro por seção."""
    st.subheader("Distribuição por Candidato")
    st.caption("Análise da distribuição de votos entre Lula (13) e Bolsonaro (22) por seção")

    # ----------------------------------------------------------
    # Seção 1: Histograma de pct_lula por seção
    # ----------------------------------------------------------
    st.markdown("### Histograma: % Lula por Seção (Presidente)")
    try:
        hist_df = analysis.presidente_13_22_por_secao(store, f)

        if not hist_df.empty:
            hist_df["pct_lula"] = (
                hist_df["votos_13"]
                / (hist_df["votos_13"] + hist_df["votos_22"])
                * 100
            ).round(2)

            fig = px.histogram(
                hist_df,
                x="pct_lula",
                nbins=50,
                title="Distribuição do % de Votos em Lula por Seção (Presidente)",
                labels={"pct_lula": "% Lula (votos válidos 13 vs 22)"},
                color_discrete_sequence=[C_BLUE],
            )
            fig.update_layout(
                xaxis_title="% Lula",
                yaxis_title="Quantidade de Seções",
                height=450,
            )
            fig.add_vline(
                x=50, line_dash="dash", line_color=C_GREY,
                annotation_text="50%", annotation_position="top right",
            )
            show_chart(fig)

            st.caption(
                f"Total de seções no histograma: {fmt_int(len(hist_df))}. "
                f"Média: {fmt_pct(hist_df['pct_lula'].mean(), 2)}, "
                f"Mediana: {fmt_pct(hist_df['pct_lula'].median(), 2)}."
            )
        else:
            st.info("Sem dados para histograma.")
    except Exception as e:
        show_error("Erro ao carregar histograma de distribuição", e)

    # ----------------------------------------------------------
    # Seção 2: Estatísticas por estado
    # ----------------------------------------------------------
    st.markdown("### Estatísticas por Estado")
    try:
        state_df = analysis.candidate_distribution_by_state(store, f)
        if not state_df.empty:
            show_df(state_df, width="stretch", hide_index=True)

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=state_df["uf"],
                y=state_df["media"],
                name="Média (% Lula)",
                marker_color=C_VERMILLION,
            ))
            fig.add_trace(go.Bar(
                x=state_df["uf"],
                y=state_df["mediana"],
                name="Mediana (% Lula)",
                marker_color=C_BLUE,
            ))
            fig.update_layout(
                barmode="group",
                xaxis_title="UF",
                yaxis_title="% Lula",
                title="Média e Mediana do % Lula por Estado",
                height=400,
            )
            fig.add_hline(
                y=50, line_dash="dash", line_color=C_GREY,
                annotation_text="50%", annotation_position="top right",
            )
            show_chart(fig)
        else:
            st.info("Sem dados de estatísticas por estado.")
    except Exception as e:
        show_error("Erro ao carregar estatísticas por estado", e)

    # ----------------------------------------------------------
    # Seção 3: Seções extremas
    # ----------------------------------------------------------
    st.markdown("### Seções com Votação Extrema")
    try:
        extreme_df = analysis.candidate_extreme_sections(store, f)
        if not extreme_df.empty:
            n_dom_13 = int((extreme_df["tipo_extremo"] == "dominancia_13").sum())
            n_dom_22 = int((extreme_df["tipo_extremo"] == "dominancia_22").sum())

            col1, col2 = st.columns(2)
            col1.metric("Dominância 13 (Lula >= 95%)", f"{fmt_int(n_dom_13)}")
            col2.metric("Dominância 22 (Bolsonaro >= 95%)", f"{fmt_int(n_dom_22)}")

            st.warning(
                f"Encontradas {fmt_int(len(extreme_df))} seções com votação extrema "
                f"(>= 95% para um candidato). Seções com poucos eleitores "
                f"tendem a apresentar esse padrão naturalmente."
            )

            show_df(extreme_df, width="stretch", hide_index=True)
        else:
            st.info("Nenhuma seção com votação extrema detectada.")
    except Exception as e:
        show_error("Erro ao carregar seções extremas", e)

    # ----------------------------------------------------------
    # Seção 4: Outliers por z-score estadual
    # ----------------------------------------------------------
    st.markdown("### Outliers por Z-Score Estadual")
    st.caption("Seções com distribuição atípica em relação à sua própria UF (z-score > 3)")
    try:
        zscore_df = analysis.candidate_section_distribution(store, f)
        if not zscore_df.empty:
            st.metric("Seções Outliers (z-score > 3)", f"{fmt_int(len(zscore_df))}")

            # Scatter plot
            limited_df = zscore_df.head(200)
            fig = px.scatter(
                limited_df,
                x="pct_lula",
                y="zscore",
                color="uf",
                hover_data=["municipio", "zona", "secao", "votos_13", "votos_22"],
                title="Outliers: % Lula vs Z-Score por UF",
                labels={
                    "pct_lula": "% Lula",
                    "zscore": "Z-Score",
                    "uf": "UF",
                },
            )
            fig.update_layout(height=450)
            show_chart(fig)

            show_df(zscore_df, width="stretch", hide_index=True)
        else:
            st.info("Nenhum outlier de distribuição por candidato detectado.")
    except Exception as e:
        show_error("Erro ao carregar outliers de distribuição", e)
