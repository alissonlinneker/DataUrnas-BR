#!/usr/bin/env python3
"""Build the archive of signed 2026 BUs (release "acervo-bu-2026").

A second, dated copy of every signed BU of both 2026 rounds, so that anyone
can later prove what the TSE published even if the official zips are
republished. Each BU is read together with the signature file that signs it:

  -bu.dat    signed by -vota.vsc   (voting machine)
  -busa.dat  signed by -sa.vsc     (Sistema de Apuração sections)

Every signature is verified during the build (verificar_vsc) and its SHA-512,
the SHA-512 it signs for the BU and the result go to the manifest. By default
only the BUs go into the tar.zst: a signature file is about 62 KB, most of it
twelve 4765-byte software-part signatures that do not compress (a test on the
AC 1st round shrank 166 MB of bu+vsc only to 155 MB), so keeping them would
need about 60 GB. --com-vsc packs them too.

Source: the official national package, one zip per round and UF
  bu_imgbu_logjez_rdv_vscmr_2026_<1t|2t>_<UF>.zip   (ZZ = abroad)
Only those four member kinds are read, through HTTP Range requests on the zip:
neighbouring members are fetched in one request (blocks up to --chunk-mb,
joining members whose gap is under --gap-kb), at most --conexoes requests at
a time (TSE limit: 4). Every request is pinned to the zip ETag (If-Range) and
the ETag is read again at the end, so a zip republished during the read is
detected. Each member is checked against the CRC-32 of the central directory.

Per round and UF the files go, sorted by name, into one deterministic tar
(zip member time as mtime) compressed with zstd. A UF whose archive would
exceed --limite-gib is split into parts by section.

Subcommands:
  construir  one tar.zst (or parts) per round and UF in --saida, plus a
             partial manifest and a JSON record per pair under --saida/partes;
             pairs already done are skipped
  fechar     merge the partial manifests into manifesto_bu_2026_<1t|2t>.csv.gz,
             write resumo_bu_2026_<1t|2t>.json (source zips with ETag,
             Last-Modified and size, counts, signature results, assets) and
             SHA512SUMS of every asset

The manifest columns and the signature checks live in conferir_acervo_bu.py,
which also verifies a downloaded copy of the archive.

Usage (analysis server):
  uv run python scripts/ele2026/acervo_bu.py construir --saida ~/dataurnas-acervo-bu/out
  uv run python scripts/ele2026/acervo_bu.py fechar --saida ~/dataurnas-acervo-bu/out
"""

from __future__ import annotations

import argparse
import calendar
import io
import json
import math
import subprocess
import sys
import tarfile
import time
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT / "src"), str(ROOT / "scripts" / "ele2026")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import conferir_acervo_bu as C  # noqa: E402


def _log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def compactar(nomes: list[str], arquivos: dict[str, bytes], datas: dict, destino: Path,
              a: argparse.Namespace) -> int:
    """Write the named files, in order, into a deterministic tar piped to zstd."""
    cmd = ["zstd", "-q", "-f", f"-{a.nivel}", f"--long={a.long}", f"-T{a.threads}",
           "-o", str(destino), "-"]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    with tarfile.open(fileobj=proc.stdin, mode="w|", format=tarfile.USTAR_FORMAT) as tf:
        for nome in nomes:
            raw = arquivos[nome]
            ti = tarfile.TarInfo(nome)
            ti.size, ti.mode = len(raw), 0o644
            # zip member time as recorded by the TSE (no time zone in zip)
            ti.mtime = calendar.timegm(datas[nome] + (0, 0, -1))
            tf.addfile(ti, io.BytesIO(raw))
    proc.stdin.close()
    if proc.wait() != 0:
        raise OSError(f"zstd failed for {destino}")
    return destino.stat().st_size


