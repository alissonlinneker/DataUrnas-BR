# Seções que encerraram depois do horário no 2º turno de 2026 e impacto possível da prorrogação

Levantamento de 25 e 26/10/2026 sobre as seções que encerraram a votação depois das 17h de Brasília no 2º turno presidencial (25/10/2026), quando a Rcl 101.673/BA (STF) prorrogou o recebimento de votos até as 19h nos locais onde as urnas ainda não tinham sido fechadas (contexto em `docs/prorrogacao-votacao-2turno-2026.md`). O objetivo é descrever, com os arquivos públicos das urnas, onde houve encerramento tardio, quantos eleitores votaram depois das 17h e quanto isso poderia pesar na diferença final entre 13 (Lula) e 22 (Flávio Bolsonaro). É um levantamento descritivo: não estima efeito causal e não faz juízo sobre a decisão.

Script: `scripts/ele2026/impacto_prorrogacao_t2.py` (testes em `tests/ele2026/test_impacto_prorrogacao_t2.py`). Saída, fora do git: `data/parquet/2026/t2/impacto/` (`resumo.json`, `tabelas.md`, `secoes_t1_t2.parquet`, `amostra_logs.parquet`, `logs_contagens.jsonl`).

## Resumo: descartar os votos dados depois das 17:00:00

| Item | Valor |
|---|---|
| Margem oficial final 13 menos 22 (TSE, 25/10/2026 23:09:21, 499.247 de 499.248 seções) | **4.429.967** (64.255.969 a 59.826.002) |
| Votos computados depois das 17:00:00 de Brasília, contados no log, nas 5.389 seções baixadas | **1.763** |
| dos quais nas 1.459 seções que encerraram depois de 17:30 | **1.080** |
| Estimativa para o país inteiro (log + estimativa para as seções sem log, ver método) | **cerca de 16.182** |
| Margem se todos os 16.182 fossem retirados do 13 | **4.413.785** |
| Margem se fossem retirados na fatia de cada seção | **4.425.907** |
| Votos depois das 17h necessários para inverter, retirando todos do 13 | 4.429.968, ou seja, **274 vezes** a estimativa nacional |
| Idem, retirando na fatia de cada seção | 17,66 milhões, **1.091 vezes** a estimativa nacional (mais do que o comparecimento das seções tardias e intermediárias juntas) |

Com o corte "além do normal" (votos depois das 17h acima do que é típico de fila), o volume cai para algumas centenas de votos:

| Corte | Votos retirados | Margem se todos do 13 | Margem na fatia da seção | Vezes o observado para inverter (todos do 13) |
|---|---|---|---|---|
| Todos os votos depois das 17:00:00, país inteiro (estimativa) | 16.182 | 4.413.785 | 4.425.907 | 274 |
| Todos os votos depois das 17:00:00, só tardias e intermediárias (contagem exata) | 1.508 | 4.428.459 | 4.429.360 | 2.938 |
| Além do normal: descontando a mesma seção no 1º turno | 355 | 4.429.612 | 4.429.841 | 12.479 |
| Além do normal: descontando a taxa das seções que fecharam no horário no 2º turno | 1.360 | 4.428.607 | 4.429.417 | 3.257 |
| Teto hipotético: fila do 1º turno inteira (3.722.948 votos depois das 17h em todo o país em 04/10) | 3.722.948 | 707.019 | 3.629.095 | 1,19 |

Nenhum cenário, nem o mais desfavorável ao 13, inverte o resultado. O último caso é deliberadamente exagerado: supõe que o 2º turno tivesse a mesma fila depois das 17h do 1º turno em todas as seções do país (o observado foi cerca de 0,4% disso) e que todos esses votos fossem do 13; mesmo assim a margem continua positiva.

## O que os dados mostram, em poucas linhas

