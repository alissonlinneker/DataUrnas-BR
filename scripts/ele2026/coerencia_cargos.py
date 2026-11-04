#!/usr/bin/env python3
"""Cross-office coherence inside each BU, 2026 general election.

A 2026 BU carries two elections: the federal one (President) and the state one
(Governor, Senator, Federal Deputy, State or District Deputy). Inside each
election the offices are grouped in blocks (``resultadosVotacao``), one per
``tipoCargo`` (majoritario / proporcional), and each block has its own turnout
(``qtdComparecimento``). Every voter who signs in at a section votes for every
office on the ballot, so the turnout must be the same in every block of the same
BU, and each office must close:

    nominal + blank + null (+ party/legenda for proportional offices)
        = seats_per_voter x turnout

where seats_per_voter is 2 for Senator in 2026 (two seats per UF) and 1 for
every other office. The script does not assume this: it records the observed
ratio and reports its distribution before applying the rule.

Subcommands:

  extrair    read only the BU members of the TSE bulk package zips
             (bu_imgbu_logjez_rdv_vscmr_<year>_<t>t_<UF>.zip) through HTTP Range
             requests, one request per member on keep-alive connections (at
             most --conns concurrent connections to the CDN), decode them with
             a process pool and write, per year/round/UF:
               cargos_<year>_<t>_<uf>.parquet  one row per section and office
               votos_<year>_<t>_<uf>.parquet   nominal votes per candidate for
                                               President and Governor
               erros_<year>_<t>_<uf>.json      members that failed
             Year/round/UF triples already written are skipped. With --sa only
             the Sistema de Apuração BUs (-busa.dat / .busa) are read, into
             files with the suffix _sa; run it too, otherwise the 2026 abroad
             contingency sections and 2 MG sections are missing.

  relatorio  coherence checks (turnout and eligible voters across offices,
             closure per office, code and party consistency, expected office
             set per UF), comparison of the BU sums with the official
             municipality/zone detail file, and the split-ticket analysis of
             the Governor runoff UFs (President 13 share against Governor
             share per section, municipality fixed effects model, standardized
             residual outliers) for 2026 and, as a base rate, 2022.

Usage (analysis server):
  uv run python scripts/ele2026/coerencia_cargos.py extrair --ano 2026 --turno 1 \\
      --saida ~/dataurnas-coerencia
  uv run python scripts/ele2026/coerencia_cargos.py extrair --ano 2026 --turno 2 \\
      --ufs AC,AM,DF,ES,RN,TO --saida ~/dataurnas-coerencia
  uv run python scripts/ele2026/coerencia_cargos.py extrair --ano 2022 --turno 2 \\
      --ufs AL,AM,BA,ES,MS,PB,PE,RO,RS,SC,SE,SP --saida ~/dataurnas-coerencia
  uv run python scripts/ele2026/coerencia_cargos.py relatorio \\
      --saida ~/dataurnas-coerencia --detalhe ~/dataurnas-historico/zip
"""

from __future__ import annotations

import argparse
import http.client
import json
import math
import os
import struct
import sys
import threading
import time
import zipfile
import zlib
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT / "src"), str(ROOT / "scripts" / "ele2026")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

URL = ("https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes{ano}/arqurnatot/"
       "bu_imgbu_logjez_rdv_vscmr_{ano}_{t}t_{uf}.zip")
UFS = ("AC AL AM AP BA CE DF ES GO MA MG MS MT PA PB PE PI PR RJ RN RO RR RS SC SE SP TO ZZ"
       .split())
# BU member suffix per year: 2026 uses "<id>-bu.dat", 2022 uses "<id>.bu".
SUFIXO_BU = {2026: "-bu.dat", 2022: ".bu"}
# BU produced by the Sistema de Apuração (contingency counting, e.g. abroad
# sections and sections whose machine failed): "<id>-busa.dat" / "<id>.busa".
SUFIXO_SA = {2026: "-busa.dat", 2022: ".busa"}

# Number of digits of a nominal vote code per office (the first two digits are
# the party number). Party (legenda) votes carry the 2-digit party number.
DIGITOS = {"presidente": 2, "governador": 2, "senador": 3, "deputadoFederal": 4,
           "deputadoEstadual": 5, "deputadoDistrital": 5}
# Official office codes used in the TSE open data files.
CD_CARGO = {"presidente": 1, "governador": 3, "senador": 5, "deputadoFederal": 6,
            "deputadoEstadual": 7, "deputadoDistrital": 8, "prefeito": 11, "vereador": 13}
TIPOS_VOTO = {1: "nominal", 2: "branco", 3: "nulo", 4: "legenda", 5: "cargoSemCandidato"}


def _log(msg: str) -> None:
    print(time.strftime("%H:%M:%S"), msg, flush=True)


# ---------------------------------------------------------------------------
# Member download: one HTTP Range request per zip member on keep-alive
# connections (one connection per thread).
# ---------------------------------------------------------------------------

_TLS = threading.local()
# Slack for the local header extra field, which may differ from the central
# directory copy (ZIP64 or timestamp fields).
_FOLGA = 1024


