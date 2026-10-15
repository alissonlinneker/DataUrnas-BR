"""Testes da cadeia de certificados de 2022 (scripts/ele2022/analisar_certificados.py).

Sem rede: os .vscmr reais de tests/ele2022/fixtures, certificados sintéticos e
um zip montado em memória servido por um leitor de faixas falso.
"""

import asyncio
import datetime as dt
import importlib.util
import io
import json
import zipfile
from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("cryptography")

ROOT = Path(__file__).resolve().parents[2]
FIX = Path(__file__).parent / "fixtures"
VSCMR_URNA = FIX / "vscmr_1t_ac_m01007_z0009_s0001.bin"  # UE2013, ECDSA P-521, AC URNA
VSCMR_2020 = FIX / "vscmr_1t_ac_m01392_z0001_s0003.bin"  # UE2020, Ed521, AC UE2020
AC_REPO = ROOT / "data" / "certificados" / "ac"


@pytest.fixture(scope="module")
def C():
    p = ROOT / "scripts" / "ele2022" / "analisar_certificados.py"
    spec = importlib.util.spec_from_file_location("analisar_certificados_2022", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def acs(C):
    return C.A26.carregar_acs(AC_REPO)


def _secoes(n_por_estrato=40):
    rows = []
    for turno in (1, 2):
        for uf, n in (("ac", n_por_estrato), ("rr", 7)):
            for i in range(n):
                rows.append({"turno": turno, "uf": uf, "cd_mun": "01007", "zona": "0009",
                             "secao": f"{i + 1:04d}", "cert_sha256": None})
    return pd.DataFrame(rows)


# --- amostra -----------------------------------------------------------------

def test_sortear_amostra_estratificada_e_reproduzivel(C):
    df = _secoes()
    am, est = C.sortear_amostra(df, 0.05, 20221002)
    assert est == {"1T/ac": (40, 2), "1T/rr": (7, 1), "2T/ac": (40, 2), "2T/rr": (7, 1)}
    assert len(am) == 6
    assert am.groupby(["turno", "uf"]).size().to_dict() == {
        (1, "ac"): 2, (1, "rr"): 1, (2, "ac"): 2, (2, "rr"): 1}
    # mesma semente, mesma amostra, em qualquer ordem de entrada
    am2, _ = C.sortear_amostra(df.sample(frac=1, random_state=1), 0.05, 20221002)
    pd.testing.assert_frame_equal(am, am2)
    # o critério é o SHA-256 documentado
    g = df[(df["turno"] == 1) & (df["uf"] == "ac")]
    ranks = sorted((C._rank(20221002, *t), t[4]) for t in g[C.CHAVE].itertuples(index=False, name=None))
    esperado = sorted(s for _r, s in ranks[:2])
    assert sorted(am[(am["turno"] == 1) & (am["uf"] == "ac")]["secao"]) == esperado
    outra, _ = C.sortear_amostra(df, 0.05, 1)
    assert not outra[C.CHAVE].equals(am[C.CHAVE])


# --- avaliação de um .vscmr ---------------------------------------------------

def test_avaliar_vscmr_fixtures(C, acs):
    urna = C.avaliar_vscmr(VSCMR_URNA.read_bytes(), 1, acs)
    assert urna["critica"] is False and urna["motivo"] is None
    assert urna["cadeia_ok"] is True and urna["assinatura_confere"] is True
    assert urna["emissor"] == "AC URNA" and urna["ac_emissor"] == "AC RAIZ UE"
    assert urna["algoritmo_chave"] == "ECDSA" and urna["modelo"] == "UE2013"
    assert urna["valido_na_eleicao"] and urna["uso_chave_ok"] and urna["ac_autoridade_ok"]
    assert urna["ac_valida_na_eleicao"] and urna["emitido_na_validade_da_ac"]
    assert urna["nivel_cadeia"] == "intermediaria"
    assert urna["cadeia_caminho"] == "ueao01663883 > AC URNA"

    e = C.avaliar_vscmr(VSCMR_2020.read_bytes(), 2, acs, cert_catalogo="0" * 64)
    assert e["cadeia_ok"] is True and e["assinatura_confere"] is True
    assert e["emissor"] == "AC UE2020" and e["ac_emissor"] == "AC URNA v2"
    assert e["algoritmo_chave"] == "Ed521" and e["modelo"] == "UE2020"
    assert e["confere_catalogo"] is False and "difere do registrado" in e["motivo"]
    assert e["critica"] is False


def test_sem_ac_fica_indeterminado(C):
    r = C.avaliar_vscmr(VSCMR_2020.read_bytes(), 1, [])
    assert r["cadeia_ok"] is None and r["critica"] is False
    assert "AC emissora ausente" in r["motivo"]


def test_ac_forjada_com_mesmo_nome_e_falha_critica(C, acs):
    from cryptography.hazmat.primitives.asymmetric import ec

    real = next(a for a in acs if C.A26._cn_cert(a) == "AC URNA")
    k = ec.generate_private_key(ec.SECP521R1())
    falsa = _cert(real.subject, real.subject, k.public_key(), k, True)
    r = C.avaliar_vscmr(VSCMR_URNA.read_bytes(), 1, [falsa])
    assert r["cadeia_ok"] is False and r["critica"] is True
    assert "não confere com a AC" in r["motivo"]


def _adulterar_assinatura_hw(raw: bytes) -> bytes:
    from dataurnas.parsers import signature as S

    sig = S.parse_vsc(raw)["hw"]["assinatura"]
    i = raw.index(sig) + len(sig) // 2
    return raw[:i] + bytes([raw[i] ^ 0x01]) + raw[i + 1:]


@pytest.mark.parametrize("fix", [VSCMR_URNA, VSCMR_2020])
def test_assinatura_que_nao_fecha_e_falha_critica(C, acs, fix):
    r = C.avaliar_vscmr(_adulterar_assinatura_hw(fix.read_bytes()), 1, acs)
    assert r["assinatura_confere"] is False and r["critica"] is True
    assert r["cadeia_ok"] is True  # o certificado continua emitido pela AC
    assert "assinatura:" in r["motivo"]


def test_vscmr_ilegivel(C, acs):
    r = C.avaliar_vscmr(b"\x30\x00", 1, acs)
    assert r["critica"] is True and r["motivo"]


# --- uso de chave --------------------------------------------------------------

def _nome(cn):
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])


