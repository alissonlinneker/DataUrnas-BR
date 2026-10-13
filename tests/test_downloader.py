"""Testes do cliente HTTP e do gerenciador de downloads (sem rede)."""

import asyncio
from email.utils import format_datetime
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from dataurnas.downloader.client import (
    DownloadResult,
    TSEClient,
    TSEFetchError,
    parse_retry_after,
)
from dataurnas.downloader.manager import DownloadManager
from dataurnas.models import Section, UrnaMeta


class Sleeps:
    """Substitui asyncio.sleep e registra as esperas pedidas."""

    def __init__(self):
        self.calls: list[float] = []

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


def make_client(handler, sleeps=None, **kw) -> TSEClient:
    return TSEClient(
        rate_limit=10_000,
        transport=httpx.MockTransport(handler),
        sleep=sleeps or Sleeps(),
        **kw,
    )


def sequence(*responses):
    """Handler que devolve as respostas em ordem (exceções são levantadas)."""
    it = iter(responses)
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url)
        item = next(it)
        if isinstance(item, Exception):
            raise item
        return item

    handler.calls = calls
    return handler


# ---------------------------------------------------------------- fetch_json


async def test_fetch_json_ok():
    handler = sequence(httpx.Response(200, json={"a": 1}))
    async with make_client(handler) as c:
        assert await c.fetch_json("https://tse.test/x.json") == {"a": 1}


async def test_fetch_json_404_retorna_none_sem_retry():
    handler = sequence(httpx.Response(404))
    async with make_client(handler) as c:
        assert await c.fetch_json("https://tse.test/x.json") is None
    assert len(handler.calls) == 1


async def test_fetch_json_retry_em_5xx_com_backoff():
    sleeps = Sleeps()
    handler = sequence(
        httpx.Response(503),
        httpx.Response(502),
        httpx.Response(200, json=[1, 2]),
    )
    async with make_client(handler, sleeps, backoff_base=1.0, backoff_max=60.0) as c:
        assert await c.fetch_json("https://tse.test/x.json") == [1, 2]
    assert len(handler.calls) == 3
    assert len(sleeps.calls) == 2
    # jitter dentro de [teto/2, teto], teto = base * 2**tentativa
    assert 0.5 <= sleeps.calls[0] <= 1.0
    assert 1.0 <= sleeps.calls[1] <= 2.0


async def test_fetch_json_respeita_retry_after_em_429():
    sleeps = Sleeps()
    handler = sequence(
        httpx.Response(429, headers={"Retry-After": "7"}),
        httpx.Response(200, json={"ok": True}),
    )
    async with make_client(handler, sleeps) as c:
        assert await c.fetch_json("https://tse.test/x.json") == {"ok": True}
    assert sleeps.calls == [7.0]


async def test_fetch_json_retry_after_limitado_ao_teto():
    sleeps = Sleeps()
    handler = sequence(
        httpx.Response(503, headers={"Retry-After": "3600"}),
        httpx.Response(200, json={}),
    )
    async with make_client(handler, sleeps, backoff_max=30.0) as c:
        await c.fetch_json("https://tse.test/x.json")
    assert sleeps.calls == [30.0]


@pytest.mark.parametrize(
    "exc",
    [
        httpx.ConnectTimeout("t"),
        httpx.RemoteProtocolError("r"),
        httpx.ReadError("e"),
        httpx.PoolTimeout("p"),
    ],
)
async def test_fetch_json_retry_em_erro_de_transporte(exc):
    handler = sequence(exc, httpx.Response(200, json={"v": 1}))
    async with make_client(handler) as c:
        assert await c.fetch_json("https://tse.test/x.json") == {"v": 1}
    assert len(handler.calls) == 2


async def test_fetch_json_esgota_tentativas_levanta_erro():
    sleeps = Sleeps()
    handler = sequence(*[httpx.Response(500)] * 3)
    async with make_client(handler, sleeps, max_retries=3) as c:
        with pytest.raises(TSEFetchError):
            await c.fetch_json("https://tse.test/x.json")
    assert len(handler.calls) == 3
    assert len(sleeps.calls) == 2  # não dorme depois da última tentativa


async def test_fetch_json_4xx_nao_transitorio_nao_repete():
    handler = sequence(httpx.Response(403))
    async with make_client(handler) as c:
        with pytest.raises(httpx.HTTPStatusError):
            await c.fetch_json("https://tse.test/x.json")
    assert len(handler.calls) == 1


