#!/usr/bin/env python3
"""Confronto dos produtos de dados abertos do TSE entre si e com os BUs assinados
(Presidente, 2026, 1º turno 04/10 e 2º turno 25/10).

Produtos (CDN do portal de dados abertos, descobertos pela API CKAN):
  votacao_secao_2026_BR.zip        votação nominal por seção (Presidente, BR)
  detalhe_votacao_secao_2026.zip   aptos, comparecimento, abstenção, brancos e
                                   nulos por seção e cargo
  bweb_<t>t_<UF>_*.zip             BU em CSV (boletim de urna na web)
  CESP_<t>t_<UF>_*.zip             correspondência esperada urna x seção
  CEFT_<t>t_<UF>_*.zip             correspondência efetivada urna x seção

Referência (ClickHouse do servidor de processamento, docs/banco-clickhouse.md):
  2º turno: v_bu_ultima e v_votos_t2_secao (BU binário decodificado);
  1º turno: ref_secoes_2026_t1 e ref_votos_2026_t1 (BU binário decodificado).

Subcomandos:
  baixar     baixa todos os arquivos (um processo, no máximo 3 req/s) e confere
             o .sha512 publicado ao lado de cada zip; grava manifesto.jsonl.
  extrair    lê os zips (Presidente) e grava Parquet normalizados em --dir.
  bu         exporta do ClickHouse os BUs por seção dos dois turnos para --dir.
  confrontar cruza tudo e grava as divergências e o resumo em --saida.

Uso:
  python3 -I scripts/ele2026/confronto_dados_abertos.py baixar --brutos <pasta>
  # no servidor, temporários em /dev/shm:
  python3 -I confronto_dados_abertos.py extrair --brutos ~/dataurnas-t2/dados_abertos/brutos \\
      --dir /dev/shm/dados_abertos
  python3 -I confronto_dados_abertos.py bu --dir /dev/shm/dados_abertos
  python3 -I confronto_dados_abertos.py confrontar --dir /dev/shm/dados_abertos \\
      --saida /dev/shm/dados_abertos/saida --certificados secoes_certificados.parquet \\
      --software secoes_software.parquet
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
import urllib.request
from pathlib import Path

CKAN = "https://dadosabertos.tse.jus.br/api/3/action/package_show?id="
PACOTES = (
    "resultados-2026",
    "resultados-2026-boletim-de-urna",
    "resultados-2026-correspondencias-esperadas-e-efetivadas-1-turno",
    "resultados-2026-correspondencias-esperadas-e-efetivadas-2-turno",
)
PADROES = (
    re.compile(r"/votacao_secao_2026_BR\.zip$"),
    re.compile(r"/detalhe_votacao_secao_2026\.zip$"),
    re.compile(r"/bweb_[12]t_[A-Z]{2}_\d+\.zip$"),
    re.compile(r"/CESP_[12]t_[A-Z]{2}_\d+\.zip$"),
    re.compile(r"/CEFT_[12]t_[A-Z]{2}_\d+\.zip$"),
)
UA = "dataurnas-auditoria/1.0"
INTERVALO = 0.34  # no máximo 3 requisições por segundo
CH = os.path.expanduser("~/dataurnas-ch/app/scripts/ch/ch.sh")


# ---------------------------------------------------------------------------
# baixar
# ---------------------------------------------------------------------------
class Ritmo:
    def __init__(self, intervalo: float) -> None:
        self.intervalo = intervalo
        self.ultimo = 0.0

    def esperar(self) -> None:
        falta = self.ultimo + self.intervalo - time.monotonic()
        if falta > 0:
            time.sleep(falta)
        self.ultimo = time.monotonic()


def _get(url: str, ritmo: Ritmo, destino: Path | None = None, tentativas: int = 5):
    for n in range(tentativas):
        ritmo.esperar()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=120) as r:
                if destino is None:
                    return r.status, r.read()
                tmp = destino.with_suffix(destino.suffix + ".tmp")
                h = hashlib.sha512()
                with open(tmp, "wb") as f:
                    while True:
                        b = r.read(1 << 20)
                        if not b:
                            break
                        h.update(b)
                        f.write(b)
                tmp.rename(destino)
                return r.status, h.hexdigest()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return 404, None
            erro = e
        except Exception as e:  # rede: tenta de novo com espera crescente
            erro = e
        print(f"  tentativa {n + 1} falhou: {url}: {erro}", flush=True)
        time.sleep(5 * (n + 1))
    return -1, None


def _sha512_arquivo(p: Path) -> str:
    h = hashlib.sha512()
    with open(p, "rb") as f:
        while True:
            b = f.read(1 << 22)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def cmd_baixar(a) -> None:
    brutos = Path(a.brutos).expanduser()
    brutos.mkdir(parents=True, exist_ok=True)
    ritmo = Ritmo(max(a.intervalo, INTERVALO))
    urls: list[str] = []
    pacotes = {}
    for p in PACOTES:
        st, corpo = _get(CKAN + p, ritmo)
        d = json.loads(corpo)["result"]
        pacotes[p] = {"metadata_modified": d.get("metadata_modified"),
                      "recursos": [(r["name"], r["url"]) for r in d["resources"]]}
        for r in d["resources"]:
            u = r["url"]
            if any(x.search(u) for x in PADROES):
                urls.append(u)
    (brutos / "ckan.json").write_text(json.dumps(pacotes, ensure_ascii=False, indent=1))
    urls = sorted(set(urls), key=lambda u: (os.path.basename(u).split("_")[0], u))
    print(f"{len(urls)} arquivos a baixar", flush=True)
    feitos = {}
    man = brutos / "manifesto.jsonl"
    if man.exists():
        for ln in man.read_text().splitlines():
            r = json.loads(ln)
            feitos[r["url"]] = r
    with open(man, "a") as fm:
        for i, u in enumerate(urls, 1):
            nome = os.path.basename(u)
            dest = brutos / nome
            if u in feitos and feitos[u].get("ok") and dest.exists():
                continue
            st, txt = _get(u + ".sha512", ritmo)
            publicado = None
            if st == 200 and txt:
                publicado = txt.decode("ascii", "replace").split()[0].lower()
            if dest.exists() and publicado and _sha512_arquivo(dest) == publicado:
                calc = publicado
            else:
                t0 = time.time()
                st2, calc = _get(u, ritmo, dest)
                if st2 != 200:
                    print(f"[{i}/{len(urls)}] FALHOU {st2} {nome}", flush=True)
                    fm.write(json.dumps({"url": u, "ok": False, "status": st2}) + "\n")
                    fm.flush()
                    continue
                print(f"[{i}/{len(urls)}] {nome} {dest.stat().st_size:,} B "
                      f"{time.time() - t0:.0f}s", flush=True)
            reg = {"url": u, "arquivo": nome, "tamanho": dest.stat().st_size,
                   "sha512": calc, "sha512_publicado": publicado,
                   "sha512_confere": (publicado == calc) if publicado else None,
                   "ok": True, "baixado_em": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
            if publicado and publicado != calc:
                print(f"  SHA-512 NÃO CONFERE: {nome}", flush=True)
            fm.write(json.dumps(reg) + "\n")
            fm.flush()
    print("fim", flush=True)


# ---------------------------------------------------------------------------
# extrair
# ---------------------------------------------------------------------------
def _descompactar(brutos: Path, destino: Path, filtro) -> list[Path]:
    """Extrai os CSV de cada zip aceito por filtro(nome_zip, nome_membro)."""
    import zipfile

    saida = []
    for z in sorted(brutos.glob("*.zip")):
        with zipfile.ZipFile(z) as zf:
            for m in zf.namelist():
                if not m.lower().endswith(".csv") or not filtro(z.name, m):
                    continue
                alvo = destino / z.stem / os.path.basename(m)
                if not alvo.exists():
                    alvo.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(m) as fi, open(str(alvo) + ".tmp", "wb") as fo:
                        while True:
                            b = fi.read(1 << 22)
                            if not b:
                                break
                            fo.write(b)
                    os.rename(str(alvo) + ".tmp", alvo)
                saida.append(alvo)
    return saida


def _rc(arquivos) -> str:
    lista = ", ".join(f"'{p}'" for p in arquivos)
    return (f"read_csv([{lista}], delim=';', quote='\"', header=true, all_varchar=true,"
            f" encoding='latin-1', filename=true, union_by_name=true)")


# chave normalizada no formato do banco: uf minúscula, município 5, zona e seção 4
CHAVE = ("lower(SG_UF) AS uf, lpad(CD_MUNICIPIO, 5, '0') AS cd_mun, "
         "lpad(NR_ZONA, 4, '0') AS zona, lpad(NR_SECAO, 4, '0') AS secao")


def _nulo(c: str) -> str:
    return f"nullif(nullif(nullif({c}, '#NULO#'), '#NULO'), '-1')"


def cmd_extrair(a) -> None:
    import duckdb

    brutos = Path(a.brutos).expanduser()
    d = Path(a.dir)
    csv = d / "csv"
    d.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute(f"SET threads = {a.threads}; SET temp_directory = '{d / 'duck_tmp'}';"
                " SET preserve_insertion_order = false;")

    def gravar(nome: str, sql: str) -> None:
        t0 = time.time()
        con.execute(f"COPY ({sql}) TO '{d / (nome + '.parquet')}' (FORMAT parquet, COMPRESSION zstd)")
        n = con.execute(f"SELECT count() FROM '{d / (nome + '.parquet')}'").fetchone()[0]
        print(f"{nome}: {n:,} linhas em {time.time() - t0:.0f}s", flush=True)

    # votação nominal por seção (Presidente, BR, os dois turnos)
    vs = _descompactar(brutos, csv, lambda z, m: z.startswith("votacao_secao_2026_BR"))
    gravar("vs_linhas", f"""
        SELECT NR_TURNO::INT AS turno, CD_ELEICAO AS cd_eleicao, {CHAVE},
               NR_LOCAL_VOTACAO::INT AS local_votacao, CD_CARGO AS cd_cargo,
               NR_VOTAVEL::INT AS nr_votavel, NM_VOTAVEL AS nm_votavel,
               QT_VOTOS::BIGINT AS qt_votos, DT_GERACAO || ' ' || HH_GERACAO AS geracao
        FROM {_rc(vs)}""")
    gravar("vs", f"""
        SELECT turno, uf, cd_mun, zona, secao,
               count() AS linhas, count(DISTINCT local_votacao) AS n_locais,
               any_value(local_votacao) AS local_votacao,
               sum(qt_votos) FILTER (WHERE nr_votavel = 13) AS v13,
               sum(qt_votos) FILTER (WHERE nr_votavel = 22) AS v22,
               sum(qt_votos) FILTER (WHERE nr_votavel = 95) AS brancos,
               sum(qt_votos) FILTER (WHERE nr_votavel = 96) AS nulos,
               sum(qt_votos) FILTER (WHERE nr_votavel NOT IN (13, 22, 95, 96)) AS outros,
               sum(qt_votos) AS total,
               count(*) - count(DISTINCT nr_votavel) AS votaveis_repetidos
        FROM '{d / 'vs_linhas.parquet'}' WHERE cd_cargo = '1'
        GROUP BY ALL""")

    # detalhe da apuração por seção (Presidente: arquivo _BR)
    det = _descompactar(brutos, csv, lambda z, m: z.startswith("detalhe_votacao_secao")
                        and m.endswith("_BR.csv"))
    gravar("det", f"""
        SELECT NR_TURNO::INT AS turno, CD_ELEICAO AS cd_eleicao, {CHAVE},
               CD_CARGO AS cd_cargo, QT_APTOS::INT AS aptos,
               QT_COMPARECIMENTO::INT AS comparecimento, QT_ABSTENCOES::INT AS abstencoes,
               QT_VOTOS_NOMINAIS::INT AS nominais, QT_VOTOS_BRANCOS::INT AS brancos,
               QT_VOTOS_NULOS::INT AS nulos, QT_VOTOS_LEGENDA::INT AS legenda,
               QT_VOTOS_ANULADOS_APU_SEP::INT AS anulados_apu_sep,
               NR_LOCAL_VOTACAO::INT AS local_votacao,
               {_nulo('DT_RECEBIMENTO_BU_HOR_TSE')} AS recebimento,
               {_nulo('DT_PRIM_TOT_PARCIAL_HOR_TSE')} AS prim_totalizacao,
               DS_ORIGEM_VOTO AS origem_voto, ST_SECAO_INSTALADA AS instalada,
               ST_SECAO_ANULADA AS anulada, {_nulo('CD_MODELO_URNA')} AS modelo,
               DT_GERACAO || ' ' || HH_GERACAO AS geracao
        FROM {_rc(det)}""")

    # BU na web (CSV), só Presidente
    bw = _descompactar(brutos, csv, lambda z, m: z.startswith("bweb_"))
    gravar("bweb", f"""
        SELECT NR_TURNO::INT AS turno, {CHAVE},
               count() AS linhas,
               count(DISTINCT (QT_APTOS, QT_COMPARECIMENTO, QT_ABSTENCOES, NR_URNA_EFETIVADA,
                               CD_CARGA_1_URNA_EFETIVADA, DT_ABERTURA, DT_ENCERRAMENTO,
                               DT_EMISSAO_BU)) AS n_cabecalhos,
               any_value(NR_LOCAL_VOTACAO)::INT AS local_votacao,
               any_value(QT_APTOS)::INT AS aptos,
               any_value(QT_COMPARECIMENTO)::INT AS comparecimento,
               any_value(QT_ABSTENCOES)::INT AS abstencoes,
               any_value(DS_TIPO_URNA) AS tipo_urna,
               any_value({_nulo('NR_URNA_EFETIVADA')})::BIGINT AS urna,
               any_value(replace(CD_CARGA_1_URNA_EFETIVADA || CD_CARGA_2_URNA_EFETIVADA, '.', ''))
                   AS carga,
               any_value(CD_FLASHCARD_URNA_EFETIVADA) AS flashcard,
               any_value({_nulo('DT_CARGA_URNA_EFETIVADA')}) AS dt_carga,
               any_value({_nulo('DT_ABERTURA')}) AS abertura,
               any_value({_nulo('DT_ENCERRAMENTO')}) AS encerramento,
               any_value({_nulo('DT_EMISSAO_BU')}) AS emissao,
               any_value({_nulo('DT_BU_RECEBIDO')}) AS recebido,
               any_value({_nulo('QT_ELEI_BIOM_SEM_HABILITACAO')})::INT AS biom_sem_habilitacao,
               any_value({_nulo('DS_SECOES_AGREGADAS')}) AS secoes_agregadas,
               any_value(NR_JUNTA_APURADORA) AS junta,
               sum(QT_VOTOS::BIGINT) FILTER (WHERE DS_TIPO_VOTAVEL = 'Nominal'
                                              AND NR_VOTAVEL = '13') AS v13,
               sum(QT_VOTOS::BIGINT) FILTER (WHERE DS_TIPO_VOTAVEL = 'Nominal'
                                              AND NR_VOTAVEL = '22') AS v22,
               sum(QT_VOTOS::BIGINT) FILTER (WHERE DS_TIPO_VOTAVEL = 'Nominal'
                                              AND NR_VOTAVEL NOT IN ('13', '22')) AS outros,
               sum(QT_VOTOS::BIGINT) FILTER (WHERE DS_TIPO_VOTAVEL = 'Branco') AS brancos,
               sum(QT_VOTOS::BIGINT) FILTER (WHERE DS_TIPO_VOTAVEL = 'Nulo') AS nulos,
               sum(QT_VOTOS::BIGINT) FILTER (WHERE DS_TIPO_VOTAVEL NOT IN
                                              ('Nominal', 'Branco', 'Nulo')) AS outros_tipos,
               sum(QT_VOTOS::BIGINT) AS total,
               string_agg(DISTINCT DS_TIPO_VOTAVEL, ',') AS tipos_votavel
        FROM {_rc(bw)} WHERE CD_CARGO_PERGUNTA = '1'
        GROUP BY ALL""")

    # correspondência efetivada
    ce = _descompactar(brutos, csv, lambda z, m: z.startswith("CEFT_"))
    gravar("ceft", f"""
        SELECT regexp_extract(filename, 'ceft_([12])t_', 1)::INT AS turno,
               regexp_extract(filename, '_(\\d{{12}})\\.csv', 1) AS arquivo_geracao,
               DT_GERACAO || ' ' || HH_GERACAO AS geracao, {CHAVE},
               NR_LOCAL_VOTACAO::INT AS local_votacao,
               SQ_CORRESPONDENCIA_ESPERADA AS sq_esperada,
               {_nulo('NR_URNA_ESPERADA')}::BIGINT AS urna_esperada,
               {_nulo('CD_CARGA_URNA_ESPERADA')} AS carga_esperada,
               CD_FLASHCARD_URNA_ESPERADA AS flash_esperada,
               {_nulo('DT_CARGA_URNA_ESPERADA')} AS dt_carga_esperada,
               {_nulo('DT_RECBTO_URNA_ESPERADA')} AS dt_recbto_esperada,
               SQ_CORRESPONDENCIA_EFETIVADA AS sq_efetivada,
               {_nulo('NR_URNA_EFETIVADA')}::BIGINT AS urna_efetivada,
               {_nulo('CD_CARGA_URNA_EFETIVADA')} AS carga_efetivada,
               CD_FLASHCARD_URNA_EFETIVADA AS flash_efetivada,
               {_nulo('DT_CARGA_URNA_EFETIVADA')} AS dt_carga_efetivada,
               {_nulo('DT_RECBTO_URNA_EFETIVADA')} AS dt_recbto_efetivada,
               CD_ORIGEM_VOTO AS cd_origem_voto, DS_ORIGEM_VOTO AS origem_voto,
               nullif(TP_DIVERGENCIA, '') AS tp_divergencia,
               NM_MAQUINA_GERACAO_MIDIA AS maq_geracao, NM_MAQUINA_TRANSM_CORRESP AS maq_transm
        FROM {_rc(ce)}""")

    # correspondência esperada: seções (csec) e urnas de contingência da zona (ccont)
    cs = _descompactar(brutos, csv, lambda z, m: z.startswith("CESP_")
                       and os.path.basename(m).lower().startswith("csec"))
    gravar("cesp_sec", f"""
        SELECT regexp_extract(filename, 'csec_([12])t_', 1)::INT AS turno,
               regexp_extract(filename, '_(\\d{{12}})\\.csv', 1) AS arquivo_geracao,
               DT_GERACAO || ' ' || HH_GERACAO AS geracao, {CHAVE},
               NR_LOCAL_VOTACAO::INT AS local_votacao,
               {_nulo('NR_URNA_ESPERADA')}::BIGINT AS urna_esperada,
               {_nulo('CD_CARGA_URNA_ESPERADA')} AS carga_esperada,
               CD_FLASHCARD_URNA_ESPERADA AS flash_esperada,
               {_nulo('DT_CARGA_URNA_ESPERADA')} AS dt_carga_esperada,
               ST_CORRESP_ALTERADA AS st_alterada,
               NM_MAQUINA_GERACAO_MIDIA AS maq_geracao
        FROM {_rc(cs)}""")
    cc = _descompactar(brutos, csv, lambda z, m: z.startswith("CESP_")
                       and os.path.basename(m).lower().startswith("ccont"))
    gravar("cesp_cont", f"""
        SELECT regexp_extract(filename, 'ccont_([12])t_', 1)::INT AS turno,
               regexp_extract(filename, '_(\\d{{12}})\\.csv', 1) AS arquivo_geracao,
               DT_GERACAO || ' ' || HH_GERACAO AS geracao,
               lower(SG_UF) AS uf, lpad(CD_MUNICIPIO, 5, '0') AS cd_mun,
               lpad(NR_ZONA, 4, '0') AS zona,
               {_nulo('NR_URNA_ESPERADA')}::BIGINT AS urna_esperada,
               {_nulo('CD_CARGA_URNA_ESPERADA')} AS carga_esperada,
               CD_FLASHCARD_URNA_ESPERADA AS flash_esperada,
               {_nulo('DT_CARGA_URNA_ESPERADA')} AS dt_carga_esperada,
               ST_CORRESP_ALTERADA AS st_alterada,
               NM_MAQUINA_GERACAO_MIDIA AS maq_geracao
        FROM {_rc(cc)}""")
    print("fim", flush=True)


# ---------------------------------------------------------------------------
# bu (ClickHouse)
# ---------------------------------------------------------------------------
SQL_BU_T2 = """
SELECT 2 AS turno, u.uf AS uf, u.cd_mun AS cd_mun, u.zona AS zona, u.secao AS secao,
       'ok' AS status, u.tipo_arquivo AS tipo_arquivo,
       toString(u.recebimento) AS recebimento, toString(u.data_hora_emissao) AS emissao,
       toString(u.hora_abertura) AS abertura, toString(u.hora_encerramento) AS encerramento,
       u.tipo_urna AS tipo_urna, u.numero_interno_urna AS urna, u.codigo_carga AS carga,
       u.qtd_codigos_carga AS qtd_codigos_carga, u.local_votacao AS local_votacao,
       u.aptos AS aptos, u.aptos_secao AS aptos_secao, u.aptos_tte AS aptos_tte,
       u.comparecimento AS comparecimento, u.comp_sem_biometria AS comp_sem_biometria,
       u.habilitados_biometria AS habilitados_biometria,
       v.v13 AS v13, v.v22 AS v22, v.outros AS outros, v.brancos AS brancos,
       v.nulos AS nulos, v.total AS total, m.modelo AS modelo
