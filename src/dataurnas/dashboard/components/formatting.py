"""Formatação numérica e textual no padrão brasileiro (pt-BR).

Sem dependência de locale do sistema: o servidor pode rodar com locale C
(contêiner) e mesmo assim exibir 1.234.567 e 12,34%.
"""

from __future__ import annotations

import math
import re
from numbers import Number

TRACO = "-"


def _is_missing(value) -> bool:
    if value is None:
        return True
    try:
        return isinstance(value, float) and math.isnan(value)
    except TypeError:
        return False


def _swap_separators(text: str) -> str:
    """Troca separadores do formato en-US (1,234.5) para pt-BR (1.234,5)."""
    return text.replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def fmt_int(value, default: str = TRACO) -> str:
    """Inteiro com separador de milhar pt-BR: 1234567 -> '1.234.567'."""
    if _is_missing(value):
        return default
    try:
        number = int(round(float(value)))
    except (TypeError, ValueError):
        return default
    return _swap_separators(f"{number:,}")


def fmt_num(value, decimals: int = 2, sign: bool = False, default: str = TRACO) -> str:
    """Número decimal pt-BR: 1234.5 -> '1.234,50' (sign=True prefixa + ou -)."""
    if _is_missing(value):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    spec = f"{'+' if sign else ''},.{decimals}f"
    return _swap_separators(format(number, spec))


def fmt_pct(value, decimals: int = 2, sign: bool = False, default: str = TRACO) -> str:
    """Percentual pt-BR: 12.345 -> '12,35%'. O valor já deve estar em pontos percentuais."""
    text = fmt_num(value, decimals=decimals, sign=sign, default=default)
    return text if text == default else f"{text}%"


def fmt_pp(value, decimals: int = 2, default: str = TRACO) -> str:
    """Diferença em pontos percentuais com sinal: 1.5 -> '+1,50 p.p.'."""
    text = fmt_num(value, decimals=decimals, sign=True, default=default)
    return text if text == default else f"{text} p.p."


def fmt_compact(value, default: str = TRACO) -> str:
    """Forma curta para cartões: 158745502 -> '158,7 mi'."""
    if _is_missing(value):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    absolute = abs(number)
    for limit, suffix in ((1e9, "bi"), (1e6, "mi"), (1e3, "mil")):
        if absolute >= limit:
            return f"{fmt_num(number / limit, 1)} {suffix}"
    return fmt_int(number)


def pct(part, whole) -> float:
    """Percentual seguro (0 quando o denominador é zero ou ausente)."""
    if _is_missing(part) or _is_missing(whole):
        return 0.0
    try:
        whole = float(whole)
        return float(part) / whole * 100 if whole else 0.0
    except (TypeError, ValueError):
        return 0.0


def is_number(value) -> bool:
    return isinstance(value, Number) and not isinstance(value, bool) and not _is_missing(value)


# ----------------------------------------------------------------------
# Acentuação de textos que vêm do banco sem acento
# ----------------------------------------------------------------------
# As descrições de issue foram gravadas no Parquet sem acentos. Corrigir na
# origem exige reconstruir o banco; aqui a correção é feita só na exibição.
_ACENTOS = {
    "abstencao": "abstenção",
    "apos": "após",
    "atencao": "atenção",
    "biometria": "biometria",
    "codigo": "código",
    "comparecimento": "comparecimento",
    "contingencia": "contingência",
    "divergencia": "divergência",
    "eleicao": "eleição",
    "eleicoes": "eleições",
    "horario": "horário",
    "inicio": "início",
    "invalido": "inválido",
    "liberacao": "liberação",
    "mesario": "mesário",
    "nao": "não",
    "numero": "número",
    "padrao": "padrão",
    "proporcao": "proporção",
    "reinicio": "reinício",
    "secao": "seção",
    "secoes": "seções",
    "substituicao": "substituição",
    "votacao": "votação",
}
_PALAVRA = re.compile(r"[A-Za-z]+")


def acentuar(texto) -> str:
    """Restaura acentos de palavras conhecidas preservando maiúsculas iniciais."""
    if not isinstance(texto, str) or not texto:
        return texto

    def _troca(match: re.Match) -> str:
        palavra = match.group(0)
        correta = _ACENTOS.get(palavra.lower())
        if correta is None:
            return palavra
        if palavra.isupper() and len(palavra) > 1:
            return correta.upper()
        if palavra[0].isupper():
            return correta[0].upper() + correta[1:]
        return correta

    texto = texto.replace("nao-padrao", "não padrão")
    return _PALAVRA.sub(_troca, texto)


SEVERIDADE_LABEL = {
    "critica": "Crítica",
    "alta": "Alta",
    "media": "Média",
    "informativa": "Informativa",
}


def severidade_label(valor) -> str:
    if not isinstance(valor, str):
        return valor
    return SEVERIDADE_LABEL.get(valor.lower(), valor)
