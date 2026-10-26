# Seções que encerraram depois do horário no 2º turno de 2026 e impacto possível da prorrogação

Levantamento nacional de 26/10/2026 sobre as seções que encerraram a votação depois das 17h de Brasília no 2º turno presidencial (25/10/2026), quando a Rcl 101.673/BA (STF) prorrogou o recebimento de votos até as 19h nos locais onde as urnas ainda não tinham sido fechadas (Ofício-Circular TSE 354/2026; contexto em `docs/prorrogacao-votacao-2turno-2026.md`). O objetivo é descrever, com os arquivos públicos das urnas, onde houve encerramento tardio, quantos eleitores votaram depois das 17h e quanto isso poderia pesar na diferença final entre 13 (Lula) e 22 (Flávio Bolsonaro). É um levantamento descritivo: não estima efeito causal e não faz juízo sobre a decisão.

Esta versão cobre todas as 497.897 seções do Brasil (mais 1.310 do exterior, fora da análise), ou seja, todos os 499.207 BUs coletados. A versão anterior (25/10/2026) cobria 135.561 seções, quase só do Norte e do Nordeste. A revisão de 26/10/2026 (análise das 08:18) passou a ter o log da urna lido em todas as 21.318 seções da amostra, menos uma, e troca a estimativa dos votos depois das 17h nas seções atrasadas pela contagem exata.

Scripts: `scripts/ele2026/analisar_encerramento_t2.py` e `scripts/ele2026/impacto_prorrogacao_t2.py` (testes em `tests/ele2026/test_encerramento_t2.py` e `tests/ele2026/test_impacto_prorrogacao_t2.py`). Saída, fora do git: `data/parquet/2026/t2/encerramento/` e `data/parquet/2026/t2/impacto/` (`resumo.json`, `tabelas.md`, `secoes_t1_t2.parquet`, `amostra_logs.parquet`, `logs_contagens.jsonl`).

## Resumo: descartar os votos dados depois das 17:00:00

| Item | Valor |
|---|---|
| Margem oficial final 13 menos 22 (TSE, totalização de 25/10/2026 23:22:22, 499.248 de 499.248 seções) | **4.430.191** (64.256.232 a 59.826.041) |
| Soma dos 499.207 BUs coletados | 64.256.232 a 59.826.041, idêntica ao oficial |
| Seções que encerraram depois de 17:10 / 17:30 / 18:00 / 19:00 (Brasília) | **11.673 / 7.581 / 7.078 / 4.359** |
| Votos computados depois das 17:00:00, contados no log, nas 21.317 seções da amostra com log lido | **7.030** |
| dos quais nas 7.580 tardias com log (todas as tardias do país, menos 1 sem log publicado) | **5.129** (3.219 depois de 17:30, 1.993 depois de 18:00, 699 depois de 18:30) |
| Estimativa para o país inteiro (contagem exata na amostra + estimativa só para as 476.579 seções no horário fora da amostra, ver método) | **cerca de 31.792** |
| Margem se todos os 31.792 fossem retirados do 13 | **4.398.399** |
| Margem se fossem retirados na fatia de cada seção | **4.422.579** |
| Margem se só os 5.129 votos das tardias fossem retirados, todos do 13 | **4.425.062** |
| Votos depois das 17h necessários para inverter, retirando todos do 13 | 4.430.192, ou seja, **139 vezes** a estimativa nacional |
| Idem, retirando na fatia de cada seção | 18,50 milhões, **582 vezes** a estimativa nacional |
| Teto da única tardia sem log (comparecimento inteiro de 186 depois das 17h, todos do 13, mais o resto da estimativa) | margem **4.398.213** (não inverte) |

**Cobertura do log nesta versão.** O `-log.jez` do 2º turno não está nos Parquet da coleta nem no ClickHouse (as partes `versoes-*.parquet` guardam só `aux`, `bu`, `busa`, `vota` e `sa`; consulta em "Como reproduzir"), por isso o log de cada seção da amostra foi baixado do TSE. Em 25/10/2026 haviam sido lidas 5.389 seções, todas de N e NE; em 26/10/2026, das 06:45 às 08:15, foram pedidos os 15.929 arquivos que faltavam (a no máximo 3 requisições por segundo, nenhuma resposta 429). A amostra inteira (21.318 seções: todas as 7.581 tardias, todas as 4.092 intermediárias, 5.451 controles e 4.194 seções aleatórias no horário) passou a ter contagem exata, menos uma tardia cujo log não está publicado (Niterói, RJ, zona 0144, seção 0007, resposta 404, comparecimento 186). A única parte estimada é a das seções que fecharam no horário e não estão na amostra.

| Corte | Votos retirados | Margem se todos do 13 | Margem na fatia da seção | Vezes o observado para inverter (todos do 13) |
|---|---|---|---|---|
| Todos os votos depois das 17:00:00, país inteiro (exato na amostra + estimativa no horário) | 31.792 | 4.398.399 | 4.422.579 | 139 |
| Só a contagem exata do log (21.317 seções) | 7.030 | 4.423.161 | 4.429.111 | 630 |
| Tardias e intermediárias (contagem exata, mais 0,4 estimado para a tardia sem log) | 6.235 | 4.423.956 | 4.429.271 | 710 |
| Além do normal: descontando a mesma seção no 1º turno | 2.405 | 4.427.786 | 4.429.874 | 1.842 |
| Além do normal: descontando a taxa dos controles pareados do 2º turno | 5.778 | 4.424.413 | 4.429.329 | 767 |
| Teto: a tardia sem log com o comparecimento inteiro (mais o resto da estimativa) | 31.978 | 4.398.213 | 4.422.512 | 138,5 |
| Teto hipotético: fila do 1º turno inteira (3.722.948 votos depois das 17h em todo o país em 04/10) | 3.722.948 | 707.243 | 3.630.650 | 1,19 |

Nenhum cenário, nem o mais desfavorável ao 13, inverte o resultado. Com a contagem exata em toda a amostra, o teto que antes dependia das 8.727 seções atrasadas sem log (margem de 1.959.017) deixou de ser necessário: só uma seção atrasada ficou sem log, e mesmo com todos os seus 186 eleitores depois das 17h e no 13 a margem fica em 4.398.213. O teto da fila do 1º turno é deliberadamente exagerado: supõe que o 2º turno teve a mesma fila depois das 17h do 1º turno em todas as seções do país (a estimativa nacional é 0,85% disso, e na amostra aleatória no horário a razão 2º/1º turno foi 0,7%) e que todos esses votos foram do 13. Anular as 7.581 seções tardias inteiras (2.202.543 votos, saldo de +226.840 para o 13) deixaria a margem em 4.203.351.

