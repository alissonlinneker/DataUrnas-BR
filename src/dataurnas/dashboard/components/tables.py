"""Tabelas com formatação numérica preservada (ordenação continua numérica)."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from dataurnas.dashboard.components.formatting import acentuar, severidade_label

MAX_TABLE_HEIGHT = 520

# Rótulos legíveis para colunas recorrentes
COLUMN_LABELS = {
    "uf": "UF",
    "estado": "UF",
    "secoes": "Seções",
    "secao": "Seção",
    "secao_id": "ID da seção",
    "municipio": "Município",
    "zona": "Zona",
    "modelo": "Modelo",
    "modelo_urna": "Modelo",
    "turno": "Turno",
    "codigo": "Código",
    "severidade": "Severidade",
    "descricao": "Descrição",
    "base_legal": "Base legal",
    "regiao": "Região",
}


def _auto_config(df: pd.DataFrame, given: dict | None) -> dict:
    config = dict(given or {})
    for col in df.columns:
        if col in config or not isinstance(col, str):
            continue
        name = str(col)
        series = df[col]
        label = COLUMN_LABELS.get(name)
        if pd.api.types.is_bool_dtype(series):
            continue
        if pd.api.types.is_numeric_dtype(series):
            # "localized" segue o idioma do navegador: 1.234.567 e 12,34 em pt-BR,
            # mantendo o valor numérico (a ordenação da coluna continua correta)
            config[col] = st.column_config.NumberColumn(label, format="localized")
        elif label:
            config[col] = st.column_config.TextColumn(label)
    return config


def prepare_display(df: pd.DataFrame) -> pd.DataFrame:
    """Acentua textos vindos do banco (descrições, severidades) só para exibição."""
    out = df
    if "descricao" in df.columns:
        out = out.copy()
        out["descricao"] = out["descricao"].map(acentuar)
    if "severidade" in df.columns and df["severidade"].dtype == object:
        out = out.copy() if out is df else out
        out["severidade"] = out["severidade"].map(severidade_label)
    return out


def show_df(data, width="stretch", height=None, hide_index=None, column_config=None, **kwargs):
    """``st.dataframe`` com formatação pt-BR automática e altura limitada."""
    if isinstance(data, pd.DataFrame):
        data = prepare_display(data)
        column_config = _auto_config(data, column_config) if not isinstance(data.columns, pd.MultiIndex) else column_config
        if height is None and len(data) > 14:
            height = MAX_TABLE_HEIGHT
        elif isinstance(height, int):
            height = min(height, MAX_TABLE_HEIGHT)
    return st.dataframe(
        data,
        width=width,
        height=height if height is not None else "auto",
        hide_index=hide_index,
        column_config=column_config,
        **kwargs,
    )


def data_expander(df: pd.DataFrame, label: str = "Ver dados do gráfico") -> None:
    """Alternativa textual a um gráfico (acessibilidade)."""
    with st.expander(label):
        show_df(df, hide_index=True)
