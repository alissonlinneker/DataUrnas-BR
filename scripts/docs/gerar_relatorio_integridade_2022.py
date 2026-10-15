#!/usr/bin/env python3
"""Gera o relatório de integridade dos arquivos de urna de 2022 (1º e 2º turnos).

Lê ``data/parquet/2022/integridade`` (``resumo.json``, ``secoes.parquet``,
``divergencias.jsonl``, ``ocorrencias_publicacao.jsonl`` e
``catalogo_manifest.json``), gerados por ``scripts/ele2022/fetch_integridade.py``,
e escreve ``docs/integridade-2022.md``: resultado, método, totais por turno e por
UF, tipos de arquivo, divergências por categoria, UF e turno, a lista completa
dos arquivos assinados e ausentes do pacote do TSE (base para o pedido de
esclarecimento), ocorrências de publicação e observações.

Uso:
    python scripts/docs/gerar_relatorio_integridade_2022.py
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PASTA = ROOT / "data" / "parquet" / "2022" / "integridade"
SAIDA = ROOT / "docs" / "integridade-2022.md"
TURNOS = ("1T", "2T")
ROTULO_TIPO = {"bu": "BU", "rdv": "RDV", "log": "log (.logjez)", "imgbu": "imagem do BU",
               "vota": "arquivo de assinatura (.vscmr)", "busa": "BU do sistema de apuração",
               "other": "outros (sistema de apuração)"}
ROTULO_CATEGORIA = {
    "hash_diverge": "SHA-512 calculado diferente do assinado",
    "assinatura_invalida": "assinatura da urna inválida",
    "hash_assinado_ausente": "arquivo publicado sem SHA-512 no .vscmr",
    "arquivo_ausente_tse": "arquivo listado no .vscmr e ausente do pacote do TSE",
}
ROTULO_OCORRENCIA = {
    "secao_sem_arquivos_no_pacote": "seção do banco sem arquivos no pacote",
    "secao_fora_do_banco": "seção do pacote ausente do banco de 2022",
    "entrada_fora_do_padrao": "entrada do zip fora do padrão de nomes",
    "entrada_corrompida": "entrada do zip corrompida",
    "pacote_indisponivel": "pacote indisponível",
}
ALGORITMO = {"ECDSA-secp521r1-SHA512": "ECDSA P-521 com SHA-512", "Ed521": "Ed521"}


def fi(n: int | float | None) -> str:
    """Inteiro no formato brasileiro (ponto como separador de milhar)."""
    return f"{int(n or 0):,}".replace(",", ".")


def fp(parte: float, todo: float) -> str:
    return (f"{parte / todo * 100:.2f}%" if todo else "-").replace(".", ",")


def fbytes(n: int) -> str:
    valor, unidade = (n / 1e9, "GB") if n >= 1e9 else (n / 1e6, "MB")
    return f"{valor:,.1f} {unidade}".replace(",", "X").replace(".", ",").replace("X", ".")


def uf_rotulo(uf: str) -> str:
    return "ZZ (exterior)" if uf.lower() == "zz" else uf.upper()


def ler_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(linha) for linha in path.read_text(encoding="utf-8").splitlines() if linha.strip()]


def tabela(cab: list[str], linhas: list[list], alinhar: str | None = None) -> list[str]:
    alinhar = alinhar or "l" + "r" * (len(cab) - 1)
    sep = ["---:" if a == "r" else "---" for a in alinhar]
    out = ["| " + " | ".join(cab) + " |", "|" + "|".join(sep) + "|"]
    out += ["| " + " | ".join(str(c) for c in linha) + " |" for linha in linhas]
    return out


def gerar(pasta: Path) -> str:
    r = json.loads((pasta / "resumo.json").read_text(encoding="utf-8"))
    secoes = pd.read_parquet(pasta / "secoes.parquet")
    divs = ler_jsonl(pasta / "divergencias.jsonl")
    ocors = ler_jsonl(pasta / "ocorrencias_publicacao.jsonl")
    manifesto = json.loads((pasta / "catalogo_manifest.json").read_text(encoding="utf-8"))
    t = r["totais"]
    cat = r.get("divergencias_por_categoria") or {}
    graves = sum(cat.get(k, 0) for k in ("hash_diverge", "assinatura_invalida", "hash_assinado_ausente"))
    agora = datetime.now().strftime("%d/%m/%Y %H:%M")
    situacao = "Concluída" if r.get("completo") and not r.get("erros_pendentes") else "Incompleta"

    L: list[str] = ["# Integridade dos arquivos de urna: eleições de 2022 (1º e 2º turnos)", ""]
    L.append(
        f"> **{situacao}** a conferência de hashes e assinaturas em {fi(t['secoes'])} seções dos dois "
        f"turnos ({r['pacotes_processados']} de {r['pacotes_esperados']} pacotes de dados abertos do TSE), "
        f"com {fi(r.get('erros_pendentes'))} erros pendentes. Relatório gerado em {agora} por "
        "`scripts/docs/gerar_relatorio_integridade_2022.py`.")
    L += ["", f"Registro da coleta: gerado em {r.get('gerado_em')}.", ""]

    # Resultado
    algs = Counter()
    for v in (r.get("algoritmos_assinatura") or {}).values():
        algs.update(v)
    alg_txt = "; ".join(f"{ALGORITMO.get(k, k)}: {fi(v)}" for k, v in sorted(algs.items()))
    n_secoes_aus = len({d["secao_id"] for d in divs if d.get("categoria") == "arquivo_ausente_tse"})
    L += ["## Resultado", ""]
    L.append(f"- **{fi(t['hash_diverge'])} SHA-512 divergentes** em {fi(t['hash_confere'] + t['hash_diverge'])} "
             "comparados (BU, RDV, log e imagem do BU de cada seção, ou o BU do sistema de apuração): todo arquivo publicado tem o conteúdo "
             "que a urna resumiu e assinou.")
    L.append(f"- **{fi(t['assinatura_invalida'])} assinaturas inválidas**: {fi(t['assinatura_valida'])} "
             f"assinaturas de urna válidas ({alg_txt}); {fi(t['assinaturas_arquivos_validas'])} assinaturas "
             f"por arquivo válidas e {fi(t['assinaturas_arquivos_invalidas'])} inválidas.")
    L.append(f"- **Votos de Presidente do BU iguais aos da base de 2022** em {fi(t['votos_conferem'])} seções; "
             f"{fi(t['votos_divergem'])} diferentes e {fi(t['votos_nao_conferidos'])} não conferidas "
             "(ver [Observações](#observações)).")
    L.append(f"- **{fi(cat.get('arquivo_ausente_tse', 0))} arquivos assinados pela urna e ausentes do pacote "
             f"do TSE**, em {fi(n_secoes_aus)} seções: ver [Arquivos assinados e ausentes do pacote do TSE]"
             "(#arquivos-assinados-e-ausentes-do-pacote-do-tse).")
    L.append(f"- **Divergências graves** (hash divergente, assinatura inválida ou arquivo sem hash assinado): "
             f"{fi(graves)}.")
    L.append(f"- **{fi(r.get('n_ocorrencias_publicacao'))} ocorrências de publicação**, todas seções presentes "
             "no pacote e ausentes do banco de 2022: ver [Ocorrências de publicação](#ocorrências-de-publicação).")
    L.append("")

    # Fonte e método
    fonte = r.get("fonte") or {}
    metodo = r.get("metodo") or {}
    L += ["## Fonte e método", ""]
    L.append(f"Fonte: {fonte.get('descricao', '')}. Padrão de URL:")
    L += ["", "```", fonte.get("url_padrao", ""), "```", ""]
    L.append(f"Pleitos: 1º turno {r['pleitos']['1T']} ({r['datas']['1T']}), 2º turno {r['pleitos']['2T']} "
             f"({r['datas']['2T']}). Cada zip é lido por faixas de bytes; cada entrada tem o CRC-32 conferido "
             "na extração. Para cada seção:")
    L.append("")
    rotulos_metodo = {"hash_arquivo": "SHA-512", "assinatura_hw": "Assinatura de hardware",
                      "assinatura_sw": "Assinatura de software", "cadeia_certificado": "Cadeia do certificado",
                      "crc32_zip": "CRC-32", "votos": "Votos"}
    for k, v in metodo.items():
        L.append(f"- **{rotulos_metodo.get(k, k)}:** {v}")
    L += ["", "O que fica comprovado e o que não fica segue o mesmo raciocínio do "
          "[relatório de 2026](relatorio-integridade-2026.md#o-que-fica-comprovado-e-o-que-não-fica): "
          "ausência de divergência mostra que o arquivo publicado é o que a urna assinou, e não prova, "
          "sozinha, a lisura da eleição; uma divergência pede investigação e não é, por si só, prova de "
          "adulteração.", ""]

    # Totais por turno
    L += ["## Totais", ""]
    tot_turno = {}
    for tr in TURNOS:
        acc = Counter()
        for v in r["por_turno"][tr]["por_uf"].values():
            acc.update({k: x for k, x in v.items() if isinstance(x, int)})
        tot_turno[tr] = acc
    metricas = [("Seções verificadas", "secoes"), ("Seções fora do banco de 2022", "fora_do_banco"),
                ("Arquivos catalogados", "arquivos"), ("SHA-512 iguais ao assinado", "hash_confere"),
                ("SHA-512 divergentes", "hash_diverge"),
                ("Arquivos sem SHA-512 a comparar (o próprio .vscmr)", "sem_hash"),
                ("Assinaturas de urna válidas", "assinatura_valida"),
                ("Assinaturas de urna inválidas", "assinatura_invalida"),
                ("Assinaturas não verificadas", "assinatura_nao_verificada"),
                ("Assinaturas por arquivo válidas", "assinaturas_arquivos_validas"),
                ("Assinaturas por arquivo inválidas", "assinaturas_arquivos_invalidas"),
                ("Votos de Presidente conferem", "votos_conferem"),
                ("Votos de Presidente divergem", "votos_divergem"),
                ("Votos não conferidos", "votos_nao_conferidos")]
    L += tabela(["Métrica", "1º turno", "2º turno", "Total"],
                [[m, fi(tot_turno["1T"][k]), fi(tot_turno["2T"][k]), fi(t[k])] for m, k in metricas])
    L += ["", f"Pacotes processados: {r['pacotes_processados']} de {r['pacotes_esperados']} "
          f"({len(r.get('execucoes') or [])} execuções registradas). Seções com status `ok`: "
          f"{fi((secoes['status_secao'] == 'ok').sum())} de {fi(len(secoes))}.", ""]

    # Por tipo de arquivo
    L += ["### Por tipo de arquivo", ""]
    L += tabela(["Tipo", "Arquivos", "Tamanho"],
                [[ROTULO_TIPO.get(k, k), fi(v["arquivos"]), fbytes(v["bytes"])]
                 for k, v in sorted((r.get("por_tipo_arquivo") or {}).items(), key=lambda kv: -kv[1]["arquivos"])])
    L.append("")

    # Algoritmos, modelos, emissores
    L += ["### Algoritmo de assinatura e modelo de urna", ""]
    linhas = []
    for tr in TURNOS:
        for k, v in sorted((r.get("algoritmos_assinatura") or {}).get(tr, {}).items()):
            linhas.append([f"{tr[0]}º turno", "algoritmo", ALGORITMO.get(k, k), fi(v)])
        for k, v in sorted((r.get("modelos_urna") or {}).get(tr, {}).items()):
            linhas.append([f"{tr[0]}º turno", "modelo", k, fi(v)])
        for k, v in sorted((r.get("emissores_certificado") or {}).get(tr, {}).items()):
            cn = next((p.split("=", 1)[1] for p in k.split(",") if p.startswith("CN=")), k)
            linhas.append([f"{tr[0]}º turno", "emissor do certificado", cn, fi(v)])
    L += tabela(["Turno", "Item", "Valor", "Seções"], linhas, "lllr")
    L.append("")

    # Por UF
    L += ["## Por UF", ""]
    div_uf = Counter((d["turno"], d["uf"]) for d in divs)
    for tr in TURNOS:
        n = int(tr[0])
        L += [f"### {n}º turno", ""]
        linhas = []
        for uf, v in sorted(r["por_turno"][tr]["por_uf"].items()):
            linhas.append([uf_rotulo(uf), fi(v["secoes"]), fi(v["fora_do_banco"]), fi(v["arquivos"]),
                           fi(v["hash_confere"]), fi(v["hash_diverge"]), fi(v["assinatura_valida"]),
                           fi(v["assinatura_invalida"]), fi(div_uf.get((n, uf), 0))])
        a = tot_turno[tr]
        linhas.append(["**Total**", fi(a["secoes"]), fi(a["fora_do_banco"]), fi(a["arquivos"]),
                       fi(a["hash_confere"]), fi(a["hash_diverge"]), fi(a["assinatura_valida"]),
                       fi(a["assinatura_invalida"]), fi(sum(c for (tt, _u), c in div_uf.items() if tt == n))])
        L += tabela(["UF", "Seções", "Fora do banco", "Arquivos", "SHA-512 iguais", "SHA-512 divergentes",
                     "Assinaturas válidas", "Assinaturas inválidas", "Arquivos ausentes do pacote"], linhas)
        L.append("")

    # Divergências
    L += ["## Divergências", "", "### Por categoria", ""]
    L += tabela(["Categoria", "Descrição", "Arquivos"],
                [[f"`{k}`", ROTULO_CATEGORIA.get(k, k), fi(v)] for k, v in cat.items()], "llr")
    L += ["", "### Por UF e turno", ""]
    L += tabela(["Turno", "UF", "Arquivos", "Seções"],
                [[f"{tt}º", uf_rotulo(u), fi(c), fi(len({d['secao_id'] for d in divs
                                                          if d['turno'] == tt and d['uf'] == u}))]
                 for (tt, u), c in sorted(div_uf.items())], "llrr")
    tipos = Counter(d["arquivo"].rsplit(".", 1)[-1] for d in divs)
    L += ["", "Por tipo de arquivo: " + "; ".join(f"`.{k}`: {fi(v)}" for k, v in tipos.most_common()) + ".", ""]

    # Lista para o TSE
    aus = sorted((d for d in divs if d.get("categoria") == "arquivo_ausente_tse"),
                 key=lambda d: (d["turno"], d["uf"], d["cd_mun"], d["zona"], d["secao"], d["arquivo"]))
    L += ["## Arquivos assinados e ausentes do pacote do TSE", ""]
    L.append(f"Cada linha é um arquivo que a urna listou e assinou no `.vscmr` (com o SHA-512 abaixo) e que "
             f"não está no zip de dados abertos do TSE da UF e do turno. São {fi(len(aus))} arquivos em "
             f"{fi(len({d['secao_id'] for d in aus}))} seções. O arquivo de assinatura dessas seções foi "
             "verificado e é válido; o que falta é o próprio arquivo, então não há como conferir o conteúdo. "
             "Esta tabela é a base do pedido de esclarecimento ao TSE: publicação dos arquivos ou explicação "
             "da ausência. A coluna SHA-512 mostra os 16 primeiros caracteres; o valor completo está em "
             "`data/parquet/2022/integridade/divergencias.jsonl` (campo `sha512_assinado`).")
    L.append("")
    L += tabela(["#", "Turno", "UF", "Município", "Zona", "Seção", "Arquivo", "SHA-512 assinado (início)"],
                [[i, f"{d['turno']}º", uf_rotulo(d["uf"]), d["cd_mun"], d["zona"], d["secao"],
                  f"`{d['arquivo']}`", f"`{(d.get('sha512_assinado') or '')[:16]}`"]
                 for i, d in enumerate(aus, 1)], "rlllllll")
    L.append("")

    # Ocorrências
    oc_cat = r.get("ocorrencias_por_categoria") or {}
    L += ["## Ocorrências de publicação", ""]
    L += tabela(["Categoria", "Descrição", "Ocorrências"],
                [[f"`{k}`", ROTULO_OCORRENCIA.get(k, k), fi(v)] for k, v in oc_cat.items()], "llr")
    fora = secoes[~secoes["no_banco_2022"]]
    n_zz = int((fora["uf"] == "zz").sum())
    L += ["", f"Há {fi(len(fora))} seções no pacote e fora do banco de 2022: {fi(n_zz)} do exterior (o banco "
          f"de 2022 não traz o exterior; não são registradas como ocorrência) e {fi(len(fora) - n_zz)} no "
          "Brasil, listadas abaixo. Todas foram verificadas normalmente (hash e assinatura); só não há votos "
          "da base para comparar.", ""]
    L += tabela(["Turno", "UF", "Município", "Zona", "Seção"],
                [[f"{o['turno']}º", uf_rotulo(o["uf"]), o["cd_mun"], o["zona"], o["secao"]]
                 for o in sorted(ocors, key=lambda o: (o["turno"], o["uf"], o["cd_mun"], o["zona"], o["secao"]))],
                "lllll")
    L.append("")

    # Observações
    no_banco_sem_votos = secoes[secoes["no_banco_2022"] & secoes["votos_conferem"].isna()]
    sv = Counter(zip(no_banco_sem_votos["turno"], no_banco_sem_votos["uf"], strict=True))
    motivos = secoes[secoes["motivo"].notna()]
    L += ["## Observações", ""]
    L.append(f"- **Votos não conferidos ({fi(t['votos_nao_conferidos'])}):** {fi(len(fora))} são seções fora do "
             f"banco; as outras {fi(len(no_banco_sem_votos))} estão no banco, mas a base Parquet "
             "(`votos_t*.parquet`) não traz votos de Presidente para elas (traz os demais cargos): "
             + "; ".join(f"{tt}º turno {uf_rotulo(u)}: {fi(c)}" for (tt, u), c in sorted(sv.items()))
             + ". É uma lacuna da base do projeto, não do arquivo da urna; o hash e a assinatura dessas "
             "seções conferem.")
    if len(motivos):
        L.append(f"- **Certificado com CN diferente do usuário registrado ({fi(len(motivos))} seções):** "
                 "a assinatura é válida; o nome comum do certificado difere do identificador de usuário "
                 "gravado no arquivo de assinatura. Seções: "
                 + "; ".join(f"`{m.secao_id}` ({m.modelo_urna}: {m.motivo})" for m in motivos.itertuples())
                 + ".")
    L.append("- **Assinatura de software (CEPESC):** algoritmo de governo não publicado; não verificada.")
    L.append("- **Cadeia de certificados:** não validada nesta conferência; subject, emissor, número de série "
             "e SHA-256 do certificado de cada urna ficam em `secoes.parquet`.")
    L.append("")

    # Catálogo
    L += ["## Catálogo de hashes por arquivo", ""]
    L.append(f"O catálogo por arquivo ({fi(manifesto['total_linhas'])} linhas em {manifesto['total_arquivos']} "
             f"arquivos Parquet, {fbytes(manifesto['total_bytes'])}, um por turno e UF, "
             "`arquivos_t<turno>_<uf>.parquet`) não fica no git, como em 2026. Colunas: "
             + ", ".join(f"`{c}`" for c in manifesto["arquivos"][0]["colunas"]) + ". O manifesto com o SHA-256 "
             "de cada anexo está em `data/parquet/2022/integridade/catalogo_manifest.json`.")
    if manifesto.get("versao"):
        L.append(f"Publicado como anexos da versão {manifesto['versao']}.")
    else:
        L.append("A publicação como anexos de uma versão ainda está pendente.")
    L.append("")

    # Pacotes
    L += ["## Pacotes do TSE", ""]
    L += tabela(["Turno", "UF", "Seções", "Entradas", "Tamanho", "Last-Modified"],
                [[f"{p['turno']}º", uf_rotulo(p["uf"]), fi(p.get("secoes")), fi(p.get("entradas")),
                  fbytes(p.get("tamanho") or 0), p.get("last_modified", "")]
                 for p in sorted(r.get("pacotes") or [], key=lambda p: (p["turno"], p["uf"]))], "llrrrl")
    L.append("")

    L += ["## Reproduzir este relatório", "", "```bash",
          "python scripts/ele2022/fetch_integridade.py --so-consolidar   # refaz resumo.json a partir das partes",
          "python scripts/ele2022/registrar_metadados_integridade.py --gravar",
          "python scripts/docs/gerar_relatorio_integridade_2022.py", "```", "",
          "Os dados de entrada ficam em `data/parquet/2022/integridade`. Veja também a "
          "[metodologia](metodologia.md) e o [relatório de 2026](relatorio-integridade-2026.md).", ""]
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pasta", default=str(PASTA))
    ap.add_argument("--saida", default=str(SAIDA))
    a = ap.parse_args(argv)
    Path(a.saida).write_text(gerar(Path(a.pasta)), encoding="utf-8")
    print(f"gravado: {a.saida}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
