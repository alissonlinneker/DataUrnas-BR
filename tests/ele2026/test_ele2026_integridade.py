"""Testes da auditoria de integridade de 2026 (sem rede).

Fixtures reais do 1º turno de 2026:
  - bu_ac_m01066_z0004_s0077.bin   BU da seção AC 01066/0004/0077
  - vsc_ac_m01066_z0004_s0077.bin  -vota.vsc da mesma seção (UE2022, Ed521)
  - vsc_am_m02550_z0001_s0645.bin  -vota.vsc de AM 02550/0001/0645 (UE2015, ECDSA P-521)
"""

import hashlib
import importlib.util
import json
import logging
from pathlib import Path

import pytest

pytest.importorskip("cryptography")

from dataurnas.analyzer import integrity as I  # noqa: E402
from dataurnas.parsers import ed521  # noqa: E402
from dataurnas.parsers.signature import parse_vsc, verificar_vsc  # noqa: E402

FIX = Path(__file__).parent / "fixtures"
BU_AC = FIX / "bu_ac_m01066_z0004_s0077.bin"
VSC_AC = FIX / "vsc_ac_m01066_z0004_s0077.bin"
VSC_AM = FIX / "vsc_am_m02550_z0001_s0645.bin"
NOME_BU = "o03220ac0106600040077-bu.dat"
NOME_VSC = "o03220ac0106600040077-vota.vsc"
IDENT = {"uf": "ac", "cd_mun": "01066", "zona": "0004", "secao": "0077"}


@pytest.fixture(scope="module")
def vsc_ac() -> bytes:
    return VSC_AC.read_bytes()


@pytest.fixture(scope="module")
def bu_ac() -> bytes:
    return BU_AC.read_bytes()


# --- parse do .vsc ----------------------------------------------------------

def test_parse_vsc_estrutura(vsc_ac):
    v = parse_vsc(vsc_ac)
    assert v["modelo_cod"] == 22
    assert v["algoritmo_hw_cod"] == 4
    sw, hw = v["sw"], v["hw"]
    assert sw["algoritmo_assinatura"] == "cepesc" and sw["usuario"] == "SEVIN"
    assert hw["algoritmo_assinatura"] == "eddsa" and hw["bits"] == 521
    assert hw["algoritmo_hash"] == "sha512"
    assert hw["usuario"] == "UEAO" and hw["serial"] == 2293919
    assert hw["data_hora"] == "20261004T154502"
    assert sw["conjunto_chave"] == "202607021654"
    assert hw["certificado"].startswith(b"-----BEGIN CERTIFICATE-----")
    nomes = [a["nome"] for a in hw["arquivos"]]
    assert nomes == [a["nome"] for a in sw["arquivos"]]
    assert len(nomes) == 11 and NOME_BU in nomes
    assert all(len(a["hash"]) == 64 for a in hw["arquivos"])
    assert all(len(a["assinatura"]) == 132 for a in hw["arquivos"])
    # autoAssinado: hash = SHA-512 do conteúdo assinado
    assert hashlib.sha512(hw["conteudo"]).digest() == hw["hash"]
    assert hashlib.sha512(sw["conteudo"]).digest() == sw["hash"]


def test_hash_assinado_confere_com_bu(vsc_ac, bu_ac):
    hashes = {a["nome"]: a["hash"] for a in parse_vsc(vsc_ac)["hw"]["arquivos"]}
    assert hashes[NOME_BU] == hashlib.sha512(bu_ac).digest()


def test_parse_vsc_rejeita_lixo():
    with pytest.raises((ValueError, IndexError)):
        parse_vsc(b"\x04\x03abc")


# --- verificação criptográfica ---------------------------------------------

def test_verificar_vsc_ed521(vsc_ac):
    r = verificar_vsc(vsc_ac, {NOME_BU})
    assert r["assinatura_valida"] is True, r["falhas"]
    assert r["algoritmo"] == "Ed521"
    assert r["assinaturas_arquivos"] == {NOME_BU: True}
    assert r["cert_subject"] == "O=TSE,C=BR,CN=UEAO02293919"
    assert "CN=AC UE2022" in r["cert_issuer"]
    assert r["cert_serial"] == "30b3c"
    assert len(r["cert_sha256"]) == 64
    assert r["falhas"] == [] and r["motivos"] == []


