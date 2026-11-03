"""2026 elections: President, 2nd round (dashboard home page).

Official TSE result by country, state and municipality, the change from the
1st round per state and the exact check of the sum of the 499,207 ballot box
reports (BU) against the official result. Display, cache and widget helpers
are shared with the 1st round page (``eleicoes_2026``).
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dataurnas.dashboard import data2026 as d26
from dataurnas.dashboard.components.charts import C_BLUE, C_GREY, candidate_color, show_chart
from dataurnas.dashboard.components.errors import safe_section
from dataurnas.dashboard.components.formatting import fmt_int, fmt_pct, fmt_pp, pct
from dataurnas.dashboard.components.tables import show_df
from dataurnas.dashboard.components.ui import empty_state, hero, kpi_cards
from dataurnas.dashboard.pages import eleicoes_2026 as t1

TURNO = 2
KEY = "2026t2"


@st.cache_data(ttl=3600, show_spinner=False)
def _conferencia_bus(sig: tuple) -> pd.DataFrame:
    """Per-state BU sums of the 2nd round checked against the official result (cached by file signature)."""
    base = d26.base_dir(TURNO)
    soma = d26.soma_bus_por_uf(base / "secoes_t2.parquet")
    return d26.reconcile_bus_t2(soma, d26.load_resultado_uf(base))


def render() -> None:
    sig = d26.files_signature(d26.base_dir(TURNO))
    resumo, cand, res_uf, res_mun = t1._oficial(sig, TURNO)

    hero(
        "Eleições 2026: Presidente, 2º turno",
        "Resultado oficial do TSE por país, estado e município, variação em relação ao 1º turno e "
        "conferência da soma dos boletins de urna de todas as seções com o resultado divulgado.",
        eyebrow=f"Eleição de {resumo.get('data_eleicao', '25/10/2026')}",
    )

    if not resumo or cand.empty:
        empty_state(
            "Resultado do 2º turno ainda não disponível",
            "Os arquivos do 2º turno devem estar em data/parquet/2026/t2.",
            image="empty-database.svg",
        )
        return

    st.caption(
        f"Fonte: TSE (resultados.tse.jus.br), totalização de {resumo.get('totais', {}).get('data_totalizacao', '-')} "
        f"às {resumo.get('totais', {}).get('hora_totalizacao', '-')}; arquivo gerado em {resumo.get('data_geracao_tse', '-')}."
    )

    with safe_section("os indicadores nacionais"):
        t1._kpis(resumo)
    with safe_section("o resultado do 2º turno"):
        _confronto(cand)
    with safe_section("o mapa por UF"):
        t1._mapa(res_uf, cand, key=KEY)
    with safe_section("a comparação com o 1º turno"):
        _comparacao_t1(res_uf, cand)
    with safe_section("a tabela de municípios"):
        t1._municipios(res_mun, cand, key=KEY)
    with safe_section("a conferência dos boletins de urna"):
        _conferencia(sig)


def _confronto(cand: pd.DataFrame) -> None:
    """Head-to-head result: one stacked bar split at 50% plus the vote margin."""
    st.markdown("### Resultado")
    a, b = cand.iloc[0], cand.iloc[1]
    margem = int(a["votos"]) - int(b["votos"])
    kpi_cards([
        {"label": f"{a['rotulo']} ({a['situacao']})", "value": fmt_int(a["votos"]),
         "help": f"{fmt_pct(a['pct_validos'])} dos válidos"},
        {"label": f"{b['rotulo']} ({b['situacao']})", "value": fmt_int(b["votos"]),
         "help": f"{fmt_pct(b['pct_validos'])} dos válidos"},
        {"label": "Diferença", "value": fmt_int(margem),
         "help": f"{fmt_pp(a['pct_validos'] - b['pct_validos'])} dos válidos", "tone": "grey"},
    ])
    fig = go.Figure()
    for i, (_, c) in enumerate(cand.head(2).iterrows()):
        fig.add_trace(go.Bar(
            x=[c["pct_validos"]], y=["Votos válidos"], orientation="h", name=c["rotulo"],
            marker_color=candidate_color(c["numero"], i),
            text=f"{c['nome_exibicao']}: {fmt_pct(c['pct_validos'])}", textposition="inside",
            hovertemplate=f"{c['rotulo']}<br>%{{x:.2f}}% dos válidos<extra></extra>",
        ))
    fig.add_vline(x=50, line_dash="dash", line_color=C_GREY)
    fig.update_layout(barmode="stack", xaxis=dict(range=[0, 100], title="% dos votos válidos"), yaxis_title="")
    show_chart(fig, height=200, caption="Linha tracejada: 50% dos votos válidos.")


def _comparacao_t1(res_uf: pd.DataFrame, cand: pd.DataFrame) -> None:
    """Per-state change between rounds: share of the first-placed candidate and turnout."""
    st.markdown("### 1º x 2º turno por UF")
    _, _, res_uf_t1, _ = t1._oficial(t1._signature(), 1)
    numeros = [int(n) for n in cand["numero"].head(2)]
    comp = d26.compare_turnos_by_uf(res_uf_t1, res_uf, numeros)
    if comp.empty:
        empty_state("Resultado do 1º turno indisponível", "O arquivo data/parquet/2026/resultado_uf.parquet é necessário.")
        return
    nomes = dict(zip(cand["numero"].astype(int), cand["nome_exibicao"], strict=False))
    n = numeros[0]
    opcoes = {f"Fatia de {nomes[n]} (% dos válidos)": f"pct_{n}", "Comparecimento (%)": "comparecimento_pct"}
    escolha = st.segmented_control("Indicador", list(opcoes), default=list(opcoes)[0], required=True,
                                   key=f"cmp{KEY}_metrica") or list(opcoes)[0]
    col = opcoes[escolha]
    var = "comparecimento_var_pp" if col == "comparecimento_pct" else f"pct_{n}_var_pp"
    comp = comp.sort_values(var)
    fig = go.Figure()
    fig.add_trace(go.Bar(x=comp["uf"].str.upper(), y=comp[f"{col}_t1"], name="1º turno", marker_color=C_GREY))
    fig.add_trace(go.Bar(x=comp["uf"].str.upper(), y=comp[f"{col}_t2"], name="2º turno",
                         marker_color=candidate_color(n) if col != "comparecimento_pct" else C_BLUE))
    fig.update_layout(barmode="group", yaxis_title=escolha, xaxis_title="UF")
    if col == "comparecimento_pct":
        fig.update_yaxes(range=[max(0, comp[[f"{col}_t1", f"{col}_t2"]].min().min() - 5), 100])
    comp_t1 = pct(res_uf_t1["comparecimento"].sum(), res_uf_t1["eleitorado"].sum())
    comp_t2 = pct(res_uf["comparecimento"].sum(), res_uf["eleitorado"].sum())
    show_chart(fig, height=400, caption=(
        f"{escolha} por UF nos dois turnos, ordenado pela variação. No 1º turno a fatia é calculada sobre os "
        "válidos de todos os candidatos. Comparecimento nacional: "
        f"{fmt_pct(comp_t1)} no 1º turno e {fmt_pct(comp_t2)} no 2º ({fmt_pp(comp_t2 - comp_t1)})."
    ))
    with st.expander("Tabela comparativa"):
        tab = comp.sort_values("uf").copy()
        tab["uf"] = tab["uf"].str.upper()
        cols = ["uf", "nome", "comparecimento_pct_t1", "comparecimento_pct_t2", "comparecimento_var_pp"]
        cfg = {
            "nome": "Estado",
            "comparecimento_pct_t1": st.column_config.NumberColumn("Comparecimento 1º turno (%)", format="%.2f"),
            "comparecimento_pct_t2": st.column_config.NumberColumn("Comparecimento 2º turno (%)", format="%.2f"),
            "comparecimento_var_pp": st.column_config.NumberColumn("Variação (p.p.)", format="%.2f"),
        }
        for num in numeros:
            cols += [f"pct_{num}_t1", f"pct_{num}_t2", f"pct_{num}_var_pp"]
            cfg[f"pct_{num}_t1"] = st.column_config.NumberColumn(f"% {nomes[num]} 1º turno", format="%.2f")
            cfg[f"pct_{num}_t2"] = st.column_config.NumberColumn(f"% {nomes[num]} 2º turno", format="%.2f")
            cfg[f"pct_{num}_var_pp"] = st.column_config.NumberColumn(f"Variação {nomes[num]} (p.p.)", format="%.2f")
        show_df(tab[cols], hide_index=True, column_config=cfg)


def _conferencia(sig: tuple) -> None:
    """BU sum x official result per state, from the per-section 2nd round file."""
    st.markdown("### Soma dos boletins de urna x resultado oficial")
    rec = _conferencia_bus(sig)
    if rec.empty:
        empty_state("Boletins do 2º turno indisponíveis", "O arquivo data/parquet/2026/t2/secoes_t2.parquet não foi encontrado.")
        return
    por_uf = rec.groupby("uf")["confere"].all()
    secoes = int(rec.loc[rec["item"] == "Seções com BU", "soma_bu"].sum())
    divergentes = int((~rec["confere"]).sum())
    kpi_cards([
        {"label": "Boletins somados", "value": fmt_int(secoes), "help": "Uma linha por seção instalada"},
        {"label": "UFs que conferem", "value": f"{int(por_uf.sum())} de {len(por_uf)}",
         "help": "Todos os itens iguais ao TSE", "tone": "green" if por_uf.all() else "red"},
        {"label": "Itens divergentes", "value": fmt_int(divergentes), "tone": "green" if divergentes == 0 else "red"},
    ])
    nac = rec.groupby("item", sort=False)[["soma_bu", "oficial", "diferenca"]].sum().reset_index()
    nac["confere"] = nac["diferenca"] == 0
    show_df(nac, hide_index=True, column_config={
        "item": "Item",
        "soma_bu": st.column_config.NumberColumn("Soma dos BUs", format="localized"),
        "oficial": st.column_config.NumberColumn("Oficial (TSE)", format="localized"),
        "diferenca": st.column_config.NumberColumn("Diferença", format="localized"),
        "confere": st.column_config.CheckboxColumn("Confere"),
    })
    with st.expander("Conferência por UF"):
        tab = rec.copy()
        tab["uf"] = tab["uf"].str.upper()
        show_df(tab, hide_index=True, column_config={
            "item": "Item", "confere": st.column_config.CheckboxColumn("Confere"),
            "soma_bu": st.column_config.NumberColumn("Soma dos BUs", format="localized"),
            "oficial": st.column_config.NumberColumn("Oficial (TSE)", format="localized"),
            "diferenca": st.column_config.NumberColumn("Diferença", format="localized"),
        })
    st.caption("Soma de comparecimento, votos de cada candidato, brancos e nulos dos boletins assinados pelas urnas, "
               "por UF, comparada com os totais divulgados pelo TSE. A recontagem voto a voto pelo RDV está na "
               "página Veredicto da auditoria 2026.")
