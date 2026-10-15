#!/usr/bin/env python3
"""Auditoria de integridade dos arquivos de urna (Presidente, 2026, 1º ou 2º turno).

Para cada seção com arquivos, sem gravar arquivo bruto em disco:
  aux.json -> todos os conjuntos (hashes) -> baixa cada arquivo listado
  -> tamanho, MD5, SHA-256, SHA-512 -> compara o SHA-512 com o hash assinado
  no .vsc -> verifica a assinatura de hardware do .vsc (Ed521 ou ECDSA P-521)
  -> opcionalmente confere os votos do BU com votos_presidente_2026.parquet.

Saída em data/parquet/2026/integridade/:
  arquivos_<uf>.parquet  uma linha por arquivo (UF grande é dividida em
                         arquivos_<uf>_parteN.parquet para ficar abaixo de 90 MB)
  secoes.parquet         uma linha por seção
  resumo.json            totais, contagens por UF, divergências e execuções
  divergencias.jsonl     gravado na hora em que cada divergência aparece

Com --analisar (padrão), roda também sobre o BU e o log em memória a mesma
auditoria por seção de 2022 (BatchAnalyzer) e grava em data/parquet/2026/auditoria/:
  issues_2026.parquet      secao_id, codigo, severidade, descricao, base_legal, detalhes
  secoes_log_2026.parquet  colunas da tabela secoes de 2022 (horários, reinícios,
                           erros e alertas do log, votos no log, biometria, fuso)

Intermediários (fora do git): parts/, checkpoint.txt, erros-*.txt, execucoes.jsonl.
Vários processos podem rodar ao mesmo tempo com UFs disjuntas (--ufs): cada
um grava partes com prefixo próprio e o checkpoint e o JSONL são só append.
Falha de rede ou HTTP vai para erros.txt e a seção é refeita no próximo run;
não é divergência. Exceção: arquivo listado no aux.json que responde 404 e não
é o .vsc nem o BU/log do SA (imgbu, imgbusa e afins, ou bu/rdv/log da urna) não
derruba a seção: vira linha com disponivel False e http_status 404, uma linha
"PUBLICACAO" no log e, se for arquivo assinado no .vsc, a divergência
arquivo_ausente_tse. A seção segue verificada e entra no checkpoint.

Com --turno 2 (pleito 3221, eleição 6258, 25/10/2026) os caminhos padrão passam
a data/parquet/2026/t2/ (integridade/, auditoria/ e os Parquet de votos de
fetch_secoes.py --turno 2), o log padrão a data/ele2026_t2_integridade.log e o
secao_id da auditoria usa o prefixo "2T/" no lugar de "1T/".

Uso:
  python3 scripts/ele2026/fetch_integridade.py --ufs ac,rr     # teste
  python3 scripts/ele2026/fetch_integridade.py                 # 27 UFs + zz
  python3 scripts/ele2026/fetch_integridade.py --so-consolidar
  python3 scripts/ele2026/fetch_integridade.py --turno 2 --ufs ac,rr
"""

from __future__ import annotations

import argparse
import asyncio
import json
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

from dataurnas.analyzer import integrity as I  # noqa: E402
from dataurnas.config import ESTADOS  # noqa: E402
from dataurnas.downloader import ele2026 as E  # noqa: E402

log = logging.getLogger("fetch_integridade")

TODAS_UFS = ESTADOS + ["zz"]
LIMITE_BYTES = 90 * 1024 * 1024
ALVO_PARTE = 80 * 1024 * 1024

ARQUIVOS_SCHEMA = pa.schema([
    ("uf", pa.string()), ("cd_mun", pa.string()), ("zona", pa.string()),
    ("secao", pa.string()), ("tipo", pa.string()), ("nome", pa.string()),
    ("tamanho", pa.int64()), ("md5", pa.string()), ("sha256", pa.string()),
    ("sha512", pa.string()), ("sha512_assinado", pa.string()),
    ("hash_confere", pa.bool_()), ("token_tse", pa.string()),
    ("data_hora_tse", pa.string()), ("disponivel", pa.bool_()),
    ("http_status", pa.int32()), ("_lote", pa.string()),
])

ISSUES_SCHEMA = pa.schema([
    ("secao_id", pa.string()), ("codigo", pa.string()), ("severidade", pa.string()),
    ("descricao", pa.string()), ("base_legal", pa.string()), ("detalhes", pa.string()),
    ("_lote", pa.string()),
])

