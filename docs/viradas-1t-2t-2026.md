# Viradas de liderança entre o 1º e o 2º turno por seção: 2026 comparado com 2022

Levantamento de 26/10/2026 sobre as seções em que o candidato que liderou no 1º turno presidencial de 2026 (04/10/2026) perdeu a liderança no 2º turno (25/10/2026), considerando só 13 (Lula) e 22 (Flávio Bolsonaro). A pergunta é se o número e o tamanho dessas viradas fogem do que é normal entre dois turnos. A referência é a eleição de 2022 (13, Lula, contra 22, Jair Bolsonaro; 1º turno em 02/10/2022 e 2º turno em 30/10/2022), medida com exatamente as mesmas regras, seção a seção.

O levantamento é descritivo. Ele não afirma fraude e também não a descarta sem base: aponta o que é esperado, o que não é, e lista as seções que merecem ser conferidas contra o boletim de urna impresso.

Script: `scripts/ele2026/viradas_t1_t2.py` (testes em `tests/ele2026/test_viradas_t1_t2.py`). Saída, fora do git: `data/parquet/2026/t2/viradas/` (`resumo.json`, `resumo_uf.parquet`, `faixas.parquet`, `secoes_2026.parquet`, `secoes_2022.parquet`, `atipicos_2026.csv` e `.parquet`, `atipicos_2022.csv` e `.parquet`). O script pode ser rodado de novo à medida que a coleta do 2º turno avança; antes, regere o encerramento:

```sh
nice -n 20 .venv/bin/python scripts/ele2026/analisar_encerramento_t2.py \
  --parts data/versoes/2026/t2/bus/parts --parts data/versoes/2026/t2-sseco/bus/parts
nice -n 20 .venv/bin/python scripts/ele2026/viradas_t1_t2.py
```

## Resumo

| Item | 2026 | 2022 (referência) |
|---|---|---|
| Seções com BU nos dois turnos | 145.489 (cobertura parcial, ver abaixo) | 470.808 (país inteiro) |
| Movimento médio da fatia do 13 (13 ÷ (13 + 22)) entre turnos, por seção | **+2,11 pontos** | **-1,64 ponto** |
| Desvio padrão desse movimento entre seções | 2,33 pontos | 2,20 pontos |
| Viradas no sentido do movimento geral | 22 para 13: **5.876** (20,4% das 28.760 seções em que o 22 liderou) | 13 para 22: **19.383** (7,9% das 243.847 seções em que o 13 liderou) |
| Esperado pelo modelo de 2022 | 5.751 (desvio 44); observado ÷ esperado **1,02** | 18.898; observado ÷ esperado 1,03 |
| Viradas no sentido contrário | 13 para 22: **116** (0,10%) | 22 para 13: 1.491 (0,66%) |
| Esperado pelo modelo de 2022 | 250 (desvio 15); observado ÷ esperado 0,46 | 1.976; observado ÷ esperado 0,75 |
| Margem média no 1º turno das seções que viraram | 10,5 votos (mediana 9) | 8,6 votos (mediana 7) |
| Viradas com margem de até 10 votos no 1º turno | 58% | 68% |
| Viradas com troca mínima zero | 80% | 86% |
| Troca mínima nas viradas: mediana, p90, p99, máximo | 0, 3, 10, 55 | 0, 2, 8, 129 |
| Atípicos (qualquer critério), por 10 mil seções | 420 (28,9) | 778 (16,5) |
| Atípicos nas 12 UFs comparáveis, por 10 mil seções | 365 (28,5) | 256 (21,2) |

Em poucas linhas:

1. **Virada em seção de margem pequena é comum, e o volume de 2026 é o esperado.** O 13 ganhou fatia em quase todo o Norte e o Nordeste entre os turnos (o 22 tinha liderado o 1º turno no país, com 56,1 milhões a 53,9 milhões, e o 13 venceu o 2º). Com esse movimento, as seções em que o 22 tinha liderado por poucos votos tendem a virar. O modelo ajustado em 2022, que só usa a margem do 1º turno, o movimento do município e o volume de outros, brancos e nulos, esperava 5.751 viradas de 22 para 13; foram 5.876 (2% a mais). Por UF, a razão observado ÷ esperado ficou entre 0,89 e 1,22. Em 2022, a mesma razão por UF variou de 0,29 a 4,02.
2. **O sentido contrário (13 para 22) teve menos viradas do que o esperado**, 116 contra 250. Isso também aconteceu em 2022 no Nordeste (0,72 do esperado): o modelo superestima viradas contra o candidato que domina a região.
3. **A dispersão do movimento entre seções é a mesma de 2022.** O desvio padrão da variação da fatia do 13 foi 2,33 pontos em 2026 e 2,20 em 2022 (2,31 e 2,07 nas UFs comparáveis). O que mudou foi o sentido do movimento, não a forma da distribuição.
4. **Troca mínima alta existe nos dois anos e com tamanhos parecidos.** Em 2026, 197 seções exigiriam pelo menos 10 eleitores (e 5% do comparecimento) passando diretamente de um candidato para o outro, se só se contasse a reserva líquida (outros, queda de brancos e nulos, aumento de comparecimento). Em 2022 foram 198, num universo três vezes maior. Considerando o tamanho do movimento de cada município e a reserva de cada seção, a taxa de 2022 previa 168 em 2026: o observado ficou 17% acima, concentrado no Ceará (52 contra 18 esperadas) e no Maranhão (34 contra 27). O maior caso de 2026 tem 55 votos; o de 2022, 129.
5. **Troca obrigatória mesmo com rotatividade total é rara nos dois anos:** 5 seções em 2026 (0,34 por 10 mil) e 11 em 2022 (0,23 por 10 mil).
6. **Desvio forte em relação ao próprio município** (|z| > 4) ocorreu em 263 seções em 2026 (18,1 por 10 mil) e 653 em 2022 (13,9 por 10 mil); nas UFs comparáveis, 17,4 e 19,4 por 10 mil. Parte dos casos de 2026 vem de municípios pequenos inteiros que se moveram contra a tendência do estado (Belo Monte, AL: 14 de 16 seções atípicas; Santo Antônio de Lisboa, PI: 13 de 24), o que indica fator local, não urna isolada.
7. **Nos atípicos de 2026, a urna é quase sempre a mesma do 1º turno.** Em 415 das 420 seções o número interno da urna é o mesmo nos dois turnos, e em 414 o código de carga também; nas 5 restantes a urna foi trocada (4 por urna de reserva). Seções que encerraram depois das 17h10 de Brasília não concentram viradas (3,3% contra 4,1% das demais) nem atípicos (0,21% contra 0,29%).

Conclusão descritiva: o número de viradas em 2026 é o que se espera de um movimento regional de cerca de 2 pontos a favor do 13 aplicado a seções com margem de poucos votos. Não há excesso de viradas. O que fica acima da referência de 2022 é um grupo pequeno de seções com troca mínima alta, sobretudo no Ceará e no Maranhão, e um punhado de seções com troca obrigatória ou desvio muito forte. Essas seções estão listadas abaixo para conferência; a explicação mais comum para casos assim é local (município que mudou de lado, eleitores que votaram em um turno e não no outro, agregação de seções), mas isso só se confirma caso a caso.

## Fonte e método

### Dados

