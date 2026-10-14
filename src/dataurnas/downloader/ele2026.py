"""Coleta de dados da eleição geral de 2026 (1º turno, Presidente).

Reúne as funções puras de transformação (testáveis sem rede) e um cliente
HTTP assíncrono enxuto, com retentativas e backoff exponencial.

Endpoints usados (base https://resultados.tse.jus.br/oficial):
  - {ciclo}/{eleicao}/config/mun-e{eleicao:06}-cm.json        lista de municípios
  - {ciclo}/{eleicao}/dados/{abr}/{abr}-c0001-e{eleicao}-u.json  resultado agregado
    (abr = br, uf ou uf+cd_mun)
  - {ciclo}/arquivo-urna/{pleito}/config/{uf}/{uf}-p{pleito}-cs.json  seções
  - {ciclo}/arquivo-urna/{pleito}/dados/{uf}/{mun}/{zona}/{secao}/...-aux.json
  - .../{hash}/{arquivo}-bu.dat (BU, ASN.1 spec v2) e -vota.vsc (assinatura)
"""

from __future__ import annotations

import asyncio
import logging
import random
from typing import Any, Iterable, Optional

from ..config import ELE2026, TSE_BASE_URL

logger = logging.getLogger(__name__)

CICLO = ELE2026["ciclo"]
PLEITO = ELE2026["pleito_1t"]
ELEICAO = ELE2026["eleicao_1t"]
CARGO = ELE2026["cargo_presidente"]

# Modelos de urna (enum ModeloEquipamento do spec de assinatura)
MODELOS = {9: "UE2009", 10: "UE2010", 11: "UE2011", 13: "UE2013",
           15: "UE2015", 20: "UE2020", 22: "UE2022"}


# ---------------------------------------------------------------------------
# Conversões básicas
# ---------------------------------------------------------------------------

def to_int(val: Any) -> Optional[int]:
    """Converte string numérica do TSE em int ('' e None viram None)."""
    if val is None:
        return None
    if isinstance(val, int):
        return val
    s = str(val).strip().replace(".", "")
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None


def to_float_br(val: Any) -> Optional[float]:
    """Converte número no formato brasileiro ('47,03') em float."""
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    if not s:
        return None
    try:
        return float(s.replace(".", "").replace(",", ".")) if "," in s else float(s)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# URLs
# ---------------------------------------------------------------------------

def url_resultado(abr: str, eleicao: str = ELEICAO, cargo: int = CARGO,
                  ciclo: str = CICLO) -> str:
    """URL do resultado agregado. abr = 'br', 'sp' ou 'sp71072' (uf + cd_mun)."""
    abr = abr.lower()
    uf = abr[:2]
    return (f"{TSE_BASE_URL}/{ciclo}/{eleicao}/dados/{uf}/"
            f"{abr}-c{cargo:04d}-e{int(eleicao):06d}-u.json")


def url_municipios(eleicao: str = ELEICAO, ciclo: str = CICLO) -> str:
    return f"{TSE_BASE_URL}/{ciclo}/{eleicao}/config/mun-e{int(eleicao):06d}-cm.json"


def url_secoes_uf(uf: str, pleito: str = PLEITO, ciclo: str = CICLO) -> str:
    uf = uf.lower()
    return (f"{TSE_BASE_URL}/{ciclo}/arquivo-urna/{pleito}/config/{uf}/"
            f"{uf}-p{int(pleito):06d}-cs.json")


def _secao_base(uf: str, mun: str, zona: str, secao: str,
                pleito: str = PLEITO, ciclo: str = CICLO) -> str:
    return (f"{TSE_BASE_URL}/{ciclo}/arquivo-urna/{pleito}/dados/"
            f"{uf.lower()}/{mun}/{zona}/{secao}")


def url_aux(uf: str, mun: str, zona: str, secao: str,
            pleito: str = PLEITO, ciclo: str = CICLO) -> str:
    uf = uf.lower()
    return (f"{_secao_base(uf, mun, zona, secao, pleito, ciclo)}/"
            f"p{int(pleito):06d}-{uf}-m{mun}-z{zona}-s{secao}-aux.json")


def url_arquivo(uf: str, mun: str, zona: str, secao: str, hash_val: str,
                nome: str, pleito: str = PLEITO, ciclo: str = CICLO) -> str:
    return f"{_secao_base(uf, mun, zona, secao, pleito, ciclo)}/{hash_val}/{nome}"


# ---------------------------------------------------------------------------
# Resultado agregado (JSON -u)
# ---------------------------------------------------------------------------

