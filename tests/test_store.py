import pytest

from dataurnas.analyzer.batch import BatchAnalyzer
from dataurnas.database.duckdb_store import DuckDBStore
from dataurnas.database.rows import SECOES_COLUMNS, extract_rows


@pytest.fixture
def store(tmp_path):
    s = DuckDBStore(tmp_path / "db" / "t.duckdb")
    yield s
    s.close()


def _counts(store):
    return {
        t: store.query(f"SELECT COUNT(*) AS n FROM {t}")[0]["n"]
        for t in ("secoes", "votos", "issues", "totais_cargo")
    }


def test_build_from_raw(store, raw_tree):
    assert store.build_from_raw(raw_dir=raw_tree, batch_size=2) == 3
    c = _counts(store)
    assert c["secoes"] == 3
    assert c["votos"] == 8 + 8 + 4
    assert c["totais_cargo"] == 2 + 2 + 1
    row = store.query("SELECT * FROM secoes WHERE id = '2T/am/02291/0005/0010'")[0]
    assert row["turno"] == 2
    assert row["fuso_offset"] == -2  # Eirunepé
    assert row["regiao"] == "norte"
    assert row["reboots"] == 0
    assert row["comparecimento"] == 235


def test_reprocessar_e_idempotente(store, raw_tree):
    store.build_from_raw(raw_dir=raw_tree)
    antes = _counts(store)
    an = BatchAnalyzer(raw_dir=raw_tree)
    for bu in an.find_bu_files():
        store._process_section(an, bu.parent, bu_file=bu)
    rows = [extract_rows(an.analyze_section(b.parent, bu_file=b)) for b in an.find_bu_files()]
    store.insert_rows(rows + rows)  # duplicado no mesmo lote
    assert _counts(store) == antes


def test_incremental_pula_existentes(store, raw_tree, monkeypatch):
    store.build_from_raw(raw_dir=raw_tree)
    chamadas = []
    original = BatchAnalyzer.analyze_section

    def espiao(self, section_dir, bu_file=None):
        chamadas.append(bu_file)
        return original(self, section_dir, bu_file=bu_file)

    monkeypatch.setattr(BatchAnalyzer, "analyze_section", espiao)
    assert store.build_incremental(raw_dir=raw_tree) == 3
    assert chamadas == []  # nada reparseado


def test_lote_com_erro_e_desfeito(store, raw_tree):
    an = BatchAnalyzer(raw_dir=raw_tree)
    rows = [extract_rows(an.analyze_section(b.parent, bu_file=b)) for b in an.find_bu_files()]
    rows[-1].votos.append(["x"])  # linha inválida
    with pytest.raises(Exception):  # noqa: B017
        store.insert_rows(rows)
    assert _counts(store)["secoes"] == 0


def test_summary_e_filtros(store, raw_tree):
    store.build_from_raw(raw_dir=raw_tree)
    s = store.get_summary()
    assert s["total_secoes"] == 3
    assert s["ufs"] == 2
    assert s["secoes_ok"] + s["secoes_com_issues"] == 3
    assert s["total_eleitores"] == 900
    opts = store.get_filter_options()
    assert opts["turnos"] == [1, 2]
    assert opts["ufs"] == ["am", "sp"]
    df = store.query_df("SELECT * FROM secoes WHERE uf = ?", ["sp"])
    assert len(df) == 1


def test_read_only(tmp_path, raw_tree):
    path = tmp_path / "ro.duckdb"
    with DuckDBStore(path) as s:
        s.build_from_raw(raw_dir=raw_tree)
    with DuckDBStore(path, read_only=True) as ro:
        assert ro.get_summary()["total_secoes"] == 3


def test_colunas_alinhadas_ao_schema(store):
    cols = [r["column_name"] for r in store.query(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'secoes' ORDER BY ordinal_position")]
    assert tuple(cols) == SECOES_COLUMNS
