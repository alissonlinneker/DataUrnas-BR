#!/usr/bin/env python3
"""Versiona, durante a apuração, o que o TSE publica do 2º turno de 2026.

Dois coletores rodam juntos (ou separados, com --so-totais / --so-bus):

totais
  A cada --intervalo-totais segundos baixa o resultado de Presidente do Brasil,
  das 27 UFs e do exterior; a cada --intervalo-municipios segundos, o de todos
  os municípios. Cada corpo diferente do anterior é gravado (gzip) e anotado em
  totais/indice.jsonl. Compara cada versão com a anterior da mesma abrangência
  e registra alerta se cair a quantidade de seções totalizadas, o total de
  votos ou os votos de algum candidato.

bus
  Passa por todas as seções em ciclos. Para cada seção baixa o aux.json; cada
  aux.json diferente é guardado. Cada hash de conjunto ainda não visto tem o BU
  (bu ou busa) e a assinatura (vota ou sa) baixados e guardados em bruto, com o
  SHA-512 e os votos de Presidente decodificados. Se a mesma seção aparecer
  com um segundo BU, os votos das duas versões são comparados e a diferença
  vira alerta.

Saída em data/versoes/2026/t2/ (ignorada pelo git):
  totais/<abr>/<dg>_<hg>_<idg>.json.gz, totais/indice.jsonl
  bus/parts/*.parquet (aux, BU e votos por versão), bus/estado.jsonl
  alertas.jsonl (uma linha por alerta, também no log)

Uso:
  python3 scripts/ele2026/versionar_t2.py                 # tudo, sem parar
  python3 scripts/ele2026/versionar_t2.py --ufs ac --ciclos 1
  python3 scripts/ele2026/versionar_t2.py --so-totais
"""

from __future__ import annotations

import argparse
import asyncio
import gzip
import hashlib
import json
import logging
import os
import signal
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

from dataurnas.config import ESTADOS  # noqa: E402
from dataurnas.downloader import ele2026 as E  # noqa: E402

log = logging.getLogger("versionar_t2")

P = E.parametros_turno(2)
URL = {"pleito": P["pleito"], "ciclo": P["ciclo"]}
TODAS_UFS = ESTADOS + ["zz"]
SAIDA = ROOT / "data" / "versoes" / "2026" / "t2"

VERSOES_SCHEMA = pa.schema([
    ("coletado_em", pa.string()), ("uf", pa.string()), ("cd_mun", pa.string()),
    ("zona", pa.string()), ("secao", pa.string()),
    ("tipo", pa.string()),  # aux | bu | busa | vota | sa
    ("hash", pa.string()), ("st_secao", pa.string()), ("st_hash", pa.string()),
    ("dt_recebimento", pa.string()), ("hr_recebimento", pa.string()),
    ("nome", pa.string()), ("sha512", pa.string()), ("tamanho", pa.int32()),
    ("conteudo", pa.binary()),
])

VOTOS_SCHEMA = pa.schema([
    ("coletado_em", pa.string()), ("uf", pa.string()), ("cd_mun", pa.string()),
    ("zona", pa.string()), ("secao", pa.string()), ("hash", pa.string()),
    ("sha512_bu", pa.string()), ("comparecimento", pa.int32()),
    ("tipo_voto", pa.string()), ("numero", pa.int32()), ("votos", pa.int32()),
])


def agora() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