def test_verificar_vsc_ecdsa_p521():
    r = verificar_vsc(VSC_AM.read_bytes(), {"o03220am0255000010645-bu.dat"})
    assert r["assinatura_valida"] is True, r["falhas"]
    assert r["algoritmo"] == "ECDSA-secp521r1-SHA512"
    assert r["modelo_cod"] == 15
    assert "CN=AC URNA" in r["cert_issuer"]


def test_ed521_rejeita_assinatura_ou_mensagem_alteradas(vsc_ac):
    v = parse_vsc(vsc_ac)
    hw = v["hw"]
    from dataurnas.parsers.signature import _chave_ed521_do_certificado, info_certificado

    chave = _chave_ed521_do_certificado(info_certificado(hw["certificado"])["_der"])
    msg = hashlib.sha512(hw["hash"]).digest()
    assert ed521.verificar(chave, msg, hw["assinatura"]) is True
    adulterada = bytearray(hw["assinatura"])
    adulterada[100] ^= 1
    assert ed521.verificar(chave, msg, bytes(adulterada)) is False
    assert ed521.verificar(chave, hw["hash"], hw["assinatura"]) is False
    assert ed521.verificar(chave, msg, hw["assinatura"][:-1]) is False


def test_vsc_com_conteudo_adulterado_e_invalido(vsc_ac):
    v = parse_vsc(vsc_ac)
    # troca um byte do hash do bu.dat dentro do conteúdo da parte HW
    h = v["hw"]["arquivos"][0]["hash"]
    i = vsc_ac.rfind(h)
    raw = bytearray(vsc_ac)
    raw[i] ^= 0xFF
    r = verificar_vsc(bytes(raw), {NOME_BU})
    assert r["assinatura_valida"] is False
    assert any("autoassinado" in f for f in r["falhas"])


# --- auditoria de conjunto e caminho de divergência ------------------------

def _divs(r: dict) -> list[dict]:
    """Divergências, sem as de rdv/log ausentes (as fixtures só têm bu e vsc)."""
    return [d for d in r["divergencias"] if d["categoria"] != "arquivo_ausente_tse"]


def _conjunto(bu: bytes, vsc: bytes) -> dict:
    return {"token": "TOKEN", "data_hora": "04/10/2026 18:34:08",
            "arquivos": [("bu", NOME_BU, bu), ("vota", NOME_VSC, vsc)]}


def test_auditar_conjunto_ok(vsc_ac, bu_ac):
    r = I.auditar_conjunto(IDENT, _conjunto(bu_ac, vsc_ac))
    assert _divs(r) == []
    por_nome = {x["nome"]: x for x in r["linhas"]}
    bu = por_nome[NOME_BU]
    assert bu["tipo"] == "bu" and bu["hash_confere"] is True
    assert bu["sha512"] == bu["sha512_assinado"] == hashlib.sha512(bu_ac).hexdigest()
    assert bu["md5"] == hashlib.md5(bu_ac).hexdigest()
    assert bu["sha256"] == hashlib.sha256(bu_ac).hexdigest()
    assert bu["tamanho"] == len(bu_ac)
    vsc = por_nome[NOME_VSC]
    assert vsc["tipo"] == "vota"
    assert vsc["sha512_assinado"] is None and vsc["hash_confere"] is None


def test_auditar_conjunto_bu_adulterado_gera_hash_diverge(vsc_ac, bu_ac):
    adulterado = bytearray(bu_ac)
    adulterado[-1] ^= 0x01
    r = I.auditar_conjunto(IDENT, _conjunto(bytes(adulterado), vsc_ac))
    [d] = _divs(r)
    assert d["categoria"] == "hash_diverge"
    assert d["arquivo"] == NOME_BU
    assert d["sha512_calculado"] == hashlib.sha512(bytes(adulterado)).hexdigest()
    assert d["sha512_assinado"] == hashlib.sha512(bu_ac).hexdigest()
    assert {k: d[k] for k in IDENT} == IDENT
    linha = next(x for x in r["linhas"] if x["nome"] == NOME_BU)
    assert linha["hash_confere"] is False


