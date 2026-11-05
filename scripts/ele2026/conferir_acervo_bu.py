#!/usr/bin/env python3
"""Verify the archive of signed 2026 BUs (release "acervo-bu-2026").

The archive is a second, dated copy of the binary BU of every section of both
2026 rounds (-bu.dat, or -busa.dat for sections counted by the Sistema de
Apuração), read by acervo_bu.py from the official national package zips of the
TSE (bu_imgbu_logjez_rdv_vscmr_2026_<1t|2t>_<UF>.zip) and packed as one
tar.zst per round and UF (large UFs split in parts). The signature files
(-vota.vsc signs -bu.dat, -sa.vsc signs -busa.dat) are read and verified
during the build and recorded in the manifest; whether they are also inside
the tar.zst depends on the build (by default acervo_bu.py keeps only the BUs,
--com-vsc packs the signature files too; see docs/acervo-bu-2026.md).

Each round has a manifest (manifesto_bu_2026_<1t|2t>.csv.gz) with one row per
file read: size, CRC-32 and date of the zip member, SHA-512, the asset that
holds it (empty if not archived) and, for BU rows, the SHA-512 that the
signature file signs for that BU (sha512_assinado), whether it matches
(hash_confere) and the per-file signature check; signature rows carry the
overall result of dataurnas.parsers.signature.verificar_vsc.

Subcommands:
  conferir    check every file against the manifest. Source: the downloaded
              release assets (--acervo DIR; SHA512SUMS is checked first) or a
              fresh read of the TSE zips (--tse). For each section, when the
              signature file is at hand (always with --tse) the signature is
              verified again and the signed SHA-512 of the BU recomputed;
              when only the BU is at hand, its SHA-512 must equal the signed
              SHA-512 recorded in the manifest. Missing, extra and changed
              files are listed.
  confrontar  cheap comparison with the zips the TSE serves today: ETag,
              Last-Modified and size of each zip, then CRC-32 and size of every
              bu/busa/vota/sa member against the manifest (central directory
              only, a few HTTP Range requests per zip). With --baixar the
              members that changed are downloaded and their SHA-512 recorded.
              This detects a later silent republication.

Usage:
  python scripts/ele2026/conferir_acervo_bu.py conferir --acervo DIR
  python scripts/ele2026/conferir_acervo_bu.py conferir --acervo DIR --tse [--ufs AC,RR]
  python scripts/ele2026/conferir_acervo_bu.py confrontar --acervo DIR [--saida diff.csv]

DIR holds the release assets (tar.zst files, the two manifests, the two
resumo_bu_2026_*.json and SHA512SUMS); with --tse or confrontar only the
manifests and summaries are needed. Reading tar.zst needs the zstd command
line tool. Requests to the TSE never exceed 4 at a time.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import io
import json
import re
import shutil
import struct
import subprocess
import sys
import tarfile
import threading
import time
import urllib.error
import urllib.request
import zipfile
import zlib
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path
from typing import Iterator, Optional

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

URL = ("https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2026/arqurnatot/"
       "bu_imgbu_logjez_rdv_vscmr_2026_{t}t_{uf}.zip")
UFS = ("AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO ZZ"
       .split())

# Member kinds read. Each data file is signed by the signature file of the
# same section named in ASSINA (the Sistema de Apuração uses -sa.vsc).
ASSINA = {"bu.dat": "vota.vsc", "busa.dat": "sa.vsc"}
TIPOS = {"bu.dat": "bu", "busa.dat": "busa", "vota.vsc": "vota", "sa.vsc": "sa"}
DADOS = ("bu", "busa")
NOME_RE = re.compile(r"^o0322([01])([a-z]{2})(\d{5})(\d{4})(\d{4})-"
                     r"(bu\.dat|busa\.dat|vota\.vsc|sa\.vsc)$")

# Manifest columns, in order.
CAMPOS = ["turno", "uf", "cd_mun", "zona", "secao", "arquivo", "tipo", "tamanho", "crc32",
          "data_zip", "sha512", "par", "sha512_assinado", "hash_confere",
          "assinatura_arquivo", "vsc_valida", "vsc_falhas", "vsc_motivos", "asset"]
# Columns recomputed from the bytes of a file alone.
DO_ARQUIVO = ["tamanho", "crc32", "sha512"]
# Columns recomputed when the signature file of the section is at hand.
DA_ASSINATURA = {"dados": ["par", "sha512_assinado", "hash_confere", "assinatura_arquivo"],
                 "vsc": ["vsc_valida", "vsc_falhas", "vsc_motivos"]}

LOCAL_HEADER = struct.Struct("<4s2B4HL2L2H")   # zipfile.structFileHeader


def _log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def _txt(v) -> str:
    """Manifest cell text: '' for None, lowercase for booleans."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "true" if v else "false"
    return str(v)