def iter_candidatos(d: dict) -> Iterable[dict]:
    """Itera os candidatos do primeiro cargo de um JSON de resultado,
    achatando agremiação (agr) > partido (par) > candidato (cand)."""
    cargos = d.get("carg") or []
    if not cargos:
        return
    for agr in cargos[0].get("agr", []):
        for par in agr.get("par", []):
            for cand in par.get("cand", []):
                yield agr, par, cand


def parse_candidatos(d: dict) -> list[dict]:
    """Linhas de candidatos (cadastro + votos) a partir do resultado nacional."""
    rows = []
    for agr, par, cand in iter_candidatos(d):
        vices = cand.get("vs") or []
        vice = vices[0] if vices else {}
        rows.append({
            "numero": to_int(cand.get("n")),
            "sq_candidato": cand.get("sqcand"),
            "nome": cand.get("nm"),
            "nome_urna": cand.get("nmu"),
            "data_nascimento": cand.get("dt"),
            "partido_numero": to_int(par.get("n")),
            "partido_sigla": par.get("sg"),
            "partido_nome": par.get("nm"),
            "federacao_numero": to_int(par.get("nfed")),
            "agremiacao_tipo": {"c": "coligacao", "i": "isolado", "f": "federacao"}.get(
                agr.get("tp", ""), agr.get("tp")),
            "agremiacao_nome": agr.get("nm"),
            "agremiacao_composicao": agr.get("com"),
            "vice_nome": vice.get("nm"),
            "vice_nome_urna": vice.get("nmu"),
            "vice_partido": vice.get("sgp"),
            "vice_sq_candidato": vice.get("sqcand"),
            "votos": to_int(cand.get("vap")) or 0,
            "pct_validos": to_float_br(cand.get("pvapn") or cand.get("pvap")),
            "situacao": cand.get("st"),
            "eleito": cand.get("e") == "s",
            "destinacao_voto": cand.get("dvt"),
            "ordem": to_int(cand.get("seq")),
        })
    rows.sort(key=lambda r: -r["votos"])
    return rows


def parse_totais(d: dict) -> dict:
    """Totais de seções, eleitorado e votos de um JSON de resultado."""
    s = d.get("s") or {}
    e = d.get("e") or {}
    v = d.get("v") or {}
    return {
        "secoes_total": to_int(s.get("ts")),
        "secoes_totalizadas": to_int(s.get("st")),
        "secoes_nao_totalizadas": to_int(s.get("snt")),
        "secoes_instaladas": to_int(s.get("si")),
        "secoes_nao_instaladas": to_int(s.get("sni")),
        "eleitorado": to_int(e.get("te")),
        "eleitorado_secoes_totalizadas": to_int(e.get("est")),
        "comparecimento": to_int(e.get("c")),
        "abstencao": to_int(e.get("a")),
        "pct_comparecimento": to_float_br(e.get("pcn") or e.get("pc")),
        "pct_abstencao": to_float_br(e.get("pan") or e.get("pa")),
        "votos_total": to_int(v.get("tv")),
        "votos_validos": to_int(v.get("vv")),
        "votos_nominais": to_int(v.get("vnom")),
        "votos_legenda": to_int(v.get("van")),
        "votos_brancos": to_int(v.get("vb")),
        "votos_nulos": to_int(v.get("vn")),
        "votos_nulos_tecnicos": to_int(v.get("vnt")),
        "votos_nulos_total": to_int(v.get("tvn")),
        "votos_anulados_apuracao_separada": to_int(v.get("vansj")),
        "pct_brancos": to_float_br(v.get("pvbn") or v.get("pvb")),
        "pct_nulos": to_float_br(v.get("ptvnn") or v.get("ptvn")),
        "data_totalizacao": d.get("dt"),
        "hora_totalizacao": d.get("ht"),
    }


def votos_por_candidato(d: dict) -> dict[int, int]:
    """Mapa número do candidato -> votos apurados."""
    out: dict[int, int] = {}
    for _agr, _par, cand in iter_candidatos(d):
        n = to_int(cand.get("n"))
        if n is not None:
            out[n] = to_int(cand.get("vap")) or 0
    return out


def resultado_row(d: dict, numeros: Iterable[int], **ident) -> dict:
    """Linha larga de resultado: identificação + totais + v_<numero> por candidato."""
    row = dict(ident)
    row.update(parse_totais(d))
    votos = votos_por_candidato(d)
    for n in numeros:
        row[f"v_{n}"] = votos.get(n, 0)
    return row


