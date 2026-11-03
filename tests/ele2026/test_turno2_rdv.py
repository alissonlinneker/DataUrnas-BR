"""--turno 2 na recontagem do RDV (fetch_rdv.py), sem rede.

O 1º turno mantém caminhos, pleito e data; o 2º usa o pleito 3221, a data
25/10/2026 (o log acumula o 1º turno), data/parquet/2026/t2/ e o prefixo
"2T/". A linha do tempo ganha votos depois das 17h de Brasília e a hora do
último voto em Brasília.
"""

from __future__ import annotations

import asyncio
import importlib.util
import io
import json
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from dataurnas.analyzer import rdv_recontagem as R
from dataurnas.config import PARQUET_2026_DIR
from dataurnas.downloader import ele2026 as E

RAIZ = Path(__file__).resolve().parents[2]
FIX = Path(__file__).parent / "fixtures"
BU_AC = FIX / "bu_ac_m01066_z0004_s0077.bin"
VSC_AC = FIX / "vsc_ac_m01066_z0004_s0077.bin"
IDENT = {"uf": "ac", "cd_mun": "01066", "zona": "0004", "secao": "0077"}
T2 = PARQUET_2026_DIR / "t2"


def _carregar(nome: str):
    p = RAIZ / "scripts" / "ele2026" / f"{nome}.py"
    spec = importlib.util.spec_from_file_location(f"t2rc_{nome}", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def rdv_mod():
    return _carregar("fetch_rdv")


def _linha(data_hora, desc, urna="02293919"):
    return f"{data_hora}\tINFO\t{urna}\tVOTA\t{desc}\tABCDEF0123456789"


def _log(eventos) -> str:
    return "\n".join(_linha(*e) for e in eventos) + "\n"


def _zip(arquivos: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for nome, dados in arquivos.items():
            z.writestr(nome, dados)
    return buf.getvalue()


LOG_T2 = [
    # 1º turno acumulado no log do 2º
    ("04/10/2026 06:00:00", "Urna pronta para receber votos"),
    ("04/10/2026 06:10:00", "O voto do eleitor foi computado"),
    ("04/10/2026 15:50:00", "O voto do eleitor foi computado"),
    ("04/10/2026 15:55:00", "Inicio do Encerramento"),
    # 2º turno
    ("25/10/2026 06:00:00", "Urna pronta para receber votos"),
    ("25/10/2026 06:30:00", "O voto do eleitor foi computado"),
    ("25/10/2026 14:59:59", "O voto do eleitor foi computado"),
    ("25/10/2026 15:00:00", "O voto do eleitor foi computado"),
    ("25/10/2026 15:20:30", "O voto do eleitor foi computado"),
    ("25/10/2026 15:25:00", "Inicio do Encerramento"),
]


# --- linha do tempo em horário de Brasília ----------------------------------

def test_log_t2_filtra_data_e_conta_apos_17h_brasilia_no_acre():
    r = R.analisar_log_tempo(_log(LOG_T2), "ac", "01066", 4, "25/10/2026",
                             ("04/10/2026",))
    assert r["fuso_offset"] == -2
    assert r["votos_log"] == 4 and r["diferenca_log_bu"] == 0
    assert r["votos_turno_anterior"] == 2
    assert r["votos_outras_datas"] == 0
    assert "log_voto_outra_data" not in r["flags"]
    assert r["aberturas"] == 1 and r["hora_pronta"] == "06:00:00"
    # 15:00 e 15:20:30 no AC são 17:00 e 17:20:30 em Brasília
    assert r["votos_log_apos_17h_brasilia"] == 2
    assert r["votos_apos_17h"] == 2
    assert r["ultimo_voto"] == "15:20:30"
    assert r["ultimo_voto_brasilia"] == "17:20:30"
    assert r["votos_antes_pronta"] == 0 and r["votos_apos_encerramento"] == 0


def test_log_sem_datas_anteriores_mantem_1o_turno():
    """Sem datas anteriores (1º turno) o voto de outra data continua marcado
    e votos_turno_anterior fica nulo."""
    r = R.analisar_log_tempo(_log(LOG_T2), "ac", "01066", 4, "25/10/2026")
    assert r["votos_turno_anterior"] is None
    assert r["votos_outras_datas"] == 2
    assert "log_voto_outra_data" in r["flags"]


@pytest.mark.parametrize("uf, mun, local, esperado_bsb, apos", [
    ("sp", "71072", "17:00:00", "17:00:00", 1),        # UTC-3
    ("sp", "71072", "16:59:59", "16:59:59", 0),
    ("rr", "03018", "16:00:00", "17:00:00", 1),        # UTC-4
    ("mt", "90670", "15:59:00", "16:59:00", 0),
    ("am", "02550", "16:10:00", "17:10:00", 1),        # Manaus, UTC-4
    ("am", "98477", "15:10:00", "17:10:00", 1),        # Tabatinga, UTC-5
    ("am", "98477", "16:10:00", "18:10:00", 1),
    ("pe", "30015", "17:30:00", "16:30:00", 0),        # Fernando de Noronha, UTC-2
    ("pe", "30015", "18:00:00", "17:00:00", 1),
])
def test_conversao_para_brasilia_por_fuso_do_municipio(uf, mun, local, esperado_bsb, apos):
    txt = _log([("25/10/2026 07:00:00", "Urna pronta para receber votos"),
                (f"25/10/2026 {local}", "O voto do eleitor foi computado")])
    r = R.analisar_log_tempo(txt, uf, mun, 1, "25/10/2026", ("04/10/2026",))
    assert r["ultimo_voto_brasilia"] == esperado_bsb
    assert r["votos_log_apos_17h_brasilia"] == apos


def test_exterior_sem_horario_de_brasilia():
    txt = _log([("25/10/2026 08:00:00", "Urna pronta para receber votos"),
                ("25/10/2026 17:30:00", "O voto do eleitor foi computado")])
    r = R.analisar_log_tempo(txt, "zz", "29467", 1, "25/10/2026", ("04/10/2026",))
    assert r["votos_log_apos_17h_brasilia"] is None
    assert r["ultimo_voto_brasilia"] is None
    assert r["votos_apos_17h"] == 1  # 17h locais, como antes


def test_virada_do_dia_em_brasilia():
    txt = _log([("25/10/2026 07:00:00", "Urna pronta para receber votos"),
                ("25/10/2026 22:30:00", "O voto do eleitor foi computado")])
    r = R.analisar_log_tempo(txt, "ac", "01066", 1, "25/10/2026")
    assert r["ultimo_voto_brasilia"] == "00:30:00 (+1d)"
    assert R._hms_dia(-1800) == "23:30:00 (-1d)"
    assert R._hms_dia(None) is None


def test_processar_secao_turno_2_auditoria_com_prefixo_2t():
    log_jez = _zip({"logd.dat": _log(LOG_T2).encode("latin-1")})
    arquivos = {"bu": ("x-bu.dat", BU_AC.read_bytes()), "log": ("x-log.jez", log_jez)}
    r = R.processar_secao(IDENT, arquivos, None, 3221, "25/10/2026", auditar=True,
                          modelo_cod=22, turno=2, datas_anteriores=("04/10/2026",))
    t = r["tempo"]
    assert t["votos_log"] == 4 and t["votos_turno_anterior"] == 2
    assert t["votos_log_apos_17h_brasilia"] == 2
    assert t["ultimo_voto_brasilia"] == "17:20:30"
    sl = r["secao_log"]
    assert sl["secao_id"] == "2T/ac/01066/0004/0077"
    assert sl["votos_log"] == 4  # a auditoria também filtra 25/10/2026
    assert not [a for a in r["achados"] if a["categoria"] == "log_voto_outra_data"]


def test_processar_secao_logsa_sem_horario_de_brasilia():
    logsa = _log([("25/10/2026 17:33:00", "Tipo de apuração selecionada (DIGITAÇÃO DE BUEx)",
                   "01808076")]).encode("latin-1")
    arquivos = {"busa": ("x-busa.dat", BU_AC.read_bytes()),
                "logsa": ("x-logsa.jez", _zip({"logd.dat": logsa}))}
    t = R.processar_secao(IDENT, arquivos, None, 3221, "25/10/2026", turno=2,
                          datas_anteriores=("04/10/2026",))["tempo"]
    assert t["votos_log"] is None and t["votos_log_apos_17h_brasilia"] is None


# --- fetch_rdv.py: parâmetros -----------------------------------------------

def test_fetch_rdv_turno_1_padroes_inalterados(rdv_mod):
    a = rdv_mod.parse_args([])
    assert a.turno == 1 and a.fonte == "catalogo"
    assert a.manifesto == str(PARQUET_2026_DIR / "integridade" / "catalogo_manifest.json")
    assert a.catalogo_local == str(PARQUET_2026_DIR / "integridade")
    assert a.saida == str(PARQUET_2026_DIR / "rdv")
    assert a.base_votos == str(PARQUET_2026_DIR)
    assert a.log == str(RAIZ / "data" / "ele2026_rdv.log")
    assert a.saida_auditoria == str(PARQUET_2026_DIR / "auditoria_v2")
    assert a.auditoria_publicada == str(PARQUET_2026_DIR / "auditoria")
    assert a.secoes_integridade == str(PARQUET_2026_DIR / "integridade" / "secoes.parquet")
    c = rdv_mod.contexto_turno(1)
    assert (c["pleito"], c["data_log"], c["prefixo_id"]) == ("3220", "04/10/2026", "1T/")
    assert c["datas_anteriores"] == () and c["refazer_sem_aux"] is False
    assert rdv_mod.DATA_ELEICAO == "04/10/2026"


def test_fetch_rdv_turno_2_padroes(rdv_mod):
    a = rdv_mod.parse_args(["--turno", "2"])
    assert a.turno == 2 and a.fonte == "aux"
    assert a.saida == str(T2 / "rdv")
    assert a.base_votos == str(T2)
    assert a.log == str(RAIZ / "data" / "ele2026_t2_rdv.log")
    assert a.saida_auditoria == str(T2 / "auditoria_v2")
    assert a.auditoria_publicada == str(T2 / "auditoria")
    assert a.secoes_integridade == str(T2 / "integridade" / "secoes.parquet")
    assert a.catalogo_local == str(T2 / "integridade")
    c = rdv_mod.contexto_turno(2)
    assert (c["pleito"], c["eleicao"], c["data_log"]) == ("3221", "6258", "25/10/2026")
    assert c["prefixo_id"] == "2T/" and c["datas_anteriores"] == ("04/10/2026",)
    assert c["refazer_sem_aux"] is True


def test_fetch_rdv_caminhos_explicitos(rdv_mod, tmp_path):
    a = rdv_mod.parse_args(["--turno", "2", "--saida", str(tmp_path / "r"),
                            "--log", str(tmp_path / "x.log"), "--fonte", "catalogo",
                            "--saida-auditoria", str(tmp_path / "a"),
                            "--auditoria-publicada", str(tmp_path / "p"),
                            "--base-votos", str(tmp_path / "v"),
                            "--secoes-integridade", str(tmp_path / "s.parquet"),
                            "--catalogo-local", str(tmp_path / "c"),
                            "--manifesto", str(tmp_path / "m.json")])
    assert a.fonte == "catalogo"
    for k, v in {"saida": "r", "log": "x.log", "saida_auditoria": "a",
                 "auditoria_publicada": "p", "base_votos": "v",
                 "secoes_integridade": "s.parquet", "catalogo_local": "c",
                 "manifesto": "m.json"}.items():
        assert getattr(a, k) == str(tmp_path / v)
    with pytest.raises(SystemExit):
        rdv_mod.parse_args(["--turno", "3"])


# --- fetch_rdv.py: rede simulada ---------------------------------------------

class FakeFetcher:
    def __init__(self, respostas):
        self.respostas, self.urls = respostas, []

    async def get(self, url):
        self.urls.append(url)
        return self.respostas.get(url)

    async def get_json(self, url):
        b = await self.get(url)
        return None if b is None else json.loads(b)


def test_secoes_do_aux_e_processar_turno_2(rdv_mod):
    c = rdv_mod.contexto_turno(2)
    url = {"pleito": "3221", "ciclo": "ele2026"}
    cs = {"abr": [{"cd": "ac", "mu": [{"cd": "01066", "zon": [
        {"cd": "0004", "sec": [{"ns": "0077"}, {"ns": "0078"}]}]}]}]}
    aux = {"hashes": [{"hash": "aa11", "st": "Totalizado", "arq": [
        {"nm": "o03221ac0106600040077-bu.dat", "tp": "bu"},
        {"nm": "o03221ac0106600040077-log.jez", "tp": "log"}]}]}
    log_jez = _zip({"logd.dat": _log(LOG_T2).encode("latin-1")})
    resp = {
        E.url_secoes_uf("ac", **url): json.dumps(cs).encode(),
        E.url_aux("ac", "01066", "0004", "0077", **url): json.dumps(aux).encode(),
        E.url_arquivo("ac", "01066", "0004", "0077", "aa11",
                      "o03221ac0106600040077-bu.dat", **url): BU_AC.read_bytes(),
        E.url_arquivo("ac", "01066", "0004", "0077", "aa11",
                      "o03221ac0106600040077-log.jez", **url): log_jez,
    }
    f = FakeFetcher(resp)

    async def rodar():
        secoes = await rdv_mod.secoes_do_aux(f, "ac", c)
        with ThreadPoolExecutor(1) as pool:
            r = await rdv_mod.processar(f, pool, secoes[0], False, None, c)
            # 0078 sem aux.json (ainda não publicada): pendente, não vai ao checkpoint
            with pytest.raises(RuntimeError, match="aux.json"):
                await rdv_mod.processar(f, pool, secoes[1], False, None, c)
        return secoes, r

    secoes, r = asyncio.run(rodar())
    assert [s["secao"] for s in secoes] == ["0077", "0078"]
    assert all("/3221/" in u for u in f.urls)
    assert r["secao"]["status"] == "sem_rdv"
    assert r["tempo"]["votos_log_apos_17h_brasilia"] == 2
    assert r["tempo"]["votos_turno_anterior"] == 2


def test_processar_turno_1_sem_aux_continua_sem_arquivos(rdv_mod):
    s = {**IDENT, "hash": None, "arquivos": None, "n_conjuntos": None}
    r = asyncio.run(rdv_mod.processar(FakeFetcher({}), None, s))
    assert r["secao"]["status"] == "sem_arquivos"


def test_carregar_catalogo_local_sem_manifesto(rdv_mod, tmp_path):
    linhas = {"uf": ["ac"], "cd_mun": ["01066"], "zona": ["0004"], "secao": ["0077"],
              "tipo": ["bu"], "nome": ["o03221ac0106600040077-bu.dat"], "sha512": ["h"],
              "token_tse": ["AAAA"], "data_hora_tse": ["25/10/2026 18:00:00"],
              "disponivel": [True]}
    pq.write_table(pa.table(linhas), tmp_path / "arquivos_ac.parquet")
    pq.write_table(pa.table({**linhas, "uf": ["am"]}), tmp_path / "arquivos_am.parquet")
    secoes = asyncio.run(rdv_mod.carregar_catalogo(FakeFetcher({}), "ac", {}, tmp_path))
    assert len(secoes) == 1 and secoes[0]["arquivos"] == {
        "bu": ("o03221ac0106600040077-bu.dat", "h")}
    assert asyncio.run(rdv_mod.carregar_catalogo(FakeFetcher({}), "rr", {}, tmp_path)) is None


# --- fetch_rdv.py: consolidação ---------------------------------------------

def _parte(rdv_mod, out: Path, tempo_extra: dict, lote: str, turno_novo: bool = True):
    parts = out / "parts"
    parts.mkdir(parents=True, exist_ok=True)
    sec = {**IDENT, "status": "sem_rdv", "comparecimento_bu": 4, "_lote": lote,
           "rdv_confere": False, "hash_confere": None, "estrutura_ok": None}
    pq.write_table(pa.Table.from_pylist([sec], schema=rdv_mod.SECOES_SCHEMA),
                   parts / f"secoes-{lote}.parquet")
    tempo = {**IDENT, "fuso_offset": -2, "comparecimento_bu": 4, "votos_log": 4,
             "diferenca_log_bu": 0, "votos_outras_datas": 0, "max_votos_minuto": 1,
             "intervalo_min_s": 10, "intervalo_mediana_s": 20,
             "hist_intervalos": [0] * (len(R.FAIXAS_INTERVALO) + 1), "flags": [],
             "origem_log": "log", "_lote": lote, **tempo_extra}
    schema = rdv_mod.TEMPO_SCHEMA
    if not turno_novo:  # parte gravada antes das colunas novas
        schema = pa.schema([f for f in schema if f.name not in
                            dict(rdv_mod.COLUNAS_TEMPO_NOVAS)])
    pq.write_table(pa.Table.from_pylist([tempo], schema=schema), parts / f"tempo-{lote}.parquet")
    for nome, sch in (("recontagem", rdv_mod.RECONTAGEM_SCHEMA),
                      ("presidente", rdv_mod.PRESIDENTE_SCHEMA),
                      ("achados", rdv_mod.ACHADOS_SCHEMA)):
        pq.write_table(sch.empty_table(), parts / f"{nome}-{lote}.parquet")


def test_consolidar_turno_2_grava_colunas_e_resumo(rdv_mod, tmp_path):
    out = tmp_path / "rdv"
    _parte(rdv_mod, out, {"votos_turno_anterior": 2, "votos_log_apos_17h_brasilia": 2,
                          "ultimo_voto_brasilia": "17:20:30"}, "20261025200000-1-00001")
    rdv_mod.consolidar(out, tmp_path / "sem_votos", None, None, turno=2)
    t = pq.read_table(out / "log_tempo_secoes.parquet").to_pylist()[0]
    assert t["votos_log_apos_17h_brasilia"] == 2
    assert t["ultimo_voto_brasilia"] == "17:20:30"
    assert t["votos_turno_anterior"] == 2
    res = json.loads((out / "resumo.json").read_text(encoding="utf-8"))
    assert (res["turno"], res["pleito"], res["data_eleicao"]) == (2, "3221", "25/10/2026")
    assert res["por_uf"]["ac"]["log_votos_apos_17h_brasilia"] == 2
    assert res["por_uf"]["ac"]["log_secoes_voto_apos_17h_brasilia"] == 1
    assert res["totais"]["log_votos_turno_anterior"] == 2


def test_consolidar_partes_antigas_sem_colunas_novas(rdv_mod, tmp_path):
    out = tmp_path / "rdv"
    _parte(rdv_mod, out, {}, "20261005200000-1-00001", turno_novo=False)
    rdv_mod.consolidar(out, tmp_path / "sem_votos")
    t = pq.read_table(out / "log_tempo_secoes.parquet")
    assert "votos_log_apos_17h_brasilia" in t.column_names
    assert t.to_pylist()[0]["ultimo_voto_brasilia"] is None
    res = json.loads((out / "resumo.json").read_text(encoding="utf-8"))
    assert (res["turno"], res["pleito"], res["data_eleicao"]) == (1, "3220", "04/10/2026")


def test_consolidar_auditoria_prefixo_2t(rdv_mod, tmp_path):
    import duckdb

    from dataurnas.database.rows import SECOES_COLUMNS  # noqa: F401 (esquema real)

    parts = tmp_path / "parts"
    parts.mkdir()
    lote = "20261025200000-1-00001"
    seclog = pa.table({"secao_id": ["2T/ac/01066/0004/0077"], "uf": ["ac"],
                       "cd_mun": ["01066"], "zona": ["0004"], "secao": ["0077"],
                       "_lote": [lote]})
    pq.write_table(seclog, parts / f"seclog-{lote}.parquet")
    issues = pa.table({"secao_id": ["2T/ac/01066/0004/0077"], "codigo": ["A03"],
                       "_lote": [lote]})
    pq.write_table(issues, parts / f"issues-{lote}.parquet")
    con = duckdb.connect()
    con.execute("CREATE TEMP TABLE s AS SELECT 'ac' uf, '01066' cd_mun, '0004' zona, "
                "'0077' secao, ? _lote", [lote])
    res = rdv_mod.consolidar_auditoria(con, parts, tmp_path / "a", None, "2T/")
    assert res["secoes_log"] == 1 and res["issues_por_codigo"] == {"A03": 1}
    con2 = duckdb.connect()
    con2.execute("CREATE TEMP TABLE s AS SELECT 'ac' uf, '01066' cd_mun, '0004' zona, "
                 "'0077' secao, ? _lote", [lote])
    assert rdv_mod.consolidar_auditoria(con2, parts, tmp_path / "b", None)["secoes_log"] == 0
