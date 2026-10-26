# Certificados e assinaturas das urnas: 2º turno de 2026

Auditoria independente dos arquivos públicos do 2º turno das Eleições Gerais de 2026 (25/10/2026, pleito 3221, eleição 6258). Gerado em 2026-10-25T23:43:28 por `scripts/ele2026/certificados_t2.py`, só com arquivos já baixados (nenhum download novo do TSE). Tabela por seção: `data/parquet/2026/t2/certificados/secoes.parquet`; números completos: `data/parquet/2026/t2/certificados/resumo.json`.

## Resultado

Nenhuma divergência de hash, nenhuma assinatura inválida e nenhuma cadeia quebrada nas 119.778 seções verificadas.

| Verificação | Resultado |
|---|---|
| SHA-512 do bu.dat igual ao valor assinado no .vsc (partes HW e SW) | sim: 119.778 |
| Nome do bu.dat igual ao listado no .vsc | sim: 119.778 |
| SHA-512 do conteúdo assinado igual ao hash autoassinado, parte de hardware | sim: 119.778 |
| Idem, parte de software | sim: 119.778 |
| Lista de hashes igual nas partes de software e de hardware | sim: 119.778 |
| Assinatura de hardware do conteúdo assinado (chave do certificado da urna) | sim: 119.778 |
| Assinatura de hardware do bu.dat | sim: 119.778 |
| Assinatura de hardware de cada arquivo listado no .vsc | 119.778 seções; assinaturas válidas: 1.313.570; inválidas: 0 |
| Certificado da urna assinado pela AC emissora | sim: 119.778 |
| Certificado da urna válido em 25/10/2026 | sim: 119.778 |
| Certificado válido no momento da assinatura (hora da urna, tolerância de 3 h) | sim: 119.778 |
| CN do certificado igual ao usuário da assinatura de hardware | sim: 119.778 |
| CN do certificado igual ao número interno da urna na carga do BU | sim: 119.778 |
| SHA-512 do arquivo guardado igual ao registrado na coleta (BU / .vsc) | sim: 136.871 / sim: 119.778 |

## Cobertura

Os arquivos do 2º turno ainda estão sendo coletados; os números abaixo são os dos arquivos disponíveis no momento da geração e mudam quando o script é executado de novo.

| Item | Seções |
|---|---:|
| Seções com algum arquivo guardado | 136.871 |
| Com BU | 136.871 |
| Com .vsc | 119.778 |
| Com BU e .vsc da mesma versão (verificáveis) | 119.778 |
| BU sem .vsc (assinatura ainda não buscada) | 17.093 |
| .vsc sem BU | 0 |
| Com certificado e assinatura verificada | 119.778 |
| Com todas as assinaturas de arquivo verificadas | 119.778 |
| Com mais de uma versão (hash) publicada | 0 |

UFs presentes: AC, AL, AM, AP, BA, CE, MA, PA, PB, PI, RR, SE, SP, TO, ZZ.

| UF | Com BU | Com .vsc | Par completo |
|---|---:|---:|---:|
| AC | 2.249 | 1.859 | 1.859 |
| AL | 7.078 | 5.578 | 5.578 |
| AM | 8.001 | 6.852 | 6.852 |
| AP | 1.911 | 1.676 | 1.676 |
| BA | 34.641 | 27.187 | 27.187 |
| CE | 15.615 | 12.739 | 12.739 |
| MA | 15.764 | 13.774 | 13.774 |
| PA | 16.506 | 15.026 | 15.026 |
| PB | 10.712 | 10.712 | 10.712 |
| PI | 10.225 | 10.225 | 10.225 |
| RR | 1.519 | 1.519 | 1.519 |
| SE | 5.923 | 5.923 | 5.923 |
| SP | 1.033 | 1.014 | 1.014 |
| TO | 4.384 | 4.384 | 4.384 |
| ZZ | 1.310 | 1.310 | 1.310 |

## Como cada verificação foi feita

