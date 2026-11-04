#!/usr/bin/env python3
"""Why the last Paraná (PR) sections of the 2026 1st round show reception on 07/10.

Question: in the 1st round (04/10/2026) the receipt time published in the
aux.json of the last ~500 PR sections is 07/10/2026, three days after the
election. Were those BUs really received and totalized late, and is anything in
their files different from the other sections?

Steps (subcommands):

  export    (analysis server) exports from ClickHouse the 1st round section
            table (all UFs, receipt time, BU header fields), the 1st and 2nd
            round votes for 13 and 22 of PR, and a 2nd round control: every
            2nd round section whose aux.json receipt is after election day,
            with the history of its aux.json versions kept by the collector
            (aux_versoes) and the SHA-512 of every stored BU (versoes_arquivo).
  pacote    (analysis server) reads, through HTTP Range requests, only the
            members it needs from the PR 1st round zip of the TSE bulk package
            (bu_imgbu_logjez_rdv_vscmr_2026_1t_PR.zip): the central directory
            of every member (dates, presence of -imgbu.dat) and, for the late
            sections plus a control sample of on-time sections of the same
            zones, the BU, RDV, log and signature file. For each of those it
            verifies the signature (verificar_vsc) and the SHA-512 of each
            member against the signed hash, recounts the RDV against the BU
            (rdv_recontagem.processar_secao) and reads the log (dates present,
            last line, voting machines, contingency or recovery events).
  analisar  (anywhere, light) joins everything and writes the small outputs.

Outputs in --out: secoes_pr_tardias.csv (one row per late PR section),
ultimas_499.csv (the last 499 receipts of the country), controle_t2.csv,
mensagens_log.csv (log messages whose prevalence differs between late and
control sections) and resumo.json.

Usage on the analysis server (clone of this repository):
  uv run python scripts/ele2026/pr_tardias_1t.py export  --work ~/dataurnas-pr-tardias
  uv run python scripts/ele2026/pr_tardias_1t.py pacote  --work ~/dataurnas-pr-tardias
  uv run python scripts/ele2026/pr_tardias_1t.py analisar --work ~/dataurnas-pr-tardias \\
      --out ~/dataurnas-pr-tardias/out
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import zipfile
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT / "src"), str(ROOT / "scripts" / "ele2026")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pandas as pd  # noqa: E402

CH = os.path.expanduser("~/dataurnas-ch/app/scripts/ch/ch.sh")
URL = ("https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2026/arqurnatot/"
       "bu_imgbu_logjez_rdv_vscmr_2026_1t_PR.zip")
NOME_RE = re.compile(r"^o03220([a-z]{2})(\d{5})(\d{4})(\d{4})-(.+)$")
KEY = ["uf", "cd_mun", "zona", "secao"]
# Official 1st round result generation time (dt/ht of every -u.json, Brasília).
RESULTADO_OFICIAL = pd.Timestamp("2026-10-05 12:51:05")
DIA = "04/10/2026"
MAX_CONEXOES = 4          # TSE limit: at most 4 concurrent connections
CONTROLE_POR_ZONA = 40    # on-time sections per zone read as control
# Log words that would point to a contingency or recovery path.
PALAVRAS = {
    "contingencia": re.compile(r"conting", re.I),
    "apuracao_sa": re.compile(r"sistema de apura|apura[cç][aã]o", re.I),
    "recuperacao": re.compile(r"recupera", re.I),
    "substituicao": re.compile(r"substitu", re.I),
    "midia": re.compile(r"m[ií]dia|pendrive|pen drive|flash", re.I),
    "transmissao": re.compile(r"transmi", re.I),
}

SQL = {
    "secoes_t1": """
SELECT s.uf AS uf, s.cd_mun AS cd_mun, s.nm_mun AS nm_mun, s.zona AS zona, s.secao AS secao,
       s.st_secao AS st_secao, s.st_hash AS st_hash, s.n_hashes AS n_hashes,
       s.dt_recebimento AS dt_rec, s.hr_recebimento AS hr_rec,
       formatDateTime(s.data_hora_emissao, '%F %T', 'UTC') AS emissao_local,
       formatDateTime(s.hora_encerramento, '%F %T', 'UTC') AS encerramento_local,
       s.tipo_urna AS tipo_urna, s.origem_bu AS origem_bu, s.modelo_urna AS modelo_urna,
       s.local_votacao AS local_votacao, s.numero_interno_urna AS numero_interno_urna,
       s.aptos AS aptos, s.comparecimento AS comparecimento,
       v.votos_13 AS v13, v.votos_22 AS v22
