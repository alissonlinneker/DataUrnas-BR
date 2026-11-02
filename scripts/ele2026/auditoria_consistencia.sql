-- Auditoria de consistência interna e de valores impossíveis nos BUs de 2026
-- (Presidente, 1º turno de 04/10/2026 e 2º turno de 25/10/2026).
--
-- Relatório: docs/auditoria-consistencia-bu-2026.md
--
-- Como rodar (no servidor de processamento, banco ClickHouse `dataurnas`):
--   ssh <servidor> '~/dataurnas-ch/app/scripts/ch/ch.sh' < scripts/ele2026/auditoria_consistencia.sql
-- O arquivo usa tabelas temporárias e precisa rodar inteiro, numa sessão só.
--
-- Fontes:
--   2º turno: v_bu_ultima (uma versão de BU por seção), v_votos_t2_secao, bu_votos
--   1º turno: ref_secoes_2026_t1, ref_votos_2026_t1, v_votos_t1_secao,
--             ref_resultado_municipio_2026_t1 (resultado oficial por município)
--   2022:     ref_secoes_2022, ref_votos_2022 (linha de base)
--
-- Convenção de horário: hora_abertura, hora_encerramento e data_hora_emissao
-- estão no relógio LOCAL da urna, gravados como DateTime('UTC'). Não usar
-- toTimeZone. Para levar ao horário de Brasília soma-se o deslocamento do fuso
-- (expressão `off` abaixo, mesma tabela de scripts/ele2026/analisar_encerramento_t2.py).
-- O exterior (uf = 'zz') fica no horário de cada país e não é convertido.

-- ---------------------------------------------------------------------------
-- 0. Panorama: tipos de BU, fase, versão de software
-- ---------------------------------------------------------------------------

SELECT tipo_arquivo, tipo_urna, fase, spec_version, versao_votacao, count() AS secoes
FROM v_bu_ultima
GROUP BY ALL
ORDER BY secoes DESC;

SELECT status, tipo_urna, fase, origem_bu, count() AS secoes
FROM ref_secoes_2026_t1
GROUP BY ALL
ORDER BY secoes DESC;

-- Uma versão de BU por seção no 2º turno e SHA-512 únicos
SELECT count() AS versoes, uniqExact(uf, cd_mun, zona, secao) AS secoes,
       countIf(erro != '') AS com_erro
FROM bu_secao FINAL;

SELECT count() AS secoes, uniqExact(sha512) AS sha512_distintos FROM v_bu_ultima;

-- ---------------------------------------------------------------------------
-- 1. Valores impossíveis e somas internas, por turno
-- ---------------------------------------------------------------------------

-- 1a. 2º turno
SELECT
    count()                                                         AS secoes,
    countIf(comparecimento > aptos)                                 AS comp_maior_aptos,
    countIf(comparecimento_bu > aptos)                              AS comp_bu_maior_aptos,
    countIf(votos_total != comparecimento)                          AS total_cargo_dif_comp,
    countIf(votos_nominais + votos_legenda + votos_brancos + votos_nulos != votos_total)
                                                                    AS soma_tipos_dif_total,
    countIf(aptos != aptos_secao + ifNull(aptos_tte, 0))            AS aptos_dif_secao_mais_tte,
    countIf(comp_sem_biometria > comparecimento_bu)                 AS sem_bio_maior_comp,
    countIf(habilitados_biometria + habilitados_biografia > aptos)  AS habilitados_maior_aptos,
    countIf(votos_legenda != 0)                                     AS com_voto_legenda,
    countIf(comparecimento != comparecimento_bu)                    AS comp_cargo_dif_comp_bu,
    countIf(municipio_bu != toInt32(cd_mun) OR zona_bu != toInt32(zona)
            OR secao_bu != toInt32(secao))                          AS identificacao_diverge,
    countIf(comparecimento = aptos)                                 AS comp_100,
    countIf(comparecimento >= 0.98 * aptos)                         AS comp_98,
    countIf(comparecimento = 0)                                     AS comp_zero,
    min(aptos), max(aptos), max(comparecimento)
FROM v_bu_ultima;

SELECT count() AS linhas_voto_negativo FROM bu_votos FINAL WHERE votos < 0;

-- Votos por tipo e número na última versão de cada seção (só 13, 22, branco e nulo)
SELECT tipo_voto, numero, count() AS linhas, sum(votos) AS votos
FROM bu_votos FINAL
WHERE sha512_bu IN (SELECT sha512 FROM v_bu_ultima)
GROUP BY ALL
ORDER BY tipo_voto, numero;

-- Soma por candidato = total do BU = comparecimento, seção a seção
SELECT count() AS secoes,
       countIf(v.total != u.votos_total)                  AS soma_dif_total,
       countIf(v.total != u.comparecimento)               AS soma_dif_comp,
       countIf(v.votos_13 + v.votos_22 != u.votos_nominais) AS nominais_dif,
       countIf(v.brancos != u.votos_brancos)              AS brancos_dif,
       countIf(v.nulos != u.votos_nulos)                  AS nulos_dif
FROM v_votos_t2_secao AS v
INNER JOIN v_bu_ultima AS u USING (uf, cd_mun, zona, secao);