1. **Hash do BU.** O SHA-512 do `bu.dat` guardado é recalculado a partir dos bytes e comparado com o hash que o `.vsc` traz para o mesmo nome de arquivo, tanto na parte de hardware quanto na de software. Também se confere o SHA-512 do conteúdo assinado (a lista de arquivos e hashes) contra o hash autoassinado de cada parte. Dos arquivos listados no `.vsc`, só o `bu.dat` está guardado no versionamento; os demais (RDV, log, imagens) não foram baixados nesta coleta.
2. **Assinatura.** A assinatura de hardware do conteúdo assinado é conferida com a chave pública do certificado que acompanha o `.vsc` (Ed521 nas UE2020 e UE2022, ECDSA P-521 com SHA-512 nas UE2013 e UE2015). Como o conteúdo assinado contém o hash de todos os arquivos, essa assinatura já autentica a lista inteira. Além dela, a assinatura individual do `bu.dat` é conferida em todas as seções, e a de cada um dos arquivos listados, na amostra indicada na cobertura.
3. **Cadeia.** A assinatura do certificado da urna é conferida com a chave pública da AC emissora (certificados em `data/certificados/ac/`), e a da AC com a da AC acima dela quando esse certificado está disponível.
4. **Padrões.** Cruzamento com o número interno da carga gravado no BU, com o horário de encerramento (`data/parquet/2026/t2/encerramento/secoes_encerramento.parquet`) e com o catálogo do 1º turno (`data/parquet/2026/integridade/secoes.parquet`, 499.207 seções com certificado, e `data/parquet/2026/secoes_2026.parquet`).

## Certificados das urnas

| Modelo | AC emissora | Algoritmo da chave | Seções | % |
|---|---|---|---:|---:|
| UE2013 | AC URNA | ECDSA | 4.383 | 3,66% |
| UE2015 | AC URNA | ECDSA | 20.275 | 16,93% |
| UE2020 | AC UE2020 | Ed521 | 49.214 | 41,09% |
| UE2022 | AC UE2022 | Ed521 | 45.906 | 38,33% |

Curvas: E-521: 95.120; secp521r1: 24.658. Algoritmo da assinatura dos certificados (OID): 1.3.6.1.4.1.44588.2.1: 95.120; 1.2.840.10045.4.3.4: 24.658. Versão X.509: v3: 119.778. Hash da assinatura de hardware: sha512: 119.778.

Certificados distintos: 119.751; chaves públicas distintas: 119.751; pares emissor e número de série distintos: 119.751.

| AC emissora | Modelo | Seções | Emitidos entre | Vencem entre | Duração (dias) | Validade publicada da AC até |
|---|---|---:|---|---|---|---|
| AC UE2020 | UE2020 | 49.214 | 23/04/2022 a 17/09/2026 | 31/12/2035 a 15/01/2038 | 5000: 48.960, 4896: 24, 4882: 17, 4861: 16 | 01/07/2037 |
| AC UE2022 | UE2022 | 45.906 | 19/05/2023 a 17/09/2026 | 25/01/2037 a 15/01/2038 | 5000: 45.179, 4872: 165, 4942: 104, 4941: 44 | 24/02/2039 |
| AC URNA | UE2013 | 4.383 | 30/07/2013 a 29/09/2026 | 08/04/2027 a 15/01/2038 | 5000: 4.370, 4131: 2, 4840: 2, 4838: 1 | 18/07/2026 |
| AC URNA | UE2015 | 20.275 | 14/06/2016 a 01/10/2026 | 21/02/2030 a 31/12/2037 | 5000: 20.246, 4168: 4, 4841: 3, 4123: 2 | 18/07/2026 |

**Extensões.** Conjuntos encontrados: `authorityKeyIdentifier,basicConstraints,cRLDistributionPoints,certificatePolicies,keyUsage,subjectKeyIdentifier` (119.778). Extensões fora do conjunto esperado (basicConstraints, keyUsage, subjectKeyIdentifier, authorityKeyIdentifier, cRLDistributionPoints, certificatePolicies): nenhum. Extensões marcadas como críticas: nenhuma: 119.778. basicConstraints com CA: não: 119.778. keyUsage: digital_signature,key_encipherment,data_encipherment: 119.778.

