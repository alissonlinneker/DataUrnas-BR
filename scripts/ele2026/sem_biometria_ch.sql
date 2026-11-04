-- Section-level export for scripts/ele2026/sem_biometria_probabilidade.py.
-- One row per section present in both rounds of 2026, with the three BU
-- enabling counts of each round (DetalhamentoComparecimento, spec v2) and the
-- presidential votes of 13 and 22 in each round.
-- Usage on the server: ch.sh < sem_biometria_ch.sql > sem_bio_2026.parquet
SELECT
    t2.uf AS uf, t2.cd_mun AS cd_mun, t2.zona AS zona, t2.secao AS secao,
    t1.aptos AS aptos_1, t2.aptos AS aptos_2,
    t1.comparecimento_bu AS comp_1, t2.comparecimento_bu AS comp_2,
    t1.comp_sem_biometria AS sem_bio_1, t2.comp_sem_biometria AS sem_bio_2,
    t1.habilitados_biometria AS hab_bio_1, t2.habilitados_biometria AS hab_bio_2,
    t1.habilitados_biografia AS hab_biog_1, t2.habilitados_biografia AS hab_biog_2,
    c.votos_13_t1 AS v13_1, c.votos_22_t1 AS v22_1,
    c.votos_13_t2 AS v13_2, c.votos_22_t2 AS v22_2
FROM dataurnas.v_bu_ultima AS t2
INNER JOIN (SELECT * FROM dataurnas.ref_secoes_2026_t1 WHERE tem_presidente) AS t1
    USING (uf, cd_mun, zona, secao)
INNER JOIN dataurnas.v_comparacao_t1_t2 AS c USING (uf, cd_mun, zona, secao)
WHERE t2.uf != 'zz'
  AND t1.comp_sem_biometria IS NOT NULL AND t2.comp_sem_biometria IS NOT NULL
FORMAT Parquet;