## O que os dados mostram, em poucas linhas

1. **Encerramento tardio no 2º turno foi raro e concentrado em poucas capitais e regiões metropolitanas.** 7.581 seções (1,52% do país) encerraram depois de 17:30. RJ tem 3.316 (Rio de Janeiro 2.162, Niterói 349, Petrópolis 297, Itaboraí 241), SP 1.968 (São Paulo 1.840), BA 1.047 (Salvador 771), PE 715 (Recife 230) e PB 316 (João Pessoa 294). Essas cinco UFs somam 7.362 das 7.581. Fora delas, nenhuma UF passa de 55.
2. **No 1º turno, encerrar tarde era comum por causa de fila.** No mesmo conjunto de seções, 84.759 encerraram depois de 17:30 no 1º turno, e o log registra 3.722.948 votos depois das 17h no país. No 2º turno, as seções que fecharam no horário tiveram em média 0,05 voto depois das 17h (amostra aleatória de 4.194 seções, todos antes de 17:10), e a fila normal depois das 17h foi 0,7% da do 1º turno nas mesmas seções.
3. **As tardias ficaram abertas, mas quase ninguém votou depois das 17h.** Nas 7.580 tardias com log (todas menos uma), 5.129 votos depois das 17h (0,23% do comparecimento delas); depois de 17:30, 3.219; depois das 18h, 1.993; depois de 18:30, 699. RJ 1.974, SP 1.644, BA 852, PE 296, PB 141. O maior número numa seção foi 39 (Ouro Branco, AL); 4.187 das 7.580 tardias não tiveram nenhum voto depois das 17h. Nas mesmas tardias, o 1º turno teve 71.924 votos depois das 17h.
4. **Comparação 1º x 2º turno (mesma seção, contra seções do mesmo município e zona que fecharam no horário):** no Brasil, a fatia do 13 cresceu um pouco **menos** nas tardias do que nos controles. Diferença em diferenças: **-0,17 ponto percentual (IC 95%: -0,27 a -0,07)**; na medida de dois candidatos, -0,20 (-0,29 a -0,11). O comparecimento cresceu um pouco mais nas tardias: +0,20 ponto (+0,11 a +0,29).
5. **Não há padrão regional a favor do 13.** O DiD da fatia do 13 é negativo no Sudeste (-0,24), no RJ (-0,31) e em SP (-0,13), praticamente zero no Nordeste (+0,03, IC inclui zero) e em PE (-0,06), e só positivo, sem significância, na BA (+0,19, IC -0,02 a +0,39). Fora da BA: -0,23 (-0,34 a -0,12).

## Fonte e método

### Dados

- **2º turno:** BUs versionados pela coleta, em quatro pastas do servidor de processamento (`~/dataurnas-mac/versoes/2026/t2/bus/parts`, `~/dataurnas-mac/versoes/2026/t2-sseco/bus/parts`, `~/dataurnas-versoes-t2/bus/parts` e `~/dataurnas-versoes-t2-nne/bus/parts`; 871 partes, 501.454 registros de BU, 499.207 seções depois da deduplicação), decodificados por `analisar_encerramento_t2.py` em `secoes_encerramento.parquet` (execução de 26/10/2026 09:28 UTC, 497.897 seções do Brasil e 1.310 do exterior, nenhuma seção com mais de uma versão de BU). O horário de encerramento do BU é local; foi convertido para Brasília pelo fuso do município (AC e 11 municípios do oeste do AM em UTC-5; demais AM, MT, MS, RO e RR em UTC-4; Fernando de Noronha em UTC-2).
- **Conferência no ClickHouse:** a contagem por UF na view `v_bu_ultima` com a mesma regra de fuso (consulta em "Como reproduzir") dá exatamente os mesmos totais: 497.897 seções, 11.673 depois de 17:10, 7.581 depois de 17:30, 7.078 depois de 18:00 e 4.359 depois de 19:00. A soma de `v_votos_t2_secao` (499.205 seções com votos de Presidente) é 64.256.232 para o 13 e 59.826.041 para o 22, igual à última versão `br` de `v_totais_ultima`.
- **1º turno:** `data/parquet/2026/secoes_2026.parquet` (hora de encerramento, aptos, comparecimento), `votos_presidente_2026.parquet` e `data/parquet/2026/rdv/log_tempo_secoes.parquet` (votos depois das 17h contados no log de todas as seções instaladas). Todas as 497.897 seções do 2º turno têm par no 1º turno (mesma UF, município, zona e seção).
- **Totais oficiais do 2º turno:** `v_totais_ultima`, nível `br`, totalizado em 25/10/2026 23:22:22, 499.248 de 499.248 seções (na execução de 26/10/2026 08:18 os mesmos números foram passados pela linha de comando, fonte `TSE br-c0001-e006258-u.json 25/10/2026 23:22:22`). A versão anterior deste relatório usava a totalização de 23:09:21 (499.247 seções, margem 4.429.967).
- **Log da urna do 2º turno:** cache incremental `logs_contagens.jsonl` (21.318 linhas, uma por seção da amostra): 5.389 seções baixadas do TSE em 25/10/2026 e 15.929 em 26/10/2026 das 06:45 às 08:15, sempre a no máximo 3 requisições por segundo. 21.317 têm contagem; uma tardia não tem log publicado (404). Contam só os eventos "O voto do eleitor foi computado" com data 25/10/2026, hora local convertida para Brasília. Em todas as 21.317 seções, menos uma (aleatória do MA, 36 votos a menos no log), o número de votos do log bate com o comparecimento do BU.

### Definições

