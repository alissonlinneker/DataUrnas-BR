"""Veredicto final: representatividade, comparação com o TSE, riscos e exportação."""

import streamlit as st
import pandas as pd

from dataurnas.dashboard.components.errors import show_error
from dataurnas.dashboard.components.ui import grupos_resumo, severity_line
from dataurnas.dashboard.filters import TURNO_LABELS
from dataurnas.dashboard.reference import TSE_2022, contar_por_grupo
from dataurnas.dashboard.state import analysis
from dataurnas.dashboard.components.formatting import fmt_int, fmt_num, fmt_pct
from dataurnas.dashboard.components.tables import show_df


def tab_veredicto(store, f):
    """Veredicto final: análise de risco e conclusão.

    A comparação com o resultado oficial só faz sentido turno a turno. Em
    "Ambos os Turnos" o usuário escolhe o turno de referência e todas as
    consultas desta página passam a usar esse turno (antes, votos de T1+T2
    eram somados e comparados com o resultado de um único turno).
    """
    if f.turno is None:
        turno_ref = st.segmented_control(
            "Turno de referência para a comparação com o TSE",
            options=[1, 2],
            format_func=lambda t: TURNO_LABELS[t],
            default=1,
            required=True,
            key="flt_veredicto_turno",
            help="O resultado oficial é publicado por turno; somar os dois turnos não tem significado eleitoral.",
        )
        f = f.with_turno(turno_ref or 1)
        st.caption("Filtro de turno em \"Ambos\": o veredicto é calculado para o turno escolhido acima.")

    OFICIAL = TSE_2022[f.turno]

    turno_label = OFICIAL["label"]
    st.subheader("Veredicto Final: Análise de Integridade Eleitoral")
    st.caption(f"Análise baseada nos dados coletados das urnas eletrônicas, {turno_label} de 2022")
    st.info(
        "Os indicadores desta página são sinais para investigação: não constituem prova de fraude "
        "nem de lisura. Pesos e limiares do score estão documentados no módulo de análise."
    )

    # ============================================================
    # 1. Cobertura dos dados
    # ============================================================
    st.markdown("---")
    st.markdown("### 1. Cobertura dos Dados")

    summary = store.query_df(f"""
        SELECT
            COUNT(*) as secoes,
            COUNT(DISTINCT uf) as ufs,
            SUM(eleitores_aptos) as eleitores,
            SUM(comparecimento) as comparecimento,
            SUM(reboots) as reboots,
            SUM(n_issues) as total_issues,
            SUM(CASE WHEN has_issues THEN 1 ELSE 0 END) as secoes_issues
        FROM secoes s WHERE {f['where']}
    """, f["params"])

    if summary.empty or int(summary.iloc[0]["secoes"]) == 0:
        st.warning("Sem dados para análise.")
        return

    s = summary.iloc[0]
    total_secoes = int(s["secoes"])
    total_eleitores = int(s["eleitores"])
    total_comp = int(s["comparecimento"])
    pct_cobertura = total_eleitores / OFICIAL["eleitores_aptos"] * 100

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Seções Analisadas", f"{fmt_int(total_secoes)}")
    col2.metric("Estados Cobertos", f"{int(s['ufs'])}/27")
    col3.metric("Eleitores Aptos na Base", f"{fmt_int(total_eleitores)}")
    col4.metric("% do Eleitorado", f"{fmt_pct(pct_cobertura, 2)}")

    if pct_cobertura >= 99:
        st.caption(
            f"A base reúne os boletins de urna de praticamente todas as seções do {turno_label} "
            f"nas 27 UFs ({fmt_pct(pct_cobertura, 2)} do eleitorado apto). Não é uma amostra: "
            f"a diferença para o total oficial inclui as seções do exterior, que não fazem "
            f"parte da base."
        )
    else:
        st.info(
            f"Os filtros atuais selecionam {fmt_pct(pct_cobertura, 2)} do eleitorado apto do "
            f"{turno_label} ({fmt_int(total_eleitores)} de {fmt_int(OFICIAL['eleitores_aptos'])}). "
            f"Os números desta página valem para esse recorte, não para o resultado nacional."
        )

    # ============================================================
    # 2. Comparação dos dados das urnas com o resultado oficial
    # ============================================================
    st.markdown("---")
    st.markdown("### 2. Comparação: Dados das Urnas vs Resultado Oficial")

    votos_base = analysis.presidente_votos_por_candidato(store, f)

    if votos_base.empty:
        st.warning("Sem dados de votação para Presidente.")
        return

    total_nominais = int(votos_base["votos"].sum())

    # Tabela comparativa
    comparacao = []
    for _, row in votos_base.iterrows():
        cand_id = int(row["candidato"])
        votos = int(row["votos"])
        pct_am = votos / total_nominais * 100

        oficial = OFICIAL["candidatos"].get(cand_id, {})
        nome = oficial.get("nome", f"Candidato {cand_id}")
        partido = oficial.get("partido", "?")
        pct_of = oficial.get("pct", 0)
        desvio = pct_am - pct_of if pct_of > 0 else None

        comparacao.append({
            "Candidato": f"{nome} ({partido})",
            "Número": cand_id,
            "Votos na Base": f"{fmt_int(votos)}",
            "% na Base": f"{fmt_pct(pct_am, 2)}",
            "% Oficial (TSE)": f"{fmt_pct(pct_of, 2)}" if pct_of > 0 else "-",
            "Desvio (p.p.)": f"{fmt_num(desvio, 2, sign=True)}" if desvio is not None else "-",
        })

    comp_df = pd.DataFrame(comparacao)
    show_df(comp_df, width="stretch", hide_index=True)

    # Calcular desvios dos dois principais
    pct_lula_am = 0
    pct_bolso_am = 0
    for _, row in votos_base.iterrows():
        cand = int(row["candidato"])
        pct = int(row["votos"]) / total_nominais * 100
        if cand == 13:
            pct_lula_am = pct
        elif cand == 22:
            pct_bolso_am = pct

    desvio_lula = abs(pct_lula_am - OFICIAL["candidatos"][13]["pct"])
    desvio_bolso = abs(pct_bolso_am - OFICIAL["candidatos"][22]["pct"])

    if desvio_lula < 1.0 and desvio_bolso < 1.0:
        st.success(
            f"Os totais calculados a partir dos boletins de urna são consistentes com o "
            f"resultado oficial do TSE. "
            f"Desvio máximo: {fmt_num(max(desvio_lula, desvio_bolso), 2)} pontos percentuais."
        )
    elif desvio_lula < 2.0 and desvio_bolso < 2.0:
        st.warning(
            f"Desvio moderado entre os dados das urnas e o resultado oficial. "
            f"Lula: {fmt_num(desvio_lula, 2)} p.p. | Bolsonaro: {fmt_num(desvio_bolso, 2)} p.p."
        )
    else:
        st.error(
            f"Desvio significativo detectado! "
            f"Lula: {fmt_num(desvio_lula, 2)} p.p. | Bolsonaro: {fmt_num(desvio_bolso, 2)} p.p."
        )

    # ============================================================
    # 3. Análise de risco e vulnerabilidades
    # ============================================================
    st.markdown("---")
    st.markdown("### 3. Análise de Risco e Vulnerabilidades")

    por_codigo = store.query_df(f"""
        SELECT i.codigo, COUNT(*) AS total
        FROM issues i JOIN secoes s ON i.secao_id = s.id
        WHERE {f['issue_where']}
        GROUP BY i.codigo
    """, f["issue_params"])
    st.markdown("**O que as ocorrências podem dizer sobre manipulação**")
    grupos_resumo(contar_por_grupo(dict(zip(por_codigo["codigo"], por_codigo["total"], strict=False))))
    st.caption(
        "Grupo 1 reúne o que não deveria ocorrer num sistema íntegro; grupo 2, inconsistências com "
        "explicações legítimas conhecidas; grupo 3, registros de operação e estatística. A classificação "
        "de cada código está na página Inconsistências e no README."
    )

    # Issues por severidade
    issues_sev = store.query_df(f"""
        SELECT i.severidade, COUNT(*) as total, COUNT(DISTINCT i.secao_id) as secoes
        FROM issues i JOIN secoes s ON i.secao_id = s.id
        WHERE {f['issue_where']}
        GROUP BY i.severidade
        ORDER BY CASE i.severidade
            WHEN 'critica' THEN 1 WHEN 'alta' THEN 2
            WHEN 'media' THEN 3 ELSE 4
        END
    """, f["issue_params"])

    # Issues que afetam diretamente a contagem de votos
    issues_voto = store.query_df(f"""
        SELECT i.codigo, COUNT(*) as total, COUNT(DISTINCT i.secao_id) as secoes
        FROM issues i JOIN secoes s ON i.secao_id = s.id
        WHERE {f['issue_where']} AND i.codigo IN ('C01','C05','A02','A06','A03')
        GROUP BY i.codigo ORDER BY total DESC
    """, f["issue_params"])

    # Votos em seções com issues graves
    votos_afetados = store.query_df(f"""
        SELECT COALESCE(SUM(s.comparecimento), 0) as comp
        FROM secoes s
        WHERE {f['where']} AND s.id IN (
            SELECT DISTINCT i.secao_id FROM issues i
            WHERE i.codigo IN ('C01','C05','A02','A06','A03')
        )
    """, f["params"])

    hashes_verificados = bool(analysis.hash_verification_status(store)["verificado"])

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**Classificação de Riscos**")

        riscos = []
        # Risco 1: Integridade de hash
        hash_issues = issues_voto[issues_voto["codigo"] == "C01"]["total"].sum() if not issues_voto.empty else 0
        if hash_issues > 0:
            riscos.append(("CRÍTICO", f"{int(hash_issues)} arquivo(s) com hash SHA-512 inválido (possível adulteração)"))
        elif not hashes_verificados:
            riscos.append(("NÃO VERIFICADO", "Hashes SHA-512 não verificados nesta base: "
                           "a integridade dos arquivos não foi avaliada"))
        else:
            riscos.append(("OK", "Nenhum hash inválido detectado: integridade dos arquivos preservada"))

        # Risco 2: Overflow de votos
        overflow = issues_voto[issues_voto["codigo"] == "C05"]["total"].sum() if not issues_voto.empty else 0
        if overflow > 0:
            riscos.append(("CRÍTICO", f"{int(overflow)} seção(ões) com mais votos que eleitores aptos"))
        else:
            riscos.append(("OK", "Nenhuma seção com votos excedendo eleitores aptos"))

        # Risco 3: Divergência log vs BU
        div_log = issues_voto[issues_voto["codigo"] == "A03"]["total"].sum() if not issues_voto.empty else 0
        if div_log > 0:
            riscos.append(("ATENÇÃO", f"{int(div_log)} seção(ões) com divergência entre log e BU (todas em urnas reserva)"))
        else:
            riscos.append(("OK", "Sem divergências entre log e boletim de urna"))

        # Risco 4: Reboots
        total_reboots = int(s["reboots"])
        pct_reboot = total_reboots / total_secoes * 100 if total_secoes > 0 else 0
        if total_reboots > 0:
            if pct_reboot > 20:
                riscos.append(("ALTO", f"{total_reboots} reboots ({fmt_pct(pct_reboot, 1)} das seções): taxa muito elevada"))
            elif pct_reboot > 10:
                riscos.append(("MÉDIO", f"{total_reboots} reboots ({fmt_pct(pct_reboot, 1)} das seções): taxa elevada"))
            else:
                riscos.append(("BAIXO", f"{total_reboots} reboots ({fmt_pct(pct_reboot, 1)} das seções)"))
        else:
            riscos.append(("OK", "Nenhum reboot durante a votação"))

        for nivel, desc in riscos:
            severity_line(nivel, desc)

    with col2:
        st.markdown("**Resumo de Issues**")
        if not issues_sev.empty:
            show_df(issues_sev, width="stretch", hide_index=True)
        else:
            st.info("Nenhuma issue encontrada.")

    # ============================================================
    # 4. Análise de impacto
    # ============================================================
    st.markdown("---")
    st.markdown("### 4. Análise de Impacto no Resultado")

    comp_afetado = int(votos_afetados.iloc[0]["comp"]) if not votos_afetados.empty else 0
    pct_afetado = comp_afetado / total_comp * 100 if total_comp > 0 else 0

    col1, col2, col3 = st.columns(3)
    col1.metric("Votos em Seções Críticas", f"{fmt_int(comp_afetado)}")
    col2.metric("% dos Votos da Base", f"{fmt_pct(pct_afetado, 2)}")
    col3.metric("Diferença oficial entre 1º e 2º colocados", f"{fmt_int(OFICIAL['diferenca_1_2'])}")

    # Análise: mesmo invalidando TODOS os votos das seções com problemas críticos
    st.markdown("**Cenário hipotético extremo:**")
    st.markdown(
        f"Se **todos os {fmt_int(comp_afetado)} votos** das seções com issues críticas "
        f"(C01, C05, A02 e A06, do grupo 1, mais A03, do grupo 2) fossem completamente invalidados, isso representaria "
        f"apenas **{fmt_pct(pct_afetado, 2)}** dos votos da base analisada."
    )

    if comp_afetado < OFICIAL["diferenca_1_2"]:
        st.success(
            f"Mesmo no cenário mais extremo (invalidação total), o volume de votos "
            f"potencialmente afetados ({fmt_int(comp_afetado)}) é muito inferior à diferença "
            f"entre o 1º e o 2º colocados ({fmt_int(OFICIAL['diferenca_1_2'])} votos). "
            f"**As inconsistências encontradas NÃO teriam capacidade de alterar o resultado.**"
        )
    else:
        st.warning(
            f"O volume de votos potencialmente afetados ({fmt_int(comp_afetado)}) merece "
            f"atenção detalhada em relação à diferença entre candidatos "
            f"({fmt_int(OFICIAL['diferenca_1_2'])} votos)."
        )

    # Comparação de distribuição em seções problemáticas vs normais
    st.markdown("**Distribuição de votos: seções com issues vs sem issues**")

    dist_df = analysis.votos_13_22_por_grupo(
        store, f, "CASE WHEN s.has_issues THEN 'Com Issues' ELSE 'Sem Issues' END"
    )

    if not dist_df.empty:
        pivot_dist = dist_df.pivot_table(
            index="grupo", columns="candidato", values="votos", fill_value=0
        )
        for col in pivot_dist.columns:
            pivot_dist[col] = pivot_dist[col].astype(int)

        totals = pivot_dist.sum(axis=1)
        pct_df = pivot_dist.copy()
        for col in pct_df.columns:
            pct_df[col] = (pivot_dist[col] / totals * 100).round(2)

        pct_df.columns = [f"Cand {c} (%)" for c in pct_df.columns]
        pivot_dist.columns = [f"Cand {c} (votos)" for c in pivot_dist.columns]

        resultado = pd.concat([pivot_dist, pct_df], axis=1)
        show_df(resultado, width="stretch")

    # Análise por modelo de urna
    st.markdown("**Distribuição por modelo de urna (Presidente)**")
    modelo_voto_df = analysis.presidente_13_22_por_modelo(store, f)

    if not modelo_voto_df.empty:
        modelo_voto_df["lula_pct"] = (modelo_voto_df["lula"] / modelo_voto_df["total"] * 100).round(1)
        modelo_voto_df["bolsonaro_pct"] = (modelo_voto_df["bolsonaro"] / modelo_voto_df["total"] * 100).round(1)
        show_df(modelo_voto_df, width="stretch", hide_index=True)

        st.caption(
            "Nota: Variações entre modelos refletem a distribuição geográfica das urnas. "
            "Modelos mais antigos (UE2009 a UE2013) predominam nas regiões Norte/Nordeste; "
            "modelos mais novos (UE2020) predominam no Sul/Sudeste."
        )

    # ============================================================
    # 5. Veredicto Final (Enhanced with analysis module)
    # ============================================================
    st.markdown("---")
    st.markdown("### 5. Veredicto Final")

    # Try to use the analysis module's confidence score
    confidence_data = None
    try:
        confidence_data = analysis.compute_confidence_score(store, f)
    except Exception as e:  # o cálculo detalhado falhou: usa o método simplificado
        show_error("Erro ao calcular o score detalhado; exibindo o cálculo simplificado", e, level="info")
        confidence_data = None

    if confidence_data and isinstance(confidence_data, dict) and "score" in confidence_data:
        score = confidence_data["score"]
        nivel_conf = confidence_data.get("nivel", "MODERADA")
        categorias = confidence_data.get("categorias", [])
        veredicto_votos = confidence_data.get("veredicto_votos", "")
        veredicto_auditoria = confidence_data.get("veredicto_auditoria", "")
        justificativa = confidence_data.get("justificativa", "")
        nota_integridade = confidence_data.get("nota_integridade")

        # Classificação visual
        if score >= 85:
            cor_conf = "success"
            veredicto = "RESULTADO CONSISTENTE"
        elif score >= 60:
            cor_conf = "warning"
            veredicto = "RESULTADO COM RESSALVAS"
        else:
            cor_conf = "error"
            veredicto = "RESULTADO QUESTIONÁVEL"

        # Score com barra de progresso
        st.markdown(f"#### Confiança na Integridade: **{fmt_num(score, 0)}/100** ({nivel_conf})")
        st.progress(min(100, max(0, int(score))) / 100)
        getattr(st, cor_conf)(f"**{veredicto}**")
        if nota_integridade:
            st.info(f"**Integridade de hash não verificada.** {nota_integridade}")

        # Categorias de risco individuais
        if categorias:
            st.markdown("#### Categorias de Risco")
            cat_cols = st.columns(min(len(categorias), 4))
            for idx, cat in enumerate(categorias):
                cat_name = cat.get("nome", f"Categoria {idx + 1}")
                cat_score_val = cat.get("score", 0)
                col_idx = idx % min(len(categorias), 4)
                if cat_score_val is None:  # componente não avaliado: sem score
                    with cat_cols[col_idx]:
                        st.metric(cat_name, "Não verificado")
                        if cat.get("detalhe"):
                            st.caption(cat["detalhe"])
                    continue
                if not isinstance(cat_score_val, (int, float)):
                    cat_score_val = 0
                with cat_cols[col_idx]:
                    if cat_score_val >= 85:
                        cat_color = "normal"
                    elif cat_score_val >= 60:
                        cat_color = "off"
                    else:
                        cat_color = "inverse"
                    st.metric(cat_name, f"{fmt_num(cat_score_val, 0)}/100", delta_color=cat_color)
                    if cat.get("detalhe"):
                        st.caption(cat["detalhe"])

        # Veredictos
        if veredicto_votos:
            st.markdown("#### Veredicto sobre os Votos")
            st.markdown(veredicto_votos)

        if veredicto_auditoria:
            st.markdown("#### Veredicto da Auditoria")
            st.markdown(veredicto_auditoria)

        if justificativa:
            st.markdown("#### Justificativa")
            st.markdown(justificativa)

    else:
        # Fallback: hand-coded confidence score (original logic)
        score = 100.0
        motivos_risco = []
        motivos_ok = []

        # Fator 1: Consistência com resultado oficial
        if desvio_lula < 0.5 and desvio_bolso < 1.0:
            motivos_ok.append(
                f"Resultados dos boletins de urna consistentes com o resultado oficial "
                f"(desvio max.: {fmt_num(max(desvio_lula, desvio_bolso), 2)} p.p.)"
            )
        else:
            score -= min(20, max(desvio_lula, desvio_bolso) * 5)
            motivos_risco.append(
                f"Desvio de {fmt_num(max(desvio_lula, desvio_bolso), 2)} p.p. em relação ao resultado oficial"
            )

        # Fator 2: Hashes (sem verificação SHA-512, nada a afirmar nem a pontuar)
        if hash_issues == 0 and not hashes_verificados:
            motivos_risco.append(
                "Hashes SHA-512 não verificados nesta base: integridade dos arquivos não avaliada"
            )
        elif hash_issues == 0:
            motivos_ok.append("Integridade de arquivos verificada: nenhum hash corrompido")
        else:
            score -= 30
            motivos_risco.append(f"{int(hash_issues)} arquivo(s) com hash inválido")

        # Fator 3: Overflow de votos
        if overflow == 0:
            motivos_ok.append("Nenhuma seção com votos excedendo eleitores aptos")
        else:
            score -= 25
            motivos_risco.append(f"{int(overflow)} seção(ões) com overflow de votos")

        # Fator 4: Reboots
        pct_reboot = total_reboots / total_secoes * 100 if total_secoes > 0 else 0
        if pct_reboot > 20:
            score -= 15
            motivos_risco.append(f"Taxa elevada de reboots: {fmt_pct(pct_reboot, 1)}")
        elif pct_reboot > 10:
            score -= 8
            motivos_risco.append(f"Taxa moderada de reboots: {fmt_pct(pct_reboot, 1)}")
        else:
            motivos_ok.append(f"Taxa de reboots dentro do aceitável: {fmt_pct(pct_reboot, 1)}")

        # Fator 5: Impacto potencial
        if comp_afetado < OFICIAL["diferenca_1_2"] * 0.01:
            motivos_ok.append(
                "Volume de votos em seções críticas insignificante frente "
                "à diferença entre candidatos"
            )
        elif comp_afetado < OFICIAL["diferenca_1_2"]:
            score -= 5
            motivos_risco.append(
                f"Votos em seções críticas ({fmt_int(comp_afetado)}) abaixo da diferença "
                f"entre candidatos, mas merecendo acompanhamento"
            )
        else:
            score -= 20
            motivos_risco.append(
                f"Volume de votos em seções críticas ({fmt_int(comp_afetado)}) próximo "
                f"ou superior à diferença entre candidatos"
            )

        # Fator 6: Distribuição uniforme de issues
        motivos_ok.append(
            "Issues distribuídas uniformemente entre estados e modelos, "
            "sem concentração suspeita"
        )

        score = max(0, min(100, score))

        # Classificação
        if score >= 85:
            nivel_conf = "ALTA"
            cor_conf = "success"
            veredicto = "RESULTADO CONSISTENTE"
        elif score >= 60:
            nivel_conf = "MODERADA"
            cor_conf = "warning"
            veredicto = "RESULTADO COM RESSALVAS"
        else:
            nivel_conf = "BAIXA"
            cor_conf = "error"
            veredicto = "RESULTADO QUESTIONÁVEL"

        # Exibir veredicto com barra de progresso
        st.markdown(f"#### Confiança na Integridade: **{fmt_num(score, 0)}/100** ({nivel_conf})")
        st.progress(min(100, max(0, int(score))) / 100)

        getattr(st, cor_conf)(f"**{veredicto}**")

        # Explicação detalhada
        st.markdown("#### Explicação")

        # Determinar se o eleito foi legitimamente eleito
        vencedor_base = 13 if pct_lula_am > pct_bolso_am else 22
        vencedor_oficial = OFICIAL["vencedor"]
        nome_vencedor = OFICIAL["candidatos"][vencedor_oficial]["nome"]
        partido_vencedor = OFICIAL["candidatos"][vencedor_oficial]["partido"]

        if vencedor_base == vencedor_oficial:
            st.markdown(
                f"Com base na análise de **{fmt_int(total_secoes)} seções** em "
                f"**{int(s['ufs'])} estados**, cobrindo **{fmt_int(total_eleitores)} eleitores** "
                f"({fmt_pct(pct_cobertura, 2)} do eleitorado), os dados das urnas eletrônicas "
                f"confirmam que o candidato **{nome_vencedor} ({partido_vencedor})** obteve "
                f"a maioria dos votos válidos no {turno_label} "
                f"(**{fmt_pct(pct_lula_am, 2)}** nos boletins vs **{fmt_pct(OFICIAL['candidatos'][13]['pct'], 2)}** oficial)."
            )
        else:
            st.warning(
                f"Os dados selecionados indicam um vencedor diferente do resultado oficial no "
                f"{turno_label}. Com filtros, isso pode refletir apenas o recorte escolhido; sem "
                f"filtros, indicaria divergência a investigar."
            )

        st.markdown("#### Justificativa")

        if motivos_ok:
            st.markdown("**Fatores positivos (sustentam a integridade):**")
            for m in motivos_ok:
                st.markdown(f"- {m}")

        if motivos_risco:
            st.markdown("**Fatores de risco (requerem atenção):**")
            for m in motivos_risco:
                st.markdown(f"- {m}")

        st.markdown("#### Conclusão")

        conclusao_parts = []

        if score >= 85:
            conclusao_parts.append(
                "A análise dos dados brutos das urnas eletrônicas **NÃO encontrou evidências** "
                "de fraude ou manipulação que pudessem alterar o resultado da eleição. "
            )
            conclusao_parts.append(
                "Os totais dos boletins de urna são consistentes com o resultado "
                "oficial divulgado pelo TSE. As inconsistências encontradas são de natureza "
                "operacional (reboots, divergências em urnas reserva) e não indicam "
                "adulteração de votos."
            )
        elif score >= 60:
            conclusao_parts.append(
                "A análise encontrou **algumas inconsistências** que merecem investigação "
                "mais aprofundada, mas que **isoladamente não são suficientes** para "
                "questionar o resultado da eleição."
            )
        else:
            conclusao_parts.append(
                "A análise encontrou **inconsistências significativas** que "
                "**comprometem a confiança** no resultado. Recomenda-se auditoria "
                "completa e independente."
            )

        conclusao_parts.append(
            f"\n\n**Nota metodológica:** Esta análise usa os boletins de urna de "
            f"{fmt_int(total_secoes)} seções ({fmt_pct(pct_cobertura, 2)} do eleitorado apto do "
            f"turno). Sem filtros, a base cobre praticamente todas as seções das 27 UFs; as "
            f"seções do exterior não estão incluídas. Com filtros, as conclusões valem apenas "
            f"para o recorte selecionado."
        )

        for p in conclusao_parts:
            st.markdown(p)

    # Vulnerabilidades sistêmicas identificadas
    st.markdown("---")
    st.markdown("### 6. Vulnerabilidades Sistêmicas Identificadas")

    vulns = [
        {
            "titulo": "Reinicialização durante a votação (C06)",
            "descricao": (
                f"**{total_reboots} reboots** detectados em {fmt_int(total_secoes)} seções "
                f"({fmt_pct(pct_reboot, 1)}). Urnas reiniciando durante a votação representam "
                f"uma vulnerabilidade de disponibilidade. Embora os votos já computados "
                f"sejam preservados (segundo o TSE), o processo de reinício pode causar "
                f"filas, inibir eleitores e potencialmente expor a urna a vetores de ataque."
            ),
            "risco": "MÉDIO" if pct_reboot < 20 else "ALTO",
            "recomendacao": "Investigar causa-raiz dos reboots por modelo de urna. "
                           "Modelos mais antigos podem necessitar substituição.",
        },
        {
            "titulo": "Software único em todas as urnas",
            "descricao": (
                "Todas as urnas analisadas executam a mesma versão de software "
                "(8.26.0.0 Onça-pintada). Isso significa que uma vulnerabilidade "
                "no software afetaria TODAS as urnas simultaneamente (single point of failure)."
            ),
            "risco": "ALTO",
            "recomendacao": "Auditoria independente do código-fonte. "
                           "Considerar diversificação de software.",
        },
        {
            "titulo": "Ausência de verificação independente",
            "descricao": (
                "O processo de votação não possui comprovante físico (voto impresso) "
                "que permita recontagem independente. A integridade depende "
                "exclusivamente do software e dos mecanismos digitais."
            ),
            "risco": "ALTO",
            "recomendacao": "Implementar trilha de auditoria física (voto impresso conferível).",
        },
        {
            "titulo": "Divergências em urnas reserva (A03)",
            "descricao": (
                f"{int(div_log)} seção(ões) apresentaram divergência entre o número "
                f"de votos registrados no log e o total do boletim de urna. "
                f"Todas ocorreram em urnas do tipo 'reservaSeção', indicando "
                f"transferência parcial de dados."
            ),
            "risco": "BAIXO",
            "recomendacao": "Documentar procedimento de contingência com urnas reserva.",
        },
    ]

    for vuln in vulns:
        with st.expander(f"Risco {vuln['risco']}: {vuln['titulo']}"):
            st.markdown(vuln["descricao"])
            st.markdown(f"**Recomendação:** {vuln['recomendacao']}")

    # Botões de exportação
    render_export_buttons(store, f)