# ---------------------------------------------------------------------------
# Manifest rows
# ---------------------------------------------------------------------------

def secao_de(nome: str) -> str:
    """Section prefix of a member name (everything before the first '-')."""
    return nome.split("-", 1)[0]


def linhas_secao(arquivos: dict[str, bytes]) -> list[dict]:
    """Manifest rows (identity and recomputed columns) for one section's files.

    arquivos maps member name to bytes; every name must match NOME_RE and
    belong to the same section. Each data file (-bu.dat, -busa.dat) is checked
    against its signature file when present: the SHA-512 the .vsc signs for
    that file name (sha512_assinado), whether it equals the file's SHA-512
    (hash_confere) and the per-file hardware signature (assinatura_arquivo).
    Each signature row carries the overall result of verificar_vsc
    (vsc_valida, vsc_falhas, vsc_motivos) and, in par, the data files of the
    section it signs. Without its counterpart those columns stay empty.
    """
    from dataurnas.parsers.signature import verificar_vsc

    pedidos: dict[str, set[str]] = defaultdict(set)
    for nome in arquivos:
        suf = nome.split("-", 1)[1]
        if suf in ASSINA and f"{secao_de(nome)}-{ASSINA[suf]}" in arquivos:
            pedidos[f"{secao_de(nome)}-{ASSINA[suf]}"].add(nome)
    for nome in arquivos:
        if nome.split("-", 1)[1] in ("vota.vsc", "sa.vsc"):
            pedidos.setdefault(nome, set())
    verif = {sig: verificar_vsc(arquivos[sig], dados) for sig, dados in pedidos.items()}

    linhas = []
    for nome in sorted(arquivos):
        m = NOME_RE.match(nome)
        if not m:
            raise ValueError(f"unexpected member name {nome!r}")
        turno, uf, mun, zona, secao, suf = m.groups()
        raw = arquivos[nome]
        sha = hashlib.sha512(raw).hexdigest()
        row = {"turno": int(turno) + 1, "uf": uf.upper(), "cd_mun": mun, "zona": zona,
               "secao": secao, "arquivo": nome, "tipo": TIPOS[suf], "tamanho": len(raw),
               "crc32": f"{zlib.crc32(raw):08x}", "sha512": sha, "par": None,
               "sha512_assinado": None, "hash_confere": None, "assinatura_arquivo": None,
               "vsc_valida": None, "vsc_falhas": None, "vsc_motivos": None}
        if suf in ASSINA:
            sig = f"{secao_de(nome)}-{ASSINA[suf]}"
            if sig in verif:
                v = verif[sig]
                h = v["hashes"].get(nome)
                row["par"] = sig
                row["sha512_assinado"] = h.hex() if h is not None else None
                row["hash_confere"] = h is not None and h.hex() == sha
                row["assinatura_arquivo"] = v["assinaturas_arquivos"].get(nome)
        else:
            v = verif[nome]
            row["par"] = ",".join(n for n in sorted(arquivos) if n in v["hashes"]) or None
            row["vsc_valida"] = v["assinatura_valida"]
            row["vsc_falhas"] = "; ".join(v["falhas"]) or None
            row["vsc_motivos"] = "; ".join(v["motivos"]) or None
        linhas.append(row)
    return linhas


