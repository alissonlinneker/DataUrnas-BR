# O equipamento afeta o voto? Modelo, troca, recarga e reserva de urna (2026)

Eleição presidencial de 2026, 1º turno em 04/10 e 2º turno em 25/10 (13 x 22),
com 2022 como linha de base. Pergunta: o modelo da urna, a troca de urna entre os
turnos, a recarga, a carga no dia da eleição, o certificado divergente, a carga
ausente do GEDAI e as urnas de contingência mudam o resultado da seção quando se
compara com seções vizinhas que não passaram por isso?

Margem final do 2º turno, conferida na soma dos BUs usada aqui: 64.256.232 (13)
menos 59.826.041 (22) = **4.430.191 votos**.

## 1. Resumo

| Hipótese | Efeito estimado (controle correto) | IC 95% | Votos equivalentes | Pior caso do IC sobre a margem | Gravidade |
|---|---|---|---|---|---|
| Urna antiga (UE2013) vota diferente, 2º turno 2026 | +0,78 p.p. para o 13 no mesmo local | +0,14 a +1,34 | 24.403 | 83.260 (1,9% da margem) | Baixa: diferença já existia em 2022 com outras urnas (placebo +0,64 p.p.) |
| Urna UE2015, 2º turno 2026 | +0,57 p.p. para o 13 no mesmo local | -0,04 a +1,08 | 126.271 | 477.208 (10,8%) | Baixa: placebo de 2022 +0,52 p.p.; swing 2022 para 2026 = +0,05 p.p. |
| Modelo muda o swing 1º para 2º turno 2026 | -0,10 a +0,00 p.p. | inclui zero em todos | menos de 21 mil | 182.462 (4,1%) | Nenhum efeito |
| Modelo antigo em 2022 ("urnas antigas votam diferente") | +1,0 a +1,8 p.p. por zona; **+0,04 a +0,12 p.p. por local** | todos os IC por local incluem zero | | | Alegação desaparece com o controle geográfico correto |
| Seção que trocou de urna (urna de seção) | +0,05 p.p. no swing | -0,06 a +0,14 | 183 | 1.113 | Nenhum efeito |
| Seção que trocou para urna de reserva | -0,06 p.p. no swing | -0,15 a +0,02 | -435 | 2.163 | Nenhum efeito |
| Mesma urna recarregada entre os turnos (370) | +0,15 p.p. no swing | -0,09 a +0,39 | 142 | 740 | Nenhum efeito |
| Urna de contingência no 2º turno (5.714) | -0,02 p.p. no swing do 13; +0,05 p.p. em brancos e nulos | -0,07 a +0,04; +0,01 a +0,10 | -229; +799 brancos/nulos | 2.061 | Sem efeito partidário; aumento mínimo de brancos e nulos |
| Carga fora do GEDAI (862) | +0,16 p.p. contra o mesmo município | p de permutação 0,037 (otimista) | 344 | 3.957 | Desprezível e explicado pela geografia |
| Carga em 25/10 (5) | -0,74 a +0,40 p.p. conforme o controle | todos incluem zero exceto um (4 clusters) | -8 a +4 | 42 | Nenhum efeito mensurável |
| Certificado divergente (3) | -0,06 a +0,38 p.p. | inclui zero | 3 | 37 | Nenhum efeito |
| Mesma urna física em outra seção (81) | coeficiente do 1º turno da seção de origem: -0,07 (EP 0,045) | placebo: +0,07 (EP 0,042) | | | Nenhum "arrasto" do resultado da urna |

Conclusão objetiva: nenhum dos efeitos de equipamento testados tem tamanho capaz
de alterar a margem de 4.430.191 votos, nem no pior extremo do intervalo de
confiança. O maior número absoluto (UE2015, pior caso 477 mil votos de margem,
10,8%) vem de uma diferença de nível que **já existia nas mesmas seções em 2022**,
quando muitas delas votavam em outras urnas, e que **não se altera** entre 2022 e
2026 nem entre o 1º e o 2º turno de 2026. Isso indica eleitorado diferente, não
equipamento. Os efeitos estatisticamente detectáveis que restam são de dezenas a
poucas centenas de votos.

## 2. Dados e método

### Fontes

