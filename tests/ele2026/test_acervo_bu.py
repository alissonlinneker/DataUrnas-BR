"""Archive of signed 2026 BUs: manifest rows and verification (no network).

Uses the real AC 01066/0004/0077 1st round BU and its -vota.vsc fixtures.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

import pytest

pytest.importorskip("cryptography")

RAIZ = Path(__file__).resolve().parents[2]
FIX = Path(__file__).parent / "fixtures"
BU = (FIX / "bu_ac_m01066_z0004_s0077.bin").read_bytes()
VSC = (FIX / "vsc_ac_m01066_z0004_s0077.bin").read_bytes()
NOME_BU = "o03220ac0106600040077-bu.dat"
NOME_VSC = "o03220ac0106600040077-vota.vsc"


def _carregar():
    p = RAIZ / "scripts" / "ele2026" / "conferir_acervo_bu.py"
    spec = importlib.util.spec_from_file_location("conferir_acervo_bu", p)
    mod = importlib.util.module_from_spec(spec)
    # registered so the process pool of cmd_conferir can pickle its functions
    sys.modules["conferir_acervo_bu"] = mod
    spec.loader.exec_module(mod)
    return mod


C = _carregar()


def _manifesto(asset: str = "acervo_bu_2026_1t_AC.tar") -> dict[str, dict]:
    """Manifest rows as read back from disk (text values)."""
    linhas = C.linhas_secao({NOME_BU: BU, NOME_VSC: VSC})
    for r in linhas:
        r["data_zip"] = "2026-10-04 17:30:00"
        r["asset"] = asset if r["tipo"] == "bu" else None
    return {r["arquivo"]: {k: C._txt(r.get(k)) for k in C.CAMPOS} for r in linhas}


def test_linhas_secao_confere_assinatura():
    bu, vsc = C.linhas_secao({NOME_VSC: VSC, NOME_BU: BU})
    assert (bu["arquivo"], vsc["arquivo"]) == (NOME_BU, NOME_VSC)
    assert (bu["turno"], bu["uf"], bu["cd_mun"], bu["zona"], bu["secao"]) == \
        (1, "AC", "01066", "0004", "0077")
    assert bu["sha512"] == hashlib.sha512(BU).hexdigest()
    assert bu["sha512_assinado"] == bu["sha512"]
    assert bu["hash_confere"] is True and bu["assinatura_arquivo"] is True
    assert bu["par"] == NOME_VSC and vsc["par"] == NOME_BU
    assert vsc["vsc_valida"] is True and vsc["vsc_falhas"] is None
    assert C.secao_ok([bu, vsc])


def test_bu_alterado_nao_confere():
    alterado = BU[:-1] + bytes([BU[-1] ^ 1])
    bu, vsc = C.linhas_secao({NOME_BU: alterado, NOME_VSC: VSC})
    assert bu["hash_confere"] is False
    assert vsc["vsc_valida"] is True    # the signature file itself is intact
    assert not C.secao_ok([bu, vsc])


def test_manifesto_ida_e_volta(tmp_path):
    linhas = list(_manifesto().values())
    p = tmp_path / "m.csv.gz"
    C.escrever_manifesto(p, linhas)
    lido = C.ler_manifesto(p)
    assert lido[NOME_BU]["hash_confere"] == "true"
    assert lido[NOME_VSC]["asset"] == ""
    assert list(lido[NOME_BU]) == C.CAMPOS
    # deterministic output: same rows, same bytes
    p2 = tmp_path / "m2.csv.gz"
    C.escrever_manifesto(p2, list(reversed(linhas)))
    assert p.read_bytes() == p2.read_bytes()


def test_conferir_secao_com_e_sem_assinatura():
    m = _manifesto()
    probs, modo, ok = C.conferir_secao({NOME_BU: BU, NOME_VSC: VSC}, m, None)
    assert (probs, modo, ok) == ([], "assinatura", True)
    probs, modo, ok = C.conferir_secao({NOME_BU: BU}, m, "acervo_bu_2026_1t_AC.tar")
    assert (probs, modo, ok) == ([], "hash", True)
    alterado = BU[:-1] + bytes([BU[-1] ^ 1])
    probs, modo, ok = C.conferir_secao({NOME_BU: alterado}, m, "acervo_bu_2026_1t_AC.tar")
    assert modo == "hash" and not ok
    textos = " ".join(p["problema"] for p in probs)
    assert "sha512" in textos and "signed SHA-512" in textos
    probs, _, _ = C.conferir_secao({NOME_BU: BU}, m, "outro.tar")
    assert probs and "manifest lists it" in probs[0]["problema"]


def _tar(path: Path, arquivos: dict[str, bytes]) -> None:
    with tarfile.open(path, "w", format=tarfile.USTAR_FORMAT) as tf:
        for nome in sorted(arquivos):
            ti = tarfile.TarInfo(nome)
            ti.size = len(arquivos[nome])
            tf.addfile(ti, io.BytesIO(arquivos[nome]))


def test_agrupar_secoes_do_tar(tmp_path):
    outro = "o03220ac0106600040078-bu.dat"
    p = tmp_path / "a.tar"
    _tar(p, {NOME_BU: BU, NOME_VSC: VSC, outro: b"x"})
    secoes = list(C.agrupar_secoes(C.ler_tar(p)))
    assert [sorted(s) for s in secoes] == [[NOME_BU, NOME_VSC], [outro]]


@pytest.mark.skipif(shutil.which("zstd") is None, reason="zstd command line tool not found")
def test_ler_tar_zst(tmp_path):
    # tarfile leaves the record padding unread; ler_tar must still end cleanly
    p = tmp_path / "a.tar"
    _tar(p, {NOME_BU: BU, NOME_VSC: VSC})
    subprocess.run(["zstd", "-q", "--rm", str(p)], check=True)
    itens = dict(C.ler_tar(tmp_path / "a.tar.zst"))
    assert itens == {NOME_BU: BU, NOME_VSC: VSC}


def test_cmd_conferir_acervo(tmp_path):
    asset = "acervo_bu_2026_1t_AC.tar"
    _tar(tmp_path / asset, {NOME_BU: BU})
    C.escrever_manifesto(tmp_path / "manifesto_bu_2026_1t.csv.gz", list(_manifesto().values()))
    (tmp_path / "SHA512SUMS").write_text(
        f"{C.sha512_arquivo(tmp_path / asset)}  {asset}\n")
    a = argparse.Namespace(acervo=str(tmp_path), tse=False, ufs="", turnos="1,2", workers=1,
                           saida=str(tmp_path / "prob.csv"))
    assert C.cmd_conferir(a) == 0
    alterado = BU[:-1] + bytes([BU[-1] ^ 1])
    _tar(tmp_path / asset, {NOME_BU: alterado})
    assert C.cmd_conferir(a) == 1
    texto = (tmp_path / "prob.csv").read_text()
    assert "differs from SHA512SUMS" in texto and NOME_BU in texto


def _info(nome: str, crc: int, tamanho: int, offset: int = 0) -> zipfile.ZipInfo:
    i = zipfile.ZipInfo(nome, date_time=(2026, 10, 4, 17, 30, 0))
    i.CRC, i.file_size, i.compress_size, i.header_offset = crc, tamanho, tamanho, offset
    return i


def test_confrontar_membros_classes():
    m = _manifesto()
    crc_bu = int(m[NOME_BU]["crc32"], 16)
    infos = [_info(NOME_BU, crc_bu, len(BU)),
             _info(NOME_VSC, 0, len(VSC)),
             _info("o03220ac0106600040078-bu.dat", 1, 10)]
    classes = {r["arquivo"]: r["classe"] for r in C.confrontar_membros(infos[:2] + infos[2:], m)}
    assert classes == {NOME_BU: "igual", NOME_VSC: "diferente",
                       "o03220ac0106600040078-bu.dat": "novo"}
    classes = {r["arquivo"]: r["classe"] for r in C.confrontar_membros(infos[:1], m)}
    assert classes[NOME_VSC] == "ausente"


def test_planejar_junta_vizinhos():
    infos = [_info("a", 0, 100, 0), _info("b", 0, 100, 2000), _info("c", 0, 100, 10 << 20)]
    plano = C.planejar(infos, chunk=8 << 20, gap=256 << 10)
    assert [[i.filename for i in ms] for _, _, ms in plano] == [["a", "b"], ["c"]]
