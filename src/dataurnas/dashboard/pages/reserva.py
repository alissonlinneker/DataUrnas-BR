"""Seções reserva, substituições e erros de log."""

import streamlit as st
import plotly.graph_objects as go

from dataurnas.dashboard.state import analysis
from dataurnas.dashboard.components.charts import C_BLUE, C_VERMILLION, show_chart
from dataurnas.dashboard.components.errors import show_error
from dataurnas.dashboard.components.formatting import fmt_int, fmt_num, fmt_pct
from dataurnas.dashboard.components.tables import show_df


def tab_reserva(store, f):
    """Tab Seções Reserva: Comparativo entre seções normais e reserva."""

    st.subheader("Seções Reserva: Análise Comparativa")
    st.caption(
        "Seções reserva (reservaSecao) são urnas substitutas ativadas quando a "
        "urna original apresenta falha. Esta análise compara seu comportamento "
        "com as seções normais."
    )

    # 1. Comparativo de métricas
    st.markdown("### Comparativo de Métricas: Normal vs Reserva")
    try:
        comp_df = analysis.reserve_vs_normal(store, f)
        if not comp_df.empty:
            show_df(comp_df, width="stretch", hide_index=True)

            # Gráfico de barras comparativo
            fig = go.Figure()
            for _, row in comp_df.iterrows():
                tipo = str(row["tipo"])
                fig.add_trace(go.Bar(
                    x=["Média Reboots", "Média Erros", "% Issues"],
                    y=[row["media_reboots"], row["media_erros"], row["pct_issues"]],
                    name=tipo,
                ))

            fig.update_layout(
                barmode="group",
                xaxis_title="Métrica",
                yaxis_title="Valor",
                title="Comparativo: Seção Normal vs Reserva",
                height=400,
            )
            show_chart(fig)

            # Destaque: seções reserva com mais reboots e erros
            reserva_row = comp_df[comp_df["tipo"] == "reservaSecao"]
            normal_row = comp_df[comp_df["tipo"] == "secao"]

            if not reserva_row.empty and not normal_row.empty:
                r = reserva_row.iloc[0]
                n = normal_row.iloc[0]

                col1, col2, col3 = st.columns(3)
                col1.metric(
                    "Seções Reserva",
                    f"{fmt_int(int(r['secoes']))}",
                    f"{fmt_pct(r['secoes'] / (r['secoes'] + n['secoes']) * 100, 2)} do total"
                    if (r["secoes"] + n["secoes"]) > 0 else "-",
                )
                col2.metric(
                    "Reboots (Reserva vs Normal)",
                    f"{fmt_num(r['media_reboots'], 2)}",
                    f"{fmt_num(r['media_reboots'] - n['media_reboots'], 2, sign=True)}",
                )
                col3.metric(
                    "Erros (Reserva vs Normal)",
                    f"{fmt_num(r['media_erros'], 2)}",
                    f"{fmt_num(r['media_erros'] - n['media_erros'], 2, sign=True)}",
                )
        else:
            st.info("Sem dados de tipo de urna disponíveis.")
    except Exception as e:
        show_error("Erro ao carregar comparativo normal vs reserva", e)

    # 2. Check A03
    st.markdown("---")
    st.markdown("### Verificação A03: Exclusividade em Seções Reserva")
    try:
        a03 = analysis.reserve_a03_check(store, f)

        if a03["total_a03"] == 0:
            st.info("Nenhuma issue A03 encontrada nos filtros atuais.")
        else:
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total A03", f"{fmt_int(a03['total_a03'])}")
            col2.metric("A03 em Reserva", f"{fmt_int(a03['a03_reserva'])}")
            col3.metric("A03 em Normal", f"{fmt_int(a03['a03_normal'])}")
            col4.metric("% em Reserva", f"{fmt_pct(a03['pct_reserva'], 1)}")

            if a03["a03_normal"] == 0:
                st.success(
                    "Todas as issues A03 (divergência votos log vs BU) ocorrem "
                    "exclusivamente em seções reserva. Isso confirma que a divergência "
                    "é causada pelo processo de contingência, e não por adulteração."
                )
            else:
                st.error(
                    f"ANOMALIA: {a03['a03_normal']} issue(s) A03 em seções NORMAIS! "
                    f"Isso é inesperado e requer investigação detalhada, pois A03 "
                    f"deveria ocorrer apenas em urnas reserva."
                )
    except Exception as e:
        show_error("Erro ao verificar A03 em seções reserva", e)

    # 3. Padrão de votação
    st.markdown("---")
    st.markdown("### Padrão de Votação: Normal vs Reserva")
    try:
        vote_df = analysis.reserve_vote_pattern(store, f)
        if not vote_df.empty:
            show_df(vote_df, width="stretch", hide_index=True)

            fig = go.Figure()
            for _, row in vote_df.iterrows():
                tipo = str(row["tipo"])
                fig.add_trace(go.Bar(
                    x=["% Lula", "% Bolsonaro", "% Nulos", "% Brancos"],
                    y=[row["pct_lula"], row["pct_bolso"], row["pct_nulos"], row["pct_brancos"]],
                    name=tipo,
                ))

            fig.update_layout(
                barmode="group",
                xaxis_title="Tipo de Voto",
                yaxis_title="Percentual (%)",
                title="Votação para Presidente: Seção Normal vs Reserva",
                height=400,
            )
            show_chart(fig)

            st.caption(
                "Diferenças no padrão de votação entre seções normais e reserva "
                "podem refletir características geográficas das seções que necessitaram "
                "de substituição, e não indicam necessariamente irregularidade."
            )
        else:
            st.info("Sem dados de votação por tipo de seção.")
    except Exception as e:
        show_error("Erro ao carregar padrão de votação por tipo", e)


