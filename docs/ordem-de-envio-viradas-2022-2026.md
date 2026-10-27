# Ordem de chegada das seções e a "virada" da curva acumulada (2022 e 2026)

Verificação das duas alegações de um vídeo que circula após o 2º turno de 2026, gravado por quem se apresenta como doutor em matemática aplicada, sobre o 2º turno de 2022:

1. **"Só houve uma inversão."** Ao reproduzir as 472 mil urnas "na ordem de envio", o percentual acumulado dos dois candidatos teria se cruzado uma vez só. Ao embaralhar a ordem mais de 3 mil vezes, haveria "várias inversões". Daí a conclusão de que "o dado disponibilizado já chega adulterado".
2. **"Vales igualmente espaçados."** Num zoom da curva, apareceriam quedas regulares ("1, 2, 3, 4, 5, 6, 7 igualmente espaçados") do candidato 22, atribuídas a "um algoritmo que liga e desliga" e "penaliza linearmente".

O vídeo mostra um gráfico Plotly (`go.Scatter(x=data2.index, y=data2['total'])`) da fração acumulada de cada candidato contra o índice da urna, com o cruzamento perto da urna 285 mil e um zoom entre as urnas 72 mil e 83 mil.

## Dados

- **2022, 2º turno:** 470.834 seções com BU (`ref_secoes_2022`, `ref_votos_2022`). A ordem é a hora de emissão do BU convertida para Brasília (`emissao - fuso_offset`). O horário de recebimento pelo TSE em 2022 não está na base.
- **2026, 2º turno:** 499.205 seções com BU (`v_votos_t2_secao`). A ordem é o horário de recebimento publicado no `aux.json` (`v_bu_ultima.recebimento`), que é a ordem real de chegada ao TSE.
- **Código:** exportação em `scripts/ele2026/ordem_envio_ch.sql` e análise em `scripts/ele2026/ordem_envio.py` (rodada no London, saída em `data/parquet/2026/t2/ordem_envio/resultado.json`).
- **Medida:** "viradas" são as trocas de sinal de `acumulado_22 - acumulado_13`. Ordens aleatórias: 3.000 permutações completas. Ordens embaralhadas por janela: 1.000 permutações que só trocam seções que chegaram no mesmo minuto (ou na mesma janela de 10 ou 30 min) e mantêm a sequência das janelas.

## Resultados

| | 2022 | 2026 |
|---|---:|---:|
| Seções | 470.834 | 499.205 |
| Viradas na ordem real | 14 | 26 |
| Última virada na ordem real (seção nº) | 285.980 | 259.204 |
| **3.000 ordens aleatórias:** viradas, média | 15,0 | 6,8 |
| última virada, mediana (seção nº) | **146** | **34** |
| última virada, percentil 99 (seção nº) | 2.563 | 564 |
| **Embaralhado só dentro do mesmo minuto:** viradas, média | 15,4 | 16,7 |
| última virada, mediana (seção nº) | **281.980** | **257.050** |
| Seções consecutivas do mesmo município, ordem real | 39,0% | 35,6% |
| Seções consecutivas do mesmo município, ordem aleatória | 0,54% | 0,51% |

### 1. A ordem aleatória não produz "várias inversões ao longo do processo"

Com a ordem embaralhada, a curva acumulada estabiliza no resultado final logo no começo, pela lei dos grandes números. Todas as viradas acontecem nas primeiras centenas de seções (mediana da última virada na seção 146 em 2022 e 34 em 2026; em 99% das simulações, antes da seção 2.563 e 564). Depois disso as linhas ficam paralelas e nunca mais se cruzam.

O que o vídeo descreve, um cruzamento lá pela urna 285 mil, é justamente o que a ordem aleatória **não** produz. Esse cruzamento tardio é a marca de uma ordem **não aleatória**, e a apuração não chega em ordem aleatória: chegam primeiro as regiões que fecham e transmitem antes, e o eleitorado de cada região vota de forma diferente.

### 2. A ordem de chegada explica a virada tardia sozinha

Mantendo apenas "quais seções chegaram em cada minuto" e embaralhando todo o resto, a última virada cai na seção 281.980 (2022) e 257.050 (2026), em mediana. Na ordem real, é na 285.980 e na 259.204. Ou seja, a posição da virada é reproduzida só pelo calendário de chegada das seções, sem nenhuma alteração de voto.

### 3. Os "vales" são lotes de um mesmo município

Na ordem real, 39% das seções chegam logo depois de outra do mesmo município. Na ordem aleatória, são 0,5%. As seções de uma zona eleitoral chegam em lote, e um lote de um município com fatia do 22 abaixo da média puxa a curva para baixo de uma vez. Depois, seções de outros lugares a recuperam devagar. É o desenho em dente de serra mostrado no zoom.

As 10 maiores quedas da curva depois da seção 20 mil (janelas de 300 seções) são todas assim:

| Ano | Seção | Queda (pp) | Fatia do 22 nas 300 seções | Município com mais seções no lote |
|---|---:|---:|---:|---|
| 2022 | 26.690 | -0,122 | 41,1% | MG 41238 (11 seções) |
| 2022 | 39.637 | -0,113 | 36,9% | SP 71072 (São Paulo, 32) |
| 2022 | 36.746 | -0,111 | 38,1% | SP 71072 (São Paulo, 39) |
| 2022 | 30.257 | -0,111 | 40,3% | CE 13897 (Fortaleza, 17) |
| 2022 | 21.407 | -0,109 | 44,1% | SP 71072 (São Paulo, 20) |
| 2026 | 23.047 | -0,131 | 39,0% | PR 75353 (29 seções) |
| 2026 | 21.389 | -0,108 | 41,6% | PA 04278 (41) |
| 2026 | 24.851 | -0,090 | 42,0% | AM 02550 (Manaus, 41) |
| 2026 | 31.961 | -0,088 | 40,0% | AM 02550 (Manaus, 23) |
| 2026 | 26.778 | -0,083 | 41,7% | PA 04278 (31) |

O espaçamento "regular" vem do ritmo de transmissão de grandes zonas, não de um algoritmo. Cada vale tem nome e endereço: dá para abrir os BUs daquele lote e conferir voto a voto.

### 4. A curva não altera o total

A curva acumulada só depende da **ordem** das seções. O ponto final é a soma dos BUs, que são assinados por cada urna. Em 2026, a soma dos 499.205 BUs assinados bate exatamente com o resultado oficial (13: 64.256.232; 22: 59.826.041; ver `docs/certificados-2turno-2026.md`). Se o "dado fosse modificado em algum lugar" entre a urna e a divulgação, a soma dos BUs assinados divergiria do total oficial, e isso não acontece. Para 2022 a base de referência deste estudo tem 470.834 das cerca de 472 mil seções, por isso não comparo a soma com o oficial aqui.

## Conclusão

As duas "provas" do vídeo não se sustentam com os dados:

- A virada única e tardia é o comportamento **esperado** quando as seções chegam em ordem geográfica e temporal. Uma ordem aleatória a teria jogado para as primeiras centenas de seções, ao contrário do que o vídeo afirma.
- Os vales são lotes de seções de um mesmo município chegando juntos, identificáveis um a um.
- O formato da curva não tem como indicar adulteração do total, porque o total é a soma de BUs assinados que podem ser conferidos individualmente.

O que este estudo **não** cobre: a integridade do software da urna, que é outra questão, tratada nos demais documentos do projeto.
