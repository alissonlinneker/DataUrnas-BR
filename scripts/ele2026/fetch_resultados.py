#!/usr/bin/env python3
"""Baixa o resultado agregado de Presidente (2026, 1º ou 2º turno) do TSE.

Níveis: Brasil, cada UF (27 + ZZ exterior) e cada município (inclusive
cidades do exterior). Grava em data/parquet/2026/ (1º turno) ou
data/parquet/2026/t2/ (2º turno, --turno 2):
  candidatos.parquet, resultado_uf.parquet, resultado_municipio.parquet,
  resumo_br.json

Uso:
  python3 scripts/ele2026/fetch_resultados.py [--concorrencia 16]
  python3 scripts/ele2026/fetch_resultados.py --turno 2
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import pyarrow as pa  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from dataurnas.downloader import ele2026 as E  # noqa: E402

log = logging.getLogger("fetch_resultados")


def write_parquet(rows: list[dict], path: Path) -> None:
    table = pa.Table.from_pylist(rows)
    tmp = path.with_suffix(".parquet.tmp")
    pq.write_table(table, tmp, compression="zstd")
    tmp.replace(path)
    log.info("gravado %s (%d linhas)", path.name, len(rows))


async def main(args: argparse.Namespace) -> int:
    out = Path(args.saida)
    out.mkdir(parents=True, exist_ok=True)
    p = E.parametros_turno(args.turno)
    eleicao, ciclo = p["eleicao"], p["ciclo"]
    f = E.HttpFetcher(concurrency=args.concorrencia)
    t0 = time.time()
    try:
        br = await f.get_json(E.url_resultado("br", eleicao=eleicao, ciclo=ciclo))
        if not br:
            log.error("resultado nacional indisponível")
            return 1
        candidatos = E.parse_candidatos(br)
        numeros = [c["numero"] for c in candidatos]
        write_parquet(candidatos, out / "candidatos.parquet")

        cm = await f.get_json(E.url_municipios(eleicao=eleicao, ciclo=ciclo))
        municipios = list(E.iter_municipios(cm))
        ufs = sorted({m["uf"] for m in municipios})
        log.info("%d UFs, %d municípios", len(ufs), len(municipios))

        # UFs
        uf_jsons = await asyncio.gather(*[f.get_json(E.url_resultado(uf, eleicao=eleicao, ciclo=ciclo))
                                         for uf in ufs])
        uf_rows = []
        for uf, d in zip(ufs, uf_jsons, strict=True):
            if not d:
                log.warning("sem resultado para UF %s", uf)
                continue
            uf_rows.append(E.resultado_row(d, numeros, uf=uf))
        write_parquet(uf_rows, out / "resultado_uf.parquet")

        # Municípios
        done = 0

        async def um(m: dict):
            nonlocal done
            d = await f.get_json(E.url_resultado(f"{m['uf']}{m['cd_mun']}",
                                                 eleicao=eleicao, ciclo=ciclo))
            done += 1
            if done % 500 == 0:
                log.info("municípios: %d/%d", done, len(municipios))
            return m, d

        res = await asyncio.gather(*[um(m) for m in municipios], return_exceptions=True)
        mun_rows, faltando = [], []
        for item in res:
            if isinstance(item, BaseException):
                faltando.append(repr(item))
                continue
            m, d = item
            if not d:
                faltando.append(f"{m['uf']}{m['cd_mun']}")
                continue
            ident = {k: m[k] for k in ("uf", "cd_mun", "cd_ibge", "nome", "capital")}
            mun_rows.append(E.resultado_row(d, numeros, **ident))
        write_parquet(mun_rows, out / "resultado_municipio.parquet")

        tot = E.parse_totais(br)
        resumo = {
            "eleicao": eleicao,
            "pleito": p["pleito"],
            "ciclo": ciclo,
            "cargo": "Presidente",
            "turno": p["turno"],
            "data_eleicao": p["data"],
            "data_geracao_tse": f"{br.get('dg')} {br.get('hg')}",
            "totais": tot,
            "candidatos": [
                {k: c[k] for k in ("numero", "nome_urna", "partido_sigla", "votos",
                                   "pct_validos", "situacao")}
                for c in candidatos
            ],
            "n_ufs": len(uf_rows),
            "n_municipios": len(mun_rows),
            "municipios_faltando": faltando,
            "checagem": {
                "soma_uf_votos_validos": sum(r["votos_validos"] or 0 for r in uf_rows),
                "soma_mun_votos_validos": sum(r["votos_validos"] or 0 for r in mun_rows),
                "br_votos_validos": tot["votos_validos"],
            },
            "http": f.stats,
            "segundos": round(time.time() - t0, 1),
        }
        (out / "resumo_br.json").write_text(
            json.dumps(resumo, ensure_ascii=False, indent=2), encoding="utf-8")
        log.info("resumo: %s", json.dumps(resumo["checagem"]))
        if faltando:
            log.warning("%d municípios sem resultado: %s", len(faltando), faltando[:10])
            return 2
        return 0
    finally:
        await f.close()


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--turno", type=int, choices=E.TURNOS, default=1,
                    help="turno da eleição: 1 (pleito 3220) ou 2 (pleito 3221); padrão: 1")
    ap.add_argument("--concorrencia", type=int, default=16,
                    help="máximo de requisições HTTP simultâneas (padrão: 16)")
    ap.add_argument("--saida", default=None,
                    help="diretório de saída dos Parquet (padrão: data/parquet/2026 no "
                         "1º turno, data/parquet/2026/t2 no 2º)")
    a = ap.parse_args(argv)
    if a.saida is None:
        a.saida = str(E.parametros_turno(a.turno)["saida"])
    return a


if __name__ == "__main__":
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    sys.exit(asyncio.run(main(args)))