-- 1b. 1º turno
SELECT
    count()                                                         AS secoes,
    countIf(comparecimento > aptos)                                 AS comp_maior_aptos,
    countIf(comparecimento_bu > aptos)                              AS comp_bu_maior_aptos,
    countIf(votos_total != comparecimento)                          AS total_cargo_dif_comp,
    countIf(votos_nominais + votos_legenda + votos_brancos + votos_nulos != votos_total)
                                                                    AS soma_tipos_dif_total,
    countIf(aptos != aptos_secao + ifNull(aptos_tte, 0))            AS aptos_dif_secao_mais_tte,
    countIf(comp_sem_biometria > comparecimento_bu)                 AS sem_bio_maior_comp,
    countIf(habilitados_biometria + habilitados_biografia > aptos)  AS habilitados_maior_aptos,
    countIf(comparecimento != comparecimento_bu)                    AS comp_cargo_dif_comp_bu,
    countIf(municipio_bu != toInt32(cd_mun) OR zona_bu != toInt32(zona)
            OR secao_bu != toInt32(secao))                          AS identificacao_diverge,
    countIf(comparecimento = aptos)                                 AS comp_100,
    countIf(comparecimento >= 0.98 * aptos)                         AS comp_98,
    countIf(comparecimento = 0)                                     AS comp_zero
FROM ref_secoes_2026_t1
WHERE status = 'ok';

SELECT count() AS linhas_voto_negativo FROM ref_votos_2026_t1 WHERE votos < 0;

SELECT tipo_voto, numero, count() AS linhas, sum(votos) AS votos
FROM ref_votos_2026_t1
GROUP BY ALL
ORDER BY tipo_voto, numero;

SELECT count() AS secoes,
       countIf(v.total != s.votos_total)    AS soma_dif_total,
       countIf(v.total != s.comparecimento) AS soma_dif_comp,
       countIf(v.votos_13 + v.votos_22 + v.votos_outros != s.votos_nominais) AS nominais_dif,
       countIf(v.brancos != s.votos_brancos) AS brancos_dif,
       countIf(v.nulos != s.votos_nulos)     AS nulos_dif
FROM v_votos_t1_secao AS v
INNER JOIN ref_secoes_2026_t1 AS s USING (uf, cd_mun, zona, secao);

-- ---------------------------------------------------------------------------
-- 2. BUs de contingência (busa, Sistema de Apuração) e coerência dos votos
-- ---------------------------------------------------------------------------

SELECT tipo_arquivo, tipo_urna, count() AS secoes,
       countIf(municipio_bu != toInt32(cd_mun) OR zona_bu != toInt32(zona)
               OR secao_bu != toInt32(secao)) AS identificacao_diverge,
       countIf(comparecimento != comparecimento_bu) AS comp_dif
FROM v_bu_ultima
GROUP BY ALL;

SELECT uf, cd_mun, zona, secao, tipo_arquivo, tipo_urna, municipio_bu, zona_bu, secao_bu,
       aptos, comparecimento, comparecimento_bu, votos_total, numero_interno_urna,
       hora_abertura, hora_encerramento, data_hora_emissao
FROM v_bu_ultima
WHERE tipo_arquivo = 'busa'
ORDER BY uf, cd_mun, zona, secao;

SELECT tipo_urna, origem_bu, uf = 'zz' AS exterior, count() AS secoes,
       countIf(comparecimento != comparecimento_bu) AS comp_dif,
       countIf(secao_bu != toInt32(secao)) AS secao_bu_dif,
       groupUniqArray(numero_interno_urna) AS equipamentos
FROM ref_secoes_2026_t1
WHERE status = 'ok' AND tipo_urna = 'contingencia'
GROUP BY ALL;

-- Contingência nos dois turnos (mesmas seções?)
SELECT countIf(t1c AND t2c) AS nos_dois, countIf(t1c AND NOT t2c) AS so_t1,
       countIf(NOT t1c AND t2c) AS so_t2
FROM
(
    SELECT a.tipo_urna = 'contingencia' AS t1c, b.tipo_urna = 'contingencia' AS t2c
    FROM (SELECT * FROM ref_secoes_2026_t1 WHERE status = 'ok') AS a
    INNER JOIN v_bu_ultima AS b USING (uf, cd_mun, zona, secao)
);

-- Seções com contingência em algum turno: votos e comparecimento nos dois turnos
SELECT c.uf, c.cd_mun, m.nome, c.zona, c.secao, c.aptos_t1, c.aptos_t2,
       c.comparecimento_t1, c.comparecimento_t2, c.votos_13_t1, c.votos_22_t1,
       c.votos_outros_t1, c.brancos_nulos_t1, c.votos_13_t2, c.votos_22_t2, c.brancos_nulos_t2
FROM v_comparacao_t1_t2 AS c
LEFT JOIN ref_resultado_municipio_2026_t1 AS m USING (uf, cd_mun)
WHERE (uf, cd_mun, zona, secao) IN
      (SELECT uf, cd_mun, zona, secao FROM ref_secoes_2026_t1 WHERE tipo_urna = 'contingencia')
ORDER BY c.uf, c.cd_mun, c.zona, c.secao;

-- Belo Horizonte 0039/0168 (contingência no 1º turno): seções do mesmo local
SELECT a.secao, a.aptos, a.comparecimento AS comp_t1, b.comparecimento AS comp_t2, a.tipo_urna,
       round(a.comparecimento / a.aptos, 3) AS pct_t1, round(b.comparecimento / b.aptos, 3) AS pct_t2
FROM ref_secoes_2026_t1 AS a
INNER JOIN v_bu_ultima AS b USING (uf, cd_mun, zona, secao)
WHERE uf = 'mg' AND cd_mun = '41238' AND zona = '0039'
  AND a.local_votacao = (SELECT local_votacao FROM v_bu_ultima
                         WHERE uf = 'mg' AND cd_mun = '41238' AND zona = '0039' AND secao = '0168')
ORDER BY secao;

