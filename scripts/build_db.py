#!/usr/bin/env python3
"""Reconstrói o banco DuckDB a partir dos arquivos Parquet distribuídos.

O banco e montado em um arquivo temporário e publicado com os.replace, de
modo que uma execução concorrente ou interrompida nunca deixa um banco pela
metade no caminho final.

Depois da importação, o script cria as tabelas agregadas do dashboard
(``agg_*``, ver ``dataurnas.dashboard.aggregates``). Elas evitam varrer os 72
milhões de votos a cada primeira carga das páginas (Benford, votação etc.).

A tabela ``metadados`` registra se os dados passaram pela verificação de
hashes SHA-512 (``verify_hashes``). O valor vem de ``metadados.parquet``,
quando distribuído junto; sem ele, o banco é marcado como NÃO verificado, a
menos que ``--hashes-verificados`` seja informado (use só se os Parquet vieram
de uma compilação com ``dataurnas db build --hashes``). O dashboard usa esse
flag para não apresentar a integridade de hash como avaliada sem que tenha sido.

Uso:
    python scripts/build_db.py            # banco principal + copia "live"
    python scripts/build_db.py --no-live  # apenas o banco principal (imagem Docker)
    python scripts/build_db.py --hashes-verificados  # Parquet de base verificada
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
from dataurnas.database import metadados as _meta  # noqa: E402

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


def _gravar_metadados(conn, hashes_verificados: bool | None) -> bool:
    """Importa metadados.parquet (se houver) e fixa o flag verify_hashes.

    Returns:
        o valor de verify_hashes gravado.
    """
    meta_pq = PARQUET_DIR / "metadados.parquet"
    if meta_pq.exists():
        conn.execute(_meta.DDL)
        conn.execute(
            f"INSERT INTO {_meta.TABELA} (chave, valor) "
            "SELECT CAST(chave AS VARCHAR), CAST(valor AS VARCHAR) FROM read_parquet(?)",
            [str(meta_pq)],
        )
    if hashes_verificados is None:
        registrado = _meta.texto_para_bool(
            _meta.ler_metadados(conn).get(_meta.CHAVE_VERIFY_HASHES))
        hashes_verificados = bool(registrado)
    _meta.gravar_verificacao_hashes(conn, hashes_verificados, origem="parquet")
    return hashes_verificados


def build(live: bool = True, hashes_verificados: bool | None = None) -> Path:
    if not PARQUET_DIR.exists():
        print(f"ERRO: Diretório {PARQUET_DIR} não encontrado.")
        print("Certifique-se de que os arquivos Parquet estão em data/parquet/")
        sys.exit(1)

    for f in REQUIRED:
        if not (PARQUET_DIR / f).exists():
            print(f"ERRO: Arquivo obrigatório não encontrado: {f}")
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

        verificado = _gravar_metadados(conn, hashes_verificados)
        print(f"  Hashes SHA-512 verificados: {'sim' if verificado else 'não'}")

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
    print(f"\nBanco construído com sucesso em {elapsed:.1f}s")
    print(f"  Principal: {DB_PATH} ({DB_PATH.stat().st_size / 1e9:.1f} GB)")
    if live:
        print(f"  Live:      {LIVE_PATH}")
    return DB_PATH


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Reconstrói o DuckDB a partir dos Parquet")
    parser.add_argument("--no-live", action="store_true",
                        help="Não criar a cópia eleicoes_2022_live.duckdb")
    parser.add_argument("--hashes-verificados", action="store_true", default=None,
                        help="Declarar que os Parquet vêm de uma compilação com "
                             "verificação SHA-512 (padrão: metadados.parquet ou não verificado)")
    args = parser.parse_args()
    build(live=not args.no_live, hashes_verificados=args.hashes_verificados)
