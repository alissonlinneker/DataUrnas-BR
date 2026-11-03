# Viradas de liderança entre o 1º e o 2º turno por seção: 2026 comparado com 2022

Levantamento de 26/10/2026 sobre as seções em que o candidato que liderou no 1º turno presidencial de 2026 (04/10/2026) perdeu a liderança no 2º turno (25/10/2026), considerando só 13 (Lula) e 22 (Flávio Bolsonaro). A pergunta é se o número e o tamanho dessas viradas fogem do que é normal entre dois turnos. A referência é a eleição de 2022 (13, Lula, contra 22, Jair Bolsonaro; 1º turno em 02/10/2022 e 2º turno em 30/10/2022), medida com exatamente as mesmas regras, seção a seção.

O levantamento é descritivo. Ele não afirma fraude e também não a descarta sem base: aponta o que é esperado, o que não é, e lista as seções que merecem ser conferidas contra o boletim de urna impresso.

**Esta versão cobre o país inteiro.** São 497.897 seções do Brasil com BU nos dois turnos (todas as 27 UFs com 100% das seções do 1º turno pareadas), mais 1.308 do exterior tratadas à parte. As versões anteriores deste documento usavam amostras parciais (145.489 seções, quase só Norte e Nordeste, e depois 248.578 seções); a comparação com elas está na seção "O que mudou em relação às execuções parciais".

Arquivos:

| Arquivo | Para quê |
|---|---|
| `scripts/ele2026/viradas_t1_t2.py` | análise seção a seção, modelo de esperado, atípicos e tabela por grupo (testes em `tests/ele2026/test_viradas_t1_t2.py`) |
| `scripts/ele2026/viradas_t2_ch.sql` | exporta do ClickHouse o 2º turno inteiro no formato que o script lê |
| `scripts/ele2026/viradas_grupos_ch.sql` | a tabela por grupo de virada direto no ClickHouse (Brasil, regiões, UFs e exterior), com a conferência de fechamento por seção |

Saída, fora do git: `data/parquet/2026/t2/viradas/` (`resumo.json`, `resumo_uf.parquet`, `faixas.parquet`, `grupos.parquet`, `secoes_2026.parquet`, `secoes_2022.parquet`, `atipicos_2026.csv` e `.parquet`, `atipicos_2022.csv` e `.parquet`, e `t2_clickhouse.parquet`, a exportação usada). A saída da execução parcial de 145.489 seções ficou em `data/parquet/2026/t2/viradas/parcial_145489/`.

Como foi rodado (26/10/2026, 09h27 a 09h30 no servidor de processamento, tudo em `/dev/shm`; o 1º turno e 2022 são os mesmos Parquet do repositório, conferidos por SHA-256):

```sh
# no servidor: 2º turno exportado do ClickHouse e tabela por grupo
~/dataurnas-ch/app/scripts/ch/ch.sh < scripts/ele2026/viradas_t2_ch.sql > t2.parquet
~/dataurnas-ch/app/scripts/ch/ch.sh < scripts/ele2026/viradas_grupos_ch.sql > grupos.tsv
# análise (pandas, numpy, duckdb e pyarrow; cerca de 30 s)
python scripts/ele2026/viradas_t1_t2.py --t2 t2.parquet --software t2.parquet --sem-bu
```

`--software` aponta para a própria exportação porque ela já traz o número interno da urna e o código de carga de cada BU do 2º turno; `--sem-bu` dispensa a leitura dos BUs nos parts locais, que não é mais necessária.

## Resumo

| Item | 2026 | 2022 (referência) |
|---|---|---|
| Seções com BU nos dois turnos (Brasil, sem exterior) | 497.897 | 470.808 |
| Movimento médio da fatia do 13 (13 ÷ (13 + 22)) entre turnos, por seção | **+2,91 pontos** | **-1,64 ponto** |
| Desvio padrão desse movimento entre seções | 2,37 pontos | 2,20 pontos |
| Viradas no sentido do movimento geral | 22 para 13: **31.341** (11,3% das 278.222 seções em que o 22 liderou) | 13 para 22: **19.383** (7,9% das 243.847 seções em que o 13 liderou) |
| Esperado pelo modelo de 2022 | 32.604 (desvio 107); observado ÷ esperado **0,96** | 18.898; observado ÷ esperado 1,03 |
| Viradas no sentido contrário | 13 para 22: **555** (0,26% das 217.536) | 22 para 13: 1.491 (0,66%) |
| Esperado pelo modelo de 2022 | 798 (desvio 27); observado ÷ esperado 0,70 | 1.976; observado ÷ esperado 0,75 |
| Margem média no 1º turno das seções que viraram | 11,0 votos (mediana 9) | 8,6 votos (mediana 7) |
| Viradas com margem de até 10 votos no 1º turno | 56% | 68% |
| Viradas com troca mínima zero | 87% | 86% |
| Troca mínima nas viradas: mediana, p90, p99, máximo | 0, 1, 8, 55 | 0, 2, 8, 129 |
| Seções com troca alta (critério 1) | 330; esperado pela taxa de 2022, 659 | 198 |
| Seções com troca estrita > 0 (critério 2) | 11 (0,22 por 10 mil) | 11 (0,23 por 10 mil) |
| Seções com desvio forte, \|z\| > 4 (critério 3) | 690 (13,9 por 10 mil) | 653 (13,9 por 10 mil) |
| Atípicos (qualquer critério), por 10 mil seções | 968 (19,4) | 778 (16,5) |

Em poucas linhas:

1. **O número de viradas é o esperado.** O 13 ganhou fatia em todas as regiões entre os turnos (+2,0 pontos no Nordeste, +2,6 no Norte, +3,0 no Sul, +3,25 no Centro-Oeste, +3,5 no Sudeste, em média por seção), e com isso as seções em que o 22 tinha liderado por poucos votos tendem a virar. O modelo ajustado em 2022, que usa só a margem do 1º turno, o movimento do município e o volume de outros, brancos e nulos, esperava 32.604 viradas de 22 para 13; foram 31.341 (4% a menos). Por UF, a razão observado ÷ esperado ficou entre 0,62 (RO) e 1,22 (RR). Em 2022, no sentido principal (13 para 22), ela foi de 0,44 a 1,38 por UF, e no sentido contrário de 0,29 a 4,02.
2. **O sentido contrário (13 para 22) teve menos viradas do que o esperado**, 555 contra 798 (0,70), praticamente a mesma razão de 2022 no sentido contrário (0,75). O modelo superestima viradas contra o movimento geral. A exceção regional é o Centro-Oeste, com 88 viradas de 13 para 22 contra 46 esperadas (DF 24 contra 8,6; GO 39 contra 22,4; MT 11 contra 6,0; MS 14 contra 9,4). São números pequenos e da mesma ordem dos desvios regionais de 2022 no sentido contrário (Nordeste 1,33; CE 4,02).
3. **A dispersão do movimento entre seções é a mesma de 2022.** O desvio padrão da variação da fatia do 13 foi 2,37 pontos em 2026 e 2,20 em 2022; entre p1 e p99 a largura é 11,25 pontos em 2026 e 10,5 em 2022. O que mudou foi o sentido do movimento, não a forma da distribuição.
4. **Troca mínima alta ficou abaixo do esperado no país.** Em 2026, 330 seções exigiriam pelo menos 10 eleitores (e 5% do comparecimento) passando diretamente de um candidato para o outro se só se contasse a reserva líquida; a taxa de 2022 por faixa de movimento e de reserva previa 659. O excesso está concentrado no Nordeste (193 contra 133), sobretudo CE (52 contra 17,6), RN (32 contra 16,9) e MA (35 contra 27,5). No Sudeste, no Sul e no Centro-Oeste ficou muito abaixo (88 contra 450). O maior caso de 2026 tem 55 votos; o de 2022, 129.
5. **Troca obrigatória mesmo com rotatividade total é rara e igual nos dois anos:** 11 seções em 2026 e 11 em 2022 (0,22 e 0,23 por 10 mil). Só uma passa de 5 votos (Santo Antônio de Lisboa, PI, 0028/0099, com 24).
6. **Desvio forte em relação ao próprio município tem a mesma frequência de 2022:** 13,9 por 10 mil seções nos dois anos. Vários grupos de casos vêm de municípios pequenos inteiros que se moveram de forma diferente do estado: Rafael Godeiro (RN, 9 de 11 seções atípicas; a fatia do 13 no município subiu de 55,7% para 65,9%, contra +2,5 pontos no RN), Belo Monte (AL, 14 de 16; caiu de 70,3% para 61,6%) e Santo Antônio de Lisboa (PI, 13 de 24; caiu de 76,3% para 68,7%). Isso indica fator local, não urna isolada.
7. **Nos atípicos, a urna é quase sempre a mesma do 1º turno.** Em 960 dos 968 o número interno da urna é o mesmo nos dois turnos, e em 959 o código de carga também; nas 8 restantes a urna foi trocada. Seções que encerraram depois das 17h10 de Brasília não concentram atípicos (0,13% contra 0,20% das demais) e têm quase a mesma taxa de viradas (6,9% contra 6,4%).
8. **A contabilidade fecha em todas as seções.** Em cada uma das 499.205 seções pareadas (Brasil e exterior), 13 + 22 + outros + brancos + nulos = comparecimento nos dois turnos, sem exceção. Por isso o ganho de 13 + 22 de cada grupo é exatamente a soma dos votos de outros do 1º turno, da queda de brancos e nulos e da variação do comparecimento (tabelas abaixo).

Conclusão descritiva: com o país inteiro, o número de viradas de 2026 é o que se espera de um movimento de cerca de 3 pontos a favor do 13 aplicado a seções com margem de poucos votos. Não há excesso de viradas, nem no total nem por UF. A troca mínima alta e a troca estrita estão no nível de 2022 ou abaixo dele; o que fica acima da referência é um grupo pequeno de seções no Nordeste (CE, RN, MA) e alguns municípios pequenos inteiros que se moveram contra ou muito além da tendência do estado. Essas seções estão listadas abaixo para conferência; a explicação mais comum para casos assim é local (município que mudou de lado, eleitores que votaram em um turno e não no outro, agregação de seções), mas isso só se confirma caso a caso.

## Variação de votos por grupo de virada

Pedido do dono: para cada grupo (22 para 13, 13 para 22, sem virada), seções e variação de Lula, Flávio, outros, brancos, nulos, inválidos (brancos + nulos), abstenção e comparecimento, em número absoluto e percentual, do 1º para o 2º turno, no Brasil e por UF e região. Fonte: `grupos.parquet` do script; os mesmos números saem de `viradas_grupos_ch.sql` direto no ClickHouse (a linha Brasil do script é a soma das cinco regiões da consulta; o exterior está só na consulta). Abstenção = aptos menos comparecimento; percentual de abstenção sobre os aptos; percentual de inválidos sobre o comparecimento.

### Brasil, 2026 (497.897 seções)

| Variação do 1º para o 2º turno | 22 para 13 | 13 para 22 | sem virada | todas |
|---|---:|---:|---:|---:|
| Seções | 31.341 | 555 | 466.001 | 497.897 |
| Lula (13) | +879.247 (+26,6%) | +4.131 (+7,7%) | +9.450.549 (+18,8%) | +10.333.927 (+19,2%) |
| Flávio (22) | +169.118 (+4,6%) | +9.104 (+17,8%) | +3.515.719 (+6,7%) | +3.693.941 (+6,6%) |
| Outros candidatos | -689.702 (-100,0%) | -10.524 (-100,0%) | -8.592.049 (-100,0%) | -9.292.275 (-100,0%) |
| Brancos | -76.441 (-41,7%) | -531 (-28,2%) | -792.189 (-37,5%) | -869.161 (-37,9%) |
| Nulos | -68.364 (-26,1%) | -404 (-13,5%) | -877.102 (-25,8%) | -945.870 (-25,8%) |
| Inválidos (brancos + nulos) | -144.805 (-32,6%) | -935 (-19,2%) | -1.669.291 (-30,3%) | -1.815.031 (-30,5%) |
| Abstenção | -213.692 (-9,3%) | -1.815 (-5,2%) | -2.705.204 (-8,9%) | -2.920.711 (-8,9%) |
| Comparecimento | +213.858 (+2,6%) | +1.776 (+1,5%) | +2.704.928 (+2,3%) | +2.920.562 (+2,3%) |
| Taxa de abstenção, 1º para 2º | 22,2% para 20,1% | 22,4% para 21,2% | 20,7% para 18,9% | 20,8% para 19,0% |
| Inválidos ÷ comparecimento, 1º para 2º | 5,5% para 3,6% | 4,1% para 3,2% | 4,7% para 3,2% | 4,8% para 3,2% |

Leitura: nas seções que viraram para o 13, o 13 ganhou 879.247 votos (+26,6%) e o 22 também ganhou, 169.118 (+4,6%). Os dois ganhos somam 1.048.365, que é exatamente o que entrou: 689.702 votos de outros candidatos no 1º turno, 144.805 de queda de brancos e nulos e 213.858 de aumento do comparecimento. Essas seções começaram com mais abstenção (22,2%) e mais inválidos (5,5%) que as demais, e foram as que mais reduziram as duas coisas. Nas 555 que viraram para o 22, o 22 ganhou 9.104 (+17,8%) e o 13 ganhou 4.131 (+7,7%); a soma, 13.235, é igual a 10.524 de outros, 935 de queda de brancos e nulos e 1.776 de comparecimento.

Detalhe de cada grupo, com os valores do 1º e do 2º turno:

**Viradas de 22 para 13 (Flávio liderou no 1º turno, Lula no 2º): 31.341 seções**

| Item | 1º turno | 2º turno | Variação | Variação % |
|---|---:|---:|---:|---:|
| Lula (13) | 3.300.822 | 4.180.069 | +879.247 | +26,6% |
| Flávio (22) | 3.649.919 | 3.819.037 | +169.118 | +4,6% |
| Outros candidatos | 689.702 | 0 | -689.702 | -100,0% |
| Brancos | 183.253 | 106.812 | -76.441 | -41,7% |
| Nulos | 261.588 | 193.224 | -68.364 | -26,1% |
| Inválidos (brancos + nulos) | 444.841 (5,5%) | 300.036 (3,6%) | -144.805 | -32,6% |
| Abstenção | 2.306.755 (22,2%) | 2.093.063 (20,1%) | -213.692 | -9,3% |
| Comparecimento | 8.085.284 (77,8%) | 8.299.142 (79,9%) | +213.858 | +2,6% |
| Aptos | 10.392.039 | 10.392.205 | +166 | +0,0% |

