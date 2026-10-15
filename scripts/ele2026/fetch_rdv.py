#!/usr/bin/env python3
"""Recontagem do RDV e linha do tempo do log (Presidente, 1º turno de 2026).

Para cada seção com RDV publicado, sem gravar arquivo bruto em disco:
  catálogo de integridade (ou aux.json) -> baixa -rdv.dat, -bu.dat e -log.jez
  do mesmo conjunto -> confere o SHA-512 com o catálogo (que já foi conferido
  com o hash assinado no .vsc) -> recontagem do RDV por cargo x BU -> votos
  computados no log x comparecimento do BU, minuto a minuto.

Saída em data/parquet/2026/rdv/ (ZSTD, cada arquivo < 90 MB):
  recontagem_secoes.parquet  uma linha por seção e cargo (RDV x BU)
  log_tempo_secoes.parquet   métricas de horário por seção e flags
  resumo.json                totais, por UF, por cargo, Presidente nacional,
                             histograma de intervalos, grupos de leitura
  divergencias.jsonl         cada divergência do RDV, gravada na hora (fsync)

Com --auditar (padrão), o mesmo download regera a auditoria por seção de BU e
log (mesmas regras e esquema da auditoria publicada, com o log lido também do
.jez aninhado da urna substituída) em data/parquet/2026/auditoria_v2/:
  secoes_log_2026.parquet, issues_2026.parquet e comparacao.json (diferenças
  por coluna e por código em relação a data/parquet/2026/auditoria/).

Divergência RDV x BU também vai para o log (data/ele2026_rdv.log) numa linha
que começa com "DIVERGENCIA_RDV ". O run não para.

Intermediários (fora do git): parts/, checkpoint.txt, erros-*.txt,
execucoes.jsonl. Falha de rede vai para erros-*.txt e a seção é refeita no
próximo run.

Lista de seções: por padrão o catálogo de integridade publicado na versão
(arquivos_<uf>.parquet, anexos do GitHub, lidos em memória) dá o nome, o
token do diretório e o SHA-512 de cada arquivo, sem pedir o aux.json.
Com --fonte aux, percorre o -cs.json e o aux.json como fetch_integridade.py.

Uso:
  python3 scripts/ele2026/fetch_rdv.py --ufs ac,rr     # teste
  python3 scripts/ele2026/fetch_rdv.py                 # 27 UFs + zz
  python3 scripts/ele2026/fetch_rdv.py --so-consolidar
  python3 scripts/ele2026/fetch_rdv.py --secoes lista.txt  # reprocessa só a lista

Com --secoes, refaz as seções listadas (uma chave uf/cd_mun/zona/secao por
linha) mesmo que já estejam no checkpoint, só nas UFs da lista. O checkpoint
só recebe linhas novas e as partes antigas ficam; a consolidação usa o lote
mais recente de cada seção.
"""

from __future__ import annotations

