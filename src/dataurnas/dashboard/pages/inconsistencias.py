"""Inconsistências registradas e integridade dos arquivos (hash)."""

import plotly.graph_objects as go
import streamlit as st

from dataurnas.dashboard.state import analysis
from dataurnas.dashboard.components.charts import C_GREY, SEVERITY_COLORS, show_chart
from dataurnas.dashboard.components.formatting import fmt_int, fmt_pct, severidade_label
from dataurnas.dashboard.components.tables import show_df
from dataurnas.dashboard.reference import ISSUE_DESCRICOES


def tab_inconsistencias(store, f):
    """Aba de Inconsistências."""
    st.subheader("Distribuição de Inconsistências")

    col1, col2 = st.columns(2)
    with col1:
        sev_df = store.query_df(f"""
            SELECT i.severidade, COUNT(*) as total
            FROM issues i JOIN secoes s ON i.secao_id = s.id
            WHERE {f['issue_where']}
            GROUP BY i.severidade
            ORDER BY CASE i.severidade
                WHEN 'critica' THEN 1
                WHEN 'alta' THEN 2
                WHEN 'media' THEN 3
                WHEN 'informativa' THEN 4
            END
        """, f["issue_params"])
        if not sev_df.empty:
            fig = go.Figure(go.Bar(
                x=[severidade_label(v) for v in sev_df["severidade"]],
                y=sev_df["total"],
                marker_color=[SEVERITY_COLORS.get(v, C_GREY) for v in sev_df["severidade"]],
                text=[fmt_int(v) for v in sev_df["total"]],
                textposition="auto",
            ))
            fig.update_layout(xaxis_title="Severidade", yaxis_title="Ocorrências", showlegend=False)
            show_chart(fig, height=320, caption="Cada barra traz o rótulo da severidade e o total de ocorrências.")
        else:
            st.info("Nenhuma inconsistência encontrada.")

    with col2:
        cod_df = store.query_df(f"""
            SELECT i.codigo, COUNT(*) as total
            FROM issues i JOIN secoes s ON i.secao_id = s.id
            WHERE {f['issue_where']}
            GROUP BY i.codigo
            ORDER BY total DESC
        """, f["issue_params"])
        if not cod_df.empty:
            st.bar_chart(cod_df.set_index("codigo"))

    st.subheader("Issues por Estado")
    uf_issues_df = store.query_df(f"""
        SELECT UPPER(s.uf) as estado, i.codigo, COUNT(*) as total
        FROM issues i JOIN secoes s ON i.secao_id = s.id
        WHERE {f['issue_where']}
        GROUP BY s.uf, i.codigo
        ORDER BY s.uf, total DESC
    """, f["issue_params"])
    if not uf_issues_df.empty:
        pivot = uf_issues_df.pivot_table(
            index="estado", columns="codigo", values="total", fill_value=0
        )
        show_df(pivot, width="stretch")

    st.subheader("Detalhes das Inconsistências")
    detail_df = store.query_df(f"""
        SELECT
            i.codigo,
            i.severidade,
            UPPER(s.uf) as uf,
            s.municipio,
            s.zona,
            s.secao,
            'UE' || s.modelo_urna as modelo,
            i.descricao,
            i.base_legal
        FROM issues i JOIN secoes s ON i.secao_id = s.id
        WHERE {f['issue_where']}
        ORDER BY
            CASE i.severidade
                WHEN 'critica' THEN 1 WHEN 'alta' THEN 2
                WHEN 'media' THEN 3 ELSE 4
            END,
            i.codigo
        LIMIT 500
    """, f["issue_params"])
    if not detail_df.empty:
        show_df(detail_df, width="stretch", height=400)
    else:
        st.info("Nenhuma inconsistência encontrada para os filtros atuais.")

    # Legenda dos códigos
    with st.expander("Legenda dos Códigos de Issue"):
        st.markdown("\n".join(f"- **{cod}**: {desc}" for cod, desc in sorted(ISSUE_DESCRICOES.items())))


def tab_integridade(store, f):
    """Tab Integridade & Assinaturas: verificação de hash SHA-512."""

    st.subheader("Integridade & Assinaturas Digitais")
    st.caption("Verificação de integridade dos arquivos das urnas via hash SHA-512")

    with st.expander("Como funciona a verificação de integridade?"):
        st.markdown(
            "Cada arquivo gerado pela urna eletrônica (BU, log, RDV) "
            "possui um hash **SHA-512** registrado no arquivo de assinatura "
            "(`.vscmr`). Durante o processamento, o DataUrnas recalcula o "
            "hash de cada arquivo baixado e compara com o hash original.\n\n"
            "- **Hash SHA-512**: Função criptográfica que gera uma "
            "\"impressão digital\" única de 512 bits para cada arquivo. "
            "Qualquer alteração no conteúdo, por menor que seja, "
            "resulta em um hash completamente diferente.\n\n"
            "- **Issue C01**: Indica que o hash recalculado NÃO corresponde "
            "ao hash original, sugerindo possível corrupção ou "
            "adulteração do arquivo.\n\n"
            "- **Se não houver issues C01**: Todos os arquivos estão "
            "íntegros: o conteúdo baixado é idêntico ao "
            "gerado pela urna."
        )

    # Resumo
    sig = analysis.signature_integrity_summary(store, f)

    if sig["total_secoes"] == 0:
        st.warning("Nenhuma seção encontrada para os filtros selecionados.")
        return

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total de Seções", f"{fmt_int(sig['total_secoes'])}")
    col2.metric("Hash Válido", f"{fmt_int(sig['secoes_hash_ok'])}")
    col3.metric("Hash Inválido", f"{fmt_int(sig['secoes_hash_falha'])}")
    col4.metric("% Íntegras", f"{fmt_pct(sig['pct_ok'], 2)}")

    st.markdown("---")

    if sig["secoes_hash_falha"] == 0:
        st.success(
            "Todas as seções passaram na verificação de "
            "integridade SHA-512. Nenhum arquivo apresentou hash inválido."
        )
    else:
        st.error(
            f"{sig['secoes_hash_falha']} seção(ões) apresentaram "
            f"hash SHA-512 inválido (issue C01). Isso indica possível "
            f"corrupção ou adulteração dos arquivos."
        )

        st.markdown("### Seções com Falha de Hash")
        detail_df = analysis.signature_detail(store, f)
        if not detail_df.empty:
            show_df(detail_df, width="stretch", hide_index=True)
        else:
            st.info("Sem detalhes disponíveis para as falhas de hash.")
