"""Leitura da auditoria de integridade dos arquivos de urna de 2026.

Arquivos em ``data/parquet/2026/integridade`` (somente leitura), gerados pela
coleta de integridade, que roda por horas e grava aos poucos:

- ``arquivos_<uf>.parquet`` (SP pode vir dividido em ``arquivos_sp_*.parquet``):
  um registro por arquivo publicado da seção, com MD5, SHA-256 e SHA-512
  calculados, o SHA-512 assinado pela urna (quando o arquivo é coberto pela
  assinatura) e o resultado da comparação (``hash_confere``).
- ``secoes.parquet``: uma linha por seção, com contagens, validade da
  assinatura e dados do certificado.
- ``resumo.json``: totais e horários da coleta.

Tudo aqui aceita dados parciais ou ausentes: arquivos ilegíveis (em gravação)
são ignorados e, se ``secoes.parquet`` ainda não existe, o resumo por seção é
derivado dos catálogos de arquivos. Nada depende do Streamlit.
"""

from __future__ import annotations

import csv
import io
import json
import logging
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
    "cert_sha256", "modelo_urna", "motivo", "votos_conferem",
]
COLUNAS_ARQUIVO = CHAVE_SECAO + [
    "tipo", "nome", "tamanho", "md5", "sha256", "sha512", "sha512_assinado", "hash_confere",
    "token_tse", "data_hora_tse",
]
# Limite de linhas do catálogo exportado em CSV (acima disso, pedir filtro mais estreito)
LIMITE_CSV = 250_000


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
    for c in ("n_arquivos", "n_hash_confere", "n_hash_diverge", "n_sem_hash"):
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
# Consulta de uma seção e exportação do catálogo
# ----------------------------------------------------------------------
def _consulta_arquivos(pasta: Path | None, uf: str, cd_mun: str | None = None, zona: str | None = None,
                       secao: str | None = None, apenas_divergentes: bool = False,
                       limite: int | None = None) -> pd.DataFrame:
    arquivos = arquivos_parquet(pasta, uf)
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
                    apenas_divergentes: bool = False, pasta: Path | None = None) -> int:
    arquivos = arquivos_parquet(pasta, uf)
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