- Horário de encerramento em Brasília pelo minuto truncado: "depois de 17:10" é 17:11:00 ou mais tarde. "Depois de 17:00" pelo minuto (17:01:00 ou mais tarde) não serve para separar seções tardias: o procedimento de encerramento leva cerca de um minuto, e 372.273 seções (75%) encerraram a partir de 17:01.
- **Tardia:** encerrou depois de 17:30 no 2º turno. **Intermediária:** 17:11 a 17:30. **No horário (controle):** até 17:10.
- **Amostra de logs (desenho):** todas as tardias e intermediárias; para cada tardia, um controle da mesma UF, município e zona que fechou até 17:10 (sem reposição); e 1% das demais seções no horário, por sorteio estável por hash. Com a cobertura nacional, a amostra tem 21.318 seções: 7.581 tardias, 4.092 intermediárias, 5.451 controles e 4.194 seções aleatórias. Todas têm log lido, menos uma tardia (21.317 com contagem). O sorteio é estável, por isso as seções lidas em 25/10 mantiveram o papel.
- **Votos depois das 17h:** eventos de voto computado a partir de 17:00:00 de Brasília.
- **Estimativa nacional:** (1) contagem exata nas 21.317 seções com log (7.030 votos: tardias 5.129, intermediárias 1.106, controles 581, aleatórias 214); (2) a tardia sem log: comparecimento (186) vezes a taxa medida no log das tardias (0,2329%), 0,4 voto; (3) as 476.579 seções no horário fora da amostra: votos depois das 17h da própria seção no 1º turno (3.525.399 no total) vezes a razão 2º/1º turno medida na amostra aleatória (214 sobre 30.468, 0,00702), 24.761,6 votos. Total: 31.792. Sensibilidade para (3): a taxa da amostra aleatória sobre o comparecimento (214 sobre 1.057.018, 0,0202%) aplicada ao comparecimento dessas seções (121.948.045, ou seja, 124.565.977 no horário menos 1.560.914 dos controles e 1.057.018 das aleatórias) dá 24.689, quase o mesmo; a taxa dos controles pareados (581 sobre 1.560.914, 0,0372%), que estão nas mesmas zonas das tardias e por isso tendem a ter mais fila, daria 45.391 e um total de 52.421, com margem de 4.377.769 se todos fossem retirados do 13.
- **Fatia do 13 e do 22:** sobre os votos válidos (nominais). No 1º turno os válidos incluem os demais candidatos, por isso a fatia do 13 sobe em quase todo o país do 1º para o 2º turno; a comparação relevante é tardias contra controles, não o nível. Também se calculou a fatia do 13 sobre a soma 13 + 22 do 1º turno (dois candidatos).
- **Diferença em diferenças (DiD):** em cada estrato (UF, município, zona) que tem ao menos uma tardia e um controle, média da variação 1º para 2º turno nas tardias menos a média nos controles; a estimativa é a média ponderada pelo número de tardias. IC 95% por bootstrap das seções dentro de cada estrato (2.000 repetições). Usa todas as seções do estrato que fecharam no horário. 7.553 das 7.581 tardias têm controle no estrato; as 28 restantes, todas de PE, estão em zonas sem nenhuma seção que tenha fechado até 17:10 (ver os municípios de PE abertos por inteiro, abaixo).

## 1. Inventário: encerramento tardio no 2º e no 1º turno

### Por região

| Região | Seções | 2º turno: depois de 17:10 | depois de 17:30 | depois de 18:00 | depois de 19:00 | 1º turno: depois de 17:10 | depois de 17:30 | depois de 18:00 | depois de 19:00 |
|---|---|---|---|---|---|---|---|---|---|
| Sudeste | 203.237 | 7.033 | 5.304 | 4.953 | 3.083 | 39.619 | 15.673 | 5.618 | 571 |
| Nordeste | 140.828 | 3.745 | 2.187 | 2.079 | 1.254 | 76.046 | 51.303 | 28.558 | 6.191 |
| Centro-Oeste | 38.048 | 330 | 48 | 28 | 17 | 9.500 | 3.943 | 1.296 | 106 |
| Norte | 43.769 | 424 | 29 | 12 | 3 | 19.232 | 11.634 | 5.943 | 1.236 |
| Sul | 72.015 | 141 | 13 | 6 | 2 | 6.098 | 2.206 | 532 | 25 |
| **Brasil** | **497.897** | **11.673** | **7.581** | **7.078** | **4.359** | **150.495** | **84.759** | **41.947** | **8.129** |

### Por UF, 2º turno (horário de Brasília)

| UF | Seções | depois de 17:10 | depois de 17:30 | depois de 18:00 | depois de 19:00 | Último encerramento |
|---|---|---|---|---|---|---|
| RJ | 37.675 | 3.841 | 3.316 | 3.188 | 2.029 | 20:45:31 |
| SP | 103.656 | 3.002 | 1.968 | 1.760 | 1.052 | 19:18:32 |
| BA | 35.476 | 1.734 | 1.047 | 994 | 727 | 19:51:49 |
| PE | 21.418 | 942 | 715 | 700 | 411 | 19:20:56 |
| PB | 10.712 | 380 | 316 | 312 | 80 | 19:10:16 |
| SE | 5.923 | 85 | 55 | 54 | 27 | 19:05:28 |
| DF | 6.969 | 203 | 29 | 17 | 12 | 19:12:28 |
| PA | 20.827 | 223 | 17 | 9 | 3 | 19:03:12 |
| MG | 52.062 | 161 | 16 | 3 | 1 | 23:04:42 |
| CE | 23.765 | 113 | 14 | 1 | 0 | 18:26:31 |
| PI | 10.225 | 67 | 14 | 9 | 5 | 19:03:17 |
| MA | 18.093 | 290 | 14 | 4 | 3 | 19:04:25 |
| MT | 8.287 | 64 | 13 | 9 | 5 | 19:01:40 |
| RS | 27.547 | 46 | 8 | 4 | 1 | 19:04:00 |
| AM | 8.157 | 113 | 8 | 1 | 0 | 18:07:12 |
| AL | 7.101 | 65 | 6 | 2 | 0 | 19:00:45 |
| RN | 8.115 | 69 | 6 | 3 | 1 | 19:02:01 |
| GO | 15.686 | 41 | 5 | 2 | 0 | 19:00:52 |
| ES | 9.844 | 29 | 4 | 2 | 1 | 19:43:21 |
| PR | 27.142 | 64 | 3 | 1 | 1 | 19:02:08 |
| SC | 17.326 | 31 | 2 | 1 | 0 | 18:31:02 |
| RO | 4.698 | 21 | 2 | 1 | 0 | 18:08:24 |
| AP | 1.914 | 11 | 1 | 0 | 0 | 17:34:02 |
| MS | 7.106 | 22 | 1 | 0 | 0 | 17:32:34 |
| AC | 2.270 | 11 | 1 | 1 | 0 | 19:00:38 |
| TO | 4.384 | 24 | 0 | 0 | 0 | 17:28:49 |
| RR | 1.519 | 21 | 0 | 0 | 0 | 17:29:51 |

### Por UF, 1º turno, mesmas seções

