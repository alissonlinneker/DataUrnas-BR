"""Comparação entre 1º e 2º turno."""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from dataurnas.dashboard.state import analysis
from dataurnas.dashboard.components.charts import C_BLUE, C_VERMILLION, show_chart
from dataurnas.dashboard.components.errors import show_error
from dataurnas.dashboard.components.formatting import fmt_int, fmt_num, fmt_pct
from dataurnas.dashboard.components.tables import show_df
from dataurnas.dashboard.reference import TSE_2022


def tab_comparacao_turnos(store, f):
    """Aba de Comparação entre 1º e 2º Turno."""
    st.subheader("Comparação entre 1º e 2º Turno")

    # Verificar se temos dados de ambos os turnos
    turnos_df = store.query_df("SELECT turno, COUNT(*) as secoes FROM secoes GROUP BY turno ORDER BY turno")
    if turnos_df.empty:
        st.warning("Sem dados disponíveis.")
        return

    turnos_presentes = set(turnos_df["turno"].tolist())
    if 1 not in turnos_presentes or 2 not in turnos_presentes:
        st.info(
            "A comparação entre turnos requer dados de ambos os turnos. "
            f"Turnos disponíveis: {', '.join(f'{t}º' for t in sorted(turnos_presentes))}. "
            "O download do turno faltante pode estar em andamento."
        )
        if 1 in turnos_presentes:
            st.markdown("Dados do **1º Turno** já disponíveis.")
        if 2 in turnos_presentes:
            st.markdown("Dados do **2º Turno** já disponíveis.")
        return

    # Resumo comparativo por turno
    st.markdown("### Resumo Geral por Turno")

    # WHERE sem a condição de turno, gerado a partir dos filtros estruturados
    base_where, base_params = f.where_sql(include_turno=False)
    issue_base_where, issue_base_params = f.issue_where_sql(include_turno=False)

    comp_df = store.query_df(f"""
        SELECT
            s.turno,
            COUNT(*) as secoes,
            COUNT(DISTINCT uf) as ufs,
            SUM(eleitores_aptos) as eleitores,
            SUM(comparecimento) as comparecimento,
            ROUND((1 - SUM(comparecimento)*1.0/NULLIF(SUM(eleitores_aptos),0))*100, 2) as abstencao_pct,
            SUM(reboots) as reboots,
            SUM(CASE WHEN has_issues THEN 1 ELSE 0 END) as com_issues,
            SUM(n_issues) as total_issues,
            ROUND(AVG(pct_biometria), 1) as media_biometria,
            ROUND(AVG(duracao_min), 0) as duracao_media
        FROM secoes s
        WHERE {base_where}
        GROUP BY s.turno
        ORDER BY s.turno
    """, base_params)

    if not comp_df.empty:
        comp_df["turno"] = comp_df["turno"].map({1: "1º Turno", 2: "2º Turno"})
        show_df(comp_df.set_index("turno"), width="stretch")

    # Comparação de votos para Presidente
    st.markdown("### Votação para Presidente: 1º vs 2º Turno")

    votos_turno = analysis.presidente_13_22_por_turno(store, f)

    if not votos_turno.empty:
        nomes_cand = {13: "Lula (PT)", 22: "Bolsonaro (PL)"}

        # Calcular percentuais
        rows = []
        for turno in [1, 2]:
            turno_data = votos_turno[votos_turno["turno"] == turno]
            total = turno_data["votos"].sum()
            for _, row in turno_data.iterrows():
                cand = int(row["candidato"])
                votos = int(row["votos"])
                pct = votos / total * 100 if total > 0 else 0
                rows.append({
                    "Turno": f"{turno}º Turno",
                    "Candidato": nomes_cand.get(cand, str(cand)),
                    "Votos": f"{fmt_int(votos)}",
                    "Percentual": f"{fmt_pct(pct, 2)}",
                    "pct_num": pct,
                })

        result_df = pd.DataFrame(rows)
        show_df(result_df[["Turno", "Candidato", "Votos", "Percentual"]],
                     width="stretch", hide_index=True)

        # Análise da mudança entre turnos
        st.markdown("### Variação entre Turnos")

        lula_1t = lula_2t = bolso_1t = bolso_2t = 0
        for r in rows:
            if "Lula" in r["Candidato"] and "1º" in r["Turno"]:
                lula_1t = r["pct_num"]
            elif "Lula" in r["Candidato"] and "2º" in r["Turno"]:
                lula_2t = r["pct_num"]
            elif "Bolsonaro" in r["Candidato"] and "1º" in r["Turno"]:
                bolso_1t = r["pct_num"]
            elif "Bolsonaro" in r["Candidato"] and "2º" in r["Turno"]:
                bolso_2t = r["pct_num"]

        col1, col2 = st.columns(2)
        col1.metric(
            "Lula (PT)",
            f"{fmt_pct(lula_2t, 2)}",
            delta=f"{fmt_num(lula_2t - lula_1t, 2, sign=True)} p.p.",
        )
        col2.metric(
            "Bolsonaro (PL)",
            f"{fmt_pct(bolso_2t, 2)}",
            delta=f"{fmt_num(bolso_2t - bolso_1t, 2, sign=True)} p.p.",
        )

        # Dados oficiais para referência
        st.markdown("**Dados Oficiais (TSE) para Referência:**")
        oficial_comp = pd.DataFrame([
            {
                "Turno": ref["label"],
                "Lula (%)": fmt_pct(ref["candidatos"][13]["pct"]),
                "Bolsonaro (%)": fmt_pct(ref["candidatos"][22]["pct"]),
                "Diferença": f"{fmt_int(ref['diferenca_1_2'])} votos",
            }
            for ref in TSE_2022.values()
        ])
        show_df(oficial_comp, width="stretch", hide_index=True)

    # Comparação de issues por turno
    st.markdown("### Inconsistências por Turno")

    issues_turno = store.query_df(f"""
        SELECT
            s.turno,
            i.severidade,
            COUNT(*) as total
        FROM issues i JOIN secoes s ON i.secao_id = s.id
        WHERE {issue_base_where}
        GROUP BY s.turno, i.severidade
        ORDER BY s.turno, CASE i.severidade
            WHEN 'critica' THEN 1 WHEN 'alta' THEN 2
            WHEN 'media' THEN 3 ELSE 4
        END
    """, issue_base_params)

    if not issues_turno.empty:
        issues_turno["turno"] = issues_turno["turno"].map({1: "1º Turno", 2: "2º Turno"})
        pivot = issues_turno.pivot_table(
            index="turno", columns="severidade", values="total", fill_value=0
        )
        show_df(pivot, width="stretch")

    # Reboots por turno
    st.markdown("### Reboots por Turno")
    reboot_turno = store.query_df(f"""
        SELECT
            s.turno,
            COUNT(*) as total_secoes,
            SUM(CASE WHEN s.reboots > 0 THEN 1 ELSE 0 END) as secoes_reboot,
            SUM(s.reboots) as total_reboots,
            ROUND(SUM(CASE WHEN s.reboots > 0 THEN 1.0 ELSE 0 END)/COUNT(*)*100, 1) as pct_reboot
        FROM secoes s
        WHERE {base_where}
        GROUP BY s.turno ORDER BY s.turno
    """, base_params)

    if not reboot_turno.empty:
        reboot_turno["turno"] = reboot_turno["turno"].map({1: "1º Turno", 2: "2º Turno"})
        show_df(reboot_turno.set_index("turno"), width="stretch")

    # Enhanced: Cross-turno attendance analysis
    st.markdown("### Comparecimento Pareado entre Turnos")
    try:
        attendance_df = analysis.cross_turno_attendance(store, f)
        if not attendance_df.empty:
            show_df(attendance_df, width="stretch", hide_index=True)
        else:
            st.info("Sem dados de comparecimento pareado.")
    except Exception as e:
        show_error("Erro ao carregar comparecimento pareado", e)

    # Enhanced: Missing sections
    st.markdown("### Seções Presentes em Apenas Um Turno")
    try:
        missing_df = analysis.cross_turno_missing(store, f)
        if not missing_df.empty:
            show_df(missing_df, width="stretch", hide_index=True)
            st.caption(
                "Seções presentes em apenas um turno podem indicar urnas substituídas, "
                "seções agregadas ou falhas no download."
            )
        else:
            st.info("Todas as seções estão presentes em ambos os turnos.")
    except Exception as e:
        show_error("Erro ao carregar seções faltantes", e)

    # Enhanced: Vote migration
    st.markdown("### Migração de Votos entre Turnos")
    try:
        migration_df = analysis.cross_turno_vote_migration(store, f)
        if not migration_df.empty:
            show_df(migration_df, width="stretch", hide_index=True)

            if "swing_lula" in migration_df.columns:
                fig = go.Figure()
                fig.add_trace(go.Bar(
                    x=migration_df["uf"],
                    y=migration_df["swing_lula"],
                    marker_color=migration_df["swing_lula"].apply(
                        lambda x: C_VERMILLION if x > 0 else C_BLUE
                    ),
                    text=migration_df["swing_lula"].round(2),
                    textposition="auto",
                ))
                fig.update_layout(
                    xaxis_title="UF",
                    yaxis_title="Swing Lula (p.p.)",
                    title="Variação do Voto em Lula entre 1T e 2T por Estado",
                    height=400,
                )
                show_chart(fig)
        else:
            st.info("Sem dados de migração de votos.")
    except Exception as e:
        show_error("Erro ao carregar migração de votos", e)
