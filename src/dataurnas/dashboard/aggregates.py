"""Tabelas agregadas pré-calculadas para o dashboard de 2022.

As análises mais pesadas varriam os 72 milhões de linhas de ``votos`` a cada
primeira carga (Benford chegava a minutos). ``scripts/build_db.py`` cria as
tabelas abaixo uma única vez, no build do banco, e as funções de análise
consultam essas tabelas com os mesmos resultados das consultas originais.

Dois tipos de agregado:

- ``agg_presidente_secao``: uma linha por seção com os totais de Presidente.
  É sempre combinada com ``secoes s`` via ``JOIN``, então aceita qualquer filtro.
- Cubos (``agg_votos_nominais``, ``agg_benford_presidente``,
  ``agg_benford_cargo``): agregados pelas dimensões de filtro em ``CUBE_DIMS``.
  Usam o alias ``s`` e as mesmas colunas de ``secoes``; o WHERE dos filtros é
  aplicado sem mudança. Quando um filtro usa coluna fora de ``CUBE_DIMS`` (por
  exemplo município) ou o banco não tem o cubo, a consulta usa a fonte bruta
  equivalente (linha a linha a partir de ``votos`` e ``secoes``), com o mesmo
  resultado.

Os dígitos de Benford são extraídos da representação decimal do inteiro,
como antes era feito em pandas com ``astype(str).str[0]`` e ``str[1]``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Dimensões de filtro do dashboard presentes nos cubos (sem município: com ele
# os cubos ficariam do tamanho da tabela bruta; filtro por município usa a
# fonte bruta, que já é pequena depois do filtro).
CUBE_DIMS = ("turno", "uf", "regiao", "modelo_urna", "is_reserva", "has_issues")

_DIMS_S = ", ".join(f"s.{d}" for d in CUBE_DIMS)

D1_SQL = "CAST(SUBSTR(CAST(v.quantidade AS VARCHAR), 1, 1) AS INTEGER)"
D2_SQL = (
    "CASE WHEN v.quantidade >= 10 "
    "THEN CAST(SUBSTR(CAST(v.quantidade AS VARCHAR), 2, 1) AS INTEGER) END"
)

# ----------------------------------------------------------------------
# Definições (SELECT) de cada agregado
# ----------------------------------------------------------------------
PRESIDENTE_SECAO_SELECT = """
    SELECT
        v.secao_id,
        SUM(v.quantidade) FILTER (WHERE v.tipo_voto = 'nominal' AND v.codigo_candidato = 13) AS votos_13,
        SUM(v.quantidade) FILTER (WHERE v.tipo_voto = 'nominal' AND v.codigo_candidato = 22) AS votos_22,
        COUNT(*) FILTER (WHERE v.tipo_voto = 'nominal' AND v.codigo_candidato = 13) AS n_13,
        COUNT(*) FILTER (WHERE v.tipo_voto = 'nominal' AND v.codigo_candidato = 22) AS n_22,
        SUM(v.quantidade) FILTER (WHERE v.tipo_voto = 'nominal') AS nominais,
        SUM(v.quantidade) FILTER (WHERE v.tipo_voto = 'branco') AS brancos,
        SUM(v.quantidade) FILTER (WHERE v.tipo_voto = 'nulo') AS nulos,
        SUM(v.quantidade) AS total
    FROM votos v
    WHERE v.cargo = 'Presidente'
    GROUP BY v.secao_id