- **2026, 2º turno:** `data/parquet/2026/t2/encerramento/secoes_encerramento.parquet`, gerado por `analisar_encerramento_t2.py` a partir dos BUs versionados (`data/versoes/2026/t2/bus/parts` e `data/versoes/2026/t2-sseco/bus/parts`, só leitura). Em 26/10/2026, 00h16, havia 145.489 seções do Brasil com BU decodificado e cargo presidente, todas pareadas com o 1º turno.
- **2026, 1º turno:** `data/parquet/2026/secoes_2026.parquet` (seções com status `ok`) e `votos_presidente_2026.parquet`. Votos nominais em 13 e 22; "outros" = demais votos nominais; brancos e nulos do cargo presidente.
- **2026, urna e carga:** número interno e código de carga do 1º turno em `secoes_2026.parquet`; do 2º turno em `data/parquet/2026/t2/software/secoes_software.parquet`. Para atípicos sem linha nesse arquivo, o script lê o próprio BU nos parts (só leitura). Nesta execução, todos os 420 atípicos tinham a informação.
- **2022:** `data/parquet/secoes.parquet` (turnos 1 e 2) e `votos_t1_a.parquet`, `votos_t1_b.parquet`, `votos_t2.parquet`, cargo presidente (código 1, eleições 544 e 545). 470.808 seções têm BU nos dois turnos. Os nomes dos municípios de 2022 vêm do código TSE, o mesmo de 2026. Em 2022 não há número interno nem código de carga no Parquet; fica só o modelo da urna.

### Cobertura de 2026 nesta execução

| UF | Cobertura (seções do 2º turno ÷ seções do 1º turno) |
|---|---|
| AC | 99,1% |
| AL | 99,7% |
| AM | 98,1% |
| AP | 99,8% |
| BA | 97,7% |
| CE | 100% |
| MA | 97,0% |
| PA | 79,3% |
| PB | 100% |
| PI | 100% |
| RR | 100% |
| SE | 100% |
| SP | 1,0% |
| TO | 100% |

As demais 13 UFs ainda não tinham BU do 2º turno coletado. "UFs comparáveis" são as 12 com cobertura de pelo menos 90% (AC, AL, AM, AP, BA, CE, MA, PB, PI, RR, SE, TO); a linha correspondente de 2022 usa as mesmas 12 UFs inteiras. PA e SP entram nas tabelas por UF, mas com amostra parcial (em SP, 1.033 seções).

### Definições (iguais em 2026 e 2022)

- **Líder** de cada turno: 13 ou 22, o que tiver mais votos nominais na seção; empate não tem líder.
- **Virada:** líder do 1º turno diferente do líder do 2º, sem empate em nenhum dos dois. Sentidos 22 para 13 e 13 para 22. A taxa de virada de um sentido é a fração das seções lideradas por aquele candidato no 1º turno que viraram.
- **Margem do 1º turno:** |votos do 13 menos votos do 22| no 1º turno, em votos.
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

Calibração em 2022, por decil de probabilidade (observado contra esperado): 9º decil 1.704 contra 1.706; 10º decil 19.076 contra 18.945; 8º decil 87 contra 198 (o modelo exagera um pouco as probabilidades intermediárias). Em 2026: 9º decil 82 contra 127; 10º decil 5.908 contra 5.869.

Também há uma tabela por faixas de margem (0, 1-2, 3-5, 6-10, 11-20, 21-40, 41-80, mais de 80 votos) e de reserva (até 5%, 5-10%, 10-15%, 15-20%, mais de 20%), em `faixas.parquet`, e o esperado correspondente (taxa de 2022 de cada faixa aplicada a 2026). Esse esperado ignora o sentido do movimento regional e por isso não serve para comparar sentidos: em 2026 ele dá 2.088 viradas de 22 para 13 e 2.643 de 13 para 22, contra 5.876 e 116 observadas, simplesmente porque em 2022 o movimento foi para o outro lado. Fica como registro de que a margem sozinha não explica as viradas; é preciso considerar o movimento do município.

### Critérios de atípico (mesma régua nos dois anos)

1. **Troca:** a maior troca mínima entre os dois candidatos é de pelo menos 10 votos e de pelo menos 5% do comparecimento do 2º turno. A régua é simétrica: vale para qualquer candidato, não só para o vencedor. O esperado vem da taxa de 2022 em cada combinação de faixa de movimento do município (0-0,5, 0,5-1, 1-2, 2-3, 3-4, 4-6, mais de 6 pontos) e de faixa de reserva.
2. **Estrita:** troca estrita maior que zero para qualquer candidato.
3. **Desvio:** |z| > 4, com z = (variação da fatia do 13 menos a mediana do município) ÷ (1,4826 × desvio absoluto mediano do município). Município com menos de 30 seções usa a UF. Só seções com pelo menos 20 votos em 13 + 22 nos dois turnos.

## Resultados por UF

### Viradas: observado contra esperado

| UF | Seções | 22 liderou no 1º | Viradas 22 para 13 | Taxa | Esperado | Obs. ÷ esp. | 13 liderou no 1º | Viradas 13 para 22 | Taxa | Esperado | Obs. ÷ esp. |
|---|---|---|---|---|---|---|---|---|---|---|---|
| AC | 2.249 | 2.148 | 34 | 1,6% | 32,3 | 1,05 | 99 | 4 | 4,0% | 2,6 | 1,54 |
| AL | 7.078 | 2.531 | 720 | 28,4% | 798,7 | 0,90 | 4.522 | 2 | 0,04% | 5,5 | 0,36 |
| AM | 8.001 | 4.481 | 553 | 12,3% | 593,2 | 0,93 | 3.484 | 16 | 0,46% | 15,2 | 1,05 |
| AP | 1.911 | 1.119 | 339 | 30,3% | 345,8 | 0,98 | 772 | 6 | 0,78% | 7,2 | 0,83 |
| BA | 34.641 | 1.877 | 497 | 26,5% | 450,0 | 1,10 | 32.711 | 25 | 0,08% | 60,5 | 0,41 |
| CE | 23.765 | 1.015 | 487 | 48,0% | 433,4 | 1,12 | 22.710 | 4 | 0,02% | 27,6 | 0,14 |
| MA | 17.542 | 1.893 | 498 | 26,3% | 449,5 | 1,11 | 15.590 | 9 | 0,06% | 28,5 | 0,32 |
| PA (79%) | 16.506 | 7.134 | 1.444 | 20,2% | 1.360,9 | 1,06 | 9.258 | 32 | 0,35% | 56,7 | 0,56 |
| PB | 10.712 | 1.527 | 780 | 51,1% | 749,0 | 1,04 | 9.126 | 3 | 0,03% | 9,5 | 0,32 |
| PI | 10.225 | 174 | 47 | 27,0% | 47,1 | 1,00 | 10.050 | 1 | 0,01% | 7,4 | 0,14 |
| RR | 1.519 | 1.431 | 14 | 1,0% | 11,5 | 1,22 | 88 | 0 | 0% | 0,2 | 0 |
| SE | 5.923 | 122 | 59 | 48,4% | 60,9 | 0,97 | 5.793 | 0 | 0% | 4,1 | 0 |
| SP (1%) | 1.033 | 744 | 163 | 21,9% | 149,2 | 1,09 | 279 | 2 | 0,72% | 2,3 | 0,87 |
| TO | 4.384 | 2.564 | 241 | 9,4% | 269,4 | 0,89 | 1.785 | 12 | 0,67% | 22,6 | 0,53 |
| Norte | 34.570 | 18.877 | 2.625 | 13,9% | 2.613,0 | 1,00 | 15.486 | 70 | 0,45% | 104,6 | 0,67 |
| Nordeste | 109.886 | 9.139 | 3.088 | 33,8% | 2.988,5 | 1,03 | 100.502 | 44 | 0,04% | 143,0 | 0,31 |
| Brasil (parcial) | 145.489 | 28.760 | 5.876 | 20,4% | 5.750,8 | 1,02 | 116.267 | 116 | 0,10% | 249,8 | 0,46 |
| UFs comparáveis | 127.950 | 20.882 | 4.269 | 20,4% | 4.240,7 | 1,01 | 106.730 | 82 | 0,08% | 190,8 | 0,43 |

