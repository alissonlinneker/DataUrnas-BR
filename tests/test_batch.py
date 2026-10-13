from conftest import make_bu_bytes

from dataurnas.analyzer.batch import BatchAnalyzer


def test_find_e_locate(raw_tree):
    an = BatchAnalyzer(raw_dir=raw_tree)
    assert len(an.find_bu_files()) == 3
    secs = an.find_sections()
    assert len(secs) == 2 and secs == sorted(secs)
    loc = an.locate(secs[0])
    assert loc == {"uf": "am", "municipio": "02291", "zona": "0005", "secao": "0010"}


def test_locate_com_raw_no_caminho_pai(tmp_path):
    # Um diretório "raw" acima de raw_dir não pode confundir a extração
    base = tmp_path / "raw" / "x" / "data" / "raw"
    sec = base / "sp" / "1" / "2" / "3"
    sec.mkdir(parents=True)
    loc = BatchAnalyzer(raw_dir=base).locate(sec)
    assert loc == {"uf": "sp", "municipio": "1", "zona": "2", "secao": "3"}


def test_secao_id_e_pleito(raw_tree):
    an = BatchAnalyzer(raw_dir=raw_tree)
    ids = sorted(an.secao_id_for(f) for f in an.find_bu_files())
    assert ids == ["1T/am/02291/0005/0010", "1T/sp/71072/0001/0001", "2T/am/02291/0005/0010"]
    assert BatchAnalyzer.pleito_to_turno("") == 1


def test_pleito_desconhecido_avisa(caplog):
    assert BatchAnalyzer.pleito_to_turno("999") == 1
    assert "desconhecido" in caplog.text


def test_analyze_section_t2_filtra_log_do_t1(raw_tree):
    an = BatchAnalyzer(raw_dir=raw_tree)
    sec = raw_tree / "am" / "02291" / "0005" / "0010"
    res = an.analyze_section(sec, bu_file=sec / "o00407-0229100050010.bu")
    assert res["turno"] == 2
    assert res["log_events"]["reboots"] == 0
    assert res["log_timing"]["hora_abertura"].startswith("30/10/2022")
    assert res["modelo"] == "2020"
    # Eirunepé (UTC-5): abertura às 07:00 locais = 09:00 de Brasília -> A04
    assert "A04" in {i.codigo for i in res["issues"]}
    assert all(i.uf == "am" and i.secao == "0010" for i in res["issues"])


def test_bu_invalido_vira_issue_e02(raw_tree):
    sec = raw_tree / "sp" / "71072" / "0001" / "0001"
    bu = sec / "o00406-7107200010001.bu"
    bu.write_bytes(b"\x00\x01lixo")
    res = BatchAnalyzer(raw_dir=raw_tree).analyze_section(sec, bu_file=bu)
    assert res["bu_obj"] is None
    assert [i.codigo for i in res["issues"]] == ["E02"]


def test_analyze_all_agrega_por_turno(raw_tree, capsys):
    an = BatchAnalyzer(raw_dir=raw_tree)
    res = an.analyze_all()
    assert res["total_secoes"] == 3
    cand = res["votacao"]["votos_por_candidato"]
    assert cand[1]["BR"]["Presidente"][0]["votos"] == 240  # 120 + 120
    assert cand[2]["BR"]["Presidente"][0]["votos"] == 130
    assert cand[1]["am"]["Governador"][0]["votos"] == 150
    assert cand[1]["sp"]["Governador"][0]["votos"] == 150
    an.print_report(res)
    out = capsys.readouterr().out
    assert "Presidente (1o turno)" in out and "Presidente (2o turno)" in out


def test_verify_hashes_opcional(raw_tree, monkeypatch):
    from dataurnas.analyzer.integrity import IntegrityAnalyzer

    chamadas = []
    monkeypatch.setattr(IntegrityAnalyzer, "verify_section_hashes",
                        lambda self, d: chamadas.append(d) or [])
    sec = raw_tree / "sp" / "71072" / "0001" / "0001"
    BatchAnalyzer(raw_dir=raw_tree).analyze_section(sec)
    assert chamadas == []
    BatchAnalyzer(raw_dir=raw_tree, verify_hashes=True).analyze_section(sec)
    assert chamadas == [sec]


def test_fixture_reutilizavel():
    assert make_bu_bytes()[:1] == b"\x30"