def _cert(sujeito, emissor, chave_pub, chave_ass, ca, ku=None):
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes

    if isinstance(sujeito, str):
        sujeito = _nome(sujeito)
    if isinstance(emissor, str):
        emissor = _nome(emissor)
    agora = dt.datetime(2020, 1, 1, tzinfo=dt.timezone.utc)
    b = (x509.CertificateBuilder().subject_name(sujeito).issuer_name(emissor)
         .public_key(chave_pub).serial_number(x509.random_serial_number())
         .not_valid_before(agora).not_valid_after(agora + dt.timedelta(days=6000))
         .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True))
    if ku is not None:
        b = b.add_extension(ku, critical=False)
    return b.sign(chave_ass, hashes.SHA512())


def _ku(assina, ac):
    from cryptography import x509
    return x509.KeyUsage(digital_signature=assina, content_commitment=False,
                         key_encipherment=False, data_encipherment=False, key_agreement=False,
                         key_cert_sign=ac, crl_sign=ac, encipher_only=False, decipher_only=False)


def test_uso_chave_e_autoridade(C):
    from cryptography.hazmat.primitives.asymmetric import ec

    k = ec.generate_private_key(ec.SECP521R1())
    boa = _cert("UEAO00000001", "AC", k.public_key(), k, False, _ku(True, False))
    assert C.uso_chave_urna(boa) == (True, [])
    sem_ku = _cert("UEAO00000001", "AC", k.public_key(), k, False)
    assert C.uso_chave_urna(sem_ku) == (False, ["sem keyUsage"])
    ca = _cert("UEAO00000001", "AC", k.public_key(), k, True, _ku(False, True))
    ok, prob = C.uso_chave_urna(ca)
    assert not ok and len(prob) == 3
    ac = _cert("AC", "RAIZ", k.public_key(), k, True, _ku(False, True))
    assert C.autoridade_ok(ac) == (True, [])
    nao_ac = _cert("AC", "RAIZ", k.public_key(), k, False, _ku(True, False))
    assert C.autoridade_ok(nao_ac)[0] is False


# --- coleta sem rede -----------------------------------------------------------

class FetcherFalso:
    def __init__(self, pacotes: dict[str, bytes]):
        self.pacotes = pacotes
        self.stats = {"ok": 0}

    async def head(self, url):
        b = self.pacotes.get(url)
        return None if b is None else {"tamanho": len(b)}

    async def faixa(self, url, ini, fim):
        self.stats["ok"] += 1
        return self.pacotes[url][ini:fim]


def _zip(entradas: dict[str, bytes]) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for nome, raw in entradas.items():
            z.writestr(nome, raw)
    return buf.getvalue()


def _amostra(*secoes):
    return pd.DataFrame([{"turno": 1, "uf": "ac", "cd_mun": m, "zona": z, "secao": s,
                          "cert_sha256": None} for m, z, s in secoes])