1. **Encerramento tardio no 2º turno foi raro e concentrado.** Nas 135.561 seções já coletadas, 1.459 (1,08%) encerraram depois de 17:30. 1.044 delas estão na Bahia e 316 na Paraíba; Salvador sozinha tem 771, João Pessoa 294, Feira de Santana 63, Lauro de Freitas 46 e Aracaju 42. Fora de BA, PB e SE, o número é residual (44 seções em 7 UFs).
2. **As seções tardias ficaram abertas até as 19h, mas quase ninguém votou depois das 17h.** 1.342 das 1.459 encerraram entre 18:50 e 19:10. Em 796 delas o último voto foi antes das 17h. O total de votos depois das 17h nas tardias foi 1.080 (0,24% do comparecimento delas); depois das 18h, 336.
3. **No 1º turno, encerrar tarde era comum por causa de fila.** Nas mesmas 135.561 seções, 43.821 (32%) encerraram depois de 17:30 no 1º turno, e o log registra 3,72 milhões de votos depois das 17h no país. No 2º turno, as seções que fecharam no horário tiveram em média 0,06 voto depois das 17h. As próprias seções tardias tiveram 20.118 votos depois das 17h no 1º turno e 1.080 no 2º.
4. **Comparação 1º x 2º turno (mesma seção, contra seções do mesmo município e zona que fecharam no horário):** a fatia do 13 cresceu praticamente o mesmo nos dois grupos. Diferença em diferenças: +0,06 ponto percentual (IC 95%: -0,10 a +0,22). O comparecimento cresceu um pouco mais nas tardias: +0,22 ponto (IC 95%: +0,03 a +0,42), concentrado na Bahia (+0,27).
5. **Não há padrão regional que se sustente.** O efeito (pequeno) no comparecimento aparece na BA; fora da BA a variação da fatia do 13 nas tardias foi ligeiramente menor que a dos controles (-0,24 ponto). No Norte, com só 14 tardias, foi -0,90 ponto. Não é possível dizer que a prorrogação favoreceu uma região inteira: o que houve de tardio está em poucas cidades, e os votos depois das 17h somam pouco mais de mil.

## Fonte e método

### Dados

- **2º turno:** BUs versionados pela coleta (`data/versoes/2026/t2/bus/parts` e `data/versoes/2026/t2-sseco/bus/parts`), decodificados por `scripts/ele2026/analisar_encerramento_t2.py` em `data/parquet/2026/t2/encerramento/secoes_encerramento.parquet` (execução de 25/10/2026 23:32, 135.561 seções do Brasil e 1.310 do exterior, que ficam fora desta análise). O horário de encerramento do BU é local; foi convertido para Brasília pelo fuso do município (AC e 11 municípios do oeste do AM em UTC-5; AM, MT, MS, RO e RR em UTC-4; Fernando de Noronha em UTC-2).
- **1º turno:** `data/parquet/2026/secoes_2026.parquet` (hora de encerramento, aptos, comparecimento), `votos_presidente_2026.parquet` (votos por candidato) e `data/parquet/2026/rdv/log_tempo_secoes.parquet` (votos depois das 17h contados no log de todas as 499.207 seções instaladas). A mesma seção é identificada por UF, município, zona e seção.
- **Totais oficiais do 2º turno:** `https://resultados.tse.jus.br/oficial/ele2026/6258/dados/br/br-c0001-e006258-u.json`, uma requisição, gerado em 25/10/2026 23:09:21 (499.247 de 499.248 seções totalizadas). A última versão `br` do índice versionado (21:58:51) dava 64.236.719 a 59.817.037.
- **Log da urna do 2º turno:** `-log.jez` de 5.389 seções baixado do TSE (pleito 3221) a no máximo 3 requisições por segundo, sem nenhum 429 nem falha. O arquivo bruto foi lido em memória e descartado; ficaram só as contagens em `logs_contagens.jsonl`. O log do 2º turno acumula o do 1º; contam só os eventos "O voto do eleitor foi computado" com data 25/10/2026. Em todas as 5.389 seções, menos uma, o número de votos do log bate com o comparecimento do BU.

### Definições

