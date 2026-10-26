# Certificados e assinaturas das urnas: 2º turno de 2026

Auditoria independente dos arquivos públicos do 2º turno das Eleições Gerais de 2026 (25/10/2026, pleito 3221, eleição 6258). Gerado em 2026-10-26T09:54:35 (UTC, relógio do servidor de processamento) por `scripts/ele2026/certificados_t2.py`, só com arquivos já baixados (nenhum download novo do TSE). Tabela por seção: `data/parquet/2026/t2/certificados/secoes.parquet`; números completos: `data/parquet/2026/t2/certificados/resumo.json`.

**Escala nacional (26/10/2026).** Esta versão cobre todas as 499.207 seções com BU do 2º turno (27 UFs e o exterior), a partir das 871 partes Parquet guardadas no servidor de processamento pelos coletores (`~/dataurnas-mac/versoes/2026/t2`, `~/dataurnas-mac/versoes/2026/t2-sseco`, `~/dataurnas-versoes-t2` e `~/dataurnas-versoes-t2-nne`). A assinatura de hardware de **todos** os arquivos listados em cada `.vsc` foi conferida (`--todas-fracao 1`), não só a do `bu.dat`. A versão anterior deste documento (25/10/2026, 23h43) era parcial: 119.778 seções de 15 UFs.

**Mudança de conclusão em relação à versão parcial.** Na amostra parcial, as urnas UE2013 e UE2015 (AC URNA, ECDSA) apareciam em 68,24% das seções que fecharam depois das 17h30 de Brasília, contra 19,46% nas demais. Com todas as seções, a proporção é de 19,88% nas tardias contra 19,81% nas demais (abaixo até dos 21,85% esperados pela composição de UF). A sobrerrepresentação vinha da composição da amostra parcial: 316 das 614 tardias daquela amostra eram da Paraíba, onde as urnas UE2013 e UE2015 de fato fecharam mais tarde (12,92% e 12,05% delas, contra 0,02% e 0,03% das UE2020 e UE2022). Em escala nacional, as tardias se concentram em RJ (3.320), SP (1.974), BA (1.051) e PE (716), com modelos novos e antigos. Detalhes na seção "Seções que fecharam depois de 17:30".

## Resultado

Nenhuma divergência de hash, nenhuma assinatura inválida e nenhuma cadeia quebrada nas 499.207 seções verificadas.

| Verificação | Resultado |
|---|---|
| SHA-512 do bu.dat igual ao valor assinado no .vsc (partes HW e SW) | sim: 499.207 |
| Nome do bu.dat igual ao listado no .vsc | sim: 499.207 |
| SHA-512 do conteúdo assinado igual ao hash autoassinado, parte de hardware | sim: 499.207 |
| Idem, parte de software | sim: 499.207 |
| Lista de hashes igual nas partes de software e de hardware | sim: 499.207 |
| Assinatura de hardware do conteúdo assinado (chave do certificado da urna) | sim: 499.207 |
| Assinatura de hardware do bu.dat | sim: 499.207 |
| Assinatura de hardware de cada arquivo listado no .vsc | 499.207 seções; assinaturas válidas: 5.487.289; inválidas: 0 |
| Certificado da urna assinado pela AC emissora | sim: 499.207 |
| Certificado da urna válido em 25/10/2026 | sim: 499.207 |
| Certificado válido no momento da assinatura (hora da urna, tolerância de 3 h) | sim: 499.207 |
| CN do certificado igual ao usuário da assinatura de hardware | sim: 499.207 |
| CN do certificado igual ao número interno da urna na carga do BU | sim: 499.204; não: 3 |
| SHA-512 do arquivo guardado igual ao registrado na coleta (BU / .vsc) | sim: 499.207 / sim: 499.207 |

## Cobertura

A coleta versionada do 2º turno terminou: o total do Brasil publicado pelo TSE está com 499.248 de 499.248 seções totalizadas desde 25/10/2026 23h27 e todos os BUs publicados estão guardados. Os números abaixo são os do conjunto completo.

### Coleta das assinaturas (.vsc) e seções sem .vsc

O TSE publica o `.vsc` alguns minutos depois do BU. O coletor (`scripts/ele2026/versionar_t2.py`) mantém o conjunto `sem_vsc` (seções com BU guardado e sem assinatura) e, a cada ciclo, busca de novo a assinatura dessas seções; cada assinatura obtida assim soma 1 ao contador `vsc_tardio`.

| Item | Valor | Fonte |
|---|---:|---|
| `sem_vsc` na partida do coletor de Londres (`dataurnas-versoes-t2-nne`, 26/10/2026 02h27) | 31.078 | `versoes.log`, linha "seções com BU e sem assinatura guardada" |
| `vsc_tardio` no ciclo 1 desse coletor (02h27 a 09h22) | 20.799 | `versoes.log`, contador do ciclo |
| `.vsc` guardados por pasta: Mac `t2` / Mac `t2-sseco` / Londres `t2` / Londres `t2-nne` | 253.450 / 552 / 37.752 / 207.453 | `versoes_arquivo` (ClickHouse), tipos `vota` e `sa` |
| Seções com BU | 499.207 | ClickHouse |
| Seções com BU e com `.vsc` do **mesmo pacote** (mesmo `hash`) | 499.207 | ClickHouse |
| BU sem `.vsc` do mesmo pacote | **0** | ClickHouse |
| `.vsc` sem BU | 0 | ClickHouse |
| Seções com mais de uma versão de BU ou de `.vsc` | 0 | ClickHouse |
| Seções do aux.json sem BU | 41, todas do exterior com status "Nao instalada" | `aux_versoes` |

Os 31.078 do `sem_vsc` incluem seções cuja assinatura já estava em outra pasta de coleta (o estado de cada coletor só enxerga a própria pasta) e seções cujo aux.json ainda não listava o `.vsc`; por isso o número é maior que o `vsc_tardio`. O que vale para a auditoria é o estado final, conferido no banco: **nenhuma seção com BU está sem a assinatura correspondente; não falta nenhuma.** Os 29 BUs do tipo `busa` (exterior, urna de contingência com sistema de apuração) vêm com assinatura do tipo `sa`; os demais 499.178, com `vota`. Os logs do coletor do Mac não estão no servidor, por isso o contador `vsc_tardio` dele não entra na tabela.

Consulta (ClickHouse, `~/dataurnas-ch/app/scripts/ch/ch.sh < arquivo.sql`):

```sql
WITH b AS (SELECT DISTINCT uf, cd_mun, zona, secao, hash FROM versoes_arquivo FINAL WHERE tipo IN ('bu','busa')),
     v AS (SELECT DISTINCT uf, cd_mun, zona, secao, hash FROM versoes_arquivo FINAL WHERE tipo IN ('vota','sa'))
SELECT (SELECT count() FROM b) AS bu_versoes,
       (SELECT count() FROM b INNER JOIN v USING (uf, cd_mun, zona, secao, hash)) AS pares_mesmo_hash,
       (SELECT count() FROM b LEFT ANTI JOIN v USING (uf, cd_mun, zona, secao, hash)) AS bu_sem_vsc_mesmo_hash,
       (SELECT count() FROM v LEFT ANTI JOIN b USING (uf, cd_mun, zona, secao, hash)) AS vsc_sem_bu
FORMAT Vertical;
-- resultado em 26/10/2026: 499207, 499207, 0, 0

SELECT st_secao, count() FROM aux_versoes FINAL
WHERE (uf, cd_mun, zona, secao) NOT IN
      (SELECT uf, cd_mun, zona, secao FROM versoes_arquivo FINAL WHERE tipo IN ('bu','busa'))
GROUP BY st_secao;
-- resultado: Nao instalada, 41 (todas com uf = 'zz')
```

| Item | Seções |
|---|---:|
| Seções com algum arquivo guardado | 499.207 |
| Com BU | 499.207 |
| Com .vsc | 499.207 |
| Com BU e .vsc da mesma versão (verificáveis) | 499.207 |
| BU sem .vsc (assinatura ainda não buscada) | 0 |
| .vsc sem BU | 0 |
| Com certificado e assinatura verificada | 499.207 |
| Com todas as assinaturas de arquivo verificadas | 499.207 |
| Com mais de uma versão (hash) publicada | 0 |

UFs presentes: AC, AL, AM, AP, BA, CE, DF, ES, GO, MA, MG, MS, MT, PA, PB, PE, PI, PR, RJ, RN, RO, RR, RS, SC, SE, SP, TO, ZZ.

