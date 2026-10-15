"""Registra ocorrências de publicação encontradas nos logs da coleta de 2026.

Uma ocorrência de publicação é um arquivo que o TSE lista no aux.json da seção,
mas que não está disponível no servidor (HTTP 404). Não é divergência de hash nem
de assinatura: o arquivo simplesmente não pôde ser verificado. O registro serve
para reportar ao TSE e investigar depois.

O script lê os logs, extrai as ocorrências e mantém, sem duplicar,
data/parquet/2026/integridade/ocorrencias_publicacao.jsonl. Pode ser executado
quantas vezes for preciso, inclusive durante a coleta.

Com --turno 2 lê data/ele2026_t2_integridade*.log e grava em
data/parquet/2026/t2/integridade/ocorrencias_publicacao.jsonl, com as URLs do
pleito 3221.

Uso:
    python3 scripts/ele2026/registrar_ocorrencias_publicacao.py
    python3 scripts/ele2026/registrar_ocorrencias_publicacao.py --acompanhar 300
    python3 scripts/ele2026/registrar_ocorrencias_publicacao.py --turno 2
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
if str(RAIZ / "src") not in sys.path:
    sys.path.insert(0, str(RAIZ / "src"))

from dataurnas.config import TSE_BASE_URL  # noqa: E402
from dataurnas.downloader import ele2026 as E  # noqa: E402


def caminhos(turno: int = 1) -> dict:
    """Logs lidos, arquivo de saída, pleito e URL base das seções do turno."""
    p = E.parametros_turno(turno)
    return {
        "logs": sorted((RAIZ / "data").glob(f"{p['prefixo_log']}integridade*.log")),
        "saida": p["saida"] / "integridade" / "ocorrencias_publicacao.jsonl",
        "pleito": p["pleito"],
        "base_url": f"{TSE_BASE_URL}/{p['ciclo']}/arquivo-urna/{p['pleito']}/dados",
    }


_T1 = caminhos(1)
LOGS = _T1["logs"]
SAIDA = _T1["saida"]
BASE_URL = _T1["base_url"]

# Formato antigo: o 404 derrubava a seção (WARNING "erro em ... RuntimeError(...)").
PADRAO = re.compile(
    r"^(?P<data>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ WARNING erro em "
    r"(?P<uf>[a-z]{2})/(?P<mun>\d{5})/(?P<zona>\d{4})/(?P<secao>\d{4}): "
    r"RuntimeError\('HTTP (?P<status>\d{3}) em arquivo listado no aux\.json: (?P<arquivo>[^']+)'\)"
)
# Formato novo: a seção segue verificada e o arquivo indisponível vira uma linha
# "PUBLICACAO" (um arquivo por linha).
PADRAO_PUBLICACAO = re.compile(
    r"^(?P<data>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ WARNING PUBLICACAO "
    r"(?P<uf>[a-z]{2})/(?P<mun>\d{5})/(?P<zona>\d{4})/(?P<secao>\d{4}): "
    r"HTTP (?P<status>\d{3}) em arquivo listado no aux\.json: (?P<arquivo>\S+)$"
)


def tipo_arquivo(nome: str) -> str:
    """Tipo pelo sufixo do nome (bu, rdv, log, imgbu, vota...)."""
    sufixo = nome.rsplit("-", 1)[-1]
    return sufixo.split(".", 1)[0]


def extrair(linhas: list[str], base_url: str = BASE_URL) -> list[dict]:
    """Extrai ocorrências de publicação das linhas de log (formatos antigo e novo).

    Sem duplicar: a mesma seção, arquivo e status entram uma vez só, com a data
    da primeira ocorrência. No formato antigo, uma linha pode listar vários
    arquivos separados por vírgula.
    """
    ocorrencias = []
    vistos: set[tuple] = set()
    for linha in linhas:
        linha = linha.strip()
        m = PADRAO.match(linha) or PADRAO_PUBLICACAO.match(linha)
        if not m:
            continue
        g = m.groupdict()
        for arquivo in (a.strip() for a in g["arquivo"].split(",")):
            k = (g["uf"], g["mun"], g["zona"], g["secao"], arquivo, int(g["status"]))
            if not arquivo or k in vistos:
                continue
            vistos.add(k)
            ocorrencias.append(_ocorrencia(g, arquivo, base_url))
    return ocorrencias


def _ocorrencia(g: dict, arquivo: str, base_url: str = BASE_URL) -> dict:
    return {
        "categoria": "arquivo_listado_nao_publicado",
        "uf": g["uf"],
        "cd_mun": g["mun"],
        "zona": g["zona"],
        "secao": g["secao"],
        "arquivo": arquivo,
        "tipo": tipo_arquivo(arquivo),
        "http_status": int(g["status"]),
        "primeira_ocorrencia": g["data"],
        "url_secao": f"{base_url}/{g['uf']}/{g['mun']}/{g['zona']}/{g['secao']}/",
        "observacao": (
            "Arquivo listado no aux.json da seção e indisponível no servidor do TSE. "
            "Não é divergência de hash nem de assinatura; o arquivo não pôde ser verificado."
        ),
    }


def enriquecer(o: dict, pleito: str = _T1["pleito"]) -> dict:
    """Acrescenta a situação da seção no aux.json (status e data de recebimento).

    Ajuda a investigar: seções ainda "Recebida" (não "Totalizada") ou recebidas
    dias depois da eleição tendem a ter publicação incompleta.
    """
    import urllib.request

    url = f"{o['url_secao']}p{int(pleito):06d}-{o['uf']}-m{o['cd_mun']}-z{o['zona']}-s{o['secao']}-aux.json"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        aux = json.loads(urllib.request.urlopen(req, timeout=30).read())
        h = (aux.get("hashes") or [{}])[0]
        o.update({
            "aux_status_secao": aux.get("st"),
            "aux_status_arquivos": h.get("st"),
            "aux_data_recebimento": f"{h.get('dr', '')} {h.get('hr', '')}".strip(),
            "aux_consultado_em": time.strftime("%Y-%m-%d %H:%M:%S"),
        })
    except Exception as e:  # registro não pode falhar por causa do enriquecimento
        o["aux_erro"] = repr(e)
    return o


def chave(o: dict) -> tuple:
    return (o["uf"], o["cd_mun"], o["zona"], o["secao"], o["arquivo"], o["http_status"])


def atualizar(turno: int = 1) -> int:
    """Lê os logs e acrescenta ao registro as ocorrências novas. Devolve quantas entraram."""
    c = _T1 if turno == 1 else caminhos(turno)
    saida = c["saida"]
    existentes: dict[tuple, dict] = {}
    if saida.exists():
        for linha in saida.read_text(encoding="utf-8").splitlines():
            if linha.strip():
                o = json.loads(linha)
                existentes[chave(o)] = o
    novas = []
    # relê a lista de logs a cada chamada (--acompanhar pega logs novos)
    for log in caminhos(turno)["logs"]:
        texto = log.read_text(encoding="utf-8", errors="replace").splitlines()
        for o in extrair(texto, c["base_url"]):
            if chave(o) not in existentes:
                existentes[chave(o)] = o
                novas.append(enriquecer(o, c["pleito"]))
    if novas:
        saida.parent.mkdir(parents=True, exist_ok=True)
        with saida.open("a", encoding="utf-8") as fh:
            for o in novas:
                fh.write(json.dumps(o, ensure_ascii=False) + "\n")
    return len(novas)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--acompanhar", type=int, default=0, metavar="SEGUNDOS",
                    help="repete a leitura a cada N segundos enquanto houver coleta rodando")
    ap.add_argument("--turno", type=int, choices=E.TURNOS, default=1,
                    help="turno da coleta: 1 ou 2 (padrão: 1)")
    args = ap.parse_args()
    saida = caminhos(args.turno)["saida"]
    while True:
        n = atualizar(args.turno)
        total = sum(1 for _ in saida.open(encoding="utf-8")) if saida.exists() else 0
        print(f"{time.strftime('%H:%M:%S')} novas: {n} | total registrado: {total}", flush=True)
        if not args.acompanhar:
            break
        time.sleep(args.acompanhar)


if __name__ == "__main__":
    main()
