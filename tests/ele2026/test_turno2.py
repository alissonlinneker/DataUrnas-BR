"""Coleta de 2026 ciente do turno (--turno 1|2), sem rede.

O 1º turno (pleito 3220, eleição 6257) mantém os caminhos de sempre; o 2º
turno (pleito 3221, eleição 6258, 25/10/2026) grava em data/parquet/2026/t2/,
usa logs data/ele2026_t2_* e secao_id com prefixo "2T/".
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from dataurnas.config import PARQUET_2026_DIR
from dataurnas.downloader import ele2026 as E

RAIZ = Path(__file__).resolve().parents[2]
FIX = Path(__file__).parent / "fixtures"
BU_AC = FIX / "bu_ac_m01066_z0004_s0077.bin"
VSC_AC = FIX / "vsc_ac_m01066_z0004_s0077.bin"
NOME_BU = "o03220ac0106600040077-bu.dat"
NOME_VSC = "o03220ac0106600040077-vota.vsc"
IDENT = {"uf": "ac", "cd_mun": "01066", "zona": "0004", "secao": "0077"}
T2 = PARQUET_2026_DIR / "t2"


def _carregar(nome: str):
    p = RAIZ / "scripts" / "ele2026" / f"{nome}.py"
    spec = importlib.util.spec_from_file_location(f"turno2_{nome}", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --- parâmetros por turno ----------------------------------------------------

def test_parametros_turno_1_inalterados():
    p = E.parametros_turno(1)
    assert (p["pleito"], p["eleicao"], p["data"]) == ("3220", "6257", "04/10/2026")
    assert p["ciclo"] == "ele2026" and p["cargo"] == 1 and p["turno"] == 1
    assert p["sufixo_dir"] == "" and p["prefixo_id"] == "1T/"
    assert p["prefixo_log"] == "ele2026_" and p["saida"] == PARQUET_2026_DIR
    # constantes do módulo continuam apontando para o 1º turno
    assert (E.PLEITO, E.ELEICAO) == ("3220", "6257")


def test_parametros_turno_2():
    p = E.parametros_turno(2)
    assert (p["pleito"], p["eleicao"], p["data"]) == ("3221", "6258", "25/10/2026")
    assert p["ciclo"] == "ele2026" and p["cargo"] == 1 and p["turno"] == 2
    assert p["sufixo_dir"] == "t2" and p["prefixo_id"] == "2T/"
    assert p["prefixo_log"] == "ele2026_t2_" and p["saida"] == T2


@pytest.mark.parametrize("turno", [0, 3, "x"])
def test_parametros_turno_invalido(turno):
    with pytest.raises(ValueError):
        E.parametros_turno(turno)


def test_urls_turno_2():
    p = E.parametros_turno(2)
    kw = {"pleito": p["pleito"], "ciclo": p["ciclo"]}
    assert E.url_secoes_uf("ac", **kw).endswith(
        "/ele2026/arquivo-urna/3221/config/ac/ac-p003221-cs.json")
    assert E.url_aux("ac", "01066", "0004", "0077", **kw).endswith(
        "/ele2026/arquivo-urna/3221/dados/ac/01066/0004/0077/"
        "p003221-ac-m01066-z0004-s0077-aux.json")
    assert E.url_arquivo("ac", "01066", "0004", "0077", "abc",
                         "o03221ac0106600040077-bu.dat", **kw).endswith(
        "/arquivo-urna/3221/dados/ac/01066/0004/0077/abc/o03221ac0106600040077-bu.dat")
    assert E.url_resultado("br", eleicao=p["eleicao"]).endswith(
        "/ele2026/6258/dados/br/br-c0001-e006258-u.json")
    assert E.url_resultado("sp71072", eleicao=p["eleicao"]).endswith(
        "/ele2026/6258/dados/sp/sp71072-c0001-e006258-u.json")
    assert E.url_municipios(eleicao=p["eleicao"]).endswith(
        "/ele2026/6258/config/mun-e006258-cm.json")


def test_bu_do_1o_turno_nao_gera_votos_na_eleicao_6258():
    sec, votos = E.bu_to_rows(BU_AC.read_bytes(), eleicao=6258)
    assert votos == [] and sec["comparecimento_bu"] is not None


# --- parse_args de cada script -----------------------------------------------

def test_parse_args_fetch_resultados():
    mod = _carregar("fetch_resultados")
    assert mod.parse_args([]).saida == str(PARQUET_2026_DIR)
    a = mod.parse_args(["--turno", "2"])
    assert a.turno == 2 and a.saida == str(T2)
    assert mod.parse_args(["--turno", "2", "--saida", "/x"]).saida == "/x"
    with pytest.raises(SystemExit):
        mod.parse_args(["--turno", "3"])


def test_parse_args_fetch_secoes():
    mod = _carregar("fetch_secoes")
    a1 = mod.parse_args(["--ufs", "ac"])
    assert a1.turno == 1 and a1.saida == str(PARQUET_2026_DIR) and a1.ufs == ["ac"]
    a2 = mod.parse_args(["--turno", "2", "--ufs", "ac,rr"])
    assert a2.turno == 2 and a2.saida == str(T2) and a2.ufs == ["ac", "rr"]


def test_parse_args_reconcile():
    mod = _carregar("reconcile")
    assert mod.parse_args([]).base == str(PARQUET_2026_DIR)
    a = mod.parse_args(["--turno", "2", "--ufs", "ac"])
    assert a.base == str(T2) and a.ufs == "ac"


def test_parse_args_fetch_integridade():
    mod = _carregar("fetch_integridade")
    a1 = mod.parse_args([])
    assert a1.turno == 1
    assert a1.saida == str(PARQUET_2026_DIR / "integridade")
    assert a1.saida_auditoria == str(PARQUET_2026_DIR / "auditoria")
    assert a1.base_votos == str(PARQUET_2026_DIR)
    assert a1.log == str(RAIZ / "data" / "ele2026_integridade.log")
    a2 = mod.parse_args(["--turno", "2", "--ufs", "ac,rr"])
    assert a2.turno == 2 and a2.ufs == ["ac", "rr"]
    assert a2.saida == str(T2 / "integridade")
    assert a2.saida_auditoria == str(T2 / "auditoria")
    assert a2.base_votos == str(T2)
    assert a2.log == str(RAIZ / "data" / "ele2026_t2_integridade.log")


def test_registrar_ocorrencias_por_turno():
    mod = _carregar("registrar_ocorrencias_publicacao")
    c1, c2 = mod.caminhos(1), mod.caminhos(2)
    assert c1["saida"] == PARQUET_2026_DIR / "integridade" / "ocorrencias_publicacao.jsonl"
    assert c1["base_url"].endswith("/ele2026/arquivo-urna/3220/dados")
    assert mod.BASE_URL == c1["base_url"] and mod.SAIDA == c1["saida"]
    assert c2["saida"] == T2 / "integridade" / "ocorrencias_publicacao.jsonl"
    assert c2["base_url"].endswith("/ele2026/arquivo-urna/3221/dados")
    assert c2["pleito"] == "3221"
    assert all(p.name.startswith("ele2026_t2_integridade") for p in c2["logs"])
    linha = ("2026-10-26 10:00:00,123 WARNING PUBLICACAO ac/01066/0004/0077: "
             "HTTP 404 em arquivo listado no aux.json: o03221ac0106600040077-imgbu.dat")
    [o] = mod.extrair([linha], c2["base_url"])
    assert o["url_secao"].endswith("/arquivo-urna/3221/dados/ac/01066/0004/0077/")
    assert o["tipo"] == "imgbu"


def test_publicar_catalogo_pastas_por_turno():
    mod = _carregar("publicar_catalogo")
    assert mod.pastas_turno(1) == (mod.PASTA, mod.DIST)
    pasta, dist = mod.pastas_turno(2)
    assert pasta == RAIZ / "data/parquet/2026/t2/integridade"
    assert dist == RAIZ / "dist/catalogo-integridade-2026-t2"


# --- coleta com fetcher falso (sem rede) -------------------------------------

class _FetcherGravador:
    """HttpFetcher sem rede que anota cada URL pedida."""

    def __init__(self, arquivos: list[tuple[str, str, bytes]]):
        self.arquivos = arquivos
        self.corpos = {nm: raw for _tp, nm, raw in arquivos}
        self.urls: list[str] = []

    async def get_json(self, url: str):
        self.urls.append(url)
        return {"st": "Totalizada", "hashes": [{
            "hash": "4a6b70", "st": "Totalizado", "dr": "25/10/2026", "hr": "18:00:00",
            "arq": [{"tp": tp, "nm": nm} for tp, nm, _ in self.arquivos]}]}

    async def get(self, url: str):
        self.urls.append(url)
        return self.corpos[url.rsplit("/", 1)[-1]]


def _arquivos():
    return [("bu", NOME_BU, BU_AC.read_bytes()), ("vota", NOME_VSC, VSC_AC.read_bytes())]


def test_fetch_secoes_turno_2_usa_pleito_3221_e_filtra_eleicao():
    mod = _carregar("fetch_secoes")
    f = _FetcherGravador(_arquivos())
    s = {**IDENT, "nm_mun": "X", "secao_principal": None}
    with ThreadPoolExecutor(1) as pool:
        row, votos = asyncio.run(mod.processar_secao(
            f, pool, s, True, E.parametros_turno(2)))
    assert f.urls and all("/arquivo-urna/3221/dados/" in u for u in f.urls)
    assert f.urls[0].endswith("p003221-ac-m01066-z0004-s0077-aux.json")
    # o BU de teste é do 1º turno (eleição 6257): nada de votos para a 6258
    assert row["status"] == "ok" and votos == []
    f1 = _FetcherGravador(_arquivos())
    with ThreadPoolExecutor(1) as pool:
        _row, votos1 = asyncio.run(mod.processar_secao(f1, pool, s, True))
    assert all("/arquivo-urna/3220/dados/" in u for u in f1.urls) and votos1


def test_fetch_integridade_turno_2_urls_e_secao_id():
    pytest.importorskip("cryptography")
    mod = _carregar("fetch_integridade")
    f = _FetcherGravador(_arquivos())
    s = {**IDENT, "secao_principal": None}
    with ThreadPoolExecutor(1) as pool:
        r = asyncio.run(mod.processar_secao(f, pool, s, (), True, E.parametros_turno(2)))
    assert f.urls and all("/arquivo-urna/3221/dados/" in u for u in f.urls)
    assert r["secao_log"]["secao_id"] == "2T/ac/01066/0004/0077"
    assert r["secao_log"]["turno"] == 2
    # votos esperados vazios conferem: o BU não tem a eleição 6258
    assert r["secao"]["votos_conferem"] is True


def test_auditar_secao_filtra_eleicao_do_turno():
    pytest.importorskip("cryptography")
    from dataurnas.analyzer import integrity as I

    conj = {"token": "T", "data_hora": "", "arquivos": _arquivos()}
    votos_1t = I._votos_bu(BU_AC.read_bytes())
    assert votos_1t
    assert I.auditar_secao(IDENT, [conj], 0, votos_1t)["secao"]["votos_conferem"] is True
    assert I.auditar_secao(IDENT, [conj], 0, ())["secao"]["votos_conferem"] is False
    r2 = I.auditar_secao(IDENT, [conj], 0, (), turno=2)
    assert r2["secao"]["votos_conferem"] is True
    r2b = I.auditar_secao(IDENT, [conj], 0, votos_1t, turno=2, eleicao=6257)
    assert r2b["secao"]["votos_conferem"] is True


# --- consolidação com prefixo do turno ---------------------------------------

def _partes_sinteticas(mod, out: Path, prefixo: str) -> None:
    parts = out / "parts"
    parts.mkdir(parents=True)
    lote = "20261026000000-1-00001"
    sec = {**IDENT, "status_secao": "ok", "n_arquivos": 1, "n_hash_confere": 1,
           "n_hash_diverge": 0, "n_sem_hash": 0, "n_indisponiveis": 0,
           "assinatura_valida": True, "_lote": lote}
    arq = {**IDENT, "tipo": "bu", "nome": "o03221ac0106600040077-bu.dat", "tamanho": 1,
           "hash_confere": True, "disponivel": True, "http_status": 200, "_lote": lote}
    sid = f"{prefixo}ac/01066/0004/0077"
    seclog = {"secao_id": sid, "turno": int(prefixo[0]), **IDENT, "_lote": lote}
    issue = {"secao_id": sid, "codigo": "X01", "severidade": "info", "descricao": "d",
             "base_legal": "", "detalhes": "", "_lote": lote}
    for nome, row, schema in (("secoes", sec, mod.SECOES_SCHEMA),
                              ("arquivos", arq, mod.ARQUIVOS_SCHEMA),
                              ("seclog", seclog, mod.SECOES_LOG_SCHEMA),
                              ("issues", issue, mod.ISSUES_SCHEMA)):
        pq.write_table(pa.Table.from_pylist([row], schema=schema),
                       parts / f"{nome}-{lote}.parquet")


def test_consolidar_auditoria_prefixo_2t(tmp_path):
    import duckdb

    mod = _carregar("fetch_integridade")
    _partes_sinteticas(mod, tmp_path, "2T/")
    con = duckdb.connect()
    con.execute(f"CREATE TEMP TABLE s AS SELECT * FROM "
                f"read_parquet('{tmp_path / 'parts' / 'secoes-*.parquet'}')")
    # com o prefixo do 1º turno nada casa
    r1 = mod.consolidar_auditoria(con, tmp_path, tmp_path / "aud1", "1T/")
    assert r1["secoes_log"] == 0
    r2 = mod.consolidar_auditoria(con, tmp_path, tmp_path / "aud2", "2T/")
    assert r2 == {"secoes_log": 1, "issues_por_codigo": {"X01": 1}}
    [(sid,)] = duckdb.sql(f"SELECT secao_id FROM read_parquet("
                          f"'{tmp_path / 'aud2' / 'secoes_log_2026.parquet'}')").fetchall()
    assert sid == "2T/ac/01066/0004/0077"


def test_consolidar_turno_2_resumo_e_ids(tmp_path):
    import duckdb

    mod = _carregar("fetch_integridade")
    out = tmp_path / "t2" / "integridade"
    _partes_sinteticas(mod, out, "2T/")
    mod.consolidar(out, None, 2)
    resumo = json.loads((out / "resumo.json").read_text(encoding="utf-8"))
    assert resumo["pleito"] == "3221" and resumo["ciclo"] == "ele2026"
    assert resumo["auditoria_bu_log"]["secoes_log"] == 1
    aud = tmp_path / "t2" / "auditoria"
    [(sid,)] = duckdb.sql(f"SELECT secao_id FROM read_parquet("
                          f"'{aud / 'issues_2026.parquet'}')").fetchall()
    assert sid.startswith("2T/")


def test_consolidar_turno_1_padrao_inalterado(tmp_path):
    mod = _carregar("fetch_integridade")
    out = tmp_path / "integridade"
    _partes_sinteticas(mod, out, "1T/")
    mod.consolidar(out, tmp_path / "auditoria")
    resumo = json.loads((out / "resumo.json").read_text(encoding="utf-8"))
    assert resumo["pleito"] == "3220"
    assert resumo["auditoria_bu_log"]["secoes_log"] == 1