| Dado | Origem |
|---|---|
| 2º turno 2026 por seção (votos, aptos, comparecimento, local, tipo de urna, número interno, código de carga) | ClickHouse, `v_bu_ultima` e `v_votos_t2_secao` (499.205 seções) |
| 1º turno 2026 por seção (com modelo, local, tipo de urna, número interno, carga) | ClickHouse, `ref_secoes_2026_t1` e `ref_votos_2026_t1` |
| Modelo da urna no 2º turno | `.vsc` de cada seção: `data/parquet/2026/t2/software/secoes_software.parquet` (`modelo_vsc`), complementado por `data/parquet/2026/t2/certificados/secoes.parquet` |
| Data da carga e conferência do certificado | `data/parquet/2026/t2/certificados/secoes.parquet` |
| Carga fora do GEDAI (862), carga em 25/10 (5), gerador sem log (86) | `data/parquet/2026/t2/linha_tempo/nacional/gedai_bu_*.csv` (ver `docs/gedai-2turno-2026.md`) |
| 2022, dois turnos, com modelo e reserva | ClickHouse, `ref_secoes_2022` e `ref_votos_2022` |

Contagens no 2º turno: UE2020 200.504, UE2022 198.746, UE2015 87.500, UE2013
12.455 (pelo `.vsc`). Mesma urna nos dois turnos em 494.770 seções; dessas, só
2 têm modelo diferente entre o 1º turno (referência) e o `.vsc` do 2º turno.
Trocaram de urna 4.426 seções com BU de urna e número interno nos dois turnos
(1.608 terminaram o 2º turno com urna de seção e 2.818 com urna de reserva).
Seções "estáveis" (mesma urna, mesma carga, urna de seção, sem nenhuma marca):
490.611. Há 94.708 locais de votação; em 8.525 deles há mais de um modelo, com
71.498 seções: é só nesses locais que o efeito do modelo é identificado com
efeito fixo de local.

### Desfechos

- Fatia do 13 nos votos válidos (no 2º turno, válidos = 13 + 22; no 1º turno,
  todos os nominais) e fatia do 22 no 1º turno.
- Brancos e nulos sobre o comparecimento; abstenção sobre os aptos.
- Swing da seção: fatia do 13 em 13+22 no 2º turno menos a mesma fatia no 1º
  turno (e o mesmo para brancos+nulos). Como a seção é a mesma, o eleitorado
  se cancela; uma urna que adulterasse votos só no 2º turno apareceria aqui.

### Estimador

Mínimos quadrados ponderados (peso = votos do denominador do desfecho), com
efeito fixo geográfico e uma variável 0/1 por grupo (modelo, reserva ou
marcador). Referência do modelo: UE2020 em 2026 e "2020" em 2022. Controles
geográficos testados: local de votação (uf, município, zona, número do local),
zona, município, UF e nenhum. Erro padrão robusto por município e IC de 95% por
bootstrap de municípios (999 réplicas, semente 20261025). Como o local e a zona
ficam dentro de um município, reamostrar municípios preserva o desvio em relação
à média do grupo; o bootstrap usa as somas X'WX e X'Wy de cada município.

Tradução para votos: efeito (fração) x votos de 13+22 das seções do grupo. Na
margem, mover uma fração d dos votos de um candidato para o outro altera a
margem em 2 x d x votos. "Pior caso" usa o extremo do IC mais distante de zero.

Grupos concentrados (zona inteira marcada, sem vizinho de controle no mesmo
local) são comparados com o resto do município e da UF, com a posição da zona
entre todas as zonas da UF em 2026 e, para as mesmas seções, em 2022, e com um
teste de permutação (sorteio de seções do município ou da UF). A permutação
ignora a correlação espacial, então o p dela é otimista.

## 3. Modelo de urna

### 3.1 2º turno de 2026, fatia do 13 nos válidos

| Modelo (x UE2020) | Sem controle | Mesma zona | Mesmo local | IC 95% (local) | Seções identificadas (local) |
|---|---|---|---|---|---|
| UE2013 | +2,41 | -1,25 | **+0,78** | +0,14 a +1,34 | 6.211 em 3.108 locais |
| UE2015 | +0,46 | -0,77 | +0,57 | -0,04 a +1,08 | 19.479 em 3.197 locais |
| UE2022 | +0,30 | +0,20 | -0,04 | -0,11 a +0,05 | 22.684 em 5.392 locais |

