#!/usr/bin/env python3
"""Logs do GEDAI-UE no 2º turno de 2026 (pleito 3221, eleição 6258).

O GEDAI-UE é o sistema dos cartórios e TREs que gera as mídias de carga e de
votação, recebe de volta as correspondências das urnas carregadas (tabela de
correspondência gravada na flash de carga) e as transmite ao TSE. O TSE publica
no portal de dados abertos um zip por UF e turno:

  log_gedai_<turno>_<UF>_<DDMMAAAAHHMM>.zip
    leiame.pdf
    gedai-ue-<uf>-<pleito>-oficial-<COMPUTADOR>-<SERIAL_TPM>-<SERIAL_INST>-log.jez
      (zip) gedai-ue-<uf>-oficial-<COMPUTADOR>-log.jez
        (zip) gedai-ue.log          texto ISO-8859-1, CRLF, uma linha por evento:
                                    "DD/MM/AAAA HH:MM:SS<TAB>NÍVEL<TAB>mensagem<TAB>hash"
      (zip) gedai-ue-<uf>-oficial-<COMPUTADOR>-log.vsc   assinatura do log

O log de cada estação é cumulativo: o arquivo do 2º turno traz também o
histórico desde a instalação (geração de mídias e cargas de setembro).

Etapas (todas só leitura nas fontes):

  extrair  lê os zips do GEDAI e grava, no diretório de saída:
           arquivos.parquet         um registro por log de estação e pacote
           correspondencias.parquet eventos de correspondência (recebida,
                                    transmitida, exportada, cadastrada...)
           midias_carga.parquet     mídias de carga geradas (NS, zona, seções)
           eventos_dia.parquet      contagem de eventos por pacote, UF, dia e tipo
           diff_versoes.parquet     comparação entre pacotes do mesmo turno
  bus      lê os BUs versionados pelo coletor e grava bus_carga.parquet com os
           dados de carga de cada seção (código, data/hora da carga, número
           interno, número de série da flash de carga, estação geradora,
           histórico de códigos de carga)
  cruzar   cruza BUs e GEDAI e grava cruzamento_bus.parquet, cargas_gedai.parquet
           e resumo.json
  tudo     as três etapas em sequência

Uso (no servidor de processamento):
  python3 scripts/ele2026/gedai_t2.py tudo \\
      --gedai ~/dataurnas-t2/gedai/1t ~/dataurnas-t2/gedai/2t ~/dataurnas-t2/gedai/2t_2510 \\
      --bus ~/dataurnas-mac/versoes/2026/t2/bus/parts ~/dataurnas-mac/versoes/2026/t2-sseco/bus/parts \\
      --encerramento ~/dataurnas-mac/parquet-t2/encerramento/secoes_encerramento.parquet \\
      --saida ~/dataurnas-t2/gedai/analise
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import time
import zipfile
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional

ROOT = Path(__file__).resolve().parents[2]
SRC = str(ROOT / "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import pandas as pd  # noqa: E402

PLEITO_T1 = "03220"
PLEITO_T2 = "03221"
CHAVE = ["uf", "cd_mun", "zona", "secao"]
MUNICIPIOS_DESTAQUE = {
    "38490": "Salvador",
    "36854": "Lauro de Freitas",
    "35157": "Feira de Santana",
}
CORTE_TARDIA_MIN = 30.0  # 17:30 de Brasília
MAX_EXEMPLOS = 30
ENCODING_LOG = "latin-1"

# ---------------------------------------------------------------------------
# Nomes de arquivo
# ---------------------------------------------------------------------------

RE_PACOTE = re.compile(r"log_gedai_(\dt)_([A-Za-z]{2})_(\d{12})\.zip$")
RE_LOG = re.compile(
    r"gedai-ue-([a-z]{2})-(\d{5})-oficial-([A-Za-z0-9]+)-([0-9A-Fa-f]+)-([0-9A-Fa-f]+)"
    r"-log\.jez$")


def parse_nome_pacote(nome: str) -> Optional[dict]:
    """log_gedai_2t_BA_251020261327.zip -> turno, uf, gerado_em (horário do nome)."""
    m = RE_PACOTE.search(os.path.basename(nome))
    if not m:
        return None
    turno, uf, stamp = m.groups()
    try:
        gerado = datetime.strptime(stamp, "%d%m%Y%H%M")
    except ValueError:
        gerado = None
    return {"turno": turno, "uf": uf.lower(), "carimbo": stamp,
            "pacote": f"{turno}_{stamp}", "gerado_em": gerado}


def parse_nome_log(nome: str) -> Optional[dict]:
    """Nome do .jez de estação, conforme o leiame do TSE."""
    m = RE_LOG.search(os.path.basename(nome))
    if not m:
        return None
    uf, pleito, comp, tpm, inst = m.groups()
    return {"uf": uf, "pleito_arquivo": pleito, "computador": comp,
            "serial_tpm": tpm.upper(), "serial_instalacao": inst.upper()}


# ---------------------------------------------------------------------------
# Linhas do log
# ---------------------------------------------------------------------------

RE_CORRESP = re.compile(
    r"^(?P<acao>Recebida|Transmitida a|Exportada a|Cadastrada|Definida como atual a)"
    r" correspondência de (?P<tipo>seção|contingência): "
    r"município (?P<mun>\d+), zona (?P<zona>\d+)"
    r"(?:, seção (?P<secao>\d+))?"
    r", carga (?P<carga>\d+), id urna (?P<urna>\d+), mc (?P<mc>[0-9A-Fa-f]+)\.?$")
ACOES = {
    "Recebida": "recebida",
    "Transmitida a": "transmitida",
    "Exportada a": "exportada",
    "Cadastrada": "cadastrada",
    "Definida como atual a": "definida_atual",
}
RE_MIDIA_CARGA = re.compile(
    r"^Mídia de carga gerada\. NS:(?P<ns>[0-9A-Fa-f]+) Z:(?P<zona>\d+)"
    r"(?: \| Seções \(M:(?P<mun>\d+)\)(?P<secoes>[\d ]*))?")
RE_PLEITO = re.compile(r"^Pleito corrente: (\d+)")
RE_CORRESP_INVALIDA = re.compile(r"correspondência de código \[(\d+)\] está inválida")


def parse_dt(s: str) -> Optional[datetime]:
    try:
        return datetime.strptime(s, "%d/%m/%Y %H:%M:%S")
    except (ValueError, TypeError):
        return None


def dividir_linha(linha: str) -> Optional[tuple[str, str, str, str]]:
    """(data_hora, nível, mensagem, hash) ou None se a linha não segue o formato."""
    p = linha.rstrip("\r\n").split("\t")
    if len(p) < 3:
        return None
    hash_linha = p[3] if len(p) > 3 else ""
    return p[0], p[1], p[2], hash_linha


def tipo_evento(msg: str) -> str:
    """Rótulo curto e estável para contagem por tipo de evento."""
    m = RE_CORRESP.match(msg)
    if m:
        t = "secao" if m.group("tipo") == "seção" else "contingencia"
        return f"correspondencia_{ACOES[m.group('acao')]}_{t}"
    if msg.startswith("Mídia de carga gerada"):
        return "midia_carga_gerada"
    if msg.startswith("Mídia de votação gerada"):
        return "midia_votacao_gerada"
    if msg.startswith("Início da geração de mídia de carga"):
        return "inicio_geracao_midia_carga"
    if msg.startswith("Abertura do GEDAI-UE"):
        return "abertura_gedai"
    if msg.startswith("Fechamento do GEDAI-UE"):
        return "fechamento_gedai"
    if RE_CORRESP_INVALIDA.search(msg):
        return "correspondencia_invalida"
    if msg.startswith("Transição para"):
        return "transicao_turno"
    if msg.startswith("Pacote ") and "importado" in msg:
        return "pacote_importado"
    if msg.startswith("Realizada a transmissão do log"):
        return "transmissao_log"
    k = re.sub(r"[0-9A-F]{8,}", "H", msg)
    k = re.sub(r"\d+", "N", k)
    return "outro:" + k[:60]


def eventos_do_log(texto: str, base: dict) -> tuple[list[dict], list[dict], Counter, dict]:
    """Extrai correspondências, mídias de carga e contagens de um log de estação.

    `base` traz as colunas comuns (pacote, uf, computador...). O pleito corrente
    é acompanhado pela linha "Pleito corrente" e zerado a cada abertura.
    """
    corr: list[dict] = []
    midias: list[dict] = []
    cont: Counter = Counter()
    pleito: Optional[str] = None
    n = 0
    prim = ult = None
    for linha in texto.splitlines():
        partes = dividir_linha(linha)
        if partes is None:
            continue
        sdt, nivel, msg, h = partes
        dt = parse_dt(sdt)
        if dt is None:
            continue
        n += 1
        prim = dt if prim is None or dt < prim else prim
        ult = dt if ult is None or dt > ult else ult
        if msg.startswith("Abertura do GEDAI-UE"):
            pleito = None
        mp = RE_PLEITO.match(msg)
        if mp:
            pleito = mp.group(1)
        te = tipo_evento(msg)
        cont[(dt.date().isoformat(), nivel, te)] += 1
        m = RE_CORRESP.match(msg)
        if m:
            corr.append({
                **base, "data_hora": dt, "nivel": nivel, "hash_linha": h,
                "pleito_corrente": pleito,
                "acao": ACOES[m.group("acao")],
                "tipo": "secao" if m.group("tipo") == "seção" else "contingencia",
                "cd_mun": m.group("mun").zfill(5), "zona": m.group("zona").zfill(4),
                "secao": None if m.group("secao") is None else m.group("secao").zfill(4),
                "codigo_carga": m.group("carga"),
                "numero_interno_urna": int(m.group("urna")),
                "mc": m.group("mc").upper(),
            })
            continue
        m = RE_MIDIA_CARGA.match(msg)
        if m:
            secs = (m.group("secoes") or "").split()
            midias.append({
                **base, "data_hora": dt, "hash_linha": h, "pleito_corrente": pleito,
                "ns": m.group("ns").upper(), "zona": m.group("zona").zfill(4),
                "cd_mun": None if m.group("mun") is None else m.group("mun").zfill(5),
                "n_secoes": len(secs), "secoes": " ".join(s.zfill(4) for s in secs),
            })
    meta = {"n_linhas": n, "primeira_data_hora": prim, "ultima_data_hora": ult}
    return corr, midias, cont, meta


# ---------------------------------------------------------------------------
# Zips aninhados
# ---------------------------------------------------------------------------

def _dt_zip(info: zipfile.ZipInfo) -> Optional[datetime]:
    try:
        return datetime(*info.date_time)
    except ValueError:
        return None


def iterar_logs_pacote(caminho: Path) -> Iterator[dict]:
    """Para cada .jez de estação no pacote, devolve metadados e o texto do log."""
    with zipfile.ZipFile(caminho) as z:
        for info in z.infolist():
            if not info.filename.endswith("-log.jez"):
                continue
            meta = parse_nome_log(info.filename) or {}
            reg: dict[str, Any] = {
                "entrada": info.filename, "entrada_dt": _dt_zip(info),
                "entrada_comentario": info.comment.decode("latin-1") or None,
                "entrada_tamanho": info.file_size, **meta,
                "interno_dt": None, "log_dt": None, "tem_vsc": False,
                "log_tamanho": None, "texto": None, "erro": None,
            }
            try:
                b1 = z.read(info)
                with zipfile.ZipFile(io.BytesIO(b1)) as z1:
                    jez = [i for i in z1.infolist() if i.filename.endswith(".jez")]
                    reg["tem_vsc"] = any(i.filename.endswith(".vsc") for i in z1.infolist())
                    if not jez:
                        raise ValueError("sem .jez interno")
                    reg["interno_dt"] = _dt_zip(jez[0])
                    with zipfile.ZipFile(io.BytesIO(z1.read(jez[0]))) as z2:
                        logs = [i for i in z2.infolist() if i.filename.endswith(".log")]
                        if not logs:
                            raise ValueError("sem .log interno")
                        reg["log_dt"] = _dt_zip(logs[0])
                        raw = z2.read(logs[0])
                        reg["log_tamanho"] = len(raw)
                        reg["texto"] = raw.decode(ENCODING_LOG)
            except Exception as e:  # registra e segue
                reg["erro"] = f"{type(e).__name__}: {e}"[:200]
            yield reg


def processar_pacote(caminho: str) -> dict:
    """Lê um pacote (zip de UF) e devolve tabelas em listas de dicts."""
    p = Path(caminho)
    pac = parse_nome_pacote(p.name) or {"turno": None, "uf": None, "carimbo": None,
                                        "pacote": p.stem, "gerado_em": None}
    arquivos, corr, midias, contagens = [], [], [], []
    textos: dict[str, str] = {}
    for reg in iterar_logs_pacote(p):
        base = {"pacote": pac["pacote"], "turno_pacote": pac["turno"],
                "uf": reg.get("uf") or pac["uf"],
                "computador": reg.get("computador"),
                "serial_tpm": reg.get("serial_tpm"),
                "serial_instalacao": reg.get("serial_instalacao")}
        meta_log = {"n_linhas": 0, "primeira_data_hora": None, "ultima_data_hora": None}
        if reg["texto"] is not None:
            c, m, cont, meta_log = eventos_do_log(reg["texto"], base)
            corr.extend(c)
            midias.extend(m)
            for (dia, nivel, te), v in cont.items():
                contagens.append({**base, "dia": dia, "nivel": nivel, "tipo_evento": te,
                                  "n": v})
            textos[reg["entrada"]] = reg["texto"]
        arquivos.append({
            **base, "zip": p.name, "zip_gerado_em": pac["gerado_em"],
            "entrada": reg["entrada"], "pleito_arquivo": reg.get("pleito_arquivo"),
            "entrada_dt": reg["entrada_dt"], "entrada_comentario": reg["entrada_comentario"],
            "entrada_tamanho": reg["entrada_tamanho"], "interno_dt": reg["interno_dt"],
            "log_dt": reg["log_dt"], "tem_vsc": reg["tem_vsc"],
            "log_tamanho": reg["log_tamanho"], "erro": reg["erro"], **meta_log})
    with zipfile.ZipFile(p) as z:
        comentario = z.comment.decode("latin-1") or None
        outros = [i.filename for i in z.infolist() if not i.filename.endswith("-log.jez")]
    return {"pacote": pac, "zip": p.name, "comentario_zip": comentario,
            "outros_arquivos": outros, "arquivos": arquivos, "correspondencias": corr,
            "midias": midias, "contagens": contagens, "textos": textos}


# ---------------------------------------------------------------------------
# Comparação entre pacotes do mesmo turno e UF
# ---------------------------------------------------------------------------

def comparar_textos(antigo: Optional[str], novo: Optional[str]) -> dict:
    """Classifica a diferença entre duas versões do log de uma estação.

    status: identico, acrescimo (o novo começa com o antigo), divergente
    (houve alteração no trecho antigo), so_novo, so_antigo.
    """
    if antigo is None and novo is None:
        return {"status": "ausente", "linhas_novas": [], "linhas_removidas": 0}
    if antigo is None:
        return {"status": "so_novo", "linhas_novas": novo.splitlines(),
                "linhas_removidas": 0}
    if novo is None:
        return {"status": "so_antigo", "linhas_novas": [],
                "linhas_removidas": len(antigo.splitlines())}
    if antigo == novo:
        return {"status": "identico", "linhas_novas": [], "linhas_removidas": 0}
    if novo.startswith(antigo):
        return {"status": "acrescimo", "linhas_novas": novo[len(antigo):].splitlines(),
                "linhas_removidas": 0}
    la, ln = antigo.splitlines(), novo.splitlines()
    sa, sn = Counter(la), Counter(ln)
    novas = list((sn - sa).elements())
    removidas = sum((sa - sn).values())
    return {"status": "divergente", "linhas_novas": novas, "linhas_removidas": removidas}


def _chave_estacao(entrada: str) -> str:
    """Identidade da estação sem o pleito do nome (1t e 2t usam pleitos distintos)."""
    m = parse_nome_log(entrada)
    if not m:
        return entrada
    return f"{m['uf']}|{m['computador']}|{m['serial_tpm']}|{m['serial_instalacao']}"


def diff_pacotes(antigo: dict, novo: dict, rotulo: str) -> list[dict]:
    """Uma linha por estação e dia: o que o pacote novo acrescenta ao antigo."""
    ta = {_chave_estacao(k): v for k, v in antigo["textos"].items()}
    tn = {_chave_estacao(k): v for k, v in novo["textos"].items()}
    out = []
    for est in sorted(set(ta) | set(tn)):
        r = comparar_textos(ta.get(est), tn.get(est))
        uf, comp, tpm, inst = (est.split("|") + [None] * 4)[:4]
        base = {"comparacao": rotulo, "pacote_antigo": antigo["pacote"]["pacote"],
                "pacote_novo": novo["pacote"]["pacote"], "uf": uf, "computador": comp,
                "serial_tpm": tpm, "serial_instalacao": inst, "status": r["status"],
                "linhas_removidas": r["linhas_removidas"]}
        por = Counter()
        for linha in r["linhas_novas"]:
            partes = dividir_linha(linha)
            if partes is None:
                continue
            dt = parse_dt(partes[0])
            if dt is None:
                continue
            por[(dt.date().isoformat(), tipo_evento(partes[2]),
                 dt.hour >= 17 and dt.date().isoformat() == "2026-10-25")] += 1
        if not por:
            out.append({**base, "dia": None, "tipo_evento": None, "apos_17h_2510": False,
                        "n": 0})
        for (dia, te, tarde), v in por.items():
            out.append({**base, "dia": dia, "tipo_evento": te, "apos_17h_2510": tarde,
                        "n": v})
    return out


# ---------------------------------------------------------------------------
# Etapa extrair
# ---------------------------------------------------------------------------

def _mapear(fn, itens: list, workers: int) -> list:
    """map em processos; com um worker (ou um item) roda no próprio processo."""
    if workers <= 1 or len(itens) <= 1:
        return [fn(i) for i in itens]
    with ProcessPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(fn, itens, chunksize=1))


def listar_pacotes(dirs: Iterable[Path]) -> list[Path]:
    out: list[Path] = []
    for d in dirs:
        d = Path(d).expanduser()
        if d.is_file() and d.suffix == ".zip":
            out.append(d)
        elif d.is_dir():
            out.extend(sorted(d.glob("log_gedai_*.zip")))
    return out


def _sem_texto(r: dict) -> dict:
    return {k: v for k, v in r.items() if k != "textos"}


def etapa_extrair(dirs: list[Path], saida: Path, workers: int) -> dict:
    pacotes = listar_pacotes(dirs)
    if not pacotes:
        raise SystemExit("nenhum pacote log_gedai_*.zip encontrado")
    saida.mkdir(parents=True, exist_ok=True)
    resultados = _mapear(processar_pacote, [str(p) for p in pacotes], workers)
    # comparações: pacotes consecutivos do mesmo turno e UF
    grupos: dict[tuple, list[dict]] = defaultdict(list)
    for r in resultados:
        grupos[(r["pacote"]["turno"], r["pacote"]["uf"])].append(r)
    diffs: list[dict] = []
    for (turno, _uf), lst in sorted(grupos.items(), key=lambda kv: str(kv[0])):
        lst.sort(key=lambda r: r["pacote"]["gerado_em"] or datetime.min)
        for a, b in zip(lst, lst[1:], strict=False):
            rot = f"{turno}_{a['pacote']['carimbo']}_{b['pacote']['carimbo']}"
            diffs.extend(diff_pacotes(a, b, rot))
    tabelas = {
        "arquivos": [x for r in resultados for x in r["arquivos"]],
        "correspondencias": [x for r in resultados for x in r["correspondencias"]],
        "midias_carga": [x for r in resultados for x in r["midias"]],
        "eventos_dia": [x for r in resultados for x in r["contagens"]],
        "diff_versoes": diffs,
    }
    for nome, linhas in tabelas.items():
        pd.DataFrame(linhas).to_parquet(saida / f"{nome}.parquet", index=False)
    pac = [{"zip": r["zip"], **{k: (v.isoformat() if isinstance(v, datetime) else v)
                                for k, v in r["pacote"].items()},
            "comentario_zip": r["comentario_zip"], "outros_arquivos": r["outros_arquivos"],
            "n_logs": len(r["arquivos"])} for r in map(_sem_texto, resultados)]
    (saida / "pacotes.json").write_text(json.dumps(pac, ensure_ascii=False, indent=1))
    return {k: len(v) for k, v in tabelas.items()} | {"pacotes": len(pac)}


# ---------------------------------------------------------------------------
# Etapa bus: dados de carga dos BUs
# ---------------------------------------------------------------------------

def _hex(v: Any) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, (bytes, bytearray)):
        return bytes(v).hex().upper()
    return str(v).upper()


def _choice(v: Any) -> tuple[Optional[str], Any]:
    if isinstance(v, tuple) and len(v) == 2:
        return v[0], v[1]
    return None, v


def carga_do_bu(raw: bytes) -> dict:
    """Campos de carga de um BU (spec v2, com recuo para v1)."""
    from dataurnas.models import SpecVersion
    from dataurnas.parsers.asn1_helper import decode_envelope

    try:
        try:
            _env, bu = decode_envelope(bytes(raw), "EntidadeBoletimUrna", SpecVersion.V2)
        except Exception:
            _env, bu = decode_envelope(bytes(raw), "EntidadeBoletimUrna", SpecVersion.V1)
    except Exception as e:
        return {"bu_erro": f"{type(e).__name__}: {e}"[:200]}
    urna = bu.get("urna") or {}
    tipo, _ = _choice(urna.get("tipoUrna"))
    if tipo is None and urna.get("tipoUrna") is not None:
        tipo = str(urna.get("tipoUrna"))
    corr = urna.get("correspondenciaResultado") or {}
    carga = corr.get("carga") or {}
    ger = carga.get("identificadorGeradorMidia") or {}
    tipo_ident, ident = _choice(corr.get("identificacao"))
    ident = ident if isinstance(ident, dict) else {}
    mz = ident.get("municipioZona") or {}
    dados = _choice(bu.get("dadosSecaoSA"))[1]
    dados = dados if isinstance(dados, dict) else {}
    hist = [str(x) for x in (bu.get("historicoCodigosCarga") or [])]
    num = carga.get("numeroInternoUrna")
    return {
        "tipo_urna": tipo,
        "codigo_carga": None if carga.get("codigoCarga") is None else str(carga["codigoCarga"]),
        "numero_interno_urna": None if num is None else int(num),
        "data_hora_carga": carga.get("dataHoraCarga"),
        "ns_flash_carga": _hex(carga.get("numeroSerieFC")),
        "gerador_nome": ger.get("nome"),
        "gerador_serial_tpm": _hex(ger.get("serialCertificadoTPM")),
        "gerador_serial_instalacao": _hex(ger.get("serialInstalacao")),
        "ident_carga_tipo": tipo_ident,
        "ident_carga_mun": None if mz.get("municipio") is None else
        str(mz["municipio"]).zfill(5),
        "ident_carga_zona": None if mz.get("zona") is None else str(mz["zona"]).zfill(4),
        "ident_carga_secao": None if ident.get("secao") is None else
        str(ident["secao"]).zfill(4),
        "historico_codigos_carga": " ".join(hist),
        "qtd_codigos_carga": len(hist),
        "abertura_local": dados.get("dataHoraAbertura"),
        "encerramento_local": dados.get("dataHoraEncerramento"),
        "bu_erro": None,
    }


def _bus_de_parte(caminho: str) -> list[dict]:
    import pyarrow.parquet as pq

    out: list[dict] = []
    try:
        pf = pq.ParquetFile(caminho)
    except Exception as e:
        return [{"parte": caminho, "bu_erro": f"parte ilegível: {e}"[:200]}]
    cols = [c for c in ("coletado_em", "uf", "cd_mun", "zona", "secao", "tipo", "sha512",
                        "conteudo") if c in pf.schema_arrow.names]
    origem = Path(caminho).parent.parent.parent.name
    for rg in range(pf.num_row_groups):
        try:
            tb = pf.read_row_group(rg, columns=cols)
        except Exception as e:
            out.append({"parte": caminho, "bu_erro": f"grupo ilegível: {e}"[:200]})
            break
        for r in tb.to_pylist():
            if r.get("tipo") != "bu" or not r.get("conteudo"):
                continue
            out.append({"uf": str(r["uf"]), "cd_mun": str(r["cd_mun"]),
                        "zona": str(r["zona"]), "secao": str(r["secao"]),
                        "origem": origem, "coletado_em": r.get("coletado_em"),
                        "sha512": r.get("sha512"), **carga_do_bu(r["conteudo"])})
    return out


def etapa_bus(dirs: list[Path], saida: Path, workers: int) -> dict:
    partes: list[str] = []
    for d in dirs:
        d = Path(d).expanduser()
        if d.is_dir():
            partes.extend(str(p) for p in sorted(d.glob("versoes-*.parquet")))
    if not partes:
        raise SystemExit("nenhuma parte versoes-*.parquet encontrada")
    linhas = [x for lst in _mapear(_bus_de_parte, partes, workers) for x in lst]
    df = pd.DataFrame(linhas)
    erros = df[df["uf"].isna()] if "uf" in df else df.iloc[0:0]
    df = df[df["uf"].notna()]
    n_versoes = df.groupby(CHAVE)["sha512"].nunique().rename("n_versoes_bu")
    n_cargas = df.groupby(CHAVE)["codigo_carga"].nunique().rename("n_codigos_carga_versoes")
    ult = (df.sort_values("coletado_em", kind="stable").groupby(CHAVE).tail(1)
           .merge(n_versoes.reset_index(), on=CHAVE).merge(n_cargas.reset_index(), on=CHAVE))
    saida.mkdir(parents=True, exist_ok=True)
    ult.to_parquet(saida / "bus_carga.parquet", index=False)
    return {"partes": len(partes), "bus_lidos": int(len(df)), "secoes": int(len(ult)),
            "bu_erro": int(ult["bu_erro"].notna().sum()), "partes_com_erro": int(len(erros))}


# ---------------------------------------------------------------------------
# Etapa cruzar
# ---------------------------------------------------------------------------

def deduplicar_correspondencias(corr: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por evento: o mesmo evento aparece em vários pacotes (log cumulativo)."""
    chave = ["uf", "computador", "serial_tpm", "serial_instalacao", "data_hora", "acao",
             "tipo", "codigo_carga", "numero_interno_urna", "mc", "hash_linha"]
    corr = corr.sort_values(["data_hora", "pacote"], kind="stable")
    n_pac = corr.groupby(chave, dropna=False, sort=False)["pacote"].transform("nunique")
    ult_pac = corr.groupby(chave, dropna=False, sort=False)["pacote"].transform("max")
    d = corr.assign(n_pacotes=n_pac, ultimo_pacote=ult_pac).drop_duplicates(chave)
    return d.drop(columns=["pacote"]).reset_index(drop=True)


