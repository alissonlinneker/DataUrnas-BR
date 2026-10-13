from conftest import log_line, make_log_7z

from dataurnas.analyzer.log_analyzer import LogAnalyzer, _parse_time


def _analisar(tmp_path, lines, **kw):
    path = make_log_7z(tmp_path / "a.logjez", lines)
    return LogAnalyzer().analyze_log(path, **kw)


def _codigos(res):
    return {i.codigo for i in res["issues"]}


def _log_votacao(abertura, encerramento, data="02/10/2022", data_enc=None):
    return [
        log_line(data, abertura, "Urna pronta para receber votos"),
        log_line(data_enc or data, encerramento, "Início do Encerramento"),
    ]


def test_parse_time_considera_segundos():
    assert _parse_time("07:30:30") == 7 * 60 + 30.5
    assert _parse_time("07:30") == 450


def test_oeste_do_amazonas_usa_utc5(tmp_path):
    # Eirunepé: 8h-17h de Brasília = 6h-15h locais
    lines = _log_votacao("05:40:00", "15:05:00")
    correto = _analisar(tmp_path, lines, uf="am", municipio="02291")
    assert not _codigos(correto) & {"M01", "A04", "A05"}
    assert correto["issues"] == []

    # Com o fuso da UF (UTC-4) os mesmos horários gerariam falsos alertas
    errado = _analisar(tmp_path, lines, uf="am", municipio="02550")
    assert {"M01", "A05"} <= _codigos(errado)


def test_fernando_de_noronha(tmp_path):
    lines = _log_votacao("08:40:00", "18:05:00")
    res = _analisar(tmp_path, lines, uf="pe", municipio="30015")
    assert res["issues"] == []
    fuso_uf = _analisar(tmp_path, lines, uf="pe", municipio="25313")
    assert "A04" in _codigos(fuso_uf)


def test_duracao_usa_data_e_segundos(tmp_path):
    res = _analisar(tmp_path, _log_votacao("07:00:50", "17:00:10"), uf="sp")
    # 9h59min20s: o cálculo antigo (só HH:MM) dava 600
    assert res["timing"]["duracao_votacao_min"] == 599
    assert res["timing"]["hora_abertura"] == "02/10/2022 07:00:50"


def test_duracao_atravessando_meia_noite(tmp_path):
    lines = _log_votacao("23:30:00", "00:30:00", data_enc="03/10/2022")
    res = _analisar(tmp_path, lines, uf="sp")
    assert res["timing"]["duracao_votacao_min"] == 60


def test_duracao_negativa_vira_issue_e03(tmp_path):
    lines = [
        log_line("02/10/2022", "17:00:00", "Início do Encerramento"),
        log_line("02/10/2022", "18:00:00", "Urna pronta para receber votos"),
    ]
    res = _analisar(tmp_path, lines, uf="sp")
    assert res["timing"]["duracao_votacao_min"] is None
    assert "E03" in _codigos(res)


def test_hora_malformada_registra_aviso(tmp_path, caplog):
    analyzer = LogAnalyzer()

    class _E:
        data = "02/10/2022"
        hora = "xx:yy"

    issues = analyzer._check_timing({"abertura": _E()}, uf="sp")
    assert issues == []
    assert "malformada" in caplog.text


def test_votos_log_vs_bu(tmp_path, bu_bytes):
    from dataurnas.parsers.bu import BUParser

    bu_path = tmp_path / "o00406-1.bu"
    bu_path.write_bytes(bu_bytes)
    bu = BUParser().parse(bu_path)  # comparecimento 235
    lines = _log_votacao("07:00:00", "17:00:00")
    lines += [log_line("02/10/2022", "10:00:00", "O voto do eleitor foi computado")] * 200
    res = _analisar(tmp_path, lines, uf="sp", bu=bu)
    assert "A03" in _codigos(res)