O sinal troca conforme o controle: sem controle o UE2013 parece favorecer o 13
em 2,4 p.p.; dentro da zona, favorece o 22 em 1,25 p.p.; dentro do local,
favorece o 13 em 0,78 p.p. Diferenças que mudam de sinal com a escala
geográfica são típicas de composição do eleitorado, não de equipamento.

Brancos, nulos e abstenção no 2º turno, dentro do local: todos os coeficientes
de modelo ficam entre -0,04 e +0,05 p.p., com IC incluindo zero (brancos: UE2013
+0,047 [-0,031; +0,142]; nulos: UE2013 +0,010 [-0,095; +0,120]; abstenção:
UE2013 -0,007 [-1,02; +0,78]).

### 3.2 1º turno de 2026

Dentro do local, o padrão é o mesmo do 2º turno, com o mesmo tamanho: UE2013
+0,79 p.p. para o 13 [+0,07; +1,35] e -0,87 p.p. para o 22 [-1,49; -0,22];
UE2015 +0,60 [-0,10; +1,13] para o 13 e -0,63 [-1,19; -0,01] para o 22. Brancos
e nulos: nenhum efeito de modelo dentro do local.

### 3.3 Placebo com 2022: o eleitorado já era diferente

As 460.120 seções de 2026 que existem com a mesma chave (UF, município, zona,
seção) em 2022 permitem perguntar: as seções que em 2026 receberam UE2013 ou
UE2015 já votavam diferente em 2022, com a urna que tinham na época?

| Modelo de 2026 (x UE2020), dentro do mesmo local de 2026 | 2º turno 2022 (placebo) | 2º turno 2026, mesma amostra | Swing 2022 para 2026 |
|---|---|---|---|
| UE2013 | +0,64 [-0,07; +1,23] | +0,68 [-0,14; +1,28] | +0,05 [-0,46; +0,47] |
| UE2015 | +0,52 [-0,17; +1,07] | +0,58 [-0,17; +1,14] | +0,05 [-0,45; +0,46] |
| UE2022 | +0,05 [-0,03; +0,13] | -0,02 [-0,09; +0,06] | -0,06 [-0,12; +0,00] |

A diferença de 2026 já estava presente, com praticamente o mesmo tamanho, em
2022. O swing por modelo entre os dois anos é zero. O swing 1º para 2º turno de
2026 por modelo também é zero (UE2013 -0,07 [-0,41; +0,25]; UE2015 -0,10 [-0,42;
+0,21]; UE2022 +0,00 [-0,04; +0,05], dentro do local). Uma urna que alterasse
votos teria de fazer isso de forma idêntica em 2022 (com outro software e, em
boa parte, outro equipamento) e nos dois turnos de 2026, o que não tem
mecanismo plausível. A leitura consistente com os dados é que seções com urna
mais antiga diferem de eleitorado das vizinhas do mesmo prédio (por exemplo,
seções mais antigas versus seções criadas recentemente).

### 3.4 A alegação de 2022 ("urnas antigas votam diferente")

Fatia do 13 nos válidos, 2º turno de 2022, modelo de 2022 contra o modelo 2020:

| Modelo 2022 | Sem controle | Mesma zona | Mesmo local (local de 2026 da mesma seção) |
|---|---|---|---|
| 2009 | +2,11 [-0,50; +4,71] | +0,98 [+0,49; +1,61] | +0,06 [-0,65; +0,63] |
| 2010 | +4,82 [+2,45; +7,06] | +1,03 [+0,61; +1,65] | +0,04 [-0,68; +0,61] |
| 2011 | +4,87 [+2,07; +7,59] | +1,30 [+0,69; +2,03] | -0,01 [-0,73; +0,56] |
| 2013 | +2,29 [-1,45; +5,91] | +1,36 [+0,83; +2,11] | +0,12 [-0,61; +0,70] |
| 2015 | +2,62 [+0,19; +4,88] | +1,81 [+1,35; +2,56] | +0,07 [-0,65; +0,67] |

