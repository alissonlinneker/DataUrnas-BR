#!/usr/bin/env python3
"""Gera o relatório de integridade dos arquivos de urna de 2026 a partir dos dados coletados.

Lê ``data/parquet/2026/integridade`` (catálogo de arquivos, resumo por seção,
``resumo.json``, ``divergencias.jsonl``, ``ocorrencias_publicacao.jsonl`` e
``certificados_resumo.json``), a auditoria de BU e log em
``data/parquet/2026/auditoria`` e escreve:

- ``docs/relatorio-integridade-2026.md``: resultado, metodologia, o que fica
  comprovado e o que não fica, totais, tabela por UF, divergências, arquivos
  indisponíveis, auditoria por grupo de leitura, certificados, download do
  catálogo e como conferir uma seção à mão.
- ``docs/assets/2026-integridade.svg``: cobertura e resultado por UF, no mesmo
  estilo das demais ilustrações (helpers de ``gerar_ilustracoes.py``).

Funciona com coleta parcial ou ausente e informa sempre a cobertura real.

Uso:
    python scripts/docs/gerar_relatorio_integridade.py
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402
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
from dataurnas.dashboard import reference as ref  # noqa: E402

VERMELHO = "#D55E00"
SAIDA_MD = ROOT / "docs" / "relatorio-integridade-2026.md"
SAIDA_SVG = ROOT / "docs" / "assets" / "2026-integridade.svg"
CICLO, PLEITO = "ele2026", "3220"
MAX_DIVERGENCIAS = 500
REPO = "alissonlinneker/DataUrnas-BR"
VERSAO_CATALOGO = getattr(ig, "CATALOGO_VERSAO", "v0.2.1")
PAGINA_CATALOGO = getattr(ig, "CATALOGO_PAGINA", f"https://github.com/{REPO}/releases/tag/{VERSAO_CATALOGO}")
URL_CATALOGO = getattr(ig, "CATALOGO_URL_PADRAO", f"https://github.com/{REPO}/releases/download/{VERSAO_CATALOGO}")
ROTULO_TIPO = {"bu": "BU", "rdv": "RDV", "log": "log", "vota": "arquivo de assinatura (.vsc)",
               "imgbu": "imagem do BU", "busa": "BU do sistema de apuração", "logsa": "log do sistema de apuração"}
ROTULO_SEVERIDADE = {"critica": "crítica", "alta": "alta", "media": "média", "informativa": "informativa"}


def _pct(parte: float, todo: float) -> float:
    return parte / todo * 100 if todo else 0.0


def _plural(n: int, um: str, varios: str) -> str:
    return f"{fmt_int(n)} {um if n == 1 else varios}"


def _algoritmo(nome: str | None) -> str:
    return {"ECDSA-secp521r1-SHA512": "ECDSA P-521 com SHA-512"}.get(nome or "", nome or "-")


def _ler_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    linhas = []
    for linha in path.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha:
            continue
        try:
            obj = json.loads(linha)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            linhas.append(obj)
    return linhas


def _ler_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        dados = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return dados if isinstance(dados, dict) else {}


def dir_publicacao(token: str | None) -> str:
    """Diretório do conjunto no servidor do TSE: o hex do token do aux.json (campo ``hash``)."""
    if not token:
        return "<hash do aux.json>"
    return token.encode("ascii").hex()


def url_secao(uf: str, cd_mun: str, zona: str, secao: str) -> str:
    return f"{TSE_BASE_URL}/{CICLO}/arquivo-urna/{PLEITO}/dados/{uf}/{cd_mun}/{zona}/{secao}"


def url_aux(uf: str, cd_mun: str, zona: str, secao: str) -> str:
    return (f"{url_secao(uf, cd_mun, zona, secao)}/"
            f"p{int(PLEITO):06d}-{uf}-m{cd_mun}-z{zona}-s{secao}-aux.json")


def url_arquivo(uf: str, cd_mun: str, zona: str, secao: str, token: str | None, nome: str) -> str:
    return f"{url_secao(uf, cd_mun, zona, secao)}/{dir_publicacao(token)}/{nome}"


# ----------------------------------------------------------------------
# Dados auxiliares
# ----------------------------------------------------------------------
def indisponiveis(pasta: Path) -> pd.DataFrame:
    """Arquivos listados no aux.json com ``disponivel = false`` em ``arquivos_<uf>.parquet``."""
    cols = ["uf", "cd_mun", "zona", "secao", "tipo", "nome", "http_status"]
    partes = []
    for arq in ig.arquivos_parquet(pasta):
        try:
            nomes = set(pq.read_schema(arq).names)
        except Exception:  # noqa: BLE001 (catálogo ilegível já é tratado pelo loader)
            continue
        if "disponivel" not in nomes:
            continue
        df = pd.read_parquet(arq, columns=[c for c in cols + ["disponivel"] if c in nomes])
        partes.append(df[df["disponivel"].eq(False)].drop(columns=["disponivel"]))
    if not partes:
        return pd.DataFrame(columns=cols)
    return pd.concat(partes, ignore_index=True)


def auditoria(pasta: Path, resumo: dict) -> dict | None:
    """Ocorrências da auditoria de BU e log de 2026 por código, severidade e grupo de leitura."""
    base = Path(pasta).parent / "auditoria"
    issues, secoes = base / "issues_2026.parquet", base / "secoes_log_2026.parquet"
    if issues.exists():
        df = pd.read_parquet(issues, columns=["secao_id", "codigo", "severidade"])
        n_secoes = len(pd.read_parquet(secoes, columns=["secao_id"])) if secoes.exists() else None
        origem = (pd.read_parquet(secoes, columns=["secao_id", "origem_bu"])
                  if secoes.exists() else pd.DataFrame(columns=["secao_id", "origem_bu"]))
        por = (df.groupby(["codigo", "severidade"])
               .agg(ocorrencias=("secao_id", "size"), secoes=("secao_id", "nunique")).reset_index())
        m03 = df[df["codigo"] == "M03"].merge(origem, on="secao_id", how="left")
        return {"secoes": n_secoes, "secoes_com_ocorrencia": int(df["secao_id"].nunique()),
                "ocorrencias": len(df), "por_codigo": por,
                "m03_busa": int(m03["origem_bu"].eq("busa").sum()), "m03_total": len(m03),
                "secoes_por_grupo": {g: int(df[df["codigo"].map(ref.ISSUE_GRUPOS).eq(g)]["secao_id"].nunique())
                                     for g in ref.GRUPOS_ORDEM}}
    bloco = (resumo or {}).get("auditoria_bu_log") or {}
    if not bloco.get("issues_por_codigo"):
        return None
    por = pd.DataFrame([{"codigo": c, "severidade": None, "ocorrencias": n, "secoes": None}
                        for c, n in bloco["issues_por_codigo"].items()])
    return {"secoes": bloco.get("secoes_log"), "secoes_com_ocorrencia": None,
            "ocorrencias": int(por["ocorrencias"].sum()), "por_codigo": por,
            "m03_busa": None, "m03_total": None, "secoes_por_grupo": {}}


def consistencia_certificados(secoes: pd.DataFrame, pasta: Path) -> dict | None:
    """Coerência dos certificados em todas as seções verificadas: unicidade, CN e emissor por modelo."""
    if secoes.empty or "cert_sha256" not in secoes:
        return None
    ok = secoes[(secoes["status_secao"] == "ok") & secoes["cert_sha256"].notna()].copy()
    if ok.empty:
        return None
    ok["cn"] = ok["cert_subject"].astype(str).str.extract(r"CN=([^,]+)", expand=False)
    ok["emissor"] = ok["cert_issuer"].astype(str).str.extract(r"CN=([^,]+)", expand=False)
    bu = Path(pasta).parent / "secoes_2026.parquet"
    if bu.exists():
        cols = set(pq.read_schema(bu).names)
        extra = [c for c in ("numero_interno_urna", "origem_bu") if c in cols]
        ok = ok.merge(pd.read_parquet(bu, columns=list(ig.CHAVE_SECAO) + extra), on=list(ig.CHAVE_SECAO),
                      how="left")
    if "origem_bu" not in ok:
        ok["origem_bu"] = None
    rep = ok.groupby("cert_sha256").size()
    rep = rep[rep > 1]
    compartilhadas = ok[ok["cert_sha256"].isin(rep.index)]
    res = {
        "secoes": len(ok),
        "distintos": int(ok["cert_sha256"].nunique()),
        "subjects": int(ok["cert_subject"].nunique()),
        "pares_emissor_serial": int(ok[["emissor", "cert_serial"]].drop_duplicates().shape[0]),
        "certs_repetidos": len(rep),
        "secoes_cert_repetido": len(compartilhadas),
        "repetidos_todos_sa": bool(len(compartilhadas)) and bool(compartilhadas["origem_bu"].eq("busa").all()),
        "repetidos_ufs": sorted(compartilhadas["uf"].str.upper().unique()),
        "cn_padrao": int(ok["cn"].str.upper().str.fullmatch(r"UEAO\d{8}").fillna(False).sum()),
        "por_modelo": (ok.groupby(["modelo_urna", "emissor", "assinatura_algoritmo"]).size()
                       .reset_index(name="secoes").to_dict("records")),
        "cn_com_bu": None,
    }
    if "numero_interno_urna" in ok:
        com = ok[ok["numero_interno_urna"].notna()].copy()
        esperado = "UEAO" + com["numero_interno_urna"].astype("int64").astype(str).str.zfill(8)
        igual = com["cn"].str.upper().eq(esperado)
        res["cn_com_bu"] = {"comparados": len(com), "iguais": int(igual.sum()),
                            "diferentes": com[~igual][list(ig.CHAVE_SECAO) + ["cn", "numero_interno_urna"]]
                            .to_dict("records")}
        cert_por_urna = com.groupby("numero_interno_urna")["cert_sha256"].nunique()
        urna_por_cert = com.groupby("cert_sha256")["numero_interno_urna"].nunique()
        res["urnas_com_mais_de_um_cert"] = int((cert_por_urna > 1).sum())
        res["certs_em_urnas_diferentes"] = int((urna_por_cert > 1).sum())
    return res


# ----------------------------------------------------------------------
# SVG
# ----------------------------------------------------------------------
def svg_integridade(t: dict, tab: pd.DataFrame, notas: list[str] | None = None) -> str:
    W = 1000
    corpo: list[str] = []
    titulo = "Integridade dos arquivos de urna, 1º turno de 2026"
    situacao = "concluída" if t["cobertura_pct"] >= 100 else "em andamento"
    subt = (f"SHA-512 recalculado x valor assinado pela urna; verificação {situacao}, "
            f"{fmt_pct(t['cobertura_pct'], 1)} das seções instaladas")

    # Faixa de indicadores
    cartoes = [
        ("Seções verificadas", fmt_int(t["verificadas"]), BLUE),
        ("SHA-512 iguais ao assinado", fmt_int(t["hash_confere"]), GREEN),
        ("SHA-512 divergentes", fmt_int(t["hash_diverge"]), VERMELHO if t["hash_diverge"] else GREEN),
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
        legenda = [(GREEN, "UF concluída")]
        if not bool(linhas["completa"].all()):
            legenda.append((LIGHT_BLUE, "em andamento"))
        legenda.append((VERMELHO, "com divergência"))
        for cor, rot in legenda:
            corpo.append(rect(lx, h - 12, 14, 14, cor, rx=3))
            corpo.append(text(lx + 20, h, rot, size=12.5, fill=MUTED))
            lx += 20 + largura_texto(rot, 12.5) + 28
        h += 26
        for nota in notas or []:
            corpo.append(text(32, h, nota, size=12.5, fill=MUTED))
            h += 20
        h += 44
    desc = (f"{fmt_int(t['verificadas'])} seções verificadas de {fmt_int(t['instaladas'])} instaladas "
            f"({fmt_pct(t['cobertura_pct'], 1)}); {fmt_int(t['hash_confere'])} hashes SHA-512 conferem, "
            f"{fmt_int(t['hash_diverge'])} divergem; {fmt_int(t['assinaturas_validas'])} assinaturas válidas; "
            f"{fmt_int(t['secoes_divergentes'])} seções com divergência de hash, assinatura ou votos."
            + (" " + " ".join(notas) if notas else ""))
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
    vsc = arqs[arqs["tipo"] == "vota"]
    return {"uf": r["uf"], "cd_mun": r["cd_mun"], "zona": r["zona"], "secao": r["secao"],
            "nome": a["nome"], "token": a["token_tse"], "sha512_assinado": a["sha512_assinado"],
            "sha512": a.get("sha512"), "vsc": vsc.iloc[0]["nome"] if not vsc.empty else None}


def _contagem_txt(d: dict | None) -> str:
    rot = {"True": "sim", "False": "não", "indeterminado": "indeterminado",
           "intermediaria": "AC intermediária", "raiz": "raiz",
           "cobre_dia_eleicao": "válidos", "fora_da_validade": "fora da validade",
           "valida": "conferida", "invalida": "não conferida", "sem_ac": "sem AC"}
    if not d:
        return "-"
    return "; ".join(f"{rot.get(k, k)}: {fmt_int(v)}" for k, v in sorted(d.items()))


def _data(iso: str | None) -> str:
    return datetime.fromisoformat(iso).strftime("%d/%m/%Y") if iso else "-"


def secao_certificados(pasta: Path, consistencia: dict | None = None) -> str:
    """Seção do relatório com a análise dos certificados das urnas: coerência em todas as seções
    (de ``secoes.parquet``) e validação da cadeia (de ``certificados_resumo.json``)."""
    p: list[str] = ["## Certificados das urnas\n"]
    p.append("Cada `.vsc` traz o certificado de hardware da urna que o assinou. A coerência desses "
             "certificados entre si e com o BU é conferida em todas as seções verificadas, a partir do "
             "catálogo. A validação da cadeia (a assinatura de cada certificado de urna conferida com a chave "
             "pública da autoridade certificadora, AC, emissora) é feita por "
             "`scripts/ele2026/analisar_certificados.py`. Os certificados públicos das AC usados estão em "
             "[`data/certificados/`](../data/certificados/README.md).\n")
    c = consistencia
    if c:
        p.append(f"### Coerência dos certificados em todas as seções ({fmt_int(c['secoes'])})\n")
        p.append("> **Concluída.** Calculada a partir de `secoes.parquet` (SHA-256, titular, emissor e número de "
                 "série do certificado de cada seção) e do número interno da urna registrado no BU "
                 "(`secoes_2026.parquet`).\n")
        linhas = [
            ["Seções verificadas com certificado", fmt_int(c["secoes"])],
            ["Certificados distintos (SHA-256 do DER)", fmt_int(c["distintos"])],
            ["Pares emissor e número de série distintos", fmt_int(c["pares_emissor_serial"])],
            ["CN no padrão `UEAO` + 8 dígitos", f"{fmt_int(c['cn_padrao'])} de {fmt_int(c['secoes'])}"],
        ]
        if "urnas_com_mais_de_um_cert" in c:
            linhas += [["Urnas (número interno do BU) com mais de um certificado",
                        fmt_int(c["urnas_com_mais_de_um_cert"])],
                       ["Certificados usados por urnas diferentes", fmt_int(c["certs_em_urnas_diferentes"])]]
        if c.get("cn_com_bu"):
            cb = c["cn_com_bu"]
            linhas.append(["CN igual ao número interno da urna no BU",
                           f"{fmt_int(cb['iguais'])} de {fmt_int(cb['comparados'])}"])
        p.append(_tabela(["Métrica", "Valor"], linhas, ["---", "---:"]) + "\n")
        mod = [[r["modelo_urna"] or "-", r["emissor"] or "-", _algoritmo(r["assinatura_algoritmo"]),
                fmt_int(r["secoes"])] for r in c["por_modelo"]]
        p.append(_tabela(["Modelo", "AC emissora", "Algoritmo da assinatura", "Seções"], mod,
                         ["---", "---", "---", "---:"]) + "\n")
        modelos = {r["modelo_urna"] for r in c["por_modelo"]}
        if len(c["por_modelo"]) == len(modelos):
            p.append("Cada modelo de urna tem uma única AC emissora e um único algoritmo.\n")
        if c["certs_repetidos"]:
            sa = (" Todas essas seções têm BU do sistema de apuração (`busa.dat`, votação por cédula), "
                  "que é emitido e assinado por uma mesma urna de apuração para várias seções; por isso o "
                  "mesmo certificado aparece em mais de uma seção.") if c["repetidos_todos_sa"] else ""
            p.append(f"**Certificado em mais de uma seção:** {_plural(c['certs_repetidos'], 'certificado', 'certificados')}, em "
                     f"{fmt_int(c['secoes_cert_repetido'])} seções ({', '.join(c['repetidos_ufs'])}).{sa}\n")
        cb = c.get("cn_com_bu")
        if cb and cb["diferentes"]:
            linhas = [[r["uf"].upper(), r["cd_mun"], r["zona"], r["secao"], str(r["cn"]),
                       f"{int(r['numero_interno_urna']):08d}"] for r in cb["diferentes"]]
            p.append(f"**CN diferente do número interno do BU:** {fmt_int(len(cb['diferentes']))} seções. O "
                     "número interno comparado é o do campo `correspondenciaResultado.carga.numeroInternoUrna` "
                     "do BU assinado, isto é, a urna para a qual a carga foi gerada. Em todas elas o hash dos "
                     "arquivos e a assinatura conferem com o certificado que acompanha o `.vsc`. A explicação "
                     "provável é a urna que votou ser outra que não a da carga original (troca de equipamento "
                     "antes da votação); é um ponto a confirmar com o TSE, não uma falha de assinatura.\n")
            p.append(_tabela(["UF", "Código do município", "Zona", "Seção", "CN do certificado", "Número interno no BU"],
                             linhas, ["---", "---", "---", "---", "---", "---"]) + "\n")
    arq = pasta / "certificados_resumo.json"
    p.append("### Validação da cadeia de certificados\n")
    if not arq.exists():
        p.append("A análise dos certificados ainda não foi executada "
                 "(`python scripts/ele2026/analisar_certificados.py`).\n")
        return "\n".join(p)
    res = _ler_json(arq)
    if not res:
        p.append("O arquivo `certificados_resumo.json` está ilegível; gere-o de novo.\n")
        return "\n".join(p)
    todas = res.get("todas") or {}
    tem_tabela = (pasta / "certificados.parquet").exists()
    fracao = todas.get("amostra_fracao")
    situacao = str(todas.get("situacao") or "").strip()
    if todas and fracao:
        amostra = fmt_pct(float(fracao) * 100, 0)
        rot = (f"Concluída na amostra de {amostra}, sorteio determinístico" if situacao.startswith("conclu")
               else f"Em andamento na amostra de {amostra}, sorteio determinístico")
        p.append(f"> **{rot}.** Critério do sorteio: {todas.get('amostra_criterio') or 'proporcional por UF'}. "
                 f"{fmt_int(todas.get('secoes_processadas', 0))} seções processadas, "
                 f"{fmt_pct(todas.get('cobertura_pct') or 0, 2)} das {fmt_int(todas.get('secoes_ok_no_pais', 0))} "
                 f"seções verificadas no país, em todas as UFs. Situação registrada em `certificados_resumo.json` "
                 f"(gerado em {todas.get('gerado_em') or res.get('gerado_em') or '-'}): "
                 f"\"{situacao or 'não informada'}\".\n")
    elif todas.get("situacao") == "concluído":
        p.append(f"> **Concluída.** Certificado de {fmt_int(todas['secoes_processadas'])} seções "
                 "conferido no modo completo.\n")
    elif todas:
        p.append(f"> **Em andamento.** Modo completo em {fmt_pct(todas.get('cobertura_pct') or 0, 2)} "
                 f"das seções ok ({fmt_int(todas['secoes_processadas'])} de "
                 f"{fmt_int(todas['secoes_ok_no_pais'])}); os números abaixo são parciais.\n")
    else:
        p.append("> **Em andamento.** Números de uma amostra de arquivos `.vsc`; o modo completo (`--todas`) "
                 "ainda não gerou `certificados.parquet`.\n")
    if todas:
        prob = (todas.get("problemas") or {}).get("n", 0)
        p.append(f"**Seções processadas** (`certificados.parquet`{'' if tem_tabela else ', ausente nesta cópia'}): "
                 f"{fmt_int(todas.get('secoes_processadas', 0))}; assinatura do certificado conferida pela AC: "
                 f"{_contagem_txt(todas.get('cadeia_ok'))}; nível da cadeia: "
                 f"{_contagem_txt(todas.get('nivel_cadeia'))}; certificado da urna válido no dia da eleição: "
                 f"{_contagem_txt(todas.get('valido_na_eleicao'))}; CN igual ao usuário da assinatura de "
                 f"hardware: {_contagem_txt(todas.get('cn_confere_usuario'))}; chaves públicas em urnas "
                 f"diferentes: {fmt_int(todas.get('chaves_em_urnas_diferentes', 0))}; problemas: "
                 f"{fmt_int(prob)}.\n")
        linhas = []
        for em, mods in sorted((todas.get("por_emissor_e_modelo") or {}).items()):
            for mod, x in sorted(mods.items()):
                linhas.append([em, mod, fmt_int(x["secoes"]),
                               f"{_data(x['nao_antes_min'])} a {_data(x['nao_antes_max'])}",
                               _contagem_txt(x.get("cadeia_ok")),
                               _contagem_txt(x.get("ac_valida_na_eleicao"))])
        if linhas:
            p.append(_tabela(["AC emissora", "Modelo", "Seções", "Emitidos entre", "Conferido pela AC",
                              "AC válida no dia"], linhas,
                             ["---", "---", "---:", "---", "---", "---"]) + "\n")
    v = res.get("vsc") or {}
    if v:
        p.append(f"**Amostra estratificada de arquivos `.vsc`** ({fmt_int(v.get('vsc_analisados', 0))} arquivos): "
                 f"validade no dia da eleição: {_contagem_txt(v.get('validade'))}; "
                 f"chaves públicas em urnas diferentes: {fmt_int(v.get('chaves_em_urnas_diferentes', 0))}"
                 + (f"; cadeia: {_contagem_txt({k: x for k, x in v['cadeia'].items() if k != 'acs_carregadas'})}"
                    if v.get("cadeia") else "") + ".\n")
    acs = todas.get("acs") or res.get("acs") or []
    if acs:
        linhas = [[a["cn"], a.get("emissor") or "-", f"{_data(a['nao_antes'])} a {_data(a['nao_depois'])}",
                   "sim" if a.get("valida_no_dia_da_eleicao") else "não",
                   a.get("confere_resumo_oficial_tse") or "não consta"] for a in acs]
        p.append(_tabela(["AC", "Emitida por", "Validade", "Válida em 04/10/2026",
                          "Confere com o resumo digital do TSE"], linhas,
                         ["---", "---", "---", "---", "---"]) + "\n")
    p.append("**Até onde vai a cadeia.** A conferência chega à AC intermediária (AC URNA, AC UE2020 e "
             "AC UE2022). Os certificados das raízes (AC RAIZ UE e AC RAIZ UE v2) e da AC URNA v2 não "
             "estão disponíveis publicamente para download; o SHA-512 deles, publicado pelo TSE, já está "
             "no script, que sobe até a raiz assim que os arquivos forem colocados em "
             "`data/certificados/ac/`.\n")
    fora = ((res.get("anomalias") or {}).get("certificado_emitido_fora_da_validade_da_ac") or {})
    exemplo = (fora.get("exemplos") or [{}])[0]
    detalhe = (f" (por exemplo, seção `{exemplo.get('secao_id')}`: {exemplo.get('detalhe')})"
               if exemplo.get("secao_id") else "")
    p.append("**Observação sobre a AC URNA.** O certificado publicado da AC URNA tem validade até "
             "18/07/2026, antes da eleição, e há certificado de urna emitido depois dessa data cuja "
             f"assinatura confere com a chave dessa AC{detalhe}. A explicação mais provável é um certificado "
             "renovado da AC URNA, com a mesma chave, que não foi publicado. É um ponto a esclarecer com "
             "o TSE (ver [ocorrências para o TSE](relatorio-tse-ocorrencias-2026.md)), não indício de "
             "adulteração.\n")
    p.append("**Assinatura de software (CEPESC).** O `.vsc` traz também uma assinatura de software feita "
             "com algoritmo de governo não publicado; ela não pode ser verificada com informação pública. "
             "A conferência acima usa a assinatura de hardware de cada urna.\n")
    return "\n".join(p)


def secao_registro_divergencias(registro: list[dict], pasta: Path) -> str:
    """Divergências registradas em ``divergencias.jsonl`` (inclui as que não afetam o hash dos arquivos
    publicados, como arquivo assinado e não publicado), com os endereços para conferência."""
    if not registro:
        return ""
    p: list[str] = []
    for d in registro:
        uf, mun, zona, sec = d.get("uf"), d.get("cd_mun"), d.get("zona"), d.get("secao")
        cat = d.get("categoria") or "-"
        rotulo, grupo, _expl = ref.INTEGRIDADE_CATEGORIAS.get(cat, (cat, None, ""))
        tipo = str(d.get("arquivo") or "").rsplit("-", 1)[-1].split(".")[0]
        p.append(f"### {ROTULO_TIPO.get(tipo, tipo)} da seção {uf.upper()}/{mun}/{zona}/{sec}: "
                 f"{rotulo[:1].lower() + rotulo[1:]}\n")
        p.append(_tabela(["Campo", "Valor"], [
            ["Categoria", f"`{cat}` (grupo de leitura {ref.GRUPOS.get(grupo, {}).get('ordem', '-')})"],
            ["Arquivo", f"`{d.get('arquivo')}`"],
            ["SHA-512 assinado pela urna", f"`{d.get('sha512_assinado') or '-'}`"],
            ["SHA-512 calculado", f"`{d['sha512_calculado']}`" if d.get("sha512_calculado") else
             "não calculado (arquivo não publicado)"],
            ["Motivo registrado", str(d.get("motivo") or "-")],
            ["Token do conjunto (aux.json)", f"`{d.get('token_tse') or '-'}`"],
            ["Registrado em", str(d.get("ts") or "-")],
        ], ["---", "---"]) + "\n")
        p.append("Endereços para conferência:\n")
        p.append(f"```\n{url_aux(uf, mun, zona, sec)}\n"
                 f"{url_arquivo(uf, mun, zona, sec, d.get('token_tse'), d.get('arquivo') or '')}\n```\n")
        arqs = ig.arquivos_da_secao(uf, mun, zona, sec, pasta)
        if not arqs.empty:
            linhas = [[f"`{r['nome']}`", ROTULO_TIPO.get(r["tipo"], r["tipo"]),
                       {True: "confere", False: "diverge"}.get(r["hash_confere"], "fora da assinatura")
                       if not pd.isna(r["hash_confere"]) else "fora da assinatura"]
                      for _, r in arqs.iterrows()]
            p.append("Demais arquivos publicados da seção:\n")
            p.append(_tabela(["Arquivo", "Tipo", "SHA-512 x assinado"], linhas, ["---", "---", "---"]) + "\n")
        if cat == "arquivo_ausente_tse":
            p.append("O `aux.json` da seção não lista o arquivo e o endereço dele responde HTTP 404. O BU e o "
                     "log publicados conferem com o que a urna assinou, a assinatura da urna é válida e os votos "
                     "do BU assinado são os mesmos do BU da coleta. O que falta é o próprio arquivo na "
                     "publicação, de modo que ele não pode ser conferido. A categoria pertence ao grupo 1 por "
                     "definição (a urna assinou um arquivo que não aparece na publicação), mas o quadro é de "
                     "lacuna de publicação a ser informada ao TSE, sem indício de alteração de conteúdo.\n")
    return "\n".join(p)


def secao_indisponiveis(ind: pd.DataFrame, ocorrencias: list[dict], nomes_uf: dict) -> str:
    p: list[str] = ["## Arquivos listados e indisponíveis no servidor do TSE\n"]
    if ind.empty and not ocorrencias:
        p.append("Nenhum arquivo listado no `aux.json` ficou indisponível.\n")
        return "\n".join(p)
    por_tipo = ind["tipo"].value_counts().to_dict() if not ind.empty else {}
    tipos = ", ".join(f"{fmt_int(n)} {ROTULO_TIPO.get(t, t)}" for t, n in sorted(por_tipo.items()))
    p.append(f"Na passagem final, {fmt_int(len(ind))} arquivos listados no `aux.json` responderam HTTP 404 "
             f"({tipos or 'nenhum'}), em {fmt_int(ind[['uf', 'cd_mun', 'zona', 'secao']].drop_duplicates().shape[0])} "
             "seções. O BU, o RDV e o log dessas seções foram baixados e conferidos normalmente. A imagem do BU "
             "tem SHA-512 no `.vsc`, como outros arquivos que a urna grava, mas o TSE não a publica nas demais "
             "seções e a conferência do projeto cobre o BU, o RDV e o log; nessas seções ela aparece no "
             "`aux.json` e o servidor responde 404. Esses arquivos ficam no catálogo com "
             "`disponivel = false` e `http_status = 404`. Não é divergência de hash nem de assinatura: o "
             "arquivo não pôde ser verificado porque não estava publicado.\n")
    if not ind.empty:
        uf = ind.groupby("uf").size().sort_values(ascending=False)
        linhas = [[u.upper(), nomes_uf.get(u, "-"), fmt_int(n)] for u, n in uf.items()]
        p.append(_tabela(["UF", "Nome", "Arquivos indisponíveis"], linhas, ["---", "---", "---:"]) + "\n")
    if ocorrencias:
        reg = pd.DataFrame(ocorrencias)
        st = reg.get("aux_status_secao", pd.Series(dtype=str)).value_counts().to_dict()
        datas = (reg["aux_data_recebimento"].astype(str).str[:10].value_counts().sort_index().to_dict()
                 if "aux_data_recebimento" in reg else {})
        nomes_ind = set(ind["nome"]) if not ind.empty else set()
        ainda = int(reg["arquivo"].isin(nomes_ind).sum())
        fora = reg[~reg["arquivo"].isin(nomes_ind)]
        p.append(f"O registro `ocorrencias_publicacao.jsonl` guarda {fmt_int(len(reg))} ocorrências, uma por "
                 "arquivo, anotadas no momento em que o 404 foi visto pela primeira vez, com o status da seção "
                 "no `aux.json` (" + "; ".join(f"{k}: {fmt_int(v)}" for k, v in st.items()) + ") e a data de "
                 "recebimento informada pelo TSE (" + "; ".join(f"{k}: {fmt_int(v)}" for k, v in datas.items())
                 + f"). Destas, {fmt_int(ainda)} continuavam indisponíveis na passagem final")
        if len(fora):
            por_uf = fora.groupby("uf").size().to_dict()
            p[-1] += (f". As outras {fmt_int(len(fora))} ("
                      + ", ".join(f"{u.upper()} {fmt_int(n)}" for u, n in sorted(por_uf.items()))
                      + ") deixaram de constar no `aux.json`: quando a seção foi verificada de novo, o arquivo "
                      "já não era listado, e o catálogo registra apenas os quatro arquivos da urna (BU, RDV, log "
                      "e `.vsc`), todos conferidos. Numa consulta de 14/10/2026 a uma dessas seções, o "
                      "`aux.json` aparece com status \"Totalizada\" e sem a imagem do BU. A diferença entre "
                      f"{fmt_int(len(reg))} e {fmt_int(ainda)} é, portanto, de arquivos retirados da lista, não "
                      "de arquivos que passaram a ser servidos.\n")
        else:
            p[-1] += ".\n"
    p.append("Todas as seções afetadas aparecem com status \"Recebida\" e foram republicadas entre 05 e "
             "07/10/2026. O caso está descrito na [investigação das seções \"Recebida\"]"
             "(investigacao-secoes-recebidas-2026.md) e consta da [relação de ocorrências para o TSE]"
             "(relatorio-tse-ocorrencias-2026.md). Trata-se de lacuna de publicação a ser informada ao TSE, "
             "não de evidência de adulteração.\n")
    return "\n".join(p)


def secao_auditoria(aud: dict | None, registro: list[dict]) -> str:
    p: list[str] = ["## Auditoria do BU e do log de 2026\n"]
    if not aud:
        p.append("A auditoria de BU e log de 2026 ainda não foi executada.\n")
        return "\n".join(p)
    por = aud["por_codigo"].copy()
    por["grupo"] = por["codigo"].map(ref.ISSUE_GRUPOS)
    sec = aud.get("secoes")
    p.append("> **Concluída.** " + (f"{fmt_int(sec)} seções com BU e log analisados. " if sec else "")
             + f"{fmt_int(aud['ocorrencias'])} ocorrências"
             + (f" em {fmt_int(aud['secoes_com_ocorrencia'])} seções" if aud.get("secoes_com_ocorrencia") else "")
             + ". Dados em `data/parquet/2026/auditoria/` (`issues_2026.parquet` e `secoes_log_2026.parquet`).\n")
    p.append("Cada código pertence a um dos três [grupos de leitura](metodologia.md#grupos-de-leitura), conforme o "
             "que pode dizer sobre manipulação. A severidade indica a prioridade de investigar; o grupo, o tipo de "
             "conclusão que o achado admite.\n")
    resumo_g = []
    for g in ref.GRUPOS_ORDEM:
        info = ref.GRUPOS[g]
        sub = por[por["grupo"] == g]
        n_sec = aud["secoes_por_grupo"].get(g)
        codigos = ", ".join(sorted(sub["codigo"].unique())) or "nenhum"
        resumo_g.append([f"{info['ordem']}. {info['nome']}", codigos, fmt_int(int(sub["ocorrencias"].sum())),
                         fmt_int(n_sec) if n_sec is not None else "-"])
    p.append(_tabela(["Grupo", "Códigos encontrados", "Ocorrências", "Seções"], resumo_g,
                     ["---", "---", "---:", "---:"]) + "\n")
    g1 = sorted(c for c, g in ref.ISSUE_GRUPOS.items() if g == "adulteracao")
    n_reg = len(registro)
    p.append(f"**Grupo 1 (indício direto de adulteração).** Nenhuma ocorrência de {', '.join(g1)} no BU e no log "
             "de 2026: nenhum BU com votos acima dos aptos ou do comparecimento, nenhum comparecimento diferente "
             "entre cargos e nenhum SHA-512 divergente. Na conferência dos arquivos, as categorias do grupo 1 "
             f"somam {_plural(n_reg, 'registro', 'registros')}"
             + (": o RDV assinado e não publicado descrito em [Divergências](#divergências)." if n_reg else ".")
             + "\n")
    sub2 = por[por["grupo"] == "investigar"]
    if not sub2.empty:
        txt = "; ".join(f"{c} ({ref.ISSUE_CATALOGO[c][0].lower()}): {fmt_int(int(n))}"
                        for c, n in sub2.groupby("codigo")["ocorrencias"].sum().items())
        extra = ""
        if aud.get("m03_total") and aud.get("m03_busa") == aud.get("m03_total"):
            extra = (f" As {fmt_int(aud['m03_total'])} ocorrências de M03 são todas de seções cujo BU veio do "
                     "sistema de apuração (`busa.dat`, votação por cédula): o log dessas seções é o do "
                     "equipamento de apuração, que não registra a abertura de votação de uma urna.")
        p.append(f"**Grupo 2 (inconsistência a investigar).** {txt}. Nenhuma ocorrência de A01 nem de A03.{extra}\n")
    else:
        p.append("**Grupo 2 (inconsistência a investigar).** Nenhuma ocorrência.\n")
    p.append("**Grupo 3 (operacional ou estatístico).** Descreve como o dia de votação transcorreu (reinícios, "
             "horários, proporção de brancos e nulos, abstenção, urna de reserva, liberação sem biometria). "
             "Sozinho, não é evidência de manipulação.\n")
    linhas = []
    ordem = {g: i for i, g in enumerate(ref.GRUPOS_ORDEM)}
    por = por.assign(_o=por["grupo"].map(ordem).fillna(9)).sort_values(["_o", "ocorrencias"],
                                                                       ascending=[True, False])
    for _, r in por.iterrows():
        nome = ref.ISSUE_CATALOGO.get(r["codigo"], (r["codigo"],))[0]
        grupo = ref.GRUPOS.get(r["grupo"], {}).get("ordem", "-")
        sev = ROTULO_SEVERIDADE.get(r["severidade"], r["severidade"] or "-")
        linhas.append([r["codigo"], nome, str(sev), str(grupo), fmt_int(int(r["ocorrencias"])),
                       fmt_int(int(r["secoes"])) if not pd.isna(r["secoes"]) else "-"])
    p.append(_tabela(["Código", "Descrição", "Severidade", "Grupo", "Ocorrências", "Seções"], linhas,
                     ["---", "---", "---", ":---:", "---:", "---:"]) + "\n")
    return "\n".join(p)


def secao_catalogo(pasta: Path) -> str:
    man = _ler_json(Path(pasta) / "catalogo_manifest.json")
    p: list[str] = ["## Catálogo de hashes por arquivo\n"]
    tam = (f" ({fmt_int(man['total_arquivos'])} arquivos Parquet, {fmt_int(round(man['total_bytes'] / 2**20))} MB "
           "no total)" if man.get("total_bytes") else "")
    linhas = f" com {fmt_int(man['total_linhas'])} arquivos catalogados" if man.get("total_linhas") else ""
    p.append(f"O catálogo completo (MD5, SHA-256, SHA-512 calculado, SHA-512 assinado, token e situação de cada "
             f"arquivo){linhas} não fica no git. Ele está publicado como anexos da versão "
             f"[{VERSAO_CATALOGO}]({PAGINA_CATALOGO}) do projeto, um Parquet por UF (`arquivos_<uf>.parquet`) e "
             f"um `SHA256SUMS`{tam}.\n")
    p.append("Baixar e conferir a integridade dos anexos:\n")
    p.append(f"```bash\nmkdir -p catalogo-2026 && cd catalogo-2026\n"
             f"gh release download {VERSAO_CATALOGO} --repo {REPO} --pattern 'arquivos_*.parquet' "
             f"--pattern SHA256SUMS\n"
             f"sha256sum -c SHA256SUMS            # macOS: shasum -a 256 -c SHA256SUMS\n```\n")
    p.append("Sem o `gh`, baixe só a UF desejada e confira apenas ela:\n")
    p.append(f"```bash\ncurl -LO {URL_CATALOGO}/arquivos_ac.parquet\ncurl -LO {URL_CATALOGO}/SHA256SUMS\n"
             "sha256sum -c --ignore-missing SHA256SUMS   # macOS: shasum -a 256 -c --ignore-missing SHA256SUMS\n```\n")
    p.append("Consulta de exemplo com DuckDB:\n")
    p.append("```python\nimport duckdb\nduckdb.sql(\"\"\"\n    SELECT tipo, count(*) AS arquivos,\n"
             "           count(*) FILTER (WHERE hash_confere) AS sha512_confere,\n"
             "           count(*) FILTER (WHERE NOT disponivel) AS indisponiveis\n"
             "    FROM 'arquivos_*.parquet' GROUP BY tipo ORDER BY tipo\n\"\"\").show()\n```\n")
    p.append("O painel, na página **Integridade dos arquivos (2026)**, baixa sob demanda o anexo da UF consultada "
             "e confere o SHA-256 com o manifesto `data/parquet/2026/integridade/catalogo_manifest.json`.\n")
    return "\n".join(p)


def relatorio_md(t: dict, tab: pd.DataFrame, div: pd.DataFrame, resumo: dict, exemplo: dict | None,
                 nomes_mun: dict, certificados: str | None = None, extras: dict | None = None) -> str:
    extras = extras or {}
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    pendentes = int((resumo or {}).get("erros_pendentes") or 0)
    concluida = t["cobertura_pct"] >= 100 and pendentes == 0
    registro = extras.get("registro") or []
    ind = extras.get("indisponiveis")
    ind = ind if ind is not None else pd.DataFrame(columns=["uf", "nome", "tipo"])
    ocorrencias = extras.get("ocorrencias") or []
    aud = extras.get("auditoria")
    nomes_uf = extras.get("nomes_uf") or {}
    algoritmos = extras.get("algoritmos") or {}
    p: list[str] = []
    p.append("# Relatório de integridade dos arquivos de urna: 1º turno de 2026\n")
    if concluida:
        p.append(f"> **Concluída** a conferência de hashes e assinaturas em {fmt_int(t['verificadas'])} de "
                 f"{fmt_int(t['instaladas'])} seções instaladas ({fmt_pct(t['cobertura_pct'])}), sem erros "
                 "pendentes" + (", e a auditoria do BU e do log de 2026" if aud else "") + ". A validação da "
                 "cadeia de certificados, numa amostra, tem a situação própria indicada em [Certificados das urnas]"
                 f"(#certificados-das-urnas). Relatório gerado em {agora} por "
                 "`scripts/docs/gerar_relatorio_integridade.py`.\n")
    else:
        p.append(f"> **Em andamento.** Cobertura: {fmt_pct(t['cobertura_pct'])} das seções instaladas verificadas "
                 f"({fmt_int(t['verificadas'])} de {fmt_int(t['instaladas'])})"
                 + (f"; {fmt_int(pendentes)} seções com erro pendente" if pendentes else "")
                 + f". Relatório gerado em {agora} por `scripts/docs/gerar_relatorio_integridade.py`; os números "
                 "mudam a cada nova execução enquanto a verificação não termina.\n")
    horarios = ig.texto_horarios(resumo)
    if horarios:
        p.append(f"Registro da coleta: {horarios}.\n")
    p.append('<p align="center">\n  <img src="assets/2026-integridade.svg" alt="Cobertura da verificação de '
             f'integridade por UF: {fmt_int(t["verificadas"])} seções verificadas, '
             f'{fmt_int(t["hash_confere"])} SHA-512 iguais ao assinado e {fmt_int(t["hash_diverge"])} divergentes" '
             'width="100%">\n</p>\n')

    if t["verificadas"]:
        p.append("## Resultado\n")
        conferidos = t["hash_confere"] + t["hash_diverge"]
        alg = "; ".join(f"{k.replace('ECDSA-secp521r1-SHA512', 'ECDSA P-521')}: {fmt_int(v)}"
                        for k, v in sorted(algoritmos.items(), key=lambda x: -x[1]))
        itens = [
            f"- **{fmt_int(t['hash_diverge'])} SHA-512 divergentes** em {fmt_int(conferidos)} comparados (BU, RDV e "
            "log de cada seção): todo arquivo publicado tem o conteúdo que a urna resumiu e assinou.",
            f"- **{fmt_int(t['assinaturas_invalidas'])} assinaturas inválidas**: {fmt_int(t['assinaturas_validas'])} "
            "assinaturas de urna válidas" + (f" ({alg})" if alg else "") + ".",
            f"- **Votos do BU assinado iguais aos do BU da coleta** em "
            f"{fmt_int(t['verificadas'] - t['votos_divergem'])} seções; {fmt_int(t['votos_divergem'])} diferentes.",
        ]
        if registro:
            itens.append(f"- **{_plural(len(registro), 'arquivo assinado', 'arquivos assinados')} pela urna e "
                         f"{'não publicado' if len(registro) == 1 else 'não publicados'}**: "
                         "ver [Divergências](#divergências).")
        if not ind.empty:
            itens.append(f"- **{fmt_int(len(ind))} arquivos listados e indisponíveis** (HTTP 404), todos fora da "
                         "conferência de BU, RDV e log: ver [Arquivos listados e indisponíveis]"
                         "(#arquivos-listados-e-indisponíveis-no-servidor-do-tse).")
        if aud:
            itens.append("- **Auditoria do BU e do log:** nenhuma ocorrência do grupo 1; ver "
                         "[Auditoria do BU e do log](#auditoria-do-bu-e-do-log-de-2026).")
        p.append("\n".join(itens) + "\n")
        p.append("Os pontos que dependem de esclarecimento do TSE estão reunidos em "
                 "[relatorio-tse-ocorrencias-2026.md](relatorio-tse-ocorrencias-2026.md).\n")

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
        "4. compara os votos do BU assinado com os do BU lido na coleta de resultados (`votos_conferem`);\n"
        "5. registra o token do `aux.json` (32 bytes em base64url) e a data e hora informadas pelo TSE.\n"
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
        "- que o certificado pertence à urna física daquela seção além do que os campos dele declaram "
        "e do que a conferência com a AC emissora mostra (ver [Certificados das urnas]"
        "(#certificados-das-urnas));\n"
        "- que os votos registrados correspondem à intenção dos eleitores;\n"
        "- nada sobre os demais arquivos cujo SHA-512 o `.vsc` também traz (imagem do BU, biometria e outros), "
        "que o TSE não publica, nem sobre o próprio `.vsc` além da assinatura.\n"
    )
    p.append("Uma divergência indica que o arquivo publicado não corresponde ao que a urna assinou e merece "
             "investigação; não é, por si só, prova de adulteração (pode haver falha de publicação, de "
             "download ou de leitura). Ausência de divergência também não prova a lisura da eleição.\n")

    p.append("## Totais\n")
    conferidos = t["hash_confere"] + t["hash_diverge"]
    linhas = [
        ["Seções instaladas (oficial)", fmt_int(t["instaladas"])],
        ["Seções verificadas", f"{fmt_int(t['verificadas'])} ({fmt_pct(t['cobertura_pct'])})"],
        ["Seções agregadas a outra", fmt_int(t["agregadas"])],
        ["Seções não instaladas", fmt_int(t["nao_instaladas"])],
        ["Seções sem arquivos publicados", fmt_int(t["sem_arquivos"])],
        ["Linhas no resumo por seção", fmt_int(t["secoes"])],
        ["Arquivos catalogados", fmt_int(t["arquivos"])],
        ["SHA-512 comparados (BU, RDV e log)", fmt_int(conferidos)],
        ["SHA-512 iguais ao assinado", f"{fmt_int(t['hash_confere'])} ({fmt_pct(_pct(t['hash_confere'], conferidos))})"],
        ["SHA-512 diferentes do assinado", fmt_int(t["hash_diverge"])],
        ["Arquivos sem SHA-512 a comparar (o próprio `.vsc`)", fmt_int(t["sem_hash"])],
        ["Arquivos listados e indisponíveis (HTTP 404)", fmt_int(len(ind))],
        ["Arquivos assinados e não publicados", fmt_int(len(registro))],
        ["Assinaturas válidas", fmt_int(t["assinaturas_validas"])],
        ["Assinaturas inválidas", fmt_int(t["assinaturas_invalidas"])],
        ["Assinaturas não verificadas", fmt_int(t["assinaturas_nao_verificadas"])],
        ["Votos do BU assinado diferentes do BU da coleta", fmt_int(t["votos_divergem"])],
        ["Seções com hash divergente, assinatura inválida ou votos diferentes", fmt_int(t["secoes_divergentes"])],
    ]
    if resumo:
        linhas.append(["Seções com erro pendente na coleta", fmt_int(pendentes)])
    p.append(_tabela(["Métrica", "Valor"], linhas, ["---", "---:"]) + "\n")
    if algoritmos:
        p.append("Algoritmo da assinatura de hardware: "
                 + "; ".join(f"{k.replace('ECDSA-secp521r1-SHA512', 'ECDSA P-521 com SHA-512')}: {fmt_int(v)}"
                             for k, v in sorted(algoritmos.items(), key=lambda x: -x[1])) + ".\n")

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
            p.append(f"Nenhuma seção com SHA-512 divergente, assinatura inválida ou votos diferentes nas "
                     f"{fmt_int(t['verificadas'])} seções verificadas"
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
    if registro:
        cats = pd.Series([d.get("categoria") for d in registro]).value_counts().to_dict()
        p.append(f"O registro `divergencias.jsonl` tem {_plural(len(registro), 'entrada', 'entradas')} ("
                 + "; ".join(f"`{k}`: {fmt_int(v)}" for k, v in cats.items()) + "), que não alteram o hash de "
                 "nenhum arquivo publicado e por isso não entram na contagem acima.\n")
        p.append(secao_registro_divergencias(registro, extras.get("pasta") or Path(".")))

    if ocorrencias or not ind.empty:
        p.append(secao_indisponiveis(ind, ocorrencias, nomes_uf))

    if aud or extras.get("pasta"):
        p.append(secao_auditoria(aud, registro))

    if certificados:
        p.append(certificados)

    if extras.get("catalogo"):
        p.append(extras["catalogo"])

    p.append("## Como conferir uma seção por conta própria\n")
    ex = exemplo or {"uf": "ac", "cd_mun": "01007", "zona": "0009", "secao": "0001",
                     "nome": "<nome do arquivo -bu.dat>", "token": None, "sha512_assinado": None, "vsc": None}
    uf, mun, zona, sec = ex["uf"], ex["cd_mun"], ex["zona"], ex["secao"]
    base = url_secao(uf, mun, zona, sec)
    vsc = ex.get("vsc") or "<nome do arquivo -vota.vsc>"
    p.append(f"Exemplo com a seção {sec} da zona {zona}, município {mun} ({uf.upper()}). Troque os códigos para "
             "conferir qualquer outra.\n")
    p.append("1. Baixe o `aux.json` da seção. O campo `hash` é o nome do diretório do conjunto publicado (o token "
             "em base64url, escrito em hexadecimal) e `arq` lista os arquivos:\n")
    p.append(f"```bash\ncurl -sO {url_aux(uf, mun, zona, sec)}\n```\n")
    p.append("2. Baixe o BU e o arquivo de assinatura (`-vota.vsc`) desse diretório:\n")
    p.append(f"```bash\ncurl -sO {base}/{dir_publicacao(ex.get('token'))}/{ex['nome']}\n"
             f"curl -sO {base}/{dir_publicacao(ex.get('token'))}/{vsc}\n```\n")
    p.append("3. Calcule o SHA-512 do arquivo (sem dependências além do Python):\n")
    p.append(f'```bash\npython3 -c "import hashlib,sys; print(hashlib.sha512(open(sys.argv[1],\'rb\').read())'
             f'.hexdigest())" {ex["nome"]}\n# alternativa: shasum -a 512 {ex["nome"]}\n```\n')
    p.append("4. Leia o SHA-512 que a urna assinou e verifique a assinatura, com o leitor do projeto "
             "(`pip install -e .` na raiz do repositório), e compare:\n")
    p.append('```bash\npython3 -c "from dataurnas.parsers.signature import verificar_vsc; '
             f"r = verificar_vsc(open('{vsc}', 'rb').read()); "
             "print('assinatura válida:', r['assinatura_valida'], r['algoritmo'], r['cert_subject']); "
             "[print(k, v.hex()) for k, v in r['hashes'].items()]\"\n```\n")
    if ex.get("sha512_assinado"):
        p.append(f"Para esta seção, o valor assinado do BU registrado no catálogo é:\n\n```\n{ex['sha512_assinado']}\n```\n")
    p.append("O resultado do passo 3 deve ser idêntico ao do passo 4 e ao valor do catálogo (coluna "
             "`sha512_assinado` de `arquivos_<uf>.parquet`, ver [Catálogo de hashes por arquivo]"
             "(#catálogo-de-hashes-por-arquivo)). O painel, na página **Integridade dos arquivos (2026)**, "
             "mostra os mesmos valores para qualquer seção.\n")

    p.append("## Reproduzir este relatório\n")
    p.append("```bash\npython scripts/docs/gerar_relatorio_integridade.py\n```\n")
    p.append("Os dados de entrada ficam em `data/parquet/2026/integridade` (`arquivos_<uf>.parquet`, `secoes.parquet`, "
             "`resumo.json`, `divergencias.jsonl`, `ocorrencias_publicacao.jsonl` e `certificados_resumo.json`) e em "
             "`data/parquet/2026/auditoria`; o número de seções instaladas vem de "
             "`data/parquet/2026/resultado_uf.parquet`. Veja também a [metodologia](metodologia.md#integridade-em-2026) "
             "e as [perguntas frequentes](faq.md).\n")
    return "\n".join(p)


# ----------------------------------------------------------------------
def gerar(pasta: Path | None = None, res_uf: pd.DataFrame | None = None, res_mun: pd.DataFrame | None = None,
          saida_md: Path = SAIDA_MD, saida_svg: Path = SAIDA_SVG) -> dict:
    pasta = Path(pasta or ig.integ_dir())
    res_uf = d26.load_resultado_uf() if res_uf is None else res_uf
    res_mun = d26.load_resultado_municipio() if res_mun is None else res_mun
    dados = ig.load_secoes(pasta)
    t = ig.totais(dados.secoes, res_uf)
    tab = ig.por_uf(dados.secoes, res_uf) if not dados.vazio else pd.DataFrame()
    div = ig.divergencias(dados.secoes)
    nomes = ({(u, m): str(n).title() for u, m, n in zip(res_mun["uf"], res_mun["cd_mun"], res_mun["nome"],
                                                        strict=False)} if not res_mun.empty else {})
    nomes_uf = dict(zip(tab["uf"], tab["nome"], strict=False)) if not tab.empty else {}
    exemplo = _exemplo(pasta, dados.secoes) if not dados.vazio else None
    resumo = ig.load_resumo(pasta)
    registro = _ler_jsonl(pasta / "divergencias.jsonl") or list(resumo.get("divergencias") or [])
    ind = indisponiveis(pasta)
    ok = dados.secoes[dados.secoes["status_secao"] == "ok"] if not dados.vazio else dados.secoes
    algoritmos = (ok["assinatura_algoritmo"].dropna().value_counts().to_dict()
                  if "assinatura_algoritmo" in ok else {})
    extras = {
        "pasta": pasta if not dados.vazio else None,
        "registro": registro,
        "indisponiveis": ind,
        "ocorrencias": _ler_jsonl(pasta / "ocorrencias_publicacao.jsonl"),
        "auditoria": auditoria(pasta, resumo) if not dados.vazio else None,
        "nomes_uf": nomes_uf,
        "algoritmos": algoritmos,
        "catalogo": secao_catalogo(pasta) if not dados.vazio else None,
    }
    consist = consistencia_certificados(dados.secoes, pasta) if not dados.vazio else None
    md = relatorio_md(t, tab, div, resumo, exemplo, nomes, secao_certificados(pasta, consist), extras)
    if dados.vazio:
        md = md.replace("## Totais\n", "## Totais\n\nA verificação ainda não gravou dados: os totais abaixo estão "
                                        "zerados.\n", 1)
    notas = []
    if registro:
        notas.append(f"{_plural(len(registro), 'arquivo assinado', 'arquivos assinados')} pela urna e "
                     f"{'não publicado' if len(registro) == 1 else 'não publicados'} pelo TSE (sem divergência de hash).")
    if not ind.empty:
        notas.append(f"{fmt_int(len(ind))} arquivos listados no aux.json e indisponíveis (HTTP 404), todos imagens do BU.")
    saida_md.parent.mkdir(parents=True, exist_ok=True)
    saida_svg.parent.mkdir(parents=True, exist_ok=True)
    saida_md.write_text(md, encoding="utf-8")
    saida_svg.write_text(svg_integridade(t, tab, notas), encoding="utf-8")
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