def test_auditar_conjunto_sem_hash_assinado_e_arquivo_ausente(vsc_ac, bu_ac):
    c = _conjunto(bu_ac, vsc_ac)
    c["arquivos"].append(("other", "o03220ac0106600040077-extra.dat", b"x"))
    r = I.auditar_conjunto(IDENT, c)
    cats = {(d["categoria"], d["arquivo"]) for d in r["divergencias"]}
    assert ("hash_assinado_ausente", "o03220ac0106600040077-extra.dat") in cats
    # rdv.dat e log.jez estão no .vsc, mas não foram passados como publicados
    assert ("arquivo_ausente_tse", "o03220ac0106600040077-rdv.dat") in cats
    assert ("arquivo_ausente_tse", "o03220ac0106600040077-log.jez") in cats
    # arquivos que o TSE não publica por padrão não contam
    assert not any("jufa" in a or "wsq" in a for _, a in cats)


def test_auditar_conjunto_assinatura_invalida(vsc_ac, bu_ac):
    raw = bytearray(vsc_ac)
    v = parse_vsc(vsc_ac)
    i = vsc_ac.find(v["hw"]["assinatura"])
    raw[i + 70] ^= 0x01  # altera S da assinatura do autoAssinado
    r = I.auditar_conjunto(IDENT, _conjunto(bu_ac, bytes(raw)))
    assert [d["categoria"] for d in _divs(r)] == ["assinatura_invalida"]
    assert r["verificacao"]["assinatura_valida"] is False


def test_auditar_secao_votos_e_campos(vsc_ac, bu_ac):
    votos = I._votos_bu(bu_ac)
    r = I.auditar_secao(IDENT, [_conjunto(bu_ac, vsc_ac)], 0, votos)
    s = r["secao"]
    assert s["status_secao"] == "ok" and s["n_arquivos"] == 2
    assert (s["n_hash_confere"], s["n_hash_diverge"], s["n_sem_hash"]) == (1, 0, 1)
    assert s["assinatura_valida"] is True and s["assinatura_algoritmo"] == "Ed521"
    assert s["modelo_urna"] == "UE2022" and s["votos_conferem"] is True
    r2 = I.auditar_secao(IDENT, [_conjunto(bu_ac, vsc_ac)], 0, (("nominal", 13, 1),))
    assert r2["secao"]["votos_conferem"] is False


def test_tipo_arquivo():
    assert I.tipo_arquivo("sa", "x-sa.vsc") == "vota"
    assert I.tipo_arquivo("logsa", "x-logsa.jez") == "log"
    assert I.tipo_arquivo("busa", "x-busa.dat") == "busa"
    assert I.tipo_arquivo("novo", "x.bin") == "other"


# --- registro imediato da divergência (script) -----------------------------