def test_coleta_consolida_e_resume_sem_rede(C, acs, tmp_path):
    from dataurnas.downloader import zip_remoto as Z

    pacote = _zip({"o00406-0100700090001.bu": b"x" * 50,
                   "o00406-0100700090001.vscmr": VSCMR_URNA.read_bytes(),
                   "o00406-0139200010003.vscsa": VSCMR_2020.read_bytes(),
                   "leiame.pdf": b"pdf"})
    f = FetcherFalso({Z.url_pacote_2022(1, "ac"): pacote})
    am = _amostra(("01007", "0009", "0001"), ("01392", "0001", "0003"), ("01392", "0001", "0099"))
    st = asyncio.run(C.coletar(am, f, acs, tmp_path))
    assert st["estratos"] == 1 and st["secoes"] == 3
    assert (tmp_path / "certificados_amostra_partes" / "t1_ac.parquet").exists()
    # retomada: estrato pronto é pulado
    assert asyncio.run(C.coletar(am, f, acs, tmp_path))["ja_feitos"] == 1
    df = C.consolidar(tmp_path)
    assert len(df) == 3 and (tmp_path / "certificados_amostra.parquet").exists()
    assert df["cadeia_ok"].tolist()[:2] == [True, True]
    assert df.iloc[2]["motivo"] == "arquivo de assinatura ausente no pacote"
    assert df["arquivo_assinatura"].tolist()[:2] == ["vscmr", "vscsa"]
    res = C.resumir(df, {"1T/ac": (60, 3)}, 20221002, 0.05, AC_REPO)
    assert res["situacao"] == "concluído" and res["falhas_criticas"] == 0
    assert res["cadeia_ok"] == {"True": 2} and res["assinatura_confere"] == {"True": 2}
    assert res["sem_certificado_por_motivo"] == {"arquivo de assinatura ausente no pacote": 1}
    assert res["arquivo_assinatura"] == {"vscmr": 1, "vscsa": 1, "indeterminado": 1}
    assert set(res["por_emissor"]) == {"AC URNA", "AC UE2020"}
    assert res["certificados_repetidos"]["certificados"] == 0
    dup = pd.concat([df.iloc[:1], df.iloc[:1].assign(turno=2), df.iloc[:1].assign(secao="0002")])
    rep = C._repetidos(dup)
    assert rep == {"certificados": 1, "so_entre_turnos": 0, "no_mesmo_turno": 1,
                   "no_mesmo_turno_por_arquivo": {"vscmr": 1}, "com_mais_de_um_cn": 0}
    assert res["raiz"]["disponivel"] is False and res["raiz"]["tentativas"]
    acurna = next(a for a in res["acs"] if a["cn"] == "AC URNA")
    assert acurna["valida_no_dia_da_eleicao"] == {"1T": True, "2T": True}
    json.dumps(res, default=str)


def test_coleta_para_na_falha_critica(C, acs, tmp_path):
    from dataurnas.downloader import zip_remoto as Z

    pacote = _zip({"o00406-0100700090001.vscmr":
                   _adulterar_assinatura_hw(VSCMR_URNA.read_bytes())})
    f = FetcherFalso({Z.url_pacote_2022(1, "ac"): pacote})
    am = _amostra(("01007", "0009", "0001"))
    with pytest.raises(C.FalhaCritica):
        asyncio.run(C.coletar(am, f, acs, tmp_path))
    falhas = (tmp_path / "certificados_amostra_falhas.jsonl").read_text().splitlines()
    assert len(falhas) == 1 and json.loads(falhas[0])["secao_id"] == "1T/ac/01007/0009/0001"
    assert not (tmp_path / "certificados_amostra_partes" / "t1_ac.parquet").exists()
    # com parar=False, registra e segue
    asyncio.run(C.coletar(am, f, acs, tmp_path, parar=False))
    assert C.consolidar(tmp_path)["critica"].tolist() == [True]


def test_pacote_indisponivel(C, acs, tmp_path):
    am = _amostra(("01007", "0009", "0001"))
    asyncio.run(C.coletar(am, FetcherFalso({}), acs, tmp_path))
    assert C.consolidar(tmp_path)["motivo"].tolist() == ["pacote indisponível"]


# --- relatório -------------------------------------------------------------------

def test_relatorio_secao_certificados(C, acs, tmp_path):
    p = ROOT / "scripts" / "docs" / "gerar_relatorio_integridade_2022.py"
    spec = importlib.util.spec_from_file_location("rel2022", p)
    R = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(R)
    assert R.secao_certificados(tmp_path) == []
    df = pd.DataFrame([{**{"turno": 1, "uf": "ac", "cd_mun": "01007", "zona": "0009",
                           "secao": "0001"}, **C.avaliar_vscmr(VSCMR_URNA.read_bytes(), 1, acs)}])
    df = df.reindex(columns=C.COLS)
    res = C.resumir(df, {"1T/ac": (20, 1)}, 20221002, 0.05, AC_REPO)
    (tmp_path / "certificados_amostra.json").write_text(json.dumps(res, default=str))
    txt = "\n".join(R.secao_certificados(tmp_path))
    assert "## Cadeia de certificados (amostra de 5%)" in txt
    assert "20221002" in txt and "AC RAIZ UE" in txt and "AC URNA" in txt
    assert "Nenhuma falha" in txt
