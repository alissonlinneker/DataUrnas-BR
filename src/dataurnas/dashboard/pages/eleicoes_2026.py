"""Eleições 2026: Presidente, 1º turno (página inicial do dashboard).

Resultado oficial (TSE) por país, UF e município, comparação com o 1º turno de
2022 e auditoria por seção a partir dos boletins de urna, que ainda estão em
coleta: a página funciona com cobertura parcial ou sem nenhum boletim.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dataurnas.dashboard import data2026 as d26
from dataurnas.dashboard.components.charts import (
    C_BLUE,
    C_GREEN,
    C_GREY,
    C_ORANGE,
    DIV_SCALE,
    SEQ_SCALE,
    candidate_color,
    show_chart,
)
from dataurnas.dashboard.components.errors import safe_section
from dataurnas.dashboard.components.formatting import fmt_int, fmt_num, fmt_pct, fmt_pp, pct
from dataurnas.dashboard.components.geo import FONTE_GEOJSON, brazil_geojson
from dataurnas.dashboard.components.tables import show_df
from dataurnas.dashboard.components.ui import empty_state, hero, kpi_cards, progress_bar

TTL_COLETA = 300  # boletins chegam em lotes; reavalia a cada 5 minutos


# ----------------------------------------------------------------------
# Cache (chaveado pela assinatura dos arquivos: novo lote invalida o cache)
# ----------------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def _oficial(sig: tuple):
    cand = d26.load_candidatos()
    res_uf = d26.load_resultado_uf()
    res_mun = d26.load_resultado_municipio()
    return (
        d26.load_resumo(),
        cand,
        d26.add_leader(res_uf, cand) if not res_uf.empty else res_uf,
        d26.add_leader(res_mun, cand) if not res_mun.empty else res_mun,
    )


# cache_resource: o conjunto completo passa de centenas de MB e não deve ser
# copiado (pickle) a cada rerun; as funções de página não o modificam.
@st.cache_resource(ttl=TTL_COLETA, max_entries=2, show_spinner="Lendo boletins de urna coletados...")
def _secoes(sig: tuple) -> d26.SecoesData:
    return d26.load_secoes()


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def _t1_2022() -> pd.DataFrame:
    return d26.load_2022_t1_by_uf()


@st.cache_data(ttl=TTL_COLETA, show_spinner=False)
def _benford(sig: tuple, numeros: tuple) -> pd.DataFrame:
    return d26.benford_first_digit(_secoes(sig).votos, list(numeros))


def _signature() -> tuple:
    return d26.files_signature()


# ----------------------------------------------------------------------
# Página
# ----------------------------------------------------------------------
def render() -> None:
    sig = _signature()
    resumo, cand, res_uf, res_mun = _oficial(sig)

    hero(
        "Eleições 2026: Presidente, 1º turno",
        "Resultado oficial do TSE por país, estado e município, comparação com 2022 e auditoria "
        "independente dos boletins de urna seção a seção.",
        eyebrow=f"Eleição de {resumo.get('data_eleicao', '04/10/2026')}",
    )

    if not resumo or cand.empty:
        empty_state(
            "Resultado de 2026 ainda não disponível",
            "Rode scripts/ele2026/fetch_resultados.py para baixar o resultado oficial em data/parquet/2026.",
            image="empty-database.svg",
        )
        return

    st.caption(
        f"Fonte: TSE (resultados.tse.jus.br), totalização de {resumo.get('totais', {}).get('data_totalizacao', '-')} "
        f"às {resumo.get('totais', {}).get('hora_totalizacao', '-')}; arquivo gerado em {resumo.get('data_geracao_tse', '-')}."
    )

    with safe_section("os indicadores nacionais"):
        _kpis(resumo)
    with safe_section("o ranking de candidatos"):
        _ranking(cand)
    with safe_section("o mapa por UF"):
        _mapa(res_uf, cand)
    with safe_section("a tabela de municípios"):
        _municipios(res_mun, cand)
    with safe_section("a comparação com 2022"):
        _comparacao_2022(res_uf)
    with safe_section("a auditoria por seção"):
        _auditoria_secoes(sig, res_uf, cand)


def _kpis(resumo: dict) -> None:
    t = resumo["totais"]
    st.markdown("### Panorama nacional")
    kpi_cards([
        {"label": "Eleitorado", "value": fmt_int(t["eleitorado"]),
         "help": f"{fmt_int(t['secoes_instaladas'])} seções instaladas"},
        {"label": "Comparecimento", "value": fmt_int(t["comparecimento"]),
         "help": fmt_pct(t["pct_comparecimento"]), "tone": "green"},
        {"label": "Abstenção", "value": fmt_int(t["abstencao"]), "help": fmt_pct(t["pct_abstencao"]), "tone": "grey"},
        {"label": "Votos válidos", "value": fmt_int(t["votos_validos"]),
         "help": f"{fmt_pct(pct(t['votos_validos'], t['votos_total']))} dos votos"},
        {"label": "Brancos", "value": fmt_int(t["votos_brancos"]), "help": fmt_pct(t["pct_brancos"]), "tone": "amber"},
        {"label": "Nulos", "value": fmt_int(t["votos_nulos_total"]),
         "help": f"{fmt_pct(t['pct_nulos'])} (inclui {fmt_int(t.get('votos_nulos_tecnicos', 0))} técnicos)",
         "tone": "red"},
    ])


def _ranking(cand: pd.DataFrame) -> None:
    st.markdown("### Votação por candidato")
    df = cand.copy()
    df["pct_txt"] = df["pct_validos"].map(fmt_pct)
    df["votos_txt"] = df["votos"].map(fmt_int)
    df_plot = df.iloc[::-1]  # maior no topo do gráfico horizontal
    fig = go.Figure(go.Bar(
        x=df_plot["pct_validos"],
        y=df_plot["rotulo"],
        orientation="h",
        marker_color=[candidate_color(n, i + 2) if i >= len(df_plot) - 6 else C_GREY
                      for i, n in enumerate(df_plot["numero"])],
        text=df_plot["pct_txt"] + "  (" + df_plot["votos_txt"] + ")",
        textposition="auto",
        hovertemplate="%{y}<br>%{x:.2f}% dos válidos<extra></extra>",
    ))
    fig.update_layout(xaxis_title="% dos votos válidos", yaxis_title="", showlegend=False)
    lider, segundo = df.iloc[0], df.iloc[1]
    show_chart(
        fig,
        height=max(320, 30 * len(df) + 80),
        caption=(
            f"{lider['rotulo']} lidera com {fmt_pct(lider['pct_validos'])} dos válidos, "
            f"{fmt_pp(lider['pct_validos'] - segundo['pct_validos'])} à frente de {segundo['rotulo']}. "
            f"Situação: {lider['situacao']} / {segundo['situacao']}."
        ),
    )
    with st.expander("Tabela de candidatos"):
        show_df(
            df[["numero", "nome_urna", "partido_sigla", "agremiacao_nome", "vice_nome_urna", "votos",
                "pct_validos", "situacao"]],
            hide_index=True,
            column_config={
                "numero": st.column_config.NumberColumn("Número", format="%d"),
                "nome_urna": "Candidato",
                "partido_sigla": "Partido",
                "agremiacao_nome": "Coligação/federação",
                "vice_nome_urna": "Vice",
                "pct_validos": st.column_config.ProgressColumn("% válidos", format="%.2f%%", min_value=0, max_value=100),
                "situacao": "Situação",
            },
        )


def _mapa(res_uf: pd.DataFrame, cand: pd.DataFrame) -> None:
    st.markdown("### Mapa por UF")
    df = res_uf[res_uf["uf"] != d26.UF_EXTERIOR].copy()
    df["sigla"] = df["uf"].str.upper()
    df["nome"] = df["uf"].map(d26.UF_NOMES)

    opcoes = {"Líder em cada UF": None}
    opcoes.update({f"% de {r}": int(n) for n, r in zip(cand["numero"].head(6), cand["rotulo"].head(6), strict=False)})
    opcoes.update({"Comparecimento (%)": "pct_comparecimento", "Nulos (%)": "pct_nulos", "Brancos (%)": "pct_brancos"})
    escolha = st.selectbox("Colorir o mapa por", list(opcoes), key="mapa2026_metrica")
    alvo = opcoes[escolha]

    geo = brazil_geojson()
    hover = {"sigla": False, "lider": True, "pct_lider": ":.2f", "margem_pp": ":.2f", "eleitorado": ":,"}
    labels = {"lider": "Líder", "pct_lider": "% do líder", "margem_pp": "Margem (p.p.)", "eleitorado": "Eleitorado"}
    if alvo is None:
        cores = {r: candidate_color(n, i) for i, (n, r) in enumerate(zip(cand["numero"], cand["rotulo"], strict=False))}
        fig = px.choropleth(df, geojson=geo, locations="sigla", featureidkey="properties.sigla",
                            color="lider", color_discrete_map=cores, hover_name="nome",
                            hover_data=hover, labels=labels)
        legenda = "Cor = candidato mais votado na UF; passe o cursor para ver % e margem."
    else:
        coluna = f"pct_{alvo}" if isinstance(alvo, int) else alvo
        escala = DIV_SCALE if isinstance(alvo, int) else SEQ_SCALE
        meio = 50 if isinstance(alvo, int) else None
        fig = px.choropleth(df, geojson=geo, locations="sigla", featureidkey="properties.sigla",
                            color=coluna, color_continuous_scale=escala, color_continuous_midpoint=meio,
                            hover_name="nome", hover_data=hover, labels={**labels, coluna: escolha})
        legenda = f"{escolha} por UF. Exterior não aparece no mapa."
    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(margin=dict(l=0, r=0, t=10, b=0))
    show_chart(fig, height=540, caption=f"{legenda} Malha: {FONTE_GEOJSON}.")

    with st.expander("Ver dados por UF"):
        cols = ["uf", "nome", "eleitorado", "pct_comparecimento", "lider", "pct_lider", "margem_pp"]
        cols += [f"pct_{int(n)}" for n in cand["numero"].head(4)]
        tab = res_uf.copy()
        tab["nome"] = tab["uf"].map(d26.UF_NOMES)
        tab["uf"] = tab["uf"].str.upper()
        nomes = dict(zip(cand["numero"].astype(int), cand["nome_exibicao"], strict=False))
        show_df(tab[cols], hide_index=True, column_config={
            f"pct_{int(n)}": st.column_config.NumberColumn(f"% {nomes[int(n)]}", format="%.2f")
            for n in cand["numero"].head(4)
        })


def _municipios(res_mun: pd.DataFrame, cand: pd.DataFrame) -> None:
    st.markdown("### Municípios")
    if res_mun.empty:
        empty_state("Resultado por município indisponível", "O arquivo resultado_municipio.parquet não foi encontrado.")
        return
    c1, c2, c3 = st.columns([2, 1, 1])
    busca = c1.text_input("Buscar município", key="mun2026_busca", placeholder="Ex.: Campinas")
    ufs = sorted(res_mun["uf"].unique())
    uf_sel = c2.multiselect("UF", ufs, key="mun2026_uf", format_func=lambda u: u.upper())
    ordem_opcoes = {"Eleitorado": "eleitorado", "Abstenção (%)": "pct_abstencao", "Nulos (%)": "pct_nulos",
                    "Margem do líder (p.p.)": "margem_pp"}
    ordem_opcoes.update({f"% {r}": f"pct_{int(n)}" for n, r in zip(cand["numero"].head(4), cand["rotulo"].head(4), strict=False)})
    ordem = c3.selectbox("Ordenar por", list(ordem_opcoes), key="mun2026_ordem")
    top_n = st.slider("Quantidade de municípios (top N)", 10, 500, 50, step=10, key="mun2026_topn")

    df = res_mun
    if uf_sel:
        df = df[df["uf"].isin(uf_sel)]
    if busca:
        df = df[df["nome"].str.contains(busca.strip(), case=False, na=False, regex=False)]
    df = df.sort_values(ordem_opcoes[ordem], ascending=False).head(top_n).copy()
    df["uf"] = df["uf"].str.upper()
    nomes = dict(zip(cand["numero"].astype(int), cand["nome_exibicao"], strict=False))
    pct_cols = [f"pct_{int(n)}" for n in cand["numero"].head(4)]
    cols = ["uf", "nome", "capital", "eleitorado", "pct_comparecimento", "pct_brancos", "pct_nulos",
            "lider", "pct_lider", "margem_pp"] + pct_cols
    show_df(df[cols], hide_index=True, column_config={
        "nome": "Município",
        "capital": st.column_config.CheckboxColumn("Capital"),
        "pct_comparecimento": st.column_config.NumberColumn("Comparecimento (%)", format="%.2f"),
        "pct_brancos": st.column_config.NumberColumn("Brancos (%)", format="%.2f"),
        "pct_nulos": st.column_config.NumberColumn("Nulos (%)", format="%.2f"),
        "lider": "Líder",
        "pct_lider": st.column_config.NumberColumn("% do líder", format="%.2f"),
        "margem_pp": st.column_config.NumberColumn("Margem (p.p.)", format="%.2f"),
        **{c: st.column_config.NumberColumn(f"% {nomes[int(c[4:])]}", format="%.2f") for c in pct_cols},
    })
    st.caption(f"{fmt_int(len(df))} município(s) exibido(s) de {fmt_int(len(res_mun))}. "
               "UF ZZ = votos no exterior (cidades fora do Brasil).")


def _comparacao_2022(res_uf: pd.DataFrame) -> None:
    st.markdown("### 2022 x 2026 (1º turno) por UF")
    t1 = _t1_2022()
    comp = d26.compare_2022_2026(res_uf, t1)
    if comp.empty:
        empty_state("Dados de 2022 indisponíveis",
                    "Os arquivos data/parquet/secoes.parquet e totais_cargo.parquet são necessários.")
        return
    metrica = st.segmented_control(
        "Indicador", ["Comparecimento", "Brancos", "Nulos"], default="Comparecimento",
        required=True, key="cmp2026_metrica",
    ) or "Comparecimento"
    m = metrica.lower()
    comp = comp.sort_values(f"{m}_var_pp")
    fig = go.Figure()
    fig.add_trace(go.Bar(x=comp["uf"].str.upper(), y=comp[f"{m}_pct_2022"], name="2022", marker_color=C_GREY))
    fig.add_trace(go.Bar(x=comp["uf"].str.upper(), y=comp[f"{m}_pct_2026"], name="2026", marker_color=C_BLUE))
    fig.update_layout(barmode="group", yaxis_title=f"{metrica} (%)", xaxis_title="UF")
    if m == "comparecimento":
        fig.update_yaxes(range=[max(0, comp[["comparecimento_pct_2022", "comparecimento_pct_2026"]].min().min() - 5), 100])
    nac_22 = pct(t1["comparecimento_2022"].sum(), t1["eleitorado_2022"].sum())
    nac_26 = pct(res_uf["comparecimento"].sum(), res_uf["eleitorado"].sum())
    show_chart(fig, height=400, caption=(
        f"{metrica} por UF, ordenado pela variação. Comparecimento nacional: {fmt_pct(nac_22)} em 2022 "
        f"e {fmt_pct(nac_26)} em 2026 ({fmt_pp(nac_26 - nac_22)}). "
        "2022 calculado a partir dos boletins de urna do 1º turno (Presidente)."
    ))
    with st.expander("Tabela comparativa"):
        tab = comp.copy()
        tab["uf"] = tab["uf"].str.upper()
        show_df(tab[["uf", "nome", "eleitorado_2022", "eleitorado", "eleitorado_var_pct",
                     "comparecimento_pct_2022", "comparecimento_pct_2026", "comparecimento_var_pp",
                     "brancos_pct_2022", "brancos_pct_2026", "brancos_var_pp",
                     "nulos_pct_2022", "nulos_pct_2026", "nulos_var_pp"]], hide_index=True,
                column_config={"eleitorado": st.column_config.NumberColumn("Eleitorado 2026", format="localized"),
                               "eleitorado_2022": st.column_config.NumberColumn("Eleitorado 2022", format="localized")})


def _auditoria_secoes(sig: tuple, res_uf: pd.DataFrame, cand: pd.DataFrame) -> None:
    st.markdown("### Auditoria por seção (boletins de urna)")
    dados = _secoes(sig)
    cov = d26.coverage_by_uf(dados.secoes, res_uf)
    total_pct = d26.overall_coverage(cov)
    ufs_completas = int(cov["completa"].sum()) if not cov.empty else 0

    st.markdown(
        f"**Cobertura da coleta:** {fmt_pct(total_pct)} das seções instaladas com boletim lido "
        f"({fmt_int(cov['com_bu'].sum() if not cov.empty else 0)} de "
        f"{fmt_int(cov['secoes_instaladas'].sum() if not cov.empty else 0)}); "
        f"{ufs_completas} de {len(cov)} UFs completas."
    )
    progress_bar(total_pct / 100, "Cobertura da coleta de boletins")
    if dados.ignorados:
        st.caption(f"{dados.ignorados} arquivo(s) em gravação foram ignorados nesta leitura.")

    if dados.vazio:
        empty_state(
            "Coleta dos boletins ainda não começou",
            "Quando scripts/ele2026/fetch_secoes.py gravar os primeiros lotes, esta seção mostra modelos de "
            "urna, horários, conferência com o resultado oficial e Lei de Benford.",
            image="empty-progress.svg",
        )
        return
    if total_pct < 100:
        st.info("Coleta em andamento: os números abaixo refletem apenas as seções já lidas e são "
                "atualizados a cada 5 minutos.")

    with st.expander("Cobertura por UF", expanded=False):
        tab = cov.copy()
        tab["uf"] = tab["uf"].str.upper()
        show_df(tab[["uf", "nome", "secoes_instaladas", "com_bu", "agregadas", "cobertura_pct", "completa"]],
                hide_index=True, column_config={
                    "secoes_instaladas": st.column_config.NumberColumn("Seções instaladas", format="localized"),
                    "com_bu": st.column_config.NumberColumn("Com BU", format="localized"),
                    "agregadas": st.column_config.NumberColumn("Agregadas", format="localized"),
                    "cobertura_pct": st.column_config.ProgressColumn("Cobertura", format="%.1f%%",
                                                                     min_value=0, max_value=100),
                    "completa": st.column_config.CheckboxColumn("Completa"),
                })

    secoes = dados.secoes[dados.secoes["status"] == "ok"]
    with safe_section("os modelos de urna"):
        _modelos(secoes)
    with safe_section("os horários de abertura e encerramento"):
        _horarios(secoes)
    with safe_section("a conferência com o resultado oficial"):
        _reconciliacao(dados, res_uf, cand)
    with safe_section("o teste de Benford"):
        _benford_2026(sig, cand)


def _modelos(secoes: pd.DataFrame) -> None:
    st.markdown("#### Modelos de urna")
    m = secoes["modelo_urna"].fillna("Não informado").value_counts().rename_axis("modelo").reset_index(name="secoes")
    m["pct"] = m["secoes"] / m["secoes"].sum() * 100
    tipos = secoes["tipo_urna"].fillna("Não informado").value_counts()
    c1, c2 = st.columns([3, 2])
    with c1:
        fig = go.Figure(go.Bar(x=m["modelo"], y=m["secoes"], marker_color=C_BLUE,
                               text=[fmt_pct(v, 1) for v in m["pct"]], textposition="auto"))
        fig.update_layout(xaxis_title="Modelo", yaxis_title="Seções", showlegend=False)
        show_chart(fig, height=320, caption="Distribuição das seções lidas por modelo de urna (campo do BU).")
    with c2:
        kpi_cards([
            {"label": "Urnas de seção", "value": fmt_int(tipos.get("secao", 0))},
            {"label": "Urnas de reserva", "value": fmt_int(tipos.get("reservaSecao", 0)), "tone": "amber"},
            {"label": "Contingência", "value": fmt_int(tipos.get("contingencia", 0)), "tone": "red",
             "help": "Votação manual ou em urna de contingência"},
        ])


def _horarios(secoes: pd.DataFrame) -> None:
    st.markdown("#### Horários de abertura e encerramento")
    ab = d26.parse_hora(secoes["hora_abertura"])
    en = d26.parse_hora(secoes["hora_encerramento"])
    df = pd.DataFrame({
        "Abertura": ab.dt.hour + ab.dt.minute / 60,
        "Encerramento": en.dt.hour + en.dt.minute / 60,
    }).melt(var_name="evento", value_name="hora").dropna()
    if df.empty:
        st.info("Sem horários nos boletins lidos.")
        return
    fig = px.histogram(df, x="hora", color="evento", nbins=60, barmode="overlay", opacity=0.75,
                       color_discrete_map={"Abertura": C_GREEN, "Encerramento": C_ORANGE},
                       labels={"hora": "Hora (registrada no BU)", "evento": "Evento"})
    fig.update_layout(yaxis_title="Seções")
    fig.update_xaxes(dtick=1)
    tardias = int(((ab.dt.hour >= 9)).sum())
    show_chart(fig, height=340, caption=(
        "Horários registrados no boletim (horário local da urna; fusos diferentes deslocam os picos). "
        f"Seções com abertura às 9h ou depois: {fmt_int(tardias)}."
    ))


def _reconciliacao(dados: d26.SecoesData, res_uf: pd.DataFrame, cand: pd.DataFrame) -> None:
    st.markdown("#### Soma dos boletins x resultado oficial por UF")
    rec = d26.reconcile_by_uf(dados.secoes, dados.votos, res_uf, cand)
    if rec.empty:
        st.info("Ainda não há UFs com boletins para conferir.")
        return
    resumo = d26.reconcile_summary(rec)
    ok = resumo[(resumo["situacao"] == "Confere")]
    div = resumo[(resumo["situacao"] == "Diverge")]
    kpi_cards([
        {"label": "UFs conferidas", "value": f"{len(ok)} de {int(resumo['completa'].sum())}",
         "help": "UFs completas sem nenhuma diferença", "tone": "green"},
        {"label": "UFs com divergência", "value": fmt_int(len(div)), "tone": "red" if len(div) else "green"},
        {"label": "UFs em coleta", "value": fmt_int(int((~resumo["completa"]).sum())), "tone": "grey"},
    ])
    tab = resumo.copy()
    tab["uf"] = tab["uf"].str.upper()

    def _cor(row):
        cor = {"Confere": "rgba(0,158,115,0.18)", "Diverge": "rgba(213,94,0,0.25)"}.get(row["situacao"], "")
        return [f"background-color: {cor}" if cor and c == "situacao" else "" for c in row.index]

    st.dataframe(
        tab[["uf", "situacao", "itens", "divergentes", "diferenca_abs"]].style.apply(_cor, axis=1),
        hide_index=True, width="stretch",
        column_config={"uf": "UF", "situacao": "Situação", "itens": "Itens conferidos",
                       "divergentes": "Itens divergentes",
                       "diferenca_abs": st.column_config.NumberColumn("Soma das diferenças", format="localized")},
    )
    st.caption("Confere = todos os itens (comparecimento, brancos, nulos, nulos técnicos, nominais e votos de cada "
               "candidato) batem exatamente com o TSE. Coleta parcial = diferença esperada até a UF terminar.")

    ufs = [u.upper() for u in rec["uf"].unique()]
    uf_det = st.selectbox("Detalhar UF", ufs, key="rec2026_uf")
    det = rec[rec["uf"] == uf_det.lower()].copy()
    nomes = dict(zip(cand["numero"].astype(int).astype(str), cand["rotulo"], strict=False))
    det["item"] = det["item"].map(lambda i: f"{i} ({nomes.get(i.split()[-1], '')})" if i.startswith("Candidato") else i)

    def _destaque(row):
        return ["color: #D55E00; font-weight: 700" if c == "diferenca" and row["diferenca"] != 0 else ""
                for c in row.index]

    st.dataframe(
        det[["item", "soma_bu", "oficial", "diferenca", "confere"]].style.apply(_destaque, axis=1),
        hide_index=True, width="stretch",
        column_config={"item": "Item", "soma_bu": st.column_config.NumberColumn("Soma dos BUs", format="localized"),
                       "oficial": st.column_config.NumberColumn("Oficial (TSE)", format="localized"),
                       "diferenca": st.column_config.NumberColumn("Diferença", format="localized"),
                       "confere": st.column_config.CheckboxColumn("Confere")},
    )


def _benford_2026(sig: tuple, cand: pd.DataFrame) -> None:
    st.markdown("#### Lei de Benford (1º dígito dos votos por seção)")
    numeros = tuple(int(n) for n in cand["numero"].head(2))
    bf = _benford(sig, numeros)
    if bf.empty:
        st.info("Seções insuficientes para o teste (mínimo de 50 por candidato).")
        return
    nomes = dict(zip(cand["numero"].astype(int), cand["rotulo"], strict=False))
    fig = go.Figure()
    for i, (numero, g) in enumerate(bf.groupby("numero")):
        fig.add_trace(go.Bar(x=g["digito"], y=g["observado_pct"], name=nomes.get(numero, str(numero)),
                             marker_color=candidate_color(numero, i)))
    esperado = bf.drop_duplicates("digito")
    fig.add_trace(go.Scatter(x=esperado["digito"], y=esperado["esperado_pct"], name="Benford (esperado)",
                             mode="lines+markers", line=dict(color=C_GREY, dash="dash")))
    fig.update_layout(barmode="group", xaxis_title="1º dígito", yaxis_title="Frequência (%)")
    fig.update_xaxes(dtick=1)
    show_chart(fig, height=360)
    stats_df = bf.drop_duplicates("numero")[["numero", "n", "chi2", "p_valor", "cramers_v"]].copy()
    stats_df["candidato"] = stats_df["numero"].map(nomes)
    stats_df["efeito"] = stats_df["cramers_v"].map(
        lambda v: "desprezível" if v < 0.05 else "pequeno" if v < 0.10 else "moderado" if v < 0.20 else "grande")
    show_df(stats_df[["candidato", "n", "chi2", "p_valor", "cramers_v", "efeito"]], hide_index=True,
            column_config={"n": st.column_config.NumberColumn("Seções", format="localized"),
                           "chi2": st.column_config.NumberColumn("Qui-quadrado", format="%.1f"),
                           "p_valor": st.column_config.NumberColumn("p-valor", format="%.4f"),
                           "cramers_v": st.column_config.NumberColumn("V de Cramér", format="%.3f"),
                           "efeito": "Tamanho do efeito"})
    st.caption(
        "Seções têm tamanho limitado (algumas centenas de eleitores), o que restringe a faixa de valores e "
        "afasta naturalmente o 1º dígito da Lei de Benford; desvios aqui não indicam fraude. "
        f"Com {fmt_int(stats_df['n'].max())} seções, o p-valor fica pequeno para qualquer desvio: o V de Cramér "
        f"mede o tamanho prático do efeito. Valores de referência: {fmt_num(0.05, 2)} (desprezível), "
        f"{fmt_num(0.10, 2)} (pequeno), {fmt_num(0.20, 2)} (moderado)."
    )