| UF | Com BU | Com .vsc | Par completo |
|---|---:|---:|---:|
| AC | 2.270 | 2.270 | 2.270 |
| AL | 7.101 | 7.101 | 7.101 |
| AM | 8.157 | 8.157 | 8.157 |
| AP | 1.914 | 1.914 | 1.914 |
| BA | 35.476 | 35.476 | 35.476 |
| CE | 23.765 | 23.765 | 23.765 |
| DF | 6.969 | 6.969 | 6.969 |
| ES | 9.844 | 9.844 | 9.844 |
| GO | 15.686 | 15.686 | 15.686 |
| MA | 18.093 | 18.093 | 18.093 |
| MG | 52.062 | 52.062 | 52.062 |
| MS | 7.106 | 7.106 | 7.106 |
| MT | 8.287 | 8.287 | 8.287 |
| PA | 20.827 | 20.827 | 20.827 |
| PB | 10.712 | 10.712 | 10.712 |
| PE | 21.418 | 21.418 | 21.418 |
| PI | 10.225 | 10.225 | 10.225 |
| PR | 27.142 | 27.142 | 27.142 |
| RJ | 37.675 | 37.675 | 37.675 |
| RN | 8.115 | 8.115 | 8.115 |
| RO | 4.698 | 4.698 | 4.698 |
| RR | 1.519 | 1.519 | 1.519 |
| RS | 27.547 | 27.547 | 27.547 |
| SC | 17.326 | 17.326 | 17.326 |
| SE | 5.923 | 5.923 | 5.923 |
| SP | 103.656 | 103.656 | 103.656 |
| TO | 4.384 | 4.384 | 4.384 |
| ZZ | 1.310 | 1.310 | 1.310 |

## Como cada verificação foi feita

1. **Hash do BU.** O SHA-512 do `bu.dat` guardado é recalculado a partir dos bytes e comparado com o hash que o `.vsc` traz para o mesmo nome de arquivo, tanto na parte de hardware quanto na de software. Também se confere o SHA-512 do conteúdo assinado (a lista de arquivos e hashes) contra o hash autoassinado de cada parte. Dos arquivos listados no `.vsc`, só o `bu.dat` está guardado no versionamento; os demais (RDV, log, imagens) não foram baixados nesta coleta.
2. **Assinatura.** A assinatura de hardware do conteúdo assinado é conferida com a chave pública do certificado que acompanha o `.vsc` (Ed521 nas UE2020 e UE2022, ECDSA P-521 com SHA-512 nas UE2013 e UE2015). Como o conteúdo assinado contém o hash de todos os arquivos, essa assinatura já autentica a lista inteira. Além dela, a assinatura individual do `bu.dat` é conferida em todas as seções, e a de cada um dos arquivos listados, na amostra indicada na cobertura.
3. **Cadeia.** A assinatura do certificado da urna é conferida com a chave pública da AC emissora (certificados em `data/certificados/ac/`), e a da AC com a da AC acima dela quando esse certificado está disponível.
4. **Padrões.** Cruzamento com o número interno da carga gravado no BU, com o horário de encerramento (`data/parquet/2026/t2/encerramento/nacional/secoes_encerramento.parquet`, execução nacional) e com o catálogo do 1º turno (`data/parquet/2026/integridade/secoes.parquet`, 499.207 seções com certificado, e `data/parquet/2026/secoes_2026.parquet`).

## Certificados das urnas

| Modelo | AC emissora | Algoritmo da chave | Seções | % |
|---|---|---|---:|---:|
| UE2013 | AC URNA | ECDSA | 12.455 | 2,49% |
| UE2015 | AC URNA | ECDSA | 87.502 | 17,53% |
| UE2020 | AC UE2020 | Ed521 | 200.504 | 40,16% |
| UE2022 | AC UE2022 | Ed521 | 198.746 | 39,81% |

Curvas: E-521: 399.250; secp521r1: 99.957. Algoritmo da assinatura dos certificados (OID): 1.3.6.1.4.1.44588.2.1: 399.250; 1.2.840.10045.4.3.4: 99.957. Versão X.509: v3: 499.207. Hash da assinatura de hardware: sha512: 499.207.

Certificados distintos: 499.179; chaves públicas distintas: 499.179; pares emissor e número de série distintos: 499.179.

| AC emissora | Modelo | Seções | Emitidos entre | Vencem entre | Duração (dias) | Validade publicada da AC até |
|---|---|---:|---|---|---|---|
| AC UE2020 | UE2020 | 200.504 | 01/04/2022 a 22/10/2026 | 09/12/2035 a 15/01/2038 | 5000: 199.436, 4853: 72, 4896: 67, 4959: 59 | 01/07/2037 |
| AC UE2022 | UE2022 | 198.746 | 19/05/2023 a 02/10/2026 | 25/01/2037 a 15/01/2038 | 5000: 195.899, 4942: 676, 4872: 225, 4941: 175 | 24/02/2039 |
| AC URNA | UE2013 | 12.455 | 30/07/2013 a 19/10/2026 | 08/04/2027 a 15/01/2038 | 5000: 12.405, 4222: 7, 4182: 6, 4838: 4 | 18/07/2026 |
| AC URNA | UE2015 | 87.502 | 14/06/2016 a 18/10/2026 | 21/02/2030 a 15/01/2038 | 5000: 87.374, 4185: 14, 4222: 12, 4882: 12 | 18/07/2026 |

**Extensões.** Conjuntos encontrados: `authorityKeyIdentifier,basicConstraints,cRLDistributionPoints,certificatePolicies,keyUsage,subjectKeyIdentifier` (499.207). Extensões fora do conjunto esperado (basicConstraints, keyUsage, subjectKeyIdentifier, authorityKeyIdentifier, cRLDistributionPoints, certificatePolicies): nenhum. Extensões marcadas como críticas: nenhuma: 499.207. basicConstraints com CA: não: 499.207. keyUsage: digital_signature,key_encipherment,data_encipherment: 499.207.

**Emissão por ano:** 2013: 12.039, 2014: 133, 2015: 10, 2016: 86.853, 2017: 91, 2018: 253, 2019: 38, 2020: 144, 2022: 197.507, 2023: 151.919, 2024: 48.809, 2025: 898, 2026: 513.

**Emissão a partir de junho de 2026, por mês:** 2026-06: 64, 2026-07: 71, 2026-08: 133, 2026-09: 86, 2026-10: 12.

**Assinatura de software.** Algoritmo: cepesc: 499.207; usuário: SEVIN: 499.207; conjunto de chaves: 202607021654: 499.207. O algoritmo CEPESC é de governo e não é publicado, por isso essa assinatura não pode ser conferida; só o hash do conteúdo da parte de software é conferido.

### Autoridades certificadoras

| AC | Emitida por | Validade | Válida em 25/10/2026 | Cadeia conferida | Confere com o resumo digital do TSE |
|---|---|---|---|---|---|
| AC UE2020 | AC URNA v2 | 05/07/2021 a 01/07/2037 | sim | AC UE2020 (intermediária) | acue2020.cer |
| AC UE2022 | AC URNA v2 | 28/02/2023 a 24/02/2039 | sim | AC UE2022 (intermediária) | acue2022.cer |
| AC URNA | AC RAIZ UE | 22/07/2011 a 18/07/2026 | não | AC URNA (intermediária) | não consta |

Caminhos de cadeia nas seções: AC UE2020: 200.504; AC UE2022: 198.746; AC URNA: 99.957.

## Padrões e incoerências

### AC URNA com certificado publicado vencido

Seções com certificado emitido pela AC URNA: 99.957. Cadeia conferida: sim: 99.957. AC válida em 25/10/2026 pelo certificado publicado: não: 99.957. Certificados de urna emitidos depois de 18/07/2026 (vencimento do certificado publicado da AC URNA) e conferidos por ela: 53.