# ------------------------------------------------------------- download_file


async def test_download_file_escreve_atomicamente(tmp_path):
    dest = tmp_path / "a" / "arq.bu"
    handler = sequence(httpx.Response(200, content=b"conteudo"))
    async with make_client(handler) as c:
        res = await c.download_file("https://tse.test/arq.bu", dest)
    assert res is DownloadResult.DOWNLOADED
    assert dest.read_bytes() == b"conteudo"
    assert not (dest.parent / "arq.bu.part").exists()


async def test_download_file_existente_e_ignorado(tmp_path):
    dest = tmp_path / "arq.bu"
    dest.write_bytes(b"x")
    handler = sequence()  # qualquer requisição quebraria o teste
    async with make_client(handler) as c:
        res = await c.download_file("https://tse.test/arq.bu", dest)
    assert res is DownloadResult.SKIPPED
    assert handler.calls == []


async def test_download_file_404(tmp_path):
    dest = tmp_path / "arq.bu"
    async with make_client(sequence(httpx.Response(404))) as c:
        res = await c.download_file("https://tse.test/arq.bu", dest)
    assert res is DownloadResult.NOT_FOUND
    assert not res
    assert not dest.exists()


async def test_download_file_falha_no_meio_nao_deixa_parcial(tmp_path):
    dest = tmp_path / "arq.bu"

    class StreamQuebrado(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b"metade"
            raise httpx.ReadError("conexão caiu")

    handler = sequence(
        httpx.Response(200, stream=StreamQuebrado()),
        httpx.Response(200, content=b"completo"),
    )
    async with make_client(handler) as c:
        res = await c.download_file("https://tse.test/arq.bu", dest)
    assert res is DownloadResult.DOWNLOADED
    assert dest.read_bytes() == b"completo"
    assert not (tmp_path / "arq.bu.part").exists()


async def test_download_file_esgota_tentativas(tmp_path):
    dest = tmp_path / "arq.bu"
    handler = sequence(*[httpx.ConnectTimeout("t")] * 2)
    async with make_client(handler, max_retries=2) as c:
        res = await c.download_file("https://tse.test/arq.bu", dest)
    assert res is DownloadResult.FAILED
    assert not dest.exists()
    assert not (tmp_path / "arq.bu.part").exists()


async def test_download_file_cancelado_remove_parcial(tmp_path):
    dest = tmp_path / "arq.bu"

    class StreamCancelado(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b"parte"
            raise asyncio.CancelledError

    async with make_client(sequence(httpx.Response(200, stream=StreamCancelado()))) as c:
        with pytest.raises(asyncio.CancelledError):
            await c.download_file("https://tse.test/arq.bu", dest)
    assert not dest.exists()
    assert not (tmp_path / "arq.bu.part").exists()


# ------------------------------------------------------------ Retry-After


def test_parse_retry_after_segundos_e_data():
    assert parse_retry_after("12") == 12.0
    assert parse_retry_after(None) is None
    assert parse_retry_after("lixo") is None
    agora = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)
    futuro = format_datetime(agora + timedelta(seconds=40), usegmt=True)
    assert parse_retry_after(futuro, now=agora.timestamp()) == pytest.approx(40.0)


# ------------------------------------------------------------------ manager


class FakeApi:
    def build_file_url(self, ciclo, pleito, section, hash_, filename):
        return f"https://tse.test/{filename}"


async def test_manager_conta_baixados_ignorados_e_falhas(tmp_path):
    section = Section(
        uf="df", municipio_codigo="97012", municipio_nome="BRASILIA",
        zona="0001", secao="0001",
    )
    urna = UrnaMeta(
        section=section, hash="abc", status="Totalizado", data="", hora="",
        arquivos=["a.bu", "b.logjez", "c.vscmr"],
    )
    manager = DownloadManager(raw_dir=tmp_path, json_dir=tmp_path, max_concurrent=2)
    dest_dir = manager._section_dir(section)
    dest_dir.mkdir(parents=True)
    (dest_dir / "b.logjez").write_bytes(b"ja existe")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("a.bu"):
            return httpx.Response(200, content=b"bu")
        return httpx.Response(404)

    async with make_client(handler) as c:
        results = await manager.download_section_files(c, FakeApi(), "ele", "1", urna)

    assert results == {"ok": 1, "skip": 1, "fail": 1}