def linha_ok(r: dict) -> bool:
    """Signature status of one manifest row (data file or signature file)."""
    if r["tipo"] in DADOS:
        return _txt(r["hash_confere"]) == "true" and _txt(r["assinatura_arquivo"]) == "true"
    return _txt(r["vsc_valida"]) == "true"


def secao_ok(linhas: list[dict]) -> bool:
    """True when every data file has its signed hash confirmed and every .vsc is valid."""
    return all(linha_ok(r) for r in linhas)


def ler_manifesto(path: Path) -> dict[str, dict]:
    """Manifest rows (all values as text) keyed by file name."""
    with gzip.open(path, "rt", newline="", encoding="utf-8") as f:
        return {r["arquivo"]: r for r in csv.DictReader(f)}


def escrever_manifesto(path: Path, linhas: list[dict]) -> None:
    """Write manifest rows sorted by file name (gzip with a fixed header time)."""
    with open(path, "wb") as raw, \
            gzip.GzipFile(fileobj=raw, mode="wb", mtime=0, filename="") as gz, \
            io.TextIOWrapper(gz, encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS, lineterminator="\n")
        w.writeheader()
        for r in sorted(linhas, key=lambda r: r["arquivo"]):
            w.writerow({k: _txt(r.get(k)) for k in CAMPOS})


def conferir_secao(arquivos: dict[str, bytes], manifesto: dict[str, dict],
                   asset: Optional[str]) -> tuple[list[dict], str, bool]:
    """Check one section's files against the manifest.

    Returns (problems, mode, ok). mode is "assinatura" when the signature
    file was at hand and the signature was verified again, "hash" when only
    the data file was at hand and its SHA-512 was compared with the signed
    SHA-512 recorded in the manifest. ok is the signature status of the
    section (recomputed in "assinatura" mode). asset, when given, must be the
    asset the manifest lists for each file.
    """
    problemas = []

    def prob(nome: str, texto: str) -> None:
        problemas.append({"arquivo": nome, "problema": texto})

    novas = linhas_secao(arquivos)
    com_assinatura = any(r["tipo"] not in DADOS for r in novas)
    ok = True
    for r in novas:
        nome = r["arquivo"]
        m = manifesto.get(nome)
        if m is None:
            prob(nome, "not in manifest")
            ok = False
            continue
        if asset is not None and m.get("asset") != asset:
            prob(nome, f"manifest lists it in {m.get('asset')!r}, found in {asset!r}")
        cols = list(DO_ARQUIVO)
        if r["tipo"] not in DADOS:
            cols += DA_ASSINATURA["vsc"]
        elif r["par"]:
            cols += DA_ASSINATURA["dados"]
        for k in cols:
            if _txt(r[k]) != m.get(k, ""):
                prob(nome, f"{k}: manifest {m.get(k)!r}, file {_txt(r[k])!r}")
        if r["tipo"] in DADOS and not r["par"]:
            # signature file not at hand: rely on the signed hash recorded
            if m.get("sha512_assinado") != r["sha512"]:
                prob(nome, "SHA-512 differs from the signed SHA-512 recorded in the manifest")
            ok = ok and linha_ok(m) and m.get("sha512_assinado") == r["sha512"]
        else:
            ok = ok and linha_ok(r)
    return problemas, "assinatura" if com_assinatura else "hash", ok


def _conferir_lote(args: tuple) -> tuple[list[dict], Counter, list[str]]:
    lote, manifesto, asset = args
    probs, cont, vistos = [], Counter(), []
    for arquivos in lote:
        p, modo, ok = conferir_secao(arquivos, manifesto, asset)
        probs.extend(p)
        cont[f"secoes_{modo}_{'ok' if ok else 'falha'}"] += 1
        vistos.extend(arquivos)
    return probs, cont, vistos


# ---------------------------------------------------------------------------
# Reading the archive
# ---------------------------------------------------------------------------