SELECT turno, uf, cd_mun, zona, secao, tipo_urna, eleitores_aptos, comparecimento
FROM ref_secoes_2022
WHERE (uf, cd_mun, zona, secao) IN (('mg', '41238', '0039', '0168'), ('mg', '50075', '0047', '0041'))
ORDER BY uf, cd_mun, zona, secao, turno;

-- ---------------------------------------------------------------------------
-- 3. Comparecimento de 100% ou perto disso
-- ---------------------------------------------------------------------------

SELECT u.uf, u.cd_mun, u.zona, u.secao, u.tipo_urna, u.aptos, u.aptos_tte, u.comparecimento,
       u.comp_sem_biometria, u.habilitados_biometria, u.habilitados_biografia,
       v.votos_13, v.votos_22, v.brancos, v.nulos,
       c.aptos_t1, c.comparecimento_t1
FROM v_bu_ultima AS u
INNER JOIN v_votos_t2_secao AS v USING (uf, cd_mun, zona, secao)
LEFT JOIN v_comparacao_t1_t2 AS c USING (uf, cd_mun, zona, secao)
WHERE u.comparecimento >= 0.98 * u.aptos
ORDER BY u.comparecimento / u.aptos DESC, u.uf;

SELECT uf, cd_mun, zona, secao, aptos, aptos_tte, comparecimento, comp_sem_biometria
FROM ref_secoes_2026_t1
WHERE status = 'ok' AND comparecimento = aptos
ORDER BY uf, cd_mun, zona, secao;

-- Linha de base 2022
SELECT turno,
       countIf(comparecimento = eleitores_aptos AND eleitores_aptos > 0) AS comp_100,
       countIf(comparecimento >= 0.98 * eleitores_aptos AND eleitores_aptos > 0) AS comp_98,
       count() AS secoes
FROM ref_secoes_2022
GROUP BY turno
ORDER BY turno;

-- Variação de comparecimento entre turnos (pontos), 2026 e 2022, seções com 50 aptos ou mais
WITH d26 AS (SELECT comparecimento_t2 / aptos_t2 - comparecimento_t1 / aptos_t1 AS dp
             FROM v_comparacao_t1_t2 WHERE uf != 'zz' AND aptos_t2 >= 50),
     d22 AS (SELECT b.comparecimento / b.eleitores_aptos - a.comparecimento / a.eleitores_aptos AS dp
             FROM ref_secoes_2022 AS a
             INNER JOIN ref_secoes_2022 AS b USING (uf, cd_mun, zona, secao)
             WHERE a.turno = 1 AND b.turno = 2 AND a.uf != 'zz'
               AND b.eleitores_aptos >= 50 AND a.eleitores_aptos > 0)
SELECT '2026' AS ano, count() AS secoes, countIf(dp <= -0.30) AS queda_30, countIf(dp <= -0.20) AS queda_20,
       countIf(dp >= 0.20) AS alta_20, countIf(dp >= 0.30) AS alta_30 FROM d26
UNION ALL
SELECT '2022', count(), countIf(dp <= -0.30), countIf(dp <= -0.20), countIf(dp >= 0.20), countIf(dp >= 0.30) FROM d22;

SELECT c.uf, c.cd_mun, m.nome, c.zona, c.secao, c.aptos_t1, c.comparecimento_t1, c.aptos_t2,
       c.comparecimento_t2, round(c.comparecimento_t1 / c.aptos_t1, 3) AS pct_t1,
       round(c.comparecimento_t2 / c.aptos_t2, 3) AS pct_t2, u.tipo_urna, u.hora_abertura
FROM v_comparacao_t1_t2 AS c
INNER JOIN v_bu_ultima AS u USING (uf, cd_mun, zona, secao)
LEFT JOIN ref_resultado_municipio_2026_t1 AS m USING (uf, cd_mun)
WHERE c.uf != 'zz' AND c.aptos_t2 >= 50
  AND abs(c.comparecimento_t2 / c.aptos_t2 - c.comparecimento_t1 / c.aptos_t1) >= 0.30
ORDER BY c.comparecimento_t2 / c.aptos_t2 - c.comparecimento_t1 / c.aptos_t1;

-- ---------------------------------------------------------------------------
-- 4. Seção com zero voto para um dos finalistas
-- ---------------------------------------------------------------------------

WITH s22 AS (SELECT turno, uf, cd_mun, zona, secao,
                    sumIf(votos, tipo_voto = 'nominal' AND numero = 13) AS v13,
                    sumIf(votos, tipo_voto = 'nominal' AND numero = 22) AS v22
             FROM ref_votos_2022 GROUP BY ALL)
SELECT '2022' AS ano, turno, count() AS secoes,
       countIf(v22 = 0 AND v13 > 0) AS zero_22, countIf(v13 = 0 AND v22 > 0) AS zero_13,
       countIf(v22 = 0 AND v13 >= 100) AS zero_22_100, countIf(v13 = 0 AND v22 >= 100) AS zero_13_100,
       sumIf(v13, v22 = 0) AS votos_13_nas_zero_22, sumIf(v22, v13 = 0) AS votos_22_nas_zero_13
FROM s22 GROUP BY turno ORDER BY turno;

SELECT '2026 T2' AS ano, count() AS secoes,
       countIf(votos_22 = 0 AND votos_13 > 0) AS zero_22, countIf(votos_13 = 0 AND votos_22 > 0) AS zero_13,
       countIf(votos_22 = 0 AND votos_13 >= 100) AS zero_22_100, countIf(votos_13 = 0 AND votos_22 >= 100) AS zero_13_100,
       sumIf(votos_13, votos_22 = 0), sumIf(votos_22, votos_13 = 0)
FROM v_votos_t2_secao;

