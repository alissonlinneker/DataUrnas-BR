"""Testes das funções puras de coleta da eleição de 2026 (sem rede)."""

from pathlib import Path

import pytest

from dataurnas.downloader import ele2026 as E

FIX = Path(__file__).parent / "fixtures"


def _resultado_fake():
    return {
        "ele": "6257", "dt": "05/10/2026", "ht": "12:51:05",
        "s": {"ts": "10", "st": "10", "snt": "0", "si": "9", "sni": "1"},
        "e": {"te": "1000", "est": "1000", "c": "800", "a": "200",
              "pc": "80,00", "pcn": "80", "pa": "20,00", "pan": "20"},
        "v": {"tv": "800", "vv": "760", "vnom": "760", "van": "0", "vb": "10",
              "vn": "28", "vnt": "2", "tvn": "30", "vansj": "0",
              "pvb": "1,25", "pvbn": "1,25", "ptvn": "3,75", "ptvnn": "3,75"},
        "carg": [{
            "cd": "1",
            "agr": [
                {"n": "1", "nm": "COLIGACAO A", "tp": "c", "com": "AAA / BBB",
                 "par": [{"n": "13", "sg": "AAA", "nm": "PARTIDO A", "nfed": "101",
                          "cand": [{"n": "13", "sqcand": "1", "nm": "FULANO DE TAL",
                                    "nmu": "FULANO", "dt": "01/01/1950", "dvt": "Válido",
                                    "seq": "2", "e": "s", "st": "2º turno",
                                    "vap": "400", "pvap": "52,63", "pvapn": "52,631578947",
                                    "vs": [{"tp": "v", "sqcand": "2", "nm": "VICE A",
                                            "nmu": "VICE", "sgp": "BBB"}]}]}]},
                {"n": "2", "nm": "PARTIDO B", "tp": "i", "com": "CCC",
                 "par": [{"n": "22", "sg": "CCC", "nm": "PARTIDO B", "nfed": "",
                          "cand": [{"n": "22", "sqcand": "3", "nm": "BELTRANO",
                                    "nmu": "BELTRANO", "seq": "1", "e": "n",
                                    "st": "Não eleito", "vap": "360", "pvap": "47,37",
                                    "vs": []}]}]},
            ],
        }],
    }


def test_conversoes_numericas():
    assert E.to_int("302807") == 302807
    assert E.to_int("") is None
    assert E.to_int(None) is None
    assert E.to_int("abc") is None
    assert E.to_float_br("47,03") == pytest.approx(47.03)
    assert E.to_float_br("64,555307782") == pytest.approx(64.555307782)
    assert E.to_float_br("100") == 100.0
    assert E.to_float_br("") is None


def test_urls():
    assert E.url_resultado("br").endswith("/ele2026/6257/dados/br/br-c0001-e006257-u.json")
    assert E.url_resultado("AC01120").endswith("/dados/ac/ac01120-c0001-e006257-u.json")
    assert E.url_municipios().endswith("/ele2026/6257/config/mun-e006257-cm.json")
    assert E.url_secoes_uf("zz").endswith("/arquivo-urna/3220/config/zz/zz-p003220-cs.json")
    assert E.url_aux("ac", "01066", "0004", "0077").endswith(
        "/dados/ac/01066/0004/0077/p003220-ac-m01066-z0004-s0077-aux.json")
    assert E.url_arquivo("ac", "01066", "0004", "0077", "abc", "x-bu.dat").endswith(
        "/dados/ac/01066/0004/0077/abc/x-bu.dat")


def test_parse_candidatos_ordena_e_achata():
    rows = E.parse_candidatos(_resultado_fake())
    assert [r["numero"] for r in rows] == [13, 22]
    a = rows[0]
    assert a["nome_urna"] == "FULANO"
    assert a["partido_sigla"] == "AAA"
    assert a["federacao_numero"] == 101
    assert a["agremiacao_tipo"] == "coligacao"
    assert a["vice_nome_urna"] == "VICE"
    assert a["vice_partido"] == "BBB"
    assert a["votos"] == 400
    assert a["pct_validos"] == pytest.approx(52.631578947)
    assert a["eleito"] is True
    b = rows[1]
    assert b["vice_nome"] is None
    assert b["federacao_numero"] is None
    assert b["agremiacao_tipo"] == "isolado"


def test_parse_totais():
    t = E.parse_totais(_resultado_fake())
    assert t["eleitorado"] == 1000
    assert t["comparecimento"] == 800
    assert t["abstencao"] == 200
    assert t["votos_validos"] == 760
    assert t["votos_brancos"] == 10
    assert t["votos_nulos"] == 28
    assert t["votos_nulos_tecnicos"] == 2
    assert t["votos_nulos_total"] == 30
    assert t["secoes_instaladas"] == 9
    assert t["pct_comparecimento"] == 80.0


def test_resultado_row_inclui_zero_para_ausente():
    row = E.resultado_row(_resultado_fake(), [13, 22, 99], uf="ac")
    assert row["uf"] == "ac"
    assert (row["v_13"], row["v_22"], row["v_99"]) == (400, 360, 0)
    assert row["v_13"] + row["v_22"] == row["votos_validos"]


