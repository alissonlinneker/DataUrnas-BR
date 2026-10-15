#!/usr/bin/env python3
"""Cadeia de certificados das urnas de 2022 numa amostra estratificada de 5%.

Mesma conferência feita em 2026 (scripts/ele2026/analisar_certificados.py),
adaptada à fonte de 2022: o .vscmr de cada seção sorteada é lido por faixas
de bytes do zip de dados abertos do TSE (um por turno e UF), descompactado em
memória com o CRC-32 conferido, e nada bruto vai para o disco.

Amostra: 5% das seções de data/parquet/2022/integridade/secoes.parquet em cada
estrato (turno, UF), arredondado para cima. Dentro do estrato, as seções são
ordenadas pelo SHA-256 de "<semente>|<turno>|<uf>|<cd_mun>|<zona>|<secao>" e
entram as primeiras. A semente padrão é 20221002 (data do 1º turno). O
critério não depende de biblioteca nem de máquina: qualquer pessoa refaz o
mesmo sorteio.

Para cada seção da amostra, confere:
  - certificado da urna assinado pela AC emissora (AC URNA, ECDSA P-521, ou
    AC UE2020, Ed521), com os certificados públicos de data/certificados/ac;
  - a AC emissora: autoridade (basicConstraints CA) com uso de chave
    keyCertSign, válida no dia da eleição, e o certificado da urna emitido
    dentro da validade dela;
  - a subida da cadeia a partir da AC, até onde os certificados disponíveis
    permitem (as raízes AC RAIZ UE e AC RAIZ UE v2 e a AC URNA v2 não são
    publicadas em forma que se possa baixar; ver data/certificados/README.md);
  - certificado da urna válido no dia do turno, sem CA, com uso de chave
    digitalSignature e sem keyCertSign;
  - a chave pública do certificado valida a assinatura de hardware do
    conteúdo assinado (autoAssinado) do .vscmr, e o SHA-512 desse conteúdo
    confere (verificar_vsc);
  - CN do certificado igual ao usuário da assinatura e SHA-256 do certificado
    igual ao registrado em secoes.parquet.

Cadeia inválida ou assinatura que não fecha com o certificado é falha
crítica: vai na hora para certificados_amostra_falhas.jsonl e para o log
(linha "FALHA "), e a execução para (a menos que se use --nao-parar).

Saída em data/parquet/2022/integridade/:
  certificados_amostra.json      resumo (amostra, critérios, contagens, AC)
  certificados_amostra.parquet   uma linha por seção da amostra
Intermediários (fora do git): certificados_amostra_partes/ (uma parte por
estrato; a execução é retomável e pula os estratos prontos).

Uso:
  nice -n 19 python3 scripts/ele2022/analisar_certificados.py
  nice -n 19 python3 scripts/ele2022/analisar_certificados.py --turnos 1 --ufs rr
  python3 scripts/ele2022/analisar_certificados.py --so-consolidar
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import importlib.util
import json
import logging
import math
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[2]
SRC = str(ROOT / "src")
if SRC not in sys.path:
    sys.path.insert(0, SRC)
AQUI = str(Path(__file__).resolve().parent)
if AQUI not in sys.path:
    sys.path.append(AQUI)

import pandas as pd  # noqa: E402

from dataurnas.config import MODELOS_URNA  # noqa: E402
from dataurnas.downloader import zip_remoto as Z  # noqa: E402
from dataurnas.parsers import signature as S  # noqa: E402

log = logging.getLogger("certificados_2022")


def _carregar_modulo(nome: str, caminho: Path):
    spec = importlib.util.spec_from_file_location(nome, caminho)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# Funções de cadeia de 2026 (carregar_acs, validar_cadeia, subir_cadeia, ...)
A26 = _carregar_modulo("analisar_certificados_2026",
                       ROOT / "scripts" / "ele2026" / "analisar_certificados.py")

PASTA = ROOT / "data" / "parquet" / "2022" / "integridade"
AC_PADRAO = ROOT / "data" / "certificados" / "ac"
SEMENTE = 20221002
FRACAO = 0.05
CHAVE = ["turno", "uf", "cd_mun", "zona", "secao"]
# Meio-dia de Brasília (UTC-3) do dia de cada turno.
DIAS = {1: datetime(2022, 10, 2, 15, 0, tzinfo=timezone.utc),
        2: datetime(2022, 10, 30, 15, 0, tzinfo=timezone.utc)}
MAX_EXEMPLOS = 50

# Raízes e AC superiores: o que foi tentado para obtê-las (sem sucesso).
RAIZ_TENTATIVAS = [
    {"url": "http://dpc.acue2020.tse.jus.br/acraizue.crt", "resultado": "HTTP 403",
     "data": "2026-10-15"},
    {"url": "http://dpc.acue2020.tse.jus.br/acurnav2.crt", "resultado": "HTTP 403",
     "data": "2026-10-15"},
    {"url": "https://dpc.acue2020.tse.jus.br/acraizue.crt", "resultado": "sem resposta (HTTPS)",
     "data": "2026-10-15"},
    {"url": "http://dpc.acraizue.tse.jus.br/", "resultado": "HTTP 403", "data": "2026-10-15"},
    {"url": "http://lcr.acraizue.tse.jus.br/", "resultado": "HTTP 403", "data": "2026-10-15"},
]

COLS = CHAVE + [
    "modelo", "cn", "cn_confere_usuario", "cert_sha256", "confere_catalogo", "algoritmo_chave",
    "emissor", "not_before", "not_after", "valido_na_eleicao", "uso_chave_ok",
    "assinatura_confere", "cadeia_ok", "ac_cn", "ac_emissor", "ac_valida_na_eleicao",
    "ac_autoridade_ok", "emitido_na_validade_da_ac", "nivel_cadeia", "cadeia_caminho",
    "critica", "motivo",
]


# ---------------------------------------------------------------------------
# Amostra
# ---------------------------------------------------------------------------

def _rank(semente: int, turno, uf, mun, zona, secao) -> str:
    return hashlib.sha256(f"{semente}|{int(turno)}|{uf}|{mun}|{zona}|{secao}".encode()).hexdigest()


def sortear_amostra(secoes: pd.DataFrame, fracao: float = FRACAO,
                    semente: int = SEMENTE) -> tuple[pd.DataFrame, dict]:
    """Amostra estratificada por (turno, UF): ceil(fracao x N) seções por
    estrato, as de menor SHA-256 de "<semente>|<turno>|<uf>|<mun>|<zona>|<secao>".
    Retorna (amostra ordenada pela chave, {"<turno>T/<uf>": (N, n)})."""
    df = secoes[CHAVE + [c for c in ("cert_sha256",) if c in secoes.columns]].copy()
    df["_rank"] = [_rank(semente, *t) for t in df[CHAVE].itertuples(index=False, name=None)]
    partes, estratos = [], {}
    for (turno, uf), g in df.groupby(["turno", "uf"], sort=True):
        n = math.ceil(fracao * len(g))
        estratos[f"{int(turno)}T/{uf}"] = (int(len(g)), int(n))
        partes.append(g.sort_values("_rank", kind="stable").head(n))
    if not partes:
        return df.iloc[0:0].drop(columns="_rank"), estratos
    am = pd.concat(partes).drop(columns="_rank")
    return am.sort_values(CHAVE).reset_index(drop=True), estratos


# ---------------------------------------------------------------------------
# Avaliação de um .vscmr
# ---------------------------------------------------------------------------

def _ext(c, cls):
    from cryptography import x509
    try:
        return c.extensions.get_extension_for_class(cls).value
    except x509.ExtensionNotFound:
        return None


def uso_chave_urna(c) -> tuple[bool, list[str]]:
    """Certificado de entidade final: digitalSignature, sem keyCertSign, sem CA."""
    from cryptography import x509
    ku, bc = _ext(c, x509.KeyUsage), _ext(c, x509.BasicConstraints)
    prob = []
    if ku is None:
        prob.append("sem keyUsage")
    else:
        if not ku.digital_signature:
            prob.append("keyUsage sem digitalSignature")
        if ku.key_cert_sign:
            prob.append("keyUsage com keyCertSign")
    if bc is not None and bc.ca:
        prob.append("basicConstraints CA no certificado da urna")
    return not prob, prob


def autoridade_ok(ac) -> tuple[bool, list[str]]:
    """Certificado de AC: basicConstraints CA e keyUsage com keyCertSign."""
    from cryptography import x509
    ku, bc = _ext(ac, x509.KeyUsage), _ext(ac, x509.BasicConstraints)
    prob = []
    if bc is None or not bc.ca:
        prob.append("AC sem basicConstraints CA")
    if ku is not None and not ku.key_cert_sign:
        prob.append("AC sem keyCertSign")
    return not prob, prob


def avaliar_vscmr(raw: bytes, turno: int, acs: list, cert_catalogo: Optional[str] = None) -> dict:
    """Uma linha (sem a chave da seção) a partir dos bytes do .vscmr."""
    dia = DIAS[int(turno)]
    linha: dict = {"critica": False}
    motivos: list[str] = []
    try:
        v = S.parse_vsc(raw)
        i = A26.info_vsc(raw)
    except Exception as e:  # noqa: BLE001 - arquivo ilegível vira linha crítica
        return {"critica": True, "assinatura_confere": False,
                "motivo": f"vscmr ilegível: {e}"[:300]}
    if "erro" in i:
        return {"critica": True, "assinatura_confere": False, "motivo": i["erro"]}
    c = i["_cert"]
    ini, fim = c.not_valid_before_utc, c.not_valid_after_utc
    cod = v["modelo_cod"]
    linha.update({
        "modelo": MODELOS_URNA.get(cod, f"Modelo_{cod}") if cod is not None else None,
        "cn": i["cn"], "cn_confere_usuario": (i["cn"] or "").upper() == (i["usuario"] or "").upper(),
        "cert_sha256": i["sha256"],
        "confere_catalogo": None if not cert_catalogo else cert_catalogo == i["sha256"],
        "algoritmo_chave": A26.familia_alg(i["oid_chave"]) or i["oid_chave"],
        "emissor": A26.cn_de_subject(i["issuer"]) or i["issuer"],
        "not_before": ini, "not_after": fim, "valido_na_eleicao": bool(ini <= dia <= fim),
    })
    if not linha["valido_na_eleicao"]:
        motivos.append(f"certificado fora da validade no dia do {turno}º turno")
    if not linha["cn_confere_usuario"]:
        motivos.append(f"CN {i['cn']} difere do usuário da assinatura {i['usuario']}")
    if linha["confere_catalogo"] is False:
        motivos.append("SHA-256 do certificado difere do registrado em secoes.parquet")
    ok_uso, prob_uso = uso_chave_urna(c)
    linha["uso_chave_ok"] = ok_uso
    motivos += prob_uso

    # a chave pública do certificado valida a assinatura do conteúdo assinado
    ver = S.verificar_vsc(raw, arquivos_verificar=set())
    linha["assinatura_confere"] = ver["assinatura_valida"]
    if ver["assinatura_valida"] is not True:
        linha["critica"] = True
        motivos += ["assinatura: " + m for m in (ver["falhas"] or ver["motivos"]
                                                 or ["não verificada"])]

    ok, desc, ac = A26.validar_cadeia(i, acs) if acs else (None, "AC emissora ausente", None)
    linha["cadeia_ok"] = ok
    if ok is False:
        linha["critica"] = True
    if ok is not True:
        motivos.append(desc)
    if ac is not None:
        nivel, caminho = A26.subir_cadeia(ac, acs)
        a_ini, a_fim = ac.not_valid_before_utc, ac.not_valid_after_utc
        ok_ac, prob_ac = autoridade_ok(ac)
        linha.update({
            "ac_cn": A26._cn_cert(ac),
            "ac_emissor": A26.cn_de_subject(ac.issuer.rfc4514_string()),
            "ac_valida_na_eleicao": bool(a_ini <= dia <= a_fim),
            "ac_autoridade_ok": ok_ac,
            "emitido_na_validade_da_ac": bool(a_ini <= ini <= a_fim),
            "nivel_cadeia": nivel,
            "cadeia_caminho": " > ".join([i["cn"] or "?"] + caminho),
        })
        motivos += prob_ac
        if not linha["ac_valida_na_eleicao"]:
            motivos.append(f"{linha['ac_cn']} fora da validade no dia do {turno}º turno")
        if not linha["emitido_na_validade_da_ac"]:
            motivos.append(f"certificado emitido fora da validade da {linha['ac_cn']}")
    linha["motivo"] = "; ".join(motivos) or None
    return linha


# ---------------------------------------------------------------------------
# Coleta por estrato (turno, UF)
# ---------------------------------------------------------------------------

class FalhaCritica(RuntimeError):
    """Cadeia inválida ou assinatura que não fecha com o certificado."""


def registrar_falha(pasta: Path, registro: dict) -> None:
    p = pasta / "certificados_amostra_falhas.jsonl"
    with open(p, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(registro, ensure_ascii=False, default=str) + "\n")
        fh.flush()
        import os
        os.fsync(fh.fileno())
    log.error("FALHA %s", json.dumps(registro, ensure_ascii=False, default=str))


def partes_dir(pasta: Path) -> Path:
    return pasta / "certificados_amostra_partes"


def nome_parte(turno: int, uf: str) -> str:
    return f"t{int(turno)}_{uf}.parquet"


async def coletar_estrato(fetcher, turno: int, uf: str, amostra: pd.DataFrame, acs: list,
                          pasta: Path, parar: bool = True) -> pd.DataFrame:
    """Lê o .vscmr de cada seção da amostra do estrato e grava a parte."""
    from fetch_integridade import ler_entradas  # noqa: PLC0415 - mesmo diretório

    url = Z.url_pacote_2022(turno, uf)
    cab = await fetcher.head(url)
    linhas: list[dict] = []
    if cab is None:
        linhas = [{**dict(zip(CHAVE, k, strict=True)), "critica": False,
                   "motivo": "pacote indisponível"}
                  for k in amostra[CHAVE].itertuples(index=False, name=None)]
    else:
        entradas = await ler_entradas(fetcher, url, cab["tamanho"])
        vscmr = {}
        for e in entradas:
            p = Z.parse_nome_v1(e.nome)
            if p and p["ext"] == "vscmr":
                vscmr[(p["cd_mun"], p["zona"], p["secao"])] = e
        del entradas

        async def uma(r) -> dict:
            base = {"turno": int(turno), "uf": uf, "cd_mun": r.cd_mun, "zona": r.zona,
                    "secao": r.secao}
            e = vscmr.get((r.cd_mun, r.zona, r.secao))
            if e is None:
                return {**base, "critica": False, "motivo": "vscmr ausente no pacote"}
            buf = await fetcher.faixa(url, e.offset, e.fim)
            raw = Z.extrair(buf, e.offset, e)
            sha_cat = getattr(r, "cert_sha256", None)
            return {**base, **avaliar_vscmr(raw, turno, acs,
                                            sha_cat if isinstance(sha_cat, str) else None)}

        tarefas = [asyncio.ensure_future(uma(r)) for r in amostra.itertuples(index=False)]
        try:
            for fut in asyncio.as_completed(tarefas):
                linha = await fut
                linhas.append(linha)
                if linha.get("critica"):
                    registrar_falha(pasta, {"secao_id": "{}T/{}/{}/{}/{}".format(
                        *[linha[k] for k in CHAVE]), **{k: linha.get(k) for k in (
                            "modelo", "cn", "emissor", "cert_sha256", "assinatura_confere",
                            "cadeia_ok", "motivo")}})
                    if parar:
                        raise FalhaCritica(linha.get("motivo") or "falha crítica")
        finally:
            for t in tarefas:
                t.cancel()
    df = pd.DataFrame(linhas).reindex(columns=COLS).sort_values(CHAVE).reset_index(drop=True)
    d = partes_dir(pasta)
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / (nome_parte(turno, uf) + ".tmp")
    df.to_parquet(tmp, index=False)
    tmp.replace(d / nome_parte(turno, uf))
    return df


async def coletar(amostra: pd.DataFrame, fetcher, acs: list, pasta: Path,
                  parar: bool = True) -> dict:
    st = {"estratos": 0, "ja_feitos": 0, "secoes": 0, "inicio": time.time()}
    for (turno, uf), g in amostra.groupby(["turno", "uf"], sort=True):
        if (partes_dir(pasta) / nome_parte(turno, uf)).exists():
            st["ja_feitos"] += 1
            continue
        t0 = time.time()
        df = await coletar_estrato(fetcher, int(turno), uf, g, acs, pasta, parar)
        st["estratos"] += 1
        st["secoes"] += len(df)
        log.info("%sT/%s: %d seções em %.0f s; cadeia_ok %s; assinatura %s; http %s",
                 turno, uf, len(df), time.time() - t0,
                 dict(Counter(df["cadeia_ok"].astype(str))),
                 dict(Counter(df["assinatura_confere"].astype(str))),
                 getattr(fetcher, "stats", {}))
    st["segundos"] = round(time.time() - st.pop("inicio"), 1)
    return st


# ---------------------------------------------------------------------------
# Consolidação e resumo
# ---------------------------------------------------------------------------

def consolidar(pasta: Path) -> pd.DataFrame:
    frames = []
    for p in sorted(partes_dir(pasta).glob("t*_*.parquet")):
        frames.append(pd.read_parquet(p))
    if not frames:
        return pd.DataFrame(columns=COLS)
    df = pd.concat(frames, ignore_index=True).reindex(columns=COLS)
    df = df.drop_duplicates(CHAVE, keep="last").sort_values(CHAVE).reset_index(drop=True)
    tmp = pasta / "certificados_amostra.parquet.tmp"
    df.to_parquet(tmp, index=False)
    tmp.replace(pasta / "certificados_amostra.parquet")
    return df


def _cont(s: pd.Series) -> dict:
    def rot(v) -> str:
        return "indeterminado" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v)
    return {k: int(v) for k, v in s.astype(object).map(rot).value_counts().items()}


def _iso(s: pd.Series) -> tuple[Optional[str], Optional[str]]:
    s = pd.to_datetime(s, utc=True).dropna()
    return (s.min().isoformat(), s.max().isoformat()) if len(s) else (None, None)


def resumir(df: pd.DataFrame, estratos: dict, semente: int, fracao: float,
            ac_dir: Optional[Path]) -> dict:
    com = df[df["cert_sha256"].notna()]
    alvo = sum(n for _N, n in estratos.values())
    out: dict = {
        "gerado_em": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "amostra": {
            "fracao": fracao, "semente": semente,
            "criterio": ("estratos (turno, UF) de secoes.parquet; em cada um, ceil(fração x N) "
                         "seções de menor SHA-256 de '<semente>|<turno>|<uf>|<cd_mun>|<zona>|<secao>'"),
            "universo": int(sum(N for N, _n in estratos.values())),
            "secoes_sorteadas": int(alvo),
            "estratos": {k: {"universo": N, "amostra": n} for k, (N, n) in sorted(estratos.items())},
        },
        "dias_eleicao": {f"{t}T": d.isoformat() for t, d in DIAS.items()},
        "secoes_processadas": int(len(df)),
        "situacao": "concluído" if len(df) >= alvo and alvo else "em andamento",
        "com_certificado": int(len(com)),
        "sem_certificado_por_motivo": {str(k): int(v) for k, v in
                                       df[df["cert_sha256"].isna()]["motivo"].fillna("?")
                                       .value_counts().items()},
        "cadeia_ok": _cont(com["cadeia_ok"]),
        "assinatura_confere": _cont(com["assinatura_confere"]),
        "valido_na_eleicao": _cont(com["valido_na_eleicao"]),
        "uso_chave_ok": _cont(com["uso_chave_ok"]),
        "cn_confere_usuario": _cont(com["cn_confere_usuario"]),
        "confere_catalogo": _cont(com["confere_catalogo"]),
        "ac_valida_na_eleicao": _cont(com["ac_valida_na_eleicao"]),
        "ac_autoridade_ok": _cont(com["ac_autoridade_ok"]),
        "emitido_na_validade_da_ac": _cont(com["emitido_na_validade_da_ac"]),
        "nivel_cadeia": _cont(com["nivel_cadeia"]),
        "certificados_distintos": int(com["cert_sha256"].nunique()),
        "falhas_criticas": int(df["critica"].fillna(False).astype(bool).sum()),
    }
    por_turno = {}
    for t, g in com.groupby("turno"):
        por_turno[f"{int(t)}T"] = {"secoes": int(len(g)), "cadeia_ok": _cont(g["cadeia_ok"]),
                                   "assinatura_confere": _cont(g["assinatura_confere"]),
                                   "valido_na_eleicao": _cont(g["valido_na_eleicao"])}
    out["por_turno"] = por_turno
    por_uf = {}
    for (t, uf), g in df.groupby(["turno", "uf"]):
        gg = g[g["cert_sha256"].notna()]
        por_uf[f"{int(t)}T/{uf}"] = {
            "secoes": int(len(g)),
            "cadeia_ok": int((gg["cadeia_ok"] == True).sum()),  # noqa: E712
            "assinatura_confere": int((gg["assinatura_confere"] == True).sum()),  # noqa: E712
            "valido_na_eleicao": int((gg["valido_na_eleicao"] == True).sum()),  # noqa: E712
            "uso_chave_ok": int((gg["uso_chave_ok"] == True).sum()),  # noqa: E712
        }
    out["por_turno_uf"] = por_uf
    por = {}
    for (em, mod, alg), g in com.groupby(["emissor", "modelo", "algoritmo_chave"], dropna=False):
        nb = _iso(g["not_before"])
        na = _iso(g["not_after"])
        por.setdefault(str(em), []).append({
            "modelo": str(mod), "algoritmo": str(alg), "secoes": int(len(g)),
            "nao_antes_min": nb[0], "nao_antes_max": nb[1],
            "nao_depois_min": na[0], "nao_depois_max": na[1],
            "cadeia_ok": _cont(g["cadeia_ok"]),
            "caminhos": {str(k): int(v) for k, v in g["cadeia_caminho"].fillna("?").str.replace(
                r"^[^>]*> ", "", regex=True).value_counts().items()},
            "ac_emissor": sorted(g["ac_emissor"].dropna().unique().tolist()),
        })
    out["por_emissor"] = por
    prob = com[com["motivo"].notna()]
    out["observacoes"] = {
        "n": int(len(prob)),
        "por_motivo": {str(k): int(v) for k, v in prob["motivo"].value_counts().head(30).items()},
        "exemplos": [{"secao_id": "{}T/{}/{}/{}/{}".format(r.turno, r.uf, r.cd_mun, r.zona, r.secao),
                      "motivo": r.motivo} for r in prob.head(MAX_EXEMPLOS).itertuples()],
    }
    crit = df[df["critica"].fillna(False).astype(bool)]
    out["falhas"] = [{"secao_id": "{}T/{}/{}/{}/{}".format(r.turno, r.uf, r.cd_mun, r.zona, r.secao),
                      "motivo": r.motivo} for r in crit.itertuples()]
    if ac_dir is not None and Path(ac_dir).exists():
        fichas = A26.descrever_acs(Path(ac_dir), DIAS[1])
        for f in fichas:
            ac_ini = datetime.fromisoformat(f["nao_antes"])
            ac_fim = datetime.fromisoformat(f["nao_depois"])
            f["valida_no_dia_da_eleicao"] = {f"{t}T": bool(ac_ini <= d <= ac_fim)
                                             for t, d in DIAS.items()}
        out["acs"] = fichas
    out["raiz"] = {
        "disponivel": False,
        "acs_superiores": {"AC URNA": "AC RAIZ UE", "AC UE2020": "AC URNA v2 (sob AC RAIZ UE v2)"},
        "explicacao": ("os certificados AC RAIZ UE, AC RAIZ UE v2 e AC URNA v2 não estão nos "
                       ".vscmr (cada um traz só o certificado da urna) nem publicados em endereço "
                       "que se possa baixar; a cadeia é conferida até a AC intermediária"),
        "tentativas": RAIZ_TENTATIVAS,
        "sha512_resumo_oficial_tse_2026": {k: v for k, v in A26.RESUMO_OFICIAL_SHA512.items()
                                           if k in ("acraiz-ue.pem", "acraizuev2.cer",
                                                    "acurnav2.cer")},
    }
    return out


# ---------------------------------------------------------------------------
# Execução
# ---------------------------------------------------------------------------

def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pasta", default=str(PASTA))
    ap.add_argument("--ac", default=str(AC_PADRAO), help="diretório com os certificados das AC")
    ap.add_argument("--semente", type=int, default=SEMENTE)
    ap.add_argument("--fracao", type=float, default=FRACAO)
    ap.add_argument("--turnos", default="1,2")
    ap.add_argument("--ufs", help="só estas UFs (ex.: rr,ac); padrão todas, inclusive zz")
    ap.add_argument("--taxa", type=float, default=6.0, help="requisições por segundo")
    ap.add_argument("--paralelos", type=int, default=3, help="requisições simultâneas")
    ap.add_argument("--nao-parar", action="store_true",
                    help="registra falha crítica e continua (padrão: para na primeira)")
    ap.add_argument("--so-consolidar", action="store_true")
    return ap.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    pasta = Path(args.pasta)
    secoes = pd.read_parquet(pasta / "secoes.parquet", columns=CHAVE + ["cert_sha256"])
    amostra, estratos = sortear_amostra(secoes, args.fracao, args.semente)
    turnos = {int(t) for t in args.turnos.split(",")}
    sel = amostra[amostra["turno"].isin(turnos)]
    if args.ufs:
        sel = sel[sel["uf"].isin([u.strip().lower() for u in args.ufs.split(",")])]
    ac_dir = Path(args.ac) if args.ac else None
    acs = A26.carregar_acs(ac_dir) if ac_dir and ac_dir.exists() else []
    log.info("amostra: %d seções em %d estratos (semente %d); nesta execução: %d; AC: %d",
             len(amostra), len(estratos), args.semente, len(sel), len(acs))
    codigo = 0
    if not args.so_consolidar:
        from fetch_integridade import RangeFetcher  # noqa: PLC0415

        async def rodar() -> dict:
            f = RangeFetcher(args.taxa, args.paralelos)
            try:
                return await coletar(sel, f, acs, pasta, parar=not args.nao_parar)
            finally:
                log.info("http: %s", f.stats)
                await f.close()

        try:
            log.info("execução: %s", asyncio.run(rodar()))
        except FalhaCritica as e:
            log.error("PARADA por falha crítica: %s (ver certificados_amostra_falhas.jsonl)", e)
            codigo = 3
    df = consolidar(pasta)
    res = resumir(df, estratos, args.semente, args.fracao, ac_dir)
    (pasta / "certificados_amostra.json").write_text(
        json.dumps(res, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    log.info("processadas %d de %d; cadeia_ok %s; assinatura %s; válido %s; falhas %d",
             res["secoes_processadas"], res["amostra"]["secoes_sorteadas"], res["cadeia_ok"],
             res["assinatura_confere"], res["valido_na_eleicao"], res["falhas_criticas"])
    return codigo


if __name__ == "__main__":
    sys.exit(main())