Taxas altas como as de CE (48%), PB (51%) e SE (48%) não significam que metade do estado virou: nessas UFs o 22 liderou em poucas seções no 1º turno (1.015 no CE, 122 em SE), quase sempre por margem estreita, e o 13 cresceu cerca de 2 pontos no 2º turno.

### Referência de 2022, mesmas métricas

| Grupo | Seções | Viradas 22 para 13 | Taxa | Esperado | Obs. ÷ esp. | Viradas 13 para 22 | Taxa | Esperado | Obs. ÷ esp. |
|---|---|---|---|---|---|---|---|---|---|
| Norte | 38.966 | 168 | 0,84% | 171,0 | 0,98 | 1.497 | 7,96% | 1.485,0 | 1,01 |
| Nordeste | 132.401 | 218 | 3,01% | 163,9 | 1,33 | 1.725 | 1,38% | 2.389,9 | 0,72 |
| Centro-Oeste | 35.928 | 136 | 0,47% | 261,5 | 0,52 | 1.782 | 25,3% | 1.457,6 | 1,22 |
| Sudeste | 194.357 | 900 | 0,77% | 1.210,4 | 0,74 | 10.718 | 14,2% | 10.222,3 | 1,05 |
| Sul | 69.156 | 69 | 0,13% | 169,6 | 0,41 | 3.661 | 21,0% | 3.342,9 | 1,10 |
| Brasil | 470.808 | 1.491 | 0,66% | 1.976,3 | 0,75 | 19.383 | 7,95% | 18.897,7 | 1,03 |
| UFs comparáveis | 120.697 | 201 | 1,31% | 163,4 | 1,23 | 1.967 | 1,87% | 2.338,5 | 0,84 |

Por UF em 2022, a razão observado ÷ esperado foi de 0,29 (PR) a 4,02 (CE) no sentido 22 para 13 e de 0,44 (CE) a 1,38 (DF) no sentido 13 para 22, excluída RR (menos de 2 viradas esperadas). Ou seja, a faixa de 0,89 a 1,22 observada em 2026 no sentido principal está bem dentro do que aconteceu em 2022.

### Margem do 1º turno nas seções que viraram

| Grupo | Viradas | Margem média | Mediana | p90 | Máximo | Até 10 votos |
|---|---|---|---|---|---|---|
| 2026 Norte | 2.695 | 10,6 | 9 | 21 | 134 | 1.541 |
| 2026 Nordeste | 3.132 | 10,4 | 9 | 22 | 48 | 1.861 |
| 2026 Brasil (parcial) | 5.992 | 10,5 | 9 | 22 | 134 | 3.492 (58%) |
| 2022 Brasil | 20.874 | 8,6 | 7 | 18 | 202 | 14.214 (68%) |
| 2022 UFs comparáveis | 2.168 | 8,5 | 7 | 18 | 202 | 1.495 (69%) |

A margem das viradas de 2026 é um pouco maior que a de 2022 porque o movimento médio foi maior no Norte e Nordeste em 2026 (+1,9 a +2,6 pontos) do que em 2022 nas mesmas regiões (-1,6 ponto). A maior margem virada em 2026, 134 votos, é a de Barcelos (AM) 0018/0037, listada entre os atípicos.

### Variação da fatia do 13 entre turnos (pontos)

| Grupo | Média | Desvio padrão | p1 | p5 | Mediana | p95 | p99 |
|---|---|---|---|---|---|---|---|
| 2026 Norte | +2,60 | 2,47 | -3,23 | -1,24 | +2,57 | +6,55 | +8,65 |
| 2026 Nordeste | +1,94 | 2,25 | -3,32 | -1,63 | +1,92 | +5,64 | +7,40 |
| 2026 Brasil (parcial) | +2,11 | 2,33 | -3,29 | -1,56 | +2,08 | +5,92 | +7,80 |
| 2026 UFs comparáveis | +2,07 | 2,31 | -3,27 | -1,58 | +2,04 | +5,84 | +7,71 |
| 2022 Norte | -1,62 | 2,40 | -7,65 | -5,50 | -1,54 | +1,96 | +3,76 |
| 2022 Nordeste | -1,67 | 1,92 | -6,50 | -4,82 | -1,62 | +1,31 | +2,71 |
| 2022 Brasil | -1,64 | 2,20 | -7,09 | -5,26 | -1,59 | +1,84 | +3,40 |
| 2022 UFs comparáveis | -1,73 | 2,07 | -6,89 | -5,08 | -1,67 | +1,44 | +2,98 |

A distribuição de 2026 é, em forma, um espelho da de 2022: centro deslocado para o lado do 13 e largura praticamente igual (entre p1 e p99: 11,1 pontos em 2026, 10,5 em 2022).

### Troca mínima

| Grupo | Viradas com troca zero | p90 nas viradas | p99 nas viradas | Máximo nas viradas | Seções com troca alta | Esperado | Troca estrita > 0 |
|---|---|---|---|---|---|---|---|
| 2026 Norte | 82% | 3 | 10 | 55 | 45 | 64,4 | 2 |
| 2026 Nordeste | 78% | 4 | 11 | 19 | 152 | 102,1 | 3 |
| 2026 Brasil (parcial) | 80% | 3 | 10 | 55 | 197 | 167,7 | 5 |
| 2026 UFs comparáveis | 79% | 3 | 11 | 55 | 179 | 142,7 | 4 |
| 2022 Brasil | 86% | 2 | 8 | 129 | 198 | 198,0 | 11 |
| 2022 UFs comparáveis | 89% | 1 | 7 | 129 | 50 | 65,8 | 8 |

"Troca alta" é o critério 1 (pelo menos 10 votos e 5% do comparecimento), em qualquer seção, virada ou não. O esperado de 2026 é a taxa de 2022 por faixa de movimento do município e de reserva. A taxa cresce muito com o movimento: em 2022, 1,6 por 10 mil seções com movimento de 1-2 pontos, 20,7 com 3-4 pontos e 83 com 4-6 pontos; em 2026, 9,2, 24,5 e 47,8 nas mesmas faixas.

Por UF, troca alta observada contra esperada em 2026: AC 5 / 3,4; AL 22 / 20,7; AM 17 / 15,8; AP 0 / 6,7; BA 17 / 17,5; **CE 52 / 17,6**; **MA 34 / 26,7**; PA 18 / 23,8; PB 11 / 9,1; PI 10 / 7,8; RR 2 / 8,3; SE 6 / 2,8; SP 0 / 1,1; TO 3 / 6,4. No CE, 18 das 52 estão em Caucaia (9) e São Gonçalo do Amarante (9), dois municípios vizinhos em que o 13 cresceu bem acima do estado.

