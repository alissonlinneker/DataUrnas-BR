#!/usr/bin/env python3
"""Forense estatística por seção: 1º e 2º turno de 2026, com 2022 como controle.

Seis frentes, todas aplicadas com a mesma régua a 2022 (1º e 2º turno) e a 2026:

1. Impressão digital eleitoral (Klimek et al., 2012): histograma 2D de
   comparecimento x fatia do vencedor por seção, massa no canto de
   comparecimento e fatia altos, inclinação da fatia sobre o comparecimento dentro
   do município (o sinal de enchimento de urna), por UF.
2. Dígitos: último dígito (uniforme) e 2º dígito de Benford (2BL, Mebane) dos
   votos de 13 e de 22 por seção, com teste qui-quadrado, tamanho de efeito (MAD)
   e uma referência simulada (binomial com a fatia do município) que mostra quanto
   do desvio é efeito do próprio tamanho das seções; por UF e por modelo de urna.
3. Swing do 1º para o 2º turno: fatia do 13 no 2º turno por seção modelada a
   partir do 1º turno (fatia do 13, votos de cada candidato, brancos, nulos e
   abstenção) com efeito fixo de município; resíduos padronizados, cauda e
   aglomerados (local de votação, zona e município).
4. Transferência: regressão ecológica de Goodman (votos do 2º turno sobre a
   composição do 1º) e perda absoluta incomum do candidato que perdeu terreno.
5. Dispersão: heterogeneidade binomial da fatia entre seções do mesmo local de
   votação, da mesma zona e do mesmo município; seções "uniformes demais"
   (subdispersão) e resultados repetidos.
6. Comparecimento: aumento de comparecimento acima do município e ganho
   concentrado num candidato.

Uso, no servidor de processamento (dados em memória, /dev/shm):

    # exporta os quatro conjuntos do ClickHouse (uma vez)
    python3 scripts/ele2026/forense_estatistica.py exportar --dir /dev/shm/forense/dados
    # análise completa (cerca de 4 min com 48 processos)
    uv run --with pandas,numpy,scipy,pyarrow,matplotlib \
        python scripts/ele2026/forense_estatistica.py analisar \
        --dados /dev/shm/forense/dados --saida /dev/shm/forense/saida --sims 960

Saída (copiada para data/parquet/2026/t2/forense/, fora do git): resumo.json com
todas as métricas, tabelas por UF e por modelo em Parquet e CSV, lista de seções e
aglomerados atípicos e as figuras em PNG.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

CH = os.path.expanduser("~/dataurnas-ch/app/scripts/ch/ch.sh")

# Candidatos com mais votos no 1º turno, além de 13 e 22 (os demais vão para "or").
OUTROS = {2026: (70, 14, 55), 2022: (15, 12, 44)}
VENCEDOR = {(2022, 1): 13, (2022, 2): 13, (2026, 1): 22, (2026, 2): 13}
REGIAO = {
    "ac": "N", "am": "N", "ap": "N", "pa": "N", "ro": "N", "rr": "N", "to": "N",
    "al": "NE", "ba": "NE", "ce": "NE", "ma": "NE", "pb": "NE", "pe": "NE",
    "pi": "NE", "rn": "NE", "se": "NE",
    "df": "CO", "go": "CO", "ms": "CO", "mt": "CO",
    "es": "SE", "mg": "SE", "rj": "SE", "sp": "SE",
    "pr": "S", "rs": "S", "sc": "S",
}

# --------------------------------------------------------------------------
# Exportação (ClickHouse)
# --------------------------------------------------------------------------

def _pivo_votos(tabela: str, filtro: str, outros: tuple[int, int, int]) -> str:
    o1, o2, o3 = outros
    return f"""
        SELECT uf, cd_mun, zona, secao,
               sumIf(votos, tipo_voto = 'nominal' AND numero = 13) AS v13,
               sumIf(votos, tipo_voto = 'nominal' AND numero = 22) AS v22,
               sumIf(votos, tipo_voto = 'nominal' AND numero = {o1}) AS o1,
               sumIf(votos, tipo_voto = 'nominal' AND numero = {o2}) AS o2,
               sumIf(votos, tipo_voto = 'nominal' AND numero = {o3}) AS o3,
               sumIf(votos, tipo_voto = 'nominal'
                     AND numero NOT IN (13, 22, {o1}, {o2}, {o3})) AS orr,
               sumIf(votos, tipo_voto = 'branco') AS br,
               sumIf(votos, tipo_voto = 'nulo') AS nu
        FROM {tabela} {filtro}
        GROUP BY uf, cd_mun, zona, secao"""


SQL = {
    "2026_t1": f"""
        SELECT toString(s.uf) AS uf, s.cd_mun AS cd_mun, s.nm_mun AS nm_mun, s.zona AS zona,
               s.secao AS secao, toInt64(ifNull(s.local_votacao, -1)) AS local,
               toString(ifNull(s.modelo_urna, '')) AS modelo,
               toInt64(ifNull(s.aptos, 0)) AS aptos,
               toInt64(ifNull(s.comparecimento, 0)) AS comp,
               v.v13 AS v13, v.v22 AS v22, v.o1 AS o1, v.o2 AS o2, v.o3 AS o3,
               v.orr AS orr, v.br AS br, v.nu AS nu
        FROM dataurnas.ref_secoes_2026_t1 AS s
        INNER JOIN ({_pivo_votos('dataurnas.ref_votos_2026_t1', '', OUTROS[2026])}) AS v
              USING (uf, cd_mun, zona, secao)
        WHERE s.status = 'ok' AND s.uf != 'zz'
        FORMAT Parquet""",
    "2026_t2": """
        WITH v AS (
            SELECT uf, cd_mun, zona, secao, sha512_bu,
                   sumIf(votos, tipo_voto = 'nominal' AND numero = 13) AS v13,
                   sumIf(votos, tipo_voto = 'nominal' AND numero = 22) AS v22,
                   sumIf(votos, tipo_voto = 'nominal' AND numero NOT IN (13, 22)) AS orr,
                   sumIf(votos, tipo_voto = 'branco') AS br,
                   sumIf(votos, tipo_voto = 'nulo') AS nu
            FROM dataurnas.bu_votos FINAL
            GROUP BY uf, cd_mun, zona, secao, sha512_bu)
        SELECT toString(u.uf) AS uf, u.cd_mun AS cd_mun, '' AS nm_mun, u.zona AS zona,
               u.secao AS secao, toInt64(ifNull(u.local_votacao, -1)) AS local,
               '' AS modelo,
               toInt64(ifNull(u.aptos, 0)) AS aptos,
               toInt64(ifNull(u.comparecimento, 0)) AS comp,
               toInt64(v.v13) AS v13, toInt64(v.v22) AS v22,
               toInt64(0) AS o1, toInt64(0) AS o2, toInt64(0) AS o3,
               toInt64(v.orr) AS orr, toInt64(v.br) AS br, toInt64(v.nu) AS nu
        FROM dataurnas.v_bu_ultima AS u
        INNER JOIN v ON v.uf = u.uf AND v.cd_mun = u.cd_mun AND v.zona = u.zona
                    AND v.secao = u.secao AND v.sha512_bu = u.sha512
        WHERE u.uf != 'zz'
        FORMAT Parquet""",
}
for _t in (1, 2):
    SQL[f"2022_t{_t}"] = f"""
        SELECT toString(s.uf) AS uf, s.cd_mun AS cd_mun, '' AS nm_mun, s.zona AS zona,
               s.secao AS secao, toInt64(-1) AS local, toString(s.modelo_urna) AS modelo,
               toInt64(s.eleitores_aptos) AS aptos, toInt64(s.comparecimento) AS comp,
               v.v13 AS v13, v.v22 AS v22, v.o1 AS o1, v.o2 AS o2, v.o3 AS o3,
               v.orr AS orr, v.br AS br, v.nu AS nu
        FROM dataurnas.ref_secoes_2022 AS s
        INNER JOIN ({_pivo_votos('dataurnas.ref_votos_2022', f'WHERE turno = {_t}', OUTROS[2022])}) AS v
              USING (uf, cd_mun, zona, secao)
        WHERE s.turno = {_t} AND s.uf != 'zz'
        FORMAT Parquet"""


def exportar(destino: Path) -> None:
    destino.mkdir(parents=True, exist_ok=True)
    for nome, sql in SQL.items():
        alvo = destino / f"{nome}.parquet"
        with open(alvo, "wb") as f:
            subprocess.run([CH], input=sql.encode(), stdout=f, check=True)
        print(f"{nome}: {alvo.stat().st_size / 1e6:.1f} MB", flush=True)


# --------------------------------------------------------------------------
# Carga e utilidades
# --------------------------------------------------------------------------

def carregar(dados: Path) -> dict[tuple[int, int], pd.DataFrame]:
    out = {}
    for ano in (2022, 2026):
        for t in (1, 2):
            df = pd.read_parquet(dados / f"{ano}_t{t}.parquet")
            df = df.drop_duplicates(["uf", "cd_mun", "zona", "secao"])
            for c in ("aptos", "comp", "v13", "v22", "o1", "o2", "o3", "orr", "br", "nu"):
                df[c] = df[c].astype(np.int64)
            df["outros"] = df[["o1", "o2", "o3", "orr"]].sum(axis=1)
            df["validos"] = df["v13"] + df["v22"] + df["outros"]
            df["mun"] = df["uf"] + df["cd_mun"]
            df["zon"] = df["mun"] + "-" + df["zona"]
            df["regiao"] = df["uf"].map(REGIAO)
            df["chave"] = df["zon"] + "-" + df["secao"]
            out[(ano, t)] = df.reset_index(drop=True)
    # modelo de urna do 2º turno de 2026: o do 1º turno (a urna é a mesma em mais de
    # 99,8% das seções, conforme docs/viradas-1t-2t-2026.md)
    m1 = out[(2026, 1)].set_index("chave")["modelo"]
    t2 = out[(2026, 2)]
    t2["modelo"] = t2["chave"].map(m1).fillna("")
    return out


def demean(x: np.ndarray, g: np.ndarray, w: np.ndarray) -> np.ndarray:
    """Subtrai a média ponderada do grupo (g = códigos inteiros 0..G-1)."""
    sw = np.bincount(g, weights=w)
    if x.ndim == 1:
        m = np.bincount(g, weights=w * x) / np.where(sw > 0, sw, 1)
        return x - m[g]
    res = np.empty_like(x, dtype=float)
    for j in range(x.shape[1]):
        m = np.bincount(g, weights=w * x[:, j]) / np.where(sw > 0, sw, 1)
        res[:, j] = x[:, j] - m[g]
    return res


def wls(X: np.ndarray, y: np.ndarray, w: np.ndarray) -> np.ndarray:
    sw = np.sqrt(w)
    beta, *_ = np.linalg.lstsq(X * sw[:, None], y * sw, rcond=None)
    return beta


def codigos(s: pd.Series) -> np.ndarray:
    return pd.factorize(s)[0].astype(np.int64)


def r(x, n=4):
    if x is None:
        return None
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        if not np.isfinite(x):
            return None
        return round(float(x), n)
    return x


# --------------------------------------------------------------------------
# 1. Impressão digital (Klimek)
# --------------------------------------------------------------------------

def fingerprint(df: pd.DataFrame, ano: int, turno: int) -> tuple[dict, pd.DataFrame, np.ndarray]:
    venc = VENCEDOR[(ano, turno)]
    d = df[(df.aptos >= 20) & (df.validos > 0)].copy()
    d["turnout"] = d.comp / d.aptos
    d["fatia"] = d[f"v{venc}"] / d.validos
    H, _, _ = np.histogram2d(d.turnout.clip(0, 1), d.fatia, bins=100, range=[[0, 1], [0, 1]])
    canto = (d.turnout >= 0.95) & (d.fatia >= 0.95)
    canto_perd = (d.turnout >= 0.95) & (d.fatia <= 0.05)
    # inclinação da fatia sobre o comparecimento dentro do município (efeito fixo)
    g = codigos(d.mun)
    w = d.aptos.to_numpy(float)
    xt = demean(d.turnout.to_numpy(float), g, w)
    yt = demean(d.fatia.to_numpy(float), g, w)
    slope = float(np.sum(w * xt * yt) / np.sum(w * xt * xt))
    corr = float(np.sum(w * xt * yt) / np.sqrt(np.sum(w * xt * xt) * np.sum(w * yt * yt)))
    res = {
        "vencedor": venc,
        "secoes": int(len(d)),
        "comparecimento_medio": r(d.comp.sum() / d.aptos.sum()),
        "comparecimento_dp_secao": r(d.turnout.std()),
        "comp_maior_que_aptos": int((df.comp > df.aptos).sum()),
        "turnout_ge_95": int((d.turnout >= 0.95).sum()),
        "turnout_ge_98": int((d.turnout >= 0.98).sum()),
        "turnout_eq_100": int((d.comp == d.aptos).sum()),
        "canto_95_95": int(canto.sum()),
        "canto_95_95_13": int(((d.turnout >= 0.95) & (d.v13 / d.validos >= 0.95)).sum()),
        "canto_95_95_22": int(((d.turnout >= 0.95) & (d.v22 / d.validos >= 0.95)).sum()),
        "fatia13_ge_95": int((d.v13 / d.validos >= 0.95).sum()),
        "fatia22_ge_95": int((d.v22 / d.validos >= 0.95).sum()),
        "canto_95_95_por_10mil": r(1e4 * canto.mean(), 3),
        "canto_95_perdedor_le_5": int(canto_perd.sum()),
        "fatia_ge_95": int((d.fatia >= 0.95).sum()),
        "fatia_le_05": int((d.fatia <= 0.05).sum()),
        "inclinacao_fatia_comp_mun": r(slope),
        "correlacao_fatia_comp_mun": r(corr),
    }
    linhas = []
    for uf, x in d.groupby("uf"):
        gg = codigos(x.mun)
        ww = x.aptos.to_numpy(float)
        a = demean(x.turnout.to_numpy(float), gg, ww)
        b = demean(x.fatia.to_numpy(float), gg, ww)
        den = np.sum(ww * a * a)
        linhas.append({
            "ano": ano, "turno": turno, "uf": uf, "secoes": len(x),
            "comparecimento": x.comp.sum() / x.aptos.sum(),
            "turnout_ge_95": int((x.turnout >= 0.95).sum()),
            "canto_95_95": int(((x.turnout >= 0.95) & (x.fatia >= 0.95)).sum()),
            "fatia_ge_95": int((x.fatia >= 0.95).sum()),
            "inclinacao_mun": float(np.sum(ww * a * b) / den) if den > 0 else np.nan,
            "correlacao_mun": float(np.sum(ww * a * b) / np.sqrt(den * np.sum(ww * b * b))) if den > 0 else np.nan,
        })
    lista = d[canto][["chave", "uf", "nm_mun", "aptos", "comp", "v13", "v22", "outros", "br", "nu",
                      "turnout", "fatia"]].assign(ano=ano, turno=turno)
    return res, pd.DataFrame(linhas), H, lista


# --------------------------------------------------------------------------
# 2. Dígitos
# --------------------------------------------------------------------------

BENFORD2 = np.array([sum(np.log10(1 + 1 / (10 * k + d)) for k in range(1, 10)) for d in range(10)])
MEDIA2 = float(np.sum(np.arange(10) * BENFORD2))  # 4,187


def segundo_digito(v: np.ndarray) -> np.ndarray:
    v = v.astype(np.int64)
    ordem = np.floor(np.log10(np.maximum(v, 1))).astype(np.int64)
    return (v // (10 ** np.maximum(ordem - 1, 0))) % 10


def _sim_digitos(args):
    n, ab, grupos, ngr, _a, _b, seed, nsim = args
    alfa, beta_ = ab
    rng = np.random.default_rng(seed)
    out_u10 = np.zeros((nsim, ngr, 10))
    out_u100 = np.zeros((nsim, ngr, 10))
    out_b2 = np.zeros((nsim, ngr, 10))
    for s in range(nsim):
        v = rng.binomial(n, rng.beta(alfa, beta_))
        m10 = v >= 10
        m100 = v >= 100
        u = v % 10
        d2 = segundo_digito(v)
        out_u10[s] = np.bincount(grupos[m10] * 10 + u[m10], minlength=ngr * 10).reshape(ngr, 10)
        out_u100[s] = np.bincount(grupos[m100] * 10 + u[m100], minlength=ngr * 10).reshape(ngr, 10)
        out_b2[s] = np.bincount(grupos[m10] * 10 + d2[m10], minlength=ngr * 10).reshape(ngr, 10)
    return out_u10, out_u100, out_b2


def _metricas_dig(cont: np.ndarray, esperado: np.ndarray) -> dict:
    """cont: (..., 10) contagens; esperado: probabilidades (10,)."""
    from scipy import stats
    n = cont.sum(-1, keepdims=True)
    freq = cont / np.where(n > 0, n, 1)
    e = n * esperado
    chi2 = ((cont - e) ** 2 / np.where(e > 0, e, 1)).sum(-1)
    mad = np.abs(freq - esperado).mean(-1)
    media = (freq * np.arange(10)).sum(-1)
    return {"n": n[..., 0], "chi2": chi2, "p": stats.chi2.sf(chi2, 9), "mad": mad, "media": media}


def digitos(df: pd.DataFrame, ano: int, turno: int, nsim: int, workers: int) -> tuple[dict, pd.DataFrame]:
    d = df[df.validos > 0].copy()
    # fatia de referência do município (deixando a própria seção de fora)
    res_json = {}
    linhas = []
    gr_uf = codigos(d.uf)
    nomes_uf = pd.factorize(d.uf)[1]
    gr_mod = codigos(d.modelo.replace("", "?"))
    nomes_mod = pd.factorize(d.modelo.replace("", "?"))[1]
    # grupos combinados: 0 = Brasil, 1..U = UF, U+1.. = modelo
    U, M = len(nomes_uf), len(nomes_mod)
    for cand in (13, 22):
        v = d[f"v{cand}"].to_numpy(np.int64)
        n = d.validos.to_numpy(np.int64)
        tm = d.groupby("mun")[f"v{cand}"].transform("sum").to_numpy(float)
        nm = d.groupby("mun")["validos"].transform("sum").to_numpy(float)
        p = np.where(nm - n > 0, (tm - v) / np.maximum(nm - n, 1), v / np.maximum(n, 1))
        p = np.clip(p, 1e-4, 1 - 1e-4)
        # heterogeneidade real entre seções do município (além da binomial): a fatia de
        # cada seção é sorteada de uma Beta com a média do município e a variância
        # entre seções observada, e os votos de uma binomial com essa fatia
        s_i = v / np.maximum(n, 1)
        gm = codigos(d.mun)
        sw = np.bincount(gm, weights=n.astype(float))
        mm = np.bincount(gm, weights=v.astype(float)) / sw
        var_obs = np.bincount(gm, weights=n * (s_i - mm[gm]) ** 2) / sw
        var_bin = np.bincount(gm, weights=n * (mm[gm] * (1 - mm[gm]) / np.maximum(n, 1))) / sw
        tau2 = np.maximum(var_obs - var_bin, 1e-5)[gm]
        kappa = np.maximum(p * (1 - p) / tau2 - 1, 2.0)
        ab = (p * kappa, (1 - p) * kappa)
        # três "visões" de agrupamento empilhadas: Brasil, UF, modelo
        G = np.concatenate([np.zeros(len(d), np.int64), 1 + gr_uf, 1 + U + gr_mod])
        vv = np.tile(v, 3)
        ngr = 1 + U + M
        obs_u10 = np.bincount(G[vv >= 10] * 10 + (vv[vv >= 10] % 10), minlength=ngr * 10).reshape(ngr, 10)
        obs_u100 = np.bincount(G[vv >= 100] * 10 + (vv[vv >= 100] % 10), minlength=ngr * 10).reshape(ngr, 10)
        d2 = segundo_digito(vv)
        obs_b2 = np.bincount(G[vv >= 10] * 10 + d2[vv >= 10], minlength=ngr * 10).reshape(ngr, 10)
        # simulação: só a parte Brasil precisa de n e p uma vez; o tile replica
        por = max(1, nsim // workers)
        tarefas = [(n, ab, np.zeros(len(d), np.int64), 1, None, None, 1000 * cand + i + 7 * ano + turno, por)
                   for i in range(workers)]
        # para UF e modelo usamos os mesmos sorteios: rodar com grupos separados
        tarefas_uf = [(n, ab, gr_uf, U, None, None, 5000 + 1000 * cand + i + 7 * ano + turno, por)
                      for i in range(workers)]
        tarefas_mod = [(n, ab, gr_mod, M, None, None, 9000 + 1000 * cand + i + 7 * ano + turno, por)
                       for i in range(workers)]
        with ProcessPoolExecutor(workers) as ex:
            rb = list(ex.map(_sim_digitos, tarefas))
            ru = list(ex.map(_sim_digitos, tarefas_uf))
            rm = list(ex.map(_sim_digitos, tarefas_mod))
        sims = [np.concatenate([np.concatenate([a[k] for a in rb]),
                                np.concatenate([a[k] for a in ru], 0),
                                np.concatenate([a[k] for a in rm], 0)], axis=1) for k in range(3)]
        unif = np.full(10, 0.1)
        for nome_teste, obs, sim, esp in (("ultimo_ge10", obs_u10, sims[0], unif),
                                          ("ultimo_ge100", obs_u100, sims[1], unif),
                                          ("benford2_ge10", obs_b2, sims[2], BENFORD2)):
            mo = _metricas_dig(obs.astype(float), esp)
            ms = _metricas_dig(sim.astype(float), esp)
            # referência simulada: média e desvio da MAD, da média e da distribuição
            simfreq = sim / np.maximum(sim.sum(-1, keepdims=True), 1)
            simmean = simfreq.mean(0)
            # qui-quadrado contra a distribuição simulada (não contra a teórica)
            e_sim = obs.sum(-1, keepdims=True) * simmean
            chi_sim = ((obs - e_sim) ** 2 / np.where(e_sim > 0, e_sim, 1)).sum(-1)
            # p empírico: fração de simulações com qui-quadrado (vs. média simulada) >= observado
            e_ss = sim.sum(-1, keepdims=True) * simmean[None]
            chi_ss = ((sim - e_ss) ** 2 / np.where(e_ss > 0, e_ss, 1)).sum(-1)
            p_emp = ((chi_ss >= chi_sim[None]).sum(0) + 1) / (chi_ss.shape[0] + 1)
            z_media = (mo["media"] - ms["media"].mean(0)) / np.where(ms["media"].std(0) > 0, ms["media"].std(0), np.nan)
            z_mad = (mo["mad"] - ms["mad"].mean(0)) / np.where(ms["mad"].std(0) > 0, ms["mad"].std(0), np.nan)
            for gi in range(ngr):
                if gi == 0:
                    tipo, nome = "brasil", "BR"
                elif gi <= U:
                    tipo, nome = "uf", nomes_uf[gi - 1]
                else:
                    tipo, nome = "modelo", nomes_mod[gi - 1 - U]
                linhas.append({
                    "ano": ano, "turno": turno, "candidato": cand, "teste": nome_teste,
                    "grupo_tipo": tipo, "grupo": nome, "n": int(mo["n"][gi]),
                    "chi2_teorico": mo["chi2"][gi], "p_teorico": mo["p"][gi],
                    "mad": mo["mad"][gi], "mad_sim_media": ms["mad"][:, gi].mean(),
                    "z_mad_vs_sim": z_mad[gi],
                    "media": mo["media"][gi], "media_sim": ms["media"][:, gi].mean(),
                    "z_media_vs_sim": z_media[gi],
                    "chi2_vs_sim": chi_sim[gi], "p_emp_vs_sim": p_emp[gi],
                    **{f"f{k}": obs[gi, k] / max(obs[gi].sum(), 1) for k in range(10)},
                    **{f"fsim{k}": simmean[gi, k] for k in range(10)},
                })
    tab = pd.DataFrame(linhas)
    br = tab[tab.grupo_tipo == "brasil"]
    for _, x in br.iterrows():
        res_json[f"{int(x.candidato)}_{x.teste}"] = {
            "n": int(x.n), "chi2_teorico": r(x.chi2_teorico, 1), "p_teorico": r(x.p_teorico, 6),
            "mad": r(x.mad, 5), "mad_sim": r(x.mad_sim_media, 5), "z_mad_vs_sim": r(x.z_mad_vs_sim, 2),
            "media": r(x.media, 4), "media_sim": r(x.media_sim, 4), "z_media_vs_sim": r(x.z_media_vs_sim, 2),
            "chi2_vs_sim": r(x.chi2_vs_sim, 1), "p_emp_vs_sim": r(x.p_emp_vs_sim, 4),
        }
    for teste in ("ultimo_ge10", "ultimo_ge100", "benford2_ge10"):
        for gt in ("uf", "modelo"):
            x = tab[(tab.teste == teste) & (tab.grupo_tipo == gt) & (tab.n >= 500)]
            res_json[f"{teste}_{gt}_grupos"] = int(len(x))
            res_json[f"{teste}_{gt}_p_emp_lt_001"] = int((x.p_emp_vs_sim < 0.001).sum())
            res_json[f"{teste}_{gt}_p_emp_lt_01"] = int((x.p_emp_vs_sim < 0.01).sum())
            res_json[f"{teste}_{gt}_absz_media_gt3"] = int((x.z_media_vs_sim.abs() > 3).sum())
    return res_json, tab


# --------------------------------------------------------------------------
# Pareamento 1º x 2º turno
# --------------------------------------------------------------------------

def parear(t1: pd.DataFrame, t2: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    a = t1.set_index("chave")
    b = t2.set_index("chave")
    comum = a.index.intersection(b.index)
    cols = ["aptos", "comp", "v13", "v22", "o1", "o2", "o3", "orr", "br", "nu", "outros", "validos"]
    p = a.loc[comum, ["uf", "regiao", "mun", "zon", "nm_mun", "zona", "secao", "local", "modelo"] + cols].copy()
    for c in cols:
        p[c + "_2"] = b.loc[comum, c].to_numpy()
    p["local_2"] = b.loc[comum, "local"].to_numpy()
    p = p.reset_index()
    total = len(p)
    ok = (p.aptos > 0) & (p.aptos_2 > 0) & ((p.aptos_2 - p.aptos).abs() <= 0.10 * p.aptos) \
        & (p.v13 + p.v22 > 0) & (p.v13_2 + p.v22_2 >= 20)
    info = {"t1": len(t1), "t2": len(t2), "pareadas": total, "usadas": int(ok.sum()),
            "descartadas_aptos_ou_pequenas": int(total - ok.sum())}
    p = p[ok].reset_index(drop=True)
    p["s1"] = p.v13 / (p.v13 + p.v22)
    p["s2"] = p.v13_2 / (p.v13_2 + p.v22_2)
    p["n2"] = p.v13_2 + p.v22_2
    p["t1"] = p.comp / p.aptos
    p["t2"] = p.comp_2 / p.aptos_2
    return p, info


# --------------------------------------------------------------------------
# 3. Swing com efeito fixo de município
# --------------------------------------------------------------------------

def swing(p: pd.DataFrame, ano: int) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    A = p.aptos.to_numpy(float)
    X = np.column_stack([
        p.s1, p.s1 ** 2, p.s1 ** 3,
        p.v13 / A, p.v22 / A, p.o1 / A, p.o2 / A, p.o3 / A, p.orr / A, p.br / A, p.nu / A,
        np.log(A),
    ]).astype(float)
    y = p.s2.to_numpy(float)
    w = p.n2.to_numpy(float)
    g = codigos(p.mun)
    Xd = demean(X, g, w)
    yd = demean(y, g, w)
    beta = wls(Xd, yd, w)
    resid = yd - Xd @ beta
    # ajuste com efeito fixo: previsão = y - resíduo
    pred = y - resid
    # variância: tau² + phi * s(1-s)/n, estimada por WLS dos resíduos ao quadrado
    sp = np.clip(pred, 0.02, 0.98)
    bvar = sp * (1 - sp) / w
    # correção de graus de liberdade pelo efeito fixo
    G = g.max() + 1
    fator = len(y) / max(len(y) - G - X.shape[1], 1)
    Z = np.column_stack([np.ones_like(bvar), bvar])
    coef, *_ = np.linalg.lstsq(Z, resid ** 2 * fator, rcond=None)
    tau2, phi = max(coef[0], 1e-6), max(coef[1], 0.1)
    sd = np.sqrt(tau2 + phi * bvar)
    z = resid / sd
    # R² dentro do município e total
    r2_dentro = 1 - np.sum(w * resid ** 2) / np.sum(w * yd ** 2)
    ybar = np.sum(w * y) / np.sum(w)
    r2_total = 1 - np.sum(w * resid ** 2) / np.sum(w * (y - ybar) ** 2)
    p = p.assign(pred=pred, resid=resid, z=z, sd=sd)
    n = len(p)
    from scipy import stats
    res = {
        "secoes": n,
        "r2_dentro_municipio": r(r2_dentro),
        "r2_total": r(r2_total),
        "tau_pp": r(100 * np.sqrt(tau2), 3),
        "phi": r(phi, 3),
        "dp_residuo_pp": r(100 * resid.std(), 3),
        "z_dp": r(z.std(), 3),
        "cauda": {},
        "coeficientes": dict(zip(["s1", "s1^2", "s1^3", "f13", "f22", "fo1", "fo2", "fo3", "for", "fbr", "fnu", "log_aptos"],
                                 [r(b, 4) for b in beta], strict=False)),
    }
    for k in (3, 4, 5, 6):
        res["cauda"][f"abs_z_gt_{k}"] = int((np.abs(z) > k).sum())
        res["cauda"][f"abs_z_gt_{k}_por_10mil"] = r(1e4 * (np.abs(z) > k).mean(), 3)
        res["cauda"][f"normal_esperado_{k}"] = r(n * 2 * stats.norm.sf(k), 2)
        res["cauda"][f"z_pos_gt_{k}"] = int((z > k).sum())
        res["cauda"][f"z_neg_lt_{k}"] = int((z < -k).sum())
    res["curtose_z"] = r(float(stats.kurtosis(z)), 3)
    # aglomerados: zona e local (efeito fixo de município) por Stouffer
    agl = []
    for nivel, chave in (("zona", "zon"), ("local", None)):
        if chave is None:
            if (p.local < 0).all():
                continue
            k = p.mun + "-" + p.zona + "-L" + p.local.astype(str)
            kk = p[p.local >= 0].assign(_k=k[p.local >= 0])
        else:
            kk = p.assign(_k=p[chave])
        gg = kk.groupby("_k").agg(uf=("uf", "first"), mun=("mun", "first"), nm_mun=("nm_mun", "first"),
                                   secoes=("z", "size"), soma_z=("z", "sum"),
                                   resid_medio_pp=("resid", "mean"))
        gg["stouffer"] = gg.soma_z / np.sqrt(gg.secoes)
        nmun = kk.groupby("mun")["_k"].nunique()
        gg = gg[(gg.secoes >= 3) & (gg.mun.map(nmun) >= 2)]
        gg["resid_medio_pp"] *= 100
        res[f"aglomerados_{nivel}"] = {
            "grupos": int(len(gg)),
            "stouffer_dp": r(gg.stouffer.std(), 3),
            "abs_stouffer_gt_4": int((gg.stouffer.abs() > 4).sum()),
            "abs_stouffer_gt_6": int((gg.stouffer.abs() > 6).sum()),
            "abs_stouffer_gt_4_por_mil": r(1e3 * (gg.stouffer.abs() > 4).mean(), 3),
        }
        gg = gg.reset_index().rename(columns={"_k": "grupo"})
        gg["nivel"] = nivel
        gg["ano"] = ano
        agl.append(gg)
    # nível município: modelo sem efeito fixo de município (só de UF)
    gu = codigos(p.uf)
    Xu = demean(X, gu, w)
    yu = demean(y, gu, w)
    bu = wls(Xu, yu, w)
    ru = yu - Xu @ bu
    pm = p.assign(ru=ru).groupby("mun").agg(uf=("uf", "first"), nm_mun=("nm_mun", "first"),
                                            secoes=("ru", "size"), n2=("n2", "sum"),
                                            resid_medio_pp=("ru", "mean"), s1=("s1", "mean"), s2=("s2", "mean"))
    pm["resid_medio_pp"] *= 100
    # escala: desvio robusto do resíduo municipal em municípios do mesmo porte
    pm["porte"] = pd.qcut(pm.secoes.rank(method="first"), 10, labels=False)
    escala = pm.groupby("porte").resid_medio_pp.transform(lambda s: 1.4826 * np.median(np.abs(s - s.median())))
    pm["z_robusto"] = (pm.resid_medio_pp - pm.groupby("porte").resid_medio_pp.transform("median")) / escala
    res["municipios"] = {
        "municipios": int(len(pm)),
        "dp_resid_pp": r(pm.resid_medio_pp.std(), 3),
        "abs_resid_gt_5pp": int((pm.resid_medio_pp.abs() > 5).sum()),
        "abs_resid_gt_10pp": int((pm.resid_medio_pp.abs() > 10).sum()),
        "abs_z_robusto_gt_5": int((pm.z_robusto.abs() > 5).sum()),
        "abs_z_robusto_gt_8": int((pm.z_robusto.abs() > 8).sum()),
    }
    pm = pm.reset_index()
    pm["nivel"] = "municipio"
    pm["ano"] = ano
    agl.append(pm.rename(columns={"mun": "grupo"}))
    por_uf = p.assign(az4=np.abs(p.z) > 4, az5=np.abs(p.z) > 5).groupby("uf").agg(
        secoes=("z", "size"), z_dp=("z", "std"), az4=("az4", "sum"), az5=("az5", "sum"),
        resid_dp_pp=("resid", "std"))
    por_uf["resid_dp_pp"] *= 100
    res["por_uf"] = por_uf.reset_index().to_dict("records")
    return res, p, pd.concat(agl, ignore_index=True)


# --------------------------------------------------------------------------
# 4. Transferência (Goodman) e perda absoluta incomum
# --------------------------------------------------------------------------

def _flag_perda(v1, v2, comp1, comp2):
    dcomp = comp2 - comp1
    esperada = v1 * np.maximum(0, -dcomp) / np.maximum(comp1, 1)
    excesso = -(v2 - v1) - esperada
    rel = excesso / np.maximum(v1, 1)
    return (excesso >= 10) & (rel >= 0.20)


def perda_simulada(p: pd.DataFrame, nsim: int, seed: int) -> dict:
    """Quantas seções com perda absoluta incomum o modelo de swing produz sozinho:
    fatia do 13 sorteada de N(previsão, dp do modelo), total 13 + 22 e comparecimento
    do 2º turno mantidos. Dá o esperado em cada ano para comparar com o observado."""
    rng = np.random.default_rng(seed)
    n2 = p.n2.to_numpy()
    out = {"13": [], "22": []}
    for _ in range(nsim):
        s = np.clip(p.pred.to_numpy() + p.sd.to_numpy() * rng.standard_normal(len(p)), 0, 1)
        v13 = np.rint(n2 * s)
        v22 = n2 - v13
        out["13"].append(_flag_perda(p.v13.to_numpy(), v13, p.comp.to_numpy(), p.comp_2.to_numpy()).sum())
        out["22"].append(_flag_perda(p.v22.to_numpy(), v22, p.comp.to_numpy(), p.comp_2.to_numpy()).sum())
    return {k: {"esperado_modelo": r(float(np.mean(v)), 1), "dp": r(float(np.std(v)), 1)} for k, v in out.items()}


def transferencia(p: pd.DataFrame, ano: int) -> dict:
    nomes1 = ["13", "22", f"o{OUTROS[ano][0]}", f"o{OUTROS[ano][1]}", f"o{OUTROS[ano][2]}",
              "outros_menores", "branco", "nulo", "abstencao"]
    X = np.column_stack([p.v13, p.v22, p.o1, p.o2, p.o3, p.orr, p.br, p.nu, p.aptos - p.comp]).astype(float)
    alvos = {"13": p.v13_2, "22": p.v22_2, "branco_nulo": p.br_2 + p.nu_2 + p.orr_2,
             "abstencao": p.aptos_2 - p.comp_2}
    res = {}
    for escopo, mask in [("BR", np.ones(len(p), bool))] + [(rg, (p.regiao == rg).to_numpy()) for rg in ("N", "NE", "CO", "SE", "S")]:
        Xm = X[mask]
        bloc = {}
        for nome, yv in alvos.items():
            b, *_ = np.linalg.lstsq(Xm, yv.to_numpy(float)[mask], rcond=None)
            bloc[nome] = dict(zip(nomes1, [r(v, 3) for v in b], strict=False))
        # versão com efeito fixo de município (contagens centradas no município)
        g = codigos(p.mun[mask])
        w1 = np.ones(mask.sum())
        Xd = demean(Xm, g, w1)
        blocfe = {}
        for nome, yv in alvos.items():
            b, *_ = np.linalg.lstsq(Xd, demean(yv.to_numpy(float)[mask], g, w1), rcond=None)
            blocfe[nome] = dict(zip(nomes1, [r(v, 3) for v in b], strict=False))
        res[escopo] = {"goodman": bloc, "goodman_ef_municipio": blocfe}
    # perda absoluta: quem perde terreno no ano (2026: 22; 2022: 13) e o outro
    d13 = p.v13_2 - p.v13
    d22 = p.v22_2 - p.v22
    dcomp = p.comp_2 - p.comp
    perdas = {}
    for cand, dv, v1 in (("13", d13, p.v13), ("22", d22, p.v22)):
        esperada = v1 * np.maximum(0, -dcomp) / p.comp.clip(lower=1)
        excesso = -dv - esperada
        rel = excesso / v1.clip(lower=1)
        m1 = (excesso >= 10) & (rel >= 0.20)
        m2 = (excesso >= 20) & (rel >= 0.30)
        m3 = (excesso >= 30) & (rel >= 0.50)
        perdas[cand] = {
            "perde_votos_absolutos": int((dv < 0).sum()),
            "perde_pct": r(100 * (dv < 0).mean(), 2),
            "excesso_ge10_e_20pct": int(m1.sum()),
            "excesso_ge20_e_30pct": int(m2.sum()),
            "excesso_ge30_e_50pct": int(m3.sum()),
            "por_10mil_ge10_20pct": r(1e4 * m1.mean(), 2),
            "perda_relativa_p99": r(float(np.percentile(-dv / v1.clip(lower=1), 99)), 4),
        }
    # ganho acima do estoque sem troca direta, com rotatividade total:
    # outros + brancos + nulos + abstenção do 1º turno (limite máximo sem tirar voto do rival)
    estoque_total = p.outros + p.br + p.nu + (p.aptos - p.comp)
    estoque_liq = p.outros + p.br + p.nu + np.maximum(0, dcomp)
    ganhos = {}
    for cand, dv in (("13", d13), ("22", d22)):
        ganhos[cand] = {
            "ganho_maior_estoque_total": int((dv > estoque_total).sum()),
            "ganho_maior_estoque_liquido": int((dv > estoque_liq).sum()),
            "ganho_maior_estoque_liquido_mais10": int((dv > estoque_liq + 10).sum()),
        }
    sim = perda_simulada(p, 200, 17 + ano)
    for cand in ("13", "22"):
        perdas[cand]["esperado_pelo_modelo_swing"] = sim[cand]["esperado_modelo"]
        perdas[cand]["dp_simulado"] = sim[cand]["dp"]
        e = sim[cand]["esperado_modelo"] or 0
        perdas[cand]["observado_sobre_esperado"] = r(perdas[cand]["excesso_ge10_e_20pct"] / e, 3) if e else None
        # por faixa da fatia do candidato no 1º turno
        sh = (p[f"v{cand}"] / (p.v13 + p.v22)).to_numpy()
        flag = _flag_perda(p[f"v{cand}"].to_numpy(), p[f"v{cand}_2"].to_numpy(), p.comp.to_numpy(), p.comp_2.to_numpy())
        faixas = pd.cut(sh, [0, .1, .2, .3, .4, .5, .6, 1], include_lowest=True)
        perdas[cand]["por_faixa_fatia_t1"] = {str(k): int(v) for k, v in pd.Series(flag).groupby(faixas, observed=False).sum().items()}
        perdas[cand]["swing_z_abs_gt4_entre_eles"] = int((np.abs(p.z.to_numpy()[flag]) > 4).sum())
    res["perda_absoluta"] = perdas
    res["brancos_nulos"] = {
        "branco_t1_pct": r(100 * p.br.sum() / p.comp.sum(), 3), "nulo_t1_pct": r(100 * p.nu.sum() / p.comp.sum(), 3),
        "branco_t2_pct": r(100 * p.br_2.sum() / p.comp_2.sum(), 3), "nulo_t2_pct": r(100 * p.nu_2.sum() / p.comp_2.sum(), 3),
        "corr_fbranco_t1_s1": r(float(np.corrcoef(p.br / p.comp, p.s1)[0, 1]), 4),
        "corr_fnulo_t1_s1": r(float(np.corrcoef(p.nu / p.comp, p.s1)[0, 1]), 4),
    }
    res["ganho_vs_estoque"] = ganhos
    res["secoes"] = int(len(p))
    return res


# --------------------------------------------------------------------------
# 5. Dispersão (heterogeneidade binomial dentro de grupos)
# --------------------------------------------------------------------------

def dispersao(df: pd.DataFrame, ano: int, turno: int) -> tuple[dict, pd.DataFrame]:
    from scipy import stats
    d = df[(df.v13 + df.v22) >= 20].copy()
    d["n"] = d.v13 + d.v22
    out = {}
    linhas = []
    niveis = [("municipio", d.mun), ("zona", d.zon)]
    if (d.local >= 0).any():
        niveis.append(("local", d.zon + "-L" + d.local.astype(str)))
    for nivel, chave in niveis:
        g = codigos(chave)
        k = np.bincount(g)
        tot13 = np.bincount(g, weights=d.v13)
        totn = np.bincount(g, weights=d.n)
        pbar = tot13 / totn
        e = d.n.to_numpy() * pbar[g]
        var = d.n.to_numpy() * pbar[g] * (1 - pbar[g])
        x2 = np.bincount(g, weights=(d.v13.to_numpy() - e) ** 2 / np.where(var > 0, var, np.nan))
        df_ = k - 1
        ok = (k >= 2) & (pbar > 0.02) & (pbar < 0.98)
        x2, df_, kk, pb = x2[ok], df_[ok], k[ok], pbar[ok]
        p_baixo = stats.chi2.cdf(x2, df_)
        p_alto = stats.chi2.sf(x2, df_)
        razao = x2 / df_
        out[nivel] = {
            "grupos": int(ok.sum()),
            "secoes_nos_grupos": int(kk.sum()),
            "razao_x2_df_mediana": r(float(np.median(razao)), 3),
            "razao_x2_df_global": r(float(x2.sum() / df_.sum()), 3),
            "subdisperso_p_lt_0001": int((p_baixo < 0.001).sum()),
            "subdisperso_p_lt_001": int((p_baixo < 0.01).sum()),
            "subdisperso_esperado_binomial_001": r(0.01 * ok.sum(), 1),
            "subdisperso_p_lt_001_por_mil": r(1e3 * (p_baixo < 0.01).mean(), 3),
            "superdisperso_p_lt_0001": int((p_alto < 0.001).sum()),
            "superdisperso_p_lt_0001_pct": r(100 * (p_alto < 0.001).mean(), 2),
        }
        nomes = pd.factorize(chave)[1][ok]
        linhas.append(pd.DataFrame({"ano": ano, "turno": turno, "nivel": nivel, "grupo": nomes,
                                    "secoes": kk, "fatia13": pb, "x2": x2, "gl": df_,
                                    "p_subdisperso": p_baixo, "p_superdisperso": p_alto}))
    # resultados idênticos dentro da mesma zona (vetor 13, 22, outros, brancos, nulos)
    dd = df[df.validos + df.br + df.nu >= 100]
    dup = dd.duplicated(["zon", "v13", "v22", "outros", "br", "nu"], keep=False)
    out["resultados_identicos_mesma_zona"] = int(dup.sum())
    vec = pd.util.hash_pandas_object(dd[["v13", "v22", "outros", "br", "nu"]], index=False).to_numpy()
    zz = dd.zon.to_numpy()
    cont = pd.DataFrame({"z": zz, "v": vec}).value_counts().rename("c").reset_index()
    pares_dentro = float((cont.c * (cont.c - 1) / 2).sum())
    nz = dd.zon.value_counts()
    poss_dentro = float((nz * (nz - 1) / 2).sum())
    rng = np.random.default_rng(ano * 10 + turno)
    uf_z = dd.groupby("zon").uf.first()
    taxas = []
    for _ in range(10):
        par = {}
        for _uf, zs in uf_z.groupby(uf_z):
            lst = rng.permutation(zs.index.to_numpy())
            if len(lst) < 2:
                continue
            for a_, b_ in zip(lst, np.roll(lst, 1), strict=True):
                par[a_] = b_
        c2 = cont.assign(z2=cont.z.map(par)).dropna()
        m = c2.merge(cont.rename(columns={"z": "z2", "c": "c2"}), on=["z2", "v"])
        pares_cruz = float((m.c * m.c2).sum())
        poss_cruz = float(sum(nz[a_] * nz[b_] for a_, b_ in par.items()))
        taxas.append(pares_cruz / poss_cruz)
    out["pares_identicos_mesma_zona"] = int(pares_dentro)
    out["taxa_pares_identicos_mesma_zona_por_milhao"] = r(1e6 * pares_dentro / poss_dentro, 3)
    out["taxa_pares_identicos_zonas_sorteadas_mesma_uf_por_milhao"] = r(1e6 * float(np.mean(taxas)), 3)
    out["razao_dentro_sobre_sorteado"] = r(pares_dentro / poss_dentro / float(np.mean(taxas)), 3)
    out["secoes_ge100_votos"] = int(len(dd))
    return out, pd.concat(linhas, ignore_index=True)


def dispersao_simulada(df: pd.DataFrame, nsim: int, seed: int) -> dict:
    """Referência para a cauda de subdispersão: dentro de cada local/zona, sorteia
    votos binomiais com a fatia do grupo e mede quantos grupos dariam p < 0,01.
    Sob homogeneidade perfeita a fração é 1%; o número real só pode ser comparado
    ao que a mesma régua dá em 2022 e no 1º turno."""
    from scipy import stats
    rng = np.random.default_rng(seed)
    d = df[(df.v13 + df.v22) >= 20]
    n = (d.v13 + d.v22).to_numpy()
    res = {}
    for nivel, chave in (("zona", d.zon),):
        g = codigos(chave)
        k = np.bincount(g)
        pbar = np.bincount(g, weights=d.v13) / np.bincount(g, weights=n)
        ok = (k >= 2) & (pbar > 0.02) & (pbar < 0.98)
        fr = []
        for _ in range(nsim):
            v = rng.binomial(n, pbar[g])
            pb = np.bincount(g, weights=v) / np.bincount(g, weights=n)
            var = n * pb[g] * (1 - pb[g])
            x2 = np.bincount(g, weights=(v - n * pb[g]) ** 2 / np.where(var > 0, var, np.nan))
            fr.append(float((stats.chi2.cdf(x2[ok], (k - 1)[ok]) < 0.01).mean()))
        res[nivel] = {"fracao_sub_001_sim_media": r(np.mean(fr), 5)}
    return res


# --------------------------------------------------------------------------
# 6. Comparecimento
# --------------------------------------------------------------------------

def comparecimento(p: pd.DataFrame, ano: int) -> tuple[dict, pd.DataFrame]:
    g = codigos(p.mun)
    w = p.aptos.to_numpy(float)
    dt = (p.t2 - p.t1).to_numpy(float)
    ds = (p.s2 - p.s1).to_numpy(float)
    e = demean(dt, g, w)
    h = demean(ds, g, w)
    slope = float(np.sum(w * e * h) / np.sum(w * e * e))
    corr = float(np.sum(w * e * h) / np.sqrt(np.sum(w * e * e) * np.sum(w * h * h)))
    dcomp = (p.comp_2 - p.comp).to_numpy()
    d13 = (p.v13_2 - p.v13).to_numpy()
    d22 = (p.v22_2 - p.v22).to_numpy()
    sd_e = 1.4826 * np.median(np.abs(e - np.median(e)))
    sd_h = 1.4826 * np.median(np.abs(h - np.median(h)))
    res = {"secoes": int(len(p)),
           "delta_comparecimento_medio_pp": r(100 * np.average(dt, weights=w), 3),
           "dp_excesso_comparecimento_pp": r(100 * e.std(), 3),
           "dp_robusto_excesso_pp": r(100 * sd_e, 3),
           "inclinacao_dfatia13_sobre_dcomp_mun": r(slope, 4),
           "correlacao_mun": r(corr, 4),
           "excesso_ge_10pp": int((e >= 0.10).sum()),
           "excesso_ge_15pp": int((e >= 0.15).sum()),
           "excesso_le_menos10pp": int((e <= -0.10).sum())}
    linhas = []
    for cand, dv, sinal in (("13", d13, 1), ("22", d22, -1)):
        captura = np.where(dcomp > 0, dv / np.maximum(dcomp, 1), np.nan)
        # ganho concentrado: comparecimento acima do município e o candidato fica
        # com 80% ou mais dos comparecentes a mais, e a fatia dele sobe acima do município
        hh = sinal * h
        m = (e >= 0.10) & (dcomp >= 20) & (captura >= 0.8) & (hh >= 3 * sd_h)
        m2 = (e >= 4 * sd_e) & (hh >= 4 * sd_h)
        res[f"concentrado_{cand}"] = int(m.sum())
        res[f"concentrado_{cand}_por_10mil"] = r(1e4 * m.mean(), 3)
        res[f"conjunto_4dp_{cand}"] = int(m2.sum())
        sel = p[m | m2].assign(candidato=cand, excesso_comp_pp=100 * e[m | m2],
                               excesso_fatia_pp=100 * h[m | m2], captura=captura[m | m2], ano=ano)
        linhas.append(sel)
    res["esperado_independente_4dp"] = r(len(p) * np.mean(e >= 4 * sd_e) * np.mean(np.abs(h) >= 4 * sd_h) / 2, 2)
    return res, pd.concat(linhas, ignore_index=True)


# --------------------------------------------------------------------------
# Figuras
# --------------------------------------------------------------------------

def figuras(hists: dict, saida: Path, swings: dict) -> list[str]:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import LogNorm
    arquivos = []
    fig, axs = plt.subplots(2, 2, figsize=(11, 10), constrained_layout=True)
    for ax, (k, H) in zip(axs.ravel(), sorted(hists.items()), strict=False):
        ano, t = k
        im = ax.imshow(H.T + 0.5, origin="lower", extent=[0, 100, 0, 100], aspect="auto",
                       norm=LogNorm(vmin=0.5, vmax=H.max()), cmap="viridis")
        ax.set_title(f"{ano}, {t}º turno: vencedor {VENCEDOR[k]}")
        ax.set_xlabel("comparecimento na seção (%)")
        ax.set_ylabel(f"fatia do {VENCEDOR[k]} nos válidos (%)")
        ax.set_xlim(40, 100)
        fig.colorbar(im, ax=ax, label="seções")
    f = saida / "impressao_digital.png"
    fig.savefig(f, dpi=110, metadata={"Software": None})
    plt.close(fig)
    arquivos.append(f.name)
    fig, ax = plt.subplots(figsize=(8, 5), constrained_layout=True)
    bins = np.linspace(-10, 10, 201)
    for ano, z in swings.items():
        ax.hist(np.clip(z, -10, 10), bins=bins, histtype="step", density=True, log=True, label=f"{ano}: 1º para 2º turno")
    from scipy import stats
    xs = np.linspace(-10, 10, 400)
    ax.plot(xs, stats.norm.pdf(xs), "k--", lw=0.8, label="normal padrão")
    ax.set_ylim(1e-7, 1)
    ax.set_xlabel("resíduo padronizado da fatia do 13 no 2º turno (z)")
    ax.set_ylabel("densidade (log)")
    ax.legend()
    f = saida / "swing_residuos.png"
    fig.savefig(f, dpi=110, metadata={"Software": None})
    plt.close(fig)
    arquivos.append(f.name)
    return arquivos


# --------------------------------------------------------------------------

def analisar(dados: Path, saida: Path, nsim: int, workers: int) -> None:
    saida.mkdir(parents=True, exist_ok=True)
    base = carregar(dados)
    resumo: dict = {"secoes_carregadas": {f"{a}_t{t}": len(x) for (a, t), x in base.items()}}

    # 1. impressão digital
    hists, fp_uf, listas = {}, [], []
    resumo["impressao_digital"] = {}
    for k, df in base.items():
        rj, tab, H, lista = fingerprint(df, *k)
        listas.append(lista)
        resumo["impressao_digital"][f"{k[0]}_t{k[1]}"] = rj
        fp_uf.append(tab)
        hists[k] = H
        print("fingerprint", k, rj["canto_95_95"], rj["inclinacao_fatia_comp_mun"], flush=True)
    pd.concat(fp_uf).to_csv(saida / "impressao_digital_uf.csv", index=False)
    pd.concat(listas).to_csv(saida / "impressao_digital_canto_95_95.csv", index=False)

    # 2. dígitos
    resumo["digitos"] = {}
    tabs = []
    for k, df in base.items():
        rj, tab = digitos(df, *k, nsim=nsim, workers=workers)
        resumo["digitos"][f"{k[0]}_t{k[1]}"] = rj
        tabs.append(tab)
        print("digitos", k, flush=True)
    dig = pd.concat(tabs, ignore_index=True)
    dig.to_parquet(saida / "digitos.parquet", index=False)
    dig.drop(columns=[c for c in dig.columns if c.startswith("fsim")]).to_csv(saida / "digitos.csv", index=False)

    # 3, 4, 6: pares de turnos
    resumo["pareamento"], resumo["swing"], resumo["transferencia"], resumo["comparecimento"] = {}, {}, {}, {}
    zs, secs, agls, concs, zch = {}, [], [], [], {}
    for ano in (2022, 2026):
        p, info = parear(base[(ano, 1)], base[(ano, 2)])
        resumo["pareamento"][str(ano)] = info
        rj, pz, agl = swing(p, ano)
        resumo["swing"][str(ano)] = rj
        zs[ano] = pz.z.to_numpy()
        top = pz.loc[pz.z.abs() > 4, ["chave", "uf", "nm_mun", "zona", "secao", "local", "modelo", "aptos", "comp",
                                       "v13", "v22", "outros", "br", "nu", "comp_2", "v13_2", "v22_2",
                                       "s1", "s2", "pred", "resid", "z"]].assign(ano=ano)
        secs.append(top)
        agls.append(agl)
        resumo["transferencia"][str(ano)] = transferencia(pz, ano)
        zch[ano] = pz.set_index("chave").z
        rc, conc = comparecimento(p, ano)
        resumo["comparecimento"][str(ano)] = rc
        concs.append(conc)
        print("swing", ano, rj["cauda"], flush=True)
    # persistência: a mesma seção (mesma chave) é atípica nos dois anos?
    c = pd.concat([zch[2022].rename("z22"), zch[2026].rename("z26")], axis=1, join="inner")
    pers = {"secoes_mesma_chave": int(len(c)), "corr_z": r(float(np.corrcoef(c.z22, c.z26)[0, 1]), 4)}
    for th in (3, 4, 5):
        m = c.z26.abs() > th
        pers[f"z26_abs_gt_{th}"] = int(m.sum())
        pers[f"z26_abs_gt_{th}_com_z22_abs_gt_3"] = int((c.z22[m].abs() > 3).sum())
        pers[f"z26_abs_gt_{th}_esperado_independente"] = r(float((c.z22.abs() > 3).mean() * m.sum()), 2)
    resumo["swing"]["persistencia_2022_2026"] = pers
    c[(c.z26.abs() > 4) & (c.z22.abs() > 3)].reset_index().to_csv(saida / "swing_persistentes.csv", index=False)
    pd.concat(secs).sort_values("z", key=np.abs, ascending=False).to_csv(saida / "swing_secoes_z4.csv", index=False)
    agl = pd.concat(agls, ignore_index=True)
    agl.to_parquet(saida / "swing_aglomerados.parquet", index=False)
    agl[(agl.nivel != "municipio") & (agl.stouffer.abs() > 4) | (agl.nivel == "municipio") & (agl.z_robusto.abs() > 5)] \
        .to_csv(saida / "swing_aglomerados_atipicos.csv", index=False)
    cc = pd.concat(concs, ignore_index=True)
    cc[["ano", "candidato", "chave", "uf", "nm_mun", "aptos", "comp", "comp_2", "v13", "v22", "v13_2", "v22_2",
        "excesso_comp_pp", "excesso_fatia_pp", "captura"]].to_csv(saida / "comparecimento_concentrado.csv", index=False)

    # 5. dispersão
    resumo["dispersao"] = {}
    tabs = []
    for k, df in base.items():
        rj, tab = dispersao(df, *k)
        rj["referencia_binomial"] = dispersao_simulada(df, 20, 11 + k[0] + k[1])
        resumo["dispersao"][f"{k[0]}_t{k[1]}"] = rj
        tabs.append(tab)
        print("dispersao", k, flush=True)
    disp = pd.concat(tabs, ignore_index=True)
    disp.to_parquet(saida / "dispersao_grupos.parquet", index=False)
    disp[disp.p_subdisperso < 0.001].to_csv(saida / "dispersao_subdispersos.csv", index=False)

    resumo["figuras"] = figuras(hists, saida, zs)
    with open(saida / "resumo.json", "w") as f:
        json.dump(resumo, f, ensure_ascii=False, indent=1, default=lambda o: r(o) if not isinstance(o, (list, dict)) else o)
    print("ok", saida, flush=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("exportar")
    e.add_argument("--dir", type=Path, required=True)
    a = sub.add_parser("analisar")
    a.add_argument("--dados", type=Path, required=True)
    a.add_argument("--saida", type=Path, required=True)
    a.add_argument("--sims", type=int, default=400)
    a.add_argument("--workers", type=int, default=min(48, os.cpu_count() or 4))
    args = ap.parse_args()
    if args.cmd == "exportar":
        exportar(args.dir)
    else:
        analisar(args.dados, args.saida, args.sims, args.workers)


if __name__ == "__main__":
    sys.exit(main())
