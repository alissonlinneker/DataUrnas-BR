#!/usr/bin/env python3
"""Marca o banco de 2022 como "hashes verificados" depois da auditoria completa.

O painel só apresenta a integridade de hash como avaliada quando a tabela
``metadados`` do DuckDB traz ``verify_hashes = true`` (ver
``dashboard/analysis.py::hash_verification_status``). Para a base distribuída
em Parquet, ``scripts/build_db.py`` lê esse valor de ``data/parquet/metadados.parquet``.

Este script lê ``data/parquet/2022/integridade/resumo.json`` (gerado por
``scripts/ele2022/fetch_integridade.py``) e só marca a base como verificada se
a auditoria estiver completa: os 56 pacotes (2 turnos x 27 UFs + exterior)
processados, nenhum erro pendente e todas as seções do banco de 2022 cobertas.

Sem ``--gravar`` apenas mostra o que seria gravado. Com ``--gravar``:
  - grava ``data/parquet/metadados.parquet`` (chave/valor), lido pelo build_db;
  - com ``--db``, atualiza também a tabela ``metadados`` de um DuckDB existente.

Divergências de hash (``hash_diverge``) não impedem a marcação, porque a
verificação foi executada; elas são listadas e precisam virar issues C01 na
base para o painel exibi-las (o script avisa e devolve código 3).

Uso:
  python3 scripts/ele2022/registrar_metadados_integridade.py            # simulação
  python3 scripts/ele2022/registrar_metadados_integridade.py --gravar
  python3 scripts/ele2022/registrar_metadados_integridade.py --gravar --db data/db/eleicoes_2022.duckdb
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = str(ROOT / "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from dataurnas.config import PARQUET_DIR  # noqa: E402
from dataurnas.database import metadados as M  # noqa: E402

RESUMO = PARQUET_DIR / "2022" / "integridade" / "resumo.json"
ORIGEM = "integridade_2022_dados_abertos"


def secoes_banco(base: Path) -> int | None:
    sp = base / "secoes.parquet"
    if not sp.exists():
        return None
    import pyarrow.parquet as pq

    return pq.ParquetFile(sp).metadata.num_rows


def avaliar(resumo: dict, n_banco: int | None) -> tuple[bool, list[str]]:
    """(pode_marcar, pendências) a partir do resumo da auditoria."""
    pend = []
    if not resumo.get("completo"):
        pend.append(f"auditoria incompleta: {resumo.get('pacotes_processados')} de "
                    f"{resumo.get('pacotes_esperados')} pacotes processados")
    if resumo.get("erros_pendentes"):
        pend.append(f"{resumo['erros_pendentes']} seções com erro pendente (rode de novo)")
    t = resumo.get("totais") or {}
    no_banco = (t.get("secoes", 0) or 0) - (t.get("fora_do_banco", 0) or 0)
    if n_banco is not None and no_banco < n_banco:
        pend.append(f"seções do banco cobertas: {no_banco} de {n_banco}")
    return not pend, pend


def valores(resumo: dict) -> dict[str, str]:
    t = resumo.get("totais") or {}
    cat = resumo.get("divergencias_por_categoria") or {}
    return {
        M.CHAVE_VERIFY_HASHES: "true",
        M.CHAVE_ORIGEM: ORIGEM,
        M.CHAVE_ATUALIZADO_EM: datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "integridade_resumo": "data/parquet/2022/integridade/resumo.json",
        "integridade_gerado_em": str(resumo.get("gerado_em")),
        "integridade_secoes": str(t.get("secoes")),
        "integridade_arquivos": str(t.get("arquivos")),
        "integridade_hash_confere": str(t.get("hash_confere")),
        "integridade_hash_diverge": str(cat.get("hash_diverge", 0)),
        "integridade_assinatura_invalida": str(cat.get("assinatura_invalida", 0)),
        "integridade_n_divergencias": str(resumo.get("n_divergencias", 0)),
    }


def gravar_parquet(vals: dict[str, str], dst: Path) -> None:
    """Upsert em metadados.parquet, preservando chaves que já existam."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    atual: dict[str, str] = {}
    if dst.exists():
        t = pq.read_table(dst)
        atual = dict(zip(t.column("chave").to_pylist(), t.column("valor").to_pylist(),
                         strict=True))
    atual.update(vals)
    tab = pa.table({"chave": list(atual), "valor": list(atual.values())})
    tmp = dst.with_suffix(".tmp")
    pq.write_table(tab, tmp)
    tmp.replace(dst)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--resumo", default=str(RESUMO))
    ap.add_argument("--base", default=str(PARQUET_DIR),
                    help="diretório com secoes.parquet de 2022 e onde fica metadados.parquet")
    ap.add_argument("--db", default=None, help="DuckDB de 2022 a atualizar também")
    ap.add_argument("--gravar", action="store_true", help="grava (sem isso, só simula)")
    a = ap.parse_args(argv)
    rp = Path(a.resumo)
    if not rp.exists():
        print(f"resumo não encontrado: {rp}")
        return 1
    resumo = json.loads(rp.read_text(encoding="utf-8"))
    ok, pend = avaliar(resumo, secoes_banco(Path(a.base)))
    vals = valores(resumo)
    print(json.dumps(vals, ensure_ascii=False, indent=1))
    if not ok:
        print("NÃO marcado como verificado:")
        for p in pend:
            print(f"  - {p}")
        return 1
    if not a.gravar:
        print("simulação: use --gravar para gravar")
        return 0
    gravar_parquet(vals, Path(a.base) / "metadados.parquet")
    print(f"gravado: {Path(a.base) / 'metadados.parquet'}")
    if a.db:
        import duckdb

        con = duckdb.connect(a.db)
        M.gravar_metadados(con, vals)
        con.close()
        print(f"gravado na tabela metadados de {a.db}")
    if int(vals["integridade_hash_diverge"]) or int(vals["integridade_assinatura_invalida"]):
        print("ATENÇÃO: há divergências de hash ou de assinatura; gere as issues C01 "
              "correspondentes antes de publicar o painel")
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
