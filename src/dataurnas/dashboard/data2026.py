"""Leitura dos dados de 2026 (Presidente, 1º turno) para o dashboard.

Arquivos em ``data/parquet/2026`` (somente leitura):

- ``candidatos.parquet``, ``resultado_uf.parquet``, ``resultado_municipio.parquet``
  e ``resumo_br.json``: resultado oficial divulgado pelo TSE (colunas ``v_<número>``
  trazem os votos de cada candidato).
- ``secoes_2026.parquet`` e ``votos_presidente_2026.parquet``: boletins de urna por
  seção, ainda sendo coletados por um processo em segundo plano. Enquanto a coleta
  não termina, os lotes ficam em ``secoes_parts/`` (com a coluna ``_lote``).

As funções aceitam coleta parcial ou ausente: lotes e arquivo consolidado são
unidos e deduplicados (fica o lote mais recente de cada seção), e arquivos
ilegíveis (ex.: um lote sendo gravado) são ignorados.

Nada aqui depende do Streamlit: o cache fica na camada de página.
"""

from __future__ import annotations

import json
import logging
import math
from dataclasses import dataclass
from pathlib import Path

import duckdb
import pandas as pd
import pyarrow.parquet as pq

from dataurnas.config import PARQUET_2026_DIR, PARQUET_DIR

logger = logging.getLogger("dataurnas.dashboard")

CHAVE_SECAO = ["uf", "cd_mun", "zona", "secao"]
UF_EXTERIOR = "zz"
UF_NOMES = {
    "ac": "Acre", "al": "Alagoas", "am": "Amazonas", "ap": "Amapá", "ba": "Bahia",
    "ce": "Ceará", "df": "Distrito Federal", "es": "Espírito Santo", "go": "Goiás",
    "ma": "Maranhão", "mg": "Minas Gerais", "ms": "Mato Grosso do Sul", "mt": "Mato Grosso",
    "pa": "Pará", "pb": "Paraíba", "pe": "Pernambuco", "pi": "Piauí", "pr": "Paraná",
    "rj": "Rio de Janeiro", "rn": "Rio Grande do Norte", "ro": "Rondônia", "rr": "Roraima",
    "rs": "Rio Grande do Sul", "sc": "Santa Catarina", "se": "Sergipe", "sp": "São Paulo",
    "to": "Tocantins", "zz": "Exterior",
}
BENFORD_1 = {d: math.log10(1 + 1 / d) for d in range(1, 10)}


def base_dir() -> Path:
    return Path(PARQUET_2026_DIR)


def _sql_list(paths: list[Path]) -> str:
    return "[" + ", ".join("'" + str(p).replace("'", "''") + "'" for p in paths) + "]"


def _legivel(path: Path) -> bool:
    """Parquet completo (rodapé válido). Um lote em gravação falha aqui."""
    try:
        pq.read_metadata(path)
        return True
    except Exception:  # noqa: BLE001 (qualquer falha = arquivo ainda não utilizável)
        logger.info("Ignorando Parquet ilegível: %s", path)
        return False


def files_signature(base: Path | None = None) -> tuple:
    """Assinatura (nome, tamanho, mtime) dos arquivos: chave de cache que muda a cada lote."""
    base = base or base_dir()
    if not base.exists():
        return ()
    files = sorted(list(base.glob("*.parquet")) + list(base.glob("*.json"))
                   + list((base / "secoes_parts").glob("*.parquet")))
    sig = []
    for p in files:
        try:
            st_ = p.stat()
            sig.append((p.name, st_.st_size, int(st_.st_mtime)))
        except OSError:
            continue
    return tuple(sig)


# ----------------------------------------------------------------------
# Resultado oficial
# ----------------------------------------------------------------------
def load_resumo(base: Path | None = None) -> dict:
    path = (base or base_dir()) / "resumo_br.json"
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as fh:
        return json.load(fh)


def load_candidatos(base: Path | None = None) -> pd.DataFrame:
    path = (base or base_dir()) / "candidatos.parquet"
    if not path.exists():
        return pd.DataFrame()
    df = pd.read_parquet(path).sort_values("votos", ascending=False).reset_index(drop=True)
    df["rotulo"] = df["nome_urna"].str.title() + " (" + df["partido_sigla"] + ")"
    return df


def load_resultado_uf(base: Path | None = None) -> pd.DataFrame:
    path = (base or base_dir()) / "resultado_uf.parquet"
    return pd.read_parquet(path) if path.exists() else pd.DataFrame()


def load_resultado_municipio(base: Path | None = None) -> pd.DataFrame:
    path = (base or base_dir()) / "resultado_municipio.parquet"
    return pd.read_parquet(path) if path.exists() else pd.DataFrame()