**Viradas de 13 para 22 (Lula liderou no 1º turno, Flávio no 2º): 555 seções**

| Item | 1º turno | 2º turno | Variação | Variação % |
|---|---:|---:|---:|---:|
| Lula (13) | 53.433 | 57.564 | +4.131 | +7,7% |
| Flávio (22) | 51.037 | 60.141 | +9.104 | +17,8% |
| Outros candidatos | 10.524 | 0 | -10.524 | -100,0% |
| Brancos | 1.883 | 1.352 | -531 | -28,2% |
| Nulos | 2.997 | 2.593 | -404 | -13,5% |
| Inválidos (brancos + nulos) | 4.880 (4,1%) | 3.945 (3,2%) | -935 | -19,2% |
| Abstenção | 34.594 (22,4%) | 32.779 (21,2%) | -1.815 | -5,2% |
| Comparecimento | 119.874 (77,6%) | 121.650 (78,8%) | +1.776 | +1,5% |
| Aptos | 154.468 | 154.429 | -39 | -0,0% |

**Sem virada: 466.001 seções**

| Item | 1º turno | 2º turno | Variação | Variação % |
|---|---:|---:|---:|---:|
| Lula (13) | 50.367.896 | 59.818.445 | +9.450.549 | +18,8% |
| Flávio (22) | 52.259.647 | 55.775.366 | +3.515.719 | +6,7% |
| Outros candidatos | 8.592.049 | 0 | -8.592.049 | -100,0% |
| Brancos | 2.109.846 | 1.317.657 | -792.189 | -37,5% |
| Nulos | 3.399.473 | 2.522.371 | -877.102 | -25,8% |
| Inválidos (brancos + nulos) | 5.509.319 (4,7%) | 3.840.028 (3,2%) | -1.669.291 | -30,3% |
| Abstenção | 30.553.550 (20,7%) | 27.848.346 (18,9%) | -2.705.204 | -8,9% |
| Comparecimento | 116.728.911 (79,3%) | 119.433.839 (81,1%) | +2.704.928 | +2,3% |
| Aptos | 147.282.461 | 147.282.185 | -276 | -0,0% |

**Todas as seções: 497.897 seções**

| Item | 1º turno | 2º turno | Variação | Variação % |
|---|---:|---:|---:|---:|
| Lula (13) | 53.722.151 | 64.056.078 | +10.333.927 | +19,2% |
| Flávio (22) | 55.960.603 | 59.654.544 | +3.693.941 | +6,6% |
| Outros candidatos | 9.292.275 | 0 | -9.292.275 | -100,0% |
| Brancos | 2.294.982 | 1.425.821 | -869.161 | -37,9% |
| Nulos | 3.664.058 | 2.718.188 | -945.870 | -25,8% |
| Inválidos (brancos + nulos) | 5.959.040 (4,8%) | 4.144.009 (3,2%) | -1.815.031 | -30,5% |
| Abstenção | 32.894.899 (20,8%) | 29.974.188 (19,0%) | -2.920.711 | -8,9% |
| Comparecimento | 124.934.069 (79,2%) | 127.854.631 (81,0%) | +2.920.562 | +2,3% |
| Aptos | 157.828.968 | 157.828.819 | -149 | -0,0% |

### Brasil, 2022 (referência, 470.808 seções)

Em 2022 o movimento foi para o 22, e as viradas no sentido do movimento foram as de 13 para 22. Diferenças marcantes: em 2022 os nulos subiram no 2º turno (+12,7%) e o comparecimento quase não mudou (+0,5%); em 2026 brancos e nulos caíram cerca de 30% e o comparecimento subiu 2,3%.

| Variação do 1º para o 2º turno | 22 para 13 | 13 para 22 | sem virada | todas |
|---|---:|---:|---:|---:|
| Seções | 1.491 | 19.383 | 449.934 | 470.808 |
| Lula (13) | +27.354 (+17,0%) | +52.234 (+2,2%) | +2.991.859 (+5,5%) | +3.071.447 (+5,4%) |
| Flávio (22) | +12.464 (+7,4%) | +413.744 (+19,1%) | +6.683.644 (+13,8%) | +7.109.852 (+14,0%) |
| Outros candidatos | -39.787 (-100,0%) | -449.081 (-100,0%) | -9.373.622 (-100,0%) | -9.862.490 (-100,0%) |
| Brancos | -115 (-2,0%) | -13.221 (-13,6%) | -182.756 (-9,8%) | -196.092 (-10,0%) |
| Nulos | +1.532 (+13,9%) | +17.400 (+11,6%) | +422.368 (+12,7%) | +441.300 (+12,7%) |
| Inválidos (brancos + nulos) | +1.417 (+8,4%) | +4.179 (+1,7%) | +239.612 (+4,6%) | +245.208 (+4,5%) |
| Abstenção | +807 (+0,8%) | -14.332 (-1,0%) | -349.873 (-1,1%) | -363.398 (-1,1%) |
| Comparecimento | +1.448 (+0,4%) | +21.076 (+0,4%) | +541.493 (+0,5%) | +564.017 (+0,5%) |
| Taxa de abstenção, 1º para 2º | 21,5% para 21,6% | 20,9% para 20,7% | 20,7% para 20,4% | 20,7% para 20,4% |
| Inválidos ÷ comparecimento, 1º para 2º | 4,4% para 4,7% | 4,8% para 4,8% | 4,4% para 4,6% | 4,4% para 4,6% |

### Por região e UF, 2026

Cada célula traz a variação absoluta do 1º para o 2º turno e, entre parênteses, a variação percentual; na abstenção, a taxa do 1º e do 2º turno. "Outros" é sempre -100% porque no 2º turno só há 13 e 22.

