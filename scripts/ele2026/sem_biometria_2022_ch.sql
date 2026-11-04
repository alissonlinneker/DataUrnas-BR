-- 2022 control for scripts/ele2026/sem_biometria_probabilidade.py.
-- One row per section present in both rounds of 2022 with turnout, the BU v1
-- count of voters enabled by fingerprint (qtdEleitoresCompBiometrico) and the
-- presidential votes of 13 and 22 in each round.
-- Usage on the server: ch.sh < sem_biometria_2022_ch.sql > sem_bio_2022.parquet
WITH v AS (
    SELECT turno, uf, cd_mun, zona, secao,
           sumIf(votos, numero = 13) AS v13, sumIf(votos, numero = 22) AS v22
    FROM dataurnas.ref_votos_2022
    GROUP BY turno, uf, cd_mun, zona, secao
),
s AS (
    SELECT s.turno AS turno, s.uf AS uf, s.cd_mun AS cd_mun, s.zona AS zona, s.secao AS secao,
           s.eleitores_aptos AS aptos, s.comparecimento AS comp, s.comp_biometrico AS bio,
           v.v13 AS v13, v.v22 AS v22
    FROM dataurnas.ref_secoes_2022 AS s
    INNER JOIN v USING (turno, uf, cd_mun, zona, secao)
)
SELECT a.uf AS uf, a.cd_mun AS cd_mun, a.zona AS zona, a.secao AS secao,
       a.aptos AS aptos_1, b.aptos AS aptos_2, a.comp AS comp_1, b.comp AS comp_2,
       a.bio AS bio_1, b.bio AS bio_2,
       a.v13 AS v13_1, a.v22 AS v22_1, b.v13 AS v13_2, b.v22 AS v22_2
FROM (SELECT * FROM s WHERE turno = 1) AS a
INNER JOIN (SELECT * FROM s WHERE turno = 2) AS b USING (uf, cd_mun, zona, secao)
WHERE a.uf != 'zz'
FORMAT Parquet;
