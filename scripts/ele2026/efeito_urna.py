#!/usr/bin/env python3
"""O equipamento afeta o voto? Modelo, troca, recarga e reserva de urna (2026 e 2022).

Perguntas e desenho (todas as estimativas por mínimos quadrados ponderados com
efeitos fixos de local de votação ou de zona, erro padrão robusto por município e
IC de 95% por bootstrap de municípios, 999 réplicas):

1. Modelo de urna. Fatia do 13 e do 22 nos votos válidos, brancos e nulos sobre o
   comparecimento e abstenção, por modelo (referência UE2020), DENTRO do mesmo
   local de votação (efeito fixo uf+município+zona+local) e, para comparar com
   2022 (que não tem local na referência), dentro da mesma zona. 1º e 2º turnos
   de 2026 e os dois turnos de 2022. Também a diferença bruta, sem controle, que
   é o que a alegação de 2022 usava.
2. Experimento natural. Swing da fatia do 13 nos votos de 13+22 (2º menos 1º
   turno) nas seções que trocaram de urna, foram recarregadas, tiveram carga no
   dia 25/10, certificado diferente do número interno, carga fora do GEDAI ou
   gerador sem log publicado, contra as seções do mesmo local (ou zona) que
   mantiveram urna e carga (diferenças em diferenças com efeito fixo).
3. Urnas de contingência (reservaSecao, reservaEncerrandoSecao) e Sistema de
   Apuração (busa): nível e swing contra as demais seções do local.
4. Mesma urna física em seções diferentes no 1º e no 2º turno: o resultado do 2º
   turno da seção acompanha o eleitorado da seção ou o 1º turno da seção de onde
   veio a urna? Comparação com sorteio placebo de uma seção do mesmo local de
   origem.

Tamanho em pontos percentuais (p.p.), IC, votos equivalentes no total nacional
(efeito x votos do grupo) e impacto na margem do 2º turno (4.430.191): mover uma
fração d dos votos de 13+22 de um candidato para o outro altera a margem em
2 x d x votos.

Uso (no servidor de processamento; temporários em /dev/shm):
  python3 efeito_urna.py extrair --dir /dev/shm/efeito_urna
  uv run --with pandas,numpy,pyarrow python3 efeito_urna.py analisar \\
      --dir /dev/shm/efeito_urna \\
      --software software.parquet --certificados certificados.parquet \\
      --gedai-dir <pasta com gedai_bu_*.csv> --saida <pasta de saída>

Entradas de `analisar`:
  <dir>/t1.parquet, t2.parquet, s2022.parquet   exportados do ClickHouse
  software: data/parquet/2026/t2/software/secoes_software.parquet (modelo do .vsc,
            urna e carga do 1º e do 2º turno)
  certificados: data/parquet/2026/t2/certificados/secoes.parquet
  gedai: gedai_bu_carga_fora_gedai.csv, gedai_bu_carga_2510.csv,
         gedai_bu_gerador_sem_log.csv (data/parquet/2026/t2/linha_tempo/nacional/)
Saídas (data/parquet/2026/t2/efeito_urna/, fora do git):
  estimativas.parquet/.csv   todas as estimativas
  secoes_2026.parquet        seções pareadas 1º x 2º turno com marcadores e swing
  pequenos_grupos.csv        seção a seção dos grupos pequenos (carga 25/10, certificado)
  urna_outra_secao.parquet   urnas usadas em seção diferente entre os turnos
  grupos_concentrados.csv    swing do grupo x resto da UF e do município, 2026 e 2022
  zonas_grupos_concentrados.csv  zona a zona, posição do swing entre as zonas da UF
  resumo.json
"""

from __future__ import annotations

import os

# uma thread de álgebra linear por processo: o paralelismo é entre estimativas
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_v, "1")

import argparse
import json
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

MARGEM_T2 = 4_430_191
N_BOOT = 999
SEMENTE = 20261025
CH = os.path.expanduser("~/dataurnas-ch/app/scripts/ch/ch.sh")

SQL_T1 = """
WITH v AS (
  SELECT uf, cd_mun, zona, secao,
         sumIf(votos, tipo_voto = 'nominal' AND numero = 13) AS v13,
         sumIf(votos, tipo_voto = 'nominal' AND numero = 22) AS v22,
         sumIf(votos, tipo_voto = 'nominal' AND numero NOT IN (13, 22)) AS vout,
         sumIf(votos, tipo_voto = 'branco') AS br,
         sumIf(votos, tipo_voto = 'nulo') AS nu
  FROM ref_votos_2026_t1 GROUP BY uf, cd_mun, zona, secao)
SELECT s.uf AS uf, s.cd_mun AS cd_mun, s.zona AS zona, s.secao AS secao,
       toString(s.local_votacao) AS local, toString(s.tipo_urna) AS tipo_urna,
       toString(s.modelo_urna) AS modelo, toString(s.numero_interno_urna) AS ni,
       toString(s.codigo_carga) AS carga, s.aptos AS aptos, s.comparecimento AS comp,
       v.v13 AS v13, v.v22 AS v22, v.vout AS vout, v.br AS br, v.nu AS nu
FROM ref_secoes_2026_t1 AS s INNER JOIN v USING (uf, cd_mun, zona, secao)
FORMAT Parquet
"""

SQL_T2 = """
SELECT b.uf AS uf, b.cd_mun AS cd_mun, b.zona AS zona, b.secao AS secao,
       toString(b.tipo_arquivo) AS tipo_arquivo, toString(b.tipo_urna) AS tipo_urna,
       toString(b.local_votacao) AS local, toString(b.numero_interno_urna) AS ni,
       toString(b.codigo_carga) AS carga, b.aptos AS aptos, b.comparecimento AS comp,
       v.votos_13 AS v13, v.votos_22 AS v22, v.brancos AS br, v.nulos AS nu
FROM v_bu_ultima AS b INNER JOIN v_votos_t2_secao AS v USING (uf, cd_mun, zona, secao)
FORMAT Parquet
"""

