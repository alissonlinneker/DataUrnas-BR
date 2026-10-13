"""Explorador de seção e dados brutos paginados."""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from dataurnas.dashboard.state import analysis
from dataurnas.dashboard.components.charts import C_BLUE, C_GREEN, C_ORANGE, C_VERMILLION, show_chart
from dataurnas.dashboard.components.errors import show_error
from dataurnas.dashboard.components.formatting import fmt_int, fmt_pct
from dataurnas.dashboard.components.tables import show_df


def tab_drilldown(store, f):
    """Tab Explorador de Seção com drill-down cascata."""
    st.subheader("Explorador de Seção")
    st.caption("Selecione uma seção específica para análise detalhada")

    # ---- Seletores em cascata ----
    col_uf, col_mun, col_zona, col_secao = st.columns(4)

    # 1. UF
    ufs_df = store.query_df(f"""
        SELECT DISTINCT s.uf
        FROM secoes s
        WHERE {f['where']}
        ORDER BY s.uf
    """, f["params"])

    if ufs_df.empty:
        st.info("Nenhuma seção encontrada para os filtros atuais.")
        return

    ufs_list = ufs_df["uf"].tolist()

    with col_uf:
        uf_sel = st.selectbox("UF", options=ufs_list, key="drilldown_uf")

    # 2. Município
    mun_params = list(f["params"]) + [uf_sel]
    mun_df = store.query_df(f"""
        SELECT DISTINCT s.municipio
        FROM secoes s
        WHERE {f['where']} AND s.uf = ?
        ORDER BY s.municipio
    """, mun_params)

    mun_list = mun_df["municipio"].tolist() if not mun_df.empty else []

    with col_mun:
        mun_sel = st.selectbox("Município", options=mun_list, key="drilldown_mun")

    # 3. Zona
    zona_params = list(f["params"]) + [uf_sel, mun_sel]
    zona_df = store.query_df(f"""
        SELECT DISTINCT s.zona
        FROM secoes s
        WHERE {f['where']} AND s.uf = ? AND s.municipio = ?
        ORDER BY s.zona
    """, zona_params)

    zona_list = zona_df["zona"].tolist() if not zona_df.empty else []

    with col_zona:
        zona_sel = st.selectbox("Zona", options=zona_list, key="drilldown_zona")

    # 4. Seção
    secao_params = list(f["params"]) + [uf_sel, mun_sel, zona_sel]
    secao_df = store.query_df(f"""
        SELECT s.id, s.secao, s.turno
        FROM secoes s
        WHERE {f['where']} AND s.uf = ? AND s.municipio = ? AND s.zona = ?
        ORDER BY s.turno, s.secao
    """, secao_params)

    if secao_df.empty:
        st.info("Nenhuma seção encontrada para a combinação selecionada.")
        return

    secao_options = {}
    for _, row in secao_df.iterrows():
        label = f"Seção {row['secao']} (T{int(row['turno'])})"
        secao_options[label] = row["id"]

    with col_secao:
        secao_label = st.selectbox(
            "Seção", options=list(secao_options.keys()), key="drilldown_secao"
        )

    if not secao_label:
        return

    secao_id = secao_options[secao_label]

    st.divider()

    # ---- Dados da seção ----
    detail = analysis.section_detail(store, secao_id)
    info = detail["info"]

    if not info:
        st.warning("Seção não encontrada no banco de dados.")
        return

    # ---- Card com informações ----
    st.markdown("### Informações da Seção")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("UF", str(info.get("uf", "-")).upper())
    c2.metric("Município", str(info.get("municipio", "-")))
    c3.metric("Zona / Seção", f"{info.get('zona', '-')} / {info.get('secao', '-')}")
    c4.metric("Turno", f"{info.get('turno', '-')}o")

    c5, c6, c7, c8 = st.columns(4)
    modelo = info.get("modelo_urna", "-")
    c5.metric("Modelo", f"UE{modelo}" if modelo and modelo != "-" else "-")
    c6.metric("Tipo Urna", str(info.get("tipo_urna", "-")))
    c7.metric("Software", str(info.get("versao_sw", "-")))
    c8.metric("Reserva", "Sim" if info.get("is_reserva") else "Não")

    c9, c10, c11, c12 = st.columns(4)
    eleitores = info.get("eleitores_aptos", 0)
    comparecimento = info.get("comparecimento", 0)
    c9.metric("Eleitores Aptos", f"{fmt_int(eleitores)}" if eleitores else "-")
    c10.metric("Comparecimento", f"{fmt_int(comparecimento)}" if comparecimento else "-")
    pct_bio = info.get("pct_biometria")
    c11.metric("Biometria", f"{fmt_pct(pct_bio, 1)}" if pd.notna(pct_bio) else "-")
    pct_abs = info.get("pct_abstencao")
    c12.metric("Abstenção", f"{fmt_pct(pct_abs, 1)}" if pd.notna(pct_abs) else "-")

    c13, c14, c15, c16 = st.columns(4)
    c13.metric("Hora Abertura", str(info.get("hora_abertura", "-")))
    c14.metric("Hora Encerramento", str(info.get("hora_encerramento", "-")))
    duracao = info.get("duracao_min")
    c15.metric("Duração (min)", f"{duracao}" if pd.notna(duracao) else "-")
    reboots = info.get("reboots", 0)
    c16.metric("Reboots", f"{reboots}")

    # ---- Score de risco ----
    st.markdown("### Score de Risco")

    risk = analysis.section_risk_score(store, secao_id)
    risk_score = risk["score"]
    risk_nivel = risk["nivel"]
    risk_detalhes = risk["detalhes"]

    col_gauge, col_detalhes = st.columns([1, 1])

    with col_gauge:
        if risk_nivel == "OK":
            bar_color = C_GREEN
        elif risk_nivel == "ATENÇÃO":
            bar_color = C_ORANGE
        else:
            bar_color = C_VERMILLION

        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=risk_score,
            domain={"x": [0, 1], "y": [0, 1]},
            title={"text": f"Risco: {risk_nivel}"},
            gauge={
                "axis": {"range": [0, 100], "tickwidth": 1},
                "bar": {"color": bar_color},
                "bgcolor": "rgba(0,0,0,0)",
                "steps": [
                    {"range": [0, 15], "color": "rgba(0,158,115,0.18)"},
                    {"range": [15, 40], "color": "rgba(230,159,0,0.20)"},
                    {"range": [40, 100], "color": "rgba(213,94,0,0.20)"},
                ],
                "threshold": {
                    "line": {"color": C_VERMILLION, "width": 2},
                    "thickness": 0.75,
                    "value": risk_score,
                },
            },
        ))
        fig.update_layout(height=300)
        show_chart(fig)

    with col_detalhes:
        st.markdown("**Fatores de risco:**")
        for detalhe in risk_detalhes:
            st.markdown(f"- {detalhe}")

    # ---- Tabela de votos por cargo/candidato ----
    st.markdown("### Votos por Cargo")
    votos_df = detail["votos"]
    if not votos_df.empty:
        for cargo in votos_df["cargo"].unique():
            cargo_data = votos_df[votos_df["cargo"] == cargo].copy()
            st.markdown(f"**{cargo}**")
            display_cols = ["tipo_voto", "codigo_candidato", "partido", "quantidade"]
            available_cols = [c for c in display_cols if c in cargo_data.columns]
            show_df(
                cargo_data[available_cols].reset_index(drop=True),
                width="stretch",
                hide_index=True,
            )
    else:
        st.info("Nenhum voto encontrado para esta seção.")

    # ---- Tabela de issues ----
    st.markdown("### Inconsistências (Issues)")
    issues_df = detail["issues"]
    if not issues_df.empty:
        display_cols = ["codigo", "severidade", "descricao", "base_legal"]
        available_cols = [c for c in display_cols if c in issues_df.columns]
        show_df(
            issues_df[available_cols].reset_index(drop=True),
            width="stretch",
            hide_index=True,
        )
    else:
        st.success("Nenhuma inconsistência registrada para esta seção.")

    # ---- Timeline visual ----
    st.markdown("### Timeline da Votação")
    hora_abertura = info.get("hora_abertura")
    hora_encerramento = info.get("hora_encerramento")

    if hora_abertura and hora_encerramento and str(hora_abertura) != "None":
        try:
            def _parse_hora(h):
                # Formato no banco: "02/10/2022 06:34:02" (data opcional)
                parts = str(h).strip().split(" ")[-1].split(":")
                if len(parts) >= 2:
                    return int(parts[0]) * 60 + int(parts[1])
                return 0

            min_abertura = _parse_hora(hora_abertura)
            min_encerramento = _parse_hora(hora_encerramento)

            fig = go.Figure()

            fig.add_trace(go.Bar(
                x=[min_encerramento - min_abertura],
                y=["Votação"],
                orientation="h",
                base=[min_abertura],
                marker_color=C_BLUE,
                text=[f"{hora_abertura} -> {hora_encerramento}"],
                textposition="inside",
                name="Período de votação",
            ))

            n_reboots = int(reboots) if pd.notna(reboots) else 0
            if n_reboots > 0:
                intervalo = (min_encerramento - min_abertura)
                for i in range(min(n_reboots, 10)):
                    pos = min_abertura + intervalo * (i + 1) / (n_reboots + 1)
                    fig.add_trace(go.Scatter(
                        x=[pos],
                        y=["Votação"],
                        mode="markers",
                        marker=dict(size=14, color=C_VERMILLION, symbol="x"),
                        name=f"Reboot {i + 1}" if i == 0 else None,
                        showlegend=(i == 0),
                    ))

            fig.add_vline(x=480, line_dash="dash", line_color=C_GREEN,
                          annotation_text="8h (abertura oficial)")
            fig.add_vline(x=1020, line_dash="dash", line_color=C_ORANGE,
                          annotation_text="17h (encerramento oficial)")

            tick_vals = list(range(360, 1260, 60))
            tick_text = [f"{v // 60}:{v % 60:02d}" for v in tick_vals]

            fig.update_layout(
                xaxis=dict(
                    title="Horário",
                    tickvals=tick_vals,
                    ticktext=tick_text,
                    range=[360, 1260],
                ),
                yaxis=dict(title=""),
                height=240,
                showlegend=True,
                margin=dict(l=10, r=10, t=30, b=40),
            )
            show_chart(fig)
        except Exception as e:
            show_error("Erro ao renderizar timeline", e)
    else:
        st.info("Informações de horário não disponíveis para esta seção.")

    # ---- Totais por cargo ----
    st.markdown("### Totais por Cargo")
    totais_df = detail["totais"]
    if not totais_df.empty:
        display_cols = [
            "cargo", "comparecimento", "nominais",
            "brancos", "nulos", "legenda", "total",
        ]
        available_cols = [c for c in display_cols if c in totais_df.columns]
        show_df(
            totais_df[available_cols].reset_index(drop=True),
            width="stretch",
            hide_index=True,
        )
    else:
        st.info("Nenhum total por cargo disponível.")


