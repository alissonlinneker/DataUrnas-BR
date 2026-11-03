"""Logs do GEDAI-UE no 2º turno de 2026 (gedai_t2.py), com amostras sintéticas."""

from __future__ import annotations

import importlib.util
import io
import json
import zipfile
from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

RAIZ = Path(__file__).resolve().parents[2]
BU_FIX = Path(__file__).parent / "fixtures" / "bu_ac_m01066_z0004_s0077.bin"


@pytest.fixture(scope="module")
def g():
    p = RAIZ / "scripts" / "ele2026" / "gedai_t2.py"
    spec = importlib.util.spec_from_file_location("gedai_t2", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Amostras sintéticas
# ---------------------------------------------------------------------------

COMP, TPM, INST = "ZXX001STD01", "ABCDEF0123456789ABCD", "0A1B2C3D"


def _linha(dt: str, msg: str, nivel: str = "INFO", h: str = "00AA11BB22CC33DD") -> str:
    return f"{dt}\t{nivel}\t{msg}\t{h}"


LOG_24 = [
    _linha("16/09/2026 10:00:00", "Abertura do GEDAI-UE - Versão 8.23.0.0 - Teste"),
    _linha("16/09/2026 10:00:01", "Pleito corrente: 03220 - 1° Turno"),
    _linha("16/09/2026 10:05:00", "Mídia de carga gerada. NS:AABBCCDD Z:0001 | Seções (M:12345) "
           "1 2 3"),
    _linha("20/09/2026 11:00:00", "Recebida correspondência de seção: município 12345, zona 0001, "
           "seção 0001, carga 111111111111111111111111, id urna 02000001, mc AABBCCDD."),
    _linha("20/09/2026 11:00:01", "Recebida correspondência de contingência: município 12345, "
           "zona 0001, carga 222222222222222222222222, id urna 02000002, mc AABBCCDD."),
    _linha("20/09/2026 11:01:00", "Transmitida a correspondência de seção: município 12345, "
           "zona 0001, seção 0001, carga 111111111111111111111111, id urna 02000001, "
           "mc AABBCCDD."),
    _linha("20/09/2026 11:02:00", "Fechamento do GEDAI-UE"),
    _linha("24/10/2026 09:00:00", "Abertura do GEDAI-UE - Versão 8.23.0.0 - Teste"),
    _linha("24/10/2026 09:00:01", "Pleito corrente: 03221 - 2° Turno"),
    _linha("24/10/2026 09:30:00", "Recebida correspondência de seção: município 12345, zona 0001, "
           "seção 0002, carga 333333333333333333333333, id urna 02000003, mc AABBCCDD."),
]
LOG_25_EXTRA = [
    _linha("25/10/2026 08:00:00", "Recebida correspondência de seção: município 12345, zona 0001, "
           "seção 0003, carga 444444444444444444444444, id urna 02000004, mc AABBCCDD."),
    _linha("25/10/2026 18:10:00", "Fechamento do GEDAI-UE"),
]


def _texto(linhas: list[str]) -> bytes:
    return ("\r\n".join(linhas) + "\r\n").encode("latin-1")


def _zip_bytes(entradas: dict[str, bytes], dt=(2026, 10, 24, 13, 0, 0)) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for nome, conteudo in entradas.items():
            info = zipfile.ZipInfo(nome, date_time=dt)
            z.writestr(info, conteudo)
    return buf.getvalue()


def _estacao(log: bytes, uf: str = "xx", pleito: str = "03221", comp: str = COMP,
             dt=(2026, 10, 24, 13, 0, 0)) -> tuple[str, bytes]:
    interno = _zip_bytes({"gedai-ue.log": log}, dt)
    meio = _zip_bytes({f"gedai-ue-{uf}-oficial-{comp}-log.jez": interno,
                       f"gedai-ue-{uf}-oficial-{comp}-log.vsc": b"0\x82assinatura"}, dt)
    return f"gedai-ue-{uf}-{pleito}-oficial-{comp}-{TPM}-{INST}-log.jez", meio


def _pacote(pasta: Path, nome: str, estacoes: list[tuple[str, bytes]],
            dt=(2026, 10, 24, 16, 0, 0)) -> Path:
    pasta.mkdir(parents=True, exist_ok=True)
    p = pasta / nome
    with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(zipfile.ZipInfo("leiame.pdf", date_time=(2024, 10, 5, 14, 9, 6)), b"%PDF")
        for n, c in estacoes:
            z.writestr(zipfile.ZipInfo(n, date_time=dt), c)
    return p


# ---------------------------------------------------------------------------
# Nomes e linhas
# ---------------------------------------------------------------------------

def test_nome_pacote(g):
    r = g.parse_nome_pacote("log_gedai_2t_BA_251020261327.zip")
    assert r["turno"] == "2t" and r["uf"] == "ba" and r["pacote"] == "2t_251020261327"
    assert r["gerado_em"] == datetime(2026, 10, 25, 13, 27)
    assert g.parse_nome_pacote("outro.zip") is None


def test_nome_log(g):
    r = g.parse_nome_log("gedai-ue-ac-03221-oficial-ZAC001STD25-29B7B62AF8A49BD65FD3-"
                         "5372FFE5-log.jez")
    assert r == {"uf": "ac", "pleito_arquivo": "03221", "computador": "ZAC001STD25",
                 "serial_tpm": "29B7B62AF8A49BD65FD3", "serial_instalacao": "5372FFE5"}
    assert g.parse_nome_log("leiame.pdf") is None


def test_tipo_evento(g):
    assert g.tipo_evento("Transmitida a correspondência de contingência: município 1, zona 2, "
                         "carga 3, id urna 4, mc AB.") == "correspondencia_transmitida_contingencia"
    assert g.tipo_evento("Mídia de carga gerada. NS:AA Z:0001") == "midia_carga_gerada"
    assert g.tipo_evento("Algo com 123 e ABCDEF12").startswith("outro:Algo com N e H")


def test_eventos_do_log(g):
    texto = _texto(LOG_24).decode("latin-1")
    corr, midias, cont, meta = g.eventos_do_log(texto, {"pacote": "p", "uf": "xx"})
    assert meta["n_linhas"] == len(LOG_24)
    assert meta["primeira_data_hora"] == datetime(2026, 9, 16, 10, 0)
    assert meta["ultima_data_hora"] == datetime(2026, 10, 24, 9, 30)
    assert len(corr) == 4
    rec = corr[0]
    assert rec["acao"] == "recebida" and rec["tipo"] == "secao"
    assert (rec["cd_mun"], rec["zona"], rec["secao"]) == ("12345", "0001", "0001")
    assert rec["codigo_carga"] == "111111111111111111111111"
    assert rec["numero_interno_urna"] == 2000001 and rec["mc"] == "AABBCCDD"
    assert rec["pleito_corrente"] == "03220"
    cont_ = corr[1]
    assert cont_["tipo"] == "contingencia" and cont_["secao"] is None
    assert corr[2]["acao"] == "transmitida"
    assert corr[3]["pleito_corrente"] == "03221"
    assert len(midias) == 1
    assert midias[0]["ns"] == "AABBCCDD" and midias[0]["cd_mun"] == "12345"
    assert midias[0]["secoes"] == "0001 0002 0003" and midias[0]["n_secoes"] == 3
    assert cont[("2026-09-20", "INFO", "correspondencia_recebida_secao")] == 1


def test_linhas_fora_do_formato_sao_ignoradas(g):
    texto = "linha solta\r\n" + _linha("xx/yy/zzzz 00:00:00", "Recebida") + "\r\n"
    corr, midias, cont, meta = g.eventos_do_log(texto, {})
    assert corr == [] and midias == [] and meta["n_linhas"] == 0


# ---------------------------------------------------------------------------
# Zips aninhados e comparação de versões
# ---------------------------------------------------------------------------

def test_processar_pacote(g, tmp_path):
    p = _pacote(tmp_path / "2t", "log_gedai_2t_XX_241020261329.zip",
                [_estacao(_texto(LOG_24))])
    r = g.processar_pacote(str(p))
    assert r["outros_arquivos"] == ["leiame.pdf"]
    assert len(r["arquivos"]) == 1
    a = r["arquivos"][0]
    assert a["computador"] == COMP and a["serial_tpm"] == TPM and a["tem_vsc"]
    assert a["erro"] is None and a["entrada_dt"] == datetime(2026, 10, 24, 16, 0)
    assert a["interno_dt"] == datetime(2026, 10, 24, 13, 0)
    assert len(r["correspondencias"]) == 4 and len(r["midias"]) == 1


def test_processar_pacote_com_jez_corrompido(g, tmp_path):
    nome = f"gedai-ue-xx-03221-oficial-{COMP}-{TPM}-{INST}-log.jez"
    p = _pacote(tmp_path, "log_gedai_2t_XX_241020261329.zip", [(nome, b"nao e zip")])
    r = g.processar_pacote(str(p))
    assert r["arquivos"][0]["erro"] is not None and r["correspondencias"] == []


def test_comparar_textos(g):
    a = "x\ny\n"
    assert g.comparar_textos(a, a)["status"] == "identico"
    r = g.comparar_textos(a, a + "z\n")
    assert r["status"] == "acrescimo" and r["linhas_novas"] == ["z"]
    r = g.comparar_textos(a + "w\n", a)
    assert r["status"] == "divergente" and r["linhas_removidas"] == 1
    assert g.comparar_textos(None, "q")["status"] == "so_novo"
    assert g.comparar_textos("q", None)["status"] == "so_antigo"


def test_extrair_compara_versoes(g, tmp_path):
    d24, d25 = tmp_path / "2t", tmp_path / "2t_2510"
    _pacote(d24, "log_gedai_2t_XX_241020261329.zip", [_estacao(_texto(LOG_24))])
    _pacote(d25, "log_gedai_2t_XX_251020261327.zip",
            [_estacao(_texto(LOG_24 + LOG_25_EXTRA), dt=(2026, 10, 25, 13, 0, 0)),
             _estacao(_texto(LOG_24[:2]), comp="ZXX002STD01")],
            dt=(2026, 10, 25, 16, 0, 0))
    saida = tmp_path / "saida"
    n = g.etapa_extrair([d24, d25], saida, workers=1)
    assert n["pacotes"] == 2
    diff = pd.read_parquet(saida / "diff_versoes.parquet")
    est = diff.drop_duplicates("computador").set_index("computador")["status"].to_dict()
    assert est == {COMP: "acrescimo", "ZXX002STD01": "so_novo"}
    novas = diff[(diff["computador"] == COMP) & (diff["n"] > 0)]
    assert novas["n"].sum() == 2
    assert set(novas["dia"]) == {"2026-10-25"}
    assert novas.loc[novas["apos_17h_2510"], "n"].sum() == 1
    pac = json.loads((saida / "pacotes.json").read_text())
    assert {p["pacote"] for p in pac} == {"2t_241020261329", "2t_251020261327"}


# ---------------------------------------------------------------------------
# BU e cruzamento
# ---------------------------------------------------------------------------

def test_carga_do_bu_invalido(g):
    assert g.carga_do_bu(b"\x00\x01")["bu_erro"]


@pytest.mark.skipif(not BU_FIX.exists(), reason="fixture de BU ausente")
def test_carga_do_bu_fixture(g):
    r = g.carga_do_bu(BU_FIX.read_bytes())
    assert r["bu_erro"] is None
    assert r["codigo_carga"] and len(r["codigo_carga"]) == 24
    assert isinstance(r["numero_interno_urna"], int)
    assert r["tipo_urna"] in {"secao", "reservaSecao"}
    assert r["qtd_codigos_carga"] >= 1


def _bus():
    base = dict(uf="xx", cd_mun="12345", zona="0001", tipo_urna="secao",
                ident_carga_tipo="identificacaoSecaoEleitoral", ident_carga_mun="12345",
                ident_carga_zona="0001", gerador_nome=COMP, gerador_serial_tpm=TPM,
                gerador_serial_instalacao=INST, ns_flash_carga="AABBCCDD",
                bu_erro=None)
    return pd.DataFrame([
        {**base, "secao": "0001", "codigo_carga": "111111111111111111111111",
         "numero_interno_urna": 2000001, "data_hora_carga": "20260920T103000",
         "ident_carga_secao": "0001", "historico_codigos_carga": "111111111111111111111111"},
        {**base, "secao": "0002", "codigo_carga": "222222222222222222222222",
         "numero_interno_urna": 2000002, "data_hora_carga": "20260920T104000",
         "tipo_urna": "reservaSecao", "ident_carga_tipo": "identificacaoContingencia",
         "ident_carga_secao": None,
         "historico_codigos_carga": "333333333333333333333333 222222222222222222222222"},
        {**base, "secao": "0009", "codigo_carga": "999999999999999999999999",
         "numero_interno_urna": 2000009, "data_hora_carga": "20261024T100000",
         "ident_carga_secao": "0009", "historico_codigos_carga": "999999999999999999999999"},
    ])


def _corr(g):
    linhas = _texto(LOG_24).decode("latin-1")
    corr, _m, _c, _meta = g.eventos_do_log(linhas, {
        "pacote": "2t_241020261329", "uf": "xx", "computador": COMP, "serial_tpm": TPM,
        "serial_instalacao": INST})
    return pd.DataFrame(corr)


def test_deduplicar_correspondencias(g):
    c = _corr(g)
    dup = pd.concat([c, c.assign(pacote="2t_251020261327")], ignore_index=True)
    u = g.deduplicar_correspondencias(dup)
    assert len(u) == len(c)
    assert set(u["n_pacotes"]) == {2}
    assert set(u["ultimo_pacote"]) == {"2t_251020261327"}


def test_cruzar_bus(g):
    corr = g.deduplicar_correspondencias(_corr(g))
    cargas = g.resumir_cargas_gedai(corr, pd.DataFrame())
    assert set(cargas["codigo_carga"]) == {"111111111111111111111111",
                                           "222222222222222222222222",
                                           "333333333333333333333333"}
    est = pd.DataFrame([{"computador": COMP, "serial_tpm": TPM, "serial_instalacao": INST}])
    x = g.cruzar_bus(_bus(), cargas, est).set_index("secao")
    assert x.loc["0001", "carga_no_gedai"] and x.loc["0001", "urna_confere"]
    assert x.loc["0001", "flash_confere"] and x.loc["0001", "secao_confere"]
    assert x.loc["0001", "minutos_carga_ate_recepcao"] == 30.0
    assert x.loc["0002", "tipo_confere"] and x.loc["0002", "mun_zona_confere"]
    assert x.loc["0002", "n_historico_fora_gedai"] == 0
    assert not x.loc["0009", "carga_no_gedai"]
    assert x.loc["0009", "urna_confere"] is None
    assert x.loc["0009", "historico_fora_gedai"] == "999999999999999999999999"
    assert x.loc["0009", "dia_carga_bu"] == "2026-10-24"
    assert x["gerador_no_gedai"].all()


def test_cargas_sem_bu(g):
    corr = g.deduplicar_correspondencias(_corr(g))
    cargas = g.resumir_cargas_gedai(corr, pd.DataFrame())
    cs = g.cargas_sem_bu(cargas, _bus()).set_index("codigo_carga")
    assert cs.loc["111111111111111111111111", "situacao"] == "usada_no_bu"
    assert cs.loc["333333333333333333333333", "situacao"] == "no_historico_do_bu"
    bus = _bus()
    bus = bus[bus["secao"] != "0002"]
    cs = g.cargas_sem_bu(cargas, bus).set_index("codigo_carga")
    assert cs.loc["333333333333333333333333", "situacao"] == "secao_sem_bu_coletado"
    bus2 = _bus().assign(secao=["0001", "0002", "0002"])
    bus2.loc[2, "codigo_carga"] = "555555555555555555555555"
    bus2.loc[2, "historico_codigos_carga"] = "555555555555555555555555"
    bus2.loc[1, "historico_codigos_carga"] = "222222222222222222222222"
    cs = g.cargas_sem_bu(cargas, bus2).set_index("codigo_carga")
    assert cs.loc["333333333333333333333333", "situacao"] == "secao_com_bu_de_outra_carga"


def test_etapa_cruzar_ponta_a_ponta(g, tmp_path):
    d24 = tmp_path / "2t"
    _pacote(d24, "log_gedai_2t_XX_241020261329.zip", [_estacao(_texto(LOG_24))])
    saida = tmp_path / "saida"
    g.etapa_extrair([d24], saida, workers=1)
    _bus().to_parquet(saida / "bus_carga.parquet", index=False)
    enc = pd.DataFrame([{"uf": "xx", "cd_mun": "12345", "zona": "0001", "secao": "0009",
                         "minutos_apos_17h_bsb": 45.0, "encerramento_bsb": "2026-10-25 17:45"}])
    enc.to_parquet(tmp_path / "enc.parquet", index=False)
    r = g.etapa_cruzar(saida, tmp_path / "enc.parquet")
    assert r == {"secoes_cruzadas": 3, "carga_fora_gedai": 1}
    resumo = json.loads((saida / "resumo.json").read_text())
    assert resumo["cruzamento"]["carga_fora_gedai_por_uf"] == {"xx": 1}
    assert resumo["tardias"]["secoes_com_bu"] == 1
    assert resumo["tardias"]["carga_fora_gedai"] == 1
    assert resumo["correspondencias_apos_17h_2510"] == 0
    assert resumo["recepcoes_por_dia"]["2026-10-24"] == {"contingencia": 0, "secao": 1}
    assert resumo["cargas_recebidas_24_25"]["2026-10-24"]["n"] == 1