FROM dataurnas.ref_secoes_2026_t1 AS s
LEFT JOIN dataurnas.v_votos_t1_secao AS v USING (uf, cd_mun, zona, secao)
WHERE s.status = 'ok'
FORMAT Parquet""",
    "votos_t2_pr": """
SELECT uf, cd_mun, zona, secao, votos_13 AS t2_v13, votos_22 AS t2_v22
FROM dataurnas.v_votos_t2_secao WHERE uf = 'pr'
FORMAT Parquet""",
    "rec_t2_pr": """
SELECT uf, cd_mun, zona, secao,
       formatDateTime(recebimento, '%F %T', 'America/Sao_Paulo') AS t2_rec, st_secao AS t2_st
FROM dataurnas.v_bu_ultima WHERE uf = 'pr'
FORMAT Parquet""",
    # 2nd round control: every section whose aux.json shows a receipt after election day.
    "controle_t2": """
WITH t AS (SELECT uf, cd_mun, zona, secao FROM dataurnas.aux_versoes
           WHERE recebimento >= toDateTime('2026-10-26 00:00:00', 'America/Sao_Paulo')
           GROUP BY uf, cd_mun, zona, secao),
a AS (SELECT uf, cd_mun, zona, secao, uniqExact(hash) AS n_hash,
             countIf(st_hash = 'Totalizado') AS n_totalizado,
             formatDateTime(minIf(recebimento, st_hash = 'Totalizado'), '%F %T',
                            'America/Sao_Paulo') AS rec_totalizado,
             formatDateTime(max(recebimento), '%F %T', 'America/Sao_Paulo') AS rec_ultimo,
             argMax(st_secao, coletado_em) AS st_final,
             argMax(fase, coletado_em) AS f_final,
             argMax(has(arquivos, concat('imgbu:', 'o03221', uf, cd_mun, zona, secao, '-imgbu.dat')),
                    coletado_em) AS final_lista_imgbu
      FROM dataurnas.aux_versoes
      WHERE (uf, cd_mun, zona, secao) IN (SELECT * FROM t) AND hash != ''
      GROUP BY uf, cd_mun, zona, secao),
v AS (SELECT uf, cd_mun, zona, secao, uniqExact(sha512) AS n_bu_sha
      FROM dataurnas.versoes_arquivo
      WHERE tipo = 'bu' AND (uf, cd_mun, zona, secao) IN (SELECT * FROM t)
      GROUP BY uf, cd_mun, zona, secao)