| UF | Seções | depois de 17:10 | depois de 17:30 | depois de 18:00 | depois de 19:00 |
|---|---|---|---|---|---|
| SP | 103.656 | 11.939 | 1.990 | 290 | 10 |
| MG | 52.062 | 11.359 | 5.778 | 2.256 | 266 |
| RJ | 37.675 | 14.610 | 7.172 | 2.895 | 285 |
| BA | 35.476 | 21.073 | 14.646 | 8.599 | 2.242 |
| RS | 27.547 | 1.671 | 594 | 134 | 5 |
| PR | 27.142 | 2.459 | 835 | 231 | 14 |
| CE | 23.765 | 12.503 | 8.260 | 4.292 | 792 |
| PE | 21.418 | 14.670 | 10.537 | 6.067 | 1.188 |
| PA | 20.827 | 10.939 | 6.812 | 3.573 | 760 |
| MA | 18.093 | 8.932 | 5.723 | 3.164 | 702 |
| SC | 17.326 | 1.968 | 777 | 167 | 6 |
| GO | 15.686 | 3.618 | 1.649 | 556 | 41 |
| PB | 10.712 | 4.486 | 2.558 | 1.058 | 116 |
| PI | 10.225 | 3.243 | 1.861 | 894 | 181 |
| ES | 9.844 | 1.711 | 733 | 177 | 10 |
| MT | 8.287 | 3.089 | 1.495 | 515 | 57 |
| AM | 8.157 | 5.350 | 3.518 | 1.882 | 418 |
| RN | 8.115 | 4.601 | 3.120 | 1.714 | 296 |
| AL | 7.101 | 4.712 | 3.594 | 2.317 | 608 |
| MS | 7.106 | 1.111 | 371 | 95 | 8 |
| DF | 6.969 | 1.682 | 428 | 130 | 0 |
| SE | 5.923 | 1.826 | 1.004 | 453 | 66 |
| RO | 4.698 | 355 | 50 | 10 | 0 |
| TO | 4.384 | 970 | 365 | 101 | 7 |
| AC | 2.270 | 440 | 207 | 71 | 10 |
| AP | 1.914 | 980 | 620 | 288 | 35 |
| RR | 1.519 | 198 | 62 | 18 | 6 |

No 1º turno o atraso estava no Nordeste e no Norte (fila); no 2º turno, quase só onde as seções foram mantidas abertas até as 19h. SP é o caso mais claro: 1.990 seções depois de 17:30 no 1º turno e 10 depois de 19:00; no 2º turno, 1.968 e 1.052. Das 1.968 tardias de SP no 2º turno, só 24 também foram tardias no 1º; no RJ, 1.301 de 3.316; em PE, 433 de 715; na BA, 397 de 1.047. No país, 2.271 das 7.581 tardias também encerraram depois de 17:30 no 1º turno.

### Municípios com mais seções tardias no 2º turno

| Município | Seções | 2º turno: depois de 17:30 | depois de 19:00 | 1º turno: depois de 17:30 | depois de 19:00 |
|---|---|---|---|---|---|
| Rio de Janeiro (RJ) | 12.635 | 2.162 | 1.449 | 4.936 | 242 |
| São Paulo (SP) | 26.683 | 1.840 | 1.008 | 565 | 1 |
| Salvador (BA) | 5.124 | 771 | 621 | 1.770 | 29 |
| Niterói (RJ) | 1.327 | 349 | 49 | 16 | 0 |
| Petrópolis (RJ) | 804 | 297 | 181 | 3 | 0 |
| João Pessoa (PB) | 1.714 | 294 | 75 | 555 | 16 |
| Itaboraí (RJ) | 540 | 241 | 162 | 55 | 2 |
| Recife (PE) | 3.481 | 230 | 151 | 1.222 | 13 |
| São Gonçalo (RJ) | 2.019 | 112 | 86 | 227 | 2 |
| Feira de Santana (BA) | 1.218 | 63 | 21 | 765 | 75 |
| Jaboatão dos Guararapes (PE) | 1.342 | 55 | 34 | 714 | 8 |
| Passira (PE) | 79 | 49 | 25 | 40 | 3 |
| Olinda (PE) | 893 | 48 | 24 | 302 | 0 |
| Lauro de Freitas (BA) | 413 | 46 | 21 | 282 | 30 |
| Aracaju (SE) | 1.354 | 42 | 21 | 168 | 0 |

Salvador, Feira de Santana e Lauro de Freitas são os três municípios citados na Rcl 101.673. Em Petrópolis, 297 de 804 seções encerraram depois de 17:30 no 2º turno, contra 3 no 1º. A tabela completa está em `data/parquet/2026/t2/impacto/tabelas.md`.

### Casos fora do comum no horário

- **Municípios inteiros abertos em PE.** A verificação de fuso de `analisar_encerramento_t2.py` acusou seis municípios de PE com mediana de encerramento por volta de 19h: Brejinho (23 seções), Cumaru (49), Itapetim (38), Passira (79), Santa Terezinha (28) e Fernando de Noronha (10). Não é erro de fuso: o recebimento pelo TSE (horário de Brasília) vem depois do encerramento convertido em todas as seções conferidas (em Noronha, por exemplo, encerramento às 20:20:56 locais, 19:20:56 de Brasília, recebido às 21:02:17). Esses municípios ficaram abertos até cerca de 19h em quase todas as seções.
- **33 seções encerraram depois de 19:15 de Brasília** (lista pela consulta `apos_19h15.sql` em "Como reproduzir"). 18 delas são de Volta Redonda (RJ), zona 0090, entre 19:16 e 19:48 (a zona tem 324 seções, 20 delas encerradas depois de 19:00). As mais tardias: Chapada Gaúcha (MG), zona 0320, seção 0185, urna de contingência (`reservaSecao`), encerrada às 23:04:42 com 96 eleitores; Duas Barras (RJ), zona 0042, seção 0108, às 20:45:31 com 221; Rio de Janeiro, zona 0179, seção 0050, às 19:57:46; Santana (BA), zona 0099, seção 0190, às 19:51:49; Santa Maria de Jetibá (ES), zona 0009, seção 0112 (`reservaEncerrandoSecao`), às 19:43:21. O encerramento depois das 19h por si só não é irregular (eleitores na fila no horário-limite votam). O log das 33 seções foi lido: somam 7 votos depois das 17h (1 depois de 18:30); as 18 de Volta Redonda e as cinco citadas acima não têm nenhum.

## 2. Votos depois das 17h (log da urna)

| Grupo | Seções com log | Comparecimento | Votos depois de 17:00 | depois de 17:10 | depois de 17:30 | depois de 18:00 | depois de 18:30 | % do comparecimento depois de 17:00 |
|---|---|---|---|---|---|---|---|---|
| Tardias (depois de 17:30) | 7.580 | 2.202.357 | 5.129 | 3.959 | 3.219 | 1.993 | 699 | 0,233% |
| Intermediárias (17:11 a 17:30) | 4.092 | 1.086.111 | 1.106 | 239 | 0 | 0 | 0 | 0,102% |
| Controles pareados (até 17:10) | 5.451 | 1.560.914 | 581 | 0 | 0 | 0 | 0 | 0,037% |
| Amostra aleatória no horário | 4.194 | 1.057.018 | 214 | 0 | 0 | 0 | 0 | 0,020% |
| **Total da amostra** | **21.317** | **5.906.400** | **7.030** | **4.198** | **3.219** | **1.993** | **699** | **0,119%** |

