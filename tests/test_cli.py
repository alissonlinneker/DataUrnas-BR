import pytest
from click.testing import CliRunner

from dataurnas import __version__, cli


@pytest.fixture
def runner():
    return CliRunner()


def test_help(runner):
    res = runner.invoke(cli.main, ["--help"])
    assert res.exit_code == 0
    for cmd in ("download", "analyze", "db", "dashboard"):
        assert cmd in res.output


def test_version(runner):
    res = runner.invoke(cli.main, ["--version"])
    assert res.exit_code == 0
    assert res.output.strip() == f"dataurnas {__version__}"


def test_uf_invalida_e_rejeitada(runner):
    res = runner.invoke(cli.main, ["download", "state", "xx"])
    assert res.exit_code != 0
    assert "xx" in res.output


def test_analyze_bu(runner, tmp_path, bu_bytes):
    path = tmp_path / "o00406-1.bu"
    path.write_bytes(bu_bytes)
    res = runner.invoke(cli.main, ["analyze", "bu", str(path)])
    assert res.exit_code == 0, res.output
    assert "Presidente" in res.output
    assert "Nenhuma inconsistência detectada." in res.output


def test_analyze_section(runner, raw_tree):
    sec = raw_tree / "am" / "02291" / "0005" / "0010"
    res = runner.invoke(cli.main, ["analyze", "section", str(sec), "--no-hashes"])
    assert res.exit_code == 0, res.output
    assert "1º turno" in res.output and "2º turno" in res.output


def test_analyze_batch_grava_json(runner, raw_tree, tmp_path, monkeypatch):
    from dataurnas.analyzer import batch

    monkeypatch.setattr(batch.BatchAnalyzer.__init__, "__defaults__", (raw_tree, False))
    out = tmp_path / "rel.json"
    res = runner.invoke(cli.main, ["analyze", "batch", "-o", str(out)])
    assert res.exit_code == 0, res.output
    assert out.read_text(encoding="utf-8").startswith("{")


def test_db_stats_sem_banco(runner, tmp_path, monkeypatch):
    from dataurnas.database import duckdb_store

    monkeypatch.setattr(duckdb_store, "DEFAULT_DB_PATH", tmp_path / "nao.duckdb")
    res = runner.invoke(cli.main, ["db", "stats"])
    assert res.exit_code == 0
    assert "Banco não encontrado" in res.output


def test_db_stats_somente_leitura(runner, tmp_path, raw_tree, monkeypatch):
    from dataurnas.database import duckdb_store

    path = tmp_path / "s.duckdb"
    with duckdb_store.DuckDBStore(path) as s:
        s.build_from_raw(raw_dir=raw_tree)
    monkeypatch.setattr(duckdb_store, "DEFAULT_DB_PATH", path)
    res = runner.invoke(cli.main, ["db", "stats"])
    assert res.exit_code == 0, res.output
    assert "Total de seções: 3" in res.output
