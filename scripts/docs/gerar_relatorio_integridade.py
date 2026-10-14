#!/usr/bin/env python3
"""Gera o relatório de integridade dos arquivos de urna de 2026 a partir dos dados coletados.

Lê ``data/parquet/2026/integridade`` (catálogo de arquivos, resumo por seção e
``resumo.json``) e escreve:

- ``docs/relatorio-integridade-2026.md``: metodologia, o que fica comprovado e o
  que não fica, totais, tabela por UF, divergências e como conferir uma seção à mão.
- ``docs/assets/2026-integridade.svg``: cobertura e resultado por UF, no mesmo
  estilo das demais ilustrações (helpers de ``gerar_ilustracoes.py``).

Funciona com coleta parcial ou ausente e informa sempre a cobertura real.

Uso:
    python scripts/docs/gerar_relatorio_integridade.py
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd  # noqa: E402
from gerar_ilustracoes import (  # noqa: E402
    BLUE,
    GREEN,
    GRID,
    INK,
    LIGHT_BLUE,
    MUTED,
    SOFT,
    documento,
    fmt_int,
    fmt_pct,
    largura_texto,
    rect,
    text,
)

from dataurnas.config import TSE_BASE_URL  # noqa: E402
from dataurnas.dashboard import data2026 as d26  # noqa: E402
from dataurnas.dashboard import integridade2026 as ig  # noqa: E402

VERMELHO = "#D55E00"
SAIDA_MD = ROOT / "docs" / "relatorio-integridade-2026.md"
SAIDA_SVG = ROOT / "docs" / "assets" / "2026-integridade.svg"
CICLO, PLEITO = "ele2026", "3220"
MAX_DIVERGENCIAS = 500


def _pct(parte: float, todo: float) -> float:
    return parte / todo * 100 if todo else 0.0


# ----------------------------------------------------------------------
# SVG
# ----------------------------------------------------------------------
def svg_integridade(t: dict, tab: pd.DataFrame) -> str:
    W = 1000
    corpo: list[str] = []
    titulo = "Integridade dos arquivos de urna, 1º turno de 2026"
    situacao = "concluída" if t["cobertura_pct"] >= 100 else "em andamento"
    subt = (f"SHA-512 recalculado x valor assinado pela urna; verificação {situacao}, "
            f"{fmt_pct(t['cobertura_pct'], 1)} das seções instaladas")

    # Faixa de indicadores
    cartoes = [
        ("Seções verificadas", fmt_int(t["verificadas"]), BLUE),
        ("Hashes conferidos", fmt_int(t["hash_confere"]), GREEN),
        ("Divergências", fmt_int(t["secoes_divergentes"]), VERMELHO if t["secoes_divergentes"] else GREEN),
        ("Assinaturas válidas", fmt_int(t["assinaturas_validas"]), GREEN),
    ]
    cw = (W - 64 - 3 * 16) / 4
    for i, (rot, val, cor) in enumerate(cartoes):
        x = 32 + i * (cw + 16)
        corpo.append(rect(x, 96, cw, 70, SOFT, rx=12))
        corpo.append(rect(x, 96, 5, 70, cor, rx=2))
        corpo.append(text(x + 18, 122, rot, size=13, fill=MUTED))
        corpo.append(text(x + 18, 153, val, size=24, weight=700))

    linhas = tab.sort_values(["cobertura_pct", "uf"], ascending=[False, True]) if not tab.empty else tab
    top, alt = 214, 22
    x0, x1 = 210, W - 230
    if linhas.empty:
        corpo.append(text(W / 2, top + 40, "Nenhuma seção verificada ainda.", size=16, fill=MUTED,
                          anchor="middle"))
        h = top + 120
    else:
        corpo.append(text(32, top - 16, "Cobertura por UF", size=14, weight=700))
        corpo.append(text(x1 + 16, top - 16, "Seções", size=13, weight=700, fill=MUTED))
        corpo.append(text(W - 32, top - 16, "Divergências", size=13, weight=700, fill=MUTED, anchor="end"))
        for v in (0, 25, 50, 75, 100):
            x = x0 + (x1 - x0) * v / 100
            fim = top + len(linhas) * alt
            corpo.append(f'<line x1="{x:.1f}" y1="{top - 6}" x2="{x:.1f}" y2="{fim}" stroke="{GRID}" '
                         f'stroke-width="1"/>')
            corpo.append(text(x, fim + 16, f"{v}%", size=11.5, fill=MUTED, anchor="middle"))
        for i, (_, r) in enumerate(linhas.iterrows()):
            y = top + i * alt
            if i % 2 == 0:
                corpo.append(rect(24, y - 1, W - 48, alt, SOFT, rx=6))
            nome = f"{r['nome'] or r['uf'].upper()} ({r['uf'].upper()})"
            corpo.append(text(36, y + 15, nome, size=12.5))
            w = (x1 - x0) * min(float(r["cobertura_pct"]), 100) / 100
            cor = VERMELHO if r["secoes_divergentes"] else (GREEN if r["completa"] else LIGHT_BLUE)
            corpo.append(rect(x0, y + 4, max(w, 2), alt - 9, cor, rx=3))
            corpo.append(text(x0 + max(w, 2) + 6 if w < (x1 - x0) - 50 else x0 + w - 6, y + 15,
                              fmt_pct(r["cobertura_pct"], 1), size=11.5, fill=INK,
                              anchor="start" if w < (x1 - x0) - 50 else "end"))
            corpo.append(text(x1 + 16, y + 15, f"{fmt_int(r['verificadas'])} de {fmt_int(r['secoes_instaladas'])}",
                              size=12, fill=MUTED))
            div = int(r["secoes_divergentes"])
            corpo.append(text(W - 32, y + 15, fmt_int(div), size=12.5, weight=700 if div else 400,
                              fill=VERMELHO if div else MUTED, anchor="end"))
        h = top + len(linhas) * alt + 40
        # Legenda
        lx = 32
        for cor, rot in ((GREEN, "UF concluída"), (LIGHT_BLUE, "em andamento"),
                         (VERMELHO, "com divergência")):
            corpo.append(rect(lx, h - 12, 14, 14, cor, rx=3))
            corpo.append(text(lx + 20, h, rot, size=12.5, fill=MUTED))
            lx += 20 + largura_texto(rot, 12.5) + 28
        h += 70
    desc = (f"{fmt_int(t['verificadas'])} seções verificadas de {fmt_int(t['instaladas'])} instaladas "
            f"({fmt_pct(t['cobertura_pct'], 1)}); {fmt_int(t['hash_confere'])} hashes SHA-512 conferem, "
            f"{fmt_int(t['hash_diverge'])} divergem; {fmt_int(t['assinaturas_validas'])} assinaturas válidas; "
            f"{fmt_int(t['secoes_divergentes'])} seções com divergência.")
    fonte = "Fonte: arquivos de urna publicados pelo TSE (resultados.tse.jus.br); verificação DataUrnas-BR"
    return documento(W, int(h), titulo, desc, corpo, subt, fonte)


# ----------------------------------------------------------------------
# Markdown
# ----------------------------------------------------------------------
def _tabela(cab: list[str], linhas: list[list[str]], alinhamento: list[str]) -> str:
    out = ["| " + " | ".join(cab) + " |", "|" + "|".join(alinhamento) + "|"]
    out += ["| " + " | ".join(lin) + " |" for lin in linhas]
    return "\n".join(out)


def _exemplo(pasta: Path, secoes: pd.DataFrame) -> dict | None:
    """Primeira seção verificada com BU catalogado, para a receita de conferência manual."""
    ok = secoes[(secoes["status_secao"] == "ok") & (secoes["n_hash_confere"] > 0)]
    if ok.empty:
        return None
    r = ok.iloc[0]
    arqs = ig.arquivos_da_secao(r["uf"], r["cd_mun"], r["zona"], r["secao"], pasta)
    bu = arqs[arqs["tipo"] == "bu"]
    if bu.empty:
        return None
    a = bu.iloc[0]
    return {"uf": r["uf"], "cd_mun": r["cd_mun"], "zona": r["zona"], "secao": r["secao"],
            "nome": a["nome"], "token": a["token_tse"], "sha512_assinado": a["sha512_assinado"]}


def relatorio_md(t: dict, tab: pd.DataFrame, div: pd.DataFrame, resumo: dict, exemplo: dict | None,
                 nomes_mun: dict) -> str:
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    concluida = t["cobertura_pct"] >= 100
    p: list[str] = []
    p.append("# Relatório de integridade dos arquivos de urna: 1º turno de 2026\n")
    status = "**Concluída.**" if concluida else "**Em andamento.**"
    p.append(f"> {status} Cobertura: {fmt_pct(t['cobertura_pct'])} das seções instaladas verificadas "
             f"({fmt_int(t['verificadas'])} de {fmt_int(t['instaladas'])}). Relatório gerado em {agora} por "
             "`scripts/docs/gerar_relatorio_integridade.py`; os números mudam a cada nova execução enquanto a "
             "verificação não termina.\n")
    horarios = ig.texto_horarios(resumo)
    if horarios:
        p.append(f"Registro da coleta: {horarios}.\n")
    p.append('<p align="center">\n  <img src="assets/2026-integridade.svg" alt="Cobertura da verificação de '
             f'integridade por UF: {fmt_int(t["verificadas"])} seções verificadas, '
             f'{fmt_int(t["secoes_divergentes"])} com divergência" width="100%">\n</p>\n')

    p.append("## Como funciona o mecanismo\n")
    p.append(
        "Ao encerrar a votação, cada urna grava o Boletim de Urna (`bu.dat`), o Registro Digital do Voto "
        "(`rdv.dat`) e o log (`log.jez`). Ela calcula o resumo **SHA-512** de cada um desses arquivos e grava os "
        "resumos num arquivo de assinatura (`.vsc`), assinado com a chave privada da própria urna. O TSE publica "
        "todos esses arquivos por seção, junto com um `aux.json` que lista os nomes e o diretório de publicação.\n"
    )
    p.append("A verificação feita pelo projeto, para cada seção:\n")
    p.append(
        "1. baixa os arquivos publicados e calcula MD5, SHA-256 e SHA-512 de cada um;\n"
        "2. lê do `.vsc` o SHA-512 assinado de cada arquivo coberto e compara com o calculado (`hash_confere`);\n"
        "3. verifica a assinatura do `.vsc` com a chave pública do certificado que o acompanha e registra "
        "algoritmo, titular, emissor, número de série e SHA-256 do certificado;\n"
        "4. registra o token do `aux.json` (32 bytes em base64url) e a data e hora informadas pelo TSE.\n"
    )
    p.append(
        "MD5 e SHA-256 não fazem parte do mecanismo da urna: ficam no catálogo para facilitar conferências com "
        "outras fontes. O token do `aux.json` identifica o conjunto publicado e não é o hash de nenhum arquivo "
        "isolado; por isso é registrado e não comparado.\n"
    )

    p.append("## O que fica comprovado e o que não fica\n")
    p.append(
        "**Comprovado, para cada seção verificada sem divergência:** os arquivos `bu.dat`, `rdv.dat` e `log.jez` "
        "publicados pelo TSE têm exatamente o conteúdo cujo SHA-512 está no arquivo de assinatura, e esse "
        "arquivo de assinatura foi assinado pela chave correspondente ao certificado que o acompanha.\n"
    )
    p.append(
        "**Não comprovado por esta verificação:**\n\n"
        "- que o software da urna é o oficial, nem que funcionou corretamente;\n"
        "- que o certificado pertence à urna física daquela seção além do que os campos dele declaram, "
        "salvo onde a cadeia de certificação for validada;\n"
        "- que os votos registrados correspondem à intenção dos eleitores;\n"
        "- nada sobre arquivos que a assinatura não cobre (imagem do BU, o próprio `.vsc` e outros).\n"
    )
    p.append("Uma divergência indica que o arquivo publicado não corresponde ao que a urna assinou e merece "
             "investigação; não é, por si só, prova de adulteração (pode haver falha de publicação, de "
             "download ou de leitura). Ausência de divergência também não prova a lisura da eleição.\n")

    p.append("## Totais\n")
    conferidos = t["hash_confere"] + t["hash_diverge"]
    p.append(_tabela(["Métrica", "Valor"], [
        ["Seções instaladas (oficial)", fmt_int(t["instaladas"])],
        ["Seções verificadas", f"{fmt_int(t['verificadas'])} ({fmt_pct(t['cobertura_pct'])})"],
        ["Seções agregadas a outra", fmt_int(t["agregadas"])],
        ["Seções não instaladas", fmt_int(t["nao_instaladas"])],
        ["Seções sem arquivos publicados", fmt_int(t["sem_arquivos"])],
        ["Arquivos catalogados", fmt_int(t["arquivos"])],
        ["SHA-512 comparados", fmt_int(conferidos)],
        ["SHA-512 iguais ao assinado", f"{fmt_int(t['hash_confere'])} ({fmt_pct(_pct(t['hash_confere'], conferidos))})"],
        ["SHA-512 diferentes do assinado", fmt_int(t["hash_diverge"])],
        ["Arquivos fora da assinatura", fmt_int(t["sem_hash"])],
        ["Assinaturas válidas", fmt_int(t["assinaturas_validas"])],
        ["Assinaturas inválidas", fmt_int(t["assinaturas_invalidas"])],
        ["Assinaturas não verificadas", fmt_int(t["assinaturas_nao_verificadas"])],
        ["Seções com alguma divergência", fmt_int(t["secoes_divergentes"])],
    ], ["---", "---:"]) + "\n")

    p.append("## Por UF\n")
    if tab.empty:
        p.append("Nenhuma UF verificada ainda.\n")
    else:
        linhas = [[r["uf"].upper(), str(r["nome"] or "-"), fmt_int(r["secoes_instaladas"]), fmt_int(r["verificadas"]),
                   fmt_pct(r["cobertura_pct"], 1), fmt_int(r["hash_confere"]), fmt_int(r["hash_diverge"]),
                   fmt_int(r["assinaturas_validas"]), fmt_int(r["secoes_divergentes"])]
                  for _, r in tab.iterrows()]
        p.append(_tabela(["UF", "Nome", "Instaladas", "Verificadas", "Cobertura", "SHA-512 conferem",
                          "SHA-512 divergem", "Assinaturas válidas", "Seções divergentes"], linhas,
                         ["---", "---", "---:", "---:", "---:", "---:", "---:", "---:", "---:"]) + "\n")

    p.append("## Divergências\n")
    if div.empty:
        if t["verificadas"]:
            p.append(f"Nenhuma divergência encontrada nas {fmt_int(t['verificadas'])} seções verificadas"
                     + ("." if concluida else ", de um total de "
                        f"{fmt_int(t['instaladas'])} instaladas; a verificação continua.") + "\n")
        else:
            p.append("Nenhuma seção verificada ainda.\n")
    else:
        mostrar = div.head(MAX_DIVERGENCIAS)
        linhas = [[r["uf"].upper(), nomes_mun.get((r["uf"], r["cd_mun"]), r["cd_mun"]), r["cd_mun"], r["zona"],
                   r["secao"], r["problemas"]] for _, r in mostrar.iterrows()]
        p.append(f"{fmt_int(len(div))} seção(ões) com divergência entre {fmt_int(t['verificadas'])} verificadas"
                 + (f" (listadas as primeiras {fmt_int(MAX_DIVERGENCIAS)})" if len(div) > MAX_DIVERGENCIAS else "")
                 + ".\n")
        p.append(_tabela(["UF", "Município", "Código", "Zona", "Seção", "Problemas"], linhas,
                         ["---", "---", "---", "---", "---", "---"]) + "\n")

    p.append("## Como conferir uma seção por conta própria\n")
    ex = exemplo or {"uf": "ac", "cd_mun": "01007", "zona": "0009", "secao": "0001",
                     "nome": "<nome do arquivo -bu.dat>", "token": "<token>", "sha512_assinado": None}
    uf, mun, zona, sec = ex["uf"], ex["cd_mun"], ex["zona"], ex["secao"]
    base = f"{TSE_BASE_URL}/{CICLO}/arquivo-urna/{PLEITO}/dados/{uf}/{mun}/{zona}/{sec}"
    p.append(f"Exemplo com a seção {sec} da zona {zona}, município {mun} ({uf.upper()}). Troque os códigos para "
             "conferir qualquer outra.\n")
    p.append("1. Baixe o `aux.json` da seção e anote o diretório (`hash`) e os nomes dos arquivos (`arq`):\n")
    p.append(f"```bash\ncurl -sO {base}/p{int(PLEITO):06d}-{uf}-m{mun}-z{zona}-s{sec}-aux.json\n```\n")
    p.append("2. Baixe o BU e o arquivo de assinatura (`-vota.vsc`) do diretório indicado:\n")
    p.append(f"```bash\ncurl -sO {base}/{ex['token']}/{ex['nome']}\n"
             f"curl -sO {base}/{ex['token']}/<nome do arquivo -vota.vsc>\n```\n")
    p.append("3. Calcule o SHA-512 do arquivo (sem dependências além do Python):\n")
    p.append(f'```bash\npython3 -c "import hashlib,sys; print(hashlib.sha512(open(sys.argv[1],\'rb\').read())'
             f'.hexdigest())" {ex["nome"]}\n# alternativa: shasum -a 512 {ex["nome"]}\n```\n')
    p.append("4. Leia o SHA-512 que a urna assinou, com o leitor do projeto, e compare:\n")
    p.append('```bash\npython3 -c "from dataurnas.parsers.signature import SignatureParser as P; '
             "[print(k, v.hex()) for k, v in P().extract_file_hashes('<arquivo>-vota.vsc').items()]\"\n```\n")
    if ex.get("sha512_assinado"):
        p.append(f"Para esta seção, o valor assinado do BU registrado no catálogo é:\n\n```\n{ex['sha512_assinado']}\n```\n")
    p.append("O resultado do passo 3 deve ser idêntico ao do passo 4 (e ao valor do catálogo em "
             "`data/parquet/2026/integridade/arquivos_<uf>.parquet`, coluna `sha512_assinado`). O painel, na "
             "página **Integridade dos arquivos (2026)**, mostra os mesmos valores para qualquer seção.\n")

    p.append("## Reproduzir este relatório\n")
    p.append("```bash\npython scripts/docs/gerar_relatorio_integridade.py\n```\n")
    p.append("Os dados de entrada ficam em `data/parquet/2026/integridade` (`arquivos_<uf>.parquet`, `secoes.parquet` "
             "e `resumo.json`); o número de seções instaladas vem de `data/parquet/2026/resultado_uf.parquet`. "
             "Veja também a [metodologia](metodologia.md#integridade-em-2026) e as "
             "[perguntas frequentes](faq.md).\n")
    return "\n".join(p)


# ----------------------------------------------------------------------
def gerar(pasta: Path | None = None, res_uf: pd.DataFrame | None = None, res_mun: pd.DataFrame | None = None,
          saida_md: Path = SAIDA_MD, saida_svg: Path = SAIDA_SVG) -> dict:
    pasta = pasta or ig.integ_dir()
    res_uf = d26.load_resultado_uf() if res_uf is None else res_uf
    res_mun = d26.load_resultado_municipio() if res_mun is None else res_mun
    dados = ig.load_secoes(pasta)
    t = ig.totais(dados.secoes, res_uf)
    tab = ig.por_uf(dados.secoes, res_uf) if not dados.vazio else pd.DataFrame()
    div = ig.divergencias(dados.secoes)
    nomes = ({(u, m): str(n).title() for u, m, n in zip(res_mun["uf"], res_mun["cd_mun"], res_mun["nome"],
                                                        strict=False)} if not res_mun.empty else {})
    exemplo = _exemplo(pasta, dados.secoes) if not dados.vazio else None
    md = relatorio_md(t, tab, div, ig.load_resumo(pasta), exemplo, nomes)
    if dados.vazio:
        md = md.replace("## Totais\n", "## Totais\n\nA verificação ainda não gravou dados: os totais abaixo estão "
                                        "zerados.\n", 1)
    saida_md.parent.mkdir(parents=True, exist_ok=True)
    saida_svg.parent.mkdir(parents=True, exist_ok=True)
    saida_md.write_text(md, encoding="utf-8")
    saida_svg.write_text(svg_integridade(t, tab), encoding="utf-8")
    return t


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pasta", type=Path, help="diretório da integridade (padrão: data/parquet/2026/integridade)")
    ap.add_argument("--md", type=Path, default=SAIDA_MD)
    ap.add_argument("--svg", type=Path, default=SAIDA_SVG)
    args = ap.parse_args()
    t = gerar(args.pasta, saida_md=args.md, saida_svg=args.svg)
    print(f"Cobertura: {fmt_pct(t['cobertura_pct'])} ({fmt_int(t['verificadas'])} de {fmt_int(t['instaladas'])} "
          f"seções); divergências: {fmt_int(t['secoes_divergentes'])}")
    for p in (args.md, args.svg):
        print(f"  {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
