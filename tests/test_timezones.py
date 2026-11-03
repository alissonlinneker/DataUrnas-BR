import pytest

from dataurnas.analyzer.timezones import get_tz_offset


@pytest.mark.parametrize("uf,mun,esperado", [
    ("am", "02291", -2),   # Eirunepé (UTC-5)
    ("AM", 98477, -2),     # Tabatinga
    ("am", "02755", -2),   # São Paulo de Olivença (abre às 6h locais nos BUs de 2026)
    ("am", "02496", -2),   # Jutaí
    ("am", "02917", -2),   # Amaturá
    ("am", "98370", -2),   # Itamarati
    ("am", "02550", -1),   # Manaus (UTC-4)
    ("am", None, -1),
    ("ac", "01000", -2),
    ("pe", "30015", 1),    # Fernando de Noronha (UTC-2)
    ("pe", "25313", 0),
    ("sp", "71072", 0),
    ("mt", "", -1),
    ("sp", "abc", 0),
])
def test_offsets(uf, mun, esperado):
    assert get_tz_offset(uf, mun) == esperado