def _conexao(host: str) -> http.client.HTTPSConnection:
    c = getattr(_TLS, "conn", None)
    if c is None:
        c = _TLS.conn = http.client.HTTPSConnection(host, timeout=120)
    return c


def _range(url: str, ini: int, fim: int) -> bytes:
    """GET bytes [ini, fim] of url, retrying with a fresh connection on errors."""
    u = urlsplit(url)
    for tentativa in range(6):
        try:
            c = _conexao(u.netloc)
            c.request("GET", u.path, headers={"Range": f"bytes={ini}-{fim}"})
            r = c.getresponse()
            data = r.read()
            if r.status != 206:
                raise OSError(f"HTTP {r.status}")
            return data
        except (OSError, http.client.HTTPException):
            c = getattr(_TLS, "conn", None)
            if c is not None:
                c.close()
            _TLS.conn = None
            if tentativa == 5:
                raise
            time.sleep(2 ** tentativa)
    raise AssertionError("unreachable")


def baixar_membro(url: str, info: dict) -> bytes:
    """Download and inflate one zip member, checking its CRC-32."""
    ini = info["offset"]
    fim = ini + 30 + info["nlen"] + _FOLGA + info["csize"] - 1
    data = _range(url, ini, fim)
    if data[:4] != b"PK\x03\x04":
        raise ValueError("bad local header signature")
    n, m = struct.unpack("<HH", data[26:30])
    off = 30 + n + m
    if off + info["csize"] > len(data):
        data += _range(url, ini + len(data), ini + off + info["csize"] - 1)
    comp = data[off:off + info["csize"]]
    if info["metodo"] == zipfile.ZIP_DEFLATED:
        raw = zlib.decompress(comp, -15)
    elif info["metodo"] == zipfile.ZIP_STORED:
        raw = comp
    else:
        raise ValueError(f"compression method {info['metodo']}")
    if zlib.crc32(raw) != info["crc"]:
        raise ValueError("CRC mismatch")
    return raw


def baixar_lote(args: tuple) -> list[tuple[str, bytes | None, str | None]]:
    url, lote = args
    out = []
    for info in lote:
        try:
            out.append((info["nome"], baixar_membro(url, info), None))
        except Exception as e:  # noqa: BLE001 - recorded per member
            out.append((info["nome"], None, f"download: {e!r}"))
    return out


# ---------------------------------------------------------------------------
# BU decoding
# ---------------------------------------------------------------------------

def _choice(v):
    """Second element of an ASN.1 CHOICE tuple ('name', value), else the value."""
    if isinstance(v, tuple) and len(v) == 2:
        return v[1]
    return v


def _nome_enum(v, mapa: dict | None = None):
    """Enumerated value as a string (decoders may return the name or the number)."""
    if isinstance(v, tuple):
        v = v[0] if isinstance(v[0], str) else v[1]
    if isinstance(v, int) and mapa:
        return mapa.get(v, str(v))
    return v


def decodificar_bu(raw: bytes, ano: int, turno: int, uf: str, nome: str) -> dict:
    """Every office of one BU: one row per office plus President/Governor votes."""
    from dataurnas.models import SpecVersion
    from dataurnas.parsers.asn1_helper import decode_envelope
    from dataurnas.parsers.bu import _CARGO_NAME_MAP, BUParser

    try:
        spec = SpecVersion.V2
        env, bu = decode_envelope(raw, "EntidadeBoletimUrna", spec)
    except Exception:
        spec = SpecVersion.V1
        env, bu = decode_envelope(raw, "EntidadeBoletimUrna", spec)
    b = BUParser()._build_bu(env, bu, spec)
    cargo_nome = {v: k for k, v in _CARGO_NAME_MAP.items()}
    chave = {"ano": ano, "turno": turno, "uf": uf, "cd_mun": int(b.municipio or 0),
             "zona": int(b.zona or 0), "secao": int(b.secao or 0), "nome": nome}
    cargos, votos = [], []
    for e in bu.get("resultadosVotacaoPorEleicao", []):
        for rv in e.get("resultadosVotacao", []):
            tipo_cargo = _nome_enum(rv.get("tipoCargo"), {1: "majoritario", 2: "proporcional"})
            comp = rv.get("qtdComparecimento")
            for t in rv.get("totaisVotosCargo", []):
                cod = _choice(t.get("codigoCargo"))
                cargo = cod if isinstance(cod, str) else cargo_nome.get(cod, f"cargo{cod}")
                cnt: Counter = Counter()
                cod_inv = par_inv = neg = 0
                for vv in t.get("votosVotaveis", []):
                    tipo = _nome_enum(vv.get("tipoVoto"), TIPOS_VOTO)
                    q = int(vv.get("quantidadeVotos", 0) or 0)
                    neg += q < 0
                    cnt[tipo] += q
                    ident = vv.get("identificacaoVotavel") or {}
                    codigo, partido = ident.get("codigo"), ident.get("partido")
                    if tipo == "nominal":
                        dig = DIGITOS.get(cargo)
                        if codigo is None or (dig and len(str(codigo)) != dig):
                            cod_inv += 1
                        elif partido is not None and str(codigo)[:2] != str(partido):
                            par_inv += 1
                        if cargo in ("presidente", "governador") and codigo is not None:
                            votos.append({**chave, "cargo": cargo, "codigo": int(codigo),
                                          "votos": q})
                    elif tipo == "legenda":
                        if codigo is None or len(str(codigo)) != 2:
                            cod_inv += 1
                        elif partido is not None and int(codigo) != int(partido):
                            par_inv += 1
                conhecidos = ("nominal", "branco", "nulo", "legenda", "cargoSemCandidato")
                cargos.append({
                    **chave, "tipo_urna": b.tipo_urna, "tipo_arquivo": b.tipo_arquivo,
                    "id_eleicao": int(e.get("idEleicao", 0) or 0),
                    "aptos": e.get("qtdEleitoresAptos"),
                    "aptos_secao": e.get("qtdEleitoresAptosSecao"),
                    "aptos_tte": e.get("qtdEleitoresAptosTTE"),
                    "tipo_cargo": str(tipo_cargo), "cargo": str(cargo),
                    "comparecimento": None if comp is None else int(comp),
                    "nominal": cnt["nominal"], "branco": cnt["branco"], "nulo": cnt["nulo"],
                    "legenda": cnt["legenda"], "sem_candidato": cnt["cargoSemCandidato"],
                    "outros": sum(v for k, v in cnt.items() if k not in conhecidos),
                    "total": sum(cnt.values()),
                    "n_votaveis": len(t.get("votosVotaveis", [])),
                    "codigo_invalido": cod_inv, "partido_invalido": par_inv,
                    "negativos": neg,
                    "chaves_extra": ",".join(sorted(set(t) - {"codigoCargo", "ordemImpressao",
                                                                 "votosVotaveis"})) or None,
                })
    return {"cargos": cargos, "votos": votos}


