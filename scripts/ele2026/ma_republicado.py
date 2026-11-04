#!/usr/bin/env python3
"""What changed in the republished 1st round MA zip of the TSE bulk package.

On 03/11/2026 at 19:59:01 GMT the TSE replaced
bu_imgbu_logjez_rdv_vscmr_2026_1t_MA.zip at the same address. The national
package audit (pacote_nacional.py) had read the previous version a few hours
earlier (16:14 UTC) and deleted it after processing, as it does with every
zip. Unlike the MG 1st round and SP 2nd round zips, no member of the new MA
zip carries a date after 20/10/2026, so the central directory alone does not
show what changed.

No copy of the old zip and no per-member CRC of it were kept. The references
that do exist, and that this script compares the new zip against, are:

  1. The per-file hash catalog of the 1st round (fetch_integridade.py,
     release v0.2.1, arquivos_ma.parquet): size, MD5, SHA-256 and SHA-512 of
     every -bu.dat, -rdv.dat, -log.jez and -vota.vsc of MA, downloaded one by
     one from resultados.tse.jus.br on 13/10/2026. The -imgbu.dat files were
     not published there (HTTP 404), so the catalog has no hash for them.
  2. The per-section results of the old zip (secoes_ma_1.parquet, 94
     columns): every figure read from the BU, the BU image and the log.
  3. The central directory read after the republication
     (cd_republicados.parquet), to confirm that the zip examined here is the
     same one seen on 04/11.

Steps:
  - HTTP HEAD of the current zip (size, Last-Modified, ETag; the ETag of this
    server is <size hex>-<mtime in microseconds hex>).
  - Zip structure: every local header checked against its central directory
    entry, member data spans checked for gaps, overlaps and trailing bytes,
    duplicate names, archive comment, compression methods, flags, extra
    fields and member dates.
  - Every member is read in full: CRC-32 recomputed, size, MD5, SHA-256 and
    SHA-512, then compared with the catalog (reference 1) and with
    cd_republicados (reference 3).
  - Every -vota.vsc is verified with dataurnas.parsers.signature.verificar_vsc
    and the SHA-512 of each data member is checked against the hash the
    machine signed.
  - Every section is processed again with pacote_nacional.processar_secao and
    each of the 94 columns is compared with the old read (reference 2).

Output in --saida: membros.parquet (one row per member), secoes_novas.parquet,
diferencas_secoes.csv, assinaturas.parquet and resumo.json.

Usage (analysis server, zip already downloaded to RAM):
  uv run python scripts/ele2026/ma_republicado.py \\
      --zip /dev/shm/ma-republicado-zip/ma_1t.zip \\
      --catalogo ~/dataurnas-ma-republicado/arquivos_ma.parquet \\
      --antigo ~/dataurnas-pacote-nacional/secoes_ma_1.parquet \\
      --cd ~/dataurnas-pacote-nacional/cd_republicados.parquet \\
      --saida ~/dataurnas-ma-republicado
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import struct
import sys
import urllib.request
import zipfile
import zlib
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT / "src"), str(ROOT / "scripts" / "ele2026")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pandas as pd  # noqa: E402

import pacote_nacional as pn  # noqa: E402

URL = pn.URL.format(t=1, uf="MA")
CHAVES = ["uf", "cd_mun", "zona", "secao"]
LOCAL_SIG = b"PK\x03\x04"


def head(url: str) -> dict:
    """Size, Last-Modified and ETag of the zip, with the ETag decoded."""
    with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=60) as r:
        h = {k.lower(): v for k, v in r.headers.items()}
    out = {"content_length": int(h["content-length"]), "last_modified": h.get("last-modified"),
           "etag": h.get("etag")}
    try:
        tam_hex, mtime_hex = out["etag"].strip('"').split("-")
        out["etag_tamanho"] = int(tam_hex, 16)
        out["etag_mtime_utc"] = pd.Timestamp(int(mtime_hex, 16), unit="us").isoformat()
    except (AttributeError, ValueError):
        pass
    return out


def estrutura(path: str) -> tuple[pd.DataFrame, dict]:
    """Local header vs central directory for every member, and byte coverage."""
    linhas, problemas = [], Counter()
    with zipfile.ZipFile(path) as z, open(path, "rb") as f:
        infos = z.infolist()
        tam_arquivo = os.path.getsize(path)
        inicio_cd = z.start_dir
        for zi in infos:
            f.seek(zi.header_offset)
            lh = f.read(30)
            (sig, _ver, flags, metodo, hora, data, crc, csize, usize,
             n_nome, n_extra) = struct.unpack("<4sHHHHHIIIHH", lh)
            nome = f.read(n_nome).decode("cp437" if not flags & 0x800 else "utf-8")
            extra_local = f.read(n_extra)
            ini_dados = zi.header_offset + 30 + n_nome + n_extra
            fim = ini_dados + zi.compress_size
            if flags & 0x08:  # data descriptor after the data
                f.seek(fim)
                dd = f.read(16)
                fim += 16 if dd[:4] == b"PK\x07\x08" else 12
            linha = {
                "nome": zi.filename, "offset": zi.header_offset, "fim": fim,
                "metodo": zi.compress_type, "flags_cd": zi.flag_bits, "flags_local": flags,
                "data_zip": "%04d-%02d-%02d %02d:%02d:%02d" % zi.date_time,
                "crc": zi.CRC, "tam": zi.file_size, "tam_comprimido": zi.compress_size,
                "extra_cd": zi.extra.hex(), "extra_local": extra_local.hex(),
                "comentario": zi.comment.hex(), "sistema": zi.create_system,
                "versao": zi.create_version, "attr_externo": zi.external_attr,
            }
            if sig != LOCAL_SIG:
                problemas["assinatura_local"] += 1
            if nome != zi.filename:
                problemas["nome_local_difere"] += 1
            if metodo != zi.compress_type:
                problemas["metodo_local_difere"] += 1
            if (hora, data) != (zi._raw_time, ((zi.date_time[0] - 1980) << 9)
                                | (zi.date_time[1] << 5) | zi.date_time[2]):
                problemas["data_local_difere"] += 1
            if not flags & 0x08 and (crc, csize, usize) != (zi.CRC, zi.compress_size,
                                                           zi.file_size):
                if not (csize == usize == 0xFFFFFFFF):  # zip64 sizes in the extra field
                    problemas["crc_tamanho_local_difere"] += 1
            linhas.append(linha)
    df = pd.DataFrame(linhas).sort_values("offset").reset_index(drop=True)
    lacunas = (df["offset"].iloc[1:].to_numpy() - df["fim"].iloc[:-1].to_numpy())
    resumo = {
        "membros": len(df), "nomes_duplicados": int(df["nome"].duplicated().sum()),
        "tamanho_arquivo": tam_arquivo, "inicio_cd": inicio_cd,
        "primeiro_offset": int(df["offset"].iloc[0]),
        "bytes_lacunas_entre_membros": int(lacunas[lacunas > 0].sum()),
        "sobreposicoes": int((lacunas < 0).sum()),
        "bytes_entre_ultimo_membro_e_cd": int(inicio_cd - df["fim"].iloc[-1]),
        "ordem_cd_igual_offset": bool(
            [zi.header_offset for zi in infos] == sorted(zi.header_offset for zi in infos)),
        "comentario_arquivo": zipfile.ZipFile(path).comment.hex(),
        "metodos": {str(k): int(v) for k, v in df["metodo"].value_counts().items()},
        "flags_cd": {str(k): int(v) for k, v in df["flags_cd"].value_counts().items()},
        "extra_cd_distintos": int(df["extra_cd"].nunique()),
        "extra_local_distintos": int(df["extra_local"].nunique()),
        "datas_por_dia": {k: int(v) for k, v in df["data_zip"].str[:10].value_counts()
                          .sort_index().items()},
        "problemas_local_x_cd": dict(problemas),
        # Late members and their position (0 = first local header in the file):
        # an entry appended at the end points to an in-place update of the zip.
        "membros_apos_05_10": [
            {"nome": r.nome, "data_zip": r.data_zip, "posicao": int(i), "offset": int(r.offset)}
            for i, r in df[df["data_zip"] > "2026-10-06"].iterrows()],
    }
    return df, resumo


def _digests(args: tuple) -> list[dict]:
    path, nomes = args
    out = []
    with zipfile.ZipFile(path) as z:
        for nome in nomes:
            raw = z.read(nome)  # zipfile also checks the CRC-32 and raises on mismatch
            out.append({"nome": nome, "crc_calculado": zlib.crc32(raw), "tam_lido": len(raw),
                        "md5": hashlib.md5(raw).hexdigest(),
                        "sha256": hashlib.sha256(raw).hexdigest(),
                        "sha512": hashlib.sha512(raw).hexdigest()})
    return out


def _assinatura(args: tuple) -> dict:
    """verificar_vsc on one section, plus SHA-512 of each member vs the signed hash."""
    from dataurnas.parsers.signature import verificar_vsc

    path, chave, membros = args
    row = dict(zip(CHAVES, chave, strict=True))
    with zipfile.ZipFile(path) as z:
        if "vota.vsc" not in membros:
            row["sem_vsc"] = True
            return row
        v = verificar_vsc(z.read(membros["vota.vsc"]), None)
        hs = {nm: h.hex() for nm, h in v["hashes"].items()}
        row.update({"assinatura_valida": v["assinatura_valida"], "algoritmo": v["algoritmo"],
                    "falhas": "; ".join(v["falhas"]) or None,
                    "motivos": "; ".join(v["motivos"]) or None,
                    "cert_serial": v["cert_serial"]})
        for tipo in ("bu.dat", "rdv.dat", "log.jez", "imgbu.dat"):
            nm = membros.get(tipo)
            if nm is None:
                continue
            k = tipo.split(".")[0]
            if nm in hs:
                row[f"hash_{k}_confere"] = hashlib.sha512(z.read(nm)).hexdigest() == hs[nm]
                row[f"assinatura_{k}_ok"] = v["assinaturas_arquivos"].get(nm)
            else:
                row[f"hash_{k}_confere"] = None  # not listed in the .vsc
    return row


def recontar_rdv(path: str, nome_rdv: str) -> dict:
    """Recount the RDV of one section against its BU (all offices, then President).

    Used for the RDV members that the 13/10 catalog does not have, so that the
    file is checked for content and not only for its signature.
    """
    from dataurnas.analyzer import rdv_recontagem as R

    nome_bu = nome_rdv.replace("-rdv.dat", "-bu.dat")
    m = pn.NOME_RE.match(nome_rdv)
    ident = dict(zip(CHAVES, m.group(2, 3, 4, 5), strict=True))
    with zipfile.ZipFile(path) as z:
        rdv, bu = z.read(nome_rdv), z.read(nome_bu)
    res = R.processar_secao(ident, {"rdv": (nome_rdv, rdv), "bu": (nome_bu, bu)}, None,
                            3220, pn.DATA[1], False, None, 1, ())
    s = res["secao"]
    return {**ident, "rdv": nome_rdv, "sha512_rdv": hashlib.sha512(rdv).hexdigest(),
            "status": s.get("status"), "motivo": s.get("motivo"),
            "registros_rdv": s.get("registros_rdv"), "n_cargos": s.get("n_cargos"),
            "estrutura_ok": s.get("estrutura_ok"), "rdv_confere": s.get("rdv_confere"),
            "presidente_rdv": dict(res["presidente"] or {}),
            "presidente_bu": pn.dados_bu(bu).get("bu_candidatos"),
            "achados": [a["categoria"] for a in res["achados"]]}


def _igual(a, b) -> bool:
    if a is None or (isinstance(a, float) and math.isnan(a)):
        return b is None or (isinstance(b, float) and math.isnan(b))
    if b is None or (isinstance(b, float) and math.isnan(b)):
        return False
    try:
        return bool(a == b)
    except (TypeError, ValueError):
        return str(a) == str(b)


def comparar_secoes(antigo: pd.DataFrame, novo: pd.DataFrame) -> pd.DataFrame:
    """One row per (section, column) whose value differs between old and new reads."""
    a = antigo.set_index(CHAVES)
    n = novo.set_index(CHAVES)
    difs = []
    for chave in a.index.symmetric_difference(n.index):
        difs.append({**dict(zip(CHAVES, chave, strict=True)), "coluna": "_secao",
                     "antigo": str(chave in a.index), "novo": str(chave in n.index)})
    comuns = a.index.intersection(n.index)
    for col in sorted(set(a.columns) | set(n.columns)):
        va = a[col].reindex(comuns) if col in a.columns else pd.Series(None, index=comuns)
        vn = n[col].reindex(comuns) if col in n.columns else pd.Series(None, index=comuns)
        for chave, x, y in zip(comuns, va.tolist(), vn.tolist(), strict=True):
            if not _igual(x, y):
                difs.append({**dict(zip(CHAVES, chave, strict=True)), "coluna": col,
                             "antigo": str(x), "novo": str(y)})
    return pd.DataFrame(difs, columns=CHAVES + ["coluna", "antigo", "novo"])


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--zip", required=True)
    ap.add_argument("--catalogo", required=True)
    ap.add_argument("--antigo", required=True)
    ap.add_argument("--cd", required=True)
    ap.add_argument("--saida", required=True)
    ap.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) - 6))
    ap.add_argument("--sem-head", action="store_true")
    a = ap.parse_args()
    saida = Path(a.saida).expanduser()
    saida.mkdir(parents=True, exist_ok=True)
    zpath = str(Path(a.zip).expanduser())
    resumo: dict = {}

    if not a.sem_head:
        resumo["head"] = head(URL)
        pn._log(f"HEAD {resumo['head']}")

    est, resumo["estrutura"] = estrutura(zpath)
    pn._log(f"structure {resumo['estrutura']}")

    nomes = est["nome"].tolist()
    lotes = [(zpath, nomes[i:i + 500]) for i in range(0, len(nomes), 500)]
    with ProcessPoolExecutor(a.workers) as ex:
        dig = pd.DataFrame([r for lote in ex.map(_digests, lotes) for r in lote])
    m = est.merge(dig, on="nome")
    m["crc_confere"] = m["crc"] == m["crc_calculado"]
    m["tam_confere"] = m["tam"] == m["tam_lido"]
    partes = m["nome"].str.extract(pn.NOME_RE)
    m[CHAVES] = partes[[1, 2, 3, 4]].to_numpy()
    m["tipo"] = partes[5]
    pn._log(f"digests: {len(m)} members, CRC ok {int(m.crc_confere.sum())}")

    # Reference 3: central directory recorded on 04/11 after the republication.
    cd = pd.read_parquet(Path(a.cd).expanduser())
    cd = cd[(cd["uf"] == "ma") & (cd["t"] == 1)][["nome", "crc", "tam", "data_zip"]]
    x = m.merge(cd, on="nome", how="outer", suffixes=("", "_cd0411"), indicator=True)
    resumo["vs_cd_0411"] = {
        "so_no_zip": int((x["_merge"] == "left_only").sum()),
        "so_no_cd_0411": int((x["_merge"] == "right_only").sum()),
        "crc_ou_tam_ou_data_diferente": int(((x["_merge"] == "both") & (
            (x["crc"] != x["crc_cd0411"]) | (x["tam"] != x["tam_cd0411"])
            | (x["data_zip"] != x["data_zip_cd0411"]))).sum()),
    }

    # Reference 1: hash catalog of 13/10 (files fetched one by one from the results site).
    cat = pd.read_parquet(Path(a.catalogo).expanduser())
    cat = cat[cat["disponivel"]][["nome", "tamanho", "md5", "sha256", "sha512", "data_hora_tse"]]
    y = m.merge(cat, on="nome", how="outer", suffixes=("", "_cat"), indicator=True)
    both = y["_merge"] == "both"
    y["igual_catalogo"] = both & (y["tam"] == y["tamanho"]) & (y["md5"] == y["md5_cat"]) \
        & (y["sha256"] == y["sha256_cat"]) & (y["sha512"] == y["sha512_cat"])
    diferentes = y[both & ~y["igual_catalogo"]]
    resumo["vs_catalogo_1310"] = {
        "membros_no_catalogo": int(both.sum()),
        "identicos": int(y["igual_catalogo"].sum()),
        "diferentes": diferentes["nome"].tolist(),
        "so_no_zip_por_tipo": {k: int(v) for k, v in
                               y[y["_merge"] == "left_only"]["tipo"].value_counts().items()},
        "so_no_catalogo": y[y["_merge"] == "right_only"]["nome"].tolist(),
    }
    m = m.merge(y[["nome", "igual_catalogo"]].dropna(subset=["nome"]), on="nome", how="left")
    m.to_parquet(saida / "membros.parquet", index=False)
    resumo["rdv_fora_do_catalogo"] = [
        recontar_rdv(zpath, nm) for nm in
        y[(y["_merge"] == "left_only") & (y["tipo"] == "rdv.dat")]["nome"]]
    pn._log(f"RDV not in catalog: {resumo['rdv_fora_do_catalogo']}")
    pn._log(f"catalog: {resumo['vs_catalogo_1310']['identicos']} identical, "
            f"{len(diferentes)} different")

    # Signatures and signed hashes, every section.
    tarefas = pn.tarefas_zip(Path(zpath), 1)
    with ProcessPoolExecutor(a.workers) as ex:
        sig = pd.DataFrame(list(ex.map(_assinatura, [(t[0], t[2], t[3]) for t in tarefas],
                                       chunksize=32)))
    sig.to_parquet(saida / "assinaturas.parquet", index=False)
    res_sig = {"secoes": len(sig),
               "assinatura_valida": {str(k): int(v) for k, v in
                                     sig["assinatura_valida"].value_counts(dropna=False).items()}}
    for c in [c for c in sig.columns if c.startswith(("hash_", "assinatura_")) and
              c != "assinatura_valida"]:
        res_sig[c] = {str(k): int(v) for k, v in sig[c].value_counts(dropna=False).items()}
    res_sig["falhas"] = sig[sig["falhas"].notna()][CHAVES + ["falhas"]].to_dict("records")
    resumo["assinaturas"] = res_sig
    pn._log(f"signatures {res_sig['assinatura_valida']}")

    # Reference 2: every section processed again, compared column by column.
    with ProcessPoolExecutor(a.workers) as ex:
        novo = pd.DataFrame([r for r, _ev in ex.map(pn.processar_secao, tarefas, chunksize=16)])
    novo.to_parquet(saida / "secoes_novas.parquet", index=False)
    antigo = pd.read_parquet(Path(a.antigo).expanduser())
    difs = comparar_secoes(antigo, novo)
    difs.to_csv(saida / "diferencas_secoes.csv", index=False)
    resumo["vs_leitura_antiga"] = {
        "secoes_antigas": len(antigo), "secoes_novas": len(novo),
        "colunas_comparadas": len(set(antigo.columns) | set(novo.columns)),
        "valores_diferentes": len(difs),
        "secoes_com_diferenca": int(difs[CHAVES].drop_duplicates().shape[0]) if len(difs) else 0,
        "por_coluna": {k: int(v) for k, v in difs["coluna"].value_counts().items()},
    }
    pn._log(f"old read: {resumo['vs_leitura_antiga']}")
    (saida / "resumo.json").write_text(json.dumps(resumo, indent=1, ensure_ascii=False,
                                                  default=str))


if __name__ == "__main__":
    main()
