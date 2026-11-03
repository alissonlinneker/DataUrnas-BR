#!/usr/bin/env python3
"""Carregador incremental das versões do 2º turno de 2026 para o ClickHouse.

Lê as pastas de coleta (partes Parquet de versões de arquivo, índice de totais e
alertas), decodifica os BUs em paralelo e insere em lote nas tabelas descritas em
scripts/ch/schema.sql. Roda no servidor de processamento, em laço:

    python scripts/ch/carregar.py --loop 300

Garantias
* Incremental: a tabela cargas_arquivos registra cada parte já carregada
  (caminho, tamanho, mtime, SHA-256). Parte nova ou alterada é lida; as demais
  não. JSONL (indice.jsonl, alertas.jsonl) é lido a partir do último deslocamento.
* Tolerante a escrita em andamento: ignora *.tmp, arquivos ocultos (rsync) e
  arquivos modificados há menos de --idade-minima segundos; de JSONL só lê até a
  última quebra de linha.
* Idempotente: os dados entram antes do registro da carga e todas as tabelas
  deduplicam pela chave (ReplacingMergeTree). Repetir uma carga não duplica nada
  nas consultas com FINAL.
* Não escreve nas pastas de coleta: só lê.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from multiprocessing import get_context
from pathlib import Path
from typing import Any, Iterable, Optional, Protocol

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

log = logging.getLogger("carregar_ch")

UTC = timezone.utc
BRT = timezone(timedelta(hours=-3))  # Brasília, sem horário de verão desde 2019
ELEICAO_T2 = 6258
CARGO_PRESIDENTE = 1
DB = "dataurnas"
EPOCA_MAX = 10**10  # prioridade = EPOCA_MAX - epoch: coleta mais antiga vence

# Pastas de coleta padrão no servidor (relativas ao HOME). Os padrões com * pegam
# coletores novos sem mudar o carregador.
PADROES_ORIGEM = (
    "dataurnas-versoes-t2*",
    "dataurnas-mac/versoes/2026/t2*",
)

COLUNAS: dict[str, list[str]] = {
    "versoes_arquivo": [
        "uf", "cd_mun", "zona", "secao", "tipo", "sha512", "md5", "tamanho", "hash",
        "nome", "st_secao", "st_hash", "dt_recebimento", "hr_recebimento",
        "recebimento", "modelo_urna_cod", "coletado_em", "origem", "lote", "prioridade",
    ],
    "arquivos_conteudo": ["sha512", "tipo", "tamanho", "md5", "conteudo"],
    "aux_versoes": [
        "uf", "cd_mun", "zona", "secao", "sha512_aux", "coletado_em", "gerado_em",
        "fase", "st_secao", "n_hashes", "idx_hash", "hash", "st_hash",
        "dt_recebimento", "hr_recebimento", "recebimento", "arquivos", "origem",
    ],
    "bu_secao": [
        "uf", "cd_mun", "zona", "secao", "sha512", "tipo_arquivo", "hash", "st_hash",
        "st_secao", "recebimento", "coletado_em", "origem", "erro", "spec_version",
        "municipio_bu", "zona_bu", "secao_bu", "local_votacao", "data_hora_emissao",
        "hora_abertura", "hora_encerramento", "tipo_urna", "versao_votacao",
        "numero_interno_urna", "codigo_carga", "qtd_codigos_carga", "fase", "aptos",
        "aptos_secao", "aptos_tte", "comparecimento", "comparecimento_bu",
        "comp_sem_biometria", "habilitados_biometria", "habilitados_biografia",
        "votos_nominais", "votos_legenda", "votos_brancos", "votos_nulos",
        "votos_total", "tem_presidente",
    ],
    "bu_votos": [
        "uf", "cd_mun", "zona", "secao", "sha512_bu", "tipo_voto", "numero",
        "partido", "votos",
    ],
    "totais_versoes": [
        "abr", "nivel", "uf", "cd_mun", "sha256", "coletado_em", "dg", "hg",
        "totalizado_em", "idg", "st", "ts", "tv", "vb", "tvn", "cand", "origem",
    ],
    "alertas": ["origem", "sha256", "em", "tipo", "secao", "dados"],
    "cargas_arquivos": [
        "caminho", "origem", "tipo_fonte", "tamanho", "mtime", "sha256",
        "deslocamento", "linhas", "status", "erro", "carregado_em",
    ],
}

# Ordem de inserção: dados antes do registro da carga.
TABELAS_DADOS = ("versoes_arquivo", "arquivos_conteudo", "aux_versoes", "bu_secao",
                 "bu_votos", "totais_versoes", "alertas")


# ---------------------------------------------------------------------------
# Conversões
# ---------------------------------------------------------------------------

def txt(x: Any) -> str:
    return "" if x is None else str(x)


def inteiro(x: Any) -> Optional[int]:
    if x is None or x == "":
        return None
    try:
        return int(x)
    except (TypeError, ValueError):
        return None


def dt_coleta(s: Optional[str]) -> Optional[datetime]:
    """'2026-10-26T00:25:38+0000' -> datetime com fuso."""
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S%z")
    except ValueError:
        try:
            d = datetime.fromisoformat(s)
        except ValueError:
            return None
        return d if d.tzinfo else d.replace(tzinfo=UTC)


def dt_brt(data: Optional[str], hora: Optional[str]) -> Optional[datetime]:
    """'25/10/2026' + '21:07:27' (horário de Brasília) -> datetime com fuso."""
    if not data or not hora:
        return None
    try:
        return datetime.strptime(f"{data} {hora}", "%d/%m/%Y %H:%M:%S").replace(tzinfo=BRT)
    except ValueError:
        return None


def dt_urna(s: Optional[str]) -> Optional[datetime]:
    """'20261025T170512' (relógio da urna) -> datetime marcado como UTC, sem
    conversão: no banco o valor mostrado é o horário local da urna."""
    if not s:
        return None
    try:
        return datetime.strptime(str(s), "%Y%m%dT%H%M%S").replace(tzinfo=UTC)
    except ValueError:
        return None


def prioridade(coletado: Optional[datetime]) -> int:
    if coletado is None:
        return 0
    return max(0, EPOCA_MAX - int(coletado.timestamp()))


def nivel_abr(abr: str) -> tuple[str, str, str]:
    """'br' -> (br, '', ''); 'sp' -> (uf, sp, ''); 'sp71072' -> (municipio, sp, 71072)."""
    a = abr.lower()
    if a == "br":
        return "br", "", ""
    if len(a) == 2:
        return "uf", a, ""
    return "municipio", a[:2], a[2:]


def sha256_arquivo(caminho: Path, bloco: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(caminho, "rb") as fh:
        while True:
            b = fh.read(bloco)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Transformação de uma parte de versões (roda no pool)
# ---------------------------------------------------------------------------

def linhas_aux(ident: dict, sha512: str, conteudo: bytes, coletado: datetime,
               origem: str) -> list[tuple]:
    try:
        aux = json.loads(conteudo)
    except (ValueError, UnicodeDecodeError):
        aux = {}
    if not isinstance(aux, dict):
        aux = {}
    hashes = [h for h in (aux.get("hashes") or []) if isinstance(h, dict)]
    base = (ident["uf"], ident["cd_mun"], ident["zona"], ident["secao"], sha512, coletado,
            dt_brt(aux.get("dg"), aux.get("hg")), txt(aux.get("f")), txt(aux.get("st")),
            len(hashes))
    if not hashes:
        return [base + (0, "", "", "", "", None, [], origem)]
    out = []
    for i, h in enumerate(hashes, start=1):
        arqs = [f"{a.get('tp', '')}:{a.get('nm', '')}" for a in h.get("arq") or []
                if isinstance(a, dict)]
        out.append(base + (i, txt(h.get("hash")), txt(h.get("st")), txt(h.get("dr")),
                           txt(h.get("hr")), dt_brt(h.get("dr"), h.get("hr")), arqs,
                           origem))
    return out


def linhas_bu(r: dict, coletado: datetime, origem: str, eleicao: int, cargo: int
              ) -> tuple[tuple, list[tuple]]:
    """Linha de bu_secao e linhas de bu_votos de uma versão de BU."""
    from dataurnas.downloader.ele2026 import bu_to_rows

    erro = ""
    try:
        sec, votos = bu_to_rows(r["conteudo"], eleicao, cargo)
    except Exception as e:  # BU ilegível vira linha com erro, não derruba a carga
        sec, votos, erro = {}, [], f"{type(e).__name__}: {e}"[:500]
    ident = (r["uf"], r["cd_mun"], r["zona"], r["secao"])
    linha = ident + (
        r["sha512"], txt(r["tipo"]), txt(r.get("hash")), txt(r.get("st_hash")),
        txt(r.get("st_secao")), dt_brt(r.get("dt_recebimento"), r.get("hr_recebimento")),
        coletado, origem, erro, txt(sec.get("spec_version")),
        inteiro(sec.get("municipio_bu")), inteiro(sec.get("zona_bu")),
        inteiro(sec.get("secao_bu")), inteiro(sec.get("local_votacao")),
        dt_urna(sec.get("data_hora_emissao")), dt_urna(sec.get("hora_abertura")),
        dt_urna(sec.get("hora_encerramento")), txt(sec.get("tipo_urna")),
        txt(sec.get("versao_votacao")), inteiro(sec.get("numero_interno_urna")),
        txt(sec.get("codigo_carga")), inteiro(sec.get("qtd_codigos_carga")) or 0,
        txt(sec.get("fase")), inteiro(sec.get("aptos")), inteiro(sec.get("aptos_secao")),
        inteiro(sec.get("aptos_tte")), inteiro(sec.get("comparecimento")),
        inteiro(sec.get("comparecimento_bu")), inteiro(sec.get("comp_sem_biometria")),
        inteiro(sec.get("habilitados_biometria")), inteiro(sec.get("habilitados_biografia")),
        int(sec.get("votos_nominais") or 0), int(sec.get("votos_legenda") or 0),
        int(sec.get("votos_brancos") or 0), int(sec.get("votos_nulos") or 0),
        int(sec.get("votos_total") or 0), bool(sec.get("tem_presidente")),
    )
    lv = [ident + (r["sha512"], txt(v["tipo_voto"]), inteiro(v.get("numero")) or 0,
                   inteiro(v.get("partido")), int(v.get("votos") or 0))
          for v in votos]
    return linha, lv


def processar_versoes(caminho: str, origem: str, eleicao: int = ELEICAO_T2,
                      cargo: int = CARGO_PRESIDENTE) -> dict[str, list[tuple]]:
    """Lê uma parte versoes-*.parquet e devolve as linhas de cada tabela."""
    import pyarrow.parquet as pq

    from dataurnas.downloader.ele2026 import modelo_from_vsc

    lote = Path(caminho).stem.removeprefix("versoes-")
    out: dict[str, list[tuple]] = {t: [] for t in
                                   ("versoes_arquivo", "arquivos_conteudo", "aux_versoes",
                                    "bu_secao", "bu_votos")}
    for r in pq.read_table(caminho).to_pylist():
        conteudo = r.get("conteudo") or b""
        sha512 = r.get("sha512") or hashlib.sha512(conteudo).hexdigest()
        r["sha512"] = sha512
        md5 = hashlib.md5(conteudo).hexdigest()
        tipo = txt(r.get("tipo"))
        coletado = dt_coleta(r.get("coletado_em")) or datetime.fromtimestamp(0, UTC)
        modelo = modelo_from_vsc(conteudo) if tipo in ("vota", "sa") else None
        ident = {k: txt(r.get(k)) for k in ("uf", "cd_mun", "zona", "secao")}
        r.update(ident)
        out["versoes_arquivo"].append((
            ident["uf"], ident["cd_mun"], ident["zona"], ident["secao"], tipo, sha512, md5,
            int(r.get("tamanho") or len(conteudo)), txt(r.get("hash")), txt(r.get("nome")),
            txt(r.get("st_secao")), txt(r.get("st_hash")), txt(r.get("dt_recebimento")),
            txt(r.get("hr_recebimento")),
            dt_brt(r.get("dt_recebimento"), r.get("hr_recebimento")), modelo, coletado,
            origem, lote, prioridade(coletado),
        ))
        out["arquivos_conteudo"].append((sha512, tipo, len(conteudo), md5, conteudo))
        if tipo == "aux":
            out["aux_versoes"].extend(linhas_aux(ident, sha512, conteudo, coletado, origem))
        elif tipo in ("bu", "busa"):
            linha, lv = linhas_bu(r, coletado, origem, eleicao, cargo)
            out["bu_secao"].append(linha)
            out["bu_votos"].extend(lv)
    return out


def _tarefa_versoes(args: tuple) -> tuple[str, Optional[dict], str]:
    caminho, origem, eleicao, cargo = args
    try:
        return caminho, processar_versoes(caminho, origem, eleicao, cargo), ""
    except Exception as e:
        return caminho, None, f"{type(e).__name__}: {e}"[:500]


# ---------------------------------------------------------------------------
# JSONL incremental (totais e alertas)
# ---------------------------------------------------------------------------

def ler_jsonl_novo(caminho: Path, deslocamento: int) -> tuple[list[bytes], int]:
    """Linhas completas a partir de `deslocamento`. Se o arquivo encolheu (foi
    reescrito), recomeça do zero; a deduplicação por SHA-256 evita repetição."""
    tam = caminho.stat().st_size
    if tam < deslocamento:
        deslocamento = 0
    with open(caminho, "rb") as fh:
        fh.seek(deslocamento)
        dados = fh.read(tam - deslocamento)
    fim = dados.rfind(b"\n")
    if fim < 0:
        return [], deslocamento
    completos = dados[:fim + 1]
    linhas = [ln for ln in completos.split(b"\n") if ln.strip()]
    return linhas, deslocamento + len(completos)


def linhas_totais(linhas: Iterable[bytes], origem: str) -> list[tuple]:
    out = []
    for ln in linhas:
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        abr = txt(r.get("abr")).lower()
        if not abr:
            continue
        nivel, uf, mun = nivel_abr(abr)
        cand = {str(k): int(v or 0) for k, v in (r.get("cand") or {}).items()}
        sha = r.get("sha256") or hashlib.sha256(ln).hexdigest()
        out.append((
            abr, nivel, uf, mun, sha,
            dt_coleta(r.get("coletado_em")) or datetime.fromtimestamp(0, UTC),
            txt(r.get("dg")), txt(r.get("hg")), dt_brt(r.get("dg"), r.get("hg")),
            inteiro(r.get("idg")) or 0, inteiro(r.get("st")), inteiro(r.get("ts")),
            inteiro(r.get("tv")), inteiro(r.get("vb")), inteiro(r.get("tvn")), cand, origem,
        ))
    return out


def linhas_alertas(linhas: Iterable[bytes], origem: str) -> list[tuple]:
    out = []
    for ln in linhas:
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if not isinstance(r, dict):
            continue
        out.append((origem, hashlib.sha256(ln.strip()).hexdigest(), dt_coleta(r.get("em")),
                    txt(r.get("tipo")), txt(r.get("secao")),
                    ln.decode("utf-8", "replace").strip()))
    return out


# ---------------------------------------------------------------------------
# Descoberta das fontes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Fonte:
    caminho: Path
    origem: str
    tipo_fonte: str  # versoes | totais | alertas
    tamanho: int
    mtime: float


@dataclass
class Registro:
    tamanho: int
    mtime: float
    sha256: str
    deslocamento: int
    status: str


def descobrir_origens(home: Path, padroes: Iterable[str] = PADROES_ORIGEM
                      ) -> dict[str, Path]:
    """Pastas de coleta (com bus/ ou totais/) -> nome da origem (caminho relativo)."""
    out: dict[str, Path] = {}
    for p in padroes:
        for d in sorted(home.glob(p)):
            if d.is_dir() and ((d / "bus").is_dir() or (d / "totais").is_dir()):
                out[str(d.relative_to(home))] = d
    return out


def _estavel(p: Path, agora: float, idade_minima: float) -> Optional[os.stat_result]:
    try:
        st = p.stat()
    except OSError:
        return None
    if agora - st.st_mtime < idade_minima:
        return None
    return st


def listar_fontes(origens: dict[str, Path], idade_minima: float = 10.0,
                  agora: Optional[float] = None) -> list[Fonte]:
    """Partes de versões (versoes-*.parquet), índice de totais e alertas.
    As partes votos-*.parquet não são lidas: os votos saem da decodificação do BU."""
    agora = time.time() if agora is None else agora
    out: list[Fonte] = []
    for origem, base in sorted(origens.items()):
        partes = base / "bus" / "parts"
        if partes.is_dir():
            for p in sorted(partes.glob("versoes-*.parquet")):
                if p.name.startswith("."):
                    continue
                st = _estavel(p, agora, idade_minima)
                if st and st.st_size > 0:
                    out.append(Fonte(p, origem, "versoes", st.st_size, st.st_mtime))
        for rel, tipo in (("totais/indice.jsonl", "totais"), ("alertas.jsonl", "alertas")):
            p = base / rel
            if p.is_file():
                st = p.stat()
                out.append(Fonte(p, origem, tipo, st.st_size, st.st_mtime))
    return out


def pendentes(fontes: list[Fonte], registro: dict[str, Registro]) -> list[Fonte]:
    out = []
    for f in fontes:
        r = registro.get(str(f.caminho))
        if f.tipo_fonte == "versoes":
            # parte com erro de leitura é tentada de novo a cada ciclo
            if (r is None or r.status == "erro" or r.tamanho != f.tamanho
                    or abs(r.mtime - f.mtime) > 1e-3):
                out.append(f)
        elif r is None or f.tamanho != r.deslocamento:
            out.append(f)
    return out


# ---------------------------------------------------------------------------
# Banco
# ---------------------------------------------------------------------------

class Banco(Protocol):
    def registro(self) -> dict[str, Registro]: ...
    def inserir(self, tabela: str, colunas: list[str], linhas: list[tuple]) -> None: ...


class BancoClickHouse:
    def __init__(self, host: str, porta: int, usuario: str, senha: str):
        import clickhouse_connect

        self.cli = clickhouse_connect.get_client(
            host=host, port=porta, username=usuario, password=senha, database=DB,
            compress="lz4", send_receive_timeout=600,
            settings={"async_insert": 0, "max_insert_block_size": 1_048_576})

    def registro(self) -> dict[str, Registro]:
        q = self.cli.query("SELECT caminho, tamanho, mtime, sha256, deslocamento, status "
                           "FROM cargas_arquivos FINAL")
        return {r[0]: Registro(int(r[1]), float(r[2]), r[3], int(r[4]), r[5])
                for r in q.result_rows}

    def inserir(self, tabela: str, colunas: list[str], linhas: list[tuple]) -> None:
        if linhas:
            self.cli.insert(tabela, linhas, column_names=colunas, database=DB)


# ---------------------------------------------------------------------------
# Ciclo de carga
# ---------------------------------------------------------------------------

@dataclass
class Acumulador:
    banco: Banco
    max_linhas: int = 400_000
    max_bytes: int = 768 << 20
    linhas: dict[str, list[tuple]] = field(default_factory=lambda: {t: [] for t in COLUNAS})
    n_linhas: int = 0
    n_bytes: int = 0
    inseridas: dict[str, int] = field(default_factory=dict)

    def adicionar(self, dados: dict[str, list[tuple]], cargas: list[tuple]) -> None:
        for t, ls in dados.items():
            self.linhas[t].extend(ls)
            self.n_linhas += len(ls)
            if t == "arquivos_conteudo":
                self.n_bytes += sum(len(x[4]) for x in ls)
        self.linhas["cargas_arquivos"].extend(cargas)
        if self.n_linhas >= self.max_linhas or self.n_bytes >= self.max_bytes:
            self.descarregar()

    def descarregar(self) -> None:
        for t in TABELAS_DADOS + ("cargas_arquivos",):
            ls = self.linhas[t]
            if ls:
                self.banco.inserir(t, COLUNAS[t], ls)
                self.inseridas[t] = self.inseridas.get(t, 0) + len(ls)
        self.linhas = {t: [] for t in COLUNAS}
        self.n_linhas = self.n_bytes = 0


def _carga(f: Fonte, sha: str, deslocamento: int, linhas: int, status: str = "ok",
           erro: str = "") -> tuple:
    return (str(f.caminho), f.origem, f.tipo_fonte, f.tamanho, f.mtime, sha, deslocamento,
            linhas, status, erro, datetime.now(UTC))


def ciclo(banco: Banco, origens: dict[str, Path], workers: int = 8,
          eleicao: int = ELEICAO_T2, cargo: int = CARGO_PRESIDENTE,
          idade_minima: float = 10.0, max_partes: int = 0) -> dict[str, Any]:
    """Uma passada: carrega o que é novo e devolve um resumo."""
    t0 = time.time()
    registro = banco.registro()
    fontes = listar_fontes(origens, idade_minima)
    pend = pendentes(fontes, registro)
    shas_ok = {r.sha256 for r in registro.values() if r.status == "ok" and r.sha256}
    acc = Acumulador(banco)
    resumo: dict[str, Any] = {"fontes": len(fontes), "pendentes": len(pend),
                              "partes_ok": 0, "partes_repetidas": 0, "partes_erro": 0,
                              "jsonl_linhas": 0}

    # JSONL primeiro: é leve e mantém os totais em dia mesmo durante uma carga longa
    for f in (x for x in pend if x.tipo_fonte != "versoes"):
        reg = registro.get(str(f.caminho))
        linhas, novo = ler_jsonl_novo(f.caminho, reg.deslocamento if reg else 0)
        conv = linhas_totais if f.tipo_fonte == "totais" else linhas_alertas
        dados = {"totais_versoes" if f.tipo_fonte == "totais" else "alertas":
                 conv(linhas, f.origem)}
        f2 = Fonte(f.caminho, f.origem, f.tipo_fonte, novo, f.mtime)
        acc.adicionar(dados, [_carga(f2, "", novo, len(linhas))])
        resumo["jsonl_linhas"] += len(linhas)

    partes = [x for x in pend if x.tipo_fonte == "versoes"]
    if max_partes:
        partes = partes[:max_partes]
    tarefas: list[tuple] = []
    por_caminho: dict[str, tuple[Fonte, str]] = {}
    for f in partes:
        sha = sha256_arquivo(f.caminho)
        if sha in shas_ok:  # mesma parte em outro caminho (cópia): só registra
            acc.adicionar({}, [_carga(f, sha, 0, 0, "repetida")])
            resumo["partes_repetidas"] += 1
            continue
        shas_ok.add(sha)
        por_caminho[str(f.caminho)] = (f, sha)
        tarefas.append((str(f.caminho), f.origem, eleicao, cargo))

    def receber(caminho: str, dados: Optional[dict], erro: str) -> None:
        f, sha = por_caminho[caminho]
        if dados is None:
            log.warning("parte %s: %s", caminho, erro)
            acc.adicionar({}, [_carga(f, sha, 0, 0, "erro", erro)])
            resumo["partes_erro"] += 1
            return
        n = len(dados.get("versoes_arquivo", []))
        acc.adicionar(dados, [_carga(f, sha, 0, n)])
        resumo["partes_ok"] += 1

    if tarefas:
        if workers <= 1 or len(tarefas) == 1:
            for t in tarefas:
                receber(*_tarefa_versoes(t))
        else:
            ctx = get_context("fork" if sys.platform.startswith("linux") else "spawn")
            with ctx.Pool(min(workers, len(tarefas))) as pool:
                for i, res in enumerate(pool.imap_unordered(_tarefa_versoes, tarefas), 1):
                    receber(*res)
                    if i % 50 == 0:
                        log.info("partes processadas: %d de %d", i, len(tarefas))
    acc.descarregar()
    resumo["inseridas"] = acc.inseridas
    resumo["segundos"] = round(time.time() - t0, 1)
    return resumo


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _origens_cli(valores: list[str], home: Path) -> dict[str, Path]:
    if not valores:
        return descobrir_origens(home)
    out = {}
    for v in valores:
        nome, _, caminho = v.partition("=")
        if not caminho:
            raise SystemExit(f"--origem espera nome=caminho, recebeu {v!r}")
        out[nome] = Path(caminho).expanduser()
    return out


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--porta", type=int, default=18123)
    ap.add_argument("--usuario", default="dataurnas")
    ap.add_argument("--senha-arquivo", default="~/dataurnas-ch/.senha")
    ap.add_argument("--origem", action="append", default=[],
                    help="nome=caminho (repetível); sem isso, descobre as pastas padrão")
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    ap.add_argument("--eleicao", type=int, default=ELEICAO_T2)
    ap.add_argument("--idade-minima", type=float, default=10.0,
                    help="ignora partes modificadas há menos de N segundos")
    ap.add_argument("--max-partes", type=int, default=0, help="limite por ciclo (0 = todas)")
    ap.add_argument("--loop", type=float, default=0, help="repete a cada N segundos")
    ap.add_argument("--trava", default="~/dataurnas-ch/carregador.lock")
    ap.add_argument("--estado", default="~/dataurnas-ch/carregador-estado.json")
    a = ap.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    trava = open(Path(a.trava).expanduser(), "w")
    try:
        fcntl.flock(trava, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        log.error("outro carregador já está rodando (%s)", a.trava)
        return 3
    senha = Path(a.senha_arquivo).expanduser().read_text().strip()
    banco = BancoClickHouse(a.host, a.porta, a.usuario, senha)
    home = Path.home()
    while True:
        origens = _origens_cli(a.origem, home)
        try:
            r = ciclo(banco, origens, a.workers, a.eleicao, CARGO_PRESIDENTE,
                      a.idade_minima, a.max_partes)
            r["origens"] = sorted(origens)
            r["fim"] = datetime.now(UTC).isoformat(timespec="seconds")
            log.info("ciclo: %s", json.dumps(r, ensure_ascii=False))
            try:
                Path(a.estado).expanduser().write_text(json.dumps(r, ensure_ascii=False))
            except OSError:
                pass
        except Exception:
            if not a.loop:
                raise
            log.exception("ciclo falhou; nova tentativa no próximo intervalo")
        if not a.loop:
            return 0
        time.sleep(a.loop)


if __name__ == "__main__":
    sys.exit(main())
