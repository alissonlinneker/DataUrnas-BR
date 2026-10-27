#!/usr/bin/env python3
"""Recontagem nacional do 2º turno de 2026 (Presidente) pelo RDV contra o BU.

Mesmo método da amostra (scripts/ele2026/rdv_log_auditoria.py) e da recontagem
nacional do 1º turno (analyzer/rdv_recontagem.py), estendido às 499.207 seções.
Só o -rdv.dat é baixado do TSE: o BU e o .vsc de cada seção já estão guardados
pelo coletor versionado (ClickHouse, tabelas versoes_arquivo e arquivos_conteudo).

Etapas (subcomandos):
  lista      exporta do ClickHouse as seções do 2º turno com o hash do pacote
             (roda no servidor de análise; grava lista.parquet).
  baixar     baixa o -rdv.dat das seções das UFs pedidas, um processo por IP,
             taxa adaptativa (recua em 429). Pula seções já baixadas e as da
             amostra (--amostra). Layout igual ao da amostra:
             <brutos>/t2/<uf>/<mun>-<zona>-<secao>-<hash16>/{rdv, ok.json}.
  processar  por UF: grava o BU e o .vsc do ClickHouse ao lado do RDV e aplica a
             rotina _rdv_um da amostra (recontagem por cargo, BU de Presidente,
             SHA-512 e assinatura no .vsc). Saída em --saida.
  relatorio  resumo.json com totais nacionais, por UF e divergências.

Uso (servidor de análise, exceto baixar, que roda nos dois IPs):
  python3 -I scripts/ele2026/rdv_nacional_t2.py lista
  python3 -I scripts/ele2026/rdv_nacional_t2.py baixar --ufs sp,mg --brutos ~/dataurnas-t2/rdv_nacional
  python3 -I scripts/ele2026/rdv_nacional_t2.py processar --brutos ~/dataurnas-t2/rdv_nacional
  python3 -I scripts/ele2026/rdv_nacional_t2.py relatorio
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT / "src"), str(ROOT / "scripts" / "ele2026")):
    if p not in sys.path:
        sys.path.insert(0, p)

import rdv_log_auditoria as A  # noqa: E402

log = logging.getLogger("rdv_nacional")
SAIDA = ROOT / "data" / "parquet" / "2026" / "t2" / "rdv_nacional"
CH = Path("~/dataurnas-ch/app/scripts/ch/ch.sh").expanduser()


def ch(sql: str) -> bytes:
    return subprocess.run([str(CH)], input=sql.encode(), capture_output=True, check=True).stdout


def cmd_lista(args: argparse.Namespace) -> None:
    import io

    import pandas as pd

    raw = ch("SELECT uf, cd_mun, zona, secao, hash FROM dataurnas.v_bu_ultima "
             "ORDER BY uf, cd_mun, zona, secao FORMAT Parquet")
    df = pd.read_parquet(io.BytesIO(raw))
    saida = Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)
    df.to_parquet(saida / "lista.parquet", index=False)
    log.info("%d seções", len(df))


def _registros(df) -> list[dict]:
    out = []
    for r in df.to_dict("records"):
        chave = f"{r['uf']}/{r['cd_mun']}/{r['zona']}/{r['secao']}"
        out.append({**r, "chave": chave, "turno": 2, "origem": "nacional"})
    return out


async def _baixar(regs: list[dict], brutos: Path, taxa: float, taxa_max: float) -> None:
    from dataurnas.downloader import ele2026 as E

    pend = [r for r in regs if not (A.dir_bruto(brutos, r) / "ok.json").exists()]
    log.info("%d seções, %d pendentes", len(regs), len(pend))
    f = E.HttpFetcher(concurrency=24, retries=8, rate=taxa, rate_max=taxa_max, http2=False)
    erros = brutos / "erros.jsonl"
    feitos, t0 = 0, time.time()

    async def um(r: dict) -> None:
        nonlocal feitos
        d = A.dir_bruto(brutos, r)
        url = lambda nm: E.url_arquivo(r["uf"], r["cd_mun"], r["zona"], r["secao"],  # noqa: E731
                                       r["hash"], nm, pleito="3221", ciclo=A.CICLO)
        try:
            nome = A.nome_padrao(r, "rdv")
            corpo = await f.get(url(nome))
            aux_usado = False
            if corpo is None:
                aux_usado = True
                aux = await f.get_json(E.url_aux(r["uf"], r["cd_mun"], r["zona"], r["secao"],
                                                 pleito="3221", ciclo=A.CICLO))
                hs = [x for x in (aux or {}).get("hashes") or [] if x.get("hash") == r["hash"]]
                arq = {a["tp"]: a["nm"] for a in (hs[0].get("arq") if hs else []) or []}
                if arq.get("rdv"):
                    nome = arq["rdv"]
                    corpo = await f.get(url(nome))
            d.mkdir(parents=True, exist_ok=True)
            if corpo is not None:
                tmp = d / f"{nome}.tmp"
                tmp.write_bytes(corpo)
                tmp.rename(d / nome)
            meta = {"chave": r["chave"], "turno": 2, "hash": r["hash"],
                    "nomes": {"rdv": nome} if corpo is not None else {},
                    "ausentes": [] if corpo is not None else ["rdv"], "aux_usado": aux_usado}
            (d / "ok.json").write_text(json.dumps(meta), encoding="utf-8")
        except Exception as e:  # noqa: BLE001  refeito na próxima execução
            with erros.open("a", encoding="utf-8") as fe:
                fe.write(json.dumps({"chave": r["chave"], "erro": f"{type(e).__name__}: {e}"[:300]})
                         + "\n")
        feitos += 1
        if feitos % 2000 == 0:
            el = time.time() - t0
            log.info("%d/%d (%.1f/s) %s %s", feitos, len(pend), feitos / el, f.rate_info(), f.stats)

    try:
        for i in range(0, len(pend), 48):
            await asyncio.gather(*[um(r) for r in pend[i:i + 48]])
    finally:
        await f.close()
    log.info("download concluído: %s", f.stats)


def cmd_baixar(args: argparse.Namespace) -> None:
    import pandas as pd

    if args.taxa_max > 25:
        raise SystemExit("taxa máxima permitida: 25 req/s por IP")
    df = pd.read_parquet(args.lista)
    ufs = set(args.ufs.split(","))
    df = df[df.uf.isin(ufs)]
    if args.amostra and Path(args.amostra).exists():
        am = pd.read_parquet(args.amostra)
        ja = set(am.uf + "/" + am.cd_mun + "/" + am.zona + "/" + am.secao)
        df = df[~(df.uf + "/" + df.cd_mun + "/" + df.zona + "/" + df.secao).isin(ja)]
    brutos = Path(args.brutos).expanduser()
    brutos.mkdir(parents=True, exist_ok=True)
    asyncio.run(_baixar(_registros(df), brutos, args.taxa, args.taxa_max))


def _conteudos_uf(uf: str) -> dict[tuple[str, str, str, str], dict[str, tuple[str, bytes]]]:
    """BU (ou BUSA) e .vsc da versão final de cada seção da UF, do ClickHouse."""
    import io

    import pandas as pd

    sql = f"""
    SELECT v.uf, v.cd_mun, v.zona, v.secao, v.tipo, v.nome, c.conteudo
    FROM (SELECT uf, cd_mun, zona, secao, tipo, argMax(nome, coletado_em) nome,
                 argMax(sha512, coletado_em) sha512
          FROM dataurnas.versoes_arquivo
          WHERE uf = '{uf}' AND tipo IN ('bu', 'busa', 'vota', 'sa')
          GROUP BY uf, cd_mun, zona, secao, tipo) v
    JOIN (SELECT sha512, any(conteudo) conteudo FROM dataurnas.arquivos_conteudo
          WHERE tipo IN ('bu', 'busa', 'vota', 'sa') GROUP BY sha512) c USING sha512
    FORMAT Parquet SETTINGS output_format_parquet_string_as_string = 0"""
    df = pd.read_parquet(io.BytesIO(ch(sql)))
    out: dict = {}
    txt = lambda v: v.decode() if isinstance(v, bytes) else v  # noqa: E731
    for r in df.itertuples(index=False):
        tipo = txt(r.tipo)
        tp = {"busa": "bu", "sa": "vota"}.get(tipo, tipo)
        chave = (txt(r.uf), txt(r.cd_mun), txt(r.zona), txt(r.secao))
        out.setdefault(chave, {})[tp] = (txt(r.nome), bytes(r.conteudo))
    return out


def cmd_processar(args: argparse.Namespace) -> None:
    from concurrent.futures import ProcessPoolExecutor

    import pandas as pd

    lista = pd.read_parquet(Path(args.saida) / "lista.parquet")
    if args.ufs:
        lista = lista[lista.uf.isin(args.ufs.split(","))]
    brutos = Path(args.brutos).expanduser()
    amostra = Path(args.brutos_amostra).expanduser()
    tmp = Path(f"/dev/shm/rdvnac-{os.getpid()}")
    saida = Path(args.saida)
    (saida / "uf").mkdir(parents=True, exist_ok=True)
    for uf, grupo in lista.groupby("uf"):
        alvo = saida / "uf" / f"{uf}.parquet"
        if alvo.exists():
            continue
        cont = _conteudos_uf(uf)
        tarefas = []
        for r in _registros(grupo):
            d = A.dir_bruto(brutos, r)
            if not (d / "ok.json").exists():
                d = A.dir_bruto(amostra, r)
            dt = A.dir_bruto(tmp, r)
            dt.mkdir(parents=True, exist_ok=True)
            meta = {"chave": r["chave"], "turno": 2, "hash": r["hash"], "nomes": {}, "ausentes": []}
            if (d / "ok.json").exists():
                m = json.loads((d / "ok.json").read_text(encoding="utf-8"))
                if m["nomes"].get("rdv"):
                    shutil.copy(d / m["nomes"]["rdv"], dt / m["nomes"]["rdv"])
                    meta["nomes"]["rdv"] = m["nomes"]["rdv"]
            for tp, (nm, conteudo) in cont.get((r["uf"], r["cd_mun"], r["zona"], r["secao"]),
                                               {}).items():
                (dt / nm).write_bytes(conteudo)
                meta["nomes"][tp] = nm
            meta["ausentes"] = [tp for tp in ("rdv", "bu", "vota") if tp not in meta["nomes"]]
            (dt / "ok.json").write_text(json.dumps(meta), encoding="utf-8")
            tarefas.append((r, str(dt), None))
        with ProcessPoolExecutor(max_workers=args.workers) as ex:
            res = list(ex.map(A._rdv_um, tarefas, chunksize=64))
        pd.DataFrame([x["secao"] for x in res]).to_parquet(alvo, index=False)
        cargos = [c for x in res for c in x["cargos"]]
        if cargos:
            pd.DataFrame(cargos).to_parquet(saida / "uf" / f"{uf}_cargos.parquet", index=False)
        shutil.rmtree(tmp, ignore_errors=True)
        df = pd.DataFrame([x["secao"] for x in res])
        log.info("%s: %d seções, presidente_confere=%s", uf, len(df),
                 df.get("presidente_confere", pd.Series(dtype=object)).value_counts(dropna=False).to_dict())


def cmd_relatorio(args: argparse.Namespace) -> None:
    import pandas as pd

    saida = Path(args.saida)
    df = pd.concat([pd.read_parquet(p) for p in sorted((saida / "uf").glob("??.parquet"))],
                   ignore_index=True)
    df.to_parquet(saida / "rdv_secoes.parquet", index=False)
    soma = lambda c: int(df[c].fillna(0).sum())  # noqa: E731
    div = df[df["presidente_confere"] == False]  # noqa: E712
    por_uf = {}
    for uf, g in df.groupby("uf"):
        por_uf[uf] = {"secoes": int(len(g)),
                      "com_rdv": int(g["rdv_presidente_total"].notna().sum()),
                      "confere": int((g["presidente_confere"] == True).sum()),  # noqa: E712
                      "diverge": int((g["presidente_confere"] == False).sum())}  # noqa: E712
    resumo = {
        "secoes": int(len(df)),
        "status": df["status"].value_counts(dropna=False).to_dict(),
        "com_rdv": int(df["rdv_presidente_total"].notna().sum()),
        "presidente_confere": int((df["presidente_confere"] == True).sum()),  # noqa: E712
        "presidente_diverge": int(len(div)),
        "rdv_confere_todos_cargos": int((df["rdv_confere"] == True).sum()),  # noqa: E712
        "hash_rdv_confere": int((df.get("hash_rdv_confere") == True).sum()),  # noqa: E712
        "hash_rdv_diverge": int((df.get("hash_rdv_confere") == False).sum()),  # noqa: E712
        "vsc_assinatura_valida": int((df.get("vsc_assinatura_valida") == True).sum()),  # noqa: E712
        "vsc_assinatura_invalida": int((df.get("vsc_assinatura_valida") == False).sum()),  # noqa: E712
        "totais": {k: {"rdv": soma(f"rdv_{k}"), "bu": soma(f"bu_{k}")}
                   for k in ("13", "22", "brancos", "nulos", "outros_nominais", "legenda",
                             "presidente_total")},
        "sem_rdv": sorted(df.loc[df["rdv_presidente_total"].isna(), "chave"].tolist()),
        "divergencias": div[["chave", "rdv_13", "bu_13", "rdv_22", "bu_22", "rdv_brancos",
                             "bu_brancos", "rdv_nulos", "bu_nulos"]].to_dict("records"),
        "por_uf": por_uf,
    }
    (saida / "resumo.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=1, default=str),
                                       encoding="utf-8")
    log.info("resumo: %s", {k: v for k, v in resumo.items() if k not in ("por_uf", "sem_rdv")})


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("comando", choices=["lista", "baixar", "processar", "relatorio"])
    ap.add_argument("--saida", default=str(SAIDA))
    ap.add_argument("--lista", default=str(SAIDA / "lista.parquet"))
    ap.add_argument("--ufs", default="")
    ap.add_argument("--brutos", default="~/dataurnas-t2/rdv_nacional")
    ap.add_argument("--brutos-amostra", default="~/dataurnas-t2/rdv_log/brutos")
    ap.add_argument("--amostra", default=str(ROOT / "data/parquet/2026/t2/rdv_log/amostra.parquet"))
    ap.add_argument("--taxa", type=float, default=15.0)
    ap.add_argument("--taxa-max", type=float, default=25.0)
    ap.add_argument("--workers", type=int, default=min(80, os.cpu_count() or 4))
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    {"lista": cmd_lista, "baixar": cmd_baixar, "processar": cmd_processar,
     "relatorio": cmd_relatorio}[args.comando](args)


if __name__ == "__main__":
    main()