def iter_municipios(cm: dict) -> Iterable[dict]:
    """Itera municípios do arquivo mun-eXXXXXX-cm.json (inclui exterior 'zz')."""
    for abr in cm.get("abr", []):
        uf = abr.get("cd", "").lower()
        for mu in abr.get("mu", []):
            yield {
                "uf": uf,
                "cd_mun": mu.get("cd"),
                "cd_ibge": mu.get("cdi") or None,
                "nome": mu.get("nm"),
                "capital": mu.get("c") == "s",
                "zonas": ",".join(mu.get("z", [])),
            }


# ---------------------------------------------------------------------------
# Seções (arquivo-urna)
# ---------------------------------------------------------------------------

def iter_secoes_cs(cs: dict) -> Iterable[dict]:
    """Itera seções do arquivo de configuração -cs.json de uma UF.

    Seções com 'nsp' foram agregadas a outra seção (principal) e não tem
    arquivos próprios; 'nsa' lista as seções agregadas a uma principal.
    """
    for abr in cs.get("abr", []):
        uf = abr.get("cd", "").lower()
        for mu in abr.get("mu", []):
            for zon in mu.get("zon", []):
                for sec in zon.get("sec", []):
                    nsa = sec.get("nsa")
                    if isinstance(nsa, list):
                        nsa = ",".join(str(x) for x in nsa)
                    yield {
                        "uf": uf,
                        "cd_mun": mu.get("cd"),
                        "nm_mun": mu.get("nm"),
                        "zona": zon.get("cd"),
                        "secao": sec.get("ns"),
                        "secao_principal": sec.get("nsp"),
                        "secoes_agregadas": nsa,
                    }


def secao_key(uf: str, mun: str, zona: str, secao: str) -> str:
    return f"{uf.lower()}/{mun}/{zona}/{secao}"


def escolher_hash(aux: dict) -> Optional[dict]:
    """Escolhe o conjunto de arquivos válido no -aux.json.

    Preferencia: hash com st 'Totalizado'; senão o último hash não nulo.
    Retorna dict com hash, status, data/hora de recebimento, nomes por tipo
    e quantidade de hashes encontrados.
    """
    hashes = [h for h in (aux.get("hashes") or [])
              if h.get("hash") and h.get("hash") != "0"]
    if not hashes:
        return None
    tot = [h for h in hashes if str(h.get("st", "")).lower().startswith("totalizad")]
    h = tot[-1] if tot else hashes[-1]
    arquivos: dict[str, str] = {}
    for a in h.get("arq") or []:
        if isinstance(a, dict):
            arquivos[a.get("tp", "")] = a.get("nm", "")
    for nome in h.get("nmarq") or []:  # formato v1
        if nome.endswith((".bu", "-bu.dat")):
            arquivos.setdefault("bu", nome)
        elif nome.endswith((".busa", "-busa.dat")):
            arquivos.setdefault("busa", nome)
        elif nome.endswith((".vscmr", ".vsc")):
            arquivos.setdefault("vota", nome)
    return {
        "hash": h["hash"],
        "st_hash": h.get("st"),
        "dt_recebimento": h.get("dr"),
        "hr_recebimento": h.get("hr"),
        "arquivos": arquivos,
        "n_hashes": len(hashes),
        "st_secao": aux.get("st"),
    }


# ---------------------------------------------------------------------------
# Assinatura (-vota.vsc): modelo da urna
# ---------------------------------------------------------------------------

def _ber_tlv(b: bytes, i: int) -> tuple[int, int, int]:
    """Lê tag/len BER em b[i]; retorna (tag, inicio_conteudo, tamanho)."""
    tag = b[i]
    i += 1
    ln = b[i]
    i += 1
    if ln & 0x80:
        n = ln & 0x7F
        ln = int.from_bytes(b[i:i + n], "big")
        i += n
    return tag, i, ln


