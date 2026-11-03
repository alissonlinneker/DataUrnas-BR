"""Curva acumulada da fatia do 22 na ordem de chegada das seções (2022 e 2026).

Mede viradas de liderança na ordem real, em 3.000 ordens aleatórias e em ordens
embaralhadas só dentro da mesma janela de tempo (1, 10 e 30 min), e lista os
maiores vales da curva com o município que domina cada bloco. Roda no London
sobre a exportação de scripts/ele2026/ordem_envio_ch.sql; saída em resultado.json.
"""
import json
import numpy as np
import pandas as pd
from multiprocessing import Pool

def viradas(d13, d22):
    s = np.sign(np.cumsum(d22) - np.cumsum(d13))
    s = s[s != 0]
    m = np.nonzero(s[1:] != s[:-1])[0]
    return len(m), (int(m[-1]) + 1 if len(m) else 0)

def perm_aleatoria(args):
    seed, v13, v22 = args
    r = np.random.default_rng(seed)
    out = []
    for _ in range(100):
        p = r.permutation(len(v13))
        out.append(viradas(v13[p], v22[p]))
    return out

def perm_janela(args):
    seed, v13, v22, jan = args
    r = np.random.default_rng(seed)
    out = []
    for _ in range(50):
        k = np.lexsort((r.random(len(v13)), jan))
        out.append(viradas(v13[k], v22[k]))
    return out

def analisar(ano, arq, pool):
    df = pd.read_parquet(arq)
    df = df.dropna(subset=["envio"]).sort_values(["envio", "uf", "cd_mun", "zona", "secao"]).reset_index(drop=True)
    v13, v22 = df.v13.to_numpy(np.int64), df.v22.to_numpy(np.int64)
    n = len(df)
    c13, c22 = np.cumsum(v13), np.cumsum(v22)
    pct22 = c22 / np.maximum(c13 + c22, 1)
    nv, ult = viradas(v13, v22)
    r = {"ano": ano, "secoes": n, "soma_13": int(c13[-1]), "soma_22": int(c22[-1]),
         "pct22_final": round(float(pct22[-1]) * 100, 3),
         "pct22_max_apos_1000": round(float(pct22[1000:].max()) * 100, 2),
         "real_viradas": nv, "real_ultima_virada_secao": ult,
         "real_ultima_virada_hora": str(df.envio.iloc[ult]) if ult else None}
    res = [x for b in pool.map(perm_aleatoria, [(s, v13, v22) for s in range(30)]) for x in b]
    a = np.array(res)
    r["aleatorio_3000"] = {"viradas_media": round(float(a[:, 0].mean()), 1), "viradas_mediana": float(np.median(a[:, 0])),
        "viradas_min": int(a[:, 0].min()), "viradas_max": int(a[:, 0].max()),
        "pct_com_1_virada_ou_menos": round(float((a[:, 0] <= 1).mean()) * 100, 1),
        "ultima_virada_mediana_secao": float(np.median(a[:, 1])), "ultima_virada_p99_secao": float(np.percentile(a[:, 1], 99))}
    for minutos in (1, 10, 30):
        jan = pd.factorize(df.envio.dt.floor(f"{minutos}min"))[0]
        res = [x for b in pool.map(perm_janela, [(s, v13, v22, jan) for s in range(20)]) for x in b]
        a = np.array(res)
        r[f"embaralhado_dentro_de_{minutos}min_1000"] = {"viradas_media": round(float(a[:, 0].mean()), 2),
            "viradas_min": int(a[:, 0].min()), "viradas_max": int(a[:, 0].max()),
            "ultima_virada_mediana_secao": float(np.median(a[:, 1]))}
    # agrupamento: seções consecutivas do mesmo município
    mun = (df.uf + df.cd_mun.astype(str)).to_numpy()
    r["mesmo_municipio_que_a_anterior_pct_real"] = round(float((mun[1:] == mun[:-1]).mean()) * 100, 1)
    p = np.random.default_rng(1).permutation(n)
    r["mesmo_municipio_que_a_anterior_pct_aleatorio"] = round(float((mun[p][1:] == mun[p][:-1]).mean()) * 100, 2)
    # vales: quedas de pct22 em janelas de 300 seções depois da secao 20 mil
    w = 300
    dlt = pct22[w:] - pct22[:-w]
    idx = np.arange(w, n)
    sel = idx >= 20000
    ordem = np.argsort(dlt[sel])
    usados, vales = [], []
    for j in ordem:
        i = int(idx[sel][j])
        if any(abs(i - u) < w for u in usados):
            continue
        usados.append(i)
        bloco = df.iloc[i - w:i]
        top = (bloco.uf + "-" + bloco.cd_mun.astype(str)).value_counts()
        b13, b22 = int(bloco.v13.sum()), int(bloco.v22.sum())
        vales.append({"secao_fim": i, "hora": str(df.envio.iloc[i]), "queda_pp": round(float(dlt[sel][j]) * 100, 3),
                      "pct22_no_bloco": round(b22 / max(b13 + b22, 1) * 100, 1),
                      "municipio_dominante": top.index[0], "secoes_dele_no_bloco": int(top.iloc[0])})
        if len(vales) == 15:
            break
    r["maiores_vales"] = vales
    curva = pd.DataFrame({"i": np.arange(n), "pct22": pct22, "envio": df.envio, "uf": df.uf, "cd_mun": df.cd_mun})
    curva.iloc[::50].to_parquet(f"curva_{ano}.parquet")
    return r

if __name__ == "__main__":
    with Pool(60) as pool:
        out = [analisar(2022, "o2022.parquet", pool), analisar(2026, "o2026.parquet", pool)]
    json.dump(out, open("resultado.json", "w"), ensure_ascii=False, indent=1, default=str)
    print(json.dumps(out, ensure_ascii=False, default=str)[:200])