def tab_dados_brutos_v2(store, f):
    """Tab de dados brutos melhorada com paginação e filtros adicionais."""
    st.subheader("Explorar Seções")

    # Filtros inline
    search_col1, search_col2, search_col3, search_col4 = st.columns(4)
    with search_col1:
        search_uf = st.text_input("Filtrar por UF (ex.: SP)", key="brutos_v2_uf")
    with search_col2:
        mun_query_where = f["where"]
        mun_query_params = list(f["params"])
        if search_uf:
            mun_query_where += " AND LOWER(s.uf) = ?"
            mun_query_params.append(search_uf.strip().lower()[:2])

        mun_options_df = store.query_df(f"""
            SELECT DISTINCT s.municipio
            FROM secoes s
            WHERE {mun_query_where}
            ORDER BY s.municipio
            LIMIT 500
        """, mun_query_params)

        mun_list = mun_options_df["municipio"].tolist() if not mun_options_df.empty else []
        search_mun = st.selectbox(
            "Município",
            [""] + mun_list,
            index=0,
            key="brutos_v2_mun",
        )
    with search_col3:
        search_zona = st.text_input("Filtrar por zona", key="brutos_v2_zona")
    with search_col4:
        search_secao = st.text_input("Filtrar por seção", key="brutos_v2_secao")

    # Montar WHERE adicional
    extra_where = f["where"]
    extra_params = list(f["params"])
    if search_uf:
        extra_where += " AND LOWER(s.uf) = ?"
        extra_params.append(search_uf.strip().lower()[:2])
    if search_mun:
        extra_where += " AND s.municipio = ?"
        extra_params.append(search_mun.strip())
    if search_zona:
        extra_where += " AND s.zona = ?"
        extra_params.append(search_zona.strip())
    if search_secao:
        extra_where += " AND s.secao = ?"
        extra_params.append(search_secao.strip())

    # Contar total de resultados
    count_df = store.query_df(f"""
        SELECT COUNT(*) AS total
        FROM secoes s
        WHERE {extra_where}
    """, extra_params)
    total_results = int(count_df.iloc[0]["total"]) if not count_df.empty else 0

    if total_results == 0:
        st.info("Nenhuma seção encontrada.")
        return

    # Paginação
    page_size = 100
    total_pages = max(1, (total_results + page_size - 1) // page_size)

    pg_col1, pg_col2, pg_col3 = st.columns([1, 2, 1])
    with pg_col1:
        page = st.number_input(
            "Página",
            min_value=1,
            max_value=total_pages,
            value=1,
            step=1,
            key="brutos_v2_page",
        )
    with pg_col3:
        st.markdown(
            f"**{fmt_int(total_results)}** resultados | "
            f"Página **{page}** de **{total_pages}**"
        )

    offset = (page - 1) * page_size

    raw_df = store.query_df(f"""
        SELECT
            s.turno, s.id, UPPER(s.uf) AS uf, s.regiao, s.municipio,
            s.zona, s.secao,
            'UE' || s.modelo_urna AS modelo, s.tipo_urna, s.versao_sw,
            s.eleitores_aptos, s.comparecimento, s.pct_abstencao,
            s.pct_biometria, s.reboots, s.erros_log,
            s.hora_abertura, s.hora_encerramento, s.duracao_min,
            s.has_issues, s.n_issues
        FROM secoes s
        WHERE {extra_where}
        ORDER BY s.turno, s.uf, s.municipio, s.zona, s.secao
        LIMIT {page_size} OFFSET {offset}
    """, extra_params)

    if not raw_df.empty:
        show_df(raw_df, width="stretch", height=500, hide_index=True)
        st.caption(
            f"Exibindo {len(raw_df)} de {fmt_int(total_results)} seções "
            f"(página {page}/{total_pages})"
        )
    else:
        st.info("Nenhuma seção encontrada para esta página.")
