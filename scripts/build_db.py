#!/usr/bin/env python3
"""Reconstroi o banco DuckDB a partir dos arquivos Parquet distribuidos.

O banco e montado em um arquivo temporario e publicado com os.replace, de
modo que uma execucao concorrente ou interrompida nunca deixa um banco pela
metade no caminho final.

Depois da importação, o script cria as tabelas agregadas do dashboard
(``agg_*``, ver ``dataurnas.dashboard.aggregates``). Elas evitam varrer os 72
milhões de votos a cada primeira carga das páginas (Benford, votação etc.).

Uso:
    python scripts/build_db.py            # banco principal + copia "live"
    python scripts/build_db.py --no-live  # apenas o banco principal (imagem Docker)
"""

import argparse
import os
import shutil
import sys
import time
from pathlib import Path

import duckdb

PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT / "src") not in sys.path:  # execução sem o pacote instalado
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

from dataurnas.dashboard.aggregates import create_aggregates  # noqa: E402
PARQUET_DIR = PROJECT_ROOT / "data" / "parquet"
DB_DIR = PROJECT_ROOT / "data" / "db"
DB_PATH = DB_DIR / "eleicoes_2022.duckdb"
LIVE_PATH = DB_DIR / "eleicoes_2022_live.duckdb"

REQUIRED = ["secoes.parquet", "issues.parquet", "totais_cargo.parquet", "schema.sql"]


def _import(conn, table: str, files: list[Path]) -> int:
    conn.execute(
        f"INSERT INTO {table} SELECT * FROM read_parquet(?)",  # tabela e constante
        [[str(f) for f in files]],
    )
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def build(live: bool = True) -> Path:
    if not PARQUET_DIR.exists():
        print(f"ERRO: Diretorio {PARQUET_DIR} nao encontrado.")
        print("Certifique-se de que os arquivos Parquet estao em data/parquet/")
        sys.exit(1)

    for f in REQUIRED:
        if not (PARQUET_DIR / f).exists():
            print(f"ERRO: Arquivo obrigatorio nao encontrado: {f}")
            sys.exit(1)

    votos_files = sorted(PARQUET_DIR.glob("votos_*.parquet"))
    if not votos_files:
        print("ERRO: Nenhum arquivo votos_*.parquet encontrado.")
        sys.exit(1)

    DB_DIR.mkdir(parents=True, exist_ok=True)
    tmp_path = DB_PATH.with_name(f"{DB_PATH.stem}.{os.getpid()}.tmp.duckdb")
    tmp_path.unlink(missing_ok=True)

    print(f"Construindo banco em {DB_PATH}...")
    start = time.time()

    conn = duckdb.connect(str(tmp_path))
    try:
        conn.execute("BEGIN TRANSACTION")
        schema_sql = (PARQUET_DIR / "schema.sql").read_text(encoding="utf-8")
        for stmt in schema_sql.split(";;"):
            stmt = stmt.strip()
            if stmt:
                conn.execute(stmt)

        for table, files in [
            ("secoes", [PARQUET_DIR / "secoes.parquet"]),
            ("issues", [PARQUET_DIR / "issues.parquet"]),
            ("totais_cargo", [PARQUET_DIR / "totais_cargo.parquet"]),
            ("votos", votos_files),
        ]:
            print(f"  Importando {table} ({len(files)} arquivo(s))...", flush=True)
            n = _import(conn, table, files)
            print(f"    {n:,} linhas")

        print("  Criando tabelas agregadas do dashboard...", flush=True)
        t_agg = time.time()
        for name, n in create_aggregates(conn).items():
            print(f"    {name}: {n:,} linhas")
        print(f"    ({time.time() - t_agg:.1f}s)")
        conn.execute("COMMIT")
        conn.execute("CHECKPOINT")
    except Exception:
        conn.close()
        tmp_path.unlink(missing_ok=True)
        raise
    conn.close()

    os.replace(tmp_path, DB_PATH)
    DB_PATH.with_suffix(".duckdb.wal").unlink(missing_ok=True)

    if live:
        print("  Criando snapshot live...")
        tmp_live = LIVE_PATH.with_suffix(".duckdb.tmp")
        shutil.copy2(DB_PATH, tmp_live)
        os.replace(tmp_live, LIVE_PATH)
    else:
        LIVE_PATH.unlink(missing_ok=True)

    elapsed = time.time() - start
    print(f"\nBanco construido com sucesso em {elapsed:.1f}s")
    print(f"  Principal: {DB_PATH} ({DB_PATH.stat().st_size / 1e9:.1f} GB)")
    if live:
        print(f"  Live:      {LIVE_PATH}")
    return DB_PATH


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reconstroi o DuckDB a partir dos Parquet")
    parser.add_argument("--no-live", action="store_true",
                        help="Nao criar a copia eleicoes_2022_live.duckdb")
    args = parser.parse_args()
    build(live=not args.no_live)
