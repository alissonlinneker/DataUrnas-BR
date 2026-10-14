"""Conexão compartilhada com o DuckDB e camada de cache do dashboard.

- Uma única conexão somente leitura por processo (``st.cache_resource``).
- Cada consulta usa um cursor próprio (``conn.cursor()``), seguro entre
  threads/sessões; a sessão também guarda um cursor para chamadas sem cache.
- Resultados de SQL e das funções de ``analysis`` são cacheados por
  ``(sql, params)`` e pela chave dos filtros, nunca pelo objeto ``store``.
- Não há construção automática do banco dentro de uma requisição: o banco é
  gerado por ``scripts/build_db.py`` (no Dockerfile ou manualmente).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

from dataurnas.dashboard import analysis as _analysis
from dataurnas.dashboard.filters import Filters
from dataurnas.database.duckdb_store import DEFAULT_DB_PATH

logger = logging.getLogger("dataurnas.dashboard")

LIVE_DB_PATH = DEFAULT_DB_PATH.parent / "eleicoes_2022_live.duckdb"
CACHE_TTL = 6 * 3600  # dados de 2022 são estáticos; o TTL só libera memória
QUERY_CACHE_ENTRIES = 600
ANALYSIS_CACHE_ENTRIES = 300


def candidate_db_paths() -> list[Path]:
    """Ordem de preferência: variável de ambiente, snapshot 'live', banco principal."""
    paths = []
    env = os.environ.get("DATAURNAS_DB_PATH")
    if env:
        paths.append(Path(env))
    paths += [LIVE_DB_PATH, DEFAULT_DB_PATH]
    return paths


@st.cache_resource(show_spinner=False)
def _connection(path: str) -> duckdb.DuckDBPyConnection:
    config = {}
    if os.environ.get("DATAURNAS_DUCKDB_MEMORY"):
        config["memory_limit"] = os.environ["DATAURNAS_DUCKDB_MEMORY"]
    if os.environ.get("DATAURNAS_DUCKDB_THREADS"):
        config["threads"] = int(os.environ["DATAURNAS_DUCKDB_THREADS"])
    return duckdb.connect(path, read_only=True, config=config)


def _open_connection() -> tuple[duckdb.DuckDBPyConnection | None, str | None]:
    for path in candidate_db_paths():
        if not path.exists():
            continue
        try:
            return _connection(str(path)), str(path)
        except duckdb.Error:
            logger.exception("Falha ao abrir o banco %s", path)
    return None, None


@st.cache_data(ttl=CACHE_TTL, max_entries=QUERY_CACHE_ENTRIES, show_spinner=False)
def _cached_query(db_path: str, sql: str, params: tuple) -> pd.DataFrame:
    cursor = _connection(db_path).cursor()
    try:
        return cursor.execute(sql, list(params)).fetchdf()
    finally:
        cursor.close()


class DashboardStore:
    """Fachada mínima compatível com ``DuckDBStore`` (``query_df``/``query``)."""

    def __init__(self, conn: duckdb.DuckDBPyConnection, path: str):
        self._conn = conn
        self.path = path

    def query_df(self, sql: str, params=None) -> pd.DataFrame:
        return _cached_query(self.path, sql, tuple(params or ()))

    def query(self, sql: str, params=None) -> list[dict]:
        df = self.query_df(sql, params)
        return df.to_dict(orient="records")

    def session_cursor(self) -> duckdb.DuckDBPyConnection:
        """Cursor da sessão atual, para consultas que não devem ir ao cache."""
        key = f"_duckdb_cursor::{self.path}"
        cursor = st.session_state.get(key)
        if cursor is None:
            cursor = self._conn.cursor()
            st.session_state[key] = cursor
        return cursor

    def get_filter_options(self) -> dict:
        def col(sql: str) -> list:
            return self.query_df(sql).iloc[:, 0].tolist()

        return {
            "turnos": col("SELECT DISTINCT turno FROM secoes ORDER BY turno"),
            "ufs": col("SELECT DISTINCT uf FROM secoes ORDER BY uf"),
            "regioes": col("SELECT DISTINCT regiao FROM secoes WHERE regiao IS NOT NULL ORDER BY regiao"),
            "modelos": col(
                "SELECT DISTINCT modelo_urna FROM secoes WHERE modelo_urna IS NOT NULL ORDER BY modelo_urna"
            ),
            "severidades": col("SELECT DISTINCT severidade FROM issues ORDER BY severidade"),
            "codigos_issue": col("SELECT DISTINCT codigo FROM issues ORDER BY codigo"),
        }

    def municipios(self, ufs: tuple) -> list[str]:
        if not ufs:
            return []
        placeholders = ",".join("?" for _ in ufs)
        df = self.query_df(
            f"SELECT DISTINCT municipio FROM secoes WHERE uf IN ({placeholders}) ORDER BY municipio",
            list(ufs),
        )
        return df["municipio"].dropna().tolist()

    def close(self) -> None:  # a conexão é compartilhada; nada a fechar por sessão
        return None


def get_store() -> DashboardStore | None:
    conn, path = _open_connection()
    if conn is None:
        return None
    return DashboardStore(conn, path)


def clear_caches() -> None:
    _cached_query.clear()
    _run_analysis.clear()


# ----------------------------------------------------------------------
# Funções de análise com cache
# ----------------------------------------------------------------------
_NAO_CACHEAR = {"generate_excel_report", "generate_text_report"}


def _persist_mode() -> str | None:
    """Usa cache em disco (~/.streamlit/cache) só se o diretório for gravável.

    Desligável com DATAURNAS_PERSIST_CACHE=0 (ex.: contêiner com HOME somente leitura).
    """
    if os.environ.get("DATAURNAS_PERSIST_CACHE", "1") in {"0", "false", "no"}:
        return None
    pasta = Path.home() / ".streamlit"
    try:
        pasta.mkdir(parents=True, exist_ok=True)
        return "disk" if os.access(pasta, os.W_OK) else None
    except OSError:
        return None


# persist="disk": algumas análises varrem os 72 milhões de votos (minutos na
# primeira vez); os dados de 2022 são estáticos, então o resultado sobrevive a
# reinícios do servidor. Limpar com "Limpar cache" ou `streamlit cache clear`.
@st.cache_data(persist=_persist_mode(), max_entries=ANALYSIS_CACHE_ENTRIES, show_spinner="Calculando análise...")
def _run_analysis(name: str, filters_key, args: tuple, kwargs: tuple, versao: str = ""):
    # ``versao`` (analysis.ANALYSIS_CACHE_VERSION) entra só na chave do cache:
    # mudar a semântica de uma análise invalida o cache persistido em disco.
    store = get_store()
    if store is None:
        raise RuntimeError("Banco de dados indisponível")
    fn = getattr(_analysis, name)
    if filters_key is None:
        return fn(store, *args, **dict(kwargs))
    return fn(store, Filters.from_key(filters_key), *args, **dict(kwargs))


class CachedAnalysis:
    """Proxy de ``dashboard.analysis`` com as funções envoltas em cache.

    Uso nas páginas: ``from dataurnas.dashboard.state import analysis`` e as
    chamadas continuam ``analysis.benford_first_digit(store, f)``.
    Constantes (ex.: ``BENFORD_SECOND_EXPECTED``) são repassadas sem mudança.
    """

    def __getattr__(self, name: str):
        attr = getattr(_analysis, name)
        if not callable(attr) or name.startswith("_") or isinstance(attr, type):
            return attr
        if name in _NAO_CACHEAR:
            return attr

        def call(store, *args, **kwargs):
            if args and isinstance(args[0], Filters):
                return _run_analysis(name, args[0].cache_key(), tuple(args[1:]),
                                     tuple(sorted(kwargs.items())), _analysis.ANALYSIS_CACHE_VERSION)
            return _run_analysis(name, None, tuple(args), tuple(sorted(kwargs.items())),
                                 _analysis.ANALYSIS_CACHE_VERSION)

        call.__name__ = name
        return call


analysis = CachedAnalysis()
