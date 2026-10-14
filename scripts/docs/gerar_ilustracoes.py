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

Uso:
    python scripts/docs/gerar_ilustracoes.py            # gera todas
    python scripts/docs/gerar_ilustracoes.py --png DIR  # também rasteriza em DIR
                                                         # (requer rsvg-convert)
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

import duckdb  # noqa: E402

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
    "se": (3.2, -2.4), "df": (2.2, 0.1), "ac": (1.2, 0.4), "es": (3.2, -0.2), "rj": (2.6, -2.0),
    "sc": (3.3, -0.2),
}
# Ajuste fino (graus) de rótulos que ficam dentro do estado
_ROTULO_AJUSTE = {"mg": (0.4, -1.2)}


def mapa_lider() -> str:
    cand = load_candidatos()
    nomes = {int(r["numero"]): (nome_proprio(str(r["nome_urna"])), str(r["partido_sigla"]))
             for _, r in cand.iterrows()}
    uf = load_resultado_uf()
    vcols = [c for c in uf.columns if c.startswith("v_")]
    uf = uf.assign(lider=uf[vcols].idxmax(axis=1).str[2:].astype(int),
                   pct=uf[vcols].max(axis=1) / uf["votos_validos"] * 100)
    dados = {r["uf"]: r for _, r in uf.iterrows()}
    lideres = (uf[uf["uf"] != UF_EXTERIOR]["lider"].value_counts().index.tolist())
    paleta = [(BLUE, "#A9D3EE"), (ORANGE, "#F6D9A0"), (GREEN, "#A6DCC9"), (NAVY, "#9DB3C4")]
    cores = {num: paleta[i % len(paleta)] for i, num in enumerate(lideres)}

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
        cor = forte if r["pct"] >= 50 else claro
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
    corpo.append(text(lx + 26, ly + 1, "50% dos válidos ou mais", size=13, fill=MUTED))
    ly += 26
    corpo.append(rect(lx, ly - 13, 18, 18, "#C9D6E0", rx=4))
    corpo.append(text(lx + 26, ly + 1, "menos de 50% dos válidos", size=13, fill=MUTED))
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
    titulo = "Quem liderou em cada UF, 1º turno de 2026"
    subt = "Presidente: candidato mais votado por unidade da federação; tom forte indica 50% dos válidos ou mais"
    desc = "Mapa do Brasil por UF colorido pelo candidato mais votado. " + "; ".join(
        f"{UF_NOMES.get(s, s.upper())}: {nomes[int(dados[s]['lider'])][0]} com "
        f"{fmt_pct(dados[s]['pct'], 1)}" for s in sorted(dados) if s != UF_EXTERIOR) + "."
    fonte = FONTE_2026 + "; malha: IBGE"
    return documento(W, H, titulo, desc, corpo, subt, fonte)


# ----------------------------------------------------------------------
# c) Comparecimento 2022 x 2026
# ----------------------------------------------------------------------
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
    valores = [v for _, a, b, _ in linhas for v in (a, b)]
    vmin = math.floor(min(valores) / 2) * 2 - 1
    vmax = math.ceil(max(valores) / 2) * 2 + 1
    W = 1000
    top = 150
    alt = 24
    x0, x1 = 250, W - 170

    def px(v: float) -> float:
        return x0 + (v - vmin) / (vmax - vmin) * (x1 - x0)

    corpo: list[str] = []
    # Legenda
    corpo.append(f'<circle cx="56" cy="104" r="7" fill="{LIGHT_BLUE}" stroke="{BLUE}" stroke-width="1.5"/>')
    corpo.append(text(70, 109, "1º turno de 2022", size=13.5, fill=INK))
    corpo.append(f'<circle cx="206" cy="104" r="7" fill="{NAVY}"/>')
    corpo.append(text(220, 109, "1º turno de 2026", size=13.5, fill=INK))
    corpo.append(text(x1 + 30, 109, "Variação", size=13, weight=700, fill=MUTED))
    corpo.append(text(x1 + 110, 109, "2026", size=13, weight=700, fill=MUTED))
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
        corpo.append(text(x1 + 110, y + 4.5, fmt_pct(b, 1), size=12, fill=MUTED))
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


GERADORES = {
    "2026-ranking.svg": ranking,
    "2026-mapa-lider.svg": mapa_lider,
    "2026-comparecimento.svg": comparecimento,
    "2022-cobertura.svg": cobertura_2022,
    "arquitetura.svg": arquitetura,
}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--png", type=Path, help="diretório para também gerar PNG (rsvg-convert)")
    ap.add_argument("--only", nargs="*", choices=sorted(GERADORES), help="gerar só estas")
    args = ap.parse_args()
    if not (PARQUET / "2026" / "candidatos.parquet").exists():
        print("Dados de 2026 não encontrados em data/parquet/2026", file=sys.stderr)
        return 1
    ASSETS.mkdir(parents=True, exist_ok=True)
    print("Gerando ilustrações:")
    for nome in args.only or GERADORES:
        destino = salvar(nome, GERADORES[nome]())
        if args.png:
            rsvg = shutil.which("rsvg-convert")
            if not rsvg:
                print("rsvg-convert não encontrado; PNG ignorado", file=sys.stderr)
                continue
            args.png.mkdir(parents=True, exist_ok=True)
            subprocess.run([rsvg, "-z", "1.5", "-o", str(args.png / destino.with_suffix(".png").name),
                            str(destino)], check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