def decodificar_lote(args: tuple) -> dict:
    ano, turno, uf, itens = args
    cargos, votos, erros = [], [], []
    for nome, raw, erro in itens:
        if raw is None:
            erros.append({"nome": nome, "erro": erro})
            continue
        try:
            d = decodificar_bu(raw, ano, turno, uf, nome)
        except Exception as e:  # noqa: BLE001 - recorded per member
            erros.append({"nome": nome, "erro": f"decode: {e!r}"})
            continue
        if not d["cargos"]:
            erros.append({"nome": nome, "erro": "BU without any office"})
        cargos += d["cargos"]
        votos += d["votos"]
    return {"cargos": cargos, "votos": votos, "erros": erros}


# ---------------------------------------------------------------------------
# extrair
# ---------------------------------------------------------------------------

def membros(url: str, sufixo: str) -> tuple[list[dict], str | None]:
    """BU members listed in the central directory of a remote zip."""
    from confronto_pacote_t2 import HttpRangeFile

    f = HttpRangeFile(url)
    z = zipfile.ZipFile(f)
    out = [{"nome": i.filename, "offset": i.header_offset, "csize": i.compress_size,
            "nlen": len(i.filename.encode("utf-8" if i.flag_bits & 0x800 else "cp437")),
            "metodo": i.compress_type, "crc": i.CRC}
           for i in z.infolist() if i.filename.endswith(sufixo)]
    return out, f.last_modified


def cmd_extrair(a: argparse.Namespace) -> None:
    import pyarrow as pa
    import pyarrow.parquet as pq

    saida = Path(a.saida).expanduser()
    saida.mkdir(parents=True, exist_ok=True)
    ufs = a.ufs.split(",") if a.ufs else UFS
    with ThreadPoolExecutor(a.conns) as tex, ProcessPoolExecutor(a.workers) as pex:
        for uf in ufs:
            base = f"{a.ano}_{a.turno}_{uf.lower()}" + ("_sa" if a.sa else "")
            if (saida / f"cargos_{base}.parquet").exists():
                continue
            t0 = time.time()
            url = URL.format(ano=a.ano, t=a.turno, uf=uf)
            infos, last_mod = membros(url, (SUFIXO_SA if a.sa else SUFIXO_BU)[a.ano])
            lotes = [infos[i:i + a.lote] for i in range(0, len(infos), a.lote)]
            futs = [pex.submit(decodificar_lote, (a.ano, a.turno, uf, itens))
                    for itens in tex.map(baixar_lote, [(url, lt) for lt in lotes])]
            cargos, votos, erros = [], [], []
            for f in futs:
                r = f.result()
                cargos += r["cargos"]
                votos += r["votos"]
                erros += r["erros"]
            pq.write_table(pa.Table.from_pylist(votos), saida / f"votos_{base}.parquet")
            (saida / f"erros_{base}.json").write_text(json.dumps(
                {"url": url, "last_modified": last_mod, "membros": len(infos),
                 "erros": erros}, ensure_ascii=False, indent=1))
            # cargos last: its presence marks the UF as done
            pq.write_table(pa.Table.from_pylist(cargos), saida / f"cargos_{base}.parquet")
            _log(f"{base}: {len(infos)} BUs, {len(cargos)} office rows, {len(votos)} vote "
                 f"rows, {len(erros)} errors, {time.time() - t0:.0f}s")


