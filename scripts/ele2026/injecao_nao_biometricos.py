"""Quick test: does the 1T->2T turnout change look like injected non-biometric votes?"""
import sys

import numpy as np
import pandas as pd

d = pd.read_parquet(sys.argv[1])
d = d[(d.pareada) & (d.tem_det_1) & (d.tem_det_2) & (d.aptos_1 > 0)].copy()
d["nb_1"] = d.sem_bio_1 + d.hab_biog_1
d["nb_2"] = d.sem_bio_2 + d.hab_biog_2
d["d_comp"] = d.comp_2 - d.comp_1
d["d_nb"] = d.nb_2 - d.nb_1
d["d_bio"] = d.hab_bio_2 - d.hab_bio_1
d["d13"] = d.v13_2 - d.v13_1
d["d22"] = d.v22_2 - d.v22_1
print("secoes", len(d))
print("delta comparecimento", d.d_comp.sum(), "delta nao biometrico", d.d_nb.sum(), "delta biometrico", d.d_bio.sum())
print("parcela nao biometrica: 1T %.4f 2T %.4f" % (d.nb_1.sum() / d.comp_1.sum(), d.nb_2.sum() / d.comp_2.sum()))

# turnout extremes
for col, a in (("comp_1", "aptos_1"), ("comp_2", "aptos_2")):
    t = d[col] / d[a]
    print(col, ">=98%:", int((t >= 0.98).sum()), " 100%:", int((t >= 1).sum()))

# within-municipality: do sections that gained more non-biometric voters gain more votes for one side?
g = d.groupby(["uf", "cd_mun"])
for v in ("d_nb", "d_bio", "d13", "d22"):
    d[v + "_w"] = (d[v] / d.aptos_1) - g[v].transform("sum") / g["aptos_1"].transform("sum")
for y in ("d13", "d22"):
    x = d.d_nb_w
    b = np.polyfit(x, d[y + "_w"], 1)[0]
    print(f"{y} por eleitor nao biometrico extra (dentro do municipio): {b:.3f}  corr={np.corrcoef(x, d[y + '_w'])[0, 1]:.4f}")
    x = d.d_bio_w
    b = np.polyfit(x, d[y + "_w"], 1)[0]
    print(f"{y} por eleitor biometrico extra (dentro do municipio): {b:.3f}  corr={np.corrcoef(x, d[y + '_w'])[0, 1]:.4f}")

# sections with a big jump in non-biometric voters
d["j"] = d.d_nb / d.aptos_1
top = d[d.j >= 0.15]
print("secoes com +15 pontos de nao biometricos:", len(top), "fatia13 1T %.4f 2T %.4f" % (
    top.v13_1.sum() / (top.v13_1.sum() + top.v22_1.sum()), top.v13_2.sum() / (top.v13_2.sum() + top.v22_2.sum())))
print("pais fatia13 1T %.4f 2T %.4f" % (d.v13_1.sum() / (d.v13_1.sum() + d.v22_1.sum()), d.v13_2.sum() / (d.v13_2.sum() + d.v22_2.sum())))
print("modelo das secoes com salto:", top.modelo_urna_1.value_counts().head(4).to_dict())
