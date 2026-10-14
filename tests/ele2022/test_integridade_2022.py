"""Auditoria de integridade de 2022 (sem rede).

Fixtures reais do 1º turno de 2022 (pacote de dados abertos do TSE, AC),
gravadas como {bu,vscmr}_1t_ac_m<mun>_z<zona>_s<secao>.bin:
  - o00406-0100700090001.{bu,vscmr}  UE2013, ECDSA P-521 (AC URNA); r e s das
    assinaturas vêm como INTEGER de 66 bytes, BER não mínimo
  - o00406-0139200010003.{bu,vscmr}  UE2020, Ed521 (AC UE2020)
"""

import asyncio
import hashlib
import importlib.util
import io
import json
import logging
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

pytest.importorskip("cryptography")

from dataurnas.analyzer import integrity as I  # noqa: E402
from dataurnas.downloader import zip_remoto as Z  # noqa: E402
from dataurnas.parsers.signature import (  # noqa: E402
    ecdsa_der_canonica,
    parse_vsc,
    verificar_vsc,
)

FIX = Path(__file__).parent / "fixtures"
ECDSA = "o00406-0100700090001"
ED521 = "o00406-0139200010003"
RAIZ = Path(__file__).resolve().parents[2]


# fixtures em .bin (o .gitignore exclui *.bu e *.vscmr de dados brutos)
ARQ_FIXTURE = {ECDSA: "1t_ac_m01007_z0009_s0001", ED521: "1t_ac_m01392_z0001_s0003"}


def _ler(base: str, ext: str) -> bytes:
    return (FIX / f"{ext}_{ARQ_FIXTURE[base]}.bin").read_bytes()