**Emissão por ano:** 2013: 4.242, 2014: 34, 2015: 3, 2016: 20.112, 2017: 32, 2018: 79, 2019: 11, 2020: 42, 2022: 48.526, 2023: 36.486, 2024: 9.858, 2025: 203, 2026: 150.

**Emissão a partir de junho de 2026, por mês:** 2026-06: 33, 2026-07: 15, 2026-08: 26, 2026-09: 29, 2026-10: 2.

**Assinatura de software.** Algoritmo: cepesc: 119.778; usuário: SEVIN: 119.778; conjunto de chaves: 202607021654: 119.778. O algoritmo CEPESC é de governo e não é publicado, por isso essa assinatura não pode ser conferida; só o hash do conteúdo da parte de software é conferido.

### Autoridades certificadoras

| AC | Emitida por | Validade | Válida em 25/10/2026 | Cadeia conferida | Confere com o resumo digital do TSE |
|---|---|---|---|---|---|
| AC UE2020 | AC URNA v2 | 05/07/2021 a 01/07/2037 | sim | AC UE2020 (intermediária) | acue2020.cer |
| AC UE2022 | AC URNA v2 | 28/02/2023 a 24/02/2039 | sim | AC UE2022 (intermediária) | acue2022.cer |
| AC URNA | AC RAIZ UE | 22/07/2011 a 18/07/2026 | não | AC URNA (intermediária) | não consta |

Caminhos de cadeia nas seções: AC UE2020: 49.214; AC UE2022: 45.906; AC URNA: 24.658.

## Padrões e incoerências

### AC URNA com certificado publicado vencido

Seções com certificado emitido pela AC URNA: 24.658. Cadeia conferida: sim: 24.658. AC válida em 25/10/2026 pelo certificado publicado: não: 24.658. Certificados de urna emitidos depois de 18/07/2026 (vencimento do certificado publicado da AC URNA) e conferidos por ela: 21.

| Seção | CN | Emitido em | Modelo | Cadeia |
|---|---|---|---|---|
| `BA/37532/0032/0150` | ueao01847990 | 20/07/2026 | UE2015 | True |
| `MA/09210/0089/0282` | ueao01844126 | 27/07/2026 | UE2015 | True |
| `MA/08893/0047/0460` | ueao01682741 | 03/08/2026 | UE2013 | True |
| `PA/05770/0085/0040` | ueao01847529 | 03/08/2026 | UE2015 | True |
| `PA/05770/0085/0055` | ueao01847646 | 03/08/2026 | UE2015 | True |
| `PA/05770/0085/0076` | ueao01847690 | 03/08/2026 | UE2015 | True |
| `PA/04472/0050/0193` | ueao01847746 | 03/08/2026 | UE2015 | True |
| `BA/33774/0071/0150` | ueao01843885 | 31/08/2026 | UE2015 | True |
| `AL/28894/0031/0159` | ueao01679245 | 09/09/2026 | UE2013 | True |
| `AL/27650/0039/0092` | ueao01844078 | 09/09/2026 | UE2015 | True |
| `AL/27472/0040/0031` | ueao01847874 | 09/09/2026 | UE2015 | True |
| `AL/27022/0039/0128` | ueao01682879 | 09/09/2026 | UE2013 | True |
| `PB/20516/0064/0355` | ueao01682134 | 14/09/2026 | UE2013 | True |
| `BA/34134/0171/0171` | ueao01844121 | 15/09/2026 | UE2015 | True |
| `MA/08494/0093/0405` | ueao01844130 | 17/09/2026 | UE2015 | True |
| `MA/08893/0047/0458` | ueao01844173 | 17/09/2026 | UE2015 | True |
| `AL/28258/0010/0271` | ueao01848297 | 23/09/2026 | UE2015 | True |
| `PB/19658/0057/0157` | ueao01682759 | 25/09/2026 | UE2013 | True |
| `PA/04472/0004/0378` | ueao01682885 | 29/09/2026 | UE2013 | True |
| `MA/09210/0076/0643` | ueao01844177 | 01/10/2026 | UE2015 | True |
| `MA/09210/0076/0636` | ueao01848205 | 01/10/2026 | UE2015 | True |