def vote_columns(df: pd.DataFrame) -> list[str]:
    return [c for c in df.columns if c.startswith("v_") and c[2:].isdigit()]


def add_leader(df: pd.DataFrame, candidatos: pd.DataFrame) -> pd.DataFrame:
    """Acrescenta líder, 2º colocado e % de cada candidato sobre os válidos."""
    out = df.copy()
    cols = vote_columns(out)
    if not cols:
        return out
    validos = out["votos_validos"].where(out["votos_validos"] > 0)
    for c in cols:
        out[f"pct_{c[2:]}"] = out[c] / validos * 100
    nomes = {}
    if not candidatos.empty:
        nomes = dict(zip(candidatos["numero"].astype(int), candidatos["rotulo"], strict=False))
    votos = out[cols].to_numpy()
    ordem = votos.argsort(axis=1)
    lider_idx = ordem[:, -1]
    segundo_idx = ordem[:, -2] if len(cols) > 1 else lider_idx
    numeros = [int(c[2:]) for c in cols]
    out["lider_numero"] = [numeros[i] for i in lider_idx]
    out["lider"] = out["lider_numero"].map(lambda n: nomes.get(n, str(n)))
    lider_votos = votos[range(len(out)), lider_idx]
    segundo_votos = votos[range(len(out)), segundo_idx]
    out["pct_lider"] = lider_votos / validos * 100
    out["margem_pp"] = (lider_votos - segundo_votos) / validos * 100
    return out


# ----------------------------------------------------------------------
# Boletins por seção (coleta parcial)
# ----------------------------------------------------------------------
@dataclass
class SecoesData:
    secoes: pd.DataFrame
    votos: pd.DataFrame
    arquivos: int
    ignorados: int

    @property
    def vazio(self) -> bool:
        return self.secoes.empty


def load_secoes(base: Path | None = None) -> SecoesData:
    """Une lotes (``secoes_parts``) e consolidado, mantendo o lote mais recente."""
    base = base or base_dir()
    parts_dir = base / "secoes_parts"
    sec_files = sorted(parts_dir.glob("secoes-*.parquet")) if parts_dir.exists() else []
    vot_files = sorted(parts_dir.glob("votos-*.parquet")) if parts_dir.exists() else []
    cons_s = base / "secoes_2026.parquet"
    cons_v = base / "votos_presidente_2026.parquet"

    candidatos = sec_files + vot_files + [p for p in (cons_s, cons_v) if p.exists()]
    legiveis = {p for p in candidatos if _legivel(p)}
    ignorados = len(candidatos) - len(legiveis)
    sec_files = [p for p in sec_files if p in legiveis]
    vot_files = [p for p in vot_files if p in legiveis]
    has_cons_s = cons_s in legiveis
    has_cons_v = cons_v in legiveis

    if not sec_files and not has_cons_s:
        return SecoesData(pd.DataFrame(), pd.DataFrame(), 0, ignorados)

    con = duckdb.connect()
    try:
        fontes_s = []
        if sec_files:
            fontes_s.append(f"SELECT * FROM read_parquet({_sql_list(sec_files)}, union_by_name = true)")
        if has_cons_s:
            fontes_s.append(f"SELECT *, '' AS _lote FROM read_parquet({_sql_list([cons_s])})")
        con.execute(f"""
            CREATE TEMP TABLE s AS
            SELECT * FROM ({' UNION ALL BY NAME '.join(fontes_s)})
            QUALIFY row_number() OVER (PARTITION BY uf, cd_mun, zona, secao ORDER BY _lote DESC) = 1
        """)
        secoes = con.execute("SELECT * EXCLUDE (_lote) FROM s ORDER BY uf, cd_mun, zona, secao").fetchdf()

        fontes_v = []
        if vot_files:
            fontes_v.append(f"SELECT * FROM read_parquet({_sql_list(vot_files)}, union_by_name = true)")
        if has_cons_v:
            fontes_v.append(f"SELECT *, '' AS _lote FROM read_parquet({_sql_list([cons_v])})")
        if fontes_v:
            votos = con.execute(f"""
                SELECT v.* EXCLUDE (_lote)
                FROM ({' UNION ALL BY NAME '.join(fontes_v)}) v
                JOIN s USING (uf, cd_mun, zona, secao, _lote)
            """).fetchdf()
        else:
            votos = pd.DataFrame(columns=CHAVE_SECAO + ["tipo_voto", "numero", "partido", "votos"])
    finally:
        con.close()
    return SecoesData(secoes, votos, len(sec_files) + int(has_cons_s), ignorados)