SQL_2022 = """
WITH v AS (
  SELECT turno, uf, cd_mun, zona, secao,
         sumIf(votos, tipo_voto = 'nominal' AND numero = 13) AS v13,
         sumIf(votos, tipo_voto = 'nominal' AND numero = 22) AS v22,
         sumIf(votos, tipo_voto = 'nominal' AND numero NOT IN (13, 22)) AS vout,
         sumIf(votos, tipo_voto = 'branco') AS br,
         sumIf(votos, tipo_voto = 'nulo') AS nu
  FROM ref_votos_2022 GROUP BY turno, uf, cd_mun, zona, secao)
SELECT s.turno AS turno, s.uf AS uf, s.cd_mun AS cd_mun, s.zona AS zona, s.secao AS secao,
       toString(s.modelo_urna) AS modelo, toString(s.tipo_urna) AS tipo_urna,
       s.is_reserva AS is_reserva, s.eleitores_aptos AS aptos, s.comparecimento AS comp,
       v.v13 AS v13, v.v22 AS v22, v.vout AS vout, v.br AS br, v.nu AS nu
FROM ref_secoes_2022 AS s INNER JOIN v USING (turno, uf, cd_mun, zona, secao)
FORMAT Parquet
"""


# --------------------------------------------------------------------------- extração
def extrair(pasta: Path) -> None:
    pasta.mkdir(parents=True, exist_ok=True)
    for nome, sql in (("t1", SQL_T1), ("t2", SQL_T2), ("s2022", SQL_2022)):
        destino = pasta / f"{nome}.parquet"
        with open(destino, "wb") as saida:
            subprocess.run([CH], input=sql.encode(), stdout=saida, check=True)
        print(f"{destino}: {destino.stat().st_size:,} bytes", flush=True)


# --------------------------------------------------------------------------- estimador
_DADOS: dict = {}


def _codigos(serie):
    import pandas as pd

    return pd.factorize(serie, sort=False)[0]


def estimar(tarefa: dict) -> list[dict]:
    """MQP com efeito fixo, EP robusto por cluster e IC por bootstrap de clusters.

    tarefa: base (chave em _DADOS), filtro (coluna booleana ou None), y, w,
    regressores (colunas 0/1 já existentes), fe (coluna), cluster (coluna).
    Como cada grupo de efeito fixo fica dentro de um único município, o
    desvio da média do grupo não muda quando se reamostram municípios; basta
    reamostrar as somas X'WX e X'Wy de cada município.
    """
    import numpy as np

    df = _DADOS[tarefa["base"]]
    if tarefa.get("filtro"):
        df = df[df[tarefa["filtro"]]]
    cols = tarefa["regressores"]
    y_col, w_col = tarefa["y"], tarefa["w"]
    df = df[list(dict.fromkeys([y_col, w_col, tarefa["fe"], tarefa["cluster"], *cols]))].dropna()
    df = df[df[w_col] > 0]
    saida_base = {k: tarefa[k] for k in ("analise", "ano", "turno", "desfecho", "controle_geo", "amostra")}
    y = df[y_col].to_numpy(float)
    w = df[w_col].to_numpy(float)
    X = df[cols].to_numpy(float)
    k = len(cols)
    resultados = []
    if tarefa["fe"] == "_sem_fe":
        g = np.zeros(len(df), dtype=np.int64)
    else:
        g = _codigos(df[tarefa["fe"]])
    cl = _codigos(df[tarefa["cluster"]])
    G = cl.max() + 1
    # identificação: grupos de efeito fixo com variação em cada regressor
    ng = g.max() + 1
    cont_g = np.bincount(g, minlength=ng)
    ident = {}
    for j, c in enumerate(cols):
        s1 = np.bincount(g, weights=X[:, j], minlength=ng)
        varia = (s1 > 0) & (s1 < cont_g)
        ident[c] = (int(X[varia[g], j].sum()), int(varia.sum()))
    # desvio da média ponderada do grupo
    sw = np.bincount(g, weights=w, minlength=ng)
    sw[sw == 0] = 1.0
    yd = y - (np.bincount(g, weights=w * y, minlength=ng) / sw)[g]
    Xd = X - np.column_stack(
        [(np.bincount(g, weights=w * X[:, j], minlength=ng) / sw)[g] for j in range(k)]
    )
    # somas por cluster
    XXc = np.zeros((G, k, k))
    for a in range(k):
        for b in range(a, k):
            v = np.bincount(cl, weights=w * Xd[:, a] * Xd[:, b], minlength=G)
            XXc[:, a, b] = v
            XXc[:, b, a] = v
    Xyc = np.column_stack([np.bincount(cl, weights=w * Xd[:, a] * yd, minlength=G) for a in range(k)])
    A = XXc.sum(0)
    if np.linalg.matrix_rank(A) < k:
        return [dict(saida_base, termo=c, erro="sem variação identificável") for c in cols]
    beta = np.linalg.solve(A, Xyc.sum(0))
    e = yd - Xd @ beta
    sc = np.column_stack([np.bincount(cl, weights=w * Xd[:, a] * e, minlength=G) for a in range(k)])
    Ainv = np.linalg.inv(A)
    V = Ainv @ (sc.T @ sc) @ Ainv * (G / max(G - 1, 1))
    se = np.sqrt(np.diag(V))
    rng = np.random.default_rng(SEMENTE)
    M = rng.multinomial(G, np.full(G, 1.0 / G), size=N_BOOT).astype(float)
    XXb = (M @ XXc.reshape(G, k * k)).reshape(N_BOOT, k, k)
    Xyb = M @ Xyc
    ok = np.linalg.matrix_rank(XXb) == k
    bb = np.full((N_BOOT, k), np.nan)
    bb[ok] = np.linalg.solve(XXb[ok], Xyb[ok][..., None])[..., 0]
    for j, c in enumerate(cols):
        sel = X[:, j] == 1
        q = np.nanpercentile(bb[:, j], [2.5, 97.5])
        # denominador do grupo: soma dos pesos (votos do desfecho) nas seções tratadas
        votos_grupo = float(w[sel].sum())
        resultados.append(
            dict(
                saida_base,
                termo=c,
                n_obs=int(len(df)),
                n_grupo=int(sel.sum()),
                n_grupo_identificado=ident[c][0],
                grupos_fe_com_variacao=ident[c][1],
                municipios=int(G),
                media_grupo=float(np.average(y[sel], weights=w[sel])) if sel.any() else None,
                media_resto=float(np.average(y[~sel], weights=w[~sel])) if (~sel).any() else None,
                efeito_pp=float(beta[j] * 100),
                ep_pp=float(se[j] * 100),
                z=float(beta[j] / se[j]) if se[j] > 0 else None,
                ic_boot_inf_pp=float(q[0] * 100),
                ic_boot_sup_pp=float(q[1] * 100),
                ic_robusto_inf_pp=float((beta[j] - 1.96 * se[j]) * 100),
                ic_robusto_sup_pp=float((beta[j] + 1.96 * se[j]) * 100),
                votos_base_grupo=votos_grupo,
                votos_equivalentes=float(beta[j] * votos_grupo),
                votos_equiv_ic_max=float(max(abs(q[0]), abs(q[1])) * votos_grupo),
                impacto_margem=float(2 * beta[j] * votos_grupo),
                impacto_margem_ic_max=float(2 * max(abs(q[0]), abs(q[1])) * votos_grupo),
            )
        )
    return resultados