FROM v_bu_ultima AS u
LEFT JOIN (
    SELECT uf, cd_mun, zona, secao, sha512_bu,
           sumIf(votos, tipo_voto = 'nominal' AND numero = 13) AS v13,
           sumIf(votos, tipo_voto = 'nominal' AND numero = 22) AS v22,
           sumIf(votos, tipo_voto = 'nominal' AND numero NOT IN (13, 22)) AS outros,
           sumIf(votos, tipo_voto = 'branco') AS brancos,
           sumIf(votos, tipo_voto = 'nulo') AS nulos,
           sum(votos) AS total
    FROM bu_votos FINAL GROUP BY uf, cd_mun, zona, secao, sha512_bu
) AS v ON v.uf = u.uf AND v.cd_mun = u.cd_mun AND v.zona = u.zona AND v.secao = u.secao
      AND v.sha512_bu = u.sha512
LEFT JOIN (
    SELECT uf, cd_mun, zona, secao, any(modelo_urna_cod) AS modelo
    FROM versoes_arquivo FINAL WHERE tipo IN ('vota', 'sa')
    GROUP BY uf, cd_mun, zona, secao
) AS m ON m.uf = u.uf AND m.cd_mun = u.cd_mun AND m.zona = u.zona AND m.secao = u.secao
SETTINGS join_use_nulls = 1
FORMAT Parquet
"""

SQL_BU_T1 = """
SELECT 1 AS turno, s.uf AS uf, s.cd_mun AS cd_mun, s.zona AS zona, s.secao AS secao,
       toString(s.status) AS status, s.secao_principal AS secao_principal,
       s.secoes_agregadas AS secoes_agregadas, toString(s.origem_bu) AS tipo_arquivo,
       concat(ifNull(s.dt_recebimento, ''), ' ', ifNull(s.hr_recebimento, '')) AS recebimento,
       toString(s.data_hora_emissao) AS emissao,
       toString(s.hora_abertura) AS abertura, toString(s.hora_encerramento) AS encerramento,
       toString(s.tipo_urna) AS tipo_urna, s.numero_interno_urna AS urna, s.codigo_carga AS carga,
       s.qtd_codigos_carga AS qtd_codigos_carga, s.local_votacao AS local_votacao,
       s.aptos AS aptos, s.aptos_secao AS aptos_secao, s.aptos_tte AS aptos_tte,
       s.comparecimento AS comparecimento, s.comp_sem_biometria AS comp_sem_biometria,
       s.habilitados_biometria AS habilitados_biometria,
       v.v13 AS v13, v.v22 AS v22, v.outros AS outros, v.brancos AS brancos,
       v.nulos AS nulos, v.total AS total, s.modelo_urna_cod AS modelo
