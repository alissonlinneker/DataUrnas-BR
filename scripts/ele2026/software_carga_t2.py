#!/usr/bin/env python3
"""Software e carga das urnas no 2º turno de 2026 (pleito 3221, eleição 6258).

Lê os BUs versionados pelo coletor do 2º turno (só leitura):

  data/versoes/2026/t2/bus/parts/versoes-*.parquet
  data/versoes/2026/t2-sseco/bus/parts/versoes-*.parquet

e, para cada seção, extrai do BU (``bu_to_rows`` com o parser do projeto):
versao_votacao, codigo_carga, qtd_codigos_carga, numero_interno_urna,
tipo_urna e fase; do arquivo de assinatura (tipo ``vota`` ou ``sa``), o modelo
da urna (``modelo_from_vsc``) e o CN, serial e emissora do certificado da
urna (``info_vsc`` de analisar_certificados.py, carregado sem modificação).

Uma seção pode ter várias versões do BU (coletas sucessivas). A linha da seção
usa a versão coletada por último, e o resumo registra se versão de software ou
código de carga mudaram entre versões.

Cruzamentos:
  - encerramento (data/parquet/2026/t2/encerramento/secoes_encerramento.parquet):
    seções que encerraram depois de 17:30 de Brasília (coluna
    minutos_apos_17h_bsb, ou calculada a partir de encerramento_bsb) contra as
    demais;
  - 1º turno (data/parquet/2026/secoes_2026.parquet): mesma seção com o mesmo
    número interno de urna, versão e código de carga do 1º turno.

Saídas (não versionadas):
  data/parquet/2026/t2/software/secoes_software.parquet
  data/parquet/2026/t2/software/resumo.json

Uso:
  nice -n 20 python3 scripts/ele2026/software_carga_t2.py
  python3 scripts/ele2026/software_carga_t2.py --dir data/versoes/2026/t2/bus/parts --limite 2000
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

ROOT = Path(__file__).resolve().parents[2]
SRC = str(ROOT / "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)

import pandas as pd  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from dataurnas.downloader import ele2026 as E  # noqa: E402

ELEICAO_T2 = 6258
CARGO_PRESIDENTE = 1
CHAVE = ["uf", "cd_mun", "zona", "secao"]
DIRS_PADRAO = [
    ROOT / "data" / "versoes" / "2026" / "t2" / "bus" / "parts",
    ROOT / "data" / "versoes" / "2026" / "t2-sseco" / "bus" / "parts",
]
ENCERRAMENTO_PADRAO = (ROOT / "data" / "parquet" / "2026" / "t2" / "encerramento"
                       / "secoes_encerramento.parquet")
T1_PADRAO = ROOT / "data" / "parquet" / "2026" / "secoes_2026.parquet"
SAIDA_PADRAO = ROOT / "data" / "parquet" / "2026" / "t2" / "software"
CORTE_TARDIA_MIN = 30.0  # 17:30 de Brasília
MAX_EXEMPLOS = 20
TIPOS_ASSINATURA = {"vota", "sa"}
COLUNAS_LEITURA = ["coletado_em", "uf", "cd_mun", "zona", "secao", "tipo",
                   "hash", "sha512", "conteudo"]


# ---------------------------------------------------------------------------
# Leitura do .vsc reaproveitada de analisar_certificados.py (sem modificá-lo)
# ---------------------------------------------------------------------------

_CERT_MOD = None


def modulo_certificados():
    """Carrega scripts/ele2026/analisar_certificados.py como módulo."""
    global _CERT_MOD
    if _CERT_MOD is None:
        p = ROOT / "scripts" / "ele2026" / "analisar_certificados.py"
        spec = importlib.util.spec_from_file_location("_cert_t2_software", p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _CERT_MOD = mod
    return _CERT_MOD


# ---------------------------------------------------------------------------
# Extração por arquivo
# ---------------------------------------------------------------------------

def extrair_bu(raw: bytes, eleicao: int = ELEICAO_T2,
               cargo: int = CARGO_PRESIDENTE) -> dict:
    """Campos de software e carga de um BU."""
    try:
        sec, _ = E.bu_to_rows(bytes(raw), eleicao, cargo)
    except Exception as e:  # BU ilegível fica registrado, não interrompe
        return {"bu_erro": f"{type(e).__name__}: {e}"[:200]}
    num = sec.get("numero_interno_urna")
    return {
        "versao_votacao": sec.get("versao_votacao"),
        "codigo_carga": None if sec.get("codigo_carga") is None else str(sec["codigo_carga"]),
        "qtd_codigos_carga": sec.get("qtd_codigos_carga"),
        "numero_interno_urna": None if num is None else int(num),
        "tipo_urna": sec.get("tipo_urna"),
        "fase": sec.get("fase"),
        "hora_encerramento": sec.get("hora_encerramento"),
        "bu_erro": None,
    }


def extrair_vsc(raw: bytes, info_fn: Optional[Callable[[bytes], dict]] = None) -> dict:
    """Modelo da urna e identificação do certificado de um .vsc."""
    raw = bytes(raw)
    cod = E.modelo_from_vsc(raw)
    out: dict[str, Any] = {
        "modelo_vsc_cod": cod,
        "modelo_vsc": E.MODELOS.get(cod) if cod is not None else None,
        "cert_cn": None, "cert_numero": None, "cert_serial": None,
        "cert_emissor": None, "cert_sha256": None, "assinatura_usuario": None,
        "vsc_erro": None,
    }
    if info_fn is None:
        info_fn = modulo_certificados().info_vsc
    try:
        i = info_fn(raw)
    except Exception as e:
        out["vsc_erro"] = f"{type(e).__name__}: {e}"[:200]
        return out
    if i.get("erro"):
        out["vsc_erro"] = str(i["erro"])
        return out
    cn = i.get("cn")
    out["cert_cn"] = cn
    out["cert_numero"] = numero_de_cn(cn)
    out["cert_serial"] = i.get("serial")
    out["cert_emissor"] = cn_de_dn(i.get("issuer"))
    out["cert_sha256"] = i.get("sha256")
    out["assinatura_usuario"] = i.get("usuario")
    return out


def cn_de_dn(dn: Any) -> Optional[str]:
    if not isinstance(dn, str):
        return None
    for parte in dn.split(","):
        k, _, v = parte.partition("=")
        if k.strip().upper() == "CN":
            return v.strip()
    return None


def numero_de_cn(cn: Any) -> Optional[int]:
    """UEAO02046316 -> 2046316; outro formato -> None."""
    if not isinstance(cn, str):
        return None
    c = cn.strip().upper()
    if c.startswith("UEAO") and c[4:].isdigit() and len(c) == 12:
        return int(c[4:])
    return None


# ---------------------------------------------------------------------------
# Leitura dos parquets versionados
# ---------------------------------------------------------------------------

def listar_partes(dirs: Iterable[Path]) -> list[Path]:
    out: list[Path] = []
    for d in dirs:
        d = Path(d)
        if d.is_dir():
            out.extend(sorted(d.glob("versoes-*.parquet")))
    return out


def iterar_registros(partes: Iterable[Path], erros: list[dict]):
    """Gera dicts (origem, coletado_em, chave, tipo, hash, sha512, conteudo)."""
    for p in partes:
        try:
            pf = pq.ParquetFile(p)
        except Exception as e:  # parte em escrita ou corrompida
            erros.append({"parte": str(p), "erro": f"{type(e).__name__}: {e}"[:200]})
            continue
        cols = [c for c in COLUNAS_LEITURA if c in pf.schema_arrow.names]
        origem = p.parent.parent.parent.name  # t2 ou t2-sseco
        for rg in range(pf.num_row_groups):
            try:
                tb = pf.read_row_group(rg, columns=cols)
            except Exception as e:
                erros.append({"parte": str(p), "erro": f"{type(e).__name__}: {e}"[:200]})
                break
            for r in tb.to_pylist():
                tipo = r.get("tipo")
                if tipo != "bu" and tipo not in TIPOS_ASSINATURA:
                    continue
                if not r.get("conteudo"):
                    continue
                r["origem"] = origem
                yield r


def coletar(registros: Iterable[dict], info_fn=None,
            limite: Optional[int] = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Extrai campos de todos os BUs e assinaturas. Devolve (bus, vscs)."""
    bus: list[dict] = []
    vscs: list[dict] = []
    vistos_bu: set = set()
    vistos_vsc: set = set()
    for r in registros:
        chave = tuple(str(r[c]) for c in CHAVE)
        ident = {c: str(r[c]) for c in CHAVE}
        ident.update(origem=r.get("origem"), coletado_em=r.get("coletado_em"),
                     hash=r.get("hash"), sha512=r.get("sha512"))
        if r["tipo"] == "bu":
            k = (chave, r.get("sha512"))
            if k in vistos_bu:
                continue
            vistos_bu.add(k)
            bus.append({**ident, **extrair_bu(r["conteudo"])})
            if limite and len(bus) >= limite:
                break
        else:
            k = (chave, r.get("sha512"))
            if k in vistos_vsc:
                continue
            vistos_vsc.add(k)
            vscs.append({**ident, "tipo_assinatura": r["tipo"],
                         **extrair_vsc(r["conteudo"], info_fn)})
    return pd.DataFrame(bus), pd.DataFrame(vscs)