def resumir_cargas_gedai(corr: pd.DataFrame, midias: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por código de carga visto no GEDAI (correspondência recebida ou
    cadastrada), com a primeira recepção e a mídia de carga de mesmo NS."""
    rec = corr[corr["acao"].isin(["recebida", "cadastrada"])].sort_values("data_hora")
    if rec.empty:
        return pd.DataFrame(columns=["codigo_carga"])
    g = rec.groupby("codigo_carga", sort=False)
    prim = g.head(1).set_index("codigo_carga")
    out = pd.DataFrame({
        "uf": prim["uf"], "tipo": prim["tipo"], "cd_mun": prim["cd_mun"],
        "zona": prim["zona"], "secao": prim["secao"],
        "numero_interno_urna": prim["numero_interno_urna"], "mc": prim["mc"],
        "computador_recepcao": prim["computador"],
        "primeira_recepcao": prim["data_hora"],
        "pleito_corrente_recepcao": prim["pleito_corrente"],
    })
    out["n_recepcoes"] = g.size()
    out["n_estacoes"] = g["computador"].nunique()
    out["n_urnas_distintas"] = g["numero_interno_urna"].nunique()
    trans = corr[corr["acao"] == "transmitida"].groupby("codigo_carga")["data_hora"].min()
    out["primeira_transmissao"] = trans.reindex(out.index)
    out = out.reset_index()
    if not midias.empty:
        m = (midias.sort_values("data_hora").drop_duplicates("ns", keep="last")
             [["ns", "data_hora", "computador", "zona", "cd_mun"]]
             .rename(columns={"ns": "mc", "data_hora": "midia_gerada_em",
                              "computador": "midia_computador", "zona": "midia_zona",
                              "cd_mun": "midia_mun"}))
        out = out.merge(m, on="mc", how="left")
    out["dia_recepcao"] = pd.to_datetime(out["primeira_recepcao"]).dt.date.astype(str)
    return out


def _dt_bu(s: Any) -> Optional[datetime]:
    try:
        return datetime.strptime(str(s), "%Y%m%dT%H%M%S")
    except (ValueError, TypeError):
        return None


def cruzar_bus(bus: pd.DataFrame, cargas: pd.DataFrame,
               estacoes: pd.DataFrame) -> pd.DataFrame:
    """Para cada seção com BU: o código de carga do BU está no GEDAI? E o número
    interno, a flash de carga, a estação geradora e a identificação batem?"""
    b = bus.copy()
    c = cargas.add_prefix("g_").rename(columns={"g_codigo_carga": "codigo_carga"})
    b = b.merge(c, on="codigo_carga", how="left")
    b["carga_no_gedai"] = b["g_tipo"].notna()
    no = b["carga_no_gedai"]

    def _cmp(x, y):
        return [None if not ok else bool(a == bb) for ok, a, bb in zip(no, x, y, strict=True)]

    b["urna_confere"] = _cmp(b["numero_interno_urna"], b["g_numero_interno_urna"])
    b["flash_confere"] = _cmp(b["ns_flash_carga"], b["g_mc"])
    tipo_esp = b["ident_carga_tipo"].map({"identificacaoSecaoEleitoral": "secao",
                                          "identificacaoContingencia": "contingencia"})
    b["tipo_confere"] = _cmp(tipo_esp, b["g_tipo"])
    b["mun_zona_confere"] = _cmp(
        b["ident_carga_mun"].fillna("") + b["ident_carga_zona"].fillna(""),
        b["g_cd_mun"].fillna("") + b["g_zona"].fillna(""))
    b["secao_confere"] = [
        None if not ok or t != "secao" else bool(s == gs)
        for ok, t, s, gs in zip(no, b["g_tipo"], b["ident_carga_secao"], b["g_secao"],
                                strict=True)]
    est = set(zip(estacoes["computador"], estacoes["serial_tpm"],
                  estacoes["serial_instalacao"], strict=True))
    nomes = set(estacoes["computador"])
    b["gerador_no_gedai"] = [
        (n, t, i) in est for n, t, i in zip(b["gerador_nome"], b["gerador_serial_tpm"],
                                            b["gerador_serial_instalacao"], strict=True)]
    b["gerador_nome_no_gedai"] = b["gerador_nome"].isin(nomes)
    b["gerador_igual_recepcao"] = _cmp(b["gerador_nome"], b["g_computador_recepcao"])
    codigos = set(cargas["codigo_carga"])
    hist = b["historico_codigos_carga"].fillna("").str.split()
    b["historico_fora_gedai"] = [" ".join(x for x in h if x not in codigos) for h in hist]
    b["n_historico_fora_gedai"] = [len(x.split()) for x in b["historico_fora_gedai"]]
    dtc = b["data_hora_carga"].map(_dt_bu)
    b["dia_carga_bu"] = [None if d is None else d.date().isoformat() for d in dtc]
    rec = pd.to_datetime(b["g_primeira_recepcao"])
    b["minutos_carga_ate_recepcao"] = [
        None if d is None or pd.isna(r) else round((r - d).total_seconds() / 60, 1)
        for d, r in zip(dtc, rec, strict=True)]
    return b


def cargas_sem_bu(cargas: pd.DataFrame, bus: pd.DataFrame) -> pd.DataFrame:
    """Cargas de seção do GEDAI cujo código não aparece em nenhum BU coletado,
    separadas pelo que se sabe da seção."""
    usados = set(bus["codigo_carga"].dropna())
    hist = set(x for h in bus["historico_codigos_carga"].fillna("") for x in h.split())
    sec_bu = set(zip(bus["cd_mun"], bus["zona"], bus["secao"], strict=True))
    cs = cargas[cargas["tipo"] == "secao"].copy()
    cs["no_bu"] = cs["codigo_carga"].isin(usados)
    cs["no_historico_bu"] = cs["codigo_carga"].isin(hist)
    cs["secao_tem_bu"] = [(m, z, s) in sec_bu for m, z, s in
                          zip(cs["cd_mun"], cs["zona"], cs["secao"], strict=True)]

    def _cls(r):
        if r.no_bu:
            return "usada_no_bu"
        if r.no_historico_bu:
            return "no_historico_do_bu"
        if r.secao_tem_bu:
            return "secao_com_bu_de_outra_carga"
        return "secao_sem_bu_coletado"

    cs["situacao"] = [_cls(r) for r in cs.itertuples()]
    return cs


def _jsonavel(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, float) and pd.isna(v):
        return None
    if isinstance(v, (pd.Timestamp, datetime)):
        return v.isoformat()
    if hasattr(v, "item"):
        try:
            return v.item()
        except (ValueError, AttributeError):
            return str(v)
    try:
        if pd.isna(v):
            return None
    except (TypeError, ValueError):
        pass
    return v


def _exemplos(df: pd.DataFrame, cols: list[str], n: int = MAX_EXEMPLOS) -> list[dict]:
    cols = [c for c in cols if c in df.columns]
    return [{c: _jsonavel(r[c]) for c in cols} for _, r in df.head(n).iterrows()]


def _contagem(s: pd.Series) -> dict:
    return {str(k): int(v) for k, v in s.value_counts(dropna=False).sort_index().items()}


COLS_EX = ["uf", "cd_mun", "zona", "secao", "tipo_urna", "codigo_carga",
           "numero_interno_urna", "data_hora_carga", "ns_flash_carga", "gerador_nome",
           "g_tipo", "g_cd_mun", "g_zona", "g_secao", "g_numero_interno_urna", "g_mc",
           "g_primeira_recepcao", "g_computador_recepcao", "minutos_apos_17h_bsb"]


def resumir_cruzamento(x: pd.DataFrame) -> dict:
    tot = int(len(x))
    no = x[x["carga_no_gedai"]]
    fora = x[~x["carga_no_gedai"]]
    out: dict[str, Any] = {
        "secoes_com_bu": tot,
        "por_tipo_urna": _contagem(x["tipo_urna"]),
        "carga_no_gedai": int(len(no)),
        "carga_fora_gedai": int(len(fora)),
        "carga_fora_gedai_por_uf": _contagem(fora["uf"]),
        "carga_fora_gedai_por_tipo_urna": _contagem(fora["tipo_urna"]),
        "carga_fora_gedai_gerador_no_gedai": _contagem(fora["gerador_no_gedai"]),
        "exemplos_carga_fora_gedai": _exemplos(fora, COLS_EX),
    }
    for c in ("urna_confere", "flash_confere", "tipo_confere", "mun_zona_confere",
              "secao_confere", "gerador_igual_recepcao"):
        s = no[c].dropna()
        ruins = no[no[c] == False]  # noqa: E712
        out[c] = {"verificadas": int(len(s)), "conferem": int(s.sum()),
                  "nao_conferem": int((~s.astype(bool)).sum()),
                  "exemplos": _exemplos(ruins, COLS_EX, 15)}
    out["gerador_no_gedai"] = _contagem(x["gerador_no_gedai"])
    out["gerador_nome_no_gedai"] = _contagem(x["gerador_nome_no_gedai"])
    ger_fora = x[~x["gerador_nome_no_gedai"]]
    out["geradores_fora_gedai"] = _contagem(ger_fora["gerador_nome"])
    out["historico_com_codigo_fora_gedai"] = int((x["n_historico_fora_gedai"] > 0).sum())
    out["exemplos_historico_fora_gedai"] = _exemplos(
        x[x["n_historico_fora_gedai"] > 0], ["uf", "cd_mun", "zona", "secao", "tipo_urna",
                                              "historico_codigos_carga",
                                              "historico_fora_gedai"], 15)
    res = x[x["tipo_urna"] == "reservaSecao"]
    out["reserva_secao_origem_contingencia"] = {
        "n": int(len(res)),
        "mesmo_municipio_e_zona": int(((res["ident_carga_mun"] == res["cd_mun"])
                                       & (res["ident_carga_zona"] == res["zona"])).sum()),
        "mesma_zona": int((res["ident_carga_zona"] == res["zona"]).sum()),
    }
    out["dia_carga_bu"] = _contagem(x["dia_carga_bu"])
    out["dia_carga_bu_por_tipo_urna"] = {
        str(t): _contagem(g["dia_carga_bu"]) for t, g in x.groupby("tipo_urna")}
    m = no["minutos_carga_ate_recepcao"].dropna()
    out["minutos_carga_ate_recepcao"] = {
        "n": int(len(m)),
        "negativos": int((m < 0).sum()),
        "mediana": None if m.empty else float(m.median()),
        "p95": None if m.empty else float(m.quantile(0.95)),
        "acima_de_7_dias": int((m > 7 * 1440).sum()),
        "exemplos_negativos": _exemplos(no[no["minutos_carga_ate_recepcao"] < 0],
                                        COLS_EX + ["minutos_carga_ate_recepcao"], 15),
    }
    return out


def resumir_recorte(x: pd.DataFrame, cs: pd.DataFrame) -> dict:
    """Resumo compacto para um subconjunto de seções (município ou seções tardias)."""
    return {
        "secoes_com_bu": int(len(x)),
        "por_tipo_urna": _contagem(x["tipo_urna"]),
        "carga_no_gedai": int(x["carga_no_gedai"].sum()),
        "carga_fora_gedai": int((~x["carga_no_gedai"]).sum()),
        "urna_nao_confere": int((x["urna_confere"] == False).sum()),  # noqa: E712
        "flash_nao_confere": int((x["flash_confere"] == False).sum()),  # noqa: E712
        "dia_carga_bu": _contagem(x["dia_carga_bu"]),
        "dia_recepcao_gedai": _contagem(x["g_dia_recepcao"]),
        "carga_em_outubro": int(x["dia_carga_bu"].fillna("").str.startswith("2026-10").sum()),
        "exemplos_carga_outubro": _exemplos(
            x[x["dia_carga_bu"].fillna("").str.startswith("2026-10")], COLS_EX, 40),
        "exemplos_fora_gedai": _exemplos(x[~x["carga_no_gedai"]], COLS_EX, 20),
        "cargas_gedai_secao_situacao": _contagem(cs["situacao"]) if len(cs) else {},
    }


def etapa_cruzar(saida: Path, encerramento: Optional[Path]) -> dict:
    corr = pd.read_parquet(saida / "correspondencias.parquet")
    midias = pd.read_parquet(saida / "midias_carga.parquet")
    arquivos = pd.read_parquet(saida / "arquivos.parquet")
    eventos = pd.read_parquet(saida / "eventos_dia.parquet")
    diff = pd.read_parquet(saida / "diff_versoes.parquet")
    bus = pd.read_parquet(saida / "bus_carga.parquet")
    bus = bus[bus["bu_erro"].isna()].copy()

    corr_u = deduplicar_correspondencias(corr)
    corr_u.to_parquet(saida / "correspondencias_unicas.parquet", index=False)
    midias_u = midias.sort_values("data_hora").drop_duplicates(
        ["computador", "serial_tpm", "serial_instalacao", "data_hora", "ns", "hash_linha"])
    cargas = resumir_cargas_gedai(corr_u, midias_u)
    cargas.to_parquet(saida / "cargas_gedai.parquet", index=False)
    estacoes = arquivos[["computador", "serial_tpm", "serial_instalacao"]].dropna(
    ).drop_duplicates()

    x = cruzar_bus(bus, cargas, estacoes)
    if encerramento is not None and Path(encerramento).expanduser().exists():
        enc = pd.read_parquet(Path(encerramento).expanduser(),
                              columns=CHAVE + ["minutos_apos_17h_bsb", "encerramento_bsb"])
        x = x.merge(enc.drop_duplicates(CHAVE), on=CHAVE, how="left")
    else:
        x["minutos_apos_17h_bsb"] = None
        x["encerramento_bsb"] = None
    x.to_parquet(saida / "cruzamento_bus.parquet", index=False)
    cs = cargas_sem_bu(cargas, bus)
    cs.to_parquet(saida / "cargas_gedai_secao.parquet", index=False)

    # contagens do GEDAI por dia
    rec = corr_u[corr_u["acao"] == "recebida"].copy()
    rec["dia"] = rec["data_hora"].dt.date.astype(str)
    rec_dia = rec.groupby(["dia", "tipo"]).size().unstack(fill_value=0)
    out_dia = {d: {k: int(v) for k, v in r.items()} for d, r in rec_dia.iterrows()}
    mid_dia = _contagem(midias_u["data_hora"].dt.date.astype(str))
    ult = corr_u["data_hora"].max()
    tarde = corr_u[(corr_u["data_hora"] >= datetime(2026, 10, 25, 17))]
    dias_alvo = ("2026-10-24", "2026-10-25")
    rec_alvo = rec[rec["dia"].isin(dias_alvo)]
    rec_alvo_uf = {d: _contagem(g["uf"]) for d, g in rec_alvo.groupby("dia")}
    cargas_alvo = cargas[cargas["dia_recepcao"].isin(dias_alvo)]
    usados = set(bus["codigo_carga"].dropna())
    tipo_bu = bus.set_index("codigo_carga")["tipo_urna"].to_dict()
    cargas_alvo = cargas_alvo.assign(
        no_bu=cargas_alvo["codigo_carga"].isin(usados),
        tipo_urna_bu=cargas_alvo["codigo_carga"].map(tipo_bu))
    cargas_alvo.to_parquet(saida / "cargas_gedai_24_25.parquet", index=False)

    ev = eventos.copy()
    todos = (ev.groupby(["pacote", "dia"])["n"].sum().reset_index())
    eventos_2510 = ev[ev["dia"] == "2026-10-25"].groupby(["pacote", "tipo_evento"])["n"].sum()

    # diff de versões
    dsum: dict[str, Any] = {}
    for rot, g in (diff.groupby("comparacao") if "comparacao" in diff else []):
        est = g.drop_duplicates(["uf", "computador", "serial_tpm", "serial_instalacao"])
        novas = g[g["n"] > 0]
        dsum[rot] = {
            "estacoes": int(len(est)),
            "status": _contagem(est["status"]),
            "linhas_novas": int(novas["n"].sum()),
            "linhas_novas_por_dia": {str(k): int(v) for k, v in
                                     novas.groupby("dia")["n"].sum().items()},
            "linhas_novas_apos_17h_2510": int(novas.loc[novas["apos_17h_2510"], "n"].sum()),
            "linhas_novas_por_tipo": {str(k): int(v) for k, v in
                                      novas.groupby("tipo_evento")["n"].sum()
                                      .sort_values(ascending=False).head(40).items()},
            "linhas_novas_24_25_por_tipo": {
                d: {str(k): int(v) for k, v in gg.groupby("tipo_evento")["n"].sum()
                    .sort_values(ascending=False).head(25).items()}
                for d, gg in novas[novas["dia"].isin(dias_alvo)].groupby("dia")},
            "linhas_novas_por_uf": {str(k): int(v) for k, v in
                                    novas.groupby("uf")["n"].sum().items()},
            "estacoes_divergentes": _exemplos(
                est[est["status"] == "divergente"],
                ["uf", "computador", "linhas_removidas"], 20),
            "estacoes_so_novo": _exemplos(est[est["status"] == "so_novo"],
                                          ["uf", "computador"], 60),
            "estacoes_so_antigo": _exemplos(est[est["status"] == "so_antigo"],
                                            ["uf", "computador"], 60),
        }

    tardias = x[x["minutos_apos_17h_bsb"].fillna(-1e9) > CORTE_TARDIA_MIN]
    destaque = {}
    for cod, nome in MUNICIPIOS_DESTAQUE.items():
        xm = x[(x["uf"] == "ba") & (x["cd_mun"] == cod)]
        cm = cs[(cs["uf"] == "ba") & (cs["cd_mun"] == cod)]
        r = resumir_recorte(xm, cm)
        r["tardias"] = resumir_recorte(xm[xm["minutos_apos_17h_bsb"].fillna(-1e9) >
                                          CORTE_TARDIA_MIN], cm.iloc[0:0])
        rm = rec[(rec["uf"] == "ba") & (rec["cd_mun"] == cod)]
        r["recepcoes_gedai_por_dia"] = _contagem(rm["dia"])
        destaque[f"{cod} {nome}"] = r

    resumo = {
        "gerado_em": datetime.now().astimezone().isoformat(timespec="seconds"),
        "pacotes": sorted(arquivos["pacote"].unique().tolist()),
        "logs_por_pacote": {str(k): int(v) for k, v in
                            arquivos.groupby("pacote").size().items()},
        "estacoes_distintas": int(len(estacoes)),
        "arquivos_com_erro": int(arquivos["erro"].notna().sum()),
        "entrada_dt_por_pacote": {str(k): sorted({str(v) for v in g["entrada_dt"]})[:5]
                                  for k, g in arquivos.groupby("pacote")},
        "interno_dt_max_por_pacote": {str(k): str(g["interno_dt"].max())
                                      for k, g in arquivos.groupby("pacote")},
        "comentarios_entrada": int(arquivos["entrada_comentario"].notna().sum()),
        "eventos_por_pacote": {str(k): int(v) for k, v in
                               todos.groupby("pacote")["n"].sum().items()},
        "eventos_2510_por_pacote_tipo": {f"{a}|{b}": int(v)
                                         for (a, b), v in eventos_2510.items()},
        "correspondencias_eventos": int(len(corr)),
        "correspondencias_unicas": int(len(corr_u)),
        "correspondencias_por_acao_tipo": {f"{a}|{t}": int(v) for (a, t), v in
                                           corr_u.groupby(["acao", "tipo"]).size().items()},
        "codigos_carga_gedai": int(len(cargas)),
        "codigos_carga_gedai_por_tipo": _contagem(cargas["tipo"]),
        "codigos_carga_com_mais_de_uma_urna": int((cargas["n_urnas_distintas"] > 1).sum()),
        "recepcoes_por_dia": out_dia,
        "midias_carga_por_dia": mid_dia,
        "recepcoes_24_25_por_uf": rec_alvo_uf,
        "cargas_recebidas_24_25": {
            d: {"n": int(len(g)), "por_tipo": _contagem(g["tipo"]),
                "usadas_em_bu": int(g["no_bu"].sum()),
                "tipo_urna_bu": _contagem(g["tipo_urna_bu"]),
                "por_uf": _contagem(g["uf"]),
                "exemplos": _exemplos(g.sort_values("primeira_recepcao"),
                                      ["uf", "cd_mun", "zona", "secao", "tipo",
                                       "codigo_carga", "numero_interno_urna", "mc",
                                       "primeira_recepcao", "computador_recepcao",
                                       "midia_gerada_em", "no_bu", "tipo_urna_bu"], 60)}
            for d, g in cargas_alvo.groupby("dia_recepcao")},
        "ultimo_evento_correspondencia": None if pd.isna(ult) else ult.isoformat(),
        "correspondencias_apos_17h_2510": int(len(tarde)),
        "cruzamento": resumir_cruzamento(x),
        "cargas_gedai_secao_situacao": _contagem(cs["situacao"]),
        "cargas_gedai_secao_situacao_por_uf": {
            str(u): _contagem(g["situacao"]) for u, g in cs.groupby("uf")},
        "tardias": resumir_recorte(tardias, cs.iloc[0:0]),
        "municipios_destaque": destaque,
        "diff_versoes": dsum,
    }
    (saida / "resumo.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=1,
                                                  default=str))
    return {"secoes_cruzadas": int(len(x)),
            "carga_fora_gedai": int((~x["carga_no_gedai"]).sum())}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("etapa", choices=["extrair", "bus", "cruzar", "tudo"])
    ap.add_argument("--gedai", nargs="+", type=Path, default=[],
                    help="diretórios (ou zips) com log_gedai_*.zip")
    ap.add_argument("--bus", nargs="+", type=Path, default=[],
                    help="diretórios com versoes-*.parquet do coletor")
    ap.add_argument("--encerramento", type=Path, default=None,
                    help="secoes_encerramento.parquet (minutos_apos_17h_bsb)")
    ap.add_argument("--saida", type=Path, required=True)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    a = ap.parse_args(argv)
    saida = a.saida.expanduser()
    t0 = time.time()
    if a.etapa in ("extrair", "tudo"):
        print("extrair:", etapa_extrair(a.gedai, saida, a.workers), flush=True)
    if a.etapa in ("bus", "tudo"):
        print("bus:", etapa_bus(a.bus, saida, a.workers), flush=True)
    if a.etapa in ("cruzar", "tudo"):
        print("cruzar:", etapa_cruzar(saida, a.encerramento), flush=True)
    print(f"concluído em {time.time() - t0:.0f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
