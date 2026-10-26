"""Linha do tempo das seções e consistência dos totais no 2º turno de 2026."""

from __future__ import annotations

import gzip
import importlib.util
import json
from datetime import datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest

RAIZ = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent / "fixtures"


def _carregar():
    p = RAIZ / "scripts" / "ele2026" / "linha_tempo_t2.py"
    spec = importlib.util.spec_from_file_location("linha_tempo_t2", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


M = _carregar()
INI = datetime(2026, 10, 25, 17, 6)
FIM = datetime(2026, 10, 25, 19, 0)


def dt(hhmmss: str) -> datetime:
    h, m, s = (int(x) for x in hhmmss.split(":"))
    return datetime(2026, 10, 25, h, m, s)


# ---------------------------------------------------------------------------
# Horários
# ---------------------------------------------------------------------------

def test_parse_dr_hr():
    assert M.parse_dr_hr("25/10/2026", "19:32:29") == dt("19:32:29")
    assert M.parse_dr_hr(None, "19:32:29") is None
    assert M.parse_dr_hr("25/10/2026", "") is None
    assert M.parse_dr_hr("lixo", "19:32:29") is None


def test_parse_coletado_converte_para_brasilia():
    assert M.parse_coletado("2026-10-25T19:39:52-0300") == dt("19:39:52")
    assert M.parse_coletado("2026-10-25T22:39:52+0000") == dt("19:39:52")
    assert M.parse_coletado(None) is None


def test_janelas():
    assert M.hora_no_dia("17:06") == dt("17:06:00")
    assert M.parse_janela("17:20-19:00") == (dt("17:20:00"), dt("19:00:00"))


@pytest.mark.parametrize("rec,esperado", [
    (None, "sem_recebimento"),
    ("17:05:59", "antes_pausa"),
    ("17:06:00", "pausa"),
    ("19:00:00", "pausa"),
    ("19:00:01", "depois_pausa"),
])
def test_faixa_recebimento(rec, esperado):
    assert M.faixa_recebimento(dt(rec) if rec else None, INI, FIM) == esperado


@pytest.mark.parametrize("abr,ht,esperado", [
    ("ac01066", "17:32:25", "2026-10-25 19:32:25"),   # UTC-5
    ("ac", "17:39:00", "2026-10-25 19:39:00"),
    ("am", "16:07:30", "2026-10-25 17:07:30"),        # UTC-4
    ("am98477", "17:32:40", "2026-10-25 19:32:40"),   # Tabatinga, UTC-5
    ("pe30015", "20:04:51", "2026-10-25 19:04:51"),   # Fernando de Noronha, UTC-2
    ("ba38490", "21:54:28", "2026-10-25 21:54:28"),
    ("br", "19:39:33", "2026-10-25 19:39:33"),
])
def test_ht_em_horario_local_vira_brasilia(abr, ht, esperado):
    r = {"abr": abr, "dt": "25/10/2026", "ht": ht}
    assert M.fmt(M.ht_brasilia(r)) == esperado


def test_ht_exterior_sem_conversao():
    assert M.ht_brasilia({"abr": "zz29262", "dt": "25/10/2026", "ht": "00:05:24"}) is None
    assert M.ht_brasilia({"abr": "ba38490", "dt": "", "ht": ""}) is None


# ---------------------------------------------------------------------------
# Marcas por seção
# ---------------------------------------------------------------------------

def test_marcas():
    pac = [{"recebimento": dt("17:07:00")}, {"recebimento": dt("19:30:00")}]
    m = M.marcas(dt("19:30:00"), dt("17:01:00"), pac, 2, INI, FIM)
    assert m == {"m_recebido_na_pausa": False, "m_algum_pacote_na_pausa": True,
                 "m_recebido_mais_2h": True, "m_mais_de_um_pacote": True,
                 "m_bu_mais_de_uma_versao": True, "m_recebimento_antes_emissao": False}
    m = M.marcas(dt("17:00:00"), dt("17:01:00"), [{"recebimento": dt("17:00:00")}], 1,
                 INI, FIM)
    assert m["m_recebimento_antes_emissao"] and not m["m_recebido_mais_2h"]
    m = M.marcas(None, None, [], 0, INI, FIM)
    assert not any(m.values())


def _aux(hashes, dg="25/10/2026", hg="19:32:29"):
    return {"dg": dg, "hg": hg, "f": "O", "st": "Recebida",
            "hashes": [{"hash": h, "dr": "25/10/2026", "hr": hr, "st": "Recebido",
                        "arq": [{"nm": "x-bu.dat", "tp": "bu"}]} for h, hr in hashes]}


def _cache(**kw):
    base = {"erro": None, "emissao_local": "20261025T150500",
            "encerramento_local": "20261025T150000", "aptos": 300, "comparecimento": 200,
            "votos_13": 100, "votos_22": 80, "votos_outros": 0, "brancos": 5, "nulos": 15,
            "tem_presidente": True}
    base.update(kw)
    return base


def test_montar_secao_acre_com_duas_versoes_de_bu():
    sec = M.Secao()
    sec.add_aux("a1", "2026-10-25T19:40:00-0300", _aux([("h1", "17:07:10")]))
    sec.add_aux("a2", "2026-10-25T20:00:00-0300",
                _aux([("h1", "17:07:10"), ("h2", "19:50:00")], hg="19:50:00"))
    sec.add_bu("s1", {"coletado_em": "2026-10-25T19:40:01-0300", "hash": "h1", "tipo": "bu",
                      "dt_recebimento": "25/10/2026", "hr_recebimento": "17:07:10"})
    sec.add_bu("s2", {"coletado_em": "2026-10-25T20:00:01-0300", "hash": "h2", "tipo": "bu",
                      "dt_recebimento": "25/10/2026", "hr_recebimento": "19:50:00"})
    cache = {"s1": _cache(), "s2": _cache(votos_13=99, nulos=16)}
    ln, mult = M.montar_secao(("ac", "01066", "0004", "0164"), sec, cache, INI, FIM)
    assert ln["fuso_utc"] == -5
    assert ln["emissao_local"] == "2026-10-25 15:05:00"
    assert ln["emissao_bsb"] == "2026-10-25 17:05:00"
    assert ln["recebimento_bu"] == "2026-10-25 19:50:00"   # última versão
    assert ln["recebimento_primeiro"] == "2026-10-25 17:07:10"
    assert ln["primeira_coleta_aux"] == "2026-10-25 19:40:00"
    assert ln["n_pacotes"] == 2 and ln["n_versoes_aux"] == 2 and ln["n_versoes_bu"] == 2
    assert ln["m_algum_pacote_na_pausa"] and not ln["m_recebido_na_pausa"]
    assert ln["m_mais_de_um_pacote"] and ln["m_bu_mais_de_uma_versao"]
    assert ln["votos_diferem_entre_versoes"] and not ln["mesmo_hash_conteudo_diferente"]
    assert ln["atraso_recebimento_min"] == 165.0
    assert [m["versao"] for m in mult] == [1, 2]


def test_montar_secao_mesmo_hash_conteudo_diferente():
    sec = M.Secao()
    sec.add_aux("a1", "2026-10-25T19:40:00-0300", _aux([("h1", "19:20:00")]))
    for s, c in (("s1", "19:40:01"), ("s2", "20:40:01")):
        sec.add_bu(s, {"coletado_em": f"2026-10-25T{c}-0300", "hash": "h1", "tipo": "bu",
                       "dt_recebimento": "25/10/2026", "hr_recebimento": "19:20:00"})
    cache = {"s1": _cache(), "s2": _cache()}
    ln, _ = M.montar_secao(("ba", "38490", "0001", "0001"), sec, cache, INI, FIM)
    assert ln["mesmo_hash_conteudo_diferente"]
    assert not ln["votos_diferem_entre_versoes"]


def test_secao_guarda_primeira_coleta_de_cada_versao():
    sec = M.Secao()
    sec.add_bu("s1", {"coletado_em": "2026-10-25T20:00:00-0300"})
    sec.add_bu("s1", {"coletado_em": "2026-10-25T19:40:00-0300"})
    sec.add_bu("s1", {"coletado_em": "2026-10-25T21:00:00-0300"})
    assert sec.bus["s1"]["coletado_em"] == "2026-10-25T19:40:00-0300"


def test_verificar_fuso_recebimento():
    linhas = [{"fuso_utc": -5, "emissao_bsb": "2026-10-25 17:02:00",
               "recebimento_bu": "2026-10-25 17:05:00"},
              {"fuso_utc": -5, "emissao_bsb": "2026-10-25 17:03:00",
               "recebimento_bu": "2026-10-25 19:30:00"}]
    v = M.verificar_fuso_recebimento(linhas, INI, FIM)["-5"]
    assert v["hr_como_brasilia"]["min"] == 3.0
    assert v["hr_como_local"]["min"] == 123.0
    assert v["recebidos_antes_da_pausa"] == 1


# ---------------------------------------------------------------------------
# Totais
# ---------------------------------------------------------------------------

def _versao(abr, hg, st, ts, c13, c22, vb=1, tvn=1, idg="1", ht=None, sha=None):
    tv = c13 + c22 + vb + tvn
    return {"abr": abr, "dg": "25/10/2026", "hg": hg, "idg": idg, "dt": "25/10/2026",
            "ht": ht or hg, "st": st, "ts": ts, "tv": tv, "vb": vb, "tvn": tvn, "c": tv,
            "cand": {"13": c13, "22": c22}, "sha256": sha or f"{abr}{hg}",
            "coletado_em": f"2026-10-25T{hg}-0300"}


def test_regressoes_e_soma_interna():
    a = _versao("ba", "19:40:00", 10, 100, 50, 40)
    b = _versao("ba", "19:41:00", 9, 101, 49, 41)
    q = M.regressoes(a, b)
    assert "st: 10 -> 9" in q and "candidato 13: 50 -> 49" in q and "ts: 100 -> 101" in q
    assert not any("candidato 22" in x for x in q)
    assert M.soma_interna(a) == 0
    a["tv"] += 3
    assert M.soma_interna(a) == 3


def test_checar_versoes_ordena_pela_geracao():
    vs = [_versao("ba", "19:50:00", 20, 100, 60, 50, idg="3"),
          _versao("ba", "19:40:00", 10, 100, 50, 40, idg="2")]
    linhas, ultima = M.checar_versoes(vs, INI, FIM)
    assert [x["versao"] for x in linhas] == [1, 2]
    assert [x["hg"] for x in linhas] == ["19:40:00", "19:50:00"]
    assert all(x["regressoes"] is None for x in linhas)
    assert ultima["ba"]["hg"] == "19:50:00"


def test_checar_versoes_marca_pausa():
    vs = [_versao("am", "19:01:54", 5, 100, 3, 1, ht="16:07:30"),
          _versao("ba", "17:06:07", 5, 100, 3, 1, ht="17:05:23")]
    linhas, _ = M.checar_versoes(vs, INI, FIM)
    am = next(x for x in linhas if x["abr"] == "am")
    ba = next(x for x in linhas if x["abr"] == "ba")
    assert am["ht_na_pausa"] and not am["hg_na_pausa"]
    assert ba["hg_na_pausa"] and not ba["ht_na_pausa"]


def test_carregar_indice_sem_repeticao(tmp_path):
    for nome, col in (("a", "19:40:00"), ("b", "19:39:00")):
        d = tmp_path / nome
        (d / "ba").mkdir(parents=True)
        r = _versao("ba", "19:38:00", 10, 100, 50, 40, ht="19:37:00", sha="x")
        r["coletado_em"] = f"2026-10-25T{col}-0300"
        (d / "indice.jsonl").write_text(json.dumps(r) + "\n")
        bruto = {"dt": "25/10/2026", "ht": "19:37:00", "e": {"c": "92"}}
        (d / "ba" / "25102026_193800_1.json.gz").write_bytes(gzip.compress(
            json.dumps(bruto).encode()))
    idx = M.carregar_indice([tmp_path / "a", tmp_path / "b"])
    assert len(idx) == 1
    assert idx[0]["coletado_em"] == "2026-10-25T19:39:00-0300"
    assert idx[0]["bruto"] and idx[0]["c"] == 92


@pytest.mark.parametrize("n,st,ts,esperado", [
    (10, 10, 10, "completo"),
    (10, 10, 12, "contagem_igual"),
    (9, 10, 10, "bus_parciais"),
    (11, 10, 12, "oficial_defasado"),
    (5, None, None, "sem_oficial"),
])
def test_classificar(n, st, ts, esperado):
    assert M.classificar(n, st, ts) == esperado


def _bu(rec, c13, c22, br=1, nu=1):
    return {"recebimento_bu": rec, "comparecimento": c13 + c22 + br + nu,
            "votos_13": c13, "votos_22": c22, "brancos": br, "nulos": nu}


def test_comparar_igual_e_diferente():
    bus = [_bu("2026-10-25 19:10:00", 10, 5), _bu("2026-10-25 19:20:00", 7, 3)]
    of = _versao("ac01066", "19:30:00", 2, 2, 17, 8, vb=2, tvn=2)
    c = M.comparar("ac01066", bus, of)
    assert c["situacao"] == "completo" and c["comparado"] and not c["tem_diferenca"]
    of = _versao("ac01066", "19:30:00", 2, 2, 18, 8, vb=2, tvn=2)
    c = M.comparar("ac01066", bus, of)
    assert c["tem_diferenca"] and json.loads(c["diferencas"]) == {"votos_13": -1,
                                                                  "comparecimento": -1}
    of = _versao("ac01066", "19:30:00", 3, 3, 30, 8)
    c = M.comparar("ac01066", bus, of)
    assert c["situacao"] == "bus_parciais" and not c["comparado"] and c["dif_votos_13"] is None


def test_comparar_versoes_com_bus():
    bus = [_bu("2026-10-25 19:10:00", 10, 5), _bu("2026-10-25 19:20:00", 7, 3),
           _bu("2026-10-25 19:40:00", 1, 1)]
    vs = [_versao("ba38490", "19:15:30", 1, 3, 10, 5, ht="19:15:00"),
          _versao("ba38490", "19:30:30", 2, 3, 17, 8, vb=2, tvn=2, ht="19:30:00"),
          _versao("ba38490", "19:35:30", 3, 3, 18, 9, vb=3, tvn=3, ht="19:35:00"),
          _versao("ba38490", "19:16:30", 1, 3, 11, 5, ht="19:16:00"),
          _versao("ba38490", "19:00:30", 0, 3, 0, 0, vb=0, tvn=0, ht="")]
    linhas, _ = M.checar_versoes(vs, INI, FIM)
    M.comparar_versoes_com_bus(linhas, {"ba38490": bus}, {"ba38490": 3})
    por_hg = {x["hg"]: x for x in linhas}
    assert por_hg["19:15:30"]["bu_comparacao"] == "igual"
    assert por_hg["19:30:30"]["bu_comparacao"] == "igual"
    assert por_hg["19:30:30"]["bu_comparacao_ordem"] == "igual"
    t = por_hg["19:35:30"]
    assert t["bu_comparacao"] == "totalizadas_mais_que_recebidas"
    assert t["bu_ate_ht_secoes"] == 2 and t["folga_s"] == 300
    assert t["bu_comparacao_ordem"] == "igual"
    d = por_hg["19:16:30"]
    assert d["bu_comparacao"] == "difere" and json.loads(d["bu_diferencas"])["votos_13"] == -1
    assert por_hg["19:00:30"]["bu_comparacao"] == "sem_secoes_totalizadas"


def test_comparar_versoes_sem_cobertura():
    vs = [_versao("ba38490", "19:30:30", 2, 3, 17, 8, ht="19:30:00")]
    linhas, _ = M.checar_versoes(vs, INI, FIM)
    M.comparar_versoes_com_bus(linhas, {"ba38490": [_bu("2026-10-25 19:10:00", 1, 1)]},
                               {"ba38490": 3})
    assert linhas[0]["bu_comparacao"] == "sem_cobertura"


def test_marcar_recebimento_apos_totalizacao():
    bus = [_bu("2026-10-25 19:10:00", 1, 1), _bu("2026-10-25 21:00:00", 1, 1)]
    vs = [_versao("pb19267", "19:25:00", 2, 2, 2, 2, ht="19:24:56"),
          _versao("pb19267", "21:05:00", 2, 2, 2, 2, ht="21:04:00", sha="b")]
    linhas, _ = M.checar_versoes(vs, INI, FIM)
    M.marcar_recebimento_apos_totalizacao(linhas, {"pb19267": bus})
    assert bus[0]["recebimento_menos_totalizacao_s"] < 0
    assert not bus[0]["m_recebimento_apos_totalizacao"]
    assert bus[1]["recebimento_menos_totalizacao_s"] == 5704
    assert bus[1]["m_recebimento_apos_totalizacao_15min"]


def test_distribuicao():
    assert M.distribuicao([]) == {"n": 0}
    d = M.distribuicao([5, 1, 3])
    assert d["min"] == 1 and d["max"] == 5 and d["p50"] == 3


# ---------------------------------------------------------------------------
# Execução completa em dados sintéticos com BU real
# ---------------------------------------------------------------------------

def test_main_ponta_a_ponta(tmp_path):
    from dataurnas.downloader.ele2026 import bu_to_rows
    raw = (FIXTURES / "bu_ac_m01066_z0004_s0077.bin").read_bytes()
    campos, votos = bu_to_rows(raw, 6258, 1)
    c13 = sum(v["votos"] for v in votos if v["numero"] == 13)
    c22 = sum(v["votos"] for v in votos if v["numero"] == 22)

    parts = tmp_path / "parts"
    parts.mkdir()
    ident = {"uf": "ac", "cd_mun": "01066", "zona": "0004", "secao": "0077"}
    aux = json.dumps(_aux([("h1", "19:20:00")], hg="19:20:00")).encode()
    linhas = [
        {**ident, "coletado_em": "2026-10-25T19:40:00-0300", "tipo": "aux", "hash": None,
         "st_secao": "Recebida", "st_hash": None, "dt_recebimento": None,
         "hr_recebimento": None, "nome": None, "sha512": "aux1", "tamanho": len(aux),
         "conteudo": aux},
        {**ident, "coletado_em": "2026-10-25T19:40:01-0300", "tipo": "bu", "hash": "h1",
         "st_secao": "Recebida", "st_hash": "Recebido", "dt_recebimento": "25/10/2026",
         "hr_recebimento": "19:20:00", "nome": "x-bu.dat", "sha512": "bu1",
         "tamanho": len(raw), "conteudo": raw},
    ]
    pq.write_table(pa.Table.from_pylist(linhas), parts / "versoes-1.parquet")

    tot = tmp_path / "totais"
    vb, nu = campos["votos_brancos"], campos["votos_nulos"]
    idx = []
    for abr in ("ac01066", "ac"):
        r = _versao(abr, "19:30:00", 1, 1, c13, c22, vb=vb, tvn=nu, ht="17:29:00")
        r["c"] = None
        idx.append(r)
        (tot / abr).mkdir(parents=True)
        bruto = {"dt": "25/10/2026", "ht": "17:29:00",
                 "e": {"c": str(campos["comparecimento"])}}
        (tot / abr / "25102026_193000_1.json.gz").write_bytes(
            gzip.compress(json.dumps(bruto).encode()))
    (tot / "indice.jsonl").write_text("".join(json.dumps(r) + "\n" for r in idx))

    saida = tmp_path / "saida"
    assert M.main(["--parts", str(parts), "--totais", str(tot), "--saida", str(saida),
                   "--sem-download", "--workers", "1"]) == 0
    resumo = json.loads((saida / "resumo.json").read_text())
    assert resumo["secoes_com_bu"] == 1
    assert resumo["ufs_comparadas"] == ["ac"]
    assert resumo["ufs_com_diferenca"] == []
    assert resumo["municipios"] == {"completo": 1}
    assert resumo["totais"]["versoes_com_regressao"] == 0
    assert resumo["totais"]["bu_x_versoes"] == {"igual": 2}
    sec = pq.read_table(saida / "secoes.parquet").to_pylist()[0]
    assert sec["recebimento_bu"] == "2026-10-25 19:20:00"
    assert sec["faixa_recebimento"] == "depois_pausa"
    assert sec["fuso_utc"] == -5
    assert (saida / "cache_bu.parquet").exists()
    # segunda execução usa o cache e chega ao mesmo resultado
    assert M.main(["--parts", str(parts), "--totais", str(tot), "--saida", str(saida),
                   "--sem-download", "--workers", "1"]) == 0
    r2 = json.loads((saida / "resumo.json").read_text())
    assert r2["leitura"].get("bu_decodificados", 0) == 0
    assert r2["comparacao_br"]["bu_secoes"] == 1


# ---------------------------------------------------------------------------
# Curva recebimento x totalização, atrasos por município e Last-Modified
# ---------------------------------------------------------------------------

def _sec(cd, secao, rec, emissao="2026-10-25 17:05:00", uf="ba"):
    return {"uf": uf, "cd_mun": cd, "zona": "0001", "secao": secao, "recebimento_bu": rec,
            "emissao_bsb": emissao, "primeira_coleta_aux": None,
            "atraso_recebimento_min": M.minutos(
                datetime.strptime(emissao, "%Y-%m-%d %H:%M:%S"),
                datetime.strptime(rec, "%Y-%m-%d %H:%M:%S"))}


def test_curva_marca_excesso_e_lista_secoes():
    secs = [_sec("38490", "0001", "2026-10-25 19:10:00"),
            _sec("38490", "0002", "2026-10-25 19:31:00"),
            _sec("38490", "0003", "2026-10-25 19:33:00")]
    vs = [_versao("ba38490", "19:20:00", 1, 3, 1, 1, ht="19:19:50"),
          _versao("ba38490", "19:30:00", 3, 3, 3, 3, ht="19:29:50")]
    linhas, ultima = M.checar_versoes(vs, INI, FIM)
    curva, exc = M.curva_recebimento_totalizacao(linhas, {"ba38490": secs}, ultima)
    por_v = {c["versao"]: c for c in curva}
    assert por_v[1]["excesso_hg"] == 0
    assert por_v[2]["recebidas_ate_hg"] == 1 and por_v[2]["excesso_hg"] == 2
    assert [e["secao"] for e in exc] == ["0002", "0003"]
    assert [e["recebimento_menos_hg_s"] for e in exc] == [60, 180]


def test_curva_ignora_cobertura_insuficiente():
    secs = [_sec("38490", "0001", "2026-10-25 19:10:00")]
    vs = [_versao("ba38490", "19:30:00", 2, 3, 3, 3)]
    linhas, ultima = M.checar_versoes(vs, INI, FIM)
    assert M.curva_recebimento_totalizacao(linhas, {"ba38490": secs}, ultima) == ([], [])


def test_atraso_por_municipio_e_destaque_ba():
    secs = [_sec("38490", "0001", "2026-10-25 21:05:00"),
            _sec("38490", "0002", "2026-10-25 19:05:00"),
            _sec("35157", "0001", "2026-10-25 19:35:00"),
            _sec("00000", "0001", "2026-10-25 17:10:00")]
    am = {(x["cd_mun"]): x for x in M.atraso_por_municipio(secs)}
    assert am["38490"]["n"] == 2 and am["38490"]["max"] == 240.0
    d = M.destaque_ba(secs)
    assert d["Salvador"]["recebidos_depois_de_21h_pct"] == 50.0
    assert d["Feira de Santana"]["n"] == 1
    assert d["resto_da_ba"]["min"] == 5.0


def test_head_last_modified_com_cache(tmp_path, monkeypatch):
    chamadas = []

    class Resp:
        headers = {"Last-Modified": "Mon, 26 Oct 2026 00:06:34 GMT"}

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def falso_urlopen(req, timeout=30):
        chamadas.append(req.get_method())
        return Resp()

    monkeypatch.setattr(M.urllib.request, "urlopen", falso_urlopen)
    monkeypatch.setattr(M.time, "sleep", lambda s: None)
    ln = {**_sec("38490", "0002", "2026-10-25 21:06:30"), "nome_bu": "o-bu.dat",
          "hash_bu": "h1", "sha512_bu": "s1"}
    destino = tmp_path / "lm.parquet"
    r = M.head_last_modified([ln], destino, 5, 9.0, [])
    assert chamadas == ["HEAD"]
    assert r["last_modified_menos_recebimento_s_por_grupo"]["Salvador"]["max"] == 4
    r = M.head_last_modified([ln], destino, 5, 9.0, [])
    assert chamadas == ["HEAD"]   # segunda vez vem do cache
    assert r["com_last_modified"] == 1