# --------------------------------------------------------------------------- preparo
MODELOS_26 = ["UE2013", "UE2015", "UE2022"]  # referência UE2020
MODELOS_22 = ["2009", "2010", "2011", "2013", "2015"]  # referência 2020


def desfechos(df, sufixo: str = "", dois_candidatos: bool = False):
    """Acrescenta fatias. validos = nominais (13+22 no 2º turno)."""
    s = sufixo
    validos = df[f"v13{s}"] + df[f"v22{s}"] + (0 if dois_candidatos else df[f"vout{s}"])
    df[f"validos{s}"] = validos
    df[f"dois{s}"] = df[f"v13{s}"] + df[f"v22{s}"]
    df[f"f13{s}"] = df[f"v13{s}"] / validos.where(validos > 0)
    df[f"f22{s}"] = df[f"v22{s}"] / validos.where(validos > 0)
    df[f"f13_2p{s}"] = df[f"v13{s}"] / df[f"dois{s}"].where(df[f"dois{s}"] > 0)
    comp = df[f"comp{s}"].where(df[f"comp{s}"] > 0)
    df[f"fbr{s}"] = df[f"br{s}"] / comp
    df[f"fnu{s}"] = df[f"nu{s}"] / comp
    df[f"fabst{s}"] = 1 - df[f"comp{s}"] / df[f"aptos{s}"].where(df[f"aptos{s}"] > 0)
    return df


def ler_csv_gedai(pasta: Path, nome: str):
    import pandas as pd

    d = pd.read_csv(pasta / nome, dtype=str)
    d["cd_mun"] = d["cd_mun"].str.zfill(5)
    d["zona"] = d["zona"].str.zfill(4)
    d["secao"] = d["secao"].str.zfill(4)
    return d


