"""Inconsistências registradas e integridade dos arquivos (hash)."""

import plotly.graph_objects as go
import streamlit as st

from dataurnas.dashboard.state import analysis
from dataurnas.dashboard.components.charts import C_GREY, C_ORANGE, C_VERMILLION, SEVERITY_COLORS, show_chart
from dataurnas.dashboard.components.formatting import fmt_int, fmt_pct, severidade_label
from dataurnas.dashboard.components.tables import show_df
from dataurnas.dashboard.components.ui import grupos_resumo
from dataurnas.dashboard.reference import (
    ANALISES_ESTATISTICAS,
    GRUPO_ADULTERACAO,
    GRUPO_INVESTIGAR,
    GRUPOS,
    GRUPOS_ORDEM,
    ISSUE_DESCRICOES,
    ISSUE_GRUPOS,
    ISSUE_MOTIVOS,
    contar_por_grupo,
    grupo_label,
    grupo_nome,
)

# Cor de apoio por grupo; o nome numerado do grupo vai sempre junto (legenda e tabela)
CORES_GRUPO = {GRUPO_ADULTERACAO: C_VERMILLION, GRUPO_INVESTIGAR: C_ORANGE}

LEITURA_GRUPOS = (
    "A severidade diz a prioridade de investigar; o **grupo de leitura** diz que tipo de conclusão o "
    "achado admite. Só o grupo 1 aponta diretamente para adulteração dos arquivos. Os arquivos públicos "
    "não alcançam uma manipulação feita dentro da urna antes da assinatura: isso é coberto por outros "
    "mecanismos (inspeção do código-fonte, cerimônia de lacração, teste de integridade no dia da eleição "
    "e Teste Público de Segurança)."
)


def _legenda_grupos() -> str:
    linhas = []
    for g in GRUPOS_ORDEM:
        linhas.append(f"**{grupo_nome(g)}**: {GRUPOS[g]['resumo']}")
        for cod in sorted(c for c, gg in ISSUE_GRUPOS.items() if gg == g):
            linhas.append(f"- **{cod}** ({ISSUE_DESCRICOES[cod]}): {ISSUE_MOTIVOS[cod]}")
        for nome, grupo, motivo in ANALISES_ESTATISTICAS.values():
            if grupo == g:
                linhas.append(f"- **{nome}** (análise agregada): {motivo}")
        linhas.append("")
    return "\n".join(linhas)


def tab_inconsistencias(store, f):
    """Aba de Inconsistências."""
    st.subheader("Distribuição de Inconsistências")

    cod_df = store.query_df(f"""
        SELECT i.codigo, COUNT(*) as total
        FROM issues i JOIN secoes s ON i.secao_id = s.id
        WHERE {f['issue_where']}
        GROUP BY i.codigo
        ORDER BY total DESC
    """, f["issue_params"])

    st.markdown("**Por grupo de leitura**")
    grupos_resumo(contar_por_grupo(dict(zip(cod_df["codigo"], cod_df["total"], strict=False))))
    st.caption(LEITURA_GRUPOS)

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
        if not cod_df.empty:
            grupos = [ISSUE_GRUPOS.get(c) for c in cod_df["codigo"]]
            fig = go.Figure()
            for g in [*GRUPOS_ORDEM, None]:
                sel = [i for i, gg in enumerate(grupos) if gg == g]
                if not sel:
                    continue
                parte = cod_df.iloc[sel]
                fig.add_bar(
                    x=parte["codigo"], y=parte["total"], name=grupo_nome(g),
                    marker_color=CORES_GRUPO.get(g, C_GREY),
                    text=[fmt_int(v) for v in parte["total"]], textposition="auto",
                )
            fig.update_layout(xaxis_title="Código", yaxis_title="Ocorrências", legend_title_text="Grupo",
                              xaxis={"categoryorder": "total descending"})
            show_chart(fig, height=320, caption="Ocorrências por código; a legenda nomeia o grupo de leitura "
                                                "de cada barra.")

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
        detail_df = detail_df.copy()
        detail_df.insert(1, "grupo", [grupo_label(c) for c in detail_df["codigo"]])
        show_df(detail_df, width="stretch", height=400, hide_index=True)
    else:
        st.info("Nenhuma inconsistência encontrada para os filtros atuais.")

    # Legenda dos códigos
    with st.expander("Legenda dos códigos por grupo de leitura"):
        st.markdown(_legenda_grupos())


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