SELECT '2026 T1' AS ano, count() AS secoes,
       countIf(votos_22 = 0 AND votos_13 > 0) AS zero_22, countIf(votos_13 = 0 AND votos_22 > 0) AS zero_13,
       countIf(votos_22 = 0 AND votos_13 >= 100) AS zero_22_100, countIf(votos_13 = 0 AND votos_22 >= 100) AS zero_13_100,
       sumIf(votos_13, votos_22 = 0), sumIf(votos_22, votos_13 = 0)
FROM v_votos_t1_secao;

-- Lista do 2º turno com histórico (1º turno de 2026 e 2º turno de 2022 na mesma chave)
WITH s22 AS (SELECT uf, cd_mun, zona, secao,
                    sumIf(votos, tipo_voto = 'nominal' AND numero = 13) AS v13,
                    sumIf(votos, tipo_voto = 'nominal' AND numero = 22) AS v22
             FROM ref_votos_2022 WHERE turno = 2 GROUP BY ALL)
SELECT t.uf, t.cd_mun, m.nome, t.zona, t.secao, t.votos_13 AS t2_13, t.votos_22 AS t2_22,
       t.brancos + t.nulos AS t2_bn, c.comparecimento_t1, c.comparecimento_t2,
       c.votos_13_t1 AS t1_13, c.votos_22_t1 AS t1_22, c.votos_outros_t1 AS t1_outros,
       s.v13 AS t2_2022_13, s.v22 AS t2_2022_22
FROM v_votos_t2_secao AS t
LEFT JOIN v_comparacao_t1_t2 AS c USING (uf, cd_mun, zona, secao)
LEFT JOIN s22 AS s USING (uf, cd_mun, zona, secao)
LEFT JOIN ref_resultado_municipio_2026_t1 AS m USING (uf, cd_mun)
WHERE (t.votos_22 = 0 AND t.votos_13 > 0) OR (t.votos_13 = 0 AND t.votos_22 > 0)
ORDER BY t.votos_13 = 0, t.uf, t.cd_mun, t.zona, t.secao;

-- Persistência: o finalista zerado no 2º turno já tinha quase nada no 1º?
WITH s22 AS (SELECT uf, cd_mun, zona, secao,
                    sumIf(votos, tipo_voto = 'nominal' AND numero = 13) AS v13,
                    sumIf(votos, tipo_voto = 'nominal' AND numero = 22) AS v22
             FROM ref_votos_2022 WHERE turno = 2 GROUP BY ALL)
SELECT if(t.votos_22 = 0, 'zero no 22', 'zero no 13') AS lado, count() AS secoes,
       countIf(if(t.votos_22 = 0, c.votos_22_t1, c.votos_13_t1) <= 2) AS t1_ate_2,
       countIf(if(t.votos_22 = 0, c.votos_22_t1, c.votos_13_t1) = 0) AS t1_zero,
       countIf(s.v13 + s.v22 > 0) AS com_par_2022,
       countIf(s.v13 + s.v22 > 0 AND if(t.votos_22 = 0, s.v22, s.v13) <= 5) AS em_2022_ate_5,
       max(if(t.votos_22 = 0, c.votos_22_t1, c.votos_13_t1)) AS maximo_t1
FROM v_votos_t2_secao AS t
INNER JOIN v_comparacao_t1_t2 AS c USING (uf, cd_mun, zona, secao)
LEFT JOIN s22 AS s USING (uf, cd_mun, zona, secao)
WHERE (t.votos_22 = 0 AND t.votos_13 > 0) OR (t.votos_13 = 0 AND t.votos_22 > 0)
GROUP BY lado;

-- ---------------------------------------------------------------------------
-- 5. Pareamento 1º x 2º turno e aptos
-- ---------------------------------------------------------------------------

SELECT
    (SELECT count() FROM v_bu_ultima) AS t2_com_bu,
    (SELECT count() FROM ref_secoes_2026_t1 WHERE status = 'ok') AS t1_com_bu,
    (SELECT count() FROM v_bu_ultima WHERE (uf, cd_mun, zona, secao) NOT IN
        (SELECT uf, cd_mun, zona, secao FROM ref_secoes_2026_t1 WHERE status = 'ok')) AS t2_sem_par_t1,
    (SELECT count() FROM ref_secoes_2026_t1 WHERE status = 'ok' AND (uf, cd_mun, zona, secao) NOT IN
        (SELECT uf, cd_mun, zona, secao FROM v_bu_ultima)) AS t1_sem_par_t2;

-- Seções que constam do aux.json do 2º turno sem BU, e o status delas no 1º turno
SELECT a.st_secao, r.status AS status_t1, count() AS secoes
FROM (SELECT uf, cd_mun, zona, secao, argMax(st_secao, coletado_em) AS st_secao
      FROM aux_versoes FINAL GROUP BY ALL) AS a
LEFT JOIN ref_secoes_2026_t1 AS r USING (uf, cd_mun, zona, secao)
WHERE (uf, cd_mun, zona, secao) NOT IN (SELECT uf, cd_mun, zona, secao FROM v_bu_ultima)
GROUP BY ALL;

-- Aptos, aptos da própria seção e aptos em trânsito (TTE)
WITH p AS (
    SELECT t1.aptos AS a1, t2.aptos AS a2, t2.aptos - t1.aptos AS da,
           t2.aptos_secao - t1.aptos_secao AS ds, t2.aptos_tte - t1.aptos_tte AS de,
           t1.aptos_secao AS s1, t2.aptos_secao AS s2,
           t1.comparecimento AS c1, t2.comparecimento AS c2,
           t1.tipo_urna AS tu1, t2.tipo_urna AS tu2,
           t1.numero_interno_urna AS urna1, t2.numero_interno_urna AS urna2
    FROM ref_secoes_2026_t1 AS t1
    INNER JOIN v_bu_ultima AS t2 USING (uf, cd_mun, zona, secao)
    WHERE t1.status = 'ok')