import argparse
import asyncio
import io
import json
import logging
import os
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[2]
SRC = str(ROOT / "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import pyarrow as pa  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from dataurnas.analyzer import rdv_recontagem as R  # noqa: E402
from dataurnas.config import ESTADOS, PARQUET_2026_DIR  # noqa: E402
from dataurnas.downloader import ele2026 as E  # noqa: E402


def _carregar_fetch_integridade_2026():
    """Carrega scripts/ele2026/fetch_integridade.py pelo caminho.

    Há outro fetch_integridade.py em scripts/ele2022; importar pelo nome curto
    pegaria o que estiver primeiro em sys.modules.
    """
    import importlib.util

    nome = "ele2026_fetch_integridade"
    if nome in sys.modules:
        return sys.modules[nome]
    spec = importlib.util.spec_from_file_location(nome, Path(__file__).resolve().parent / "fetch_integridade.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[nome] = mod
    spec.loader.exec_module(mod)
    return mod


_FI = _carregar_fetch_integridade_2026()
ISSUES_SCHEMA, SECOES_LOG_SCHEMA = _FI.ISSUES_SCHEMA, _FI.SECOES_LOG_SCHEMA

log = logging.getLogger("fetch_rdv")

TODAS_UFS = ESTADOS + ["zz"]
LIMITE_BYTES = 90 * 1024 * 1024
ALVO_PARTE = 80 * 1024 * 1024
DATA_ELEICAO = "04/10/2026"
TIPOS = ("rdv", "bu", "busa", "log", "logsa")
CATEGORIAS_ALERTA = {"rdv_bu_diverge", "rdv_bu_diverge_sa", "rdv_registros_diverge",
                     "rdv_estrutura", "rdv_hash_diverge", "rdv_nao_decodificado"}
MANIFESTO = PARQUET_2026_DIR / "integridade" / "catalogo_manifest.json"

IDENT = [("uf", pa.string()), ("cd_mun", pa.string()), ("zona", pa.string()),
         ("secao", pa.string())]
RECONTAGEM_SCHEMA = pa.schema(IDENT + [
    ("id_eleicao", pa.int32()), ("cargo", pa.string()), ("codigo_cargo", pa.int16()),
    ("qtd_escolhas", pa.int16()), ("registros_rdv", pa.int32()),
    ("comparecimento_bu", pa.int32()), ("votos_rdv", pa.int32()), ("votos_bu", pa.int32()),
    ("nominais_rdv", pa.int32()), ("nominais_bu", pa.int32()),
    ("legenda_rdv", pa.int32()), ("legenda_bu", pa.int32()),
    ("brancos_rdv", pa.int32()), ("brancos_bu", pa.int32()),
    ("nulos_rdv", pa.int32()), ("nulos_bu", pa.int32()), ("n_votaveis", pa.int32()),
    ("confere", pa.bool_()), ("detalhes", pa.string()), ("_lote", pa.string()),
])
TEMPO_SCHEMA = pa.schema(IDENT + [
    ("fuso_offset", pa.int8()), ("comparecimento_bu", pa.int32()), ("votos_log", pa.int32()),
    ("diferenca_log_bu", pa.int32()), ("votos_outras_datas", pa.int32()),
    ("n_urnas_log", pa.int16()), ("aberturas", pa.int16()), ("hora_pronta", pa.string()),
    ("hora_encerramento", pa.string()), ("primeiro_voto", pa.string()),
    ("ultimo_voto", pa.string()), ("votos_antes_8h", pa.int32()),
    ("votos_apos_17h", pa.int32()), ("votos_antes_pronta", pa.int32()),
    ("votos_apos_encerramento", pa.int32()), ("max_votos_minuto", pa.int16()),
    ("minuto_pico", pa.string()), ("intervalo_min_s", pa.int32()),
    ("intervalo_mediana_s", pa.int32()), ("intervalos_lt_10s", pa.int32()),
    ("intervalos_lt_5s", pa.int32()), ("maior_lacuna_min", pa.float32()),
    ("lacunas_60min", pa.int16()), ("inversoes_relogio", pa.int32()),
    ("ajustes_hora", pa.int16()), ("hist_intervalos", pa.list_(pa.int32())),
    ("flags", pa.list_(pa.string())), ("grupo", pa.int8()), ("origem_log", pa.string()),
    ("_lote", pa.string()),
])
SECOES_SCHEMA = pa.schema(IDENT + [
    ("status", pa.string()), ("motivo", pa.string()), ("hash_confere", pa.bool_()),
    ("comparecimento_bu", pa.int32()), ("origem_bu", pa.string()), ("n_cargos", pa.int16()),
    ("registros_rdv", pa.int32()), ("tipo_arquivo_rdv", pa.string()),
    ("tipo_urna_rdv", pa.string()), ("origem_rdv", pa.string()),
    ("estrutura_ok", pa.bool_()), ("rdv_confere", pa.bool_()), ("_lote", pa.string()),
])
PRESIDENTE_SCHEMA = pa.schema(IDENT + [
    ("chave", pa.string()), ("votos", pa.int32()), ("_lote", pa.string())])
ACHADOS_SCHEMA = pa.schema(IDENT + [
    ("categoria", pa.string()), ("grupo", pa.int8()), ("cargo", pa.string()),
    ("detalhes", pa.string()), ("_lote", pa.string())])


def _init_worker(src: str) -> None:
    if src not in sys.path:
        sys.path.insert(0, src)


class Divergencias:
    """Grava cada divergência do RDV na hora (JSONL com fsync) e no log."""

    def __init__(self, path: Path):
        self.path = path
        self.n = 0

    def registrar(self, d: dict) -> None:
        d = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), **d}
        linha = json.dumps(d, ensure_ascii=False, default=str)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(linha + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        self.n += 1
        log.warning("DIVERGENCIA_RDV %s", linha)


def prefixo_lote(parts: Path, agora: float) -> str:
    """Prefixo aaaammddhhmmss do lote, sempre maior que o de qualquer parte já
    gravada.

    A consolidação fica com o lote de maior nome de cada seção. Se o relógio
    ou o fuso do processo mudar entre execuções, a hora local pode sair menor
    que a de lotes antigos e a seção refeita perderia para a versão velha;
    nesse caso o prefixo passa a ser o maior existente + 1 s.
    """
    import datetime as dt

    atual = time.strftime("%Y%m%d%H%M%S", time.localtime(agora))
    existentes = [p.name.split("-")[1] for p in parts.glob("secoes-*.parquet")
                  if len(p.name.split("-")) > 2 and p.name.split("-")[1].isdigit()]
    maior = max(existentes, default="")
    if len(maior) == 14 and maior >= atual:
        prox = dt.datetime.strptime(maior, "%Y%m%d%H%M%S") + dt.timedelta(seconds=1)
        return prox.strftime("%Y%m%d%H%M%S")
    return atual


class Writer:
    """Acumula linhas e grava partes Parquet + checkpoint."""

    TABELAS = (("recontagem", RECONTAGEM_SCHEMA), ("tempo", TEMPO_SCHEMA),
               ("secoes", SECOES_SCHEMA), ("presidente", PRESIDENTE_SCHEMA),
               ("achados", ACHADOS_SCHEMA), ("seclog", SECOES_LOG_SCHEMA),
               ("issues", ISSUES_SCHEMA))

    def __init__(self, out: Path, lote: int):
        self.parts = out / "parts"
        self.parts.mkdir(parents=True, exist_ok=True)
        self.ckpt = out / "checkpoint.txt"
        self.lote = lote
        self.rows: dict[str, list[dict]] = {n: [] for n, _ in self.TABELAS}
        self.keys: list[str] = []
        self.n_part = 0
        self.prefix = prefixo_lote(self.parts, time.time()) + f"-{os.getpid()}"

    def done_keys(self) -> set[str]:
        if not self.ckpt.exists():
            return set()
        with open(self.ckpt, encoding="utf-8") as fh:
            return {ln.strip() for ln in fh if ln.strip()}

    def add(self, key: str, r: dict) -> None:
        ident = {k: r["secao"][k] for k in ("uf", "cd_mun", "zona", "secao")}
        self.rows["secoes"].append(r["secao"])
        self.rows["recontagem"].extend(r["linhas"])
        if r.get("tempo"):
            self.rows["tempo"].append(r["tempo"])
        for chave, v in r["presidente"].items():
            self.rows["presidente"].append({**ident, "chave": chave, "votos": v})
        for a in r["achados"]:
            det = {k: v for k, v in a.items()
                   if k not in ("uf", "cd_mun", "zona", "secao", "categoria", "grupo", "cargo")}
            self.rows["achados"].append({
                **ident, "categoria": a["categoria"], "grupo": a["grupo"],
                "cargo": a.get("cargo"),
                "detalhes": json.dumps(det, ensure_ascii=False, default=str)})
        if r.get("secao_log") is not None:
            self.rows["seclog"].append(r["secao_log"])
        for i in r.get("issues") or []:
            self.rows["issues"].append(dict(zip(
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
        for nome, schema in self.TABELAS:
            rows = self.rows[nome]
            for r in rows:
                r["_lote"] = lote
            t = pa.Table.from_pylist(rows, schema=schema)
            dst = self.parts / f"{nome}-{lote}.parquet"
            tmp = dst.with_suffix(".tmp")
            pq.write_table(t, tmp, compression="zstd")
            tmp.replace(dst)
        with open(self.ckpt, "a", encoding="utf-8") as fh:
            fh.write("\n".join(self.keys) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        log.info("lote %s gravado: %d seções, %d linhas de recontagem", lote,
                 len(self.keys), len(self.rows["recontagem"]))
        self.rows = {n: [] for n, _ in self.TABELAS}
        self.keys = []


# ---------------------------------------------------------------------------
# Lista de seções
# ---------------------------------------------------------------------------

def _ordem_data(dh: Optional[str]) -> str:
    """'04/10/2026 18:34:08' -> '20261004 18:34:08' (ordenável)."""
    if not dh or len(dh) < 10:
        return ""
    return f"{dh[6:10]}{dh[3:5]}{dh[0:2]}{dh[10:]}"


def secoes_do_catalogo(tabela: pa.Table) -> list[dict]:
    """Agrupa o catálogo de integridade por seção e escolhe o conjunto com RDV
    (o mais recente, se houver mais de um). Seção sem RDV publicado entra com
    arquivos sem 'rdv' e vira status sem_rdv."""
    cols = tabela.to_pydict()
    por_secao: dict[tuple, dict[str, dict]] = defaultdict(lambda: defaultdict(dict))
    datas: dict[tuple, dict[str, str]] = defaultdict(dict)
    for i in range(tabela.num_rows):
        tp = (cols["tipo"][i] or "").lower()
        if tp not in TIPOS:
            continue
        if cols.get("disponivel") and cols["disponivel"][i] is False:
            continue
        k = (cols["uf"][i], cols["cd_mun"][i], cols["zona"][i], cols["secao"][i])
        tok = cols["token_tse"][i]
        por_secao[k][tok][tp] = (cols["nome"][i], cols["sha512"][i])
        datas[k][tok] = _ordem_data(cols["data_hora_tse"][i])
    out = []
    for k, conjuntos in por_secao.items():
        com_rdv = [t for t, a in conjuntos.items() if "rdv" in a]
        cand = com_rdv or list(conjuntos)
        tok = max(cand, key=lambda t: datas[k].get(t, ""))
        out.append({"uf": k[0], "cd_mun": k[1], "zona": k[2], "secao": k[3],
                    "hash": tok.encode("ascii").hex(), "arquivos": dict(conjuntos[tok]),
                    "n_conjuntos": len(conjuntos)})
    out.sort(key=lambda s: (s["cd_mun"], s["zona"], s["secao"]))
    return out


async def carregar_catalogo(f: E.HttpFetcher, uf: str, manifesto: dict,
                            dir_local: Optional[Path]) -> Optional[list[dict]]:
    """Lê arquivos_<uf>*.parquet (local, se existir, ou anexo da versão) em memória."""
    colunas = ["uf", "cd_mun", "zona", "secao", "tipo", "nome", "sha512", "token_tse",
               "data_hora_tse", "disponivel"]
    tabelas = []
    nomes = [a["arquivo"] for a in manifesto.get("arquivos", []) if a.get("uf") == uf]
    for nome in nomes:
        local = dir_local / nome if dir_local else None
        if local and local.exists():
            tabelas.append(pq.read_table(local, columns=colunas))
            continue
        corpo = await f.get(f"{manifesto['url_base']}/{nome}")
        if corpo is None:
            return None
        tabelas.append(pq.read_table(io.BytesIO(corpo), columns=colunas))
    if not tabelas:
        return None
    return secoes_do_catalogo(pa.concat_tables(tabelas))


async def secoes_do_aux(f: E.HttpFetcher, uf: str) -> list[dict]:
    """Alternativa sem catálogo: -cs.json + aux.json de cada seção."""
    cs = await f.get_json(E.url_secoes_uf(uf))
    out = []
    for s in E.iter_secoes_cs(cs or {}):
        if s.get("secao_principal"):
            continue
        out.append({**{k: s[k] for k in ("uf", "cd_mun", "zona", "secao")},
                    "hash": None, "arquivos": None, "n_conjuntos": None})
    return out


async def resolver_aux(f: E.HttpFetcher, s: dict) -> Optional[dict]:
    aux = await f.get_json(E.url_aux(s["uf"], s["cd_mun"], s["zona"], s["secao"]))
    hashes = [h for h in ((aux or {}).get("hashes") or []) if h.get("hash") not in (None, "0")]
    if not hashes:
        return None
    conj = [h for h in hashes if any(a.get("tp") == "rdv" for a in h.get("arq") or [])]
    h = (conj or hashes)[-1]
    arqs = {a["tp"]: (a["nm"], None) for a in h.get("arq") or []
            if isinstance(a, dict) and a.get("tp") in TIPOS}
    return {**s, "hash": h["hash"], "arquivos": arqs, "n_conjuntos": len(hashes)}


# ---------------------------------------------------------------------------
# Processamento
# ---------------------------------------------------------------------------

def modelos_uf(uf: str, secoes_integridade: Path) -> dict[str, int]:
    """Código do modelo da urna por seção (lido do .vsc na auditoria de integridade)."""
    from dataurnas.config import MODELOS_URNA

    if not secoes_integridade.exists():
        return {}
    cod = {v: k for k, v in MODELOS_URNA.items()}
    t = pq.read_table(secoes_integridade, columns=["uf", "cd_mun", "zona", "secao",
                                                   "modelo_urna"],
                      filters=[("uf", "=", uf)]).to_pydict()
    return {E.secao_key(u, m, z, s): cod[mo]
            for u, m, z, s, mo in zip(t["uf"], t["cd_mun"], t["zona"], t["secao"],
                                      t["modelo_urna"], strict=True) if mo in cod}


async def processar(f: E.HttpFetcher, pool: ProcessPoolExecutor, s: dict,
                    auditar: bool = False, modelo_cod: Optional[int] = None) -> dict:
    ident = {k: s[k] for k in ("uf", "cd_mun", "zona", "secao")}
    if s["arquivos"] is None:
        s = await resolver_aux(f, s)
        if s is None:
            return {"secao": {**ident, "status": "sem_arquivos", "motivo": "aux.json sem conjunto"},
                    "linhas": [], "tempo": None, "achados": [], "presidente": {}}
    tps = [tp for tp in TIPOS if tp in s["arquivos"]]
    if "log" in tps and "logsa" in tps:
        tps.remove("logsa")  # como na auditoria publicada: log da urna, senão o do SA
    corpos = await asyncio.gather(*[
        f.get(E.url_arquivo(s["uf"], s["cd_mun"], s["zona"], s["secao"], s["hash"],
                            s["arquivos"][tp][0])) for tp in tps])
    faltando = [s["arquivos"][tp][0] for tp, b in zip(tps, corpos, strict=True) if b is None]
    if faltando:
        raise RuntimeError(f"HTTP 404: {','.join(faltando)}")
    arquivos = {tp: (s["arquivos"][tp][0], b) for tp, b in zip(tps, corpos, strict=True)}
    sha = {tp: s["arquivos"][tp][1] for tp in tps if s["arquivos"][tp][1]}
    del corpos
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(pool, R.processar_secao, ident, arquivos, sha or None,
                                      int(E.PLEITO), DATA_ELEICAO, auditar, modelo_cod)


def ler_lista_secoes(path: Path) -> set[str]:
    """Chaves uf/cd_mun/zona/secao de um arquivo (uma por linha; # comenta)."""
    out = set()
    for ln in Path(path).read_text(encoding="utf-8").splitlines():
        ln = ln.split("#", 1)[0].strip().lower()
        if not ln:
            continue
        if ln.count("/") != 3:
            raise ValueError(f"chave de seção inválida em {path}: {ln!r}")
        out.add(ln)
    return out


def registrar_execucao(out: Path, evento: dict) -> None:
    with open(out / "execucoes.jsonl", "a", encoding="utf-8") as fh:
        fh.write(json.dumps(evento, ensure_ascii=False) + "\n")


async def run(args: argparse.Namespace) -> int:
    out = Path(args.saida)
    out.mkdir(parents=True, exist_ok=True)
    w = Writer(out, args.lote)
    divs = Divergencias(out / "divergencias.jsonl")
    done = w.done_keys()
    refazer = ler_lista_secoes(Path(args.secoes)) if args.secoes else None
    ufs = args.ufs
    if refazer is not None:
        ufs = [u for u in args.ufs if any(k.startswith(f"{u}/") for k in refazer)]
        log.info("--secoes: %d seções a refazer em %d UFs", len(refazer), len(ufs))
    inicio = time.strftime("%Y-%m-%dT%H:%M:%S")
    registrar_execucao(out, {"inicio": inicio, "ufs": ufs, "pid": os.getpid(),
                             "lista_secoes": Path(args.secoes).name if args.secoes else None, "n_refazer": len(refazer or ()),
                             "fonte": args.fonte, "taxa": args.taxa, "taxa_max": args.taxa_max,
                             "workers": args.workers})
    log.info("checkpoint: %d seções já processadas", len(done))
    f = E.HttpFetcher(concurrency=args.concorrencia, http2=args.http2,
                      connections=args.conexoes, rate=args.taxa, rate_max=args.taxa_max)
    pool = ProcessPoolExecutor(max_workers=args.workers, initializer=_init_worker,
                               initargs=(SRC,))
    manifesto = json.loads(Path(args.manifesto).read_text(encoding="utf-8")) \
        if args.fonte == "catalogo" else {}
    dir_local = Path(args.catalogo_local) if args.catalogo_local else None
    erros: list[str] = []
    t0 = time.time()
    n_ok = 0
    try:
        for uf in ufs:
            if args.fonte == "catalogo":
                secoes = await carregar_catalogo(f, uf, manifesto, dir_local)
                if secoes is None:
                    log.error("catálogo de %s indisponível; usando aux.json", uf)
                    secoes = await secoes_do_aux(f, uf)
            else:
                secoes = await secoes_do_aux(f, uf)
            if refazer is not None:
                secoes = [s for s in secoes
                          if E.secao_key(s["uf"], s["cd_mun"], s["zona"], s["secao"]) in refazer]
            else:
                secoes = [s for s in secoes
                          if E.secao_key(s["uf"], s["cd_mun"], s["zona"], s["secao"]) not in done]
            modelos = (modelos_uf(uf, Path(args.secoes_integridade))
                       if args.auditar else {})
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
                        r = await processar(f, pool, s, args.auditar, modelos.get(key))
                    except Exception as e:  # noqa: BLE001 - refeito no próximo run
                        erros.append(f"{key}:{e!r}"[:300])
                        log.warning("erro em %s: %r", key, e)
                        continue
                    for a in r["achados"]:
                        if a["categoria"] in CATEGORIAS_ALERTA:
                            divs.registrar(a)
                    w.add(key, r)
                    n_uf += 1
                    n_ok += 1
                    if n_ok % 2000 == 0:
                        el = time.time() - t0
                        log.info("progresso: %d seções em %.0fs (%.2f/s) | %d divergências RDV "
                                 "| taxa %s | http %s", n_ok, el, n_ok / el, divs.n,
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
                                 "divergencias_rdv": divs.n, "http": dict(f.stats)})
    log.info("fim: %d seções em %.0fs (%.2f/s), %d erros, %d divergências RDV, http %s",
             n_ok, el, n_ok / el if el else 0, len(erros), divs.n, f.stats)
    if erros:
        dst = out / f"erros-{w.prefix}.txt"
        dst.write_text("\n".join(erros) + "\n", encoding="utf-8")
        log.warning("erros gravados em %s; rode de novo para refazer", dst.name)
    if not args.sem_consolidar:
        consolidar(out, Path(args.base_votos), Path(args.saida_auditoria),
                   Path(args.auditoria_publicada))
    return 0 if not erros else 2


# ---------------------------------------------------------------------------
# Consolidação
# ---------------------------------------------------------------------------

def _copiar(con, sel: str, dst: Path) -> list[str]:
    """COPY para Parquet ZSTD; divide em _parteN se passar de 90 MB."""
    for p in dst.parent.glob(f"{dst.stem}*.parquet"):
        p.unlink()
    tmp = f"{dst}.tmp"
    con.execute(f"COPY ({sel}) TO '{tmp}' (FORMAT PARQUET, COMPRESSION ZSTD)")
    tam = os.path.getsize(tmp)
    if tam <= LIMITE_BYTES:
        os.replace(tmp, dst)
        return [dst.name]
    os.remove(tmp)
    n = con.execute(f"SELECT count(*) FROM ({sel})").fetchone()[0]
    partes = -(-tam // ALVO_PARTE)
    por = -(-n // partes)
    nomes = []
    for i in range(partes):
        p = dst.with_name(f"{dst.stem}_parte{i + 1}.parquet")
        con.execute(f"COPY ({sel} LIMIT {por} OFFSET {i * por}) TO '{p}' "
                    "(FORMAT PARQUET, COMPRESSION ZSTD)")
        nomes.append(p.name)
    log.info("%s dividido em %d partes (%d MB)", dst.name, partes, tam >> 20)
    return nomes


def consolidar(out: Path, base_votos: Optional[Path] = None,
               dst_auditoria: Optional[Path] = None,
               auditoria_publicada: Optional[Path] = None) -> None:
    import duckdb

    parts = out / "parts"
    if not any(parts.glob("secoes-*.parquet")):
        log.warning("nenhuma parte para consolidar")
        return
    con = duckdb.connect()
    con.execute(f"""CREATE TEMP TABLE s AS
        SELECT * FROM read_parquet('{parts / "secoes-*.parquet"}', union_by_name = true)
        QUALIFY row_number() OVER (PARTITION BY uf, cd_mun, zona, secao ORDER BY _lote DESC) = 1""")
    for nome in ("recontagem", "tempo", "presidente", "achados"):
        if any(parts.glob(f"{nome}-*.parquet")):
            con.execute(f"""CREATE TEMP TABLE {nome} AS
                SELECT x.* EXCLUDE (_lote)
                FROM read_parquet('{parts / f"{nome}-*.parquet"}', union_by_name = true) x
                JOIN s USING (uf, cd_mun, zona, secao, _lote)""")
    # Partes gravadas antes da coluna origem_log: eram todas lidas como log de urna.
    con.execute("ALTER TABLE tempo ADD COLUMN IF NOT EXISTS origem_log VARCHAR")
    con.execute("UPDATE tempo SET origem_log = 'log' WHERE origem_log IS NULL")
    auditoria = {}
    if dst_auditoria is not None and any(parts.glob("seclog-*.parquet")):
        auditoria = consolidar_auditoria(con, parts, dst_auditoria, auditoria_publicada)
    arquivos = []
    arquivos += _copiar(con, "SELECT * FROM recontagem ORDER BY uf, cd_mun, zona, secao, "
                             "id_eleicao, codigo_cargo", out / "recontagem_secoes.parquet")
    arquivos += _copiar(con, "SELECT * FROM tempo ORDER BY uf, cd_mun, zona, secao",
                        out / "log_tempo_secoes.parquet")

    def q(sql):
        return con.execute(sql).fetchall()

    por_uf = {}
    for row in q("""
        SELECT s.uf, count(*), count(*) FILTER (WHERE status = 'ok'),
               count(*) FILTER (WHERE status = 'sem_rdv'),
               count(*) FILTER (WHERE status NOT IN ('ok', 'sem_rdv')),
               count(*) FILTER (WHERE rdv_confere), count(*) FILTER (WHERE NOT rdv_confere
                                                                     AND status = 'ok'),
               count(*) FILTER (WHERE hash_confere), count(*) FILTER (WHERE NOT hash_confere),
               count(*) FILTER (WHERE NOT estrutura_ok),
               coalesce(sum(registros_rdv), 0), coalesce(sum(comparecimento_bu), 0),
               count(*) FILTER (WHERE origem_bu = 'busa')
        FROM s GROUP BY 1 ORDER BY 1"""):
        por_uf[row[0]] = dict(zip(
            ["secoes", "ok", "sem_rdv", "outros_status", "rdv_confere", "rdv_diverge",
             "hash_confere", "hash_diverge", "estrutura_invalida", "registros_rdv",
             "comparecimento_bu", "secoes_bu_sa"], [int(x) for x in row[1:]], strict=True))
    # Seções com só o log do SA (origem_log = 'logsa') ficam fora da soma log x BU:
    # o log da digitação não tem eventos de voto.
    tempo_uf = {r[0]: {"votos_log": int(r[1] or 0), "comparecimento_bu": int(r[2] or 0),
                       "secoes_log_diverge": int(r[3]), "secoes_fora_sequencia": int(r[4]),
                       "secoes_voto_antes_8h": int(r[5]), "secoes_log_sa": int(r[6])}
                for r in q("""SELECT uf, sum(votos_log) FILTER (WHERE NOT sa),
                    sum(comparecimento_bu) FILTER (WHERE NOT sa),
                    count(*) FILTER (WHERE diferenca_log_bu <> 0 AND NOT sa),
                    count(*) FILTER (WHERE list_contains(flags, 'log_voto_fora_sequencia')),
                    count(*) FILTER (WHERE votos_antes_8h > 0),
                    count(*) FILTER (WHERE sa)
                    FROM (SELECT *, origem_log = 'logsa' AS sa FROM tempo)
                    GROUP BY 1""")}
    for uf, v in tempo_uf.items():
        por_uf.setdefault(uf, {}).update({f"log_{k}": x for k, x in v.items()})
    totais = {}
    for v in por_uf.values():
        for k, x in v.items():
            totais[k] = totais.get(k, 0) + x

    por_cargo = {f"{r[0]}/{r[1]}": {
        "linhas": int(r[2]), "confere": int(r[3]), "diverge": int(r[4]),
        "registros_rdv": int(r[5]), "votos_rdv": int(r[6]), "votos_bu": int(r[7]),
        "brancos_rdv": int(r[8]), "brancos_bu": int(r[9]), "nulos_rdv": int(r[10]),
        "nulos_bu": int(r[11])}
        for r in q("""SELECT id_eleicao, cargo, count(*), count(*) FILTER (WHERE confere),
            count(*) FILTER (WHERE NOT confere), sum(registros_rdv), sum(votos_rdv),
            sum(votos_bu), sum(brancos_rdv), sum(brancos_bu), sum(nulos_rdv), sum(nulos_bu)
            FROM recontagem GROUP BY 1, 2 ORDER BY 1, 2""")}

    presidente = {}
    if "presidente" in {r[0] for r in q("SHOW TABLES")}:
        presidente = {"rdv": {k: int(v) for k, v in q(
            "SELECT chave, sum(votos) FROM presidente GROUP BY 1 ORDER BY 2 DESC")}}
        vp = (base_votos or PARQUET_2026_DIR) / "votos_presidente_2026.parquet"
        if vp.exists():
            ok = "SELECT uf, cd_mun, zona, secao FROM s WHERE status = 'ok'"
            oficial = {}
            for tv, n, v in q(f"""SELECT v.tipo_voto, v.numero, sum(v.votos)
                    FROM read_parquet('{vp}') v JOIN ({ok}) USING (uf, cd_mun, zona, secao)
                    GROUP BY 1, 2"""):
                k = tv if tv in ("branco", "nulo") or n is None else f"{tv}:{int(n)}"
                oficial[k] = oficial.get(k, 0) + int(v)
            presidente["bu_coleta_resultados"] = dict(sorted(oficial.items(),
                                                             key=lambda x: -x[1]))
            todas = set(oficial) | set(presidente["rdv"])
            presidente["diferencas"] = {k: [presidente["rdv"].get(k, 0), oficial.get(k, 0)]
                                        for k in sorted(todas)
                                        if presidente["rdv"].get(k, 0) != oficial.get(k, 0)}

    achados_cat = {}
    if "achados" in {r[0] for r in q("SHOW TABLES")}:
        achados_cat = {c: {"grupo": int(g), "ocorrencias": int(n), "secoes": int(ns)}
                       for c, g, n, ns in q("""SELECT categoria, min(grupo), count(*),
                           count(DISTINCT uf || cd_mun || zona || secao)
                           FROM achados GROUP BY 1 ORDER BY 1""")}
    flags = {c: {"grupo": R.CATEGORIAS.get(c), "secoes": int(n)} for c, n in q(
        "SELECT f, count(*) FROM (SELECT unnest(flags) f FROM tempo) GROUP BY 1 ORDER BY 1")}
    grupos = {str(g): int(n) for g, n in q(
        "SELECT grupo, count(*) FROM tempo WHERE grupo IS NOT NULL GROUP BY 1 ORDER BY 1")}
    hist = [int(x or 0) for x in q(
        f"SELECT {', '.join(f'sum(hist_intervalos[{i + 1}])' for i in range(len(R.FAIXAS_INTERVALO) + 1))} "
        "FROM tempo")[0]]
    limites = [0, *R.FAIXAS_INTERVALO]
    faixas = [f"[{a},{b})" for a, b in zip(limites, R.FAIXAS_INTERVALO, strict=False)] + \
        [f"[{R.FAIXAS_INTERVALO[-1]},inf)"]
    dist = q("""SELECT quantile_cont(intervalo_min_s, [0.001, 0.01, 0.1, 0.5]),
                quantile_cont(intervalo_mediana_s, [0.1, 0.5, 0.9]),
                max(max_votos_minuto), quantile_cont(max_votos_minuto, [0.5, 0.99]),
                min(intervalo_min_s) FROM tempo""")[0]
    pico = {str(k): int(n) for k, n in q(
        "SELECT max_votos_minuto, count(*) FROM tempo GROUP BY 1 ORDER BY 1")}

    divergencias = []
    jp = out / "divergencias.jsonl"
    if jp.exists():
        vistos = set()
        for ln in jp.read_text(encoding="utf-8").splitlines():
            if ln.strip():
                d = json.loads(ln)
                k = (d.get("uf"), d.get("cd_mun"), d.get("zona"), d.get("secao"),
                     d.get("categoria"), d.get("cargo"))
                if k not in vistos:
                    vistos.add(k)
                    divergencias.append(d)
    execucoes = []
    ep = out / "execucoes.jsonl"
    if ep.exists():
        execucoes = [json.loads(ln) for ln in ep.read_text(encoding="utf-8").splitlines()
                     if ln.strip()]
    feitas = Writer(out, 1).done_keys()
    pendentes = set()
    for ep_ in out.glob("erros-*.txt"):
        for ln in ep_.read_text(encoding="utf-8").splitlines():
            k = ln.split(":", 1)[0].strip()
            if k.count("/") == 3 and k not in feitas:
                pendentes.add(k)
    resumo = {
        "gerado_em": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "pleito": E.PLEITO, "ciclo": E.CICLO, "data_eleicao": DATA_ELEICAO,
        "metodo": {
            "rdv": "EntidadeResultadoRDV (spec/v2/rdv.asn1) decodificado em memória; cada "
                   "registro recontado por cargo: nominal pelo número digitado, legenda pelos "
                   "2 primeiros dígitos, branco e brancoAposSuspensao como branco, nulo, "
                   "nuloAposSuspensao e nuloPorRepeticao como nulo, *CargoSemCandidato como "
                   "cargoSemCandidato (agrupado em nulo se o BU não tiver o tipo).",
            "bu": "BU do mesmo conjunto de arquivos, decodificado com parsers/bu.py; "
                  "comparação por candidato, legenda, brancos e nulos em cada cargo e "
                  "registros do RDV = comparecimento x quantidadeEscolhas. Nas seções com BU "
                  "do Sistema de Apuração (totais.secoes_bu_sa) o RDV também é gerado pelo SA a "
                  "partir dos dados digitados, então RDV = BU ali não é conferência "
                  "independente.",
            "hash": "SHA-512 de cada arquivo baixado comparado ao catálogo de integridade "
                    "(arquivos_<uf>.parquet, já conferido com o hash assinado no .vsc).",
            "log": "eventos 'O voto do eleitor foi computado' do dia da eleição; abertura "
                   "oficial 8h e fim 17h de Brasília convertidos para a hora local da urna "
                   "(timezones.get_tz_offset; exterior em hora local). Voto fora de sequência:"
                   " antes da 'Urna pronta para receber votos' ou depois do 'Inicio do "
                   "Encerramento' da mesma urna. Intervalos medidos entre votos consecutivos "
                   "da mesma urna. Logs aninhados ordenados pela data e hora do nome e linhas "
                   "idênticas repetidas entre arquivos do pacote (o mesmo log copiado mais de "
                   "uma vez) contadas uma vez. Seções só com log do SA (-logsa.jez, digitação "
                   "do BU, sem eventos de voto) ficam fora da comparação log x BU "
                   "(origem_log = 'logsa', totais.log_secoes_log_sa).",
            "grupos": "1 = indício direto (RDV x BU, registros, estrutura, hash); 2 = "
                      "inconsistência a investigar (log x BU, sequência, outra data, RDV não "
                      "decodificado, BU do SA); 3 = operacional (horários, rajadas, lacunas).",
        },
        "totais": totais,
        "por_uf": por_uf,
        "por_cargo": por_cargo,
        "presidente": presidente,
        "achados_por_categoria": achados_cat,
        "flags_log": flags,
        "secoes_por_grupo_log": grupos,
        "intervalos": {"faixas_s": faixas, "contagem": hist,
                       "intervalo_min_s_quantis_0.1_1_10_50pct": dist[0],
                       "intervalo_mediana_s_quantis_10_50_90pct": dist[1],
                       "max_votos_minuto": dist[2], "max_votos_minuto_quantis_50_99pct": dist[3],
                       "menor_intervalo_s": dist[4], "secoes_por_pico_minuto": pico},
        "arquivos_parquet": arquivos,
        "auditoria_bu_log": auditoria,
        "n_divergencias_rdv": len(divergencias),
        "divergencias_rdv": divergencias[:500],
        "erros_pendentes": len(pendentes),
        "execucoes": execucoes,
    }
    (out / "resumo.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=1,
                                                default=str), encoding="utf-8")
    log.info("consolidado: %d seções, %d divergências RDV, arquivos %s",
             totais.get("secoes", 0), len(divergencias), arquivos)


def consolidar_auditoria(con, parts: Path, dst: Path, publicada: Optional[Path]) -> dict:
    """secoes_log_2026.parquet e issues_2026.parquet (mesmo esquema da
    auditoria publicada, lote mais recente de cada seção) e comparacao.json
    com a auditoria publicada."""
    dst.mkdir(parents=True, exist_ok=True)
    con.execute("""CREATE OR REPLACE TEMP TABLE sid AS
        SELECT '1T/' || uf || '/' || cd_mun || '/' || zona || '/' || secao AS secao_id, _lote
        FROM s""")
    dl = dst / "secoes_log_2026.parquet"
    con.execute(f"""CREATE OR REPLACE TEMP TABLE seclog_n AS
        SELECT x.* EXCLUDE (_lote)
        FROM read_parquet('{parts / "seclog-*.parquet"}', union_by_name = true) x
        JOIN sid USING (secao_id, _lote)""")
    con.execute(f"""COPY (SELECT * FROM seclog_n ORDER BY uf, cd_mun, zona, secao)
        TO '{dl}.tmp' (FORMAT PARQUET, COMPRESSION ZSTD)""")
    os.replace(f"{dl}.tmp", dl)
    di = dst / "issues_2026.parquet"
    con.execute(f"""CREATE OR REPLACE TEMP TABLE issues_n AS
        SELECT x.* EXCLUDE (_lote)
        FROM read_parquet('{parts / "issues-*.parquet"}', union_by_name = true) x
        JOIN sid USING (secao_id, _lote)""")
    con.execute(f"""COPY (SELECT * FROM issues_n ORDER BY secao_id, codigo)
        TO '{di}.tmp' (FORMAT PARQUET, COMPRESSION ZSTD)""")
    os.replace(f"{di}.tmp", di)
    for p in (dl, di):
        if p.stat().st_size > LIMITE_BYTES:
            log.error("%s passou de 90 MB (%d MB)", p.name, p.stat().st_size >> 20)
    res = {"secoes_log": con.execute("SELECT count(*) FROM seclog_n").fetchone()[0],
           "issues_por_codigo": {c: int(n) for c, n in con.execute(
               "SELECT codigo, count(*) FROM issues_n GROUP BY 1 ORDER BY 1").fetchall()}}
    if publicada and (publicada / "secoes_log_2026.parquet").exists():
        res["comparacao"] = comparar_auditorias(con, publicada, dst)
    log.info("auditoria v2: %s", json.dumps(res, ensure_ascii=False, default=str)[:1500])
    return res


def comparar_auditorias(con, publicada: Path, dst: Path) -> dict:
    """Compara a auditoria nova (tabelas seclog_n e issues_n) com a publicada,
    só nas seções processadas nesta auditoria."""
    from dataurnas.dashboard.reference import GRUPO_ADULTERACAO, ISSUE_GRUPOS

    pl, pi = publicada / "secoes_log_2026.parquet", publicada / "issues_2026.parquet"
    con.execute(f"""CREATE OR REPLACE TEMP TABLE seclog_p AS
        SELECT p.* FROM read_parquet('{pl}') p JOIN seclog_n n USING (secao_id)""")
    con.execute(f"""CREATE OR REPLACE TEMP TABLE issues_p AS
        SELECT p.* FROM read_parquet('{pi}') p JOIN seclog_n n USING (secao_id)""")
    cols = [c for c, *_ in con.execute("DESCRIBE seclog_n").fetchall()
            if c not in ("secao_id", "n_issues", "has_issues")]
    mudou_col = {c: int(con.execute(f"""SELECT count(*) FROM seclog_n n
        JOIN seclog_p p USING (secao_id) WHERE n.{c} IS DISTINCT FROM p.{c}""").fetchone()[0])
        for c in cols}
    cond = " OR ".join(f"n.{c} IS DISTINCT FROM p.{c}" for c in cols)
    secoes_mudaram = int(con.execute(f"""SELECT count(*) FROM seclog_n n
        JOIN seclog_p p USING (secao_id) WHERE {cond}""").fetchone()[0])
    por_codigo = {}
    for cod, n_pub, n_nov, s_ganhou, s_perdeu, s_mudou in con.execute("""
        WITH p AS (SELECT secao_id, codigo, count(*) n,
                          string_agg(severidade || '|' || descricao, ';' ORDER BY descricao) d
                   FROM issues_p GROUP BY 1, 2),
             q AS (SELECT secao_id, codigo, count(*) n,
                          string_agg(severidade || '|' || descricao, ';' ORDER BY descricao) d
                   FROM issues_n GROUP BY 1, 2)
        SELECT coalesce(p.codigo, q.codigo) codigo, coalesce(sum(p.n), 0), coalesce(sum(q.n), 0),
               count(*) FILTER (WHERE p.secao_id IS NULL),
               count(*) FILTER (WHERE q.secao_id IS NULL),
               count(*) FILTER (WHERE p.secao_id IS NOT NULL AND q.secao_id IS NOT NULL
                                AND p.d <> q.d)
        FROM p FULL JOIN q USING (secao_id, codigo) GROUP BY 1 ORDER BY 1""").fetchall():
        por_codigo[cod] = {"ocorrencias_publicada": int(n_pub), "ocorrencias_nova": int(n_nov),
                           "secoes_ganharam": int(s_ganhou), "secoes_perderam": int(s_perdeu),
                           "secoes_descricao_mudou": int(s_mudou),
                           "grupo": ISSUE_GRUPOS.get(cod)}
    secoes_issues_mudaram = int(con.execute("""
        WITH p AS (SELECT secao_id, string_agg(codigo || '|' || descricao, ';'
                          ORDER BY codigo, descricao) d FROM issues_p GROUP BY 1),
             q AS (SELECT secao_id, string_agg(codigo || '|' || descricao, ';'
                          ORDER BY codigo, descricao) d FROM issues_n GROUP BY 1)
        SELECT count(*) FROM p FULL JOIN q USING (secao_id)
        WHERE p.d IS DISTINCT FROM q.d""").fetchone()[0])
    grupo1 = [c for c, g in ISSUE_GRUPOS.items() if g == GRUPO_ADULTERACAO]
    alvo = ["A03", *grupo1]
    exemplos = {c: [r[0] for r in con.execute(
        "SELECT DISTINCT secao_id FROM issues_n WHERE codigo = ? ORDER BY 1 LIMIT 20",
        [c]).fetchall()] for c in alvo}
    comp = {
        "secoes_comparadas": int(con.execute("SELECT count(*) FROM seclog_p").fetchone()[0]),
        "secoes_log_mudaram": secoes_mudaram,
        "secoes_log_mudaram_por_coluna": {c: n for c, n in mudou_col.items() if n},
        "secoes_issues_mudaram": secoes_issues_mudaram,
        "issues_por_codigo": por_codigo,
        "a03_e_grupo1_na_nova": {c: {"secoes": len(v), "exemplos": v}
                                 for c, v in exemplos.items() if v},
    }
    (dst / "comparacao.json").write_text(json.dumps(comp, ensure_ascii=False, indent=1),
                                         encoding="utf-8")
    return comp


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ufs", default=",".join(TODAS_UFS))
    ap.add_argument("--fonte", choices=("catalogo", "aux"), default="catalogo",
                    help="lista de seções e nomes: catálogo de integridade ou aux.json")
    ap.add_argument("--manifesto", default=str(MANIFESTO))
    ap.add_argument("--catalogo-local", default=str(PARQUET_2026_DIR / "integridade"),
                    help="diretório com arquivos_<uf>.parquet locais (usados se existirem)")
    ap.add_argument("--concorrencia", type=int, default=24,
                    help="seções em andamento ao mesmo tempo (padrão: 24)")
    ap.add_argument("--workers", type=int, default=3, help="processos de decodificação")
    ap.add_argument("--lote", type=int, default=2000)
    ap.add_argument("--http2", action=argparse.BooleanOptionalAction, default=True)
    ap.add_argument("--taxa", type=float, default=20.0, help="req/s inicial (AIMD em 429)")
    ap.add_argument("--taxa-max", type=float, default=25.0, help="teto da taxa em req/s")
    ap.add_argument("--conexoes", type=int, default=2)
    ap.add_argument("--base-votos", default=str(PARQUET_2026_DIR))
    ap.add_argument("--saida", default=str(PARQUET_2026_DIR / "rdv"))
    ap.add_argument("--log", default=str(ROOT / "data" / "ele2026_rdv.log"))
    ap.add_argument("--auditar", action=argparse.BooleanOptionalAction, default=True,
                    help="regera a auditoria por seção de BU e log com o mesmo download")
    ap.add_argument("--saida-auditoria", default=str(PARQUET_2026_DIR / "auditoria_v2"))
    ap.add_argument("--auditoria-publicada", default=str(PARQUET_2026_DIR / "auditoria"))
    ap.add_argument("--secoes-integridade",
                    default=str(PARQUET_2026_DIR / "integridade" / "secoes.parquet"),
                    help="modelo da urna por seção (lido do .vsc na integridade)")
    ap.add_argument("--secoes", default=None,
                    help="arquivo com chaves uf/cd_mun/zona/secao a refazer (ignora o checkpoint)")
    ap.add_argument("--sem-consolidar", action="store_true")
    ap.add_argument("--so-consolidar", action="store_true")
    a = ap.parse_args(argv)
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
        consolidar(Path(args.saida), Path(args.base_votos), Path(args.saida_auditoria),
                   Path(args.auditoria_publicada))
        sys.exit(0)
    sys.exit(asyncio.run(run(args)))
