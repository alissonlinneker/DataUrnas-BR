"""Malha das UFs do Brasil, versionada no repositório (sem download em runtime).

Fonte: IBGE, API de malhas territoriais v3 (qualidade mínima, divisão por UF),
dados públicos do governo federal. Coordenadas arredondadas para 3 casas e
propriedade ``sigla`` (ex.: "SP") adicionada a partir do código IBGE.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

GEOJSON_PATH = Path(__file__).resolve().parent.parent / "assets" / "brasil-uf.geojson"
FONTE_GEOJSON = "IBGE, API de malhas territoriais (dados públicos)"


@lru_cache(maxsize=1)
def brazil_geojson() -> dict:
    with GEOJSON_PATH.open(encoding="utf-8") as fh:
        return json.load(fh)
