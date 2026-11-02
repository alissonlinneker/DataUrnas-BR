-- Biometria por seção, 1º turno (04/10/2026) x 2º turno (25/10/2026), Presidente.
-- Fonte: BU (DetalhamentoComparecimento da spec v2 do BU, ver spec/v2/bu.asn1).
--   T1: dataurnas.ref_secoes_2026_t1 (carregada de data/parquet/2026/secoes_2026.parquet)
--   T2: dataurnas.v_bu_ultima (última versão publicada de cada seção)
-- Uma linha por seção do 2º turno, com o 1º turno da mesma seção ao lado.
-- hora_encerramento é hora LOCAL rotulada como UTC: sai como texto, sem conversão.
-- Uso no servidor: ch.sh < biometria_t1_t2_ch.sql > secoes_biometria.parquet
SELECT
    t2.uf AS uf, t2.cd_mun AS cd_mun, t2.zona AS zona, t2.secao AS secao,
    t1.status AS status_1, t1.hash AS hash_1, t1.tipo_urna AS tipo_urna_1,
    t1.modelo_urna AS modelo_urna_1, t1.numero_interno_urna AS numero_interno_urna_1,
    t1.aptos AS aptos_1, t1.comparecimento_bu AS comp_1,
    t1.comp_sem_biometria AS sem_bio_1, t1.habilitados_biometria AS hab_bio_1,
    t1.habilitados_biografia AS hab_biog_1,
    formatDateTime(t1.hora_encerramento, '%H:%i:%S') AS encerramento_local_1,
    t2.hash AS hash_2, t2.tipo_arquivo AS tipo_arquivo_2, t2.tipo_urna AS tipo_urna_2,
    t2.numero_interno_urna AS numero_interno_urna_2,
    t2.aptos AS aptos_2, t2.comparecimento_bu AS comp_2,
    t2.comp_sem_biometria AS sem_bio_2, t2.habilitados_biometria AS hab_bio_2,
    t2.habilitados_biografia AS hab_biog_2,
    formatDateTime(t2.hora_encerramento, '%H:%i:%S') AS encerramento_local_2
FROM dataurnas.v_bu_ultima AS t2
LEFT JOIN
(
    SELECT * FROM dataurnas.ref_secoes_2026_t1 WHERE tem_presidente
) AS t1 USING (uf, cd_mun, zona, secao)
SETTINGS join_use_nulls = 1
FORMAT Parquet;