| Seção | CN | Emitido em | Modelo | Cadeia |
|---|---|---|---|---|
| `SP/71072/0254/0024` | ueao01682534 | 20/07/2026 | UE2013 | True |
| `ES/56995/0026/0355` | ueao01682925 | 20/07/2026 | UE2013 | True |
| `SP/62170/0022/0119` | ueao01682927 | 20/07/2026 | UE2013 | True |
| `ES/56995/0026/0040` | ueao01682953 | 20/07/2026 | UE2013 | True |
| `ES/56995/0026/0005` | ueao01682957 | 20/07/2026 | UE2013 | True |
| `ES/56995/0026/0318` | ueao01682962 | 20/07/2026 | UE2013 | True |
| `BA/39632/0141/0103` | ueao01844118 | 20/07/2026 | UE2015 | True |
| `GO/96016/0094/0109` | ueao01847655 | 20/07/2026 | UE2015 | True |
| `BA/37532/0032/0150` | ueao01847990 | 20/07/2026 | UE2015 | True |
| `GO/96873/0125/0088` | ueao01848317 | 20/07/2026 | UE2015 | True |
| `MA/09210/0089/0282` | ueao01844126 | 27/07/2026 | UE2015 | True |
| `SP/66818/0400/0141` | ueao01682645 | 03/08/2026 | UE2013 | True |
| `MA/08893/0047/0460` | ueao01682741 | 03/08/2026 | UE2013 | True |
| `PA/05770/0085/0040` | ueao01847529 | 03/08/2026 | UE2015 | True |
| `PA/05770/0085/0055` | ueao01847646 | 03/08/2026 | UE2015 | True |
| `PA/05770/0085/0076` | ueao01847690 | 03/08/2026 | UE2015 | True |
| `PA/04472/0050/0193` | ueao01847746 | 03/08/2026 | UE2015 | True |
| `SP/70718/0273/0082` | ueao01848224 | 03/08/2026 | UE2015 | True |
| `MT/90670/0039/0531` | ueao01681706 | 31/08/2026 | UE2013 | True |
| `PE/23515/0054/0192` | ueao01682260 | 31/08/2026 | UE2013 | True |
| `SP/64777/0394/0197` | ueao01682724 | 31/08/2026 | UE2013 | True |
| `SP/67130/0074/0076` | ueao01842388 | 31/08/2026 | UE2015 | True |
| `BA/33774/0071/0150` | ueao01843885 | 31/08/2026 | UE2015 | True |
| `MT/91677/0020/0485` | ueao01847378 | 31/08/2026 | UE2015 | True |
| `PE/25631/0116/0020` | ueao01848139 | 31/08/2026 | UE2015 | True |
| `SP/71072/0280/0564` | ueao01682525 | 03/09/2026 | UE2013 | True |
| `ES/56995/0053/0384` | ueao01682614 | 03/09/2026 | UE2013 | True |
| `PE/25330/0041/0173` | ueao01682785 | 03/09/2026 | UE2013 | True |
| `AL/28894/0031/0159` | ueao01679245 | 09/09/2026 | UE2013 | True |
| `AL/27650/0039/0092` | ueao01844078 | 09/09/2026 | UE2015 | True |
| `AL/27472/0040/0031` | ueao01847874 | 09/09/2026 | UE2015 | True |
| `AL/28673/0051/0121` | ueao01682873 | 09/09/2026 | UE2013 | True |
| `AL/27022/0039/0128` | ueao01682879 | 09/09/2026 | UE2013 | True |
| `SP/63711/0119/0173` | ueao01682105 | 12/09/2026 | UE2013 | True |
| `PB/20516/0064/0355` | ueao01682134 | 14/09/2026 | UE2013 | True |
| `BA/34134/0171/0171` | ueao01844121 | 15/09/2026 | UE2015 | True |
| `MA/08494/0093/0405` | ueao01844130 | 17/09/2026 | UE2015 | True |
| `MA/08079/0016/0032` | ueao01844165 | 17/09/2026 | UE2015 | True |
| `MA/08893/0047/0458` | ueao01844173 | 17/09/2026 | UE2015 | True |
| `MT/90670/0001/1108` | ueao01847523 | 17/09/2026 | UE2015 | True |
| `SP/65471/0052/0047` | ueao01843888 | 17/09/2026 | UE2015 | True |
| `PE/24198/0056/0386` | ueao01844163 | 18/09/2026 | UE2015 | True |
| `PE/23418/0061/0105` | ueao01847549 | 18/09/2026 | UE2015 | True |
| `PE/24198/0056/0422` | ueao01847748 | 18/09/2026 | UE2015 | True |
| `PE/23698/0132/0024` | ueao01848222 | 18/09/2026 | UE2015 | True |
| `PR/74128/0150/0144` | ueao01681993 | 22/09/2026 | UE2013 | True |
| `AL/28258/0010/0271` | ueao01848297 | 23/09/2026 | UE2015 | True |
| `PB/19658/0057/0157` | ueao01682759 | 25/09/2026 | UE2013 | True |
| `PA/04472/0004/0378` | ueao01682885 | 29/09/2026 | UE2013 | True |
| `MA/09210/0076/0643` | ueao01844177 | 01/10/2026 | UE2015 | True |
| `MA/09210/0076/0636` | ueao01848205 | 01/10/2026 | UE2015 | True |
| `SP/71072/0004/0114` | ueao01847509 | 18/10/2026 | UE2015 | True |
| `SP/62634/0214/0003` | ueao01682541 | 19/10/2026 | UE2013 | True |

A situação é a mesma do 1º turno: a assinatura confere com a chave do certificado publicado da AC URNA, que venceu em 18/07/2026. A explicação mais provável continua sendo um certificado renovado da AC URNA, com a mesma chave, que não foi publicado (ver a seção 4 de [ocorrências para o TSE](relatorio-tse-ocorrencias-2026.md)).

### CN do certificado diferente do número interno da carga

3 seção(ões) no 2º turno (no 1º turno foram 14 em 499.207).

| Seção | CN | Número interno no BU | Tipo de urna | Modelo | CN no 1º turno | Número interno no 1º turno | Fechou depois de 17:30 |
|---|---|---|---|---|---|---|---|
| `SP/64777/0393/0312` | UEAO02399743 | 02396114 | secao | UE2022 | UEAO02396114 | 02396114 | False |
| `RJ/58696/0027/0139` | UEAO02189420 | 02179194 | secao | UE2020 | UEAO02179194 | 02179194 | False |
| `ES/57932/0009/0085` | ueao01758779 | 01841837 | secao | UE2015 | ueao01841837 | 01841837 | False |

Nas três seções a assinatura do conteúdo, a do `bu.dat`, a de todos os arquivos listados e a cadeia conferem com o certificado que acompanha o `.vsc`; no 1º turno, as três tinham CN igual ao número interno. O que difere é a urna que assinou: o BU registra a carga feita para uma urna, e o arquivo foi assinado por outra. Em `ES/57932/0009/0085`, a urna que assinou (ueao01758779) é a mesma que, na seção vizinha `ES/57932/0009/0112`, aparece como `reservaEncerrandoSecao` (urna de reserva que encerra a seção, encerramento às 19h43 locais); é a única seção do 2º turno em que um mesmo certificado de urna de votação (`.vsc` do tipo `vota`) aparece em duas seções. As urnas que assinaram `SP/64777/0393/0312` (UEAO02399743) e `RJ/58696/0027/0139` (UEAO02189420) não aparecem como número interno em nenhum BU do 1º ou do 2º turno de 2026. Como no 1º turno (14 seções), a explicação provável é troca de equipamento depois da carga, e o ponto deve ser confirmado com o TSE; não é falha de hash nem de assinatura.

### Mesmo certificado em mais de uma seção

3 certificado(s), em 31 seções. Por tipo de urna: contingencia: 29; secao: 1; reservaEncerrandoSecao: 1; por tipo de arquivo de assinatura: sa: 29; vota: 2.

| Seção | CN | Certificado (SHA-256, início) | Tipo de urna |
|---|---|---|---|
| `ES/57932/0009/0085` | ueao01758779 | `2a339b6fb8c84194` | secao |
| `ES/57932/0009/0112` | ueao01758779 | `2a339b6fb8c84194` | reservaEncerrandoSecao |
| `ZZ/30708/0001/0444` | ueao01762246 | `73f3d72065ff13f4` | contingencia |
| `ZZ/29300/0001/0006` | ueao01762246 | `73f3d72065ff13f4` | contingencia |
| `ZZ/30163/0001/0647` | ueao01762246 | `73f3d72065ff13f4` | contingencia |
| `ZZ/30171/0001/1340` | ueao01762246 | `73f3d72065ff13f4` | contingencia |
| `ZZ/29394/0001/0028` | ueao01762246 | `73f3d72065ff13f4` | contingencia |
| `ZZ/29858/0001/1183` | ueao01762246 | `73f3d72065ff13f4` | contingencia |
| `ZZ/30821/0001/1524` | ueao01762246 | `73f3d72065ff13f4` | contingencia |
| `ZZ/29254/0001/0001` | ueao01762246 | `73f3d72065ff13f4` | contingencia |
| `ZZ/29750/0001/1703` | ueao01762246 | `73f3d72065ff13f4` | contingencia |
| `ZZ/29173/0001/0494` | ueao01808076 | `c6b351defd689f29` | contingencia |
| `ZZ/29297/0001/0495` | ueao01808076 | `c6b351defd689f29` | contingencia |
| `ZZ/29777/0001/0127` | ueao01808076 | `c6b351defd689f29` | contingencia |
| `ZZ/29912/0001/0150` | ueao01808076 | `c6b351defd689f29` | contingencia |
| `ZZ/29580/0001/0096` | ueao01808076 | `c6b351defd689f29` | contingencia |
| `ZZ/39102/0001/0712` | ueao01808076 | `c6b351defd689f29` | contingencia |
| `ZZ/29564/0001/0091` | ueao01808076 | `c6b351defd689f29` | contingencia |
| `ZZ/29645/0001/0380` | ueao01808076 | `c6b351defd689f29` | contingencia |
| `ZZ/29270/0001/0003` | ueao01808076 | `c6b351defd689f29` | contingencia |
| `ZZ/99473/0001/1327` | ueao01808076 | `c6b351defd689f29` | contingencia |
| `ZZ/30597/0001/1182` | ueao01808076 | `c6b351defd689f29` | contingencia |
| `ZZ/30686/0001/0443` | ueao01808076 | `c6b351defd689f29` | contingencia |
| `ZZ/38962/0001/0558` | ueao01808076 | `c6b351defd689f29` | contingencia |
| `ZZ/30333/0001/0353` | ueao01808076 | `c6b351defd689f29` | contingencia |
| `ZZ/30430/0001/0384` | ueao01808076 | `c6b351defd689f29` | contingencia |
| `ZZ/99155/0001/1504` | ueao01808076 | `c6b351defd689f29` | contingencia |
| `ZZ/30295/0001/0348` | ueao01808076 | `c6b351defd689f29` | contingencia |
| `ZZ/30325/0001/0352` | ueao01808076 | `c6b351defd689f29` | contingencia |
| `ZZ/30546/0001/1764` | ueao01808076 | `c6b351defd689f29` | contingencia |
| `ZZ/99180/0001/1228` | ueao01808076 | `c6b351defd689f29` | contingencia |

