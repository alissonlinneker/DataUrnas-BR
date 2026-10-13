"""Lei de Benford (1º e 2º dígitos e todos os cargos)."""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from dataurnas.dashboard.state import analysis
from dataurnas.dashboard.components.charts import C_BLUE, C_VERMILLION, show_chart
from dataurnas.dashboard.components.errors import show_error
from dataurnas.dashboard.components.tables import show_df


def tab_benford_v2(store, f):
    """Aba Lei de Benford: Análise de 1º e 2º dígito + todos os cargos."""

    st.subheader("Lei de Benford: Distribuição do Primeiro e Segundo Dígito")
    st.caption(
        "Análise da conformidade dos votos com a distribuição esperada "
        "pela Lei de Benford (1º e 2º dígitos)"
    )

    with st.expander("O que é a Lei de Benford?"):
        st.markdown(
            "A **Lei de Benford** (ou Lei do Primeiro Dígito) prevê que em muitos conjuntos de dados "
            "numéricos naturais, o dígito 1 aparece como primeiro dígito em ~30,1% dos casos, "
            "o dígito 2 em ~17,6%, e assim por diante, em escala logarítmica decrescente.\n\n"
            "A lei também se aplica ao **segundo dígito**, com uma distribuição mais uniforme "
            "(de ~11,97% para o dígito 0 até ~8,50% para o dígito 9).\n\n"
            "Em contextos eleitorais, essa lei pode ser aplicada aos totais de votos por seção "
            "para verificar se a distribuição é consistente com dados não manipulados. "
            "No entanto, **desvios não implicam necessariamente fraude**: fatores como "
            "tamanho das seções, distribuição geográfica e regras eleitorais podem causar desvios naturais.\n\n"
            "O **teste Qui-Quadrado** quantifica o desvio entre a distribuição observada e a esperada. "
            "O **Cramér's V** mede o tamanho do efeito (V < 0,05 = desprezível, "
            "V < 0,10 = pequeno, V < 0,20 = moderado). "
            "O **teste KS** avalia a distância entre as distribuições acumuladas."
        )

    # ============================================================
    # Seção 1: Primeiro Dígito (original)
    # ============================================================
    st.markdown("### Distribuição do 1º Dígito: Observado vs Esperado")
    try:
        benford_df = analysis.benford_first_digit(store, f)

        if not benford_df.empty:
            candidatos = benford_df["candidato"].unique()
            for cand in candidatos:
                cand_data = benford_df[benford_df["candidato"] == cand]
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=cand_data["digito"],
                    y=cand_data["pct_observado"],
                    name="Observado",
                    marker_color=C_BLUE,
                ))
                fig.add_trace(go.Bar(
                    x=cand_data["digito"],
                    y=cand_data["pct_esperado"],
                    name="Esperado (Benford)",
                    marker_color=C_VERMILLION,
                ))
                fig.update_layout(
                    title=f"Candidato {cand}: 1º Dígito",
                    xaxis_title="Primeiro Dígito",
                    yaxis_title="Frequência (%)",
                    barmode="group",
                    height=350,
                )
                show_chart(fig)
        else:
            st.info("Sem dados suficientes para análise de Benford (1º dígito).")
    except Exception as e:
        show_error("Erro ao carregar distribuição de Benford (1º dígito)", e)

    # Teste Qui-Quadrado por candidato (1º dígito)
    st.markdown("### Teste Qui-Quadrado por Candidato (1º Dígito)")
    try:
        chi2_df = analysis.benford_chi_squared(store, f)

        if not chi2_df.empty:
            show_df(chi2_df, width="stretch", hide_index=True)

            nao_conformes = chi2_df[~chi2_df["conforme"].astype(bool)]
            if len(nao_conformes) == 0:
                st.success(
                    "Todos os candidatos apresentam distribuição conforme "
                    "a Lei de Benford (p > 0,05)."
                )
            else:
                st.warning(
                    f"{len(nao_conformes)} candidato(s) com desvio significativo "
                    "da Lei de Benford. "
                    "Isso não implica fraude necessariamente: veja a explicação acima."
                )
        else:
            st.info("Sem dados para teste Qui-Quadrado (1º dígito).")
    except Exception as e:
        show_error("Erro ao carregar teste Qui-Quadrado (1º dígito)", e)

    # Conformidade por estado (1º dígito)
    st.markdown("### Conformidade por Estado (1º Dígito)")
    try:
        state_df = analysis.benford_by_state(store, f)

        if not state_df.empty:
            show_df(state_df, width="stretch", hide_index=True)
        else:
            st.info("Sem dados por estado.")
    except Exception as e:
        show_error("Erro ao carregar conformidade por estado", e)

    # ============================================================
    # Seção 2: Segundo Dígito (NOVA)
    # ============================================================
    st.markdown("---")
    st.markdown("### Análise do 2º Dígito")
    st.caption(
        "Distribuição do segundo dígito dos votos por seção para Presidente. "
        "Seções com menos de 10 votos (sem segundo dígito) são excluídas."
    )

    try:
        second_digit_df = analysis.benford_second_digit(store, f)
        if not second_digit_df.empty:
            candidatos_2d = second_digit_df["candidato"].unique()

            # Distribuição esperada para exibir no gráfico
            expected_pcts = {
                d: round(analysis.BENFORD_SECOND_EXPECTED[d] * 100, 4) for d in range(0, 10)
            }

            for cand in candidatos_2d:
                cand_data = second_digit_df[
                    second_digit_df["candidato"] == cand
                ].copy()

                # Garantir todos os dígitos 0-9
                full_digits = pd.DataFrame({"digito": range(0, 10)})
                cand_data = full_digits.merge(
                    cand_data[["digito", "percentual"]], on="digito", how="left"
                ).fillna(0)

                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=cand_data["digito"],
                    y=cand_data["percentual"],
                    name="Observado",
                    marker_color=C_BLUE,
                ))
                fig.add_trace(go.Bar(
                    x=cand_data["digito"],
                    y=[expected_pcts[d] for d in range(0, 10)],
                    name="Esperado (Benford 2º dígito)",
                    marker_color=C_VERMILLION,
                ))
                fig.update_layout(
                    title=f"Candidato {cand}: 2º Dígito",
                    xaxis_title="Segundo Dígito",
                    yaxis_title="Frequência (%)",
                    barmode="group",
                    height=350,
                )
                show_chart(fig)
        else:
            st.info(
                "Sem dados suficientes para análise do 2º dígito de Benford."
            )
    except Exception as e:
        show_error("Erro ao carregar distribuição do 2º dígito", e)

    # Tabela de testes estatísticos para 2º dígito
    st.markdown("### Testes Estatísticos: 2º Dígito (Chi-Quadrado + KS + Cramér's V)")
    try:
        chi2_second = analysis.benford_second_digit_chi(store, f)
        if chi2_second:
            chi2_second_df = pd.DataFrame(chi2_second)
            show_df(chi2_second_df, width="stretch", hide_index=True)

            nao_conf_2d = chi2_second_df[~chi2_second_df["conforme"].astype(bool)]
            if len(nao_conf_2d) == 0:
                st.success(
                    "Todos os candidatos apresentam distribuição do 2º dígito "
                    "conforme a Lei de Benford (p > 0,05 e Cramér's V < 0,10)."
                )
            else:
                st.warning(
                    f"{len(nao_conf_2d)} candidato(s) com desvio no 2º dígito. "
                    "Verifique o Cramér's V para avaliar a relevância prática do desvio."
                )

            st.caption(
                "Cramér's V < 0,05 = efeito desprezível | "
                "< 0,10 = efeito pequeno | "
                "< 0,20 = efeito moderado | "
                ">= 0,20 = efeito grande"
            )
        else:
            st.info("Sem dados para testes estatísticos do 2º dígito.")
    except Exception as e:
        show_error("Erro ao carregar testes do 2º dígito", e)

    # ============================================================
    # Seção 3: Benford por Cargo (NOVA)
    # ============================================================
    st.markdown("---")
    st.markdown("### Benford por Cargo")
    st.caption(
        "Aplicação da Lei de Benford (1º dígito) para todos os cargos, "
        "não apenas Presidente. Inclui Chi-Quadrado e Cramér's V."
    )

    try:
        offices_df = analysis.benford_all_offices(store, f)
        if not offices_df.empty:
            show_df(offices_df, width="stretch", hide_index=True)

            n_conformes_cargo = int(offices_df["conforme"].sum())
            n_total_cargo = len(offices_df)

            if n_conformes_cargo == n_total_cargo:
                st.success(
                    f"Todos os {n_total_cargo} cargos apresentam distribuição "
                    "conforme a Lei de Benford (p > 0,05)."
                )
            else:
                n_nao_conf = n_total_cargo - n_conformes_cargo
                st.warning(
                    f"{n_nao_conf}/{n_total_cargo} cargo(s) com desvio "
                    "significativo (p <= 0,05). "
                    "Verifique o Cramér's V para avaliar a relevância prática."
                )

            # Destacar cargos com Cramér's V alto
            altos_v = offices_df[offices_df["cramers_v"] >= 0.10]
            if not altos_v.empty:
                st.info(
                    f"{len(altos_v)} cargo(s) com Cramér's V >= 0,10: "
                    f"{', '.join(altos_v['cargo'].tolist())}. "
                    "Investigação adicional pode ser útil."
                )
        else:
            st.info("Sem dados suficientes para análise por cargo.")
    except Exception as e:
        show_error("Erro ao carregar Benford por cargo", e)