def preparar(args):
    import numpy as np
    import pandas as pd

    pasta = Path(args.dir)
    chave = ["uf", "cd_mun", "zona", "secao"]
    t1 = pd.read_parquet(pasta / "t1.parquet")
    t2 = pd.read_parquet(pasta / "t2.parquet")
    for d in (t1, t2):
        for c in ("local", "ni", "carga", "tipo_urna", "modelo"):
            if c in d:
                d[c] = d[c].replace({"\\N": None, "": None, "None": None})
    sw = pd.read_parquet(
        args.software,
        columns=chave + ["modelo_vsc", "t1_modelo_urna", "mesma_urna_t1", "numero_interno_urna", "t1_numero_interno_urna"],
    )
    cert = pd.read_parquet(args.certificados, columns=chave + ["data_hora_carga", "cn_igual_numero_interno", "modelo"])
    t1 = desfechos(t1)
    t2 = desfechos(t2, dois_candidatos=True)
    t1 = t1.rename(columns={c: f"{c}_t1" for c in t1.columns if c not in chave})
    t2 = t2.rename(columns={c: f"{c}_t2" for c in t2.columns if c not in chave})
    df = t2.merge(t1, on=chave, how="left").merge(sw, on=chave, how="left").merge(
        cert.rename(columns={"modelo": "modelo_cert"}), on=chave, how="left"
    )
    df["modelo_t2"] = df["modelo_vsc"].fillna(df["modelo_cert"])
    df["mun"] = df["uf"] + df["cd_mun"]
    df["zona_fe"] = df["mun"] + "|" + df["zona"]
    loc2 = df["local_t2"].fillna(df["local_t1"])
    df["local_fe_t2"] = np.where(loc2.notna(), df["zona_fe"] + "|" + loc2.astype(str), df["zona_fe"] + "|s" + df["secao"])
    df["tem_t1"] = df["v13_t1"].notna()
    # marcadores
    df["mesma_urna"] = (df["ni_t2"] == df["ni_t1"]) & df["ni_t1"].notna()
    df["mesma_carga"] = df["carga_t2"] == df["carga_t1"]
    df["urna_t2"] = df["tipo_arquivo_t2"] == "bu"
    df["trocou_urna"] = df["urna_t2"] & df["tem_t1"] & ~df["mesma_urna"] & df["ni_t1"].notna()
    df["trocou_urna_secao"] = df["trocou_urna"] & (df["tipo_urna_t2"] == "secao")
    df["trocou_urna_reserva"] = df["trocou_urna"] & (df["tipo_urna_t2"] != "secao")
    df["reserva_t2"] = df["urna_t2"] & df["tipo_urna_t2"].isin(["reservaSecao", "reservaEncerrandoSecao"])
    df["reserva_t1"] = df["tipo_urna_t1"].isin(["reservaSecao", "reservaEncerrandoSecao"])
    df["recarregada"] = df["mesma_urna"] & ~df["mesma_carga"]
    df["busa"] = df["tipo_arquivo_t2"] == "busa"
    fora = ler_csv_gedai(Path(args.gedai_dir), "gedai_bu_carga_fora_gedai.csv")
    c2510 = ler_csv_gedai(Path(args.gedai_dir), "gedai_bu_carga_2510.csv")
    semlog = ler_csv_gedai(Path(args.gedai_dir), "gedai_bu_gerador_sem_log.csv")
    idx = df.set_index(chave).index
    df["carga_fora_gedai"] = idx.isin(fora.set_index(chave).index)
    df["carga_2510"] = idx.isin(c2510.set_index(chave).index)
    df["gerador_sem_log"] = idx.isin(semlog.set_index(chave).index)
    df["cert_divergente"] = df["cn_igual_numero_interno"].fillna(True).astype(str).isin(["False", "false", "0"])
    # subgrupos da carga fora do GEDAI pelas estações citadas
    m = df["carga_fora_gedai"]
    df["fora_parauapebas"] = m & (df["uf"] == "pa") & (df["zona"] == "0106")
    df["fora_monte_alegre"] = m & (df["uf"] == "pa") & (df["cd_mun"] == "04952")
    df["fora_guarulhos"] = m & (df["uf"] == "sp") & (df["zona"] == "0176")
    df["fora_mg_0339"] = m & (df["uf"] == "mg") & (df["zona"] == "0339")
    df["fora_outras"] = m & ~(df["fora_parauapebas"] | df["fora_monte_alegre"] | df["fora_guarulhos"] | df["fora_mg_0339"])
    sinal = ["trocou_urna", "recarregada", "reserva_t2", "reserva_t1", "busa", "carga_fora_gedai", "carga_2510", "gerador_sem_log", "cert_divergente"]
    df["estavel"] = df["urna_t2"] & df["tem_t1"] & df["mesma_urna"] & df["mesma_carga"] & ~df[sinal].any(axis=1) & (df["tipo_urna_t2"] == "secao")
    df["swing13"] = df["f13_2p_t2"] - df["f13_2p_t1"]
    df["swing_bn"] = (df["fbr_t2"] + df["fnu_t2"]) - (df["fbr_t1"] + df["fnu_t1"])
    df["swing_abst"] = df["fabst_t2"] - df["fabst_t1"]
    for mod in MODELOS_26:
        df[f"m_{mod}"] = (df["modelo_t2"] == mod).astype(float)
        df[f"m1_{mod}"] = (df["modelo_t1"] == mod).astype(float)
    df.loc[df["modelo_t2"].isna(), [f"m_{m}" for m in MODELOS_26]] = np.nan
    df.loc[df["modelo_t1"].isna(), [f"m1_{m}" for m in MODELOS_26]] = np.nan
    df["d_reserva_t2"] = df["reserva_t2"].astype(float)
    df["d_reserva_t1"] = df["reserva_t1"].astype(float)
    df["d_busa"] = df["busa"].astype(float)

    # 1º turno completo (inclui seções sem 2º turno pareado)
    t1c = pd.read_parquet(pasta / "t1.parquet")
    t1c = desfechos(t1c)
    t1c["mun"] = t1c["uf"] + t1c["cd_mun"]
    t1c["zona_fe"] = t1c["mun"] + "|" + t1c["zona"]
    t1c["local_fe"] = np.where(t1c["local"].notna(), t1c["zona_fe"] + "|" + t1c["local"].astype(str), t1c["zona_fe"] + "|s" + t1c["secao"])
    for mod in MODELOS_26:
        t1c[f"m1_{mod}"] = np.where(t1c["modelo"].notna(), (t1c["modelo"] == mod).astype(float), np.nan)
    t1c["d_reserva_t1"] = t1c["tipo_urna"].isin(["reservaSecao", "reservaEncerrandoSecao"]).astype(float)

    s22 = pd.read_parquet(pasta / "s2022.parquet")
    s22 = desfechos(s22)
    s22["mun"] = s22["uf"] + s22["cd_mun"].astype(str).str.zfill(5)
    s22["zona_fe"] = s22["mun"] + "|" + s22["zona"].astype(str).str.zfill(4)
    for mod in MODELOS_22:
        s22[f"m22_{mod}"] = (s22["modelo"] == mod).astype(float)
    s22["d_reserva"] = s22["is_reserva"].astype(float)

    # mesma seção (uf, município, zona, seção) em 2022: placebo do eleitorado.
    # A referência de 2022 não tem local de votação; usa-se o local de 2026 da
    # mesma seção (a seção pode ter mudado de prédio, o que só dilui o controle).
    s22k = s22.copy()
    s22k["cd_mun"] = s22k["cd_mun"].astype(str).str.zfill(5)
    s22k["zona"] = s22k["zona"].astype(str).str.zfill(4)
    s22k["secao"] = s22k["secao"].astype(str).str.zfill(4)
    for turno in (1, 2):
        p = s22k[s22k["turno"] == turno][chave + ["f13", "f13_2p", "dois", "validos", "modelo", "is_reserva"]]
        p = p.rename(columns={c: f"{c}_22t{turno}" for c in p.columns if c not in chave})
        df = df.merge(p, on=chave, how="left")
    for mod in MODELOS_22:
        df[f"m22_{mod}"] = np.where(df["modelo_22t2"].notna(), (df["modelo_22t2"] == mod).astype(float), np.nan)
    df["d_reserva_22t2"] = df["is_reserva_22t2"].astype(float)
    df["swing_22_26"] = df["f13_2p_t2"] - df["f13_2p_22t2"]
    df["swing22"] = df["f13_2p_22t2"] - df["f13_2p_22t1"]
    df["tem_22"] = df["f13_2p_22t2"].notna()
    return df, t1c, s22