# ---------------------------------------------------------------------------
# relatorio
# ---------------------------------------------------------------------------

def _r(x, n=4):
    try:
        x = float(x)
    except (TypeError, ValueError):
        return x
    return None if math.isnan(x) or math.isinf(x) else round(x, n)


def _ler(saida: Path, padrao: str):
    import pandas as pd

    ps = sorted(saida.glob(padrao))
    return pd.concat([pd.read_parquet(p) for p in ps], ignore_index=True) if ps else None


def checar_coerencia(df):
    """Per office row flags and per section summary of the coherence checks.

    Returns (rows with any divergence, summary dict, seat ratio table)."""
    import numpy as np

    sec = ["ano", "turno", "uf", "cd_mun", "zona", "secao", "nome"]
    df = df.copy()
    # Seats per voter observed: total votes / turnout, per year, round and office.
    pos = df["comparecimento"] > 0
    df["razao"] = np.where(pos, df["total"] / df["comparecimento"].where(pos, 1), np.nan)
    razoes = (df[pos].assign(razao=lambda d: d["razao"].round(6))
              .groupby(["ano", "turno", "cargo", "razao"]).size()
              .rename("linhas").reset_index())
    # Rule (validated by the ratio table): 2 votes per voter for Senator in 2026.
    df["vagas"] = np.where((df["cargo"] == "senador") & (df["ano"] == 2026), 2, 1)
    df["fecha"] = df["total"] == df["vagas"] * df["comparecimento"]
    df["legenda_majoritario"] = (df["tipo_cargo"] == "majoritario") & (df["legenda"] > 0)
    df["comp_maior_aptos"] = df["comparecimento"] > df["aptos"]
    # aptos = aptos_secao + aptos_tte (fields absent in some spec v1 BUs: not checked there)
    df["aptos_soma"] = df["aptos_secao"].notna() & (
        (df["aptos_secao"] + df["aptos_tte"].fillna(0)) != df["aptos"])
    # Inside one election every office must show the same turnout.
    df["comp_distintos"] = df.groupby(sec + ["id_eleicao"])["comparecimento"].transform("nunique")
    df["linhas_mesmo_cargo"] = df.groupby(sec + ["cargo"])["cargo"].transform("size")

    # Across the federal (President) election and every other election of the
    # same BU (the state one and, where held, a supplementary municipal one)
    # turnout and eligible voters may differ only by transit voters (TTE) who
    # may vote for President only: aptos_secao must match (when the BU spec has
    # it) and 0 <= turnout_fed - turnout_other <= aptos_fed - aptos_other.
    el = df.groupby(sec + ["id_eleicao"]).agg(
        comp=("comparecimento", "first"), aptos=("aptos", "first"),
        aptos_secao=("aptos_secao", "first"), tte=("aptos_tte", "first"),
        fed=("cargo", lambda s: "presidente" in set(s)),
        estadual=("cargo", lambda s: "governador" in set(s))).reset_index()
    fed = el[el.fed].drop(columns=["fed", "estadual", "id_eleicao"])
    out = el[~el.fed].drop(columns=["fed"])
    par = fed.merge(out, on=sec, how="inner", suffixes=("_fed", "_est"))
    par["d_comp"] = par["comp_fed"] - par["comp_est"]
    par["d_aptos"] = par["aptos_fed"] - par["aptos_est"]
    par["d_tte"] = par["tte_fed"] - par["tte_est"]
    par["aptos_divergente"] = (par["aptos_secao_fed"].notna() & par["aptos_secao_est"].notna()
                               & (par["aptos_secao_fed"] != par["aptos_secao_est"]))
    par["comp_eleicoes_inexplicado"] = (par["d_comp"] < 0) | (par["d_comp"] > par["d_aptos"])
    par["comp_eleicoes_difere_tte"] = (par["d_comp"] != 0) & ~par["comp_eleicoes_inexplicado"]
    por_secao = par.groupby(sec).agg(
        aptos_divergente=("aptos_divergente", "any"),
        comp_eleicoes_inexplicado=("comp_eleicoes_inexplicado", "any"),
        comp_eleicoes_difere_tte=("comp_eleicoes_difere_tte", "any"),
        d_comp=("d_comp", "max"), d_aptos=("d_aptos", "max")).reset_index()
    df = df.merge(por_secao, on=sec, how="left")
    for c in ("aptos_divergente", "comp_eleicoes_inexplicado", "comp_eleicoes_difere_tte"):
        df[c] = df[c].fillna(False).astype(bool)

    # Expected office set per UF and round.
    def esperado(ano, turno, uf):
        if turno == 2:
            return None  # depends on the runoff list, checked separately
        if uf == "ZZ":
            return frozenset({"presidente"})
        est = "deputadoDistrital" if uf == "DF" else "deputadoEstadual"
        return frozenset({"presidente", "governador", "senador", "deputadoFederal", est})

    # offices outside the general election (supplementary municipal elections
    # held the same day, including office codes the parser does not name, such
    # as "cargo25" in PE 30015) are reported apart and left out of the
    # expected set
    df["municipal"] = ~df["cargo"].isin(DIGITOS)
    conj = (df[~df["municipal"]].groupby(sec)["cargo"].agg(lambda s: frozenset(s))
            .rename("cargos").reset_index())
    conj["esperado"] = [esperado(a, t, u) for a, t, u in zip(conj.ano, conj.turno, conj.uf, strict=True)]
    conj["cargos_fora_do_esperado"] = [e is not None and c != e
                                       for c, e in zip(conj.cargos, conj.esperado, strict=True)]
    df = df.merge(conj[sec + ["cargos_fora_do_esperado"]], on=sec, how="left")

    contagens = ("codigo_invalido", "partido_invalido", "negativos", "sem_candidato", "outros")
    flags = ["fecha_nao", "comp_divergente", "comp_eleicoes_inexplicado", "aptos_divergente",
             "legenda_majoritario", "comp_maior_aptos", "aptos_soma",
             *(f"f_{c}" for c in contagens), "cargo_repetido", "cargos_fora_do_esperado",
             "f_chaves_extra"]
    df["fecha_nao"] = ~df["fecha"]
    df["comp_divergente"] = df["comp_distintos"] > 1
    df["cargo_repetido"] = df["linhas_mesmo_cargo"] > 1
    for c in contagens:
        df[f"f_{c}"] = df[c].fillna(0) > 0
    df["f_chaves_extra"] = df["chaves_extra"].notna()
    df["alguma"] = df[flags].any(axis=1)

    resumo = {}
    for (ano, turno), d in df.groupby(["ano", "turno"]):
        s = d.groupby(sec)[flags].any()
        resumo[f"{ano}_{turno}t"] = {
            "secoes": int(len(s)), "linhas_cargo": int(len(d)),
            "secoes_por_cargo": {k: int(v) for k, v in d.groupby("cargo")
                                 .apply(lambda x: x[sec].drop_duplicates().shape[0]).items()},
            "secoes_com_divergencia": {f: int(s[f].sum()) for f in flags},
            "secoes_com_qualquer_divergencia": int(s.any(axis=1).sum()),
            # informative, not a divergence: federal and state turnout differ
            # by out-of-state transit voters
            "secoes_comp_fed_est_difere_por_tte": int(
                d.groupby(sec)["comp_eleicoes_difere_tte"].any().sum()),
            "votos_tte_so_presidente": int(
                par[(par.ano == ano) & (par.turno == turno) & par.estadual]["d_comp"].sum()),
            "secoes_com_eleicao_municipal": int(d[d["municipal"]][sec].drop_duplicates().shape[0]),
            "linhas_por_tipo_urna": {str(k): int(v) for k, v in
                                     d["tipo_urna"].value_counts(dropna=False).items()},
            "comparecimento_zero": int((d.groupby(sec)["comparecimento"].max() == 0).sum()),
        }
    cols = sec + ["tipo_urna", "id_eleicao", "aptos", "aptos_secao", "aptos_tte",
                  "tipo_cargo", "cargo", "comparecimento", "nominal", "branco", "nulo",
                  "legenda", "sem_candidato", "outros", "total", "vagas", "codigo_invalido",
                  "partido_invalido", "chaves_extra", "d_comp", "d_aptos"] + flags
    div = df.loc[df.groupby(sec)["alguma"].transform("any"), cols]
    return div, resumo, razoes, par