A situação é a mesma do 1º turno: a assinatura confere com a chave do certificado publicado da AC URNA, que venceu em 18/07/2026. A explicação mais provável continua sendo um certificado renovado da AC URNA, com a mesma chave, que não foi publicado (ver a seção 4 de [ocorrências para o TSE](relatorio-tse-ocorrencias-2026.md)).

### CN do certificado diferente do número interno da carga

0 seção(ões) no 2º turno (no 1º turno foram 14 em 499.207).

### Mesmo certificado em mais de uma seção

2 certificado(s), em 29 seções. Por tipo de urna: contingencia: 29; por tipo de arquivo de assinatura: sa: 29.

Todas essas seções têm arquivo de assinatura do sistema de apuração (`.vsc` do tipo `sa`), emitido por uma mesma urna de apuração para várias seções (votação por cédula); por isso o mesmo certificado aparece em mais de uma seção. No 1º turno ocorreu o mesmo (1 certificado em 29 seções do exterior).

| Seção | CN | Certificado (SHA-256, início) | Tipo de urna |
|---|---|---|---|
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

Mesmo CN com certificados diferentes dentro do 2º turno: 0 CN, 0 seções. Mesma chave pública em urnas diferentes: 0 seções. CN em minúsculas (`ueao...`): 24.658 (todas as urnas da AC URNA, como no 1º turno).

### Datas de emissão

Certificados emitidos depois da carga da urna (data e hora da carga gravadas no BU, hora local tomada como UTC-3): 0. Emitidos nos 60 dias anteriores ao 2º turno: 49 (AC UE2022: 29; AC URNA: 14; AC UE2020: 6); depois do 1º turno (04/10/2026): 0. Certificado fora da validade no momento da assinatura: 0.

Data da carga gravada no BU: 136.871 seções com data, de 15/09/2026 a 24/10/2026; até o dia do 1º turno: 136.226; entre os turnos (recarga): 645 (secao: 564; reservaSecao: 81).

