#!/usr/bin/env python3
"""Auditoria de integridade dos arquivos de urna de 2022 (1º e 2º turnos).

Mesma verificação feita em 2026 (scripts/ele2026/fetch_integridade.py), adaptada
à fonte que ainda existe para 2022. A API de resultados não serve mais o pleito
de 2022 (ele2022/arquivo-urna/406 e 407 respondem 404 desde que o pleito saiu de
ele-c.json); os mesmos arquivos estão no portal de dados abertos do TSE, um zip
por turno e UF, lido aqui por faixas de bytes (HTTP Range), sem gravar nada
bruto em disco:

  zip remoto -> diretório central (ZIP64 em SP) -> blocos contíguos de seções
  -> descompacta cada entrada em memória e confere o CRC-32 do zip
  -> tamanho, MD5, SHA-256, SHA-512 de .bu, .rdv, .logjez, .imgbu
  -> compara o SHA-512 com o hash assinado no .vscmr (partes SW e HW)
  -> verifica a assinatura de hardware (ECDSA P-521 nas urnas de 2022) do
     conteúdo assinado e de cada arquivo publicado, com o certificado da urna
  -> opcionalmente confere os votos de Presidente do BU com o banco de 2022
     (data/parquet/votos_t*.parquet)

Categorias de divergência (iguais às de 2026): hash_diverge, assinatura_invalida,
hash_assinado_ausente e arquivo_ausente_tse (arquivo publicado pelo TSE e
assinado no .vscmr, mas ausente no pacote). Cada divergência vai na hora para
divergencias.jsonl (com fsync) e para o log, numa linha "DIVERGENCIA ".

Ocorrências de publicação (não são divergências): seção do banco de 2022 sem
arquivos no pacote, seção do pacote fora do banco, entrada com nome fora do
padrão, pacote indisponível e entrada corrompida no zip (CRC-32).

Saída em data/parquet/2022/integridade/:
  secoes.parquet                  uma linha por seção e turno
  arquivos_t<turno>_<uf>.parquet  uma linha por arquivo (fora do git; anexos de
                                  versão, descritos em catalogo_manifest.json)
  catalogo_manifest.json          arquivo, turno, UF, tamanho, SHA-256, linhas
  resumo.json                     totais, por turno e UF, algoritmos, modelos,
                                  divergências, ocorrências, pacotes, execuções
  divergencias.jsonl              gravado na hora de cada divergência
  ocorrencias_publicacao.jsonl    gravado na hora de cada ocorrência

Intermediários (fora do git): parts/, checkpoint.txt, erros-*.txt,
execucoes.jsonl, pacotes.jsonl. O checkpoint é por seção (secao_id "1T/ac/...")
e o processo pode ser interrompido e retomado a qualquer momento.

Uso:
  nice -n 20 python3 scripts/ele2022/fetch_integridade.py --turnos 1 --ufs ac,rr
  nice -n 20 python3 scripts/ele2022/fetch_integridade.py          # 2 turnos, 27 UFs + zz
  python3 scripts/ele2022/fetch_integridade.py --so-consolidar
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import os
import random
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

from dataurnas.config import ELECTIONS, ESTADOS, PARQUET_DIR  # noqa: E402
from dataurnas.downloader import zip_remoto as Z  # noqa: E402

log = logging.getLogger("fetch_integridade_2022")

ELE2022 = ELECTIONS["presidencial_2022"]
PLEITOS = {1: ELE2022["pleito_1t"], 2: ELE2022["pleito_2t"]}
ELEICOES = {1: int(ELE2022["eleicao_1t"]), 2: int(ELE2022["eleicao_2t"])}
DATAS = {1: "02/10/2022", 2: "30/10/2022"}
CARGO_PRESIDENTE = 1
TODAS_UFS = ESTADOS + ["zz"]
SAIDA_PADRAO = PARQUET_DIR / "2022" / "integridade"
LIMITE_BYTES = 90 * 1024 * 1024
ALVO_PARTE = 80 * 1024 * 1024
TAXA_TETO = 25.0  # req/s, limite combinado com o dono do projeto
FONTE = "pacote de dados abertos"

ARQUIVOS_SCHEMA = pa.schema([
    ("turno", pa.int32()), ("uf", pa.string()), ("cd_mun", pa.string()),
    ("zona", pa.string()), ("secao", pa.string()), ("tipo", pa.string()),
    ("nome", pa.string()), ("tamanho", pa.int64()), ("md5", pa.string()),
    ("sha256", pa.string()), ("sha512", pa.string()), ("sha512_assinado", pa.string()),
    ("hash_confere", pa.bool_()), ("assinatura_arquivo_valida", pa.bool_()),
    ("crc32", pa.string()), ("data_hora_zip", pa.string()), ("_lote", pa.string()),
])

SECOES_SCHEMA = pa.schema([
    ("turno", pa.int32()), ("secao_id", pa.string()), ("uf", pa.string()),
    ("cd_mun", pa.string()), ("zona", pa.string()), ("secao", pa.string()),
    ("status_secao", pa.string()), ("no_banco_2022", pa.bool_()),
    ("n_arquivos", pa.int32()), ("n_hash_confere", pa.int32()),
    ("n_hash_diverge", pa.int32()), ("n_sem_hash", pa.int32()),
    ("assinatura_valida", pa.bool_()), ("assinatura_algoritmo", pa.string()),
    ("n_assinaturas_arquivos_validas", pa.int32()),
    ("n_assinaturas_arquivos_invalidas", pa.int32()),
    ("cert_subject", pa.string()), ("cert_issuer", pa.string()),
    ("cert_serial", pa.string()), ("cert_sha256", pa.string()),
    ("modelo_urna", pa.string()), ("motivo", pa.string()),
    ("votos_conferem", pa.bool_()), ("_lote", pa.string()),
])

CATEGORIAS_OCORRENCIA = (
    "secao_sem_arquivos_no_pacote",   # seção do banco de 2022 ausente no zip
    "secao_fora_do_banco",            # seção do zip que não está no banco de 2022
    "entrada_fora_do_padrao",         # nome de entrada fora de o00406-MMMMMZZZZSSSS.ext
    "entrada_corrompida",             # CRC-32 ou tamanho do zip não conferem
    "pacote_indisponivel",            # zip da UF/turno não encontrado
)


def secao_id(turno: int, uf: str, mun: str, zona: str, secao: str) -> str:
    return f"{turno}T/{uf.lower()}/{mun}/{zona}/{secao}"


def _init_worker(src: str) -> None:
    if src not in sys.path:
        sys.path.insert(0, src)
    try:  # processos de hash e verificação com a menor prioridade
        os.nice(19)
    except OSError:
        pass


# ---------------------------------------------------------------------------
# Registros gravados na hora (JSONL com fsync)
# ---------------------------------------------------------------------------

class Jsonl:
    """Grava cada registro na hora (JSONL com fsync) e no log com um prefixo."""

    def __init__(self, path: Path, prefixo: str, nivel: int = logging.WARNING):
        self.path = path
        self.prefixo = prefixo
        self.nivel = nivel
        self.n = 0

    def registrar(self, d: dict) -> None:
        d = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), **d}
        linha = json.dumps(d, ensure_ascii=False)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(linha + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        self.n += 1
        log.log(self.nivel, "%s %s", self.prefixo, linha)


class Writer:
    """Acumula linhas e grava partes Parquet + checkpoint."""

    def __init__(self, out: Path, lote: int):
        self.parts = out / "parts"
        self.parts.mkdir(parents=True, exist_ok=True)
        self.ckpt = out / "checkpoint.txt"
        self.lote = lote
        self.arquivos: list[dict] = []
        self.secoes: list[dict] = []
        self.keys: list[str] = []
        self.n_part = 0
        self.prefix = time.strftime("%Y%m%d%H%M%S") + f"-{os.getpid()}"

    def done_keys(self) -> set[str]:
        if not self.ckpt.exists():
            return set()
        with open(self.ckpt, encoding="utf-8") as fh:
            return {ln.strip() for ln in fh if ln.strip()}

    def add(self, key: str, sec: dict, arquivos: list[dict]) -> None:
        self.secoes.append(sec)
        self.arquivos.extend(arquivos)
        self.keys.append(key)
        if len(self.keys) >= self.lote:
            self.flush()

    def flush(self) -> None:
        if not self.keys:
            return
        self.n_part += 1
        lote = f"{self.prefix}-{self.n_part:05d}"
        for rows in (self.secoes, self.arquivos):
            for r in rows:
                r["_lote"] = lote
        for nome, rows, schema in (("secoes", self.secoes, SECOES_SCHEMA),
                                   ("arquivos", self.arquivos, ARQUIVOS_SCHEMA)):
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


# ---------------------------------------------------------------------------
# Auditoria de uma seção (executada no pool de processos)
# ---------------------------------------------------------------------------

def _votos_bu(raw: bytes, eleicao: int) -> tuple:
    from dataurnas.downloader.ele2026 import bu_to_rows

    _sec, votos = bu_to_rows(raw, eleicao=eleicao, cargo=CARGO_PRESIDENTE)
    return tuple(sorted((v["tipo_voto"], v["numero"] or 0, v["votos"] or 0) for v in votos))


def auditar_secao_2022(turno: int, ident: dict, arquivos: list[tuple],
                       esperado: Optional[tuple], no_banco: bool) -> dict:
    """Audita os arquivos de uma seção de 2022.

    arquivos: [(nome, bytes, crc32_hex, data_hora_zip)].
    Retorna {"secao", "linhas", "divergencias"}.
    """
    from dataurnas.analyzer import integrity as I
    from dataurnas.config import MODELOS_URNA

    sid = secao_id(turno, ident["uf"], ident["cd_mun"], ident["zona"], ident["secao"])
    meta = {nm: (crc, dh) for nm, _raw, crc, dh in arquivos}
    conjunto = {"token": None, "data_hora": "", "arquivos": [
        (Z.TIPO_POR_EXTENSAO.get(nm.rsplit(".", 1)[-1], nm.rsplit(".", 1)[-1]), nm, raw)
        for nm, raw, _crc, _dh in arquivos]}
    r = I.auditar_conjunto(ident, conjunto, sufixos_publicados=I.SUFIXOS_PUBLICADOS_V1,
                           fonte=FONTE)
    v = r["verificacao"] or {}
    assin_arq = v.get("assinaturas_arquivos") or {}
    linhas = []
    for ln in r["linhas"]:
        crc, dh = meta.get(ln["nome"], (None, None))
        linhas.append({
            "turno": turno, "uf": ln["uf"], "cd_mun": ln["cd_mun"], "zona": ln["zona"],
            "secao": ln["secao"], "tipo": ln["tipo"], "nome": ln["nome"],
            "tamanho": ln["tamanho"], "md5": ln["md5"], "sha256": ln["sha256"],
            "sha512": ln["sha512"], "sha512_assinado": ln["sha512_assinado"],
            "hash_confere": ln["hash_confere"],
            "assinatura_arquivo_valida": assin_arq.get(ln["nome"]),
            "crc32": crc, "data_hora_zip": dh,
        })
    divs = []
    for d in r["divergencias"]:
        d = {k: x for k, x in d.items() if k != "token_tse"}
        divs.append({"turno": turno, "secao_id": sid, **d})
    motivos: list[str] = []
    if r["verificacao"] is None:
        motivos.append("seção sem arquivo de assinatura (.vscmr) no pacote")
    else:
        motivos.extend(v["falhas"] + v["motivos"])
    votos_conferem = None
    if esperado is not None:
        raw_bu = next((raw for nm, raw, _c, _d in arquivos if nm.endswith(".bu")), None) \
            or next((raw for nm, raw, _c, _d in arquivos if nm.endswith(".busa")), None)
        if raw_bu is not None:
            try:
                votos_conferem = _votos_bu(raw_bu, ELEICOES[turno]) == esperado
            except Exception as e:  # noqa: BLE001 - BU ilegível vira motivo
                motivos.append(f"BU não decodificado: {e!r}"[:200])
            if votos_conferem is False:
                motivos.append("votos de Presidente do BU diferem do banco de 2022")
    cod = v.get("modelo_cod")
    validas = sum(1 for x in assin_arq.values() if x)
    secao = {
        "turno": turno, "secao_id": sid, **ident,
        "status_secao": "ok" if linhas else "sem_arquivos",
        "no_banco_2022": no_banco,
        "n_arquivos": len(linhas),
        "n_hash_confere": sum(1 for x in linhas if x["hash_confere"] is True),
        "n_hash_diverge": sum(1 for x in linhas if x["hash_confere"] is False),
        "n_sem_hash": sum(1 for x in linhas if x["hash_confere"] is None),
        "assinatura_valida": v.get("assinatura_valida") if r["verificacao"] else None,
        "assinatura_algoritmo": v.get("algoritmo"),
        "n_assinaturas_arquivos_validas": validas,
        "n_assinaturas_arquivos_invalidas": len(assin_arq) - validas,
        "cert_subject": v.get("cert_subject"), "cert_issuer": v.get("cert_issuer"),
        "cert_serial": v.get("cert_serial"), "cert_sha256": v.get("cert_sha256"),
        "modelo_urna": MODELOS_URNA.get(cod, f"Modelo_{cod}") if cod else None,
        "motivo": "; ".join(motivos)[:2000] or None,
        "votos_conferem": votos_conferem,
    }
    return {"secao": secao, "linhas": linhas, "divergencias": divs}


def auditar_bloco(turno: int, uf: str, buf: bytes, base: int, secoes: list) -> list[dict]:
    """Extrai e audita as seções de um bloco de bytes do zip.

    secoes: [(chave, [Entrada], esperado, no_banco)]. Uma seção com entrada
    corrompida volta com "erro" (o bloco é baixado de novo no próximo run).
    """
    out = []
    for (mun, zona, sec), entradas, esperado, no_banco in secoes:
        ident = {"uf": uf, "cd_mun": mun, "zona": zona, "secao": sec}
        try:
            arquivos = [(e.nome, Z.extrair(buf, base, e), f"{e.crc:08x}", e.data_hora)
                        for e in entradas]
        except ValueError as e:
            out.append({"ident": ident, "erro": str(e)})
            continue
        try:
            r = auditar_secao_2022(turno, ident, arquivos, esperado, no_banco)
        except Exception as e:  # noqa: BLE001 - registrado e refeito no próximo run
            out.append({"ident": ident, "erro": f"falha na auditoria: {e!r}"[:300]})
            continue
        r["ident"] = ident
        out.append(r)
    return out


# ---------------------------------------------------------------------------
# Banco de 2022: seções esperadas e votos de Presidente
# ---------------------------------------------------------------------------

def esperado_banco(turno: int, uf: str, base: Path, conferir_votos: bool
                   ) -> tuple[set[tuple], dict[tuple, tuple]]:
    """Seções do banco de 2022 (data/parquet/secoes.parquet) e votos de
    Presidente por seção (votos_t*.parquet), normalizados como no BU."""
    import duckdb

    sp = base / "secoes.parquet"
    if not sp.exists():
        return set(), {}
    prefixo = f"{turno}T/{uf.lower()}/"
    con = duckdb.connect()
    secoes = {(m, z, s) for m, z, s in con.execute(
        f"SELECT municipio, zona, secao FROM read_parquet('{sp}') "
        "WHERE starts_with(id, ?)", [prefixo]).fetchall()}
    votos: dict[tuple, list] = {}
    vps = sorted(base.glob(f"votos_t{turno}*.parquet"))
    if conferir_votos and vps:
        lista = ", ".join(f"'{p}'" for p in vps)
        for sid, tv, n, q in con.execute(
                f"SELECT secao_id, tipo_voto, codigo_candidato, quantidade "
                f"FROM read_parquet([{lista}]) WHERE starts_with(secao_id, ?) "
                f"AND codigo_cargo = ?", [prefixo, CARGO_PRESIDENTE]).fetchall():
            _t, _u, m, z, s = sid.split("/")
            votos.setdefault((m, z, s), []).append((tv, n or 0, q or 0))
    con.close()
    return secoes, {k: tuple(sorted(v)) for k, v in votos.items()}


# ---------------------------------------------------------------------------
# HTTP por faixas
# ---------------------------------------------------------------------------

class RangeFetcher:
    """GET com Range, taxa limitada (AIMD em 429), retentativas e backoff."""

    def __init__(self, taxa: float, paralelos: int, retries: int = 8, timeout: float = 120.0):
        import httpx

        from dataurnas.downloader.ele2026 import AdaptiveRate

        self._httpx = httpx
        taxa = min(taxa, TAXA_TETO)
        self.limiter = AdaptiveRate(taxa, taxa, rate_min=0.5)
        self.sem = asyncio.Semaphore(paralelos)
        self.retries = retries
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=20.0), http2=True,
            follow_redirects=True,
            limits=httpx.Limits(max_connections=paralelos + 1),
            headers={"User-Agent": "dataurnas-br/0.1 (auditoria academica)"})
        self.stats = {"ok": 0, "429": 0, "retry": 0, "fail": 0, "bytes": 0}

    async def close(self) -> None:
        await self.client.aclose()

    async def head(self, url: str) -> Optional[dict]:
        for attempt in range(self.retries):
            try:
                await self.limiter.acquire()
                r = await self.client.head(url)
                if r.status_code == 404:
                    return None
                r.raise_for_status()
                return {"tamanho": int(r.headers["content-length"]),
                        "last_modified": r.headers.get("last-modified"),
                        "etag": r.headers.get("etag")}
            except (self._httpx.HTTPError, OSError, KeyError, ValueError):
                self.stats["retry"] += 1
                await asyncio.sleep(min(60.0, 0.5 * 2 ** attempt) + random.random())
        raise RuntimeError(f"HEAD falhou após {self.retries} tentativas: {url}")

    async def faixa(self, url: str, ini: int, fim: int) -> bytes:
        """Bytes [ini, fim) do recurso; levanta exceção após as tentativas."""
        last: Optional[BaseException] = None
        for attempt in range(self.retries):
            pause = 0.0
            try:
                await self.limiter.acquire()
                async with self.sem:
                    r = await self.client.get(url, headers={"Range": f"bytes={ini}-{fim - 1}"})
                if r.status_code == 429:
                    self.stats["429"] += 1
                    pause = 5.0
                    self.limiter.throttled(pause)
                if r.status_code != 206:
                    raise self._httpx.HTTPStatusError(
                        f"HTTP {r.status_code} (esperado 206)", request=r.request, response=r)
                if len(r.content) != fim - ini:
                    raise ValueError(f"faixa com {len(r.content)} bytes, esperado {fim - ini}")
                self.stats["ok"] += 1
                self.stats["bytes"] += len(r.content)
                self.limiter.success()
                return r.content
            except (self._httpx.HTTPError, OSError, ValueError) as e:
                last = e
                self.stats["retry"] += 1
                await asyncio.sleep(max(pause, min(60.0, 0.5 * 2 ** attempt)) + random.random())
        self.stats["fail"] += 1
        raise RuntimeError(f"falha após {self.retries} tentativas: {url} [{ini},{fim}): {last!r}")


async def ler_entradas(f: RangeFetcher, url: str, tamanho: int) -> list[Z.Entrada]:
    cauda_ini = max(0, tamanho - 65536 - 22)
    cauda = await f.faixa(url, cauda_ini, tamanho)
    d, z64 = Z.localizar_diretorio(cauda, tamanho)
    if d is None:
        d = Z.parse_zip64_eocd(await f.faixa(url, z64, z64 + 56))
    cd = bytearray()
    passo = 32 << 20
    for ini in range(d.offset, d.offset + d.tamanho, passo):
        cd += await f.faixa(url, ini, min(d.offset + d.tamanho, ini + passo))
    entradas = Z.parse_diretorio(bytes(cd), d.offset)
    if len(entradas) != d.n_entradas:
        raise ValueError(f"diretório central com {len(entradas)} entradas, "
                         f"esperado {d.n_entradas}")
    return entradas


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------

def registrar_execucao(out: Path, evento: dict, nome: str = "execucoes.jsonl") -> None:
    with open(out / nome, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(evento, ensure_ascii=False) + "\n")


async def processar_pacote(args, f: RangeFetcher, pool: ProcessPoolExecutor, w: Writer,
                           divs: Jsonl, ocors: Jsonl, done: set[str], turno: int, uf: str,
                           erros: list[str], progresso: dict) -> None:
    out = Path(args.saida)
    url = Z.url_pacote_2022(turno, uf)
    info = await f.head(url)
    if info is None:
        ocors.registrar({"categoria": "pacote_indisponivel", "turno": turno, "uf": uf,
                         "url": url, "observacao": "HTTP 404 no zip da UF e turno"})
        erros.append(f"{turno}T/{uf}:pacote_404")
        return
    entradas = await ler_entradas(f, url, info["tamanho"])
    secoes, outros = Z.agrupar_secoes(entradas)
    registrar_execucao(out, {"turno": turno, "uf": uf, "url": url, **info,
                             "entradas": len(entradas), "secoes": len(secoes),
                             "fora_do_padrao": outros,
                             "consultado_em": time.strftime("%Y-%m-%dT%H:%M:%S")},
                       "pacotes.jsonl")
    for nm in outros:
        if nm.lower() != "leiame.pdf":
            ocors.registrar({"categoria": "entrada_fora_do_padrao", "turno": turno,
                             "uf": uf, "arquivo": nm, "url": url})
    pleito = PLEITOS[turno]
    for k, es in secoes.items():
        ps = {Z.parse_nome_v1(e.nome)["pleito"] for e in es}
        if ps != {pleito}:
            log.warning("seção %s/%s com pleito %s no nome (esperado %s)", uf, "/".join(k),
                        ps, pleito)
    banco, votos = (esperado_banco(turno, uf, Path(args.base_2022), args.conferir_votos)
                    if uf != "zz" else (set(), {}))
    pend = {k for k in secoes if secao_id(turno, uf, *k) not in done}
    blocos = [b for b in Z.montar_blocos(secoes, args.bloco_mb << 20)
              if any(k in pend for k in b[2])]
    log.info("pacote %dT %s: %d entradas, %d seções (%d no banco), %d pendentes em %d blocos, "
             "%.0f MB", turno, uf, len(entradas), len(secoes), len(banco), len(pend),
             len(blocos), info["tamanho"] / 1e6)
    q: asyncio.Queue = asyncio.Queue()
    for b in blocos:
        q.put_nowait(b)
    loop = asyncio.get_running_loop()

    async def baixar(ini: int, fim: int, ks: list) -> list[tuple[bytes, int, object]]:
        """[(bytes, offset, None)] com o bloco inteiro, ou, para seção com
        entradas espalhadas e faixa grande demais, [(bytes, offset, Entrada)]
        com uma faixa por entrada."""
        if len(ks) == 1 and fim - ini > 2 * (args.bloco_mb << 20):
            return [(await f.faixa(url, e.offset, e.fim), e.offset, e) for e in secoes[ks[0]]]
        return [(await f.faixa(url, ini, fim), ini, None)]

    async def worker():
        while True:
            try:
                ini, fim, ks = q.get_nowait()
            except asyncio.QueueEmpty:
                return
            ks = [k for k in ks if k in pend]
            payload = [(k, secoes[k], votos.get(k) if args.conferir_votos and k in banco
                        and k in votos else None, k in banco) for k in ks]
            try:
                faixas = await baixar(ini, fim, ks)
                if len(faixas) == 1 and faixas[0][2] is None:
                    res = await loop.run_in_executor(pool, auditar_bloco, turno, uf,
                                                     faixas[0][0], faixas[0][1], payload)
                else:
                    # seção espalhada: monta um buffer esparso por entrada
                    res = []
                    for k, _es, esp, nb in payload:
                        arquivos_ok = True
                        ident = {"uf": uf, "cd_mun": k[0], "zona": k[1], "secao": k[2]}
                        arqs = []
                        for p, o, e in faixas:
                            try:
                                arqs.append((e.nome, Z.extrair(p, o, e), f"{e.crc:08x}",
                                             e.data_hora))
                            except ValueError as ex:
                                res.append({"ident": ident, "erro": str(ex)})
                                arquivos_ok = False
                                break
                        if arquivos_ok:
                            r = await loop.run_in_executor(pool, auditar_secao_2022, turno,
                                                           ident, arqs, esp, nb)
                            r["ident"] = ident
                            res.append(r)
            except Exception as e:  # noqa: BLE001 - registrado e refeito no próximo run
                for k in ks:
                    erros.append(f"{secao_id(turno, uf, *k)}:{e!r}"[:300])
                log.warning("erro no bloco %dT %s [%d,%d): %r", turno, uf, ini, fim, e)
                continue
            for r in res:
                idt = r["ident"]
                sid = secao_id(turno, uf, idt["cd_mun"], idt["zona"], idt["secao"])
                if "erro" in r:
                    erros.append(f"{sid}:{r['erro']}"[:300])
                    log.warning("erro em %s: %s", sid, r["erro"])
                    if "CRC" in r["erro"] or "tamanho" in r["erro"]:
                        ocors.registrar({"categoria": "entrada_corrompida", "turno": turno,
                                         "secao_id": sid, **idt, "motivo": r["erro"],
                                         "url": url})
                    continue
                for d in r["divergencias"]:
                    divs.registrar({**d, "url_pacote": url})
                if not r["secao"]["no_banco_2022"] and uf != "zz":
                    ocors.registrar({"categoria": "secao_fora_do_banco", "turno": turno,
                                     "secao_id": sid, **idt, "url": url,
                                     "observacao": "seção presente no pacote do TSE e "
                                                   "ausente do banco de 2022"})
                w.add(sid, r["secao"], r["linhas"])
                progresso["n"] += 1
                if progresso["n"] % 2000 == 0:
                    el = time.time() - progresso["t0"]
                    log.info("progresso: %d seções em %.0fs (%.2f/s) | %d divergências | "
                             "%.1f GB baixados | http %s", progresso["n"], el,
                             progresso["n"] / el, divs.n, f.stats["bytes"] / 1e9, f.stats)

    await asyncio.gather(*[worker() for _ in range(args.paralelos)])
    # seções do banco de 2022 que não vieram no pacote
    for k in sorted(banco - set(secoes)):
        sid = secao_id(turno, uf, *k)
        if sid in done:
            continue
        idt = {"uf": uf, "cd_mun": k[0], "zona": k[1], "secao": k[2]}
        ocors.registrar({"categoria": "secao_sem_arquivos_no_pacote", "turno": turno,
                         "secao_id": sid, **idt, "url": url,
                         "observacao": "seção do banco de 2022 sem nenhum arquivo no pacote"})
        w.add(sid, {"turno": turno, "secao_id": sid, **idt, "status_secao": "ausente_pacote",
                    "no_banco_2022": True, "n_arquivos": 0, "n_hash_confere": 0,
                    "n_hash_diverge": 0, "n_sem_hash": 0,
                    "n_assinaturas_arquivos_validas": 0,
                    "n_assinaturas_arquivos_invalidas": 0,
                    "motivo": "seção sem arquivos no pacote de dados abertos"}, [])
    w.flush()


async def run(args: argparse.Namespace) -> int:
    out = Path(args.saida)
    out.mkdir(parents=True, exist_ok=True)
    w = Writer(out, args.lote)
    divs = Jsonl(out / "divergencias.jsonl", "DIVERGENCIA")
    ocors = Jsonl(out / "ocorrencias_publicacao.jsonl", "PUBLICACAO")
    done = w.done_keys()
    inicio = time.strftime("%Y-%m-%dT%H:%M:%S")
    registrar_execucao(out, {"inicio": inicio, "turnos": args.turnos, "ufs": args.ufs,
                             "pid": os.getpid()})
    log.info("checkpoint: %d seções já processadas", len(done))
    f = RangeFetcher(args.taxa, args.paralelos)
    pool = ProcessPoolExecutor(max_workers=args.workers, initializer=_init_worker,
                               initargs=(SRC,))
    erros: list[str] = []
    progresso = {"n": 0, "t0": time.time()}
    try:
        for turno in args.turnos:
            for uf in args.ufs:
                t_uf, n0, b0 = time.time(), progresso["n"], f.stats["bytes"]
                try:
                    await processar_pacote(args, f, pool, w, divs, ocors, done, turno, uf,
                                           erros, progresso)
                except Exception as e:  # noqa: BLE001 - pacote refeito no próximo run
                    erros.append(f"{turno}T/{uf}:{e!r}"[:300])
                    log.error("pacote %dT %s falhou: %r", turno, uf, e)
                    continue
                el = time.time() - t_uf
                log.info("pacote %dT %s concluído: %d seções em %.0fs (%.2f/s, %.1f MB/s)",
                         turno, uf, progresso["n"] - n0, el,
                         (progresso["n"] - n0) / el if el else 0,
                         (f.stats["bytes"] - b0) / 1e6 / el if el else 0)
    finally:
        w.flush()
        await f.close()
        pool.shutdown(wait=True)
        el = time.time() - progresso["t0"]
        registrar_execucao(out, {"inicio": inicio, "fim": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                 "secoes": progresso["n"], "segundos": round(el),
                                 "erros": len(erros), "divergencias": divs.n,
                                 "ocorrencias": ocors.n, "http": dict(f.stats)})
    log.info("fim: %d seções em %.0fs, %d erros, %d divergências, %d ocorrências, http %s",
             progresso["n"], el, len(erros), divs.n, ocors.n, f.stats)
    if erros:
        dst = out / f"erros-{w.prefix}.txt"
        dst.write_text("\n".join(erros) + "\n", encoding="utf-8")
        log.warning("erros gravados em %s; rode de novo para refazer", dst.name)
    if not args.sem_consolidar:
        consolidar(out, args.versao_catalogo)
    return 0 if not erros else 2


# ---------------------------------------------------------------------------
# Consolidação
# ---------------------------------------------------------------------------

def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for bloco in iter(lambda: fh.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def _escrever_catalogo(con, turno: int, uf: str, out: Path) -> list[Path]:
    """arquivos_t<turno>_<uf>.parquet; dividido em partes se passar de 90 MB."""
    base = f"arquivos_t{turno}_{uf}"
    for p in out.glob(f"{base}.parquet"):
        p.unlink()
    for p in out.glob(f"{base}_parte*.parquet"):
        p.unlink()
    dst = out / f"{base}.parquet"
    sel = (f"SELECT * EXCLUDE (_lote) FROM a WHERE turno = {int(turno)} AND uf = '{uf}' "
           "ORDER BY cd_mun, zona, secao, nome")
    con.execute(f"COPY ({sel}) TO '{dst}.tmp' (FORMAT PARQUET, COMPRESSION ZSTD)")
    tam = os.path.getsize(f"{dst}.tmp")
    if tam <= LIMITE_BYTES:
        os.replace(f"{dst}.tmp", dst)
        return [dst]
    os.remove(f"{dst}.tmp")
    n = con.execute(f"SELECT count(*) FROM a WHERE turno = {int(turno)} AND uf = '{uf}'"
                    ).fetchone()[0]
    partes = -(-tam // ALVO_PARTE)
    por = -(-n // partes)
    nomes = []
    for i in range(partes):
        p = out / f"{base}_parte{i + 1}.parquet"
        con.execute(f"COPY ({sel} LIMIT {por} OFFSET {i * por}) TO '{p}' "
                    "(FORMAT PARQUET, COMPRESSION ZSTD)")
        nomes.append(p)
    return nomes


def _ler_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines()
            if ln.strip()]


def _dedup(regs: list[dict], campos: tuple) -> list[dict]:
    vistos, out = set(), []
    for d in regs:
        k = tuple(d.get(c) for c in campos)
        if k not in vistos:
            vistos.add(k)
            out.append(d)
    return out


def consolidar(out: Path, versao_catalogo: Optional[str] = None) -> Optional[dict]:
    """Junta as partes (lote mais recente de cada seção) e grava secoes.parquet,
    os catálogos por turno e UF, catalogo_manifest.json e resumo.json."""
    import duckdb

    from dataurnas.analyzer import integrity as I

    parts = out / "parts"
    if not any(parts.glob("secoes-*.parquet")):
        log.warning("nenhuma parte para consolidar")
        return None
    con = duckdb.connect()
    con.execute(f"""
        CREATE TEMP TABLE s AS
        SELECT * FROM read_parquet('{parts / "secoes-*.parquet"}', union_by_name = true)
        QUALIFY row_number() OVER (PARTITION BY secao_id ORDER BY _lote DESC) = 1""")
    con.execute(f"""
        CREATE TEMP TABLE a AS
        SELECT x.* FROM read_parquet('{parts / "arquivos-*.parquet"}', union_by_name = true) x
        JOIN s USING (turno, uf, cd_mun, zona, secao, _lote)""")
    dst_s = out / "secoes.parquet"
    con.execute(f"""COPY (SELECT * EXCLUDE (_lote) FROM s ORDER BY turno, uf, cd_mun, zona, secao)
                    TO '{dst_s}.tmp' (FORMAT PARQUET, COMPRESSION ZSTD)""")
    os.replace(f"{dst_s}.tmp", dst_s)

    catalogo = []
    for turno, uf in con.execute("SELECT DISTINCT turno, uf FROM a ORDER BY 1, 2").fetchall():
        for p in _escrever_catalogo(con, turno, uf, out):
            meta = pq.ParquetFile(p).metadata
            catalogo.append({"arquivo": p.name, "turno": int(turno), "uf": uf,
                             "tamanho": p.stat().st_size, "sha256": _sha256(p),
                             "linhas": meta.num_rows,
                             "colunas": [c.name for c in meta.schema.to_arrow_schema()]})
    manifesto = {
        "descricao": "Catálogo de hashes por arquivo das urnas de 2022 (1º e 2º turnos), "
                     "um anexo por turno e UF.",
        "versao": versao_catalogo,
        "url_base": (f"https://github.com/alissonlinneker/DataUrnas-BR/releases/download/"
                     f"{versao_catalogo}" if versao_catalogo else None),
        "total_arquivos": len(catalogo),
        "total_bytes": sum(c["tamanho"] for c in catalogo),
        "total_linhas": sum(c["linhas"] for c in catalogo),
        "arquivos": catalogo,
    }
    (out / "catalogo_manifest.json").write_text(
        json.dumps(manifesto, ensure_ascii=False, indent=1), encoding="utf-8")

    cols = ["secoes", "ok", "ausente_pacote", "fora_do_banco", "arquivos", "hash_confere",
            "hash_diverge", "sem_hash", "assinatura_valida", "assinatura_invalida",
            "assinatura_nao_verificada", "assinaturas_arquivos_validas",
            "assinaturas_arquivos_invalidas", "votos_conferem", "votos_divergem",
            "votos_nao_conferidos"]
    agg = """count(*), count(*) FILTER (WHERE status_secao = 'ok'),
             count(*) FILTER (WHERE status_secao = 'ausente_pacote'),
             count(*) FILTER (WHERE NOT no_banco_2022),
             coalesce(sum(n_arquivos), 0), coalesce(sum(n_hash_confere), 0),
             coalesce(sum(n_hash_diverge), 0), coalesce(sum(n_sem_hash), 0),
             count(*) FILTER (WHERE assinatura_valida),
             count(*) FILTER (WHERE NOT assinatura_valida),
             count(*) FILTER (WHERE status_secao = 'ok' AND assinatura_valida IS NULL),
             coalesce(sum(n_assinaturas_arquivos_validas), 0),
             coalesce(sum(n_assinaturas_arquivos_invalidas), 0),
             count(*) FILTER (WHERE votos_conferem),
             count(*) FILTER (WHERE NOT votos_conferem),
             count(*) FILTER (WHERE status_secao = 'ok' AND votos_conferem IS NULL)"""
    por_turno: dict = {}
    for row in con.execute(f"SELECT turno, uf, {agg} FROM s GROUP BY 1, 2 ORDER BY 1, 2"
                           ).fetchall():
        t = f"{row[0]}T"
        por_turno.setdefault(t, {"por_uf": {}})["por_uf"][row[1]] = dict(
            zip(cols, [int(x) for x in row[2:]], strict=True))
    for d in por_turno.values():
        d["totais"] = {c: sum(v[c] for v in d["por_uf"].values()) for c in cols}
    totais = {c: sum(d["totais"][c] for d in por_turno.values()) for c in cols}

    def _contagem(sql: str) -> dict:
        res: dict = {}
        for t, k, n in con.execute(sql).fetchall():
            res.setdefault(f"{t}T", {})[str(k)] = int(n)
        return res

    algoritmos = _contagem("SELECT turno, assinatura_algoritmo, count(*) FROM s "
                           "WHERE status_secao = 'ok' GROUP BY 1, 2 ORDER BY 1, 3 DESC")
    modelos = _contagem("SELECT turno, modelo_urna, count(*) FROM s "
                        "WHERE status_secao = 'ok' GROUP BY 1, 2 ORDER BY 1, 2")
    emissores = _contagem("SELECT turno, cert_issuer, count(*) FROM s "
                          "WHERE status_secao = 'ok' GROUP BY 1, 2 ORDER BY 1, 3 DESC")
    por_tipo = {t: {"arquivos": int(n), "bytes": int(b or 0)} for t, n, b in con.execute(
        "SELECT tipo, count(*), sum(tamanho) FROM a GROUP BY 1 ORDER BY 1").fetchall()}

    divergencias = _dedup(_ler_jsonl(out / "divergencias.jsonl"),
                          ("secao_id", "arquivo", "categoria"))
    por_categoria = {c: sum(1 for d in divergencias if d.get("categoria") == c)
                     for c in I.CATEGORIAS_DIVERGENCIA}
    ocorrencias = _dedup(_ler_jsonl(out / "ocorrencias_publicacao.jsonl"),
                         ("categoria", "turno", "uf", "secao_id", "arquivo"))
    ocorr_cat = {c: sum(1 for d in ocorrencias if d.get("categoria") == c)
                 for c in CATEGORIAS_OCORRENCIA}
    pacotes = {}
    for p in _ler_jsonl(out / "pacotes.jsonl"):
        pacotes[p["url"]] = {k: p.get(k) for k in ("turno", "uf", "url", "tamanho",
                                                   "last_modified", "etag", "entradas",
                                                   "secoes", "fora_do_padrao",
                                                   "consultado_em")}
    feitas = Writer(out, 1).done_keys()
    pendentes = set()
    for ep in out.glob("erros-*.txt"):
        for ln in ep.read_text(encoding="utf-8").splitlines():
            k = ln.split(":", 1)[0].strip()
            if k and k not in feitas:
                pendentes.add(k)
    esperados = 2 * len(TODAS_UFS)
    completo = (len(pacotes) == esperados and not pendentes
                and ocorr_cat["pacote_indisponivel"] == 0)
    resumo = {
        "gerado_em": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "ciclo": ELE2022["ciclo"],
        "pleitos": {"1T": PLEITOS[1], "2T": PLEITOS[2]},
        "eleicoes": {"1T": ELEICOES[1], "2T": ELEICOES[2]},
        "datas": {"1T": DATAS[1], "2T": DATAS[2]},
        "fonte": {
            "descricao": "zips de arquivos de urna do portal de dados abertos do TSE, "
                         "lidos por faixas de bytes; a API de resultados não serve mais "
                         "os arquivos de 2022 (HTTP 404)",
            "url_padrao": Z.url_pacote_2022(1, "XX").replace("1t_XX", "<turno>t_<UF>"),
        },
        "metodo": {
            "hash_arquivo": "SHA-512 do arquivo publicado comparado ao hash da lista de "
                            "arquivos assinados no .vscmr (partes SW e HW).",
            "assinatura_hw": "ECDSA P-521 com SHA-512 (ou Ed521, se o certificado trouxer "
                             "a chave Ed521); a mensagem assinada é o hash SHA-512 do "
                             "arquivo. Verificados o autoAssinado (lista inteira) e cada "
                             "arquivo publicado. r e s vêm como INTEGER de 66 bytes "
                             "(BER não mínimo) e são recodificados em DER antes da "
                             "verificação.",
            "assinatura_sw": "CEPESC (algoritmo de governo não publicado): não verificada.",
            "cadeia_certificado": "não validada aqui; registramos subject, issuer, serial "
                                  "e SHA-256 do certificado da urna.",
            "crc32_zip": "CRC-32 de cada entrada do zip conferido na extração.",
            "votos": "votos de Presidente do BU comparados com data/parquet/votos_t*.parquet",
        },
        "completo": completo,
        "pacotes_processados": len(pacotes),
        "pacotes_esperados": esperados,
        "totais": totais,
        "por_turno": por_turno,
        "por_tipo_arquivo": por_tipo,
        "algoritmos_assinatura": algoritmos,
        "modelos_urna": modelos,
        "emissores_certificado": emissores,
        "arquivos_parquet": [c["arquivo"] for c in catalogo],
        "n_divergencias": len(divergencias),
        "divergencias_por_categoria": por_categoria,
        "divergencias": divergencias[:1000],
        "n_ocorrencias_publicacao": len(ocorrencias),
        "ocorrencias_por_categoria": ocorr_cat,
        "erros_pendentes": len(pendentes),
        "pacotes": sorted(pacotes.values(), key=lambda p: (p["turno"], p["uf"])),
        "execucoes": _ler_jsonl(out / "execucoes.jsonl"),
    }
    (out / "resumo.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=1),
                                     encoding="utf-8")
    log.info("consolidado: %d seções, %d catálogos, %d divergências, %d ocorrências, "
             "completo=%s", totais["secoes"], len(catalogo), len(divergencias),
             len(ocorrencias), completo)
    return resumo


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--turnos", default="1,2", help="turnos (padrão: 1,2)")
    ap.add_argument("--ufs", default=",".join(TODAS_UFS),
                    help="UFs separadas por vírgula (padrão: 27 UFs + zz)")
    ap.add_argument("--workers", type=int, default=3,
                    help="processos de hash e verificação (padrão: 3)")
    ap.add_argument("--paralelos", type=int, default=3,
                    help="blocos baixados ao mesmo tempo (padrão: 3)")
    ap.add_argument("--taxa", type=float, default=10.0,
                    help=f"requisições por segundo (padrão: 10, teto {TAXA_TETO:.0f})")
    ap.add_argument("--bloco-mb", type=int, default=8,
                    help="tamanho alvo de cada faixa baixada em MB (padrão: 8)")
    ap.add_argument("--lote", type=int, default=2000,
                    help="seções por parte Parquet gravada e anotada no checkpoint")
    ap.add_argument("--conferir-votos", action=argparse.BooleanOptionalAction, default=True,
                    help="confere os votos de Presidente do BU com o banco de 2022")
    ap.add_argument("--base-2022", default=str(PARQUET_DIR),
                    help="diretório com secoes.parquet e votos_t*.parquet de 2022")
    ap.add_argument("--saida", default=str(SAIDA_PADRAO),
                    help="diretório de saída (padrão: data/parquet/2022/integridade)")
    ap.add_argument("--log", default=str(ROOT / "data" / "ele2022_integridade.log"),
                    help="arquivo de log (padrão: data/ele2022_integridade.log)")
    ap.add_argument("--versao-catalogo", default=None,
                    help="versão do GitHub em que os catálogos serão anexados (manifesto)")
    ap.add_argument("--sem-consolidar", action="store_true")
    ap.add_argument("--so-consolidar", action="store_true")
    a = ap.parse_args(argv)
    a.turnos = [int(t) for t in a.turnos.split(",") if t.strip()]
    if any(t not in (1, 2) for t in a.turnos):
        ap.error("--turnos aceita 1 e 2")
    a.ufs = [u.strip().lower() for u in a.ufs.split(",") if u.strip()]
    a.taxa = min(a.taxa, TAXA_TETO)
    a.workers = max(1, min(a.workers, 3))
    return a


def configurar_log(path: str) -> None:
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    raiz = logging.getLogger()
    raiz.setLevel(logging.INFO)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(path, encoding="utf-8")
    fh.setFormatter(fmt)
    raiz.addHandler(fh)
    if sys.stderr.isatty():
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        raiz.addHandler(sh)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("hpack").setLevel(logging.WARNING)


if __name__ == "__main__":
    args = parse_args()
    configurar_log(args.log)
    if args.so_consolidar:
        consolidar(Path(args.saida), args.versao_catalogo)
        sys.exit(0)
    sys.exit(asyncio.run(run(args)))