def modelo_from_vsc(raw: bytes) -> Optional[int]:
    """Extrai o código do modelo da urna de um arquivo -vota.vsc.

    Spec v2 publicado (2024): EntidadeAssinaturaEcourna começa com
    modeloEquipamento (ENUMERATED, tag 0x0a). Nos arquivos de 2026 o modelo
    vem num SEQUENCE ao final: SEQUENCE { assinaturaSW, assinaturaHW,
    SEQUENCE { ENUMERATED modelo, ENUMERATED algoritmo } }. Trata os dois.
    """
    try:
        tag, i, ln = _ber_tlv(raw, 0)
        if tag != 0x30:
            return None
        end = min(i + ln, len(raw))
        filhos = []
        while i < end:
            t, j, l2 = _ber_tlv(raw, i)
            filhos.append((t, j, l2))
            i = j + l2
        if filhos and filhos[0][0] == 0x0A:
            t, j, l2 = filhos[0]
            return int.from_bytes(raw[j:j + l2], "big")
        for t, j, l2 in reversed(filhos):
            if t == 0x30 and l2 <= 16:
                t2, k, l3 = _ber_tlv(raw, j)
                if t2 == 0x0A:
                    return int.from_bytes(raw[k:k + l3], "big")
    except (IndexError, ValueError):
        return None
    return None


# ---------------------------------------------------------------------------
# Boletim de Urna -> linhas
# ---------------------------------------------------------------------------

def bu_to_rows(raw: bytes, eleicao: int = int(ELEICAO), cargo: int = CARGO
               ) -> tuple[dict, list[dict]]:
    """Decodifica um BU (spec v2) com o parser do projeto e devolve
    (campos_da_secao, votos_do_cargo).

    Executado em processo separado (pool), por isso só recebe bytes.
    """
    from ..models import SpecVersion, TipoVoto
    from ..parsers.asn1_helper import decode_envelope
    from ..parsers.bu import BUParser

    try:
        spec = SpecVersion.V2
        env, bu = decode_envelope(raw, "EntidadeBoletimUrna", spec)
    except Exception:
        spec = SpecVersion.V1
        env, bu = decode_envelope(raw, "EntidadeBoletimUrna", spec)
    b = BUParser()._build_bu(env, bu, spec)

    det = bu.get("detalhamentoComparecimento") or {}
    ident = bu.get("identificacaoSecao") or {}
    carga_hist = bu.get("historicoCodigosCarga") or []
    sec: dict[str, Any] = {
        "spec_version": spec.value,
        "municipio_bu": b.municipio,
        "zona_bu": b.zona,
        "secao_bu": b.secao,
        "local_votacao": ident.get("local") if isinstance(ident, dict) else None,
        "data_hora_emissao": b.data_hora_emissao,
        "hora_abertura": b.hora_abertura,
        "hora_encerramento": b.hora_encerramento,
        "tipo_urna": b.tipo_urna,
        "versao_votacao": b.versao_votacao,
        "numero_interno_urna": b.numero_interno,
        "codigo_carga": b.codigo_carga or (carga_hist[-1] if carga_hist else None),
        "qtd_codigos_carga": len(carga_hist),
        "fase": str(env.get("fase")) if env.get("fase") is not None else None,
        "comparecimento_bu": bu.get("qtdEleitoresCompareceram"),
        "comp_sem_biometria": det.get("qtdEleitoresCompareceramSemBiometria"),
        "habilitados_biometria": det.get("qtdEleitoresHabilitadosPorBiometria"),
        "habilitados_biografia": det.get("qtdEleitoresHabilitadosPorBiografia"),
        "aptos": None, "aptos_secao": None, "aptos_tte": None,
        "comparecimento": None,
        "votos_nominais": 0, "votos_legenda": 0, "votos_brancos": 0,
        "votos_nulos": 0, "votos_total": 0, "tem_presidente": False,
    }
    votos: list[dict] = []
    for res in b.resultados_por_eleicao:
        if res.id_eleicao != eleicao:
            continue
        sec["aptos"] = res.eleitores_aptos
        sec["aptos_secao"] = res.eleitores_aptos_secao
        sec["aptos_tte"] = res.eleitores_aptos_tte
        for rc in res.resultados:
            if rc.codigo_cargo != cargo:
                continue
            sec["tem_presidente"] = True
            sec["comparecimento"] = rc.comparecimento
            for v in rc.votos:
                tipo = v.tipo_voto
                q = v.quantidade or 0
                sec["votos_total"] += q
                if tipo == TipoVoto.NOMINAL:
                    sec["votos_nominais"] += q
                elif tipo == TipoVoto.LEGENDA:
                    sec["votos_legenda"] += q
                elif tipo == TipoVoto.BRANCO:
                    sec["votos_brancos"] += q
                elif tipo == TipoVoto.NULO:
                    sec["votos_nulos"] += q
                votos.append({
                    "tipo_voto": tipo.value,
                    "numero": v.codigo_votavel,
                    "partido": v.partido,
                    "votos": q,
                })
    return sec, votos