# Mesmas colunas da tabela secoes de 2022 (id -> secao_id), mais cd_mun,
# tem_log e origem_bu.
SECOES_LOG_SCHEMA = pa.schema([
    ("secao_id", pa.string()), ("turno", pa.int32()), ("uf", pa.string()),
    ("regiao", pa.string()), ("municipio", pa.string()), ("cd_mun", pa.string()),
    ("zona", pa.string()), ("secao", pa.string()), ("modelo_urna", pa.string()),
    ("tipo_urna", pa.string()), ("versao_sw", pa.string()), ("fuso_offset", pa.int32()),
    ("emissao", pa.string()), ("eleitores_aptos", pa.int32()),
    ("comparecimento", pa.int32()), ("lib_codigo", pa.int32()),
    ("comp_biometrico", pa.int32()), ("pct_biometria", pa.float64()),
    ("pct_abstencao", pa.float64()), ("hora_abertura", pa.string()),
    ("hora_encerramento", pa.string()), ("duracao_min", pa.int32()),
    ("reboots", pa.int32()), ("erros_log", pa.int32()), ("alertas_mesario", pa.int32()),
    ("votos_log", pa.int32()), ("substituicoes", pa.int32()), ("is_reserva", pa.bool_()),
    ("has_issues", pa.bool_()), ("n_issues", pa.int32()), ("tem_log", pa.bool_()),
    ("origem_bu", pa.string()), ("_lote", pa.string()),
])

SECOES_SCHEMA = pa.schema([
    ("uf", pa.string()), ("cd_mun", pa.string()), ("zona", pa.string()),
    ("secao", pa.string()), ("status_secao", pa.string()),
    ("n_arquivos", pa.int32()), ("n_hash_confere", pa.int32()),
    ("n_hash_diverge", pa.int32()), ("n_sem_hash", pa.int32()),
    ("assinatura_valida", pa.bool_()), ("assinatura_algoritmo", pa.string()),
    ("cert_subject", pa.string()), ("cert_issuer", pa.string()),
    ("cert_serial", pa.string()), ("cert_sha256", pa.string()),
    ("modelo_urna", pa.string()), ("motivo", pa.string()),
    ("votos_conferem", pa.bool_()), ("n_indisponiveis", pa.int32()),
    ("_lote", pa.string()),
])


# 404 nestes arquivos derruba a seção (refeita no próximo run): sem o .vsc não
# há verificação, e o BU/log do SA são a alternativa ao BU/log da urna.
TIPOS_404_REFAZ = {"vota", "sa", "busa", "logsa"}


def refaz_em_404(tp: str, nome: str) -> bool:
    """True se o 404 deste arquivo deve derrubar a seção (erro HTTP refeito)."""
    return (tp or "").lower() in TIPOS_404_REFAZ or I.eh_assinatura(tp, nome)


def _init_worker(src: str) -> None:
    if src not in sys.path:
        sys.path.insert(0, src)


def token_tse(hash_hex: str) -> str:
    """Token base64url do TSE (o diretório do conjunto é o hex desse token)."""
    try:
        return bytes.fromhex(hash_hex).decode("ascii")
    except (ValueError, UnicodeDecodeError):
        return hash_hex


