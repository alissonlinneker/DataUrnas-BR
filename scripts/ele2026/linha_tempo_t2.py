#!/usr/bin/env python3
"""Linha do tempo das seções e consistência dos totais no 2º turno de 2026.

Contexto: em 25/10/2026 a votação foi prorrogada até as 19h onde ainda não
tinha sido encerrada às 17h, e o TSE pausou a totalização entre cerca de 17h06
(ou 17h20, conforme a fonte) e 19h (docs/prorrogacao-votacao-2turno-2026.md).
Este script reúne, com os arquivos públicos já versionados por versionar_t2.py,
checagens objetivas sobre esse intervalo. É descritivo: aponta ocorrências e
diferenças, não atribui causa.

Entradas (só leitura, uma ou mais cópias com a mesma estrutura):
  --parts DIR    versoes-*.parquet (aux.json e BU de cada versão vista)
  --totais DIR   indice.jsonl e <abr>/*.json.gz (totais agregados versionados)

Saída em data/parquet/2026/t2/linha_tempo/ (ignorada pelo git):
  secoes.parquet            uma linha por seção: emissão, recebimento, coleta, marcas
  bus_versoes.parquet       todas as versões de BU das seções com mais de uma
  totais_versoes.parquet    cada versão dos totais: regressões, soma interna, BU x total
  comparacao_uf.parquet     soma dos BUs x última versão oficial, por UF
  comparacao_municipio.parquet  idem, por município
  faixas_uf.parquet         seções e votos por faixa de recebimento (antes, pausa, depois)
  oficial_municipios/       JSON de resultado municipal baixados quando faltaram
  cache_bu.parquet          campos decodificados por SHA-512 do BU (acelera reexecuções)
  resumo.json               contagens e listas das ocorrências

Horários:
  - Emissão do BU: gravada no horário LOCAL da urna; convertida para Brasília
    pelo fuso do município (mesma tabela de analisar_encerramento_t2.py).
  - Recebimento (dr/hr do aux.json): tratado como horário de Brasília. A
    hipótese é testada a cada execução (resumo.json, "verificacao_fuso_recebimento"):
    se hr fosse horário local, nas UFs a oeste os recebimentos apareceriam
    1 ou 2 horas ANTES da emissão convertida para Brasília.
    Em 25/10/2026 a leitura como Brasília deu atraso mínimo de 2 a 4 minutos
    nos três fusos (UTC-5, -4 e -3); a leitura como horário local daria atraso
    mínimo de 2 h no Acre e de 1 h nas UFs em UTC-4. Em quase todas as seções
    dr/hr coincide com dg/hg do próprio aux.json (geração do arquivo), então o
    campo marca o registro do pacote no sistema de divulgação, que pode não ser
    o instante exato da chegada ao TSE.
  - Totais (JSON de resultado): dg/hg (geração do arquivo) em Brasília; dt/ht
    (momento da totalização) no horário LOCAL da abrangência (no Acre ht vem
    2 h antes de hg). ht é convertido para Brasília pelo fuso da UF ou do
    município; no exterior fica sem conversão.
  - coletado_em: relógio do coletor, em Brasília (-0300). A coleta começou às
    19h34, então "primeira vez visto" nunca é anterior a isso.

Uso:
  python3 scripts/ele2026/linha_tempo_t2.py
  python3 scripts/ele2026/linha_tempo_t2.py --parts D1 --parts D2 --totais T1 --totais T2
  python3 scripts/ele2026/linha_tempo_t2.py --pausa-inicio 17:20 --sem-download
"""

from __future__ import annotations

import argparse
import gzip
import importlib.util
import json
import logging
import sys
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Optional