### Atípicos: 2026 contra 2022

| Grupo | Seções | Troca | Estrita | Desvio | Total (algum critério) | Por 10 mil |
|---|---|---|---|---|---|---|
| 2026 Brasil (parcial) | 145.489 | 197 | 5 | 263 | 420 | 28,9 |
| 2026 UFs comparáveis | 127.950 | 179 | 4 | 223 | 365 | 28,5 |
| 2022 Brasil | 470.808 | 198 | 11 | 653 | 778 | 16,5 |
| 2022 UFs comparáveis | 120.697 | 50 | 8 | 234 | 256 | 21,2 |

Por UF, atípicos por 10 mil seções em 2026 (2022 entre parênteses): AC 48,9 (56,5); AL 55,1 (9,1); AM 43,7 (28,2); AP 15,7 (17,2); BA 14,7 (19,3); CE 31,6 (21,1); MA 41,0 (26,8); PB 18,7 (4,2); PI 31,3 (33,5); RR 39,5 (39,4); SE 16,9 (14,6); TO 25,1 (22,7). O excesso de 2026 nas UFs comparáveis vem quase todo do critério de troca (179 contra 50), e esse critério depende do tamanho do movimento, que em 2026 foi maior nessas UFs. Descontado o movimento (esperado de 142,7), sobram cerca de 36 seções acima da referência. O critério de desvio, que já compara cada seção com o próprio município, está no mesmo nível de 2022.

AL chama atenção (39 atípicos contra 6 em 2022): 14 deles estão em Belo Monte, onde todas as 16 seções se moveram para o 22 (a fatia do 13 no município caiu de 70,3% para 61,6%) enquanto o estado se moveu para o 13. Com menos de 30 seções, o município é comparado com a UF, e o movimento do município inteiro aparece como desvio de cada seção. É um efeito local, não de seção isolada. O mesmo vale para Santo Antônio de Lisboa (PI, 13 de 24 seções atípicas; todas as 24 se moveram para o 22, e a fatia do 13 no município caiu de 76,3% para 68,7%), onde a seção 0028/0099 já tinha se movido para o 22 em 2022 (troca 25, z -5,4).

### Urna, carga, contingência e horário dos atípicos de 2026

- Mesmo número interno de urna nos dois turnos: 415 de 420. Mesmo código de carga: 414 de 420.
- Urna diferente: 5 (Santana do Ipanema, AL, 0019/0234; Brejolândia, BA, 0190/0023; Campo Formoso, BA, 0053/0274; Santo Antônio de Lisboa, PI, 0028/0095; Tobias Barreto, SE, 0023/0087). Em 4 delas houve urna de reserva em um dos turnos.
- Urna de reserva (`reservaSecao`) no 2º turno: 6 de 420. Nenhuma de contingência.
- Encerramento: 8 dos 420 atípicos encerraram depois das 17h10 de Brasília no 2º turno. Entre todas as seções, as que encerraram depois das 17h10 tiveram 3,3% de viradas e 0,21% de atípicos; as demais, 4,1% e 0,29%.

## Seções para conferência

A lista completa (420 seções de 2026 e 778 de 2022, com todas as colunas) está em `data/parquet/2026/t2/viradas/atipicos_2026.csv` e `atipicos_2022.csv`. Abaixo, as 30 de 2026 com maior troca estrita, troca mínima e desvio, todas as viradas atípicas e as de urna trocada. A conferência natural é contra o boletim de urna impresso da seção (QR Code) nos dois turnos e contra a ata da mesa receptora.

Colunas: "Outros / BN 1º" = votos em outros candidatos e brancos + nulos no 1º turno; "Troca mín." = a maior troca mínima entre os dois candidatos e a favor de quem; "z" = desvio da variação da fatia do 13 em relação ao município (ou à UF); encerramento no horário local da urna.

Casos que merecem destaque:

- **Santo Antônio de Lisboa (PI) 0028/0099:** 214 x 56 no 1º turno e 146 x 122 no 2º, com a mesma urna e a mesma carga. Mesmo aceitando rotatividade total, pelo menos 24 eleitores teriam de ter passado do 13 para o 22. É a única seção de 2026 com troca estrita acima de 5. Não virou (o 13 continuou à frente), e a mesma seção já tinha se movido para o 22 em 2022 (191 x 82 para 161 x 115).
- **Santa Rosa do Purus (AC) 0003/0095:** 102 x 105 para 174 x 47 (troca mínima 55). Em 2022 a mesma seção teve a virada inversa, de tamanho igual: 130 x 93 para 37 x 149 (troca 55). A oscilação forte entre turnos nessa seção não é nova.
- **Manoel Urbano (AC) 0003/0160:** virada de 13 para 22, 112 x 55 para 48 x 104, contra o movimento do estado. Em 2022 a seção 0003/0100 do mesmo município teve o maior caso daquele ano (4 x 206 para 160 x 45, troca 129).
- **Barcelos (AM) 0018/0037:** 37 x 171 para 84 x 71, com queda de comparecimento de 231 para 190 e brancos + nulos de 15 para 35. É a maior margem virada de 2026 (134 votos). A troca estrita é zero: a queda de comparecimento e a rotatividade explicam a virada sem exigir troca direta.
- **São Paulo de Olivença (AM) 0022/0070:** 154 x 20 para 180 x 1 (troca estrita 5).

### As 30 seções de 2026 com maior troca estrita, troca mínima e desvio