SELECT count() AS pares, sum(a1) AS aptos_t1, sum(a2) AS aptos_t2,
       countIf(da != 0) AS aptos_mudaram, countIf(ds != 0) AS aptos_secao_mudaram,
       countIf(ds = 0 AND da != 0) AS so_tte_mudou,
       sum(ds) AS soma_delta_secao, sum(de) AS soma_delta_tte,
       sumIf(ds, ds > 0), sumIf(ds, ds < 0), sumIf(de, de > 0), sumIf(de, de < 0),
       min(ds), max(ds), min(de), max(de),
       countIf(abs(da) >= 30) AS delta_aptos_30, countIf(s1 = 0) AS so_tte_t1, countIf(s2 = 0) AS so_tte_t2,
       countIf(c2 > a1) AS comp_t2_maior_aptos_t1, countIf(c1 > a2) AS comp_t1_maior_aptos_t2,
       countIf(tu1 != tu2) AS tipo_urna_mudou, countIf(urna1 = urna2) AS mesma_urna,
       sum(c1) AS comp_t1, sum(c2) AS comp_t2
FROM p;

-- Distribuição da variação dos aptos da própria seção
SELECT t2.aptos_secao - t1.aptos_secao AS delta_aptos_secao, count() AS secoes
FROM ref_secoes_2026_t1 AS t1
INNER JOIN v_bu_ultima AS t2 USING (uf, cd_mun, zona, secao)
WHERE t1.status = 'ok' AND t2.aptos_secao != t1.aptos_secao
GROUP BY delta_aptos_secao
ORDER BY delta_aptos_secao;

-- Por UF (o trânsito entre UFs desloca aptos de uma UF para outra)
SELECT uf, sum(t2.aptos - t1.aptos) AS delta_aptos, sum(t2.aptos_secao - t1.aptos_secao) AS delta_secao,
       sum(t2.aptos_tte - t1.aptos_tte) AS delta_tte, countIf(t2.aptos != t1.aptos) AS secoes_mudaram
FROM ref_secoes_2026_t1 AS t1
INNER JOIN v_bu_ultima AS t2 USING (uf, cd_mun, zona, secao)
WHERE t1.status = 'ok'
GROUP BY uf ORDER BY uf;

-- Maiores variações de aptos
SELECT uf, cd_mun, zona, secao, t1.aptos AS a1, t2.aptos AS a2, t1.aptos_secao AS s1, t2.aptos_secao AS s2,
       t1.aptos_tte AS e1, t2.aptos_tte AS e2, t1.comparecimento AS c1, t2.comparecimento AS c2
FROM ref_secoes_2026_t1 AS t1
INNER JOIN v_bu_ultima AS t2 USING (uf, cd_mun, zona, secao)
WHERE t1.status = 'ok' AND abs(t2.aptos - t1.aptos) >= 30
ORDER BY abs(t2.aptos - t1.aptos) DESC;

-- Linha de base 2022
SELECT countIf(a.eleitores_aptos != b.eleitores_aptos) AS aptos_mudaram,
       sum(a.eleitores_aptos) AS aptos_t1, sum(b.eleitores_aptos) AS aptos_t2,
       sum(a.comparecimento) AS comp_t1, sum(b.comparecimento) AS comp_t2
FROM ref_secoes_2022 AS a
INNER JOIN ref_secoes_2022 AS b USING (uf, cd_mun, zona, secao)
WHERE a.turno = 1 AND b.turno = 2;

-- ---------------------------------------------------------------------------
-- 6. BUs com o mesmo vetor de votos em seções distintas
-- ---------------------------------------------------------------------------

CREATE TEMPORARY TABLE t2v AS
SELECT u.uf AS uf, u.cd_mun AS cd_mun, u.zona AS zona, u.secao AS secao,
       u.aptos AS a, u.comparecimento AS c, v.votos_13 AS x, v.votos_22 AS y,
       v.brancos AS b, v.nulos AS n, u.numero_interno_urna AS urna, u.local_votacao AS loc
FROM v_bu_ultima AS u
INNER JOIN v_votos_t2_secao AS v USING (uf, cd_mun, zona, secao);

CREATE TEMPORARY TABLE pares_iguais AS
SELECT p.uf AS uf1, p.cd_mun AS m1, p.zona AS z1, p.secao AS s1,
       q.uf AS uf2, q.cd_mun AS m2, q.zona AS z2, q.secao AS s2,
       p.a AS a, p.c AS c, p.x AS x, p.y AS y, p.b AS b, p.n AS n,
       p.urna AS u1, q.urna AS u2, p.loc AS l1, q.loc AS l2
FROM t2v AS p
INNER JOIN t2v AS q ON p.a = q.a AND p.c = q.c AND p.x = q.x AND p.y = q.y AND p.b = q.b AND p.n = q.n
WHERE (p.uf, p.cd_mun, p.zona, p.secao) < (q.uf, q.cd_mun, q.zona, q.secao);

SELECT count() AS pares, countIf(uf1 = uf2) AS mesma_uf, countIf(uf1 = uf2 AND m1 = m2) AS mesmo_municipio,
       countIf(uf1 = uf2 AND m1 = m2 AND z1 = z2) AS mesma_zona,
       countIf(uf1 = uf2 AND m1 = m2 AND z1 = z2 AND l1 = l2) AS mesmo_local,
       countIf(u1 = u2) AS mesma_urna, min(c), quantile(0.5)(c), max(c)
