"""Prepara o catálogo de hashes por arquivo de 2026 para publicação como anexos.

Os catálogos ``data/parquet/2026/integridade/arquivos_<uf>.parquet`` (um registro
por arquivo publicado, com MD5, SHA-256 e SHA-512) somam centenas de MB e não
são versionados no git. Eles vão como anexos individuais de uma versão do
projeto no GitHub, um por UF, junto com um ``SHA256SUMS``.

O script:

- copia cada ``arquivos_<uf>.parquet`` para ``dist/catalogo-integridade-2026/``;
- grava ali o ``SHA256SUMS`` (formato do ``sha256sum``, conferível com
  ``sha256sum -c SHA256SUMS``);
- grava ``data/parquet/2026/integridade/catalogo_manifest.json`` (versionado),
  com arquivo, UF, tamanho, SHA-256, linhas e colunas de cada anexo. O painel
  usa esse manifesto para baixar só a UF consultada e conferir o SHA-256;
- imprime o comando ``gh release upload`` (não executa nada no GitHub).

Uso:
    python3 scripts/ele2026/publicar_catalogo.py
    python3 scripts/ele2026/publicar_catalogo.py --versao v0.3.0
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import sys
from pathlib import Path

import pyarrow.parquet as pq

RAIZ = Path(__file__).resolve().parents[2]
PASTA = RAIZ / "data/parquet/2026/integridade"
DIST = RAIZ / "dist/catalogo-integridade-2026"
REPO = "alissonlinneker/DataUrnas-BR"
VERSAO = "v0.3.0"
MANIFESTO = "catalogo_manifest.json"
PADRAO = re.compile(r"^arquivos_(?P<uf>[a-z]{2})(?:_[^/]+)?\.parquet$")


def sha256_arquivo(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for bloco in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def catalogos(pasta: Path) -> list[Path]:
    return sorted(p for p in pasta.glob("arquivos_*.parquet") if PADRAO.match(p.name))


def montar(pasta: Path = PASTA, dist: Path = DIST, versao: str = VERSAO, repo: str = REPO) -> dict:
    """Copia os catálogos para ``dist``, grava SHA256SUMS e o manifesto; devolve o manifesto."""
    arquivos = catalogos(pasta)
    if not arquivos:
        raise SystemExit(f"Nenhum arquivos_<uf>.parquet em {pasta}")
    dist.mkdir(parents=True, exist_ok=True)
    for antigo in list(dist.glob("arquivos_*.parquet")) + [dist / "SHA256SUMS"]:
        antigo.unlink(missing_ok=True)

    entradas = []
    for origem in arquivos:
        meta = pq.ParquetFile(origem).metadata  # falha aqui se o arquivo estiver incompleto
        destino = dist / origem.name
        shutil.copyfile(origem, destino)  # só o conteúdo, sem atributos estendidos
        sha = sha256_arquivo(destino)
        if sha != sha256_arquivo(origem):
            raise SystemExit(f"{origem.name} mudou durante a cópia; rode de novo com a coleta parada")
        entradas.append({
            "arquivo": origem.name,
            "uf": PADRAO.match(origem.name)["uf"],
            "tamanho": destino.stat().st_size,
            "sha256": sha,
            "linhas": int(meta.num_rows),
            "colunas": list(meta.schema.to_arrow_schema().names),
        })

    (dist / "SHA256SUMS").write_text(
        "".join(f"{e['sha256']}  {e['arquivo']}\n" for e in entradas), encoding="utf-8")
    manifesto = {
        "descricao": "Catálogo de hashes por arquivo das urnas de 2026, um anexo por UF.",
        "versao": versao,
        "url_base": f"https://github.com/{repo}/releases/download/{versao}",
        "total_arquivos": len(entradas),
        "total_bytes": sum(e["tamanho"] for e in entradas),
        "total_linhas": sum(e["linhas"] for e in entradas),
        "arquivos": entradas,
    }
    (pasta / MANIFESTO).write_text(json.dumps(manifesto, ensure_ascii=False, indent=1) + "\n",
                                   encoding="utf-8")
    return manifesto


def comando_upload(dist: Path = DIST, versao: str = VERSAO, repo: str = REPO) -> str:
    try:
        rel = dist.relative_to(RAIZ)
    except ValueError:
        rel = dist
    return (f"gh release upload {versao} {rel}/arquivos_*.parquet {rel}/SHA256SUMS "
            f"--repo {repo} --clobber")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--versao", default=VERSAO, help=f"tag da versão (padrão {VERSAO})")
    ap.add_argument("--repo", default=REPO)
    ap.add_argument("--pasta", type=Path, default=PASTA)
    ap.add_argument("--dist", type=Path, default=DIST)
    args = ap.parse_args(argv)

    m = montar(args.pasta, args.dist, args.versao, args.repo)
    mb = f"{m['total_bytes'] / (1 << 20):.1f}".replace(".", ",")
    linhas = f"{m['total_linhas']:,}".replace(",", ".")
    print(f"{m['total_arquivos']} catálogos, {mb} MB, {linhas} linhas")
    print(f"Anexos e SHA256SUMS em: {args.dist}")
    print(f"Manifesto (versionar): {args.pasta / MANIFESTO}")
    print("\nCom a versão já criada no GitHub, envie os anexos com:\n")
    print(f"  {comando_upload(args.dist, args.versao, args.repo)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
