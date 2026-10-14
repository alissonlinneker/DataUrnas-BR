#!/usr/bin/env python3
"""Rebuild PARALELO do banco DuckDB com parser turno-aware.

Usa multiprocessing para analisar seções em paralelo (CPU-bound), enquanto
o processo principal grava no DuckDB (único escritor) em lotes
transacionais via DuckDBStore.insert_rows.

Suporta RESUME: seções já presentes no banco são descartadas ANTES do
parse (o secao_id é derivado do caminho do arquivo).

SEGURANÇA: exige backup prévio. Dados raw NÃO são alterados.
"""

import argparse
import logging
import multiprocessing as mp
import os
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from dataurnas.analyzer.batch import BatchAnalyzer
from dataurnas.config import RAW_DIR
from dataurnas.database.duckdb_store import DEFAULT_DB_PATH, DuckDBStore
from dataurnas.database.rows import extract_rows

LOG_FILE = Path(__file__).parent.parent / "data" / "rebuild_parallel.log"
BACKUP = DEFAULT_DB_PATH.parent / "eleicoes_2022_BACKUP.duckdb"
SNAPSHOT = DEFAULT_DB_PATH.parent / "eleicoes_2022_live.duckdb"

logger = logging.getLogger("rebuild_parallel")

# Analisador do worker, inicializado UMA VEZ por processo
_worker_analyzer = None


def _setup_logging() -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    fmt = "%(asctime)s [%(levelname)s] %(message)s"
    file_handler = logging.FileHandler(str(LOG_FILE), mode="a", encoding="utf-8")
    file_handler.setFormatter(logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S"))
    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(logging.Formatter(fmt, datefmt="%H:%M:%S"))
    logging.basicConfig(level=logging.INFO, handlers=[file_handler, console], force=True)


def _init_worker() -> None:
    global _worker_analyzer
    _worker_analyzer = BatchAnalyzer(raw_dir=RAW_DIR)


def parse_section(bu_file_str: str):
    """Worker: analisa UMA seção e devolve SectionRows (ou dict de erro)."""
    try:
        bu_file = Path(bu_file_str)
        result = _worker_analyzer.analyze_section(bu_file.parent, bu_file=bu_file)
        return extract_rows(result)
    except Exception as e:
        return {"error": str(e), "file": bu_file_str}


def create_snapshot(store: DuckDBStore) -> None:
    """Copia o banco para o snapshot do dashboard de forma atômica.

    O CHECKPOINT roda no mesmo processo que escreve, sem transação aberta,
    então o arquivo copiado está consistente. A cópia vai para um arquivo
    temporário e é publicada com os.replace.
    """
    store._conn.execute("CHECKPOINT")
    tmp = SNAPSHOT.with_suffix(".duckdb.tmp")
    shutil.copy2(str(DEFAULT_DB_PATH), str(tmp))
    os.replace(tmp, SNAPSHOT)
    SNAPSHOT.with_suffix(".duckdb.wal").unlink(missing_ok=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 1),
                    help="processos de parsing (padrão: núcleos menos 1)")
    ap.add_argument("--batch-size", type=int, default=500,
                    help="seções por transação de escrita no DuckDB (padrão: 500)")
    ap.add_argument("--snapshot-every", type=int, default=50_000,
                    help="Seções gravadas entre snapshots do dashboard (0 desativa)")
    ap.add_argument("--min-bus", type=int, default=900_000,
                    help="Aborta se houver menos BUs no disco (proteção contra raw incompleto)")
    ap.add_argument("--no-backup-check", action="store_true",
                    help="não exige o backup do banco antes de começar")
    args = ap.parse_args()

    _setup_logging()
    logger.info("REBUILD PARALELO - INÍCIO")

    if not args.no_backup_check and not BACKUP.exists():
        logger.error("ABORTANDO: backup não encontrado em %s", BACKUP)
        sys.exit(1)

    store = DuckDBStore(DEFAULT_DB_PATH)
    existing_ids = store.existing_ids()
    logger.info("Seções já no banco (resume): %d", len(existing_ids))

    analyzer = BatchAnalyzer(raw_dir=RAW_DIR)
    bu_files = analyzer.find_bu_files()
    total_disk = len(bu_files)
    logger.info("BUs no disco: %d", total_disk)
    if total_disk < args.min_bus:
        logger.error("ABORTANDO: apenas %d BUs (mínimo %d)", total_disk, args.min_bus)
        sys.exit(1)

    # Resume: filtrar antes do parse
    pendentes = [str(f) for f in bu_files if analyzer.secao_id_for(f) not in existing_ids]
    skipped = total_disk - len(pendentes)
    logger.info("A processar: %d | pulados (já no banco): %d | workers: %d",
                len(pendentes), skipped, args.workers)

    start = time.time()
    compiled = errors = 0
    error_samples: list[str] = []
    next_snapshot = args.snapshot_every
    batch = []

    with mp.Pool(processes=args.workers, initializer=_init_worker) as pool:
        for i, item in enumerate(pool.imap_unordered(parse_section, pendentes, chunksize=100), 1):
            if isinstance(item, dict):
                errors += 1
                if len(error_samples) < 20:
                    error_samples.append(f"{item['file']}: {item['error']}")
                continue
            batch.append(item)
            if len(batch) >= args.batch_size:
                compiled += store.insert_rows(batch)
                batch = []

            if i % 2000 == 0:
                elapsed = time.time() - start
                rate = i / (elapsed / 60) if elapsed > 0 else 0
                eta_h = (len(pendentes) - i) / rate / 60 if rate > 0 else 0
                logger.info("Progresso: %d/%d | %d gravados, %d erros | %.0f/min | ETA %.1f h",
                            i, len(pendentes), compiled, errors, rate, eta_h)

            if args.snapshot_every and compiled >= next_snapshot:
                logger.info("Snapshot intermediário (%d gravados)", compiled)
                try:
                    create_snapshot(store)
                except OSError as e:
                    logger.warning("Falha ao criar snapshot: %s", e)
                next_snapshot += args.snapshot_every

    if batch:
        compiled += store.insert_rows(batch)

    # Workers usam BatchAnalyzer padrão (sem verificação SHA-512)
    store.registrar_verificacao_hashes(
        analyzer.verify_hashes, incremental=True, secoes_anteriores=len(existing_ids),
    )
    create_snapshot(store)
    count, t1, t2 = store._contagem_turnos()
    reboots_t2 = store._conn.execute(
        "SELECT COUNT(*) FROM secoes WHERE turno = 2 AND reboots > 0"
    ).fetchone()[0]
    store.close()

    elapsed = time.time() - start
    logger.info("REBUILD PARALELO COMPLETO em %.1f h", elapsed / 3600)
    logger.info("Total no banco: %d seções (1T: %d, 2T: %d)", count, t1, t2)
    logger.info("Gravados: %d | pulados: %d | erros: %d", compiled, skipped, errors)
    logger.info("Reboots T2: %d seções (%.1f%%)", reboots_t2, reboots_t2 / (t2 or 1) * 100)
    for sample in error_samples[:10]:
        logger.info("  erro: %s", sample)


if __name__ == "__main__":
    main()