FROM pares_iguais;

-- Algum par também é idêntico no 1º turno?
SELECT count() AS pares_iguais_tambem_no_t1
FROM pares_iguais AS p
INNER JOIN v_votos_t1_secao AS a ON a.uf = p.uf1 AND a.cd_mun = p.m1 AND a.zona = p.z1 AND a.secao = p.s1
INNER JOIN v_votos_t1_secao AS b ON b.uf = p.uf2 AND b.cd_mun = p.m2 AND b.zona = p.z2 AND b.secao = p.s2
WHERE a.comparecimento = b.comparecimento AND a.votos_13 = b.votos_13 AND a.votos_22 = b.votos_22
  AND a.votos_outros = b.votos_outros AND a.brancos = b.brancos AND a.nulos = b.nulos;

SELECT * FROM pares_iguais WHERE uf1 = uf2 AND m1 = m2 AND z1 = z2 AND l1 = l2 ORDER BY uf1;

-- Decomposição das coincidências: pares de seções com a mesma chave, 2022 x 2026 (2º turno)
CREATE TEMPORARY TABLE base_coinc AS
SELECT '2026' AS ano, a, c, x, y, b, n FROM t2v
UNION ALL
SELECT '2022', r.eleitores_aptos, r.comparecimento, s.x, s.y, s.b, s.n
FROM (SELECT uf, cd_mun, zona, secao,
             sumIf(votos, tipo_voto = 'nominal' AND numero = 13) AS x,
             sumIf(votos, tipo_voto = 'nominal' AND numero = 22) AS y,
             sumIf(votos, tipo_voto = 'branco') AS b, sumIf(votos, tipo_voto = 'nulo') AS n
      FROM ref_votos_2022 WHERE turno = 2 GROUP BY ALL) AS s
INNER JOIN ref_secoes_2022 AS r
    ON r.turno = 2 AND r.uf = s.uf AND r.cd_mun = s.cd_mun AND r.zona = s.zona AND r.secao = s.secao;

SELECT * FROM (
          SELECT ano, 'c' AS chave, sum(k * (k - 1) / 2) AS pares FROM (SELECT ano, count() AS k FROM base_coinc GROUP BY ano, c) GROUP BY ano
UNION ALL SELECT ano, 'a,c', sum(k * (k - 1) / 2) FROM (SELECT ano, count() AS k FROM base_coinc GROUP BY ano, a, c) GROUP BY ano
UNION ALL SELECT ano, 'c,x,y', sum(k * (k - 1) / 2) FROM (SELECT ano, count() AS k FROM base_coinc GROUP BY ano, c, x, y) GROUP BY ano
UNION ALL SELECT ano, 'c,x,y,b,n', sum(k * (k - 1) / 2) FROM (SELECT ano, count() AS k FROM base_coinc GROUP BY ano, c, x, y, b, n) GROUP BY ano
UNION ALL SELECT ano, 'a,c,x,y,b,n', sum(k * (k - 1) / 2) FROM (SELECT ano, count() AS k FROM base_coinc GROUP BY ano, a, c, x, y, b, n) GROUP BY ano
UNION ALL SELECT ano, 'secoes', count() FROM base_coinc GROUP BY ano)
ORDER BY chave, ano;

SELECT ano, avg(b + n) AS brancos_nulos_medio, avg(c) AS comparecimento_medio, stddevPop(c) AS dp_comparecimento
FROM base_coinc GROUP BY ano;

-- 1º turno: vetor completo (12 candidatos, brancos e nulos)
WITH s AS (SELECT uf, cd_mun, zona, secao, arraySort(groupArray((tipo_voto, numero, votos))) AS vet
           FROM ref_votos_2026_t1 GROUP BY ALL),
     g AS (SELECT r.aptos AS a, r.comparecimento AS c, s.vet AS vet, count() AS k
           FROM s INNER JOIN ref_secoes_2026_t1 AS r USING (uf, cd_mun, zona, secao)
           GROUP BY ALL HAVING k > 1)
SELECT count() AS grupos, sum(k) AS secoes, max(k) FROM g;

-- ---------------------------------------------------------------------------
-- 7. Número interno da urna repetido
-- ---------------------------------------------------------------------------

SELECT tipo_arquivo, count() AS equipamentos_repetidos, sum(k) AS secoes, max(k) AS max_secoes
FROM (SELECT numero_interno_urna, any(tipo_arquivo) AS tipo_arquivo, count() AS k
      FROM v_bu_ultima GROUP BY numero_interno_urna HAVING k > 1)
GROUP BY ALL;

SELECT origem_bu, count() AS equipamentos_repetidos, sum(k) AS secoes, max(k) AS max_secoes
FROM (SELECT numero_interno_urna, any(origem_bu) AS origem_bu, count() AS k
      FROM ref_secoes_2026_t1 WHERE status = 'ok' GROUP BY numero_interno_urna HAVING k > 1)
GROUP BY ALL;

-- Urna que aparece em seção diferente no outro turno
SELECT a.tipo_urna AS tipo_t2, b.tipo_urna AS tipo_t1,
       a.uf = b.uf AND a.cd_mun = b.cd_mun AS mesmo_municipio,
       a.uf = b.uf AND a.cd_mun = b.cd_mun AND a.zona = b.zona AS mesma_zona, count() AS urnas
FROM v_bu_ultima AS a
INNER JOIN (SELECT * FROM ref_secoes_2026_t1 WHERE status = 'ok') AS b
    ON a.numero_interno_urna = b.numero_interno_urna