"""

# Fontes "linha a linha" equivalentes aos cubos: expõem todas as colunas de
# seções (s.*), então qualquer filtro funciona sobre elas.
_RAW_SOURCES = {
    "agg_votos_nominais": """
        SELECT s.*, v.secao_id, v.cargo, v.codigo_candidato, v.partido, v.quantidade AS votos
        FROM votos v JOIN secoes s ON v.secao_id = s.id
        WHERE v.tipo_voto = 'nominal'
    """,
    "agg_benford_presidente": f"""
        SELECT s.*, v.codigo_candidato AS candidato, {D1_SQL} AS d1, {D2_SQL} AS d2, 1 AS n
        FROM votos v JOIN secoes s ON v.secao_id = s.id
        WHERE v.cargo = 'Presidente' AND v.tipo_voto = 'nominal' AND v.quantidade > 0
    """,
    "agg_benford_cargo": f"""
        SELECT s.*, v.cargo, {D1_SQL} AS d1, 1 AS n
        FROM votos v JOIN secoes s ON v.secao_id = s.id
        WHERE v.tipo_voto = 'nominal' AND v.quantidade > 0
    """,
}

_CUBE_SELECTS = {
    "agg_votos_nominais": f"""
        SELECT {_DIMS_S}, v.cargo, v.codigo_candidato, v.partido,
               SUM(v.quantidade) AS votos,
               COUNT(DISTINCT v.secao_id) AS secoes
        FROM votos v JOIN secoes s ON v.secao_id = s.id
        WHERE v.tipo_voto = 'nominal'
        GROUP BY ALL
    """,
    "agg_benford_presidente": f"""
        SELECT {_DIMS_S}, v.codigo_candidato AS candidato, {D1_SQL} AS d1, {D2_SQL} AS d2,
               COUNT(*) AS n
        FROM votos v JOIN secoes s ON v.secao_id = s.id
        WHERE v.cargo = 'Presidente' AND v.tipo_voto = 'nominal' AND v.quantidade > 0
        GROUP BY ALL
    """,
    "agg_benford_cargo": f"""
        SELECT {_DIMS_S}, v.cargo, {D1_SQL} AS d1, COUNT(*) AS n
        FROM votos v JOIN secoes s ON v.secao_id = s.id
        WHERE v.tipo_voto = 'nominal' AND v.quantidade > 0
        GROUP BY ALL
    """,
}

AGGREGATE_TABLES = ("agg_presidente_secao", *_CUBE_SELECTS)


def create_aggregates(conn) -> dict[str, int]:
    """Cria (ou recria) as tabelas agregadas a partir de ``votos`` e ``secoes``.

    Ordena cada tabela pelas colunas mais filtradas para aproveitar os zone
    maps do DuckDB. Devolve o número de linhas de cada tabela.
    """
    counts = {}
    conn.execute("DROP TABLE IF EXISTS agg_presidente_secao")
    conn.execute(
        f"CREATE TABLE agg_presidente_secao AS {PRESIDENTE_SECAO_SELECT} ORDER BY secao_id"
    )
    for name, select in _CUBE_SELECTS.items():
        conn.execute(f"DROP TABLE IF EXISTS {name}")
        conn.execute(f"CREATE TABLE {name} AS {select} ORDER BY turno, uf")
    for name in AGGREGATE_TABLES:
        counts[name] = conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
    return counts


# ----------------------------------------------------------------------
# Uso nas consultas
# ----------------------------------------------------------------------
def available_tables(store) -> frozenset:
    """Agregados presentes no banco (consulta barata, cacheada no dashboard)."""
    df = store.query_df(
        "SELECT table_name FROM information_schema.tables WHERE table_name LIKE 'agg\\_%' ESCAPE '\\'"
    )
    return frozenset(df["table_name"].tolist()) if not df.empty else frozenset()


def _where_columns(where: str) -> set[str]:
    return set(re.findall(r"\bs\.([A-Za-z_][A-Za-z0-9_]*)", where))


def cube_usable(where: str) -> bool:
    """True se o WHERE (alias ``s``) só usa colunas presentes nos cubos."""
    return _where_columns(where) <= set(CUBE_DIMS)


@dataclass(frozen=True)
class CubeSource:
    """Fonte FROM de um cubo: tabela agregada ou subconsulta bruta equivalente.

    ``secoes_expr`` conta seções distintas (somente ``agg_votos_nominais``).
    """

    sql: str
    is_cube: bool
    secoes_expr: str = ""


def cube_source(store, where: str, name: str) -> CubeSource:
    if name not in _CUBE_SELECTS:
        raise KeyError(name)
    if cube_usable(where) and name in available_tables(store):
        return CubeSource(name, True, "CAST(SUM(s.secoes) AS BIGINT)")
    return CubeSource(f"({_RAW_SOURCES[name]})", False, "COUNT(DISTINCT s.secao_id)")


def presidente_secao_source(store) -> str:
    """FROM de ``agg_presidente_secao`` (ou a subconsulta equivalente)."""
    if "agg_presidente_secao" in available_tables(store):
        return "agg_presidente_secao"
    return f"({PRESIDENTE_SECAO_SELECT})"


def presidente_join(store) -> str:
    """FROM com os totais de Presidente por seção (alias ``p``) e as seções (``s``)."""
    return f"{presidente_secao_source(store)} p JOIN secoes s ON p.secao_id = s.id"


# Fragmentos sobre ``agg_presidente_secao`` (alias p). Como ``quantidade`` nunca
# é NULL, SUM(CASE WHEN candidato = 13 THEN quantidade ELSE 0 END) sobre os
# registros nominais de 13 e 22 de uma seção é COALESCE(p.votos_13, 0), e a
# seção só participa se tiver algum desses registros (P_TEM_13_22).
P13 = "COALESCE(p.votos_13, 0)"
P22 = "COALESCE(p.votos_22, 0)"
P_TEM_13_22 = "(p.n_13 + p.n_22) > 0"
