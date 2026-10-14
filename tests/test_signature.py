import hashlib

import pytest

from dataurnas.analyzer.batch import BatchAnalyzer
from dataurnas.analyzer.integrity import IntegrityAnalyzer
from dataurnas.models import SpecVersion
from dataurnas.parsers.asn1_helper import get_compiler
from dataurnas.parsers.signature import SignatureParser, modelo_codigo_from_bytes


def _entidade_assinatura(compiler, arquivos: dict[str, bytes]) -> dict:
    conteudo = compiler.encode("Assinatura", {
        "arquivosAssinados": [
            {"nomeArquivo": nome,
             "assinatura": {"tamanho": 64, "hash": h, "assinatura": b"\x00"}}
            for nome, h in arquivos.items()
        ],
    })
    return {
        "dataHoraCriacao": "20221002T170500",
        "versao": 2,
        "autoAssinado": {
            "usuario": {"nomeUsuario": "secao", "serial": 1},
            "algoritmoHash": {"algoritmo": "sha512"},
            "algoritmoAssinatura": {"algoritmo": "ecdsa", "bits": 256},
            "assinatura": {"tamanho": 64, "hash": b"\x01", "assinatura": b"\x02"},
        },
        "conteudoAutoAssinado": bytes(conteudo),
    }


def make_vscmr_2022(arquivos: dict[str, bytes], modelo: str = "ue2020") -> bytes:
    c = get_compiler(SpecVersion.V1, "assinatura")
    ent = _entidade_assinatura(c, arquivos)
    return bytes(c.encode("EntidadeAssinaturaResultado", {
        "modeloUrna": modelo, "assinaturaSW": ent, "assinaturaHW": ent,
    }))


def _tlv(tag: int, content: bytes) -> bytes:
    n = len(content)
    if n < 0x80:
        return bytes([tag, n]) + content
    ln = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return bytes([tag, 0x80 | len(ln)]) + ln + content


def make_vsc_2026(modelo: int = 22) -> bytes:
    """Formato observado em 2026: o modelo vem num SEQUENCE ao final."""
    c = get_compiler(SpecVersion.V1, "assinatura")
    ent = bytes(c.encode("EntidadeAssinatura", _entidade_assinatura(c, {"a-bu.dat": b"\x00"})))
    bloco = _tlv(0x30, _tlv(0x0A, bytes([modelo])) + _tlv(0x0A, b"\x02"))
    return _tlv(0x30, ent + ent + bloco)


def test_modelo_2022(tmp_path):
    path = tmp_path / "o00406-1.vscmr"
    path.write_bytes(make_vscmr_2022({}, modelo="ue2015"))
    assert SignatureParser().get_model(path) == "UE2015"
    assert modelo_codigo_from_bytes(path.read_bytes()) == 15


def test_modelo_2026_no_bloco_final(tmp_path):
    path = tmp_path / "o00001-x-vota.vsc"
    path.write_bytes(make_vsc_2026(22))
    assert SignatureParser().get_model(path) == "UE2022"


@pytest.mark.parametrize("raw", [b"", b"\x04\x00", b"\x30\x05\x0a"])
def test_modelo_bytes_invalidos(raw):
    assert modelo_codigo_from_bytes(raw) is None


def test_extract_file_hashes_le_arquivos_assinados(tmp_path):
    h = hashlib.sha512(b"bu").digest()
    path = tmp_path / "o00406-1.vscmr"
    path.write_bytes(make_vscmr_2022({"o00406-1.bu": h}))
    assert SignatureParser().extract_file_hashes(path) == {"o00406-1.bu": h}


def test_verificacao_ponta_a_ponta(tmp_path):
    (tmp_path / "o00406-1.bu").write_bytes(b"bu")
    (tmp_path / "o00406-1.rdv").write_bytes(b"rdv adulterado")
    (tmp_path / "o00406-1.vscmr").write_bytes(make_vscmr_2022({
        "o00406-1.bu": hashlib.sha512(b"bu").digest(),
        "o00406-1.rdv": hashlib.sha512(b"rdv").digest(),
        "o00406-1.imgbu": hashlib.sha512(b"img").digest(),
    }))
    issues = IntegrityAnalyzer().verify_section_hashes(tmp_path)
    por_arquivo = {i.detalhes["arquivo"]: i.codigo for i in issues}
    assert por_arquivo == {"o00406-1.rdv": "C01", "o00406-1.imgbu": "E01"}


def test_batch_usa_modelo_da_assinatura(raw_tree):
    sec = raw_tree / "sp" / "71072" / "0001" / "0001"
    (sec / "o00406-7107200010001.vscmr").write_bytes(make_vscmr_2022({}, modelo="ue2013"))
    res = BatchAnalyzer(raw_dir=raw_tree).analyze_section(
        sec, bu_file=sec / "o00406-7107200010001.bu")
    assert res["modelo"] == "2013"