def ler_tar(path: Path) -> Iterator[tuple[str, bytes]]:
    """(name, bytes) of every regular member of a .tar or .tar.zst, in stream order.

    Nothing is written to disk; member names are only used as dictionary keys.
    """
    if not path.name.endswith(".tar.zst"):
        with tarfile.open(path, mode="r|") as tf:
            for m in tf:
                if m.isfile():
                    yield m.name, tf.extractfile(m).read()
        return
    if shutil.which("zstd") is None:
        raise SystemExit("zstd command line tool not found (needed for .tar.zst)")
    # input through stdin: the zstd CLI silently skips a symlinked file argument
    with open(path, "rb") as entrada:
        proc = subprocess.Popen(["zstd", "-dcq", "--long=31"], stdin=entrada,
                                stdout=subprocess.PIPE)
    completo = False
    try:
        with tarfile.open(fileobj=proc.stdout, mode="r|") as tf:
            for m in tf:
                if m.isfile():
                    yield m.name, tf.extractfile(m).read()
        # tarfile stops at the end-of-archive marker and leaves the record
        # padding unread; drain it so zstd does not exit on a broken pipe
        while proc.stdout.read(1 << 16):
            pass
        completo = True
    finally:
        if not completo:
            proc.kill()   # reader stopped early or failed: zstd exit code is moot
        proc.stdout.close()
        if proc.wait() != 0 and completo:
            raise OSError(f"zstd failed on {path}")


def agrupar_secoes(itens: Iterator[tuple[str, bytes]]) -> Iterator[dict[str, bytes]]:
    """Group (name, bytes) pairs sorted by name into one dict per section."""
    atual: dict[str, bytes] = {}
    for nome, raw in itens:
        if atual and secao_de(nome) != secao_de(next(iter(atual))):
            yield atual
            atual = {}
        atual[nome] = raw
    if atual:
        yield atual


def sha512_arquivo(path: Path) -> str:
    h = hashlib.sha512()
    with open(path, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 22), b""):
            h.update(bloco)
    return h.hexdigest()


def ler_sha512sums(path: Path) -> dict[str, str]:
    """Asset name -> SHA-512 from a SHA512SUMS file (sha512sum format)."""
    out = {}
    for linha in path.read_text().splitlines():
        if linha.strip():
            h, nome = linha.split(None, 1)
            out[nome.strip().lstrip("*")] = h
    return out


def ler_manifestos(d: Path) -> dict[str, dict]:
    manifesto: dict[str, dict] = {}
    for mp in sorted(d.glob("manifesto_bu_2026_*.csv.gz")):
        manifesto.update(ler_manifesto(mp))
    if not manifesto:
        raise SystemExit(f"no manifesto_bu_2026_*.csv.gz in {d}")
    return manifesto


# ---------------------------------------------------------------------------
# Reading the TSE zips
# ---------------------------------------------------------------------------

class ArquivoMudou(OSError):
    """The remote zip changed while it was being read."""


def cabecalho(url: str) -> dict:
    """Size, ETag and Last-Modified of a URL (HEAD request)."""
    req = urllib.request.Request(url, method="HEAD")
    with urllib.request.urlopen(req, timeout=60) as r:
        return {"url": url, "tamanho": int(r.headers["Content-Length"]),
                "etag": r.headers.get("ETag"), "last_modified": r.headers.get("Last-Modified")}


def baixar_range(url: str, ini: int, fim: int, etag: Optional[str] = None) -> bytes:
    """Bytes ini..fim (inclusive) of url, with retries and back-off on 403/429/5xx.

    With etag the request carries If-Range: a changed file answers 200 with
    the whole body instead of 206, which raises ArquivoMudou. Errors only slow
    the client down; server limits are never bypassed.
    """
    espera = 5
    for tentativa in range(12):
        try:
            h = {"Range": f"bytes={ini}-{fim}"}
            if etag:
                h["If-Range"] = etag
            req = urllib.request.Request(url, headers=h)
            with urllib.request.urlopen(req, timeout=180) as r:
                if r.status != 206:
                    raise ArquivoMudou(f"{url} answered {r.status} to a range request")
                if etag and r.headers.get("ETag") not in (None, etag):
                    raise ArquivoMudou(f"{url} ETag changed to {r.headers.get('ETag')}")
                d = r.read()
            if len(d) == fim - ini + 1:
                return d
            raise OSError(f"short read {len(d)} of {fim - ini + 1}")
        except urllib.error.HTTPError as e:
            if e.code not in (403, 429, 500, 502, 503, 504):
                raise
            _log(f"HTTP {e.code} on {url.rsplit('/', 1)[-1]}, waiting {espera * 6}s")
            time.sleep(espera * 6)
        except ArquivoMudou:
            raise
        except OSError as e:
            if tentativa == 11:
                raise
            _log(f"{type(e).__name__} {e}, retrying in {espera}s")
            time.sleep(espera)
        espera = min(espera * 2, 120)
    raise OSError("range failed")


