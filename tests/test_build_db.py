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


# ----------------------------------------------------------------------
# Agregados pré-calculados (caminho rápido do build)
# ----------------------------------------------------------------------
def _parquet_e_modulo(tmp_path, raw_tree, monkeypatch):
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
    return mod, pq, db_dir / "eleicoes_2022.duckdb"


def _assert_agregados_iguais_ao_calculo(db_path):
    """Cada agg_* do banco é idêntico (linhas, tipos e EXCEPT ALL) ao recálculo."""
    from dataurnas.dashboard import aggregates as agg

    con = duckdb.connect(str(db_path), read_only=True)
    try:
        for name, (select, _order) in agg._TABLE_DEFS.items():
            assert con.execute(f"DESCRIBE {name}").fetchall() == \
                con.execute(f"DESCRIBE ({select})").fetchall()
            for a, b in [(name, f"({select})"), (f"({select})", name)]:
                diff = con.execute(
                    f"SELECT COUNT(*) FROM (SELECT * FROM {a} EXCEPT ALL SELECT * FROM {b})"
                ).fetchone()[0]
                assert diff == 0, name
    finally:
        con.close()


@pytest.mark.skipif(not SCHEMA.exists(), reason="schema.sql dos Parquet ausente")
def test_agregados_caminho_rapido(tmp_path, raw_tree, monkeypatch, capsys):
    mod, pq, db_path = _parquet_e_modulo(tmp_path, raw_tree, monkeypatch)
    agg_dir = pq / "agregados"

    mod.build(live=False, exportar_agregados=agg_dir)
    assert (agg_dir / "manifest.json").exists()
    assert len(list(agg_dir.glob("agg_*.parquet"))) == 4
    capsys.readouterr()

    mod.build(live=False)
    out = capsys.readouterr().out
    assert "importados" in out
    assert "Criando tabelas agregadas" not in out
    _assert_agregados_iguais_ao_calculo(db_path)

    mod.build(live=False, recalcular_agregados=True)
    assert "Criando tabelas agregadas" in capsys.readouterr().out


@pytest.mark.skipif(not SCHEMA.exists(), reason="schema.sql dos Parquet ausente")
def test_agregados_ausentes_ou_corrompidos_recalculam(tmp_path, raw_tree, monkeypatch, capsys):
    mod, pq, db_path = _parquet_e_modulo(tmp_path, raw_tree, monkeypatch)
    agg_dir = pq / "agregados"

    mod.build(live=False)  # sem diretório de agregados
    out = capsys.readouterr().out
    assert "manifesto ausente" in out and "Criando tabelas agregadas" in out
    _assert_agregados_iguais_ao_calculo(db_path)

    mod.build(live=False, exportar_agregados=agg_dir)
    capsys.readouterr()
    with open(agg_dir / "agg_benford_cargo.parquet", "ab") as f:
        f.write(b"x")
    mod.build(live=False)
    out = capsys.readouterr().out
    assert "conteúdo diferente do manifesto" in out and "Criando tabelas agregadas" in out
    _assert_agregados_iguais_ao_calculo(db_path)


@pytest.mark.skipif(not SCHEMA.exists(), reason="schema.sql dos Parquet ausente")
def test_agregados_desatualizados_sao_recalculados(tmp_path, raw_tree, monkeypatch, capsys):
    import json

    mod, pq, db_path = _parquet_e_modulo(tmp_path, raw_tree, monkeypatch)
    agg_dir = pq / "agregados"
    mod.build(live=False, exportar_agregados=agg_dir)
    capsys.readouterr()

    # Dados de origem mudam depois da exportação: votos de Presidente dobrados
    con = duckdb.connect()
    votos = pq / "votos_t1_a.parquet"
    con.execute(f"COPY (SELECT * REPLACE (quantidade * 2 AS quantidade) FROM '{votos}') "
                f"TO '{pq / 'votos_tmp.parquet'}' (FORMAT PARQUET)")
    con.close()
    (pq / "votos_tmp.parquet").replace(votos)

    mod.build(live=False)
    out = capsys.readouterr().out
    assert "Parquet de origem mudaram" in out and "Criando tabelas agregadas" in out
    _assert_agregados_iguais_ao_calculo(db_path)

    # Definições SQL diferentes das registradas no manifesto também invalidam
    mod.build(live=False, exportar_agregados=agg_dir)
    manifest = json.loads((agg_dir / "manifest.json").read_text(encoding="utf-8"))
    manifest["definicoes"] = "0" * 64
    (agg_dir / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    capsys.readouterr()
    mod.build(live=False)
    assert "definições SQL mudaram" in capsys.readouterr().out


AGG_DIST = ROOT / "data" / "parquet" / "agregados"


@pytest.mark.skipif(not (AGG_DIST / "manifest.json").exists(),
                    reason="agregados pré-calculados não distribuídos")
def test_agregados_distribuidos_conferem_com_os_parquet():
    """Falha se os Parquet ou aggregates.py mudarem sem reexportar os agregados."""
    from dataurnas.dashboard import aggregates as agg

    files = agg.input_files(ROOT / "data" / "parquet")
    if not files:
        pytest.skip("Parquet de 2022 ausentes")
    manifest, motivo = agg.check_manifest(AGG_DIST, agg.input_fingerprint(files))
    assert manifest is not None, (
        f"{motivo}: rode python scripts/build_db.py --no-live "
        "--exportar-agregados data/parquet/agregados")
    for info in manifest["tabelas"].values():
        assert (AGG_DIST / info["arquivo"]).stat().st_size < 50_000_000


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