| UF | Município | Zona | Seção | Virada | Critério | 1º turno 13 x 22 | Outros / BN 1º | 2º turno 13 x 22 | BN 2º | Comparec. 1º / 2º | Aptos 1º / 2º | Troca mín. (a favor de) | Troca estrita | z | Mesma urna | Mesma carga | Urna 1º / 2º | Encerramento local 1º / 2º |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| PI | SANTO ANTÔNIO DE LISBOA | 0028 | 0099 | não | estrita+troca+desvio | 214 x 56 | 5 / 12 | 146 x 122 | 5 | 287 / 273 | 312 / 312 | 54 (22) | 24 | -12,5 | sim | sim | seção / seção | 17:54 / 17:00 |
| AM | SÃO PAULO DE OLIVENÇA | 0022 | 0070 | não | estrita+troca+desvio | 154 x 20 | 6 / 3 | 180 x 1 | 3 | 183 / 184 | 195 / 195 | 19 (13) | 5 | +5,2 | sim | sim | seção / seção | 15:05 / 15:06 |
| AL | SÃO SEBASTIÃO | 0049 | 0135 | não | estrita+desvio | 25 x 11 | 0 / 2 | 31 x 7 | 0 | 38 / 38 | 39 / 39 | 4 (13) | 3 | +5,1 | sim | sim | seção / seção | 17:04 / 17:01 |
| PA | CASTANHAL | 0004 | 0580 | não | estrita | 35 x 81 | 4 / 2 | 47 x 73 | 1 | 122 / 121 | 127 / 127 | 7 (13) | 1 | +3,4 | sim | sim | seção / seção | 17:01 / 17:00 |
| MA | BOM JARDIM | 0078 | 0296 | não | estrita | 59 x 7 | 1 / 2 | 65 x 3 | 2 | 69 / 70 | 71 / 71 | 4 (13) | 1 | +1,8 | sim | sim | seção / seção | 17:02 / 17:01 |
| AC | SANTA ROSA DO PURUS | 0003 | 0095 | 22->13 | troca+desvio | 102 x 105 | 9 / 4 | 174 x 47 | 7 | 220 / 228 | 339 / 337 | 55 (13) | 0 | +10,2 | sim | sim | seção / seção | 15:02 / 15:01 |
| AC | MANOEL URBANO | 0003 | 0160 | 13->22 | troca+desvio | 112 x 55 | 0 / 3 | 48 x 104 | 21 | 170 / 173 | 238 / 236 | 46 (22) | 0 | -16,2 | sim | sim | seção / seção | 15:03 / 15:02 |
| AM | BARCELOS | 0018 | 0037 | 22->13 | troca+desvio | 37 x 171 | 8 / 15 | 84 x 71 | 35 | 231 / 190 | 377 / 377 | 39 (13) | 0 | +14,2 | sim | sim | seção / seção | 19:05 / 16:00 |
| PA | ANAPU | 0080 | 0254 | não | troca+desvio | 127 x 29 | 0 / 2 | 158 x 4 | 0 | 158 / 162 | 238 / 238 | 25 (13) | 0 | +8,1 | sim | sim | seção / seção | 17:30 / 17:00 |
| CE | SÃO GONÇALO DO AMARANTE | 0036 | 0054 | não | troca+desvio | 123 x 119 | 22 / 18 | 173 x 91 | 15 | 282 / 279 | 335 / 335 | 25 (13) | 0 | +4,2 | sim | sim | seção / seção | 17:48 / 17:01 |
| MA | LAGO DA PEDRA | 0074 | 0066 | não | troca+desvio | 124 x 86 | 10 / 12 | 170 x 62 | 1 | 232 / 233 | 299 / 299 | 24 (13) | 0 | +6,4 | sim | sim | seção / seção | 17:25 / 17:00 |
| CE | CAUCAIA | 0120 | 0361 | não | troca | 244 x 49 | 7 / 12 | 276 x 24 | 13 | 312 / 313 | 349 / 349 | 24 (13) | 0 | +2,8 | sim | sim | seção / seção | 18:51 / 17:00 |
| AL | BELO MONTE | 0029 | 0023 | não | troca+desvio | 192 x 76 | 8 / 12 | 163 x 113 | 6 | 288 / 282 | 359 / 360 | 23 (22) | 0 | -7,5 | sim | sim | seção / seção | 18:03 / 17:01 |
| BA | ANTAS | 0082 | 0205 | não | troca | 147 x 110 | 9 / 13 | 187 x 87 | 6 | 279 / 280 | 348 / 348 | 23 (13) | 0 | +3,4 | sim | sim | seção / seção | 17:23 / 17:02 |
| PA | SÃO MIGUEL DO GUAMÁ | 0011 | 0420 | não | troca+desvio | 131 x 83 | 7 / 11 | 167 x 62 | 6 | 232 / 235 | 277 / 277 | 21 (13) | 0 | +4,2 | sim | sim | seção / seção | 17:24 / 17:04 |
| CE | CAUCAIA | 0120 | 0315 | não | troca | 146 x 86 | 7 / 12 | 184 x 65 | 8 | 251 / 257 | 305 / 305 | 21 (13) | 0 | +4,0 | sim | sim | seção / seção | 17:39 / 17:00 |
| AM | IPIXUNA | 0045 | 0063 | não | troca+desvio | 135 x 61 | 12 / 19 | 167 x 2 | 28 | 227 / 197 | 335 / 335 | 20 (13) | 0 | +7,3 | sim | sim | reserva / reserva | 18:58 / 15:02 |
| AL | BELO MONTE | 0029 | 0056 | não | troca+desvio | 207 x 100 | 12 / 12 | 172 x 133 | 11 | 331 / 316 | 393 / 393 | 20 (22) | 0 | -6,8 | sim | sim | seção / seção | 19:09 / 17:03 |
| BA | RIACHÃO DAS NEVES | 0182 | 0063 | não | troca | 160 x 58 | 5 / 8 | 189 x 38 | 5 | 231 / 232 | 278 / 278 | 20 (13) | 0 | +4,0 | sim | sim | seção / seção | 17:51 / 17:03 |
| CE | SÃO GONÇALO DO AMARANTE | 0036 | 0262 | não | troca | 143 x 94 | 12 / 12 | 182 x 74 | 12 | 261 / 268 | 320 / 320 | 20 (13) | 0 | +2,7 | sim | sim | seção / seção | 17:40 / 17:00 |
| AL | BELO MONTE | 0029 | 0053 | não | troca+desvio | 192 x 87 | 13 / 22 | 170 x 131 | 10 | 314 / 311 | 386 / 386 | 19 (22) | 0 | -7,4 | sim | sim | seção / seção | 19:05 / 17:02 |
| PI | SANTO ANTÔNIO DE LISBOA | 0028 | 0094 | não | troca+desvio | 172 x 56 | 5 / 11 | 147 x 83 | 8 | 244 / 238 | 295 / 295 | 19 (22) | 0 | -6,1 | sim | sim | seção / seção | 17:03 / 17:05 |
| BA | PONTO NOVO | 0149 | 0183 | não | troca | 178 x 99 | 13 / 9 | 222 x 80 | 7 | 299 / 309 | 389 / 389 | 19 (13) | 0 | +3,8 | sim | sim | seção / seção | 17:51 / 17:02 |
| PA | BOM JESUS DO TOCANTINS | 0100 | 0315 | não | troca | 170 x 44 | 6 / 8 | 202 x 25 | 1 | 228 / 228 | 302 / 302 | 19 (13) | 0 | +3,7 | sim | sim | seção / seção | 17:44 / 17:01 |
| AL | MACEIÓ | 0003 | 0061 | 22->13 | troca | 124 x 149 | 9 / 25 | 167 x 129 | 10 | 307 / 306 | 375 / 375 | 19 (13) | 0 | +3,5 | sim | sim | seção / seção | 18:19 / 17:03 |
| CE | SÃO GONÇALO DO AMARANTE | 0036 | 0281 | não | troca | 133 x 91 | 14 / 7 | 166 x 65 | 9 | 245 / 240 | 304 / 304 | 19 (13) | 0 | +3,3 | sim | sim | seção / seção | 17:06 / 17:02 |
| CE | SÃO GONÇALO DO AMARANTE | 0036 | 0070 | não | troca | 133 x 105 | 12 / 17 | 185 x 86 | 7 | 267 / 278 | 336 / 336 | 19 (13) | 0 | +3,3 | sim | sim | seção / seção | 17:33 / 17:00 |
| AM | ATALAIA DO NORTE | 0042 | 0013 | não | troca | 144 x 82 | 11 / 7 | 175 x 62 | 8 | 244 / 245 | 325 / 325 | 19 (13) | 0 | +2,0 | sim | sim | seção / seção | 16:24 / 15:01 |
| AL | BELO MONTE | 0029 | 0047 | não | troca+desvio | 201 x 89 | 10 / 17 | 171 x 124 | 10 | 317 / 305 | 392 / 392 | 18 (22) | 0 | -6,9 | sim | sim | seção / seção | 19:17 / 17:03 |
| PI | SANTO ANTÔNIO DE LISBOA | 0028 | 0093 | não | troca+desvio | 190 x 61 | 3 / 7 | 169 x 85 | 4 | 261 / 258 | 296 / 296 | 18 (22) | 0 | -5,0 | sim | sim | seção / seção | 17:44 / 17:01 |

