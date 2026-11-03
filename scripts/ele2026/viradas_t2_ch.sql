-- Exporta do ClickHouse o 2º turno de 2026 no formato de
-- data/parquet/2026/t2/encerramento/secoes_encerramento.parquet, para que
-- scripts/ele2026/viradas_t1_t2.py rode com todas as seções do país.
--
-- Uma linha por seção do Brasil (última versão de BU, v_bu_ultima; o exterior,
-- 'zz', fica de fora como no relatório de encerramento), com votos da última
-- versão (bu_votos), horários convertidos para Brasília pelo mesmo critério de
-- analisar_encerramento_t2.py (FUSO_UF e FUSO_MUNICIPIO) e, para o número
-- interno da urna e o código de carga, as colunas do próprio BU.
--
-- Uso (no servidor, saída em memória):
--   ~/dataurnas-ch/app/scripts/ch/ch.sh < viradas_t2_ch.sql > secoes_encerramento.parquet
WITH
    v AS (
        SELECT uf, cd_mun, zona, secao, sha512_bu,
               sumIf(votos, tipo_voto = 'nominal' AND numero = 13) AS votos_13,
               sumIf(votos, tipo_voto = 'nominal' AND numero = 22) AS votos_22,
               sumIf(votos, tipo_voto = 'nominal' AND numero NOT IN (13, 22)) AS votos_outros_nominais,
               sumIf(votos, tipo_voto = 'branco') AS votos_brancos,
               sumIf(votos, tipo_voto = 'nulo') AS votos_nulos,
               sum(votos) AS votos_total_cargo
        FROM dataurnas.bu_votos FINAL
        GROUP BY uf, cd_mun, zona, secao, sha512_bu
    ),
    n AS (SELECT uf, cd_mun, zona, secao, versoes FROM dataurnas.v_bu_versoes_por_secao)
SELECT
    toString(u.uf) AS uf, u.cd_mun AS cd_mun, '' AS municipio, u.zona AS zona, u.secao AS secao,
    toString(u.tipo_arquivo) AS tipo_arquivo, '' AS nome_arquivo, u.hash AS hash, u.sha512 AS sha512,
    toString(u.st_secao) AS st_secao,
    toInt64(u.fuso) AS fuso_utc,
    formatDateTime(u.hora_abertura, '%Y-%m-%d %H:%i:%S') AS abertura_local,
    formatDateTime(u.hora_encerramento, '%Y-%m-%d %H:%i:%S') AS encerramento_local,
    formatDateTime(u.hora_encerramento + toIntervalHour(-3 - u.fuso), '%Y-%m-%d %H:%i:%S')
        AS encerramento_bsb,
    toString(u.tipo_urna) AS tipo_urna,
    toInt64(ifNull(u.aptos, 0)) AS aptos,
    toInt64(ifNull(u.comparecimento, 0)) AS comparecimento,
    toInt64(v.votos_13) AS votos_13, toInt64(v.votos_22) AS votos_22,
    toInt64(v.votos_outros_nominais) AS votos_outros_nominais,
    toInt64(v.votos_brancos) AS votos_brancos, toInt64(v.votos_nulos) AS votos_nulos,
    toInt64(v.votos_total_cargo) AS votos_total,
    v.sha512_bu != '' AS tem_presidente,
    CAST(NULL AS Nullable(String)) AS erro_decodificacao,
    round(dateDiff('second', toDateTime('2026-10-25 17:00:00', 'UTC'),
                   u.hora_encerramento + toIntervalHour(-3 - u.fuso)) / 60.0, 2)
        AS minutos_apos_17h_bsb,
    toInt64(n.versoes) AS n_versoes_bu,
    u.numero_interno_urna AS numero_interno_urna,
    u.codigo_carga AS codigo_carga
FROM (
    SELECT *,
           multiIf(
               cd_mun IN ('02020', '02054', '02135', '02291', '02313', '02399', '02496',
                          '02755', '02917', '98370', '98477'), -5,
               cd_mun = '30015', -2,
               uf = 'ac', -5,
               uf IN ('am', 'mt', 'ms', 'ro', 'rr'), -4,
               -3) AS fuso
    FROM dataurnas.v_bu_ultima
    WHERE uf != 'zz'
) AS u
LEFT JOIN v ON v.uf = u.uf AND v.cd_mun = u.cd_mun AND v.zona = u.zona
           AND v.secao = u.secao AND v.sha512_bu = u.sha512
LEFT JOIN n ON n.uf = u.uf AND n.cd_mun = u.cd_mun AND n.zona = u.zona AND n.secao = u.secao
ORDER BY uf, cd_mun, zona, secao
SETTINGS join_use_nulls = 0
FORMAT Parquet;