Mesmo CN com certificados diferentes dentro do 2º turno: 0 CN, 0 seções. Mesma chave pública em urnas diferentes: 0 seções. CN em minúsculas (`ueao...`): 99.957 (todas as urnas da AC URNA, como no 1º turno).

### Datas de emissão

Certificados emitidos depois da carga da urna (data e hora da carga gravadas no BU, hora local tomada como UTC-3): 0. Emitidos nos 60 dias anteriores ao 2º turno: 137 (AC UE2022: 69; AC URNA: 35; AC UE2020: 33); depois do 1º turno (04/10/2026): 6. Certificado fora da validade no momento da assinatura: 0.

Data da carga gravada no BU: 499.207 seções com data, de 15/09/2026 a 25/10/2026; até o dia do 1º turno: 496.962; entre os turnos (recarga): 2.245 (secao: 1.970; reservaSecao: 275).

| Seção | CN | Emitido em | AC | Modelo | Tipo de urna |
|---|---|---|---|---|---|
| `AL/27855/0003/0283` | UEAO02473165 | 2026-09-09T14:18:55 | AC UE2022 | UE2022 | secao |
| `TO/92185/0007/0118` | UEAO02474229 | 2026-09-09T14:19:22 | AC UE2022 | UE2022 | secao |
| `MG/41238/0333/0191` | UEAO02474483 | 2026-09-09T14:19:48 | AC UE2022 | UE2022 | secao |
| `AL/27855/0054/0537` | UEAO02474617 | 2026-09-09T14:20:15 | AC UE2022 | UE2022 | secao |
| `AL/27855/0003/0341` | UEAO02474618 | 2026-09-09T14:20:42 | AC UE2022 | UE2022 | secao |
| `MG/41238/0333/0172` | UEAO02474632 | 2026-09-09T14:21:09 | AC UE2022 | UE2022 | secao |
| `AL/28673/0051/0121` | ueao01682873 | 2026-09-09T17:29:04 | AC URNA | UE2013 | secao |
| `AL/27022/0039/0128` | ueao01682879 | 2026-09-09T17:29:06 | AC URNA | UE2013 | secao |
| `SP/62510/0298/0122` | UEAO02471392 | 2026-09-10T11:57:07 | AC UE2022 | UE2022 | secao |
| `MG/41238/0332/0106` | UEAO02473269 | 2026-09-10T11:57:33 | AC UE2022 | UE2022 | secao |
| `MG/43710/0093/0129` | UEAO02474098 | 2026-09-10T11:58:00 | AC UE2022 | UE2022 | secao |
| `MG/40444/0063/0178` | UEAO02014792 | 2026-09-11T21:24:25 | AC UE2020 | UE2020 | secao |
| `MG/40444/0063/0167` | UEAO02234674 | 2026-09-11T21:25:12 | AC UE2020 | UE2020 | secao |
| `CE/13897/0082/0379` | UEAO02463888 | 2026-09-11T21:26:04 | AC UE2022 | UE2022 | secao |
| `SP/63711/0119/0173` | ueao01682105 | 2026-09-12T17:59:14 | AC URNA | UE2013 | reservaSecao |
| `PR/78859/0199/0311` | UEAO02013546 | 2026-09-12T17:59:35 | AC UE2020 | UE2020 | secao |
| `PB/20516/0064/0355` | ueao01682134 | 2026-09-14T20:27:33 | AC URNA | UE2013 | secao |
| `MG/41238/0334/0115` | UEAO02472194 | 2026-09-14T20:28:44 | AC UE2022 | UE2022 | secao |
| `MG/41238/0331/0080` | UEAO02474149 | 2026-09-14T20:29:42 | AC UE2022 | UE2022 | reservaSecao |
| `BA/34134/0171/0171` | ueao01844121 | 2026-09-15T17:46:33 | AC URNA | UE2015 | secao |
| `PR/84557/0169/0085` | UEAO02015594 | 2026-09-15T17:47:25 | AC UE2020 | UE2020 | secao |
| `MA/08494/0093/0405` | ueao01844130 | 2026-09-17T13:04:30 | AC URNA | UE2015 | secao |
| `MA/08079/0016/0032` | ueao01844165 | 2026-09-17T13:04:33 | AC URNA | UE2015 | secao |
| `MA/08893/0047/0458` | ueao01844173 | 2026-09-17T13:04:36 | AC URNA | UE2015 | secao |
| `MT/90670/0001/1108` | ueao01847523 | 2026-09-17T13:04:38 | AC URNA | UE2015 | secao |
| `BA/37133/0118/0144` | UEAO02101728 | 2026-09-17T13:05:30 | AC UE2020 | UE2020 | secao |
| `BA/35939/0095/0123` | UEAO02471586 | 2026-09-17T13:06:32 | AC UE2022 | UE2022 | secao |
| `BA/35939/0095/0124` | UEAO02472368 | 2026-09-17T13:07:02 | AC UE2022 | UE2022 | secao |
| `SP/65471/0052/0047` | ueao01843888 | 2026-09-17T19:40:00 | AC URNA | UE2015 | secao |
| `PE/24198/0056/0386` | ueao01844163 | 2026-09-18T19:25:44 | AC URNA | UE2015 | secao |
| `PE/23418/0061/0105` | ueao01847549 | 2026-09-18T19:25:49 | AC URNA | UE2015 | secao |
| `PE/24198/0056/0422` | ueao01847748 | 2026-09-18T19:25:51 | AC URNA | UE2015 | secao |
| `PE/23698/0132/0024` | ueao01848222 | 2026-09-18T19:25:54 | AC URNA | UE2015 | secao |
| `PR/74128/0150/0144` | ueao01681993 | 2026-09-22T21:14:48 | AC URNA | UE2013 | reservaSecao |
| `MG/54038/0335/0025` | UEAO02101274 | 2026-09-22T21:16:38 | AC UE2020 | UE2020 | secao |
| `PR/75353/0178/0357` | UEAO02471491 | 2026-09-22T21:19:33 | AC UE2022 | UE2022 | reservaSecao |
| `PR/76678/0041/0247` | UEAO02472350 | 2026-09-22T21:20:02 | AC UE2022 | UE2022 | secao |
| `AL/28258/0010/0271` | ueao01848297 | 2026-09-23T16:14:54 | AC URNA | UE2015 | secao |
| `MT/90646/0005/0193` | UEAO02472373 | 2026-09-23T16:15:30 | AC UE2022 | UE2022 | secao |
| `PB/19658/0057/0157` | ueao01682759 | 2026-09-25T13:02:02 | AC URNA | UE2013 | secao |
| `PR/74810/0009/0278` | UEAO02072086 | 2026-09-25T13:03:50 | AC UE2020 | UE2020 | reservaSecao |
| `MG/54011/0347/0121` | UEAO02100634 | 2026-09-28T21:36:24 | AC UE2020 | UE2020 | reservaSecao |
| `SC/81833/0021/0126` | UEAO02472569 | 2026-09-28T21:38:52 | AC UE2022 | UE2022 | secao |
| `PE/25313/0002/0548` | UEAO02472913 | 2026-09-28T21:39:19 | AC UE2022 | UE2022 | secao |
| `PA/04472/0004/0378` | ueao01682885 | 2026-09-29T17:33:33 | AC URNA | UE2013 | secao |
| `MG/45519/0101/0131` | UEAO02102451 | 2026-09-29T17:34:33 | AC UE2020 | UE2020 | reservaSecao |
| `PR/77534/0033/0001` | UEAO02221958 | 2026-09-29T20:24:57 | AC UE2020 | UE2020 | secao |
| `MG/41238/0331/0197` | UEAO02474562 | 2026-09-29T20:25:50 | AC UE2022 | UE2022 | reservaSecao |
| `MG/50431/0226/0230` | UEAO02013432 | 2026-10-01T11:55:13 | AC UE2020 | UE2020 | secao |
| `MA/09210/0076/0643` | ueao01844177 | 2026-10-01T18:57:51 | AC URNA | UE2015 | reservaSecao |
| `MA/09210/0076/0636` | ueao01848205 | 2026-10-01T18:57:56 | AC URNA | UE2015 | reservaSecao |
| `SC/83275/0084/0099` | UEAO02472827 | 2026-10-02T11:57:59 | AC UE2022 | UE2022 | secao |
| `MG/54011/0276/0125` | UEAO02013659 | 2026-10-02T19:48:37 | AC UE2020 | UE2020 | reservaSecao |
| `MG/54011/0276/0304` | UEAO02248287 | 2026-10-02T19:49:23 | AC UE2020 | UE2020 | reservaSecao |
| `MG/40339/0009/0177` | UEAO02014666 | 2026-10-08T12:20:50 | AC UE2020 | UE2020 | secao |
| `MG/47031/0148/0078` | UEAO02103893 | 2026-10-14T16:54:19 | AC UE2020 | UE2020 | secao |
| `MG/45551/0120/0100` | UEAO02015548 | 2026-10-17T20:53:27 | AC UE2020 | UE2020 | secao |
| `SP/71072/0004/0114` | ueao01847509 | 2026-10-18T17:55:29 | AC URNA | UE2015 | secao |
| `SP/62634/0214/0003` | ueao01682541 | 2026-10-19T18:04:26 | AC URNA | UE2013 | reservaSecao |
| `MG/53716/0269/0215` | UEAO02015461 | 2026-10-22T12:55:11 | AC UE2020 | UE2020 | secao |