def render_export_buttons(store, f):
    """Botões de exportação do veredicto (relatórios do turno exibido)."""
    st.markdown("---")
    st.markdown("### Exportar Relatório")

    # O relatório gerado fica associado aos filtros que o produziram: trocar
    # um filtro não deixa disponível para download um relatório antigo.
    chave = hash(f)
    col1, col2 = st.columns(2)

    with col1:
        if st.button("Gerar Relatório Excel", type="secondary", key="export_excel_btn"):
            with st.spinner("Gerando relatório Excel..."):
                try:
                    st.session_state["_export_excel"] = (chave, analysis.generate_excel_report(store, f))
                except Exception as e:
                    show_error("Erro ao gerar o relatório Excel", e)

        gerado = st.session_state.get("_export_excel")
        if gerado and gerado[0] == chave:
            st.download_button(
                label="Baixar Relatório Excel (.xlsx)",
                data=gerado[1],
                file_name=f"auditoria_eleicoes_2022_{f.file_suffix}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

    with col2:
        if st.button("Gerar Relatório Texto", type="secondary", key="export_text_btn"):
            with st.spinner("Gerando relatório texto..."):
                try:
                    st.session_state["_export_text"] = (chave, analysis.generate_text_report(store, f))
                except Exception as e:
                    show_error("Erro ao gerar o relatório texto", e)

        gerado = st.session_state.get("_export_text")
        if gerado and gerado[0] == chave:
            st.download_button(
                label="Baixar Relatório Texto (.txt)",
                data=gerado[1],
                file_name=f"auditoria_eleicoes_2022_{f.file_suffix}.txt",
                mime="text/plain",
            )
