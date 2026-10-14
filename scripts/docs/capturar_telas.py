#!/usr/bin/env python3
"""Captura telas do painel para o README (docs/assets/telas/).

Sobe o painel Streamlit em modo headless numa porta livre, abre o
``chrome-headless-shell`` do cache do Playwright e conversa com ele pelo
protocolo DevTools (CDP) usando ``websockets``, que já vem com o Streamlit. Não
precisa do pacote ``playwright`` em Python.

Telas geradas:

- ``2026-desktop.png`` (1440x900): página inicial, resultado de 2026.
- ``2026-mobile.png`` (390x844): a mesma página em tela de celular.
- ``2022-veredicto.png`` (1440x900): veredicto da auditoria de 2022.
- ``2022-benford.png`` (1440x900): Lei de Benford, 2022.

Navegador e painel são sempre encerrados pelo PID (bloco ``finally``), e o
perfil temporário do navegador é apagado. Ao fim, os PNG passam por limpeza de
metadados (``exiftool`` e ``xattr``, quando disponíveis).

O script pode ser executado de novo a qualquer momento, por exemplo quando a
coleta seção a seção de 2026 terminar.

Uso:
    python scripts/docs/capturar_telas.py
    python scripts/docs/capturar_telas.py --only 2026-desktop 2026-mobile
    python scripts/docs/capturar_telas.py --chrome /caminho/chrome-headless-shell
"""

from __future__ import annotations

import argparse
import base64
import glob
import io
import itertools
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from websockets.sync.client import connect

ROOT = Path(__file__).resolve().parents[2]
SAIDA = ROOT / "docs" / "assets" / "telas"
APP = ROOT / "src" / "dataurnas" / "dashboard" / "app.py"
LIMITE_BYTES = 400 * 1024
FLAGS_CHROME = [
    "--headless",
    "--mute-audio",
    "--use-angle=metal",
    "--enable-gpu",
    "--ignore-gpu-blocklist",
    "--hide-scrollbars",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-extensions",
    "--disable-background-networking",
    "--lang=pt-BR",
]


@dataclass(frozen=True)
class Tela:
    nome: str
    caminho: str
    largura: int
    altura: int
    movel: bool = False
    # Barra lateral recolhida dá mais largura ao conteúdo (cartões de KPI)
    recolher_lateral: bool = True


TELAS = [
    # A página de 2026 é a padrão do st.navigation e responde na raiz
    Tela("2026-desktop", "/", 1440, 900),
    Tela("2026-mobile", "/", 390, 844, movel=True),
    Tela("2022-veredicto", "/veredicto", 1440, 900),
    Tela("2022-benford", "/benford", 1440, 900),
]

# Painel pronto: sem indicador de execução, sem spinners/esqueletos, com o
# conteúdo principal montado e todos os gráficos Plotly já desenhados.
JS_PRONTO = """
(() => {
  const main = document.querySelector('[data-testid="stMain"], section.main');
  if (!main || main.innerText.trim().length < 40) return 'sem-conteudo';
  const status = document.querySelector('[data-testid="stStatusWidget"]');
  if (status && status.innerText.trim().length) return 'executando';
  if (document.querySelector('[data-testid="stSpinner"], [data-testid="stSkeleton"]'))
    return 'carregando';
  const graficos = [...document.querySelectorAll('.js-plotly-plot')];
  if (graficos.some(g => !g.querySelector('.main-svg'))) return 'graficos';
  return 'ok:' + graficos.length + ':' + main.innerText.length;
})()
"""

JS_RECOLHER = """
(() => {
  const lateral = document.querySelector('[data-testid="stSidebar"]');
  if (!lateral || lateral.getAttribute('aria-expanded') === 'false') return false;
  const botao = document.querySelector(
    '[data-testid="stSidebarCollapseButton"] button, [data-testid="stSidebarHeader"] button');
  if (!botao) return false;
  botao.click();
  return true;
})()
"""

JS_FECHAR_AVISOS = """
document.querySelectorAll('[role="dialog"] button[aria-label="Close"]').forEach(b => b.click())
"""


# ----------------------------------------------------------------------
# Processos
# ----------------------------------------------------------------------
def porta_livre() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def esperar_http(url: str, timeout: float) -> None:
    limite = time.monotonic() + timeout
    while time.monotonic() < limite:
        try:
            with urllib.request.urlopen(url, timeout=3) as r:  # noqa: S310 (localhost)
                if r.status == 200:
                    return
        except OSError:
            pass
        time.sleep(0.5)
    raise TimeoutError(f"{url} não respondeu em {timeout:.0f}s")