### Seções que fecharam depois de 17:30 (Brasília) x demais x 1º turno

Seções com certificado e horário de encerramento: 7.611 tardias (mais de 30 minutos depois das 17h de Brasília) e 490.286 demais; sem horário: 1.310.

| AC emissora | Tardias (2º turno) | Esperado pela UF | Demais (2º turno) | Mesmas seções no 1º turno | 1º turno, todas |
|---|---:|---:|---:|---:|---:|
| AC UE2020 | 3.328 (43,73%) | 3.026 (39,77%) | 197.176 (40,22%) | 3.330 (43,75%) | 200.463 (40,16%) |
| AC UE2022 | 2.770 (36,39%) | 2.921 (38,38%) | 195.976 (39,97%) | 2.768 (36,37%) | 198.759 (39,81%) |
| AC URNA | 1.513 (19,88%) | 1.663 (21,85%) | 97.134 (19,81%) | 1.513 (19,88%) | 99.985 (20,03%) |

| Algoritmo | Tardias (2º turno) | Demais (2º turno) | 1º turno, todas |
|---|---:|---:|---:|
| ECDSA | 1.513 (19,88%) | 97.134 (19,81%) | 99.985 (20,03%) |
| Ed521 | 6.098 (80,12%) | 393.152 (80,19%) | 399.222 (79,97%) |

Seções tardias por UF: RJ: 3.320, SP: 1.974, BA: 1.051, PE: 716, PB: 316, SE: 55, DF: 33, PA: 19, MA: 17, MG: 17, CE: 14, PI: 14, MT: 13, AM: 9, RS: 9, AL: 7, RN: 7, GO: 5, ES: 4, PR: 3, SC: 3, RO: 2, AP: 1, AC: 1, MS: 1.

A coluna "Esperado pela UF" aplica, a cada seção tardia, a proporção de emissores das demais seções da mesma UF. Diferença entre as tardias e o esperado indica que, dentro das mesmas UFs, as seções que fecharam tarde usam outros modelos de urna; isso não é falha de assinatura nem de certificado (emissor e algoritmo são consequência do modelo).

Proporção de seções tardias por UF e modelo (UFs com 5 ou mais seções tardias):

| UF | UE2013 | UE2015 | UE2020 | UE2022 |
|---|---:|---:|---:|---:|
| RJ | 4,71% (14/297) | 8,05% (644/8.002) | 12,79% (2.008/15.696) | 4,78% (654/13.680) |
| SP | 1,49% (24/1.614) | 1,26% (255/20.229) | 2,04% (837/41.053) | 2,11% (858/40.760) |
| BA | 3,30% (55/1.668) | 1,53% (97/6.321) | 0,66% (89/13.426) | 5,76% (810/14.061) |
| PE | 1,19% (7/587) | 1,39% (55/3.968) | 3,56% (297/8.337) | 4,19% (357/8.526) |
| PB | 12,92% (89/689) | 12,05% (225/1.867) | 0,02% (1/4.483) | 0,03% (1/3.673) |
| SE | 5,26% (1/19) | 1,10% (10/907) | 0,69% (18/2.615) | 1,09% (26/2.382) |
| DF |  | 0,29% (4/1.373) | 0,27% (11/4.004) | 1,13% (18/1.592) |
| PA | 0,00% (0/100) | 0,07% (3/4.422) | 0,14% (13/8.980) | 0,04% (3/7.325) |
| MA | 0,00% (0/676) | 0,07% (2/2.944) | 0,14% (10/7.297) | 0,07% (5/7.176) |
| MG | 0,36% (1/275) | 0,05% (4/8.806) | 0,05% (10/20.492) | 0,01% (2/22.489) |
| CE | 0,40% (3/754) | 0,03% (1/3.529) | 0,03% (3/9.627) | 0,07% (7/9.855) |
| PI | 0,00% (0/142) | 0,16% (3/1.898) | 0,10% (4/4.123) | 0,17% (7/4.062) |
| MT | 0,79% (1/127) | 0,08% (1/1.295) | 0,28% (9/3.239) | 0,06% (2/3.626) |
| AM |  | 0,09% (2/2.174) | 0,18% (5/2.793) | 0,06% (2/3.190) |
| RS | 0,11% (1/898) | 0,00% (0/3.710) | 0,05% (5/9.981) | 0,02% (3/12.958) |
| AL | 0,30% (1/338) | 0,09% (1/1.157) | 0,04% (1/2.654) | 0,14% (4/2.952) |
| RN |  | 0,20% (3/1.477) | 0,05% (2/3.830) | 0,07% (2/2.808) |
| GO | 0,29% (1/346) | 0,00% (0/2.434) | 0,00% (0/6.695) | 0,06% (4/6.211) |

| Indicador | Tardias | Demais |
|---|---|---|
| valido_no_dia | sim: 7.611 | sim: 490.286 |
| cadeia_ok | sim: 7.611 | sim: 490.286 |
| assinatura_conteudo_ok | sim: 7.611 | sim: 490.286 |
| assinatura_bu_ok | sim: 7.611 | sim: 490.286 |
| bu_hash_confere | sim: 7.611 | sim: 490.286 |
| cn_igual_numero_interno | sim: 7.611 | sim: 490.283; não: 3 |
| mesmo_cert_t1 | sim: 7.517; não: 94 | sim: 485.962; não: 4.324 |
| emitido_apos_carga | não: 7.611 | não: 490.286 |

| Emissão do certificado | Tardias | Demais |
|---|---|---|
| Mediana | 18/06/2022 | 28/05/2022 |
| Emitidos depois do 1º turno | 0 | 6 |
| Emitidos nos 30 dias anteriores | 0 | 21 |

**Comparação com a versão parcial.** A versão de 25/10/2026 (119.778 seções, 614 tardias) indicava a AC URNA em 68,24% das tardias contra 21,42% esperados pela UF. Com as 497.897 seções do Brasil, a AC URNA está em 19,88% das 7.611 tardias, contra 21,85% esperados pela UF e 19,81% nas demais: não há sobrerrepresentação dos modelos antigos no conjunto nacional. O efeito existe dentro da Paraíba (316 tardias, das quais 314 em UE2013 ou UE2015) e, em menor grau, na Bahia para UE2013 (3,30%), mas é compensado em RJ, SP e PE, onde as UE2020 e UE2022 fecharam tarde em proporção igual ou maior. Em todas as tardias, hash, assinaturas, cadeia e validade conferem como nas demais.

O horário de encerramento usado aqui vem da execução nacional de `scripts/ele2026/analisar_encerramento_t2.py` sobre as mesmas 871 partes (497.897 seções do Brasil e 1.310 do exterior). O critério deste documento é `minutos_apos_17h_bsb > 30`, que dá 7.611 seções; o `resumo.json` do script de encerramento conta 7.581 em `depois_17h30` pelo critério de faixas dele (as duas contagens vêm do mesmo arquivo e diferem só no critério), gravada em `data/parquet/2026/t2/encerramento/nacional/`.

### 1º turno x 2º turno

