from datetime import datetime

from dataurnas.models import LogEntry


def _entry(data="02/10/2022", hora="07:00:05"):
    return LogEntry(data=data, hora=hora, severidade="INFO", id_urna="1",
                    aplicativo="VOTA", descricao="x")


def test_timestamp_usa_formato_do_log():
    assert _entry().timestamp == datetime(2022, 10, 2, 7, 0, 5)


def test_timestamp_invalido_retorna_none():
    assert _entry(data="2022-10-02").timestamp is None
    assert _entry(hora="25:00:00").timestamp is None
