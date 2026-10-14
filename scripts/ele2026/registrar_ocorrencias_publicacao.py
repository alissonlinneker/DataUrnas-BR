"""Registra ocorrências de publicação encontradas nos logs da coleta de 2026.

Uma ocorrência de publicação é um arquivo que o TSE lista no aux.json da seção,
mas que não está disponível no servidor (HTTP 404). Não é divergência de hash nem
de assinatura: o arquivo simplesmente não pôde ser verificado. O registro serve
para reportar ao TSE e investigar depois.

O script lê os logs, extrai as ocorrências e mantém, sem duplicar,
data/parquet/2026/integridade/ocorrencias_publicacao.jsonl. Pode ser executado
quantas vezes for preciso, inclusive durante a coleta.

Uso:
    python3 scripts/ele2026/registrar_ocorrencias_publicacao.py
    python3 scripts/ele2026/registrar_ocorrencias_publicacao.py --acompanhar 300
"""

from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
LOGS = sorted((RAIZ / "data").glob("ele2026_integridade*.log"))
SAIDA = RAIZ / "data/parquet/2026/integridade/ocorrencias_publicacao.jsonl"
BASE_URL = "https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3220/dados"

PADRAO = re.compile(
    r"^(?P<data>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+ WARNING erro em "
    r"(?P<uf>[a-z]{2})/(?P<mun>\d{5})/(?P<zona>\d{4})/(?P<secao>\d{4}): "
    r"RuntimeError\('HTTP (?P<status>\d{3}) em arquivo listado no aux\.json: (?P<arquivo>[^']+)'\)"
)


def tipo_arquivo(nome: str) -> str:
    """Tipo pelo sufixo do nome (bu, rdv, log, imgbu, vota...)."""
    sufixo = nome.rsplit("-", 1)[-1]
    return sufixo.split(".", 1)[0]


def extrair(linhas: list[str]) -> list[dict]:
    """Extrai ocorrências de publicação das linhas de log."""
    ocorrencias = []
    for linha in linhas:
        m = PADRAO.match(linha.strip())
        if not m:
            continue
        g = m.groupdict()
        ocorrencias.append({
            "categoria": "arquivo_listado_nao_publicado",
            "uf": g["uf"],
            "cd_mun": g["mun"],
            "zona": g["zona"],
            "secao": g["secao"],
            "arquivo": g["arquivo"],
            "tipo": tipo_arquivo(g["arquivo"]),
            "http_status": int(g["status"]),
            "primeira_ocorrencia": g["data"],
            "url_secao": f"{BASE_URL}/{g['uf']}/{g['mun']}/{g['zona']}/{g['secao']}/",
            "observacao": (
                "Arquivo listado no aux.json da seção e indisponível no servidor do TSE. "
                "Não é divergência de hash nem de assinatura; o arquivo não pôde ser verificado."
            ),
        })
    return ocorrencias


def enriquecer(o: dict) -> dict:
    """Acrescenta a situação da seção no aux.json (status e data de recebimento).

    Ajuda a investigar: seções ainda "Recebida" (não "Totalizada") ou recebidas
    dias depois da eleição tendem a ter publicação incompleta.
    """
    import urllib.request

    url = f"{o['url_secao']}p003220-{o['uf']}-m{o['cd_mun']}-z{o['zona']}-s{o['secao']}-aux.json"
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


def atualizar() -> int:
    """Lê os logs e acrescenta ao registro as ocorrências novas. Devolve quantas entraram."""
    existentes: dict[tuple, dict] = {}
    if SAIDA.exists():
        for linha in SAIDA.read_text(encoding="utf-8").splitlines():
            if linha.strip():
                o = json.loads(linha)
                existentes[chave(o)] = o
    novas = []
    for log in LOGS:
        for o in extrair(log.read_text(encoding="utf-8", errors="replace").splitlines()):
            if chave(o) not in existentes:
                existentes[chave(o)] = o
                novas.append(enriquecer(o))
    if novas:
        SAIDA.parent.mkdir(parents=True, exist_ok=True)
        with SAIDA.open("a", encoding="utf-8") as fh:
            for o in novas:
                fh.write(json.dumps(o, ensure_ascii=False) + "\n")
    return len(novas)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--acompanhar", type=int, default=0, metavar="SEGUNDOS",
                    help="repete a leitura a cada N segundos enquanto houver coleta rodando")
    args = ap.parse_args()
    while True:
        n = atualizar()
        total = sum(1 for _ in SAIDA.open(encoding="utf-8")) if SAIDA.exists() else 0
        print(f"{time.strftime('%H:%M:%S')} novas: {n} | total registrado: {total}", flush=True)
        if not args.acompanhar:
            break
        time.sleep(args.acompanhar)


if __name__ == "__main__":
    main()
