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

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

import duckdb

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

# SELECT e ORDER BY de cada tabela. A ordem física aproveita os zone maps do
# DuckDB nas colunas mais filtradas.
_TABLE_DEFS = {
    "agg_presidente_secao": (PRESIDENTE_SECAO_SELECT, "secao_id"),
    **{name: (select, "turno, uf") for name, select in _CUBE_SELECTS.items()},
}

# Arquivos de entrada dos agregados (em data/parquet). ``issues`` e
# ``totais_cargo`` não participam das definições acima.
INPUT_PATTERNS = ("secoes.parquet", "votos_*.parquet")

MANIFEST_NAME = "manifest.json"
_MANIFEST_VERSION = 1
_HASH_CHUNK = 1 << 20


def create_aggregates(conn) -> dict[str, int]:
    """Cria (ou recria) as tabelas agregadas a partir de ``votos`` e ``secoes``.

    Ordena cada tabela pelas colunas mais filtradas para aproveitar os zone
    maps do DuckDB. Devolve o número de linhas de cada tabela.
    """
    for name, (select, order) in _TABLE_DEFS.items():
        conn.execute(f"DROP TABLE IF EXISTS {name}")
        conn.execute(f"CREATE TABLE {name} AS {select} ORDER BY {order}")
    return {name: conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
            for name in AGGREGATE_TABLES}


# ----------------------------------------------------------------------
# Agregados pré-calculados em Parquet (build rápido da imagem)
# ----------------------------------------------------------------------
def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(_HASH_CHUNK):
            h.update(chunk)
    return h.hexdigest()


def definitions_hash() -> str:
    """Hash das definições SQL; muda sempre que um agregado muda de fórmula."""
    h = hashlib.sha256(f"v{_MANIFEST_VERSION}".encode())
    for name, (select, order) in _TABLE_DEFS.items():
        h.update(f"\0{name}\0{select}\0{order}".encode())
    return h.hexdigest()


def input_files(parquet_dir: Path) -> list[Path]:
    """Parquet de origem dos agregados, em ordem estável."""
    files: list[Path] = []
    for pattern in INPUT_PATTERNS:
        files.extend(sorted(Path(parquet_dir).glob(pattern)))
    return files


def input_fingerprint(files: list[Path]) -> str:
    """Hash do conteúdo (e do nome) dos Parquet de origem.

    Usa o conteúdo e não o mtime: o git não preserva datas de modificação,
    então o mtime mudaria a cada checkout sem que os dados mudassem.
    """
    h = hashlib.sha256()
    for f in files:
        h.update(f"\0{Path(f).name}\0{_sha256_file(Path(f))}".encode())
    return h.hexdigest()


def _columns(conn, relation: str) -> list[list[str]]:
    return [[r[0], r[1]] for r in conn.execute(f"DESCRIBE {relation}").fetchall()]


def export_aggregates(conn, out_dir: Path, fingerprint: str) -> dict:
    """Grava cada ``agg_*`` em ``out_dir/<nome>.parquet`` (ZSTD) e o manifesto.

    ``fingerprint`` deve ser o ``input_fingerprint`` dos Parquet a partir dos
    quais o banco aberto em ``conn`` foi construído.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    tabelas = {}
    for name in AGGREGATE_TABLES:
        dest = out_dir / f"{name}.parquet"
        tmp = dest.with_name(f"{dest.name}.tmp")
        # SELECT * sem ORDER BY preserva a ordem de inserção (ORDER BY do CREATE)
        conn.execute(
            f"COPY (SELECT * FROM {name}) TO '{tmp}' "  # nome constante, caminho local
            "(FORMAT PARQUET, COMPRESSION ZSTD, ROW_GROUP_SIZE 122880)"
        )
        os.replace(tmp, dest)
        tabelas[name] = {
            "arquivo": dest.name,
            "linhas": conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0],
            "colunas": _columns(conn, name),
            "sha256": _sha256_file(dest),
        }
    manifest = {
        "versao": _MANIFEST_VERSION,
        "definicoes": definitions_hash(),
        "entradas": fingerprint,
        "tabelas": tabelas,
    }
    tmp = out_dir / f"{MANIFEST_NAME}.tmp"
    tmp.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, out_dir / MANIFEST_NAME)
    return manifest


def check_manifest(agg_dir: Path, fingerprint: str) -> tuple[dict | None, str]:
    """Valida o manifesto dos agregados pré-calculados.

    Returns:
        (manifesto, "") quando os arquivos podem ser usados, ou (None, motivo).
    """
    path = Path(agg_dir) / MANIFEST_NAME
    if not path.exists():
        return None, "manifesto ausente"
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return None, f"manifesto ilegível ({e})"
    if manifest.get("versao") != _MANIFEST_VERSION:
        return None, "versão do manifesto diferente"
    if manifest.get("definicoes") != definitions_hash():
        return None, "definições SQL mudaram desde a exportação"
    if manifest.get("entradas") != fingerprint:
        return None, "Parquet de origem mudaram desde a exportação"
    tabelas = manifest.get("tabelas") or {}
    if set(tabelas) != set(AGGREGATE_TABLES):
        return None, "conjunto de tabelas diferente"
    for info in tabelas.values():
        f = Path(agg_dir) / Path(str(info.get("arquivo", ""))).name
        if not f.is_file():
            return None, f"{f.name} ausente"
        if _sha256_file(f) != info.get("sha256"):
            return None, f"{f.name} com conteúdo diferente do manifesto"
    return manifest, ""


def import_aggregates(conn, agg_dir: Path, fingerprint: str) -> tuple[dict[str, int] | None, str]:
    """Importa os ``agg_*`` pré-calculados, se o manifesto confere.

    Requer ``votos`` e ``secoes`` já carregados: os tipos das colunas vêm das
    próprias definições (``DESCRIBE`` só faz o bind, sem executar a consulta) e
    são conferidos com o manifesto, de modo que o resultado é idêntico ao de
    ``create_aggregates``. Em qualquer divergência, nada fica criado e o motivo
    é devolvido para o chamador recalcular.
    """
    manifest, motivo = check_manifest(agg_dir, fingerprint)
    if manifest is None:
        return None, motivo
    counts = {}
    try:
        for name, (select, _order) in _TABLE_DEFS.items():
            info = manifest["tabelas"][name]
            colunas = _columns(conn, f"({select})")
            if colunas != info["colunas"]:
                raise ValueError(f"{name}: colunas ou tipos diferentes do manifesto")
            ddl = ", ".join(f'"{c}" {t}' for c, t in colunas)
            conn.execute(f"DROP TABLE IF EXISTS {name}")
            conn.execute(f"CREATE TABLE {name} ({ddl})")
            conn.execute(
                f"INSERT INTO {name} SELECT * FROM read_parquet(?)",
                [str(Path(agg_dir) / Path(info["arquivo"]).name)],
            )
            n = conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
            if n != info["linhas"]:
                raise ValueError(f"{name}: {n} linhas, manifesto indica {info['linhas']}")
            counts[name] = n
    except (duckdb.Error, ValueError, KeyError, TypeError) as e:
        for name in AGGREGATE_TABLES:
            conn.execute(f"DROP TABLE IF EXISTS {name}")
        return None, str(e)
    return counts, ""


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