Nas seções que fecharam até 17:10 (controles e aleatórias), nenhum voto foi computado depois de 17:10: os 795 votos depois das 17h delas são o fim normal da fila. A tabela por UF e papel está em `tabelas.md` ("Votos no log depois dos cortes, por UF e papel").

Tardias com log, por UF:

| UF | Tardias | com log | Comparecimento | Votos depois das 17h | depois das 18h | % do comparecimento | Maior numa seção | Votos depois das 17h na mesma seção no 1º turno |
|---|---|---|---|---|---|---|---|---|
| RJ | 3.316 | 3.315 | 978.577 | 1.974 | 883 | 0,202% | 9 | 35.337 |
| SP | 1.968 | 1.968 | 534.703 | 1.644 | 641 | 0,307% | 23 | 2.142 |
| BA | 1.047 | 1.047 | 323.511 | 852 | 287 | 0,263% | 22 | 16.327 |
| PE | 715 | 715 | 214.495 | 296 | 113 | 0,138% | 4 | 13.395 |
| PB | 316 | 316 | 95.534 | 141 | 41 | 0,148% | 5 | 2.719 |
| demais | 219 | 219 | 55.537 | 222 | 28 | 0,400% | 39 | 2.004 |
| **Brasil** | **7.581** | **7.580** | **2.202.357** | **5.129** | **1.993** | **0,233%** | **39** | **71.924** |

Nas demais UFs: AL 42 votos depois das 17h, GO 42, SE 22, MG 20, MA 17, RS 17, PI 14, CE 10, RN 8, AM, DF e PA 7 cada, MT 5, ES 2, PR e SC 1 cada, AC, AP, MS e RO 0. O maior número numa seção foi 39 (Ouro Branco, AL, zona 0050, seção 0079); só 8 tardias tiveram 10 votos ou mais depois das 17h.

**Comparação 1º x 2º turno nas atrasadas com log.** Nas mesmas 7.580 tardias, o 1º turno teve 71.924 votos depois das 17h e o 2º turno 5.129 (razão 0,0713); nas 4.092 intermediárias, 48.431 e 1.106 (razão 0,0228). Somadas, 120.355 no 1º turno e 6.235 no 2º (5,2%). Nas seções aleatórias no horário, 30.468 e 214 (0,7%). Ou seja, as seções que ficaram abertas tiveram depois das 17h cerca de 7% do movimento que tiveram no 1º turno, quando havia fila; no SP a relação se inverte (1.644 no 2º turno contra 2.142 no 1º, 77%), porque lá quase nenhuma dessas seções tinha fila no 1º turno.

Os votos depois das 17h além da fila típica somam 4.169,8 nas tardias com log (taxa dos controles pareados do mesmo estrato aplicada ao comparecimento de cada tardia; `excesso_votos_apos_17h_sobre_controles` no `resumo.json`).

## 3. Comparação 1º x 2º turno

### Agregado por grupo (país inteiro)

| Grupo no 2º turno | Seções | Comparecimento 2º | % 13 no 1º | % 22 no 1º | % 13 no 2º | Comparecimento/aptos 1º | 2º | Saldo 13 menos 22 no 1º | no 2º |
|---|---|---|---|---|---|---|---|---|---|
| No horário | 486.224 | 124.565.977 | 45,05 | 47,15 | 51,65 | 79,19% | 81,02% | -2.431.833 | 3.988.144 |
| Intermediária | 4.092 | 1.086.111 | 51,90 | 40,47 | 58,90 | 78,50% | 80,67% | 114.394 | 186.550 |
| Tardia | 7.581 | 2.202.543 | 47,75 | 43,80 | 55,34 | 77,53% | 80,61% | 78.987 | 226.840 |
| Controles do mesmo estrato das tardias | 88.530 | 24.378.470 | 48,68 | 42,84 | 56,15 | 78,76% | 81,18% | 1.308.387 | 2.891.632 |

As tardias votaram no 1º turno de forma parecida com as seções do mesmo município e zona que fecharam no horário: 47,7% para Lula e 43,8% para Flávio, contra 48,7% e 42,8% nos controles do mesmo estrato.

### Tardias por UF, 1º e 2º turno

| UF | Tardias | % 13 no 1º (tardias) | % 13 no 2º (tardias) | % 13 no 1º (no horário, UF) | % 13 no 2º (no horário, UF) | Comparecimento 1º e 2º (tardias) |
|---|---|---|---|---|---|---|
| RJ | 3.316 | 39,20 | 46,69 | 39,40 | 46,88 | 75,80% e 78,64% |
| SP | 1.968 | 48,22 | 56,93 | 37,94 | 45,87 | 76,29% e 79,57% |
| BA | 1.047 | 64,90 | 72,27 | 66,20 | 71,23 | 79,96% e 84,27% |
| PE | 715 | 59,94 | 65,83 | 63,60 | 69,34 | 82,15% e 84,91% |
| PB | 316 | 46,62 | 52,95 | 61,89 | 68,03 | 83,50% e 85,48% |
| SE | 55 | 58,15 | 65,92 | 62,78 | 69,56 | 82,22% e 84,38% |
| DF | 29 | 40,86 | 47,77 | 38,11 | 45,72 | 82,74% e 84,80% |
| PA | 17 | 53,42 | 59,66 | 49,87 | 54,97 | 82,60% e 83,44% |
| MG | 16 | 46,50 | 53,24 | 43,31 | 50,42 | 75,56% e 78,14% |
| CE | 14 | 59,69 | 65,49 | 63,29 | 68,93 | 83,22% e 85,35% |
| MA | 14 | 82,03 | 85,85 | 63,90 | 69,46 | 76,49% e 75,35% |
| PI | 14 | 69,57 | 74,33 | 70,97 | 75,86 | 83,54% e 84,55% |
| MT | 13 | 26,88 | 31,31 | 29,16 | 33,92 | 77,94% e 80,18% |
| AM | 8 | 54,65 | 58,47 | 48,13 | 53,93 | 75,51% e 74,05% |
| RS | 8 | 44,21 | 52,03 | 35,72 | 42,16 | 76,55% e 78,22% |
| AL, RN, GO, ES, PR, RO, SC, AC, AP, MS | 31 | | | | | |

