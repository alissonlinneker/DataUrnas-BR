"""Paleta acessível e ajustes responsivos para gráficos Plotly.

A paleta segue Okabe-Ito (segura para daltonismo). Os gráficos usam fundo
transparente para funcionar nos temas claro e escuro do Streamlit.
"""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

# Okabe-Ito
C_BLUE = "#0072B2"
C_VERMILLION = "#D55E00"
C_ORANGE = "#E69F00"
C_GREEN = "#009E73"
C_SKY = "#56B4E9"
C_YELLOW = "#F0E442"
C_PURPLE = "#CC79A7"
C_GREY = "#8A8F98"

CATEGORICAL = [C_BLUE, C_VERMILLION, C_GREEN, C_ORANGE, C_SKY, C_PURPLE, C_YELLOW, C_GREY]

# Cores fixas por candidato (2022 e 2026), coerentes entre todas as páginas
CANDIDATE_COLORS = {
    13: C_VERMILLION,
    22: C_BLUE,
    70: C_GREEN,
    14: C_ORANGE,
    55: C_SKY,
    30: C_PURPLE,
    15: C_GREEN,
    12: C_ORANGE,
}

# Severidade: cor + rótulo textual sempre (nunca só a cor)
SEVERITY_COLORS = {
    "critica": C_VERMILLION,
    "alta": C_ORANGE,
    "media": C_YELLOW,
    "informativa": C_SKY,
    "ok": C_GREEN,
}

# Escalas contínuas (perceptualmente uniformes e legíveis em daltonismo)
SEQ_SCALE = "Cividis"
SEQ_RISK = "YlOrRd"
DIV_SCALE = "RdBu_r"

DEFAULT_HEIGHT = 380
MAX_HEIGHT = 640
PLOTLY_CONFIG = {
    "displaylogo": False,
    "responsive": True,
    "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"],
}


def candidate_color(numero, fallback_index: int = 0) -> str:
    try:
        return CANDIDATE_COLORS[int(numero)]
    except (KeyError, TypeError, ValueError):
        return CATEGORICAL[fallback_index % len(CATEGORICAL)]


def style_fig(fig: go.Figure, height: int | None = None, legend_bottom: bool = True) -> go.Figure:
    """Layout enxuto e responsivo: altura limitada, legenda horizontal, margens curtas."""
    current = fig.layout.height
    target = height or current or DEFAULT_HEIGHT
    target = max(220, min(int(target), MAX_HEIGHT))
    fig.update_layout(
        height=target,
        autosize=True,
        margin=dict(l=8, r=8, t=48 if fig.layout.title.text else 16, b=8),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter, 'Source Sans 3', system-ui, sans-serif", size=13),
        title=dict(font=dict(size=15), x=0, xanchor="left"),
        separators=",.",  # decimal vírgula, milhar ponto (pt-BR)
        colorway=CATEGORICAL,
        hoverlabel=dict(font_size=12),
    )
    if legend_bottom and fig.layout.showlegend is not False:
        fig.update_layout(
            legend=dict(orientation="h", yanchor="top", y=-0.18, xanchor="left", x=0, title_text="")
        )
    fig.update_xaxes(automargin=True, gridcolor="rgba(128,128,128,0.18)", zerolinecolor="rgba(128,128,128,0.3)")
    fig.update_yaxes(automargin=True, gridcolor="rgba(128,128,128,0.18)", zerolinecolor="rgba(128,128,128,0.3)")
    return fig


def show_chart(fig: go.Figure, height: int | None = None, caption: str | None = None, key: str | None = None):
    """Renderiza o gráfico ocupando a largura do contêiner, com descrição opcional."""
    style_fig(fig, height=height)
    st.plotly_chart(fig, width="stretch", config=PLOTLY_CONFIG, key=key)
    if caption:
        st.caption(caption)