| Local | Grupo | Seções | Lula | Flávio | Outros | Brancos | Nulos | Inválidos | Abstenção (taxa 1º para 2º) | Comparecimento |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|
| **Brasil** | 22 para 13 | 31.341 | +879.247 (+26,6%) | +169.118 (+4,6%) | -689.702 (-100,0%) | -76.441 (-41,7%) | -68.364 (-26,1%) | -144.805 (-32,6%) | -213.692 (22,2% para 20,1%) | +213.858 (+2,6%) |
| **Brasil** | 13 para 22 | 555 | +4.131 (+7,7%) | +9.104 (+17,8%) | -10.524 (-100,0%) | -531 (-28,2%) | -404 (-13,5%) | -935 (-19,2%) | -1.815 (22,4% para 21,2%) | +1.776 (+1,5%) |
| **Brasil** | sem virada | 466.001 | +9.450.549 (+18,8%) | +3.515.719 (+6,7%) | -8.592.049 (-100,0%) | -792.189 (-37,5%) | -877.102 (-25,8%) | -1.669.291 (-30,3%) | -2.705.204 (20,7% para 18,9%) | +2.704.928 (+2,3%) |
| **Norte** | 22 para 13 | 2.781 | +53.477 (+17,4%) | -5.948 (-1,8%) | -52.717 (-100,0%) | -2.996 (-31,5%) | -5.705 (-30,9%) | -8.701 (-31,1%) | +13.869 (18,9% para 20,4%) | -13.889 (-1,9%) |
| **Norte** | 13 para 22 | 78 | -289 (-3,7%) | +523 (+7,0%) | -968 (-100,0%) | -5 (-3,5%) | -78 (-18,5%) | -83 (-14,7%) | +814 (20,3% para 24,1%) | -817 (-4,8%) |
| **Norte** | sem virada | 40.910 | +420.836 (+9,9%) | +19.535 (+0,4%) | -578.599 (-100,0%) | -24.649 (-24,7%) | -60.300 (-25,7%) | -84.949 (-25,4%) | +222.881 (19,5% para 21,3%) | -223.177 (-2,3%) |
| **Nordeste** | 22 para 13 | 3.890 | +102.039 (+22,1%) | +11.115 (+2,2%) | -71.098 (-100,0%) | -7.948 (-41,6%) | -11.636 (-34,1%) | -19.584 (-36,8%) | -22.516 (17,6% para 15,9%) | +22.472 (+2,1%) |
| **Nordeste** | 13 para 22 | 51 | +300 (+5,7%) | +777 (+15,7%) | -786 (-100,0%) | -49 (-30,6%) | -96 (-29,2%) | -145 (-29,7%) | -150 (19,3% para 18,3%) | +146 (+1,3%) |
| **Nordeste** | sem virada | 136.887 | +2.853.509 (+13,6%) | +385.871 (+3,9%) | -1.740.457 (-100,0%) | -249.552 (-44,0%) | -445.228 (-37,7%) | -694.780 (-39,7%) | -804.474 (18,4% para 16,5%) | +804.143 (+2,3%) |
| **Centro-Oeste** | 22 para 13 | 2.066 | +59.064 (+29,1%) | +16.030 (+7,1%) | -56.608 (-100,0%) | -1.907 (-24,6%) | -3.092 (-24,9%) | -4.999 (-24,8%) | -13.423 (22,9% para 20,9%) | +13.487 (+2,7%) |
| **Centro-Oeste** | 13 para 22 | 88 | +868 (+10,5%) | +1.689 (+21,3%) | -2.211 (-100,0%) | -53 (-22,9%) | -33 (-9,8%) | -86 (-15,1%) | -273 (21,9% para 20,8%) | +260 (+1,4%) |
| **Centro-Oeste** | sem virada | 35.894 | +710.944 (+25,8%) | +452.712 (+9,2%) | -929.234 (-100,0%) | -15.082 (-14,4%) | -34.069 (-18,3%) | -49.151 (-16,9%) | -184.767 (21,6% para 20,0%) | +185.271 (+2,1%) |
| **Sudeste** | 22 para 13 | 19.733 | +587.576 (+28,8%) | +129.767 (+5,7%) | -452.246 (-100,0%) | -55.313 (-42,9%) | -42.963 (-23,8%) | -98.276 (-31,7%) | -166.661 (23,3% para 20,8%) | +166.821 (+3,3%) |
| **Sudeste** | 13 para 22 | 230 | +2.585 (+11,3%) | +4.525 (+20,6%) | -4.974 (-100,0%) | -265 (-28,8%) | -155 (-10,2%) | -420 (-17,2%) | -1.729 (24,0% para 21,5%) | +1.716 (+3,3%) |
| **Sudeste** | sem virada | 183.274 | +4.210.172 (+24,5%) | +1.810.600 (+8,0%) | -3.888.158 (-100,0%) | -392.206 (-38,6%) | -295.040 (-20,1%) | -687.246 (-27,6%) | -1.445.301 (22,6% para 20,2%) | +1.445.368 (+3,1%) |
| **Sul** | 22 para 13 | 2.871 | +77.091 (+26,9%) | +18.154 (+5,8%) | -57.033 (-100,0%) | -8.277 (-46,4%) | -4.968 (-30,9%) | -13.245 (-39,1%) | -24.961 (23,6% para 20,9%) | +24.967 (+3,6%) |
| **Sul** | 13 para 22 | 108 | +667 (+7,3%) | +1.590 (+18,2%) | -1.585 (-100,0%) | -159 (-37,1%) | -42 (-11,0%) | -201 (-24,8%) | -477 (22,0% para 20,2%) | +471 (+2,3%) |
| **Sul** | sem virada | 69.036 | +1.255.088 (+24,2%) | +847.001 (+8,3%) | -1.455.601 (-100,0%) | -110.700 (-34,4%) | -42.465 (-13,0%) | -153.165 (-23,6%) | -493.543 (20,3% para 18,1%) | +493.323 (+2,8%) |
| AC | 22 para 13 | 34 | +81 (+2,9%) | -767 (-23,4%) | -322 (-100,0%) | -6 (-11,1%) | +34 (+13,3%) | +28 (+9,1%) | +977 (24,3% para 35,3%) | -980 (-14,5%) |
| AC | 13 para 22 | 4 | -101 (-26,2%) | +50 (+16,1%) | -37 (-100,0%) | +2 (+40,0%) | +5 (+13,5%) | +7 (+16,7%) | +79 (23,1% para 31,0%) | -81 (-10,5%) |
| AC | sem virada | 2.232 | +9.763 (+7,4%) | -14.375 (-4,8%) | -31.153 (-100,0%) | -559 (-10,1%) | +2.709 (+20,3%) | +2.150 (+11,4%) | +33.593 (20,4% para 25,9%) | -33.615 (-7,0%) |
| AL | 22 para 13 | 721 | +20.069 (+22,7%) | +402 (+0,4%) | -11.274 (-100,0%) | -2.241 (-50,9%) | -4.780 (-54,0%) | -7.021 (-53,0%) | -2.204 (19,3% para 18,5%) | +2.176 (+1,0%) |
| AL | 13 para 22 | 2 | +11 (+5,9%) | +22 (+12,2%) | -26 (-100,0%) | -5 (-55,6%) | -5 (-38,5%) | -10 (-45,5%) | +3 (20,6% para 21,2%) | -3 (-0,7%) |
| AL | sem virada | 6.378 | +137.082 (+15,1%) | +7.998 (+1,3%) | -76.452 (-100,0%) | -14.483 (-49,4%) | -43.114 (-56,0%) | -57.597 (-54,2%) | -11.048 (20,8% para 20,3%) | +11.031 (+0,6%) |
| AM | 22 para 13 | 560 | +11.045 (+16,7%) | -2.298 (-3,1%) | -12.154 (-100,0%) | -618 (-27,3%) | +912 (+32,3%) | +294 (+5,8%) | +3.098 (19,7% para 21,3%) | -3.113 (-2,0%) |
| AM | 13 para 22 | 17 | -71 (-3,9%) | +78 (+4,4%) | -252 (-100,0%) | +11 (+33,3%) | +22 (+35,5%) | +33 (+34,7%) | +212 (24,1% para 28,1%) | -212 (-5,4%) |
| AM | sem virada | 7.580 | +87.813 (+9,0%) | +701 (+0,1%) | -134.679 (-100,0%) | -5.471 (-24,7%) | +12.471 (+34,2%) | +7.000 (+12,0%) | +39.230 (20,2% para 21,7%) | -39.165 (-1,9%) |
| AP | 22 para 13 | 340 | +4.247 (+11,4%) | -3.011 (-7,3%) | -8.242 (-100,0%) | -179 (-21,3%) | -425 (-31,3%) | -604 (-27,5%) | +7.616 (16,8% para 24,0%) | -7.610 (-8,6%) |
| AP | 13 para 22 | 6 | -87 (-14,1%) | -55 (-9,2%) | -87 (-100,0%) | -2 (-22,2%) | -7 (-36,8%) | -9 (-32,1%) | +239 (18,3% para 32,9%) | -238 (-17,9%) |
| AP | sem virada | 1.568 | +6.305 (+3,6%) | -10.538 (-6,2%) | -31.765 (-100,0%) | -914 (-25,6%) | -1.827 (-31,0%) | -2.741 (-29,0%) | +38.654 (17,5% para 25,8%) | -38.739 (-10,0%) |
| BA | 22 para 13 | 534 | +13.354 (+21,8%) | +2.311 (+3,5%) | -9.494 (-100,0%) | -596 (-27,6%) | -945 (-23,3%) | -1.541 (-24,8%) | -4.687 (19,9% para 17,3%) | +4.630 (+3,2%) |
| BA | 13 para 22 | 27 | +159 (+6,1%) | +436 (+17,7%) | -396 (-100,0%) | -28 (-33,3%) | -50 (-26,6%) | -78 (-28,7%) | -122 (21,5% para 19,9%) | +121 (+2,1%) |
| BA | sem virada | 34.915 | +806.974 (+14,4%) | +163.429 (+6,9%) | -443.296 (-100,0%) | -61.591 (-40,3%) | -101.821 (-30,5%) | -163.412 (-33,6%) | -363.498 (20,0% para 16,7%) | +363.695 (+4,1%) |
| CE | 22 para 13 | 487 | +11.893 (+21,2%) | +1.271 (+2,1%) | -9.056 (-100,0%) | -962 (-40,6%) | -1.135 (-31,6%) | -2.097 (-35,2%) | -2.003 (14,3% para 13,0%) | +2.011 (+1,5%) |
| CE | 13 para 22 | 4 | +22 (+5,4%) | +66 (+17,7%) | -79 (-100,0%) | +1 (+14,3%) | +1 (+6,7%) | +2 (+9,1%) | -16 (13,5% para 12,0%) | +11 (+1,2%) |
| CE | sem virada | 23.274 | +468.946 (+13,4%) | +61.291 (+3,6%) | -296.743 (-100,0%) | -45.948 (-45,5%) | -75.196 (-40,5%) | -121.144 (-42,3%) | -112.377 (15,6% para 13,9%) | +112.350 (+1,9%) |
| DF | 22 para 13 | 556 | +15.037 (+25,7%) | +3.456 (+5,3%) | -15.113 (-100,0%) | -397 (-17,5%) | +597 (+21,6%) | +200 (+4,0%) | -3.517 (20,5% para 18,5%) | +3.580 (+2,5%) |
| DF | 13 para 22 | 24 | +275 (+10,5%) | +476 (+18,8%) | -688 (-100,0%) | -20 (-25,3%) | +32 (+42,7%) | +12 (+7,8%) | -79 (17,3% para 16,2%) | +75 (+1,2%) |
| DF | sem virada | 6.389 | +134.285 (+21,9%) | +65.994 (+7,8%) | -171.821 (-100,0%) | -2.559 (-11,1%) | +7.330 (+24,2%) | +4.771 (+8,9%) | -32.613 (18,8% para 17,2%) | +33.229 (+2,0%) |
| ES | 22 para 13 | 684 | +14.969 (+21,4%) | +1.744 (+2,3%) | -12.604 (-100,0%) | -891 (-25,6%) | +1.566 (+33,6%) | +675 (+8,3%) | -4.771 (22,6% para 20,4%) | +4.784 (+2,9%) |
| ES | 13 para 22 | 11 | +41 (+3,8%) | +123 (+11,9%) | -173 (-100,0%) | -10 (-28,6%) | +41 (+69,5%) | +31 (+33,0%) | -23 (18,9% para 18,2%) | +22 (+0,9%) |
| ES | sem virada | 9.149 | +136.927 (+17,6%) | +59.443 (+5,1%) | -155.200 (-100,0%) | -9.230 (-23,2%) | +20.186 (+38,0%) | +10.956 (+11,8%) | -52.273 (21,3% para 19,4%) | +52.126 (+2,4%) |
| GO | 22 para 13 | 897 | +30.446 (+35,5%) | +11.221 (+11,7%) | -32.639 (-100,0%) | -591 (-18,1%) | -2.570 (-39,5%) | -3.161 (-32,3%) | -5.871 (23,6% para 21,6%) | +5.867 (+2,6%) |
| GO | 13 para 22 | 39 | +546 (+16,0%) | +909 (+28,0%) | -1.282 (-100,0%) | -21 (-20,6%) | -41 (-23,2%) | -62 (-22,2%) | -119 (23,6% para 22,5%) | +111 (+1,4%) |
| GO | sem virada | 14.750 | +365.683 (+33,2%) | +281.316 (+14,4%) | -553.241 (-100,0%) | -1.817 (-4,3%) | -22.226 (-24,3%) | -24.043 (-18,0%) | -69.908 (21,7% para 20,3%) | +69.715 (+1,9%) |
| MA | 22 para 13 | 504 | +10.542 (+18,4%) | -114 (-0,2%) | -9.079 (-100,0%) | -349 (-22,3%) | -758 (-29,8%) | -1.107 (-26,9%) | -265 (18,1% para 17,9%) | +242 (+0,2%) |
| MA | 13 para 22 | 9 | +17 (+1,9%) | +73 (+8,4%) | -102 (-100,0%) | 0 (0,0%) | -24 (-48,0%) | -24 (-38,7%) | +38 (19,6% para 21,1%) | -36 (-1,9%) |
| MA | sem virada | 17.580 | +231.371 (+9,2%) | -9.028 (-0,8%) | -196.262 (-100,0%) | -15.111 (-33,8%) | -43.748 (-43,5%) | -58.859 (-40,5%) | +32.733 (19,8% para 20,4%) | -32.778 (-0,8%) |
| MG | 22 para 13 | 5.570 | +163.326 (+28,1%) | +38.019 (+5,9%) | -124.883 (-100,0%) | -15.677 (-43,8%) | -13.113 (-27,3%) | -28.790 (-34,3%) | -47.591 (22,3% para 19,7%) | +47.672 (+3,3%) |
| MG | 13 para 22 | 93 | +845 (+9,7%) | +1.565 (+18,6%) | -1.601 (-100,0%) | -111 (-31,7%) | -136 (-23,5%) | -247 (-26,6%) | -561 (23,9% para 21,7%) | +562 (+2,9%) |
| MG | sem virada | 46.399 | +997.992 (+21,7%) | +424.654 (+8,3%) | -883.828 (-100,0%) | -88.373 (-38,1%) | -91.750 (-26,7%) | -180.123 (-31,3%) | -359.005 (22,9% para 20,4%) | +358.695 (+3,2%) |
| MS | 22 para 13 | 361 | +8.001 (+24,8%) | +1.070 (+3,0%) | -4.761 (-100,0%) | -598 (-42,9%) | -611 (-34,6%) | -1.209 (-38,2%) | -3.100 (26,2% para 23,2%) | +3.101 (+4,1%) |
| MS | 13 para 22 | 14 | +26 (+2,4%) | +144 (+13,6%) | -116 (-100,0%) | -3 (-13,0%) | -3 (-9,1%) | -6 (-10,7%) | -48 (27,1% para 25,6%) | +48 (+2,1%) |
| MS | sem virada | 6.731 | +104.091 (+21,5%) | +53.327 (+6,4%) | -95.271 (-100,0%) | -5.711 (-28,8%) | -6.345 (-22,8%) | -12.056 (-25,3%) | -50.085 (23,7% para 21,1%) | +50.091 (+3,4%) |
| MT | 22 para 13 | 252 | +5.580 (+21,0%) | +283 (+1,0%) | -4.095 (-100,0%) | -321 (-38,9%) | -508 (-36,9%) | -829 (-37,7%) | -935 (21,8% para 20,6%) | +939 (+1,5%) |
| MT | 13 para 22 | 11 | +21 (+1,8%) | +160 (+14,7%) | -125 (-100,0%) | -9 (-33,3%) | -21 (-39,6%) | -30 (-37,5%) | -27 (21,4% para 20,5%) | +26 (+1,1%) |
| MT | sem virada | 8.024 | +106.885 (+19,3%) | +52.075 (+4,1%) | -108.901 (-100,0%) | -4.995 (-25,1%) | -12.828 (-35,1%) | -17.823 (-31,6%) | -32.161 (22,2% para 21,0%) | +32.236 (+1,6%) |
| PA | 22 para 13 | 1.558 | +34.439 (+19,8%) | +1.721 (+0,9%) | -28.247 (-100,0%) | -2.151 (-37,3%) | -6.590 (-53,4%) | -8.741 (-48,2%) | +835 (18,9% para 19,1%) | -828 (-0,2%) |
| PA | 13 para 22 | 37 | -11 (-0,3%) | +345 (+9,6%) | -452 (-100,0%) | -15 (-20,3%) | -123 (-53,5%) | -138 (-45,4%) | +254 (18,6% para 21,2%) | -256 (-3,2%) |
| PA | sem virada | 19.232 | +228.784 (+10,2%) | +33.917 (+1,7%) | -243.462 (-100,0%) | -15.536 (-32,1%) | -79.550 (-58,3%) | -95.086 (-51,5%) | +75.508 (19,1% para 20,4%) | -75.847 (-1,6%) |
| PB | 22 para 13 | 780 | +22.652 (+24,8%) | +3.567 (+3,6%) | -15.613 (-100,0%) | -2.205 (-47,9%) | -3.181 (-37,6%) | -5.386 (-41,3%) | -5.249 (15,3% para 13,3%) | +5.220 (+2,4%) |
| PB | 13 para 22 | 3 | +35 (+9,3%) | +58 (+16,0%) | -67 (-100,0%) | -8 (-44,4%) | -5 (-20,8%) | -13 (-31,0%) | -12 (14,0% para 12,8%) | +13 (+1,5%) |
| PB | sem virada | 9.929 | +230.245 (+15,9%) | +30.208 (+4,1%) | -125.653 (-100,0%) | -24.141 (-50,6%) | -56.320 (-51,5%) | -80.461 (-51,2%) | -54.408 (17,6% para 15,7%) | +54.339 (+2,2%) |
| PE | 22 para 13 | 358 | +9.915 (+21,7%) | +2.092 (+4,3%) | -6.983 (-100,0%) | -852 (-44,7%) | -798 (-27,3%) | -1.650 (-34,2%) | -3.359 (17,1% para 14,4%) | +3.374 (+3,2%) |
| PE | 13 para 22 | 5 | +58 (+8,6%) | +100 (+15,3%) | -108 (-100,0%) | -4 (-16,7%) | -7 (-24,1%) | -11 (-20,8%) | -40 (16,6% para 14,4%) | +39 (+2,6%) |
| PE | sem virada | 21.055 | +553.569 (+15,8%) | +92.319 (+5,5%) | -302.050 (-100,0%) | -51.877 (-48,2%) | -79.969 (-40,5%) | -131.846 (-43,2%) | -212.229 (18,2% para 15,2%) | +211.992 (+3,7%) |
| PI | 22 para 13 | 47 | +888 (+17,8%) | +20 (+0,4%) | -787 (-100,0%) | -25 (-20,5%) | -55 (-22,2%) | -80 (-21,6%) | -36 (17,1% para 16,8%) | +41 (+0,4%) |
| PI | 13 para 22 | 1 | -2 (-3,1%) | +22 (+34,9%) | -8 (-100,0%) | -5 (-83,3%) | -6 (-60,0%) | -11 (-68,8%) | -1 (8,5% para 7,9%) | +1 (+0,7%) |
| PI | sem virada | 10.177 | +129.393 (+8,5%) | +8.789 (+1,7%) | -104.913 (-100,0%) | -12.162 (-43,1%) | -22.202 (-33,7%) | -34.364 (-36,5%) | +1.027 (17,2% para 17,2%) | -1.095 (-0,0%) |
| PR | 22 para 13 | 814 | +20.466 (+25,8%) | +4.465 (+5,1%) | -14.275 (-100,0%) | -1.900 (-42,6%) | -1.348 (-30,5%) | -3.248 (-36,6%) | -7.398 (23,0% para 20,0%) | +7.408 (+3,9%) |
| PR | 13 para 22 | 38 | +213 (+6,2%) | +571 (+17,5%) | -532 (-100,0%) | -56 (-40,0%) | -16 (-11,3%) | -72 (-25,5%) | -181 (23,1% para 21,3%) | +180 (+2,4%) |
| PR | sem virada | 26.290 | +491.228 (+24,9%) | +341.063 (+8,8%) | -570.762 (-100,0%) | -37.971 (-32,2%) | -13.264 (-10,3%) | -51.235 (-20,8%) | -210.332 (20,5% para 18,0%) | +210.294 (+3,2%) |
| RJ | 22 para 13 | 4.271 | +118.594 (+26,4%) | +11.749 (+2,3%) | -81.965 (-100,0%) | -12.047 (-47,9%) | -8.152 (-23,2%) | -20.199 (-33,5%) | -28.149 (24,6% para 22,7%) | +28.179 (+2,6%) |
| RJ | 13 para 22 | 25 | +250 (+10,7%) | +403 (+17,7%) | -428 (-100,0%) | -49 (-55,1%) | -1 (-0,8%) | -50 (-23,5%) | -178 (26,9% para 24,4%) | +175 (+3,3%) |
| RJ | sem virada | 33.379 | +753.528 (+23,2%) | +190.037 (+4,3%) | -627.829 (-100,0%) | -78.201 (-44,2%) | -48.242 (-19,1%) | -126.443 (-29,5%) | -189.442 (23,1% para 21,5%) | +189.293 (+2,2%) |
| RN | 22 para 13 | 400 | +11.421 (+22,4%) | +1.409 (+2,6%) | -7.705 (-100,0%) | -651 (-36,6%) | +78 (+2,5%) | -573 (-11,7%) | -4.507 (19,2% para 16,1%) | +4.552 (+3,8%) |
| RN | 13 para 22 | 0 | | | | | | | | |
| RN | sem virada | 7.715 | +164.212 (+13,8%) | +15.507 (+2,3%) | -105.800 (-100,0%) | -12.582 (-40,1%) | -4.079 (-6,5%) | -16.661 (-17,7%) | -57.261 (18,3% para 16,1%) | +57.258 (+2,8%) |
| RO | 22 para 13 | 34 | +542 (+17,1%) | -34 (-1,0%) | -631 (-100,0%) | -8 (-9,2%) | -30 (-25,0%) | -38 (-18,4%) | +159 (20,0% para 21,7%) | -161 (-2,1%) |
| RO | 13 para 22 | 2 | +4 (+3,6%) | +16 (+15,0%) | -13 (-100,0%) | +1 (n/d) | -1 (-50,0%) | 0 (0,0%) | -7 (16,4% para 13,9%) | +7 (+3,0%) |
| RO | sem virada | 4.662 | +43.233 (+17,5%) | +21.412 (+3,3%) | -63.826 (-100,0%) | -1.478 (-15,1%) | -1.778 (-13,7%) | -3.256 (-14,3%) | +2.472 (21,7% para 21,9%) | -2.437 (-0,2%) |
| RR | 22 para 13 | 14 | +97 (+8,5%) | -308 (-23,9%) | -93 (-100,0%) | -6 (-42,9%) | -14 (-40,0%) | -20 (-40,8%) | +318 (13,7% para 24,4%) | -324 (-12,6%) |
| RR | 13 para 22 | 0 | | | | | | | | |
| RR | sem virada | 1.505 | +8.988 (+12,3%) | -11.339 (-4,9%) | -19.724 (-100,0%) | -436 (-16,7%) | -1.340 (-29,4%) | -1.776 (-24,8%) | +23.876 (17,1% para 23,1%) | -23.851 (-7,2%) |
| RS | 22 para 13 | 1.807 | +49.606 (+27,4%) | +12.216 (+6,1%) | -37.341 (-100,0%) | -5.904 (-48,5%) | -3.334 (-32,3%) | -9.238 (-41,1%) | -15.251 (24,1% para 21,4%) | +15.243 (+3,5%) |
| RS | 13 para 22 | 62 | +417 (+8,2%) | +909 (+18,7%) | -965 (-100,0%) | -89 (-34,5%) | -18 (-8,7%) | -107 (-23,1%) | -259 (21,8% para 20,0%) | +254 (+2,2%) |
| RS | sem virada | 25.678 | +479.770 (+22,8%) | +287.470 (+8,5%) | -516.451 (-100,0%) | -52.883 (-38,9%) | -26.668 (-22,1%) | -79.551 (-31,0%) | -171.452 (21,2% para 19,0%) | +171.238 (+2,7%) |
| SC | 22 para 13 | 250 | +7.019 (+27,1%) | +1.473 (+5,1%) | -5.417 (-100,0%) | -473 (-39,7%) | -286 (-21,0%) | -759 (-29,7%) | -2.312 (22,5% para 19,7%) | +2.316 (+3,7%) |
| SC | 13 para 22 | 8 | +37 (+5,6%) | +110 (+17,5%) | -88 (-100,0%) | -14 (-46,7%) | -8 (-24,2%) | -22 (-34,9%) | -37 (17,6% para 15,4%) | +37 (+2,6%) |
| SC | sem virada | 17.068 | +284.090 (+25,8%) | +218.468 (+7,4%) | -368.388 (-100,0%) | -19.846 (-29,3%) | -2.533 (-3,3%) | -22.379 (-15,5%) | -111.759 (18,9% para 16,9%) | +111.791 (+2,4%) |
| SE | 22 para 13 | 59 | +1.305 (+21,7%) | +157 (+2,5%) | -1.107 (-100,0%) | -67 (-35,3%) | -62 (-19,1%) | -129 (-25,0%) | -206 (15,8% para 14,5%) | +226 (+1,6%) |
| SE | 13 para 22 | 0 | | | | | | | | |
| SE | sem virada | 5.864 | +131.717 (+15,5%) | +15.358 (+3,7%) | -89.288 (-100,0%) | -11.657 (-47,3%) | -18.779 (-37,8%) | -30.436 (-41,0%) | -27.413 (17,3% para 15,7%) | +27.351 (+1,9%) |
| SP | 22 para 13 | 9.208 | +290.687 (+30,9%) | +78.255 (+7,5%) | -232.794 (-100,0%) | -26.698 (-41,3%) | -23.264 (-25,1%) | -49.962 (-31,8%) | -86.150 (23,3% para 20,5%) | +86.186 (+3,6%) |
| SP | 13 para 22 | 101 | +1.449 (+13,6%) | +2.434 (+23,8%) | -2.772 (-100,0%) | -95 (-21,3%) | -59 (-7,7%) | -154 (-12,7%) | -967 (24,0% para 21,0%) | +957 (+3,8%) |
| SP | sem virada | 94.347 | +2.321.725 (+27,1%) | +1.136.466 (+9,6%) | -2.221.301 (-100,0%) | -216.402 (-38,1%) | -175.234 (-21,3%) | -391.636 (-28,2%) | -844.581 (22,5% para 19,7%) | +845.254 (+3,5%) |
| TO | 22 para 13 | 241 | +3.026 (+13,2%) | -1.251 (-5,0%) | -3.028 (-100,0%) | -28 (-5,7%) | +408 (+26,5%) | +380 (+18,7%) | +866 (18,9% para 20,2%) | -873 (-1,6%) |
| TO | 13 para 22 | 12 | -23 (-1,9%) | +89 (+7,9%) | -127 (-100,0%) | -2 (-9,1%) | +26 (+36,1%) | +24 (+25,5%) | +37 (19,7% para 20,9%) | -37 (-1,5%) |
| TO | sem virada | 4.131 | +35.950 (+9,5%) | -243 (-0,1%) | -53.990 (-100,0%) | -255 (-3,3%) | +9.015 (+36,4%) | +8.760 (+26,9%) | +9.548 (18,3% para 19,2%) | -9.523 (-1,0%) |