def conferir_oficial(df, detalhe_zip: Path, ano: int):
    """BU sums per round/UF/municipality/zone/office against the official
    detalhe_votacao_munzona file (turnout, blank, sections)."""
    import pandas as pd

    if not detalhe_zip.exists():
        return None
    with zipfile.ZipFile(detalhe_zip) as z:
        nomes = [n for n in z.namelist() if n.endswith(".csv") and "BRASIL" not in n]
        of = pd.concat([pd.read_csv(z.open(n), sep=";", encoding="latin1",
                                    usecols=["NR_TURNO", "SG_UF", "CD_MUNICIPIO", "NR_ZONA",
                                             "CD_CARGO", "QT_APTOS", "QT_COMPARECIMENTO",
                                             "QT_VOTOS_BRANCOS", "QT_TOTAL_SECOES",
                                             "QT_SECOES_PRINCIPAIS",
                                             "QT_SECOES_NAO_INSTALADAS"])
                        for n in nomes], ignore_index=True)
    of = of.rename(columns={"NR_TURNO": "turno", "SG_UF": "uf", "CD_MUNICIPIO": "cd_mun",
                            "NR_ZONA": "zona", "CD_CARGO": "cd_cargo", "QT_APTOS": "of_aptos",
                            "QT_COMPARECIMENTO": "of_comp", "QT_VOTOS_BRANCOS": "of_branco",
                            "QT_TOTAL_SECOES": "of_secoes",
                            "QT_SECOES_PRINCIPAIS": "of_secoes_principais",
                            "QT_SECOES_NAO_INSTALADAS": "of_nao_instaladas"})
    d = df[df["ano"] == ano].copy()
    d["cd_cargo"] = d["cargo"].map(CD_CARGO)
    bu = (d.groupby(["turno", "uf", "cd_mun", "zona", "cd_cargo"])
          .agg(bu_comp=("comparecimento", "sum"), bu_branco=("branco", "sum"),
               bu_aptos=("aptos", "sum"), bu_secoes=("secao", "size")).reset_index())
    keys = ["turno", "uf", "cd_mun", "zona", "cd_cargo"]
    # only the round/UF pairs that were extracted
    lidos = d[["turno", "uf"]].drop_duplicates()
    m = bu.merge(of.merge(lidos, on=["turno", "uf"]), on=keys, how="outer", indicator=True)
    m["dif_aptos"] = m["bu_aptos"].fillna(0) - m["of_aptos"].fillna(0)
    m["dif_comp"] = m["bu_comp"].fillna(0) - m["of_comp"].fillna(0)
    m["dif_branco"] = m["bu_branco"].fillna(0) - m["of_branco"].fillna(0)
    return m


