"""Identidade visual: CSS global, cabeçalho, rodapé, cartões e estados vazios.

As cores de destaque têm contraste suficiente nos temas claro e escuro; os
fundos usam transparência sobre a cor do tema para não fixar claro/escuro.
"""

from __future__ import annotations

import base64
import html
from functools import lru_cache
from pathlib import Path

import streamlit as st

ASSETS = Path(__file__).resolve().parent.parent / "assets"

LICENCA = "MIT"
REPO_URL = "https://github.com/alissonlinneker/DataUrnas-BR"

CSS = """
<style>
:root {
  --du-blue: #0072B2;
  --du-navy: #0B3A5B;
  --du-green: #009E73;
  --du-amber: #E69F00;
  --du-red: #D55E00;
  --du-border: rgba(128, 128, 128, 0.28);
  --du-surface: rgba(128, 128, 128, 0.07);
}
.block-container { padding-top: 2.2rem; padding-bottom: 2rem; max-width: 1400px; }
h1, h2, h3 { letter-spacing: -0.01em; }

/* Cabeçalho */
.du-header { display: flex; align-items: center; gap: 1rem; margin: 0 0 0.75rem 0; }
.du-header img { width: 52px; height: 52px; flex: 0 0 auto; }
.du-header .du-title { font-size: 1.55rem; font-weight: 700; line-height: 1.2; margin: 0; }
.du-header .du-sub { font-size: 0.95rem; opacity: 0.8; margin: 0.15rem 0 0 0; }
.du-eyebrow { display: inline-block; font-size: 0.72rem; font-weight: 700; letter-spacing: 0.08em;
  text-transform: uppercase; color: var(--du-blue); background: rgba(0, 114, 178, 0.12);
  border-radius: 999px; padding: 0.15rem 0.6rem; margin-bottom: 0.3rem; }

/* Herói */
.du-hero { display: grid; grid-template-columns: minmax(0, 1.4fr) minmax(0, 1fr); gap: 1.25rem;
  align-items: center; border: 1px solid var(--du-border); background: var(--du-surface);
  border-radius: 18px; padding: 1.1rem 1.25rem; margin-bottom: 1rem; }
.du-hero img { width: 100%; max-height: 210px; object-fit: contain; }
.du-hero h1 { font-size: 1.75rem; margin: 0.2rem 0 0.4rem 0; padding: 0; }
.du-hero p { margin: 0; opacity: 0.85; }

/* Cartões de KPI */
.du-kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(175px, 1fr)); gap: 0.75rem; margin: 0.25rem 0 1rem 0; }
.du-kpi { border: 1px solid var(--du-border); background: var(--du-surface); border-radius: 14px;
  padding: 0.75rem 0.9rem; border-left: 5px solid var(--du-blue); min-width: 0; }
.du-kpi .du-kpi-label { font-size: 0.8rem; font-weight: 600; opacity: 0.8; text-transform: uppercase;
  letter-spacing: 0.04em; white-space: normal; }
.du-kpi .du-kpi-value { font-size: clamp(1.15rem, 1.6vw, 1.55rem); font-weight: 700; line-height: 1.25;
  margin-top: 0.15rem; white-space: nowrap; font-variant-numeric: tabular-nums; }
.du-kpi .du-kpi-help { font-size: 0.82rem; opacity: 0.78; margin-top: 0.1rem; }
.du-kpi.green { border-left-color: var(--du-green); }
.du-kpi.amber { border-left-color: var(--du-amber); }
.du-kpi.red { border-left-color: var(--du-red); }
.du-kpi.grey { border-left-color: #8A8F98; }

/* Selo de severidade: texto + cor + forma (nunca só cor) */
.du-badge { display: inline-block; font-weight: 700; font-size: 0.78rem; letter-spacing: 0.03em;
  border-radius: 6px; padding: 0.1rem 0.5rem; border: 1.5px solid currentColor; }
.du-badge.critica { color: #B54800; background: rgba(213, 94, 0, 0.12); }
.du-badge.alta { color: #9A6700; background: rgba(230, 159, 0, 0.14); }
.du-badge.media { color: #7A6A00; background: rgba(240, 228, 66, 0.18); }
.du-badge.informativa { color: #00639E; background: rgba(86, 180, 233, 0.16); }
.du-badge.ok { color: #007A58; background: rgba(0, 158, 115, 0.14); }
@media (prefers-color-scheme: dark) {
  .du-badge.critica { color: #FF9E5E; } .du-badge.alta { color: #F5C04A; }
  .du-badge.media { color: #F0E442; } .du-badge.informativa { color: #8FD0F5; } .du-badge.ok { color: #4FD1A5; }
}

/* Estado vazio */
.du-empty { text-align: center; border: 1px dashed var(--du-border); border-radius: 16px; padding: 1.25rem; margin: 0.5rem 0 1rem 0; }
.du-empty img { width: 180px; max-width: 60%; }
.du-empty h4 { margin: 0.5rem 0 0.25rem 0; }
.du-empty p { margin: 0; opacity: 0.85; }

/* Barra de cobertura */
.du-progress { height: 10px; border-radius: 999px; background: var(--du-border); overflow: hidden; margin: 0.35rem 0 0.2rem 0; }
.du-progress > span { display: block; height: 100%; background: linear-gradient(90deg, var(--du-blue), var(--du-green)); }

/* Rodapé */
.du-footer { margin-top: 2.5rem; padding-top: 1rem; border-top: 1px solid var(--du-border); font-size: 0.85rem; opacity: 0.85; }
.du-footer a { color: inherit; }

/* Métricas nativas: rótulo longo pode quebrar linha em vez de truncar */
[data-testid="stMetricLabel"] p { white-space: normal; }
[data-testid="stMetricValue"] { font-size: 1.6rem; }

@media (max-width: 900px) {
  .du-hero { grid-template-columns: 1fr; }
  .du-hero img { max-height: 150px; }
}
@media (max-width: 640px) {
  .block-container { padding-left: 0.85rem; padding-right: 0.85rem; padding-top: 1.2rem; }
  .du-header img { width: 40px; height: 40px; }
  .du-header .du-title { font-size: 1.2rem; }
  .du-hero h1 { font-size: 1.35rem; }
  .du-kpis { grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0.5rem; }
  .du-kpi { padding: 0.6rem 0.7rem; }
  .du-kpi .du-kpi-value { font-size: 1.2rem; }
  [data-testid="stMetricValue"] { font-size: 1.25rem; }
  /* Colunas de widgets passam a ocupar a linha inteira */
  [data-testid="stHorizontalBlock"] { flex-wrap: wrap; }
  [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] { min-width: calc(50% - 0.5rem) !important; flex: 1 1 calc(50% - 0.5rem) !important; }
}
@media (max-width: 340px) {
  .du-kpis { grid-template-columns: 1fr; }
  [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] { min-width: 100% !important; flex: 1 1 100% !important; }
}
</style>
"""