def _carregar_script():
    p = RAIZ / "scripts" / "ele2022" / "fetch_integridade.py"
    spec = importlib.util.spec_from_file_location("fetch_integridade_2022", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mod():
    return _carregar_script()


# --- ECDSA com INTEGER de largura fixa ---------------------------------------

def test_ecdsa_der_canonica_reescreve_inteiros_de_largura_fixa():
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.hazmat.primitives.asymmetric.utils import (
        decode_dss_signature,
        encode_dss_signature,
    )

    chave = ec.generate_private_key(ec.SECP521R1())
    msg = hashlib.sha512(b"arquivo").digest()
    for _ in range(20):
        der = chave.sign(msg, ec.ECDSA(hashes.SHA512()))
        r, s = decode_dss_signature(der)
        corpo = b"".join(b"\x02\x42" + v.to_bytes(66, "big") for v in (r, s))
        fixa = b"\x30\x81" + bytes([len(corpo)]) + corpo
        assert ecdsa_der_canonica(fixa) == encode_dss_signature(r, s)
        cru = r.to_bytes(66, "big") + s.to_bytes(66, "big")
        assert ecdsa_der_canonica(cru) == encode_dss_signature(r, s)
        chave.public_key().verify(ecdsa_der_canonica(fixa), msg, ec.ECDSA(hashes.SHA512()))
    assert ecdsa_der_canonica(b"lixo") is None
    assert ecdsa_der_canonica(b"\x30\x03\x02\x01\x00") is None


def test_vscmr_ecdsa_2022_valido_em_todos_os_arquivos():
    raw = _ler(ECDSA, "vscmr")
    v = parse_vsc(raw)
    assert v["modelo_cod"] == 13
    assert v["hw"]["algoritmo_assinatura"] == "ecdsa"
    # a fixture tem assinaturas com r ou s menores que 2^520 (zeros à esquerda)
    assert any(a["assinatura"][5] == 0 or a["assinatura"][73] == 0
               for a in v["hw"]["arquivos"])
    r = verificar_vsc(raw)
    assert r["assinatura_valida"] is True, r["falhas"]
    assert r["algoritmo"] == "ECDSA-secp521r1-SHA512"
    assert len(r["assinaturas_arquivos"]) == 11
    assert all(r["assinaturas_arquivos"].values())
    assert "CN=AC URNA" in r["cert_issuer"]


def test_vscmr_ed521_2022_valido():
    r = verificar_vsc(_ler(ED521, "vscmr"), {f"{ED521}.bu"})
    assert r["assinatura_valida"] is True, r["falhas"]
    assert r["algoritmo"] == "Ed521"
    assert r["modelo_cod"] == 20
    assert "CN=AC UE2020" in r["cert_issuer"]


def test_vscmr_com_assinatura_alterada_e_invalido():
    raw = bytearray(_ler(ECDSA, "vscmr"))
    v = parse_vsc(bytes(raw))
    alvo = v["hw"]["arquivos"][0]["assinatura"]
    i = bytes(raw).find(alvo)
    raw[i + 40] ^= 1
    r = verificar_vsc(bytes(raw))
    assert r["assinatura_valida"] is False
    assert any("assinatura" in f for f in r["falhas"])


# --- auditoria de uma seção --------------------------------------------------

def _arquivos(base: str, bu: bytes | None = None) -> list[tuple]:
    bu = _ler(base, "bu") if bu is None else bu
    return [(f"{base}.bu", bu, "0", "2022-10-02 17:00:00"),
            (f"{base}.vscmr", _ler(base, "vscmr"), "0", "2022-10-02 17:00:00")]


IDENT = {"uf": "ac", "cd_mun": "01007", "zona": "0009", "secao": "0001"}


def test_auditar_secao_2022_ok_e_ausentes(mod):
    r = mod.auditar_secao_2022(1, IDENT, _arquivos(ECDSA), None, True)
    s = r["secao"]
    assert s["secao_id"] == "1T/ac/01007/0009/0001"
    assert s["status_secao"] == "ok" and s["assinatura_valida"] is True
    assert (s["n_arquivos"], s["n_hash_confere"], s["n_hash_diverge"]) == (2, 1, 0)
    assert s["modelo_urna"] == "UE2013"
    assert s["n_assinaturas_arquivos_validas"] == 1
    bu = next(x for x in r["linhas"] if x["tipo"] == "bu")
    assert bu["hash_confere"] is True and bu["assinatura_arquivo_valida"] is True
    assert bu["sha512"] == hashlib.sha512(_ler(ECDSA, "bu")).hexdigest()
    # .rdv, .logjez e .imgbu são assinados e publicados, mas não vieram
    cats = sorted((d["arquivo"].rsplit(".", 1)[1], d["categoria"]) for d in r["divergencias"])
    assert cats == [("imgbu", "arquivo_ausente_tse"), ("logjez", "arquivo_ausente_tse"),
                    ("rdv", "arquivo_ausente_tse")]
    assert all("pacote de dados abertos" in d["motivo"] for d in r["divergencias"])
    assert all(d["turno"] == 1 and "token_tse" not in d for d in r["divergencias"])


def test_auditar_secao_2022_bu_adulterado(mod):
    bu = _ler(ECDSA, "bu")
    r = mod.auditar_secao_2022(1, IDENT, _arquivos(ECDSA, bu[:-1] + bytes([bu[-1] ^ 1])),
                               None, True)
    assert r["secao"]["n_hash_diverge"] == 1
    assert any(d["categoria"] == "hash_diverge" for d in r["divergencias"])


def test_auditar_secao_2022_votos(mod):
    votos = mod._votos_bu(_ler(ECDSA, "bu"), 544)
    assert votos and all(len(v) == 3 for v in votos)
    assert sum(v[2] for v in votos) > 0
    ok = mod.auditar_secao_2022(1, IDENT, _arquivos(ECDSA), votos, True)
    assert ok["secao"]["votos_conferem"] is True
    errado = tuple(sorted(votos[:-1] + ((votos[-1][0], votos[-1][1], votos[-1][2] + 1),)))
    r = mod.auditar_secao_2022(1, IDENT, _arquivos(ECDSA), errado, True)
    assert r["secao"]["votos_conferem"] is False
    assert "diferem do banco" in r["secao"]["motivo"]


def test_tipos_v1():
    assert I.tipo_arquivo(Z.TIPO_POR_EXTENSAO["logjez"], "x.logjez") == "log"
    assert I.tipo_arquivo(Z.TIPO_POR_EXTENSAO["vscmr"], "x.vscmr") == "vota"
    assert I.tipo_arquivo(Z.TIPO_POR_EXTENSAO["vscsa"], "x.vscsa") == "vota"
    assert I.eh_assinatura("", "x.vscmr")


# --- argumentos e registros na hora -----------------------------------------

def test_parse_args_limites(mod):
    a = mod.parse_args(["--turnos", "1", "--ufs", "AC,rr", "--taxa", "90", "--workers", "8"])
    assert a.turnos == [1] and a.ufs == ["ac", "rr"]
    assert a.taxa == 25.0 and a.workers == 3
    a = mod.parse_args([])
    assert a.turnos == [1, 2] and len(a.ufs) == 28 and a.ufs[-1] == "zz"
    assert a.saida.endswith("data/parquet/2022/integridade")
    assert a.log.endswith("data/ele2022_integridade.log")
    with pytest.raises(SystemExit):
        mod.parse_args(["--turnos", "3"])


def test_divergencia_gravada_na_hora(mod, tmp_path, caplog):
    reg = mod.Jsonl(tmp_path / "divergencias.jsonl", "DIVERGENCIA")
    with caplog.at_level(logging.WARNING, logger="fetch_integridade_2022"):
        reg.registrar({"categoria": "hash_diverge", "secao_id": "1T/ac/1/2/3"})
    (linha,) = (tmp_path / "divergencias.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(linha)["categoria"] == "hash_diverge"
    assert any(m.startswith("DIVERGENCIA ") for m in caplog.messages)


# --- ponta a ponta com um zip em memória ------------------------------------

class FakeFetcher:
    """Serve um zip em memória por faixas, como o CDN do TSE."""

    def __init__(self, dados: bytes):
        self.dados = dados
        self.pedidos = 0
        self.stats = {"bytes": 0}

    async def head(self, url):
        return {"tamanho": len(self.dados), "last_modified": "x", "etag": "y"}

    async def faixa(self, url, ini, fim):
        self.pedidos += 1
        self.stats["bytes"] += fim - ini
        return self.dados[ini:fim]

    async def close(self):
        pass


def _zip_secoes() -> bytes:
    bu = _ler(ECDSA, "bu")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("leiame.pdf", b"%PDF")
        z.writestr(f"{ECDSA}.bu", bu)
        z.writestr(f"{ECDSA}.vscmr", _ler(ECDSA, "vscmr"))
        # outra seção com o .vscmr da primeira: nenhum nome confere
        z.writestr("o00406-0100700090009.bu", bu)
        z.writestr("o00406-0100700090009.vscmr", _ler(ECDSA, "vscmr"))
        z.writestr("estranho.txt", b"?")
    return buf.getvalue()


def _base_2022(tmp_path: Path, mod) -> Path:
    import pyarrow as pa
    import pyarrow.parquet as pq

    base = tmp_path / "base"
    base.mkdir()
    ids = ["1T/ac/01007/0009/0001", "1T/ac/01007/0009/0009", "1T/ac/01007/0009/0777"]
    pq.write_table(pa.table({
        "id": ids, "municipio": ["01007"] * 3, "zona": ["0009"] * 3,
        "secao": ["0001", "0009", "0777"]}), base / "secoes.parquet")
    votos = mod._votos_bu(_ler(ECDSA, "bu"), 544)
    pq.write_table(pa.table({
        "secao_id": ["1T/ac/01007/0009/0001"] * len(votos),
        "codigo_cargo": [1] * len(votos),
        "tipo_voto": [v[0] for v in votos],
        "codigo_candidato": [v[1] or None for v in votos],
        "quantidade": [v[2] for v in votos]}), base / "votos_t1_b.parquet")
    return base


def test_ponta_a_ponta_offline(mod, tmp_path):
    out = tmp_path / "integridade"
    args = mod.parse_args(["--turnos", "1", "--ufs", "ac", "--saida", str(out),
                           "--base-2022", str(_base_2022(tmp_path, mod))])
    out.mkdir()
    f = FakeFetcher(_zip_secoes())
    w = mod.Writer(out, 1000)
    divs = mod.Jsonl(out / "divergencias.jsonl", "DIVERGENCIA")
    ocors = mod.Jsonl(out / "ocorrencias_publicacao.jsonl", "PUBLICACAO")
    erros: list[str] = []
    prog = {"n": 0, "t0": 0.0}
    with ThreadPoolExecutor(2) as pool:
        asyncio.run(mod.processar_pacote(args, f, pool, w, divs, ocors, set(), 1, "ac",
                                         erros, prog))
    assert erros == []
    assert prog["n"] == 2
    resumo = mod.consolidar(out, "v9.9.9")
    t = resumo["por_turno"]["1T"]["totais"]
    assert (t["secoes"], t["ok"], t["ausente_pacote"]) == (3, 2, 1)
    assert t["hash_diverge"] == 0 and t["assinatura_valida"] == 2
    assert t["votos_conferem"] == 1 and t["votos_nao_conferidos"] == 1
    cats = resumo["divergencias_por_categoria"]
    # seção 0009: BU com nome sem hash no .vscmr (de outra seção), e os 4
    # arquivos assinados desse .vscmr ausentes; seção 0001: rdv, logjez, imgbu
    assert cats == {"hash_diverge": 0, "assinatura_invalida": 0,
                    "hash_assinado_ausente": 1, "arquivo_ausente_tse": 7}
    oc = resumo["ocorrencias_por_categoria"]
    assert oc["secao_sem_arquivos_no_pacote"] == 1 and oc["entrada_fora_do_padrao"] == 1
    assert resumo["completo"] is False  # só 1 dos 56 pacotes
    man = json.loads((out / "catalogo_manifest.json").read_text(encoding="utf-8"))
    assert [a["arquivo"] for a in man["arquivos"]] == ["arquivos_t1_ac.parquet"]
    assert man["url_base"].endswith("/v9.9.9") and man["total_linhas"] == 4
    assert (out / "secoes.parquet").exists()
    # retomada: tudo no checkpoint, nada é baixado de novo além do diretório
    pedidos = f.pedidos
    w2 = mod.Writer(out, 1000)
    prog2 = {"n": 0, "t0": 0.0}
    with ThreadPoolExecutor(1) as pool:
        asyncio.run(mod.processar_pacote(args, f, pool, w2, divs, ocors, w2.done_keys(),
                                         1, "ac", erros, prog2))
    assert prog2["n"] == 0 and f.pedidos - pedidos <= 3


# --- metadados do banco de 2022 ----------------------------------------------

def _carregar_meta():
    p = RAIZ / "scripts" / "ele2022" / "registrar_metadados_integridade.py"
    spec = importlib.util.spec_from_file_location("registrar_metadados_2022", p)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_metadados_so_marca_auditoria_completa(tmp_path):
    import pyarrow.parquet as pq

    m = _carregar_meta()
    resumo = {"completo": False, "pacotes_processados": 2, "pacotes_esperados": 56,
              "erros_pendentes": 0, "totais": {"secoes": 10, "fora_do_banco": 0},
              "divergencias_por_categoria": {}, "n_divergencias": 0}
    rp = tmp_path / "resumo.json"
    rp.write_text(json.dumps(resumo), encoding="utf-8")
    assert m.main(["--resumo", str(rp), "--base", str(tmp_path), "--gravar"]) == 1
    assert not (tmp_path / "metadados.parquet").exists()
    resumo["completo"] = True
    rp.write_text(json.dumps(resumo), encoding="utf-8")
    assert m.main(["--resumo", str(rp), "--base", str(tmp_path)]) == 0  # simulação
    assert not (tmp_path / "metadados.parquet").exists()
    assert m.main(["--resumo", str(rp), "--base", str(tmp_path), "--gravar"]) == 0
    t = pq.read_table(tmp_path / "metadados.parquet").to_pylist()
    kv = {r["chave"]: r["valor"] for r in t}
    assert kv["verify_hashes"] == "true" and kv["origem"] == m.ORIGEM
    ok, pend = m.avaliar({**resumo, "erros_pendentes": 3}, None)
    assert not ok and "erro pendente" in pend[0]
    ok, pend = m.avaliar(resumo, 11)
    assert not ok and "10 de 11" in pend[0]