def test_iter_municipios():
    cm = {"abr": [{"cd": "AC", "mu": [{"cd": "01120", "cdi": "1200013", "nm": "ACRELÂNDIA",
                                        "c": "n", "z": ["0008"]}]},
                  {"cd": "zz", "mu": [{"cd": "29254", "cdi": "", "nm": "ABIDJÃ",
                                        "c": "n", "z": ["0001"]}]}]}
    ms = list(E.iter_municipios(cm))
    assert ms[0] == {"uf": "ac", "cd_mun": "01120", "cd_ibge": "1200013",
                     "nome": "ACRELÂNDIA", "capital": False, "zonas": "0008"}
    assert ms[1]["cd_ibge"] is None


def test_iter_secoes_cs_marca_agregadas():
    cs = {"abr": [{"cd": "ac", "mu": [{"cd": "01074", "nm": "CRUZEIRO DO SUL", "zon": [
        {"cd": "0004", "sec": [{"ns": "0229", "nsa": ["0270"]},
                               {"ns": "0270", "nsp": "0229"},
                               {"ns": "0001", "da": "04/10/2026"}]}]}]}]}
    secs = list(E.iter_secoes_cs(cs))
    assert len(secs) == 3
    assert secs[0]["secoes_agregadas"] == "0270"
    assert secs[1]["secao_principal"] == "0229"
    assert secs[2]["secao_principal"] is None
    assert E.secao_key("AC", "01074", "0004", "0001") == "ac/01074/0004/0001"


def test_escolher_hash_prefere_totalizado():
    aux = {"st": "Totalizada", "hashes": [
        {"hash": "0", "st": "Excluído"},
        {"hash": "aaa", "st": "Recebido", "dr": "04/10/2026", "hr": "18:00:00",
         "arq": [{"nm": "x-bu.dat", "tp": "bu"}]},
        {"hash": "bbb", "st": "Totalizado", "dr": "04/10/2026", "hr": "18:34:08",
         "arq": [{"nm": "o-bu.dat", "tp": "bu"}, {"nm": "o-vota.vsc", "tp": "vota"}]},
    ]}
    h = E.escolher_hash(aux)
    assert h["hash"] == "bbb"
    assert h["arquivos"] == {"bu": "o-bu.dat", "vota": "o-vota.vsc"}
    assert h["n_hashes"] == 2
    assert h["hr_recebimento"] == "18:34:08"


def test_escolher_hash_busa_e_vazio():
    aux = {"hashes": [{"hash": "c", "st": "Totalizado", "arq": [
        {"nm": "s-busa.dat", "tp": "busa"}, {"nm": "s-sa.vsc", "tp": "sa"}]}]}
    assert E.escolher_hash(aux)["arquivos"] == {"busa": "s-busa.dat", "sa": "s-sa.vsc"}
    assert E.escolher_hash({"hashes": []}) is None
    assert E.escolher_hash({"hashes": [{"hash": "0"}]}) is None
    v1 = {"hashes": [{"hash": "d", "st": "Totalizado", "nmarq": ["a.bu", "a.vscmr"]}]}
    assert E.escolher_hash(v1)["arquivos"] == {"bu": "a.bu", "vota": "a.vscmr"}


def _tlv(tag: int, content: bytes) -> bytes:
    n = len(content)
    if n < 0x80:
        return bytes([tag, n]) + content
    ln = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return bytes([tag, 0x80 | len(ln)]) + ln + content


def test_modelo_from_vsc_formato_2026_no_final():
    sw = _tlv(0x30, b"\x1b\x0f20261004T154502" + b"\x00" * 300)
    hw = _tlv(0x30, b"\x1b\x0f20261004T154502" + b"\x01" * 50)
    tail = bytes.fromhex("30060a01160a0104")  # UE2022, eddsa
    assert E.modelo_from_vsc(_tlv(0x30, sw + hw + tail)) == 22


def test_modelo_from_vsc_formato_spec_v2_no_inicio():
    raw = _tlv(0x30, bytes.fromhex("0a0114") + _tlv(0x30, b"\x00" * 10)
               + _tlv(0x30, b"\x00" * 10))
    assert E.modelo_from_vsc(raw) == 20


def test_modelo_from_vsc_invalido():
    assert E.modelo_from_vsc(b"") is None
    assert E.modelo_from_vsc(b"\x04\x02ab") is None


def test_bu_to_rows_com_bu_real_de_2026():
    raw = (FIX / "bu_ac_m01066_z0004_s0077.bin").read_bytes()
    sec, votos = E.bu_to_rows(raw)
    assert sec["spec_version"] == "v2"
    assert (sec["municipio_bu"], sec["zona_bu"], sec["secao_bu"]) == (1066, 4, 77)
    assert sec["tem_presidente"] is True
    assert sec["aptos"] == 289
    assert sec["comparecimento"] == 234
    assert sec["comparecimento_bu"] == 234
    assert sec["votos_total"] == 234
    assert sec["votos_brancos"] == 4
    assert sec["votos_nulos"] == 13
    assert sec["votos_nominais"] == 217
    assert sec["tipo_urna"] == "secao"
    assert sec["hora_abertura"] == "20261004T060652"
    por_num = {v["numero"]: v["votos"] for v in votos if v["tipo_voto"] == "nominal"}
    assert por_num == {13: 99, 14: 4, 22: 103, 55: 5, 70: 6}
    assert sum(v["votos"] for v in votos) == sec["comparecimento"]


def test_bu_to_rows_eleicao_inexistente_nao_gera_votos():
    raw = (FIX / "bu_ac_m01066_z0004_s0077.bin").read_bytes()
    sec, votos = E.bu_to_rows(raw, eleicao=1)
    assert votos == []
    assert sec["tem_presidente"] is False