def split_ticket(votos, ano: int, ufs: list[str]):
    """President x Governor runoff split-ticket analysis per section.

    p = share of President candidate 13 among 13+22 valid votes; g = share of
    the Governor candidate (of the two) whose section share is positively
    correlated with p. Correlations are reported on the share scale.

    Model per UF, on the logit scale so that it stays bounded at the extremes
    (a linear share model overshoots 1 in sections where both 13 and the
    aligned Governor candidate get 99%):
        logit(g) = alpha_municipality + beta * logit(p)
    with empirical logits log((x + 0.5) / (n - x + 0.5)), fitted by weighted
    least squares after the within-municipality transform. The residual
    variance of a section is the binomial variance of the Governor logit plus
    beta^2 times that of the President logit, times an overdispersion factor
    estimated robustly (median of the squared standardized residuals divided
    by the median of a chi-square with one degree of freedom). A section is
    flagged only when it departs from its own municipality's
    President-Governor relation far beyond what the rest of the UF shows."""
    import numpy as np
    import pandas as pd

    sec = ["uf", "cd_mun", "zona", "secao"]
    v = votos[(votos["ano"] == ano) & (votos["turno"] == 2) & votos["uf"].isin(ufs)]
    v = v.groupby(sec + ["cargo", "codigo"], as_index=False)["votos"].sum()
    pres = v[v.cargo == "presidente"].pivot_table(index=sec, columns="codigo", values="votos",
                                                  fill_value=0)
    gov = v[v.cargo == "governador"].pivot_table(index=sec, columns="codigo", values="votos",
                                                 fill_value=0)
    linhas, secoes = [], []
    for uf in ufs:
        if uf not in pres.index.get_level_values(0) or uf not in gov.index.get_level_values(0):
            continue
        p = pres.loc[uf]
        g = gov.loc[uf]
        g = g.loc[:, (g.sum() > 0)]
        cand = list(g.sum().sort_values(ascending=False).index[:2])
        d = pd.DataFrame({"p13": p.get(13, 0), "p22": p.get(22, 0)}).join(
            g[cand].rename(columns={cand[0]: "gA", cand[1]: "gB"}), how="inner").reset_index()
        d.insert(0, "uf", uf)
        d["np"] = d["p13"] + d["p22"]
        d["n"] = d["gA"] + d["gB"]
        d = d[(d["np"] > 0) & (d["n"] > 0)].copy()
        d["p"] = d["p13"] / d["np"]
        d["g"] = d["gA"] / d["n"]
        w = d["n"].to_numpy(float)
        r_bruto = np.corrcoef(d["p"], d["g"])[0, 1]
        cand_alinhado = cand[0]
        if r_bruto < 0:  # orient g to the candidate aligned with 13
            d["g"] = 1 - d["g"]
            d[["gA", "gB"]] = d[["gB", "gA"]].to_numpy()
            cand_alinhado = cand[1]
        cand_outro = cand[1] if cand_alinhado == cand[0] else cand[0]

        def wmean(x, grp, peso):
            return (x * peso).groupby(grp).transform("sum") / peso.groupby(grp).transform("sum")

        mun = d["cd_mun"]
        # share-scale correlations, weighted by n
        pd_ = d["p"] - wmean(d["p"], mun, d["n"])
        gd_ = d["g"] - wmean(d["g"], mun, d["n"])
        r_w = float(np.cov(d["p"], d["g"], aweights=w)[0, 1]
                    / math.sqrt(np.cov(d["p"], aweights=w)[()] * np.cov(d["g"], aweights=w)[()]))
        r_dentro = float((w * pd_ * gd_).sum() / math.sqrt((w * pd_ ** 2).sum() *
                                                           (w * gd_ ** 2).sum()))
        # logit-scale fixed effects model
        lp = np.log((d["p13"] + 0.5) / (d["p22"] + 0.5))
        lg = np.log((d["gA"] + 0.5) / (d["gB"] + 0.5))
        vp = 1 / (d["p13"] + 0.5) + 1 / (d["p22"] + 0.5)
        vg = 1 / (d["gA"] + 0.5) + 1 / (d["gB"] + 0.5)
        peso = 1 / vg
        lpd = lp - wmean(lp, mun, peso)
        lgd = lg - wmean(lg, mun, peso)
        beta = float((peso * lpd * lgd).sum() / (peso * lpd * lpd).sum())
        res = lgd - beta * lpd
        var = vg + beta ** 2 * vp
        phi = float(np.median(res ** 2 / var) / 0.454936)
        d["z"] = res / np.sqrt(phi * var)
        # fitted Governor share implied by the model
        d["ajuste"] = 1 / (1 + np.exp(-(lg - res)))
        grandes = (d["np"] >= 50) & (d["n"] >= 50)
        opostos = grandes & (((d["p"] >= 0.9) & (d["g"] <= 0.1)) |
                             ((d["p"] <= 0.1) & (d["g"] >= 0.9)))
        n = len(d)
        linhas.append({
            "ano": ano, "uf": uf, "secoes": n, "gov_alinhado_13": int(cand_alinhado),
            "gov_outro": int(cand_outro),
            "p13_uf": _r(d["p13"].sum() / d["np"].sum()), "g_uf": _r(d["gA"].sum() / d["n"].sum()),
            "r_secoes": _r(r_w), "r_dentro_municipio": _r(r_dentro), "beta_logit_fe": _r(beta),
            "phi": _r(phi, 3),
            "z_maior_4": int((d["z"].abs() > 4).sum()), "z_maior_5": int((d["z"].abs() > 5).sum()),
            "z_maior_6": int((d["z"].abs() > 6).sum()),
            "pct_z_maior_4": _r(100 * (d["z"].abs() > 4).mean(), 3),
            "esperado_normal_z4": _r(n * math.erfc(4 / math.sqrt(2)), 2),
            "opostos_extremos": int(opostos.sum()),
            "gov_zero_cand_alinhado_n100": int(((d["n"] >= 100) & (d["gA"] == 0)).sum()),
            "gov_zero_outro_n100": int(((d["n"] >= 100) & (d["gB"] == 0)).sum()),
            "pres_zero_13_n100": int(((d["np"] >= 100) & (d["p13"] == 0)).sum()),
            "pres_zero_22_n100": int(((d["np"] >= 100) & (d["p22"] == 0)).sum()),
        })
        d["ano"] = ano
        d["opostos_extremos"] = opostos
        secoes.append(d)
    return pd.DataFrame(linhas), (pd.concat(secoes, ignore_index=True) if secoes else None)