FROM ref_secoes_2026_t1 AS s
LEFT JOIN (
    SELECT uf, cd_mun, zona, secao,
           sumIf(votos, tipo_voto = 'nominal' AND numero = 13) AS v13,
           sumIf(votos, tipo_voto = 'nominal' AND numero = 22) AS v22,
           sumIf(votos, tipo_voto = 'nominal' AND numero NOT IN (13, 22)) AS outros,
           sumIf(votos, tipo_voto = 'branco') AS brancos,
           sumIf(votos, tipo_voto = 'nulo') AS nulos,
           sum(votos) AS total
    FROM ref_votos_2026_t1 GROUP BY uf, cd_mun, zona, secao
) AS v ON v.uf = s.uf AND v.cd_mun = s.cd_mun AND v.zona = s.zona AND v.secao = s.secao
SETTINGS join_use_nulls = 1
FORMAT Parquet
"""


def cmd_bu(a) -> None:
    import subprocess

    d = Path(a.dir)
    d.mkdir(parents=True, exist_ok=True)
    for nome, sql in (("bu_t1", SQL_BU_T1), ("bu_t2", SQL_BU_T2)):
        with open(d / f"{nome}.parquet", "wb") as f:
            subprocess.run([CH], input=sql.encode(), stdout=f, check=True)
        print(nome, (d / f"{nome}.parquet").stat().st_size, flush=True)


# ---------------------------------------------------------------------------
# confrontar
# ---------------------------------------------------------------------------
K = ("uf", "cd_mun", "zona", "secao")
ON = " AND ".join(f"p.{k} = b.{k}" for k in ("turno",) + K)

# seções do 2º turno com certificado de urna diferente do número interno da carga
# (docs/certificados-2turno-2026.md): seção -> número da urna que assinou (CN)
CERT = {
    ("sp", "64777", "0393", "0312"): 2399743,
    ("rj", "58696", "0027", "0139"): 2189420,
    ("es", "57932", "0009", "0085"): 1758779,
}

# campos comparados como texto; os demais como inteiro
TEXTO = {"carga", "abertura", "encerramento", "emissao_bu", "modelo_urna"}

# (confronto, produto, turnos, [(campo, expressão no produto, expressão no BU)])
CONFRONTOS = [
    ("votacao_secao x BU", "vs", (1, 2), [
        ("votos_13", "p.v13", "b.v13"), ("votos_22", "p.v22", "b.v22"),
        ("brancos", "p.brancos", "b.brancos"), ("nulos", "p.nulos", "b.nulos"),
        ("outros_candidatos", "coalesce(p.outros, 0)", "b.outros"),
        ("total", "p.total", "b.total"),
        ("local_votacao", "p.local_votacao", "b.local_votacao"),
    ]),
    ("detalhe_votacao_secao x BU", "det", (1, 2), [
        ("aptos", "p.aptos", "b.aptos"),
        ("comparecimento", "p.comparecimento", "b.comparecimento"),
        ("abstencao", "p.abstencoes", "b.aptos - b.comparecimento"),
        ("nominais", "p.nominais", "b.v13 + b.v22 + b.outros"),
        ("brancos", "p.brancos", "b.brancos"), ("nulos", "p.nulos", "b.nulos"),
        ("legenda", "p.legenda", "0"),
        ("anulados_apurados_em_separado", "p.anulados_apu_sep", "0"),
        ("local_votacao", "p.local_votacao", "b.local_votacao"),
        ("modelo_urna", "right(p.modelo, 2)", "b.modelo::VARCHAR"),
    ]),
    ("detalhe x votacao_secao", "det_vs", (1, 2), [
        ("nominais", "p.nominais", "b.v13 + b.v22 + coalesce(b.outros, 0)"),
        ("brancos", "p.brancos", "b.brancos"), ("nulos", "p.nulos", "b.nulos"),
        ("local_votacao", "p.local_votacao", "b.local_votacao"),
    ]),
    ("bweb x BU", "bweb", (1, 2), [
        ("aptos", "p.aptos", "b.aptos"),
        ("comparecimento", "p.comparecimento", "b.comparecimento"),
        ("abstencao", "p.abstencoes", "b.aptos - b.comparecimento"),
        ("votos_13", "p.v13", "b.v13"), ("votos_22", "p.v22", "b.v22"),
        ("outros_candidatos", "coalesce(p.outros, 0)", "b.outros"),
        ("brancos", "coalesce(p.brancos, 0)", "b.brancos"),
        ("nulos", "coalesce(p.nulos, 0)", "b.nulos"),
        ("total", "p.total", "b.total"),
        ("urna", "p.urna", "b.urna"),
        ("carga", "lpad(p.carga, 24, '0')", "lpad(b.carga, 24, '0')"),
        ("abertura", "p.abertura", "b.abertura"),
        ("encerramento", "p.encerramento", "b.encerramento"),
        ("emissao_bu", "p.emissao", "b.emissao"),
        ("local_votacao", "p.local_votacao", "b.local_votacao"),
    ]),
    ("correspondência efetivada x BU", "ceft", (1, 2), [
        ("urna", "p.urna_efetivada", "b.urna"),
        ("carga", "lpad(p.carga_efetivada, 24, '0')", "lpad(b.carga, 24, '0')"),
        ("local_votacao", "p.local_votacao", "b.local_votacao"),
    ]),
]


def cmd_confrontar(a) -> None:
    import duckdb

    d = Path(a.dir)
    out = Path(a.saida)
    out.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect()
    con.execute(f"SET threads = {a.threads}; SET temp_directory = '{d / 'duck_tmp'}';")
    q = lambda s: con.execute(s).fetchall()  # noqa: E731

    def par(nome: str) -> str:
        return f"'{d / (nome + '.parquet')}'"

    def gravar(nome: str, sql: str, csv: bool = False) -> int:
        ext = "csv" if csv else "parquet"
        fmt = "(FORMAT csv, HEADER)" if csv else "(FORMAT parquet, COMPRESSION zstd)"
        con.execute(f"COPY ({sql}) TO '{out / (nome + '.' + ext)}' {fmt}")
        return con.execute(f"SELECT count() FROM ({sql})").fetchone()[0]

    iso = "strftime(strptime({c}, '%d/%m/%Y %H:%M:%S'), '%Y-%m-%d %H:%M:%S')"
    con.execute(f"""
        CREATE VIEW bu AS
        SELECT * REPLACE (
                   CASE WHEN status = 'ok' THEN coalesce(v13, 0) END AS v13,
                   CASE WHEN status = 'ok' THEN coalesce(v22, 0) END AS v22,
                   CASE WHEN status = 'ok' THEN coalesce(outros, 0) END AS outros,
                   CASE WHEN status = 'ok' THEN coalesce(brancos, 0) END AS brancos,
                   CASE WHEN status = 'ok' THEN coalesce(nulos, 0) END AS nulos,
                   CASE WHEN status = 'ok' THEN coalesce(total, 0) END AS total),
               total IS NULL AND status = 'ok' AS bu_sem_votos_presidente,
               CASE WHEN turno = 1 AND trim(recebimento) != ''
                    THEN {iso.format(c='recebimento')} ELSE recebimento END AS receb_iso
        FROM read_parquet([{par('bu_t1')}, {par('bu_t2')}], union_by_name = true);
        CREATE VIEW bu_ok AS SELECT * FROM bu WHERE status = 'ok';
        -- votável sem voto não aparece no produto: soma ausente vale 0
        CREATE VIEW vs AS SELECT * REPLACE (coalesce(v13, 0) AS v13, coalesce(v22, 0) AS v22, coalesce(brancos, 0) AS brancos, coalesce(nulos, 0) AS nulos, coalesce(outros, 0) AS outros)
            FROM {par('vs')};
        CREATE VIEW det AS SELECT *, {iso.format(c='recebimento')} AS receb_iso
            FROM {par('det')} WHERE cd_cargo = '1';
        CREATE VIEW bweb AS SELECT * REPLACE (coalesce(v13, 0) AS v13, coalesce(v22, 0) AS v22, coalesce(brancos, 0) AS brancos, coalesce(nulos, 0) AS nulos, coalesce(outros, 0) AS outros, coalesce(outros_tipos, 0) AS outros_tipos)
            FROM {par('bweb')};
        CREATE VIEW ceft AS SELECT * FROM {par('ceft')};
        CREATE VIEW csec AS SELECT * FROM {par('cesp_sec')};
        CREATE VIEW ccont AS SELECT * FROM {par('cesp_cont')};
        -- geração mais recente da correspondência esperada de cada turno
        CREATE VIEW csec_ult AS SELECT * FROM csec
            WHERE (turno, arquivo_geracao) IN (SELECT (turno, max(arquivo_geracao))
                   FROM csec GROUP BY turno, uf);
    """)
    r: dict = {"entradas": {}, "cobertura": {}, "confrontos": {}}

    # --- entradas -----------------------------------------------------------
    for t in ("vs", "det", "bweb", "ceft", "csec", "ccont", "bu"):
        r["entradas"][t] = q(f"SELECT turno, count(), count(DISTINCT (uf, cd_mun, zona"
                             f"{', secao' if t != 'ccont' else ''})) FROM {t} GROUP BY 1 ORDER BY 1")
    r["entradas"]["bu_status"] = q("SELECT turno, status, count() FROM bu GROUP BY ALL ORDER BY ALL")
    r["entradas"]["vs_votaveis_especiais"] = q(
        "SELECT turno, nr_votavel, any_value(nm_votavel), count(), sum(qt_votos) "
        f"FROM {par('vs_linhas')} WHERE nr_votavel IN (95, 96, 97) OR nr_votavel > 99 "
        "GROUP BY ALL ORDER BY ALL")
    r["entradas"]["vs_votaveis_repetidos"] = q("SELECT turno, count() FROM vs WHERE votaveis_repetidos > 0 GROUP BY 1")
    r["entradas"]["bweb_cabecalho_inconsistente"] = q("SELECT turno, count() FROM bweb WHERE n_cabecalhos > 1 GROUP BY 1")
    r["entradas"]["bweb_tipos_votavel"] = q("SELECT turno, tipos_votavel, count() FROM bweb GROUP BY ALL ORDER BY 3 DESC")
    r["entradas"]["bweb_tipo_urna"] = q("SELECT turno, tipo_urna, count() FROM bweb GROUP BY ALL ORDER BY ALL")
    r["entradas"]["det_status"] = q(
        "SELECT turno, origem_voto, instalada, anulada, count() FROM det GROUP BY ALL ORDER BY ALL")
    r["entradas"]["det_cargos"] = q(f"SELECT turno, cd_cargo, count() FROM {par('det')} GROUP BY ALL ORDER BY ALL")
    r["entradas"]["ceft_tp_divergencia"] = q(
        "SELECT turno, cd_origem_voto, tp_divergencia, count(), "
        "count() FILTER (WHERE urna_esperada IS DISTINCT FROM urna_efetivada) "
        "FROM ceft GROUP BY ALL ORDER BY ALL")
    r["entradas"]["ceft_linhas_por_secao"] = q(
        "SELECT turno, n, count() FROM (SELECT turno, uf, cd_mun, zona, secao, count() n "
        "FROM ceft GROUP BY ALL) GROUP BY ALL ORDER BY ALL")
    r["entradas"]["csec_geracoes"] = q(
        "SELECT turno, arquivo_geracao, st_alterada, count() FROM csec GROUP BY ALL ORDER BY ALL")
    r["entradas"]["ccont_geracoes"] = q(
        "SELECT turno, arquivo_geracao, st_alterada, count() FROM ccont GROUP BY ALL ORDER BY ALL")

    # --- cobertura: seção presente no produto e no BU -----------------------
    cob = []
    for t in ("vs", "det", "bweb", "ceft", "csec_ult"):
        cob.append(f"""
          SELECT '{t}' AS produto, coalesce(p.turno, b.turno) AS turno,
                 coalesce(p.uf, b.uf) AS uf, coalesce(p.cd_mun, b.cd_mun) AS cd_mun,
                 coalesce(p.zona, b.zona) AS zona, coalesce(p.secao, b.secao) AS secao,
                 p.uf IS NOT NULL AS no_produto, b.uf IS NOT NULL AS no_bu, b.status AS status_bu
          FROM (SELECT DISTINCT turno, uf, cd_mun, zona, secao FROM {t}) p
          FULL JOIN bu b ON {ON}
          WHERE b.turno IN (SELECT DISTINCT turno FROM {t}) OR b.uf IS NULL""")
    con.execute("CREATE TABLE cob AS " + " UNION ALL ".join(cob))
    r["cobertura"]["resumo"] = q("""
        SELECT produto, turno, no_produto, no_bu, coalesce(status_bu, '-'), count()
        FROM cob GROUP BY ALL ORDER BY ALL""")
    gravar("cobertura_divergente", "SELECT * FROM cob WHERE NOT coalesce(no_produto AND status_bu = 'ok', false) "
           "AND NOT coalesce(NOT no_produto AND status_bu IN ('agregada', 'nao_instalada'), false)")

    # --- confrontos campo a campo ------------------------------------------
    partes = []
    for nome, prod, turnos, campos in CONFRONTOS:
        if prod == "det_vs":
            src, ref = "det", "vs"
        else:
            src, ref = prod, "bu_ok"
        for campo, ep, eb in campos:
            if campo not in TEXTO:
                ep, eb = f"TRY_CAST({ep} AS BIGINT)", f"TRY_CAST({eb} AS BIGINT)"
            partes.append(f"""
              SELECT '{nome}' AS confronto, p.turno, p.uf, p.cd_mun, p.zona, p.secao,
                     '{campo}' AS campo, ({ep})::VARCHAR AS valor_produto,
                     ({eb})::VARCHAR AS valor_referencia
              FROM {src} p JOIN {ref} b ON {ON}
              WHERE p.turno IN {tuple(turnos) if len(turnos) > 1 else f'({turnos[0]})'}
                AND ({ep})::VARCHAR IS DISTINCT FROM ({eb})::VARCHAR""")
    con.execute("CREATE TABLE div AS " + " UNION ALL ".join(partes))
    gravar("divergencias", "SELECT * FROM div ORDER BY ALL")
    r["confrontos"]["divergencias_por_campo"] = q(
        "SELECT confronto, turno, campo, count(), count(DISTINCT (uf, cd_mun, zona, secao)) "
        "FROM div GROUP BY ALL ORDER BY ALL")
    # pares comparados por confronto (denominador)
    for nome, prod, _turnos, _ in CONFRONTOS:
        src, ref = ("det", "vs") if prod == "det_vs" else (prod, "bu_ok")
        r["confrontos"][f"pares::{nome}"] = q(
            f"SELECT p.turno, count() FROM {src} p JOIN {ref} b ON {ON} GROUP BY 1 ORDER BY 1")
    # totais nacionais por produto
    r["confrontos"]["totais"] = {
        "bu": q("SELECT turno, sum(v13), sum(v22), sum(brancos), sum(nulos), sum(outros), "
                "sum(aptos), sum(comparecimento), count() FROM bu_ok GROUP BY 1 ORDER BY 1"),
        "vs": q("SELECT turno, sum(v13), sum(v22), sum(brancos), sum(nulos), sum(outros), "
                "NULL, NULL, count() FROM vs GROUP BY 1 ORDER BY 1"),
        "det": q("SELECT turno, NULL, NULL, sum(brancos), sum(nulos), sum(nominais), "
                 "sum(aptos), sum(comparecimento), count() FROM det GROUP BY 1 ORDER BY 1"),
        "bweb": q("SELECT turno, sum(v13), sum(v22), sum(brancos), sum(nulos), sum(outros), "
                  "sum(aptos), sum(comparecimento), count() FROM bweb GROUP BY 1 ORDER BY 1"),
    }
    # recebimento do BU: data/hora do produto x data/hora da coleta do BU (aux.json no
    # 2º turno; referência do 1º turno). Diferença em segundos, só informativo.
    for t, col in (("det", "receb_iso"), ("bweb", "recebido")):
        r["confrontos"][f"recebimento_delta_s::{t}"] = q(f"""
            WITH x AS (SELECT p.turno, date_diff('second', TRY_CAST(b.receb_iso AS TIMESTAMP),
                                                 TRY_CAST(p.{col} AS TIMESTAMP)) AS dlt
                       FROM {t} p JOIN bu_ok b ON {ON})
            SELECT turno, count(), count(dlt), count() FILTER (WHERE dlt = 0),
                   count() FILTER (WHERE abs(dlt) <= 5), count() FILTER (WHERE abs(dlt) > 300),
                   min(dlt), quantile_cont(dlt, 0.5), max(dlt)
            FROM x GROUP BY 1 ORDER BY 1""")
    r["entradas"]["bu_sem_votos_presidente"] = q(
        "SELECT turno, uf, cd_mun, zona, secao, aptos, comparecimento FROM bu "
        "WHERE bu_sem_votos_presidente ORDER BY ALL")
    r["entradas"]["ceft_carga_23_digitos"] = q(
        "SELECT turno, count() FROM ceft WHERE length(carga_efetivada) < 24 GROUP BY 1")

    # biometria: o bweb traz QT_ELEI_BIOM_SEM_HABILITACAO; o BU, comparecimento sem
    # biometria. Só informativo (os conceitos podem não ser iguais).
    r["confrontos"]["bweb_biometria"] = q(f"""
        SELECT p.turno, count(), count() FILTER (WHERE p.biom_sem_habilitacao = b.comp_sem_biometria),
               sum(p.biom_sem_habilitacao), sum(b.comp_sem_biometria)
        FROM bweb p JOIN bu_ok b ON {ON} GROUP BY 1""")

    # --- correspondências: urna esperada, efetivada e a do BU ---------------
    lp = "lpad({c}, 24, '0')"
    con.execute(f"""
        CREATE TABLE urnas AS
        WITH b1 AS (SELECT * FROM bu_ok WHERE turno = 1),
             b2 AS (SELECT * FROM bu_ok WHERE turno = 2),
             c1 AS (SELECT * FROM ceft WHERE turno = 1),
             e1 AS (SELECT * FROM csec_ult WHERE turno = 1),
             e2 AS (SELECT * FROM csec_ult WHERE turno = 2),
             e2a AS (SELECT * FROM csec WHERE turno = 2 AND arquivo_geracao =
                     (SELECT min(arquivo_geracao) FROM csec WHERE turno = 2))
        SELECT coalesce(b2.uf, b1.uf) AS uf, coalesce(b2.cd_mun, b1.cd_mun) AS cd_mun,
               coalesce(b2.zona, b1.zona) AS zona, coalesce(b2.secao, b1.secao) AS secao,
               b1.urna AS urna_bu_t1, {lp.format(c='b1.carga')} AS carga_bu_t1,
               b1.tipo_urna AS tipo_urna_t1, b1.qtd_codigos_carga AS qtd_cargas_t1,
               e1.urna_esperada AS urna_esp_t1_cesp, c1.urna_esperada AS urna_esp_t1,
               {lp.format(c='c1.carga_esperada')} AS carga_esp_t1,
               c1.urna_efetivada AS urna_efet_t1, {lp.format(c='c1.carga_efetivada')} AS carga_efet_t1,
               c1.tp_divergencia AS tp_div_t1, c1.cd_origem_voto AS origem_t1,
               b2.urna AS urna_bu_t2, {lp.format(c='b2.carga')} AS carga_bu_t2,
               b2.tipo_urna AS tipo_urna_t2, b2.qtd_codigos_carga AS qtd_cargas_t2,
               e2.urna_esperada AS urna_esp_t2, {lp.format(c='e2.carga_esperada')} AS carga_esp_t2,
               e2.st_alterada AS st_alterada_t2, e2a.urna_esperada AS urna_esp_t2_1a_geracao,
               e2a.st_alterada AS st_alterada_t2_1a_geracao
        FROM b2
        FULL JOIN b1 USING (uf, cd_mun, zona, secao)
        LEFT JOIN c1 USING (uf, cd_mun, zona, secao)
        LEFT JOIN e1 USING (uf, cd_mun, zona, secao)
        LEFT JOIN e2 USING (uf, cd_mun, zona, secao)
        LEFT JOIN e2a USING (uf, cd_mun, zona, secao);
        -- urnas de contingência esperadas (qualquer geração do turno)
        CREATE TABLE cont AS SELECT DISTINCT turno, uf, cd_mun, zona, urna_esperada AS urna FROM ccont;
        CREATE TABLE sec_urna AS SELECT DISTINCT turno, urna_esperada AS urna, uf, cd_mun, zona, secao
            FROM csec;
        CREATE TABLE bu_urna AS SELECT turno, urna, uf, cd_mun, zona, secao, tipo_urna FROM bu_ok;
    """)

    def explica(t: int) -> str:
        """Classifica a urna do BU contra as correspondências do turno t."""
        bu, esp, tipo = f"u.urna_bu_t{t}", f"u.urna_esp_t{t}", f"u.tipo_urna_t{t}"
        outra = "(x.uf, x.cd_mun, x.zona, x.secao) != (u.uf, u.cd_mun, u.zona, u.secao)"
        return f"""
          CASE WHEN {bu} IS NULL THEN 'sem BU'
               WHEN {esp} IS NULL THEN 'sem correspondência esperada'
               WHEN {esp} = {bu} THEN 'igual à esperada'
               ELSE (CASE WHEN {tipo} = 'secao' THEN 'seção comum: ' ELSE 'reserva/contingência: ' END) ||
                 CASE WHEN EXISTS (SELECT 1 FROM cont x WHERE x.turno = {t} AND x.uf = u.uf
                                   AND x.zona = u.zona AND x.urna = {bu})
                        THEN 'urna de contingência da zona'
                      WHEN EXISTS (SELECT 1 FROM cont x WHERE x.turno = {t} AND x.uf = u.uf
                                   AND x.urna = {bu})
                        THEN 'urna de contingência de outra zona da UF'
                      WHEN EXISTS (SELECT 1 FROM cont x WHERE x.turno = {t} AND x.urna = {bu})
                        THEN 'urna de contingência de outra UF'
                      WHEN EXISTS (SELECT 1 FROM sec_urna x WHERE x.turno = {t} AND x.urna = {bu}
                                   AND {outra})
                        THEN 'urna esperada em outra seção'
                      ELSE 'urna fora das correspondências do turno' END
          END"""

    con.execute(f"""
        CREATE TABLE urnas_cls AS
        SELECT u.*,
          {explica(1)} AS explicacao_t1,
          (u.urna_efet_t1 = u.urna_bu_t1) AS t1_efetivada_igual_bu,
          (u.carga_efet_t1 = u.carga_bu_t1) AS t1_carga_efetivada_igual_bu,
          (u.urna_esp_t1_cesp IS NOT DISTINCT FROM u.urna_esp_t1) AS t1_cesp_igual_ceft,
          {explica(2)} AS explicacao_t2,
          (u.carga_esp_t2 = u.carga_bu_t2) AS t2_carga_esperada_igual_bu,
          (SELECT string_agg(x.uf || '/' || x.cd_mun || '/' || x.zona || '/' || x.secao || ' ' ||
                             x.tipo_urna, '; ')
             FROM bu_urna x WHERE x.turno = 2 AND x.urna = u.urna_bu_t2
              AND (x.uf, x.cd_mun, x.zona, x.secao) != (u.uf, u.cd_mun, u.zona, u.secao))
              AS t2_urna_bu_em_outra_secao,
          (SELECT string_agg(x.uf || '/' || x.cd_mun || '/' || x.zona || '/' || x.secao || ' ' ||
                             x.tipo_urna, '; ')
             FROM bu_urna x WHERE x.turno = 2 AND x.urna = u.urna_esp_t2
              AND (x.uf, x.cd_mun, x.zona, x.secao) != (u.uf, u.cd_mun, u.zona, u.secao))
              AS t2_urna_esperada_usada_em,
          (u.urna_bu_t1 != u.urna_bu_t2) AS urna_mudou_entre_turnos,
          (u.urna_esp_t2 = u.urna_bu_t1) AS t2_esperava_urna_do_t1,
          (u.urna_esp_t2 IS DISTINCT FROM u.urna_esp_t2_1a_geracao) AS t2_esperada_mudou_entre_geracoes
        FROM urnas u
    """)
    gravar("urnas_secao", "SELECT * FROM urnas_cls")
    r["correspondencia"] = {
        "t1_efetivada_x_bu": q("""
            SELECT t1_efetivada_igual_bu, t1_carga_efetivada_igual_bu, count() FROM urnas_cls
            WHERE urna_bu_t1 IS NOT NULL GROUP BY ALL ORDER BY ALL"""),
        "t1_explicacao": q("""
            SELECT tipo_urna_t1, tp_div_t1, origem_t1, explicacao_t1, count() FROM urnas_cls
            WHERE urna_bu_t1 IS NOT NULL GROUP BY ALL ORDER BY ALL"""),
        "t1_cesp_x_ceft": q("SELECT t1_cesp_igual_ceft, count() FROM urnas_cls "
                            "WHERE urna_bu_t1 IS NOT NULL GROUP BY ALL"),
        "t2_explicacao": q("""
            SELECT tipo_urna_t2, explicacao_t2, count() FROM urnas_cls
            WHERE urna_bu_t2 IS NOT NULL GROUP BY ALL ORDER BY ALL"""),
        "t2_carga": q("""
            SELECT tipo_urna_t2, explicacao_t2 = 'igual à esperada', t2_carga_esperada_igual_bu,
                   qtd_cargas_t2, count()
            FROM urnas_cls WHERE urna_bu_t2 IS NOT NULL GROUP BY ALL ORDER BY ALL"""),
        "mudou_entre_turnos": q("""
            SELECT tipo_urna_t1, tipo_urna_t2, t2_esperava_urna_do_t1, explicacao_t2, count()
            FROM urnas_cls WHERE urna_mudou_entre_turnos GROUP BY ALL ORDER BY ALL"""),
        "t2_esperada_mudou_entre_geracoes": q("""
            SELECT st_alterada_t2_1a_geracao, st_alterada_t2, t2_esperada_mudou_entre_geracoes,
                   count() FROM urnas_cls WHERE urna_bu_t2 IS NOT NULL GROUP BY ALL ORDER BY ALL"""),
        "t2_mudou_geracao_x_bu": q("""
            SELECT urna_bu_t2 = urna_esp_t2 AS bu_igual_2a, urna_bu_t2 = urna_esp_t2_1a_geracao
                   AS bu_igual_1a, urna_bu_t1 = urna_esp_t2_1a_geracao AS t1_igual_1a,
                   tipo_urna_t2, count()
            FROM urnas_cls WHERE t2_esperada_mudou_entre_geracoes AND urna_bu_t2 IS NOT NULL
            GROUP BY ALL ORDER BY ALL"""),
        # a 2ª geração marca ST_CORRESP_ALTERADA (S alterada, * nova, N não alterada):
        # confere a marca com a mudança real de urna ou carga entre as gerações
        "geracoes_x_marca": q("""
            WITH g AS (SELECT turno, min(arquivo_geracao) g1, max(arquivo_geracao) g2
                       FROM csec GROUP BY turno),
                 a AS (SELECT c.* FROM csec c JOIN g ON c.turno = g.turno AND c.arquivo_geracao = g.g1),
                 b AS (SELECT c.* FROM csec c JOIN g ON c.turno = g.turno AND c.arquivo_geracao = g.g2)
            SELECT b.turno, b.st_alterada, a.uf IS NULL AS nova_na_2a,
                   a.urna_esperada IS DISTINCT FROM b.urna_esperada AS urna_mudou,
                   lpad(a.carga_esperada, 24, '0') IS DISTINCT FROM lpad(b.carga_esperada, 24, '0')
                       AS carga_mudou, count()
            FROM b LEFT JOIN a USING (turno, uf, cd_mun, zona, secao)
            GROUP BY ALL ORDER BY ALL"""),
        "geracoes_sumidas_na_2a": q("""
            WITH g AS (SELECT turno, min(arquivo_geracao) g1, max(arquivo_geracao) g2
                       FROM csec GROUP BY turno),
                 a AS (SELECT c.* FROM csec c JOIN g ON c.turno = g.turno AND c.arquivo_geracao = g.g1),
                 b AS (SELECT c.* FROM csec c JOIN g ON c.turno = g.turno AND c.arquivo_geracao = g.g2)
            SELECT a.turno, a.uf, a.cd_mun, a.zona, a.secao, a.urna_esperada
            FROM a ANTI JOIN b USING (turno, uf, cd_mun, zona, secao) ORDER BY ALL"""),
        "t2_urna_bu_repetida": q("""
            SELECT count() FROM urnas_cls WHERE t2_urna_bu_em_outra_secao IS NOT NULL"""),
    }
    gravar("urna_t2_secao_comum_sem_explicacao", """
        SELECT * FROM urnas_cls WHERE explicacao_t2 LIKE 'seção comum:%' ORDER BY ALL""")
    gravar("urna_t2_reserva_fora_contingencia", """
        SELECT * FROM urnas_cls WHERE explicacao_t2 LIKE 'reserva/contingência:%'
          AND explicacao_t2 NOT LIKE '%contingência da zona' ORDER BY ALL""")
    gravar("urna_t2_carga_diverge", """
        SELECT * FROM urnas_cls WHERE explicacao_t2 = 'igual à esperada'
          AND NOT coalesce(t2_carga_esperada_igual_bu, false) AND tipo_urna_t2 = 'secao'
        ORDER BY ALL""")
    gravar("urna_t1_divergente", """
        SELECT * FROM urnas_cls WHERE urna_bu_t1 IS NOT NULL AND (
              NOT coalesce(t1_efetivada_igual_bu, false)
           OR NOT coalesce(t1_carga_efetivada_igual_bu, false)
           OR explicacao_t1 LIKE 'seção comum:%'
           OR (explicacao_t1 LIKE 'reserva/contingência:%' AND tp_div_t1 IS NULL)
           OR (explicacao_t1 = 'igual à esperada' AND tp_div_t1 IS NOT NULL)) ORDER BY ALL""")

    # --- as 3 seções de certificado diferente -------------------------------
    cert = []
    for (uf, mun, zona, sec), cn in CERT.items():
        linha = q(f"""SELECT * FROM urnas_cls WHERE uf='{uf}' AND cd_mun='{mun}'
                      AND zona='{zona}' AND secao='{sec}'""")
        cols = [c[0] for c in con.description]
        reg = {"secao": f"{uf.upper()}/{mun}/{zona}/{sec}", "urna_certificado": cn,
               "linha": dict(zip(cols, linha[0], strict=True)) if linha else None}
        reg["certificado_em_csec"] = q(f"SELECT turno, arquivo_geracao, uf, cd_mun, zona, secao, st_alterada FROM csec WHERE urna_esperada = {cn} ORDER BY ALL")
        reg["certificado_em_ccont"] = q(f"SELECT turno, arquivo_geracao, uf, cd_mun, zona, st_alterada FROM ccont WHERE urna_esperada = {cn} ORDER BY ALL")
        reg["certificado_em_ceft"] = q(f"SELECT turno, uf, cd_mun, zona, secao, urna_esperada, urna_efetivada, tp_divergencia FROM ceft WHERE urna_esperada = {cn} OR urna_efetivada = {cn}")
        reg["certificado_em_bu"] = q(f"SELECT turno, uf, cd_mun, zona, secao, tipo_urna FROM bu WHERE urna = {cn}")
        reg["certificado_em_bweb"] = q(f"SELECT turno, uf, cd_mun, zona, secao, tipo_urna FROM bweb WHERE urna = {cn}")
        reg["csec_secao"] = q(f"SELECT turno, arquivo_geracao, urna_esperada, carga_esperada, dt_carga_esperada, st_alterada FROM csec WHERE uf='{uf}' AND cd_mun='{mun}' AND zona='{zona}' AND secao='{sec}' ORDER BY ALL")
        cert.append(reg)
    r["certificados"] = cert

    # --- contagens por UF e município ---------------------------------------
    con.execute("""
        CREATE TABLE cont_uf AS
        WITH x AS (
          SELECT 'bu' AS produto, turno, uf, cd_mun FROM bu_ok
          UNION ALL SELECT 'votacao_secao', turno, uf, cd_mun FROM vs
          UNION ALL SELECT 'detalhe', turno, uf, cd_mun FROM det
          UNION ALL SELECT 'bweb', turno, uf, cd_mun FROM bweb
          UNION ALL SELECT 'corresp_efetivada', turno, uf, cd_mun FROM
                    (SELECT DISTINCT turno, uf, cd_mun, zona, secao FROM ceft)
          UNION ALL SELECT 'corresp_esperada', turno, uf, cd_mun FROM csec_ult)
        SELECT * FROM x""")
    gravar("contagens_uf", """
        PIVOT (SELECT turno, uf, produto, count() n FROM cont_uf GROUP BY ALL)
        ON produto USING sum(n) ORDER BY turno, uf""", csv=True)
    gravar("contagens_municipio_divergentes", """
        WITH p AS (PIVOT (SELECT turno, uf, cd_mun, produto, count() n FROM cont_uf GROUP BY ALL)
                   ON produto USING sum(n))
        SELECT * FROM p WHERE NOT (bu IS NOT DISTINCT FROM votacao_secao
                                   AND bu IS NOT DISTINCT FROM detalhe)
        ORDER BY turno, uf, cd_mun""", csv=True)
    r["contagens_municipio_divergentes"] = q(
        f"SELECT count() FROM read_csv('{out / 'contagens_municipio_divergentes.csv'}')")

    if a.brutos:
        b = Path(a.brutos).expanduser()
        man = [json.loads(x) for x in (b / "manifesto.jsonl").read_text().splitlines()]
        r["arquivos"] = {
            "n": len(man),
            "sha512_confere": sum(1 for m in man if m.get("sha512_confere") is True),
            "sem_sha512_publicado": [m["arquivo"] for m in man if m.get("sha512_publicado") is None],
            "nao_confere": [m["arquivo"] for m in man if m.get("sha512_confere") is False],
            "bytes": sum(m.get("tamanho", 0) for m in man),
        }
    (out / "resumo.json").write_text(json.dumps(r, ensure_ascii=False, indent=1, default=str))
    print(json.dumps(r["confrontos"]["divergencias_por_campo"], ensure_ascii=False, default=str))
    print("fim", flush=True)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("baixar")
    b.add_argument("--brutos", required=True)
    b.add_argument("--intervalo", type=float, default=INTERVALO,
                   help="segundos entre requisições (mínimo 0,34)")
    e = sub.add_parser("extrair")
    e.add_argument("--brutos", required=True)
    e.add_argument("--dir", default="/dev/shm/dados_abertos")
    e.add_argument("--threads", type=int, default=32)
    u = sub.add_parser("bu")
    u.add_argument("--dir", default="/dev/shm/dados_abertos")
    c = sub.add_parser("confrontar")
    c.add_argument("--dir", default="/dev/shm/dados_abertos")
    c.add_argument("--saida", required=True)
    c.add_argument("--brutos", default=None, help="pasta com manifesto.jsonl e ckan.json")
    c.add_argument("--software", default=None)
    c.add_argument("--threads", type=int, default=32)
    a = ap.parse_args(argv)
    {"baixar": cmd_baixar, "extrair": cmd_extrair, "bu": cmd_bu,
     "confrontar": cmd_confrontar}[a.cmd](a)


if __name__ == "__main__":
    main()
