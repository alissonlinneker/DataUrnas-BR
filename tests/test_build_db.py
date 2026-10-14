"""Smoke test do scripts/build_db.py com Parquet sintéticos."""

import importlib.util
from pathlib import Path

import duckdb
import pytest

from dataurnas.database.duckdb_store import DuckDBStore

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "data" / "parquet" / "schema.sql"


def _load_build_db():
    spec = importlib.util.spec_from_file_location("build_db", ROOT / "scripts" / "build_db.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.skipif(not SCHEMA.exists(), reason="schema.sql dos Parquet ausente")
def test_build_db_a_partir_de_parquet(tmp_path, raw_tree, monkeypatch):
    # Gera Parquet a partir de um banco montado pelo próprio store
    src = tmp_path / "src.duckdb"
    with DuckDBStore(src) as store:
        store.build_from_raw(raw_dir=raw_tree)
    pq = tmp_path / "parquet"
    pq.mkdir()
    con = duckdb.connect(str(src), read_only=True)
    for table, name in [("secoes", "secoes"), ("issues", "issues"),
                        ("totais_cargo", "totais_cargo"), ("votos", "votos_t1_a")]:
        con.execute(f"COPY {table} TO '{pq / name}.parquet' (FORMAT PARQUET)")
    con.close()
    (pq / "schema.sql").write_text(SCHEMA.read_text(encoding="utf-8"), encoding="utf-8")

    mod = _load_build_db()
    db_dir = tmp_path / "db"
    monkeypatch.setattr(mod, "PARQUET_DIR", pq)
    monkeypatch.setattr(mod, "DB_DIR", db_dir)
    monkeypatch.setattr(mod, "DB_PATH", db_dir / "eleicoes_2022.duckdb")
    monkeypatch.setattr(mod, "LIVE_PATH", db_dir / "eleicoes_2022_live.duckdb")

    mod.build(live=False)
    assert not (db_dir / "eleicoes_2022_live.duckdb").exists()
    assert not list(db_dir.glob("*.tmp*"))
    with DuckDBStore(db_dir / "eleicoes_2022.duckdb", read_only=True) as store:
        assert store.get_summary()["total_secoes"] == 3
    con = duckdb.connect(str(db_dir / "eleicoes_2022.duckdb"), read_only=True)
    tabelas = {r[0] for r in con.execute("SELECT table_name FROM information_schema.tables").fetchall()}
    n_pres = con.execute("SELECT COUNT(*) FROM agg_presidente_secao").fetchone()[0]
    con.close()
    from dataurnas.dashboard.aggregates import AGGREGATE_TABLES

    assert set(AGGREGATE_TABLES) <= tabelas
    assert n_pres == 3

    def flag():
        with DuckDBStore(db_dir / "eleicoes_2022.duckdb", read_only=True) as st:
            return st.hashes_verificados()

    # Sem metadados.parquet nem declaração: base marcada como não verificada
    assert "metadados" in tabelas
    assert flag() is False

    mod.build(live=True)  # reexecução substitui o banco sem erro
    assert (db_dir / "eleicoes_2022_live.duckdb").exists()

    mod.build(live=False, hashes_verificados=True)  # declaração explícita
    assert flag() is True

    # metadados.parquet distribuído junto com os dados prevalece sem declaração
    con = duckdb.connect()
    con.execute(f"COPY (SELECT 'verify_hashes' AS chave, 'true' AS valor) "
                f"TO '{pq / 'metadados.parquet'}' (FORMAT PARQUET)")
    con.close()
    mod.build(live=False)
    assert flag() is True


def test_rebuild_parallel_worker_sem_efeito_no_import(raw_tree, tmp_path):
    spec = importlib.util.spec_from_file_location(
        "rebuild_parallel", ROOT / "scripts" / "rebuild_parallel.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    from dataurnas.analyzer.batch import BatchAnalyzer
    from dataurnas.database.rows import SectionRows

    mod._worker_analyzer = BatchAnalyzer(raw_dir=raw_tree)
    bu = next(iter(BatchAnalyzer(raw_dir=raw_tree).find_bu_files()))
    rows = mod.parse_section(str(bu))
    assert isinstance(rows, SectionRows)
    assert rows.secao_id.endswith("/0010") or rows.secao_id.endswith("/0001")

    with DuckDBStore(tmp_path / "p.duckdb") as store:
        assert store.insert_rows([rows]) == 1
        assert store.insert_rows([rows]) == 1
        assert store.get_summary()["total_secoes"] == 1