| Seção | CN | Emitido em | AC | Modelo | Tipo de urna |
|---|---|---|---|---|---|
| `BA/33774/0071/0150` | ueao01843885 | 2026-08-31T15:59:29 | AC URNA | UE2015 | secao |
| `BA/33634/0075/0240` | UEAO02016370 | 2026-08-31T16:02:52 | AC UE2020 | UE2020 | secao |
| `PI/12190/0001/0305` | UEAO02041252 | 2026-08-31T16:03:14 | AC UE2020 | UE2020 | secao |
| `MA/07978/0032/0173` | UEAO02101423 | 2026-08-31T16:04:23 | AC UE2020 | UE2020 | secao |
| `BA/33634/0070/0109` | UEAO02101595 | 2026-08-31T16:04:46 | AC UE2020 | UE2020 | secao |
| `SP/63134/0303/0195` | UEAO02101631 | 2026-08-31T16:05:32 | AC UE2020 | UE2020 | secao |
| `PI/12190/0097/0447` | UEAO02395949 | 2026-08-31T16:08:49 | AC UE2022 | UE2022 | secao |
| `PI/12190/0097/0403` | UEAO02465612 | 2026-08-31T16:09:15 | AC UE2022 | UE2022 | secao |
| `PI/12190/0097/0551` | UEAO02471130 | 2026-08-31T16:11:01 | AC UE2022 | UE2022 | secao |
| `PI/12190/0097/0442` | UEAO02471199 | 2026-08-31T16:11:54 | AC UE2022 | UE2022 | secao |
| `BA/37397/0119/0148` | UEAO02472016 | 2026-08-31T16:12:47 | AC UE2022 | UE2022 | secao |
| `MA/08958/0083/0121` | UEAO02472062 | 2026-08-31T16:13:14 | AC UE2022 | UE2022 | secao |
| `PI/12190/0097/0401` | UEAO02472424 | 2026-08-31T16:14:33 | AC UE2022 | UE2022 | secao |
| `BA/38970/0088/0207` | UEAO02472842 | 2026-08-31T16:15:54 | AC UE2022 | UE2022 | secao |
| `BA/38393/0111/0112` | UEAO02472971 | 2026-08-31T16:17:14 | AC UE2022 | UE2022 | secao |
| `PB/19291/0055/0004` | UEAO02474471 | 2026-08-31T16:21:42 | AC UE2022 | UE2022 | secao |
| `PI/12190/0097/0564` | UEAO02474586 | 2026-08-31T16:22:10 | AC UE2022 | UE2022 | secao |
| `PI/12190/0097/0443` | UEAO02474662 | 2026-08-31T16:22:37 | AC UE2022 | UE2022 | secao |
| `CE/13897/0003/0516` | UEAO02464105 | 2026-09-03T17:45:36 | AC UE2022 | UE2022 | secao |
| `CE/13897/0002/0759` | UEAO02465624 | 2026-09-03T17:46:30 | AC UE2022 | UE2022 | secao |
| `CE/13897/0003/0610` | UEAO02471070 | 2026-09-03T17:46:56 | AC UE2022 | UE2022 | secao |
| `CE/13897/0003/0614` | UEAO02472853 | 2026-09-03T17:48:17 | AC UE2022 | UE2022 | secao |
| `CE/13897/0002/0398` | UEAO02472854 | 2026-09-03T17:48:44 | AC UE2022 | UE2022 | secao |
| `CE/13897/0002/0370` | UEAO02474105 | 2026-09-03T17:50:31 | AC UE2022 | UE2022 | secao |
| `AL/28894/0031/0159` | ueao01679245 | 2026-09-09T14:02:59 | AC URNA | UE2013 | secao |
| `AL/27650/0039/0092` | ueao01844078 | 2026-09-09T14:04:18 | AC URNA | UE2015 | secao |
| `AL/27472/0040/0031` | ueao01847874 | 2026-09-09T14:04:28 | AC URNA | UE2015 | secao |
| `AL/27855/0054/0536` | UEAO02464496 | 2026-09-09T14:11:19 | AC UE2022 | UE2022 | secao |
| `AL/27855/0003/0367` | UEAO02470882 | 2026-09-09T14:12:39 | AC UE2022 | UE2022 | reservaSecao |
| `AL/27855/0003/0288` | UEAO02470884 | 2026-09-09T14:13:06 | AC UE2022 | UE2022 | secao |
| `TO/73440/0029/0531` | UEAO02472262 | 2026-09-09T14:14:52 | AC UE2022 | UE2022 | secao |
| `AL/28479/0012/0156` | UEAO02472923 | 2026-09-09T14:18:02 | AC UE2022 | UE2022 | secao |
| `AL/27855/0003/0283` | UEAO02473165 | 2026-09-09T14:18:55 | AC UE2022 | UE2022 | secao |
| `TO/92185/0007/0118` | UEAO02474229 | 2026-09-09T14:19:22 | AC UE2022 | UE2022 | secao |
| `AL/27855/0054/0537` | UEAO02474617 | 2026-09-09T14:20:15 | AC UE2022 | UE2022 | secao |
| `AL/27022/0039/0128` | ueao01682879 | 2026-09-09T17:29:06 | AC URNA | UE2013 | secao |
| `CE/13897/0082/0379` | UEAO02463888 | 2026-09-11T21:26:04 | AC UE2022 | UE2022 | secao |
| `PB/20516/0064/0355` | ueao01682134 | 2026-09-14T20:27:33 | AC URNA | UE2013 | secao |
| `BA/34134/0171/0171` | ueao01844121 | 2026-09-15T17:46:33 | AC URNA | UE2015 | secao |
| `MA/08494/0093/0405` | ueao01844130 | 2026-09-17T13:04:30 | AC URNA | UE2015 | secao |
| `MA/08893/0047/0458` | ueao01844173 | 2026-09-17T13:04:36 | AC URNA | UE2015 | secao |
| `BA/37133/0118/0144` | UEAO02101728 | 2026-09-17T13:05:30 | AC UE2020 | UE2020 | secao |
| `BA/35939/0095/0123` | UEAO02471586 | 2026-09-17T13:06:32 | AC UE2022 | UE2022 | secao |
| `BA/35939/0095/0124` | UEAO02472368 | 2026-09-17T13:07:02 | AC UE2022 | UE2022 | secao |
| `AL/28258/0010/0271` | ueao01848297 | 2026-09-23T16:14:54 | AC URNA | UE2015 | secao |
| `PB/19658/0057/0157` | ueao01682759 | 2026-09-25T13:02:02 | AC URNA | UE2013 | secao |
| `PA/04472/0004/0378` | ueao01682885 | 2026-09-29T17:33:33 | AC URNA | UE2013 | secao |
| `MA/09210/0076/0643` | ueao01844177 | 2026-10-01T18:57:51 | AC URNA | UE2015 | reservaSecao |
| `MA/09210/0076/0636` | ueao01848205 | 2026-10-01T18:57:56 | AC URNA | UE2015 | reservaSecao |