# ---------------------------------------------------------------------------
# Cliente HTTP assíncrono
# ---------------------------------------------------------------------------

class AdaptiveRate:
    """Limitador de taxa AIMD: espaça requisições em 1/rate segundos, reduz a
    taxa (multiplicativo) ao receber 429 e aumenta devagar (aditivo) com sucesso."""

    def __init__(self, rate: float, rate_max: float, rate_min: float = 2.0,
                 step: float = 0.02, factor: float = 0.7):
        self.rate = rate
        self.rate_max = rate_max
        self.rate_min = rate_min
        self.step = step
        self.factor = factor
        self._next = 0.0
        self._last_cut = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        loop = asyncio.get_running_loop()
        async with self._lock:
            now = loop.time()
            t = max(now, self._next)
            self._next = t + 1.0 / self.rate
        if t > now:
            await asyncio.sleep(t - now)

    def success(self) -> None:
        self.rate = min(self.rate_max, self.rate + self.step)

    def throttled(self, pause: float = 2.0) -> None:
        loop = asyncio.get_running_loop()
        now = loop.time()
        if now - self._last_cut < 2.0:  # um corte por janela evita cascata
            return
        self._last_cut = now
        self.rate = max(self.rate_min, self.rate * self.factor)
        self._next = max(self._next, now + pause)


class HttpFetcher:
    """GET com limite de concorrência, taxa adaptativa (AIMD em 429),
    retentativas e backoff exponencial."""

    def __init__(self, concurrency: int = 16, retries: int = 8,
                 timeout: float = 30.0, http2: bool = True, connections: int = 1,
                 rate: Optional[float] = None, rate_max: Optional[float] = None):
        """connections > 1 abre vários clientes HTTP/2 usados em rodízio.
        rate (req/s) liga o limitador adaptativo; None desliga."""
        import httpx

        self._httpx = httpx
        self.sem = asyncio.Semaphore(concurrency)
        self.retries = retries
        self.limiter = AdaptiveRate(rate, rate_max or rate) if rate else None
        n = max(1, connections)
        per = max(1, concurrency // n)
        self.clients = [
            httpx.AsyncClient(
                timeout=httpx.Timeout(timeout, connect=20.0),
                limits=httpx.Limits(max_connections=per, max_keepalive_connections=per),
                http2=http2,
                follow_redirects=True,
                headers={"User-Agent": "dataurnas-br/0.1 (auditoria academica)"},
            )
            for _ in range(n)
        ]
        self._rr = 0
        self.stats = {"ok": 0, "404": 0, "429": 0, "retry": 0, "fail": 0, "bytes": 0}

    def _next_client(self):
        self._rr = (self._rr + 1) % len(self.clients)
        return self.clients[self._rr]

    async def close(self) -> None:
        for c in self.clients:
            await c.aclose()

    async def get(self, url: str) -> Optional[bytes]:
        """Retorna o corpo, None em 404, levanta exceção após esgotar tentativas."""
        last: Optional[BaseException] = None
        for attempt in range(self.retries):
            pause = 0.0
            try:
                if self.limiter:
                    await self.limiter.acquire()
                async with self.sem:
                    r = await self._next_client().get(url)
                if r.status_code == 404:
                    self.stats["404"] += 1
                    return None
                if r.status_code == 429:
                    self.stats["429"] += 1
                    ra = to_float_br(r.headers.get("retry-after")) or 0.0
                    pause = min(60.0, max(ra, 2.0))
                    if self.limiter:
                        self.limiter.throttled(pause)
                if r.status_code in (429, 500, 502, 503, 504, 403):
                    raise self._httpx.HTTPStatusError(
                        f"HTTP {r.status_code}", request=r.request, response=r)
                r.raise_for_status()
                self.stats["ok"] += 1
                self.stats["bytes"] += len(r.content)
                if self.limiter:
                    self.limiter.success()
                return r.content
            except (self._httpx.HTTPError, OSError) as e:
                last = e
                self.stats["retry"] += 1
                await asyncio.sleep(max(pause, min(60.0, 0.5 * 2 ** attempt))
                                    + random.random())
        self.stats["fail"] += 1
        raise RuntimeError(f"falha após {self.retries} tentativas: {url}: {last!r}")

    def rate_info(self) -> str:
        return f"{self.limiter.rate:.1f} req/s" if self.limiter else "sem limite"

    async def get_json(self, url: str) -> Optional[dict]:
        import json

        body = await self.get(url)
        return None if body is None else json.loads(body)