ROOT = Path(__file__).resolve().parents[2]
SRC = str(ROOT / "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import pyarrow as pa  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402


def _carregar_encerramento():
    """Reaproveita fusos e conversões de analisar_encerramento_t2.py."""
    p = Path(__file__).resolve().parent / "analisar_encerramento_t2.py"
    spec = importlib.util.spec_from_file_location("analisar_encerramento_t2", p)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


ENC = _carregar_encerramento()
fuso_utc = ENC.fuso_utc
para_brasilia = ENC.para_brasilia
parse_hora_urna = ENC.parse_hora_urna

log = logging.getLogger("linha_tempo_t2")

ELEICAO = 6258
CARGO = 1
DIA = "2026-10-25"
VERSOES = ROOT / "data" / "versoes" / "2026"
PARTS_PADRAO = [VERSOES / "t2" / "bus" / "parts", VERSOES / "t2-sseco" / "bus" / "parts"]
TOTAIS_PADRAO = [VERSOES / "t2" / "totais"]
SAIDA_PADRAO = ROOT / "data" / "parquet" / "2026" / "t2" / "linha_tempo"
URL_RESULTADO = ("https://resultados.tse.jus.br/oficial/ele2026/6258/dados/{uf}/"
                 "{abr}-c0001-e006258-u.json")

PAUSA_INICIO = "17:06"
PAUSA_FIM = "19:00"
JANELAS_ALTERNATIVAS = ("17:20-19:00", "17:00-19:00")
LIMITE_ATRASO_MIN = 120
LIMITE_APOS_TOT_S = 900
CAMPOS_VOTOS = ("comparecimento", "votos_13", "votos_22", "brancos", "nulos")
CAMPOS_OFICIAL = ("secoes",) + CAMPOS_VOTOS


# ---------------------------------------------------------------------------
# Horários
# ---------------------------------------------------------------------------

def parse_dr_hr(dr: Optional[str], hr: Optional[str]) -> Optional[datetime]:
    """'25/10/2026' + '19:32:29' para datetime ingênuo (Brasília)."""
    if not dr or not hr:
        return None
    try:
        return datetime.strptime(f"{dr} {hr}", "%d/%m/%Y %H:%M:%S")
    except ValueError:
        return None


def parse_coletado(valor: Optional[str]) -> Optional[datetime]:
    """'2026-10-25T19:39:52-0300' para datetime ingênuo em Brasília."""
    if not valor:
        return None
    try:
        dt = datetime.strptime(valor, "%Y-%m-%dT%H:%M:%S%z")
    except ValueError:
        return None
    off = dt.utcoffset() or timedelta(0)
    return (dt - off + timedelta(hours=-3)).replace(tzinfo=None)


def hora_no_dia(hhmm: str, dia: str = DIA) -> datetime:
    """'17:06' ou '17:06:30' no dia da eleição."""
    partes = [int(x) for x in hhmm.split(":")]
    while len(partes) < 3:
        partes.append(0)
    base = datetime.strptime(dia, "%Y-%m-%d")
    return base.replace(hour=partes[0], minute=partes[1], second=partes[2])


def parse_janela(texto: str, dia: str = DIA) -> tuple[datetime, datetime]:
    """'17:20-19:00' para (início, fim)."""
    ini, fim = texto.split("-")
    return hora_no_dia(ini.strip(), dia), hora_no_dia(fim.strip(), dia)


def faixa_recebimento(rec: Optional[datetime], ini: datetime, fim: datetime) -> str:
    """antes_pausa (rec < ini), pausa (ini <= rec <= fim), depois_pausa (rec > fim)."""
    if rec is None:
        return "sem_recebimento"
    if rec < ini:
        return "antes_pausa"
    if rec <= fim:
        return "pausa"
    return "depois_pausa"


def minutos(a: Optional[datetime], b: Optional[datetime]) -> Optional[float]:
    """b - a em minutos."""
    if a is None or b is None:
        return None
    return round((b - a).total_seconds() / 60.0, 2)


def fmt(dt: Optional[datetime]) -> Optional[str]:
    return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else None


# ---------------------------------------------------------------------------
# Leitura dos parts
# ---------------------------------------------------------------------------

COLUNAS = ["coletado_em", "uf", "cd_mun", "zona", "secao", "tipo", "hash",
           "st_secao", "st_hash", "dt_recebimento", "hr_recebimento", "nome",
           "sha512", "conteudo"]


def _decodificar(raw: bytes) -> dict:
    """Campos do BU usados aqui. Erro de decodificação vira campo 'erro'."""
    from dataurnas.downloader.ele2026 import bu_to_rows
    try:
        c, votos = bu_to_rows(raw, ELEICAO, CARGO)
    except Exception as e:  # BU ilegível não some, vira linha com erro
        return {"erro": f"{type(e).__name__}: {e}"}
    por_num: dict[int, int] = defaultdict(int)
    for v in votos:
        if v["tipo_voto"] == "nominal" and v["numero"] is not None:
            por_num[int(v["numero"])] += v["votos"] or 0
    return {
        "erro": None,
        "emissao_local": c.get("data_hora_emissao"),
        "encerramento_local": c.get("hora_encerramento"),
        "aptos": c.get("aptos"), "comparecimento": c.get("comparecimento"),
        "votos_13": por_num.get(13, 0), "votos_22": por_num.get(22, 0),
        "votos_outros": sum(q for n, q in por_num.items() if n not in (13, 22)),
        "brancos": c.get("votos_brancos"), "nulos": c.get("votos_nulos"),
        "tem_presidente": bool(c.get("tem_presidente")),
    }


CACHE_SCHEMA = pa.schema([
    ("sha512", pa.string()), ("erro", pa.string()), ("emissao_local", pa.string()),
    ("encerramento_local", pa.string()), ("aptos", pa.int64()),
    ("comparecimento", pa.int64()), ("votos_13", pa.int64()), ("votos_22", pa.int64()),
    ("votos_outros", pa.int64()), ("brancos", pa.int64()), ("nulos", pa.int64()),
    ("tem_presidente", pa.bool_()),
])


def ler_cache(caminho: Path) -> dict[str, dict]:
    if not caminho.exists():
        return {}
    try:
        return {r.pop("sha512"): r for r in pq.read_table(caminho).to_pylist()}
    except Exception as e:
        log.warning("cache ignorado (%s)", e)
        return {}


def gravar_cache(cache: dict[str, dict], caminho: Path) -> None:
    linhas = [{"sha512": k, **v} for k, v in cache.items() if not v.get("erro")]
    tmp = caminho.with_suffix(".tmp")
    pq.write_table(pa.Table.from_pylist(linhas, schema=CACHE_SCHEMA), tmp,
                   compression="zstd")
    tmp.replace(caminho)


def iter_registros(dirs: Iterable[Path]) -> Iterable[tuple[str, list[dict]]]:
    """(origem, registros aux/bu/busa) de cada part, com conteudo em bytes."""
    for d in dirs:
        arquivos = sorted(Path(d).glob("versoes-*.parquet"))
        log.info("%s: %d arquivos", d, len(arquivos))
        for f in arquivos:
            try:
                nomes = set(pq.read_schema(f).names)
                cols = [c for c in COLUNAS if c in nomes]
                t = pq.read_table(f, columns=cols,
                                  filters=[("tipo", "in", ["aux", "bu", "busa"])])
            except Exception as e:  # part em gravação ou corrompido
                log.warning("ignorado %s: %s", f.name, e)
                continue
            yield f"{Path(d).name}/{f.name}", t.to_pylist()


class Secao:
    """Tudo o que foi visto de uma seção, em todas as cópias."""

    __slots__ = ("aux", "bus")

    def __init__(self) -> None:
        self.aux: dict[str, dict] = {}   # sha512 do aux.json -> {coletado, json}
        self.bus: dict[str, dict] = {}   # sha512 do BU -> registro + decodificado

    def add_aux(self, sha: str, coletado: Optional[str], doc: dict) -> None:
        atual = self.aux.get(sha)
        if atual is None or (coletado or "") < (atual["coletado_em"] or ""):
            self.aux[sha] = {"coletado_em": coletado, "doc": doc}

    def add_bu(self, sha: str, reg: dict) -> None:
        atual = self.bus.get(sha)
        if atual is None or (reg.get("coletado_em") or "") < (atual.get("coletado_em") or ""):
            self.bus[sha] = reg


def carregar_secoes(dirs: list[Path], cache: dict[str, dict], workers: int
                    ) -> tuple[dict[tuple, Secao], dict]:
    secoes: dict[tuple, Secao] = defaultdict(Secao)
    cont = Counter()
    pool = ProcessPoolExecutor(workers) if workers > 1 else None
    try:
        for origem, regs in iter_registros(dirs):
            pend_raw, pend_sha = [], []
            for r in regs:
                k = (r["uf"], str(r["cd_mun"]).zfill(5), r["zona"], r["secao"])
                raw = r.pop("conteudo", None)
                if r["tipo"] == "aux":
                    cont["aux"] += 1
                    try:
                        doc = json.loads(raw) if raw else {}
                    except ValueError:
                        cont["aux_ilegivel"] += 1
                        doc = {}
                    secoes[k].add_aux(r.get("sha512") or "", r.get("coletado_em"), doc)
                    continue
                cont["bu"] += 1
                sha = r.get("sha512") or ""
                r["origem_part"] = origem
                secoes[k].add_bu(sha, r)
                if sha not in cache and raw is not None and sha not in pend_sha:
                    pend_raw.append(raw)
                    pend_sha.append(sha)
            if pend_raw:
                if pool:
                    dec = list(pool.map(_decodificar, pend_raw, chunksize=128))
                else:
                    dec = [_decodificar(x) for x in pend_raw]
                for sha, d in zip(pend_sha, dec, strict=True):
                    cache[sha] = d
                cont["bu_decodificados"] += len(pend_raw)
    finally:
        if pool:
            pool.shutdown()
    return secoes, dict(cont)


# ---------------------------------------------------------------------------
# Linha por seção
# ---------------------------------------------------------------------------

def pacotes_aux(sec: Secao) -> list[dict]:
    """Pacotes (hashes) distintos listados em qualquer versão do aux.json."""
    vistos: dict[str, dict] = {}
    for a in sorted(sec.aux.values(), key=lambda x: x["coletado_em"] or ""):
        for h in a["doc"].get("hashes") or []:
            hv = h.get("hash")
            if not hv or hv == "0" or hv in vistos:
                continue
            vistos[hv] = {"hash": hv, "st": h.get("st"),
                          "recebimento": parse_dr_hr(h.get("dr"), h.get("hr")),
                          "primeira_coleta": a["coletado_em"],
                          "arqs": ",".join(sorted(x.get("tp", "") for x in h.get("arq") or []
                                                  if isinstance(x, dict)))}
    return list(vistos.values())


def montar_secao(chave: tuple, sec: Secao, cache: dict[str, dict],
                 ini: datetime, fim: datetime) -> tuple[dict, list[dict]]:
    """Linha da seção e, quando há mais de uma, a lista das versões de BU."""
    uf, cd, zona, secao = chave
    utc = fuso_utc(uf, cd)
    auxs = sorted(sec.aux.values(), key=lambda x: x["coletado_em"] or "")
    ult_aux = auxs[-1]["doc"] if auxs else {}
    pacotes = pacotes_aux(sec)
    recs = [p["recebimento"] for p in pacotes if p["recebimento"]]

    versoes = sorted(sec.bus.items(), key=lambda kv: kv[1].get("coletado_em") or "")
    linha: dict = {
        "uf": uf, "cd_mun": cd, "zona": zona, "secao": secao, "fuso_utc": utc,
        "n_versoes_aux": len(auxs),
        "st_secao": ult_aux.get("st"),
        "aux_gerado": fmt(parse_dr_hr(ult_aux.get("dg"), ult_aux.get("hg"))),
        "primeira_coleta_aux": fmt(parse_coletado(auxs[0]["coletado_em"])) if auxs else None,
        "n_pacotes": len(pacotes),
        "n_pacotes_ultimo_aux": len([h for h in ult_aux.get("hashes") or []
                                     if h.get("hash") not in (None, "", "0")]),
        "status_pacotes": ",".join(sorted({p["st"] or "" for p in pacotes})) or None,
        "recebimento_primeiro": fmt(min(recs)) if recs else None,
        "recebimento_ultimo": fmt(max(recs)) if recs else None,
        "n_versoes_bu": len(versoes),
        "n_hashes_bu": len({v.get("hash") for _, v in versoes}),
    }
    multiplas: list[dict] = []
    rec_bu = em_bsb = None
    if versoes:
        sha, reg = versoes[-1]
        d = cache.get(sha) or {"erro": "sem_conteudo"}
        em_local = parse_hora_urna(d.get("emissao_local"))
        em_bsb = para_brasilia(em_local, utc)
        rec_bu = parse_dr_hr(reg.get("dt_recebimento"), reg.get("hr_recebimento"))
        if rec_bu is None:  # BU sem dr/hr próprio: usa o pacote do mesmo hash
            for p in pacotes:
                if p["hash"] == reg.get("hash"):
                    rec_bu = p["recebimento"]
        linha.update({
            "tipo_arquivo": reg.get("tipo"), "nome_bu": reg.get("nome"),
            "hash_bu": reg.get("hash"), "sha512_bu": sha,
            "origem_part": reg.get("origem_part"),
            "primeira_coleta_bu": fmt(min(filter(None, (parse_coletado(v.get("coletado_em"))
                                                        for _, v in versoes)), default=None)),
            "emissao_local": fmt(em_local), "emissao_bsb": fmt(em_bsb),
            "encerramento_bsb": fmt(para_brasilia(parse_hora_urna(d.get("encerramento_local")),
                                                  utc)),
            "recebimento_bu": fmt(rec_bu),
            "erro_decodificacao": d.get("erro"),
            **{k: d.get(k) for k in ("aptos", "comparecimento", "votos_13", "votos_22",
                                     "votos_outros", "brancos", "nulos")},
        })
        conteudo = set()
        hashes_sha: dict[str, set] = defaultdict(set)
        for i, (s, r) in enumerate(versoes, 1):
            dv = cache.get(s) or {}
            conteudo.add(tuple(dv.get(k) for k in ("comparecimento", "votos_13", "votos_22",
                                                    "votos_outros", "brancos", "nulos")))
            hashes_sha[r.get("hash")].add(s)
            if len(versoes) > 1:
                multiplas.append({"uf": uf, "cd_mun": cd, "zona": zona, "secao": secao,
                                  "versao": i, "sha512": s, "hash": r.get("hash"),
                                  "tipo": r.get("tipo"), "st_hash": r.get("st_hash"),
                                  "coletado_em": r.get("coletado_em"),
                                  "recebimento": fmt(parse_dr_hr(r.get("dt_recebimento"),
                                                                 r.get("hr_recebimento"))),
                                  "origem_part": r.get("origem_part"),
                                  **{k: dv.get(k) for k in CAMPOS_VOTOS},
                                  "votos_outros": dv.get("votos_outros"),
                                  "emissao_local": dv.get("emissao_local")})
        linha["votos_diferem_entre_versoes"] = len(conteudo) > 1
        linha["mesmo_hash_conteudo_diferente"] = any(len(v) > 1 for v in hashes_sha.values())
    else:
        linha["votos_diferem_entre_versoes"] = False
        linha["mesmo_hash_conteudo_diferente"] = False

    atraso = minutos(em_bsb, rec_bu)
    linha["atraso_recebimento_min"] = atraso
    linha["faixa_recebimento"] = faixa_recebimento(rec_bu, ini, fim)
    linha.update(marcas(rec_bu, em_bsb, pacotes, len(versoes), ini, fim))
    return linha, multiplas


def marcas(rec_bu: Optional[datetime], em_bsb: Optional[datetime], pacotes: list[dict],
           n_versoes_bu: int, ini: datetime, fim: datetime) -> dict:
    """Marcas booleanas da seção."""
    atraso = minutos(em_bsb, rec_bu)
    return {
        "m_recebido_na_pausa": rec_bu is not None and ini <= rec_bu <= fim,
        "m_algum_pacote_na_pausa": any(p["recebimento"] and ini <= p["recebimento"] <= fim
                                       for p in pacotes),
        "m_recebido_mais_2h": atraso is not None and atraso > LIMITE_ATRASO_MIN,
        "m_mais_de_um_pacote": len(pacotes) > 1,
        "m_bu_mais_de_uma_versao": n_versoes_bu > 1,
        "m_recebimento_antes_emissao": atraso is not None and atraso < 0,
    }


MARCAS = ("m_recebido_na_pausa", "m_algum_pacote_na_pausa", "m_recebido_mais_2h",
          "m_mais_de_um_pacote", "m_bu_mais_de_uma_versao", "m_recebimento_antes_emissao",
          "votos_diferem_entre_versoes", "mesmo_hash_conteudo_diferente",
          "m_recebimento_apos_totalizacao", "m_recebimento_apos_totalizacao_15min")


def verificar_fuso_recebimento(linhas: list[dict], ini: datetime, fim: datetime) -> dict:
    """Testa se hr do aux.json está em Brasília: compara, por fuso, o atraso entre
    emissão (convertida para Brasília) e recebimento sob as duas leituras."""
    grupos: dict[int, list[tuple[datetime, datetime]]] = defaultdict(list)
    for ln in linhas:
        if ln.get("fuso_utc") is None or not ln.get("emissao_bsb") or not ln.get("recebimento_bu"):
            continue
        grupos[ln["fuso_utc"]].append((
            datetime.strptime(ln["emissao_bsb"], "%Y-%m-%d %H:%M:%S"),
            datetime.strptime(ln["recebimento_bu"], "%Y-%m-%d %H:%M:%S")))
    out = {}
    for utc, pares in sorted(grupos.items()):
        desloc = timedelta(hours=-3 - utc)  # se hr fosse local: hr + desloc = Brasília
        lido_bsb = sorted(minutos(e, r) for e, r in pares)
        lido_local = sorted(minutos(e, r + desloc) for e, r in pares)
        antes = [m for (e, r), m in zip(pares, (minutos(e, r) for e, r in pares), strict=True)
                 if r < ini]

        def q(xs, p):
            return xs[min(len(xs) - 1, int(p * len(xs)))] if xs else None
        out[str(utc)] = {
            "secoes": len(pares),
            "hr_como_brasilia": {"negativos": sum(1 for m in lido_bsb if m < 0),
                                 "min": q(lido_bsb, 0), "p01": q(lido_bsb, 0.01),
                                 "mediana": q(lido_bsb, 0.5)},
            "hr_como_local": {"negativos": sum(1 for m in lido_local if m < 0),
                              "min": q(lido_local, 0), "p01": q(lido_local, 0.01),
                              "mediana": q(lido_local, 0.5)},
            "recebidos_antes_da_pausa": len(antes),
            "atraso_mediano_antes_da_pausa_min": q(sorted(antes), 0.5),
            "recebidos_na_pausa": sum(1 for _, r in pares if ini <= r <= fim),
        }
    return out


# ---------------------------------------------------------------------------
# Totais versionados
# ---------------------------------------------------------------------------

def carregar_indice(dirs: list[Path]) -> list[dict]:
    """Versões dos totais de todas as cópias, sem repetição (abr + sha256).
    Completa cada versão com dt/ht e comparecimento do JSON bruto, quando há."""
    por_chave: dict[tuple, dict] = {}
    for d in dirs:
        p = Path(d) / "indice.jsonl"
        if not p.exists():
            log.warning("sem índice em %s", d)
            continue
        for ln in p.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            k = (r.get("abr"), r.get("sha256"))
            atual = por_chave.get(k)
            if atual is None or (r.get("coletado_em") or "") < (atual.get("coletado_em") or ""):
                r["_dir"] = str(d)
                por_chave[k] = r
    out = []
    for r in por_chave.values():
        nome = f"{(r.get('dg') or '').replace('/', '')}_{(r.get('hg') or '').replace(':', '')}_{r.get('idg')}"
        bruto = Path(r["_dir"]) / r["abr"] / f"{nome}.json.gz"
        r.update(extrair_bruto(bruto))
        out.append(r)
    return out


def extrair_bruto(caminho: Path) -> dict:
    """dt/ht e comparecimento (e.c) de um JSON de resultado gzip."""
    try:
        d = json.loads(gzip.decompress(caminho.read_bytes()))
    except Exception:
        return {"bruto": False}
    e = d.get("e") or {}
    return {"bruto": True, "dt": d.get("dt"), "ht": d.get("ht"), "c": _int(e.get("c"))}


def _int(v) -> Optional[int]:
    if v is None or v == "":
        return None
    try:
        return int(str(v).replace(".", ""))
    except ValueError:
        return None


def chave_ordem(r: dict) -> tuple:
    """Ordena versões da mesma abrangência pela geração do arquivo no TSE."""
    g = parse_dr_hr(r.get("dg"), r.get("hg")) or datetime.min
    return (g, _int(r.get("idg")) or 0, r.get("coletado_em") or "")


def resumo_oficial(r: dict) -> dict:
    """Valores comparáveis com a soma dos BUs."""
    cand = r.get("cand") or {}
    return {"secoes": r.get("st"), "secoes_total": r.get("ts"),
            "comparecimento": r.get("c") if r.get("c") is not None else r.get("tv"),
            "votos_13": cand.get("13"), "votos_22": cand.get("22"),
            "brancos": r.get("vb"), "nulos": r.get("tvn"), "tv": r.get("tv")}


def regressoes(ant: dict, novo: dict) -> list[str]:
    """Quedas entre duas versões consecutivas (deveriam só subir) e ts mudando."""
    out = []
    for k in ("st", "tv", "vb", "tvn", "c"):
        a, b = ant.get(k), novo.get(k)
        if a is not None and b is not None and b < a:
            out.append(f"{k}: {a} -> {b}")
    for n, q in (ant.get("cand") or {}).items():
        q2 = (novo.get("cand") or {}).get(n)
        if q2 is not None and q2 < q:
            out.append(f"candidato {n}: {q} -> {q2}")
    if ant.get("ts") is not None and novo.get("ts") is not None and ant["ts"] != novo["ts"]:
        out.append(f"ts: {ant['ts']} -> {novo['ts']}")
    return out


def soma_interna(r: dict) -> Optional[int]:
    """tv - (nominais + brancos + nulos). Zero quando o total fecha."""
    cand = r.get("cand") or {}
    if r.get("tv") is None or r.get("vb") is None or r.get("tvn") is None:
        return None
    return r["tv"] - (sum(cand.values()) + r["vb"] + r["tvn"])


def fuso_abr(abr: str) -> Optional[int]:
    """Fuso (offset UTC) da abrangência: br e UF pela capital/UF, município pela
    tabela de municípios. None para o exterior (cada país tem o seu)."""
    abr = abr.lower()
    if abr == "br":
        return -3
    if len(abr) == 2:
        return fuso_utc(abr, "")
    return fuso_utc(abr[:2], abr[2:])


def ht_brasilia(r: dict) -> Optional[datetime]:
    """dt/ht do JSON de resultado convertidos para Brasília. O TSE grava dt/ht
    (momento da totalização) no horário LOCAL da abrangência; dg/hg (geração do
    arquivo) em Brasília. Exterior: None."""
    t = parse_dr_hr(r.get("dt"), r.get("ht"))
    return para_brasilia(t, fuso_abr(r.get("abr") or ""))


def checar_versoes(indice: list[dict], ini: Optional[datetime] = None,
                   fim: Optional[datetime] = None) -> tuple[list[dict], dict[str, dict]]:
    """Ordena por abrangência, marca regressões e soma interna. Devolve as linhas
    e a última versão de cada abrangência."""
    por_abr: dict[str, list[dict]] = defaultdict(list)
    for r in indice:
        por_abr[r["abr"]].append(r)
    linhas, ultima = [], {}
    for abr, vs in por_abr.items():
        vs.sort(key=chave_ordem)
        ant = None
        for i, r in enumerate(vs, 1):
            q = regressoes(ant, r) if ant else []
            of = resumo_oficial(r)
            hg = parse_dr_hr(r.get("dg"), r.get("hg"))
            htb = ht_brasilia(r)
            linhas.append({
                "abr": abr, "versao": i, "coletado_em": r.get("coletado_em"),
                "dg": r.get("dg"), "hg": r.get("hg"), "idg": r.get("idg"),
                "dt": r.get("dt"), "ht": r.get("ht"), "ht_bsb": fmt(htb),
                "sha256": r.get("sha256"),
                "hg_na_pausa": bool(ini and hg and ini <= hg <= fim),
                "ht_na_pausa": bool(ini and htb and ini <= htb <= fim),
                **{k: of[k] for k in ("secoes", "secoes_total", "comparecimento",
                                      "votos_13", "votos_22", "brancos", "nulos", "tv")},
                "regressoes": "; ".join(q) or None,
                "diferenca_soma_interna": soma_interna(r),
            })
            ant = r
        ultima[abr] = vs[-1]
    return linhas, ultima


# ---------------------------------------------------------------------------
# BU x oficial
# ---------------------------------------------------------------------------

def somar(linhas: Iterable[dict]) -> dict:
    s = {"secoes": 0, **{k: 0 for k in CAMPOS_VOTOS}}
    for ln in linhas:
        s["secoes"] += 1
        for k in CAMPOS_VOTOS:
            s[k] += int(ln.get(k) or 0)
    return s


def classificar(n_bu: int, st: Optional[int], ts: Optional[int]) -> str:
    """Situação da cobertura de uma abrangência.
    completo: BUs de todas as seções e oficial 100% totalizado (comparação exata);
    contagem_igual: BUs = seções totalizadas, mas o oficial ainda não está em 100%;
    bus_parciais: há menos BUs que seções totalizadas;
    oficial_defasado: há mais BUs que seções totalizadas na última versão vista."""
    if st is None:
        return "sem_oficial"
    if n_bu == st:
        return "completo" if st == ts else "contagem_igual"
    return "bus_parciais" if n_bu < st else "oficial_defasado"


def comparar(abr: str, linhas: list[dict], oficial: Optional[dict]) -> dict:
    """Soma dos BUs da abrangência x versão oficial. Diferenças só são calculadas
    quando a contagem de seções coincide."""
    s = somar(linhas)
    of = resumo_oficial(oficial) if oficial else {}
    situacao = classificar(s["secoes"], of.get("secoes"), of.get("secoes_total"))
    out = {"abr": abr, "situacao": situacao,
           "oficial_hg": oficial.get("hg") if oficial else None,
           "oficial_dg": oficial.get("dg") if oficial else None,
           "oficial_idg": oficial.get("idg") if oficial else None,
           "secoes_total_oficial": of.get("secoes_total"),
           "cobertura": round(s["secoes"] / of["secoes"], 6) if of.get("secoes") else None}
    for k in CAMPOS_OFICIAL:
        out[f"bu_{k}"] = s[k]
        out[f"oficial_{k}"] = of.get(k)
    comparavel = situacao in ("completo", "contagem_igual")
    difs = {}
    for k in CAMPOS_OFICIAL:
        dif = (s[k] - of[k]) if comparavel and of.get(k) is not None else None
        out[f"dif_{k}"] = dif
        if dif:
            difs[k] = dif
    out["comparado"] = comparavel
    out["tem_diferenca"] = bool(difs)
    out["diferencas"] = json.dumps(difs) if difs else None
    return out


def comparar_versoes_com_bus(versoes: list[dict], por_abr: dict[str, list[dict]],
                             n_total: dict[str, int]) -> None:
    """Para cada versão dos totais de uma abrangência com BUs de todas as seções:

    - bu_comparacao: soma os BUs com recebimento (dr/hr) até a totalização
      (dt/ht em Brasília) e compara quando a contagem bate com as seções
      totalizadas (st); senão diz em que sentido a contagem difere;
    - bu_comparacao_ordem: soma os st primeiros BUs pela ordem de recebimento
      e compara com a versão (testa se o total intermediário é a soma das
      primeiras seções recebidas, sem depender do relógio);
    - folga_s: segundos entre ht e o recebimento do st-ésimo BU (positivo quando
      o st-ésimo BU tem dr/hr posterior à totalização).

    Altera as linhas em lugar."""
    ordenados: dict[str, list[tuple[datetime, dict]]] = {}
    for abr, ls in por_abr.items():
        ordenados[abr] = sorted(((datetime.strptime(ln["recebimento_bu"], "%Y-%m-%d %H:%M:%S"), ln)
                                 for ln in ls if ln.get("recebimento_bu")),
                                key=lambda x: x[0])
    for v in versoes:
        abr = v["abr"]
        v.update({"bu_ate_ht_secoes": None, "bu_comparacao": "sem_cobertura",
                  "bu_diferencas": None, "bu_comparacao_ordem": None,
                  "bu_diferencas_ordem": None, "folga_s": None})
        ls = por_abr.get(abr)
        if not ls or v.get("secoes_total") is None or len(ls) != v["secoes_total"] \
                or len(ls) != n_total.get(abr, -1):
            continue
        st = v.get("secoes") or 0
        if st == 0:
            v["bu_comparacao"] = "sem_secoes_totalizadas"
            continue
        lst = ordenados[abr]
        if st <= len(lst):
            s = somar(ln for _, ln in lst[:st])
            difs = {k: s[k] - v[k] for k in CAMPOS_VOTOS if v.get(k) is not None and s[k] != v[k]}
            v["bu_comparacao_ordem"] = "difere" if difs else "igual"
            v["bu_diferencas_ordem"] = json.dumps(difs) if difs else None
        ht = datetime.strptime(v["ht_bsb"], "%Y-%m-%d %H:%M:%S") if v.get("ht_bsb") else None
        if ht is None:
            v["bu_comparacao"] = "sem_ht"
            continue
        if st <= len(lst):
            v["folga_s"] = int((lst[st - 1][0] - ht).total_seconds())
        sel = [ln for t, ln in lst if t <= ht]
        v["bu_ate_ht_secoes"] = len(sel)
        if len(sel) < st:
            v["bu_comparacao"] = "totalizadas_mais_que_recebidas"
            continue
        if len(sel) > st:
            v["bu_comparacao"] = "recebidas_mais_que_totalizadas"
            continue
        s = somar(sel)
        difs = {k: s[k] - v[k] for k in CAMPOS_VOTOS if v.get(k) is not None and s[k] != v[k]}
        v["bu_comparacao"] = "difere" if difs else "igual"
        v["bu_diferencas"] = json.dumps(difs) if difs else None


def marcar_recebimento_apos_totalizacao(versoes: list[dict],
                                        por_mun: dict[str, list[dict]]) -> None:
    """Nos municípios com BU de todas as seções, toma a primeira versão vista com
    100% das seções totalizadas e marca as seções cujo recebimento (dr/hr) é
    posterior ao ht dessa versão. Altera as linhas das seções em lugar."""
    completa: dict[str, str] = {}
    total: dict[str, int] = {}
    for v in versoes:
        if len(v["abr"]) > 2 and v.get("secoes_total") is not None:
            total[v["abr"]] = v["secoes_total"]
        if len(v["abr"]) <= 2 or not v.get("ht_bsb") or not v.get("secoes"):
            continue
        if v["secoes"] != v.get("secoes_total"):
            continue
        if v["abr"] not in completa or v["ht_bsb"] < completa[v["abr"]]:
            completa[v["abr"]] = v["ht_bsb"]
    for abr, ls in por_mun.items():
        ht = completa.get(abr)
        if ht is None or len(ls) != total.get(abr, -1):
            continue
        t_ht = datetime.strptime(ht, "%Y-%m-%d %H:%M:%S")
        for ln in ls:
            ln["ht_totalizacao_completa_mun"] = ht
            rec = ln.get("recebimento_bu")
            d = (int((datetime.strptime(rec, "%Y-%m-%d %H:%M:%S") - t_ht).total_seconds())
                 if rec else None)
            ln["recebimento_menos_totalizacao_s"] = d
            ln["m_recebimento_apos_totalizacao"] = d is not None and d > 0
            ln["m_recebimento_apos_totalizacao_15min"] = d is not None and d > LIMITE_APOS_TOT_S


def curva_recebimento_totalizacao(versoes: list[dict], por_abr: dict[str, list[dict]],
                                  ultima: dict[str, dict]) -> tuple[list[dict], list[dict]]:
    """Curva acumulada por abrangência: seções com recebimento (dr/hr do aux.json)
    <= t contra seções totalizadas (st) na versão gerada em t (hg, Brasília) e
    na totalização dessa versão (ht convertido para Brasília).

    Só entra abrangência em que o número de seções com BU é >= st da última
    versão vista (cobertura suficiente): supondo que toda seção totalizada tem
    BU publicado, as seções recebidas contadas aqui incluem todas as
    totalizadas. Excesso > 0 quer dizer que o TSE já tinha totalizado mais
    seções do que o aux.json mostra como recebidas até t.

    Devolve (linhas da curva, seções do excesso). As seções do excesso são as k
    de recebimento mais cedo depois de t (k = excesso em hg): o menor conjunto
    que explicaria a contagem, não necessariamente as seções totalizadas."""
    curva, excesso = [], []
    for abr, ls in por_abr.items():
        of = ultima.get(abr)
        if not of or of.get("st") is None or len(ls) < of["st"]:
            continue
        recs = sorted((datetime.strptime(ln["recebimento_bu"], "%Y-%m-%d %H:%M:%S"), ln)
                      for ln in ls if ln.get("recebimento_bu"))
        tempos = [t for t, _ in recs]
        for v in versoes:
            if v["abr"] != abr or not v.get("secoes"):
                continue
            hg = parse_dr_hr(v.get("dg"), v.get("hg"))
            ht = datetime.strptime(v["ht_bsb"], "%Y-%m-%d %H:%M:%S") if v.get("ht_bsb") else None
            n_hg = _contar_ate(tempos, hg)
            n_ht = _contar_ate(tempos, ht) if ht else None
            exc = v["secoes"] - n_hg if n_hg is not None else None
            curva.append({"abr": abr, "versao": v["versao"], "hg_bsb": fmt(hg),
                          "ht_bsb": v.get("ht_bsb"), "secoes_totalizadas": v["secoes"],
                          "secoes_total": v.get("secoes_total"), "bu_secoes": len(ls),
                          "recebidas_ate_hg": n_hg, "recebidas_ate_ht": n_ht,
                          "excesso_hg": exc,
                          "excesso_ht": v["secoes"] - n_ht if n_ht is not None else None})
            if exc and exc > 0:
                for t, ln in recs[n_hg:n_hg + exc]:
                    excesso.append({"abr": abr, "versao": v["versao"], "hg_bsb": fmt(hg),
                                    "secoes_totalizadas": v["secoes"],
                                    "recebidas_ate_hg": n_hg, "excesso_hg": exc,
                                    "uf": ln["uf"], "cd_mun": ln["cd_mun"], "zona": ln["zona"],
                                    "secao": ln["secao"], "recebimento_bu": ln["recebimento_bu"],
                                    "recebimento_menos_hg_s": int((t - hg).total_seconds()),
                                    "emissao_bsb": ln.get("emissao_bsb"),
                                    "primeira_coleta_aux": ln.get("primeira_coleta_aux")})
    return curva, excesso


def _contar_ate(tempos: list[datetime], t: Optional[datetime]) -> Optional[int]:
    if t is None:
        return None
    import bisect
    return bisect.bisect_right(tempos, t)


def atraso_por_municipio(linhas: list[dict]) -> list[dict]:
    """Distribuição de (recebimento - emissão em Brasília), em minutos, por município."""
    grupos: dict[tuple, list] = defaultdict(list)
    for ln in linhas:
        if ln.get("atraso_recebimento_min") is not None:
            grupos[(ln["uf"], ln["cd_mun"])].append(ln["atraso_recebimento_min"])
    return [{"uf": uf, "cd_mun": cd, **distribuicao(xs)} for (uf, cd), xs in sorted(grupos.items())]


DESTAQUES_BA = {"38490": "Salvador", "36854": "Lauro de Freitas", "35157": "Feira de Santana"}


def destaque_ba(linhas: list[dict]) -> dict:
    """Atraso recebimento - emissão (min) nos municípios destacados contra o resto da BA."""
    grupos: dict[str, list] = defaultdict(list)
    for ln in linhas:
        if ln["uf"] != "ba" or ln.get("atraso_recebimento_min") is None:
            continue
        grupos[DESTAQUES_BA.get(ln["cd_mun"], "resto_da_ba")].append(ln["atraso_recebimento_min"])
    out = {}
    for nome, xs in grupos.items():
        d = distribuicao(xs)
        d["recebidos_depois_de_21h_pct"] = None
        out[nome] = d
    rec21 = defaultdict(lambda: [0, 0])
    for ln in linhas:
        if ln["uf"] == "ba" and ln.get("recebimento_bu"):
            g = DESTAQUES_BA.get(ln["cd_mun"], "resto_da_ba")
            rec21[g][1] += 1
            rec21[g][0] += ln["recebimento_bu"][11:16] >= "21:00"
    for g, (a, b) in rec21.items():
        if g in out:
            out[g]["recebidos_depois_de_21h_pct"] = round(100.0 * a / b, 2) if b else None
    return out


def head_last_modified(linhas: list[dict], destino: Path, n_por_grupo: int, taxa: float,
                       extras: list[dict]) -> dict:
    """HEAD no bu.dat de uma amostra (no máximo 3 req/s), com cache por SHA-512.
    Amostra: n_por_grupo seções de cada município destacado da BA, do resto da BA
    e de cada outra UF com BU, mais as seções do excesso da curva."""
    from email.utils import parsedate_to_datetime

    from dataurnas.downloader import ele2026 as E
    P = E.parametros_turno(2)
    cache = {}
    if destino.exists():
        cache = {r["sha512_bu"]: r for r in pq.read_table(destino).to_pylist()}
    grupos: dict[str, list] = defaultdict(list)
    for ln in linhas:
        if not ln.get("nome_bu") or not ln.get("hash_bu"):
            continue
        g = (DESTAQUES_BA.get(ln["cd_mun"], "resto_da_ba") if ln["uf"] == "ba" else ln["uf"])
        grupos[g].append(ln)
    idx = {(ln["uf"], ln["cd_mun"], ln["zona"], ln["secao"]): ln for ln in linhas}
    amostra = []
    for g, ls in sorted(grupos.items()):
        passo = max(1, len(ls) // max(1, n_por_grupo))
        amostra += [(g, ln) for ln in ls[::passo][:n_por_grupo]]
    for e in extras:
        ln = idx.get((e["uf"], e["cd_mun"], e["zona"], e["secao"]))
        if ln and ln.get("nome_bu"):
            amostra.append(("excesso_curva", ln))
    intervalo = 1.0 / max(0.1, min(taxa, 3.0))
    cont = Counter()
    seguidos_429 = 0
    parado = None
    for g, ln in amostra:
        sha = ln["sha512_bu"]
        if sha in cache:
            cache[sha]["grupo"] = g
            continue
        url = E.url_arquivo(ln["uf"], ln["cd_mun"], ln["zona"], ln["secao"], ln["hash_bu"],
                            ln["nome_bu"], pleito=P["pleito"], ciclo=P["ciclo"])
        time.sleep(intervalo)
        try:
            req = urllib.request.Request(url, method="HEAD",
                                         headers={"User-Agent": "dataurnas-br"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                lm = resp.headers.get("Last-Modified")
            seguidos_429 = 0
        except urllib.error.HTTPError as e:
            cont[f"http_{e.code}"] += 1
            if e.code == 429:
                seguidos_429 += 1
                if seguidos_429 >= 3:
                    parado = "429 repetido; amostra interrompida"
                    break
                time.sleep(30 * seguidos_429)
            continue
        except (urllib.error.URLError, TimeoutError):
            cont["erro_rede"] += 1
            continue
        cont["ok"] += 1
        lm_bsb = None
        if lm:
            try:
                lm_bsb = (parsedate_to_datetime(lm) - timedelta(hours=3)).replace(tzinfo=None)
            except (TypeError, ValueError):
                pass
        rec = ln.get("recebimento_bu")
        cache[sha] = {"sha512_bu": sha, "grupo": g, "uf": ln["uf"], "cd_mun": ln["cd_mun"],
                      "zona": ln["zona"], "secao": ln["secao"], "last_modified": lm,
                      "last_modified_bsb": fmt(lm_bsb), "recebimento_bu": rec,
                      "emissao_bsb": ln.get("emissao_bsb"),
                      "last_modified_menos_recebimento_s": (
                          int((lm_bsb - datetime.strptime(rec, "%Y-%m-%d %H:%M:%S"))
                              .total_seconds()) if lm_bsb and rec else None)}
    linhas_lm = list(cache.values())
    if linhas_lm:
        gravar(linhas_lm, destino)
    por_grupo: dict[str, list] = defaultdict(list)
    for r in linhas_lm:
        if r.get("last_modified_menos_recebimento_s") is not None:
            por_grupo[r["grupo"]].append(r["last_modified_menos_recebimento_s"])
    return {"requisicoes": dict(cont), "parado": parado, "amostra": len(amostra),
            "com_last_modified": sum(len(x) for x in por_grupo.values()),
            "last_modified_menos_recebimento_s_por_grupo": {
                g: distribuicao(xs) for g, xs in sorted(por_grupo.items())}}


def distribuicao(xs: list[float]) -> dict:
    xs = sorted(xs)
    if not xs:
        return {"n": 0}

    def q(p):
        return xs[min(len(xs) - 1, int(p * len(xs)))]
    return {"n": len(xs), "min": xs[0], "p50": q(0.5), "p90": q(0.9), "p99": q(0.99),
            "max": xs[-1]}


# ---------------------------------------------------------------------------
# Download moderado de resultados municipais
# ---------------------------------------------------------------------------

class LimiteTSE(Exception):
    pass


def baixar_municipios(abrs: list[str], destino: Path, taxa: float, maximo: int) -> dict:
    """Baixa o JSON de resultado de cada município (no máximo `taxa` req/s).
    Para em 429 repetido. Devolve contagens."""
    destino.mkdir(parents=True, exist_ok=True)
    cont = Counter()
    intervalo = 1.0 / max(0.1, min(taxa, 5.0))
    seguidos_429 = 0
    for abr in abrs[:maximo]:
        url = URL_RESULTADO.format(uf=abr[:2], abr=abr)
        espera = 30.0
        while True:
            time.sleep(intervalo)
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "dataurnas-br"})
                with urllib.request.urlopen(req, timeout=30) as resp:
                    body = resp.read()
                seguidos_429 = 0
                break
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    seguidos_429 += 1
                    cont["http_429"] += 1
                    if seguidos_429 >= 3:
                        raise LimiteTSE(f"429 repetido em {abr}; parado após "
                                        f"{cont['baixados']} downloads") from e
                    log.warning("429 em %s, esperando %.0fs", abr, espera)
                    time.sleep(espera)
                    espera *= 2
                    continue
                cont[f"http_{e.code}"] += 1
                body = None
                break
            except (urllib.error.URLError, TimeoutError) as e:
                cont["erro_rede"] += 1
                log.warning("%s: %s", abr, e)
                body = None
                break
        if body is None:
            continue
        try:
            d = json.loads(body)
        except ValueError:
            cont["json_invalido"] += 1
            continue
        nome = f"{abr}_{(d.get('dg') or '').replace('/', '')}_{(d.get('hg') or '').replace(':', '')}_{d.get('idg')}.json.gz"
        (destino / nome).write_bytes(gzip.compress(body, 6))
        cont["baixados"] += 1
    return dict(cont)


def carregar_baixados(destino: Path) -> list[dict]:
    """Versões municipais baixadas por este script, no formato do índice."""
    out = []
    if not destino.exists():
        return out
    from dataurnas.downloader import ele2026 as E
    for p in sorted(destino.glob("*.json.gz")):
        try:
            d = json.loads(gzip.decompress(p.read_bytes()))
        except Exception:
            continue
        s, v, e = d.get("s") or {}, d.get("v") or {}, d.get("e") or {}
        abr = p.name.split("_")[0]
        out.append({
            "coletado_em": None, "abr": abr, "sha256": f"baixado:{p.name}",
            "dg": d.get("dg"), "hg": d.get("hg"), "idg": d.get("idg"),
            "dt": d.get("dt"), "ht": d.get("ht"), "bruto": True,
            "st": _int(s.get("st")), "ts": _int(s.get("ts")), "tv": _int(v.get("tv")),
            "vb": _int(v.get("vb")), "tvn": _int(v.get("tvn")), "c": _int(e.get("c")),
            "cand": {str(c.get("n")): _int(c.get("vap")) or 0
                     for _, _, c in E.iter_candidatos(d)},
        })
    return out


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------

def gravar(linhas: list[dict], caminho: Path) -> None:
    tmp = caminho.with_suffix(".parquet.tmp")
    tabela = pa.Table.from_pylist(linhas) if linhas else pa.table({})
    pq.write_table(tabela, tmp, compression="zstd")
    tmp.replace(caminho)
    log.info("gravado %s (%d linhas)", caminho.name, len(linhas))


def faixas_por_uf(linhas: list[dict]) -> list[dict]:
    grupos: dict[tuple, list] = defaultdict(list)
    for ln in linhas:
        grupos[(ln["uf"], ln["faixa_recebimento"])].append(ln)
        grupos[("br", ln["faixa_recebimento"])].append(ln)
    return [{"uf": uf, "faixa": fx, **somar(ls)} for (uf, fx), ls in sorted(grupos.items())]


def resumir_curva(curva: list[dict], excesso: list[dict], limite: int) -> dict:
    """Contagens da curva acumulada e versões com excesso, por município e UF."""
    com = [c for c in curva if c["excesso_hg"] and c["excesso_hg"] > 0]
    com_ht = [c for c in curva if c["excesso_ht"] and c["excesso_ht"] > 0]
    abrs = {c["abr"] for c in curva}
    return {
        "criterio": ("abrangências com seções com BU >= seções totalizadas na última "
                     "versão; excesso = st da versão - seções com dr/hr <= t"),
        "abrangencias": len(abrs),
        "ufs": sorted(a for a in abrs if len(a) == 2),
        "versoes": len(curva),
        "versoes_excesso_em_hg": len(com),
        "abrangencias_excesso_em_hg": len({c["abr"] for c in com}),
        "secoes_excesso_em_hg_soma": sum(c["excesso_hg"] for c in com),
        "versoes_excesso_em_ht": len(com_ht),
        "excesso_hg_max": max((c["excesso_hg"] for c in com), default=0),
        "recebimento_menos_hg_s_secoes_do_excesso": distribuicao(
            [e["recebimento_menos_hg_s"] for e in excesso]),
        "excesso_por_uf": dict(Counter(c["abr"][:2] for c in com)),
        "versoes_com_excesso": sorted(com, key=lambda c: -c["excesso_hg"])[:limite],
    }


def resumir_pausa(versoes: list[dict], marca: str) -> dict:
    """Versões dos totais marcadas (gerada ou totalizada na pausa)."""
    sel = [v for v in versoes if v.get(marca)]
    com = [v for v in sel if v.get("secoes")]
    return {"versoes": len(sel), "com_secoes_totalizadas": len(com),
            "abrangencias": len({v["abr"] for v in sel}),
            "hg_min": min((v["hg"] for v in sel), default=None),
            "hg_max": max((v["hg"] for v in sel), default=None),
            "ht_bsb_min": min((v["ht_bsb"] for v in sel if v["ht_bsb"]), default=None),
            "ht_bsb_max": max((v["ht_bsb"] for v in sel if v["ht_bsb"]), default=None),
            "itens": [{k: v.get(k) for k in ("abr", "versao", "hg", "ht", "ht_bsb", "secoes",
                                             "secoes_total", "comparecimento")}
                      for v in sorted(com, key=lambda x: (x["ht_bsb"] or "", x["abr"]))][:500]}


ORDEM_LISTA = {"m_recebimento_apos_totalizacao_15min": "recebimento_menos_totalizacao_s",
               "m_recebimento_antes_emissao": "atraso_recebimento_min"}


def lista(linhas: list[dict], marca: str, campos: tuple, limite: int) -> dict:
    """Seções com a marca; algumas listas vêm ordenadas pelo valor mais extremo."""
    sel = [ln for ln in linhas if ln.get(marca)]
    chave = ORDEM_LISTA.get(marca)
    if chave:
        sel.sort(key=lambda x: abs(x.get(chave) or 0), reverse=True)
    return {"total": len(sel), "itens": [{k: ln.get(k) for k in campos} for ln in sel[:limite]]}


CAMPOS_LISTA = ("uf", "cd_mun", "zona", "secao", "emissao_bsb", "recebimento_bu",
                "recebimento_primeiro", "recebimento_ultimo", "atraso_recebimento_min",
                "primeira_coleta_aux", "primeira_coleta_bu", "n_pacotes", "n_versoes_bu",
                "st_secao", "ht_totalizacao_completa_mun", "recebimento_menos_totalizacao_s",
                "comparecimento", "votos_13",
                "votos_22")


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--parts", action="append", help="diretório com versoes-*.parquet (repetível)")
    ap.add_argument("--totais", action="append", help="diretório com indice.jsonl (repetível)")
    ap.add_argument("--saida", default=str(SAIDA_PADRAO))
    ap.add_argument("--pausa-inicio", default=PAUSA_INICIO, help="HH:MM, Brasília")
    ap.add_argument("--pausa-fim", default=PAUSA_FIM, help="HH:MM, Brasília")
    ap.add_argument("--janela-alternativa", action="append",
                    help="HH:MM-HH:MM contada à parte no resumo (repetível)")
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--sem-download", action="store_true",
                    help="não baixa resultados municipais que faltarem")
    ap.add_argument("--taxa", type=float, default=2.0, help="req/s no download (máximo 5)")
    ap.add_argument("--max-downloads", type=int, default=400)
    ap.add_argument("--head-amostra", type=int, default=0,
                    help="seções por grupo para HEAD do bu.dat (Last-Modified); 0 desliga")
    ap.add_argument("--head-taxa", type=float, default=2.0, help="req/s no HEAD (máximo 3)")
    ap.add_argument("--limite-lista", type=int, default=500,
                    help="itens por lista no resumo.json (os parquets têm todos)")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    ini, fim = hora_no_dia(args.pausa_inicio), hora_no_dia(args.pausa_fim)
    alternativas = args.janela_alternativa or list(JANELAS_ALTERNATIVAS)
    parts = [Path(p) for p in (args.parts or [str(p) for p in PARTS_PADRAO if p.exists()])]
    tots = [Path(p) for p in (args.totais or [str(p) for p in TOTAIS_PADRAO if p.exists()])]
    saida = Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)
    dir_oficial = saida / "oficial_municipios"

    # 1. seções
    cache_path = saida / "cache_bu.parquet"
    cache = ler_cache(cache_path)
    secoes, cont = carregar_secoes(parts, cache, args.workers)
    gravar_cache(cache, cache_path)
    log.info("leitura: %s; %d seções", cont, len(secoes))
    linhas, multiplas = [], []
    for k in sorted(secoes):
        ln, mv = montar_secao(k, secoes[k], cache, ini, fim)
        linhas.append(ln)
        multiplas.extend(mv)
    for jan in alternativas:
        a, b = parse_janela(jan)
        col = "m_pausa_" + jan.replace(":", "").replace("-", "_")
        for ln in linhas:
            rec = ln.get("recebimento_bu")
            t = datetime.strptime(rec, "%Y-%m-%d %H:%M:%S") if rec else None
            ln[col] = t is not None and a <= t <= b
    com_bu = [ln for ln in linhas if ln.get("sha512_bu") and not ln.get("erro_decodificacao")]

    # 2. totais
    indice = carregar_indice(tots)
    baixados = carregar_baixados(dir_oficial)
    versoes, ultima = checar_versoes(indice, ini, fim)
    log.info("totais: %d versões, %d abrangências", len(versoes), len(ultima))

    por_uf: dict[str, list] = defaultdict(list)
    por_mun: dict[str, list] = defaultdict(list)
    for ln in com_bu:
        por_uf[ln["uf"]].append(ln)
        por_mun[f"{ln['uf']}{ln['cd_mun']}"].append(ln)

    def oficial_mun(abr: str) -> Optional[dict]:
        cands = [r for r in baixados if r["abr"] == abr]
        if abr in ultima:
            cands.append(ultima[abr])
        return max(cands, key=chave_ordem) if cands else None

    # municípios cuja versão oficial falta ou parece defasada frente aos BUs
    download = {"executado": False}
    precisam = []
    for abr, ls in por_mun.items():
        of = oficial_mun(abr)
        if of is None or (of.get("st") is not None and of.get("ts") is not None
                          and of["st"] < of["ts"] and len(ls) >= of["st"]):
            precisam.append(abr)
    download["necessarios"] = len(precisam)
    if precisam and not args.sem_download:
        download["executado"] = True
        try:
            download.update(baixar_municipios(sorted(precisam), dir_oficial, args.taxa,
                                              args.max_downloads))
        except LimiteTSE as e:
            download["parado"] = str(e)
            log.error("%s", e)
        baixados = carregar_baixados(dir_oficial)

    comp_mun = [comparar(abr, ls, oficial_mun(abr)) for abr, ls in sorted(por_mun.items())]
    for c in comp_mun:
        c["uf"] = c["abr"][:2]
    comp_uf = []
    for uf in sorted(set(por_uf) | {a for a in ultima if len(a) == 2 and a != "br"}):
        c = comparar(uf, por_uf.get(uf, []), ultima.get(uf))
        # subconjunto: municípios completos da UF, BU x oficial municipal
        mc = [m for m in comp_mun if m["uf"] == uf and m["situacao"] == "completo"]
        c["municipios_completos"] = len(mc)
        for k in CAMPOS_OFICIAL:
            c[f"subconj_bu_{k}"] = sum(m[f"bu_{k}"] or 0 for m in mc)
            c[f"subconj_oficial_{k}"] = sum(m[f"oficial_{k}"] or 0 for m in mc)
        comp_uf.append(c)
    br = comparar("br", [ln for ln in com_bu], ultima.get("br"))

    # BU x versões intermediárias (só abrangências com BU de todas as seções)
    n_total = {abr: (ultima[abr].get("ts") or -1) for abr in ultima}
    por_abr = {**por_mun, **por_uf}
    comparar_versoes_com_bus(versoes, por_abr, n_total)
    marcar_recebimento_apos_totalizacao(versoes, por_mun)
    curva, excesso = curva_recebimento_totalizacao(versoes, por_abr, ultima)
    lm = {"executado": False}
    if args.head_amostra and not args.sem_download:
        lm = head_last_modified(com_bu, saida / "last_modified.parquet", args.head_amostra,
                                args.head_taxa, excesso[:args.head_amostra])
        lm["executado"] = True

    # 3. faixas
    faixas = faixas_por_uf(com_bu)
    primeira_versao = {}
    for v in versoes:
        if len(v["abr"]) == 2 and v["abr"] not in primeira_versao:
            primeira_versao[v["abr"]] = v
    totais_inicio = {abr: {k: v.get(k) for k in ("coletado_em", "hg", "secoes", "secoes_total",
                                                  "comparecimento", "votos_13", "votos_22")}
                     for abr, v in sorted(primeira_versao.items())}

    gravar(linhas, saida / "secoes.parquet")
    gravar(multiplas, saida / "bus_versoes.parquet")
    gravar(versoes, saida / "totais_versoes.parquet")
    gravar(comp_uf, saida / "comparacao_uf.parquet")
    gravar(comp_mun, saida / "comparacao_municipio.parquet")
    gravar(faixas, saida / "faixas_uf.parquet")
    gravar(curva, saida / "curva_recebimento_totalizacao.parquet")
    gravar(excesso, saida / "curva_excesso_secoes.parquet")
    gravar(atraso_por_municipio(linhas), saida / "atraso_municipio.parquet")

    # 4. resumo
    marcas_cont = {m: sum(1 for ln in linhas if ln.get(m)) for m in MARCAS}
    for jan in alternativas:
        col = "m_pausa_" + jan.replace(":", "").replace("-", "_")
        marcas_cont[col] = sum(1 for ln in linhas if ln.get(col))
    regress = [v for v in versoes if v["regressoes"]]
    soma_int = [v for v in versoes if v["diferenca_soma_interna"]]
    comp_v = Counter(v["bu_comparacao"] for v in versoes)
    resumo = {
        "gerado_em": datetime.now().astimezone().isoformat(timespec="seconds"),
        "diretorios_parts": [str(p) for p in parts],
        "diretorios_totais": [str(p) for p in tots],
        "observacao": ("Dados parciais: a coleta continua. Recebimento = dr/hr do aux.json "
                       "(Brasília, ver verificacao_fuso_recebimento). Emissão = horário do BU "
                       "convertido do fuso do município. Totais versionados só a partir de "
                       "19h34; antes disso não há versão gravada. Descritivo, sem inferência "
                       "causal."),
        "pausa": {"inicio": fmt(ini), "fim": fmt(fim), "alternativas": alternativas,
                  "criterio": "inicio <= recebimento <= fim"},
        "leitura": cont,
        "secoes_vistas": len(linhas),
        "secoes_com_bu": len(com_bu),
        "bus_ilegiveis": sum(1 for ln in linhas if ln.get("erro_decodificacao")),
        "status_secao": dict(Counter(ln.get("st_secao") for ln in linhas)),
        "status_pacotes": dict(Counter(ln.get("status_pacotes") for ln in linhas)),
        "aux_gerado_igual_recebimento": dict(Counter(
            "igual" if ln.get("aux_gerado") == ln.get("recebimento_bu") else "diferente"
            for ln in linhas if ln.get("recebimento_bu"))),
        "verificacao_fuso_recebimento": verificar_fuso_recebimento(linhas, ini, fim),
        "marcas": marcas_cont,
        "recebimentos_por_minuto_16h50_19h30": dict(sorted(Counter(
            ln["recebimento_bu"][11:16] for ln in linhas if ln.get("recebimento_bu")
            and "16:50" <= ln["recebimento_bu"][11:16] <= "19:30").items())),
        "ultimo_recebimento_antes_de_19h": max((ln["recebimento_bu"] for ln in linhas
                                                if ln.get("recebimento_bu")
                                                and ln["recebimento_bu"] < fmt(fim)),
                                               default=None),
        "primeiro_recebimento_a_partir_de_19h": min((ln["recebimento_bu"] for ln in linhas
                                                     if ln.get("recebimento_bu")
                                                     and ln["recebimento_bu"] >= fmt(fim)),
                                                    default=None),
        "faixa_recebimento_br": {f["faixa"]: {k: f[k] for k in ("secoes",) + CAMPOS_VOTOS}
                                 for f in faixas if f["uf"] == "br"},
        "totais_primeira_versao_gravada": totais_inicio,
        "totais": {
            "versoes": len(versoes), "abrangencias": len(ultima),
            "versoes_com_regressao": len(regress),
            "regressoes": [{k: v[k] for k in ("abr", "versao", "hg", "idg", "regressoes")}
                           for v in regress[:args.limite_lista]],
            "versoes_soma_interna_diferente": len(soma_int),
            "soma_interna_diferente": [{k: v[k] for k in ("abr", "hg", "idg",
                                                          "diferenca_soma_interna")}
                                       for v in soma_int[:args.limite_lista]],
            "versoes_geradas_na_pausa": resumir_pausa(versoes, "hg_na_pausa"),
            "versoes_totalizadas_na_pausa": resumir_pausa(versoes, "ht_na_pausa"),
            "ultima_totalizacao_antes_de_19h": max((v["ht_bsb"] for v in versoes
                                                    if v["ht_bsb"] and v["ht_bsb"] < fmt(fim)),
                                                   default=None),
            "ht_bsb_por_minuto_16h50_19h30": dict(sorted(Counter(
                v["ht_bsb"][11:16] for v in versoes
                if v["ht_bsb"] and "16:50" <= v["ht_bsb"][11:16] <= "19:30").items())),
            "bu_x_versoes": dict(comp_v),
            "bu_x_versoes_ordem_recebimento": dict(Counter(v["bu_comparacao_ordem"]
                                                           for v in versoes
                                                           if v["bu_comparacao_ordem"])),
            "bu_x_versoes_ordem_diferentes": [
                {k: v.get(k) for k in ("abr", "hg", "ht_bsb", "idg", "secoes",
                                       "bu_diferencas_ordem")}
                for v in versoes if v["bu_comparacao_ordem"] == "difere"][:args.limite_lista],
            "folga_s_totalizadas_mais_que_recebidas": distribuicao(
                [v["folga_s"] for v in versoes
                 if v["bu_comparacao"] == "totalizadas_mais_que_recebidas"
                 and v["folga_s"] is not None]),
            "bu_x_versoes_totalizadas_mais_que_recebidas": [
                {k: v.get(k) for k in ("abr", "hg", "ht_bsb", "idg", "secoes", "bu_ate_ht_secoes")}
                for v in versoes if v["bu_comparacao"] == "totalizadas_mais_que_recebidas"
            ][:args.limite_lista],
            "bu_x_versoes_diferentes": [{k: v.get(k) for k in ("abr", "hg", "ht", "idg", "secoes",
                                                               "bu_diferencas")}
                                        for v in versoes if v["bu_comparacao"] == "difere"],
        },
        "download_municipios": download,
        "comparacao_br": br,
        "cobertura_uf": {c["abr"]: {"situacao": c["situacao"], "bu_secoes": c["bu_secoes"],
                                    "oficial_secoes": c["oficial_secoes"],
                                    "secoes_total": c["secoes_total_oficial"],
                                    "cobertura": c["cobertura"],
                                    "municipios_completos": c["municipios_completos"]}
                         for c in comp_uf},
        "ufs_comparadas": [c["abr"] for c in comp_uf if c["comparado"]],
        "ufs_com_diferenca": [c for c in comp_uf if c["tem_diferenca"]],
        "subconjunto_municipios_completos_por_uf": {
            c["abr"]: {k: {"bu": c[f"subconj_bu_{k}"], "oficial": c[f"subconj_oficial_{k}"],
                           "dif": c[f"subconj_bu_{k}"] - c[f"subconj_oficial_{k}"]}
                       for k in CAMPOS_OFICIAL}
            for c in comp_uf if c["municipios_completos"]},
        "municipios": dict(Counter(c["situacao"] for c in comp_mun)),
        "municipios_com_diferenca": [c for c in comp_mun if c["tem_diferenca"]],
        "listas": {m: lista(linhas, m, CAMPOS_LISTA, args.limite_lista)
                   for m in ("m_recebido_na_pausa", "m_recebimento_antes_emissao",
                             "m_mais_de_um_pacote", "m_bu_mais_de_uma_versao",
                             "votos_diferem_entre_versoes", "mesmo_hash_conteudo_diferente",
                             "m_recebimento_apos_totalizacao_15min")},
        "recebimento_menos_totalizacao_s": distribuicao(
            [ln["recebimento_menos_totalizacao_s"] for ln in linhas
             if ln.get("recebimento_menos_totalizacao_s") is not None]),
        "curva_recebimento_totalizacao": resumir_curva(curva, excesso, args.limite_lista),
        "atraso_recebimento_emissao_ba_destaques_min": destaque_ba(linhas),
        "last_modified_amostra": lm,
        "recebidos_mais_2h_por_uf": dict(Counter(ln["uf"] for ln in linhas
                                                 if ln.get("m_recebido_mais_2h"))),
    }
    (saida / "resumo.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=1,
                                                  default=str), encoding="utf-8")
    log.info("seções %d (com BU %d); na pausa %d; antes da emissão %d; regressões %d; "
             "UFs comparadas %s; municípios %s",
             len(linhas), len(com_bu), marcas_cont["m_recebido_na_pausa"],
             marcas_cont["m_recebimento_antes_emissao"], len(regress),
             resumo["ufs_comparadas"], resumo["municipios"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
