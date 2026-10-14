#!/usr/bin/env python3
"""Confere se a soma dos BUs por seção bate com o resultado oficial da UF.

Compara, por UF presente em secoes_2026.parquet:
  - votos por candidato (BU) x vap do resultado_uf.parquet
  - brancos, nulos, comparecimento e votos nominais
  - número de seções com BU x seções totalizadas

Uso:
  python3 scripts/ele2026/reconcile.py [--ufs ac,rr]
Sai com código 1 se houver divergência.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import duckdb  # noqa: E402

from dataurnas.config import PARQUET_2026_DIR  # noqa: E402


def reconciliar(base: Path, ufs: list[str] | None = None) -> tuple[list[dict], bool]:
    con = duckdb.connect()
    sec = str(base / "secoes_2026.parquet")
    vot = str(base / "votos_presidente_2026.parquet")
    res_uf = str(base / "resultado_uf.parquet")
    cand = str(base / "candidatos.parquet")
    ufs_bu = [r[0] for r in con.execute(
        f"SELECT DISTINCT uf FROM read_parquet('{sec}') ORDER BY 1").fetchall()]
    if ufs:
        ufs_bu = [u for u in ufs_bu if u in ufs]
    numeros = [r[0] for r in con.execute(
        f"SELECT numero FROM read_parquet('{cand}') ORDER BY votos DESC").fetchall()]
    linhas, ok_geral = [], True
    for uf in ufs_bu:
        oficial = con.execute(
            f"SELECT * FROM read_parquet('{res_uf}') WHERE uf = ?", [uf]).fetchdf()
        if oficial.empty:
            continue
        of = oficial.iloc[0]
        bu = con.execute(f"""
            SELECT count(*) FILTER (WHERE status = 'ok') AS secoes_bu,
                   count(*) FILTER (WHERE status = 'agregada') AS agregadas,
                   count(*) FILTER (WHERE status NOT IN ('ok', 'agregada', 'nao_instalada')) AS sem_bu,
                   coalesce(sum(comparecimento), 0) AS comparecimento,
                   coalesce(sum(votos_brancos), 0) AS brancos,
                   coalesce(sum(votos_nulos), 0) AS nulos,
                   coalesce(sum(votos_nominais), 0) AS nominais
            FROM read_parquet('{sec}') WHERE uf = ?""", [uf]).fetchone()
        por_cand = dict(con.execute(f"""
            SELECT numero, sum(votos) FROM read_parquet('{vot}')
            WHERE uf = ? AND tipo_voto = 'nominal' GROUP BY 1""", [uf]).fetchall())
        # Voto nominal no BU para número que não e candidato válido (registro
        # indeferido/cancelado) e contado pelo TSE como "nulo técnico" (vnt).
        nulos_tecnicos = sum(int(v) for n, v in por_cand.items() if n not in numeros)
        nominais_validos = int(bu[6]) - nulos_tecnicos
        checks = [
            ("comparecimento", bu[3], int(of["comparecimento"])),
            ("brancos", bu[4], int(of["votos_brancos"])),
            ("nulos", bu[5], int(of["votos_nulos"])),
            ("nulos_tecnicos", nulos_tecnicos, int(of["votos_nulos_tecnicos"] or 0)),
            ("nominais_validos", nominais_validos, int(of["votos_nominais"])),
            ("secoes_com_bu_x_instaladas", bu[0], int(of["secoes_instaladas"])),
        ]
        checks += [(f"cand_{n}", int(por_cand.get(n, 0)), int(of[f"v_{n}"])) for n in numeros]
        for nome, v_bu, v_of in checks:
            ok = v_bu == v_of
            ok_geral &= ok
            linhas.append({"uf": uf, "item": nome, "soma_bu": v_bu, "oficial": v_of,
                           "diferenca": v_bu - v_of, "ok": ok})
        linhas.append({"uf": uf, "item": "info_agregadas/sem_bu", "soma_bu": bu[1],
                       "oficial": bu[2], "diferenca": 0, "ok": True})
    return linhas, ok_geral


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--ufs", default="",
                    help="UFs separadas por vírgula (padrão: todas as presentes nos dados)")
    ap.add_argument("--base", default=str(PARQUET_2026_DIR),
                    help="diretório com os Parquet de 2026 (padrão: data/parquet/2026)")
    ap.add_argument("--so-divergencias", action="store_true",
                    help="mostra apenas as linhas com diferença")
    a = ap.parse_args()
    ufs = [u.strip().lower() for u in a.ufs.split(",") if u.strip()] or None
    linhas, ok = reconciliar(Path(a.base), ufs)
    print(f"{'uf':<3} {'item':<24} {'soma_bu':>12} {'oficial':>12} {'dif':>8}  ok")
    for r in linhas:
        if a.so_divergencias and r["ok"]:
            continue
        print(f"{r['uf']:<3} {r['item']:<24} {r['soma_bu']:>12} {r['oficial']:>12} "
              f"{r['diferenca']:>8}  {'sim' if r['ok'] else 'NÃO'}")
    print("RESULTADO:", "reconciliado" if ok else "DIVERGENTE")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