class ZipRemoto(io.RawIOBase):
    """Seekable read-only view of a remote zip through HTTP Range requests.

    Used to read the central directory with zipfile.ZipFile; every request is
    pinned to the ETag seen in the first HEAD.
    """

    def __init__(self, url: str) -> None:
        self.url, self.pos = url, 0
        self.info = cabecalho(url)
        self.size = self.info["tamanho"]

    def seekable(self) -> bool:
        return True

    def readable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.pos

    def seek(self, off: int, whence: int = 0) -> int:
        self.pos = off if whence == 0 else (self.pos + off if whence == 1 else self.size + off)
        return self.pos

    def read(self, n: int = -1) -> bytes:
        if n < 0:
            n = self.size - self.pos
        if n == 0 or self.pos >= self.size:
            return b""
        fim = min(self.size, self.pos + n) - 1
        d = baixar_range(self.url, self.pos, fim, self.info["etag"])
        self.pos += len(d)
        return d

    def readinto(self, b) -> int:
        d = self.read(len(b))
        b[:len(d)] = d
        return len(d)


def membros_zip(turno: int, uf: str) -> tuple[dict, list[zipfile.ZipInfo]]:
    """Source metadata and members of the read kinds of one round/UF zip."""
    f = ZipRemoto(URL.format(t=turno, uf=uf))
    z = zipfile.ZipFile(f)
    infos = [i for i in z.infolist()
             if (m := NOME_RE.match(i.filename)) and int(m.group(1)) == turno - 1]
    return {**f.info, "membros_zip": len(z.infolist())}, infos


def membro(buf: bytes, base: int, info: zipfile.ZipInfo) -> bytes:
    """Bytes of one stored/deflated member taken from a range buffer starting at base."""
    i = info.header_offset - base
    h = LOCAL_HEADER.unpack_from(buf, i)
    if h[0] != b"PK\x03\x04":
        raise ValueError("bad local header")
    ini = i + LOCAL_HEADER.size + h[10] + h[11]
    dados = buf[ini:ini + info.compress_size]
    if len(dados) != info.compress_size:
        raise ValueError("member past the range")
    if info.compress_type == zipfile.ZIP_DEFLATED:
        dados = zlib.decompress(dados, -15)
    elif info.compress_type != zipfile.ZIP_STORED:
        raise ValueError(f"compression {info.compress_type}")
    if zlib.crc32(dados) != info.CRC or len(dados) != info.file_size:
        raise ValueError("CRC or size mismatch")
    return dados


def baixar_membro(url: str, info: zipfile.ZipInfo, etag: Optional[str]) -> bytes:
    """One member alone: local header first, then the exact byte span."""
    ini = info.header_offset
    h = LOCAL_HEADER.unpack(baixar_range(url, ini, ini + LOCAL_HEADER.size - 1, etag))
    fim = ini + LOCAL_HEADER.size + h[10] + h[11] + info.compress_size - 1
    return membro(baixar_range(url, ini, fim, etag), ini, info)