| Comparação | Seções |
|---|---:|
| Seções do 2º turno com certificado e com certificado no 1º turno | 499.207 |
| Mesmo certificado nos dois turnos | 494.767 |
| Certificado diferente, outra urna (CN diferente) | 4.440 |
| Certificado diferente com o mesmo CN na mesma seção | 0 |
| CN do 2º turno presente no 1º turno (qualquer seção) | 494.852 |
| Mesmo CN com certificado diferente entre os turnos | 0 |
| Certificado do 1º turno usado em outra seção no 2º | 104 |
| Certificado não visto no 1º turno | 4.355 |
| Idem, emitido depois do 1º turno | 6 |

Urna diferente da do 1º turno, por tipo de urna no BU do 2º turno: reservaSecao: 2.815; secao: 1.614; contingencia: 9; reservaEncerrandoSecao: 2. A maior parte é urna de reserva (`reservaSecao`), isto é, urna substituída; todas essas seções têm hash, assinatura e cadeia conferidos como as demais.

**Urnas que votaram em outra seção no 1º turno** (mesmo certificado):

| Seção (2º turno) | CN | Seção no 1º turno | Tipo de urna |
|---|---|---|---|
| `AC/01015/0002/0088` | UEAO02264191 | `AC/01015/0002/0093` | secao |
| `BA/38490/0011/0599` | UEAO02351617 | `BA/38490/0018/0482` | secao |
| `BA/38490/0016/0369` | UEAO02352413 | `BA/38490/0014/0512` | secao |
| `BA/38490/0017/0401` | UEAO02427178 | `BA/38490/0015/0387` | secao |
| `CE/14818/0079/0214` | ueao01671949 | `CE/15350/0079/0034` | reservaSecao |
| `CE/14818/0079/0241` | ueao01819939 | `CE/13064/0079/0246` | reservaSecao |
| `PA/04707/0075/0674` | UEAO02187576 | `PA/04707/0075/0672` | reservaSecao |
| `PA/04642/0078/0281` | UEAO02192585 | `PA/04642/0078/0249` | reservaSecao |
| `BA/38490/0013/0339` | UEAO02270014 | `BA/38490/0017/0426` | secao |
| `BA/36633/0051/0052` | ueao01767383 | `BA/37818/0181/0279` | reservaSecao |
| `SE/31232/0028/0148` | UEAO02175595 | `SE/31135/0015/0177` | secao |
| `SE/31879/0015/0300` | UEAO02044283 | `SE/31410/0006/0111` | reservaSecao |
| `SE/31194/0024/0014` | UEAO02307174 | `SE/31577/0009/0046` | secao |
| `SE/32336/0021/0075` | UEAO02303588 | `SE/31950/0034/0385` | secao |
| `SE/31453/0024/0102` | UEAO02313075 | `SE/32115/0018/0114` | secao |
| `SE/32239/0031/0042` | UEAO02045938 | `SE/31879/0015/0300` | reservaSecao |
| `SE/31291/0014/0142` | UEAO02174534 | `SE/32417/0022/0039` | secao |
| `SE/31712/0013/0042` | UEAO02341842 | `SE/32239/0031/0042` | secao |
| `SE/31054/0002/0168` | ueao01791133 | `SE/31054/0001/0346` | reservaSecao |
| `SE/31054/0027/0317` | UEAO02042066 | `SE/31798/0014/0136` | secao |
| `SE/31054/0027/0392` | UEAO02199511 | `SE/32336/0021/0264` | secao |
| `ZZ/29297/0001/0495` | ueao01808076 | `ZZ/29173/0001/0494` | contingencia |
| `ZZ/29777/0001/0127` | ueao01808076 | `ZZ/29173/0001/0494` | contingencia |
| `ZZ/29912/0001/0150` | ueao01808076 | `ZZ/29173/0001/0494` | contingencia |
| `ZZ/29580/0001/0096` | ueao01808076 | `ZZ/29173/0001/0494` | contingencia |
| `ZZ/39102/0001/0712` | ueao01808076 | `ZZ/29173/0001/0494` | contingencia |
| `ZZ/29564/0001/0091` | ueao01808076 | `ZZ/29173/0001/0494` | contingencia |
| `ZZ/29645/0001/0380` | ueao01808076 | `ZZ/29173/0001/0494` | contingencia |
| `ZZ/29270/0001/0003` | ueao01808076 | `ZZ/29173/0001/0494` | contingencia |
| `ZZ/99473/0001/1327` | ueao01808076 | `ZZ/29173/0001/0494` | contingencia |
| `ZZ/30597/0001/1182` | ueao01808076 | `ZZ/29173/0001/0494` | contingencia |
| `ZZ/30686/0001/0443` | ueao01808076 | `ZZ/29173/0001/0494` | contingencia |
| `ZZ/38962/0001/0558` | ueao01808076 | `ZZ/29173/0001/0494` | contingencia |
| `ZZ/30333/0001/0353` | ueao01808076 | `ZZ/29173/0001/0494` | contingencia |
| `ZZ/30430/0001/0384` | ueao01808076 | `ZZ/29173/0001/0494` | contingencia |
| `ZZ/99155/0001/1504` | ueao01808076 | `ZZ/29173/0001/0494` | contingencia |
| `ZZ/30295/0001/0348` | ueao01808076 | `ZZ/29173/0001/0494` | contingencia |
| `ZZ/30325/0001/0352` | ueao01808076 | `ZZ/29173/0001/0494` | contingencia |
| `ZZ/30546/0001/1764` | ueao01808076 | `ZZ/29173/0001/0494` | contingencia |
| `ZZ/99180/0001/1228` | ueao01808076 | `ZZ/29173/0001/0494` | contingencia |
| `SP/70335/0187/0123` | ueao01820267 | `SP/70335/0187/0057` | secao |
| `SP/70572/0306/0290` | ueao01835060 | `SP/70572/0306/0115` | secao |
| `SP/68756/0093/0515` | ueao01786618 | `SP/68756/0093/0201` | secao |
| `CE/13234/0067/0034` | UEAO02322962 | `CE/13234/0067/0123` | secao |
| `SP/63614/0227/0350` | ueao01836583 | `SP/63614/0227/0023` | reservaSecao |
| `SP/66397/0399/0236` | ueao01826264 | `SP/66397/0399/0335` | reservaSecao |
| `SP/72095/0144/0013` | ueao01840488 | `SP/72095/0144/0150` | reservaSecao |
| `SP/63134/0388/0114` | ueao01817812 | `SP/63134/0388/0113` | secao |
| `SP/63134/0388/0113` | ueao01819392 | `SP/63134/0388/0114` | secao |
| `BA/38490/0005/0100` | UEAO02425552 | `BA/38490/0004/0494` | secao |
| `BA/38490/0016/0047` | UEAO02288651 | `BA/38490/0007/0003` | secao |
| `PR/77437/0091/0032` | ueao01778782 | `PR/76015/0091/0016` | reservaSecao |
| `BA/39934/0183/0320` | UEAO02386005 | `BA/39934/0183/0343` | secao |
| `PE/25356/0028/0061` | ueao01816369 | `PE/25836/0026/0131` | secao |
| `PE/25577/0047/0066` | ueao01814218 | `PE/25291/0047/0001` | secao |
| `RN/16144/0018/0030` | UEAO02057882 | `RN/16055/0018/0046` | secao |
| `RN/16039/0029/0252` | UEAO02372712 | `RN/16039/0029/0121` | reservaSecao |
| `RO/00035/0020/0116` | UEAO02251902 | `RO/00035/0020/0243` | secao |
| `SC/80454/0002/0109` | UEAO02190835 | `SC/80233/0002/0092` | secao |
| `SP/64955/0191/0086` | ueao01653948 | `SP/64955/0191/0068` | reservaSecao |
| `SP/70718/0273/0195` | ueao01845124 | `SP/70718/0273/0078` | reservaSecao |
| `SP/70718/0273/0224` | ueao01823664 | `SP/70718/0273/0305` | reservaSecao |
| `SP/69051/0135/0332` | UEAO02181097 | `SP/71358/0135/0206` | secao |
| `SP/62200/0427/0049` | UEAO02182494 | `SP/72176/0427/0035` | secao |
| `GO/93734/0147/0124` | UEAO02334021 | `GO/93734/0002/0285` | reservaSecao |
| `MT/90603/0021/0198` | UEAO02006688 | `MT/90689/0021/0124` | reservaSecao |
| `SP/71579/0416/0097` | UEAO02144093 | `SP/71579/0416/0141` | secao |
| `MT/90670/0051/0240` | ueao01819757 | `MT/90670/0051/0270` | secao |
| `MT/90670/0055/0192` | ueao01839518 | `MT/91677/0049/0011` | secao |
| `SP/70998/0412/0225` | ueao01824662 | `SP/70998/0412/0385` | secao |
| `SP/70998/0412/0334` | ueao01834570 | `SP/70998/0412/0371` | reservaSecao |
| `SP/71072/0249/0561` | ueao01819671 | `SP/71072/0249/0020` | secao |
| `SP/71072/0257/0032` | UEAO02362612 | `SP/71072/0257/0305` | secao |
| `SP/71072/0352/0015` | ueao01821132 | `SP/71072/0352/0487` | reservaSecao |
| `SP/71072/0418/0150` | ueao01819430 | `SP/71072/0418/0133` | secao |
| `SP/71072/0418/0168` | UEAO02276282 | `SP/71072/0418/0073` | secao |
| `SP/71072/0418/0187` | UEAO02398894 | `SP/71072/0418/0114` | reservaSecao |
| `SP/71072/0418/0373` | UEAO02403160 | `SP/71072/0418/0418` | secao |
| `SP/71072/0418/0452` | ueao01670355 | `SP/71072/0418/0387` | secao |
| `SP/71072/0418/0475` | UEAO02397674 | `SP/71072/0418/0363` | secao |
| `SP/71153/0132/0048` | ueao01830744 | `SP/65099/0132/0289` | secao |
| `MG/41114/0023/0103` | UEAO02472105 | `MG/41114/0023/0083` | secao |
| `MG/45950/0288/0066` | UEAO02453198 | `MG/40800/0288/0219` | secao |
| `MG/46272/0141/0395` | UEAO02134760 | `MG/46833/0141/0105` | reservaSecao |
| `MG/40282/0063/0081` | UEAO02091118 | `MG/40282/0063/0198` | reservaSecao |
| `MG/40282/0063/0140` | UEAO02136884 | `MG/40282/0063/0148` | reservaSecao |
| `MG/51578/0002/0073` | UEAO02098259 | `MG/40053/0002/0106` | reservaSecao |
| `MG/41238/0029/0034` | UEAO02419683 | `MG/41238/0332/0106` | secao |
| `MG/41238/0030/0267` | UEAO02262011 | `MG/41238/0332/0028` | reservaSecao |
| `MG/45136/0100/0119` | ueao01758263 | `MG/45136/0100/0118` | reservaSecao |
| `MG/46337/0132/0065` | ueao01653361 | `MG/46337/0132/0078` | reservaSecao |
| `MG/54038/0314/0296` | UEAO02084930 | `MG/54038/0314/0063` | secao |
| `MG/54038/0314/0332` | UEAO02131647 | `MG/54038/0314/0208` | reservaSecao |
| `RJ/60011/0162/0323` | ueao01750285 | `RJ/60011/0162/0183` | secao |
| `RJ/60011/0185/0062` | ueao01668090 | `RJ/60011/0118/0361` | reservaSecao |
| `RJ/60011/0185/0158` | ueao01793722 | `RJ/60011/0022/0202` | secao |
| `RJ/60011/0214/0100` | ueao01819594 | `RJ/60011/0214/0167` | reservaSecao |
| `RJ/60011/0219/0278` | ueao01825823 | `RJ/60011/0185/0050` | secao |
| `RJ/58165/0040/0090` | UEAO02430458 | `RJ/59153/0195/0303` | secao |
| `RJ/59013/0089/0101` | UEAO02231771 | `RJ/59013/0089/0464` | reservaSecao |
| `ES/56472/0024/0104` | ueao01751052 | `ES/56472/0024/0131` | reservaSecao |
| `ES/56995/0053/0014` | ueao01656698 | `ES/56995/0053/0028` | reservaSecao |
| `ES/57053/0001/0574` | UEAO02353044 | `ES/57053/0001/0046` | reservaSecao |
| `ES/56251/0034/0918` | ueao01824539 | `ES/56251/0034/0971` | reservaSecao |

