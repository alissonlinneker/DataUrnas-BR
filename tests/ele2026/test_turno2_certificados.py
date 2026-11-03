"""--turno 2 na análise de certificados (analisar_certificados.py), sem rede.

O 1º turno mantém caminhos, pleito e data; o 2º lê de data/parquet/2026/t2/,
baixa os .vsc do pleito 3221 e confere a validade em 25/10/2026.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import importlib.util
import json
from pathlib import Path

import pytest

from dataurnas.config import PARQUET_2026_DIR
from dataurnas.downloader import ele2026 as E

pytest.importorskip("cryptography")

RAIZ = Path(__file__).resolve().parents[2]
VSC_AC = Path(__file__).parent / "fixtures" / "vsc_ac_m01066_z0004_s0077.bin"
T2 = PARQUET_2026_DIR / "t2"


@pytest.fixture(scope="module")
def cert():
    p = RAIZ / "scripts" / "ele2026" / "analisar_certificados.py"
    spec = importlib.util.spec_from_file_location("t2_analisar_certificados", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class FakeFetcher:
    def __init__(self, respostas):
        self.respostas, self.urls, self.stats = respostas, [], {}

    async def get(self, url):
        self.urls.append(url)
        return self.respostas.get(url)

    async def get_json(self, url):
        b = await self.get(url)
        return None if b is None else json.loads(b)


def test_certificados_turno_1_padroes_inalterados(cert):
    a = cert.parse_args([])
    assert a.turno == 1
    assert a.integridade == str(cert.DIR_INTEGRIDADE)
    assert a.bu == str(cert.BU_PADRAO) and a.saida == str(cert.SAIDA_PADRAO)
    c = cert.contexto_turno(1)
    assert c["pleito"] == "3220" and c["dia"] == cert.DIA_ELEICAO
    assert cert.nome_vsc("AC", "01007", "0009", "0001") == "o03220ac0100700090001-vota.vsc"


def test_certificados_turno_2_padroes(cert, tmp_path):
    a = cert.parse_args(["--turno", "2", "--todas"])
    assert a.integridade == str(T2 / "integridade")
    assert a.bu == str(T2 / "secoes_2026.parquet")
    assert a.saida == str(T2 / "integridade" / "certificados_resumo.json")
    assert a.tabela == str(T2 / "integridade" / "certificados.parquet")
    c = cert.contexto_turno(2)
    assert c["pleito"] == "3221"
    assert c["dia"] == dt.datetime(2026, 10, 25, 12, 0, tzinfo=dt.timezone.utc)
    assert cert.nome_vsc("ac", "01007", "0009", "0001", pleito="3221") == \
        "o03221ac0100700090001-vota.vsc"
    b = cert.parse_args(["--turno", "2", "--todas", "--bu", str(tmp_path / "b.parquet"),
                         "--saida", str(tmp_path / "r.json"),
                         "--tabela", str(tmp_path / "t.parquet")])
    assert (b.bu, b.saida, b.tabela) == (str(tmp_path / "b.parquet"), str(tmp_path / "r.json"),
                                         str(tmp_path / "t.parquet"))


def test_avaliar_vsc_validade_no_dia_do_turno(cert):
    cert._init_worker(None)
    raw = VSC_AC.read_bytes()
    i = cert.info_vsc(raw)
    fim = dt.datetime.fromisoformat(i["nao_depois"])
    assert cert.avaliar_vsc(raw, cert.contexto_turno(2)["dia"].isoformat())[
        "valido_na_eleicao"] is True
    depois = (fim + dt.timedelta(days=1)).isoformat()
    assert cert.avaliar_vsc(raw, depois)["valido_na_eleicao"] is False


def test_coletar_todas_turno_2_usa_pleito_3221(cert, tmp_path):
    import pandas as pd

    url = {"pleito": "3221"}
    sec = pd.DataFrame([
        {"uf": "ac", "cd_mun": "01066", "zona": "0004", "secao": "0077", "status": "ok",
         "hash": "aa11", "fase": "oficial"},
        {"uf": "ac", "cd_mun": "01066", "zona": "0004", "secao": "0078", "status": "ok",
         "hash": None, "fase": "oficial"},
    ])
    aux = {"hashes": [{"hash": "bb22", "st": "Totalizado", "arq": [
        {"nm": "o03221ac0106600040078-vota.vsc", "tp": "vota"}]}]}
    resp = {
        E.url_arquivo("ac", "01066", "0004", "0077", "aa11",
                      "o03221ac0106600040077-vota.vsc", **url): VSC_AC.read_bytes(),
        E.url_aux("ac", "01066", "0004", "0078", **url): json.dumps(aux).encode(),
        E.url_arquivo("ac", "01066", "0004", "0078", "bb22",
                      "o03221ac0106600040078-vota.vsc", **url): VSC_AC.read_bytes(),
    }
    f = FakeFetcher(resp)
    c = cert.contexto_turno(2)
    tabela = tmp_path / "certificados.parquet"
    st = asyncio.run(cert.coletar_todas(sec, f, tabela, None, processos=0, tarefas=1,
                                        log=lambda *_: None, pleito=c["pleito"],
                                        dia=c["dia"]))
    assert st["processadas"] == 2 and st["origem"] == {"direto": 1, "aux": 1}
    assert all("/3221/" in u for u in f.urls)
    df = cert.consolidar(tabela)
    assert df["valido_na_eleicao"].tolist() == [True, True]


def test_main_turno_2_grava_dia_do_turno(cert, tmp_path):
    import pandas as pd

    base = tmp_path / "integ"
    (base / "parts").mkdir(parents=True)
    pd.DataFrame([{
        "uf": "ac", "cd_mun": "01007", "zona": "0009", "secao": "0001",
        "status_secao": "ok", "assinatura_valida": True, "assinatura_algoritmo": "Ed521",
        "cert_subject": "O=TSE,C=BR,CN=UEAO02468149",
        "cert_issuer": "L=Brasilia,OU=STI,O=TSE,C=BR,ST=DF,CN=AC UE2022",
        "cert_serial": "1", "cert_sha256": "ab" * 32, "modelo_urna": "UE2022",
        "motivo": None, "_lote": "l1"}]).to_parquet(base / "parts" / "secoes-x-00001.parquet")
    saida = tmp_path / "r.json"
    assert cert.main(["--turno", "2", "--integridade", str(base), "--bu",
                      str(tmp_path / "nao-existe.parquet"), "--saida", str(saida)]) == 0
    res = json.loads(saida.read_text(encoding="utf-8"))
    assert res["turno"] == 2 and res["dia_eleicao"] == "2026-10-25"