class Divergencias:
    """Grava cada divergência na hora (JSONL com fsync) e no log."""

    def __init__(self, path: Path):
        self.path = path
        self.n = 0

    def registrar(self, d: dict) -> None:
        d = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), **d}
        linha = json.dumps(d, ensure_ascii=False, sort_keys=False)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(linha + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        self.n += 1
        log.warning("DIVERGENCIA %s", linha)


class Writer:
    """Acumula linhas e grava partes Parquet + checkpoint."""

    def __init__(self, out: Path, lote: int):
        self.parts = out / "parts"
        self.parts.mkdir(parents=True, exist_ok=True)
        self.ckpt = out / "checkpoint.txt"
        self.lote = lote
        self.arquivos: list[dict] = []
        self.secoes: list[dict] = []
        self.issues: list[dict] = []
        self.secoes_log: list[dict] = []
        self.keys: list[str] = []
        self.n_part = 0
        self.prefix = time.strftime("%Y%m%d%H%M%S") + f"-{os.getpid()}"

    def done_keys(self) -> set[str]:
        if not self.ckpt.exists():
            return set()
        with open(self.ckpt, encoding="utf-8") as fh:
            return {ln.strip() for ln in fh if ln.strip()}

    def add(self, key: str, sec: dict, arquivos: list[dict],
            secao_log: Optional[dict] = None, issues: Optional[list] = None) -> None:
        self.secoes.append(sec)
        self.arquivos.extend(arquivos)
        if secao_log is not None:
            self.secoes_log.append(secao_log)
        for i in issues or []:
            self.issues.append(dict(zip(
                ("secao_id", "codigo", "severidade", "descricao", "base_legal", "detalhes"),
                i, strict=True)))
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
        for rows in (self.arquivos, self.issues, self.secoes_log):
            for r in rows:
                r["_lote"] = lote
        for nome, rows, schema in (("secoes", self.secoes, SECOES_SCHEMA),
                                   ("arquivos", self.arquivos, ARQUIVOS_SCHEMA),
                                   ("issues", self.issues, ISSUES_SCHEMA),
                                   ("seclog", self.secoes_log, SECOES_LOG_SCHEMA)):
            t = pa.Table.from_pylist(rows, schema=schema)
            dst = self.parts / f"{nome}-{lote}.parquet"
            tmp = dst.with_suffix(".tmp")
            pq.write_table(t, tmp, compression="zstd")
            tmp.replace(dst)
        with open(self.ckpt, "a", encoding="utf-8") as fh:
            fh.write("\n".join(self.keys) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        log.info("lote %s gravado: %d seções, %d arquivos", lote, len(self.keys),
                 len(self.arquivos))
        self.secoes, self.arquivos, self.keys = [], [], []
        self.issues, self.secoes_log = [], []


def votos_esperados_uf(uf: str, base: Path) -> tuple[set[str], dict[str, tuple]]:
    """Seções 'ok' da coleta anterior e seus votos, normalizados como no BU."""
    import duckdb

    sp = base / "secoes_2026.parquet"
    vp = base / "votos_presidente_2026.parquet"
    if not sp.exists() or not vp.exists():
        return set(), {}
    con = duckdb.connect()
    ok = {f"{u}/{m}/{z}/{s}" for u, m, z, s in con.execute(
        f"SELECT uf, cd_mun, zona, secao FROM read_parquet('{sp}') "
        "WHERE uf = ? AND status = 'ok'", [uf]).fetchall()}
    votos: dict[str, list] = {}
    for u, m, z, s, tv, n, q in con.execute(
            f"SELECT uf, cd_mun, zona, secao, tipo_voto, numero, votos "
            f"FROM read_parquet('{vp}') WHERE uf = ?", [uf]).fetchall():
        votos.setdefault(f"{u}/{m}/{z}/{s}", []).append((tv, n or 0, q or 0))
    con.close()
    return ok, {k: tuple(sorted(v)) for k, v in votos.items()}


async def processar_secao(f: E.HttpFetcher, pool: ProcessPoolExecutor, s: dict,
                          esperado: Optional[tuple], analisar: bool = True,
                          p: Optional[dict] = None) -> dict:
    p = p or E.parametros_turno(1)
    url = {"pleito": p["pleito"], "ciclo": p["ciclo"]}
    uf, mun, zona, secao = s["uf"], s["cd_mun"], s["zona"], s["secao"]
    ident = {"uf": uf, "cd_mun": mun, "zona": zona, "secao": secao}
    vazio = {"n_arquivos": 0, "n_hash_confere": 0, "n_hash_diverge": 0, "n_sem_hash": 0,
             "n_indisponiveis": 0}
    if s.get("secao_principal"):
        return {"linhas": [], "divergencias": [], "secao": {
            **ident, **vazio, "status_secao": "agregada",
            "motivo": f"agregada à seção {s['secao_principal']}"}}
    aux = await f.get_json(E.url_aux(uf, mun, zona, secao, **url))
    if not aux:
        return {"linhas": [], "divergencias": [], "secao": {
            **ident, **vazio, "status_secao": "sem_arquivos",
            "motivo": "aux.json não publicado (404)"}}
    hashes = [h for h in (aux.get("hashes") or []) if h.get("hash") and h["hash"] != "0"]
    if not hashes:
        st = str(aux.get("st", "")).lower()
        status = "nao_instalada" if "instalada" in st and "nao" in st.replace("ã", "a") \
            else "sem_arquivos"
        return {"linhas": [], "divergencias": [], "secao": {
            **ident, **vazio, "status_secao": status, "motivo": f"aux.json: st={aux.get('st')}"}}
    escolha = E.escolher_hash(aux)
    escolhido = next((i for i, h in enumerate(hashes) if h["hash"] == escolha["hash"]),
                     len(hashes) - 1)
    pedidos = []
    for h in hashes:
        for a in h.get("arq") or []:
            if isinstance(a, dict) and a.get("nm"):
                pedidos.append((h["hash"], a.get("tp", ""), a["nm"]))
    corpos = await asyncio.gather(*[
        f.get(E.url_arquivo(uf, mun, zona, secao, hh, nm, **url))
        for hh, _tp, nm in pedidos])
    faltando = [(tp, nm) for (_h, tp, nm), b in zip(pedidos, corpos, strict=True)
                if b is None]
    refaz = [nm for tp, nm in faltando if refaz_em_404(tp, nm)]
    if refaz:
        # 404 no .vsc ou no BU/log do SA: tratado como erro HTTP (refeito no
        # próximo run), nunca como divergência.
        raise RuntimeError(f"HTTP 404 em arquivo listado no aux.json: {','.join(refaz)}")
    for _tp, nm in faltando:
        # demais arquivos: a seção segue; a falha fica registrada na linha do
        # arquivo (disponivel False) e no log, para registrar_ocorrencias_publicacao.py
        log.warning("PUBLICACAO %s/%s/%s/%s: HTTP 404 em arquivo listado no aux.json: %s",
                    uf, mun, zona, secao, nm)
    conjuntos = []
    for h in hashes:
        arqs = [(tp, nm, b) for (hh, tp, nm), b in zip(pedidos, corpos, strict=True)
                if hh == h["hash"]]
        conjuntos.append({"token": token_tse(h["hash"]),
                          "data_hora": f"{h.get('dr', '')} {h.get('hr', '')}".strip(),
                          "arquivos": arqs})
    del corpos
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(pool, I.auditar_secao, ident, conjuntos,
                                      escolhido, esperado, analisar, p["turno"])


def registrar_execucao(out: Path, evento: dict) -> None:
    """Uma linha JSON por evento (append: vários processos podem rodar juntos)."""
    with open(out / "execucoes.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(evento, ensure_ascii=False) + "\n")


async def run(args: argparse.Namespace) -> int:
    p = E.parametros_turno(args.turno)
    out = Path(args.saida)
    out.mkdir(parents=True, exist_ok=True)
    w = Writer(out, args.lote)
    divs = Divergencias(out / "divergencias.jsonl")
    done = w.done_keys()
    inicio = time.strftime("%Y-%m-%dT%H:%M:%S")
    registrar_execucao(out, {"inicio": inicio, "ufs": args.ufs, "pid": os.getpid()})
    log.info("checkpoint: %d seções já processadas", len(done))
    log.info("turno %d: pleito %s, eleição %s, saída %s", p["turno"], p["pleito"],
             p["eleicao"], out)
    f = E.HttpFetcher(concurrency=args.concorrencia, http2=args.http2,
                      connections=args.conexoes, rate=args.taxa, rate_max=args.taxa_max)
    pool = ProcessPoolExecutor(max_workers=args.workers, initializer=_init_worker,
                               initargs=(SRC,))
    erros: list[str] = []
    t0 = time.time()
    n_ok = 0
    try:
        for uf in args.ufs:
            cs = await f.get_json(E.url_secoes_uf(uf, pleito=p["pleito"], ciclo=p["ciclo"]))
            if not cs:
                log.error("sem lista de seções para %s", uf)
                erros.append(f"{uf}:sem_cs")
                continue
            secoes = [s for s in E.iter_secoes_cs(cs)
                      if E.secao_key(s["uf"], s["cd_mun"], s["zona"], s["secao"]) not in done]
            ok_keys, votos = (votos_esperados_uf(uf, Path(args.base_votos))
                              if args.conferir_votos else (set(), {}))
            log.info("UF %s: %d seções pendentes (%d com votos para conferir)",
                     uf, len(secoes), len(ok_keys))
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
                    esperado = votos.get(key, ()) if key in ok_keys else None
                    try:
                        r = await processar_secao(f, pool, s, esperado, args.analisar, p)
                    except Exception as e:  # noqa: BLE001 - registrado e refeito no próximo run
                        erros.append(f"{key}:{e!r}"[:300])
                        log.warning("erro em %s: %r", key, e)
                        continue
                    for d in r["divergencias"]:
                        divs.registrar(d)
                    w.add(key, r["secao"], r["linhas"], r.get("secao_log"),
                          r.get("issues"))
                    n_uf += 1
                    n_ok += 1
                    if n_ok % 2000 == 0:
                        el = time.time() - t0
                        log.info("progresso: %d seções em %.0fs (%.2f/s) | %d divergências | "
                                 "taxa %s | http %s", n_ok, el, n_ok / el, divs.n,
                                 f.rate_info(), f.stats)

            await asyncio.gather(*[worker() for _ in range(args.concorrencia)])
            w.flush()
            el = time.time() - t_uf
            log.info("UF %s concluída: %d seções em %.0fs (%.2f/s)", uf, n_uf, el,
                     n_uf / el if el else 0)
    finally:
        w.flush()
        await f.close()
        pool.shutdown(wait=True)
        el = time.time() - t0
        registrar_execucao(out, {"inicio": inicio, "fim": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                 "secoes": n_ok, "segundos": round(el), "erros": len(erros),
                                 "divergencias": divs.n, "http": dict(f.stats)})
    log.info("fim: %d seções em %.0fs (%.2f/s), %d erros, %d divergências, taxa final %s, "
             "http %s", n_ok, el, n_ok / el if el else 0, len(erros), divs.n,
             f.rate_info(), f.stats)
    if erros:
        dst = out / f"erros-{w.prefix}.txt"
        dst.write_text("\n".join(erros) + "\n", encoding="utf-8")
        log.warning("erros gravados em %s; rode de novo para refazer", dst.name)
    if not args.sem_consolidar:
        consolidar(out, Path(args.saida_auditoria), args.turno)
    return 0 if not erros else 2


def _escrever_uf(con, uf: str, out: Path) -> list[str]:
    """Grava arquivos_<uf>.parquet; divide em partes se passar de 90 MB."""
    for p in out.glob(f"arquivos_{uf}*.parquet"):
        p.unlink()
    dst = out / f"arquivos_{uf}.parquet"
    sel = (f"SELECT * EXCLUDE (_lote) FROM a WHERE uf = '{uf}' "
           "ORDER BY cd_mun, zona, secao, data_hora_tse, nome")
    con.execute(f"COPY ({sel}) TO '{dst}.tmp' (FORMAT PARQUET, COMPRESSION ZSTD)")
    tam = os.path.getsize(f"{dst}.tmp")
    if tam <= LIMITE_BYTES:
        os.replace(f"{dst}.tmp", dst)
        return [dst.name]
    os.remove(f"{dst}.tmp")
    n = con.execute(f"SELECT count(*) FROM a WHERE uf = '{uf}'").fetchone()[0]
    partes = -(-tam // ALVO_PARTE)
    por = -(-n // partes)
    nomes = []
    for i in range(partes):
        p = out / f"arquivos_{uf}_parte{i + 1}.parquet"
        con.execute(f"COPY ({sel} LIMIT {por} OFFSET {i * por}) TO '{p}' "
                    "(FORMAT PARQUET, COMPRESSION ZSTD)")
        nomes.append(p.name)
    log.info("arquivos_%s dividido em %d partes (%d MB no total)", uf, partes, tam >> 20)
    return nomes


def consolidar_auditoria(con, out: Path, dst_dir: Path, prefixo_id: str = "1T/") -> dict:
    """issues_2026.parquet e secoes_log_2026.parquet (lote mais recente de
    cada seção, mesmo critério de secoes.parquet).

    prefixo_id: '1T/' ou '2T/', o mesmo de make_secao_id no turno coletado."""
    parts = out / "parts"
    if not any(parts.glob("seclog-*.parquet")):
        return {}
    dst_dir.mkdir(parents=True, exist_ok=True)
    con.execute("""CREATE OR REPLACE TEMP TABLE sid AS
        SELECT ? || uf || '/' || cd_mun || '/' || zona || '/' || secao AS secao_id, _lote
        FROM s""", [prefixo_id])
    dl = dst_dir / "secoes_log_2026.parquet"
    con.execute(f"""COPY (
        SELECT x.* EXCLUDE (_lote)
        FROM read_parquet('{parts / "seclog-*.parquet"}', union_by_name = true) x
        JOIN sid USING (secao_id, _lote) ORDER BY uf, cd_mun, zona, secao)
        TO '{dl}.tmp' (FORMAT PARQUET, COMPRESSION ZSTD)""")
    os.replace(f"{dl}.tmp", dl)
    di = dst_dir / "issues_2026.parquet"
    if any(parts.glob("issues-*.parquet")):
        con.execute(f"""COPY (
            SELECT x.* EXCLUDE (_lote)
            FROM read_parquet('{parts / "issues-*.parquet"}', union_by_name = true) x
            JOIN sid USING (secao_id, _lote) ORDER BY secao_id, codigo)
            TO '{di}.tmp' (FORMAT PARQUET, COMPRESSION ZSTD)""")
        os.replace(f"{di}.tmp", di)
    for p in (dl, di):
        if p.exists() and p.stat().st_size > LIMITE_BYTES:
            log.error("%s passou de 90 MB (%d MB)", p.name, p.stat().st_size >> 20)
    n_log = con.execute(f"SELECT count(*) FROM read_parquet('{dl}')").fetchone()[0]
    por_codigo = {}
    if di.exists():
        por_codigo = {c: int(n) for c, n in con.execute(
            f"SELECT codigo, count(*) FROM read_parquet('{di}') GROUP BY 1 ORDER BY 1"
        ).fetchall()}
    log.info("auditoria: %s (%d seções), %s (%d issues)", dl.name, n_log, di.name,
             sum(por_codigo.values()))
    return {"secoes_log": int(n_log), "issues_por_codigo": por_codigo}


def consolidar(out: Path, dst_auditoria: Optional[Path] = None, turno: int = 1) -> None:
    """Junta as partes (mantendo o lote mais recente de cada seção) nos
    Parquet finais e grava resumo.json."""
    import duckdb

    p = E.parametros_turno(turno)

    parts = out / "parts"
    if not any(parts.glob("secoes-*.parquet")):
        log.warning("nenhuma parte para consolidar")
        return
    con = duckdb.connect()
    con.execute(f"""
        CREATE TEMP TABLE s AS
        SELECT * FROM read_parquet('{parts / "secoes-*.parquet"}', union_by_name = true)
        QUALIFY row_number() OVER (PARTITION BY uf, cd_mun, zona, secao ORDER BY _lote DESC) = 1
    """)
    con.execute(f"""
        CREATE TEMP TABLE a AS
        SELECT x.* FROM read_parquet('{parts / "arquivos-*.parquet"}', union_by_name = true) x
        JOIN s USING (uf, cd_mun, zona, secao, _lote)
    """)
    # partes gravadas antes das colunas de disponibilidade: todo arquivo
    # listado foi baixado (o 404 derrubava a seção)
    for tbl, col, tipo, padrao in (("s", "n_indisponiveis", "INTEGER", "0"),
                                   ("a", "disponivel", "BOOLEAN", "true"),
                                   ("a", "http_status", "INTEGER", "200")):
        if col not in {r[0] for r in con.execute(f"DESCRIBE {tbl}").fetchall()}:
            con.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} {tipo}")
        con.execute(f"UPDATE {tbl} SET {col} = {padrao} WHERE {col} IS NULL")
    dst_s = out / "secoes.parquet"
    con.execute(f"""COPY (SELECT * EXCLUDE (_lote) FROM s ORDER BY uf, cd_mun, zona, secao)
                    TO '{dst_s}.tmp' (FORMAT PARQUET, COMPRESSION ZSTD)""")
    os.replace(f"{dst_s}.tmp", dst_s)
    auditoria = consolidar_auditoria(
        con, out, dst_auditoria or (out.parent / "auditoria"), p["prefixo_id"])
    ufs = [r[0] for r in con.execute("SELECT DISTINCT uf FROM s ORDER BY uf").fetchall()]
    arquivos_parquet = []
    for uf in ufs:
        arquivos_parquet.extend(_escrever_uf(con, uf, out))

    por_uf = {}
    for row in con.execute("""
        SELECT uf, count(*) secoes,
               count(*) FILTER (WHERE status_secao = 'ok') ok,
               count(*) FILTER (WHERE status_secao = 'agregada') agregada,
               count(*) FILTER (WHERE status_secao = 'nao_instalada') nao_instalada,
               count(*) FILTER (WHERE status_secao = 'sem_arquivos') sem_arquivos,
               coalesce(sum(n_arquivos), 0), coalesce(sum(n_hash_confere), 0),
               coalesce(sum(n_hash_diverge), 0), coalesce(sum(n_sem_hash), 0),
               count(*) FILTER (WHERE assinatura_valida),
               count(*) FILTER (WHERE NOT assinatura_valida),
               count(*) FILTER (WHERE status_secao = 'ok' AND assinatura_valida IS NULL),
               count(*) FILTER (WHERE votos_conferem),
               count(*) FILTER (WHERE NOT votos_conferem),
               coalesce(sum(n_indisponiveis), 0),
               count(*) FILTER (WHERE n_indisponiveis > 0)
        FROM s GROUP BY uf ORDER BY uf""").fetchall():
        por_uf[row[0]] = dict(zip(
            ["secoes", "ok", "agregada", "nao_instalada", "sem_arquivos", "arquivos",
             "hash_confere", "hash_diverge", "sem_hash", "assinatura_valida",
             "assinatura_invalida", "assinatura_nao_verificada", "votos_conferem",
             "votos_divergem", "arquivos_indisponiveis", "secoes_com_indisponiveis"],
            [int(x) for x in row[1:]], strict=True))
    totais = {k: sum(v[k] for v in por_uf.values()) for k in next(iter(por_uf.values()))}
    por_tipo = {t: {"arquivos": int(n), "bytes": int(b or 0), "indisponiveis": int(i)}
                for t, n, b, i in con.execute(
        "SELECT tipo, count(*), sum(tamanho), count(*) FILTER (WHERE NOT disponivel) "
        "FROM a GROUP BY tipo ORDER BY tipo").fetchall()}
    indisponiveis_por_tipo = {t: v["indisponiveis"] for t, v in por_tipo.items()
                              if v["indisponiveis"]}
    algoritmos = {str(k): int(n) for k, n in con.execute(
        "SELECT assinatura_algoritmo, count(*) FROM s WHERE status_secao = 'ok' "
        "GROUP BY 1 ORDER BY 2 DESC").fetchall()}
    modelos = {str(k): int(n) for k, n in con.execute(
        "SELECT modelo_urna, count(*) FROM s WHERE status_secao = 'ok' "
        "GROUP BY 1 ORDER BY 1").fetchall()}

    divergencias = []
    jp = out / "divergencias.jsonl"
    if jp.exists():
        vistos = set()
        for ln in jp.read_text(encoding="utf-8").splitlines():
            if not ln.strip():
                continue
            d = json.loads(ln)
            k = (d.get("uf"), d.get("cd_mun"), d.get("zona"), d.get("secao"),
                 d.get("arquivo"), d.get("categoria"), d.get("token_tse"))
            if k not in vistos:
                vistos.add(k)
                divergencias.append(d)
    por_categoria = {c: sum(1 for d in divergencias if d.get("categoria") == c)
                     for c in I.CATEGORIAS_DIVERGENCIA}
    execucoes = []
    ep = out / "execucoes.jsonl"
    if ep.exists():
        execucoes = [json.loads(ln) for ln in ep.read_text(encoding="utf-8").splitlines()
                     if ln.strip()]
    # seções com erro em algum run que ainda não foram concluídas
    feitas = Writer(out, 1).done_keys()
    pendentes = set()
    for ep_ in out.glob("erros-*.txt"):
        for ln in ep_.read_text(encoding="utf-8").splitlines():
            k = ln.split(":", 1)[0].strip()
            if k.count("/") == 3 and k not in feitas:
                pendentes.add(k)
    erros_pend = len(pendentes)
    resumo = {
        "gerado_em": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "pleito": p["pleito"], "ciclo": p["ciclo"],
        "metodo": {
            "hash_arquivo": "SHA-512 do arquivo publicado comparado ao hash da lista "
                            "de arquivos assinados no .vsc (partes SW e HW).",
            "assinatura_hw": "Ed521 (ICP-Brasil, SHAKE256, dom5 'SigEd521', contexto "
                             "vazio) ou ECDSA P-521 com SHA-512; a mensagem assinada é "
                             "SHA-512(hash), em que hash = SHA-512 do conteúdo. "
                             "Verificados o autoAssinado (lista inteira) e cada "
                             "arquivo publicado.",
            "assinatura_sw": "CEPESC (algoritmo de governo não publicado): não verificada.",
            "cadeia_certificado": "não validada: os certificados das AC emissoras "
                                  "(AC URNA, AC UE2022) não vêm nos arquivos e a LCR "
                                  "pública responde 403; registramos subject, issuer, "
                                  "serial e SHA-256 do certificado da urna.",
            "token_tse": "token base64url de 32 bytes do aux.json; não corresponde ao "
                         "hash de nenhum arquivo isolado publicado e não é verificado.",
        },
        "totais": totais,
        "por_uf": por_uf,
        "por_tipo_arquivo": por_tipo,
        "arquivos_indisponiveis": {
            "total": sum(indisponiveis_por_tipo.values()),
            "por_tipo": indisponiveis_por_tipo,
            "descricao": "arquivos listados no aux.json que o servidor do TSE responde "
                         "com HTTP 404 (disponivel = false em arquivos_<uf>.parquet)",
        },
        "algoritmos_assinatura": algoritmos,
        "modelos_urna": modelos,
        "arquivos_parquet": arquivos_parquet,
        "n_divergencias": len(divergencias),
        "divergencias_por_categoria": por_categoria,
        "divergencias": divergencias,
        "erros_pendentes": erros_pend,
        "auditoria_bu_log": auditoria,
        "execucoes": execucoes,
    }
    (out / "resumo.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    log.info("consolidado: secoes.parquet (%d seções), %d arquivos Parquet por UF, "
             "%d divergências", totais["secoes"], len(arquivos_parquet), len(divergencias))


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--turno", type=int, choices=E.TURNOS, default=1,
                    help="turno da eleição: 1 (pleito 3220) ou 2 (pleito 3221); padrão: 1")
    ap.add_argument("--ufs", default=",".join(TODAS_UFS),
                    help="lista de UFs separadas por vírgula (padrão: 27 UFs + zz)")
    ap.add_argument("--concorrencia", type=int, default=96,
                    help="seções processadas em paralelo (padrão: 96)")
    ap.add_argument("--workers", type=int, default=max(2, (os.cpu_count() or 4) // 2),
                    help="processos de hash e verificação (padrão: metade dos núcleos)")
    ap.add_argument("--lote", type=int, default=2000,
                    help="seções por parte Parquet gravada e anotada no checkpoint")
    ap.add_argument("--conferir-votos", action=argparse.BooleanOptionalAction, default=True,
                    help="confere os votos do BU com votos_presidente_2026.parquet")
    ap.add_argument("--base-votos", default=None,
                    help="diretório com secoes_2026.parquet e votos_presidente_2026.parquet "
                         "(padrão: data/parquet/2026 ou data/parquet/2026/t2)")
    ap.add_argument("--analisar", action=argparse.BooleanOptionalAction, default=True,
                    help="roda a auditoria por seção de 2022 (BU e log) e grava "
                         "data/parquet/2026[/t2]/auditoria/ (padrão: ativado)")
    ap.add_argument("--saida-auditoria", default=None,
                    help="diretório de issues_2026.parquet e secoes_log_2026.parquet "
                         "(padrão: data/parquet/2026[/t2]/auditoria)")
    ap.add_argument("--http2", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--taxa", type=float, default=50.0,
                    help="taxa inicial em req/s, reduzida automaticamente em HTTP 429")
    ap.add_argument("--taxa-max", type=float, default=90.0, help="teto da taxa adaptativa")
    ap.add_argument("--conexoes", type=int, default=4,
                    help="clientes HTTP/2 em rodízio (padrão: 4)")
    ap.add_argument("--saida", default=None,
                    help="diretório de saída (padrão: data/parquet/2026/integridade no "
                         "1º turno, data/parquet/2026/t2/integridade no 2º)")
    ap.add_argument("--log", default=None,
                    help="arquivo de log (padrão: data/ele2026_integridade.log no 1º "
                         "turno, data/ele2026_t2_integridade.log no 2º)")
    ap.add_argument("--sem-consolidar", action="store_true")
    ap.add_argument("--so-consolidar", action="store_true")
    a = ap.parse_args(argv)
    p = E.parametros_turno(a.turno)
    if a.base_votos is None:
        a.base_votos = str(p["saida"])
    if a.saida is None:
        a.saida = str(p["saida"] / "integridade")
    if a.saida_auditoria is None:
        a.saida_auditoria = str(p["saida"] / "auditoria")
    if a.log is None:
        a.log = str(ROOT / "data" / f"{p['prefixo_log']}integridade.log")
    a.ufs = [u.strip().lower() for u in a.ufs.split(",") if u.strip()]
    return a


def configurar_log(path: str) -> None:
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    raiz = logging.getLogger()
    raiz.setLevel(logging.INFO)
    fh = logging.FileHandler(path, encoding="utf-8")
    fh.setFormatter(fmt)
    raiz.addHandler(fh)
    if sys.stderr.isatty():
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        raiz.addHandler(sh)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


if __name__ == "__main__":
    args = parse_args()
    configurar_log(args.log)
    if args.so_consolidar:
        consolidar(Path(args.saida), Path(args.saida_auditoria), args.turno)
        sys.exit(0)
    sys.exit(asyncio.run(run(args)))
