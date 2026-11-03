#!/usr/bin/env python3
"""Emissão tardia do BU no 2º turno de 2026 (item 14) e a contingência de
Belo Horizonte 0039/0168 no 1º turno (item 8a), lidas no log da urna.

Item 14 de docs/auditoria-consistencia-bu-2026.md: 368 seções do 2º turno
(25/10/2026) têm o BU emitido mais de 1 hora depois do encerramento registrado
no próprio BU. Este script baixa do TSE o -log.jez dessas 368 seções e de 368
seções de controle das mesmas zonas (emissão até 10 minutos depois do
encerramento), lê o logd.dat de cada uma e descreve o que a urna registrou
entre o encerramento e a emissão do BU.

Item 8a: a seção mg 41238 0039/0168 foi apurada no Sistema de Apuração (SA)
no 1º turno. O script baixa todos os arquivos publicados dessa seção no 1º
turno (pleito 3220) e no 2º (3221) e descreve o log do SA e o log das urnas.

Fontes, todas públicas:
  data/parquet/2026/t2/encerramento/secoes_encerramento.parquet
      (analisar_encerramento_t2.py: hash, nome do BU, encerramento e emissão
      em hora local, que é a hora gravada no BU)
  https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/<pleito>/dados/
      <uf>/<mun>/<zona>/<secao>/p00<pleito>-<uf>-m<mun>-z<zona>-s<secao>-aux.json
      e os arquivos na subpasta do hash.

O log é texto latin-1 com colunas: data e hora local da urna, nível, número
interno da urna, aplicação, mensagem, hash encadeado. O log do 2º turno
acumula o do 1º; só entram eventos de 25/10/2026. O pacote -log.jez de uma
seção com troca de urna traz o log da urna substituída aninhado
(parsers/log.textos_zip junta os dois na ordem de uso).

Etapas (cada uma pode rodar sozinha):
  selecionar  monta amostra.csv (368 tardias + 368 controles) a partir do parquet
  baixar      um processo, no máximo --taxa req/s (padrão 2,5): aux.json e log
              de cada seção da amostra, e todos os arquivos de BH 0039/0168
  analisar    lê os logs e grava secoes.csv, eventos_intervalo.csv,
              vocabulario_intervalo.csv, bh_0039_0168.json, resumo.json e
              tabelas.md em --saida

Uso (no servidor de análise; brutos fora do git):
  python3 scripts/ele2026/emissao_tardia_logs.py selecionar \\
      --encerramento secoes_encerramento.parquet --saida /dev/shm/et/out
  python3 scripts/ele2026/emissao_tardia_logs.py baixar \\
      --saida /dev/shm/et/out --brutos ~/dataurnas-t2/emissao_tardia
  python3 scripts/ele2026/emissao_tardia_logs.py analisar \\
      --saida /dev/shm/et/out --brutos ~/dataurnas-t2/emissao_tardia
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import logging
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[2]
SRC = str(ROOT / "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

log = logging.getLogger("emissao_tardia_logs")

CICLO = "ele2026"
PLEITO = {1: "3220", 2: "3221"}
DATA = {1: "04/10/2026", 2: "25/10/2026"}
LIMIAR_TARDIA = 3600   # segundos entre encerramento e emissão do BU
LIMIAR_CONTROLE = 600  # controle: emissão até 10 minutos depois do encerramento
SEED = 2026

BH = {"uf": "mg", "cd_mun": "41238", "zona": "0039", "secao": "0168"}

CAMPOS_AMOSTRA = ["grupo", "uf", "cd_mun", "municipio", "zona", "secao", "tipo_urna",
                  "nome_arquivo", "hash", "fuso_utc", "encerramento_local", "emissao_local",
                  "recebimento_bsb", "atraso_s", "aptos", "comparecimento"]


def chave(r: dict) -> str:
    return f"{r['uf']}/{r['cd_mun']}/{r['zona']}/{r['secao']}"


def _ordem(k: str) -> str:
    return hashlib.sha256(f"{SEED}/{k}".encode()).hexdigest()


def _dt(s: str) -> datetime:
    return datetime.strptime(str(s)[:19], "%Y-%m-%d %H:%M:%S")


# ---------------------------------------------------------------------------
# Seleção
# ---------------------------------------------------------------------------

def selecionar(encerramento: Path, saida: Path) -> Path:
    """368 seções com emissão mais de 1 hora depois do encerramento (Brasil) e,
    por zona, o mesmo número de controles com emissão em até 10 minutos,
    escolhidos por ordem pseudoaleatória estável (sha256 da chave). Se a zona
    não tiver controles suficientes, completa com o mesmo município."""
    import pandas as pd

    df = pd.read_parquet(encerramento)
    df = df[(df["uf"] != "zz") & df["encerramento_local"].notna() & df["emissao_local"].notna()].copy()
    df["atraso_s"] = [(_dt(m) - _dt(e)).total_seconds()
                      for e, m in zip(df["encerramento_local"], df["emissao_local"], strict=True)]
    tard = df[df["atraso_s"] > LIMIAR_TARDIA].copy()
    tard["grupo"] = "tardia"
    cand = df[(df["atraso_s"] >= 0) & (df["atraso_s"] <= LIMIAR_CONTROLE)].copy()
    cand["k"] = [chave(r) for r in cand[["uf", "cd_mun", "zona", "secao"]].to_dict("records")]
    cand["ordem"] = [_ordem(k) for k in cand["k"]]
    cand = cand.sort_values("ordem")
    usados: set[str] = set()
    controles = []
    falta_mun: Counter = Counter()
    for (uf, mun, zona), g in tard.groupby(["uf", "cd_mun", "zona"]):
        n = len(g)
        c = cand[(cand["uf"] == uf) & (cand["cd_mun"] == mun) & (cand["zona"] == zona)
                 & ~cand["k"].isin(usados)].head(n)
        usados.update(c["k"])
        controles.append(c)
        if len(c) < n:
            falta_mun[(uf, mun)] += n - len(c)
    for (uf, mun), n in falta_mun.items():
        c = cand[(cand["uf"] == uf) & (cand["cd_mun"] == mun) & ~cand["k"].isin(usados)].head(n)
        usados.update(c["k"])
        controles.append(c)
    ctrl = pd.concat(controles)
    ctrl["grupo"] = "controle"
    am = pd.concat([tard, ctrl])[CAMPOS_AMOSTRA].sort_values(["grupo", "uf", "cd_mun", "zona", "secao"])
    saida.mkdir(parents=True, exist_ok=True)
    p = saida / "amostra.csv"
    am.to_csv(p, index=False)
    log.info("amostra: %d tardias, %d controles (%d completados no município)",
             len(tard), len(ctrl), sum(falta_mun.values()))
    return p


def ler_amostra(saida: Path) -> list[dict]:
    with (saida / "amostra.csv").open(encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for c in ("cd_mun", "zona", "secao"):
            r[c] = r[c].zfill({"cd_mun": 5, "zona": 4, "secao": 4}[c])
    return rows


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------

def caminho_aux(brutos: Path, r: dict, turno: int) -> Path:
    return brutos / "aux" / f"t{turno}" / r["uf"] / f"{r['cd_mun']}-{r['zona']}-{r['secao']}.json"


def caminho_log(brutos: Path, r: dict, h: str, nome: str) -> Path:
    return brutos / "t2" / r["uf"] / f"{r['cd_mun']}-{r['zona']}-{r['secao']}" / h[:16] / nome


def _grava(dest: Path, raw: bytes) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.name + ".tmp")
    tmp.write_bytes(raw)
    tmp.rename(dest)


async def baixar(saida: Path, brutos: Path, rate: float) -> None:
    """aux.json do 2º turno de cada seção da amostra e o log (tp log ou logsa)
    de todos os hashes listados; para BH 0039/0168, aux.json e todos os
    arquivos de todos os hashes nos dois turnos. Um processo, um HttpFetcher,
    no máximo `rate` req/s (o limitador espaça cada requisição, retentativas
    incluídas)."""
    from dataurnas.downloader import ele2026 as E

    amostra = ler_amostra(saida)
    f = E.HttpFetcher(concurrency=3, retries=8, rate=rate, rate_max=rate, http2=False)
    erros = brutos / "erros.jsonl"
    brutos.mkdir(parents=True, exist_ok=True)
    feitos = 0

    def erro(k: str, etapa: str, e: object) -> None:
        with erros.open("a", encoding="utf-8") as fe:
            fe.write(json.dumps({"chave": k, "etapa": etapa, "erro": str(e)[:300]}) + "\n")

    async def aux_json(r: dict, turno: int) -> Optional[dict]:
        p = caminho_aux(brutos, r, turno)
        if p.exists():
            return json.loads(p.read_bytes())
        raw = await f.get(E.url_aux(r["uf"], r["cd_mun"], r["zona"], r["secao"],
                                    pleito=PLEITO[turno], ciclo=CICLO))
        if raw is None:
            return None
        _grava(p, raw)
        return json.loads(raw)

    async def uma(r: dict) -> None:
        nonlocal feitos
        k = chave(r)
        try:
            aux = await aux_json(r, 2)
            if aux is None:
                erro(k, "aux", "aux_nao_publicado")
            else:
                for h in aux.get("hashes") or []:
                    for a in h.get("arq") or []:
                        if a.get("tp") not in ("log", "logsa"):
                            continue
                        dest = caminho_log(brutos, r, h["hash"], a["nm"])
                        if dest.exists():
                            continue
                        raw = await f.get(E.url_arquivo(r["uf"], r["cd_mun"], r["zona"], r["secao"],
                                                        h["hash"], a["nm"], pleito=PLEITO[2],
                                                        ciclo=CICLO))
                        if raw is None:
                            erro(k, a["nm"], "nao_publicado")
                        else:
                            _grava(dest, raw)
        except Exception as e:  # noqa: BLE001  refeito na próxima execução
            erro(k, "rede", f"{type(e).__name__}: {e}")
        feitos += 1
        if feitos % 100 == 0:
            log.info("%d/%d seções (%s) %s", feitos, len(amostra), f.rate_info(), f.stats)

    async def bh() -> None:
        for turno in (1, 2):
            try:
                aux = await aux_json(BH, turno)
                if aux is None:
                    erro(chave(BH), f"aux_t{turno}", "aux_nao_publicado")
                    continue
                for h in aux.get("hashes") or []:
                    for a in h.get("arq") or []:
                        dest = brutos / "bh" / f"t{turno}" / h["hash"][:16] / a["nm"]
                        if dest.exists():
                            continue
                        raw = await f.get(E.url_arquivo(BH["uf"], BH["cd_mun"], BH["zona"],
                                                        BH["secao"], h["hash"], a["nm"],
                                                        pleito=PLEITO[turno], ciclo=CICLO))
                        if raw is None:
                            erro(chave(BH), a["nm"], "nao_publicado")
                        else:
                            _grava(dest, raw)
            except Exception as e:  # noqa: BLE001
                erro(chave(BH), f"rede_t{turno}", f"{type(e).__name__}: {e}")

    try:
        await bh()
        for i in range(0, len(amostra), 30):
            await asyncio.gather(*[uma(r) for r in amostra[i:i + 30]])
    finally:
        await f.close()
    log.info("download concluído: %s", f.stats)


# ---------------------------------------------------------------------------
# Leitura do log
# ---------------------------------------------------------------------------

EV_CONFIRMADO = "Procedimento de encerramento confirmado"   # = hora de encerramento do BU
EV_INICIO_ENC = ("Inicio do Encerramento", "Início do Encerramento")
EV_BU = "Gerando relatório [BU] [INÍCIO]"                     # = hora de emissão do BU
EV_ARQ_BU = "Gerando arquivo de resultado [bu.dat] + [Início]"
EV_VIA_BU = "Imprimindo relatório [BU] via"
EV_VOTO = "O voto do eleitor foi computado"
EV_PRONTA = "Urna pronta para receber votos"
EV_LIGADA = "Urna ligada em"
EV_DESL_CHAVE = "Urna desligada pela chave"
EV_FECHA_LOG = "Fechando o arquivo de Log"
DESLIGAMENTO_NORMAL = (EV_DESL_CHAVE, EV_FECHA_LOG, "Desligando a urna",
                       "Urna reiniciada a pedido do aplicativo")
EV_PERGUNTA_MES = "Operador indagado se ocorrerá registro de mesários"
EV_MES_REG = re.compile(r"^Mesário \d+ registrado$")
EV_TITULO_INV = "Digitado título inválido para o registro de mesário"
EV_FIM_MES = "Operador encerrou ciclo de registro de mesários"
# linhas que a urna grava sozinha a cada 30 minutos (estado da mídia, memória e energia)
AUTOMATICAS = ("Espaço livre na", "Espaço utilizado na", "Quantidade de memória",
               "Urna ligada conectada na rede", "Urna ligada somente", "Urna ligada na bateria")
RE_ENERGIA = re.compile(r"bateria|energia|rede el[eé]trica|rede CA", re.IGNORECASE)
RE_NUM = re.compile(r"\d+")


def _seg(h: str) -> int:
    return int(h[0:2]) * 3600 + int(h[3:5]) * 60 + int(h[6:8])


def _hms(s: Optional[int]) -> Optional[str]:
    if s is None:
        return None
    return f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}"


def automatica(msg: str) -> bool:
    return msg.startswith(AUTOMATICAS)


def normalizar(msg: str) -> str:
    return RE_NUM.sub("N", msg)


def linhas_log(raw: bytes) -> list[dict]:
    """Linhas do log na ordem do arquivo (logs aninhados de urnas trocadas
    primeiro, como em parsers/log.textos_zip)."""
    from dataurnas.analyzer.rdv_recontagem import texto_log

    texto = texto_log(raw) or ""
    out = []
    for ln in texto.split("\n"):
        p = ln.rstrip("\r").split("\t")
        if len(p) < 5 or len(p[0]) < 19:
            continue
        out.append({"data": p[0][:10], "hora": p[0][11:19], "nivel": p[1], "urna": p[2],
                    "app": p[3], "msg": p[4]})
    return out


def _eh_emissao(x: dict) -> bool:
    """Linha que marca a emissão do BU: 'Gerando relatório [BU] [INÍCIO]' na
    urna (VOTA) ou, na recuperação de dados (RED) em outra urna, a geração do
    arquivo bu.dat."""
    return x["msg"] == EV_BU or (x["app"] == "RED" and x["msg"] == EV_ARQ_BU)


def analisar_secao(r: dict, linhas: list[dict], data: str = DATA[2]) -> tuple[dict, list[dict]]:
    """Métricas do intervalo entre o encerramento e a emissão do BU e a lista
    de eventos desse intervalo.

    O encerramento do BU coincide com a linha 'Procedimento de encerramento
    confirmado' e a emissão com 'Gerando relatório [BU] [INÍCIO]' (ou, quando
    o BU sai do Recuperador de Dados, com a geração do bu.dat). O intervalo é
    a janela de horário [encerramento, emissão] do dia da eleição, com as
    linhas em ordem de horário (num pacote com urna trocada, o log aninhado e o
    da urna final se sobrepõem na ordem do arquivo)."""
    enc = _seg(r["encerramento_local"][11:19])
    emi = _seg(r["emissao_local"][11:19])
    dia = [x | {"s": _seg(x["hora"]), "pos": i} for i, x in enumerate(linhas) if x["data"] == data]
    m: dict = {"chave": chave(r), "grupo": r["grupo"], "uf": r["uf"], "cd_mun": r["cd_mun"],
               "zona": r["zona"], "secao": r["secao"], "tipo_urna": r["tipo_urna"],
               "fuso_utc": r["fuso_utc"],
               "encerramento_bu": r["encerramento_local"][11:19],
               "emissao_bu": r["emissao_local"][11:19], "atraso_min": round(float(r["atraso_s"]) / 60, 1),
               "linhas_log": len(linhas), "linhas_dia": len(dia)}
    # contagens do dia inteiro, em todas as urnas do pacote
    m["votos_dia"] = sum(1 for x in dia if EV_VOTO in x["msg"])
    m["votos_apos_hora_encerramento_bu"] = sum(1 for x in dia if EV_VOTO in x["msg"] and x["s"] > enc)
    m["prontas_apos_hora_encerramento_bu"] = sum(1 for x in dia if EV_PRONTA in x["msg"] and x["s"] > enc)
    m["bu_gerado_no_dia"] = sum(1 for x in dia if _eh_emissao(x))
    m["arquivo_bu_gerado_no_dia"] = sum(1 for x in dia if x["msg"] == EV_ARQ_BU)
    m["vias_bu_impressas_no_dia"] = sum(1 for x in dia if x["msg"].startswith(EV_VIA_BU))
    m["encerramentos_confirmados_no_dia"] = sum(1 for x in dia if x["msg"] == EV_CONFIRMADO)
    m["urnas_no_dia"] = len({x["urna"] for x in dia})
    conf = [x for x in dia if x["msg"] == EV_CONFIRMADO]
    bu = [x for x in dia if _eh_emissao(x)]
    if not conf or not bu:
        m["status"] = "sem_conf" if not conf else "sem_bu"
        return m, []
    c = min(conf, key=lambda x: abs(x["s"] - enc))
    e = min(bu, key=lambda x: abs(x["s"] - emi))
    m["status"] = "ok"
    m["hora_confirmado_log"] = c["hora"]
    m["hora_bu_log"] = e["hora"]
    m["app_emissao"] = e["app"]
    m["dif_encerramento_s"] = c["s"] - enc
    m["dif_emissao_s"] = e["s"] - emi
    evs = sorted((x for x in dia if c["s"] <= x["s"] <= e["s"]), key=lambda x: (x["s"], x["pos"]))
    msgs = [x["msg"] for x in evs]
    ini = [x["hora"] for x in evs if x["msg"] in EV_INICIO_ENC]
    m["hora_inicio_encerramento"] = ini[-1] if ini else None
    m["eventos_intervalo"] = len(evs)
    m["eventos_operador_intervalo"] = sum(1 for x in msgs if not automatica(x))
    m["votos_intervalo"] = sum(1 for x in msgs if EV_VOTO in x)
    m["prontas_intervalo"] = sum(1 for x in msgs if EV_PRONTA in x)
    m["urnas_intervalo"] = ",".join(sorted({x["urna"] for x in evs}))
    m["apps_intervalo"] = ",".join(sorted({x["app"] for x in evs}))
    m["ligacoes_intervalo"] = sum(1 for x in msgs if x.startswith(EV_LIGADA))
    m["deslig_chave_intervalo"] = sum(1 for x in msgs if x == EV_DESL_CHAVE)
    m["fecha_log_intervalo"] = sum(1 for x in msgs if x == EV_FECHA_LOG)
    # ligação sem nenhum registro de desligamento desde o início do intervalo (a
    # urna está ligada no encerramento) ou desde a ligação anterior: a urna parou
    # sem o desligamento normal (chave, reinício pedido pelo aplicativo ou
    # fechamento do log)
    abruptos, desligou = 0, False
    for x in msgs:
        if x.startswith(EV_LIGADA):
            abruptos += 0 if desligou else 1
            desligou = False
        elif x in DESLIGAMENTO_NORMAL:
            desligou = True
    m["religacoes_sem_desligamento"] = abruptos
    m["erros_intervalo"] = sum(1 for x in msgs if x.startswith("Não é possível continuar a execução"))
    m["mesarios_registrados_intervalo"] = sum(1 for x in msgs if EV_MES_REG.match(x))
    m["titulos_invalidos_intervalo"] = sum(1 for x in msgs if x == EV_TITULO_INV)
    m["pergunta_registro_mesarios"] = int(any(x == EV_PERGUNTA_MES for x in msgs))
    energia = [x for x in msgs if RE_ENERGIA.search(x)]
    m["msgs_energia_intervalo"] = " | ".join(sorted(set(normalizar(x) for x in energia)))[:500]
    # urna sem a rede elétrica (falta de energia ou cabo desligado) em algum momento do intervalo
    m["sem_rede_eletrica"] = int(any(x.startswith(("Urna operando na bateria", "Urna operando com bateria",
                                                   "Urna ligada desconectada da rede CA"))
                                     for x in msgs))
    # maior espera sem ação de operador (linhas automáticas não contam)
    op = [x for x in evs if not automatica(x["msg"])]
    gap, a, b = -1, None, None
    for x, y in zip(op, op[1:], strict=False):
        if y["s"] - x["s"] > gap:
            gap, a, b = y["s"] - x["s"], x, y
    m["maior_espera_min"] = round(gap / 60, 1) if a is not None else None
    m["espera_de"] = a["hora"] if a else None
    m["espera_ate"] = b["hora"] if b else None
    m["evento_antes_espera"] = normalizar(a["msg"]) if a else None
    m["evento_depois_espera"] = normalizar(b["msg"]) if b else None
    m["mesarios_registrados_apos_espera"] = (sum(1 for x in op if x["s"] >= b["s"] and EV_MES_REG.match(x["msg"]))
                                             if b else None)
    m["classe"] = classificar(m)
    eventos = [{"chave": m["chave"], "grupo": m["grupo"], "ordem": k, "hora": x["hora"],
                "urna": x["urna"], "app": x["app"], "automatica": int(automatica(x["msg"])),
                "msg": x["msg"]} for k, x in enumerate(evs)]
    return m, eventos


CLASSES = {
    "voto_apos_encerramento": "voto computado depois do encerramento",
    "reabertura": "nova 'Urna pronta para receber votos' depois do encerramento",
    "troca_urna": "troca de urna no intervalo (outra urna emitiu o BU)",
    "desligada_religada": "urna desligada e religada antes da emissão",
    "registro_mesarios": "urna ligada na tela de registro de mesários, sem reinício",
    "outro": "outro",
}


def classificar(m: dict) -> str:
    if m["votos_intervalo"] or m["votos_apos_hora_encerramento_bu"]:
        return "voto_apos_encerramento"
    if m["prontas_intervalo"] or m["prontas_apos_hora_encerramento_bu"]:
        return "reabertura"
    if "," in m["urnas_intervalo"]:
        return "troca_urna"
    if m["ligacoes_intervalo"]:
        return "desligada_religada"
    if m["pergunta_registro_mesarios"] and m["evento_antes_espera"] is not None:
        return "registro_mesarios"
    return "outro"


# ---------------------------------------------------------------------------
# Análise
# ---------------------------------------------------------------------------

def _arquivos_log(brutos: Path, r: dict) -> list[Path]:
    d = brutos / "t2" / r["uf"] / f"{r['cd_mun']}-{r['zona']}-{r['secao']}"
    return sorted(p for p in d.glob("*/*") if not p.name.endswith(".tmp"))


def _uma(args: tuple) -> tuple[dict, list[dict]]:
    r, arquivos = args
    if not arquivos:
        return {"chave": chave(r), "grupo": r["grupo"], "status": "sem_log"}, []
    if len(arquivos) > 1:
        log.warning("%s: %d logs publicados, uso o do hash do BU", chave(r), len(arquivos))
    arq = [p for p in arquivos if p.parent.name == r["hash"][:16]] or arquivos
    m, ev = analisar_secao(r, linhas_log(arq[0].read_bytes()))
    m["arquivo"] = arq[0].name
    m["n_logs_publicados"] = len(arquivos)
    return m, ev


def _escrever_csv(p: Path, rows: list[dict]) -> None:
    campos: list[str] = []
    for r in rows:
        for k in r:
            if k not in campos:
                campos.append(k)
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(rows)


def analisar_bh(brutos: Path) -> dict:
    """Arquivos de BH 0039/0168: BU do SA (busa) e RDV do 1º turno, BU e RDV
    do 2º turno, e as linhas do log do SA do dia da eleição."""
    from dataurnas.models import SpecVersion
    from dataurnas.parsers.asn1_helper import decode_envelope
    from dataurnas.parsers.rdv import parse_rdv_bytes, recontar

    out: dict = {"chave": chave(BH)}
    for turno in (1, 2):
        aux = caminho_aux(brutos, BH, turno)
        if aux.exists():
            a = json.loads(aux.read_bytes())
            out[f"aux_t{turno}"] = [{k: h.get(k) for k in ("dr", "hr", "st")}
                                    | {"arquivos": [x["nm"] for x in h.get("arq") or []]}
                                    for h in a.get("hashes") or []]
        for p in sorted((brutos / "bh" / f"t{turno}").glob("*/*")):
            raw = p.read_bytes()
            if p.name.endswith(("-bu.dat", "-busa.dat")):
                _, bu = decode_envelope(raw, "EntidadeBoletimUrna", SpecVersion.V2)
                urna = bu["urna"]
                info = {"arquivo": p.name, "tipoUrna": urna.get("tipoUrna"),
                        "tipoArquivo": urna.get("tipoArquivo"),
                        "numeroInternoUrna": urna["correspondenciaResultado"]["carga"]["numeroInternoUrna"],
                        "motivoUtilizacaoSA": urna.get("motivoUtilizacaoSA"),
                        "dadosSecaoSA": bu.get("dadosSecaoSA"),
                        "dataHoraEmissao": bu.get("dataHoraEmissao"),
                        "historicoCodigosCarga": bu.get("historicoCodigosCarga")}
                for e in bu["resultadosVotacaoPorEleicao"]:
                    for rv in e["resultadosVotacao"]:
                        for tc in rv["totaisVotosCargo"]:
                            if "presidente" in str(tc.get("codigoCargo")):
                                info["aptos"] = e.get("qtdEleitoresAptos")
                                info["comparecimento"] = rv.get("qtdComparecimento")
                                info["presidente"] = {
                                    (str(v["identificacaoVotavel"]["codigo"]) if v.get("identificacaoVotavel")
                                     else v["tipoVoto"]): v["quantidadeVotos"] for v in tc["votosVotaveis"]}
                out[f"bu_t{turno}"] = json.loads(json.dumps(info, default=str))
            elif p.name.endswith("-rdv.dat"):
                rdv = parse_rdv_bytes(raw)
                blocos = []
                for e in rdv.eleicoes:
                    for c in e.cargos:
                        if c.codigo_cargo == 1:
                            blocos.append({"origem": e.origem, "tipo_cedula_sa": e.tipo_cedula_sa,
                                           "origem_votos_sa": e.origem_votos_sa,
                                           "registros": c.n_registros,
                                           "presidente": {f"{k[0]}:{k[1]}" if k[1] else k[0]: v
                                                          for k, v in recontar(c).items()}})
                out[f"rdv_t{turno}"] = {"tipo_arquivo": rdv.tipo_arquivo,
                                        "numero_interno_urna": rdv.numero_interno_urna,
                                        "historico_codigos_carga": rdv.historico_codigos_carga,
                                        "blocos_presidente": blocos}
            elif p.name.endswith((".jez",)):
                linhas = linhas_log(raw)
                dia = [x for x in linhas if x["data"] == DATA[turno]]
                out[f"log_t{turno}"] = {
                    "arquivo": p.name, "linhas": len(linhas), "linhas_dia": len(dia),
                    "urnas": sorted({x["urna"] for x in linhas}),
                    "apps_dia": dict(Counter(x["app"] for x in dia)),
                    "eventos_dia": [f"{x['hora']} {x['urna']} {x['app']} {x['msg']}" for x in dia
                                    if turno == 1 and x["app"] in ("SA", "GAP")
                                    and not x["msg"].startswith("Verificação de assinatura")],
                    "votos_dia": sum(1 for x in dia if EV_VOTO in x["msg"]),
                }
    return out


def analisar(saida: Path, brutos: Path) -> None:
    from concurrent.futures import ProcessPoolExecutor

    amostra = ler_amostra(saida)
    tarefas = [(r, _arquivos_log(brutos, r)) for r in amostra]
    with ProcessPoolExecutor() as ex:
        res = list(ex.map(_uma, tarefas, chunksize=8))
    secoes = [m for m, _ in res]
    eventos = [e for _, ev in res for e in ev]
    _escrever_csv(saida / "secoes.csv", secoes)
    _escrever_csv(saida / "eventos_intervalo.csv", eventos)
    # vocabulário do intervalo por grupo (mensagens normalizadas, sem as automáticas)
    voc: dict = defaultdict(Counter)
    for e in eventos:
        voc[(normalizar(e["msg"]), e["app"])][e["grupo"]] += 1
    _escrever_csv(saida / "vocabulario_intervalo.csv",
                  [{"msg": k[0], "app": k[1], "tardia": c["tardia"], "controle": c["controle"]}
                   for k, c in sorted(voc.items(), key=lambda kv: -sum(kv[1].values()))])
    bh = analisar_bh(brutos)
    (saida / "bh_0039_0168.json").write_text(json.dumps(bh, ensure_ascii=False, indent=1), encoding="utf-8")
    resumo = resumir(secoes)
    (saida / "resumo.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=1), encoding="utf-8")
    (saida / "tabelas.md").write_text(tabelas(resumo, secoes), encoding="utf-8")
    log.info("análise: %d seções, %d eventos no intervalo", len(secoes), len(eventos))


def resumir(secoes: list[dict]) -> dict:
    out: dict = {}
    for g in ("tardia", "controle"):
        s = [m for m in secoes if m.get("grupo") == g]
        ok = [m for m in s if m.get("status") == "ok"]
        soma = lambda k: sum(int(m.get(k) or 0) for m in ok)  # noqa: E731
        com = lambda k: sum(1 for m in ok if int(m.get(k) or 0) > 0)  # noqa: E731
        out[g] = {
            "secoes": len(s),
            "status": dict(Counter(m.get("status") for m in s)),
            "encerramento_bu_igual_log": sum(1 for m in ok if m["dif_encerramento_s"] == 0),
            "emissao_bu_igual_log": sum(1 for m in ok if m["dif_emissao_s"] == 0),
            "classes": dict(Counter(m["classe"] for m in ok)),
            "votos_apos_hora_encerramento_bu": soma("votos_apos_hora_encerramento_bu"),
            "votos_intervalo": soma("votos_intervalo"),
            "prontas_apos_hora_encerramento_bu": soma("prontas_apos_hora_encerramento_bu"),
            "prontas_intervalo": soma("prontas_intervalo"),
            "secoes_com_ligacao_no_intervalo": com("ligacoes_intervalo"),
            "ligacoes_no_intervalo": soma("ligacoes_intervalo"),
            "secoes_com_deslig_chave": com("deslig_chave_intervalo"),
            "secoes_com_religacao_sem_desligamento": com("religacoes_sem_desligamento"),
            "secoes_sem_rede_eletrica": com("sem_rede_eletrica"),
            "secoes_com_erro_fatal": com("erros_intervalo"),
            "secoes_com_mais_de_uma_urna_no_intervalo": sum(1 for m in ok if "," in m["urnas_intervalo"]),
            "secoes_com_pergunta_registro_mesarios": com("pergunta_registro_mesarios"),
            "secoes_com_mesario_registrado_no_intervalo": com("mesarios_registrados_intervalo"),
            "mesarios_registrados_no_intervalo": soma("mesarios_registrados_intervalo"),
            "secoes_com_mesario_registrado_apos_maior_espera": com("mesarios_registrados_apos_espera"),
            "secoes_com_titulo_invalido": com("titulos_invalidos_intervalo"),
            "bu_gerado_no_dia": dict(Counter(m["bu_gerado_no_dia"] for m in ok)),
            "arquivo_bu_gerado_no_dia": dict(Counter(m["arquivo_bu_gerado_no_dia"] for m in ok)),
            "vias_bu_impressas_no_dia": dict(Counter(m["vias_bu_impressas_no_dia"] for m in ok)),
            "encerramentos_confirmados_no_dia": dict(Counter(m["encerramentos_confirmados_no_dia"] for m in ok)),
            "evento_antes_maior_espera": dict(Counter(m["evento_antes_espera"] for m in ok).most_common(15)),
            "evento_depois_maior_espera": dict(Counter(m["evento_depois_espera"] for m in ok).most_common(15)),
        }
    return out


def tabelas(resumo: dict, secoes: list[dict]) -> str:
    t, c = resumo["tardia"], resumo["controle"]
    out = ["| Classe | Tardias | Controles |", "|---|---:|---:|"]
    for k, rot in CLASSES.items():
        out.append(f"| {rot} | {t['classes'].get(k, 0)} | {c['classes'].get(k, 0)} |")
    out += ["", "| Contagem no log | Tardias | Controles |", "|---|---:|---:|"]
    for k in ("votos_apos_hora_encerramento_bu", "votos_intervalo", "prontas_apos_hora_encerramento_bu",
              "secoes_com_ligacao_no_intervalo", "ligacoes_no_intervalo", "secoes_com_deslig_chave",
              "secoes_com_religacao_sem_desligamento", "secoes_sem_rede_eletrica", "secoes_com_erro_fatal",
              "secoes_com_mais_de_uma_urna_no_intervalo", "secoes_com_pergunta_registro_mesarios",
              "secoes_com_mesario_registrado_no_intervalo", "mesarios_registrados_no_intervalo",
              "secoes_com_titulo_invalido", "encerramento_bu_igual_log", "emissao_bu_igual_log"):
        out.append(f"| {k} | {t[k]} | {c[k]} |")
    out += ["", "Seções tardias fora da classe 'registro_mesarios':", "",
            "| Seção | Classe | Encerramento | Emissão | Urnas | Ligações | Sem rede | Erros |",
            "|---|---|---|---|---|---:|---:|---:|"]
    for m in secoes:
        if m.get("grupo") == "tardia" and m.get("classe") not in (None, "registro_mesarios"):
            out.append(f"| {m['chave']} | {m['classe']} | {m['encerramento_bu']} | {m['emissao_bu']} | "
                       f"{m['urnas_intervalo']} | {m['ligacoes_intervalo']} | {m['sem_rede_eletrica']} | "
                       f"{m['erros_intervalo']} |")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("etapa", choices=["selecionar", "baixar", "analisar"])
    ap.add_argument("--encerramento", type=Path,
                    default=ROOT / "data" / "parquet" / "2026" / "t2" / "encerramento"
                    / "secoes_encerramento.parquet")
    ap.add_argument("--saida", type=Path, default=ROOT / "data" / "parquet" / "2026" / "t2"
                    / "emissao_tardia")
    ap.add_argument("--brutos", type=Path, default=Path.home() / "dataurnas-t2" / "emissao_tardia")
    ap.add_argument("--taxa", type=float, default=2.5, help="req/s, no máximo 3")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if args.taxa > 3:
        ap.error("--taxa acima de 3 req/s")
    if args.etapa == "selecionar":
        selecionar(args.encerramento, args.saida)
    elif args.etapa == "baixar":
        asyncio.run(baixar(args.saida, args.brutos.expanduser(), args.taxa))
    else:
        analisar(args.saida, args.brutos.expanduser())


if __name__ == "__main__":
    main()