def planejar(infos: list[zipfile.ZipInfo], chunk: int, gap: int) -> list[tuple]:
    """Group members (sorted by offset) into (start, end_exclusive, members) ranges.

    Neighbouring members whose gap is at most gap bytes share one request of
    at most chunk bytes, as in zeresima.py.
    """
    folga = 1024   # local header name + extra field, bounded generously
    out: list[tuple] = []
    for i in sorted(infos, key=lambda x: x.header_offset):
        ini = i.header_offset
        fim = ini + 30 + len(i.filename) + folga + i.compress_size
        if out and ini - out[-1][1] <= gap and fim - out[-1][0] <= chunk:
            s, _, ms = out[-1]
            out[-1] = (s, fim, ms + [i])
        else:
            out.append((ini, fim, [i]))
    return out


def baixar_par(turno: int, uf: str, conexoes: int = 4, chunk_mb: int = 8,
               gap_kb: int = 256) -> tuple[dict, dict[str, bytes], dict[str, tuple]]:
    """Source metadata, member bytes and zip dates of the read kinds of one zip.

    The ETag is read again at the end; a zip that changed during the read
    raises ArquivoMudou.
    """
    fonte, infos = membros_zip(turno, uf)
    url, etag, tamanho = fonte["url"], fonte["etag"], fonte["tamanho"]
    plano = planejar(infos, chunk_mb << 20, gap_kb << 10)
    arquivos: dict[str, bytes] = {}
    lido = [0]
    lock = threading.Lock()

    def um(rng: tuple) -> None:
        ini, fim, membros = rng
        buf = baixar_range(url, ini, min(fim, tamanho) - 1, etag)
        out = {}
        for i in membros:
            try:
                out[i.filename] = membro(buf, ini, i)
            except ValueError as e:
                if "past the range" not in str(e):
                    raise
                out[i.filename] = baixar_membro(url, i, etag)
        with lock:
            arquivos.update(out)
            lido[0] += len(buf)

    with ThreadPoolExecutor(conexoes) as ex:
        list(ex.map(um, plano))
    depois = cabecalho(url)
    if (depois["etag"], depois["tamanho"]) != (etag, tamanho):
        raise ArquivoMudou(f"{url} changed during the read: {fonte} -> {depois}")
    faltam = {i.filename for i in infos} - set(arquivos)
    if faltam:
        raise OSError(f"{len(faltam)} members not read, e.g. {sorted(faltam)[:3]}")
    fonte.update({"turno": turno, "uf": uf, "lido_em": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                  "bytes_lidos": lido[0], "requisicoes": len(plano)})
    return fonte, arquivos, {i.filename: i.date_time for i in infos}


def data_zip(date_time: tuple) -> str:
    return "%04d-%02d-%02d %02d:%02d:%02d" % date_time


# ---------------------------------------------------------------------------
# conferir
# ---------------------------------------------------------------------------

