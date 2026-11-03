#!/usr/bin/env python3
"""Gera as ilustrações estáticas (SVG) usadas no README a partir dos dados reais.

Não usa bibliotecas de gráficos: o SVG é escrito à mão, o que mantém o arquivo
pequeno, legível no GitHub (temas claro e escuro, graças ao cartão de fundo
opaco) e sem dependências novas.

Saídas em ``docs/assets/``:

- ``2026-ranking.svg``: votos e percentual dos válidos de cada candidato.
- ``2026-mapa-lider.svg``: UF colorida pelo candidato mais votado.
- ``2026-comparecimento.svg``: comparecimento por UF, 1º turno de 2022 x 2026.
- ``2022-cobertura.svg``: cobertura da auditoria de 2022 e ocorrências por severidade.
- ``arquitetura.svg``: fluxo do projeto, da API do TSE ao painel.
- ``2026-t2-resultado.svg``: resultado nacional do 2º turno de 2026.
- ``2026-t2-mapa-lider.svg``: UF colorida pelo candidato mais votado no 2º turno.
- ``2026-t2-comparecimento.svg``: comparecimento por UF, 1º x 2º turno de 2026.
- ``2026-t2-integridade.svg``: assinaturas, hashes e recontagem do RDV no 2º turno.
- ``2026-veredicto.svg``: o que foi verificado e o que não pode ser verificado.
- ``banner.svg`` e ``banner.png``: capa do README.
- ``social-preview.png``: capa do repositório no GitHub (1280x640).

Uso:
    python scripts/docs/gerar_ilustracoes.py            # gera todas
    python scripts/docs/gerar_ilustracoes.py --png DIR  # também rasteriza em DIR
                                                         # (requer rsvg-convert)

Os PNG de capa (banner e social preview) exigem ``rsvg-convert``; os metadados
são removidos com ``exiftool`` quando ele está instalado.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import duckdb  # noqa: E402
import pandas as pd  # noqa: E402

from dataurnas.dashboard.data2026 import (  # noqa: E402
    UF_EXTERIOR,
    UF_NOMES,
    compare_2022_2026,
    load_2022_t1_by_uf,
    load_candidatos,
    load_resultado_uf,
    load_resumo,
)

ASSETS = ROOT / "docs" / "assets"
PARQUET = ROOT / "data" / "parquet"
GEOJSON = ROOT / "src" / "dataurnas" / "dashboard" / "assets" / "brasil-uf.geojson"

# Identidade visual (Okabe-Ito, segura para daltonismo)
NAVY = "#0B3A5B"
BLUE = "#0072B2"
LIGHT_BLUE = "#56B4E9"
GREEN = "#009E73"
ORANGE = "#E69F00"
INK = "#0B3A5B"
MUTED = "#4F6B80"
GRID = "#D9E3EB"
CARD = "#FFFFFF"
CARD_STROKE = "#CBD8E3"
SOFT = "#F2F6F9"
FONT = "Inter, 'Helvetica Neue', Helvetica, Arial, sans-serif"

FONTE_2026 = "Fonte: TSE, resultados oficiais do 1º turno de 2026"
FONTE_2022 = "Fonte: TSE, arquivos de urna das eleições de 2022 (compilação DataUrnas-BR)"
FONTE_2026_T2 = "Fonte: TSE, resultados oficiais do 2º turno de 2026"

DIR_2026 = PARQUET / "2026"
DIR_2026_T2 = DIR_2026 / "t2"


# ----------------------------------------------------------------------
# Formatação pt-BR
# ----------------------------------------------------------------------
def fmt_int(n: float) -> str:
    return f"{int(round(n)):,}".replace(",", ".")


def fmt_pct(x: float, casas: int = 2) -> str:
    return f"{x:.{casas}f}".replace(".", ",") + "%"


def fmt_num(x: float, casas: int = 1) -> str:
    return f"{x:.{casas}f}".replace(".", ",")


_MINUSCULAS = {"da", "de", "do", "das", "dos", "e"}


# Prenomes que o TSE publica sem acento e cuja grafia é inequívoca (mesmo critério do README)
_ACENTOS = {"flavio": "flávio"}


def nome_proprio(nome: str) -> str:
    partes = [_ACENTOS.get(p, p) for p in nome.lower().split()]
    return " ".join(p if p in _MINUSCULAS and i else p.capitalize() for i, p in enumerate(partes))


def largura_texto(texto: str, tamanho: float, negrito: bool = False) -> float:
    """Largura aproximada do texto (métrica média de Inter/Helvetica)."""
    total = 0.0
    for ch in texto:
        if ch in "il.,:;|!'":
            total += 0.28
        elif ch in " ":
            total += 0.28
        elif ch in "mwMW":
            total += 0.86
        elif ch.isupper():
            total += 0.68
        elif ch.isdigit():
            total += 0.56
        else:
            total += 0.53
    return total * tamanho * (1.06 if negrito else 1.0)


# ----------------------------------------------------------------------
# Primitivas SVG
# ----------------------------------------------------------------------
def text(x: float, y: float, conteudo: str, size: float = 14, weight: int = 400,
         fill: str = INK, anchor: str = "start", extra: str = "") -> str:
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" font-weight="{weight}" '
            f'fill="{fill}" text-anchor="{anchor}"{extra}>{escape(conteudo)}</text>')


def rect(x: float, y: float, w: float, h: float, fill: str, rx: float = 0, extra: str = "") -> str:
    return (f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(w, 0):.1f}" height="{h:.1f}" '
            f'rx="{rx}" fill="{fill}"{extra}/>')


def documento(largura: int, altura: int, titulo: str, descricao: str, corpo: list[str],
              subtitulo: str = "", fonte: str = "") -> str:
    """Cartão com título, subtítulo, corpo e linha de fonte."""
    partes = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{largura}" height="{altura}" '
        f'viewBox="0 0 {largura} {altura}" role="img" aria-labelledby="titulo descricao">',
        f'<title id="titulo">{escape(titulo)}</title>',
        f'<desc id="descricao">{escape(descricao)}</desc>',
        f'<rect x="1" y="1" width="{largura - 2}" height="{altura - 2}" rx="18" fill="{CARD}" '
        f'stroke="{CARD_STROKE}" stroke-width="1.5"/>',
        f'<g font-family="{FONT}">',
        rect(32, 30, 6, 30 if subtitulo else 24, ORANGE, rx=3),
        text(50, 50, titulo, size=22, weight=700),
    ]
    if subtitulo:
        partes.append(text(50, 74, subtitulo, size=14, fill=MUTED))
    partes.extend(corpo)
    if fonte:
        partes.append(f'<line x1="32" y1="{altura - 46}" x2="{largura - 32}" y2="{altura - 46}" '
                      f'stroke="{GRID}" stroke-width="1"/>')
        partes.append(text(32, altura - 22, fonte, size=12.5, fill=MUTED))
        partes.append(text(largura - 32, altura - 22, "DataUrnas-BR", size=12.5, weight=700,
                           fill=NAVY, anchor="end"))
    partes.append("</g></svg>")
    return "\n".join(partes) + "\n"


def salvar(nome: str, conteudo: str) -> Path:
    destino = ASSETS / nome
    destino.write_text(conteudo, encoding="utf-8")
    print(f"  {destino.relative_to(ROOT)} ({destino.stat().st_size / 1024:.1f} KB)")
    return destino


# ----------------------------------------------------------------------
# a) Ranking de candidatos
# ----------------------------------------------------------------------
def ranking() -> str:
    cand = load_candidatos().sort_values("votos", ascending=False).reset_index(drop=True)
    resumo = load_resumo()
    validos = int(resumo["totais"]["votos_validos"])
    W = 1000
    top = 112
    linha = 38
    rotulo_w = 350
    x0 = 32 + rotulo_w
    valor_w = 300
    barra_max = W - x0 - valor_w - 32
    pct_max = float(cand["pct_validos"].max())
    corpo: list[str] = []
    for i, r in cand.iterrows():
        y = top + i * linha
        segundo = str(r["situacao"]).lower().startswith("2")
        nome = nome_proprio(str(r["nome_urna"]))
        if i % 2 == 0:
            corpo.append(rect(24, y - 4, W - 48, linha - 2, SOFT, rx=8))
        corpo.append(text(40, y + 19, str(int(r["numero"])), size=13, weight=700, fill=MUTED))
        corpo.append(text(74, y + 19, nome, size=15, weight=700 if segundo else 500))
        corpo.append(text(x0 - 16, y + 19, str(r["partido_sigla"]), size=12, fill=MUTED,
                          anchor="end"))
        w = max(barra_max * float(r["pct_validos"]) / pct_max, 3)
        corpo.append(rect(x0, y + 5, w, linha - 16, BLUE if segundo else "#9FB8CB", rx=4))
        rot = f"{fmt_int(r['votos'])}  ·  {fmt_pct(r['pct_validos'])}"
        corpo.append(text(x0 + w + 10, y + 19, rot, size=13.5, weight=700 if segundo else 400,
                          fill=INK if segundo else MUTED))
        if segundo:
            bx = x0 + w + 10 + largura_texto(rot, 13.5, True) + 12
            corpo.append(rect(bx, y + 3, 74, 24, ORANGE, rx=12))
            corpo.append(text(bx + 37, y + 20, "2º turno", size=12.5, weight=700, anchor="middle"))
    h = top + len(cand) * linha + 70
    titulo = "Presidente, 1º turno de 2026: votos por candidato"
    subt = f"Votos nominais e percentual dos {fmt_int(validos)} votos válidos; em destaque, quem vai ao 2º turno"
    desc = "Barras horizontais com os votos de cada candidato. " + "; ".join(
        f"{nome_proprio(str(r['nome_urna']))} ({r['partido_sigla']}): {fmt_int(r['votos'])} votos, "
        f"{fmt_pct(r['pct_validos'])} dos válidos" for _, r in cand.iterrows()) + "."
    return documento(W, h, titulo, desc, corpo, subt, FONTE_2026)


# ----------------------------------------------------------------------
# b) Mapa por líder
# ----------------------------------------------------------------------
def _aneis(geom: dict) -> list[list[list[float]]]:
    """Anéis externos de cada polígono (buracos não existem na malha das UFs)."""
    if geom["type"] == "Polygon":
        return [geom["coordinates"][0]]
    return [poly[0] for poly in geom["coordinates"]]


def _centroide(anel: list[list[float]]) -> tuple[float, float, float]:
    a = cx = cy = 0.0
    for (x1, y1), (x2, y2) in zip(anel, anel[1:] + anel[:1], strict=True):
        f = x1 * y2 - x2 * y1
        a += f
        cx += (x1 + x2) * f
        cy += (y1 + y2) * f
    a /= 2
    if a == 0:
        return anel[0][0], anel[0][1], 0.0
    return cx / (6 * a), cy / (6 * a), abs(a)


# Deslocamento do rótulo (graus de longitude, latitude) para UFs pequenas ou
# rótulos que colidiriam; quando há deslocamento, uma linha guia liga ao estado.
_ROTULO_DESLOC = {
    "rn": (3.2, 0.9), "pb": (4.0, 0.1), "pe": (4.6, -0.9), "al": (3.8, -1.6),
    "se": (3.2, -2.7), "df": (2.2, 0.1), "ac": (1.2, 0.4), "es": (3.2, -0.2), "rj": (2.6, -2.0),
    "sc": (3.3, -0.2),
}
# Ajuste fino (graus) de rótulos que ficam dentro do estado
_ROTULO_AJUSTE = {"mg": (0.4, -1.2)}


def _lideres_uf(base: Path) -> pd.DataFrame:
    """UF result with the leading candidate number and its share of valid votes."""
    uf = load_resultado_uf(base)
    vcols = [c for c in uf.columns if c.startswith("v_")]
    return uf.assign(lider=uf[vcols].idxmax(axis=1).str[2:].astype(int),
                     pct=uf[vcols].max(axis=1) / uf["votos_validos"] * 100)


def _cores_lideres() -> dict[int, tuple[str, str]]:
    """Leader colors fixed by the 1st round ranking, so both rounds share one legend."""
    uf = _lideres_uf(DIR_2026)
    lideres = uf[uf["uf"] != UF_EXTERIOR]["lider"].value_counts().index.tolist()
    paleta = [(BLUE, "#A9D3EE"), (ORANGE, "#F6D9A0"), (GREEN, "#A6DCC9"), (NAVY, "#9DB3C4")]
    return {num: paleta[i % len(paleta)] for i, num in enumerate(lideres)}


def mapa_lider(turno: int = 1) -> str:
    """Map by UF leader; in the 2nd round every leader has 50%+, so the strong tone marks 60%."""
    base = DIR_2026_T2 if turno == 2 else DIR_2026
    limiar = 60 if turno == 2 else 50
    cand = load_candidatos(base)
    nomes = {int(r["numero"]): (nome_proprio(str(r["nome_urna"])), str(r["partido_sigla"]))
             for _, r in cand.iterrows()}
    uf = _lideres_uf(base)
    dados = {r["uf"]: r for _, r in uf.iterrows()}
    lideres = (uf[uf["uf"] != UF_EXTERIOR]["lider"].value_counts().index.tolist())
    cores = _cores_lideres()

    geo = json.loads(GEOJSON.read_text(encoding="utf-8"))
    lon_min, lon_max, lat_min, lat_max = -74.2, -28.6, -34.0, 5.6
    escala_x = math.cos(math.radians(15))
    W, H = 1000, 730
    mx, my, mw, mh = 40, 100, 600, 560
    k = min(mw / ((lon_max - lon_min) * escala_x), mh / (lat_max - lat_min))

    def proj(lon: float, lat: float) -> tuple[float, float]:
        return mx + (lon - lon_min) * escala_x * k, my + (lat_max - lat) * k

    corpo: list[str] = []
    rotulos: list[str] = []
    for feat in geo["features"]:
        sigla = str(feat["properties"]["sigla"]).lower()
        r = dados.get(sigla)
        if r is None:
            continue
        forte, claro = cores[int(r["lider"])]
        cor = forte if r["pct"] >= limiar else claro
        d = []
        maior = (0.0, 0.0, -1.0)
        for anel in _aneis(feat["geometry"]):
            pts = [proj(lon, lat) for lon, lat in anel]
            d.append("M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in pts) + "Z")
            c = _centroide(anel)
            if c[2] > maior[2]:
                maior = c
        nome = UF_NOMES.get(sigla, sigla.upper())
        corpo.append(f'<path d="{"".join(d)}" fill="{cor}" stroke="#FFFFFF" stroke-width="1.2" '
                     f'stroke-linejoin="round"><title>{escape(nome)}: '
                     f'{escape(nomes[int(r["lider"])][0])}, {fmt_pct(r["pct"], 1)}</title></path>')
        cx, cy = proj(maior[0], maior[1])
        dx, dy = _ROTULO_DESLOC.get(sigla, (0.0, 0.0))
        if (dx, dy) != (0.0, 0.0):
            lx, ly = proj(maior[0] + dx, maior[1] + dy)
            rotulos.append(f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{lx - 4:.1f}" y2="{ly - 4:.1f}" '
                           f'stroke="{MUTED}" stroke-width="1"/>')
            rotulos.append(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="2" fill="{INK}"/>')
            rotulos.append(rect(lx - 4, ly - 15, 46, 31, "#FFFFFF", rx=6,
                                extra=' fill-opacity="0.92"'))
            rotulos.append(text(lx, ly - 2, sigla.upper(), size=12, weight=700, fill=INK))
            rotulos.append(text(lx, ly + 11, fmt_pct(r["pct"], 1), size=10.5, fill=MUTED))
        else:
            ax, ay = _ROTULO_AJUSTE.get(sigla, (0.0, 0.0))
            cx, cy = proj(maior[0] + ax, maior[1] + ay)
            claro_txt = cor == forte and cor in (BLUE, NAVY, GREEN)
            fill = "#FFFFFF" if claro_txt else INK
            rotulos.append(text(cx, cy - 1, sigla.upper(), size=12, weight=700, fill=fill,
                                anchor="middle"))
            rotulos.append(text(cx, cy + 12, fmt_pct(r["pct"], 1), size=10.5, fill=fill,
                                anchor="middle"))
    corpo.extend(rotulos)

    # Legenda e resumo
    lx = 690
    ly = 140
    corpo.append(text(lx, ly, "Candidato mais votado na UF", size=15, weight=700))
    ly += 30
    contagem = uf[uf["uf"] != UF_EXTERIOR]["lider"].value_counts()
    for num in lideres:
        forte, claro = cores[num]
        nome, sigla_p = nomes[num]
        corpo.append(rect(lx, ly - 14, 18, 18, forte, rx=4))
        corpo.append(rect(lx + 22, ly - 14, 18, 18, claro, rx=4))
        corpo.append(text(lx + 50, ly, f"{nome} ({sigla_p})", size=14.5, weight=700))
        corpo.append(text(lx + 50, ly + 19, f"lidera em {int(contagem[num])} UFs", size=13,
                          fill=MUTED))
        ly += 52
    corpo.append(rect(lx, ly - 13, 18, 18, "#6E8799", rx=4))
    corpo.append(text(lx + 26, ly + 1, f"{limiar}% dos válidos ou mais", size=13, fill=MUTED))
    ly += 26
    corpo.append(rect(lx, ly - 13, 18, 18, "#C9D6E0", rx=4))
    corpo.append(text(lx + 26, ly + 1, f"menos de {limiar}% dos válidos", size=13, fill=MUTED))
    ly += 44
    corpo.append(text(lx, ly, "O número em cada UF é o percentual", size=13, fill=MUTED))
    corpo.append(text(lx, ly + 18, "de votos válidos do líder.", size=13, fill=MUTED))
    ext = dados.get(UF_EXTERIOR)
    if ext is not None:
        ly += 50
        corpo.append(rect(lx - 10, ly - 22, 280, 64, SOFT, rx=10))
        corpo.append(text(lx + 4, ly, "Exterior (fora do mapa)", size=13, weight=700))
        corpo.append(text(lx + 4, ly + 22,
                          f"{nomes[int(ext['lider'])][0]}, {fmt_pct(ext['pct'], 1)} dos válidos",
                          size=13, fill=MUTED))
    titulo = f"Quem liderou em cada UF, {turno}º turno de 2026"
    subt = ("Presidente: candidato mais votado por unidade da federação; tom forte indica "
            f"{limiar}% dos válidos ou mais")
    desc = "Mapa do Brasil por UF colorido pelo candidato mais votado. " + "; ".join(
        f"{UF_NOMES.get(s, s.upper())}: {nomes[int(dados[s]['lider'])][0]} com "
        f"{fmt_pct(dados[s]['pct'], 1)}" for s in sorted(dados) if s != UF_EXTERIOR) + "."
    fonte = (FONTE_2026_T2 if turno == 2 else FONTE_2026) + "; malha: IBGE"
    return documento(W, H, titulo, desc, corpo, subt, fonte)


# ----------------------------------------------------------------------
# c) Comparecimento 2022 x 2026
# ----------------------------------------------------------------------
def _halteres(linhas: list[tuple[str, float, float, bool]], rot_a: str, rot_b: str, col_b: str,
              margem_dir: int = 170, col_dx: int = 110) -> tuple[list[str], int]:
    """Dumbbell rows (label, value a, value b, highlight); returns the body and its bottom y."""
    valores = [v for _, a, b, _ in linhas for v in (a, b)]
    vmin = math.floor(min(valores) / 2) * 2 - 1
    vmax = math.ceil(max(valores) / 2) * 2 + 1
    W = 1000
    top = 150
    alt = 24
    x0, x1 = 250, W - margem_dir

    def px(v: float) -> float:
        return x0 + (v - vmin) / (vmax - vmin) * (x1 - x0)

    corpo: list[str] = []
    # Legenda
    corpo.append(f'<circle cx="56" cy="104" r="7" fill="{LIGHT_BLUE}" stroke="{BLUE}" stroke-width="1.5"/>')
    corpo.append(text(70, 109, rot_a, size=13.5, fill=INK))
    corpo.append(f'<circle cx="206" cy="104" r="7" fill="{NAVY}"/>')
    corpo.append(text(220, 109, rot_b, size=13.5, fill=INK))
    corpo.append(text(x1 + 30, 109, "Variação", size=13, weight=700, fill=MUTED))
    corpo.append(text(x1 + col_dx, 109, col_b, size=13, weight=700, fill=MUTED))
    # Grade
    fim = top + len(linhas) * alt + 6
    for v in range(vmin + 1, vmax, 2):
        x = px(v)
        corpo.append(f'<line x1="{x:.1f}" y1="{top - 10}" x2="{x:.1f}" y2="{fim}" stroke="{GRID}" '
                     f'stroke-width="1"/>')
        corpo.append(text(x, top - 16, f"{v}%", size=11.5, fill=MUTED, anchor="middle"))
    for i, (rot, a, b, destaque) in enumerate(linhas):
        y = top + i * alt + (6 if i else 0) + 10
        if destaque:
            corpo.append(rect(24, y - 13, W - 48, alt + 2, SOFT, rx=8))
        corpo.append(text(x0 - 14, y + 4.5, rot, size=13, weight=700 if destaque else 400,
                          anchor="end"))
        xa, xb = px(a), px(b)
        corpo.append(f'<line x1="{xa:.1f}" y1="{y}" x2="{xb:.1f}" y2="{y}" stroke="#9FB8CB" '
                     f'stroke-width="3" stroke-linecap="round"/>')
        corpo.append(f'<circle cx="{xa:.1f}" cy="{y}" r="5.5" fill="{LIGHT_BLUE}" stroke="{BLUE}" '
                     f'stroke-width="1.3"/>')
        corpo.append(f'<circle cx="{xb:.1f}" cy="{y}" r="5.5" fill="{NAVY}"/>')
        delta = round(b - a, 1)
        sinal = "+" if delta > 0 else ("−" if delta < 0 else "")
        cor = GREEN if delta > 0 else (ORANGE if delta < 0 else MUTED)
        corpo.append(text(x1 + 30, y + 4.5, f"{sinal}{fmt_num(abs(delta))} p.p.", size=13,
                          weight=700, fill=cor if cor != ORANGE else "#B07800"))
        corpo.append(text(x1 + col_dx, y + 4.5, fmt_pct(b, 1), size=12, fill=MUTED))
    return corpo, fim


def comparecimento() -> str:
    t22 = load_2022_t1_by_uf(PARQUET)
    res = load_resultado_uf()
    res = res[res["uf"] != UF_EXTERIOR]
    comp = compare_2022_2026(res, t22).sort_values("comparecimento_pct_2026", ascending=False)
    br26 = res["comparecimento"].sum() / res["eleitorado"].sum() * 100
    br22 = t22["comparecimento_2022"].sum() / t22["eleitorado_2022"].sum() * 100
    linhas = [("Brasil", br22, br26, True)] + [
        (f"{r['nome']} ({r['uf'].upper()})", r["comparecimento_pct_2022"],
         r["comparecimento_pct_2026"], False) for _, r in comp.iterrows()]
    corpo, fim = _halteres(linhas, "1º turno de 2022", "1º turno de 2026", "2026")
    W = 1000
    h = fim + 80
    titulo = "Comparecimento por UF: 1º turno de 2022 x 2026"
    subt = "Eleitores que votaram sobre o eleitorado apto; variação em pontos percentuais (exterior não incluído)"
    desc = "Gráfico de halteres com o comparecimento de cada UF. " + "; ".join(
        f"{rot}: {fmt_pct(a, 1)} em 2022 e {fmt_pct(b, 1)} em 2026" for rot, a, b, _ in linhas) + "."
    fonte = "Fonte: TSE, resultados oficiais do 1º turno de 2026; 2022: boletins de urna por seção"
    return documento(W, h, titulo, desc, corpo, subt, fonte)


# ----------------------------------------------------------------------
# d) Cobertura de 2022
# ----------------------------------------------------------------------
def cobertura_2022() -> str:
    con = duckdb.connect()
    try:
        sec = con.execute(
            "SELECT turno, modelo_urna, COUNT(*) n, COUNT(DISTINCT uf) ufs FROM read_parquet(?) "
            "GROUP BY ALL", [str(PARQUET / "secoes.parquet")]).fetchdf()
        ufs = con.execute("SELECT COUNT(DISTINCT uf) FROM read_parquet(?)",
                          [str(PARQUET / "secoes.parquet")]).fetchone()[0]
        votos = sum(con.execute("SELECT COUNT(*) FROM read_parquet(?)", [str(p)]).fetchone()[0]
                    for p in sorted(PARQUET.glob("votos_*.parquet")))
        sev = con.execute("SELECT severidade, COUNT(*) n FROM read_parquet(?) GROUP BY 1",
                          [str(PARQUET / "issues.parquet")]).fetchdf()
    finally:
        con.close()
    total = int(sec["n"].sum())
    por_turno = sec.groupby("turno")["n"].sum().to_dict()
    modelos = sec.groupby("modelo_urna")["n"].sum().sort_index()
    sev_n = dict(zip(sev["severidade"], sev["n"].astype(int), strict=True))
    n_issues = sum(sev_n.values())

    W, H = 1000, 560
    corpo: list[str] = []
    tiles = [
        (fmt_int(total), "seções auditadas", "dois turnos da eleição presidencial"),
        (str(ufs), "UFs", "todas as unidades da federação"),
        (fmt_int(votos), "registros de votos", "por seção, cargo e candidato"),
        (fmt_int(n_issues), "ocorrências", "indicadores para investigação"),
    ]
    tw, gap = 222, 13
    for i, (num, rot, sub) in enumerate(tiles):
        x = 32 + i * (tw + gap)
        corpo.append(rect(x, 100, tw, 112, SOFT, rx=12))
        corpo.append(rect(x, 100, 5, 112, [BLUE, GREEN, LIGHT_BLUE, ORANGE][i], rx=2.5))
        corpo.append(text(x + 20, 146, num, size=30, weight=800, fill=NAVY))
        corpo.append(text(x + 20, 172, rot, size=15, weight=700))
        corpo.append(text(x + 20, 194, sub, size=12, fill=MUTED))

    # Turnos
    y = 252
    corpo.append(text(32, y, "Seções por turno", size=15, weight=700))
    t1, t2 = int(por_turno.get(1, 0)), int(por_turno.get(2, 0))
    bw = W - 64
    w1 = bw * t1 / max(total, 1)
    corpo.append(rect(32, y + 14, w1 - 2, 34, BLUE, rx=6))
    corpo.append(rect(32 + w1 + 2, y + 14, bw - w1 - 2, 34, LIGHT_BLUE, rx=6))
    corpo.append(text(46, y + 37, f"1º turno, 02/10/2022: {fmt_int(t1)}", size=13.5, weight=700,
                      fill="#FFFFFF"))
    corpo.append(text(32 + w1 + 16, y + 37, f"2º turno, 30/10/2022: {fmt_int(t2)}", size=13.5,
                      weight=700, fill=NAVY))

    # Modelos
    y = 340
    corpo.append(text(32, y, "Modelo da urna (seções)", size=15, weight=700))
    tons = ["#0B3A5B", "#0F5A8A", "#0072B2", "#3C97CC", "#56B4E9", "#A9D3EE"]
    x = 32.0
    for (modelo, n), cor in zip(modelos.items(), tons, strict=False):
        w = bw * n / total
        corpo.append(rect(x, y + 14, w - 2, 34, cor, rx=4))
        rot = f"UE{modelo}"
        claro = cor in ("#56B4E9", "#A9D3EE")
        if w > 80:
            corpo.append(text(x + w / 2, y + 30, rot, size=12.5, weight=700,
                              fill=NAVY if claro else "#FFFFFF", anchor="middle"))
            corpo.append(text(x + w / 2, y + 44, fmt_pct(n / total * 100, 1), size=11,
                              fill=NAVY if claro else "#E8F3FA", anchor="middle"))
        else:
            corpo.append(text(x + w / 2, y + 36, rot, size=11, weight=700,
                              fill=NAVY if claro else "#FFFFFF", anchor="middle"))
        x += w
    corpo.append(text(32, y + 70, "Software de votação 8.26.0.0 (Onça-pintada) em todas as seções",
                      size=12.5, fill=MUTED))

    # Severidade
    y = 444
    corpo.append(text(32, y, "Ocorrências por severidade", size=15, weight=700))
    ordem = [("alta", "Alta", ORANGE), ("media", "Média", LIGHT_BLUE),
             ("informativa", "Informativa", "#9FB8CB")]
    maxn = max(sev_n.values())
    for i, (chave, rot, cor) in enumerate(ordem):
        n = sev_n.get(chave, 0)
        xx = 32 + i * 316
        corpo.append(text(xx, y + 30, rot, size=13.5, weight=700))
        corpo.append(text(xx + 290, y + 30, f"{fmt_int(n)} ({fmt_pct(n / n_issues * 100, 1)})",
                          size=13, fill=MUTED, anchor="end"))
        corpo.append(rect(xx, y + 40, 290, 10, SOFT, rx=5))
        corpo.append(rect(xx, y + 40, 290 * n / maxn, 10, cor, rx=5))
    titulo = "Eleições 2022: cobertura completa da auditoria"
    subt = "Todos os boletins de urna e logs publicados pelo TSE para Presidente, 1º e 2º turnos"
    desc = (f"Infográfico: {fmt_int(total)} seções ({fmt_int(t1)} no 1º turno e {fmt_int(t2)} no 2º), "
            f"{ufs} UFs, {fmt_int(votos)} registros de votos, modelos de urna "
            + ", ".join(f"UE{m}: {fmt_int(n)}" for m, n in modelos.items())
            + f". {fmt_int(n_issues)} ocorrências: "
            + ", ".join(f"{rot} {fmt_int(sev_n.get(c, 0))}" for c, rot, _ in ordem) + ".")
    return documento(W, H, titulo, desc, corpo, subt, FONTE_2022)


# ----------------------------------------------------------------------
# e) Arquitetura
# ----------------------------------------------------------------------
def _caixa(x: float, y: float, w: float, h: float, titulo: str, linhas: list[str], cor: str,
           icone: str = "") -> list[str]:
    out = [
        rect(x, y, w, h, "#FFFFFF", rx=12, extra=f' stroke="{cor}" stroke-width="2"'),
        rect(x, y, w, 34, cor, rx=12),
        rect(x, y + 20, w, 14, cor),
        text(x + 14, y + 23, (icone + "  " if icone else "") + titulo, size=14, weight=700,
             fill="#FFFFFF" if cor != LIGHT_BLUE else NAVY),
    ]
    for i, linha in enumerate(linhas):
        out.append(text(x + 14, y + 56 + i * 19, linha, size=12.5, fill=INK if i == 0 else MUTED))
    return out


def _seta(x1: float, y1: float, x2: float, y2: float) -> str:
    return (f'<path d="M{x1:.1f},{y1:.1f} L{x2:.1f},{y2:.1f}" stroke="{MUTED}" stroke-width="2" '
            f'fill="none" marker-end="url(#seta)"/>')


def arquitetura() -> str:
    W, H = 1200, 590
    corpo: list[str] = [
        '<defs><marker id="seta" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" '
        f'markerHeight="8" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{MUTED}"/>'
        "</marker></defs>",
    ]
    # Faixas das etapas
    etapas = [(32, 190, "1. Fonte"), (242, 200, "2. Coleta"), (462, 230, "3. Decodificação"),
              (712, 210, "4. Análise"), (942, 226, "5. Dados e painel")]
    for x, w, rot in etapas:
        corpo.append(rect(x, 100, w, H - 160, SOFT, rx=14))
        corpo.append(text(x + 14, 124, rot, size=13, weight=700, fill=MUTED))

    # 1. Fonte
    corpo += _caixa(44, 220, 166, 150, "API do TSE", ["resultados.tse.jus.br", "config, UF, seção,",
                                                       "aux.json e arquivos", "da urna"], NAVY)
    # 2. Coleta
    corpo += _caixa(254, 150, 176, 132, "downloader", ["httpx assíncrono", "backoff e Retry-After",
                                                        "escrita atômica"], BLUE)
    corpo += _caixa(254, 310, 176, 132, "ele2026", ["resultados agregados", "BU por seção",
                                                     "com checkpoint"], BLUE)
    # 3. Decodificação
    corpo += _caixa(474, 140, 206, 100, "BU e RDV", ["ASN.1/BER, spec v1 e v2", "asn1tools"],
                    GREEN)
    corpo += _caixa(474, 256, 206, 100, "Log da urna", [".logjez (7z, texto)",
                                                        "filtro pela data do turno"], GREEN)
    corpo += _caixa(474, 372, 206, 100, "Assinatura", [".vscmr / -vota.vsc",
                                                       "hashes SHA-512"], GREEN)
    # 4. Análise
    corpo += _caixa(724, 160, 186, 290, "Verificações", ["4 eixos por seção:", "integridade",
                                                          "consistência", "log e horários",
                                                          "estatística", "", "cada achado vira",
                                                          "ocorrência com", "código e severidade"],
                    ORANGE)
    # 5. Dados e painel
    corpo += _caixa(954, 150, 202, 128, "DuckDB + Parquet", ["secoes, votos, issues,",
                                                             "totais_cargo", "Parquet ZSTD"], NAVY)
    corpo += _caixa(954, 318, 202, 128, "Painel Streamlit", ["páginas temáticas",
                                                             "filtros e exportação",
                                                             "2022 e 2026"], LIGHT_BLUE)
    # Setas
    corpo += [
        _seta(210, 270, 252, 216), _seta(210, 320, 252, 376),
        f'<path d="M430,216 H451 M451,190 V422 M680,190 H701 M680,422 H701 M701,190 V422" '
        f'stroke="{MUTED}" stroke-width="2" fill="none"/>',
        _seta(451, 190, 472, 190), _seta(451, 306, 472, 306), _seta(451, 422, 472, 422),
        _seta(680, 306, 722, 306),
        _seta(910, 260, 952, 214),
        _seta(1055, 278, 1055, 316),
        f'<path d="M342,442 V500 H1172 V214 H1158" stroke="{MUTED}" stroke-width="2" '
        'stroke-dasharray="6 5" fill="none" marker-end="url(#seta)"/>',
        rect(560, 488, 330, 24, "#FFFFFF", rx=12, extra=f' stroke="{GRID}"'),
        text(725, 505, "2026: totais oficiais seguem direto para Parquet", size=12, fill=MUTED,
             anchor="middle"),
    ]
    titulo = "Arquitetura do DataUrnas-BR"
    subt = "Dos arquivos públicos da urna ao painel: cada etapa é reproduzível a partir dos dados do TSE"
    desc = ("Diagrama de fluxo em cinco etapas: a API pública do TSE alimenta o downloader e a coleta "
            "de 2026; os arquivos são decodificados (BU e RDV em ASN.1, log 7z e assinatura com "
            "hashes SHA-512); as verificações de integridade, consistência, log e estatística geram "
            "ocorrências; os resultados ficam em DuckDB e Parquet ZSTD e são exibidos no painel "
            "Streamlit.")
    return documento(W, H, titulo, desc, corpo, subt, "Código aberto, licença MIT")


# ----------------------------------------------------------------------
# f) 2º turno de 2026
# ----------------------------------------------------------------------
def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _tiles(corpo: list[str], y: float, tiles: list[tuple[str, str, str]], cores: list[str],
           h: float = 104, num_size: float = 28) -> None:
    """Row of four stat tiles (number, label, note) in the cobertura_2022 style."""
    tw, gap = 222, 13
    for i, (num, rot, sub) in enumerate(tiles):
        x = 32 + i * (tw + gap)
        corpo.append(rect(x, y, tw, h, SOFT, rx=12))
        corpo.append(rect(x, y, 5, h, cores[i % len(cores)], rx=2.5))
        corpo.append(text(x + 20, y + 40, num, size=num_size, weight=800, fill=NAVY))
        corpo.append(text(x + 20, y + 66, rot, size=14, weight=700))
        corpo.append(text(x + 20, y + 87, sub, size=12, fill=MUTED))


def _check(cx: float, cy: float, r: float = 10, cor: str = GREEN) -> str:
    """Filled circle with a check mark drawn as a path (no glyph dependency)."""
    s = r / 10
    return (f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" fill="{cor}"/>'
            f'<path d="M{cx - 4.5 * s:.1f},{cy + 0.2 * s:.1f} L{cx - 1.2 * s:.1f},{cy + 3.5 * s:.1f} '
            f'L{cx + 4.8 * s:.1f},{cy - 3.6 * s:.1f}" stroke="#FFFFFF" stroke-width="{2.4 * s:.1f}" '
            'fill="none" stroke-linecap="round" stroke-linejoin="round"/>')


def resultado_t2() -> str:
    resumo = _json(DIR_2026_T2 / "resumo_br.json")
    t = resumo["totais"]
    cand = sorted(resumo["candidatos"], key=lambda c: -c["votos"])
    cores = _cores_lideres()
    validos = int(t["votos_validos"])
    W, H = 1000, 540
    corpo: list[str] = []

    # Candidate headers: winner on the left, runner-up right-aligned
    for lado, c in zip(("esq", "dir"), cand, strict=True):
        num = int(c["numero"])
        cor = cores.get(num, (BLUE, ""))[0]
        nome = f"{nome_proprio(c['nome_urna'])} ({c['partido_sigla']})"
        eleito = str(c["situacao"]).lower() == "eleito"
        if lado == "esq":
            corpo.append(f'<circle cx="52" cy="122" r="20" fill="{cor}"/>')
            corpo.append(text(52, 128, str(num), size=16, weight=800, fill=INK, anchor="middle"))
            corpo.append(text(84, 128, nome, size=19, weight=700))
            if eleito:
                bx = 84 + largura_texto(nome, 19, True) + 12
                corpo.append(rect(bx, 110, 66, 24, GREEN, rx=12))
                corpo.append(text(bx + 33, 127, "Eleito", size=12.5, weight=700, fill="#FFFFFF",
                                  anchor="middle"))
            corpo.append(text(32, 196, fmt_pct(c["pct_validos"]), size=46, weight=800, fill=NAVY))
            corpo.append(text(32, 222, f"{fmt_int(c['votos'])} votos", size=15, fill=MUTED))
        else:
            corpo.append(f'<circle cx="{W - 52}" cy="122" r="20" fill="{cor}"/>')
            corpo.append(text(W - 52, 128, str(num), size=16, weight=800, fill="#FFFFFF",
                              anchor="middle"))
            corpo.append(text(W - 84, 128, nome, size=19, weight=700, anchor="end"))
            corpo.append(text(W - 32, 196, fmt_pct(c["pct_validos"]), size=46, weight=800,
                              fill=NAVY, anchor="end"))
            corpo.append(text(W - 32, 222, f"{fmt_int(c['votos'])} votos", size=15, fill=MUTED,
                              anchor="end"))

    # Split bar of valid votes with the 50% reference
    bx, bw, by, bh = 32, W - 64, 244, 46
    w1 = bw * cand[0]["votos"] / validos
    corpo.append(rect(bx, by, w1 - 2, bh, cores.get(int(cand[0]["numero"]), (ORANGE, ""))[0], rx=8))
    corpo.append(rect(bx + w1 + 2, by, bw - w1 - 2, bh,
                      cores.get(int(cand[1]["numero"]), (BLUE, ""))[0], rx=8))
    meio = bx + bw / 2
    corpo.append(f'<line x1="{meio:.1f}" y1="{by - 10}" x2="{meio:.1f}" y2="{by + bh + 10}" '
                 f'stroke="{INK}" stroke-width="2" stroke-dasharray="4 4"/>')
    corpo.append(text(meio, by + bh + 28, "50% dos válidos", size=12.5, fill=MUTED, anchor="middle"))
    margem = cand[0]["votos"] - cand[1]["votos"]
    pp = cand[0]["pct_validos"] - cand[1]["pct_validos"]
    corpo.append(text(W / 2, by + bh + 60,
                      f"Diferença: {fmt_int(margem)} votos ({fmt_num(pp, 2)} pontos percentuais "
                      f"dos {fmt_int(validos)} válidos)", size=15, weight=700, anchor="middle"))

    # Turnout, abstention, blank and null votes
    tiles = [
        (fmt_int(t["comparecimento"]), "comparecimento",
         f"{fmt_pct(t['pct_comparecimento'])} do eleitorado"),
        (fmt_int(t["abstencao"]), "abstenção", f"{fmt_pct(t['pct_abstencao'])} do eleitorado"),
        (fmt_int(t["votos_brancos"]), "votos brancos", f"{fmt_pct(t['pct_brancos'])} dos votos"),
        (fmt_int(t["votos_nulos_total"]), "votos nulos", f"{fmt_pct(t['pct_nulos'])} dos votos"),
    ]
    _tiles(corpo, 368, tiles, [NAVY, "#9FB8CB", LIGHT_BLUE, MUTED], h=100, num_size=24)
    titulo = "Presidente, 2º turno de 2026: resultado nacional"
    subt = (f"Percentual dos votos válidos; eleitorado de {fmt_int(t['eleitorado'])} e "
            f"{fmt_int(t['secoes_instaladas'])} seções instaladas")
    desc = ("Barra dividida com o resultado do 2º turno. " + "; ".join(
        f"{nome_proprio(c['nome_urna'])} ({c['partido_sigla']}): {fmt_int(c['votos'])} votos, "
        f"{fmt_pct(c['pct_validos'])} dos válidos" for c in cand)
        + f". Diferença de {fmt_int(margem)} votos. Comparecimento {fmt_int(t['comparecimento'])} "
        f"({fmt_pct(t['pct_comparecimento'])}), abstenção {fmt_int(t['abstencao'])}, brancos "
        f"{fmt_int(t['votos_brancos'])} e nulos {fmt_int(t['votos_nulos_total'])}.")
    return documento(W, H, titulo, desc, corpo, subt, FONTE_2026_T2)


def mapa_lider_t2() -> str:
    return mapa_lider(turno=2)


def comparecimento_t2() -> str:
    t1 = load_resultado_uf(DIR_2026)
    t2 = load_resultado_uf(DIR_2026_T2)
    t1, t2 = (d[d["uf"] != UF_EXTERIOR].set_index("uf") for d in (t1, t2))
    br1 = t1["comparecimento"].sum() / t1["eleitorado"].sum() * 100
    br2 = t2["comparecimento"].sum() / t2["eleitorado"].sum() * 100
    p1 = t1["comparecimento"] / t1["eleitorado"] * 100
    p2 = (t2["comparecimento"] / t2["eleitorado"] * 100).sort_values(ascending=False)
    linhas = [("Brasil", br1, br2, True)] + [
        (f"{UF_NOMES.get(uf, uf.upper())} ({uf.upper()})", float(p1[uf]), float(v), False)
        for uf, v in p2.items()]
    corpo, fim = _halteres(linhas, "1º turno de 2026", "2º turno de 2026", "2º turno",
                           margem_dir=210, col_dx=120)
    titulo = "Comparecimento por UF: 1º x 2º turno de 2026"
    subt = "Eleitores que votaram sobre o eleitorado apto; variação em pontos percentuais (exterior não incluído)"
    desc = "Gráfico de halteres com o comparecimento de cada UF. " + "; ".join(
        f"{rot}: {fmt_pct(a, 1)} no 1º turno e {fmt_pct(b, 1)} no 2º" for rot, a, b, _ in linhas) + "."
    fonte = "Fonte: TSE, resultados oficiais do 1º e do 2º turno de 2026"
    return documento(1000, fim + 80, titulo, desc, corpo, subt, fonte)


def integridade_t2() -> str:
    resumo = _json(DIR_2026_T2 / "resumo_br.json")
    rdv = _json(DIR_2026_T2 / "rdv_nacional_resumo.json")
    cert = _json(DIR_2026_T2 / "certificados_resumo.json")
    t = resumo["totais"]
    assin = cert["verificacoes"]["assinaturas_arquivos"]
    bu_hash = int(cert["verificacoes"]["bu_hash_confere"].get("True", 0))
    con = duckdb.connect()
    try:
        soma_bu = con.execute(
            "SELECT SUM(v13), SUM(v22), SUM(brancos), SUM(nulos), SUM(comparecimento), COUNT(*) "
            "FROM read_parquet(?)", [str(DIR_2026_T2 / "secoes_t2.parquet")]).fetchone()
    finally:
        con.close()
    nomes = {int(c["numero"]): f"{nome_proprio(c['nome_urna'])} ({c['partido_sigla']})"
             for c in resumo["candidatos"]}
    oficial = {"13": 0, "22": 0}
    for c in resumo["candidatos"]:
        oficial[str(c["numero"])] = int(c["votos"])
    linhas = [
        (f"13  {nomes.get(13, '')}", rdv["totais"]["13"]["rdv"], soma_bu[0], oficial["13"]),
        (f"22  {nomes.get(22, '')}", rdv["totais"]["22"]["rdv"], soma_bu[1], oficial["22"]),
        ("Brancos", rdv["totais"]["brancos"]["rdv"], soma_bu[2], t["votos_brancos"]),
        ("Nulos", rdv["totais"]["nulos"]["rdv"], soma_bu[3], t["votos_nulos_total"]),
        ("Total (comparecimento)", rdv["totais"]["presidente_total"]["rdv"], soma_bu[4],
         t["comparecimento"]),
    ]
    W = 1000
    corpo: list[str] = []
    n_sec = int(rdv["secoes"])
    tiles = [
        (fmt_int(n_sec), "seções com BU",
         f"de {fmt_int(t['secoes_total'])}; {t['secoes_nao_instaladas']} não instaladas"),
        (fmt_int(assin["ok"]), "assinaturas válidas", f"{fmt_int(assin['falha'])} inválidas"),
        (fmt_int(bu_hash), "hashes do BU conferem", "SHA-512 assinado x publicado"),
        (fmt_int(rdv["presidente_diverge"]), "divergências RDV x BU",
         f"{fmt_int(rdv['com_rdv'])} seções recontadas"),
    ]
    _tiles(corpo, 96, tiles, [BLUE, GREEN, LIGHT_BLUE, GREEN])

    # Three independent sums of the same votes
    y = 244
    corpo.append(text(32, y, "Três somas dos mesmos votos, o mesmo resultado", size=15, weight=700))
    cols = [(560, "Recontagem do RDV"), (720, "Soma dos BUs"), (880, "Resultado oficial"),
            (W - 40, "Diferença")]
    y += 34
    for x, rot in cols:
        corpo.append(text(x, y, rot, size=12.5, weight=700, fill=MUTED, anchor="end"))
    corpo.append(f'<line x1="32" y1="{y + 10}" x2="{W - 32}" y2="{y + 10}" stroke="{GRID}"/>')
    y += 16
    dif_max = 0
    for i, (rot, a, b, c) in enumerate(linhas):
        yy = y + i * 34
        if i % 2 == 0:
            corpo.append(rect(24, yy, W - 48, 32, SOFT, rx=8))
        total = i == len(linhas) - 1
        corpo.append(text(40, yy + 21, rot, size=14, weight=700 if total or i < 2 else 500))
        for (x, _), v in zip(cols[:3], (a, b, c), strict=True):
            corpo.append(text(x, yy + 21, fmt_int(v), size=14, weight=700 if total else 400,
                              anchor="end"))
        dif = max(abs(int(a) - int(b)), abs(int(b) - int(c)), abs(int(a) - int(c)))
        dif_max = max(dif_max, dif)
        corpo.append(text(cols[3][0], yy + 21, fmt_int(dif), size=14, weight=800,
                          fill=GREEN if dif == 0 else ORANGE, anchor="end"))
    y += len(linhas) * 34 + 12
    corpo.append(text(32, y + 8, "RDV: registro digital do voto, recontado voto a voto; BU: boletim de "
                      "urna assinado; oficial: totalização divulgada pelo TSE.", size=12.5, fill=MUTED))

    # RDV recount by UF
    y += 50
    corpo.append(text(32, y, "Recontagem do RDV por UF: seções recontadas, 0 divergências em todas",
                      size=15, weight=700))
    por_uf = rdv["por_uf"]
    ufs = sorted(por_uf, key=lambda u: (u == UF_EXTERIOR, u))
    por_linha = 14
    cw = (W - 64 - (por_linha - 1) * 6) / por_linha
    y += 16
    for i, uf in enumerate(ufs):
        r = por_uf[uf]
        x = 32 + (i % por_linha) * (cw + 6)
        yy = y + (i // por_linha) * 54
        ok = int(r["diverge"]) == 0
        corpo.append(rect(x, yy, cw, 48, "#DDF1EA" if ok else "#F6D9A0", rx=8))
        corpo.append(text(x + cw / 2, yy + 20, "EXT" if uf == UF_EXTERIOR else uf.upper(), size=13,
                          weight=700, anchor="middle"))
        corpo.append(text(x + cw / 2, yy + 37, fmt_int(r["com_rdv"]), size=11, fill=MUTED,
                          anchor="middle"))
    y += ((len(ufs) + por_linha - 1) // por_linha) * 54 + 14
    sem = len(rdv.get("sem_rdv", []))
    corpo.append(text(32, y + 4, f"EXT: exterior. As {sem} seções do exterior sem RDV tiveram "
                      "comparecimento 0.", size=12.5, fill=MUTED))
    h = int(y + 70)
    titulo = "Integridade e recontagem, 2º turno de 2026"
    subt = "Assinatura da urna, hash do BU e recontagem voto a voto do RDV em todas as seções com BU"
    desc = (f"{fmt_int(n_sec)} seções com BU de {fmt_int(t['secoes_total'])} "
            f"({t['secoes_nao_instaladas']} não instaladas no exterior); {fmt_int(assin['ok'])} "
            f"assinaturas válidas e {fmt_int(assin['falha'])} inválidas; {fmt_int(bu_hash)} hashes "
            f"SHA-512 do BU conferem; RDV recontado em {fmt_int(rdv['com_rdv'])} seções com "
            f"{fmt_int(rdv['presidente_diverge'])} divergências. "
            + "; ".join(f"{rot.strip()}: RDV {fmt_int(a)}, BUs {fmt_int(b)}, oficial {fmt_int(c)}"
                        for rot, a, b, c in linhas)
            + f". Maior diferença entre as três somas: {fmt_int(dif_max)}.")
    fonte = "Fonte: arquivos de urna do 2º turno de 2026 (TSE); verificação DataUrnas-BR"
    return documento(W, h, titulo, desc, corpo, subt, fonte)


# ----------------------------------------------------------------------
# g) Veredicto da auditoria (resumo de docs/veredicto-auditoria-2026.md)
# ----------------------------------------------------------------------
# Short labels for the 19 checks of the verdict table; keep in sync with the document.
VERIFICADO = [
    ("Coleta versionada, 8 voltas de reconferência", "0 arquivos alterados ou removidos"),
    ("Assinatura digital de todos os arquivos", "5.487.289 válidas, 0 inválidas"),
    ("Soma dos BUs x resultado oficial", "igual voto a voto: Brasil, UFs e 5.757 municípios"),
    ("Totais divulgados durante a apuração", "12 mil versões; nunca diminuíram"),
    ("Valores impossíveis no BU", "0 em 998.414 BUs dos dois turnos"),
    ("Recontagem do RDV x BU", "0 divergências: 499.206 seções (1º) e 499.205 (2º)"),
    ("Log eleitor a eleitor x BU", "votos no log = comparecimento em 2.997 seções"),
    ("Encerramento tardio e margem", "pior cenário ainda mantém 4.398.399 de margem"),
    ("BUs emitidos mais de 1 h após o encerramento", "368 seções; 0 votos depois do fim"),
    ("Viradas por seção do 1º para o 2º turno", "31.341 observadas x 32.604 esperadas"),
    ("Estatística forense com 2022 como controle", "nenhum padrão maior que o de 2022"),
    ("Modelo de urna, troca e contingência", "maior pior caso: 3.957 votos"),
    ("Biometria do 1º x 2º turno", "variações de décimos de ponto, sem relação com o voto"),
    ("Cargas x logs de preparação (GEDAI)", "99,83% conferem; 862 cargas sem log"),
    ("Linha do tempo de emissão e totalização", "nenhum BU emitido depois de totalizado"),
    ("Dados abertos x BU", "0 divergências de voto"),
    ("Hashes lacrados x programas nos logs", "todos os de inicialização estão na lista"),
    ("Assinatura JWS dos resultados divulgados", "11.572 válidas, 0 inválidas"),
    ("Alegações externas sobre viradas", "explicadas pela ordem geográfica de chegada"),
]
NAO_VERIFICAVEL = [
    ("Qual software rodou em cada urna",
     "a ligação com a lista lacrada só é feita por amostragem, com relatórios não publicados"),
    ("Adulteração idêntica em todas as urnas",
     "não deixa diferença entre grupos; depende do Teste de Integridade (relatório até 23/01/2027)"),
    ("O que aconteceu na seção fora do arquivo",
     "por exemplo, a demora de uma mesa para emitir o BU: está nas atas, não nos arquivos"),
]


def veredicto() -> str:
    W = 1000
    corpo: list[str] = []
    corpo.append(rect(32, 96, W - 64, 82, "#E7F5EF", rx=12))
    corpo.append(rect(32, 96, 6, 82, GREEN, rx=3))
    corpo.append(_check(70, 137, r=16))
    corpo.append(text(100, 130, "Nenhuma evidência de manipulação, de contagem errada ou de dado",
                      size=17, weight=700))
    corpo.append(text(100, 154, "impossível nos arquivos públicos, em nenhum dos dois turnos.",
                      size=17, weight=700))

    y = 220
    corpo.append(text(32, y, f"O que foi verificado e o resultado ({len(VERIFICADO)})", size=15,
                      weight=700))
    meio = (len(VERIFICADO) + 1) // 2
    col_w = (W - 64 - 24) / 2
    y0 = y + 22
    for i, (rot, res) in enumerate(VERIFICADO):
        col, lin = divmod(i, meio)
        x = 32 + col * (col_w + 24)
        yy = y0 + lin * 50
        corpo.append(_check(x + 11, yy + 15, r=10))
        corpo.append(text(x + 30, yy + 14, f"{i + 1}. {rot}", size=13.5, weight=700))
        corpo.append(text(x + 30, yy + 33, res, size=12.5, fill=MUTED))
    y = y0 + meio * 50 + 26
    corpo.append(f'<line x1="32" y1="{y - 6}" x2="{W - 32}" y2="{y - 6}" stroke="{GRID}"/>')
    y += 22
    corpo.append(text(32, y, f"Não pode ser verificado com dados públicos ({len(NAO_VERIFICAVEL)})",
                      size=15, weight=700))
    y += 22
    for rot, res in NAO_VERIFICAVEL:
        corpo.append(f'<circle cx="43" cy="{y + 15}" r="10" fill="#FFFFFF" stroke="#B07800" '
                     'stroke-width="2"/>')
        corpo.append(text(43, y + 20, "?", size=13, weight=800, fill="#B07800", anchor="middle"))
        corpo.append(text(62, y + 14, rot, size=13.5, weight=700))
        corpo.append(text(62, y + 33, res, size=12.5, fill=MUTED))
        y += 50
    y += 10
    corpo.append(rect(32, y, W - 64, 40, SOFT, rx=10))
    corpo.append(text(48, y + 25, "12 pontos de transparência e registro pedem esclarecimento do "
                      "TSE; nenhum deles altera a contagem.", size=13, fill=INK))
    h = int(y + 40 + 76)
    titulo = "Veredicto da auditoria: eleição presidencial de 2026"
    subt = "19 verificações sobre os arquivos públicos dos dois turnos; método e números em docs/"
    desc = ("Infográfico do veredicto: nenhuma evidência de manipulação, de contagem errada ou de "
            "dado impossível nos arquivos públicos, em nenhum dos dois turnos. Verificado: "
            + "; ".join(f"{rot}: {res}" for rot, res in VERIFICADO)
            + ". Não pode ser verificado com dados públicos: "
            + "; ".join(f"{rot} ({res})" for rot, res in NAO_VERIFICAVEL)
            + ". 12 pontos pedem esclarecimento do TSE, nenhum altera a contagem.")
    fonte = "Fonte: docs/veredicto-auditoria-2026.md e documentos citados nele"
    return documento(W, h, titulo, desc, corpo, subt, fonte)


# ----------------------------------------------------------------------
# h) Capas: banner do README e social preview do GitHub (1280x640)
# ----------------------------------------------------------------------
_CAPA_FUNDO = """<defs>
<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
<stop offset="0" stop-color="#071F33"/><stop offset="0.55" stop-color="#0B3A5B"/>
<stop offset="1" stop-color="#0D4C77"/>
</linearGradient>
<pattern id="dots" width="32" height="32" patternUnits="userSpaceOnUse">
<circle cx="2" cy="2" r="1.6" fill="#FFFFFF" fill-opacity="0.06"/>
</pattern>
</defs>
<rect width="1280" height="640" fill="url(#bg)"/>
<rect width="1280" height="640" fill="url(#dots)"/>"""

# Logo (same drawing as docs/assets/logo.svg) on a translucent tile for dark backgrounds
_CAPA_LOGO = """<rect x="4" y="10" width="56" height="44" rx="9" fill="#FFFFFF" fill-opacity="0.08"/>
<rect x="4" y="10" width="56" height="44" rx="9" fill="none" stroke="#56B4E9" stroke-opacity="0.55" stroke-width="1.2"/>
<rect x="10" y="16" width="26" height="20" rx="3" fill="#E8F3FA"/>
<rect x="14" y="28" width="4" height="5" rx="1" fill="#0072B2"/>
<rect x="20" y="24" width="4" height="9" rx="1" fill="#009E73"/>
<rect x="26" y="20" width="4" height="13" rx="1" fill="#E69F00"/>
<g fill="#9CC9E6">
<rect x="41" y="17" width="5" height="4" rx="1"/><rect x="48" y="17" width="5" height="4" rx="1"/>
<rect x="41" y="23" width="5" height="4" rx="1"/><rect x="48" y="23" width="5" height="4" rx="1"/>
<rect x="41" y="29" width="5" height="4" rx="1"/><rect x="48" y="29" width="5" height="4" rx="1"/>
</g>
<rect x="41" y="36" width="12" height="5" rx="1.5" fill="#009E73"/>
<rect x="10" y="41" width="26" height="3" rx="1.5" fill="#56B4E9"/>
<rect x="10" y="47" width="16" height="2.5" rx="1.25" fill="#56B4E9" opacity=".6"/>"""


def _capa(titulo: str, descricao: str, corpo: list[str]) -> str:
    return "\n".join([
        '<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="640" viewBox="0 0 1280 640" '
        'role="img" aria-labelledby="t d">',
        f'<title id="t">{escape(titulo)}</title>',
        f'<desc id="d">{escape(descricao)}</desc>',
        _CAPA_FUNDO,
        *corpo,
        "</svg>",
    ]) + "\n"


def _pilula(x: float, y: float, rot: str, size: float, destaque: bool) -> tuple[str, float]:
    """Rounded chip; returns the SVG and its width."""
    w = largura_texto(rot, size, True) + 1.4 * size
    h = size * 2.2
    fundo = (f'fill="{ORANGE}"' if destaque
             else 'fill="#FFFFFF" fill-opacity="0.12" stroke="#FFFFFF" stroke-opacity="0.3"')
    svg = (f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{h / 2:.1f}" {fundo}/>'
           + text(x + w / 2, y + h / 2 + size * 0.36, rot, size=size, weight=600,
                  fill=NAVY if destaque else "#FFFFFF", anchor="middle"))
    return svg, w


def banner() -> str:
    corpo = [
        # Decorative chart, kept from the original identity
        '<g><rect x="852" y="200" width="340" height="340" rx="28" fill="#FFFFFF" fill-opacity="0.05" '
        'stroke="#FFFFFF" stroke-opacity="0.12"/>',
        '<rect x="884" y="380" width="34" height="130" rx="6" fill="#0072B2"/>'
        '<rect x="930" y="330" width="34" height="180" rx="6" fill="#56B4E9"/>'
        '<rect x="976" y="400" width="34" height="110" rx="6" fill="#009E73"/>'
        '<rect x="1022" y="290" width="34" height="220" rx="6" fill="#0072B2"/>'
        '<rect x="1068" y="350" width="34" height="160" rx="6" fill="#56B4E9"/>'
        '<rect x="1114" y="250" width="34" height="260" rx="6" fill="#E69F00"/>',
        '<polyline points="901,356 947,306 993,376 1039,266 1085,326 1131,226" fill="none" '
        'stroke="#FFFFFF" stroke-opacity="0.75" stroke-width="4" stroke-linejoin="round" '
        'stroke-linecap="round"/>',
        '<g fill="#FFFFFF">' + "".join(f'<circle cx="{x}" cy="{y}" r="6"/>' for x, y in (
            (901, 356), (947, 306), (993, 376), (1039, 266), (1085, 326), (1131, 226))) + "</g>",
        '<line x1="872" y1="512" x2="1172" y2="512" stroke="#FFFFFF" stroke-opacity="0.35" '
        'stroke-width="2"/></g>',
        f'<g transform="translate(88 64) scale(2)">{_CAPA_LOGO}</g>',
        f'<g font-family="{FONT}" fill="#FFFFFF">',
        '<text x="96" y="300" font-size="88" font-weight="800" letter-spacing="-2">DataUrnas'
        '<tspan fill="#56B4E9">-BR</tspan></text>',
        text(98, 358, "Auditoria independente dos arquivos", size=31, weight=500, fill="#FFFFFF",
             extra=' fill-opacity="0.92"'),
        text(98, 398, "públicos da urna eletrônica", size=31, weight=500, fill="#FFFFFF",
             extra=' fill-opacity="0.92"'),
    ]
    x = 96.0
    for rot, destaque in (("2022: 941.987 seções", False), ("2026: Presidente, 1º e 2º turnos", True)):
        svg, w = _pilula(x, 446, rot, 21, destaque)
        corpo.append(svg)
        x += w + 16
    corpo.append(text(98, 548, "Código aberto · Dados públicos do TSE · Resultados reproduzíveis",
                      size=20, weight=500, fill="#FFFFFF", extra=' fill-opacity="0.75"'))
    corpo.append("</g>")
    return _capa("DataUrnas-BR",
                 "Auditoria independente dos arquivos públicos da urna eletrônica: eleições de 2022 "
                 "(941.987 seções) e eleição presidencial de 2026, 1º e 2º turnos.", corpo)


def social_preview() -> str:
    rdv1 = _json(DIR_2026 / "rdv" / "resumo.json")["totais"]
    rdv2 = _json(DIR_2026_T2 / "rdv_nacional_resumo.json")
    assin = _json(DIR_2026_T2 / "certificados_resumo.json")["verificacoes"]["assinaturas_arquivos"]
    secoes = int(rdv2["secoes"])
    diverg = int(rdv1["rdv_diverge"]) + int(rdv2["presidente_diverge"])
    corpo = [
        f'<g transform="translate(72 52) scale(1.6)">{_CAPA_LOGO}</g>',
        f'<g font-family="{FONT}" fill="#FFFFFF">',
        '<text x="190" y="128" font-size="72" font-weight="800" letter-spacing="-1.5">DataUrnas'
        '<tspan fill="#56B4E9">-BR</tspan></text>',
        text(78, 216, "Auditoria independente das urnas eletrônicas", size=40, weight=700,
             fill="#FFFFFF"),
    ]
    svg, _ = _pilula(78, 248, "Eleição presidencial de 2026: 1º e 2º turnos", 24, True)
    corpo.append(svg)
    stats = [
        (fmt_int(secoes), "seções verificadas", "em cada turno"),
        (fmt_int(diverg), "divergências", "na recontagem do RDV"),
        (fmt_num(assin["ok"] / 1e6, 2).rstrip("0").rstrip(",") + " mi", "assinaturas válidas",
         f"{fmt_int(assin['falha'])} inválidas (2º turno)"),
    ]
    cw, gap = 360, 22
    for i, (num, rot, sub) in enumerate(stats):
        x = 78 + i * (cw + gap)
        corpo.append(rect(x, 342, cw, 190, "#FFFFFF", rx=20,
                          extra=' fill-opacity="0.08" stroke="#FFFFFF" stroke-opacity="0.18"'))
        corpo.append(rect(x, 342, 8, 190, [LIGHT_BLUE, GREEN, ORANGE][i], rx=4))
        corpo.append(text(x + 34, 428, num, size=66, weight=800, fill="#FFFFFF"))
        corpo.append(text(x + 34, 474, rot, size=27, weight=700, fill="#FFFFFF"))
        corpo.append(text(x + 34, 508, sub, size=22, weight=500, fill="#FFFFFF",
                          extra=' fill-opacity="0.78"'))
    corpo.append(text(78, 590, "Código aberto · Dados públicos do TSE · Resultados reproduzíveis",
                      size=24, weight=500, fill="#FFFFFF", extra=' fill-opacity="0.78"'))
    corpo.append("</g>")
    return _capa("DataUrnas-BR",
                 f"Auditoria independente das urnas eletrônicas, eleição presidencial de 2026, 1º e 2º "
                 f"turnos: {fmt_int(secoes)} seções verificadas em cada turno, {fmt_int(diverg)} "
                 f"divergências na recontagem do RDV e {fmt_int(assin['ok'])} assinaturas válidas.",
                 corpo)


def rasterizar(svg: Path, png: Path, zoom: float = 1.0) -> bool:
    """Render an SVG to PNG with rsvg-convert and strip every metadata field from the PNG."""
    rsvg = shutil.which("rsvg-convert")
    if not rsvg:
        print("rsvg-convert não encontrado; PNG ignorado", file=sys.stderr)
        return False
    png.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([rsvg, "-z", str(zoom), "-o", str(png), str(svg)], check=True)
    exiftool = shutil.which("exiftool")
    if exiftool:
        subprocess.run([exiftool, "-q", "-all=", "-overwrite_original", str(png)], check=True)
    else:
        print(f"exiftool não encontrado; metadados de {png.name} não removidos", file=sys.stderr)
    return True


GERADORES = {
    "2026-ranking.svg": ranking,
    "2026-mapa-lider.svg": mapa_lider,
    "2026-comparecimento.svg": comparecimento,
    "2022-cobertura.svg": cobertura_2022,
    "arquitetura.svg": arquitetura,
    "2026-t2-resultado.svg": resultado_t2,
    "2026-t2-mapa-lider.svg": mapa_lider_t2,
    "2026-t2-comparecimento.svg": comparecimento_t2,
    "2026-t2-integridade.svg": integridade_t2,
    "2026-veredicto.svg": veredicto,
    "banner.svg": banner,
}

# PNG covers: name -> SVG in docs/assets (rendered from the file) or a generator whose SVG
# is only rendered from a temporary file and not kept
CAPAS_PNG = {
    "banner.png": "banner.svg",
    "social-preview.png": social_preview,
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--png", type=Path, help="diretório para também gerar PNG (rsvg-convert)")
    ap.add_argument("--only", nargs="*", choices=sorted([*GERADORES, *CAPAS_PNG]),
                    help="gerar só estas")
    args = ap.parse_args()
    if not (PARQUET / "2026" / "candidatos.parquet").exists():
        print("Dados de 2026 não encontrados em data/parquet/2026", file=sys.stderr)
        return 1
    ASSETS.mkdir(parents=True, exist_ok=True)
    print("Gerando ilustrações:")
    alvos = args.only or [*GERADORES, *CAPAS_PNG]
    for nome in alvos:
        if nome in CAPAS_PNG:
            continue
        destino = salvar(nome, GERADORES[nome]())
        if args.png:
            rasterizar(destino, args.png / destino.with_suffix(".png").name, zoom=1.5)
    for nome in alvos:
        fonte = CAPAS_PNG.get(nome)
        if fonte is None:
            continue
        destino = ASSETS / nome
        if isinstance(fonte, str):
            ok = rasterizar(ASSETS / fonte, destino)
        else:
            with tempfile.TemporaryDirectory() as tmp:
                svg = Path(tmp) / destino.with_suffix(".svg").name
                svg.write_text(fonte(), encoding="utf-8")
                ok = rasterizar(svg, destino)
        if ok:
            print(f"  {destino.relative_to(ROOT)} ({destino.stat().st_size / 1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