SELECT * FROM a LEFT JOIN v USING (uf, cd_mun, zona, secao)
FORMAT Parquet""",
}


def ch(sql: str) -> bytes:
    return subprocess.run([CH], input=sql.encode(), capture_output=True, check=True).stdout


def cmd_export(a: argparse.Namespace) -> None:
    work = Path(a.work).expanduser()
    work.mkdir(parents=True, exist_ok=True)
    for nome, sql in SQL.items():
        (work / f"{nome}.parquet").write_bytes(ch(sql))
        print(nome, len(pd.read_parquet(work / f"{nome}.parquet")), flush=True)


def carregar_t1(work: Path) -> pd.DataFrame:
    """1st round sections with BU and their published receipt time (Brasília)."""
    d = pd.read_parquet(work / "secoes_t1.parquet")
    d["rec"] = pd.to_datetime(d["dt_rec"] + " " + d["hr_rec"], format="%d/%m/%Y %H:%M:%S",
                              errors="coerce")
    return d[d["rec"].notna()].copy()


def tardias(d: pd.DataFrame) -> pd.Series:
    """Sections whose published receipt is after the official result was generated."""
    return d["rec"] > RESULTADO_OFICIAL


# ----------------------------------------------------------------------
# pacote
# ----------------------------------------------------------------------

_LOCAL = threading.local()


def _zip() -> zipfile.ZipFile:
    """One Range-backed ZipFile per worker thread (one TSE connection each)."""
    from confronto_pacote_t2 import HttpRangeFile

    z = getattr(_LOCAL, "z", None)
    if z is None:
        z = _LOCAL.z = zipfile.ZipFile(HttpRangeFile(URL))
    return z


def ler_log(texto: str) -> dict:
    """Dates, last line, machines and keyword hits of one voting machine log."""
    datas: Counter = Counter()
    urnas: set[str] = set()
    msgs: set[str] = set()
    kw: Counter = Counter()
    ultima = primeira = None
    for ln in texto.split("\n"):
        p = ln.split("\t")
        if len(p) < 5 or len(p[0]) < 19:
            continue
        datas[p[0][:10]] += 1
        primeira = primeira or p[0][:19]
        ultima = p[0][:19]
        urnas.add(p[2])
        msg = re.sub(r"\d+", "N", p[4])[:160]
        msgs.add(f"{p[1]}|{p[3]}|{msg}")
        for k, rx in PALAVRAS.items():
            if rx.search(p[4]):
                kw[k] += 1
    return {"log_primeira": primeira, "log_ultima": ultima,
            "log_datas": json.dumps(dict(sorted(datas.items())), ensure_ascii=False),
            "log_linhas_fora_do_dia": sum(n for dt, n in datas.items() if dt != DIA),
            "log_n_urnas": len(urnas),
            **{f"log_kw_{k}": kw.get(k, 0) for k in PALAVRAS}, "_msgs": msgs}


def examinar(args: tuple) -> dict:
    """Signature, member hashes, RDV recount and log of one section."""
    from dataurnas.analyzer import rdv_recontagem as R
    from dataurnas.parsers.signature import verificar_vsc

    chave, membros, grupo = args
    row = {**dict(zip(KEY, chave, strict=True)), "grupo": grupo}
    z = _zip()
    raw = {k: z.read(nm) for k, nm in membros.items()
           if k in ("bu.dat", "rdv.dat", "log.jez", "vota.vsc", "imgbu.dat")}
    if "vota.vsc" in raw:
        v = verificar_vsc(raw["vota.vsc"], None)
        hs = {nm: h.hex() for nm, h in v["hashes"].items()}
        row.update(assinatura_valida=v["assinatura_valida"], algoritmo=v["algoritmo"],
                   falhas="; ".join(v["falhas"]) or None)
        for tp in ("bu.dat", "rdv.dat", "log.jez", "imgbu.dat"):
            nm = membros.get(tp)
            if nm is not None and tp in raw:
                k = tp.split(".")[0]
                row[f"hash_{k}_confere"] = (hashlib.sha512(raw[tp]).hexdigest() == hs[nm]
                                            if nm in hs else None)
    ident = dict(zip(KEY, chave, strict=True))
    arqs = {k.split(".")[0]: (membros[k], raw[k]) for k in ("bu.dat", "rdv.dat") if k in raw}
    if "bu" in arqs:
        res = R.processar_secao(ident, arqs, None, 3220, DIA, False, None, 1, ())
        s = res["secao"]
        pres = res["presidente"]
        row.update(rdv_status=s["status"], rdv_confere=s.get("rdv_confere"),
                   rdv_tipo_urna=s.get("tipo_urna_rdv"),
                   rdv_v13=pres.get("nominal:13"), rdv_v22=pres.get("nominal:22"))
    if "log.jez" in raw:
        txt = R.texto_log(raw["log.jez"])
        if txt:
            row.update(ler_log(txt))
    return row


def cmd_pacote(a: argparse.Namespace) -> None:
    from confronto_pacote_t2 import HttpRangeFile

    work = Path(a.work).expanduser()
    f = HttpRangeFile(URL)
    z = zipfile.ZipFile(f)
    membros: dict[tuple, dict[str, str]] = {}
    cd = []
    for i in z.infolist():
        m = NOME_RE.match(i.filename)
        if not m:
            continue
        chave = m.group(1, 2, 3, 4)
        membros.setdefault(chave, {})[m.group(5)] = i.filename
        cd.append({**dict(zip(KEY, chave, strict=True)), "tipo": m.group(5),
                   "data_zip": "%04d-%02d-%02d %02d:%02d:%02d" % i.date_time,
                   "tamanho": i.file_size})
    pd.DataFrame(cd).to_parquet(work / "pacote_cd.parquet", index=False)
    (work / "pacote_head.json").write_text(json.dumps(
        {"url": URL, "tamanho": f.size, "last_modified": f.last_modified}))
    print("central directory:", len(cd), "members,", len(membros), "sections", flush=True)

    d = carregar_t1(work)
    pr = d[d["uf"] == "pr"]
    late = pr[tardias(pr)]
    zonas = set(zip(late["cd_mun"], late["zona"], strict=True))
    ok = pr[~tardias(pr) & pd.Series([(m, zn) in zonas for m, zn in zip(pr["cd_mun"], pr["zona"], strict=True)],
                                     index=pr.index)]
    ctrl = (ok.sort_values(KEY).groupby(["cd_mun", "zona"], group_keys=False)
            .head(CONTROLE_POR_ZONA))
    tarefas = [((r.uf, r.cd_mun, r.zona, r.secao), membros.get((r.uf, r.cd_mun, r.zona, r.secao), {}),
                g) for g, df in (("tardia", late), ("controle", ctrl)) for r in df.itertuples()]
    print("sections to read:", len(tarefas), flush=True)
    linhas, msgs = [], []
    with ThreadPoolExecutor(MAX_CONEXOES) as ex:
        for i, row in enumerate(ex.map(examinar, tarefas), 1):
            for mm in row.pop("_msgs", set()):
                msgs.append({**{k: row[k] for k in KEY}, "grupo": row["grupo"], "msg": mm})
            linhas.append(row)
            if i % 100 == 0:
                print(i, flush=True)
    pd.DataFrame(linhas).to_parquet(work / "pacote_secoes.parquet", index=False)
    pd.DataFrame(msgs).to_parquet(work / "pacote_msgs.parquet", index=False)


# ----------------------------------------------------------------------
# analisar
# ----------------------------------------------------------------------

def _share(v13, v22) -> float | None:
    t = float(v13) + float(v22)
    return round(100 * float(v13) / t, 2) if t else None


def cmd_analisar(a: argparse.Namespace) -> None:
    work = Path(a.work).expanduser()
    out = Path(a.out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    d = carregar_t1(work)
    d["tardia"] = tardias(d)
    res: dict = {"resultado_oficial_gerado": str(RESULTADO_OFICIAL)}

    # 1. The last 499 receipts of the country and the late sections per UF
    ult = d.sort_values("rec").tail(499)
    ult[KEY + ["nm_mun", "rec", "st_secao"]].to_csv(out / "ultimas_499.csv", index=False)
    res["ultimas_499"] = {"por_uf": ult["uf"].value_counts().to_dict(),
                          "primeira": str(ult["rec"].min()), "ultima": str(ult["rec"].max()),
                          "st_secao": ult["st_secao"].value_counts().to_dict()}
    lt = d[d["tardia"]]
    res["tardias_brasil"] = {
        "secoes": len(lt), "por_uf": lt["uf"].value_counts().to_dict(),
        "st_secao": lt["st_secao"].value_counts().to_dict(),
        "recebida_fora_das_tardias": int(((d["st_secao"] == "Recebida") & ~d["tardia"]).sum())}

    # 2. PR late sections: where, when and what kind of BU
    pr = d[d["uf"] == "pr"].copy()
    pl = pr[pr["tardia"]].copy()
    tot_zona = pr.groupby(["cd_mun", "nm_mun", "zona"]).size().rename("secoes_zona")
    zn = (pl.groupby(["cd_mun", "nm_mun", "zona"])
          .agg(tardias=("secao", "size"), rec_min=("rec", "min"), rec_max=("rec", "max"),
               locais=("local_votacao", "nunique"))
          .join(tot_zona).reset_index().sort_values("rec_min"))
    zn["rec_min"], zn["rec_max"] = zn["rec_min"].astype(str), zn["rec_max"].astype(str)
    res["pr"] = {
        "secoes_pr": len(pr), "tardias": len(pl),
        "tardias_entre_ultimas_499": int(ult["uf"].eq("pr").sum()),
        "rec_min": str(pl["rec"].min()), "rec_max": str(pl["rec"].max()),
        "comparecimento": int(pl["comparecimento"].sum()),
        "municipios": int(pl["cd_mun"].nunique()), "zonas": int(len(zn)),
        "por_zona": zn.to_dict("records"),
        "st_secao": pl["st_secao"].value_counts().to_dict(),
        "tipo_urna": pl["tipo_urna"].value_counts().to_dict(),
        "tipo_urna_pr_todas": pr["tipo_urna"].value_counts().to_dict(),
        "origem_bu": pl["origem_bu"].value_counts(dropna=False).astype(int).to_dict(),
        "modelo_urna": pl["modelo_urna"].value_counts().to_dict(),
        "modelo_urna_pr_todas": pr["modelo_urna"].value_counts().to_dict(),
        "emissao_local_min": pl["emissao_local"].min(), "emissao_local_max": pl["emissao_local"].max(),
        "encerramento_local_min": pl["encerramento_local"].min(),
        "encerramento_local_max": pl["encerramento_local"].max(),
        "encerradas_apos_17h05": int((pl["encerramento_local"].str[11:] > "17:05:00").sum()),
        "encerradas_apos_17h05_pr_pontuais": int(
            (pr.loc[~pr["tardia"], "encerramento_local"].str[11:] > "17:05:00").sum()),
    }

    # 3. Votes: late sections vs on-time sections of the same zones and municipalities
    votos = {}
    for nome, mask in (("tardias", pr["tardia"]),
                       ("mesmas_zonas_pontuais", ~pr["tardia"] & pr.set_index(["cd_mun", "zona"])
                        .index.isin(zn.set_index(["cd_mun", "zona"]).index)),
                       ("mesmos_municipios_pontuais", ~pr["tardia"] & pr["cd_mun"].isin(pl["cd_mun"])),
                       ("pr_pontuais", ~pr["tardia"])):
        s = pr[mask]
        votos[nome] = {"secoes": int(len(s)), "v13": int(s["v13"].sum()), "v22": int(s["v22"].sum()),
                       "fatia_13_no_13_22": _share(s["v13"].sum(), s["v22"].sum())}
    # same comparison zone by zone (late vs on-time of the same zone)
    pz = []
    for (m, z_), g in pr.groupby(["cd_mun", "zona"]):
        if not g["tardia"].any():
            continue
        t, o = g[g["tardia"]], g[~g["tardia"]]
        pz.append({"cd_mun": m, "zona": z_, "tardias": len(t), "pontuais": len(o),
                   "fatia13_tardias": _share(t["v13"].sum(), t["v22"].sum()),
                   "fatia13_pontuais": _share(o["v13"].sum(), o["v22"].sum()) if len(o) else None})
    votos["por_zona"] = pz
    t2 = pd.read_parquet(work / "votos_t2_pr.parquet")
    p2 = pr.merge(t2, on=KEY, how="left")
    for nome, mask in (("tardias", p2["tardia"]), ("pontuais", ~p2["tardia"])):
        s = p2[mask]
        votos[f"t2_{nome}"] = {"fatia13_t1": _share(s["v13"].sum(), s["v22"].sum()),
                               "fatia13_t2": _share(s["t2_v13"].sum(), s["t2_v22"].sum())}
    res["votos"] = votos

    # 4. 2nd round: same PR sections and the national control
    r2 = pd.read_parquet(work / "rec_t2_pr.parquet")
    r2["t2_rec"] = pd.to_datetime(r2["t2_rec"])
    r2p = r2.merge(pl[KEY], on=KEY)
    res["t2_mesmas_secoes"] = {"secoes": len(r2p), "rec_min": str(r2p["t2_rec"].min()),
                               "rec_max": str(r2p["t2_rec"].max()),
                               "st": r2p["t2_st"].value_counts().to_dict(),
                               "pr_rec_max_t2": str(r2["t2_rec"].max())}
    c2 = pd.read_parquet(work / "controle_t2.parquet")
    c2.to_csv(out / "controle_t2.csv", index=False)
    res["controle_t2"] = {
        "secoes": len(c2), "por_uf": c2["uf"].value_counts().to_dict(),
        "um_unico_hash": int((c2["n_hash"] == 1).sum()),
        "totalizadas_antes": int((c2["n_totalizado"] > 0).sum()),
        "rec_totalizado_max": c2["rec_totalizado"].max(),
        "rec_ultimo_min": c2["rec_ultimo"].min(), "rec_ultimo_max": c2["rec_ultimo"].max(),
        "bu_sha_unico": int((c2["n_bu_sha"] == 1).sum()),
        "st_final": c2["st_final"].value_counts().to_dict(),
        "f_final": c2["f_final"].value_counts().to_dict(),
        "final_lista_imgbu": int(c2["final_lista_imgbu"].sum())}

    # 5. Bulk package: central directory, signatures, RDV and logs
    cd = pd.read_parquet(work / "pacote_cd.parquet")
    cd = cd.merge(pr[KEY + ["tardia"]], on=KEY, how="left")
    res["pacote_head"] = json.loads((work / "pacote_head.json").read_text())
    imgbu = cd[cd["tipo"] == "imgbu.dat"][KEY].assign(tem_imgbu=True)
    pri = pr.merge(imgbu, on=KEY, how="left").fillna({"tem_imgbu": False})
    datas = cd[cd["tipo"] == "bu.dat"].copy()
    datas["dia_zip"] = datas["data_zip"].str[:10]
    res["pacote_cd"] = {
        "membros": len(cd), "secoes": int(cd[KEY].drop_duplicates().shape[0]),
        "imgbu_tardias": int(pri.loc[pri["tardia"], "tem_imgbu"].sum()),
        "imgbu_pontuais": int(pri.loc[~pri["tardia"], "tem_imgbu"].sum()),
        "data_zip_bu_tardias": datas[datas["tardia"] == True]["dia_zip"].value_counts().to_dict(),  # noqa: E712
        "data_zip_bu_pontuais": datas[datas["tardia"] == False]["dia_zip"].value_counts().head(10).to_dict(),  # noqa: E712
    }
    ps = pd.read_parquet(work / "pacote_secoes.parquet")
    pk = {}
    for g, s in ps.groupby("grupo"):
        pk[g] = {
            "secoes": len(s),
            "assinatura_valida": s["assinatura_valida"].value_counts(dropna=False).astype(int)
            .rename(str).to_dict(),
            **{c: s[c].value_counts(dropna=False).astype(int).rename(str).to_dict()
               for c in ("hash_bu_confere", "hash_rdv_confere", "hash_log_confere",
                         "hash_imgbu_confere", "rdv_confere", "rdv_tipo_urna") if c in s},
            "log_linhas_fora_do_dia": int((s["log_linhas_fora_do_dia"] > 0).sum()),
            "log_ultima_min": s["log_ultima"].min(), "log_ultima_max": s["log_ultima"].max(),
            "log_mais_de_uma_urna": int((s["log_n_urnas"] > 1).sum()),
            **{f"secoes_{c}": int((s[c] > 0).sum()) for c in s.columns if c.startswith("log_kw_")},
        }
    res["pacote_exame"] = pk
    # RDV recount vs the BU table of the project (votes 13 and 22)
    chk = ps[ps["grupo"] == "tardia"].merge(pr[KEY + ["v13", "v22"]], on=KEY)
    res["pacote_exame"]["tardia"]["rdv_13_22_igual_bu"] = int(
        ((chk["rdv_v13"] == chk["v13"]) & (chk["rdv_v22"] == chk["v22"])).sum())

    msgs = pd.read_parquet(work / "pacote_msgs.parquet")
    n = ps["grupo"].value_counts()
    pv = (msgs.groupby(["msg", "grupo"]).size().unstack(fill_value=0)
          .reindex(columns=["tardia", "controle"], fill_value=0))
    pv["pct_tardia"] = (100 * pv["tardia"] / n.get("tardia", 1)).round(1)
    pv["pct_controle"] = (100 * pv["controle"] / n.get("controle", 1)).round(1)
    pv["dif"] = pv["pct_tardia"] - pv["pct_controle"]
    pv = pv.reindex(pv["dif"].abs().sort_values(ascending=False).index)
    pv.head(60).to_csv(out / "mensagens_log.csv")
    res["mensagens_log_max_dif_pontos"] = float(pv["dif"].abs().max())

    # 6. Per-section table of the late PR sections
    tab = (pl.merge(ps[ps["grupo"] == "tardia"].drop(columns=["grupo"]), on=KEY, how="left")
           .merge(pri[KEY + ["tem_imgbu"]], on=KEY, how="left")
           .merge(r2[KEY + ["t2_rec"]], on=KEY, how="left"))
    cols = KEY + ["nm_mun", "local_votacao", "rec", "st_secao", "emissao_local",
                  "encerramento_local", "tipo_urna", "origem_bu", "modelo_urna", "comparecimento",
                  "v13", "v22", "tem_imgbu", "assinatura_valida", "hash_bu_confere",
                  "hash_rdv_confere", "hash_log_confere", "rdv_confere", "rdv_v13", "rdv_v22",
                  "log_ultima", "log_linhas_fora_do_dia", "log_n_urnas", "t2_rec"]
    tab[[c for c in cols if c in tab]].sort_values("rec").to_csv(
        out / "secoes_pr_tardias.csv", index=False)
    (out / "resumo.json").write_text(json.dumps(res, indent=2, ensure_ascii=False, default=str))
    print(json.dumps(res, indent=2, ensure_ascii=False, default=str))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for nome in ("export", "pacote", "analisar"):
        p = sub.add_parser(nome)
        p.add_argument("--work", default="~/dataurnas-pr-tardias")
        if nome == "analisar":
            p.add_argument("--out", default="~/dataurnas-pr-tardias/out")
    a = ap.parse_args()
    {"export": cmd_export, "pacote": cmd_pacote, "analisar": cmd_analisar}[a.cmd](a)


if __name__ == "__main__":
    main()