def tab_substituicoes_erros(store, f):
    """Tab Substituições & Erros: Análise de substituições e erros de log."""

    st.subheader("Substituições & Erros de Log")
    st.caption(
        "Análise de eventos de substituição/contingência nas urnas e "
        "distribuição de erros registrados no log por modelo de urna."
    )

    # 1. Substituições por estado
    st.markdown("### Substituições por Estado")
    try:
        sub_state_df = analysis.substitution_by_state(store, f)
        if not sub_state_df.empty:
            total_sub = int(sub_state_df["total_substituicoes"].sum())
            total_secoes_sub = int(sub_state_df["secoes_com_substituicao"].sum())

            col1, col2 = st.columns(2)
            col1.metric("Total de Substituições", f"{fmt_int(total_sub)}")
            col2.metric("Seções com Substituição", f"{fmt_int(total_secoes_sub)}")

            show_df(sub_state_df, width="stretch", hide_index=True)

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=sub_state_df["uf"].str.upper(),
                y=sub_state_df["total_substituicoes"],
                name="Total Substituições",
                marker_color=C_BLUE,
                text=sub_state_df["total_substituicoes"],
                textposition="auto",
            ))
            fig.update_layout(
                xaxis_title="UF",
                yaxis_title="Total de Substituições",
                title="Substituições por Estado",
                height=400,
            )
            show_chart(fig)

            fig2 = go.Figure()
            fig2.add_trace(go.Bar(
                x=sub_state_df["uf"].str.upper(),
                y=sub_state_df["pct_secoes"],
                name="% Seções com Substituição",
                marker_color=C_VERMILLION,
                text=sub_state_df["pct_secoes"].apply(lambda x: f"{fmt_pct(x, 1)}"),
                textposition="auto",
            ))
            fig2.update_layout(
                xaxis_title="UF",
                yaxis_title="% de Seções",
                title="Percentual de Seções com Substituição por Estado",
                height=400,
            )
            show_chart(fig2)
        else:
            st.info("Nenhuma substituição registrada nos filtros atuais.")
    except Exception as e:
        show_error("Erro ao carregar substituições por estado", e)

    # 2. Votação com/sem substituição
    st.markdown("---")
    st.markdown("### Votação: Com Substituição vs Sem Substituição")
    try:
        sub_vote_df = analysis.substitution_vs_result(store, f)
        if not sub_vote_df.empty:
            show_df(sub_vote_df, width="stretch", hide_index=True)

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=sub_vote_df["grupo"],
                y=sub_vote_df["pct_lula"],
                name="Lula (%)",
                marker_color=C_VERMILLION,
            ))
            fig.add_trace(go.Bar(
                x=sub_vote_df["grupo"],
                y=sub_vote_df["pct_bolso"],
                name="Bolsonaro (%)",
                marker_color=C_BLUE,
            ))
            fig.update_layout(
                barmode="group",
                xaxis_title="Grupo",
                yaxis_title="Percentual (%)",
                title="Votação para Presidente: Com vs Sem Substituição",
                height=400,
            )
            show_chart(fig)

            com_sub = sub_vote_df[sub_vote_df["grupo"] == "com_substituição"]
            sem_sub = sub_vote_df[sub_vote_df["grupo"] == "sem_substituição"]

            if not com_sub.empty and not sem_sub.empty:
                diff_lula = float(com_sub.iloc[0]["pct_lula"]) - float(sem_sub.iloc[0]["pct_lula"])
                diff_bolso = float(com_sub.iloc[0]["pct_bolso"]) - float(sem_sub.iloc[0]["pct_bolso"])

                if abs(diff_lula) < 2.0 and abs(diff_bolso) < 2.0:
                    st.success(
                        f"Diferença pequena entre grupos: "
                        f"Lula {fmt_num(diff_lula, 2, sign=True)} p.p., Bolsonaro {fmt_num(diff_bolso, 2, sign=True)} p.p. "
                        f"Substituições não parecem afetar o padrão de votação."
                    )
                else:
                    st.warning(
                        f"Diferença detectada: "
                        f"Lula {fmt_num(diff_lula, 2, sign=True)} p.p., Bolsonaro {fmt_num(diff_bolso, 2, sign=True)} p.p. "
                        f"Pode refletir distribuição geográfica das substituições."
                    )
        else:
            st.info("Sem dados de votação para comparação.")
    except Exception as e:
        show_error("Erro ao carregar votação por substituição", e)

    # 3. Erros de log por modelo
    st.markdown("---")
    st.markdown("### Erros de Log por Modelo de Urna")
    try:
        err_df = analysis.error_log_by_model(store, f)
        if not err_df.empty:
            show_df(err_df, width="stretch", hide_index=True)

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=err_df["modelo_urna"].apply(lambda m: f"UE{m}" if m else "?"),
                y=err_df["media_erros"],
                name="Média de Erros",
                marker_color=C_BLUE,
            ))
            fig.add_trace(go.Bar(
                x=err_df["modelo_urna"].apply(lambda m: f"UE{m}" if m else "?"),
                y=err_df["pct_com_erros"],
                name="% Seções com Erros",
                marker_color=C_VERMILLION,
            ))
            fig.update_layout(
                barmode="group",
                xaxis_title="Modelo de Urna",
                yaxis_title="Valor",
                title="Erros de Log por Modelo de Urna",
                height=400,
            )
            show_chart(fig)

            worst = err_df.iloc[0]
            st.info(
                f"Modelo com mais erros: UE{worst['modelo_urna']} "
                f"(média: {fmt_num(worst['media_erros'], 2)}, "
                f"máximo: {int(worst['max_erros'])}, "
                f"{fmt_pct(worst['pct_com_erros'], 1)} com erros)."
            )

            st.caption(
                "Modelos mais antigos tendem a apresentar mais erros de log. "
                "Isso pode refletir desgaste do hardware, mas não necessariamente "
                "indica comprometimento dos votos."
            )
        else:
            st.info("Sem dados de erros de log por modelo.")
    except Exception as e:
        show_error("Erro ao carregar erros por modelo", e)