- Horário de encerramento em Brasília pelo minuto truncado: "depois de 17:10" é 17:11:00 ou mais tarde (mesma regra das faixas de `analisar_encerramento_t2.py`).
- **Tardia:** encerrou depois de 17:30 no 2º turno. **Intermediária:** 17:11 a 17:30. **No horário (controle):** até 17:10.
- **Amostra de logs:** todas as tardias (1.459) e intermediárias (1.487); para cada tardia, um controle da mesma UF, município e zona que fechou até 17:10 (1.233 controles, sem reposição; todas as tardias têm controle); e 1% das demais seções no horário, por sorteio estável por hash (1.210 seções), para medir a fila normal no 2º turno.
- **Votos depois das 17h:** eventos de voto computado com hora local convertida para Brasília, a partir de 17:00:00.
- **Fatia do 13 e do 22:** sobre os votos válidos (nominais). No 1º turno os válidos incluem os demais candidatos, por isso a fatia do 13 sobe em quase todo o país do 1º para o 2º turno; a comparação relevante é tardias contra controles, não o nível. Também se calculou a fatia do 13 sobre a soma 13 + 22 do 1º turno (dois candidatos).
- **Diferença em diferenças (DiD):** em cada estrato (UF, município, zona) que tem ao menos uma tardia e um controle, média da variação 1º para 2º turno nas tardias menos a média nos controles; a estimativa é a média ponderada pelo número de tardias. IC 95% por bootstrap das seções dentro de cada estrato (2.000 repetições). Usa todas as seções do estrato que fecharam no horário, não só os controles do log.

## 1. Cobertura da coleta no 2º turno

A coleta dos BUs ainda estava em andamento. N e NE estão quase completos; Sul, Sudeste e Centro-Oeste praticamente não entraram.

| Região | UF com cobertura | Seções coletadas / seções do 1º turno |
|---|---|---|
| Norte | AC 99,1%, AM 98,1%, AP 99,8%, PA 79,3%, RR 100%, TO 100% | RO 0% |
| Nordeste | AL 99,7%, BA 97,6%, CE 65,7%, MA 87,1%, PB 100%, PI 100%, SE 100% | PE 0%, RN 0% |
| Sudeste | SP 1,0% | ES, MG, RJ 0% |
| Sul | nenhuma | PR, RS, SC 0% |
| Centro-Oeste | nenhuma | DF, GO, MS, MT 0% |

No total, 135.561 de 497.897 seções do Brasil (27%). Os números deste relatório valem para essas seções; o que acontece em PE, RN, Sul, Sudeste e Centro-Oeste não está medido (ver Limitações). A estimativa nacional de votos depois das 17h preenche essas seções com o que se observou no 1º turno de cada uma, ajustado pela fila do 2º turno.

## 2. Inventário: encerramento tardio no 2º e no 1º turno

### Por região (só seções já coletadas no 2º turno, comparadas com elas mesmas no 1º)

| Região | Seções | 2º turno: depois de 17:10 | depois de 17:30 | depois de 18:00 | depois de 19:00 | 1º turno: depois de 17:10 | depois de 17:30 | depois de 18:00 | depois de 19:00 |
|---|---|---|---|---|---|---|---|---|---|
| Nordeste | 99.958 | 2.593 | 1.445 | 1.371 | 839 | 50.778 | 33.580 | 18.558 | 4.255 |
| Norte | 34.570 | 342 | 14 | 1 | 0 | 16.780 | 10.215 | 5.126 | 1.045 |
| Sudeste (só SP, 1%) | 1.033 | 11 | 0 | 0 | 0 | 69 | 26 | 6 | 0 |

### Por UF, 2º turno (seções coletadas)