def empacotar(turno: int, uf: str, arquivos: dict[str, bytes], datas: dict, saida: Path,
              a: argparse.Namespace) -> dict[str, list[str]]:
    """Pack one round/UF; split into parts by section when over the size limit.

    Returns asset name -> member names in it.
    """
    nomes = sorted(n for n in arquivos if a.com_vsc or C.TIPOS[n.split("-", 1)[1]]
                   in ("bu", "busa"))
    base = f"acervo_bu_2026_{turno}t_{uf}"
    limite = int(a.limite_gib * (1 << 30))
    unico = saida / f"{base}.tar.zst"
    t0 = time.time()
    tam = compactar(nomes, arquivos, datas, unico, a)
    _log(f"{base}: {sum(len(arquivos[n]) for n in nomes) / 1e6:.0f} MB -> {tam / 1e6:.0f} MB "
         f"in {time.time() - t0:.0f}s")
    if tam <= limite:
        return {unico.name: nomes}
    unico.unlink()
    n = math.ceil(tam / (limite * 0.85))
    secoes: dict[str, list[str]] = defaultdict(list)
    for nome in nomes:
        secoes[C.secao_de(nome)].append(nome)
    grupos: list[list[str]] = [[] for _ in range(n)]
    total = sum(len(arquivos[x]) for x in nomes)
    acum = 0
    for sec in sorted(secoes):
        k = min(n - 1, int(acum * n / total))
        grupos[k].extend(secoes[sec])
        acum += sum(len(arquivos[x]) for x in secoes[sec])
    out = {}
    for k, g in enumerate(grupos, 1):
        p = saida / f"{base}_p{k}.tar.zst"
        t = compactar(g, arquivos, datas, p, a)
        if t > limite:
            raise OSError(f"{p.name} still {t} bytes; raise the number of parts")
        _log(f"{p.name}: {t / 1e6:.0f} MB")
        out[p.name] = g
    return out


def construir_par(turno: int, uf: str, a: argparse.Namespace, saida: Path,
                  pool: ProcessPoolExecutor) -> None:
    partes = saida / "partes"
    marca = partes / f"{turno}t_{uf}.json"
    if marca.exists():
        _log(f"{turno}t {uf}: already done")
        return
    t0 = time.time()
    fonte, arquivos, datas = C.baixar_par(turno, uf, a.conexoes, a.chunk_mb, a.gap_kb)
    t1 = time.time()
    _log(f"{turno}t {uf}: {len(arquivos)} files, {fonte['bytes_lidos'] / 1e6:.0f} MB read "
         f"in {t1 - t0:.0f}s ({fonte['requisicoes']} requests)")
    secoes: dict[str, dict[str, bytes]] = defaultdict(dict)
    for nome, raw in arquivos.items():
        secoes[C.secao_de(nome)][nome] = raw
    linhas = [r for rs in pool.map(C.linhas_secao, list(secoes.values()), chunksize=64)
              for r in rs]
    assets = empacotar(turno, uf, arquivos, datas, saida, a)
    asset_de = {n: asset for asset, ns in assets.items() for n in ns}
    for r in linhas:
        r["data_zip"] = C.data_zip(datas[r["arquivo"]])
        r["asset"] = asset_de.get(r["arquivo"])
    C.escrever_manifesto(partes / f"manifesto_{turno}t_{uf}.csv.gz", linhas)
    fonte["assets"] = {k: (saida / k).stat().st_size for k in assets}
    fonte["segundos"] = round(time.time() - t0)
    tmp = marca.with_suffix(".tmp")
    tmp.write_text(json.dumps(fonte, indent=1, ensure_ascii=False))
    tmp.rename(marca)
    _log(f"{turno}t {uf}: done in {fonte['segundos']}s")


def cmd_construir(a: argparse.Namespace) -> None:
    saida = Path(a.saida).expanduser()
    (saida / "partes").mkdir(parents=True, exist_ok=True)
    ufs = [u.upper() for u in a.ufs.split(",")] if a.ufs else C.UFS
    with ProcessPoolExecutor(a.workers) as pool:
        for t in (int(x) for x in a.turnos.split(",")):
            for uf in ufs:
                construir_par(t, uf, a, saida, pool)