def cmd_conferir(a: argparse.Namespace) -> int:
    d = Path(a.acervo).expanduser()
    erros: list[dict] = []
    manifesto = ler_manifestos(d)
    ufs = {u.upper() for u in a.ufs.split(",")} if a.ufs else None
    turnos = {int(t) for t in a.turnos.split(",")}
    alvo = {k: v for k, v in manifesto.items()
            if int(v["turno"]) in turnos and (ufs is None or v["uf"] in ufs)}
    cont: Counter = Counter()
    vistos: set[str] = set()
    pendentes: list = []

    def drenar(limite: int) -> None:
        """Collect finished batches until at most limite are still running."""
        while len(pendentes) > limite:
            probs, c, vs = pendentes.pop(0).result()
            erros.extend(probs)
            cont.update(c)
            vistos.update(vs)

    def lotes(secoes: Iterator[dict[str, bytes]], asset: Optional[str]) -> Iterator[tuple]:
        """Batches of 200 sections with only the manifest rows they need."""
        lote: list[dict[str, bytes]] = []
        for sec in secoes:
            lote.append(sec)
            if len(lote) == 200:
                yield lote, {n: manifesto[n] for s in lote for n in s if n in manifesto}, asset
                lote = []
        if lote:
            yield lote, {n: manifesto[n] for s in lote for n in s if n in manifesto}, asset

    if a.tse:
        fontes = {}
        for rp in sorted(d.glob("resumo_bu_2026_*.json")):
            for f in json.loads(rp.read_text()).get("fontes", []):
                fontes[(int(f["turno"]), f["uf"])] = f
        pares = sorted({(int(v["turno"]), v["uf"]) for v in alvo.values()})
        with ProcessPoolExecutor(a.workers) as ex:
            for turno, uf in pares:
                fonte, arquivos, _datas = baixar_par(turno, uf, a.conexoes)
                antes = fontes.get((turno, uf), {})
                if antes and antes.get("etag") != fonte["etag"]:
                    _log(f"{turno}t {uf}: zip ETag {fonte['etag']} differs from the archived "
                         f"{antes.get('etag')} (Last-Modified {fonte['last_modified']})")
                secoes = agrupar_secoes((n, arquivos[n]) for n in sorted(arquivos))
                n0 = len(erros)
                for args in lotes(secoes, None):
                    pendentes.append(ex.submit(_conferir_lote, args))
                    drenar(2 * a.workers)
                drenar(0)
                _log(f"{turno}t {uf}: {len(arquivos)} files, {len(erros) - n0} problems")
    else:
        somas = d / "SHA512SUMS"
        if somas.exists():
            for nome, h in ler_sha512sums(somas).items():
                p = d / nome
                if not p.exists():
                    erros.append({"arquivo": nome, "problema": "asset missing"})
                elif sha512_arquivo(p) != h:
                    erros.append({"arquivo": nome,
                                  "problema": "asset SHA-512 differs from SHA512SUMS"})
            _log(f"SHA512SUMS checked, {len(erros)} problems")
        else:
            _log("no SHA512SUMS in the directory, asset hashes not checked")
        assets = sorted({v["asset"] for v in alvo.values() if v["asset"]})
        with ProcessPoolExecutor(a.workers) as ex:
            for nome in assets:
                p = d / nome
                if not p.exists():
                    continue   # reported below file by file
                n0 = len(erros)
                for args in lotes(agrupar_secoes(ler_tar(p)), nome):
                    pendentes.append(ex.submit(_conferir_lote, args))
                    drenar(2 * a.workers)
                drenar(0)
                _log(f"{nome}: {len(erros) - n0} problems")
        alvo = {k: v for k, v in alvo.items() if v["asset"]}
    for nome in sorted(set(alvo) - vistos):
        erros.append({"arquivo": nome, "problema": "in manifest, not found"})
    print(json.dumps({"arquivos_esperados": len(alvo), "arquivos_conferidos": len(vistos),
                      **dict(sorted(cont.items())), "problemas": len(erros)}, indent=1))
    for e in erros[:50]:
        print("PROBLEM", e["arquivo"], e["problema"])
    if a.saida:
        with open(a.saida, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["arquivo", "problema"])
            w.writeheader()
            w.writerows(erros)
    return 1 if erros or any(k.endswith("_falha") for k in cont) else 0


# ---------------------------------------------------------------------------
# confrontar
# ---------------------------------------------------------------------------

def confrontar_membros(infos: list[zipfile.ZipInfo], manifesto: dict[str, dict]) -> list[dict]:
    """Classify each manifest file against the members of a zip served today.

    classes: igual (same CRC-32 and size), diferente, novo (member not in the
    manifest) and ausente (manifest file no longer in the zip).
    """
    out, vistos = [], set()
    for i in infos:
        m = manifesto.get(i.filename) or {}
        vistos.add(i.filename)
        crc = f"{i.CRC:08x}"
        if not m:
            classe = "novo"
        elif m["crc32"] == crc and int(m["tamanho"]) == i.file_size:
            classe = "igual"
        else:
            classe = "diferente"
        out.append({"arquivo": i.filename, "classe": classe, "crc32_acervo": m.get("crc32"),
                    "crc32_tse": crc, "tamanho_acervo": m.get("tamanho"),
                    "tamanho_tse": i.file_size, "data_zip_acervo": m.get("data_zip"),
                    "data_zip_tse": data_zip(i.date_time), "sha512_acervo": m.get("sha512"),
                    "sha512_tse": None})
    for nome, m in manifesto.items():
        if nome not in vistos:
            out.append({"arquivo": nome, "classe": "ausente", "crc32_acervo": m["crc32"],
                        "crc32_tse": None, "tamanho_acervo": m["tamanho"], "tamanho_tse": None,
                        "data_zip_acervo": m["data_zip"], "data_zip_tse": None,
                        "sha512_acervo": m["sha512"], "sha512_tse": None})
    return out