No 1º turno de 2022 o retrato é o mesmo (sem controle +3,3 a +5,7 p.p.; por zona
+1,3 a +2,3 p.p.). Sem controle, a diferença de 2022 chega a 5 p.p., o número que
circulou como "urnas antigas votam no 13". Dentro da zona ela cai para 1 a 2
p.p., e dentro do mesmo local de votação some (todos os coeficientes entre -0,01
e +0,12 p.p., IC incluindo zero). As urnas antigas estavam concentradas em
regiões que votam mais no 13; dentro do mesmo prédio, o modelo não faz
diferença. Limitação: a referência de 2022 não traz o local de votação; usou-se
o local de 2026 da mesma seção, o que só pode diluir o controle (seções que
mudaram de prédio), nunca criar um efeito nulo artificial.

## 4. Experimento natural: troca, recarga e marcas de carga

Desfecho principal: swing da fatia do 13 (13+22), 2º menos 1º turno. Controle:
as 490.611 seções estáveis. Quatro controles geográficos; abaixo o de local
(onde há vizinhos) e o de município.

| Grupo | Seções | Identificadas no local | Swing, local | IC 95% | Swing, município | IC 95% | Votos equivalentes (local) | Pior caso na margem |
|---|---|---|---|---|---|---|---|---|
| Trocou de urna, urna de seção | 1.608 | 1.527 | +0,05 | -0,06 a +0,14 | -0,02 | -0,12 a +0,08 | 183 | 1.113 |
| Trocou de urna, urna de reserva | 2.818 | 2.654 | -0,06 | -0,15 a +0,02 | -0,04 | -0,12 a +0,03 | -435 | 2.163 |
| Mesma urna recarregada (14 a 24/10) | 370 | 339 | +0,15 | -0,09 a +0,39 | +0,13 | -0,12 a +0,38 | 142 | 740 |
| Carga fora do GEDAI, todas | 862 | 95 | +0,05 | -0,48 a +0,49 | -0,25 | -0,73 a +0,17 | 116 | 3.155 |
| Carga fora do GEDAI, outras estações | 110 | 68 | -0,13 | -0,64 a +0,35 | -0,58 | -1,30 a +0,16 | -34 | 655 |
| Carga em 25/10 | 5 | 4 | -0,74 | -1,87 a -0,07 | -0,38 | -1,84 a +0,67 | -8 | 40 |
| Certificado diferente do número interno | 3 | 3 | +0,38 | -1,41 a +2,36 | -0,06 | -1,43 a +2,18 | 3 | 37 |

Brancos+nulos (swing): nenhum grupo acima com efeito fora do ruído, exceto a
carga de 25/10 com efeito fixo de local (+1,65 p.p., 4 seções, 18 votos), que
perde significância com qualquer outro controle; com 4 a 5 municípios o
bootstrap não é confiável.

O resultado da carga em 25/10 com efeito fixo de local (-0,74 p.p., IC excluindo
zero) se apoia em 4 seções de 4 municípios e não se sustenta por zona, município
ou UF. Seção a seção (`pequenos_grupos.csv`): Atibaia 0016/0436 tem swing de
+4,65 p.p., abaixo das 3 seções estáveis do local (média +6,52 p.p., que diferem
pouco entre si, por isso z = -3,8), mas exatamente na média da zona (+4,75 p.p., z =
-0,05). As demais ficam entre z = -1,2 e +0,7. Efeito máximo plausível: 42 votos
de margem.

As três seções com certificado diferente do número interno (Santa Maria de
Jetibá ES 0009/0085, Nova Iguaçu RJ 0027/0139, Guarulhos SP 0393/0312) têm
swing de +1,1, +4,1 e +6,2 p.p., com z contra a zona de -0,96, +0,21 e +0,87.
Nenhuma é atípica.

### 4.1 Grupos concentrados (zona inteira marcada)

Swing do 13 (13+22), em p.p.; diferença contra o resto da UF e do município em
2026 e, para as mesmas seções, em 2022:

