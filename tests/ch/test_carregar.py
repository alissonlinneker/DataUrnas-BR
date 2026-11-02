"""Carregador incremental do ClickHouse: transformação, descoberta e idempotência.

Usa partes Parquet sintéticas (com um BU e uma assinatura reais de fixture) e um
banco falso em memória; não precisa de ClickHouse.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

RAIZ = Path(__file__).resolve().parents[2]
FIX = RAIZ / "tests" / "ele2026" / "fixtures"
BU = (FIX / "bu_ac_m01066_z0004_s0077.bin").read_bytes()
VSC = (FIX / "vsc_ac_m01066_z0004_s0077.bin").read_bytes()
ELEICAO_FIXTURE = 6257  # o BU de fixture é do 1º turno


def _carregar():
    p = RAIZ / "scripts" / "ch" / "carregar.py"
    spec = importlib.util.spec_from_file_location("carregar_ch", p)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["carregar_ch"] = mod
    spec.loader.exec_module(mod)
    return mod


M = _carregar()

SCHEMA = pa.schema([
    ("coletado_em", pa.string()), ("uf", pa.string()), ("cd_mun", pa.string()),
    ("zona", pa.string()), ("secao", pa.string()), ("tipo", pa.string()),
    ("hash", pa.string()), ("st_secao", pa.string()), ("st_hash", pa.string()),
    ("dt_recebimento", pa.string()), ("hr_recebimento", pa.string()),
    ("nome", pa.string()), ("sha512", pa.string()), ("tamanho", pa.int32()),
    ("conteudo", pa.binary()),
])

AUX = {"dg": "25/10/2026", "hg": "21:07:27", "f": "O", "st": "Recebida", "hashes": [
    {"hash": "abc", "dr": "25/10/2026", "hr": "21:07:27", "st": "Recebido",
     "arq": [{"nm": "o0-bu.dat", "tp": "bu"}, {"nm": "o0-vota.vsc", "tp": "vota"}]}]}


def _linha(tipo, conteudo, secao="0077", coletado="2026-10-26T00:25:38+0000", **kw):
    import hashlib
    base = {"coletado_em": coletado, "uf": "ac", "cd_mun": "01066", "zona": "0004",
            "secao": secao, "tipo": tipo, "hash": None, "st_secao": "Recebida",
            "st_hash": None, "dt_recebimento": None, "hr_recebimento": None,
            "nome": None, "sha512": hashlib.sha512(conteudo).hexdigest(),
            "tamanho": len(conteudo), "conteudo": conteudo}
    base.update(kw)
    return base


def _parte(caminho: Path, linhas: list[dict], idade: float = 3600) -> Path:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(pa.Table.from_pylist(linhas, schema=SCHEMA), caminho, compression="zstd")
    t = time.time() - idade
    os.utime(caminho, (t, t))
    return caminho


def _linhas_padrao():
    pacote = {"hash": "abc", "st_hash": "Recebido", "dt_recebimento": "25/10/2026",
              "hr_recebimento": "21:07:27"}
    return [
        _linha("aux", json.dumps(AUX).encode()),
        _linha("aux", b'{"st":"N\xc3\xa3o recebida"}', secao="0078"),
        _linha("bu", BU, nome="o0-bu.dat", **pacote),
        _linha("vota", VSC, nome="o0-vota.vsc", **pacote),
        _linha("bu", b"isto nao e um BU", secao="0079", nome="x-bu.dat", hash="zz"),
    ]


class BancoFalso:
    def __init__(self):
        self.tabelas: dict[str, list[dict]] = {}

    def registro(self):
        reg = {}
        for r in self.tabelas.get("cargas_arquivos", []):
            ant = reg.get(r["caminho"])
            if ant is None or r["carregado_em"] >= ant[0]:
                reg[r["caminho"]] = (r["carregado_em"], M.Registro(
                    r["tamanho"], r["mtime"], r["sha256"], r["deslocamento"], r["status"]))
        return {k: v[1] for k, v in reg.items()}

    def inserir(self, tabela, colunas, linhas):
        assert all(len(x) == len(colunas) for x in linhas), tabela
        self.tabelas.setdefault(tabela, []).extend(dict(zip(colunas, x, strict=True)) for x in linhas)

    def n(self, tabela):
        return len(self.tabelas.get(tabela, []))


# ---------------------------------------------------------------------------

def test_conversoes_de_data_e_abrangencia():
    d = M.dt_brt("25/10/2026", "21:07:27")
    assert d.utcoffset() == timedelta(hours=-3)
    assert d.astimezone(timezone.utc).hour == 0
    assert M.dt_brt(None, "10:00:00") is None
    u = M.dt_urna("20261025T170512")
    assert (u.hour, u.minute, u.tzinfo) == (17, 5, timezone.utc)
    assert M.dt_urna("lixo") is None
    assert M.dt_coleta("2026-10-26T00:25:38+0000").tzinfo is not None
    assert M.nivel_abr("br") == ("br", "", "")
    assert M.nivel_abr("SP") == ("uf", "sp", "")
    assert M.nivel_abr("sp71072") == ("municipio", "sp", "71072")
    cedo = datetime(2026, 10, 25, tzinfo=timezone.utc)
    assert M.prioridade(cedo) > M.prioridade(cedo + timedelta(hours=1))


def test_colunas_batem_com_o_schema_sql():
    sql = (RAIZ / "scripts" / "ch" / "schema.sql").read_text(encoding="utf-8")
    for tabela, cols in M.COLUNAS.items():
        ini = sql.index(f"dataurnas.{tabela}\n")
        bloco = sql[ini:sql.index("ENGINE", ini)]
        for c in cols:
            assert f"\n    {c} " in bloco or f" {c} " in bloco, (tabela, c)


def test_processar_versoes_gera_linhas_de_todas_as_tabelas(tmp_path):
    p = _parte(tmp_path / "versoes-lote1-00001.parquet", _linhas_padrao())
    out = M.processar_versoes(str(p), "orig", ELEICAO_FIXTURE, 1)

    assert len(out["versoes_arquivo"]) == 5
    assert len(out["arquivos_conteudo"]) == 5
    cols = M.COLUNAS["versoes_arquivo"]
    va = [dict(zip(cols, r, strict=True)) for r in out["versoes_arquivo"]]
    assert {r["lote"] for r in va} == {"lote1-00001"}
    vota = next(r for r in va if r["tipo"] == "vota")
    assert vota["modelo_urna_cod"] == 22
    bu = next(r for r in va if r["tipo"] == "bu" and r["secao"] == "0077")
    assert bu["recebimento"] == M.dt_brt("25/10/2026", "21:07:27")

    aux = [dict(zip(M.COLUNAS["aux_versoes"], r, strict=True)) for r in out["aux_versoes"]]
    assert len(aux) == 2
    a1 = next(r for r in aux if r["secao"] == "0077")
    assert (a1["n_hashes"], a1["idx_hash"], a1["hash"]) == (1, 1, "abc")
    assert a1["arquivos"] == ["bu:o0-bu.dat", "vota:o0-vota.vsc"]
    a2 = next(r for r in aux if r["secao"] == "0078")
    assert (a2["n_hashes"], a2["idx_hash"], a2["hash"]) == (0, 0, "")

    bus = [dict(zip(M.COLUNAS["bu_secao"], r, strict=True)) for r in out["bu_secao"]]
    ok = next(r for r in bus if r["secao"] == "0077")
    ruim = next(r for r in bus if r["secao"] == "0079")
    assert ok["erro"] == "" and ok["tem_presidente"] is True
    assert ok["hora_encerramento"] == M.dt_urna("20261004T154041")
    assert ruim["erro"] and ruim["tem_presidente"] is False
    votos = [dict(zip(M.COLUNAS["bu_votos"], r, strict=True)) for r in out["bu_votos"]]
    assert votos and all(v["sha512_bu"] == ok["sha512"] for v in votos)
    assert sum(v["votos"] for v in votos) == ok["votos_total"]


def test_eleicao_errada_nao_gera_votos(tmp_path):
    p = _parte(tmp_path / "versoes-x.parquet", [_linha("bu", BU)])
    out = M.processar_versoes(str(p), "o", M.ELEICAO_T2, 1)
    assert out["bu_votos"] == []
    assert dict(zip(M.COLUNAS["bu_secao"], out["bu_secao"][0], strict=True))["tem_presidente"] is False


def test_listar_fontes_ignora_tmp_ocultos_e_recentes(tmp_path):
    base = tmp_path / "coleta"
    partes = base / "bus" / "parts"
    _parte(partes / "versoes-a.parquet", [_linha("aux", b"{}")])
    _parte(partes / "versoes-recente.parquet", [_linha("aux", b"{}")], idade=0)
    (partes / "versoes-b.tmp").write_bytes(b"x")
    (partes / ".versoes-c.parquet.XYZ").write_bytes(b"x")
    _parte(partes / "votos-a.parquet", [_linha("aux", b"{}")])
    (base / "totais").mkdir()
    (base / "totais" / "indice.jsonl").write_text("")
    fontes = M.listar_fontes({"coleta": base}, idade_minima=10)
    nomes = sorted((f.tipo_fonte, f.caminho.name) for f in fontes)
    assert nomes == [("totais", "indice.jsonl"), ("versoes", "versoes-a.parquet")]


def test_descobrir_origens(tmp_path):
    (tmp_path / "dataurnas-versoes-t2" / "bus").mkdir(parents=True)
    (tmp_path / "dataurnas-versoes-t2-nne" / "totais").mkdir(parents=True)
    (tmp_path / "dataurnas-mac" / "versoes" / "2026" / "t2-sseco" / "bus").mkdir(parents=True)
    (tmp_path / "dataurnas-versoes-t2-vazia").mkdir()
    o = M.descobrir_origens(tmp_path)
    assert sorted(o) == ["dataurnas-mac/versoes/2026/t2-sseco", "dataurnas-versoes-t2",
                         "dataurnas-versoes-t2-nne"]


def test_jsonl_incremental_so_le_linhas_completas(tmp_path):
    p = tmp_path / "a.jsonl"
    p.write_bytes(b'{"a":1}\n{"a":2}\n{"a":')
    linhas, d = M.ler_jsonl_novo(p, 0)
    assert linhas == [b'{"a":1}', b'{"a":2}'] and d == 16
    with open(p, "ab") as fh:
        fh.write(b'3}\n')
    linhas, d2 = M.ler_jsonl_novo(p, d)
    assert linhas == [b'{"a":3}'] and d2 == p.stat().st_size
    p.write_bytes(b'{"a":9}\n')  # reescrito menor: recomeça do zero
    linhas, d3 = M.ler_jsonl_novo(p, d2)
    assert linhas == [b'{"a":9}'] and d3 == 8


def test_linhas_totais_e_alertas():
    ln = json.dumps({"coletado_em": "2026-10-26T00:25:35+0000", "abr": "ac01007",
                     "sha256": "s1", "dg": "25/10/2026", "hg": "21:24:30", "idg": "41",
                     "st": 10, "ts": 12, "tv": 100, "vb": 2, "tvn": 3,
                     "cand": {"22": 60, "13": 35}}).encode()
    t = dict(zip(M.COLUNAS["totais_versoes"], M.linhas_totais([ln, b"lixo"], "o")[0], strict=True))
    assert (t["nivel"], t["uf"], t["cd_mun"], t["idg"], t["st"]) == ("municipio", "ac",
                                                                      "01007", 41, 10)
    assert t["cand"] == {"22": 60, "13": 35}
    assert t["totalizado_em"] == M.dt_brt("25/10/2026", "21:24:30")
    al = json.dumps({"em": "2026-10-26T01:00:00+0000", "tipo": "bu_votos_diferentes",
                     "secao": "ac/01007/0009/0001"}).encode()
    a = dict(zip(M.COLUNAS["alertas"], M.linhas_alertas([al], "o")[0], strict=True))
    assert (a["tipo"], a["secao"]) == ("bu_votos_diferentes", "ac/01007/0009/0001")
    assert json.loads(a["dados"])["tipo"] == "bu_votos_diferentes"


def _coleta(base: Path) -> Path:
    _parte(base / "bus" / "parts" / "versoes-l1-00001.parquet", _linhas_padrao())
    (base / "totais").mkdir(parents=True, exist_ok=True)
    reg = {"coletado_em": "2026-10-26T00:25:35+0000", "abr": "br", "sha256": "s1",
           "dg": "25/10/2026", "hg": "21:24:30", "idg": "1", "st": 1, "ts": 2,
           "tv": 3, "vb": 0, "tvn": 0, "cand": {"13": 2, "22": 1}}
    (base / "totais" / "indice.jsonl").write_text(json.dumps(reg) + "\n")
    (base / "alertas.jsonl").write_text(json.dumps({"em": "2026-10-26T01:00:00+0000",
                                                    "tipo": "x"}) + "\n")
    return base


@pytest.mark.parametrize("workers", [1, 2])
def test_ciclo_incremental_e_idempotente(tmp_path, workers):
    a = _coleta(tmp_path / "a")
    banco = BancoFalso()
    origens = {"a": a}
    r1 = M.ciclo(banco, origens, workers=workers, eleicao=ELEICAO_FIXTURE)
    assert r1["partes_ok"] == 1 and r1["jsonl_linhas"] == 2
    assert banco.n("versoes_arquivo") == 5 and banco.n("bu_secao") == 2
    assert banco.n("totais_versoes") == 1 and banco.n("alertas") == 1
    assert banco.n("bu_votos") > 0

    # segunda passada sem nada novo: não insere dados
    antes = {t: banco.n(t) for t in M.TABELAS_DADOS}
    r2 = M.ciclo(banco, origens, workers=workers, eleicao=ELEICAO_FIXTURE)
    assert r2["pendentes"] == 0
    assert {t: banco.n(t) for t in M.TABELAS_DADOS} == antes

    # linha nova no índice de totais e a mesma parte copiada em outra origem
    with open(a / "totais" / "indice.jsonl", "a") as fh:
        fh.write(json.dumps({"abr": "sp", "sha256": "s2", "idg": "2",
                             "coletado_em": "2026-10-26T00:30:00+0000"}) + "\n")
    b = tmp_path / "b" / "bus" / "parts"
    b.mkdir(parents=True)
    src = a / "bus" / "parts" / "versoes-l1-00001.parquet"
    dst = b / "versoes-l1-00001.parquet"
    dst.write_bytes(src.read_bytes())
    t = time.time() - 3600
    os.utime(dst, (t, t))
    r3 = M.ciclo(banco, {"a": a, "b": tmp_path / "b"}, workers=workers,
                 eleicao=ELEICAO_FIXTURE)
    assert r3["jsonl_linhas"] == 1 and r3["partes_repetidas"] == 1
    assert banco.n("totais_versoes") == 2
    assert banco.n("versoes_arquivo") == 5


def test_parte_corrompida_vira_erro_e_e_tentada_de_novo(tmp_path):
    base = tmp_path / "c"
    p = base / "bus" / "parts" / "versoes-ruim.parquet"
    p.parent.mkdir(parents=True)
    p.write_bytes(b"nao e parquet")
    t = time.time() - 3600
    os.utime(p, (t, t))
    banco = BancoFalso()
    r = M.ciclo(banco, {"c": base}, workers=1)
    assert r["partes_erro"] == 1
    assert banco.registro()[str(p)].status == "erro"
    assert M.pendentes(M.listar_fontes({"c": base}), banco.registro())