A diferença de nível entre tardias e o resto da UF é composição geográfica: as tardias de SP estão quase todas na capital, onde o 13 tem fatia maior que no interior; as de PB, em João Pessoa e Cabedelo; as da BA, em Salvador e região metropolitana. A tabela completa por UF está em `resumo.json` (`votos_por_uf_tardias`).

### Diferença em diferenças (tardias menos controles do mesmo município e zona), em pontos percentuais

| Recorte | Estratos | Tardias | Controles | Fatia do 13 | Fatia do 22 | Fatia do 13 (dois candidatos no 1º) | Comparecimento |
|---|---|---|---|---|---|---|---|
| **Brasil** | 429 | 7.553 | 88.530 | **-0,17 (-0,27 a -0,07)** | +0,19 (+0,10 a +0,28) | -0,20 (-0,29 a -0,11) | +0,20 (+0,11 a +0,29) |
| Nordeste | 206 | 2.159 | 29.997 | +0,03 (-0,09 a +0,15) | +0,19 (+0,09 a +0,29) | -0,07 (-0,17 a +0,02) | +0,22 (+0,07 a +0,37) |
| Sudeste | 174 | 5.304 | 46.603 | -0,24 (-0,38 a -0,11) | +0,18 (+0,04 a +0,31) | -0,24 (-0,36 a -0,12) | +0,19 (+0,07 a +0,31) |
| Norte | 18 | 29 | 3.737 | -0,92 (-1,43 a -0,38) | +0,78 (+0,29 a +1,25) | -0,85 (-1,27 a -0,37) | +0,32 (-0,07 a +0,68) |
| Centro-Oeste | 19 | 48 | 5.639 | -0,43 (-0,84 a -0,04) | +0,91 (+0,53 a +1,27) | -0,54 (-0,89 a -0,18) | +0,43 (+0,13 a +0,75) |
| Sul | 12 | 13 | 2.554 | +0,08 (-0,19 a +0,34) | +0,59 (+0,47 a +0,71) | -0,41 (-0,52 a -0,30) | -0,24 (-0,38 a -0,09) |
| RJ | 83 | 3.316 | 18.137 | -0,31 (-0,50 a -0,11) | +0,28 (+0,09 a +0,48) | -0,30 (-0,47 a -0,12) | +0,18 (+0,00 a +0,37) |
| SP | 73 | 1.968 | 26.121 | -0,13 (-0,24 a -0,02) | +0,02 (-0,10 a +0,13) | -0,15 (-0,25 a -0,05) | +0,21 (+0,12 a +0,31) |
| BA | 82 | 1.047 | 10.696 | +0,19 (-0,02 a +0,39) | +0,14 (-0,03 a +0,31) | +0,01 (-0,15 a +0,17) | +0,27 (+0,00 a +0,53) |
| PE | 65 | 687 | 11.057 | -0,06 (-0,20 a +0,11) | +0,25 (+0,09 a +0,39) | -0,12 (-0,25 a +0,02) | +0,18 (-0,03 a +0,38) |
| PB | 6 | 316 | 672 | -0,21 (-0,50 a +0,10) | +0,06 (-0,25 a +0,37) | -0,06 (-0,33 a +0,20) | +0,08 (-0,18 a +0,33) |
| SE | 11 | 55 | 1.912 | -0,05 (-0,61 a +0,51) | +0,77 (+0,32 a +1,20) | -0,58 (-1,00 a -0,16) | +0,25 (-0,22 a +0,70) |
| DF | 7 | 29 | 2.466 | -0,49 (-1,10 a +0,09) | +1,20 (+0,76 a +1,65) | -0,85 (-1,34 a -0,35) | +0,33 (-0,07 a +0,71) |
| Fora da BA | 347 | 6.506 | 77.834 | -0,23 (-0,34 a -0,12) | | | +0,19 (+0,09 a +0,28) |
| Salvador, Feira de Santana e Lauro de Freitas | 22 | 880 | 4.954 | +0,21 (-0,03 a +0,45) | | | +0,29 (-0,01 a +0,61) |

Leitura: com o país inteiro, o resultado parcial de 25/10 (+0,06, IC -0,10 a +0,22, quase só BA e PB) virou -0,17 (IC -0,27 a -0,07): nas seções que ficaram abertas, a fatia do 13 cresceu um pouco menos do que nas seções vizinhas que fecharam no horário. O peso vem do RJ e de SP, que agora entram. Na BA o resultado é o mesmo da versão anterior (+0,19, intervalo que inclui zero). O comparecimento cresceu um pouco mais nas tardias em quase todos os recortes (+0,20 ponto no Brasil). Nas UFs com poucas tardias os intervalos são estreitos porque há muitos controles, mas cada estimativa se apoia em 1 a 29 seções; não deve ser lida como padrão da UF (DiD por UF completo em `resumo.json`).

## 4. Impacto na diferença final (cenários pedidos)

Diferença oficial 13 menos 22: 4.430.191.

### Nas seções tardias, com a contagem do log

| Cenário | Brasil (7.580 tardias com log) | RJ | SP | BA | PE | PB | SE |
|---|---|---|---|---|---|---|---|
| Votos depois das 17h nas tardias com log | 5.129 | 1.974 | 1.644 | 852 | 296 | 141 | 22 |
| (a) Extremo, todos para um candidato: a diferença se move no máximo | ±5.129 | ±1.974 | ±1.644 | ±852 | ±296 | ±141 | ±22 |
| (b) Saldo 13 menos 22 desses votos pela fatia da própria seção no 2º turno | +675 | -155 | +303 | +384 | +91 | +9 | +8 |
| (c) Idem pela fatia da própria seção no 1º turno (dois candidatos) | +349 | -316 | +206 | +348 | +79 | +2 | +7 |
| Diferença sem esses votos, cenário (a) com todos do 13 | 4.425.062 | 4.428.217 | 4.428.547 | 4.429.339 | 4.429.895 | 4.430.050 | 4.430.169 |
| Diferença sem esses votos, cenário (b) | 4.429.516 | 4.430.346 | 4.429.888 | 4.429.807 | 4.430.100 | 4.430.182 | 4.430.183 |

No RJ o saldo dos cenários (b) e (c) é negativo porque o 22 teve mais votos que o 13 nas tardias do estado (46,69% para o 13 no 2º turno); retirar esses votos aumentaria a margem do 13. Para (c) não é possível usar a fatia dos votos dados antes das 17h: o RDV é embaralhado por construção e o log não registra o candidato, então não há como separar os votos por horário. A fatia do 1º turno da mesma seção é o substituto.

### Estimativa nacional e cenário de descarte