Observação sobre o Norte: é a única região em que o comparecimento caiu entre os turnos (-2,3% nas seções sem virada; AC -7,0%, com abstenção de 20,4% para 25,9%), e por isso a variação do comparecimento entra negativa na conta das fontes.

### Exterior (1.308 seções)

Fora das tabelas do script, que tratam só do Brasil. Pela consulta `viradas_grupos_ch.sql`: 54 viradas de 22 para 13, 10 de 13 para 22 e 1.244 sem virada. No total do exterior, Lula 157.385 para 200.154 (+42.769), Flávio 143.900 para 171.497 (+27.597), outros 29.718 para 0, brancos 5.816 para 4.675, nulos 4.945 para 5.117 e comparecimento 341.764 para 381.443 (+39.679; abstenção de 62,7% para 58,4% dos aptos). Duas seções do exterior (29564 0001/0091 e 30686 0001/0443) não têm voto no 2º turno (comparecimento zero) e ficam fora do pareamento; a segunda tinha 2 votos no 13 no 1º turno.

## Decomposição nacional do ganho de Lula

Com todas as seções: o ganho de Lula do 1º para o 2º turno foi de **10.376.694 votos**, e o de Flávio de **3.721.538**. Juntos, 14.098.232. A soma dos BUs reproduz o resultado oficial voto a voto no 2º turno (Lula 64.256.232, Flávio 59.826.041, brancos 1.430.496, nulos 2.723.305, comparecimento 128.236.074, iguais ao total do Brasil publicado às 23h22 de 25/10/2026 com 499.248 de 499.248 seções) e no 1º turno (Lula 53.879.538, Flávio 56.104.503, brancos 2.300.798, comparecimento 125.275.835).

| Item | 1º turno | 2º turno | Diferença |
|---|---:|---:|---:|
| Lula (13) | 53.879.538 | 64.256.232 | **+10.376.694** |
| Flávio (22) | 56.104.503 | 59.826.041 | **+3.721.538** |
| Outros candidatos (BUs) | 9.321.993 | 0 | -9.321.993 |
| Brancos | 2.300.798 | 1.430.496 | -870.302 |
| Nulos (BUs) | 3.669.003 | 2.723.305 | -945.698 |
| Brancos e nulos (BUs) | 5.969.801 | 4.153.801 | -1.816.000 |
| Comparecimento | 125.275.835 | 128.236.074 | **+2.960.239** |
| Eleitorado (oficial) | 158.745.502 | 158.745.502 | 0 |

Fontes do ganho de 13 + 22, somando até o último voto: 9.321.993 votos de outros candidatos no 1º turno + 1.816.000 de queda de brancos e nulos + 2.960.239 de aumento do comparecimento = 14.098.232.

Diferença de classificação com o total oficial do 1º turno: os BUs trazem 5.246 votos nominais no número 28, que o resultado oficial conta entre os nulos (`votos_nulos_total` de `ref_resultado_municipio_2026_t1` = 3.674.249 = 3.669.003 + 5.246). Por isso o oficial mostra outros 9.316.747 e brancos e nulos 5.975.047 (queda de 1.821.246). A soma das três fontes é a mesma: 9.316.747 + 1.821.246 + 2.960.239 = 14.098.232.

Por região (seções pareadas; a única diferença para o total acima é a seção 30686 0001/0443 do exterior, com 2 votos no 13 e comparecimento 2 só no 1º turno):

| Região | Seções | Ganho de Lula | Ganho de Flávio | Ganho 13 + 22 | Votos de outros no 1º turno | Queda de brancos e nulos | Aumento de comparecimento | Fontes somadas |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Norte | 43.769 | +474.024 | +14.110 | +488.134 | 632.284 | +93.733 | -237.883 | +488.134 |
| Nordeste | 140.828 | +2.955.848 | +397.763 | +3.353.611 | 1.812.341 | +714.509 | +826.761 | +3.353.611 |
| Centro-Oeste | 38.048 | +770.876 | +470.431 | +1.241.307 | 988.053 | +54.236 | +199.018 | +1.241.307 |
| Sudeste | 203.237 | +4.800.333 | +1.944.892 | +6.745.225 | 4.345.378 | +785.942 | +1.613.905 | +6.745.225 |
| Sul | 72.015 | +1.332.846 | +866.745 | +2.199.591 | 1.514.219 | +166.611 | +518.761 | +2.199.591 |
| Exterior | 1.308 | +42.769 | +27.597 | +70.366 | 29.718 | +969 | +39.679 | +70.366 |
| **Total (BUs pareados)** | 499.205 | +10.376.696 | +3.721.538 | +14.098.234 | 9.321.993 | +1.816.000 | +2.960.241 | +14.098.234 |

O que a conta por seção acrescenta à conta nacional:

- **A identidade vale em cada seção, não só no total.** Em todas as 499.205 seções pareadas, 13 + 22 + outros + brancos + nulos = comparecimento nos dois turnos (conferência `fecha_t1_falhas` e `fecha_t2_falhas` da consulta, zero em todos os níveis).
- **O ganho de Lula passou dos votos de outros do 1º turno em 275.257 seções do Brasil** (55% delas), somando 2.568.284 votos acima desses outros. Nessas seções a diferença vem da queda de brancos e nulos, do aumento do comparecimento ou de eleitores que mudaram de lado.
- **A parte que nenhuma reserva líquida da seção cobre é pequena.** A troca mínima a favor do 13 (ganho do 13 menos outros, menos queda de brancos e nulos, menos aumento do comparecimento) é positiva em 44.875 seções e soma 147.283 votos, 1,4% do ganho de Lula. A favor do 22, é positiva em 663 seções e soma 1.636 votos. Isso é conta líquida: não identifica eleitores, só diz que naquelas seções o saldo exige ao menos esse número de eleitores trocando diretamente de candidato (ou ausentes de um turno votando no outro).
- **Com rotatividade total aceita (troca estrita), sobram 20 votos a favor do 13 em 10 seções e 24 a favor do 22 em uma seção** (Santo Antônio de Lisboa, PI, 0028/0099).
- **Flávio perdeu votos em relação ao 1º turno em 82.155 seções**, e Lula em 9.575.

## O que mudou em relação às execuções parciais

| Item | 145.489 seções (N/NE, PA 79%, SP 1%) | 248.578 seções (N/NE e 61 mil de SP, com exterior) | País inteiro (497.897 + 1.308 do exterior) |
|---|---:|---:|---:|
| Viradas 22 para 13 | 5.876 | 11.891 | 31.341 (31.395 com o exterior) |
| Viradas 13 para 22 | 116 | 179 | 555 (565 com o exterior) |
| Sem virada | 139.497 | 236.508 | 466.001 (467.245 com o exterior) |
| Observado ÷ esperado, 22 para 13 | 1,02 | n/d | 0,96 |
| Lula nas seções 22 para 13 | n/d | +318.557 | +879.247 |
| Flávio nas seções 22 para 13 | n/d | +46.558 | +169.118 |
| Outros nas seções 22 para 13 | n/d | -248.119 | -689.702 |
| Brancos e nulos nas seções 22 para 13 | n/d | -56.330 | -144.805 |
| Comparecimento nas seções 22 para 13 | n/d | +60.666 | +213.858 |
| Abstenção nas seções 22 para 13 | n/d | 21,0% para 19,5% | 22,2% para 20,1% |
| Atípicos por 10 mil seções | 28,9 | n/d | 19,4 |

A entrada do Sudeste, do Sul e do Centro-Oeste reduziu a taxa de atípicos (essas regiões têm 11,8 a 20,3 por 10 mil, contra 26,1 no Nordeste e 34,3 no Norte) e baixou a razão observado ÷ esperado das viradas de 1,02 para 0,96. Os destaques das execuções parciais continuam na lista (CE, com Caucaia e São Gonçalo do Amarante; MA; Santo Antônio de Lisboa, PI, 0028/0099; Santa Rosa do Purus, AC, 0003/0095; Barcelos, AM, 0018/0037), com os mesmos números, porque essas UFs já estavam completas.

## Fonte e método

### Dados