| UF | Seções | depois de 17:10 | depois de 17:30 | depois de 18:00 | depois de 19:00 |
|---|---|---|---|---|---|
| BA | 34.641 | 1.720 | 1.044 | 993 | 727 |
| PB | 10.712 | 380 | 316 | 312 | 80 |
| SE | 5.923 | 85 | 55 | 54 | 27 |
| PI | 10.225 | 67 | 14 | 9 | 5 |
| AM | 8.001 | 106 | 7 | 1 | 0 |
| AL | 7.078 | 65 | 6 | 2 | 0 |
| PA | 16.506 | 170 | 6 | 0 | 0 |
| CE | 15.615 | 64 | 5 | 0 | 0 |
| MA | 15.764 | 212 | 5 | 1 | 0 |
| AP | 1.911 | 11 | 1 | 0 | 0 |
| AC, RR, TO, SP | 9.185 | 66 | 0 | 0 | 0 |

### Por UF, 1º turno, mesmas seções

| UF | Seções | depois de 17:10 | depois de 17:30 | depois de 18:00 | depois de 19:00 |
|---|---|---|---|---|---|
| BA | 34.641 | 20.538 | 14.234 | 8.336 | 2.180 |
| PB | 10.712 | 4.486 | 2.558 | 1.058 | 116 |
| SE | 5.923 | 1.826 | 1.004 | 453 | 66 |
| PI | 10.225 | 3.243 | 1.861 | 894 | 181 |
| AL | 7.078 | 4.698 | 3.585 | 2.311 | 605 |
| MA | 15.764 | 7.844 | 5.022 | 2.800 | 616 |
| AM | 8.001 | 5.258 | 3.458 | 1.850 | 413 |
| PA | 16.506 | 8.939 | 5.504 | 2.799 | 574 |

No país inteiro, no 1º turno, 84.759 seções encerraram depois de 17:30 (SP 1.990, MG 5.778, RJ 7.172, PE 10.537, RS 594, por exemplo). Encerrar tarde no 1º turno era sinal de fila; no 2º turno quase não houve fila (ver seção 3), e o encerramento tardio passou a ser quase só o das seções mantidas abertas até as 19h.

### Municípios com mais seções tardias no 2º turno

| Município | Seções | 2º turno: depois de 17:30 | depois de 19:00 | 1º turno: depois de 17:30 | depois de 19:00 |
|---|---|---|---|---|---|
| Salvador (BA) | 5.123 | 771 | 621 | 1.769 | 29 |
| João Pessoa (PB) | 1.714 | 294 | 75 | 555 | 16 |
| Feira de Santana (BA) | 1.218 | 63 | 21 | 765 | 75 |
| Lauro de Freitas (BA) | 413 | 46 | 21 | 282 | 30 |
| Aracaju (SE) | 1.354 | 42 | 21 | 168 | 0 |
| Encruzilhada (BA) | 55 | 20 | 5 | 19 | 4 |
| Cabedelo (PB) | 168 | 19 | 4 | 16 | 0 |
| Pojuca (BA) | 88 | 17 | 9 | 19 | 0 |
| Ribeirão do Largo (BA) | 28 | 12 | 9 | 16 | 1 |
| Governador Mangabeira (BA) | 60 | 10 | 3 | 24 | 3 |

Salvador, Feira de Santana e Lauro de Freitas são os três municípios citados na Rcl 101.673. Em Salvador, 15% das seções encerraram depois de 17:30 no 2º turno (35% no 1º), mas 621 encerraram depois de 19:00 no 2º contra 29 no 1º. A tabela completa está em `data/parquet/2026/t2/impacto/tabelas.md`.

Das 1.459 tardias do 2º turno, 483 também encerraram depois de 17:30 no 1º turno e 976 não.

## 3. Votos depois das 17h (log da urna)

| Grupo | Seções | Comparecimento | Votos depois de 17:00 | depois de 17:10 | depois de 17:30 | depois de 18:00 | depois de 18:30 | % do comparecimento depois de 17:00 |
|---|---|---|---|---|---|---|---|---|
| Tardias (depois de 17:30) | 1.459 | 444.030 | 1.080 | 734 | 560 | 336 | 126 | 0,243% |
| Intermediárias (17:11 a 17:30) | 1.487 | 389.515 | 428 | 84 | 0 | 0 | 0 | 0,110% |
| Controles pareados (até 17:10) | 1.233 | 372.388 | 185 | 0 | 0 | 0 | 0 | 0,050% |
| Amostra aleatória no horário | 1.210 | 295.026 | 70 | 0 | 0 | 0 | 0 | 0,024% |