def cmd_fechar(a: argparse.Namespace) -> None:
    saida = Path(a.saida).expanduser()
    partes = saida / "partes"
    for turno in (1, 2):
        linhas = []
        fontes = []
        for uf in C.UFS:
            mp = partes / f"manifesto_{turno}t_{uf}.csv.gz"
            jp = partes / f"{turno}t_{uf}.json"
            if not (mp.exists() and jp.exists()):
                raise SystemExit(f"missing pair {turno}t {uf}")
            linhas.extend(C.ler_manifesto(mp).values())
            fontes.append(json.loads(jp.read_text()))
        C.escrever_manifesto(saida / f"manifesto_bu_2026_{turno}t.csv.gz", linhas)
        por_secao: dict[str, list[dict]] = defaultdict(list)
        for r in linhas:
            por_secao[C.secao_de(r["arquivo"])].append(r)
        falhas = [r for r in linhas if
                  (r["tipo"] in ("bu", "busa") and
                   (r["hash_confere"] != "true" or r["assinatura_arquivo"] != "true"))
                  or (r["tipo"] in ("vota", "sa") and r["vsc_valida"] != "true")]
        tipos = Counter(r["tipo"] for r in linhas)
        bytes_tipo = Counter()
        for r in linhas:
            bytes_tipo[r["tipo"]] += int(r["tamanho"])
        assets = {k: v for f in fontes for k, v in f["assets"].items()}
        resumo = {
            "turno": turno,
            "secoes": len(por_secao),
            "secoes_assinatura_ok": sum(C.secao_ok(v) for v in por_secao.values()),
            "arquivos_por_tipo": dict(sorted(tipos.items())),
            "bytes_por_tipo": dict(sorted(bytes_tipo.items())),
            "bu_sem_assinatura": sum(1 for r in linhas if r["tipo"] in ("bu", "busa")
                                     and not r["par"]),
            "falhas": [{k: r[k] for k in ("arquivo", "tipo", "hash_confere",
                                          "assinatura_arquivo", "vsc_valida", "vsc_falhas")}
                       for r in falhas],
            "motivos_vsc": dict(Counter(r["vsc_motivos"] for r in linhas
                                        if r["tipo"] in ("vota", "sa") and r["vsc_motivos"])),
            "assets": dict(sorted(assets.items())),
            "bytes_assets": sum(assets.values()),
            "fontes": sorted(({k: f[k] for k in ("turno", "uf", "url", "etag", "last_modified",
                                                 "tamanho", "membros_zip", "lido_em",
                                                 "bytes_lidos", "requisicoes")}
                              for f in fontes), key=lambda f: f["uf"]),
        }
        (saida / f"resumo_bu_2026_{turno}t.json").write_text(
            json.dumps(resumo, indent=1, ensure_ascii=False) + "\n")
        _log(f"{turno}t: {resumo['secoes']} sections, {resumo['secoes_assinatura_ok']} ok, "
             f"{len(falhas)} failing files, assets {resumo['bytes_assets'] / 1e9:.2f} GB")
    nomes = sorted(p.name for p in saida.iterdir()
                   if p.name.endswith(".tar.zst") or p.name.startswith(("manifesto_bu_2026_",
                                                                         "resumo_bu_2026_")))
    somas = [f"{C.sha512_arquivo(saida / n)}  {n}" for n in nomes]
    (saida / "SHA512SUMS").write_text("\n".join(somas) + "\n")
    _log(f"SHA512SUMS: {len(nomes)} assets")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("construir")
    p.add_argument("--saida", required=True)
    p.add_argument("--ufs", default="")
    p.add_argument("--turnos", default="1,2")
    p.add_argument("--conexoes", type=int, default=4, help="max concurrent requests (TSE: 4)")
    p.add_argument("--chunk-mb", type=int, default=8)
    p.add_argument("--gap-kb", type=int, default=256)
    p.add_argument("--workers", type=int, default=48, help="processes checking signatures")
    p.add_argument("--nivel", type=int, default=19, help="zstd level")
    p.add_argument("--long", type=int, default=27, help="zstd long-distance window (log2)")
    p.add_argument("--threads", type=int, default=0, help="zstd threads (0 = all cores)")
    p.add_argument("--limite-gib", type=float, default=1.9, help="max size of one asset")
    p.add_argument("--com-vsc", action="store_true",
                   help="also pack the signature files (about 60 GB more for both rounds)")
    p = sub.add_parser("fechar")
    p.add_argument("--saida", required=True)
    a = ap.parse_args()
    {"construir": cmd_construir, "fechar": cmd_fechar}[a.cmd](a)


if __name__ == "__main__":
    main()