# --------------------------------------------------------------------------- urna em outra seção
def urna_outra_secao(df):
    """Seções do 2º turno cuja urna votou em OUTRA seção no 1º turno."""
    import numpy as np

    rng = np.random.default_rng(SEMENTE)
    base = df[df["tem_t1"] & df["ni_t1"].notna()]
    mapa = base.drop_duplicates("ni_t1").set_index("ni_t1")
    cand = df[df["trocou_urna"] & df["ni_t2"].isin(mapa.index)].copy()
    o = mapa.loc[cand["ni_t2"]]
    cand["orig_uf"] = o["uf"].to_numpy()
    cand["orig_cd_mun"] = o["cd_mun"].to_numpy()
    cand["orig_zona"] = o["zona"].to_numpy()
    cand["orig_secao"] = o["secao"].to_numpy()
    cand["orig_local_fe"] = o["local_fe_t2"].to_numpy()
    cand["orig_f13_2p_t1"] = o["f13_2p_t1"].to_numpy()
    cand["orig_f13_2p_t2"] = o["f13_2p_t2"].to_numpy()
    cand["mesmo_local"] = cand["orig_local_fe"] == cand["local_fe_t2"]
    cand["mesma_zona"] = (cand["orig_uf"] == cand["uf"]) & (cand["orig_cd_mun"] == cand["cd_mun"]) & (cand["orig_zona"] == cand["zona"])
    # placebo: outra seção sorteada no mesmo local da seção de origem
    por_local = base.groupby("local_fe_t2")["f13_2p_t1"].apply(lambda s: s.to_numpy())
    plac = []
    for loc, orig_val in zip(cand["orig_local_fe"], cand["orig_f13_2p_t1"], strict=True):
        arr = por_local.get(loc)
        if arr is None or len(arr) < 2:
            plac.append(np.nan)
            continue
        # sorteia até achar valor de outra seção (evita a própria origem)
        for _ in range(5):
            v = arr[rng.integers(len(arr))]
            if v != orig_val:
                break
        plac.append(v)
    cand["placebo_f13_2p_t1"] = plac
    c = cand.dropna(subset=["f13_2p_t2", "f13_2p_t1", "orig_f13_2p_t1"])
    d_propria = (c["f13_2p_t2"] - c["f13_2p_t1"]).abs()
    d_origem = (c["f13_2p_t2"] - c["orig_f13_2p_t1"]).abs()
    cp = c.dropna(subset=["placebo_f13_2p_t1"])
    d_plac = (cp["f13_2p_t2"] - cp["placebo_f13_2p_t1"]).abs()
    d_orig_p = (cp["f13_2p_t2"] - cp["orig_f13_2p_t1"]).abs()

    # regressão: f13_t2(S) = a + b f13_t1(S) + c f13_t1(origem) [+ placebo], MQO simples
    def mqo(y, X):
        X = np.column_stack([np.ones(len(y)), X])
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
        e = y - X @ beta
        V = np.linalg.inv(X.T @ X) * (e @ e) / (len(y) - X.shape[1])
        return beta, np.sqrt(np.diag(V))

    fora_local = cp[~cp["mesmo_local"]]
    reg = {}
    for nome, sub in (("todas", cp), ("origem_em_outro_local", fora_local)):
        if len(sub) < 30:
            continue
        b, se = mqo(sub["f13_2p_t2"].to_numpy(), sub[["f13_2p_t1", "orig_f13_2p_t1", "placebo_f13_2p_t1"]].to_numpy())
        reg[nome] = dict(
            n=int(len(sub)),
            coef_propria_t1=float(b[1]), ep_propria=float(se[1]),
            coef_origem_t1=float(b[2]), ep_origem=float(se[2]),
            coef_placebo_t1=float(b[3]), ep_placebo=float(se[3]),
        )
    res = dict(
        secoes_com_urna_de_outra_secao=int(len(cand)),
        com_votos_comparaveis=int(len(c)),
        origem_mesmo_local=int(c["mesmo_local"].sum()),
        origem_mesma_zona=int(c["mesma_zona"].sum()),
        origem_outro_municipio=int(((c["orig_uf"] != c["uf"]) | (c["orig_cd_mun"] != c["cd_mun"])).sum()),
        mediana_dist_propria_t1_pp=float(d_propria.median() * 100),
        mediana_dist_origem_t1_pp=float(d_origem.median() * 100),
        frac_mais_perto_da_origem=float((d_origem < d_propria).mean()),
        frac_mais_perto_da_origem_que_placebo=float((d_orig_p < d_plac).mean()),
        frac_placebo_mais_perto=float((d_plac < d_orig_p).mean()),
        n_placebo=int(len(cp)),
        regressao=reg,
    )
    return cand, res


