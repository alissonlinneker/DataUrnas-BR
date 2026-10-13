"""Análise da inconsistência A03 (votos no log vs BU)."""

import streamlit as st

from dataurnas.dashboard.state import analysis
from dataurnas.dashboard.components.errors import show_error
from dataurnas.dashboard.components.formatting import fmt_pct
from dataurnas.dashboard.components.tables import show_df


def tab_a03(store, f):
    """Aba Análise A03: divergência de votos no log vs BU."""
    st.subheader("Análise A03: Divergência de Votos entre Log e Boletim de Urna")
    st.caption("Investigação detalhada da issue A03 (votos contabilizados no log divergem do BU)")

    with st.expander("Causa-raiz da issue A03"):
        st.markdown(
            "A issue **A03** ocorre quando o número de votos registrados no arquivo de log "
            "da urna diverge do total presente no Boletim de Urna (BU).\n\n"
            "**Causa identificada:** Na grande maioria dos casos, isso ocorre em **urnas reserva** "
            "(tipo `reservaSecao`), onde a urna substituiu outra que apresentou falha. "
            "O log da urna reserva registra apenas os votos computados após a substituição, "
            "enquanto o BU contém o total consolidado (incluindo votos da urna original, "
            "quando transferidos).\n\n"
            "**No 2º Turno**, há um fator adicional: o log acumula registros do 1º e 2º turno. "
            "A contagem de votos no log pode incluir eventos de ambos os turnos, "
            "gerando divergência artificial com o BU do 2º turno.\n\n"
            "**Conclusão:** A03 é um artefato do processo de contingência e acumulação de logs, "
            "**não indicando adulteração de votos**."
        )

    # A03 por turno
    st.markdown("### Resumo por Turno")
    try:
        turno_df = analysis.a03_by_turno(store, f)
        if not turno_df.empty:
            show_df(turno_df, width="stretch", hide_index=True)

            col1, col2 = st.columns(2)
            for _, row in turno_df.iterrows():
                turno_val = row.get("turno", "?")
                count_val = int(row.get("count", 0))
                pct_val = row.get("pct_of_secoes", 0)
                if turno_val == 1:
                    col1.metric("A03 no 1º Turno", f"{count_val}", f"{fmt_pct(pct_val, 2)} das seções")
                elif turno_val == 2:
                    col2.metric("A03 no 2º Turno", f"{count_val}", f"{fmt_pct(pct_val, 2)} das seções")
        else:
            st.info("Nenhuma issue A03 encontrada.")
    except Exception as e:
        show_error("Erro ao carregar A03 por turno", e)

    # Detalhes A03
    st.markdown("### Seções com Divergência A03")
    try:
        detail_df = analysis.a03_detail(store, f)
        if not detail_df.empty:
            show_df(detail_df, width="stretch", hide_index=True)

            st.caption(
                "votos_log = votos contabilizados no log | "
                "comparecimento = total no BU | "
                "ratio = votos_log / comparecimento"
            )
        else:
            st.info("Nenhuma seção com A03 nos filtros atuais.")
    except Exception as e:
        show_error("Erro ao carregar detalhes A03", e)