### Todas as viradas atípicas de 2026 (56 seções)

| UF | Município | Zona | Seção | Virada | Critério | 1º turno 13 x 22 | Outros / BN 1º | 2º turno 13 x 22 | BN 2º | Comparec. 1º / 2º | Aptos 1º / 2º | Troca mín. (a favor de) | Troca estrita | z | Mesma urna | Mesma carga | Urna 1º / 2º | Encerramento local 1º / 2º |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| AC | SANTA ROSA DO PURUS | 0003 | 0095 | 22->13 | troca+desvio | 102 x 105 | 9 / 4 | 174 x 47 | 7 | 220 / 228 | 339 / 337 | 55 (13) | 0 | +10,2 | sim | sim | seção / seção | 15:02 / 15:01 |
| AC | MANOEL URBANO | 0003 | 0160 | 13->22 | troca+desvio | 112 x 55 | 0 / 3 | 48 x 104 | 21 | 170 / 173 | 238 / 236 | 46 (22) | 0 | -16,2 | sim | sim | seção / seção | 15:03 / 15:02 |
| AM | BARCELOS | 0018 | 0037 | 22->13 | troca+desvio | 37 x 171 | 8 / 15 | 84 x 71 | 35 | 231 / 190 | 377 / 377 | 39 (13) | 0 | +14,2 | sim | sim | seção / seção | 19:05 / 16:00 |
| AL | MACEIÓ | 0003 | 0061 | 22->13 | troca | 124 x 149 | 9 / 25 | 167 x 129 | 10 | 307 / 306 | 375 / 375 | 19 (13) | 0 | +3,5 | sim | sim | seção / seção | 18:19 / 17:03 |
| CE | SÃO GONÇALO DO AMARANTE | 0036 | 0285 | 22->13 | troca | 105 x 144 | 17 / 11 | 140 x 122 | 13 | 277 / 275 | 336 / 336 | 18 (13) | 0 | +2,9 | sim | sim | seção / seção | 17:06 / 17:01 |
| PA | TAILÂNDIA | 0093 | 0166 | 22->13 | troca | 83 x 95 | 5 / 6 | 110 x 77 | 4 | 189 / 191 | 295 / 295 | 18 (13) | 0 | +2,8 | sim | sim | seção / seção | 17:20 / 17:04 |
| AC | FEIJÓ | 0007 | 0067 | 22->13 | troca+desvio | 35 x 59 | 0 / 4 | 52 x 14 | 7 | 98 / 73 | 155 / 155 | 17 (13) | 0 | +11,0 | sim | sim | seção / seção | 15:00 / 15:01 |
| SE | TOBIAS BARRETO | 0023 | 0087 | 22->13 | troca | 79 x 82 | 6 / 4 | 102 x 65 | 4 | 171 / 171 | 207 / 207 | 17 (13) | 0 | +3,8 | não | não | seção / reserva | 17:04 / 17:05 |
| CE | BARREIRA | 0052 | 0174 | 22->13 | troca | 145 x 151 | 7 / 8 | 177 x 134 | 2 | 311 / 313 | 344 / 344 | 17 (13) | 0 | +3,1 | sim | sim | seção / seção | 18:37 / 17:00 |
| PA | TAILÂNDIA | 0093 | 0180 | 22->13 | troca | 95 x 111 | 12 / 5 | 123 x 94 | 4 | 223 / 221 | 293 / 293 | 15 (13) | 0 | +2,2 | sim | sim | seção / seção | 17:32 / 17:02 |
| PA | BELÉM | 0030 | 0807 | 22->13 | troca+desvio | 116 x 117 | 27 / 15 | 165 x 102 | 7 | 275 / 274 | 358 / 358 | 14 (13) | 0 | +4,9 | sim | sim | seção / seção | 17:12 / 17:03 |
| AL | JUNQUEIRO | 0034 | 0215 | 22->13 | troca | 108 x 140 | 14 / 15 | 144 x 126 | 9 | 277 / 279 | 340 / 340 | 14 (13) | 0 | +3,4 | sim | sim | seção / seção | 17:13 / 17:00 |
| RR | PACARAIMA | 0007 | 0107 | 22->13 | troca | 76 x 94 | 5 / 1 | 94 x 60 | 4 | 176 / 158 | 198 / 198 | 13 (13) | 0 | +3,9 | sim | sim | seção / seção | 16:11 / 16:00 |
| CE | TIANGUÁ | 0081 | 0286 | 22->13 | troca | 97 x 125 | 11 / 14 | 138 x 112 | 6 | 247 / 256 | 296 / 296 | 13 (13) | 0 | +3,4 | sim | sim | seção / seção | 18:15 / 17:02 |
| AL | MACEIÓ | 0003 | 0016 | 22->13 | troca | 75 x 105 | 8 / 9 | 101 x 92 | 5 | 197 / 198 | 310 / 310 | 13 (13) | 0 | +3,3 | sim | sim | seção / seção | 17:08 / 17:00 |
| BA | LUÍS EDUARDO MAGALHÃES | 0205 | 0062 | 22->13 | troca | 112 x 133 | 2 / 6 | 136 x 120 | 3 | 253 / 259 | 321 / 321 | 13 (13) | 0 | +1,9 | sim | sim | seção / seção | 17:14 / 17:01 |
| PA | ORIXIMINÁ | 0038 | 0253 | 22->13 | troca | 97 x 118 | 11 / 7 | 127 x 104 | 1 | 233 / 232 | 315 / 315 | 13 (13) | 0 | +1,8 | sim | sim | seção / seção | 17:01 / 17:04 |
| PB | CABEDELO | 0057 | 0115 | 22->13 | desvio | 100 x 131 | 18 / 20 | 147 x 119 | 6 | 269 / 272 | 338 / 338 | 12 (13) | 0 | +4,8 | sim | sim | seção / seção | 17:09 / 17:09 |
| BA | SENTO SÉ | 0096 | 0079 | 22->13 | troca+desvio | 68 x 74 | 4 / 5 | 84 x 54 | 7 | 151 / 145 | 175 / 175 | 12 (13) | 0 | +4,3 | sim | sim | seção / seção | 17:01 / 17:02 |
| AC | FEIJÓ | 0007 | 0089 | 22->13 | troca | 91 x 134 | 9 / 15 | 113 x 101 | 14 | 249 / 228 | 341 / 341 | 12 (13) | 0 | +2,7 | sim | sim | seção / seção | 15:12 / 15:05 |
| PA | IPIXUNA DO PARÁ | 0049 | 0239 | 22->13 | troca | 104 x 106 | 5 / 9 | 130 x 94 | 7 | 224 / 231 | 318 / 318 | 12 (13) | 0 | +1,9 | sim | sim | seção / seção | 17:08 / 17:04 |
| PA | TAILÂNDIA | 0093 | 0096 | 22->13 | troca | 111 x 114 | 8 / 5 | 135 x 100 | 1 | 238 / 236 | 296 / 296 | 12 (13) | 0 | +1,3 | sim | sim | seção / seção | 18:38 / 17:02 |
| AM | IRANDUBA | 0056 | 0185 | 22->13 | troca+desvio | 55 x 70 | 8 / 4 | 74 x 54 | 4 | 137 / 132 | 176 / 176 | 11 (13) | 0 | +4,6 | sim | sim | seção / seção | 16:16 / 16:07 |
| AM | MANAUS | 0063 | 0822 | 22->13 | desvio | 113 x 147 | 29 / 6 | 153 x 122 | 9 | 295 / 284 | 365 / 365 | 11 (13) | 0 | +4,4 | sim | sim | seção / seção | 16:28 / 16:02 |
| MA | BURITICUPU | 0095 | 0098 | 22->13 | troca | 98 x 108 | 9 / 4 | 119 x 94 | 3 | 219 / 216 | 279 / 279 | 11 (13) | 0 | +2,9 | sim | sim | seção / seção | 17:05 / 17:02 |
| BA | EUNÁPOLIS | 0203 | 0125 | 22->13 | troca | 80 x 86 | 2 / 7 | 94 x 74 | 6 | 175 / 174 | 218 / 218 | 11 (13) | 0 | +2,7 | sim | sim | seção / seção | 17:03 / 17:01 |
| MA | GRAJAÚ | 0015 | 0033 | 22->13 | troca | 99 x 113 | 5 / 5 | 117 x 99 | 3 | 222 / 219 | 267 / 267 | 11 (13) | 0 | +2,3 | sim | sim | seção / seção | 17:02 / 17:00 |
| PA | ORIXIMINÁ | 0038 | 0229 | 22->13 | troca | 84 x 112 | 12 / 12 | 116 x 98 | 3 | 220 / 217 | 294 / 294 | 11 (13) | 0 | +2,3 | sim | sim | seção / seção | 17:11 / 17:02 |
| PI | CASTELO DO PIAUÍ | 0034 | 0162 | 22->13 | troca+desvio | 57 x 69 | 3 / 2 | 77 x 55 | 6 | 131 / 138 | 177 / 177 | 10 (13) | 0 | +5,4 | sim | sim | seção / seção | 17:02 / 17:03 |
| MA | ITINGA DO MARANHÃO | 0098 | 0210 | 22->13 | troca+desvio | 77 x 89 | 6 / 2 | 94 x 71 | 1 | 174 / 166 | 234 / 234 | 10 (13) | 0 | +4,4 | sim | sim | seção / seção | 17:21 / 17:00 |
| CE | PACAJUS | 0049 | 0356 | 22->13 | desvio | 92 x 96 | 7 / 28 | 127 x 86 | 14 | 223 / 227 | 261 / 261 | 10 (13) | 0 | +4,0 | sim | sim | seção / seção | 17:16 / 17:03 |
| CE | ITAPAJÉ | 0041 | 0035 | 22->13 | troca | 76 x 102 | 8 / 9 | 95 x 92 | 8 | 195 / 195 | 237 / 237 | 10 (13) | 0 | +2,3 | sim | sim | seção / seção | 17:03 / 17:01 |
| PB | JOÃO PESSOA | 0077 | 0214 | 22->13 | desvio | 90 x 126 | 15 / 20 | 138 x 118 | 3 | 251 / 259 | 297 / 296 | 8 (13) | 0 | +4,6 | sim | sim | seção / seção | 17:03 / 17:01 |
| BA | MARAÚ | 0078 | 0206 | 22->13 | desvio | 47 x 53 | 3 / 4 | 60 x 45 | 1 | 107 / 106 | 145 / 145 | 7 (13) | 0 | +4,2 | sim | sim | seção / seção | 17:20 / 17:03 |
| PA | BENEVIDES | 0078 | 0494 | 22->13 | desvio | 28 x 35 | 2 / 1 | 40 x 26 | 4 | 66 / 70 | 81 / 81 | 6 (13) | 0 | +8,1 | sim | sim | reserva / reserva | 17:03 / 17:01 |
| PA | BELÉM | 0097 | 0553 | 22->13 | desvio | 35 x 36 | 5 / 4 | 49 x 26 | 1 | 80 / 76 | 88 / 88 | 6 (13) | 0 | +7,1 | sim | sim | seção / seção | 17:03 / 17:00 |
| BA | CAMPO FORMOSO | 0053 | 0274 | 22->13 | desvio | 41 x 53 | 2 / 12 | 60 x 42 | 1 | 108 / 103 | 134 / 134 | 6 (13) | 0 | +5,9 | não | não | seção / reserva | 17:03 / 17:01 |
| PB | JOÃO PESSOA | 0077 | 0274 | 22->13 | desvio | 97 x 136 | 25 / 31 | 147 x 130 | 19 | 289 / 296 | 347 / 347 | 6 (13) | 0 | +4,2 | sim | sim | seção / seção | 17:11 / 17:01 |
| PB | JOÃO PESSOA | 0077 | 0140 | 22->13 | desvio | 77 x 81 | 13 / 20 | 111 x 74 | 5 | 191 / 190 | 218 / 218 | 6 (13) | 0 | +4,1 | sim | sim | seção / seção | 17:03 / 17:01 |
| PA | RURÓPOLIS | 0068 | 0149 | 22->13 | desvio | 14 x 28 | 5 / 3 | 24 x 23 | 3 | 50 / 50 | 57 / 57 | 5 (13) | 0 | +8,2 | sim | sim | seção / seção | 17:04 / 17:03 |
| PA | ITAITUBA | 0034 | 0376 | 22->13 | desvio | 21 x 40 | 4 / 3 | 32 x 28 | 1 | 68 / 61 | 91 / 91 | 5 (13) | 0 | +6,6 | sim | sim | seção / seção | 17:00 / 17:01 |
| AL | MACEIÓ | 0054 | 0554 | 22->13 | desvio | 20 x 33 | 2 / 2 | 33 x 29 | 0 | 57 / 62 | 70 / 70 | 4 (13) | 0 | +5,8 | sim | sim | seção / seção | 17:06 / 17:01 |
| MA | AMARANTE DO MARANHÃO | 0099 | 0152 | 22->13 | desvio | 55 x 72 | 5 / 16 | 71 x 53 | 9 | 148 / 133 | 220 / 220 | 4 (13) | 0 | +5,4 | sim | sim | seção / seção | 17:07 / 17:02 |
| RR | BOA VISTA | 0005 | 0765 | 22->13 | desvio | 33 x 48 | 1 / 2 | 40 x 34 | 0 | 84 / 74 | 89 / 89 | 4 (13) | 0 | +5,2 | sim | sim | seção / seção | 16:12 / 16:05 |
| PA | CONCEIÇÃO DO ARAGUAIA | 0024 | 0402 | 22->13 | desvio | 28 x 39 | 2 / 0 | 34 x 29 | 1 | 69 / 64 | 88 / 88 | 4 (13) | 0 | +4,6 | sim | sim | seção / seção | 17:01 / 17:00 |
| AL | MACEIÓ | 0003 | 0337 | 22->13 | desvio | 77 x 107 | 21 / 20 | 113 x 97 | 9 | 225 / 219 | 265 / 265 | 4 (13) | 0 | +4,0 | sim | sim | seção / seção | 17:07 / 17:02 |
| AM | EIRUNEPÉ | 0011 | 0094 | 22->13 | desvio | 61 x 68 | 19 / 9 | 87 x 58 | 5 | 157 / 150 | 234 / 234 | 3 (13) | 0 | +5,1 | sim | sim | seção / seção | 15:06 / 15:03 |
| PI | MILTON BRANDÃO | 0012 | 0211 | 13->22 | desvio | 64 x 63 | 8 / 16 | 62 x 85 | 5 | 151 / 152 | 165 / 165 | 2 (22) | 0 | -4,5 | sim | sim | seção / seção | 17:00 / 17:00 |
| AL | CORURIPE | 0007 | 0153 | 22->13 | desvio | 32 x 49 | 7 / 3 | 42 x 40 | 2 | 91 / 84 | 103 / 103 | 2 (13) | 0 | +4,3 | sim | sim | seção / seção | 17:15 / 17:01 |
| BA | CAMAÇARI | 0170 | 0262 | 22->13 | desvio | 37 x 61 | 6 / 3 | 40 x 20 | 2 | 107 / 62 | 119 / 68 | 0 (13) | 0 | +14,9 | sim | sim | seção / seção | 17:02 / 17:01 |
| AM | FONTE BOA | 0010 | 0070 | 22->13 | desvio | 20 x 21 | 1 / 0 | 19 x 14 | 0 | 42 / 33 | 52 / 52 | 0 (13) | 0 | +7,0 | sim | sim | seção / seção | 16:02 / 16:01 |
| AM | MANAUS | 0068 | 0777 | 13->22 | desvio | 51 x 40 | 6 / 0 | 42 x 44 | 5 | 97 / 91 | 123 / 123 | 0 (13) | 0 | -5,5 | sim | sim | seção / seção | 16:01 / 16:00 |
| AC | CRUZEIRO DO SUL | 0004 | 0382 | 22->13 | desvio | 48 x 53 | 0 / 11 | 41 x 27 | 12 | 112 / 80 | 182 / 182 | 0 (13) | 0 | +4,6 | sim | sim | seção / seção | 15:01 / 15:00 |
| AC | CRUZEIRO DO SUL | 0004 | 0297 | 22->13 | desvio | 59 x 64 | 5 / 6 | 51 x 33 | 9 | 134 / 93 | 182 / 182 | 0 (13) | 0 | +4,6 | sim | sim | seção / seção | 15:02 / 15:04 |
| AC | CRUZEIRO DO SUL | 0004 | 0470 | 22->13 | desvio | 39 x 61 | 6 / 3 | 45 x 42 | 6 | 109 / 93 | 148 / 146 | 0 (13) | 0 | +4,6 | sim | sim | seção / seção | 15:01 / 15:00 |
| BA | ITABELA | 0189 | 0082 | 13->22 | desvio | 132 x 126 | 20 / 15 | 132 x 150 | 16 | 293 / 298 | 377 / 377 | 0 (13) | 0 | -4,1 | sim | sim | seção / seção | 17:48 / 17:03 |