# ---------------------------------------------------------------------------
# Consolidação por seção
# ---------------------------------------------------------------------------

def _n_distintos(s: pd.Series) -> int:
    return int(s.dropna().nunique())


def consolidar(bus: pd.DataFrame, vscs: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por seção: BU coletado por último e o .vsc do mesmo hash."""
    if bus.empty:
        return pd.DataFrame(columns=CHAVE)
    b = bus.sort_values("coletado_em", kind="stable")
    agg = b.groupby(CHAVE, sort=False).agg(
        n_versoes_bu=("sha512", "nunique"),
        n_versoes_software=("versao_votacao", _n_distintos),
        n_codigos_carga_versoes=("codigo_carga", _n_distintos),
        n_numeros_internos_versoes=("numero_interno_urna", _n_distintos),
    ).reset_index()
    ult = b.groupby(CHAVE, sort=False).tail(1)
    df = ult.merge(agg, on=CHAVE, how="left")
    if not vscs.empty:
        v = vscs.sort_values("coletado_em", kind="stable")
        cols_v = [c for c in v.columns if c not in
                  ("origem", "coletado_em", "sha512")]
        por_hash = v.groupby(CHAVE + ["hash"], sort=False).tail(1)[cols_v]
        df = df.merge(por_hash, on=CHAVE + ["hash"], how="left")
        # sem .vsc do mesmo hash: usa o último .vsc da seção
        casou = df["tipo_assinatura"].notna()
        falta = ~casou
        if falta.any():
            ult_v = v.groupby(CHAVE, sort=False).tail(1)[
                [c for c in cols_v if c != "hash"]]
            fb = df.loc[falta, CHAVE].merge(ult_v, on=CHAVE, how="left")
            fb.index = df.index[falta]
            for c in ult_v.columns:
                if c not in CHAVE:
                    df[c] = df[c].astype(object)
                    df.loc[falta, c] = fb[c].astype(object)
        df["vsc_mesmo_hash"] = [
            True if c else (False if t is not None and not pd.isna(t) else None)
            for c, t in zip(casou, df["tipo_assinatura"], strict=True)]
    for c in ("modelo_vsc_cod", "modelo_vsc", "cert_cn", "cert_numero", "cert_serial",
              "cert_emissor", "cert_sha256", "assinatura_usuario", "vsc_erro",
              "tipo_assinatura", "vsc_mesmo_hash"):
        if c not in df.columns:
            df[c] = None
    df["cn_difere_numero_interno"] = [
        (None if pd.isna(a) or pd.isna(c) else bool(int(a) != int(c)))
        for a, c in zip(df["numero_interno_urna"], df["cert_numero"], strict=True)]
    return df.reset_index(drop=True)


def minutos_apos_17h(enc_bsb: Any) -> Optional[float]:
    """'2026-10-25 17:31:00' -> 31.0."""
    if not isinstance(enc_bsb, str) or not enc_bsb:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            t = datetime.strptime(enc_bsb[:19], fmt)
            base = t.replace(hour=17, minute=0, second=0)
            return (t - base).total_seconds() / 60.0
        except ValueError:
            continue
    return None


def juntar_encerramento(df: pd.DataFrame, enc: Optional[pd.DataFrame],
                        corte: float = CORTE_TARDIA_MIN) -> pd.DataFrame:
    df = df.copy()
    if enc is None or enc.empty:
        df["minutos_apos_17h_bsb"] = None
        df["tardia"] = None
        return df
    e = enc.copy()
    if "minutos_apos_17h_bsb" not in e.columns:
        e["minutos_apos_17h_bsb"] = e["encerramento_bsb"].map(minutos_apos_17h)
    cols = CHAVE + ["minutos_apos_17h_bsb"] + (
        ["encerramento_bsb"] if "encerramento_bsb" in e.columns else [])
    e = e[cols].drop_duplicates(CHAVE, keep="last")
    df = df.merge(e, on=CHAVE, how="left")
    m = df["minutos_apos_17h_bsb"]
    df["tardia"] = [None if pd.isna(x) else bool(x > corte) for x in m]
    return df


def juntar_t1(df: pd.DataFrame, t1: Optional[pd.DataFrame]) -> pd.DataFrame:
    df = df.copy()
    novos = ["t1_numero_interno_urna", "t1_versao_votacao", "t1_codigo_carga",
             "t1_tipo_urna", "t1_modelo_urna"]
    if t1 is None or t1.empty:
        for c in novos:
            df[c] = None
        df["mesma_urna_t1"] = None
        return df
    ren = {"numero_interno_urna": "t1_numero_interno_urna",
           "versao_votacao": "t1_versao_votacao", "codigo_carga": "t1_codigo_carga",
           "tipo_urna": "t1_tipo_urna", "modelo_urna": "t1_modelo_urna"}
    t = t1[[c for c in CHAVE + list(ren) if c in t1.columns]].rename(columns=ren)
    t = t.drop_duplicates(CHAVE, keep="first")
    df = df.merge(t, on=CHAVE, how="left")
    for c in novos:
        if c not in df.columns:
            df[c] = None
    df["mesma_urna_t1"] = [
        None if pd.isna(a) or pd.isna(b) else bool(int(a) == int(b))
        for a, b in zip(df["numero_interno_urna"], df["t1_numero_interno_urna"], strict=True)]
    return df


# ---------------------------------------------------------------------------
# Resumo
# ---------------------------------------------------------------------------

def _sid(r) -> str:
    return f"{r['uf']}-{r['cd_mun']}-{r['zona']}-{r['secao']}"


def _jsonavel(v: Any) -> Any:
    if v is None or v is pd.NA:
        return None
    if hasattr(v, "item"):  # escalares numpy
        v = v.item()
    if isinstance(v, float) and v != v:
        return None
    return v


def _exemplos(df: pd.DataFrame, cols: list[str]) -> list[dict]:
    out = []
    for _, r in df.head(MAX_EXEMPLOS).iterrows():
        d = {"secao_id": _sid(r)}
        for c in cols:
            d[c] = _jsonavel(r.get(c))
        out.append(d)
    return out


def _contagem(s: pd.Series) -> dict:
    return {str(k): int(v) for k, v in s.fillna("(ausente)").astype(str)
            .value_counts().items()}


def _taxa(n: int, d: int) -> Optional[float]:
    return round(n / d, 6) if d else None


def resumir(df: pd.DataFrame) -> dict:
    """Indicadores de software e carga de um conjunto de seções."""
    n = int(len(df))
    if n == 0:
        return {"secoes": 0}
    vv = df["versao_votacao"]
    modal = vv.dropna().mode()
    modal = modal.iloc[0] if len(modal) else None
    ver_dif = df[vv.notna() & (vv != modal)]
    multi = df[df["qtd_codigos_carga"].fillna(0).astype(int) > 1]
    carga_rep = df[df["codigo_carga"].notna()].groupby("codigo_carga").filter(
        lambda g: len(g) > 1)
    cn = df["cn_difere_numero_interno"]
    cn_dif = df[cn.fillna(False).astype(bool)]
    cn_cmp = int(cn.notna().sum())
    mudou_sw = df[df["n_versoes_software"].fillna(0) > 1]
    mudou_carga = df[df["n_codigos_carga_versoes"].fillna(0) > 1]
    mudou_urna = df[df["n_numeros_internos_versoes"].fillna(0) > 1]
    out = {
        "secoes": n,
        "bu_ilegivel": int(df["bu_erro"].notna().sum()) if "bu_erro" in df else 0,
        "versao_votacao": _contagem(vv),
        "versao_modal": modal,
        "secoes_versao_diferente_da_modal": {
            "n": int(len(ver_dif)),
            "exemplos": _exemplos(ver_dif, ["versao_votacao", "tipo_urna"])},
        "qtd_codigos_carga": _contagem(df["qtd_codigos_carga"]),
        "secoes_mais_de_um_codigo_carga": {
            "n": int(len(multi)),
            "por_tipo_urna": _contagem(multi["tipo_urna"]),
            "exemplos": _exemplos(multi, ["qtd_codigos_carga", "codigo_carga",
                                          "tipo_urna"])},
        "codigo_carga_em_mais_de_uma_secao": {
            "codigos": int(carga_rep["codigo_carga"].nunique()),
            "secoes": int(len(carga_rep)),
            "exemplos": _exemplos(carga_rep.sort_values("codigo_carga"),
                                  ["codigo_carga", "numero_interno_urna"])},
        "tipo_urna": _contagem(df["tipo_urna"]),
        "fase": _contagem(df["fase"]),
        "modelo_vsc": _contagem(df["modelo_vsc"]),
        "assinatura": {
            "com_vsc": int(df["tipo_assinatura"].notna().sum()),
            "vsc_ilegivel": int(df["vsc_erro"].notna().sum()),
            "vsc_de_outra_versao_do_bu": int((df["vsc_mesmo_hash"] == False).sum()),  # noqa: E712
        },
        "cn_x_numero_interno": {
            "comparadas": cn_cmp,
            "divergentes": int(len(cn_dif)),
            "taxa_divergencia": _taxa(len(cn_dif), cn_cmp),
            "divergentes_por_tipo_urna": _contagem(cn_dif["tipo_urna"]),
            "exemplos": _exemplos(cn_dif, ["numero_interno_urna", "cert_cn",
                                           "tipo_urna", "modelo_vsc"])},
        "entre_versoes_do_bu": {
            "secoes_com_mais_de_uma_versao": int((df["n_versoes_bu"] > 1).sum()),
            "versao_software_mudou": int(len(mudou_sw)),
            "codigo_carga_mudou": int(len(mudou_carga)),
            "numero_interno_mudou": int(len(mudou_urna)),
            "exemplos_carga_mudou": _exemplos(mudou_carga, ["n_versoes_bu",
                                                            "codigo_carga"]),
        },
    }
    if "mesma_urna_t1" in df.columns:
        m = df["mesma_urna_t1"]
        cmp_ = df[m.notna()]
        dif = cmp_[~cmp_["mesma_urna_t1"].astype(bool)]
        t1v = df["t1_versao_votacao"]
        t1c = df["t1_codigo_carga"]
        mesma_carga = df[t1c.notna() & df["codigo_carga"].notna()
                         & (t1c.astype(str) == df["codigo_carga"].astype(str))]
        out["comparacao_t1"] = {
            "secoes_com_t1": int(df["t1_numero_interno_urna"].notna().sum()),
            "comparadas_numero_interno": int(len(cmp_)),
            "mesma_urna": int(cmp_["mesma_urna_t1"].astype(bool).sum()),
            "urna_diferente": int(len(dif)),
            "taxa_urna_diferente": _taxa(len(dif), len(cmp_)),
            "urna_diferente_por_tipo_t2": _contagem(dif["tipo_urna"]),
            "urna_diferente_por_tipo_t1": _contagem(dif["t1_tipo_urna"]),
            "versao_t1": _contagem(t1v[df["t1_numero_interno_urna"].notna()]),
            "versao_igual_t1": int((t1v.notna() & (t1v == df["versao_votacao"])).sum()),
            "codigo_carga_igual_t1": int(len(mesma_carga)),
            "mesma_urna_codigo_carga_diferente": int(
                (cmp_["mesma_urna_t1"].astype(bool)
                 & (cmp_["t1_codigo_carga"].astype(str)
                    != cmp_["codigo_carga"].astype(str))).sum()),
            "exemplos_urna_diferente": _exemplos(
                dif, ["numero_interno_urna", "t1_numero_interno_urna",
                      "tipo_urna", "t1_tipo_urna"]),
        }
    return out


def montar_resumo(df: pd.DataFrame, meta: dict) -> dict:
    out = {**meta, "todas": resumir(df)}
    if "tardia" in df.columns and df["tardia"].notna().any():
        t = df["tardia"]
        out["recorte_encerramento"] = {
            "criterio": f"minutos_apos_17h_bsb > {CORTE_TARDIA_MIN:g} (após 17:30 de Brasília)",
            "sem_encerramento": int(t.isna().sum()),
            "tardias_por_uf": _contagem(df.loc[t.fillna(False).astype(bool), "uf"]),
            "tardias": resumir(df[t.fillna(False).astype(bool)]),
            "demais": resumir(df[t.notna() & ~t.fillna(False).astype(bool)]),
        }
    return out


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------

def _ler_opcional(p: Path, cols: Optional[list[str]] = None) -> Optional[pd.DataFrame]:
    if not p or not Path(p).exists():
        return None
    nomes = pq.ParquetFile(p).schema_arrow.names
    use = [c for c in cols if c in nomes] if cols else None
    return pd.read_parquet(p, columns=use)


def _limpar_para_parquet(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    for c in df.columns:
        if df[c].dtype == object:
            vals = df[c].dropna()
            if len(vals) and vals.map(lambda x: isinstance(x, bool)).all():
                df[c] = df[c].astype("boolean")
            elif len(vals) and not vals.map(lambda x: isinstance(x, (int, float))).all():
                df[c] = df[c].map(lambda x: None if x is None or (
                    not isinstance(x, str) and pd.isna(x)) else str(x))
    for c in ("numero_interno_urna", "cert_numero", "t1_numero_interno_urna",
              "qtd_codigos_carga", "modelo_vsc_cod", "n_versoes_bu"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")
    return df


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dir", action="append", type=Path, dest="dirs",
                    help="diretório com versoes-*.parquet (repetível)")
    ap.add_argument("--encerramento", type=Path, default=ENCERRAMENTO_PADRAO)
    ap.add_argument("--t1", type=Path, default=T1_PADRAO)
    ap.add_argument("--saida", type=Path, default=SAIDA_PADRAO)
    ap.add_argument("--limite", type=int, default=None,
                    help="para depois de N BUs (teste)")
    a = ap.parse_args(argv)
    dirs = a.dirs or DIRS_PADRAO
    t0 = time.time()
    partes = listar_partes(dirs)
    if not partes:
        print("nenhuma parte versoes-*.parquet encontrada", file=sys.stderr)
        return 1
    erros: list[dict] = []
    bus, vscs = coletar(iterar_registros(partes, erros), limite=a.limite)
    print(f"{len(partes)} partes, {len(bus)} BUs, {len(vscs)} assinaturas "
          f"({time.time() - t0:.0f}s)", file=sys.stderr)
    df = consolidar(bus, vscs)
    enc = _ler_opcional(a.encerramento, CHAVE + ["minutos_apos_17h_bsb", "encerramento_bsb"])
    df = juntar_encerramento(df, enc)
    t1 = _ler_opcional(a.t1, CHAVE + ["numero_interno_urna", "versao_votacao",
                                      "codigo_carga", "tipo_urna", "modelo_urna"])
    df = juntar_t1(df, t1)
    a.saida.mkdir(parents=True, exist_ok=True)
    _limpar_para_parquet(df).to_parquet(a.saida / "secoes_software.parquet", index=False)
    meta = {
        "gerado_em": datetime.now().astimezone().isoformat(timespec="seconds"),
        "eleicao": ELEICAO_T2, "pleito": 3221,
        "fontes": [str(Path(d)) for d in dirs],
        "partes_lidas": len(partes), "partes_com_erro": erros[:MAX_EXEMPLOS],
        "bus_lidos": int(len(bus)), "assinaturas_lidas": int(len(vscs)),
        "tipos_assinatura": _contagem(vscs["tipo_assinatura"]) if len(vscs) else {},
        "origem": _contagem(df["origem"]) if len(df) else {},
        "parcial": True,
        "observacao": ("Coleta do 2º turno em andamento; os números refletem as "
                       "partes existentes no momento da execução."),
    }
    resumo = montar_resumo(df, meta)
    (a.saida / "resumo.json").write_text(
        json.dumps(resumo, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
    print(f"{len(df)} seções -> {a.saida} ({time.time() - t0:.0f}s)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())

