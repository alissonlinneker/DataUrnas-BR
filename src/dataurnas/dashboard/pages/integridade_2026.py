"""Eleições 2026: integridade dos arquivos de urna (hashes e assinatura digital).

Mostra o resultado da conferência dos arquivos publicados pelo TSE contra o
arquivo de assinatura de cada urna. A coleta roda por horas: a página funciona
com cobertura parcial ou sem nenhum dado e é reavaliada a cada 5 minutos.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from dataurnas.dashboard import data2026 as d26
from dataurnas.dashboard import integridade2026 as ig
from dataurnas.dashboard.components.charts import C_BLUE, C_GREEN, C_VERMILLION, SEQ_SCALE, show_chart
from dataurnas.dashboard.components.errors import safe_section
from dataurnas.dashboard.components.formatting import fmt_int, fmt_pct, pct
from dataurnas.dashboard.components.geo import FONTE_GEOJSON, brazil_geojson
from dataurnas.dashboard.components.tables import show_df
from dataurnas.dashboard.components.ui import empty_state, grupos_resumo, header, kpi_cards, progress_bar
from dataurnas.dashboard.reference import (
    GRUPO_ADULTERACAO,
    GRUPO_INVESTIGAR,
    INTEGRIDADE_CATEGORIAS,
    ISSUE_DESCRICOES,
    contar_por_grupo,
    grupo_label,
    grupo_nome,
)

TTL_COLETA = 300

EXPLICACAO = (
    "Ao encerrar a votação, cada urna grava o Boletim de Urna (BU), o Registro Digital do Voto (RDV) e o "
    "log, e gera um arquivo de assinatura (`.vsc`) que contém o resumo **SHA-512** desses três arquivos, "
    "assinado com a chave da própria urna. O TSE publica todos eles. Aqui o SHA-512 é recalculado a partir "
    "dos arquivos publicados e comparado ao valor assinado, e a assinatura do `.vsc` é verificada com o "
    "certificado da urna."
)
DETALHES = """
- **Hash confere:** o arquivo publicado tem exatamente o conteúdo que a urna resumiu e assinou.
- **Assinatura válida:** o arquivo `.vsc` (com os hashes dentro) foi assinado pela chave correspondente ao
  certificado que o acompanha e não foi alterado depois.
- **O que isso não mostra:** que o software da urna é íntegro, que o certificado pertence a uma urna
  específica do TSE além do que os campos dele declaram, nem que os votos registrados correspondem à
  intenção dos eleitores. Mostra apenas a correspondência entre o que foi publicado e o que a urna assinou.
- **MD5 e SHA-256** são catalogados para facilitar conferências futuras com outras fontes. A urna não usa
  MD5; eles não fazem parte do mecanismo oficial.
- **Token do TSE** (`aux.json`): valor de 32 bytes em base64url que não é o hash de nenhum arquivo isolado.
  É registrado no catálogo, mas não é comparado.
- Arquivos que a assinatura não cobre (imagem do BU, o próprio `.vsc` e outros) aparecem como
  "Não coberto pela assinatura", o que é esperado.
