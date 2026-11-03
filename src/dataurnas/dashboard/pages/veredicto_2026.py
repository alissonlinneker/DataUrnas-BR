"""Audit verdict for the 2026 presidential election (both rounds).

All texts and numbers come from ``data/parquet/2026/t2/veredicto_2026.json``
(summary of ``docs/veredicto-auditoria-2026.md``) and the national RDV recount
from ``rdv_nacional_resumo.json``; nothing is hard-coded here.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from dataurnas.dashboard import data2026 as d26
from dataurnas.dashboard.components.errors import safe_section
from dataurnas.dashboard.components.formatting import fmt_int
from dataurnas.dashboard.components.tables import show_df
from dataurnas.dashboard.components.ui import REPO_URL, empty_state, hero, kpi_cards


@st.cache_data(ttl=3600, show_spinner=False)
def _dados(sig: tuple) -> tuple[dict, dict]:
    """Verdict and RDV recount, cached by the signature of the 2nd round files."""
    return d26.load_veredicto(), d26.load_rdv_resumo()


def render() -> None:
    veredicto, rdv = _dados(d26.files_signature(d26.base_dir(2)))
    hero(
        "Veredicto da auditoria 2026",
        "Conclusão da auditoria independente dos arquivos públicos das urnas e da totalização da eleição "
        "presidencial de 2026, nos dois turnos: o que foi verificado, o resultado de cada verificação, o que "
        "os dados públicos não permitem verificar e as pendências para o TSE.",
        eyebrow=f"Atualizado em {veredicto.get('data_referencia', '-')}",
    )
    if not veredicto:
        empty_state("Veredicto indisponível", "O arquivo data/parquet/2026/t2/veredicto_2026.json não foi encontrado.",
                    image="empty-database.svg")
        return

    with safe_section("o resumo do veredicto"):
        _resumo(veredicto)
    with safe_section("a recontagem pelo RDV"):
        _rdv(rdv)
    with safe_section("a tabela de verificações"):
        _verificacoes(veredicto)
    with safe_section("o que não pode ser verificado"):
        _nao_verificavel(veredicto)
    with safe_section("as pendências"):
        _pendencias(veredicto)


def _resumo(v: dict) -> None:
    texto = v["veredicto"]
    st.markdown("### Veredicto")
    st.success(f"**{texto['conclusao']}**\n\n{texto['detalhe']}")
    st.info(f"**Limite da auditoria.** {texto['limite']}")
    st.markdown(texto["pendencias"])

    ind, res = v.get("indicadores", {}), v.get("resultado_oficial_2t", {})
    cand = res.get("candidatos", [])
    kpi_cards([
        *[{"label": f"{c['nome']} ({c['numero']})", "value": fmt_int(c["votos"]), "help": "Resultado oficial do 2º turno"}
          for c in cand],
        {"label": "Margem", "value": fmt_int(res.get("margem")), "tone": "grey",
         "help": f"Brancos {fmt_int(res.get('brancos'))}; nulos {fmt_int(res.get('nulos'))}"},
        {"label": "Verificações", "value": fmt_int(ind.get("verificacoes")), "tone": "green",
         "help": f"{fmt_int(ind.get('bus_checados_dois_turnos'))} BUs dos dois turnos"},
        {"label": "Assinaturas inválidas", "value": fmt_int(ind.get("assinaturas_invalidas_2t")), "tone": "green",
         "help": f"de {fmt_int(ind.get('assinaturas_verificadas_2t'))} verificadas no 2º turno"},
        {"label": "Divergências RDV x BU", "value": fmt_int(ind.get("rdv_divergencias")), "tone": "green",
         "help": f"{fmt_int(ind.get('rdv_secoes_recontadas_2t'))} seções recontadas no 2º turno"},
        {"label": "Pendências para o TSE", "value": fmt_int(ind.get("pendencias")), "tone": "amber",
         "help": "Nenhuma altera a contagem"},
    ])


def _rdv(rdv: dict) -> None:
    st.markdown("### Recontagem nacional do 2º turno pelo RDV")
    tab = d26.rdv_totais_df(rdv)
    if tab.empty:
        st.info("Resumo da recontagem pelo RDV indisponível.")
        return
    st.markdown(
        f"O registro digital do voto foi lido em {fmt_int(rdv.get('com_rdv'))} de {fmt_int(rdv.get('secoes'))} seções "
        f"(as demais, no exterior, não tiveram votos): {fmt_int(rdv.get('presidente_confere'))} conferem com o BU e "
        f"{fmt_int(rdv.get('presidente_diverge'))} divergem. Hash do RDV válido em {fmt_int(rdv.get('hash_rdv_confere'))} "
        f"seções e assinatura do pacote válida em {fmt_int(rdv.get('vsc_assinatura_valida'))}."
    )
    show_df(tab, hide_index=True, column_config={
        "item": "Item",
        "rdv": st.column_config.NumberColumn("Soma do RDV", format="localized"),
        "bu": st.column_config.NumberColumn("Soma dos BUs", format="localized"),
        "diferenca": st.column_config.NumberColumn("Diferença", format="localized"),
        "confere": st.column_config.CheckboxColumn("Confere"),
    })


def _verificacoes(v: dict) -> None:
    st.markdown("### O que foi verificado e o resultado")
    df = d26.verificacoes_df(v)
    df["link"] = REPO_URL + "/blob/main/" + df["documento"]
    show_df(df[["n", "verificacao", "escopo", "resultado", "situacao_label", "link"]], hide_index=True, column_config={
        "n": st.column_config.NumberColumn("#", format="%d"),
        "verificacao": st.column_config.TextColumn("Verificação", width="large"),
        "escopo": st.column_config.TextColumn("Escopo", width="medium"),
        "resultado": st.column_config.TextColumn("Resultado", width="large"),
        "situacao_label": "Situação",
        "link": st.column_config.LinkColumn("Documento", display_text=r"docs/(.*)\.md"),
    })
    st.caption("Cada linha remete ao documento com o método, as consultas e os números completos. "
               "\"Contagem confere; pendência de registro\" indica que os votos conferem, mas há ponto de registro "
               "listado nas pendências.")


def _nao_verificavel(v: dict) -> None:
    st.markdown("### O que não pode ser verificado com dados públicos")
    for i, item in enumerate(v.get("nao_verificavel", []), start=1):
        st.markdown(f"{i}. **{item['titulo']}.** {item['descricao']}")


def _pendencias(v: dict) -> None:
    st.markdown("### Pendências para esclarecimento do TSE")
    st.caption(v.get("pendencias_nota", ""))
    show_df(pd.DataFrame(v.get("pendencias", [])), hide_index=True, column_config={
        "n": st.column_config.NumberColumn("#", format="%d"),
        "descricao": st.column_config.TextColumn("Pendência", width="large"),
    })