# --------------------------------------------------------------------------- grupos concentrados
def ranking_zonas(df, grupos):
    """Grupos concentrados em poucas zonas (zona inteira tratada, sem vizinho de
    controle no local): compara o swing da zona com o de todas as zonas da UF, em
    2026 e, para as mesmas seções, em 2022 (1º para 2º turno). Se a zona já se
    desviava em 2022, o desvio é regional e não do equipamento de 2026."""
    import numpy as np
    import pandas as pd

    base = df[(df["urna_t2"] | df["busa"]) & df["swing13"].notna() & (df["dois_t2"] > 0)].copy()
    base["_w26"] = base["dois_t2"]
    base["_w22"] = base["dois_22t2"].where(base["swing22"].notna(), 0).fillna(0)

    def agrega(g):
        w26, w22 = g["_w26"].to_numpy(), g["_w22"].to_numpy()
        return pd.Series({
            "secoes": len(g),
            "swing26": np.average(g["swing13"], weights=w26),
            "swing22": np.average(g["swing22"].fillna(0), weights=w22) if w22.sum() > 0 else np.nan,
            "votos_2p_t2": w26.sum(),
        })

    zonas = base.groupby(["uf", "zona_fe"]).apply(agrega).reset_index()
    for ano in ("26", "22"):
        zonas[f"pct_uf_{ano}"] = zonas.groupby("uf")[f"swing{ano}"].rank(pct=True)
        m = zonas.groupby("uf")[f"swing{ano}"].transform("mean")
        sd = zonas.groupby("uf")[f"swing{ano}"].transform("std")
        zonas[f"z_uf_{ano}"] = (zonas[f"swing{ano}"] - m) / sd
    linhas_z, linhas_g = [], []
    for gr in grupos:
        T = base[base[gr]]
        if T.empty:
            continue
        zs = T["zona_fe"].unique()
        tz = T.groupby("zona_fe").size()
        for z in zs:
            r = zonas[zonas["zona_fe"] == z].iloc[0].to_dict()
            r.update(grupo=gr, secoes_tratadas_na_zona=int(tz[z]), zonas_na_uf=int((zonas["uf"] == r["uf"]).sum()))
            linhas_z.append(r)
        ufs = T["uf"].unique()
        resto = base[base["uf"].isin(ufs) & ~base["zona_fe"].isin(zs)]
        resto_mun = base[base["mun"].isin(T["mun"].unique()) & ~base[gr]]

        def wm(d, y, w):
            ok = d[y].notna() & (d[w] > 0)
            return float(np.average(d.loc[ok, y], weights=d.loc[ok, w])) if ok.any() else np.nan

        t26, r26, m26 = wm(T, "swing13", "_w26"), wm(resto, "swing13", "_w26"), wm(resto_mun, "swing13", "_w26")
        t22, r22 = wm(T, "swing22", "_w22"), wm(resto, "swing22", "_w22")
        v = float(T["_w26"].sum())
        # permutação: n seções sorteadas do município (sem tratadas) ou, se o
        # município inteiro é tratado, da UF. Ignora a correlação espacial (as
        # tratadas são vizinhas), logo o p é otimista: serve de limite inferior.
        pool = resto_mun if len(resto_mun) >= 3 * len(T) else base[base["uf"].isin(ufs) & ~base[gr]]
        rng = np.random.default_rng(SEMENTE)
        ps, pw = pool["swing13"].to_numpy(), pool["_w26"].to_numpy()
        idx = rng.integers(0, len(ps), size=(4999, len(T)))
        sim = (ps[idx] * pw[idx]).sum(1) / pw[idx].sum(1)
        ref = float(np.average(ps, weights=pw))
        p_perm = float((np.abs(sim - ref) >= abs(t26 - ref)).mean())
        linhas_g.append(dict(
            pool_permutacao="município" if pool is resto_mun else "UF", p_permutacao=p_perm,
            grupo=gr, secoes=int(len(T)), zonas=int(len(zs)), ufs=",".join(sorted(ufs)),
            swing26_grupo_pp=t26 * 100, swing26_resto_uf_pp=r26 * 100, swing26_resto_municipio_pp=m26 * 100,
            dif26_vs_uf_pp=(t26 - r26) * 100, dif26_vs_municipio_pp=(t26 - m26) * 100,
            swing22_mesmas_secoes_pp=t22 * 100, swing22_resto_uf_pp=r22 * 100, dif22_vs_uf_pp=(t22 - r22) * 100,
            dif_em_dif_26_menos_22_pp=((t26 - r26) - (t22 - r22)) * 100,
            votos_2p_t2=v, votos_equivalentes_vs_uf=(t26 - r26) * v,
            impacto_margem_vs_uf=2 * (t26 - r26) * v,
        ))
    return pd.DataFrame(linhas_z), pd.DataFrame(linhas_g)