| Grupo | Seções | 2026 x UF | 2026 x município | 2022 x UF (mesmas seções) | Dif. em dif. 2026 - 2022 | Posição da zona na UF, 2026 | Impacto na margem (x UF) |
|---|---|---|---|---|---|---|---|
| Parauapebas PA, zona 0106 | 358 | +1,14 | -0,40 | +0,25 | +0,89 | 92,5º percentil (z = 1,51) de 160 zonas | 2.107 |
| Guarulhos SP, zona 0176 | 267 | +0,25 | -0,14 | +0,30 | -0,05 | 58º percentil (z = 0,34) de 779 | 338 |
| Zona 0339 MG (Jequeri, Piedade de Ponte Nova, Sericita, Urucânia) | 96 | -1,15 | sem controle | +0,87 | -2,02 | 18º a 56º percentil | -526 (favorece o 22) |
| Monte Alegre PA, zona 0019 | 31 | +1,15 | +1,06 (p = 0,011) | -0,86 | +2,01 | zona: 72,5º percentil | 143 |
| Gerador sem log (Jaguariaíva PR 0018 e 1 seção em Toledo MG) | 86 | +0,24 | +2,72 (1 seção) | +0,44 | -0,20 | 78º percentil (z = 0,84) | 99 |
| Sistema de Apuração no exterior (busa) | 27 | -2,90 [-5,07; -0,70] | sem controle | sem dado | | | -46 (favorece o 22) |

Leitura: Parauapebas tem swing para o 13 acima da média do Pará, mas abaixo das
outras zonas do próprio município; entre as 160 zonas do Pará, fica no 92º
percentil, sem nada de extremo. A zona 0339 de MG andou menos para o 13 que o
estado, isto é, contra quem venceu. Monte Alegre: 31 seções com +1,06 p.p. sobre
o resto do município (p de permutação 0,011, otimista por ignorar a vizinhança),
equivalendo a 71 votos (143 de margem). As 27 seções do Sistema de Apuração no
exterior andaram menos para o 13 que as demais seções do exterior (-2,9 p.p., 23
votos). Em todos os casos o volume é irrelevante diante da margem.

## 5. Urnas de contingência (reserva)

| Medida | Efeito | IC 95% | Votos |
|---|---|---|---|
| 2º turno 2026, nível da fatia do 13, mesmo local | -0,11 p.p. | -0,21 a +0,01 | -1.506 |
| 2º turno 2026, swing do 13, mesmo local | -0,02 p.p. | -0,07 a +0,04 | -229 |
| 2º turno 2026, swing de brancos+nulos, mesmo local | **+0,05 p.p.** | +0,01 a +0,10 | +799 |
| 1º turno 2026, fatia do 22, mesmo local | +0,17 p.p. | +0,02 a +0,33 | +1.230 |
| 1º turno 2026, fatia do 13, mesmo local | -0,09 p.p. | -0,23 a +0,06 | -619 |
| 1º turno 2026, abstenção, mesmo local | **+0,80 p.p.** | +0,54 a +1,07 | 7.894 eleitores |
| 1º turno 2026, brancos, mesmo local | -0,08 p.p. | -0,12 a -0,04 | -600 |
| Reserva no 1º turno, swing do 13 para o 2º turno | +0,02 p.p. | -0,06 a +0,10 | 169 |
| 2022, 1º turno, abstenção, mesma zona | +0,95 p.p. | +0,82 a +1,06 | |
| 2022, 2º turno, fatia do 13, mesmo local de 2026 | +0,02 p.p. | -0,05 a +0,08 | |

A troca por urna de contingência não muda a preferência entre 13 e 22. O que
ela muda, de forma consistente em 2022 e 2026, é o comparecimento no 1º turno:
seções cuja urna falhou e foi substituída têm cerca de 0,8 a 0,95 p.p. a mais de
abstenção que as vizinhas (eleitor que desiste com a fila parada). O efeito do
1º turno de 2026 sobre a fatia do 22 (+0,17 p.p., cerca de 1.230 votos) está no
limite da significância, não aparece para o 13 nem no 2º turno, e não sobrevive
a qualquer correção por comparações múltiplas (444 estimativas). No 2º
turno, brancos+nulos sobem 0,05 p.p. nas seções com reserva (cerca de 800 votos
no país), sem direção partidária.

## 6. Mesma urna física em seções diferentes

Só 81 seções votaram no 2º turno com uma urna (mesmo número interno) que no 1º
turno estava em outra seção; as demais trocas usaram urnas que não votaram em
nenhuma seção no 1º turno. Das 81, a origem estava no mesmo local em 4, na mesma
zona em 41 e em outro município em 28.