Por UF, nas tardias: BA 852 votos depois das 17h (287 depois das 18h), PB 141, AL 42, SE 22, PI 14, AM 6, CE, MA e PA 1 cada, AP 0. Por município: Salvador 665 em 771 seções, João Pessoa 128 em 294, Lauro de Freitas 47, Feira de Santana 35, Aracaju 18. O maior número numa seção foi 39.

Nas mesmas seções tardias, o log do 1º turno registra 20.118 votos depois das 17h; no 2º, 1.080. Em todo o país, o 1º turno teve 3.722.948 votos depois das 17h (fila). Na amostra aleatória do 2º turno, os votos depois das 17h foram 0,4% do que as mesmas seções tiveram no 1º.

Os votos depois das 17h além da fila típica (taxa dos controles pareados aplicada ao comparecimento de cada tardia) somam 838 nas tardias; descontando a mesma seção no 1º turno, 355 nas tardias e intermediárias.

## 4. Comparação 1º x 2º turno

### Agregado por grupo (seções coletadas)

| Grupo no 2º turno | Seções | Comparecimento 2º | % 13 no 1º | % 22 no 1º | % 13 no 2º | Comparecimento/aptos 1º | 2º | Saldo 13 menos 22 no 1º | no 2º |
|---|---|---|---|---|---|---|---|---|---|
| No horário | 132.615 | 33.023.093 | 59,12 | 35,26 | 64,87 | 81,25% | 81,96% | 7.446.438 | 9.533.632 |
| Intermediária | 1.487 | 389.515 | 62,72 | 31,48 | 68,92 | 80,19% | 81,94% | 112.789 | 142.653 |
| Tardia | 1.459 | 444.030 | 60,42 | 32,10 | 67,68 | 80,82% | 84,44% | 113.617 | 151.510 |
| Controles do mesmo estrato das tardias | 18.548 | 5.122.949 | 60,00 | 33,26 | 66,73 | 81,15% | 83,52% | 1.259.962 | 1.656.140 |

As seções tardias votaram no 1º turno de forma parecida com as seções do mesmo município e zona que fecharam no horário: 60,4% para Lula e 32,1% para Flávio, contra 60,0% e 33,3% nos controles do mesmo estrato.

### Tardias por UF, 1º e 2º turno

| UF | Tardias | % 13 no 1º (tardias) | % 13 no 2º (tardias) | % 13 no 1º (no horário, UF) | % 13 no 2º (no horário, UF) | Comparecimento 1º e 2º (tardias) |
|---|---|---|---|---|---|---|
| BA | 1.044 | 64,87 | 72,25 | 66,38 | 71,41 | 79,97% e 84,28% |
| PB | 316 | 46,62 | 52,95 | 61,89 | 68,03 | 83,50% e 85,48% |
| SE | 55 | 58,15 | 65,92 | 62,78 | 69,56 | 82,22% e 84,38% |
| PI | 14 | 69,57 | 74,33 | 70,97 | 75,86 | 83,54% e 84,55% |
| AM | 7 | 51,14 | 55,53 | 47,94 | 53,77 | 76,51% e 75,56% |
| AL | 6 | 67,97 | 72,36 | 54,70 | 60,74 | 79,57% e 78,73% |
| PA | 6 | 51,42 | 57,59 | 49,64 | 54,92 | 80,27% e 80,68% |
| CE | 5 | 47,98 | 55,21 | 62,43 | 68,11 | 85,50% e 86,88% |
| MA | 5 | 76,04 | 79,50 | 62,95 | 68,58 | 77,19% e 76,28% |
| AP | 1 | 38,23 | 43,80 | 45,73 | 52,90 | 83,24% e 72,91% |