def _carregar_script():
    p = Path(__file__).resolve().parents[2] / "scripts" / "ele2026" / "fetch_integridade.py"
    spec = importlib.util.spec_from_file_location("fetch_integridade", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_divergencia_gravada_na_hora_e_logada(tmp_path, caplog, vsc_ac, bu_ac):
    mod = _carregar_script()
    adulterado = bu_ac[:-1] + bytes([bu_ac[-1] ^ 1])
    r = I.auditar_conjunto(IDENT, _conjunto(adulterado, vsc_ac))
    reg = mod.Divergencias(tmp_path / "divergencias.jsonl")
    with caplog.at_level(logging.WARNING, logger="fetch_integridade"):
        for d in _divs(r):
            reg.registrar(d)
    linhas = (tmp_path / "divergencias.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(linhas) == 1
    d = json.loads(linhas[0])
    for k in ("uf", "cd_mun", "zona", "secao", "arquivo", "sha512_calculado",
              "sha512_assinado", "motivo", "categoria"):
        assert k in d
    assert d["categoria"] == "hash_diverge"
    assert any(m.startswith("DIVERGENCIA ") for m in caplog.messages)


def test_token_tse():
    mod = _carregar_script()
    hx = "4a6b704a7350756e6a5a496433337049453538516932486a676159553779785542752d6d765749354f41343d"
    assert mod.token_tse(hx) == "JkpJsPunjZId33pIE58Qi2HjgaYU7yxUBu-mvWI5OA4="


# --- auditoria por seção de 2022 aplicada a 2026 (BU e log em memória) -----

def _log_zip(linhas: list[str]) -> bytes:
    """Log sintético no formato de 2026 (ZIP com logd.dat em latin-1)."""
    import io
    import zipfile

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("logd.dat", "\n".join(linhas).encode("latin-1"))
    return buf.getvalue()


def _linha(hora: str, desc: str, data: str = "04/10/2026") -> str:
    return f"{data} {hora}\tINFO\t02293919\tVOTA\t{desc}\tABCDEF0123456789"


def test_log_2026_em_zip_e_lido_em_memoria():
    from dataurnas.parsers.log import LogParser

    raw = _log_zip([_linha("06:00:00", "Urna pronta para receber votos"),
                    _linha("06:10:00", "O voto do eleitor foi computado")])
    entries = LogParser().parse_bytes(raw)
    assert [e.hora for e in entries] == ["06:00:00", "06:10:00"]


def test_analise_secao_bytes_horarios_fuso_e_reinicio(bu_ac):
    """AC (UTC-5, offset -2 h): 06h local = 08h de Brasília. Duas aberturas
    no dia do turno = 1 reinício (C06)."""
    from dataurnas.analyzer.batch import BatchAnalyzer
    from dataurnas.database.rows import SECOES_COLUMNS, extract_rows

    log = _log_zip([
        _linha("06:00:00", "Urna pronta para receber votos"),
        _linha("07:00:00", "Início das operações do logd"),
        _linha("07:01:00", "Urna pronta para receber votos"),
        *[_linha("07:30:00", "O voto do eleitor foi computado")] * 234,
        _linha("15:05:00", "Início do Encerramento"),
    ])
    loc = {"uf": "ac", "municipio": "01066", "zona": "0004", "secao": "0077"}
    r = BatchAnalyzer().analyze_section_bytes(loc, bu_ac, log, turno=1,
                                              turno_date="04/10/2026", modelo="2022")
    linha = dict(zip(SECOES_COLUMNS, extract_rows(r).secao, strict=True))
    assert linha["fuso_offset"] == -2
    assert linha["hora_abertura"] == "04/10/2026 06:00:00"
    assert linha["hora_encerramento"] == "04/10/2026 15:05:00"
    assert linha["duracao_min"] == 545
    assert linha["votos_log"] == 234 and linha["comparecimento"] == 234
    # biometria da spec v2: HabilitadosPorBiometria e HabilitadosPorBiografia
    assert (linha["comp_biometrico"], linha["lib_codigo"]) == (212, 13)
    codigos = {i.codigo for i in r["issues"]}
    assert "C06" in codigos
    # abertura 08h e encerramento 17h05 de Brasília: sem M01/A04/A05
    assert not codigos & {"M01", "A04", "A05", "A03"}
    # Senador com 2 vagas em 2026 (468 votos para 234 eleitores) não é C05/A02
    assert not codigos & {"C05", "A02"}


def test_a01_desconta_voto_em_transito():
    from dataurnas.analyzer.integrity import ConsistencyAnalyzer, aptos_sem_transito
    from dataurnas.models import BoletimUrna, ResultadoEleicao

    def bu(federal: ResultadoEleicao, estadual: ResultadoEleicao) -> BoletimUrna:
        b = BoletimUrna.__new__(BoletimUrna)
        b.resultados_por_eleicao = [federal, estadual]
        b.uf, b.municipio, b.zona, b.secao = "sp", 71072, 1, 1
        return b

    def el(i, aptos, secao, tte):
        e = ResultadoEleicao.__new__(ResultadoEleicao)
        e.id_eleicao, e.eleitores_aptos = i, aptos
        e.eleitores_aptos_secao, e.eleitores_aptos_tte = secao, tte
        e.resultados = []
        return e

    ca = ConsistencyAnalyzer()
    # 300 da seção + 12 em trânsito só na federal: não é A01
    assert ca.check_cross_election_consistency(
        bu(el(6257, 312, 300, 12), el(6259, 300, 300, 0))) == []
    # sem aptos_secao: usa aptos - aptos_tte
    assert aptos_sem_transito(el(6257, 312, None, 12)) == 300
    assert ca.check_cross_election_consistency(
        bu(el(6257, 312, None, 12), el(6259, 300, None, 0))) == []
    # divergência real do eleitorado da seção continua sendo A01
    [issue] = ca.check_cross_election_consistency(
        bu(el(6257, 301, 301, 0), el(6259, 300, 300, 0)))
    assert issue.codigo == "A01"


def test_votos_por_eleitor_senador():
    from dataurnas.analyzer.integrity import votos_por_eleitor

    assert votos_por_eleitor("Senador", "20261004T154409") == 2
    assert votos_por_eleitor("Senador", "02/10/2022 17:00:00") == 1
    assert votos_por_eleitor("Senador", "20181007T170000") == 2
    assert votos_por_eleitor("Governador", "20261004T154409") == 1
    assert votos_por_eleitor("Senador", None) == 1


def test_auditar_secao_com_analise(vsc_ac, bu_ac):
    r = I.auditar_secao(IDENT, [_conjunto(bu_ac, vsc_ac)], 0, None, analisar=True)
    s = r["secao_log"]
    assert s["secao_id"] == "1T/ac/01066/0004/0077"
    assert s["modelo_urna"] == "2022" and s["fuso_offset"] == -2
    assert s["tem_log"] is False and s["origem_bu"] == "bu"
    assert all(i[0] == s["secao_id"] for i in r["issues"])


# --- arquivo listado no aux.json e indisponível (HTTP 404) -----------------

NOME_RDV = "o03220ac0106600040077-rdv.dat"
NOME_IMGBU = "o03220ac0106600040077-imgbu.dat"


class _FetcherFalso:
    """HttpFetcher sem rede: aux.json fixo e corpos por nome (None = 404)."""

    def __init__(self, arquivos: list[tuple[str, str, bytes | None]]):
        self.arquivos = arquivos
        self.corpos = {nm: raw for _tp, nm, raw in arquivos}

    async def get_json(self, url: str):
        return {"st": "Recebida", "hashes": [{
            "hash": "4a6b70", "st": "Recebida", "dr": "06/10/2026", "hr": "10:00:00",
            "arq": [{"tp": tp, "nm": nm} for tp, nm, _ in self.arquivos]}]}

    async def get(self, url: str):
        return self.corpos[url.rsplit("/", 1)[-1]]


def _processar(mod, arquivos, caplog):
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    s = {**IDENT, "secao_principal": None}
    with ThreadPoolExecutor(1) as pool, \
            caplog.at_level(logging.WARNING, logger="fetch_integridade"):
        return asyncio.run(mod.processar_secao(_FetcherFalso(arquivos), pool, s, None, False))


def _gravar(mod, tmp_path, r) -> set[str]:
    import pyarrow.parquet as pq

    w = mod.Writer(tmp_path, 10)
    key = "ac/01066/0004/0077"
    w.add(key, r["secao"], r["linhas"], r.get("secao_log"), r.get("issues"))
    w.flush()
    [parte] = (tmp_path / "parts").glob("arquivos-*.parquet")
    assert {"disponivel", "http_status"} <= set(pq.read_schema(parte).names)
    return w.done_keys()


def test_imgbu_404_nao_derruba_a_secao(tmp_path, caplog, vsc_ac, bu_ac):
    mod = _carregar_script()
    r = _processar(mod, [("bu", NOME_BU, bu_ac), ("vota", NOME_VSC, vsc_ac),
                         ("imgbu", NOME_IMGBU, None)], caplog)
    por_nome = {x["nome"]: x for x in r["linhas"]}
    img = por_nome[NOME_IMGBU]
    assert img["disponivel"] is False and img["http_status"] == 404
    assert img["tamanho"] is None and img["sha512"] is None and img["hash_confere"] is None
    bu = por_nome[NOME_BU]
    assert bu["disponivel"] is True and bu["http_status"] == 200 and bu["hash_confere"] is True
    s = r["secao"]
    assert s["status_secao"] == "ok" and s["assinatura_valida"] is True
    assert s["n_indisponiveis"] == 1 and s["n_sem_hash"] == 1  # o .vsc
    assert not any(d["arquivo"] == NOME_IMGBU for d in r["divergencias"])
    assert any(m.startswith("PUBLICACAO ac/01066/0004/0077: HTTP 404") and NOME_IMGBU in m
               for m in caplog.messages)
    assert "ac/01066/0004/0077" in _gravar(mod, tmp_path, r)

    mod.consolidar(tmp_path, tmp_path / "auditoria")
    resumo = json.loads((tmp_path / "resumo.json").read_text(encoding="utf-8"))
    assert resumo["arquivos_indisponiveis"]["total"] == 1
    assert resumo["arquivos_indisponiveis"]["por_tipo"] == {"imgbu": 1}
    assert resumo["por_uf"]["ac"]["arquivos_indisponiveis"] == 1
    import duckdb

    disp = duckdb.sql(f"SELECT nome, disponivel, http_status FROM "
                      f"read_parquet('{tmp_path / 'arquivos_ac.parquet'}')").fetchall()
    assert (NOME_IMGBU, False, 404) in disp and (NOME_BU, True, 200) in disp
    [(n_ind,)] = duckdb.sql(f"SELECT n_indisponiveis FROM "
                            f"read_parquet('{tmp_path / 'secoes.parquet'}')").fetchall()
    assert n_ind == 1


def test_rdv_assinado_404_gera_divergencia_e_checkpoint(tmp_path, caplog, vsc_ac, bu_ac):
    mod = _carregar_script()
    r = _processar(mod, [("bu", NOME_BU, bu_ac), ("rdv", NOME_RDV, None),
                         ("vota", NOME_VSC, vsc_ac)], caplog)
    [d] = [d for d in r["divergencias"] if d["arquivo"] == NOME_RDV]
    assert d["categoria"] == "arquivo_ausente_tse" and "404" in d["motivo"]
    rdv = next(x for x in r["linhas"] if x["nome"] == NOME_RDV)
    assert rdv["disponivel"] is False and rdv["http_status"] == 404
    assert rdv["sha512_assinado"] == d["sha512_assinado"] and rdv["hash_confere"] is None
    s = r["secao"]
    assert s["assinatura_valida"] is True and s["n_hash_confere"] == 1
    assert s["n_indisponiveis"] == 1
    assert "ac/01066/0004/0077" in _gravar(mod, tmp_path, r)


def test_vsc_404_continua_derrubando_a_secao(caplog, bu_ac):
    mod = _carregar_script()
    with pytest.raises(RuntimeError, match="HTTP 404 em arquivo listado no aux.json"):
        _processar(mod, [("bu", NOME_BU, bu_ac), ("vota", NOME_VSC, None)], caplog)


def test_registrar_ocorrencias_formatos_antigo_e_novo():
    p = Path(__file__).resolve().parents[2] / "scripts" / "ele2026" / \
        "registrar_ocorrencias_publicacao.py"
    spec = importlib.util.spec_from_file_location("registrar_ocorrencias_publicacao", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    antigo = ("2026-10-08 10:00:00,123 WARNING erro em ba/38490/0016/0123: "
              "RuntimeError('HTTP 404 em arquivo listado no aux.json: "
              "o03220ba3849000160123-imgbu.dat')")
    novo = ("2026-10-14 11:00:00,456 WARNING PUBLICACAO ba/38490/0016/0123: HTTP 404 em "
            "arquivo listado no aux.json: o03220ba3849000160123-imgbu.dat")
    outro = ("2026-10-14 11:00:01,000 WARNING PUBLICACAO ma/07846/0074/0228: HTTP 404 em "
             "arquivo listado no aux.json: o03220ma0784600740228-rdv.dat")
    oc = mod.extrair([antigo, novo, novo, outro, "linha qualquer"])
    assert [(o["uf"], o["arquivo"], o["tipo"], o["http_status"]) for o in oc] == [
        ("ba", "o03220ba3849000160123-imgbu.dat", "imgbu", 404),
        ("ma", "o03220ma0784600740228-rdv.dat", "rdv", 404)]
    assert oc[0]["primeira_ocorrencia"] == "2026-10-08 10:00:00"
