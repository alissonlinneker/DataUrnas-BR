"""Cliente HTTP assíncrono para a API pública do TSE.

Recursos:
- rate limiting por token bucket;
- retry com backoff exponencial e jitter para falhas transitórias
  (5xx, 408, 429 e erros de transporte), respeitando ``Retry-After``;
- escrita atômica: o arquivo é gravado em ``<destino>.part`` e só então
  movido para o destino com ``os.replace``, de modo que um processo
  interrompido nunca deixa um arquivo parcial com o nome definitivo.

Os padrões de concorrência e taxa são conservadores (o servidor é de um
órgão público) e podem ser ajustados pelas variáveis de ambiente
``DATAURNAS_RATE_LIMIT`` (requisições por segundo) e
``DATAURNAS_MAX_CONCURRENT`` (downloads simultâneos, ver ``manager.py``).
"""

from __future__ import annotations

import asyncio
import email.utils
import enum
import importlib.util
import logging
import os
import random
import time
from collections.abc import Awaitable, Callable
from pathlib import Path

import httpx

from ..config import CONNECT_TIMEOUT, MAX_RETRIES, READ_TIMEOUT

logger = logging.getLogger(__name__)


def env_int(name: str, default: int) -> int:
    try:
        value = int(os.environ.get(name, default))
    except ValueError:
        logger.warning("Valor inválido em %s; usando %d", name, default)
        return default
    return value if value > 0 else default


#: Requisições por segundo, por cliente.
DEFAULT_RATE_LIMIT = env_int("DATAURNAS_RATE_LIMIT", 200)

#: Status HTTP considerados transitórios (vale a pena tentar de novo).
RETRYABLE_STATUS = frozenset({408, 425, 429, 500, 502, 503, 504})

#: Espera inicial e teto do backoff exponencial, em segundos.
BACKOFF_BASE = 1.0
BACKOFF_MAX = 60.0

_HTTP2_AVAILABLE = importlib.util.find_spec("h2") is not None


class DownloadResult(enum.Enum):
    """Resultado de ``TSEClient.download_file``."""

    DOWNLOADED = "downloaded"
    SKIPPED = "skipped"
    NOT_FOUND = "not_found"
    FAILED = "failed"

    @property
    def ok(self) -> bool:
        """Verdadeiro quando o arquivo está disponível no disco."""
        return self in (DownloadResult.DOWNLOADED, DownloadResult.SKIPPED)

    def __bool__(self) -> bool:  # compatibilidade com o retorno booleano antigo
        return self.ok


class TSEFetchError(RuntimeError):
    """Falha definitiva ao buscar um recurso (tentativas esgotadas)."""


class _RetryableStatus(Exception):
    def __init__(self, response: httpx.Response):
        super().__init__(f"HTTP {response.status_code}")
        self.response = response


class RateLimiter:
    """Rate limiter simples baseado em token bucket."""

    def __init__(self, rate: int = DEFAULT_RATE_LIMIT):
        self._rate = max(1, rate)
        self._tokens = float(self._rate)
        self._last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self):
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_refill
            self._tokens = min(self._rate, self._tokens + elapsed * self._rate)
            self._last_refill = now
            if self._tokens < 1:
                wait = (1 - self._tokens) / self._rate
                await asyncio.sleep(wait)
                self._last_refill = time.monotonic()
                self._tokens = 0
            else:
                self._tokens -= 1


def parse_retry_after(value: str | None, now: float | None = None) -> float | None:
    """Interpreta o cabeçalho ``Retry-After`` (segundos ou data HTTP)."""
    if not value:
        return None
    value = value.strip()
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        parsed = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None
    if parsed is None:
        return None
    reference = time.time() if now is None else now
    return max(0.0, parsed.timestamp() - reference)