def iniciar_streamlit(porta: int, log: Path) -> subprocess.Popen:
    streamlit = Path(sys.executable).with_name("streamlit")
    cmd = [str(streamlit) if streamlit.exists() else "streamlit", "run", str(APP),
           "--server.headless=true", f"--server.port={porta}", "--server.address=127.0.0.1",
           "--browser.gatherUsageStats=false", "--client.toolbarMode=viewer",
           "--theme.base=light"]
    fh = log.open("w")
    return subprocess.Popen(cmd, cwd=ROOT, stdout=fh, stderr=subprocess.STDOUT,
                            start_new_session=True)


def localizar_chrome(explicito: str | None) -> str:
    if explicito:
        return explicito
    cache = Path.home() / "Library" / "Caches" / "ms-playwright"
    if not cache.exists():
        cache = Path.home() / ".cache" / "ms-playwright"
    candidatos = sorted(glob.glob(str(cache / "chromium_headless_shell-*" / "*" /
                                      "chrome-headless-shell")), reverse=True)
    if not candidatos:
        raise FileNotFoundError("chrome-headless-shell não encontrado no cache do Playwright; "
                                "instale com `npx playwright install chromium-headless-shell` "
                                "ou informe --chrome")
    return candidatos[0]


def iniciar_chrome(binario: str, perfil: Path) -> tuple[subprocess.Popen, str]:
    cmd = [binario, *FLAGS_CHROME, "--remote-debugging-port=0",
           f"--user-data-dir={perfil}", "about:blank"]
    proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                            start_new_session=True)
    arquivo = perfil / "DevToolsActivePort"
    limite = time.monotonic() + 30
    while time.monotonic() < limite:
        if arquivo.exists() and arquivo.read_text().strip():
            porta = arquivo.read_text().split()[0]
            return proc, f"http://127.0.0.1:{porta}"
        if proc.poll() is not None:
            raise RuntimeError("chrome-headless-shell encerrou ao iniciar")
        time.sleep(0.2)
    raise TimeoutError("chrome-headless-shell não abriu a porta de depuração")


def encerrar(proc: subprocess.Popen | None, nome: str) -> None:
    """Encerra pelo PID (grupo de processos criado por start_new_session)."""
    if proc is None or proc.poll() is not None:
        return
    for sinal, espera in ((signal.SIGTERM, 10), (signal.SIGKILL, 5)):
        try:
            os.killpg(proc.pid, sinal)
        except ProcessLookupError:
            return
        try:
            proc.wait(timeout=espera)
            return
        except subprocess.TimeoutExpired:
            continue
    print(f"aviso: {nome} (PID {proc.pid}) não encerrou", file=sys.stderr)


# ----------------------------------------------------------------------
# CDP
# ----------------------------------------------------------------------
class Pagina:
    def __init__(self, ws) -> None:
        self.ws = ws
        self.ids = itertools.count(1)

    def cmd(self, metodo: str, timeout: float = 60, **params) -> dict:
        mid = next(self.ids)
        self.ws.send(json.dumps({"id": mid, "method": metodo, "params": params}))
        limite = time.monotonic() + timeout
        while True:
            resto = limite - time.monotonic()
            if resto <= 0:
                raise TimeoutError(metodo)
            msg = json.loads(self.ws.recv(timeout=resto))
            if msg.get("id") == mid:
                if "error" in msg:
                    raise RuntimeError(f"{metodo}: {msg['error']}")
                return msg.get("result", {})

    def avaliar(self, expressao: str):
        r = self.cmd("Runtime.evaluate", expression=expressao, returnByValue=True)
        return r.get("result", {}).get("value")



def nova_pagina(base_cdp: str) -> str:
    """Abre uma aba e devolve o endereço WebSocket dela."""
    req = urllib.request.Request(f"{base_cdp}/json/new?about:blank", method="PUT")
    with urllib.request.urlopen(req, timeout=10) as r:  # noqa: S310 (localhost)
        return json.load(r)["webSocketDebuggerUrl"]


def fechar_navegador(base_cdp: str) -> None:
    with urllib.request.urlopen(f"{base_cdp}/json/version", timeout=5) as r:  # noqa: S310
        ws_url = json.load(r)["webSocketDebuggerUrl"]
    with connect(ws_url, open_timeout=5) as ws:
        ws.send(json.dumps({"id": 1, "method": "Browser.close"}))


def esperar_pronto(pag: Pagina, timeout: float) -> str:
    """Espera o painel ficar estável: mesmo estado 'ok' em 3 leituras seguidas."""
    limite = time.monotonic() + timeout
    anterior, iguais, estado = None, 0, ""
    while time.monotonic() < limite:
        estado = str(pag.avaliar(JS_PRONTO))
        if estado.startswith("ok"):
            iguais = iguais + 1 if estado == anterior else 1
            if iguais >= 3:
                return estado
        else:
            iguais = 0
        anterior = estado
        time.sleep(1.0)
    raise TimeoutError(f"painel não estabilizou (último estado: {estado})")