def cmd_confrontar(a: argparse.Namespace) -> int:
    d = Path(a.acervo).expanduser()
    manifesto = ler_manifestos(d)
    fontes = {}
    for rp in sorted(d.glob("resumo_bu_2026_*.json")):
        for f in json.loads(rp.read_text()).get("fontes", []):
            fontes[(int(f["turno"]), f["uf"])] = f
    por_par: dict[tuple, dict] = defaultdict(dict)
    for k, v in manifesto.items():
        por_par[(int(v["turno"]), v["uf"])][k] = v
    linhas, zips = [], []
    for (turno, uf), do_par in sorted(por_par.items()):
        info, infos = membros_zip(turno, uf)
        antes = fontes.get((turno, uf), {})
        zips.append({"turno": turno, "uf": uf, "etag_acervo": antes.get("etag"),
                     "etag_tse": info["etag"], "last_modified_acervo": antes.get("last_modified"),
                     "last_modified_tse": info["last_modified"],
                     "tamanho_acervo": antes.get("tamanho"), "tamanho_tse": info["tamanho"]})
        rows = confrontar_membros(infos, do_par)
        if a.baixar:
            por_nome = {i.filename: i for i in infos}
            for r in rows:
                if r["classe"] in ("diferente", "novo"):
                    raw = baixar_membro(info["url"], por_nome[r["arquivo"]], info["etag"])
                    r["sha512_tse"] = hashlib.sha512(raw).hexdigest()
        c = Counter(r["classe"] for r in rows)
        estado = ("not recorded" if not antes.get("etag") else
                  "same" if info["etag"] == antes["etag"] else "CHANGED")
        _log(f"{turno}t {uf}: ETag {estado}; {dict(c)}")
        linhas.extend({"turno": turno, "uf": uf, **r} for r in rows)
    resumo = {"classes": dict(Counter(r["classe"] for r in linhas)),
              "zips_com_etag_diferente": [f"{z['turno']}t {z['uf']}" for z in zips
                                          if z["etag_acervo"]
                                          and z["etag_acervo"] != z["etag_tse"]]}
    print(json.dumps(resumo, indent=1, ensure_ascii=False))
    if a.saida:
        campos = ["turno", "uf", "arquivo", "classe", "crc32_acervo", "crc32_tse",
                  "tamanho_acervo", "tamanho_tse", "data_zip_acervo", "data_zip_tse",
                  "sha512_acervo", "sha512_tse"]
        with open(a.saida, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=campos)
            w.writeheader()
            w.writerows(r for r in linhas if r["classe"] != "igual")
    return 1 if resumo["zips_com_etag_diferente"] or set(resumo["classes"]) - {"igual"} else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("conferir", help="check every file against the manifest")
    p.add_argument("--acervo", required=True, help="directory with the release assets")
    p.add_argument("--tse", action="store_true",
                   help="read the files from the TSE zips instead of the tar.zst assets")
    p.add_argument("--ufs", default="", help="only these UFs (comma separated)")
    p.add_argument("--turnos", default="1,2")
    p.add_argument("--conexoes", type=int, default=4, help="max concurrent requests (TSE: 4)")
    p.add_argument("--workers", type=int, default=4)
    p.add_argument("--saida", default="", help="CSV with every problem found")
    p = sub.add_parser("confrontar", help="compare the manifest with the TSE zips of today")
    p.add_argument("--acervo", required=True, help="directory with manifests and summaries")
    p.add_argument("--saida", default="", help="CSV with every file that is not equal")
    p.add_argument("--baixar", action="store_true",
                   help="download changed or new members and record their SHA-512")
    a = ap.parse_args()
    return {"conferir": cmd_conferir, "confrontar": cmd_confrontar}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