### Atípicos de 2026 com urna diferente entre os turnos

| UF | Município | Zona | Seção | Virada | Critério | 1º turno 13 x 22 | Outros / BN 1º | 2º turno 13 x 22 | BN 2º | Comparec. 1º / 2º | Aptos 1º / 2º | Troca mín. (a favor de) | Troca estrita | z | Mesma urna | Mesma carga | Urna 1º / 2º | Encerramento local 1º / 2º |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| AL | SANTANA DO IPANEMA | 0019 | 0234 | não | troca | 133 x 79 | 10 / 9 | 162 x 62 | 9 | 231 / 233 | 287 / 287 | 17 (13) | 0 | +3,0 | não | não | seção / seção | 17:07 / 17:04 |
| BA | BREJOLÂNDIA | 0190 | 0023 | não | troca | 171 x 79 | 4 / 5 | 196 x 64 | 6 | 259 / 266 | 348 / 348 | 14 (13) | 0 | +1,9 | não | não | reserva / seção | 19:57 / 17:05 |
| BA | CAMPO FORMOSO | 0053 | 0274 | 22->13 | desvio | 41 x 53 | 2 / 12 | 60 x 42 | 1 | 108 / 103 | 134 / 134 | 6 (13) | 0 | +5,9 | não | não | seção / reserva | 17:03 / 17:01 |
| PI | SANTO ANTÔNIO DE LISBOA | 0028 | 0095 | não | desvio | 164 x 52 | 2 / 13 | 149 x 74 | 4 | 231 / 227 | 273 / 273 | 11 (22) | 0 | -5,0 | não | não | seção / reserva | 17:17 / 17:01 |
| SE | TOBIAS BARRETO | 0023 | 0087 | 22->13 | troca | 79 x 82 | 6 / 4 | 102 x 65 | 4 | 171 / 171 | 207 / 207 | 17 (13) | 0 | +3,8 | não | não | seção / reserva | 17:04 / 17:05 |