- **2026, 2º turno:** banco ClickHouse do servidor de processamento (`docs/banco-clickhouse.md`), exportado por `viradas_t2_ch.sql` em 26/10/2026, 09h27: última versão de BU de cada seção (`v_bu_ultima`) e votos de Presidente dessa versão (`bu_votos`). São 499.207 seções com BU, todas decodificadas; 497.897 no Brasil (o exterior fica de fora do script) e todas pareadas com o 1º turno. Horário de encerramento convertido para Brasília pelo mesmo critério de `analisar_encerramento_t2.py` (fuso por UF e os 12 municípios de `FUSO_MUNICIPIO`). Número interno da urna e código de carga vêm do próprio BU.
- **2026, 1º turno:** `data/parquet/2026/secoes_2026.parquet` (seções com status `ok`) e `votos_presidente_2026.parquet` (cópias idênticas, por SHA-256, às do servidor). Votos nominais em 13 e 22; "outros" = demais votos nominais (inclui os 5.246 do número 28); brancos e nulos do cargo Presidente.
- **2022:** `data/parquet/secoes.parquet` (turnos 1 e 2) e `votos_t1_a.parquet`, `votos_t1_b.parquet`, `votos_t2.parquet`, cargo Presidente (código 1, eleições 544 e 545). 470.808 seções têm BU nos dois turnos. Os nomes dos municípios de 2022 vêm do código TSE, o mesmo de 2026. Em 2022 não há número interno nem código de carga no Parquet; fica só o modelo da urna.

Cobertura: em todas as 27 UFs, as seções do 2º turno pareadas são 100% das seções do 1º turno com BU. Com isso, "UFs comparáveis" das versões anteriores passa a ser o Brasil inteiro e deixa de aparecer nas tabelas.

### Definições (iguais em 2026 e 2022)

- **Líder** de cada turno: 13 ou 22, o que tiver mais votos nominais na seção; empate não tem líder.
- **Virada:** líder do 1º turno diferente do líder do 2º, sem empate em nenhum dos dois. Sentidos 22 para 13 e 13 para 22. A taxa de virada de um sentido é a fração das seções lideradas por aquele candidato no 1º turno que viraram. Na tabela por grupo, "sem virada" inclui as seções com empate em algum turno.
- **Margem do 1º turno:** \|votos do 13 menos votos do 22\| no 1º turno, em votos.
- **Fatia do 13:** 13 ÷ (13 + 22) em cada turno; variação = fatia no 2º menos fatia no 1º (em pontos).
- **Troca mínima** de um candidato X: o mínimo de eleitores do adversário que precisariam ter passado para X se os votos novos de X só pudessem vir de três fontes: os votos de outros candidatos no 1º turno, a queda de brancos e nulos (se houve) e o aumento de comparecimento (se houve). Fórmula: max(0, ganho de X - (outros do 1º + max(0, BN do 1º - BN do 2º) + max(0, comparecimento do 2º - comparecimento do 1º))). Nas viradas, a troca mínima é a do vencedor do 2º turno.
- **Troca estrita:** o mesmo cálculo, mas aceitando qualquer rotatividade: todos os brancos e nulos do 1º turno e todos os ausentes do 1º turno (até o comparecimento do 2º) poderiam ter votado em X. É o mínimo logicamente obrigatório de eleitores que mudaram diretamente de um candidato para o outro.

A troca mínima é uma conta líquida. Ela não prova que alguém mudou de voto: um eleitor do 13 pode ter faltado no 2º turno e um ausente do 1º turno pode ter votado no 22, e o saldo aparece como "troca" sem que ninguém tenha mudado. A troca estrita elimina essa ambiguidade, e por isso é muito mais rara.

### Modelo de esperado

Regressão logística ajustada nas 468.682 seções de 2022 com líder no 1º turno. A variável resposta é "virou" e as explicativas são:

- a margem do 1º turno como fração dos votos 13 + 22;
- o movimento do município entre turnos a favor do 2º colocado da seção, calculado sem a própria seção (município com menos de 100 votos nas demais seções usa a UF);
- o excesso desse movimento sobre metade da margem, sozinho e multiplicado pela raiz do número de votos (quanto maior a seção, menos ruído);
- a reserva do 1º turno ((outros + brancos + nulos) ÷ comparecimento);
- o logaritmo do número de votos 13 + 22.

Coeficientes (2022): intercepto -1,187; excesso × raiz(n) +7,315; excesso -19,515; margem × raiz(n) +0,096; reserva -1,244; log(n) +0,237. O modelo é aplicado a 2026 com o movimento observado em 2026 em cada município: a pergunta é se, dado o movimento geral, a quantidade de viradas seção a seção é a normal. O esperado de um grupo é a soma das probabilidades; o desvio informado é o da soma de eventos independentes.

Calibração por decil de probabilidade (observado contra esperado). Em 2022: 8º decil 87 contra 198; 9º decil 1.704 contra 1.706; 10º decil 19.076 contra 18.945. Em 2026: 8º decil 216 contra 344; 9º decil 3.234 contra 3.205; 10º decil 28.430 contra 29.805. O modelo exagera um pouco as probabilidades intermediárias e, em 2026, também as mais altas (5% no último decil).

Também há uma tabela por faixas de margem (0, 1-2, 3-5, 6-10, 11-20, 21-40, 41-80, mais de 80 votos) e de reserva (até 5%, 5-10%, 10-15%, 15-20%, mais de 20%), em `faixas.parquet`, e o esperado correspondente (taxa de 2022 de cada faixa aplicada a 2026). Esse esperado ignora o sentido do movimento regional e por isso não serve para comparar sentidos: em 2026 ele dá 11.517 viradas de 22 para 13 e 10.065 de 13 para 22, contra 31.341 e 555 observadas, simplesmente porque em 2022 o movimento foi para o outro lado. Fica como registro de que a margem sozinha não explica as viradas; é preciso considerar o movimento do município.

### Critérios de atípico (mesma régua nos dois anos)

1. **Troca:** a maior troca mínima entre os dois candidatos é de pelo menos 10 votos e de pelo menos 5% do comparecimento do 2º turno. A régua é simétrica: vale para qualquer candidato, não só para o vencedor. O esperado vem da taxa de 2022 em cada combinação de faixa de movimento do município (0-0,5, 0,5-1, 1-2, 2-3, 3-4, 4-6, mais de 6 pontos) e de faixa de reserva.
2. **Estrita:** troca estrita maior que zero para qualquer candidato.
3. **Desvio:** \|z\| > 4, com z = (variação da fatia do 13 menos a mediana do município) ÷ (1,4826 × desvio absoluto mediano do município). Município com menos de 30 seções usa a UF. Só seções com pelo menos 20 votos em 13 + 22 nos dois turnos.

## Resultados por UF

### Viradas: observado contra esperado (2026)

| UF | Seções | 22 liderou no 1º | Viradas 22 para 13 | Taxa | Esperado | Obs. ÷ esp. | 13 liderou no 1º | Viradas 13 para 22 | Taxa | Esperado | Obs. ÷ esp. |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| AC | 2.270 | 2.169 | 34 | 1,6% | 32,3 | 1,05 | 99 | 4 | 4,04% | 2,6 | 1,54 |
| AL | 7.101 | 2.538 | 721 | 28,4% | 800,4 | 0,90 | 4.537 | 2 | 0,04% | 5,6 | 0,36 |
| AM | 8.157 | 4.500 | 560 | 12,4% | 599,6 | 0,93 | 3.621 | 17 | 0,47% | 16,0 | 1,06 |
| AP | 1.914 | 1.121 | 340 | 30,3% | 346,3 | 0,98 | 773 | 6 | 0,78% | 7,2 | 0,83 |
| BA | 35.476 | 2.047 | 534 | 26,1% | 480,9 | 1,11 | 33.376 | 27 | 0,08% | 63,2 | 0,43 |
| CE | 23.765 | 1.015 | 487 | 48,0% | 433,4 | 1,12 | 22.710 | 4 | 0,02% | 27,6 | 0,14 |
| DF | 6.969 | 6.076 | 556 | 9,2% | 767,0 | 0,72 | 856 | 24 | 2,80% | 8,6 | 2,79 |
| ES | 9.844 | 7.937 | 684 | 8,6% | 761,6 | 0,90 | 1.852 | 11 | 0,59% | 26,6 | 0,41 |
| GO | 15.686 | 14.297 | 897 | 6,3% | 1.082,5 | 0,83 | 1.326 | 39 | 2,94% | 22,4 | 1,74 |
| MA | 18.093 | 1.907 | 504 | 26,4% | 455,5 | 1,11 | 16.127 | 9 | 0,06% | 28,6 | 0,32 |
| MG | 52.062 | 31.543 | 5.570 | 17,7% | 5.761,0 | 0,97 | 20.119 | 93 | 0,46% | 148,7 | 0,62 |
| MS | 7.106 | 6.411 | 361 | 5,6% | 412,7 | 0,88 | 671 | 14 | 2,09% | 9,4 | 1,49 |
| MT | 8.287 | 7.657 | 252 | 3,3% | 271,7 | 0,93 | 619 | 11 | 1,78% | 6,0 | 1,83 |
| PA | 20.827 | 9.140 | 1.558 | 17,0% | 1.482,2 | 1,05 | 11.561 | 37 | 0,32% | 65,3 | 0,57 |
| PB | 10.712 | 1.527 | 780 | 51,1% | 749,0 | 1,04 | 9.126 | 3 | 0,03% | 9,5 | 0,32 |
| PE | 21.418 | 875 | 358 | 40,9% | 349,7 | 1,02 | 20.495 | 5 | 0,02% | 18,2 | 0,28 |
| PI | 10.225 | 174 | 47 | 27,0% | 47,1 | 1,00 | 10.050 | 1 | 0,01% | 7,4 | 0,14 |
| PR | 27.142 | 25.118 | 814 | 3,2% | 998,5 | 0,81 | 1.967 | 38 | 1,93% | 37,9 | 1,00 |
| RJ | 37.675 | 29.715 | 4.271 | 14,4% | 4.603,6 | 0,93 | 7.768 | 25 | 0,32% | 30,5 | 0,82 |
| RN | 8.115 | 971 | 400 | 41,2% | 401,1 | 1,00 | 7.110 | 0 | 0,00% | 8,3 | 0,00 |
| RO | 4.698 | 4.618 | 34 | 0,7% | 54,7 | 0,62 | 76 | 2 | 2,63% | 1,0 | 2,00 |
| RR | 1.519 | 1.431 | 14 | 1,0% | 11,5 | 1,22 | 88 | 0 | 0,00% | 0,2 | 0,00 |
| RS | 27.547 | 21.032 | 1.807 | 8,6% | 1.826,5 | 0,99 | 6.369 | 62 | 0,97% | 67,0 | 0,93 |
| SC | 17.326 | 16.658 | 250 | 1,5% | 280,2 | 0,89 | 647 | 8 | 1,24% | 7,7 | 1,04 |
| SE | 5.923 | 122 | 59 | 48,4% | 60,9 | 0,97 | 5.793 | 0 | 0,00% | 4,1 | 0,00 |
| SP | 103.656 | 75.059 | 9.208 | 12,3% | 9.265,1 | 0,99 | 28.015 | 101 | 0,36% | 145,9 | 0,69 |
| TO | 4.384 | 2.564 | 241 | 9,4% | 269,4 | 0,90 | 1.785 | 12 | 0,67% | 22,6 | 0,53 |
| Norte | 43.769 | 25.543 | 2.781 | 10,9% | 2.795,9 | 0,99 | 18.003 | 78 | 0,43% | 114,9 | 0,68 |
| Nordeste | 140.828 | 11.176 | 3.890 | 34,8% | 3.778,0 | 1,03 | 129.324 | 51 | 0,04% | 172,3 | 0,30 |
| Centro-Oeste | 38.048 | 34.441 | 2.066 | 6,0% | 2.534,0 | 0,81 | 3.472 | 88 | 2,54% | 46,3 | 1,90 |
| Sudeste | 203.237 | 144.254 | 19.733 | 13,7% | 20.391,3 | 0,97 | 57.754 | 230 | 0,40% | 351,6 | 0,65 |
| Sul | 72.015 | 62.808 | 2.871 | 4,6% | 3.105,2 | 0,93 | 8.983 | 108 | 1,20% | 112,6 | 0,96 |
| Brasil | 497.897 | 278.222 | 31.341 | 11,3% | 32.604,4 | 0,96 | 217.536 | 555 | 0,26% | 797,7 | 0,70 |

Taxas altas como as de CE (48%), PB (51%), SE (48%), RN (41%) e PE (41%) não significam que metade do estado virou: nessas UFs o 22 liderou em poucas seções no 1º turno (1.015 no CE, 122 em SE), quase sempre por margem estreita, e o 13 cresceu cerca de 2 pontos no 2º turno. Razões abaixo de 1 no sentido 22 para 13 (DF 0,72, RO 0,62, PR 0,81, GO 0,83) e acima de 1 no sentido 13 para 22 no Centro-Oeste mostram que ali as seções resistiram ao movimento mais do que o modelo de 2022 previa; nenhuma UF tem excesso de viradas no sentido do movimento acima de 1,22.

### Referência de 2022, mesmas métricas

| Grupo | Seções | Viradas 22 para 13 | Taxa | Esperado | Obs. ÷ esp. | Viradas 13 para 22 | Taxa | Esperado | Obs. ÷ esp. |
|---|---|---|---|---|---|---|---|---|---|
| Norte | 38.966 | 168 | 0,84% | 171,0 | 0,98 | 1.497 | 7,96% | 1.485,0 | 1,01 |
| Nordeste | 132.401 | 218 | 3,01% | 163,9 | 1,33 | 1.725 | 1,38% | 2.389,9 | 0,72 |
| Centro-Oeste | 35.928 | 136 | 0,47% | 261,5 | 0,52 | 1.782 | 25,3% | 1.457,6 | 1,22 |
| Sudeste | 194.357 | 900 | 0,77% | 1.210,4 | 0,74 | 10.718 | 14,2% | 10.222,3 | 1,05 |
| Sul | 69.156 | 69 | 0,13% | 169,6 | 0,41 | 3.661 | 21,0% | 3.342,9 | 1,10 |
| Brasil | 470.808 | 1.491 | 0,66% | 1.976,3 | 0,75 | 19.383 | 7,95% | 18.897,7 | 1,03 |

Por UF em 2022, a razão observado ÷ esperado foi de 0,29 (PR) a 4,02 (CE) no sentido 22 para 13 e de 0,44 (CE) a 1,38 (DF) no sentido 13 para 22, excluída RR (menos de 2 viradas esperadas). A faixa de 2026 no sentido principal (0,62 a 1,22) está dentro do que aconteceu em 2022.