class Alertas:
    def __init__(self, path: Path):
        self.path = path

    def registrar(self, tipo: str, **dados) -> None:
        reg = {"em": agora(), "tipo": tipo, **dados}
        log.warning("ALERTA %s %s", tipo, json.dumps(dados, ensure_ascii=False))
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(reg, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Totais agregados
# ---------------------------------------------------------------------------

def resumo_totais(d: dict) -> dict:
    s = d.get("s") or {}
    v = d.get("v") or {}
    cand = {str(c.get("n")): E.to_int(c.get("vap")) or 0
            for _, _, c in E.iter_candidatos(d)}
    return {
        "dg": d.get("dg"), "hg": d.get("hg"), "idg": d.get("idg"),
        "st": E.to_int(s.get("st")), "ts": E.to_int(s.get("ts")),
        "tv": E.to_int(v.get("tv")), "vb": E.to_int(v.get("vb")),
        "tvn": E.to_int(v.get("tvn")), "cand": cand,
    }


def regressoes(ant: dict, novo: dict) -> list[str]:
    """Quedas entre duas versões da mesma abrangência (deveriam só subir)."""
    out = []
    for k in ("st", "tv", "vb", "tvn"):
        if ant.get(k) is not None and novo.get(k) is not None and novo[k] < ant[k]:
            out.append(f"{k}: {ant[k]} -> {novo[k]}")
    for n, q in (ant.get("cand") or {}).items():
        q2 = (novo.get("cand") or {}).get(n)
        if q2 is not None and q2 < q:
            out.append(f"candidato {n}: {q} -> {q2}")
    return out


class Totais:
    def __init__(self, f: E.HttpFetcher, out: Path, alertas: Alertas):
        self.f = f
        self.dir = out / "totais"
        self.dir.mkdir(parents=True, exist_ok=True)
        self.indice = self.dir / "indice.jsonl"
        self.alertas = alertas
        self.ultimo: dict[str, tuple[str, dict]] = {}
        if self.indice.exists():
            for ln in self.indice.read_text(encoding="utf-8").splitlines():
                r = json.loads(ln)
                self.ultimo[r["abr"]] = (r["sha256"], r)

    async def coletar(self, abr: str) -> bool:
        body = await self.f.get(E.url_resultado(abr, eleicao=P["eleicao"],
                                                cargo=P["cargo"], ciclo=P["ciclo"]))
        if body is None:
            return False
        sha = hashlib.sha256(body).hexdigest()
        ant = self.ultimo.get(abr)
        if ant and ant[0] == sha:
            return False
        d = json.loads(body)
        r = {"coletado_em": agora(), "abr": abr, "sha256": sha, **resumo_totais(d)}
        nome = f"{(r['dg'] or '').replace('/', '')}_{(r['hg'] or '').replace(':', '')}_{r['idg']}"
        sub = self.dir / abr
        sub.mkdir(exist_ok=True)
        (sub / f"{nome}.json.gz").write_bytes(gzip.compress(body, 6))
        if ant:
            quedas = regressoes(ant[1], r)
            if quedas:
                self.alertas.registrar("totais_regressao", abr=abr, de=ant[1].get("idg"),
                                       para=r["idg"], quedas=quedas)
        with open(self.indice, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")
        self.ultimo[abr] = (sha, r)
        return True

    async def rodada(self, abrs: list[str]) -> int:
        res = await asyncio.gather(*[self.coletar(a) for a in abrs],
                                   return_exceptions=True)
        for a, x in zip(abrs, res, strict=True):
            if isinstance(x, Exception):
                log.warning("totais %s: %r", a, x)
        return sum(1 for x in res if x is True)

    async def municipios(self) -> list[str]:
        cm = await self.f.get_json(E.url_municipios(eleicao=P["eleicao"], ciclo=P["ciclo"]))
        if not cm:
            return []
        return [f"{m['uf']}{m['cd_mun']}" for m in E.iter_municipios(cm)]

    async def loop(self, ufs: list[str], intervalo: float, intervalo_mun: float,
                   parar: asyncio.Event) -> None:
        abrs = ["br"] + ufs
        muns: list[str] = []
        t_mun = 0.0
        while not parar.is_set():
            n = await self.rodada(abrs)
            br = self.ultimo.get("br")
            if br:
                r = br[1]
                log.info("totais: %d novas | BR %s %s seções %s/%s votos %s %s",
                         n, r["dg"], r["hg"], r["st"], r["ts"], r["tv"], r["cand"])
            if intervalo_mun and time.time() - t_mun >= intervalo_mun:
                if not muns:
                    muns = await self.municipios()
                    muns = [m for m in muns if m[:2] in ufs]
                t0 = time.time()
                n = await self.rodada(muns)
                t_mun = time.time()
                log.info("totais municipais: %d de %d com versão nova em %.0fs",
                         n, len(muns), t_mun - t0)
            try:
                await asyncio.wait_for(parar.wait(), intervalo)
            except asyncio.TimeoutError:
                pass


# ---------------------------------------------------------------------------
# Arquivos por seção (aux.json, BU, assinatura)
# ---------------------------------------------------------------------------

def _init_worker(src: str) -> None:
    if src not in sys.path:
        sys.path.insert(0, src)


def votos_bu(raw: bytes) -> tuple[Optional[int], list[tuple[str, int, int]]]:
    sec, votos = E.bu_to_rows(raw, int(P["eleicao"]), P["cargo"])
    return sec.get("comparecimento"), sorted(
        (v["tipo_voto"], v["numero"] or 0, v["votos"]) for v in votos)


class Estado:
    """O que já foi visto por seção: SHA-256 do último aux.json e hashes de
    conjunto com o SHA-512 do BU e os votos. Persistido em estado.jsonl."""

    def __init__(self, path: Path):
        self.path = path
        self.aux: dict[str, str] = {}
        self.bus: dict[str, dict[str, dict]] = {}
        # arquivos guardados por seção: (hash, nome) -> registro com tipo e MD5
        self.arqs: dict[str, dict[tuple[str, str], dict]] = {}
        if path.exists():
            for ln in path.read_text(encoding="utf-8").splitlines():
                r = json.loads(ln)
                if r["t"] == "aux":
                    self.aux[r["k"]] = r["sha"]
                elif r["t"] == "arq":
                    self.arqs.setdefault(r["k"], {})[(r["hash"], r["nome"])] = r
                else:
                    self.bus.setdefault(r["k"], {})[r["hash"]] = r
        self.fh = open(path, "a", encoding="utf-8")

    def gravar(self, r: dict) -> None:
        self.fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    def flush(self) -> None:
        self.fh.flush()
        os.fsync(self.fh.fileno())


class Bus:
    def __init__(self, f: E.HttpFetcher, out: Path, alertas: Alertas,
                 pool: ProcessPoolExecutor, lote: int):
        self.f = f
        self.dir = out / "bus"
        self.parts = self.dir / "parts"
        self.parts.mkdir(parents=True, exist_ok=True)
        self.alertas = alertas
        self.pool = pool
        self.lote = lote
        self.estado = Estado(self.dir / "estado.jsonl")
        self.versoes: list[dict] = []
        self.votos: list[dict] = []
        self.pend_estado: list[dict] = []
        self.n_part = 0
        self.prefixo = time.strftime("%Y%m%d%H%M%S") + f"-{os.getpid()}"
        self.cont = {"aux_novo": 0, "bu_novo": 0, "sem_aux": 0, "sem_bu": 0,
                     "igual": 0, "erro": 0, "conferidos": 0, "alterados": 0}
        self.reverificar = False
        self._completar_md5()

    def _completar_md5(self) -> None:
        """Anota o MD5 dos arquivos gravados antes de o estado guardar o MD5."""
        faltam = {k for k in self.estado.bus if k not in self.estado.arqs}
        if not faltam:
            return
        n = 0
        for part in sorted(self.parts.glob("versoes-*.parquet")):
            t = pq.read_table(part, columns=["uf", "cd_mun", "zona", "secao", "tipo",
                                             "hash", "nome", "conteudo"])
            for r in t.to_pylist():
                if r["tipo"] == "aux":
                    continue
                k = E.secao_key(r["uf"], r["cd_mun"], r["zona"], r["secao"])
                if k not in faltam or r["hash"] not in self.estado.bus.get(k, {}):
                    continue
                reg = {"t": "arq", "k": k, "hash": r["hash"], "nome": r["nome"],
                       "tipo": r["tipo"], "md5": hashlib.md5(r["conteudo"]).hexdigest()}
                self.estado.arqs.setdefault(k, {})[(r["hash"], r["nome"])] = reg
                self.estado.gravar(reg)
                n += 1
        self.estado.flush()
        log.info("MD5 anotado para %d arquivos já guardados", n)

    def flush(self) -> None:
        if not self.versoes and not self.pend_estado:
            return
        self.n_part += 1
        lote = f"{self.prefixo}-{self.n_part:05d}"
        for nome, rows, schema in (("versoes", self.versoes, VERSOES_SCHEMA),
                                   ("votos", self.votos, VOTOS_SCHEMA)):
            if not rows:
                continue
            dst = self.parts / f"{nome}-{lote}.parquet"
            tmp = dst.with_suffix(".tmp")
            pq.write_table(pa.Table.from_pylist(rows, schema=schema), tmp,
                           compression="zstd")
            tmp.replace(dst)
        # o estado só é anotado depois que as partes estão no disco
        for r in self.pend_estado:
            self.estado.gravar(r)
        self.estado.flush()
        self.versoes, self.votos, self.pend_estado = [], [], []

    def _guardar(self, ident: dict, tipo: str, conteudo: bytes, **campos) -> str:
        sha = hashlib.sha512(conteudo).hexdigest()
        self.versoes.append({"coletado_em": agora(), **ident, "tipo": tipo,
                             "sha512": sha, "tamanho": len(conteudo),
                             "conteudo": conteudo, **campos})
        if tipo != "aux":
            k = E.secao_key(ident["uf"], ident["cd_mun"], ident["zona"], ident["secao"])
            reg = {"t": "arq", "k": k, "hash": campos["hash"], "nome": campos["nome"],
                   "tipo": tipo, "md5": hashlib.md5(conteudo).hexdigest()}
            self.estado.arqs.setdefault(k, {})[(reg["hash"], reg["nome"])] = reg
            self.pend_estado.append(reg)
        return sha

    async def conferir(self, key: str, ident: dict) -> None:
        """Confere por HEAD (ETag = MD5) cada arquivo já guardado da seção.
        Arquivo trocado no mesmo endereço é baixado de novo e vira alerta."""
        uf, mun, zona, secao = ident["uf"], ident["cd_mun"], ident["zona"], ident["secao"]
        for (hv, nome), reg in list(self.estado.arqs.get(key, {}).items()):
            url = E.url_arquivo(uf, mun, zona, secao, hv, nome, **URL)
            h = await self.f.head(url)
            self.cont["conferidos"] += 1
            if h is None:
                self.alertas.registrar("arquivo_removido", secao=key, hash=hv, nome=nome,
                                       md5=reg["md5"])
                continue
            etag = (h.get("etag") or "").strip('"')
            if not etag or "-" in etag or etag == reg["md5"]:
                continue  # ETag de upload em partes não é o MD5: nada a comparar
            raw = await self.f.get(url)
            if raw is None or hashlib.md5(raw).hexdigest() == reg["md5"]:
                continue
            self.cont["alterados"] += 1
            sha = self._guardar(ident, reg["tipo"], raw, hash=hv, nome=nome,
                                st_hash="alterado_mesmo_endereco")
            dados = {"secao": key, "hash": hv, "nome": nome, "tipo_arquivo": reg["tipo"],
                     "md5_anterior": reg["md5"], "md5_novo": hashlib.md5(raw).hexdigest(),
                     "sha512_novo": sha, "last_modified": h.get("last-modified")}
            if reg["tipo"] in ("bu", "busa"):
                loop = asyncio.get_running_loop()
                comp, votos = await loop.run_in_executor(self.pool, votos_bu, raw)
                ant = self.estado.bus.get(key, {}).get(hv) or {}
                dados["comparecimento"] = [ant.get("comparecimento"), comp]
                dados["votos_iguais"] = ([list(x) for x in ant.get("votos", [])]
                                         == [list(x) for x in votos])
                dados["votos_anterior"], dados["votos_novo"] = ant.get("votos"), votos
            self.alertas.registrar("arquivo_alterado", **dados)

    async def secao(self, s: dict) -> None:
        uf, mun, zona, secao = s["uf"], s["cd_mun"], s["zona"], s["secao"]
        key = E.secao_key(uf, mun, zona, secao)
        ident = {"uf": uf, "cd_mun": mun, "zona": zona, "secao": secao}
        body = await self.f.get(E.url_aux(uf, mun, zona, secao, **URL))
        if body is None:
            self.cont["sem_aux"] += 1
            return
        sha_aux = hashlib.sha256(body).hexdigest()
        if self.estado.aux.get(key) == sha_aux:
            self.cont["igual"] += 1
            if self.reverificar:
                await self.conferir(key, ident)
            return
        aux = json.loads(body)
        self._guardar(ident, "aux", body, st_secao=aux.get("st"))
        self.cont["aux_novo"] += 1
        if key in self.estado.arqs:
            # aux.json mudou: confere também o que já estava guardado
            await self.conferir(key, ident)
        vistos = self.estado.bus.setdefault(key, {})
        completo = True
        for h in aux.get("hashes") or []:
            hv = h.get("hash")
            if not hv or hv == "0" or hv in vistos:
                continue
            arqs = {a.get("tp", ""): a.get("nm", "") for a in h.get("arq") or []
                    if isinstance(a, dict)}
            tp_bu = "bu" if "bu" in arqs else ("busa" if "busa" in arqs else None)
            if not tp_bu:
                continue
            campos = {"hash": hv, "st_secao": aux.get("st"), "st_hash": h.get("st"),
                      "dt_recebimento": h.get("dr"), "hr_recebimento": h.get("hr")}
            raw_bu = await self.f.get(E.url_arquivo(uf, mun, zona, secao, hv,
                                                    arqs[tp_bu], **URL))
            if raw_bu is None:
                self.cont["sem_bu"] += 1
                completo = False
                continue
            sha_bu = self._guardar(ident, tp_bu, raw_bu, nome=arqs[tp_bu], **campos)
            tp_vsc = "vota" if "vota" in arqs else ("sa" if "sa" in arqs else None)
            if tp_vsc:
                raw_vsc = await self.f.get(E.url_arquivo(uf, mun, zona, secao, hv,
                                                         arqs[tp_vsc], **URL))
                if raw_vsc is not None:
                    self._guardar(ident, tp_vsc, raw_vsc, nome=arqs[tp_vsc], **campos)
            loop = asyncio.get_running_loop()
            comp, votos = await loop.run_in_executor(self.pool, votos_bu, raw_bu)
            em = agora()
            for tv, num, q in votos:
                self.votos.append({"coletado_em": em, **ident, "hash": hv,
                                   "sha512_bu": sha_bu, "comparecimento": comp,
                                   "tipo_voto": tv, "numero": num, "votos": q})
            reg = {"t": "bu", "k": key, "hash": hv, "sha512": sha_bu,
                   "comparecimento": comp, "votos": votos, "em": em}
            for hv_ant, ant in vistos.items():
                if ant["sha512"] == sha_bu:
                    continue
                dados = {"secao": key, "hash_anterior": hv_ant, "hash_novo": hv,
                         "comparecimento": [ant["comparecimento"], comp]}
                if [list(x) for x in ant["votos"]] != [list(x) for x in votos]:
                    self.alertas.registrar("bu_votos_diferentes", **dados,
                                           votos_anterior=ant["votos"], votos_novo=votos)
                else:
                    self.alertas.registrar("bu_nova_versao_mesmos_votos", **dados)
            vistos[hv] = reg
            self.pend_estado.append(reg)
            self.cont["bu_novo"] += 1
        if completo:
            # com BU listado e ainda indisponível o aux.json é relido no próximo ciclo
            self.estado.aux[key] = sha_aux
            self.pend_estado.append({"t": "aux", "k": key, "sha": sha_aux})
        if len(self.versoes) >= self.lote:
            self.flush()

    async def ciclo(self, ufs: list[str], concorrencia: int) -> None:
        for uf in ufs:
            cs = await self.f.get_json(E.url_secoes_uf(uf, **URL))
            if not cs:
                log.error("sem lista de seções para %s", uf)
                continue
            secoes = [s for s in E.iter_secoes_cs(cs) if not s.get("secao_principal")]
            q: asyncio.Queue = asyncio.Queue()
            for s in secoes:
                q.put_nowait(s)
            t0 = time.time()

            async def worker():
                while True:
                    try:
                        s = q.get_nowait()
                    except asyncio.QueueEmpty:
                        return
                    try:
                        await self.secao(s)
                    except Exception as e:  # noqa: BLE001 - refeito no próximo ciclo
                        self.cont["erro"] += 1
                        log.warning("erro em %s/%s/%s/%s: %r", s["uf"], s["cd_mun"],
                                    s["zona"], s["secao"], e)

            await asyncio.gather(*[worker() for _ in range(concorrencia)])
            self.flush()
            log.info("bus %s: %d seções em %.0fs | %s | http %s", uf, len(secoes),
                     time.time() - t0, self.cont, self.f.stats)


# ---------------------------------------------------------------------------

async def run(args: argparse.Namespace) -> int:
    out = Path(args.saida)
    out.mkdir(parents=True, exist_ok=True)
    alertas = Alertas(out / "alertas.jsonl")
    parar = asyncio.Event()
    tarefas = []
    bus = None
    f_tot = E.HttpFetcher(concurrency=8, http2=True, rate=10, rate_max=20)
    f_bus = E.HttpFetcher(concurrency=args.concorrencia, http2=True,
                          connections=args.conexoes, rate=args.taxa,
                          rate_max=args.taxa_max)
    if f_bus.limiter:
        # o padrão (piso 2 req/s, +0,02 por sucesso) leva horas para se recuperar
        # depois de uma rajada de 429 do TSE
        f_bus.limiter.rate_min = min(args.taxa_min, args.taxa)
        f_bus.limiter.step = 0.2
    pool = ProcessPoolExecutor(max_workers=args.workers, initializer=_init_worker,
                               initargs=(SRC,))
    try:
        if not args.so_bus:
            tot = Totais(f_tot, out, alertas)
            tarefas.append(asyncio.create_task(
                tot.loop(args.ufs, args.intervalo_totais, args.intervalo_municipios, parar)))
        if not args.so_totais:
            bus = Bus(f_bus, out, alertas, pool, args.lote)

            async def ciclos():
                n = 0
                while not parar.is_set() and (not args.ciclos or n < args.ciclos):
                    n += 1
                    bus.reverificar = bool(args.reverificar_a_cada) and (
                        n % args.reverificar_a_cada == 0)
                    if bus.reverificar:
                        log.info("bus: ciclo %d confere por HEAD os arquivos já guardados", n)
                    t0 = time.time()
                    log.info("bus: ciclo %d começou", n)
                    await bus.ciclo(args.ufs, args.concorrencia)
                    log.info("bus: ciclo %d terminou em %.0fs", n, time.time() - t0)
                    if args.pausa_ciclo:
                        try:
                            await asyncio.wait_for(parar.wait(), args.pausa_ciclo)
                        except asyncio.TimeoutError:
                            pass
                if args.ciclos:
                    parar.set()

            tarefas.append(asyncio.create_task(ciclos()))
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, lambda: [t.cancel() for t in tarefas])
        try:
            await asyncio.gather(*tarefas)
        except asyncio.CancelledError:
            log.info("interrompido: gravando o que já foi baixado")
    finally:
        parar.set()
        if bus is not None:
            bus.flush()
        await f_tot.close()
        await f_bus.close()
        pool.shutdown(wait=True)
    return 0


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ufs", default=",".join(TODAS_UFS),
                    help="UFs separadas por vírgula (padrão: 27 + zz)")
    ap.add_argument("--saida", default=str(SAIDA))
    ap.add_argument("--so-totais", action="store_true")
    ap.add_argument("--so-bus", action="store_true")
    ap.add_argument("--ciclos", type=int, default=0,
                    help="quantos ciclos de seções (0 = sem parar)")
    ap.add_argument("--pausa-ciclo", type=float, default=60.0)
    ap.add_argument("--intervalo-totais", type=float, default=60.0)
    ap.add_argument("--intervalo-municipios", type=float, default=900.0,
                    help="0 desliga os totais municipais")
    ap.add_argument("--concorrencia", type=int, default=48)
    ap.add_argument("--conexoes", type=int, default=2)
    ap.add_argument("--taxa", type=float, default=40.0)
    ap.add_argument("--taxa-max", type=float, default=70.0)
    ap.add_argument("--taxa-min", type=float, default=10.0,
                    help="piso da taxa adaptativa depois de 429 (req/s)")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--lote", type=int, default=2000)
    ap.add_argument("--reverificar-a-cada", type=int, default=2,
                    help="a cada N ciclos confere por HEAD todos os arquivos guardados "
                         "(0 desliga)")
    a = ap.parse_args(argv)
    a.ufs = [u.strip().lower() for u in a.ufs.split(",") if u.strip()]
    return a


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    return asyncio.run(run(parse_args()))


if __name__ == "__main__":
    sys.exit(main())