A diferença de nível entre tardias e o resto da UF é composição geográfica: as tardias de PB estão quase todas em João Pessoa e Cabedelo, onde o 13 tem fatia menor que no interior; as da BA estão em Salvador e região metropolitana.

### Diferença em diferenças (tardias menos controles do mesmo município e zona), em pontos percentuais

| Recorte | Estratos | Tardias | Controles | Fatia do 13 | Fatia do 22 | Fatia do 13 (dois candidatos no 1º) | Comparecimento |
|---|---|---|---|---|---|---|---|
| Brasil (coletado) | 131 | 1.459 | 18.548 | +0,06 (-0,10 a +0,22) | +0,17 (+0,03 a +0,30) | -0,05 (-0,18 a +0,07) | +0,22 (+0,03 a +0,42) |
| Nordeste | 119 | 1.445 | 15.782 | +0,07 (-0,09 a +0,23) | +0,16 (+0,02 a +0,30) | -0,04 (-0,17 a +0,08) | +0,22 (+0,02 a +0,43) |
| Norte | 12 | 14 | 2.766 | -0,90 (-1,27 a -0,55) | +1,15 (+0,91 a +1,39) | -1,07 (-1,30 a -0,82) | +0,15 (-0,31 a +0,60) |
| BA | 80 | 1.044 | 10.430 | +0,18 (-0,02 a +0,39) | +0,14 (-0,02 a +0,32) | +0,01 (-0,15 a +0,17) | +0,27 (+0,01 a +0,54) |
| Salvador, Feira de Santana e Lauro de Freitas | 22 | 880 | 4.953 | +0,21 (-0,03 a +0,46) | | | +0,29 (-0,02 a +0,60) |
| Fora da BA | 51 | 415 | 8.118 | -0,24 (-0,48 a -0,01) | | | +0,11 (-0,10 a +0,31) |
| PB | 6 | 316 | 672 | -0,21 (-0,50 a +0,10) | +0,06 (-0,25 a +0,37) | -0,06 (-0,33 a +0,20) | +0,08 (-0,18 a +0,33) |
| SE | 11 | 55 | 1.912 | -0,05 (-0,61 a +0,51) | +0,77 (+0,32 a +1,20) | -0,58 (-1,00 a -0,16) | +0,25 (-0,22 a +0,70) |

Leitura: a fatia do 13 e a do 22 sobem ambas um pouco mais nas tardias porque os demais candidatos do 1º turno saem da conta; na medida de dois candidatos, que neutraliza isso, a diferença no Brasil coletado é -0,05 ponto, com intervalo que inclui zero. Nas UFs com poucas tardias (AL, AM, AP, MA, PA), os intervalos são estreitos porque há muitos controles, mas cada estimativa se apoia em 1 a 7 seções e reflete poucas zonas; não deve ser lida como padrão da UF.

## 5. Impacto na diferença final (cenários pedidos)

Diferença oficial 13 menos 22: 4.429.967.

### Nas seções tardias, com a contagem do log

| Cenário | Brasil | BA | PB | SE |
|---|---|---|---|---|
| Votos depois das 17h nas tardias | 1.080 | 852 | 141 | 22 |
| (a) Extremo, todos para um candidato: a diferença se move no máximo | ±1.080 | ±852 | ±141 | ±22 |
| (b) Saldo 13 menos 22 desses votos pela fatia da própria seção no 2º turno | +428 | +384 | +9 | +8 |
| (c) Idem pela fatia da própria seção no 1º turno (dois candidatos) | +381 | +348 | +2 | +7 |
| Diferença sem esses votos, cenário (b) | 4.429.539 | | | |

Para (c) não é possível usar a fatia dos votos dados antes das 17h: o RDV é embaralhado por construção e o log não registra o candidato, então não há como separar os votos por horário. A fatia do 1º turno da mesma seção é o substituto.

Limite que não depende do log: anular todas as 1.459 seções tardias (444.030 votos, saldo de +151.510 para o 13) deixaria a diferença em 4.278.457.

