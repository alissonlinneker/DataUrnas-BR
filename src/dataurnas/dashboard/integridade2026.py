"""Leitura da auditoria de integridade dos arquivos de urna de 2026.

Arquivos em ``data/parquet/2026/integridade`` (somente leitura), gerados pela
coleta de integridade, que roda por horas e grava aos poucos:

- ``arquivos_<uf>.parquet`` (SP pode vir dividido em ``arquivos_sp_*.parquet``):
  um registro por arquivo publicado da seção, com MD5, SHA-256 e SHA-512
  calculados, o SHA-512 assinado pela urna (quando o arquivo é coberto pela
  assinatura) e o resultado da comparação (``hash_confere``). Arquivo listado
  no aux.json e indisponível no servidor (HTTP 404) vem com ``disponivel``
  falso, ``http_status`` 404 e hashes nulos (catálogos antigos não têm essas
  colunas: todo arquivo listado foi baixado).
- ``secoes.parquet``: uma linha por seção, com contagens, validade da
  assinatura e dados do certificado.
- ``resumo.json``: totais e horários da coleta.
- ``catalogo_manifest.json``: nome, tamanho, SHA-256, linhas e colunas de cada
  ``arquivos_<uf>.parquet``. Os catálogos por arquivo não são versionados no
  git: são publicados como anexos de uma versão do projeto no GitHub. Quando o
  catálogo de uma UF não existe localmente, a consulta por seção e o CSV baixam
  só o daquela UF (``DATAURNAS_CATALOGO_URL``), conferem o SHA-256 contra o
  manifesto e guardam a cópia num cache em disco. Os indicadores agregados vêm
  só de ``secoes.parquet`` e ``resumo.json``.

Tudo aqui aceita dados parciais ou ausentes: arquivos ilegíveis (em gravação)
são ignorados e, se ``secoes.parquet`` ainda não existe, o resumo por seção é
derivado dos catálogos de arquivos. Nada depende do Streamlit.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import logging
import os
import tempfile
import threading
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import duckdb
import pandas as pd

from dataurnas.dashboard.data2026 import CHAVE_SECAO, UF_NOMES, _legivel, _sql_list, base_dir

logger = logging.getLogger("dataurnas.dashboard")

TIPOS_ASSINADOS = ("bu", "rdv", "log")
STATUS_SECAO = ("ok", "agregada", "nao_instalada", "sem_arquivos")
COLUNAS_SECAO = CHAVE_SECAO + [
    "status_secao", "n_arquivos", "n_hash_confere", "n_hash_diverge", "n_sem_hash",
    "assinatura_valida", "assinatura_algoritmo", "cert_subject", "cert_issuer", "cert_serial",
    "cert_sha256", "modelo_urna", "motivo", "votos_conferem", "n_indisponiveis",
]
COLUNAS_ARQUIVO = CHAVE_SECAO + [
    "tipo", "nome", "tamanho", "md5", "sha256", "sha512", "sha512_assinado", "hash_confere",
    "token_tse", "data_hora_tse", "disponivel", "http_status",
]
# Limite de linhas do catálogo exportado em CSV (acima disso, pedir filtro mais estreito)
LIMITE_CSV = 250_000

# Catálogo por arquivo publicado como anexos da versão do projeto no GitHub
CATALOGO_VERSAO = "v0.2.1"
CATALOGO_URL_PADRAO = (
    f"https://github.com/alissonlinneker/DataUrnas-BR/releases/download/{CATALOGO_VERSAO}"
)
CATALOGO_PAGINA = f"https://github.com/alissonlinneker/DataUrnas-BR/releases/tag/{CATALOGO_VERSAO}"
MANIFESTO = "catalogo_manifest.json"
LIMITE_DOWNLOAD_MB = 200  # maior anexo aceito (SP tem cerca de 78 MB)
LIMITE_CACHE_MB = 600  # acima disso, os catálogos usados há mais tempo saem do cache
TIMEOUT_DOWNLOAD = 30  # segundos sem resposta do servidor
_BLOCO = 1 << 20


def integ_dir(base: Path | None = None) -> Path:
    return (base or base_dir()) / "integridade"


def arquivos_parquet(pasta: Path | None = None, uf: str | None = None) -> list[Path]:
    """Catálogos de arquivos legíveis (todas as UFs ou só ``uf``, incluindo partes de SP)."""
    pasta = pasta or integ_dir()
    if not pasta.exists():
        return []
    if uf:
        uf = uf.lower()
        candidatos = list(pasta.glob(f"arquivos_{uf}.parquet")) + list(pasta.glob(f"arquivos_{uf}_*.parquet"))
    else:
        candidatos = list(pasta.glob("arquivos_*.parquet"))
    return sorted(p for p in candidatos if _legivel(p))


class CatalogoIndisponivel(RuntimeError):
    """O catálogo da UF não existe localmente e não pôde ser obtido (mensagem legível)."""


def _env_int(nome: str, padrao: int) -> int:
    try:
        return int(os.environ.get(nome, "") or padrao)
    except ValueError:
        return padrao


def load_manifesto(pasta: Path | None = None) -> dict:
    """``catalogo_manifest.json`` (vazio se ausente ou ilegível)."""
    path = (pasta or integ_dir()) / MANIFESTO
    if not path.exists():
        return {}
    try:
        dados = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        logger.info("Ignorando manifesto ilegível: %s", path)
        return {}
    return dados if isinstance(dados, dict) else {}


def entradas_manifesto(manifesto: dict, uf: str) -> list[dict]:
    """Entradas do manifesto da ``uf`` (SP pode ter várias partes)."""
    uf = uf.lower()
    out = []
    for e in manifesto.get("arquivos") or []:
        if not isinstance(e, dict) or not e.get("arquivo") or not e.get("sha256"):
            continue
        if str(e.get("uf", "")).lower() == uf:
            out.append(e)
    return sorted(out, key=lambda e: e["arquivo"])


def url_catalogo(arquivo: str) -> str:
    """URL do anexo. ``DATAURNAS_CATALOGO_URL`` é a base (ou um modelo com ``{arquivo}``)."""
    base = os.environ.get("DATAURNAS_CATALOGO_URL") or CATALOGO_URL_PADRAO
    if "{arquivo}" in base:
        return base.replace("{arquivo}", arquivo)
    return f"{base.rstrip('/')}/{arquivo}"


def cache_dir() -> Path:
    """Diretório do cache em disco (``DATAURNAS_CATALOGO_CACHE`` ou o temporário do sistema)."""
    env = os.environ.get("DATAURNAS_CATALOGO_CACHE")
    return Path(env) if env else Path(tempfile.gettempdir()) / "dataurnas-catalogo"


def _sha256_arquivo(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for bloco in iter(lambda: fh.read(_BLOCO), b""):
            h.update(bloco)
    return h.hexdigest()


def _abrir_url(url: str, timeout: float):
    """Resposta HTTP em streaming (ponto único de rede, substituído nos testes)."""
    req = urllib.request.Request(url, headers={"User-Agent": "DataUrnas-BR"})
    return urllib.request.urlopen(req, timeout=timeout)  # noqa: S310 (URL https fixa ou configurada)


_VERIFICADOS: set[tuple[str, int, int]] = set()
_TRAVAS: dict[str, threading.Lock] = {}
_TRAVA_GLOBAL = threading.Lock()


def _trava(nome: str) -> threading.Lock:
    with _TRAVA_GLOBAL:
        return _TRAVAS.setdefault(nome, threading.Lock())


def _confere_em_cache(path: Path, tamanho: int | None, sha256: str) -> bool:
    try:
        st_ = path.stat()
    except OSError:
        return False
    if tamanho is not None and st_.st_size != tamanho:
        return False
    chave = (str(path), st_.st_size, st_.st_mtime_ns)
    if chave in _VERIFICADOS:
        return True
    if _sha256_arquivo(path) != sha256:
        return False
    _VERIFICADOS.add(chave)
    return True


def _limpar_cache(pasta: Path, manter: Path, limite: int) -> None:
    """Remove os catálogos usados há mais tempo até o cache caber em ``limite`` bytes."""
    try:
        itens = [(p, p.stat()) for p in pasta.glob("*.parquet")]
    except OSError:
        return
    total = sum(st_.st_size for _, st_ in itens)
    for p, st_ in sorted(itens, key=lambda x: x[1].st_mtime):
        if total <= limite:
            break
        if p == manter:
            continue
        try:
            p.unlink()
            total -= st_.st_size
        except OSError:
            continue


def _baixar_catalogo(entrada: dict, uf: str) -> Path:
    arquivo = str(entrada["arquivo"])
    sha256 = str(entrada["sha256"]).lower()
    tamanho = entrada.get("tamanho")
    tamanho = int(tamanho) if tamanho is not None else None
    url = url_catalogo(arquivo)
    pasta = cache_dir()
    destino = pasta / f"{sha256[:16]}_{Path(arquivo).name}"
    limite = _env_int("DATAURNAS_CATALOGO_MAX_MB", LIMITE_DOWNLOAD_MB) << 20
    rotulo = uf.upper()
    if tamanho is not None and tamanho > limite:
        raise CatalogoIndisponivel(
            f"O catálogo de hashes de {rotulo} tem {tamanho >> 20} MB, acima do limite de "
            f"{limite >> 20} MB para download pelo painel. Baixe-o diretamente em {url}.")
    with _trava(destino.name):
        if _confere_em_cache(destino, tamanho, sha256):
            try:
                os.utime(destino)  # marca uso recente (ordem de limpeza do cache)
            except OSError:
                pass
            return destino
        try:
            pasta.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise CatalogoIndisponivel(
                f"Sem espaço de cache para o catálogo de hashes de {rotulo} ({exc.strerror or exc}).") from exc
        tmp = pasta / f".{destino.name}.{uuid.uuid4().hex}.part"
        timeout = _env_int("DATAURNAS_CATALOGO_TIMEOUT", TIMEOUT_DOWNLOAD)
        h = hashlib.sha256()
        lidos = 0
        maximo = tamanho if tamanho is not None else limite
        try:
            with _abrir_url(url, timeout) as resp, tmp.open("wb") as out:
                for bloco in iter(lambda: resp.read(_BLOCO), b""):
                    lidos += len(bloco)
                    if lidos > maximo:
                        raise CatalogoIndisponivel(
                            f"O catálogo de hashes de {rotulo} recebido é maior que o esperado; "
                            "o download foi interrompido.")
                    h.update(bloco)
                    out.write(bloco)
            if h.hexdigest() != sha256 or (tamanho is not None and lidos != tamanho):
                raise CatalogoIndisponivel(
                    f"O catálogo de hashes de {rotulo} baixado de {url} não confere com o SHA-256 do "
                    "manifesto (catalogo_manifest.json) e foi descartado.")
            os.replace(tmp, destino)
        except CatalogoIndisponivel:
            raise
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            motivo = getattr(exc, "reason", None) or getattr(exc, "code", None) or exc
            raise CatalogoIndisponivel(
                f"O catálogo de hashes de {rotulo} não está nesta instalação e não pôde ser baixado agora "
                f"({motivo}). Verifique a conexão e tente de novo, ou baixe o arquivo em {url}.") from exc
        finally:
            tmp.unlink(missing_ok=True)
        st_ = destino.stat()
        _VERIFICADOS.add((str(destino), st_.st_size, st_.st_mtime_ns))
        _limpar_cache(pasta, destino, _env_int("DATAURNAS_CATALOGO_CACHE_MB", LIMITE_CACHE_MB) << 20)
        logger.info("Catálogo %s baixado (%d bytes) para %s", arquivo, lidos, destino)
        return destino


def catalogo_local(uf: str, pasta: Path | None = None) -> bool:
    """True se o catálogo da ``uf`` está em ``pasta`` (sem precisar de download)."""
    return bool(arquivos_parquet(pasta, uf))


def tamanho_remoto(uf: str, pasta: Path | None = None) -> int:
    """Bytes a baixar para a ``uf`` segundo o manifesto (0 se não há o que baixar)."""
    return sum(int(e.get("tamanho") or 0) for e in entradas_manifesto(load_manifesto(pasta), uf))


def catalogo_uf(uf: str, pasta: Path | None = None, remoto: bool = True) -> list[Path]:
    """Catálogos da ``uf``: os locais e, sem eles, os anexos listados no manifesto.

    O download só acontece com manifesto (é ele que dá o SHA-256 a conferir).
    Levanta ``CatalogoIndisponivel`` com mensagem legível se a rede falhar.
    """
    locais = arquivos_parquet(pasta, uf)
    if locais or not remoto:
        return locais
    entradas = entradas_manifesto(load_manifesto(pasta), uf)
    return [_baixar_catalogo(e, uf) for e in entradas]


def contar_pelas_secoes(secoes: pd.DataFrame, uf: str, cd_mun: str | None = None,
                        apenas_divergentes: bool = False) -> int:
    """Arquivos de um filtro contados pelo resumo por seção (sem ler o catálogo)."""
    if secoes.empty:
        return 0
    s = secoes[secoes["uf"] == uf.lower()]
    if cd_mun:
        s = s[s["cd_mun"] == str(cd_mun)]
    col = "n_hash_diverge" if apenas_divergentes else "n_arquivos"
    return int(pd.to_numeric(s[col], errors="coerce").fillna(0).sum())


def files_signature(pasta: Path | None = None) -> tuple:
    """Assinatura (nome, tamanho, mtime) dos arquivos: muda a cada gravação da coleta."""
    pasta = pasta or integ_dir()
    if not pasta.exists():
        return ()
    sig = []
    for p in sorted(list(pasta.glob("*.parquet")) + list(pasta.glob("*.json"))):
        try:
            st_ = p.stat()
            sig.append((p.name, st_.st_size, int(st_.st_mtime)))
        except OSError:
            continue
    return tuple(sig)


def load_resumo(pasta: Path | None = None) -> dict:
    path = (pasta or integ_dir()) / "resumo.json"
    if not path.exists():
        return {}
    try:
        with path.open(encoding="utf-8") as fh:
            dados = json.load(fh)
        return dados if isinstance(dados, dict) else {}
    except (OSError, ValueError):
        logger.info("Ignorando resumo.json ilegível: %s", path)
        return {}


def horarios_coleta(resumo: dict) -> dict[str, str]:
    """Horários registrados no ``resumo.json`` (chaves com data/hora), sem supor um nome fixo."""
    out: dict[str, str] = {}

    def _visitar(d: dict, prefixo: str = "") -> None:
        for k, v in d.items():
            nome = f"{prefixo}{k}"
            if isinstance(v, dict) and k in {"timestamps", "horarios", "tempos"}:
                _visitar(v, f"{k}.")
            elif isinstance(v, str) and any(t in k.lower() for t in
                                             ("data", "hora", "inicio", "fim", "atualiz", "gerad", "timestamp")):
                out[nome] = v

    _visitar(resumo)
    return out


_ROTULOS_HORARIO = {"inicio": "início", "fim": "fim", "atualizado_em": "atualizado em",
                    "gerado_em": "gerado em", "data_hora": "data e hora", "timestamp": "registro"}


def rotulo_horario(chave: str) -> str:
    """Rótulo legível (com acento) para uma chave de horário do ``resumo.json``."""
    base = chave.split(".")[-1]
    return _ROTULOS_HORARIO.get(base.lower(), base.replace("_", " "))


def texto_horarios(resumo: dict) -> str:
    return "; ".join(f"{rotulo_horario(k)}: {v}" for k, v in horarios_coleta(resumo).items())


# ----------------------------------------------------------------------
# Resumo por seção
# ----------------------------------------------------------------------
@dataclass
class IntegridadeData:
    secoes: pd.DataFrame
    arquivos: list[Path] = field(default_factory=list)
    ignorados: int = 0
    origem: str = ""  # "secoes.parquet", "catalogo" ou ""

    @property
    def vazio(self) -> bool:
        return self.secoes.empty


def _normalizar_secoes(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in COLUNAS_SECAO:
        if c not in df.columns:
            df[c] = None
    for c in ("n_arquivos", "n_hash_confere", "n_hash_diverge", "n_sem_hash", "n_indisponiveis"):
        df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0).astype("int64")
    for c in ("assinatura_valida", "votos_conferem"):
        df[c] = df[c].astype("boolean")
    for c in CHAVE_SECAO:
        df[c] = df[c].astype(str)
    df["uf"] = df["uf"].str.lower()
    df["status_secao"] = df["status_secao"].fillna("ok").astype(str)
    return df.drop_duplicates(CHAVE_SECAO, keep="last").sort_values(CHAVE_SECAO).reset_index(drop=True)


def _secoes_do_catalogo(arquivos: list[Path]) -> pd.DataFrame:
    """Resumo por seção derivado dos catálogos (enquanto ``secoes.parquet`` não existe)."""
    con = duckdb.connect()
    try:
        return con.execute(f"""
            SELECT uf, cd_mun, zona, secao,
                   'ok' AS status_secao,
                   COUNT(*) AS n_arquivos,
                   COUNT(*) FILTER (WHERE hash_confere IS TRUE) AS n_hash_confere,
                   COUNT(*) FILTER (WHERE hash_confere IS FALSE) AS n_hash_diverge,
                   COUNT(*) FILTER (WHERE hash_confere IS NULL) AS n_sem_hash
            FROM read_parquet({_sql_list(arquivos)}, union_by_name = true)
            GROUP BY ALL
        """).fetchdf()
    finally:
        con.close()


def load_secoes(pasta: Path | None = None) -> IntegridadeData:
    """Resumo por seção; usa ``secoes.parquet`` e, se ausente, deriva dos catálogos."""
    pasta = pasta or integ_dir()
    if not pasta.exists():
        return IntegridadeData(pd.DataFrame(columns=COLUNAS_SECAO))
    todos = list(pasta.glob("arquivos_*.parquet"))
    arquivos = arquivos_parquet(pasta)
    path = pasta / "secoes.parquet"
    ignorados = len(todos) - len(arquivos)
    if path.exists():
        if _legivel(path):
            return IntegridadeData(_normalizar_secoes(pd.read_parquet(path)), arquivos, ignorados, "secoes.parquet")
        ignorados += 1
    if arquivos:
        return IntegridadeData(_normalizar_secoes(_secoes_do_catalogo(arquivos)), arquivos, ignorados, "catalogo")
    return IntegridadeData(pd.DataFrame(columns=COLUNAS_SECAO), arquivos, ignorados)


def _falso(valor) -> bool:
    """True só para False explícito (nulo = não verificado)."""
    return valor is not None and not pd.isna(valor) and not bool(valor)


def _divergente(df: pd.DataFrame) -> pd.Series:
    return ((df["n_hash_diverge"] > 0)
            | df["assinatura_valida"].eq(False).fillna(False)
            | df["votos_conferem"].eq(False).fillna(False)).astype(bool)


def totais(secoes: pd.DataFrame, res_uf: pd.DataFrame | None = None) -> dict:
    """Indicadores gerais. Cobertura = seções verificadas / seções instaladas (oficial)."""
    instaladas = int(res_uf["secoes_instaladas"].sum()) if res_uf is not None and not res_uf.empty else 0
    if secoes.empty:
        return {"secoes": 0, "verificadas": 0, "agregadas": 0, "nao_instaladas": 0, "sem_arquivos": 0,
                "arquivos": 0, "hash_confere": 0, "hash_diverge": 0, "sem_hash": 0,
                "assinaturas_validas": 0, "assinaturas_invalidas": 0, "assinaturas_nao_verificadas": 0,
                "votos_divergem": 0, "secoes_divergentes": 0, "instaladas": instaladas,
                "cobertura_pct": 0.0}
    ok = secoes[secoes["status_secao"] == "ok"]
    status = secoes["status_secao"].value_counts()
    verificadas = len(ok)
    return {
        "secoes": len(secoes),
        "verificadas": verificadas,
        "agregadas": int(status.get("agregada", 0)),
        "nao_instaladas": int(status.get("nao_instalada", 0)),
        "sem_arquivos": int(status.get("sem_arquivos", 0)),
        "arquivos": int(secoes["n_arquivos"].sum()),
        "hash_confere": int(secoes["n_hash_confere"].sum()),
        "hash_diverge": int(secoes["n_hash_diverge"].sum()),
        "sem_hash": int(secoes["n_sem_hash"].sum()),
        "assinaturas_validas": int(ok["assinatura_valida"].eq(True).fillna(False).sum()),
        "assinaturas_invalidas": int(ok["assinatura_valida"].eq(False).fillna(False).sum()),
        "assinaturas_nao_verificadas": int(ok["assinatura_valida"].isna().sum()),
        "votos_divergem": int(secoes["votos_conferem"].eq(False).fillna(False).sum()),
        "secoes_divergentes": int(_divergente(secoes).sum()),
        "instaladas": instaladas,
        "cobertura_pct": min(100.0, verificadas / instaladas * 100) if instaladas else 0.0,
    }


def por_uf(secoes: pd.DataFrame, res_uf: pd.DataFrame | None = None) -> pd.DataFrame:
    """Uma linha por UF (todas as do resultado oficial, mesmo sem dado ainda)."""
    cols = ["uf", "nome", "secoes_instaladas", "verificadas", "agregadas", "nao_instaladas", "sem_arquivos",
            "arquivos", "hash_confere", "hash_diverge", "sem_hash", "assinaturas_validas",
            "assinaturas_invalidas", "secoes_divergentes", "cobertura_pct", "completa"]
    if secoes.empty:
        agg = pd.DataFrame(columns=[c for c in cols if c not in {"nome", "secoes_instaladas", "cobertura_pct",
                                                               "completa"}])
    else:
        s = secoes.assign(
            _ok=secoes["status_secao"].eq("ok"),
            _agr=secoes["status_secao"].eq("agregada"),
            _ni=secoes["status_secao"].eq("nao_instalada"),
            _sa=secoes["status_secao"].eq("sem_arquivos"),
            _av=secoes["assinatura_valida"].eq(True).fillna(False),
            _ai=secoes["assinatura_valida"].eq(False).fillna(False),
            _dv=_divergente(secoes),
        )
        agg = s.groupby("uf").agg(
            verificadas=("_ok", "sum"), agregadas=("_agr", "sum"), nao_instaladas=("_ni", "sum"),
            sem_arquivos=("_sa", "sum"), arquivos=("n_arquivos", "sum"), hash_confere=("n_hash_confere", "sum"),
            hash_diverge=("n_hash_diverge", "sum"), sem_hash=("n_sem_hash", "sum"),
            assinaturas_validas=("_av", "sum"), assinaturas_invalidas=("_ai", "sum"),
            secoes_divergentes=("_dv", "sum"),
        ).reset_index()
    if res_uf is not None and not res_uf.empty:
        base = res_uf[["uf", "secoes_instaladas"]].copy()
        out = base.merge(agg, on="uf", how="outer")
    else:
        out = agg.copy()
        out["secoes_instaladas"] = pd.NA
    num = [c for c in cols if c not in {"uf", "nome", "cobertura_pct", "completa", "secoes_instaladas"}]
    for c in num:
        out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0).astype("int64")
    inst = pd.to_numeric(out["secoes_instaladas"], errors="coerce")
    out["cobertura_pct"] = (out["verificadas"] / inst.where(inst > 0) * 100).clip(upper=100).fillna(0.0)
    out["completa"] = inst.notna() & (out["verificadas"] >= inst)
    out["secoes_instaladas"] = inst.fillna(0).astype("int64")
    out["nome"] = out["uf"].map(UF_NOMES)
    return out[cols].sort_values("uf").reset_index(drop=True)


def divergencias(secoes: pd.DataFrame) -> pd.DataFrame:
    """Seções com hash divergente, assinatura inválida ou votos que não conferem."""
    if secoes.empty:
        return pd.DataFrame(columns=CHAVE_SECAO + ["problemas", "n_hash_diverge", "assinatura_valida",
                                                   "votos_conferem", "modelo_urna", "motivo"])
    d = secoes[_divergente(secoes)].copy()

    def _problemas(r) -> str:
        p = []
        if r["n_hash_diverge"] > 0:
            p.append(f"{int(r['n_hash_diverge'])} hash(es) divergente(s)")
        if _falso(r["assinatura_valida"]):
            p.append("assinatura inválida")
        if _falso(r["votos_conferem"]):
            p.append("votos não conferem")
        return "; ".join(p)

    d["problemas"] = d.apply(_problemas, axis=1) if not d.empty else pd.Series(dtype=str)
    return d[CHAVE_SECAO + ["problemas", "n_hash_diverge", "assinatura_valida", "votos_conferem",
                            "modelo_urna", "motivo"]].reset_index(drop=True)


# ----------------------------------------------------------------------
# Contagens para o resumo por grupo de leitura (reference.GRUPOS)
# ----------------------------------------------------------------------
# Categorias que só existem no divergencias.jsonl (as demais saem de ``totais``)
CATEGORIAS_SO_NO_JSONL = ("hash_assinado_ausente", "arquivo_ausente_tse")


def contar_divergencias(pasta: Path | None = None) -> dict[str, int]:
    """Divergências por categoria em ``divergencias.jsonl``, sem repetir.

    Usa a mesma chave de deduplicação do resumo da coleta. O arquivo é gravado
    durante a coleta: linhas incompletas ou ilegíveis são ignoradas.
    """
    path = (pasta or integ_dir()) / "divergencias.jsonl"
    if not path.exists():
        return {}
    vistos: set[tuple] = set()
    out: dict[str, int] = {}
    try:
        linhas = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return {}
    for ln in linhas:
        if not ln.strip():
            continue
        try:
            d = json.loads(ln)
        except ValueError:
            continue
        if not isinstance(d, dict) or not d.get("categoria"):
            continue
        k = (d.get("uf"), d.get("cd_mun"), d.get("zona"), d.get("secao"),
             d.get("arquivo"), d.get("categoria"), d.get("token_tse"))
        if k in vistos:
            continue
        vistos.add(k)
        out[d["categoria"]] = out.get(d["categoria"], 0) + 1
    return out


def contar_issues_auditoria(base: Path | None = None) -> dict[str, int]:
    """Ocorrências por código da auditoria por seção de 2026 (``auditoria/issues_2026.parquet``)."""
    path = (base or base_dir()) / "auditoria" / "issues_2026.parquet"
    if not path.exists() or not _legivel(path):
        return {}
    con = duckdb.connect()
    try:
        rows = con.execute(
            "SELECT codigo, COUNT(*) FROM read_parquet(?) GROUP BY codigo", [str(path)]
        ).fetchall()
    finally:
        con.close()
    return {str(c): int(n) for c, n in rows}


def contagens_2026(t: dict, pasta: Path | None = None, base: Path | None = None) -> dict[str, int]:
    """Totais por categoria de integridade e por código de inconsistência de 2026.

    ``t`` é o resultado de ``totais``: hashes divergentes (por arquivo), assinaturas
    inválidas e votos que não conferem (por seção) saem dele, para bater com os
    indicadores da página. As outras duas categorias vêm do ``divergencias.jsonl``.
    """
    out = {
        "hash_diverge": int(t.get("hash_diverge", 0)),
        "assinatura_invalida": int(t.get("assinaturas_invalidas", 0)),
        "votos_divergem": int(t.get("votos_divergem", 0)),
    }
    divs = contar_divergencias(pasta)
    for cat in CATEGORIAS_SO_NO_JSONL:
        out[cat] = int(divs.get(cat, 0))
    out.update(contar_issues_auditoria(base))
    return out


# ----------------------------------------------------------------------
# Consulta de uma seção e exportação do catálogo
# ----------------------------------------------------------------------
def _consulta_arquivos(pasta: Path | None, uf: str, cd_mun: str | None = None, zona: str | None = None,
                       secao: str | None = None, apenas_divergentes: bool = False,
                       limite: int | None = None) -> pd.DataFrame:
    arquivos = catalogo_uf(uf, pasta)
    if not arquivos:
        return pd.DataFrame(columns=COLUNAS_ARQUIVO)
    filtros, params = ["lower(uf) = ?"], [uf.lower()]
    for col, val in (("cd_mun", cd_mun), ("zona", zona), ("secao", secao)):
        if val:
            filtros.append(f"{col} = ?")
            params.append(str(val))
    if apenas_divergentes:
        filtros.append("hash_confere IS FALSE")
    sql = (f"SELECT * FROM read_parquet({_sql_list(arquivos)}, union_by_name = true) "
           f"WHERE {' AND '.join(filtros)} ORDER BY cd_mun, zona, secao, tipo, nome")
    if limite:
        sql += f" LIMIT {int(limite)}"
    con = duckdb.connect()
    try:
        df = con.execute(sql, params).fetchdf()
    finally:
        con.close()
    for c in COLUNAS_ARQUIVO:
        if c not in df.columns:
            df[c] = None
    return df[COLUNAS_ARQUIVO + [c for c in df.columns if c not in COLUNAS_ARQUIVO]]


def arquivos_da_secao(uf: str, cd_mun: str, zona: str, secao: str, pasta: Path | None = None) -> pd.DataFrame:
    """Todos os arquivos catalogados de uma seção, com a situação do SHA-512."""
    df = _consulta_arquivos(pasta, uf, cd_mun, zona, secao)
    if df.empty:
        return df
    df = df.copy()
    df["situacao_hash"] = df.apply(situacao_hash, axis=1)
    return df


def situacao_hash(row) -> str:
    conf = row.get("hash_confere")
    if conf is None or pd.isna(conf):
        if row.get("tipo") in TIPOS_ASSINADOS:
            return "Sem hash assinado"
        return "Não coberto pela assinatura"
    return "Confere" if bool(conf) else "Diverge"


def contar_catalogo(uf: str, cd_mun: str | None = None, zona: str | None = None,
                    apenas_divergentes: bool = False, pasta: Path | None = None,
                    remoto: bool = False) -> int:
    """Arquivos do filtro no catálogo (só local por padrão: contar não justifica um download)."""
    arquivos = catalogo_uf(uf, pasta, remoto=remoto)
    if not arquivos:
        return 0
    filtros, params = ["lower(uf) = ?"], [uf.lower()]
    for col, val in (("cd_mun", cd_mun), ("zona", zona)):
        if val:
            filtros.append(f"{col} = ?")
            params.append(str(val))
    if apenas_divergentes:
        filtros.append("hash_confere IS FALSE")
    con = duckdb.connect()
    try:
        return int(con.execute(
            f"SELECT COUNT(*) FROM read_parquet({_sql_list(arquivos)}, union_by_name = true) "
            f"WHERE {' AND '.join(filtros)}", params).fetchone()[0])
    finally:
        con.close()


def catalogo_csv(uf: str, cd_mun: str | None = None, zona: str | None = None,
                 apenas_divergentes: bool = False, pasta: Path | None = None,
                 limite: int = LIMITE_CSV) -> bytes:
    """Catálogo filtrado em CSV (UTF-8 com BOM, separador ';', abre direto em planilhas pt-BR)."""
    df = _consulta_arquivos(pasta, uf, cd_mun, zona, None, apenas_divergentes, limite)
    buf = io.StringIO()
    df.to_csv(buf, index=False, sep=";", quoting=csv.QUOTE_MINIMAL)
    return ("" + buf.getvalue()).encode("utf-8")


def mascarar_hash(valor, inicio: int = 12, fim: int = 8) -> str:
    """Forma curta para tabelas estreitas: primeiros e últimos caracteres do hash."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)) or valor == "":
        return "-"
    s = str(valor)
    return s if len(s) <= inicio + fim + 3 else f"{s[:inicio]}...{s[-fim:]}"