@lru_cache(maxsize=16)
def asset_data_uri(name: str) -> str:
    data = (ASSETS / name).read_bytes()
    mime = "image/svg+xml" if name.endswith(".svg") else "image/png"
    return f"data:{mime};base64,{base64.b64encode(data).decode()}"


def inject_css() -> None:
    st.markdown(CSS, unsafe_allow_html=True)


def header(title: str, subtitle: str = "", eyebrow: str = "") -> None:
    eyebrow_html = f'<span class="du-eyebrow">{html.escape(eyebrow)}</span>' if eyebrow else ""
    st.markdown(
        f"""
        <div class="du-header">
          <img src="{asset_data_uri('logo.svg')}" alt="Logotipo DataUrnas-BR: urna eletrônica com gráfico"/>
          <div>
            {eyebrow_html}
            <p class="du-title" role="heading" aria-level="1">{html.escape(title)}</p>
            <p class="du-sub">{html.escape(subtitle)}</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def hero(title: str, text: str, eyebrow: str = "") -> None:
    eyebrow_html = f'<span class="du-eyebrow">{html.escape(eyebrow)}</span>' if eyebrow else ""
    st.markdown(
        f"""
        <section class="du-hero">
          <div>
            {eyebrow_html}
            <h1>{html.escape(title)}</h1>
            <p>{html.escape(text)}</p>
          </div>
          <img src="{asset_data_uri('hero.svg')}" alt=""/>
        </section>
        """,
        unsafe_allow_html=True,
    )


def kpi_cards(items: list[dict]) -> None:
    """Cartões responsivos (grid CSS: várias colunas no desktop, 2 ou 1 no celular).

    Cada item: {"label", "value", "help"?, "tone"? in blue/green/amber/red/grey}.
    """
    cards = []
    for item in items:
        tone = item.get("tone", "")
        help_html = f'<div class="du-kpi-help">{html.escape(str(item["help"]))}</div>' if item.get("help") else ""
        cards.append(
            f'<div class="du-kpi {html.escape(tone)}"><div class="du-kpi-label">{html.escape(str(item["label"]))}</div>'
            f'<div class="du-kpi-value">{html.escape(str(item["value"]))}</div>{help_html}</div>'
        )
    st.markdown(f'<div class="du-kpis">{"".join(cards)}</div>', unsafe_allow_html=True)


SEVERIDADES = {
    "CRÍTICO": "critica", "CRÍTICA": "critica", "ALTO": "alta", "ALTA": "alta",
    "MÉDIO": "media", "MÉDIA": "media", "ATENÇÃO": "informativa", "BAIXO": "ok",
    "BAIXA": "ok", "OK": "ok", "INFORMATIVA": "informativa",
}


def badge_html(nivel: str) -> str:
    cls = SEVERIDADES.get(str(nivel).upper(), "informativa")
    return f'<span class="du-badge {cls}">{html.escape(str(nivel).upper())}</span>'


def severity_line(nivel: str, texto: str) -> None:
    """Linha de risco com selo textual colorido (acessível sem depender da cor)."""
    st.markdown(f"{badge_html(nivel)} {html.escape(texto)}", unsafe_allow_html=True)


def empty_state(title: str, text: str, image: str = "empty-data.svg") -> None:
    st.markdown(
        f"""
        <div class="du-empty">
          <img src="{asset_data_uri(image)}" alt=""/>
          <h4>{html.escape(title)}</h4>
          <p>{html.escape(text)}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def progress_bar(fraction: float, label: str) -> None:
    pct_value = max(0.0, min(1.0, float(fraction or 0))) * 100
    st.markdown(
        f'<div class="du-progress" role="progressbar" aria-valuemin="0" aria-valuemax="100" '
        f'aria-valuenow="{pct_value:.0f}" aria-label="{html.escape(label)}"><span style="width:{pct_value:.2f}%"></span></div>',
        unsafe_allow_html=True,
    )


def footer() -> None:
    st.markdown(
        f"""
        <footer class="du-footer">
          <strong>Fontes:</strong> Tribunal Superior Eleitoral (TSE), dados abertos de resultados
          (<a href="https://resultados.tse.jus.br" target="_blank" rel="noopener">resultados.tse.jus.br</a>)
          e boletins de urna públicos; malha das UFs: IBGE (API de malhas territoriais, dados públicos).<br/>
          Os indicadores são sinais para investigação e não constituem prova de fraude nem de lisura.
          Código sob licença {LICENCA}:
          <a href="{REPO_URL}" target="_blank" rel="noopener">DataUrnas-BR</a>.
        </footer>
        """,
        unsafe_allow_html=True,
    )


def grupos_resumo(contagens: dict[str, int], unidade: str = "ocorrência(s)") -> None:
    """Três cartões, um por grupo de leitura, com o total e a explicação de uma linha.

    O grupo é identificado pelo número e pelo nome, não só pela cor da borda.
    """
    from dataurnas.dashboard.reference import GRUPO_OPERACIONAL, GRUPOS, GRUPOS_ORDEM, grupo_nome

    def _tom(grupo: str, total: int) -> str:
        # Zero nos grupos 1 e 2 é o resultado esperado (verde); o grupo 3 é sempre neutro
        if grupo == GRUPO_OPERACIONAL or total:
            return GRUPOS[grupo]["tom"]
        return "green"

    kpi_cards([
        {"label": grupo_nome(g), "value": f"{int(contagens.get(g, 0)):,} {unidade}".replace(",", "."),
         "help": GRUPOS[g]["resumo"], "tone": _tom(g, int(contagens.get(g, 0)))}
        for g in GRUPOS_ORDEM
    ])


def nota_grupo_analise(chave: str) -> None:
    """Linha que situa uma análise agregada (Benford, outliers) no seu grupo de leitura."""
    from dataurnas.dashboard.reference import ANALISES_ESTATISTICAS, GRUPOS, grupo_nome

    _nome, grupo, motivo = ANALISES_ESTATISTICAS[chave]
    selo = badge_html(f"Grupo {GRUPOS[grupo]['ordem']}")
    st.markdown(f"{selo} **Grupo de leitura: {html.escape(grupo_nome(grupo))}.** "
                f"{html.escape(motivo)}", unsafe_allow_html=True)