def coverage_by_uf(secoes: pd.DataFrame, res_uf: pd.DataFrame) -> pd.DataFrame:
    """Cobertura da coleta: seções com BU / seções instaladas (oficial), por UF."""
    if res_uf.empty:
        return pd.DataFrame()
    base = res_uf[["uf", "secoes_total", "secoes_instaladas"]].copy()
    if secoes.empty:
        cont = pd.DataFrame({"uf": [], "processadas": [], "com_bu": [], "agregadas": []})
    else:
        cont = secoes.groupby("uf").agg(
            processadas=("status", "size"),
            com_bu=("status", lambda s: int((s == "ok").sum())),
            agregadas=("status", lambda s: int((s == "agregada").sum())),
        ).reset_index()
    out = base.merge(cont, on="uf", how="left").fillna({"processadas": 0, "com_bu": 0, "agregadas": 0})
    for c in ("processadas", "com_bu", "agregadas"):
        out[c] = out[c].astype(int)
    out["cobertura_pct"] = (out["com_bu"] / out["secoes_instaladas"].where(out["secoes_instaladas"] > 0) * 100).fillna(0.0)
    out["completa"] = out["com_bu"] >= out["secoes_instaladas"]
    out["nome"] = out["uf"].map(UF_NOMES)
    return out.sort_values("uf").reset_index(drop=True)


def overall_coverage(cov: pd.DataFrame) -> float:
    if cov.empty or cov["secoes_instaladas"].sum() == 0:
        return 0.0
    return float(cov["com_bu"].sum() / cov["secoes_instaladas"].sum() * 100)


def reconcile_by_uf(secoes: pd.DataFrame, votos: pd.DataFrame, res_uf: pd.DataFrame,
                    candidatos: pd.DataFrame) -> pd.DataFrame:
    """Soma dos BUs x resultado oficial por UF (mesma regra de ``scripts/ele2026/reconcile.py``).

    Voto nominal em número que não é candidato válido conta como nulo técnico.
    Em UF com coleta parcial a diferença é esperada; a coluna ``completa`` indica
    quando a comparação é conclusiva.
    """
    if secoes.empty or res_uf.empty:
        return pd.DataFrame()
    numeros = [int(n) for n in candidatos["numero"]] if not candidatos.empty else []
    ok = secoes[secoes["status"] == "ok"]
    agg = ok.groupby("uf").agg(
        secoes_bu=("status", "size"),
        comparecimento=("comparecimento", "sum"),
        brancos=("votos_brancos", "sum"),
        nulos=("votos_nulos", "sum"),
        nominais=("votos_nominais", "sum"),
    )
    nom = votos[votos["tipo_voto"] == "nominal"] if not votos.empty else votos
    por_cand = (nom.groupby(["uf", "numero"])["votos"].sum().unstack(fill_value=0)
                if not nom.empty else pd.DataFrame())

    linhas = []
    oficial = res_uf.set_index("uf")
    for uf, row in agg.iterrows():
        if uf not in oficial.index:
            continue
        of = oficial.loc[uf]
        cand = por_cand.loc[uf] if uf in por_cand.index else pd.Series(dtype="int64")
        nulos_tec = int(sum(int(v) for n, v in cand.items() if int(n) not in numeros))
        completa = int(row["secoes_bu"]) >= int(of["secoes_instaladas"])
        itens = [
            ("Seções com BU", int(row["secoes_bu"]), int(of["secoes_instaladas"])),
            ("Comparecimento", int(row["comparecimento"]), int(of["comparecimento"])),
            ("Brancos", int(row["brancos"]), int(of["votos_brancos"])),
            ("Nulos", int(row["nulos"]), int(of["votos_nulos"])),
            ("Nulos técnicos", nulos_tec, int(of.get("votos_nulos_tecnicos", 0) or 0)),
            ("Nominais válidos", int(row["nominais"]) - nulos_tec, int(of["votos_nominais"])),
        ]
        itens += [(f"Candidato {n}", int(cand.get(n, 0)), int(of.get(f"v_{n}", 0))) for n in numeros]
        for item, soma, ref in itens:
            linhas.append({"uf": uf, "item": item, "soma_bu": soma, "oficial": ref,
                           "diferenca": soma - ref, "completa": completa,
                           "confere": soma == ref})
    return pd.DataFrame(linhas)


