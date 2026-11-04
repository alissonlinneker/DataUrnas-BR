-- Exports for scripts/ele2026/chegada_bus.py (arrival order of BUs at the tally).
-- One query per block; the Python "export" step splits on the "-- @name" markers
-- and pipes each block to ch.sh, writing <name>.parquet.
-- Clock columns from the voting machine (data_hora_emissao) hold LOCAL time
-- labelled as UTC: format them with 'UTC' and never convert time zones.

-- @t2_2026
SELECT u.uf AS uf, u.cd_mun AS cd_mun, u.zona AS zona, u.secao AS secao,
       formatDateTime(u.recebimento, '%F %T', 'America/Sao_Paulo') AS rec,
       formatDateTime(u.data_hora_emissao, '%F %T', 'UTC') AS emi_local,
       toString(u.tipo_urna) AS tipo_urna, u.aptos AS aptos, u.comparecimento AS comp,
       v.votos_13 AS v13, v.votos_22 AS v22
FROM dataurnas.v_bu_ultima AS u
INNER JOIN dataurnas.v_votos_t2_secao AS v USING (uf, cd_mun, zona, secao)
FORMAT Parquet;

-- @t1_2026
SELECT s.uf AS uf, s.cd_mun AS cd_mun, s.zona AS zona, s.secao AS secao,
       concat(s.dt_recebimento, ' ', s.hr_recebimento) AS rec,
       formatDateTime(s.data_hora_emissao, '%F %T', 'UTC') AS emi_local,
       toString(s.tipo_urna) AS tipo_urna, s.aptos AS aptos, s.comparecimento AS comp,
       v.votos_13 AS v13, v.votos_22 AS v22, v.votos_outros AS vout
FROM dataurnas.ref_secoes_2026_t1 AS s
INNER JOIN dataurnas.v_votos_t1_secao AS v USING (uf, cd_mun, zona, secao)
FORMAT Parquet;

-- @y2022
SELECT s.turno AS turno, s.uf AS uf, s.cd_mun AS cd_mun, s.zona AS zona, s.secao AS secao,
       s.emissao AS emissao, s.fuso_offset AS fuso_offset, toString(s.tipo_urna) AS tipo_urna,
       s.is_reserva AS is_reserva, s.eleitores_aptos AS aptos, s.comparecimento AS comp,
       v.v13 AS v13, v.v22 AS v22
FROM dataurnas.ref_secoes_2022 AS s
INNER JOIN (
    SELECT turno, uf, cd_mun, zona, secao,
           sumIf(votos, numero = 13) AS v13, sumIf(votos, numero = 22) AS v22
    FROM dataurnas.ref_votos_2022
    WHERE tipo_voto = 'nominal'
    GROUP BY turno, uf, cd_mun, zona, secao
) AS v USING (turno, uf, cd_mun, zona, secao)
FORMAT Parquet;

-- @municipios
SELECT uf, cd_mun, capital, eleitorado
FROM dataurnas.ref_resultado_municipio_2026_t1
FORMAT Parquet;