WHERE (a.uf, a.cd_mun, a.zona, a.secao) != (b.uf, b.cd_mun, b.zona, b.secao)
  AND a.tipo_arquivo = 'bu' AND b.tipo_urna != 'contingencia'
GROUP BY ALL ORDER BY urnas DESC;

-- ---------------------------------------------------------------------------
-- 8. Horários: abertura, encerramento, emissão e duração
-- ---------------------------------------------------------------------------

CREATE TEMPORARY TABLE horarios AS
WITH multiIf(cd_mun IN ('02020', '02054', '02135', '02291', '02313', '02399', '02496',
                        '02755', '02917', '98370', '98477'), 2,
             uf = 'ac', 2, uf IN ('am', 'mt', 'ms', 'ro', 'rr'), 1, cd_mun = '30015', -1, 0) AS off
SELECT 'T2' AS turno, uf, cd_mun, zona, secao, tipo_urna, toDate('2026-10-25') AS dia, off,
       hora_abertura + toIntervalHour(off) AS ab, hora_encerramento + toIntervalHour(off) AS en,
       data_hora_emissao + toIntervalHour(off) AS em,
       hora_abertura AS ab_local, hora_encerramento AS en_local, data_hora_emissao AS em_local
FROM v_bu_ultima
UNION ALL
SELECT 'T1', uf, cd_mun, zona, secao, tipo_urna, toDate('2026-10-04'), off,
       hora_abertura + toIntervalHour(off), hora_encerramento + toIntervalHour(off),
       data_hora_emissao + toIntervalHour(off), hora_abertura, hora_encerramento, data_hora_emissao
FROM ref_secoes_2026_t1
WHERE status = 'ok';

SELECT turno, uf = 'zz' AS exterior, count() AS secoes,
       countIf(ab IS NULL) AS sem_abertura, countIf(em IS NULL) AS sem_emissao,
       countIf(toDate(ab_local) != dia) AS abertura_outro_dia,
       countIf(toDate(en_local) != dia) AS encerramento_outro_dia,
       countIf(toDate(em_local) != dia) AS emissao_outro_dia,
       countIf(formatDateTime(ab, '%H:%i:%S') < '08:00:00') AS abertura_antes_8h_brasilia,
       countIf(formatDateTime(ab, '%H:%i:%S') >= '08:10:00') AS abertura_8h10_ou_depois,
       countIf(formatDateTime(ab, '%H:%i:%S') >= '09:00:00') AS abertura_9h_ou_depois,
       countIf(formatDateTime(ab_local, '%H:%i:%S') < '07:00:00') AS abertura_antes_7h_local,
       countIf(formatDateTime(ab_local, '%H:%i:%S') > '09:00:00') AS abertura_depois_9h_local,
       countIf(formatDateTime(en, '%H:%i:%S') < '17:00:00') AS encerramento_antes_17h_brasilia,
       countIf(em < en) AS emissao_antes_encerramento, countIf(em < ab) AS emissao_antes_abertura,
       countIf(en < ab) AS encerramento_antes_abertura,
       countIf(dateDiff('second', en, em) > 3600) AS emissao_mais_1h_apos_encerramento,
       min(ab), max(ab), min(en), max(en), min(em), max(em)
FROM horarios
GROUP BY turno, exterior
ORDER BY turno, exterior;

-- Abertura antes das 7h locais: só nos fusos UTC-5 (06h locais = 08h de Brasília)
SELECT off, count() AS secoes, countIf(formatDateTime(ab_local, '%H:%i') < '07:00') AS antes_7h_local,
       min(formatDateTime(ab_local, '%H:%i:%S')) AS primeira_local
FROM horarios WHERE turno = 'T2' AND uf != 'zz' GROUP BY off ORDER BY off;

-- Duração em minutos (abertura a encerramento)
SELECT turno, tipo_urna, count() AS secoes,
       quantiles(0.001, 0.01, 0.5, 0.99, 0.999)(dateDiff('minute', ab, en)) AS duracao_min,
       min(dateDiff('minute', ab, en)), max(dateDiff('minute', ab, en))
FROM horarios
WHERE uf != 'zz' AND ab IS NOT NULL
GROUP BY ALL ORDER BY turno, tipo_urna;

-- Aberturas às 10h de Brasília ou depois no 2º turno
SELECT uf, cd_mun, zona, secao, tipo_urna, ab AS abertura_brasilia, en AS encerramento_brasilia
FROM horarios
WHERE turno = 'T2' AND uf != 'zz' AND formatDateTime(ab, '%H:%i') >= '10:00'
ORDER BY ab DESC;

-- Atraso entre encerramento e emissão do BU, por UF e turno
SELECT a.uf, a.secoes, a.p50 AS p50_t2_s, a.p99 AS p99_t2_s, a.mais_30min AS t2_mais_30min,
       a.mais_1h AS t2_mais_1h, b.p50 AS p50_t1_s, b.mais_30min AS t1_mais_30min, b.mais_1h AS t1_mais_1h
FROM (SELECT uf, count() AS secoes, quantile(0.5)(d) AS p50, quantile(0.99)(d) AS p99,
             countIf(d > 1800) AS mais_30min, countIf(d > 3600) AS mais_1h
      FROM (SELECT uf, dateDiff('second', en, em) AS d FROM horarios WHERE turno = 'T2' AND ab IS NOT NULL)
      GROUP BY uf) AS a
INNER JOIN
     (SELECT uf, quantile(0.5)(d) AS p50, countIf(d > 1800) AS mais_30min, countIf(d > 3600) AS mais_1h
      FROM (SELECT uf, dateDiff('second', en, em) AS d FROM horarios WHERE turno = 'T1' AND ab IS NOT NULL)
      GROUP BY uf) AS b USING (uf)