**Certificados emitidos depois do 1º turno:**

| Seção | CN | AC | Emitido em | Modelo | Tipo de urna |
|---|---|---|---|---|---|
| `SP/62634/0214/0003` | ueao01682541 | AC URNA | 2026-10-19T18:04:26 | UE2013 | reservaSecao |
| `SP/71072/0004/0114` | ueao01847509 | AC URNA | 2026-10-18T17:55:29 | UE2015 | secao |
| `MG/53716/0269/0215` | UEAO02015461 | AC UE2020 | 2026-10-22T12:55:11 | UE2020 | secao |
| `MG/40339/0009/0177` | UEAO02014666 | AC UE2020 | 2026-10-08T12:20:50 | UE2020 | secao |
| `MG/45551/0120/0100` | UEAO02015548 | AC UE2020 | 2026-10-17T20:53:27 | UE2020 | secao |
| `MG/47031/0148/0078` | UEAO02103893 | AC UE2020 | 2026-10-14T16:54:19 | UE2020 | secao |

Distribuição no 1º turno (todas as seções com certificado):

| Modelo | AC emissora | Algoritmo | Seções | % |
|---|---|---|---:|---:|
| UE2013 | AC URNA | ECDSA | 11.921 | 2,39% |
| UE2015 | AC URNA | ECDSA | 88.064 | 17,64% |
| UE2020 | AC UE2020 | Ed521 | 200.463 | 40,16% |
| UE2022 | AC UE2022 | Ed521 | 198.759 | 39,81% |

## Software, carga e modelo de urna

Fontes: tabela `bu_secao` do ClickHouse (BU decodificado de cada seção), `versoes_arquivo` (modelo gravado no `.vsc`) e `ref_secoes_2026_t1` (1º turno); conferência independente com `scripts/ele2026/software_carga_t2.py`, que decodifica de novo os 499.178 BUs do tipo `bu` direto das partes Parquet (os 29 `busa` do exterior ficam fora desse script) e grava `data/parquet/2026/t2/software/secoes_software.parquet` e `resumo.json`. Os dois caminhos dão os mesmos números; as únicas diferenças são as 29 seções `busa`, que só o banco inclui (por isso o script conta 494.752 seções com a mesma urna do 1º turno e 4.426 com urna diferente, contra 494.772 e 4.435 no banco).

| Item | Resultado |
|---|---|
| BUs decodificados | 499.207, nenhum com erro |
| Versão do software de votação | `10.23.0.0 - Praia da Barra do Cahy` em todas as 499.207 seções |
| Mesma versão do 1º turno na mesma seção | 499.207 de 499.207 |
| Fase do BU | oficial: 499.207 |
| Tipo de urna | secao: 493.464; reservaSecao: 5.712; contingencia: 29; reservaEncerrandoSecao: 2 |
| Seções com mais de uma versão de BU (software, carga ou urna mudando entre versões) | 0 |
| Códigos de carga distintos | 499.180 para 499.207 seções; o mesmo código só se repete nas 29 seções do exterior apuradas por 2 urnas de contingência (as mesmas 29 do certificado repetido, acima) |
| Histórico de códigos de carga no BU (`historicoCodigosCarga`) | 1 código: 493.495; 2: 5.495; 3: 205; 4: 11; 5: 1. Todas as 5.712 seções com mais de um código são `reservaSecao` (urna substituída) |
| CN do certificado diferente do número interno da carga | 3 (ver acima) |

**Modelo de urna** (campo de modelo do `.vsc`; coincide com a AC emissora do certificado em todas as seções):

| Modelo | 2º turno | % | 1º turno | % |
|---|---:|---:|---:|---:|
| UE2013 | 12.455 | 2,49% | 11.921 | 2,39% |
| UE2015 | 87.502 | 17,53% | 88.064 | 17,64% |
| UE2020 | 200.504 | 40,16% | 200.463 | 40,16% |
| UE2022 | 198.746 | 39,81% | 198.759 | 39,81% |

No 2º turno, 87.473 seções UE2015 têm `.vsc` do tipo `vota` e 29 do tipo `sa` (apuração do exterior).

**Urna e carga entre os turnos** (mesma seção):

| Comparação | Seções |
|---|---:|
| Seções do 2º turno com par no 1º turno | 499.207 |
| Mesma urna (número interno) | 494.772 |
| Mesma urna e mesmo código de carga | 494.402 |
| Mesma urna com código de carga novo (urna recarregada entre os turnos) | 370 (secao: 367; reservaSecao: 3) |
| Urna diferente | 4.435 (reservaSecao no 2º turno: 2.816) |

Data da carga gravada no BU: 496.962 seções carregadas entre 15/09 e 04/10/2026 (1º turno) e 2.245 depois do 1º turno (secao: 1.970; reservaSecao: 275), concentradas entre 13/10 e 24/10 (709 em 24/10). As 370 recargas da mesma urna têm data de carga entre 14/10 e 24/10/2026; nenhuma seção tem código de carga diferente do 1º turno com data de carga anterior ao 1º turno, e nenhuma tem carga posterior ao 1º turno com o mesmo código do 1º turno. Cinco seções têm carga datada do próprio dia 25/10/2026, todas com urna diferente da do 1º turno e todas com a carga antes da abertura registrada no BU (horário local da urna):