### Estimativa nacional e cenário de descarte

| Componente | Seções | Votos depois das 17h | Como |
|---|---|---|---|
| Contagem exata no log | 5.389 | 1.763 | tardias, intermediárias, controles e amostra aleatória |
| Seções no horário sem log | 130.172 | 7.434 | votos depois das 17h da seção no 1º turno vezes a razão 2º/1º turno medida na amostra aleatória (0,004) |
| Seções ainda não coletadas no 2º turno | 362.336 | 6.985 | idem |
| Total | 497.897 | 16.182 | |

Todas as tardias e intermediárias têm log, então o teto pedido para seção tardia sem log (o comparecimento inteiro) não precisou ser usado. Para as seções que fecharam no horário, esse teto seria o comparecimento delas inteiro, o que não tem sentido físico (elas fecharam até 17:10); em vez dele, o relatório usa como teto a fila inteira do 1º turno (última linha da tabela do resumo).

Votos necessários para inverter: retirando só do 13, 4.429.968 votos depois das 17h. Retirando na fatia de cada seção, a margem média por voto retirado é 0,25 (país) ou 0,40 (tardias e intermediárias), e seriam necessários de 11 a 18 milhões de votos depois das 17h, mais do que o comparecimento de todas as seções que encerraram depois de 17:10.

## 6. Padrões nas tardias

### Distribuição da fatia do 13 no 2º turno (por seção)

| Grupo | Seções | Média | P10 | P25 | Mediana | P75 | P90 |
|---|---|---|---|---|---|---|---|
| Tardias | 1.459 | 67,8 | 51,1 | 58,8 | 71,1 | 76,4 | 79,9 |
| Controles do mesmo estrato | 18.548 | 67,1 | 49,2 | 58,3 | 68,1 | 76,5 | 82,7 |
| Tardias, 1º turno | 1.459 | 60,9 | 44,7 | 51,9 | 63,1 | 69,0 | 73,8 |
| Controles, 1º turno | 18.548 | 60,8 | 42,4 | 51,3 | 61,2 | 70,1 | 78,2 |

Histograma da fatia do 13 no 2º turno (faixas de 10 pontos, de 30 a 100%): tardias 6, 119, 281, 263, 646, 136, 8; controles 235, 1.779, 3.321, 4.888, 5.406, 2.457, 447. As tardias têm menos seções nas pontas (abaixo de 40% e acima de 80%), o que combina com a concentração em capitais e regiões metropolitanas.

### Testes simples (Welch, IC 95%)

| Medida | Tardias | Controles do mesmo estrato | Diferença | IC 95% |
|---|---|---|---|---|
| Fatia do 13 no 2º turno | 67,81 | 67,12 | +0,69 | +0,08 a +1,30 |
| Fatia do 13 no 1º turno | 60,90 | 60,77 | +0,13 | -0,49 a +0,74 |
| Variação da fatia do 13 (1º para 2º) | 6,91 | 6,35 | +0,56 | +0,43 a +0,70 |
| Variação do comparecimento (1º para 2º) | 3,49 | 2,13 | +1,36 | +1,22 a +1,51 |

O teste de Welch compara as tardias com todos os controles dos mesmos estratos juntos, sem pesar por estrato. Como Salvador e região metropolitana têm muitas tardias e uma variação da fatia do 13 maior que a média dos estratos, a diferença de +0,56 é em grande parte composição; dentro de cada município e zona (DiD, seção 4) ela cai para +0,06 e o intervalo inclui zero. A diferença no comparecimento também diminui (de +1,36 para +0,22 ponto), mas continua positiva no agregado e na BA. Não se pode atribuir esse aumento à prorrogação: os votos depois das 17h nas tardias (0,24% do comparecimento) explicam no máximo cerca de 0,2 ponto, o que é da mesma ordem do DiD, mas as seções que ficaram abertas não foram escolhidas ao acaso.

### Casos extremos