| Componente | Seções | Votos depois das 17h | Como |
|---|---|---|---|
| Contagem exata no log | 21.317 | 7.030 | tardias (5.129), intermediárias (1.106), controles (581) e amostra aleatória (214) |
| Tardia sem log publicado | 1 | 0,4 | comparecimento (186) vezes a taxa do log das tardias (0,2329%); teto: 186, o comparecimento inteiro |
| Seções no horário fora da amostra | 476.579 | 24.761,6 | votos depois das 17h da seção no 1º turno (3.525.399) vezes a razão 2º/1º turno da amostra aleatória (0,00702); pela taxa da amostra aleatória sobre o comparecimento, 24.689 |
| Total | 497.897 | 31.792 | 22% exato, 78% estimado |

Votos necessários para inverter: retirando só do 13, 4.430.192 votos depois das 17h (139 vezes a estimativa nacional). Retirando na fatia de cada seção, a margem média por voto retirado é 0,24 (país) ou 0,15 (tardias e intermediárias), e seriam necessários de 18,5 a 30 milhões de votos depois das 17h, mais do que o comparecimento de todas as seções que encerraram depois de 17:10 (3,29 milhões).

## 5. Padrões nas tardias

### Distribuição da fatia do 13 no 2º turno (por seção)

| Grupo | Seções | Média | P10 | P25 | Mediana | P75 | P90 |
|---|---|---|---|---|---|---|---|
| Tardias | 7.581 | 55,6 | 38,9 | 44,4 | 54,9 | 65,4 | 74,5 |
| Controles do mesmo estrato | 88.530 | 56,2 | 39,2 | 46,1 | 55,4 | 65,4 | 75,0 |
| Tardias, 1º turno | 7.581 | 48,2 | 31,7 | 36,7 | 47,1 | 57,9 | 67,3 |
| Controles, 1º turno | 88.530 | 48,9 | 31,8 | 38,3 | 47,5 | 58,1 | 68,5 |

Histograma da fatia do 13 no 2º turno (faixas de 10 pontos, de 20 a 100%): tardias 44, 895, 2.061, 1.719, 1.575, 1.008, 257, 22; controles 1.413, 8.284, 21.232, 23.377, 19.461, 9.690, 3.951, 841 (mais 281 controles abaixo de 20%, nenhuma tardia).

### Testes simples (Welch, IC 95%)

| Medida | Tardias | Controles do mesmo estrato | Diferença | IC 95% |
|---|---|---|---|---|
| Fatia do 13 no 2º turno | 55,61 | 56,19 | -0,57 | -0,89 a -0,26 |
| Fatia do 13 no 1º turno | 48,16 | 48,92 | -0,76 | -1,08 a -0,43 |
| Variação da fatia do 13 (1º para 2º) | 7,45 | 7,27 | +0,19 | +0,13 a +0,24 |
| Variação do comparecimento (1º para 2º) | 2,97 | 2,29 | +0,68 | +0,62 a +0,73 |

O teste de Welch compara as tardias com todos os controles dos mesmos estratos juntos, sem pesar por estrato, e mistura composição geográfica. Dentro de cada município e zona (DiD, seção 3), a variação da fatia do 13 nas tardias fica 0,17 ponto **abaixo** da dos controles, e a do comparecimento 0,20 ponto acima. Não se pode atribuir essa diferença de comparecimento à prorrogação: as seções que ficaram abertas não foram escolhidas ao acaso.

### Casos extremos

41 das 7.132 tardias com estrato de 5 ou mais controles têm variação da fatia do 13 a mais de 3 desvios-padrão da média dos controles do mesmo estrato (0,57%): 28 acima e 13 abaixo do esperado; 22 delas no RJ, 6 em SP, 6 na BA e 4 em PE. Como referência, aplicando a mesma regra às próprias seções no horário (cada uma contra a média e o desvio do seu estrato), 0,40% delas passam de 3 desvios, 1.379 acima e 564 abaixo: a cauda é mais pesada que a normal e assimétrica no país inteiro, não só nas tardias. A lista está em `resumo.json` (`extremos_z3`) e em `tabelas.md`. As seis maiores:

| Seção | Encerramento | Comparecimento | % 13 no 1º | % 13 no 2º | Variação | Esperada (controles) | z |
|---|---|---|---|---|---|---|---|
| RJ, Rio de Janeiro, zona 0233, seção 0161 | 19:00:35 | 122 | 48,51 | 46,55 | -1,96 | +7,73 | -4,35 |
| RJ, Rio de Janeiro, zona 0238, seção 0227 | 19:03:09 | 279 | 34,17 | 49,43 | +15,26 | +7,16 | +4,32 |
| RJ, Rio de Janeiro, zona 0238, seção 0234 | 19:02:21 | 297 | 45,53 | 60,57 | +15,05 | +7,16 | +4,20 |
| SP, São Paulo, zona 0253, seção 0475 | 19:00:31 | 202 | 33,15 | 49,74 | +16,59 | +7,74 | +3,97 |
| RJ, Petrópolis, zona 0065, seção 0287 | 19:00:37 | 225 | 43,40 | 60,38 | +16,98 | +7,99 | +3,95 |
| RJ, Rio de Janeiro, zona 0009, seção 0429 | 19:02:28 | 327 | 48,28 | 61,90 | +13,63 | +6,74 | +3,66 |

## Limitações

- **Log do 2º turno só na amostra.** O `-log.jez` não faz parte da coleta versionada (Parquet e ClickHouse têm só `aux`, `bu`, `busa`, `vota` e `sa`) e foi baixado do TSE apenas para as 21.318 seções da amostra. A contagem é exata em todas as tardias e intermediárias, menos uma tardia sem log publicado (Niterói, zona 0144, seção 0007, 186 eleitores). Os 24.761,6 votos depois das 17h atribuídos às 476.579 seções no horário fora da amostra (78% do total nacional) são estimativa pela amostra aleatória de 4.194 seções; com a taxa dos controles pareados, mais alta, seriam 45.391, e a margem com todos retirados do 13 ficaria em 4.377.769. Como essas seções fecharam até 17:10, nenhum voto delas pode ser posterior a 17:10.
- **Seleção não aleatória.** As seções que ficaram abertas dependeram de decisões dos TREs e das mesas, do horário em que a ordem chegou e de onde havia eleitores ou fila. Diferenças entre tardias e controles não são efeito da prorrogação.
- **Composição geográfica.** As tardias estão concentradas no Rio de Janeiro, em São Paulo, Salvador, Recife, João Pessoa e entorno. Comparações sem estrato misturam essa composição com o horário; por isso o resultado principal é o DiD dentro de município e zona.
- **Fatia dos votos depois das 17h.** O candidato de cada voto não é observável por horário (RDV embaralhado, log sem candidato). Os cenários (b) e (c) supõem que esses votos se dividiram como o total da seção no 2º turno ou no 1º turno.
- **Horário do BU e do log.** O horário de encerramento é o do relógio da urna, convertido pelo fuso do município. Seções com urna de contingência (`reservaSecao`, `reservaEncerrandoSecao`) usam o BU final. Uma seção da amostra tem número de votos no log diferente do comparecimento do BU.
- **Exterior** (1.310 seções) fora da análise: cada país segue o próprio fuso.
- **Totalizadas e BUs.** O TSE totalizou 499.248 seções; a coleta tem BU de 499.207 (497.897 no Brasil e 1.310 no exterior). As somas de 13 e 22 dos BUs batem exatamente com o total oficial.