### Seções que fecharam depois de 17:30 (Brasília) x demais x 1º turno

Seções com certificado e horário de encerramento: 614 tardias (mais de 30 minutos depois das 17h de Brasília) e 117.854 demais; sem horário: 1.310.

| AC emissora | Tardias (2º turno) | Esperado pela UF | Demais (2º turno) | Mesmas seções no 1º turno | 1º turno, todas |
|---|---:|---:|---:|---:|---:|
| AC UE2020 | 97 (15,80%) | 255 (41,60%) | 49.117 (41,68%) | 97 (15,80%) | 200.463 (40,16%) |
| AC UE2022 | 98 (15,96%) | 227 (36,98%) | 45.808 (38,87%) | 98 (15,96%) | 198.759 (39,81%) |
| AC URNA | 419 (68,24%) | 131 (21,42%) | 22.929 (19,46%) | 419 (68,24%) | 99.985 (20,03%) |

| Algoritmo | Tardias (2º turno) | Demais (2º turno) | 1º turno, todas |
|---|---:|---:|---:|
| ECDSA | 419 (68,24%) | 22.929 (19,46%) | 99.985 (20,03%) |
| Ed521 | 195 (31,76%) | 94.925 (80,54%) | 399.222 (79,97%) |

Seções tardias por UF: PB: 316, BA: 202, SE: 55, PI: 14, PA: 7, AM: 5, CE: 5, AL: 5, MA: 4, AP: 1.

A coluna "Esperado pela UF" aplica, a cada seção tardia, a proporção de emissores das demais seções da mesma UF. Diferença entre as tardias e o esperado indica que, dentro das mesmas UFs, as seções que fecharam tarde usam outros modelos de urna; isso não é falha de assinatura nem de certificado (emissor e algoritmo são consequência do modelo).

**Padrão encontrado:** a AC URNA aparece em 68,24% das seções tardias, contra 21,42% esperados pela composição de UF. A AC emissora acompanha o modelo da urna, então o padrão é de modelo de hardware (urnas mais antigas fecharam mais tarde), e não de certificado: nessas seções a cadeia, a validade e as assinaturas conferem como nas demais (tabela de indicadores abaixo).

Proporção de seções tardias por UF e modelo (UFs com 5 ou mais seções tardias):

| UF | UE2013 | UE2015 | UE2020 | UE2022 |
|---|---:|---:|---:|---:|
| PB | 12,92% (89/689) | 12,05% (225/1.867) | 0,02% (1/4.483) | 0,03% (1/3.673) |
| BA | 0,77% (8/1.040) | 1,49% (78/5.242) | 0,61% (64/10.480) | 0,50% (52/10.425) |
| SE | 5,26% (1/19) | 1,10% (10/907) | 0,69% (18/2.615) | 1,09% (26/2.382) |
| PI | 0,00% (0/142) | 0,16% (3/1.898) | 0,10% (4/4.123) | 0,17% (7/4.062) |
| PA | 0,00% (0/64) | 0,07% (2/2.817) | 0,05% (4/7.670) | 0,02% (1/4.475) |
| AL | 0,00% (0/288) | 0,10% (1/967) | 0,00% (0/2.105) | 0,18% (4/2.218) |
| AM |  | 0,05% (1/1.950) | 0,13% (3/2.325) | 0,04% (1/2.577) |
| CE | 0,00% (0/526) | 0,00% (0/1.720) | 0,02% (1/5.126) | 0,07% (4/5.367) |

