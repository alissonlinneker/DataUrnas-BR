#!/usr/bin/env python3
"""Compare the TSE bulk package of the 2026 2nd round with the versioned files.

The TSE published, on 26/10/2026, one zip per UF with every file of every
section (bu_imgbu_logjez_rdv_vscmr_2026_2t_<UF>.zip). During the count the
collector in versionar_t2.py stored every BU (-bu.dat) and signature
(-vota.vsc) the moment it appeared on resultados.tse.jus.br.

This script reads only the central directory of each zip through HTTP Range
requests (a few requests per UF, nothing is downloaded in full) and compares
the CRC-32 and size of each -bu.dat and -vota.vsc with the CRC-32 and size of
every version the collector stored under the same file name. Each member falls
in one of these classes:

  igual_ultima      equal to the last stored version
  igual_anterior    equal to an older stored version, not the last one
  diferente         differs from every stored version (the member is then
                    downloaded and its SHA-512 recorded for inspection)
  sem_versao        the collector never stored this file name

Output (in --saida): pacote_membros.parquet, confronto.parquet and
resumo.json. Run it where the collector parts live (the London server).

Usage:
  python3 scripts/ele2026/confronto_pacote_t2.py \
      --versoes ~/dataurnas-mac/versoes/2026/t2 ~/dataurnas-versoes-t2-nne \
      --saida ~/dataurnas-pacote-t2
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import urllib.request
import zipfile
import zlib
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

URL = ("https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2026/arqurnatot/"
       "bu_imgbu_logjez_rdv_vscmr_2026_2t_{uf}.zip")
UFS = ("AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO ZZ"
       .split())
TIPOS = {"bu.dat": "bu", "vota.vsc": "vota"}
NOME_RE = re.compile(r"^o03221([a-z]{2})(\d{5})(\d{4})(\d{4})-(.+)$")


class HttpRangeFile(io.RawIOBase):
    """Read-only seekable file backed by HTTP Range requests."""

    def __init__(self, url: str) -> None:
        self.url, self.pos = url, 0
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=60) as r:
            self.size = int(r.headers["Content-Length"])
            self.last_modified = r.headers.get("Last-Modified")

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
        end = min(self.size, self.pos + n) - 1
        req = urllib.request.Request(self.url, headers={"Range": f"bytes={self.pos}-{end}"})
        for tentativa in range(5):
            try:
                with urllib.request.urlopen(req, timeout=120) as r:
                    data = r.read()
                break
            except OSError:
                if tentativa == 4:
                    raise
        self.pos += len(data)
        return data

    def readinto(self, b) -> int:
        data = self.read(len(b))
        b[:len(data)] = data
        return len(data)


def membros_uf(uf: str) -> tuple[str, str, list[dict]]:
    """List the -bu.dat and -vota.vsc members of one UF zip (central directory only)."""
    f = HttpRangeFile(URL.format(uf=uf))
    z = zipfile.ZipFile(f)
    rows = []
    for i in z.infolist():
        m = NOME_RE.match(i.filename)
        if not m or m.group(5) not in TIPOS:
            continue
        rows.append({"uf": m.group(1), "nome": i.filename, "tipo": TIPOS[m.group(5)],
                     "crc": i.CRC, "tamanho": i.file_size,
                     "data_zip": "%04d-%02d-%02d %02d:%02d:%02d" % i.date_time})
    return uf, f.last_modified, rows


def crc_part(path: str) -> list[dict]:
    """CRC-32 and size of each stored bu/vota version in one collector part."""
    t = pq.read_table(path, columns=["nome", "tipo", "coletado_em", "st_hash", "conteudo"],
                      filters=[("tipo", "in", ["bu", "vota"])])
    out = []
    for r in t.to_pylist():
        c = r["conteudo"]
        out.append({"nome": r["nome"], "coletado_em": r["coletado_em"],
                    "st_hash": r["st_hash"], "crc": zlib.crc32(c), "tamanho": len(c),
                    "sha512": hashlib.sha512(c).hexdigest()})
    return out


def baixar_membro(uf: str, nome: str) -> str:
    """Download one member through Range requests and return its SHA-512."""
    z = zipfile.ZipFile(HttpRangeFile(URL.format(uf=uf.upper())))
    return hashlib.sha512(z.read(nome)).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--versoes", nargs="+", required=True,
                    help="collector output dirs (each with bus/parts)")
    ap.add_argument("--saida", required=True)
    ap.add_argument("--workers", type=int, default=32)
    a = ap.parse_args()
    out = Path(a.saida).expanduser()
    out.mkdir(parents=True, exist_ok=True)

    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(membros_uf, UFS))
    pacote = [r for _, _, rows in res for r in rows]
    datas = {uf: lm for uf, lm, _ in res}
    pq.write_table(pa.Table.from_pylist(pacote), out / "pacote_membros.parquet")
    print("membros no pacote:", len(pacote), flush=True)

    parts = sorted(str(p) for d in a.versoes
                   for p in Path(d).expanduser().glob("bus/parts/versoes-*.parquet"))
    versoes: dict[str, list[dict]] = {}
    with ProcessPoolExecutor(a.workers) as ex:
        for rows in ex.map(crc_part, parts, chunksize=4):
            for r in rows:
                versoes.setdefault(r["nome"], []).append(r)
    print("partes lidas:", len(parts), "nomes guardados:", len(versoes), flush=True)

    linhas = []
    for m in pacote:
        vs = sorted(versoes.get(m["nome"], []), key=lambda v: v["coletado_em"])
        # the same content may be stored twice (two collectors): dedupe by CRC+size
        iguais = [v for v in vs if v["crc"] == m["crc"] and v["tamanho"] == m["tamanho"]]
        if not vs:
            classe = "sem_versao"
        elif (vs[-1]["crc"], vs[-1]["tamanho"]) == (m["crc"], m["tamanho"]):
            classe = "igual_ultima"
        elif iguais:
            classe = "igual_anterior"
        else:
            classe = "diferente"
        distintas = len({(v["crc"], v["tamanho"]) for v in vs})
        linhas.append({**m, "classe": classe, "versoes_distintas": distintas,
                       "primeira_coleta": vs[0]["coletado_em"] if vs else None,
                       "coleta_igual": iguais[0]["coletado_em"] if iguais else None,
                       "sha512_guardado": iguais[0]["sha512"] if iguais else
                       (vs[-1]["sha512"] if vs else None),
                       "sha512_pacote": None})

    for ln in linhas:
        if ln["classe"] == "diferente":
            ln["sha512_pacote"] = baixar_membro(ln["uf"], ln["nome"])
    pq.write_table(pa.Table.from_pylist(linhas), out / "confronto.parquet")

    resumo = {
        "pacote_last_modified": datas,
        "membros": len(linhas),
        "por_tipo_classe": {f"{t}:{c}": n for (t, c), n in
                            sorted(Counter((ln["tipo"], ln["classe"]) for ln in linhas).items())},
        "nomes_guardados_fora_do_pacote": len(set(versoes) - {m["nome"] for m in pacote}),
        "diferentes": [{k: ln[k] for k in ("nome", "crc", "tamanho", "sha512_guardado",
                                           "sha512_pacote")}
                       for ln in linhas if ln["classe"] == "diferente"][:200],
    }
    (out / "resumo.json").write_text(json.dumps(resumo, indent=2, ensure_ascii=False))
    print(json.dumps({k: v for k, v in resumo.items() if k != "diferentes"}, indent=2,
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