### Margem do 1º turno nas seções que viraram

| Grupo | Viradas | Margem média | Mediana | p90 | Máximo | Até 10 votos |
|---|---|---|---|---|---|---|
| 2026 Norte | 2.859 | 10,6 | 9 | 21 | 134 | 1.640 (57%) |
| 2026 Nordeste | 3.941 | 10,2 | 8 | 22 | 48 | 2.386 (61%) |
| 2026 Centro-Oeste | 2.154 | 11,0 | 10 | 22 | 48 | 1.170 (54%) |
| 2026 Sudeste | 19.963 | 11,4 | 10 | 23 | 59 | 10.782 (54%) |
| 2026 Sul | 2.979 | 9,9 | 8 | 20 | 42 | 1.825 (61%) |
| 2026 Brasil | 31.896 | 11,0 | 9 | 22 | 134 | 17.803 (56%) |
| 2022 Norte | 1.665 | 8,4 | 7 | 17 | 202 | 1.169 (70%) |
| 2022 Nordeste | 1.943 | 8,1 | 6 | 17 | 38 | 1.372 (71%) |
| 2022 Centro-Oeste | 1.918 | 8,2 | 7 | 17 | 38 | 1.351 (70%) |
| 2022 Sudeste | 11.618 | 8,4 | 7 | 18 | 46 | 8.033 (69%) |
| 2022 Sul | 3.730 | 9,8 | 8 | 20 | 45 | 2.289 (61%) |
| 2022 Brasil | 20.874 | 8,6 | 7 | 18 | 202 | 14.214 (68%) |

A margem das viradas de 2026 é um pouco maior que a de 2022 porque o movimento médio foi maior em 2026 (+2,9 pontos contra -1,6). A maior margem virada em 2026, 134 votos, é a de Barcelos (AM) 0018/0037, listada entre os atípicos.

### Variação da fatia do 13 entre turnos (pontos)

| Grupo | Média | Desvio padrão | p1 | p5 | Mediana | p95 | p99 |
|---|---|---|---|---|---|---|---|
| 2026 Norte | +2,56 | 2,46 | -3,20 | -1,29 | +2,53 | +6,49 | +8,58 |
| 2026 Nordeste | +1,99 | 2,19 | -3,12 | -1,50 | +1,97 | +5,60 | +7,32 |
| 2026 Centro-Oeste | +3,25 | 2,28 | -2,17 | -0,39 | +3,22 | +7,02 | +8,74 |
| 2026 Sudeste | +3,51 | 2,35 | -2,09 | -0,30 | +3,50 | +7,35 | +9,12 |
| 2026 Sul | +3,03 | 2,16 | -2,18 | -0,42 | +3,01 | +6,55 | +8,26 |
| 2026 Brasil | +2,91 | 2,37 | -2,63 | -0,89 | +2,88 | +6,80 | +8,62 |
| 2022 Norte | -1,62 | 2,40 | -7,65 | -5,50 | -1,54 | +1,96 | +3,76 |
| 2022 Nordeste | -1,67 | 1,92 | -6,50 | -4,82 | -1,62 | +1,31 | +2,71 |
| 2022 Centro-Oeste | -1,48 | 2,22 | -7,03 | -5,20 | -1,41 | +2,02 | +3,50 |
| 2022 Sudeste | -1,51 | 2,29 | -6,95 | -5,26 | -1,49 | +2,17 | +3,74 |
| 2022 Sul | -2,04 | 2,30 | -7,99 | -5,90 | -1,93 | +1,48 | +2,90 |
| 2022 Brasil | -1,64 | 2,20 | -7,09 | -5,26 | -1,59 | +1,84 | +3,40 |

A distribuição de 2026 é, em forma, um espelho da de 2022: centro deslocado para o lado do 13 e largura praticamente igual em todas as regiões (desvio padrão de 2,2 a 2,5 pontos nos dois anos).

### Troca mínima

| Grupo | Viradas com troca zero | p90 nas viradas | p99 nas viradas | Máximo nas viradas | Seções com troca alta | Esperado | Troca estrita > 0 |
|---|---|---|---|---|---|---|---|
| 2026 Norte | 82% | 3 | 10 | 55 | 49 | 76,9 | 3 |
| 2026 Nordeste | 79% | 3 | 11 | 21 | 193 | 132,9 | 5 |
| 2026 Centro-Oeste | 90% | 0 | 6 | 13 | 15 | 64,7 | 0 |
| 2026 Sudeste | 89% | 1 | 7 | 19 | 69 | 286,0 | 3 |
| 2026 Sul | 90% | 0 | 6 | 12 | 4 | 99,0 | 0 |
| 2026 Brasil | 87% | 1 | 8 | 55 | 330 | 659,4 | 11 |
| 2022 Norte | 88% | 1 | 8 | 129 | 31 | 26,9 | 1 |
| 2022 Nordeste | 92% | 0 | 6 | 29 | 42 | 60,2 | 7 |
| 2022 Centro-Oeste | 81% | 3 | 9 | 13 | 21 | 16,3 | 0 |
| 2022 Sudeste | 90% | 0 | 7 | 17 | 28 | 40,9 | 2 |
| 2022 Sul | 74% | 4 | 11 | 20 | 76 | 53,8 | 1 |
| 2022 Brasil | 86% | 2 | 8 | 129 | 198 | 198,0 | 11 |

"Troca alta" é o critério 1 (pelo menos 10 votos e 5% do comparecimento), em qualquer seção, virada ou não. O esperado de 2026 é a taxa de 2022 por faixa de movimento do município e de reserva. Em 2022 a taxa cresce muito com o movimento: 1,6 por 10 mil seções com movimento de 1-2 pontos, 20,7 com 3-4 pontos e 83 com 4-6 pontos. Em 2026, com o país inteiro, ela cresce bem menos: 7,1, 5,3 e 10,5 nas mesmas faixas. Como em 2026 a maior parte das seções está nas faixas de 2-6 pontos, o esperado pela régua de 2022 (659) fica bem acima do observado (330).

Por UF, troca alta observada contra esperada em 2026: AC 5 / 3,5; AL 22 / 20,8; AM 17 / 16,0; AP 0 / 6,7; BA 17 / 17,9; CE 52 / 17,6; DF 0 / 7,9; ES 0 / 11,3; GO 1 / 7,5; MA 35 / 27,5; MG 11 / 56,5; MS 4 / 24,2; MT 10 / 25,0; PA 22 / 29,2; PB 11 / 9,1; PE 8 / 12,6; PI 10 / 7,8; PR 1 / 39,9; RJ 45 / 114,2; RN 32 / 16,9; RO 0 / 6,8; RR 2 / 8,3; RS 3 / 30,2; SC 0 / 28,8; SE 6 / 2,8; SP 13 / 103,9; TO 3 / 6,4. No CE, 18 das 52 estão em Caucaia (9) e São Gonçalo do Amarante (9), dois municípios vizinhos em que o 13 cresceu mais que o estado (de 59,9% para 63,1% e de 58,7% para 62,1%, contra +2,0 pontos no CE). No RN, 9 das 32 estão em Rafael Godeiro (ver acima). No RJ, 9 das 45 estão em Campos dos Goytacazes.

### Atípicos: 2026 contra 2022

| Grupo | Seções | Troca | Estrita | Desvio | Total (algum critério) | Por 10 mil |
|---|---|---|---|---|---|---|
| 2026 Norte | 43.769 | 49 | 3 | 113 | 150 | 34,3 |
| 2026 Nordeste | 140.828 | 193 | 5 | 205 | 367 | 26,1 |
| 2026 Centro-Oeste | 38.048 | 15 | 0 | 54 | 66 | 17,4 |
| 2026 Sudeste | 203.237 | 69 | 3 | 175 | 239 | 11,8 |
| 2026 Sul | 72.015 | 4 | 0 | 143 | 146 | 20,3 |
| 2026 Brasil | 497.897 | 330 | 11 | 690 | 968 | 19,4 |
| 2022 Norte | 38.966 | 31 | 1 | 97 | 112 | 28,7 |
| 2022 Nordeste | 132.401 | 42 | 7 | 219 | 239 | 18,1 |
| 2022 Centro-Oeste | 35.928 | 21 | 0 | 48 | 64 | 17,8 |
| 2022 Sudeste | 194.357 | 28 | 2 | 159 | 176 | 9,1 |
| 2022 Sul | 69.156 | 76 | 1 | 130 | 187 | 27,0 |
| 2022 Brasil | 470.808 | 198 | 11 | 653 | 778 | 16,5 |

Por UF, atípicos por 10 mil seções em 2026 (2022 entre parênteses): AC 48,5 (56,5); AL 53,5 (9,1); AM 44,1 (28,2); AP 15,7 (17,2); BA 14,9 (19,3); CE 31,6 (21,1); DF 4,3 (8,9); ES 17,3 (5,4); GO 15,9 (16,4); MA 42,6 (26,8); MG 14,6 (18,2); MS 14,1 (17,4); MT 33,8 (28,8); PA 35,5 (29,6); PB 18,7 (4,2); PE 9,8 (8,3); PI 31,3 (33,5); PR 18,1 (17,5); RJ 14,9 (5,9); RN 50,5 (20,9); RO 19,2 (19,1); RR 39,5 (39,4); RS 22,5 (37,9); SC 20,2 (24,0); SE 16,9 (14,6); SP 8,7 (5,9); TO 25,1 (22,7).

Municípios com mais atípicos em 2026: Belo Monte (AL) 14, São Paulo (SP) 13 (a capital, a maior cidade do país), Santo Antônio de Lisboa (PI) 13, Caucaia (CE) 10, Campos dos Goytacazes (RJ) 9, São Gonçalo do Amarante (CE) 9 e Rafael Godeiro (RN) 9.

AL chama atenção (38 atípicos, 53,5 por 10 mil, contra 9,1 em 2022): 14 deles estão em Belo Monte, onde todas as 16 seções se moveram para o 22 (a fatia do 13 no município caiu de 70,3% para 61,6%) enquanto o estado se moveu para o 13. Com menos de 30 seções, o município é comparado com a UF, e o movimento do município inteiro aparece como desvio de cada seção. É um efeito local, não de seção isolada. O mesmo vale para Santo Antônio de Lisboa (PI, 13 de 24 seções atípicas; todas as 24 se moveram para o 22), onde a seção 0028/0099 já tinha se movido para o 22 em 2022 (troca 25, z -5,4), e para Rafael Godeiro (RN, 9 de 11), no sentido do 13.

### Urna, carga, contingência e horário dos atípicos de 2026

- Mesmo número interno de urna nos dois turnos: 960 de 968. Mesmo código de carga: 959 de 968.
- Urna diferente: 8 (lista abaixo).
- Urna de reserva (`reservaSecao`) no 2º turno: 12 de 968. Nenhuma de contingência.
- Encerramento: 18 dos 968 atípicos encerraram depois das 17h10 de Brasília no 2º turno. Entre todas as seções, as 13.356 que encerraram depois das 17h10 tiveram 6,9% de viradas e 0,13% de atípicos; as demais, 6,4% e 0,20%.

## Seções para conferência

A lista completa (968 seções de 2026 e 778 de 2022, com todas as colunas) está em `data/parquet/2026/t2/viradas/atipicos_2026.csv` e `atipicos_2022.csv`. Abaixo, as 30 de 2026 com maior troca estrita, troca mínima e desvio, as 40 primeiras viradas atípicas pela mesma ordem (são 157 no total: 128 de 22 para 13 e 29 de 13 para 22) e as de urna trocada. A conferência natural é contra o boletim de urna impresso da seção (QR Code) nos dois turnos e contra a ata da mesa receptora.

Colunas: "Outros / BN 1º" = votos em outros candidatos e brancos + nulos no 1º turno; "Troca mín." = a maior troca mínima entre os dois candidatos e a favor de quem; "z" = desvio da variação da fatia do 13 em relação ao município (ou à UF); encerramento no horário local da urna.

Casos que merecem destaque:

- **Santo Antônio de Lisboa (PI) 0028/0099:** 214 x 56 no 1º turno e 146 x 122 no 2º, com a mesma urna e a mesma carga. Mesmo aceitando rotatividade total, pelo menos 24 eleitores teriam de ter passado do 13 para o 22. É a única seção do país com troca estrita acima de 5. Não virou (o 13 continuou à frente), e a mesma seção já tinha se movido para o 22 em 2022 (191 x 82 para 161 x 115).
- **Santa Rosa do Purus (AC) 0003/0095:** 102 x 105 para 174 x 47 (troca mínima 55, a maior do país). Em 2022 a mesma seção teve a virada inversa, de tamanho igual: 130 x 93 para 37 x 149 (troca 55). A oscilação forte entre turnos nessa seção não é nova.
- **Manoel Urbano (AC) 0003/0160:** virada de 13 para 22, 112 x 55 para 48 x 104, contra o movimento do estado. Em 2022 a seção 0003/0100 do mesmo município teve o maior caso daquele ano (4 x 206 para 160 x 45, troca 129).
- **Barcelos (AM) 0018/0037:** 37 x 171 para 84 x 71, com queda de comparecimento de 231 para 190 e brancos + nulos de 15 para 35. É a maior margem virada de 2026 (134 votos). A troca estrita é zero: a queda de comparecimento e a rotatividade explicam a virada sem exigir troca direta.
- **São Paulo de Olivença (AM) 0022/0070:** 154 x 20 para 180 x 1 (troca estrita 5).
- **São Paulo (SP) 0325/0685:** 42 x 11 para 48 x 4 em uma seção de 56 aptos (troca estrita 3). É o único caso de troca estrita no Sudeste acima de 2 votos.
- **Rafael Godeiro (RN), zona 0037:** 9 das 11 seções do município são atípicas, todas a favor do 13 (troca mínima de 21 a 26 nas maiores); o município inteiro se moveu cerca de 10 pontos, contra 2,5 no RN.

### As 30 seções de 2026 com maior troca estrita, troca mínima e desvio

