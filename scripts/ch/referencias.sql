-- Carrega as tabelas de referência (1º turno de 2026 e 2022) a partir dos Parquet
-- copiados para ~/dataurnas-ch/ref no servidor (visíveis no contêiner em
-- /var/lib/clickhouse/user_files/ref). Recarrega do zero: pode ser reaplicado.
--
--   docker exec -i dataurnas-clickhouse clickhouse-client --user dataurnas \
--     --password "$(cat ~/dataurnas-ch/.senha)" --multiquery < scripts/ch/referencias.sql

TRUNCATE TABLE IF EXISTS dataurnas.ref_secoes_2026_t1;
INSERT INTO dataurnas.ref_secoes_2026_t1
SELECT uf, cd_mun, nm_mun, zona, secao, status, secao_principal, secoes_agregadas,
       st_secao, hash, st_hash, n_hashes, dt_recebimento, hr_recebimento, spec_version,
       municipio_bu, zona_bu, secao_bu, local_votacao,
       parseDateTimeOrNull(data_hora_emissao, '%Y%m%dT%H%i%s', 'UTC'),
       parseDateTimeOrNull(hora_abertura, '%Y%m%dT%H%i%s', 'UTC'),
       parseDateTimeOrNull(hora_encerramento, '%Y%m%dT%H%i%s', 'UTC'),
       tipo_urna, versao_votacao, numero_interno_urna, codigo_carga, qtd_codigos_carga,
       fase, modelo_urna_cod, modelo_urna, aptos, aptos_secao, aptos_tte, comparecimento,
       comparecimento_bu, comp_sem_biometria, habilitados_biometria, habilitados_biografia,
       votos_nominais, votos_legenda, votos_brancos, votos_nulos, votos_total,
       tem_presidente, origem_bu
FROM file('ref/2026/secoes_2026.parquet', Parquet);

TRUNCATE TABLE IF EXISTS dataurnas.ref_votos_2026_t1;
INSERT INTO dataurnas.ref_votos_2026_t1
SELECT uf, cd_mun, zona, secao, tipo_voto, ifNull(numero, 0), partido, votos
FROM file('ref/2026/votos_presidente_2026.parquet', Parquet);

TRUNCATE TABLE IF EXISTS dataurnas.ref_resultado_municipio_2026_t1;
INSERT INTO dataurnas.ref_resultado_municipio_2026_t1
SELECT uf, cd_mun, cd_ibge, nome, capital, secoes_total, secoes_totalizadas, eleitorado,
       comparecimento, votos_total, votos_validos, votos_brancos, votos_nulos_total,
       data_totalizacao, hora_totalizacao, v_13, v_22
FROM file('ref/2026/resultado_municipio.parquet', Parquet);

TRUNCATE TABLE IF EXISTS dataurnas.ref_secoes_2022;
INSERT INTO dataurnas.ref_secoes_2022
SELECT turno, uf, regiao, municipio, zona, secao, ifNull(modelo_urna, ''),
       ifNull(tipo_urna, ''), ifNull(versao_sw, ''), ifNull(fuso_offset, 0),
       ifNull(emissao, ''), ifNull(eleitores_aptos, 0), ifNull(comparecimento, 0),
       ifNull(comp_biometrico, 0),
       parseDateTimeOrNull(hora_abertura, '%d/%m/%Y %H:%i:%s', 'UTC'),
       parseDateTimeOrNull(hora_encerramento, '%d/%m/%Y %H:%i:%s', 'UTC'),
       ifNull(duracao_min, 0), ifNull(reboots, 0), ifNull(is_reserva, false),
       ifNull(n_issues, 0)
FROM file('ref/2022/secoes.parquet', Parquet);

TRUNCATE TABLE IF EXISTS dataurnas.ref_votos_2022;
INSERT INTO dataurnas.ref_votos_2022
SELECT toUInt8(substring(p[1], 1, 1)) AS turno, p[2], p[3], p[4], p[5],
       tipo_voto, ifNull(codigo_candidato, 0), partido, quantidade
FROM
(
    SELECT splitByChar('/', secao_id) AS p, tipo_voto, codigo_candidato, partido, quantidade
    FROM file('ref/2022/votos_{t1_a,t1_b,t2}.parquet', Parquet)
    WHERE codigo_cargo = 1
);