## Limitações

- **Cobertura parcial de 2026.** Esta execução tem 145.489 seções do 2º turno, quase todas do Norte e Nordeste (mais 79% do PA e 1% de SP). Os números de "Brasil" de 2026 não representam o país; as comparações mais limpas são por UF e a linha "UFs comparáveis". O script deve ser rodado de novo quando a coleta terminar.
- **Movimento de 2026 parcialmente estimado.** O movimento do município é calculado com as seções já coletadas; em municípios com coleta incompleta (sobretudo no PA) ele pode mudar.
- **Seções agregadas.** O pareamento é por UF, município, zona e seção. Se a agregação de seções mudou entre os turnos, aptos e comparecimento mudam e a seção pode parecer atípica sem que nada tenha acontecido com os votos. Há 14.577 seções de 2026 (e 58.701 de 2022) com aptos diferentes entre turnos, na maioria por diferença pequena; a coluna `aptos_1` / `aptos_2` está nas listas.
- **Troca mínima é conta líquida.** Ela não identifica eleitores. Uma troca mínima alta é compatível com eleitores que faltaram em um turno e outros que vieram no outro. Só a troca estrita é obrigatória, e ela ainda supõe que o eleitorado da seção é o mesmo (salvo agregação).
- **O modelo de esperado é simples.** É uma regressão logística com cinco variáveis, ajustada em uma única eleição. Ele acerta o total de viradas no sentido do movimento (2022 e 2026), mas superestima as viradas contra o candidato dominante na região (2022 Nordeste: 0,72; 2026: 0,46) e as probabilidades intermediárias. Razões observado ÷ esperado por UF entre 0,3 e 4 aconteceram em 2022.
- **2022 e 2026 não são eleições iguais.** Em 2022 o movimento entre turnos foi para o 22 (com a mesma intensidade, em sentido oposto); em 2026 foi para o 13. Os candidatos 22 são diferentes. A régua é a mesma, mas a comparação é com o comportamento normal de seções entre dois turnos, não com o mesmo eleitorado.
- **Critérios de atípico são de triagem.** Os limiares (10 votos e 5% do comparecimento; |z| > 4; 30 seções por município) foram fixados antes de olhar as seções e aplicados igualmente aos dois anos. Com 145 mil seções, alguns casos extremos são esperados por acaso; ser atípico não é evidência de irregularidade, é motivo para conferir o boletim impresso.
- **Fonte única.** Os votos vêm dos BUs publicados pelo TSE. A conferência independente (QR Code do boletim impresso, ata da mesa) não foi feita aqui para as seções listadas.