| UF | Município | Zona | Seção | Virada | Critério | 1º turno 13 x 22 | Outros / BN 1º | 2º turno 13 x 22 | BN 2º | Comparec. 1º / 2º | Aptos 1º / 2º | Troca mín. (a favor de) | Troca estrita | z | Mesma urna | Mesma carga | Urna 1º / 2º | Encerramento local 1º / 2º |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PI | SANTO ANTÔNIO DE LISBOA | 0028 | 0099 | não | estrita+troca+desvio | 214 x 56 | 5 / 12 | 146 x 122 | 5 | 287 / 273 | 312 / 312 | 54 (22) | 24 | -12,5 | sim | sim | seção / seção | 17:54 / 17:00 |
| AM | SÃO PAULO DE OLIVENÇA | 0022 | 0070 | não | estrita+troca+desvio | 154 x 20 | 6 / 3 | 180 x 1 | 3 | 183 / 184 | 195 / 195 | 19 (13) | 5 | +5,2 | sim | sim | seção / seção | 15:05 / 15:06 |
| SP | SÃO PAULO | 0325 | 0685 | não | estrita+desvio | 42 x 11 | 0 / 2 | 48 x 4 | 1 | 55 / 53 | 56 / 56 | 5 (13) | 3 | +4,5 | sim | sim | seção / seção | 17:01 / 17:02 |
| AL | SÃO SEBASTIÃO | 0049 | 0135 | não | estrita+desvio | 25 x 11 | 0 / 2 | 31 x 7 | 0 | 38 / 38 | 39 / 39 | 4 (13) | 3 | +5,1 | sim | sim | seção / seção | 17:04 / 17:01 |
| BA | VITÓRIA DA CONQUISTA | 0041 | 0400 | não | estrita | 36 x 17 | 0 / 0 | 38 x 14 | 1 | 53 / 53 | 53 / 53 | 2 (13) | 2 | +1,4 | sim | sim | seção / seção | 17:01 / 17:00 |
| MG | JAÍBA | 0063 | 0194 | não | estrita | 78 x 11 | 3 / 8 | 94 x 9 | 0 | 100 / 103 | 103 / 103 | 2 (13) | 2 | +0,2 | sim | sim | seção / seção | 17:01 / 17:01 |
| PA | CASTANHAL | 0004 | 0580 | não | estrita | 35 x 81 | 4 / 2 | 47 x 73 | 1 | 122 / 121 | 127 / 127 | 7 (13) | 1 | +3,4 | sim | sim | seção / seção | 17:01 / 17:00 |
| MA | BOM JARDIM | 0078 | 0296 | não | estrita | 59 x 7 | 1 / 2 | 65 x 3 | 2 | 69 / 70 | 71 / 71 | 4 (13) | 1 | +1,8 | sim | sim | seção / seção | 17:02 / 17:01 |
| PE | CHÃ DE ALEGRIA | 0021 | 0149 | não | estrita | 39 x 13 | 1 / 2 | 44 x 10 | 1 | 55 / 55 | 56 / 56 | 3 (13) | 1 | +2,8 | sim | sim | seção / seção | 17:03 / 17:01 |
| PA | ALENQUER | 0021 | 0296 | não | estrita | 21 x 42 | 1 / 0 | 24 x 40 | 0 | 64 / 64 | 65 / 65 | 2 (13) | 1 | +0,7 | sim | sim | seção / seção | 17:00 / 17:04 |
| MG | ARAGUARI | 0016 | 0347 | não | estrita | 4 x 33 | 0 / 0 | 5 x 29 | 0 | 37 / 34 | 37 / 37 | 1 (13) | 1 | -0,0 | sim | sim | seção / seção | 17:00 / 17:00 |
| AC | SANTA ROSA DO PURUS | 0003 | 0095 | 22 para 13 | troca+desvio | 102 x 105 | 9 / 4 | 174 x 47 | 7 | 220 / 228 | 339 / 337 | 55 (13) | 0 | +10,2 | sim | sim | seção / seção | 15:02 / 15:01 |
| AC | MANOEL URBANO | 0003 | 0160 | 13 para 22 | troca+desvio | 112 x 55 | 0 / 3 | 48 x 104 | 21 | 170 / 173 | 238 / 236 | 46 (22) | 0 | -16,2 | sim | sim | seção / seção | 15:03 / 15:02 |
| AM | BARCELOS | 0018 | 0037 | 22 para 13 | troca+desvio | 37 x 171 | 8 / 15 | 84 x 71 | 35 | 231 / 190 | 377 / 377 | 39 (13) | 0 | +14,2 | sim | sim | seção / seção | 19:05 / 16:00 |
| RN | RAFAEL GODEIRO | 0037 | 0077 | não | troca+desvio | 155 x 117 | 8 / 4 | 190 x 88 | 7 | 284 / 285 | 344 / 344 | 26 (13) | 0 | +4,4 | sim | sim | seção / seção | 17:10 / 17:00 |
| PA | ANAPU | 0080 | 0254 | não | troca+desvio | 127 x 29 | 0 / 2 | 158 x 4 | 0 | 158 / 162 | 238 / 238 | 25 (13) | 0 | +8,1 | sim | sim | seção / seção | 17:30 / 17:00 |
| CE | SÃO GONÇALO DO AMARANTE | 0036 | 0054 | não | troca+desvio | 123 x 119 | 22 / 18 | 173 x 91 | 15 | 282 / 279 | 335 / 335 | 25 (13) | 0 | +4,2 | sim | sim | seção / seção | 17:48 / 17:01 |
| MA | LAGO DA PEDRA | 0074 | 0066 | não | troca+desvio | 124 x 86 | 10 / 12 | 170 x 62 | 1 | 232 / 233 | 299 / 299 | 24 (13) | 0 | +6,4 | sim | sim | seção / seção | 17:25 / 17:00 |
| RN | RAFAEL GODEIRO | 0037 | 0076 | não | troca+desvio | 143 x 126 | 5 / 10 | 176 x 91 | 6 | 284 / 273 | 346 / 346 | 24 (13) | 0 | +5,1 | sim | sim | seção / seção | 17:20 / 17:01 |
| RN | RAFAEL GODEIRO | 0037 | 0074 | não | troca+desvio | 133 x 99 | 10 / 9 | 169 x 75 | 7 | 251 / 251 | 308 / 308 | 24 (13) | 0 | +4,7 | sim | sim | seção / seção | 17:09 / 17:01 |
| CE | CAUCAIA | 0120 | 0361 | não | troca | 244 x 49 | 7 / 12 | 276 x 24 | 13 | 312 / 313 | 349 / 349 | 24 (13) | 0 | +2,8 | sim | sim | seção / seção | 18:51 / 17:00 |
| AL | BELO MONTE | 0029 | 0023 | não | troca+desvio | 192 x 76 | 8 / 12 | 163 x 113 | 6 | 288 / 282 | 359 / 360 | 23 (22) | 0 | -7,5 | sim | sim | seção / seção | 18:03 / 17:01 |
| BA | ANTAS | 0082 | 0205 | não | troca | 147 x 110 | 9 / 13 | 187 x 87 | 6 | 279 / 280 | 348 / 348 | 23 (13) | 0 | +3,4 | sim | sim | seção / seção | 17:23 / 17:02 |
| RN | RAFAEL GODEIRO | 0037 | 0072 | não | troca | 148 x 103 | 2 / 6 | 176 x 81 | 5 | 259 / 262 | 322 / 323 | 22 (13) | 0 | +3,5 | sim | sim | seção / seção | 17:13 / 17:00 |
| PA | SÃO MIGUEL DO GUAMÁ | 0011 | 0420 | não | troca+desvio | 131 x 83 | 7 / 11 | 167 x 62 | 6 | 232 / 235 | 277 / 277 | 21 (13) | 0 | +4,6 | sim | sim | seção / seção | 17:24 / 17:04 |
| RN | RAFAEL GODEIRO | 0037 | 0079 | 22 para 13 | troca+desvio | 136 x 137 | 6 / 12 | 169 x 110 | 6 | 291 / 285 | 346 / 346 | 21 (13) | 0 | +4,1 | sim | sim | seção / seção | 17:25 / 17:01 |
| CE | CAUCAIA | 0120 | 0315 | não | troca | 146 x 86 | 7 / 12 | 184 x 65 | 8 | 251 / 257 | 305 / 305 | 21 (13) | 0 | +4,0 | sim | sim | seção / seção | 17:39 / 17:00 |
| RN | AFONSO BEZERRA | 0018 | 0059 | não | troca | 178 x 92 | 10 / 21 | 218 x 71 | 13 | 301 / 302 | 350 / 350 | 21 (13) | 0 | +2,7 | sim | sim | seção / seção | 18:56 / 17:00 |
| AM | IPIXUNA | 0045 | 0063 | não | troca+desvio | 135 x 61 | 12 / 19 | 167 x 2 | 28 | 227 / 197 | 335 / 335 | 20 (13) | 0 | +7,3 | sim | sim | reserva / reserva | 18:58 / 15:02 |
| AL | BELO MONTE | 0029 | 0056 | não | troca+desvio | 207 x 100 | 12 / 12 | 172 x 133 | 11 | 331 / 316 | 393 / 393 | 20 (22) | 0 | -6,8 | sim | sim | seção / seção | 19:09 / 17:03 |

### Viradas atípicas de 2026: as 40 primeiras de 157