"""


# ----------------------------------------------------------------------
# Cache
# ----------------------------------------------------------------------
@st.cache_resource(ttl=TTL_COLETA, max_entries=2, show_spinner="Lendo a auditoria de integridade...")
def _dados(sig: tuple) -> ig.IntegridadeData:
    return ig.load_secoes()


@st.cache_data(ttl=3600, show_spinner=False)
def _oficial(sig: tuple) -> tuple[pd.DataFrame, pd.DataFrame]:
    return d26.load_resultado_uf(), d26.load_resultado_municipio()


@st.cache_data(ttl=TTL_COLETA, show_spinner=False)
def _arquivos_secao(sig: tuple, uf: str, cd_mun: str, zona: str, secao: str) -> pd.DataFrame:
    return ig.arquivos_da_secao(uf, cd_mun, zona, secao)


@st.cache_data(ttl=TTL_COLETA, show_spinner=False)
def _contar(sig: tuple, uf: str, cd_mun: str | None, zona: str | None, divergentes: bool) -> int:
    return ig.contar_catalogo(uf, cd_mun, zona, divergentes)


@st.cache_data(ttl=TTL_COLETA, show_spinner=False)
def _contagens(sig: tuple, t_itens: tuple) -> dict[str, int]:
    return ig.contagens_2026(dict(t_itens))


@st.cache_data(ttl=TTL_COLETA, max_entries=4, show_spinner="Gerando o CSV...")
def _csv(sig: tuple, uf: str, cd_mun: str | None, zona: str | None, divergentes: bool) -> bytes:
    return ig.catalogo_csv(uf, cd_mun, zona, divergentes)


# ----------------------------------------------------------------------
# Página
# ----------------------------------------------------------------------
def render() -> None:
    sig = ig.files_signature()
    header("Integridade dos arquivos (2026)",
           "Hashes SHA-512 e assinatura digital de cada urna, conferidos a partir dos arquivos publicados",
           eyebrow="Eleições 2026")
    st.markdown(EXPLICACAO)
    with st.expander("O que a conferência mostra e o que não mostra"):
        st.markdown(DETALHES)

    res_uf, res_mun = _oficial(d26.files_signature())
    dados = _dados(sig)
    resumo = ig.load_resumo()

    if dados.vazio:
        empty_state(
            "Auditoria de integridade ainda não disponível",
            "Quando a coleta gravar os primeiros arquivos em data/parquet/2026/integridade, esta página mostra "
            "os hashes conferidos, as assinaturas e a consulta por seção.",
            image="empty-progress.svg",
        )
        return

    t = ig.totais(dados.secoes, res_uf)
    with safe_section("a cobertura da auditoria"):
        _cobertura(t, dados, resumo)
    with safe_section("os indicadores de integridade"):
        _kpis(t)
    with safe_section("a leitura por grupo"):
        secao_grupos(sig, t)
    with safe_section("o resumo por UF"):
        _por_uf(dados.secoes, res_uf)
    with safe_section("as divergências"):
        _divergencias(dados.secoes, t, res_mun)
    with safe_section("a consulta por seção"):
        _consulta(sig, dados.secoes, res_mun)
    with safe_section("a exportação do catálogo"):
        _exportar(sig, dados.secoes, res_mun)


def _cobertura(t: dict, dados: ig.IntegridadeData, resumo: dict) -> None:
    st.markdown(
        f"**Cobertura:** {fmt_pct(t['cobertura_pct'])} das seções instaladas verificadas "
        f"({fmt_int(t['verificadas'])} de {fmt_int(t['instaladas'])})."
    )
    progress_bar(t["cobertura_pct"] / 100, "Cobertura da auditoria de integridade")
    notas = []
    horarios = ig.texto_horarios(resumo)
    if horarios:
        notas.append(f"Coleta ({horarios}).")
    if dados.origem == "catalogo":
        notas.append("O resumo por seção ainda não foi gravado: contagens derivadas do catálogo de arquivos, "
                     "sem os dados de assinatura.")
    if dados.ignorados:
        notas.append(f"{dados.ignorados} arquivo(s) em gravação foram ignorados nesta leitura.")
    if notas:
        st.caption(" ".join(notas))
    if t["cobertura_pct"] < 100:
        st.info("Auditoria em andamento: os números refletem apenas as seções já verificadas e são "
                "atualizados a cada 5 minutos.")


def _kpis(t: dict) -> None:
    st.markdown("### Panorama")
    conferidos_pct = pct(t["hash_confere"], t["hash_confere"] + t["hash_diverge"])
    kpi_cards([
        {"label": "Seções verificadas", "value": fmt_int(t["verificadas"]),
         "help": f"{fmt_int(t['agregadas'])} agregadas, {fmt_int(t['nao_instaladas'])} não instaladas"},
        {"label": "Arquivos catalogados", "value": fmt_int(t["arquivos"]),
         "help": f"{fmt_int(t['sem_hash'])} fora da assinatura"},
        {"label": "Hashes conferidos", "value": fmt_int(t["hash_confere"]),
         "help": f"{fmt_pct(conferidos_pct)} dos comparados", "tone": "green"},
        {"label": "Divergências", "value": fmt_int(t["secoes_divergentes"]),
         "help": f"{fmt_int(t['hash_diverge'])} hash(es), {fmt_int(t['assinaturas_invalidas'])} assinatura(s)",
         "tone": "red" if t["secoes_divergentes"] else "green"},
        {"label": "Assinaturas válidas", "value": fmt_int(t["assinaturas_validas"]),
         "help": (f"{fmt_int(t['assinaturas_nao_verificadas'])} não verificadas"
                  if t["assinaturas_nao_verificadas"] else "das seções verificadas"),
         "tone": "green"},
        {"label": "Cobertura", "value": fmt_pct(t["cobertura_pct"], 1),
         "help": f"de {fmt_int(t['instaladas'])} seções instaladas", "tone": "grey"},
    ])


def secao_grupos(sig: tuple, t: dict, detalhe: bool = True) -> None:
    """Resumo em três grupos de leitura (integridade dos arquivos e auditoria por seção de 2026)."""
    st.markdown("### O que as ocorrências podem dizer sobre manipulação")
    cont = _contagens(sig, tuple(sorted(t.items())))
    grupos_resumo(contar_por_grupo(cont), unidade="registro(s)")
    st.caption(
        "Grupo 1: divergências de hash ou de assinatura e arquivos fora da assinatura. Grupo 2: votos do BU "
        "assinado que não conferem com a coleta de boletins e inconsistências como A03. Grupo 3: registros "
        "de operação (reinícios, horários, biometria) e indicadores estatísticos da auditoria por seção. "
        "Hashes divergentes contam arquivos; assinaturas e votos contam seções; códigos contam ocorrências. "
        "Números parciais enquanto a coleta roda."
    )
    if not detalhe:
        return
    linhas = [{"chave": k, "descricao": v[0], "grupo": grupo_nome(v[1]), "total": int(cont.get(k, 0))}
              for k, v in INTEGRIDADE_CATEGORIAS.items()]
    linhas += [{"chave": k, "descricao": ISSUE_DESCRICOES.get(k, ""), "grupo": grupo_label(k), "total": n}
               for k, n in sorted(cont.items()) if k not in INTEGRIDADE_CATEGORIAS and n]
    with st.expander("Detalhe por categoria de integridade e código de inconsistência"):
        show_df(pd.DataFrame(linhas).sort_values(["grupo", "chave"]), hide_index=True,
                column_config={"chave": "Categoria ou código", "descricao": "Descrição", "grupo": "Grupo",
                               "total": st.column_config.NumberColumn("Total", format="localized")})


def _por_uf(secoes: pd.DataFrame, res_uf: pd.DataFrame) -> None:
    st.markdown("### Por UF")
    tab = ig.por_uf(secoes, res_uf)
    if tab.empty:
        st.info("Ainda não há UFs verificadas.")
        return
    aba_mapa, aba_barras, aba_tabela = st.tabs(["Mapa", "Barras", "Tabela"])
    with aba_mapa:
        df = tab[tab["uf"] != d26.UF_EXTERIOR].copy()
        df["sigla"] = df["uf"].str.upper()
        fig = px.choropleth(
            df, geojson=brazil_geojson(), locations="sigla", featureidkey="properties.sigla",
            color="cobertura_pct", color_continuous_scale=SEQ_SCALE, range_color=(0, 100),
            hover_name="nome",
            hover_data={"sigla": False, "verificadas": ":,", "secoes_instaladas": ":,",
                        "secoes_divergentes": ":,", "cobertura_pct": ":.1f"},
            labels={"cobertura_pct": "Cobertura (%)", "verificadas": "Verificadas",
                    "secoes_instaladas": "Instaladas", "secoes_divergentes": "Seções com divergência"},
        )
        fig.update_geos(fitbounds="locations", visible=False)
        fig.update_layout(margin=dict(l=0, r=0, t=10, b=0))
        show_chart(fig, height=500, caption=f"Cobertura da verificação por UF. Exterior aparece na tabela e "
                                            f"nas barras. Malha: {FONTE_GEOJSON}.")
    with aba_barras:
        df = tab.sort_values("cobertura_pct")
        cores = [C_VERMILLION if d else (C_GREEN if c else C_BLUE)
                 for d, c in zip(df["secoes_divergentes"], df["completa"], strict=False)]
        fig = go.Figure(go.Bar(
            x=df["cobertura_pct"], y=df["uf"].str.upper(), orientation="h", marker_color=cores,
            text=[fmt_pct(v, 1) for v in df["cobertura_pct"]], textposition="auto",
            customdata=df[["verificadas", "secoes_instaladas", "secoes_divergentes"]].to_numpy(),
            hovertemplate="%{y}: %{x:.1f}%<br>%{customdata[0]:,} de %{customdata[1]:,} seções"
                          "<br>Divergências: %{customdata[2]}<extra></extra>",
        ))
        fig.update_layout(xaxis_title="Cobertura (%)", yaxis_title="", showlegend=False)
        fig.update_xaxes(range=[0, 100])
        show_chart(fig, height=640, caption="Verde: UF completa; azul: em andamento; vermelho: UF com ao menos "
                                            "uma seção divergente.")
    with aba_tabela:
        out = tab.copy()
        out["uf"] = out["uf"].str.upper()
        show_df(out, hide_index=True, column_config={
            "nome": "Nome",
            "secoes_instaladas": st.column_config.NumberColumn("Instaladas", format="localized"),
            "verificadas": st.column_config.NumberColumn("Verificadas", format="localized"),
            "agregadas": st.column_config.NumberColumn("Agregadas", format="localized"),
            "nao_instaladas": st.column_config.NumberColumn("Não instaladas", format="localized"),
            "sem_arquivos": st.column_config.NumberColumn("Sem arquivos", format="localized"),
            "arquivos": st.column_config.NumberColumn("Arquivos", format="localized"),
            "hash_confere": st.column_config.NumberColumn("Hashes conferem", format="localized"),
            "hash_diverge": st.column_config.NumberColumn("Hashes divergem", format="localized"),
            "sem_hash": st.column_config.NumberColumn("Fora da assinatura", format="localized"),
            "assinaturas_validas": st.column_config.NumberColumn("Assinaturas válidas", format="localized"),
            "assinaturas_invalidas": st.column_config.NumberColumn("Assinaturas inválidas", format="localized"),
            "secoes_divergentes": st.column_config.NumberColumn("Seções divergentes", format="localized"),
            "cobertura_pct": st.column_config.ProgressColumn("Cobertura", format="%.1f%%", min_value=0,
                                                             max_value=100),
            "completa": st.column_config.CheckboxColumn("Completa"),
        })


def _nomes_municipios(res_mun: pd.DataFrame) -> dict[tuple[str, str], str]:
    if res_mun.empty:
        return {}
    return {(u, m): str(n).title() for u, m, n in zip(res_mun["uf"], res_mun["cd_mun"], res_mun["nome"],
                                                      strict=False)}


def _divergencias(secoes: pd.DataFrame, t: dict, res_mun: pd.DataFrame) -> None:
    st.markdown("### Divergências")
    div = ig.divergencias(secoes)
    if div.empty:
        empty_state(
            f"Nenhuma divergência encontrada nas {fmt_int(t['verificadas'])} seções verificadas",
            "Em todas elas o SHA-512 recalculado dos arquivos publicados é igual ao valor assinado pela urna"
            + (" e a assinatura é válida." if t["assinaturas_invalidas"] == 0 and t["assinaturas_validas"] else ".")
            + (" A verificação continua nas seções restantes." if t["cobertura_pct"] < 100 else ""),
            image="empty-ok.svg",
        )
        return
    nomes = _nomes_municipios(res_mun)
    tab = div.copy()
    tab["municipio"] = [nomes.get((u, m), m) for u, m in zip(tab["uf"], tab["cd_mun"], strict=False)]
    tab["uf"] = tab["uf"].str.upper()
    adulteracao = (tab["n_hash_diverge"] > 0) | tab["assinatura_valida"].eq(False).fillna(False)
    tab["grupo"] = [grupo_nome(GRUPO_ADULTERACAO) if a else grupo_nome(GRUPO_INVESTIGAR) for a in adulteracao]
    st.warning(f"{fmt_int(len(tab))} seção(ões) com divergência entre {fmt_int(t['verificadas'])} verificadas. "
               "Use a consulta por seção abaixo para ver os arquivos e os hashes envolvidos.")
    grupos_presentes = sorted(set(tab["grupo"]))
    if len(grupos_presentes) > 1:
        escolhidos = st.multiselect("Grupo de leitura", grupos_presentes, default=grupos_presentes,
                                    key="integ_div_grupos")
        tab = tab[tab["grupo"].isin(escolhidos)]
    show_df(tab[["uf", "municipio", "cd_mun", "zona", "secao", "grupo", "problemas", "modelo_urna", "motivo"]],
            hide_index=True, column_config={"cd_mun": "Cód. município", "grupo": "Grupo",
                                            "problemas": "Problemas", "motivo": "Observação"})


def _consulta(sig: tuple, secoes: pd.DataFrame, res_mun: pd.DataFrame) -> None:
    st.markdown("### Consultar uma seção")
    st.caption("Escolha UF, município, zona e seção para ver cada arquivo com MD5, SHA-256 e SHA-512 "
               "(calculado e assinado), a situação da assinatura e o certificado da urna.")
    nomes = _nomes_municipios(res_mun)
    c1, c2, c3, c4 = st.columns([1, 2, 1, 1])
    ufs = sorted(secoes["uf"].unique())
    uf = c1.selectbox("UF", ufs, index=None, placeholder="UF", format_func=str.upper, key="integ_uf")
    if not uf:
        return
    s_uf = secoes[secoes["uf"] == uf]
    muns = sorted(s_uf["cd_mun"].unique(), key=lambda m: nomes.get((uf, m), m))
    mun = c2.selectbox("Município", muns, index=None, placeholder="Digite para buscar",
                       format_func=lambda m: f"{nomes.get((uf, m), 'Município')} ({m})", key="integ_mun")
    if not mun:
        return
    s_mun = s_uf[s_uf["cd_mun"] == mun]
    zona = c3.selectbox("Zona", sorted(s_mun["zona"].unique()), index=None, placeholder="Zona", key="integ_zona")
    if not zona:
        return
    s_zona = s_mun[s_mun["zona"] == zona]
    secao = c4.selectbox("Seção", sorted(s_zona["secao"].unique()), index=None, placeholder="Seção",
                         key="integ_secao")
    if not secao:
        return
    linha = s_zona[s_zona["secao"] == secao].iloc[0]
    _detalhe_secao(sig, linha, nomes.get((uf, mun), mun))


def _txt(valor) -> str | None:
    return None if valor is None or pd.isna(valor) or valor == "" else str(valor)


def _sim_nao(valor, sim: str = "Válida", nao: str = "Inválida", nulo: str = "Não verificada") -> str:
    if valor is None or pd.isna(valor):
        return nulo
    return sim if bool(valor) else nao


def _detalhe_secao(sig: tuple, linha: pd.Series, municipio: str) -> None:
    uf, mun, zona, secao = (str(linha[c]) for c in d26.CHAVE_SECAO)
    st.markdown(f"#### {municipio} ({uf.upper()}), zona {zona}, seção {secao}")
    status = str(linha.get("status_secao") or "ok")
    assinatura = _sim_nao(linha.get("assinatura_valida"))
    kpi_cards([
        {"label": "Situação", "value": {"ok": "Verificada", "agregada": "Agregada",
                                        "nao_instalada": "Não instalada",
                                        "sem_arquivos": "Sem arquivos"}.get(status, status),
         "tone": "green" if status == "ok" else "grey", "help": _txt(linha.get("motivo"))},
        {"label": "Hashes", "value": f"{fmt_int(linha['n_hash_confere'])} conferem",
         "help": f"{fmt_int(linha['n_hash_diverge'])} divergem, {fmt_int(linha['n_sem_hash'])} fora da assinatura",
         "tone": "red" if linha["n_hash_diverge"] else "green"},
        {"label": "Assinatura", "value": assinatura, "help": _txt(linha.get("assinatura_algoritmo")),
         "tone": {"Válida": "green", "Inválida": "red"}.get(assinatura, "grey")},
        {"label": "Votos x BU", "value": _sim_nao(linha.get("votos_conferem"), "Conferem", "Não conferem",
                                                  "Não comparado"),
         "help": _txt(linha.get("modelo_urna"))},
    ])
    if status != "ok":
        st.info("Seção sem arquivos próprios para conferir (agregada a outra, não instalada ou sem publicação).")

    arquivos = _com_catalogo(uf, lambda: _arquivos_secao(sig, uf, mun, zona, secao))
    if arquivos is not None and arquivos.empty:
        st.info("Nenhum arquivo catalogado para esta seção.")
    elif arquivos is not None:
        tab = arquivos.copy()
        for c in ("md5", "sha256", "sha512", "sha512_assinado"):
            tab[f"{c}_curto"] = tab[c].map(ig.mascarar_hash)
        show_df(tab[["tipo", "nome", "tamanho", "situacao_hash", "sha512_curto", "sha512_assinado_curto",
                     "sha256_curto", "md5_curto"]], hide_index=True, column_config={
            "tipo": "Tipo", "nome": "Arquivo",
            "tamanho": st.column_config.NumberColumn("Bytes", format="localized"),
            "situacao_hash": "SHA-512", "sha512_curto": "SHA-512 calculado",
            "sha512_assinado_curto": "SHA-512 assinado", "sha256_curto": "SHA-256", "md5_curto": "MD5",
        })
        with st.expander("Hashes completos (para copiar)"):
            for _, a in arquivos.iterrows():
                st.markdown(f"**{a['nome']}** ({a['tipo']}): {a['situacao_hash']}")
                linhas = [f"SHA-512 calculado: {a['sha512'] or '-'}",
                          f"SHA-512 assinado:  {a['sha512_assinado'] if pd.notna(a['sha512_assinado']) else '-'}",
                          f"SHA-256:           {a['sha256'] or '-'}",
                          f"MD5:               {a['md5'] or '-'}"]
                if pd.notna(a.get("token_tse")):
                    linhas.append(f"Token TSE:         {a['token_tse']} ({a.get('data_hora_tse') or '-'})")
                st.code("\n".join(linhas), language=None, wrap_lines=True)

    with st.expander("Certificado da urna"):
        cert = pd.DataFrame({
            "Campo": ["Algoritmo", "Titular (subject)", "Emissor (issuer)", "Número de série", "SHA-256 do certificado",
                      "Modelo da urna"],
            "Valor": [str(linha.get(c)) if pd.notna(linha.get(c)) else "-"
                      for c in ("assinatura_algoritmo", "cert_subject", "cert_issuer", "cert_serial", "cert_sha256",
                                "modelo_urna")],
        })
        st.dataframe(cert, hide_index=True, width="stretch")


def _com_catalogo(uf: str, ler):
    """Executa ``ler``; se o catálogo da UF vier da internet, avisa e trata a falha sem quebrar a página."""
    if ig.catalogo_local(uf):
        return ler()
    mb = ig.tamanho_remoto(uf) / (1 << 20)
    try:
        with st.spinner(f"Obtendo o catálogo de hashes de {uf.upper()} ({fmt_num_mb(mb)})..."):
            return ler()
    except ig.CatalogoIndisponivel as exc:
        st.warning(str(exc))
        return None


def fmt_num_mb(mb: float) -> str:
    return f"{mb:.1f} MB".replace(".", ",") if mb else "tamanho desconhecido"


def _exportar(sig: tuple, secoes: pd.DataFrame, res_mun: pd.DataFrame) -> None:
    st.markdown("### Baixar o catálogo")
    st.caption("CSV com um registro por arquivo (UTF-8, separador ponto e vírgula): MD5, SHA-256, SHA-512 calculado, "
               "SHA-512 assinado, resultado da comparação e token do TSE.")
    nomes = _nomes_municipios(res_mun)
    c1, c2, c3 = st.columns([1, 2, 1])
    uf = c1.selectbox("UF", sorted(secoes["uf"].unique()), format_func=str.upper, key="integ_csv_uf")
    muns = sorted(secoes.loc[secoes["uf"] == uf, "cd_mun"].unique(), key=lambda m: nomes.get((uf, m), m))
    mun = c2.selectbox("Município (opcional)", muns, index=None, placeholder="Todos",
                       format_func=lambda m: f"{nomes.get((uf, m), 'Município')} ({m})", key="integ_csv_mun")
    divergentes = c3.toggle("Só divergentes", key="integ_csv_div")
    # Sem o catálogo local, a contagem sai do resumo por seção: o download só acontece ao preparar o CSV
    if ig.catalogo_local(uf):
        n = _contar(sig, uf, mun, None, divergentes)
    else:
        n = ig.contar_pelas_secoes(secoes, uf, mun, divergentes)
    if n == 0:
        st.info("Nenhum arquivo catalogado com esse filtro.")
        return
    if n > ig.LIMITE_CSV:
        st.info(f"O filtro seleciona {fmt_int(n)} arquivos, acima do limite de {fmt_int(ig.LIMITE_CSV)} por download. "
                "Escolha um município. O catálogo completo de cada UF (Parquet) está nos anexos da versão "
                f"[{ig.CATALOGO_VERSAO}]({ig.CATALOGO_PAGINA}) do projeto, conferível pelo SHA256SUMS.")
        return
    chave = ("integ_csv_pronto", uf, mun, divergentes)
    if st.session_state.get("integ_csv_chave") != chave:
        if not st.button(f"Preparar CSV ({fmt_int(n)} arquivos)", key="integ_csv_preparar"):
            return
        st.session_state["integ_csv_chave"] = chave
    nome = "_".join(p for p in ("integridade_2026", uf, mun, "divergentes" if divergentes else None) if p)
    dados = _com_catalogo(uf, lambda: _csv(sig, uf, mun, None, divergentes))
    if dados is None:
        st.session_state.pop("integ_csv_chave", None)
        return
    st.download_button("Baixar CSV", dados, file_name=f"{nome}.csv",
                       mime="text/csv", icon=":material/download:", key="integ_csv_baixar")