## Como reproduzir

No servidor de processamento (as partes ficam lá, só leitura), com um ambiente temporário em memória (`/dev/shm`), sem gravar nada em `/work`:

```sh
# código e referências do 1º turno no ambiente temporário
rsync -a --relative pyproject.toml src/dataurnas spec scripts/ele2026 tests/ele2026 \
  data/parquet/2026/secoes_2026.parquet data/parquet/2026/votos_presidente_2026.parquet \
  data/parquet/2026/resumo_br.json data/parquet/2026/rdv/log_tempo_secoes.parquet \
  data/parquet/2026/t2/impacto/logs_contagens.jsonl data/parquet/2026/t2/encerramento/municipios.json \
  <servidor>:/dev/shm/enc-nac/
cd /dev/shm/enc-nac && UV_CACHE_DIR=/dev/shm/enc-nac/.uvcache uv venv -p 3.12 venv
VIRTUAL_ENV=venv uv pip install asn1tools httpx py7zr click pandas numpy pyarrow cryptography scipy pytest

# 1) decodificação nacional dos BUs (cerca de 2 min com 64 processos)
venv/bin/python scripts/ele2026/analisar_encerramento_t2.py \
  --parts ~/dataurnas-mac/versoes/2026/t2/bus/parts \
  --parts ~/dataurnas-mac/versoes/2026/t2-sseco/bus/parts \
  --parts ~/dataurnas-versoes-t2/bus/parts \
  --parts ~/dataurnas-versoes-t2-nne/bus/parts \
  --municipios data/parquet/2026/t2/encerramento/municipios.json --workers 64

# 2) análise nacional (cerca de 2,5 min), com o total oficial final
venv/bin/python scripts/ele2026/impacto_prorrogacao_t2.py \
  --oficial-13 64256232 --oficial-22 59826041 --oficial-comparecimento 128236074 \
  --oficial-fonte "v_totais_ultima br, totalizado 25/10/2026 23:22:22, 499.248 de 499.248 seções"

# 2a) contagem exata da amostra inteira (execução de 26/10/2026, na máquina local):
#     primeiro com --baixar-logs (baixa só os logs que faltam no cache, 3 req/s;
#     15.929 arquivos das 06:45 às 08:15), depois a análise sobre o cache completo
nice -n 20 uv run --with scipy python scripts/ele2026/impacto_prorrogacao_t2.py \
  --oficial-13 64256232 --oficial-22 59826041 \
  --oficial-fonte "TSE br-c0001-e006258-u.json 25/10/2026 23:22:22" --baixar-logs
nice -n 20 uv run --with scipy python scripts/ele2026/impacto_prorrogacao_t2.py \
  --oficial-13 64256232 --oficial-22 59826041 \
  --oficial-fonte "TSE br-c0001-e006258-u.json 25/10/2026 23:22:22"

# testes
venv/bin/python -m pytest -q tests/ele2026/test_impacto_prorrogacao_t2.py tests/ele2026/test_encerramento_t2.py
```

Consultas no ClickHouse (`~/dataurnas-ch/app/scripts/ch/ch.sh < arquivo.sql`):

```sql
-- total oficial final e soma dos BUs
SELECT abr, totalizado_em, st, ts, cand['13'] AS v13, cand['22'] AS v22,
       cand['13'] - cand['22'] AS margem
FROM v_totais_ultima WHERE nivel = 'br';
SELECT count() AS secoes, sum(votos_13) AS v13, sum(votos_22) AS v22,
       sum(votos_13) - sum(votos_22) AS margem, sum(comparecimento) AS comp
FROM v_votos_t2_secao;

-- tipos de arquivo guardados na coleta (não há log)
SELECT tipo, count(), sum(tamanho) FROM versoes_arquivo FINAL GROUP BY tipo;

-- encerramento_uf.sql: encerramento por UF, Brasília, minuto truncado
WITH
  multiIf(cd_mun IN ('02020','02054','02135','02291','02313','02399','02496','02755',
                     '02917','98370','98477'), -5,
          cd_mun = '30015', -2,
          uf = 'ac', -5,
          uf IN ('am','mt','ms','ro','rr'), -4, -3) AS fuso,
  hora_encerramento + toIntervalHour(-3 - fuso) AS enc_bsb,
  dateDiff('minute', toDateTime('2026-10-25 17:00:00', 'UTC'), toStartOfMinute(enc_bsb)) AS m
SELECT uf, count() AS secoes,
       countIf(m >= 1) AS depois_17h00, countIf(m >= 11) AS depois_17h10,
       countIf(m >= 31) AS depois_17h30, countIf(m >= 61) AS depois_18h00,
       countIf(m >= 121) AS depois_19h00, max(enc_bsb) AS ultimo_bsb
FROM v_bu_ultima
WHERE uf != 'zz'
GROUP BY uf WITH TOTALS
ORDER BY depois_17h30 DESC;

-- apos_19h15.sql: mesmas expressões do WITH acima, seções depois de 19:15
-- SELECT uf, cd_mun, zona, secao, hora_abertura, hora_encerramento, enc_bsb,
--        recebimento, tipo_urna, comparecimento
-- FROM v_bu_ultima WHERE uf != 'zz' AND m >= 136 ORDER BY enc_bsb DESC;
```

O cache `logs_contagens.jsonl` é incremental e a amostra é estável: com o cache completo (21.318 seções), rodar o passo 2a sem `--baixar-logs` reproduz os números deste relatório sem nenhum acesso ao TSE. Os números derivados que não estão no `resumo.json` (sensibilidade da estimativa no horário pela taxa sobre o comparecimento ou pela taxa dos controles, votos do 1º turno nas seções no horário fora da amostra, tabela de tardias por UF) saem de `amostra_logs.parquet` e dos totais de `log_votos_apos_17h` e `votos_por_grupo`, como descrito em "Definições".
