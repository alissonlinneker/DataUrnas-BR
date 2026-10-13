"""Tratamento de erros: registra o detalhe no log e mostra mensagem amigável.

Nunca exibir a exceção crua ao usuário (pode conter SQL e caminhos do
servidor). O detalhe vai para o logger ``dataurnas.dashboard``.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager

import streamlit as st

logger = logging.getLogger("dataurnas.dashboard")

_SUFIXO = "Tente novamente em instantes ou ajuste os filtros."


def show_error(message: str, exc: BaseException | None = None, level: str = "warning") -> None:
    """Registra ``exc`` com traceback e mostra ``message`` sem detalhes internos."""
    text = message.rstrip(" :.")
    if text.lower().startswith("erro ao "):
        text = "Não foi possível " + text[len("erro ao "):]
    if exc is not None:
        logger.error("%s", text, exc_info=exc)
    getattr(st, level if level in {"warning", "error", "info"} else "warning")(f"{text}. {_SUFIXO}")


@contextmanager
def safe_section(name: str):
    """Isola uma seção da página: um erro nela não derruba o restante."""
    try:
        yield
    except Exception as exc:  # noqa: BLE001 (fronteira de UI: tudo é registrado)
        # Exceções de controle do Streamlit (rerun/stop) precisam propagar
        if type(exc).__name__ in {"RerunException", "StopException"}:
            raise
        show_error(f"Não foi possível carregar {name}", exc)