| UF | Município | Zona | Seção | Virada | Critério | 1º turno 13 x 22 | Outros / BN 1º | 2º turno 13 x 22 | BN 2º | Comparec. 1º / 2º | Aptos 1º / 2º | Troca mín. (a favor de) | Troca estrita | z | Mesma urna | Mesma carga | Urna 1º / 2º | Encerramento local 1º / 2º |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| AC | SANTA ROSA DO PURUS | 0003 | 0095 | 22 para 13 | troca+desvio | 102 x 105 | 9 / 4 | 174 x 47 | 7 | 220 / 228 | 339 / 337 | 55 (13) | 0 | +10,2 | sim | sim | seção / seção | 15:02 / 15:01 |
| AC | MANOEL URBANO | 0003 | 0160 | 13 para 22 | troca+desvio | 112 x 55 | 0 / 3 | 48 x 104 | 21 | 170 / 173 | 238 / 236 | 46 (22) | 0 | -16,2 | sim | sim | seção / seção | 15:03 / 15:02 |
| AM | BARCELOS | 0018 | 0037 | 22 para 13 | troca+desvio | 37 x 171 | 8 / 15 | 84 x 71 | 35 | 231 / 190 | 377 / 377 | 39 (13) | 0 | +14,2 | sim | sim | seção / seção | 19:05 / 16:00 |
| RN | RAFAEL GODEIRO | 0037 | 0079 | 22 para 13 | troca+desvio | 136 x 137 | 6 / 12 | 169 x 110 | 6 | 291 / 285 | 346 / 346 | 21 (13) | 0 | +4,1 | sim | sim | seção / seção | 17:25 / 17:01 |
| AL | MACEIÓ | 0003 | 0061 | 22 para 13 | troca | 124 x 149 | 9 / 25 | 167 x 129 | 10 | 307 / 306 | 375 / 375 | 19 (13) | 0 | +3,5 | sim | sim | seção / seção | 18:19 / 17:03 |
| RJ | BELFORD ROXO | 0153 | 0237 | 22 para 13 | troca | 106 x 151 | 18 / 12 | 150 x 132 | 6 | 287 / 288 | 371 / 371 | 19 (13) | 0 | +3,3 | sim | sim | seção / seção | 17:38 / 17:04 |
| RJ | JAPERI | 0139 | 0017 | 22 para 13 | troca | 121 x 150 | 8 / 10 | 151 x 129 | 7 | 289 / 287 | 337 / 337 | 19 (13) | 0 | +2,0 | sim | sim | seção / seção | 17:08 / 17:01 |
| CE | SÃO GONÇALO DO AMARANTE | 0036 | 0285 | 22 para 13 | troca | 105 x 144 | 17 / 11 | 140 x 122 | 13 | 277 / 275 | 336 / 336 | 18 (13) | 0 | +2,9 | sim | sim | seção / seção | 17:06 / 17:01 |
| RJ | DUQUE DE CAXIAS | 0079 | 0668 | 22 para 13 | troca | 110 x 143 | 12 / 13 | 145 x 124 | 8 | 278 / 277 | 329 / 329 | 18 (13) | 0 | +2,8 | sim | sim | seção / seção | 17:08 / 17:05 |
| PA | TAILÂNDIA | 0093 | 0166 | 22 para 13 | troca | 83 x 95 | 5 / 6 | 110 x 77 | 4 | 189 / 191 | 295 / 295 | 18 (13) | 0 | +2,8 | sim | sim | seção / seção | 17:20 / 17:04 |
| AC | FEIJÓ | 0007 | 0067 | 22 para 13 | troca+desvio | 35 x 59 | 0 / 4 | 52 x 14 | 7 | 98 / 73 | 155 / 155 | 17 (13) | 0 | +11,0 | sim | sim | seção / seção | 15:00 / 15:01 |
| SE | TOBIAS BARRETO | 0023 | 0087 | 22 para 13 | troca | 79 x 82 | 6 / 4 | 102 x 65 | 4 | 171 / 171 | 207 / 207 | 17 (13) | 0 | +3,8 | não | não | seção / reserva | 17:04 / 17:05 |
| RJ | SÃO FIDÉLIS | 0035 | 0139 | 22 para 13 | troca | 87 x 89 | 10 / 3 | 115 x 72 | 2 | 189 / 189 | 255 / 255 | 17 (13) | 0 | +3,8 | sim | sim | seção / seção | 17:14 / 17:04 |
| CE | BARREIRA | 0052 | 0174 | 22 para 13 | troca | 145 x 151 | 7 / 8 | 177 x 134 | 2 | 311 / 313 | 344 / 344 | 17 (13) | 0 | +3,1 | sim | sim | seção / seção | 18:37 / 17:00 |
| RJ | CAMPOS DOS GOYTACAZES | 0075 | 0026 | 22 para 13 | troca | 97 x 144 | 21 / 15 | 135 x 122 | 19 | 277 / 276 | 342 / 342 | 17 (13) | 0 | +2,6 | sim | sim | seção / seção | 17:19 / 17:07 |
| RJ | ITAGUAÍ | 0105 | 0207 | 22 para 13 | troca+desvio | 51 x 86 | 5 / 6 | 72 x 66 | 8 | 148 / 146 | 200 / 200 | 16 (13) | 0 | +5,3 | sim | sim | seção / seção | 17:06 / 17:03 |
| RJ | SÃO JOÃO DE MERITI | 0088 | 0124 | 22 para 13 | troca | 100 x 145 | 16 / 22 | 144 x 129 | 16 | 283 / 289 | 341 / 341 | 16 (13) | 0 | +3,4 | sim | sim | seção / seção | 17:04 / 17:01 |
| RJ | MACAÉ | 0254 | 0111 | 22 para 13 | troca | 123 x 126 | 18 / 20 | 164 x 108 | 13 | 287 / 285 | 367 / 367 | 16 (13) | 0 | +3,1 | sim | sim | seção / seção | 17:56 / 17:09 |
| PA | NOVO REPARTIMENTO | 0101 | 0141 | 22 para 13 | troca | 104 x 143 | 3 / 11 | 130 x 127 | 6 | 261 / 263 | 345 / 345 | 16 (13) | 0 | +2,5 | sim | sim | seção / seção | 18:38 / 17:00 |
| SP | ITIRAPINA | 0245 | 0130 | 22 para 13 | troca | 106 x 132 | 13 / 14 | 141 x 116 | 9 | 265 / 266 | 357 / 357 | 16 (13) | 0 | +2,2 | sim | sim | seção / seção | 17:01 / 17:00 |
| RN | CEARÁ-MIRIM | 0006 | 0062 | 22 para 13 | troca | 110 x 120 | 8 / 11 | 139 x 105 | 11 | 249 / 255 | 291 / 292 | 15 (13) | 0 | +3,6 | sim | sim | seção / seção | 17:08 / 17:03 |
| SP | CAÇAPAVA | 0029 | 0232 | 22 para 13 | troca | 84 x 118 | 12 / 18 | 118 x 101 | 11 | 232 / 230 | 286 / 286 | 15 (13) | 0 | +3,6 | sim | sim | seção / seção | 17:02 / 17:01 |
| PA | TAILÂNDIA | 0093 | 0180 | 22 para 13 | troca | 95 x 111 | 12 / 5 | 123 x 94 | 4 | 223 / 221 | 293 / 293 | 15 (13) | 0 | +2,2 | sim | sim | seção / seção | 17:32 / 17:02 |
| PA | BELÉM | 0030 | 0807 | 22 para 13 | troca+desvio | 116 x 117 | 27 / 15 | 165 x 102 | 7 | 275 / 274 | 358 / 358 | 14 (13) | 0 | +4,9 | sim | sim | seção / seção | 17:12 / 17:03 |
| SP | ITARARÉ | 0057 | 0108 | 22 para 13 | troca | 80 x 100 | 11 / 16 | 112 x 86 | 9 | 207 / 207 | 311 / 311 | 14 (13) | 0 | +3,5 | sim | sim | seção / seção | 17:00 / 17:00 |
| AL | JUNQUEIRO | 0034 | 0215 | 22 para 13 | troca | 108 x 140 | 14 / 15 | 144 x 126 | 9 | 277 / 279 | 340 / 340 | 14 (13) | 0 | +3,4 | sim | sim | seção / seção | 17:13 / 17:00 |
| MG | CORONEL FABRICIANO | 0097 | 0142 | 22 para 13 | troca | 115 x 116 | 10 / 11 | 149 x 102 | 9 | 252 / 260 | 329 / 329 | 14 (13) | 0 | +3,1 | sim | sim | seção / seção | 17:32 / 17:00 |
| RJ | DUQUE DE CAXIAS | 0079 | 0023 | 22 para 13 | troca | 92 x 128 | 16 / 18 | 128 x 114 | 12 | 254 / 254 | 305 / 305 | 14 (13) | 0 | +3,1 | sim | sim | seção / seção | 17:15 / 17:17 |
| RJ | MESQUITA | 0150 | 0204 | 22 para 13 | troca | 102 x 144 | 12 / 18 | 135 x 127 | 11 | 276 / 273 | 343 / 343 | 14 (13) | 0 | +2,7 | sim | sim | seção / seção | 17:23 / 17:00 |
| RJ | NOVA IGUAÇU | 0084 | 0687 | 22 para 13 | troca | 104 x 140 | 14 / 16 | 138 x 126 | 12 | 274 / 276 | 346 / 346 | 14 (13) | 0 | +2,3 | sim | sim | seção / seção | 17:19 / 17:01 |
| RJ | MAGÉ | 0110 | 0306 | 22 para 13 | troca | 122 x 128 | 18 / 12 | 157 x 114 | 9 | 280 / 280 | 335 / 335 | 14 (13) | 0 | +2,1 | sim | sim | seção / seção | 17:05 / 17:01 |
| MS | BELA VISTA | 0017 | 0007 | 22 para 13 | troca+desvio | 51 x 74 | 2 / 3 | 68 x 60 | 4 | 130 / 132 | 175 / 175 | 13 (13) | 0 | +5,2 | sim | sim | seção / seção | 16:00 / 16:00 |
| RR | PACARAIMA | 0007 | 0107 | 22 para 13 | troca | 76 x 94 | 5 / 1 | 94 x 60 | 4 | 176 / 158 | 198 / 198 | 13 (13) | 0 | +3,9 | sim | sim | seção / seção | 16:11 / 16:00 |
| CE | TIANGUÁ | 0081 | 0286 | 22 para 13 | troca | 97 x 125 | 11 / 14 | 138 x 112 | 6 | 247 / 256 | 296 / 296 | 13 (13) | 0 | +3,4 | sim | sim | seção / seção | 18:15 / 17:02 |
| AL | MACEIÓ | 0003 | 0016 | 22 para 13 | troca | 75 x 105 | 8 / 9 | 101 x 92 | 5 | 197 / 198 | 310 / 310 | 13 (13) | 0 | +3,3 | sim | sim | seção / seção | 17:08 / 17:00 |
| PA | ORIXIMINÁ | 0038 | 0253 | 22 para 13 | troca | 97 x 118 | 11 / 7 | 127 x 104 | 1 | 233 / 232 | 315 / 315 | 13 (13) | 0 | +1,9 | sim | sim | seção / seção | 17:01 / 17:04 |
| BA | LUÍS EDUARDO MAGALHÃES | 0205 | 0062 | 22 para 13 | troca | 112 x 133 | 2 / 6 | 136 x 120 | 3 | 253 / 259 | 321 / 321 | 13 (13) | 0 | +1,9 | sim | sim | seção / seção | 17:14 / 17:01 |
| PB | CABEDELO | 0057 | 0115 | 22 para 13 | desvio | 100 x 131 | 18 / 20 | 147 x 119 | 6 | 269 / 272 | 338 / 338 | 12 (13) | 0 | +4,8 | sim | sim | seção / seção | 17:09 / 17:09 |
| SP | SÃO PAULO | 0255 | 0428 | 22 para 13 | desvio | 88 x 110 | 27 / 15 | 136 x 98 | 11 | 240 / 245 | 307 / 307 | 12 (13) | 0 | +4,7 | sim | sim | seção / seção | 17:04 / 17:01 |
| SP | CAMPINAS | 0378 | 0436 | 22 para 13 | troca+desvio | 85 x 105 | 16 / 11 | 128 x 93 | 6 | 217 / 227 | 277 / 277 | 12 (13) | 0 | +4,7 | sim | sim | seção / seção | 17:03 / 17:01 |

### Atípicos de 2026 com urna diferente entre os turnos

| UF | Município | Zona | Seção | Virada | Critério | 1º turno 13 x 22 | Outros / BN 1º | 2º turno 13 x 22 | BN 2º | Comparec. 1º / 2º | Aptos 1º / 2º | Troca mín. (a favor de) | Troca estrita | z | Mesma urna | Mesma carga | Urna 1º / 2º | Encerramento local 1º / 2º |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| AL | SANTANA DO IPANEMA | 0019 | 0234 | não | troca | 133 x 79 | 10 / 9 | 162 x 62 | 9 | 231 / 233 | 287 / 287 | 17 (13) | 0 | +3,0 | não | não | seção / seção | 17:07 / 17:04 |
| BA | BREJOLÂNDIA | 0190 | 0023 | não | troca | 171 x 79 | 4 / 5 | 196 x 64 | 6 | 259 / 266 | 348 / 348 | 14 (13) | 0 | +1,9 | não | não | reserva / seção | 19:57 / 17:05 |
| BA | CAMPO FORMOSO | 0053 | 0274 | 22 para 13 | desvio | 41 x 53 | 2 / 12 | 60 x 42 | 1 | 108 / 103 | 134 / 134 | 6 (13) | 0 | +5,9 | não | não | seção / reserva | 17:03 / 17:01 |
| MG | ARAGUARI | 0016 | 0264 | não | desvio | 65 x 37 | 6 / 6 | 66 x 45 | 3 | 114 / 114 | 135 / 135 | 0 (13) | 0 | -4,5 | não | não | seção / reserva | 17:05 / 18:35 |
| PA | COLARES | 0008 | 0350 | não | desvio | 63 x 33 | 4 / 6 | 57 x 39 | 1 | 106 / 97 | 126 / 126 | 0 (13) | 0 | -4,2 | não | não | seção / reserva | 17:01 / 17:00 |
| PI | SANTO ANTÔNIO DE LISBOA | 0028 | 0095 | não | desvio | 164 x 52 | 2 / 13 | 149 x 74 | 4 | 231 / 227 | 273 / 273 | 11 (22) | 0 | -5,0 | não | não | seção / reserva | 17:17 / 17:01 |
| RJ | MESQUITA | 0150 | 0076 | não | troca | 83 x 142 | 8 / 12 | 106 x 127 | 10 | 245 / 243 | 347 / 347 | 13 (13) | 0 | +2,0 | não | não | seção / reserva | 17:10 / 17:01 |
| SE | TOBIAS BARRETO | 0023 | 0087 | 22 para 13 | troca | 79 x 82 | 6 / 4 | 102 x 65 | 4 | 171 / 171 | 207 / 207 | 17 (13) | 0 | +3,8 | não | não | seção / reserva | 17:04 / 17:05 |

## Consultas registradas

Além dos dois arquivos SQL, os números de conferência deste documento vieram destas consultas no ClickHouse (26/10/2026, 09h20 a 09h30):

```sql
-- seções com BU e pareamento
SELECT count() FROM dataurnas.v_bu_ultima;                       -- 499.207
SELECT count(), countIf(virada) FROM dataurnas.v_comparacao_t1_t2; -- 499.205, 31.960
SELECT status, tem_presidente, count() FROM dataurnas.ref_secoes_2026_t1 GROUP BY ALL;
-- ok 499.207; agregada 17.931; nao_instalada 41

-- seções do 1º turno sem par no 2º e BUs do 2º turno sem voto de Presidente
SELECT t1.uf, t1.cd_mun, t1.zona, t1.secao, t1.comparecimento, t1.votos_13, t1.votos_22
FROM dataurnas.v_votos_t1_secao t1
LEFT ANTI JOIN dataurnas.v_votos_t2_secao t2 USING (uf, cd_mun, zona, secao);
SELECT u.uf, u.cd_mun, u.zona, u.secao, u.aptos, u.comparecimento
FROM dataurnas.v_bu_ultima u
LEFT ANTI JOIN dataurnas.v_votos_t2_secao t USING (uf, cd_mun, zona, secao);

-- votos do 1º turno por número (o 28 aparece com 5.246)
SELECT tipo_voto, numero, sum(votos) FROM dataurnas.ref_votos_2026_t1 GROUP BY ALL ORDER BY 1, 2;

-- totais oficiais do 1º turno (soma dos municípios) e do 2º turno (Brasil)
SELECT sum(eleitorado), sum(comparecimento), sum(votos_brancos), sum(votos_nulos_total),
       sum(v_13), sum(v_22), sum(secoes_totalizadas)
FROM dataurnas.ref_resultado_municipio_2026_t1;
SELECT totalizado_em, st, ts, tv, vb, tvn, cand['13'], cand['22']
FROM dataurnas.v_totais_ultima WHERE nivel = 'br';
```

`v_comparacao_t1_t2` conta 31.960 viradas porque inclui o exterior (31.395 + 565 = 31.960).

## Limitações

- **Versão de BU.** O 2º turno usa a última versão de BU de cada seção (`v_bu_ultima`, pelo recebimento no TSE). Seção com pacote substituto pode exigir análise caso a caso (`v_bu_versoes_por_secao`).
- **Seções agregadas.** O pareamento é por UF, município, zona e seção. Se a agregação de seções mudou entre os turnos, aptos e comparecimento mudam e a seção pode parecer atípica sem que nada tenha acontecido com os votos. Há 55.406 seções de 2026 (e 58.701 de 2022) com aptos diferentes entre turnos, na maioria por diferença pequena; a coluna `aptos_1` / `aptos_2` está nas listas.
- **Troca mínima é conta líquida.** Ela não identifica eleitores. Uma troca mínima alta é compatível com eleitores que faltaram em um turno e outros que vieram no outro. Só a troca estrita é obrigatória, e ela ainda supõe que o eleitorado da seção é o mesmo (salvo agregação).
- **O modelo de esperado é simples.** É uma regressão logística com cinco variáveis, ajustada em uma única eleição. Ele acerta o total de viradas no sentido do movimento (1,03 em 2022, 0,96 em 2026), mas superestima as viradas contra o movimento geral (0,75 em 2022 e 0,70 em 2026) e as probabilidades intermediárias. Razões observado ÷ esperado por UF entre 0,3 e 4 aconteceram em 2022.
- **2022 e 2026 não são eleições iguais.** Em 2022 o movimento entre turnos foi para o 22; em 2026, para o 13, e mais forte (+2,9 contra -1,6 pontos). Os candidatos 22 são diferentes. A régua é a mesma, mas a comparação é com o comportamento normal de seções entre dois turnos, não com o mesmo eleitorado.
- **Critérios de atípico são de triagem.** Os limiares (10 votos e 5% do comparecimento; \|z\| > 4; 30 seções por município) foram fixados antes de olhar as seções e aplicados igualmente aos dois anos. Com quase 500 mil seções, casos extremos são esperados por acaso; ser atípico não é evidência de irregularidade, é motivo para conferir o boletim impresso.
- **Fonte única.** Os votos vêm dos BUs publicados pelo TSE. A conferência independente (QR Code do boletim impresso, ata da mesa) não foi feita aqui para as seções listadas.
- **Exterior.** O exterior entra só na tabela por grupo e na decomposição nacional; o modelo, os atípicos e as tabelas por UF tratam só do Brasil, como em 2022 (o Parquet de 2022 não tem o exterior).