def capturar(pag: Pagina, base: str, tela: Tela, timeout: float) -> bytes:
    pag.cmd("Emulation.setDeviceMetricsOverride", width=tela.largura, height=tela.altura,
            deviceScaleFactor=2 if tela.movel else 1, mobile=tela.movel)
    pag.cmd("Emulation.setTouchEmulationEnabled", enabled=tela.movel)
    pag.cmd("Emulation.setEmulatedMedia", features=[{"name": "prefers-color-scheme",
                                                     "value": "light"}])
    pag.cmd("Page.navigate", url=base + tela.caminho)
    time.sleep(2)
    estado = esperar_pronto(pag, timeout)
    pag.avaliar(JS_FECHAR_AVISOS)
    if tela.recolher_lateral and not tela.movel and pag.avaliar(JS_RECOLHER):
        time.sleep(1.5)
        estado = esperar_pronto(pag, timeout)
    # Gráficos Plotly animam a entrada; um respiro evita capturar no meio
    pag.avaliar("window.scrollTo(0, 0)")
    time.sleep(2.5)
    print(f"  {tela.nome}: pronto ({estado})")
    r = pag.cmd("Page.captureScreenshot", format="png", captureBeyondViewport=False)
    return base64.b64decode(r["data"])


# ----------------------------------------------------------------------
# Pós-processamento
# ----------------------------------------------------------------------
def gravar_png(dados: bytes, destino: Path) -> None:
    """Grava o PNG; se passar do limite, reduz a paleta (Pillow) ou otimiza (oxipng/pngquant)."""
    destino.write_bytes(dados)
    if destino.stat().st_size <= LIMITE_BYTES:
        return
    if shutil.which("pngquant"):
        subprocess.run(["pngquant", "--force", "--skip-if-larger", "--quality=70-95",
                        "--output", str(destino), str(destino)], check=False)
    elif shutil.which("oxipng"):
        subprocess.run(["oxipng", "-o", "4", "--strip", "all", str(destino)], check=False)
    else:
        try:
            from PIL import Image
        except ImportError:
            return
        img = Image.open(io.BytesIO(dados)).convert("RGB")
        img.quantize(colors=256, method=Image.Quantize.MEDIANCUT,
                     dither=Image.Dither.FLOYDSTEINBERG).save(destino, optimize=True)


def limpar_metadados(arquivos: list[Path]) -> None:
    if not arquivos:
        return
    if shutil.which("exiftool"):
        subprocess.run(["exiftool", "-q", "-all=", "-overwrite_original", *map(str, arquivos)],
                       check=False)
    else:
        print("aviso: exiftool não encontrado; metadados não removidos", file=sys.stderr)
    if shutil.which("xattr"):
        for f in arquivos:
            subprocess.run(["xattr", "-c", str(f)], check=False)


# ----------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--only", nargs="*", choices=[t.nome for t in TELAS], help="capturar só estas")
    ap.add_argument("--chrome", help="caminho do chrome-headless-shell")
    ap.add_argument("--timeout", type=float, default=300, help="espera máxima por tela (s)")
    args = ap.parse_args()
    telas = [t for t in TELAS if not args.only or t.nome in args.only]

    SAIDA.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="dataurnas-telas-"))
    perfil = tmp / "perfil"
    perfil.mkdir()
    porta = porta_livre()
    base = f"http://127.0.0.1:{porta}"
    painel = navegador = None
    base_cdp = None
    gerados: list[Path] = []
    try:
        print(f"Subindo o painel em {base} ...")
        painel = iniciar_streamlit(porta, tmp / "streamlit.log")
        esperar_http(f"{base}/_stcore/health", timeout=120)
        navegador, base_cdp = iniciar_chrome(localizar_chrome(args.chrome), perfil)
        with connect(nova_pagina(base_cdp), max_size=64 * 1024 * 1024, open_timeout=15) as ws:
            pag = Pagina(ws)
            pag.cmd("Page.enable")
            pag.cmd("Runtime.enable")
            for tela in telas:
                destino = SAIDA / f"{tela.nome}.png"
                gravar_png(capturar(pag, base, tela, args.timeout), destino)
                gerados.append(destino)
    except Exception as exc:  # noqa: BLE001
        log = tmp / "streamlit.log"
        if log.exists():
            print("--- final do log do Streamlit ---", file=sys.stderr)
            print("\n".join(log.read_text(errors="replace").splitlines()[-30:]), file=sys.stderr)
        print(f"erro: {exc}", file=sys.stderr)
        return 1
    finally:
        if base_cdp and navegador and navegador.poll() is None:
            try:
                fechar_navegador(base_cdp)
                navegador.wait(timeout=10)
            except Exception:  # noqa: BLE001
                pass
        encerrar(navegador, "chrome-headless-shell")
        encerrar(painel, "streamlit")
        shutil.rmtree(tmp, ignore_errors=True)
        limpar_metadados(gerados)

    for f in gerados:
        print(f"  {f.relative_to(ROOT)} ({f.stat().st_size / 1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