| Indicador | Tardias | Demais |
|---|---|---|
| valido_no_dia | sim: 614 | sim: 117.854 |
| cadeia_ok | sim: 614 | sim: 117.854 |
| assinatura_conteudo_ok | sim: 614 | sim: 117.854 |
| assinatura_bu_ok | sim: 614 | sim: 117.854 |
| bu_hash_confere | sim: 614 | sim: 117.854 |
| cn_igual_numero_interno | sim: 614 | sim: 117.854 |
| mesmo_cert_t1 | sim: 604; não: 10 | sim: 116.678; não: 1.176 |
| emitido_apos_carga | não: 614 | não: 117.854 |

| Emissão do certificado | Tardias | Demais |
|---|---|---|
| Mediana | 29/07/2016 | 13/06/2022 |
| Emitidos depois do 1º turno | 0 | 0 |
| Emitidos nos 30 dias anteriores | 0 | 4 |

### 1º turno x 2º turno

| Comparação | Seções |
|---|---:|
| Seções do 2º turno com certificado e com certificado no 1º turno | 119.778 |
| Mesmo certificado nos dois turnos | 118.570 |
| Certificado diferente, outra urna (CN diferente) | 1.208 |
| Certificado diferente com o mesmo CN na mesma seção | 0 |
| CN do 2º turno presente no 1º turno (qualquer seção) | 118.591 |
| Mesmo CN com certificado diferente entre os turnos | 0 |
| Certificado do 1º turno usado em outra seção no 2º | 40 |
| Certificado não visto no 1º turno | 1.187 |
| Idem, emitido depois do 1º turno | 0 |

Urna diferente da do 1º turno, por tipo de urna no BU do 2º turno: reservaSecao: 756; secao: 443; contingencia: 9. A maior parte é urna de reserva (`reservaSecao`), isto é, urna substituída; todas essas seções têm hash, assinatura e cadeia conferidos como as demais.

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

Distribuição no 1º turno (todas as seções com certificado):

| Modelo | AC emissora | Algoritmo | Seções | % |
|---|---|---|---:|---:|
| UE2013 | AC URNA | ECDSA | 11.921 | 2,39% |
| UE2015 | AC URNA | ECDSA | 88.064 | 17,64% |
| UE2020 | AC UE2020 | Ed521 | 200.463 | 40,16% |
| UE2022 | AC UE2022 | Ed521 | 198.759 | 39,81% |

## O que não pode ser verificado com dados públicos

- **Raízes e AC URNA v2.** Os certificados da AC RAIZ UE, da AC RAIZ UE v2 e da AC URNA v2 não estão publicados para download; só o SHA-512 deles consta do resumo digital do TSE. A cadeia termina na AC intermediária (AC URNA, AC UE2020, AC UE2022). O script sobe até a raiz assim que os arquivos forem colocados em `data/certificados/ac/`.
- **AC URNA renovada.** O certificado publicado da AC URNA venceu em 18/07/2026. Não há como confirmar, com dados públicos, a existência de um certificado renovado com a mesma chave.
- **Revogação.** Os certificados apontam para listas de revogação (cRLDistributionPoints) que não são públicas na internet; não foi possível conferir se algum certificado foi revogado.
- **Assinatura de software (CEPESC).** Algoritmo de governo não publicado.
- **Arquivos não guardados.** Só o `bu.dat` e o `.vsc` estão no versionamento; o hash dos demais arquivos listados no `.vsc` (RDV, log, imagens do BU) não foi comparado com os arquivos, apenas a assinatura sobre a lista de hashes.
- **Hora da urna.** A data e a hora da assinatura e da carga são as do relógio da urna, em hora local; a comparação com a validade do certificado usa tolerância de 3 horas.
- **Cobertura parcial.** Parte das seções ainda não tem `.vsc` guardado; ver a tabela de cobertura.

## Reproduzir

```sh
nice -n 20 .venv/bin/python scripts/ele2026/certificados_t2.py tudo --processos 3 \
    --relatorio docs/certificados-2turno-2026.md
# outra cópia dos arquivos (por exemplo, a de Londres):
#   --versoes t2=data/versoes/2026/t2/bus/parts --versoes londres=/caminho/parts
```