def reconcile_summary(rec: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por UF: completa? itens divergentes? diferença absoluta total."""
    if rec.empty:
        return pd.DataFrame()
    g = rec.groupby("uf").agg(
        completa=("completa", "first"),
        itens=("item", "size"),
        divergentes=("confere", lambda s: int((~s).sum())),
        diferenca_abs=("diferenca", lambda s: int(s.abs().sum())),
    ).reset_index()
    g["situacao"] = g.apply(
        lambda r: ("Confere" if r["divergentes"] == 0 else "Diverge") if r["completa"] else "Coleta parcial",
        axis=1,
    )
    return g


def parse_hora(serie: pd.Series) -> pd.Series:
    """'20261004T060001' -> Timestamp (horário registrado no BU, fuso local da urna)."""
    return pd.to_datetime(serie, format="%Y%m%dT%H%M%S", errors="coerce")


def benford_first_digit(votos: pd.DataFrame, numeros: list[int], min_secoes: int = 50) -> pd.DataFrame:
    """Distribuição do 1º dígito dos votos por seção, por candidato, com qui-quadrado e V de Cramér."""
    from scipy import stats

    if votos.empty:
        return pd.DataFrame()
    nom = votos[(votos["tipo_voto"] == "nominal") & (votos["numero"].isin(numeros)) & (votos["votos"] > 0)]
    linhas = []
    for numero, grupo in nom.groupby("numero"):
        digitos = grupo["votos"].astype(str).str[0].astype(int)
        n = len(digitos)
        if n < min_secoes:
            continue
        obs = digitos.value_counts().reindex(range(1, 10), fill_value=0)
        esperado = [BENFORD_1[d] * n for d in range(1, 10)]
        chi2, p = stats.chisquare(obs.to_numpy(), esperado)
        v = math.sqrt(chi2 / (n * 8)) if n else 0.0
        for d in range(1, 10):
            linhas.append({"numero": int(numero), "digito": d, "observado_pct": obs[d] / n * 100,
                           "esperado_pct": BENFORD_1[d] * 100, "n": n, "chi2": float(chi2),
                           "p_valor": float(p), "cramers_v": v})
    return pd.DataFrame(linhas)


# ----------------------------------------------------------------------
# Comparação com 2022 (1º turno), lida direto dos Parquet distribuídos
# ----------------------------------------------------------------------
def load_2022_t1_by_uf(parquet_dir: Path | None = None) -> pd.DataFrame:
    """Comparecimento, brancos e nulos (Presidente) por UF no 1º turno de 2022.

    Usa ``data/parquet/secoes.parquet`` e ``totais_cargo.parquet`` (não exige o banco).
    """
    parquet_dir = parquet_dir or Path(PARQUET_DIR)
    secoes = parquet_dir / "secoes.parquet"
    totais = parquet_dir / "totais_cargo.parquet"
    if not secoes.exists() or not totais.exists():
        return pd.DataFrame()
    con = duckdb.connect()
    try:
        return con.execute(
            """
            WITH s AS (
                SELECT id, uf, eleitores_aptos, comparecimento
                FROM read_parquet(?) WHERE turno = 1
            ), t AS (
                SELECT secao_id, SUM(brancos) AS brancos, SUM(nulos) AS nulos, SUM(total) AS total
                FROM read_parquet(?) WHERE cargo = 'Presidente' GROUP BY secao_id
            )
            SELECT s.uf,
                   COUNT(*) AS secoes_2022,
                   SUM(s.eleitores_aptos) AS eleitorado_2022,
                   SUM(s.comparecimento) AS comparecimento_2022,
                   SUM(t.brancos) AS brancos_2022,
                   SUM(t.nulos) AS nulos_2022,
                   SUM(t.total) AS votos_2022
            FROM s LEFT JOIN t ON t.secao_id = s.id
            GROUP BY s.uf ORDER BY s.uf
            """,
            [str(secoes), str(totais)],
        ).fetchdf()
    finally:
        con.close()


def compare_2022_2026(res_uf: pd.DataFrame, t1_2022: pd.DataFrame) -> pd.DataFrame:
    if res_uf.empty or t1_2022.empty:
        return pd.DataFrame()
    a = res_uf[["uf", "eleitorado", "comparecimento", "votos_total", "votos_brancos", "votos_nulos_total"]].copy()
    a["comparecimento_pct_2026"] = a["comparecimento"] / a["eleitorado"] * 100
    a["brancos_pct_2026"] = a["votos_brancos"] / a["votos_total"] * 100
    a["nulos_pct_2026"] = a["votos_nulos_total"] / a["votos_total"] * 100
    b = t1_2022.copy()
    b["comparecimento_pct_2022"] = b["comparecimento_2022"] / b["eleitorado_2022"] * 100
    b["brancos_pct_2022"] = b["brancos_2022"] / b["votos_2022"] * 100
    b["nulos_pct_2022"] = b["nulos_2022"] / b["votos_2022"] * 100
    out = a.merge(b, on="uf", how="inner")
    for m in ("comparecimento", "brancos", "nulos"):
        out[f"{m}_var_pp"] = out[f"{m}_pct_2026"] - out[f"{m}_pct_2022"]
    out["eleitorado_var_pct"] = (out["eleitorado"] / out["eleitorado_2022"] - 1) * 100
    out["nome"] = out["uf"].map(UF_NOMES)
    return out
