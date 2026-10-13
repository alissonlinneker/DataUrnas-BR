from conftest import default_log_lines, log_line, make_log_7z

from dataurnas.parsers import log as log_module
from dataurnas.parsers.log import LogParser


def test_parse_log_7z(tmp_path):
    path = make_log_7z(tmp_path / "a.logjez", default_log_lines(votos=3) + ["lixo sem formato"])
    entries = LogParser().parse(path)
    assert len(entries) == 7
    assert entries[0].data == "02/10/2022"
    assert entries[0].timestamp is not None


def test_extract_events_basico(tmp_path):
    parser = LogParser()
    entries = parser.parse(make_log_7z(tmp_path / "a.logjez", default_log_lines(votos=4)))
    ev = parser.extract_events(entries)
    assert ev["modelo"] == "2020"
    assert ev["abertura"].hora == "07:00:05"
    assert ev["encerramento"].hora == "16:00:30"
    assert ev["votos_computados"] == 4
    assert ev["reboots"] == 0


def test_filtro_turno_date_remove_eventos_do_t1(tmp_path):
    lines = default_log_lines(votos=2) + default_log_lines(data="30/10/2022", votos=3)
    parser = LogParser()
    entries = parser.parse(make_log_7z(tmp_path / "t2.logjez", lines))

    sem_filtro = parser.extract_events(entries)
    assert sem_filtro["reboots"] == 1  # falso reboot

    ev = parser.extract_events(entries, turno_date="30/10/2022")
    assert ev["reboots"] == 0
    assert ev["votos_computados"] == 3
    assert ev["abertura"].data == "30/10/2022"


def test_reboot_e_encerramento_ultimo(tmp_path):
    d = "02/10/2022"
    lines = [
        log_line(d, "07:00:00", "Urna pronta para receber votos"),
        log_line(d, "09:00:00", "Urna pronta para receber votos"),
        log_line(d, "17:00:00", "Início do Encerramento"),
        log_line(d, "17:05:00", "Início do Encerramento"),
    ]
    parser = LogParser()
    ev = parser.extract_events(parser.parse(make_log_7z(tmp_path / "r.logjez", lines)))
    assert ev["reboots"] == 1
    assert ev["abertura"].hora == "07:00:00"
    assert ev["encerramento"].hora == "17:05:00"


def test_log_acima_do_limite_e_recusado(tmp_path, monkeypatch):
    monkeypatch.setattr(log_module, "MAX_LOG_BYTES", 10)
    path = make_log_7z(tmp_path / "big.logjez", default_log_lines(votos=5))
    assert LogParser().parse(path) == []


def test_arquivo_invalido_retorna_vazio(tmp_path):
    path = tmp_path / "x.logjez"
    path.write_bytes(b"nao e 7z")
    assert LogParser().parse(path) == []