| Seção | Carga | Abertura | Encerramento | Comparecimento / aptos |
|---|---|---|---|---|
| `MS/90514/0008/0486` | 06:55 | 07:26 | 16:01 | 280 / 339 |
| `MS/91650/0051/0044` | 07:36 | 08:13 | 16:00 | 218 / 261 |
| `SP/61816/0016/0436` | 07:58 | 08:32 | 17:00 | 297 / 373 |
| `PR/74918/0056/0037` | 09:20 | 10:02 | 17:01 | 278 / 324 |
| `PR/75833/0043/0397` | 10:04 | 10:51 | 17:00 | 38 / 65 |

Duas cargas ficam entre os turnos fora da janela principal: `PR/75280/0133/0058` (09/10, reservaSecao) e `GO/92274/0119/0079` (12/10, secao). Nenhum certificado foi emitido depois da carga da urna que o usa.

**Seções que fecharam depois das 17h30 de Brasília** (`minutos_apos_17h_bsb > 30`): 7.611, todas na versão 10.23.0.0. Modelos: UE2020 3.328 (43,73%), UE2022 2.770 (36,39%), UE2015 1.315 (17,28%), UE2013 198 (2,60%); nas demais 490.286 seções, UE2020 40,22%, UE2022 39,97%, UE2015 17,52% e UE2013 2,29%. Mesma urna do 1º turno: 7.518 tardias (98,78%) e 485.966 demais (99,12%); recarga da mesma urna entre os turnos: 9 tardias e 361 demais; histórico com mais de um código de carga: 121 tardias (1,59%) e 5.549 demais (1,13%). Sem horário de encerramento: as 1.310 seções do exterior.

Consultas (ClickHouse):

```sql
-- versão, tipo de urna, histórico de carga, códigos e números internos repetidos
SELECT versao_votacao, count() FROM bu_secao FINAL GROUP BY 1;
SELECT tipo_urna, fase, count() FROM bu_secao FINAL GROUP BY 1, 2 ORDER BY 3 DESC;
SELECT qtd_codigos_carga, count() FROM bu_secao FINAL GROUP BY 1 ORDER BY 1;
SELECT count(), sum(n) FROM (SELECT codigo_carga, uniqExact(uf, cd_mun, zona, secao) AS n
    FROM bu_secao FINAL WHERE codigo_carga != '' GROUP BY codigo_carga HAVING n > 1);
-- modelo de urna pelo .vsc (13 = UE2013, 15 = UE2015, 20 = UE2020, 22 = UE2022)
SELECT tipo, modelo_urna_cod, count() FROM versoes_arquivo FINAL
WHERE tipo IN ('vota', 'sa') GROUP BY 1, 2 ORDER BY 1, 2;
-- 1º turno x 2º turno
WITH t2 AS (SELECT uf, cd_mun, zona, secao, tipo_urna, numero_interno_urna AS n2,
                   codigo_carga AS c2, versao_votacao AS v2 FROM bu_secao FINAL),
     t1 AS (SELECT uf, cd_mun, zona, secao, numero_interno_urna AS n1, codigo_carga AS c1,
                   versao_votacao AS v1 FROM ref_secoes_2026_t1 WHERE versao_votacao IS NOT NULL)
SELECT count() AS secoes_par, countIf(v1 = v2) AS mesma_versao, countIf(n1 = n2) AS mesma_urna,
       countIf(n1 = n2 AND c1 = c2) AS mesma_urna_mesma_carga,
       countIf(n1 = n2 AND c1 != c2) AS mesma_urna_carga_diferente,
       countIf(n1 != n2) AS urna_diferente,
       countIf(n1 != n2 AND tipo_urna = 'reservaSecao') AS urna_diferente_reserva
FROM t2 INNER JOIN t1 USING (uf, cd_mun, zona, secao) FORMAT Vertical;
-- resultado em 26/10/2026: 499207, 499207, 494772, 494402, 370, 4435, 2816
```

A data da carga não está no banco; ela vem do extrato do BU gravado por `certificados_t2.py extrair` (coluna `data_hora_carga` de `_partes/extrato/*.bu.parquet`) e está na coluna `data_hora_carga` de `data/parquet/2026/t2/certificados/secoes.parquet`.

## O que não pode ser verificado com dados públicos

- **Raízes e AC URNA v2.** Os certificados da AC RAIZ UE, da AC RAIZ UE v2 e da AC URNA v2 não estão publicados para download; só o SHA-512 deles consta do resumo digital do TSE. A cadeia termina na AC intermediária (AC URNA, AC UE2020, AC UE2022). O script sobe até a raiz assim que os arquivos forem colocados em `data/certificados/ac/`.
- **AC URNA renovada.** O certificado publicado da AC URNA venceu em 18/07/2026. Não há como confirmar, com dados públicos, a existência de um certificado renovado com a mesma chave.
- **Revogação.** Os certificados apontam para listas de revogação (cRLDistributionPoints) que não são públicas na internet; não foi possível conferir se algum certificado foi revogado.
- **Assinatura de software (CEPESC).** Algoritmo de governo não publicado.
- **Arquivos não guardados.** Só o `bu.dat` e o `.vsc` estão no versionamento; o hash dos demais arquivos listados no `.vsc` (RDV, log, imagens do BU) não foi comparado com os arquivos, apenas a assinatura sobre a lista de hashes.
- **Hora da urna.** A data e a hora da assinatura e da carga são as do relógio da urna, em hora local; a comparação com a validade do certificado usa tolerância de 3 horas.
- **Seções sem BU.** As 41 seções do exterior com status "Nao instalada" no aux.json não têm BU nem assinatura; todas as seções com BU têm o `.vsc` do mesmo pacote.

## Reproduzir

Execução nacional de 26/10/2026, no servidor de processamento (96 vCPU), com cópia do código e das referências em `/dev/shm/du-audit/app` e ambiente Python criado com `uv` a partir do `pyproject.toml`. Tempos: extração 12 s; verificação de 5.487.289 assinaturas de arquivo (Ed521 em Python puro e ECDSA) em 1.526 s com 72 processos; análise em cerca de 2 min.

```sh
cd /dev/shm/du-audit
P="--versoes mac=$HOME/dataurnas-mac/versoes/2026/t2/bus/parts \
   --versoes sseco=$HOME/dataurnas-mac/versoes/2026/t2-sseco/bus/parts \
   --versoes lon=$HOME/dataurnas-versoes-t2/bus/parts \
   --versoes nne=$HOME/dataurnas-versoes-t2-nne/bus/parts"
# encerramento nacional (pré-requisito do recorte das seções tardias)
venv/bin/python app/scripts/ele2026/analisar_encerramento_t2.py \
    --parts $HOME/dataurnas-mac/versoes/2026/t2/bus/parts \
    --parts $HOME/dataurnas-mac/versoes/2026/t2-sseco/bus/parts \
    --parts $HOME/dataurnas-versoes-t2/bus/parts \
    --parts $HOME/dataurnas-versoes-t2-nne/bus/parts \
    --municipios app/data/parquet/2026/t2/encerramento/municipios.json \
    --saida out/encerramento --workers 32
# certificados e assinaturas
venv/bin/python app/scripts/ele2026/certificados_t2.py extrair $P --saida out/certificados --processos 64
venv/bin/python app/scripts/ele2026/certificados_t2.py verificar --saida out/certificados \
    --ac app/data/certificados/ac --processos 72 --todas-fracao 1
venv/bin/python app/scripts/ele2026/certificados_t2.py analisar $P --saida out/certificados \
    --ac app/data/certificados/ac --encerramento out/encerramento/secoes_encerramento.parquet \
    --t1-catalogo app/data/parquet/2026/integridade/secoes.parquet \
    --t1-bu app/data/parquet/2026/secoes_2026.parquet --todas-fracao 1 \
    --relatorio out/certificados-2turno-2026.md
# software e carga
venv/bin/python app/scripts/ele2026/software_carga_t2.py \
    --dir $HOME/dataurnas-mac/versoes/2026/t2/bus/parts \
    --dir $HOME/dataurnas-mac/versoes/2026/t2-sseco/bus/parts \
    --dir $HOME/dataurnas-versoes-t2/bus/parts \
    --dir $HOME/dataurnas-versoes-t2-nne/bus/parts \
    --encerramento out/encerramento/secoes_encerramento.parquet \
    --t1 app/data/parquet/2026/secoes_2026.parquet --saida out/software
```

As saídas foram copiadas para `data/parquet/2026/t2/certificados/`, `data/parquet/2026/t2/software/` e `data/parquet/2026/t2/encerramento/nacional/` (pastas ignoradas pelo git). O relatório gerado pelo script foi completado à mão com as seções "Escala nacional", "Coleta das assinaturas", "Software, carga e modelo de urna" e os comentários sobre as três seções com CN diferente e sobre a comparação com a versão parcial.
