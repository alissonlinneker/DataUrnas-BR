-- Variação de votos entre o 1º e o 2º turno de 2026 por grupo de virada
-- (22 para 13, 13 para 22, sem virada), seção a seção, no país inteiro.
--
-- Seções: todas com BU do 2º turno (v_votos_t2_secao, última versão) pareadas
-- com o BU do 1º turno (v_votos_t1_secao). Grupo pelo líder (13 x 22) de cada
-- turno, com a mesma regra de viradas_t1_t2.py: empate não tem líder e não vira.
-- "Outros" no 2º turno = votos de Presidente que não são 13, 22, branco nem nulo
-- (deve ser zero). Abstenção = aptos - comparecimento.
--
-- Níveis: brasil (sem o exterior), regiao, uf, exterior ('zz') e total (Brasil
-- mais exterior). Uso (no servidor):
--   ~/dataurnas-ch/app/scripts/ch/ch.sh < viradas_grupos_ch.sql > grupos.tsv
WITH b AS (
    SELECT t2.uf AS uf,
           multiIf(t2.uf IN ('ac', 'am', 'ap', 'pa', 'ro', 'rr', 'to'), 'Norte',
                   t2.uf IN ('al', 'ba', 'ce', 'ma', 'pb', 'pe', 'pi', 'rn', 'se'), 'Nordeste',
                   t2.uf IN ('df', 'go', 'ms', 'mt'), 'Centro-Oeste',
                   t2.uf IN ('es', 'mg', 'rj', 'sp'), 'Sudeste',
                   t2.uf IN ('pr', 'rs', 'sc'), 'Sul', 'Exterior') AS regiao,
           multiIf(t1.votos_13 > t1.votos_22, '13', t1.votos_22 > t1.votos_13, '22', 'empate') AS l1,
           multiIf(t2.votos_13 > t2.votos_22, '13', t2.votos_22 > t2.votos_13, '22', 'empate') AS l2,
           multiIf(l1 = '22' AND l2 = '13', '22 para 13',
                   l1 = '13' AND l2 = '22', '13 para 22', 'sem virada') AS grupo,
           toInt64(ifNull(t1.aptos, 0)) AS a1, toInt64(ifNull(t2.aptos, 0)) AS a2,
           toInt64(ifNull(t1.comparecimento, 0)) AS c1, toInt64(ifNull(t2.comparecimento, 0)) AS c2,
           t1.votos_13 AS l13_1, t2.votos_13 AS l13_2,
           t1.votos_22 AS f22_1, t2.votos_22 AS f22_2,
           t1.votos_outros AS o1,
           t2.total - t2.votos_13 - t2.votos_22 - t2.brancos - t2.nulos AS o2,
           t1.brancos AS br1, t2.brancos AS br2, t1.nulos AS nu1, t2.nulos AS nu2,
           t1.total AS tot1, t2.total AS tot2
    FROM dataurnas.v_votos_t2_secao AS t2
    INNER JOIN dataurnas.v_votos_t1_secao AS t1
        ON t1.uf = t2.uf AND t1.cd_mun = t2.cd_mun AND t1.zona = t2.zona AND t1.secao = t2.secao
),
g AS (
    SELECT multiIf(grouping(uf) = 0, 'uf', grouping(regiao) = 0, 'regiao', 'pais') AS nivel_bruto,
           multiIf(grouping(uf) = 0, toString(uf), grouping(regiao) = 0, regiao, 'BR+ZZ') AS chave,
           if(grouping(grupo) = 0, grupo, 'todas') AS grupo_v,
           count() AS secoes,
           sum(a1) AS aptos_1, sum(a2) AS aptos_2,
           sum(c1) AS comparecimento_1, sum(c2) AS comparecimento_2,
           sum(a1 - c1) AS abstencao_1, sum(a2 - c2) AS abstencao_2,
           sum(l13_1) AS lula_1, sum(l13_2) AS lula_2,
           sum(f22_1) AS flavio_1, sum(f22_2) AS flavio_2,
           sum(o1) AS outros_1, sum(o2) AS outros_2,
           sum(br1) AS brancos_1, sum(br2) AS brancos_2,
           sum(nu1) AS nulos_1, sum(nu2) AS nulos_2,
           sum(tot1) AS total_1, sum(tot2) AS total_2,
           countIf(l13_1 + f22_1 + o1 + br1 + nu1 != c1) AS fecha_t1_falhas,
           countIf(l13_2 + f22_2 + o2 + br2 + nu2 != c2) AS fecha_t2_falhas
    FROM b
    GROUP BY GROUPING SETS ((grupo), (regiao, grupo), (uf, grupo), (), (regiao), (uf))
)
SELECT nivel_bruto AS nivel, chave, grupo_v AS grupo, * EXCEPT (nivel_bruto, chave, grupo_v)
FROM g
ORDER BY nivel, chave, grupo
FORMAT TSVWithNames;