class TSEClient:
    """Cliente HTTP para a API do TSE com retry e rate limiting."""

    def __init__(
        self,
        rate_limit: int = DEFAULT_RATE_LIMIT,
        *,
        max_retries: int = MAX_RETRIES,
        backoff_base: float = BACKOFF_BASE,
        backoff_max: float = BACKOFF_MAX,
        max_connections: int = 100,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] | None = None,
    ):
        self._rate_limiter = RateLimiter(rate_limit)
        self._client: httpx.AsyncClient | None = None
        self._max_retries = max(1, max_retries)
        self._backoff_base = backoff_base
        self._backoff_max = backoff_max
        self._max_connections = max_connections
        self._transport = transport
        self._sleep = sleep or asyncio.sleep

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(
                    connect=CONNECT_TIMEOUT,
                    read=READ_TIMEOUT,
                    write=READ_TIMEOUT,
                    pool=READ_TIMEOUT,
                ),
                limits=httpx.Limits(
                    max_connections=self._max_connections,
                    max_keepalive_connections=max(1, self._max_connections // 2),
                ),
                follow_redirects=True,
                # http2 exige o pacote opcional h2; sem ele o httpx falha ao criar o cliente.
                http2=_HTTP2_AVAILABLE and self._transport is None,
                transport=self._transport,
            )
        return self._client

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    def _backoff(self, attempt: int, retry_after: float | None = None) -> float:
        """Espera antes da próxima tentativa (backoff exponencial com jitter total)."""
        if retry_after is not None:
            return min(retry_after, self._backoff_max)
        ceiling = min(self._backoff_max, self._backoff_base * (2 ** attempt))
        return random.uniform(ceiling / 2, ceiling)

    async def _wait_retry(self, attempt: int, url: str, reason: str,
                          response: httpx.Response | None = None) -> None:
        retry_after = None
        if response is not None:
            retry_after = parse_retry_after(response.headers.get("Retry-After"))
        wait = self._backoff(attempt, retry_after)
        logger.warning(
            "%s em %s (tentativa %d/%d); nova tentativa em %.1fs",
            reason, url, attempt + 1, self._max_retries, wait,
        )
        await self._sleep(wait)

    async def fetch_json(self, url: str) -> dict | list | None:
        """Busca JSON da API do TSE.

        Retorna ``None`` apenas para 404. Status 4xx não transitórios
        propagam ``httpx.HTTPStatusError``; falhas transitórias que
        esgotam as tentativas levantam ``TSEFetchError``.
        """
        last_error: Exception | None = None
        for attempt in range(self._max_retries):
            await self._rate_limiter.acquire()
            response = None
            try:
                client = await self._get_client()
                response = await client.get(url)
                if response.status_code == 404:
                    logger.debug("404 para %s", url)
                    return None
                if response.status_code in RETRYABLE_STATUS:
                    raise _RetryableStatus(response)
                response.raise_for_status()
                return response.json()
            except _RetryableStatus as exc:
                last_error = exc
                reason = f"HTTP {exc.response.status_code}"
                response = exc.response
            except httpx.TransportError as exc:
                last_error = exc
                reason = f"Erro de transporte ({type(exc).__name__})"
            if attempt < self._max_retries - 1:
                await self._wait_retry(attempt, url, reason, response)
        raise TSEFetchError(
            f"Falha ao buscar {url} após {self._max_retries} tentativas: {last_error}"
        ) from last_error

    async def download_file(
        self, url: str, dest: Path, skip_existing: bool = True
    ) -> DownloadResult:
        """Baixa um arquivo do TSE para ``dest`` com escrita atômica.

        O conteúdo é gravado em ``<dest>.part`` e movido para ``dest`` com
        ``os.replace`` só depois de recebido por completo.
        """
        if skip_existing and dest.exists() and dest.stat().st_size > 0:
            logger.debug("Arquivo já existe: %s", dest)
            return DownloadResult.SKIPPED

        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_name(dest.name + ".part")

        for attempt in range(self._max_retries):
            await self._rate_limiter.acquire()
            response = None
            try:
                client = await self._get_client()
                async with client.stream("GET", url) as response:
                    if response.status_code == 404:
                        logger.debug("404 para %s", url)
                        return DownloadResult.NOT_FOUND
                    if response.status_code in RETRYABLE_STATUS:
                        raise _RetryableStatus(response)
                    if response.is_error:
                        logger.error("HTTP %d ao baixar %s", response.status_code, url)
                        return DownloadResult.FAILED
                    with open(tmp, "wb") as fh:
                        async for chunk in response.aiter_bytes(chunk_size=65536):
                            fh.write(chunk)
                        fh.flush()
                        os.fsync(fh.fileno())
                os.replace(tmp, dest)
                logger.debug("Baixado: %s -> %s", url, dest)
                return DownloadResult.DOWNLOADED
            except _RetryableStatus as exc:
                reason = f"HTTP {exc.response.status_code}"
                response = exc.response
            except httpx.TransportError as exc:
                reason = f"Erro de transporte ({type(exc).__name__})"
                response = None
            except BaseException:
                tmp.unlink(missing_ok=True)
                raise
            tmp.unlink(missing_ok=True)
            if attempt < self._max_retries - 1:
                await self._wait_retry(attempt, url, reason, response)

        logger.error("Tentativas esgotadas ao baixar %s", url)
        return DownloadResult.FAILED

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()