Seis tardias têm variação da fatia do 13 a mais de 3 desvios-padrão da média dos controles do mesmo estrato (de 1.459 com estrato de 5 ou mais controles; com distribuição normal se esperariam cerca de 4):

| Seção | Encerramento | Comparecimento | % 13 no 1º | % 13 no 2º | Variação | Esperada (controles) | z |
|---|---|---|---|---|---|---|---|
| BA, Araci, zona 0123, seção 0135 | 19:05:08 | 277 | 88,98 | 85,02 | -3,96 | +3,19 | -3,45 |
| BA, Salvador, zona 0019, seção 0389 | 19:04:18 | 306 | 61,33 | 75,77 | +14,44 | +8,41 | +3,16 |
| PB, João Pessoa, zona 0076, seção 0410 | 18:59:34 | 300 | 48,79 | 60,21 | +11,42 | +6,13 | +3,10 |
| BA, Salvador, zona 0010, seção 0077 | 19:00:32 | 336 | 73,00 | 74,62 | +1,62 | +7,35 | -3,07 |
| BA, Salvador, zona 0005, seção 0299 | 19:00:45 | 297 | 57,35 | 71,13 | +13,77 | +7,37 | +3,04 |
| BA, Salvador, zona 0017, seção 0579 | 19:00:51 | 108 | 58,89 | 73,74 | +14,85 | +8,28 | +3,02 |

Os desvios vão para os dois lados (4 com variação do 13 acima do esperado e 2 abaixo), em número compatível com o acaso.

## Limitações

- **Cobertura parcial.** 27% das seções do país, quase todas do Norte e do Nordeste. PE e RN (que, pelas notícias, mantiveram seções abertas) e todo o Sul, Sudeste e Centro-Oeste ainda não entraram. Em SP o TRE disse que cerca de 20% das seções estavam abertas às 17h18. A estimativa nacional supõe, nas seções não coletadas, a mesma relação entre a fila do 2º e a do 1º turno vista na amostra; se houver muitas seções mantidas até as 19h nessas UFs, o número de votos depois das 17h será maior. Para inverter o resultado, porém, seriam precisos mais de 4,4 milhões de votos depois das 17h todos do 13, mais que toda a fila do 1º turno no país (3,72 milhões).
- **Seleção não aleatória.** As seções que ficaram abertas dependeram de decisões dos TREs e das mesas, do horário em que a ordem chegou e de onde havia eleitores ou fila. Diferenças entre tardias e controles não são efeito da prorrogação.
- **Composição geográfica.** As tardias estão concentradas em Salvador, João Pessoa e entorno. Comparações sem estrato misturam essa composição com o horário; por isso o resultado principal é o DiD dentro de município e zona.
- **Fatia dos votos depois das 17h.** O candidato de cada voto não é observável por horário (RDV embaralhado, log sem candidato). Os cenários (b) e (c) supõem que esses votos se dividiram como o total da seção no 2º turno ou no 1º turno.
- **Horário do BU e do log.** O horário de encerramento é o do relógio da urna, convertido pelo fuso do município. Seções com urna de contingência (`reservaSecao`) usam o BU final. Uma seção da amostra tem número de votos no log diferente do comparecimento do BU.
- **Exterior** (1.310 seções) fora da análise: cada país segue o próprio fuso.
- A coleta continua: rodar de novo `analisar_encerramento_t2.py` e `impacto_prorrogacao_t2.py --baixar-logs` atualiza tudo; o cache de logs é incremental e a escolha da amostra é estável.

## Como reproduzir

```sh
nice -n 20 .venv/bin/python scripts/ele2026/analisar_encerramento_t2.py \
  --parts data/versoes/2026/t2/bus/parts --parts data/versoes/2026/t2-sseco/bus/parts --workers 3
curl -s https://resultados.tse.jus.br/oficial/ele2026/6258/dados/br/br-c0001-e006258-u.json -o br.json
nice -n 20 .venv/bin/python scripts/ele2026/impacto_prorrogacao_t2.py --total-oficial br.json --baixar-logs
```
