"""Fuso horário local das seções em relação a Brasília (UTC-3).

Os logs da urna registram hora local, enquanto a votação de 2022 seguiu o
horário de Brasília (8h às 17h). O offset é negativo quando o local está
atrás de Brasília.

A UF não basta para todos os casos: o oeste do Amazonas segue o fuso do Acre
(UTC-5) e Fernando de Noronha (PE) está em UTC-2. Por isso o offset é
resolvido por município (código TSE) quando conhecido, com fallback por UF.
"""

from ..config import TIMEZONE_OFFSETS

# Municípios cuja sede fica a oeste da linha Tabatinga-Porto Acre e, portanto,
# seguem UTC-5 (Decreto 2.784/1913, restabelecido pela Lei 12.876/2013).
# Códigos de município do cadastro do TSE (não IBGE).
_AM_UTC5 = {
    2054: "Atalaia do Norte",
    2135: "Benjamin Constant",
    2291: "Eirunepé",
    2313: "Envira",
    2020: "Guajará",
    2399: "Ipixuna",
    98477: "Tabatinga",
}

# Exceções por (uf, código TSE do município) -> offset em horas
MUNICIPIO_TZ_OFFSETS: dict[tuple[str, int], int] = {
    **{("am", cod): -2 for cod in _AM_UTC5},
    ("pe", 30015): 1,  # Fernando de Noronha (UTC-2)
}


def _codigo_municipio(municipio) -> int | None:
    if municipio is None or municipio == "":
        return None
    try:
        return int(str(municipio).strip())
    except ValueError:
        return None


def get_tz_offset(uf: str, municipio=None) -> int:
    """Offset em horas da hora local em relação a Brasília.

    Args:
        uf: sigla da UF (qualquer caixa).
        municipio: código TSE do município (int ou string, com ou sem zeros
            à esquerda). Opcional.
    """
    uf_key = (uf or "").lower()
    cod = _codigo_municipio(municipio)
    if cod is not None:
        override = MUNICIPIO_TZ_OFFSETS.get((uf_key, cod))
        if override is not None:
            return override
    return TIMEZONE_OFFSETS.get(uf_key, 0)