# --------------------------------------------------------------------------- análise
def analisar(args):
    import numpy as np
    import pandas as pd

    saida = Path(args.saida)
    saida.mkdir(parents=True, exist_ok=True)
    df, t1c, s22 = preparar(args)
    _DADOS["t2"] = df
    _DADOS["t1"] = t1c
    _DADOS["s22"] = s22
    for base in (df, t1c, s22):
        base["_sem_fe"] = "0"
    df["f_urna_t2"] = df["urna_t2"]
    df["f_urna_t1t2"] = df["urna_t2"] & df["tem_t1"]
    t1c["f_urna_t1"] = t1c["tipo_urna"].isin(["secao", "reservaSecao", "reservaEncerrandoSecao"])
    s22["f_t1"] = s22["turno"] == 1
    s22["f_t2"] = s22["turno"] == 2
    tarefas = []
    meta = dict(analise=None, ano=None, turno=None, desfecho=None, controle_geo=None, amostra=None)

    def tf(**kw):
        t = dict(meta)
        t.update(kw)
        t.setdefault("cluster", "mun")
        tarefas.append(t)

    # 1) modelo de urna
    desf_t2 = [("f13_t2", "validos_t2", "fatia 13 nos válidos"), ("fbr_t2", "comp_t2", "brancos/comparecimento"),
               ("fnu_t2", "comp_t2", "nulos/comparecimento"), ("fabst_t2", "aptos_t2", "abstenção")]
    desf_t1 = [("f13", "validos", "fatia 13 nos válidos"), ("f22", "validos", "fatia 22 nos válidos"),
               ("fbr", "comp", "brancos/comparecimento"), ("fnu", "comp", "nulos/comparecimento"),
               ("fabst", "aptos", "abstenção")]
    regs_t2 = [f"m_{m}" for m in MODELOS_26] + ["d_reserva_t2"]
    regs_t1 = [f"m1_{m}" for m in MODELOS_26] + ["d_reserva_t1"]
    for fe, nome_fe in (("local_fe_t2", "local"), ("zona_fe", "zona"), ("_sem_fe", "nenhum")):
        for y, w, nome in desf_t2:
            tf(analise="modelo", ano=2026, turno=2, desfecho=nome, controle_geo=nome_fe, amostra="BU de urna",
               base="t2", filtro="f_urna_t2", y=y, w=w, regressores=regs_t2, fe=fe)
    fe_t1 = {"local": "local_fe", "zona": "zona_fe", "nenhum": "_sem_fe"}
    for nome_fe, fe in fe_t1.items():
        for y, w, nome in desf_t1:
            tf(analise="modelo", ano=2026, turno=1, desfecho=nome, controle_geo=nome_fe, amostra="BU de urna",
               base="t1", filtro="f_urna_t1", y=y, w=w, regressores=regs_t1, fe=fe)
    regs_22 = [f"m22_{m}" for m in MODELOS_22] + ["d_reserva"]
    for turno in (1, 2):
        for fe, nome_fe in (("zona_fe", "zona"), ("_sem_fe", "nenhum")):
            for y, w, nome in desf_t1:
                tf(analise="modelo", ano=2022, turno=turno, desfecho=nome, controle_geo=nome_fe, amostra="todas",
                   base="s22", filtro=f"f_t{turno}", y=y, w=w, regressores=regs_22, fe=fe)
    # mesmo modelo nos dois turnos e swing por modelo (efeito do modelo sobre a mudança)
    for fe, nome_fe in (("local_fe_t2", "local"), ("zona_fe", "zona")):
        tf(analise="modelo_swing", ano=2026, turno=0, desfecho="swing fatia 13 (13+22)", controle_geo=nome_fe,
           amostra="seções estáveis", base="t2", filtro="estavel", y="swing13", w="dois_t2",
           regressores=[f"m_{m}" for m in MODELOS_26], fe=fe)

    # placebo do eleitorado: as seções que em 2026 receberam cada modelo já votavam
    # diferente em 2022 (com outra urna)? E o modelo de 2022 dentro do local de 2026.
    df["f_22"] = df["f_urna_t2"] & df["tem_22"]
    for fe, nome_fe in (("local_fe_t2", "local"), ("zona_fe", "zona")):
        tf(analise="modelo_placebo_2022", ano=2022, turno=2, desfecho="fatia 13 (13+22) em 2022 por modelo de 2026",
           controle_geo=nome_fe, amostra="seções presentes nos dois anos", base="t2", filtro="f_22",
           y="f13_2p_22t2", w="dois_22t2", regressores=[f"m_{m}" for m in MODELOS_26], fe=fe)
        tf(analise="modelo_2022_local", ano=2022, turno=2, desfecho="fatia 13 (13+22) em 2022 por modelo de 2022",
           controle_geo=nome_fe, amostra="seções presentes nos dois anos", base="t2", filtro="f_22",
           y="f13_2p_22t2", w="dois_22t2", regressores=[f"m22_{m}" for m in MODELOS_22] + ["d_reserva_22t2"], fe=fe)
        tf(analise="modelo_2026_mesma_amostra", ano=2026, turno=2, desfecho="fatia 13 (13+22) em 2026 por modelo de 2026",
           controle_geo=nome_fe, amostra="seções presentes nos dois anos", base="t2", filtro="f_22",
           y="f13_2p_t2", w="dois_t2", regressores=[f"m_{m}" for m in MODELOS_26], fe=fe)
        tf(analise="modelo_swing_2022_2026", ano=2026, turno=2, desfecho="swing fatia 13 (13+22) 2º turno 2022 para 2026",
           controle_geo=nome_fe, amostra="seções presentes nos dois anos", base="t2", filtro="f_22",
           y="swing_22_26", w="dois_t2", regressores=[f"m_{m}" for m in MODELOS_26], fe=fe)

    # 2) e 3) diferenças em diferenças
    tratamentos = ["trocou_urna_secao", "trocou_urna_reserva", "recarregada", "reserva_t2", "reserva_t1", "busa",
                   "carga_fora_gedai", "fora_parauapebas", "fora_guarulhos", "fora_mg_0339", "fora_monte_alegre",
                   "fora_outras", "gerador_sem_log", "carga_2510", "cert_divergente"]
    for tr in tratamentos:
        col_f = f"amostra_{tr}"
        df[col_f] = df["tem_t1"] & (df["estavel"] | df[tr])
        df[f"d_{tr}"] = df[tr].astype(float)
        for y, w, nome in (("swing13", "dois_t2", "swing fatia 13 (13+22)"),
                           ("swing_bn", "comp_t2", "swing brancos+nulos"),
                           ("f13_2p_t2", "dois_t2", "nível fatia 13 no 2º turno")):
            for fe, nome_fe in (("local_fe_t2", "local"), ("zona_fe", "zona"), ("mun", "município"), ("uf", "UF")):
                tf(analise="tratamento", ano=2026, turno=2, desfecho=nome, controle_geo=nome_fe,
                   amostra=f"estáveis + {tr}", base="t2", filtro=col_f, y=y, w=w,
                   regressores=[f"d_{tr}"], fe=fe)
    # 2022: reserva em cada turno já coberta pelo regressor d_reserva nas regressões de modelo

    # executa em paralelo (os dados são herdados pelo fork)
    import multiprocessing as mp

    ctx = mp.get_context("fork")
    with ProcessPoolExecutor(max_workers=min(args.workers, len(tarefas)), mp_context=ctx) as ex:
        res = [r for lote in ex.map(estimar, tarefas, chunksize=1) for r in lote]
    est = pd.DataFrame(res)
    est.to_parquet(saida / "estimativas.parquet", index=False)
    est.to_csv(saida / "estimativas.csv", index=False)

    # grupos pequenos: seção a seção contra o local
    loc_est = df[df["estavel"]].groupby("local_fe_t2").apply(
        lambda g: pd.Series({"media_local": np.average(g["swing13"].dropna(), weights=g.loc[g["swing13"].notna(), "dois_t2"]) if g["swing13"].notna().any() else np.nan,
                             "dp_local": g["swing13"].std(), "n_local": g["swing13"].notna().sum()})
    )
    zona_est = df[df["estavel"]].groupby("zona_fe")["swing13"].agg(["mean", "std", "count"])
    peq = df[df["carga_2510"] | df["cert_divergente"] | df["busa"]].copy()
    peq = peq.join(loc_est, on="local_fe_t2").join(zona_est.rename(columns={"mean": "media_zona", "std": "dp_zona", "count": "n_zona"}), on="zona_fe")
    peq["z_local"] = (peq["swing13"] - peq["media_local"]) / peq["dp_local"]
    peq["z_zona"] = (peq["swing13"] - peq["media_zona"]) / peq["dp_zona"]
    cols_peq = ["uf", "cd_mun", "zona", "secao", "carga_2510", "cert_divergente", "busa", "tipo_urna_t1", "tipo_urna_t2",
                "modelo_t1", "modelo_t2", "ni_t1", "ni_t2", "data_hora_carga", "v13_t1", "v22_t1", "v13_t2", "v22_t2",
                "f13_2p_t1", "f13_2p_t2", "swing13", "media_local", "dp_local", "n_local", "z_local", "media_zona",
                "dp_zona", "n_zona", "z_zona"]
    peq[cols_peq].to_csv(saida / "pequenos_grupos.csv", index=False)

    # resíduo de swing contra o local: distribuição nas estáveis x grupos
    df = df.join(loc_est, on="local_fe_t2")
    df["resid_swing_local"] = df["swing13"] - df["media_local"]
    cauda = {}
    for tr in ["estavel", *tratamentos]:
        r = df.loc[df[tr], "resid_swing_local"].dropna()
        cauda[tr] = dict(n=int(len(r)), media_pp=float(r.mean() * 100) if len(r) else None,
                         frac_abs_maior_10pp=float((r.abs() > 0.10).mean()) if len(r) else None)
    cauda["_obs"] = "estáveis incluem a própria seção na média do local; serve só de régua de dispersão"

    rk_sec, rk_grp = ranking_zonas(df, ["carga_fora_gedai", "fora_parauapebas", "fora_guarulhos", "fora_mg_0339",
                                        "fora_monte_alegre", "fora_outras", "gerador_sem_log", "busa",
                                        "carga_2510", "cert_divergente", "recarregada"])
    rk_sec.to_csv(saida / "zonas_grupos_concentrados.csv", index=False)
    rk_grp.to_csv(saida / "grupos_concentrados.csv", index=False)
    cand, res_outra = urna_outra_secao(df)
    cand.to_parquet(saida / "urna_outra_secao.parquet", index=False)
    manter = ["uf", "cd_mun", "zona", "secao", "local_fe_t2", "tipo_arquivo_t2", "tipo_urna_t1", "tipo_urna_t2",
              "modelo_t1", "modelo_t2", "ni_t1", "ni_t2", "carga_t1", "carga_t2", "data_hora_carga",
              "v13_t1", "v22_t1", "vout_t1", "br_t1", "nu_t1", "comp_t1", "aptos_t1",
              "v13_t2", "v22_t2", "br_t2", "nu_t2", "comp_t2", "aptos_t2", "f13_2p_t1", "f13_2p_t2",
              "swing13", "swing_bn", "estavel", *tratamentos, "resid_swing_local",
              "modelo_22t2", "f13_2p_22t2", "dois_22t2", "swing_22_26"]
    df[manter].to_parquet(saida / "secoes_2026.parquet", index=False)

    contagens = {c: int(df[c].sum()) for c in ["estavel", "trocou_urna", *tratamentos, "mesma_urna", "tem_t1", "urna_t2"]}
    contagens["secoes_t2"] = int(len(df))
    contagens["secoes_com_2022"] = int(df["tem_22"].sum())
    contagens["modelo_t2"] = df["modelo_t2"].value_counts(dropna=False).to_dict()
    contagens["modelo_t1"] = t1c["modelo"].value_counts(dropna=False).to_dict()
    contagens["modelo_t1_x_t2_mesma_urna"] = int((df["mesma_urna"] & (df["modelo_t1"] == df["modelo_t2"])).sum())
    contagens["modelo_t1_dif_t2_mesma_urna"] = int((df["mesma_urna"] & df["modelo_t1"].notna() & df["modelo_t2"].notna() & (df["modelo_t1"] != df["modelo_t2"])).sum())
    contagens["locais_t2"] = int(df["local_fe_t2"].nunique())
    contagens["locais_com_mais_de_um_modelo_t2"] = int((df.groupby("local_fe_t2")["modelo_t2"].nunique() > 1).sum())
    contagens["secoes_em_locais_mistos_t2"] = int(df["local_fe_t2"].map(df.groupby("local_fe_t2")["modelo_t2"].nunique()).gt(1).sum())
    tot = dict(v13=int(df["v13_t2"].sum()), v22=int(df["v22_t2"].sum()))
    tot["margem"] = tot["v13"] - tot["v22"]
    resumo = dict(contagens=contagens, totais_t2=tot, margem_referencia=MARGEM_T2, n_boot=N_BOOT,
                  semente=SEMENTE, cauda_residuo=cauda, urna_outra_secao=res_outra,
                  grupos_concentrados=rk_grp.to_dict(orient="records"),
                  n_estimativas=int(len(est)))
    (saida / "resumo.json").write_text(json.dumps(resumo, ensure_ascii=False, indent=1, default=str))
    print(json.dumps(resumo, ensure_ascii=False, indent=1, default=str)[:6000])


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("extrair")
    e.add_argument("--dir", default="/dev/shm/efeito_urna")
    a = sub.add_parser("analisar")
    a.add_argument("--dir", default="/dev/shm/efeito_urna")
    a.add_argument("--software", default="data/parquet/2026/t2/software/secoes_software.parquet")
    a.add_argument("--certificados", default="data/parquet/2026/t2/certificados/secoes.parquet")
    a.add_argument("--gedai-dir", default="data/parquet/2026/t2/linha_tempo/nacional")
    a.add_argument("--saida", default="data/parquet/2026/t2/efeito_urna")
    a.add_argument("--workers", type=int, default=48)
    args = p.parse_args(argv)
    if args.cmd == "extrair":
        extrair(Path(args.dir))
    else:
        analisar(args)


if __name__ == "__main__":
    sys.exit(main())