Se a urna "carregasse" o comportamento da seção anterior, o 2º turno da seção
nova acompanharia o 1º turno da seção de origem. Regressão nas 77 seções com
placebo disponível: fatia do 13 no 2º turno = 0,973 x (1º turno da própria seção,
EP 0,020) - 0,072 x (1º turno da seção de origem da urna, EP 0,045) + 0,070 x (1º
turno de uma seção sorteada no mesmo local da origem, EP 0,042). O coeficiente
da origem é zero e igual em tamanho ao do placebo. A distância mediana entre o
2º turno e o 1º turno da própria seção é 2,6 p.p.; até o 1º turno da origem,
6,2 p.p. A seção nova fica mais perto da origem do que do placebo em 45% dos
casos (esperado: 50%). O resultado acompanha o eleitorado, não a máquina.

## 7. Dispersão geral

Resíduo do swing de cada seção contra a média das seções estáveis do mesmo
local: entre as 490.611 estáveis, só 0,0055% ficam mais de 10 p.p. fora. Em
nenhum grupo testado (trocas, recargas, reservas, cargas fora do GEDAI, cargas
de 25/10, certificados) há seção com resíduo acima de 10 p.p.; a fração é zero
em todos, exceto reserva no 2º turno (2 de 5.372) e reserva no 1º turno (2 de
2.848), proporções da mesma ordem das estáveis.

## 8. O que NÃO deu efeito

- Modelo de urna sobre o swing entre os turnos de 2026 e entre 2022 e 2026.
- Modelo de urna sobre brancos, nulos e abstenção dentro do local.
- Modelo de 2022 dentro do mesmo local (a alegação de 2022 se desfaz).
- Troca de urna entre os turnos (urna de seção ou de reserva).
- Recarga da mesma urna entre 14 e 24/10.
- Carga no dia 25/10, certificado divergente, gerador sem log publicado.
- Carga ausente do GEDAI como um todo e por estação, quando comparada com o
  próprio município (Parauapebas e Guarulhos abaixo do município; MG 0339 contra
  o 13).
- Urna de contingência sobre a escolha entre 13 e 22.
- Mesma urna física em outra seção.

## 9. Limitações

- Efeito fixo de local só identifica onde há variação dentro do local. No
  modelo, isso cobre 71.498 seções em 8.525 locais; por isso o IC do local é
  mais largo que o da zona.
- A alocação de urnas dentro do local não é aleatória. O placebo de 2022 mostra
  que essa seleção existe e explica o nível; ela não afeta o swing.
- Grupos com 3 a 5 seções e bootstrap com poucos municípios não sustentam
  inferência; foram analisados também seção a seção.
- Grupos em zona inteira (Parauapebas, MG 0339, Jaguariaíva) não têm vizinho de
  controle no local; comparação feita com o município, a UF e a própria zona em
  2022. Isso não separa um efeito de carga de um movimento regional, mas limita
  o tamanho máximo do efeito.
- 444 estimativas: alguns IC excluírem zero por acaso é esperado (cerca
  de 5%). Os poucos casos marginais têm dezenas a poucos milhares de votos.
- 2022 sem local de votação na referência; usado o local de 2026 da mesma
  seção (460.120 seções casadas).
- A análise mede efeitos sobre os votos registrados no BU. Não testa
  adulteração que fosse idêntica em todas as urnas e todas as seções, que não
  deixa assinatura comparativa.

## 10. Reprodução

No servidor de processamento (temporários em `/dev/shm`):

```sh
python3 scripts/ele2026/efeito_urna.py extrair --dir /dev/shm/efeito_urna/ch
uv run --no-project --with pandas,numpy,pyarrow python3 scripts/ele2026/efeito_urna.py analisar \
    --dir /dev/shm/efeito_urna/ch \
    --software secoes_software.parquet --certificados secoes.parquet \
    --gedai-dir <pasta com gedai_bu_*.csv> --saida /dev/shm/efeito_urna/out
```

Saídas em `data/parquet/2026/t2/efeito_urna/` (fora do git):
`estimativas.parquet`/`.csv` (todas as 444 estimativas, com IC robusto e por
bootstrap, seções identificadas, votos equivalentes e impacto na margem),
`secoes_2026.parquet` (seções pareadas com marcadores e swings),
`pequenos_grupos.csv`, `grupos_concentrados.csv`,
`zonas_grupos_concentrados.csv`, `urna_outra_secao.parquet` e `resumo.json`.
Execução completa: cerca de 3 minutos com 48 processos.
