#!/usr/bin/env python3
"""Baixa e decodifica o BU de cada seção (Presidente, 1º turno de 2026).

Fluxo por seção, sem gravar arquivo bruto em disco:
  aux.json -> escolhe hash -> baixa -bu.dat (e -vota.vsc se --modelo)
  -> decodifica com o parser do projeto (pool de processos) -> linhas.

As linhas são gravadas em lotes (partes Parquet ZSTD) em
data/parquet/2026/secoes_parts/ e cada lote gravado e anotado no checkpoint
(secoes_checkpoint.txt). Ao rodar de novo, seções já anotadas são puladas.
No final as partes são consolidadas (com deduplicação) em
secoes_2026.parquet e votos_presidente_2026.parquet.

Uso:
  python3 scripts/ele2026/fetch_secoes.py --ufs ac          # teste
  python3 scripts/ele2026/fetch_secoes.py                    # todas (27 + zz)
  python3 scripts/ele2026/fetch_secoes.py --so-consolidar
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[2]
SRC = str(ROOT / "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import pyarrow as pa  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from dataurnas.config import ESTADOS, PARQUET_2026_DIR  # noqa: E402
from dataurnas.downloader import ele2026 as E  # noqa: E402

log = logging.getLogger("fetch_secoes")

TODAS_UFS = ESTADOS + ["zz"]

SECOES_SCHEMA = pa.schema([
    ("uf", pa.string()), ("cd_mun", pa.string()), ("nm_mun", pa.string()),
    ("zona", pa.string()), ("secao", pa.string()),
    ("status", pa.string()),  # ok | agregada | nao_instalada | sem_aux | sem_bu
    ("origem_bu", pa.string()),  # bu (urna) | busa (Sistema de Apuração)
    ("secao_principal", pa.string()), ("secoes_agregadas", pa.string()),
    ("st_secao", pa.string()), ("hash", pa.string()), ("st_hash", pa.string()),
    ("n_hashes", pa.int16()),
    ("dt_recebimento", pa.string()), ("hr_recebimento", pa.string()),
    ("spec_version", pa.string()),
    ("municipio_bu", pa.int32()), ("zona_bu", pa.int32()), ("secao_bu", pa.int32()),
    ("local_votacao", pa.int32()),
    ("data_hora_emissao", pa.string()), ("hora_abertura", pa.string()),
    ("hora_encerramento", pa.string()),
    ("tipo_urna", pa.string()), ("versao_votacao", pa.string()),
    ("numero_interno_urna", pa.int64()), ("codigo_carga", pa.string()),
    ("qtd_codigos_carga", pa.int16()), ("fase", pa.string()),
    ("modelo_urna_cod", pa.int16()), ("modelo_urna", pa.string()),
    ("aptos", pa.int32()), ("aptos_secao", pa.int32()), ("aptos_tte", pa.int32()),
    ("comparecimento", pa.int32()), ("comparecimento_bu", pa.int32()),
    ("comp_sem_biometria", pa.int32()), ("habilitados_biometria", pa.int32()),
    ("habilitados_biografia", pa.int32()),
    ("votos_nominais", pa.int32()), ("votos_legenda", pa.int32()),
    ("votos_brancos", pa.int32()), ("votos_nulos", pa.int32()),
    ("votos_total", pa.int32()), ("tem_presidente", pa.bool_()),
    ("_lote", pa.string()),
])

VOTOS_SCHEMA = pa.schema([
    ("uf", pa.string()), ("cd_mun", pa.string()), ("zona", pa.string()),
    ("secao", pa.string()), ("tipo_voto", pa.string()), ("numero", pa.int32()),
    ("partido", pa.int32()), ("votos", pa.int32()), ("_lote", pa.string()),
])


def _init_worker(src: str) -> None:
    if src not in sys.path:
        sys.path.insert(0, src)


class Writer:
    """Acumula linhas e grava partes Parquet + checkpoint."""

    def __init__(self, out: Path, lote: int):
        self.parts = out / "secoes_parts"
        self.parts.mkdir(parents=True, exist_ok=True)
        self.ckpt = out / "secoes_checkpoint.txt"
        self.lote = lote
        self.secoes: list[dict] = []
        self.votos: list[dict] = []
        self.keys: list[str] = []
        self.n_part = 0
        self.prefix = time.strftime("%Y%m%d%H%M%S") + f"-{os.getpid()}"

    def done_keys(self) -> set[str]:
        if not self.ckpt.exists():
            return set()
        with open(self.ckpt, encoding="utf-8") as fh:
            return {ln.strip() for ln in fh if ln.strip()}

    def add(self, key: str, sec: dict, votos: list[dict]) -> None:
        self.secoes.append(sec)
        self.votos.extend(votos)
        self.keys.append(key)
        if len(self.keys) >= self.lote:
            self.flush()

    def flush(self) -> None:
        if not self.keys:
            return
        self.n_part += 1
        lote = f"{self.prefix}-{self.n_part:05d}"
        for r in self.secoes:
            r["_lote"] = lote
        for r in self.votos:
            r["_lote"] = lote
        for nome, rows, schema in (("secoes", self.secoes, SECOES_SCHEMA),
                                   ("votos", self.votos, VOTOS_SCHEMA)):
            t = pa.Table.from_pylist(rows, schema=schema)
            dst = self.parts / f"{nome}-{lote}.parquet"
            tmp = dst.with_suffix(".tmp")
            pq.write_table(t, tmp, compression="zstd")
            tmp.replace(dst)
        with open(self.ckpt, "a", encoding="utf-8") as fh:
            fh.write("\n".join(self.keys) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        log.info("lote %s gravado: %d seções, %d votos", lote, len(self.keys), len(self.votos))
        self.secoes, self.votos, self.keys = [], [], []


async def processar_secao(f: E.HttpFetcher, pool: ProcessPoolExecutor,
                          s: dict, modelo: bool) -> tuple[dict, list[dict]]:
    uf, mun, zona, secao = s["uf"], s["cd_mun"], s["zona"], s["secao"]
    row = dict(s)
    if s.get("secao_principal"):
        row["status"] = "agregada"
        return row, []
    aux = await f.get_json(E.url_aux(uf, mun, zona, secao))
    if not aux:
        row["status"] = "sem_aux"
        return row, []
    h = E.escolher_hash(aux)
    row["st_secao"] = aux.get("st")
    arqs = h["arquivos"] if h else {}
    # BU da urna (-bu.dat) ou, na falta, BU do Sistema de Apuração (-busa.dat)
    tp_bu = "bu" if "bu" in arqs else ("busa" if "busa" in arqs else None)
    tp_vsc = "vota" if "vota" in arqs else ("sa" if "sa" in arqs else None)
    if not h or not tp_bu:
        st = str(aux.get("st", "")).lower()
        row["status"] = "nao_instalada" if "instalada" in st and "nao" in st else "sem_bu"
        return row, []
    row.update({k: h[k] for k in ("hash", "st_hash", "n_hashes",
                                   "dt_recebimento", "hr_recebimento")})
    row["origem_bu"] = tp_bu
    bu_task = f.get(E.url_arquivo(uf, mun, zona, secao, h["hash"], arqs[tp_bu]))
    vsc_task = None
    if modelo and tp_vsc:
        vsc_task = f.get(E.url_arquivo(uf, mun, zona, secao, h["hash"], arqs[tp_vsc]))
    raw_bu = await bu_task
    raw_vsc = await vsc_task if vsc_task else None
    if raw_bu is None:
        row["status"] = "sem_bu"
        return row, []
    loop = asyncio.get_running_loop()
    sec, votos = await loop.run_in_executor(pool, E.bu_to_rows, raw_bu)
    del raw_bu
    row.update(sec)
    if raw_vsc:
        cod = E.modelo_from_vsc(raw_vsc)
        row["modelo_urna_cod"] = cod
        row["modelo_urna"] = E.MODELOS.get(cod, f"Modelo_{cod}") if cod else None
    row["status"] = "ok"
    ident = {"uf": uf, "cd_mun": mun, "zona": zona, "secao": secao}
    return row, [{**ident, **v} for v in votos]


async def run(args: argparse.Namespace) -> int:
    out = Path(args.saida)
    out.mkdir(parents=True, exist_ok=True)
    w = Writer(out, args.lote)
    done = w.done_keys()
    log.info("checkpoint: %d seções já processadas", len(done))
    f = E.HttpFetcher(concurrency=args.concorrencia, http2=args.http2,
                      connections=args.conexoes,
                      rate=args.taxa, rate_max=args.taxa_max)
    pool = ProcessPoolExecutor(max_workers=args.workers, initializer=_init_worker,
                               initargs=(SRC,))
    erros: list[str] = []
    t0 = time.time()
    n_ok = 0
    try:
        for uf in args.ufs:
            cs = await f.get_json(E.url_secoes_uf(uf))
            if not cs:
                log.error("sem lista de seções para %s", uf)
                erros.append(f"{uf}:sem_cs")
                continue
            secoes = [s for s in E.iter_secoes_cs(cs)
                      if E.secao_key(s["uf"], s["cd_mun"], s["zona"], s["secao"]) not in done]
            log.info("UF %s: %d seções pendentes", uf, len(secoes))
            q: asyncio.Queue = asyncio.Queue()
            for s in secoes:
                q.put_nowait(s)
            t_uf = time.time()
            n_uf = 0

            async def worker():
                nonlocal n_uf, n_ok
                while True:
                    try:
                        s = q.get_nowait()
                    except asyncio.QueueEmpty:
                        return
                    key = E.secao_key(s["uf"], s["cd_mun"], s["zona"], s["secao"])
                    try:
                        row, votos = await processar_secao(f, pool, s, args.modelo)
                    except Exception as e:  # noqa: BLE001 - registrado e refeito no próximo run
                        erros.append(f"{key}:{e!r}"[:300])
                        log.warning("erro em %s: %r", key, e)
                        continue
                    w.add(key, row, votos)
                    n_uf += 1
                    n_ok += 1
                    if n_ok % 2000 == 0:
                        el = time.time() - t0
                        log.info("progresso: %d seções em %.0fs (%.1f/s) | taxa %s | http %s",
                                 n_ok, el, n_ok / el, f.rate_info(), f.stats)

            await asyncio.gather(*[worker() for _ in range(args.concorrencia)])
            w.flush()
            el = time.time() - t_uf
            log.info("UF %s concluída: %d seções em %.0fs (%.1f/s)", uf, n_uf, el,
                     n_uf / el if el else 0)
    finally:
        w.flush()
        await f.close()
        pool.shutdown(wait=True)
    el = time.time() - t0
    log.info("fim: %d seções em %.0fs (%.1f/s), %d erros, taxa final %s, http %s",
             n_ok, el, n_ok / el if el else 0, len(erros), f.rate_info(), f.stats)
    if erros:
        (out / "secoes_erros.txt").write_text("\n".join(erros) + "\n", encoding="utf-8")
        log.warning("erros gravados em secoes_erros.txt; rode de novo para refazer")
    if not args.sem_consolidar:
        consolidar(out)
    return 0 if not erros else 2


def consolidar(out: Path) -> None:
    """Junta as partes em dois Parquet finais, mantendo o lote mais recente
    de cada seção (protege contra duplicatas de execuções interrompidas)."""
    import duckdb

    parts = out / "secoes_parts"
    if not any(parts.glob("secoes-*.parquet")):
        log.warning("nenhuma parte para consolidar")
        return
    con = duckdb.connect()
    sp = str(parts / "secoes-*.parquet")
    vp = str(parts / "votos-*.parquet")
    con.execute(f"""
        CREATE TEMP TABLE s AS
        SELECT * FROM read_parquet('{sp}', union_by_name = true)
        QUALIFY row_number() OVER (PARTITION BY uf, cd_mun, zona, secao ORDER BY _lote DESC) = 1
    """)
    dst_s = out / "secoes_2026.parquet"
    dst_v = out / "votos_presidente_2026.parquet"
    con.execute(f"""COPY (SELECT * EXCLUDE (_lote) FROM s ORDER BY uf, cd_mun, zona, secao)
                    TO '{dst_s}.tmp' (FORMAT PARQUET, COMPRESSION ZSTD)""")
    con.execute(f"""COPY (
        SELECT v.* EXCLUDE (_lote) FROM read_parquet('{vp}', union_by_name = true) v
        JOIN s USING (uf, cd_mun, zona, secao, _lote)
        ORDER BY uf, cd_mun, zona, secao, numero) TO '{dst_v}.tmp'
        (FORMAT PARQUET, COMPRESSION ZSTD)""")
    os.replace(f"{dst_s}.tmp", dst_s)
    os.replace(f"{dst_v}.tmp", dst_v)
    ns = con.execute(f"SELECT count(*) FROM read_parquet('{dst_s}')").fetchone()[0]
    nv = con.execute(f"SELECT count(*) FROM read_parquet('{dst_v}')").fetchone()[0]
    log.info("consolidado: %s (%d linhas), %s (%d linhas)", dst_s.name, ns, dst_v.name, nv)


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ufs", default=",".join(TODAS_UFS),
                    help="lista de UFs separadas por vírgula (padrão: 27 UFs + zz)")
    ap.add_argument("--concorrencia", type=int, default=96,
                    help="seções processadas em paralelo (padrão: 96)")
    ap.add_argument("--workers", type=int, default=max(2, (os.cpu_count() or 4) // 2),
                    help="processos que decodificam os BUs (padrão: metade dos núcleos, mínimo 2)")
    ap.add_argument("--lote", type=int, default=5000,
                    help="seções por parte Parquet gravada e anotada no checkpoint (padrão: 5000)")
    ap.add_argument("--modelo", action=argparse.BooleanOptionalAction, default=True,
                    help="baixa o -vota.vsc (~60 KB) para extrair o modelo da urna (padrão: ativado)")
    ap.add_argument("--http2", action=argparse.BooleanOptionalAction, default=True,
                    help="usa HTTP/2 (padrão: ativado); HTTP/1.1 (--no-http2) foi bem mais lento nos testes")
    ap.add_argument("--taxa", type=float, default=50.0,
                    help="taxa inicial em req/s, reduzida automaticamente em HTTP 429 (padrão: 50)")
    ap.add_argument("--taxa-max", type=float, default=90.0,
                    help="teto da taxa adaptativa, em req/s (padrão: 90)")
    ap.add_argument("--conexoes", type=int, default=4,
                    help="clientes HTTP/2 em rodízio (cada um com janela de fluxo própria; padrão: 4)")
    ap.add_argument("--saida", default=str(PARQUET_2026_DIR),
                    help="diretório de saída das partes e dos Parquet finais (padrão: data/parquet/2026)")
    ap.add_argument("--sem-consolidar", action="store_true",
                    help="não consolida as partes ao final da coleta")
    ap.add_argument("--so-consolidar", action="store_true",
                    help="apenas consolida as partes já gravadas, sem baixar nada")
    a = ap.parse_args(argv)
    a.ufs = [u.strip().lower() for u in a.ufs.split(",") if u.strip()]
    return a


if __name__ == "__main__":
    args = parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    if args.so_consolidar:
        consolidar(Path(args.saida))
        sys.exit(0)
    sys.exit(asyncio.run(run(args)))