def cmd_relatorio(a: argparse.Namespace) -> None:
    import pandas as pd

    saida = Path(a.saida).expanduser()
    repo = Path(a.repo).expanduser()
    repo.mkdir(parents=True, exist_ok=True)
    df = _ler(saida, "cargos_*.parquet")
    votos = _ler(saida, "votos_*.parquet")
    erros = {}
    for p in sorted(saida.glob("erros_*.json")):
        j = json.loads(p.read_text())
        erros[p.stem[6:]] = {"membros": j["membros"], "erros": len(j["erros"]),
                             "last_modified": j["last_modified"],
                             "exemplos": j["erros"][:5]}

    div, resumo, razoes, par = checar_coerencia(df)
    div.to_parquet(repo / "divergencias.parquet", index=False)
    razoes.to_csv(repo / "razao_votos_comparecimento.csv", index=False)

    # Federal x state election per year/round/UF (runoff: President x Governor).
    secs_uf = df.drop_duplicates(["ano", "turno", "uf", "nome"]).groupby(
        ["ano", "turno", "uf"]).size()
    pares = {}
    for (ano, turno, uf, estadual), d in par.groupby(["ano", "turno", "uf", "estadual"]):
        pares[f"{ano}_{turno}t_{uf}" + ("" if estadual else "_municipal")] = {
            "secoes": int(secs_uf.get((ano, turno, uf), 0)),
            "secoes_com_as_duas_eleicoes": int(len(d)),
            "comp_igual": int((d["d_comp"] == 0).sum()),
            "comp_difere_explicado_tte": int(d["comp_eleicoes_difere_tte"].sum()),
            "comp_difere_inexplicado": int(d["comp_eleicoes_inexplicado"].sum()),
            "aptos_secao_divergente": int(d["aptos_divergente"].sum()),
            "votos_so_presidente_tte": int(d["d_comp"].sum()),
        }

    oficial = {}
    for ano in sorted(df["ano"].unique()):
        z = Path(a.detalhe).expanduser() / f"detalhe_votacao_munzona_{ano}.zip"
        m = conferir_oficial(df, z, int(ano))
        if m is None:
            continue
        ambos = m["_merge"] == "both"
        ruins = m[~ambos | (m["dif_comp"] != 0) | (m["dif_branco"] != 0) | (m["dif_aptos"] != 0)]
        ruins.to_csv(repo / f"conferencia_oficial_{ano}.csv", index=False)
        oficial[str(ano)] = {
            "munzona_cargo": int(len(m)),
            "so_no_bu": int((m["_merge"] == "left_only").sum()),
            "so_no_oficial": int((m["_merge"] == "right_only").sum()),
            "aptos_diferente": int((ambos & (m["dif_aptos"] != 0)).sum()),
            "comparecimento_diferente": int((ambos & (m["dif_comp"] != 0)).sum()),
            "brancos_diferente": int((ambos & (m["dif_branco"] != 0)).sum()),
            "soma_dif_comparecimento": int(m.loc[ambos, "dif_comp"].sum()),
            "por_turno_cargo": {f"{t}t_{c}": {k: int(x[k].sum()) for k in
                                              ("bu_aptos", "of_aptos", "bu_comp", "of_comp",
                                               "bu_branco", "of_branco", "bu_secoes",
                                               "of_secoes", "of_secoes_principais",
                                               "of_nao_instaladas")}
                                for (t, c), x in m.groupby(["turno", "cd_cargo"])},
        }

    # Split ticket in the Governor runoff UFs, 2026 and 2022.
    disp = pd.read_csv(ROOT / "data/parquet/historico/disputas_2t.csv")
    tabs, secs = [], []
    for ano in sorted(votos["ano"].unique()):
        ufs = sorted(disp[(disp.ano == ano) & (disp.cargo == "governador")]["uf"])
        if ano == 2026:
            d26 = pd.read_csv(ROOT / "data/parquet/historico/disputas_2t_2026.csv")
            ufs = sorted(d26[d26.cargo == "governador"]["uf"])
        tab, s = split_ticket(votos, int(ano), ufs)
        tabs.append(tab)
        if s is not None:
            secs.append(s)
    tab = pd.concat(tabs, ignore_index=True)
    tab.to_csv(repo / "split_ticket_uf.csv", index=False)
    s = pd.concat(secs, ignore_index=True)
    cols = ["ano", "uf", "cd_mun", "zona", "secao", "p13", "p22", "gA", "gB", "np", "n", "p",
            "g", "ajuste", "z", "opostos_extremos"]
    out = s.loc[(s["z"].abs() > 4) | s["opostos_extremos"], cols].sort_values(
        "z", key=lambda x: -x.abs())
    out.to_parquet(repo / "split_ticket_outliers.parquet", index=False)
    mun = (s.assign(out4=s["z"].abs() > 4).groupby(["ano", "uf", "cd_mun"])
           .agg(secoes=("z", "size"), outliers_z4=("out4", "sum")).reset_index())
    mun = mun[mun["outliers_z4"] > 0].sort_values("outliers_z4", ascending=False)
    mun.to_csv(repo / "split_ticket_outliers_municipio.csv", index=False)

    final = {"gerado_em": time.strftime("%Y-%m-%d %H:%M:%S"), "membros_e_erros": erros,
             "coerencia": resumo, "federal_x_estadual": pares,
             "conferencia_oficial": oficial,
             "split_ticket": tab.to_dict(orient="records"),
             "split_top20": out.head(20).to_dict(orient="records")}
    (repo / "resumo.json").write_text(json.dumps(final, indent=1, ensure_ascii=False,
                                                 default=str))
    print(json.dumps({k: final[k] for k in ("coerencia", "federal_x_estadual",
                                             "conferencia_oficial")},
                     indent=1, ensure_ascii=False, default=str))
    print(tab.to_string())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    pe = sp.add_parser("extrair")
    pe.add_argument("--ano", type=int, choices=sorted(SUFIXO_BU), required=True)
    pe.add_argument("--turno", type=int, choices=(1, 2), required=True)
    pe.add_argument("--ufs", help="comma separated UFs (default: all, ZZ included)")
    pe.add_argument("--saida", required=True)
    pe.add_argument("--conns", type=int, default=4,
                    help="concurrent connections to the TSE CDN (keep at 4 or less)")
    pe.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    pe.add_argument("--lote", type=int, default=200, help="members per download batch")
    pe.add_argument("--sa", action="store_true",
                    help="read only the Sistema de Apuração BUs (files *_sa)")
    pr = sp.add_parser("relatorio")
    pr.add_argument("--saida", required=True)
    pr.add_argument("--detalhe", default="~/dataurnas-historico/zip",
                    help="dir with detalhe_votacao_munzona_<year>.zip")
    pr.add_argument("--repo", default=str(ROOT / "data/parquet/2026/coerencia_cargos"))
    a = ap.parse_args()
    if a.cmd == "extrair":
        if a.conns > 4:
            ap.error("--conns above 4 is not allowed (TSE CDN limit)")
        cmd_extrair(a)
    else:
        cmd_relatorio(a)


if __name__ == "__main__":
    main()