ORDER BY a.mais_1h DESC;

-- Lista das seções do 2º turno com BU emitido mais de 1 hora depois do encerramento
SELECT uf, cd_mun, zona, secao, tipo_urna, en_local AS encerramento_local, em_local AS emissao_local,
       dateDiff('minute', en, em) AS atraso_min
FROM horarios
WHERE turno = 'T2' AND ab IS NOT NULL AND dateDiff('second', en, em) > 3600
ORDER BY uf, cd_mun, zona, secao;

-- Essas seções votaram diferente das demais da mesma zona?
CREATE TEMPORARY TABLE emissao AS
SELECT uf, cd_mun, zona, secao, dateDiff('second', en, em) > 3600 AS tardia
FROM horarios WHERE turno = 'T2' AND ab IS NOT NULL;

SELECT e.tardia, count() AS secoes,
       round(100 * sum(c.votos_13_t1) / sum(c.votos_13_t1 + c.votos_22_t1), 3) AS pct_13_t1,
       round(100 * sum(c.votos_13_t2) / sum(c.votos_13_t2 + c.votos_22_t2), 3) AS pct_13_t2,
       round(pct_13_t2 - pct_13_t1, 3) AS variacao,
       round(100 * sum(c.comparecimento_t1) / sum(c.aptos_t1), 3) AS comp_t1,
       round(100 * sum(c.comparecimento_t2) / sum(c.aptos_t2), 3) AS comp_t2
FROM emissao AS e
INNER JOIN v_comparacao_t1_t2 AS c USING (uf, cd_mun, zona, secao)
WHERE (uf, cd_mun, zona) IN (SELECT DISTINCT uf, cd_mun, zona FROM emissao WHERE tardia)
GROUP BY e.tardia;

-- Linha de base: urna de reserva em 2022
SELECT turno, tipo_urna, count() AS secoes FROM ref_secoes_2022 GROUP BY ALL ORDER BY turno, secoes DESC;

-- ---------------------------------------------------------------------------
-- 9. Soma dos BUs x resultado oficial
-- ---------------------------------------------------------------------------

-- 9a. 1º turno, por município (válidos = nominais sem o 28, que o TSE conta como nulo técnico)
WITH b AS (SELECT uf, cd_mun, uniqExact(zona, secao) AS secoes, sum(aptos) AS aptos,
                  sum(comparecimento) AS comp
           FROM ref_secoes_2026_t1 WHERE status = 'ok' GROUP BY ALL),
     v AS (SELECT uf, cd_mun,
                  sumIf(votos, tipo_voto = 'nominal' AND numero = 13) AS v13,
                  sumIf(votos, tipo_voto = 'nominal' AND numero = 22) AS v22,
                  sumIf(votos, tipo_voto = 'nominal' AND numero != 28) AS validos,
                  sumIf(votos, tipo_voto = 'branco') AS brancos,
                  sumIf(votos, tipo_voto = 'nulo') + sumIf(votos, tipo_voto = 'nominal' AND numero = 28) AS nulos
           FROM ref_votos_2026_t1 GROUP BY ALL)
SELECT count() AS municipios,
       countIf(b.secoes != r.secoes_totalizadas) AS secoes_dif,
       countIf(b.comp != r.comparecimento) AS comparecimento_dif,
       countIf(v.v13 != r.v_13) AS dif_13, countIf(v.v22 != r.v_22) AS dif_22,
       countIf(v.validos != r.votos_validos) AS validos_dif,
       countIf(v.brancos != r.votos_brancos) AS brancos_dif,
       countIf(v.nulos != r.votos_nulos_total) AS nulos_dif,
       countIf(b.aptos != r.eleitorado) AS eleitorado_dif,
       sum(r.eleitorado) - sum(b.aptos) AS eleitorado_menos_aptos,
       sum(b.secoes), sum(r.secoes_totalizadas),
       sum(v.v13), sum(r.v_13), sum(v.v22), sum(r.v_22),
       sum(v.validos), sum(r.votos_validos), sum(b.comp), sum(r.comparecimento)
FROM ref_resultado_municipio_2026_t1 AS r
LEFT JOIN b USING (uf, cd_mun)
LEFT JOIN v USING (uf, cd_mun);

-- Municípios sem nenhuma seção com BU (as 41 não instaladas)
SELECT r.uf, r.cd_mun, r.nome, r.eleitorado, r.secoes_total, n.nao_instaladas
FROM ref_resultado_municipio_2026_t1 AS r
INNER JOIN (SELECT uf, cd_mun, count() AS nao_instaladas FROM ref_secoes_2026_t1
            WHERE status = 'nao_instalada' GROUP BY ALL) AS n USING (uf, cd_mun)
ORDER BY r.uf, r.cd_mun;

-- 9b. 2º turno, Brasil: soma dos BUs x último total publicado
SELECT (SELECT sum(votos_13) FROM v_votos_t2_secao) AS bu_13, cand['13'] AS oficial_13,
       (SELECT sum(votos_22) FROM v_votos_t2_secao) AS bu_22, cand['22'] AS oficial_22,
       (SELECT sum(brancos) FROM v_votos_t2_secao) AS bu_brancos, vb AS oficial_brancos,
       (SELECT sum(nulos) FROM v_votos_t2_secao) AS bu_nulos, tvn AS oficial_nulos,
       (SELECT sum(comparecimento) FROM v_bu_ultima) AS bu_comparecimento, tv AS oficial_votos,
       st, ts, totalizado_em
FROM v_totais_ultima
WHERE nivel = 'br';
