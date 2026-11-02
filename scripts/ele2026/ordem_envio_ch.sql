SELECT s.uf uf, s.cd_mun cd_mun, s.zona zona, s.secao secao, s.emissao - toIntervalHour(s.fuso_offset) envio, sumIf(v.votos, v.numero=13) v13, sumIf(v.votos, v.numero=22) v22
FROM dataurnas.ref_secoes_2022 s JOIN (SELECT * FROM dataurnas.ref_votos_2022 WHERE turno=2 AND numero IN (13,22)) v USING (uf, cd_mun, zona, secao)
WHERE s.turno=2 GROUP BY uf, cd_mun, zona, secao, envio INTO OUTFILE '/tmp/o2022.parquet' TRUNCATE FORMAT Parquet;
SELECT uf, cd_mun, zona, secao, recebimento envio, votos_13 v13, votos_22 v22 FROM dataurnas.v_votos_t2_secao JOIN (SELECT uf, cd_mun, zona, secao, recebimento FROM dataurnas.v_bu_ultima) b USING (uf, cd_mun, zona, secao) INTO OUTFILE '/tmp/o2026.parquet' TRUNCATE FORMAT Parquet;
