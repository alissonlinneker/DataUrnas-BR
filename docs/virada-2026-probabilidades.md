# A virada do 2º turno de 2026: aritmética, história e probabilidade

Pergunta: a virada de Lula no 2º turno de 2026 (perdeu o 1º turno por 2.224.965 votos e venceu o 2º por 4.430.191) é matematicamente impossível ou rara a ponto de indicar fraude? Existe algum caminho, pelos dados publicados, para estimar a chance de Flávio Bolsonaro ter sido o vencedor real?

Este documento junta os estudos feitos para responder a isso. Cada item remete ao estudo completo, com método, dados e scripts.

## Resumo

| Pergunta | Resposta curta | Estudo |
|---|---|---|
| A virada fecha nos números? | Sim, voto a voto. Lula ganhou 10.376.694 votos entre os turnos e Flávio 3.721.538. A soma (14.098.232) é exatamente o que ficou disponível: eleitores dos outros candidatos, brancos e nulos a menos e comparecimento maior. | seção 1 |
| Algum candidato ganhou mais votos do que havia para ganhar, em alguma seção? | Não nas seções com o mesmo eleitorado nos dois turnos. | [viradas por seção](viradas-1t-2t-2026.md), [forense estatística](forense-estatistica-2026.md) |
| O líder do 1º turno nunca perdeu o 2º? | Para presidente, no Brasil, de fato nunca tinha perdido (6 de 6 desde 2002, mais 1989). Para governador, perdeu 29 vezes em 103 disputas. Em disputas com margem abaixo de 3 pontos, o líder perdeu em 12 de 23. Fora do Brasil, há 31 casos conferidos de líder que perdeu o 2º turno, 7 deles com margem menor que a de 2026. | seção 2 |
| A fatia de Lula nos votos disponíveis (73,6%) é anormal? | Não. Em 2022, quem estava atrás (Bolsonaro) ficou com 69,8%. Entre as 103 disputas de governador, 73,6% está no percentil 81. | seção 3 |
| As pesquisas indicavam outro resultado? | As de véspera davam Flávio com 50,8% a 51% dos válidos; Lula fez 51,79%. Erro de cerca de 2,8 pontos, na mesma ordem do erro de 2022 no 1º turno. | seção 4 |
| Os apoios a Flávio não deveriam ter levado os votos? | Apoio declarado não transfere voto de forma automática. A estimativa por seção indica que os eleitores do 3º colocado foram mais para Lula. Brancos e nulos que voltaram foram, em boa parte, para Lula. | seção 5 |
| Quanta fraude seria necessária para inverter o resultado, e ela apareceria? | No mínimo 2.215.096 votos trocados. Concentrada em parte das seções ou numa região, apareceria. Só uma troca quase igual em todas as urnas, de 4 a 5 votos por seção, passaria sem deixar padrão estatístico. | seção 6 |
| A ordem de chegada dos BUs mostra injeção? | Não. A curva da noite é reproduzida só com a geografia de chegada e o voto esperado de cada seção. | [chegada dos BUs](chegada-bus-2026.md) |
| Votos sem biometria foram inseridos? | Nenhum valor impossível, e os eleitores extras sem digital votaram como os com digital. | [biometria](biometria-1t-2t-2026.md) |
| Eleitorado maior que a população favoreceu Lula? | O contrário: nesses municípios a virada para Lula foi menor. | seção 7 |
| Os arquivos das urnas conferem entre si? | Sim. Imagem do BU, BU, RDV e log conferem nas 499.207 seções dos dois turnos; as divergências pontuais têm causa documentada e não mudam votos. | [pacote nacional](pacote-nacional-imgbu-logs-2026.md), [RDV e log](rdv-log-2026.md) |
| Qual a probabilidade de Flávio ter vencido de verdade? | Não existe número honesto para isso. A estatística descarta as fraudes grandes que deixam rastro; a fraude que não deixa rastro estatístico só pode ser descartada pela verificação do software. | seção 8 |

## 1. A aritmética da virada

Votos de presidente, totais oficiais conferidos com os BUs de todas as seções.

| | 1º turno | 2º turno | Variação |
|---|---:|---:|---:|
| Flávio (22) | 56.104.503 | 59.826.041 | +3.721.538 |
| Lula (13) | 53.879.538 | 64.256.232 | +10.376.694 |
| Diferença (13 menos 22) | -2.224.965 | +4.430.191 | +6.655.156 |

Os 14.098.232 votos que os dois somaram a mais vieram de:

- 9,32 milhões de eleitores de outros candidatos no 1º turno;
- 1,82 milhão de brancos e nulos a menos;
- 2,96 milhões de comparecimentos a mais.

Lula precisava de 57,9% desse total para empatar: metade de 14,10 milhões mais metade da desvantagem do 1º turno, ou seja, 7,05 milhões mais 1,11 milhão, que dão 8,16 milhões. Teve 73,6%. Não há nada impossível nessa conta. A pergunta real é se 73,6% é plausível, o que as seções 2 a 5 tratam.

## 2. Base histórica: o líder do 1º turno perde o 2º?

Fonte: arquivos de votação por município e zona do TSE (`votacao_candidato_munzona` e `detalhe_votacao_munzona`, 1994 a 2026). Uma linha por disputa de 2º turno para presidente, governador e prefeito, com o mesmo par de finalistas do 1º turno. Script: [scripts/historico/viradas_segundo_turno.py](../scripts/historico/viradas_segundo_turno.py). Dados: [data/parquet/historico/](../data/parquet/historico/).

São 454 disputas de 1994 a 2024, das quais 116 foram viradas (25,6%).

| Cargo | Disputas | Viradas |
|---|---:|---:|
| Presidente (2002 a 2022) | 6 | 0 |
| Governador | 103 | 29 |
| Prefeito (municípios acima de 200 mil eleitores) | 345 | 87 |

**Presidente.** É verdade que, até 2026, nenhum líder do 1º turno tinha perdido o 2º para presidente (1989 também não: Collor liderou e venceu). Mas são só 7 casos, e nenhum tinha margem pequena: a menor era a de 2022 (5,2 pontos). Com 7 observações, "nunca aconteceu" não diz quase nada sobre a probabilidade num caso de margem de 1,87 ponto. A comparação útil são as disputas com margem parecida.

**Taxa de virada por margem do 1º turno** (presidente e governador):

| Margem do líder no 1º turno (pontos) | Disputas | Viradas | Taxa |
|---|---:|---:|---:|
| 0 a 1 | 10 | 5 | 50% |
| 1 a 2 | 10 | 5 | 50% |
| 2 a 3 | 3 | 2 | 67% |
| 3 a 5 | 11 | 3 | 27% |
| 5 a 7,5 | 20 | 7 | 35% |
| 7,5 a 10 | 11 | 3 | 27% |
| 10 a 15 | 16 | 3 | 19% |
| 15 a 20 | 18 | 0 | 0% |
| acima de 20 | 10 | 1 | 10% |

Viradas de governador com margem abaixo de 3 pontos: DF 1994, PA 1994, SE 1994, RS 1998, RR 2002, AP 2010, RR 2010, AM 2014, PA 2014, PB 2014, SC 2018 e MS 2022. Em 2026, além da Presidência, houve virada para governador no RN (margem de 0,78 ponto) e no TO (1,58).

**Modelo logístico.** A probabilidade de o líder perder, ajustada só pela margem do 1º turno, nas 109 disputas de presidente e governador, é de **48%** para a margem de 2026 (intervalo de 95%: 34% a 63%). Incluindo a fatia dos outros candidatos, 40% (24% a 59%). Com todas as 454 disputas, 30% a 40%, conforme o modelo. Em nenhum modelo a virada de 2026 é rara: é perto de cara ou coroa. Detalhes em [modelo_logistico.json](../data/parquet/historico/modelo_logistico.json).

**Outros países.** Uma pesquisa em fontes abertas (resultados conferidos página a página) achou 31 eleições presidenciais em que o líder do 1º turno perdeu o 2º. Em 7 delas a margem do 1º turno era menor que a do Brasil em 2026:

| País e ano | Margem no 1º turno (pontos) | Resultado do 2º turno |
|---|---:|---|
| Chipre 2008 | 0,22 | Christofias 53,37 x Kasoulides 46,63 |
| Lituânia 2019 | 0,37 | Nausėda 66,53 x Šimonytė 33,47 |
| Libéria 2023 | 0,39 | Boakai 50,64 x Weah 49,36 |
| Colômbia 1998 | 0,41 | Pastrana 50,34 x Serpa 46,58 |
| Gana 2008 | 1,21 | Atta Mills 50,23 x Akufo-Addo 49,77 |
| Croácia 2014/15 | 1,27 | Grabar-Kitarović 50,74 x Josipović 49,26 |
| Polônia 2025 | 1,82 | Nawrocki 50,89 x Trzaskowski 49,11 |

Outras 5 tiveram margem entre 2 e 3 pontos: Chile 2021, França 1981 e 1995, Chile 2025 e Argentina 2015. Há viradas com margem bem maior, como Peru 2016 (18,8 pontos), Romênia 2025 (20,0) e Portugal 1986 (20,9).

### Correções feitas na base histórica

Ao rodar a base, dois defeitos de leitura dos arquivos do TSE apareceram e foram corrigidos antes de qualquer conclusão:

1. Em 2002 e 2010, as linhas de presidente e governador trazem o código do município em `SG_UE`. Lido como estava, cada município virava uma "disputa" (2.788 em 2002). A unidade da disputa passou a ser definida pelo cargo: Brasil para presidente, UF para governador e município para prefeito.
2. Alguns municípios pequenos têm linhas de turno 2 que não são 2º turno (por exemplo, Cerro Grande/RS em 2020, com 2.346 votos). Como só há 2º turno de prefeito acima de 200 mil eleitores (Constituição, art. 29, II), essas linhas foram excluídas.

O arquivo de 2016 também não abria com a codificação latin-1; a leitura passou a converter cada arquivo de cp1252 para UTF-8.

## 3. A fatia dos votos disponíveis que ficou com quem estava atrás

"Votos disponíveis" é o que os dois finalistas somaram a mais no 2º turno. A tabela mostra quanto disso ficou com quem estava em 2º lugar no 1º turno.

| Ano | Líder do 1º turno | 2º colocado | Margem (pontos) | Votos disponíveis | Fatia do 2º colocado |
|---|---|---|---:|---:|---:|
| 2002 | Lula | Serra | 23,2 | 27.003.425 | 50,6% |
| 2006 | Lula | Alckmin | 7,0 | 9.207.486 | -26,3% (Alckmin perdeu votos) |
| 2010 | Dilma | Serra | 14,3 | 18.680.200 | 56,6% |
| 2014 | Dilma | Aécio | 8,0 | 27.377.394 | 59,0% |
| 2018 | Bolsonaro | Haddad | 16,8 | 24.219.692 | 64,8% |
| 2022 | Lula | Bolsonaro | 5,2 | 10.220.504 | 69,8% |
| 2026 | Flávio | Lula | 1,9 | 14.098.232 | 73,6% |

Em 2022, Bolsonaro, que estava atrás, ficou com 69,8% dos votos disponíveis e não virou porque a margem era de 5,2 pontos. Em 2026, Lula ficou com 73,6%, 3,8 pontos acima, numa margem de 1,9 ponto. Entre as 103 disputas de governador, 19% tiveram fatia do 2º colocado maior que 73,6%.

## 4. Pesquisas de véspera

As últimas pesquisas antes do 2º turno davam Flávio na frente: Datafolha com 51% x 49% dos válidos e AtlasIntel com 49,9% x 48,4% do total. Lula fez 51,79% dos válidos. O erro foi de cerca de 2,8 pontos na fatia de Lula.

Erro desse tamanho já aconteceu no Brasil sem contestação dos números: no 1º turno de 2022, a última Datafolha dava Bolsonaro com 36% dos válidos, e ele teve 43,2%. Erro de pesquisa não é prova de nada, para nenhum lado. Ele mostra só que a disputa estava dentro da margem que as pesquisas conseguem medir.

Fontes: [Datafolha de véspera, Bem Paraná](https://www.bemparana.com.br/eleicoes-2026/datafolha-flavio-bolsonaro-tem-51-dos-votos-validos-e-lula-49-na-vespera-do-2o-turno/), [última AtlasIntel, BP Money](https://bpmoney.com.br/politica/flavio-499-lula-484-ultima-atlasintel-antes-urnas/), [Datafolha de véspera de 2022, O Povo](https://www.opovo.com.br/eleicoes-2022/2022/10/29/pesquisa-datafolha-lula-52-bolsonaro-48-no-2-turno.html).

## 5. Apoios declarados e para onde foram os votos

Os principais derrotados do 1º turno apoiaram Flávio (Cury, Caiado, Zema e Clariana); Renan Santos ficou neutro ([Viva](https://viva.com.br/politica/lula-x-flavio-bolsonaro-quem-os-candidatos-derrotados-apoiam-no-segundo-turno.html)). Apoio de candidato não obriga o eleitor. Em 2022, os eleitores de Tebet também não seguiram em bloco o apoio dela a Lula.

A regressão ecológica (Goodman) sobre as seções estima para onde foi cada grupo do 1º turno. Valores com efeito fixo de município entre parênteses. Detalhes em [forense estatística](forense-estatistica-2026.md#regressão-ecológica-goodman).

| Grupo do 1º turno de 2026 | Para Lula | Para Flávio |
|---|---:|---:|
| 3º colocado (70) | 0,567 (0,528) | 0,285 (0,305) |
| 4º (14) | 0,428 (0,321) | 0,436 (0,350) |
| 5º (55) | 0,416 (0,354) | 0,532 (0,575) |
| Branco | 0,881 (0,673) | 0,114 (-0,013) |
| Nulo | 0,661 (0,608) | 0,113 (0,114) |
| Abstenção | 0,089 (0,119) | 0,038 (0,044) |

Lula e Flávio mantiveram praticamente todos os seus eleitores do 1º turno (coeficientes de 0,99 a 1,03). A diferença veio dos eleitores do 3º colocado, dos brancos e nulos que voltaram a escolher e dos ausentes do 1º turno. Isso é padrão de mobilização e de voto útil, e aparece espalhado pelo país, não concentrado em seções. É inferência ecológica: não identifica eleitor nenhum e é frágil para candidatos pequenos.

## 6. Quanta fraude seria necessária, e se ela apareceria

Para Flávio vencer, pelo menos 2.215.096 votos teriam de ter saído dele e ido para Lula (metade da margem, mais um). A simulação aplicou essa troca aos votos do 1º turno de cada seção, de várias formas, e mediu se a distribuição da variação entre turnos ficaria diferente da observada. Script: [scripts/ele2026/simulacao_inversao.py](../scripts/ele2026/simulacao_inversao.py). Dados: [simulacao_inversao.json](../data/parquet/2026/t2/simulacao_inversao.json).

| Cenário | Votos trocados por seção alterada | Desvio-padrão da variação (pontos) | Seções acima de 4 desvios |
|---|---:|---:|---:|
| Observado em 2026 | | 2,37 | 664 |
| Todas as seções, troca uniforme | 4,4 | 2,61 | 667 |
| 50% das seções, sorteadas | 8,9 | 3,22 | 125 |
| 25% das seções | 17,8 | 4,18 | 1.008 |
| 10% das seções | 44,5 | 6,24 | 43.079 |
| 5% das seções | 89,0 | 8,66 | 24.816 |
| Só no Nordeste | | 3,54 | |

- Uma fraude concentrada em parte das seções, ou numa região, deixaria a variação entre seções muito mais espalhada que a observada e que a de 2022. Isso não aparece.
- Só uma troca quase igual em todas as urnas, de 4 a 5 votos por seção, passaria sem padrão estatístico visível. Isso exigiria adulterar o software de todas as urnas, e nenhum teste estatístico consegue descartar essa hipótese.

## 7. Eleitorado maior que a população adulta

Em 2.866 municípios, o eleitorado de 2026 é maior que a população com 12 anos ou mais no Censo 2022 (excesso somado de 2,44 milhões). Se votos em nome de ausentes tivessem favorecido Lula, esses municípios teriam virada maior. Aconteceu o contrário: variação da fatia de Lula de 2,05 pontos nesses municípios, contra 3,15 no resto. A correlação entre o excesso de eleitores e a virada é negativa (-0,24 dentro de cada UF). Os casos extremos, como Davinópolis (GO), com 2,5 eleitores por adulto, estão na lista de pedidos ao TSE em [mapa de verificações](mapa-verificacoes-2026.md). Script: [scripts/ele2026/eleitorado_populacao.py](../scripts/ele2026/eleitorado_populacao.py).

## 8. A probabilidade de Flávio ter sido o vencedor real

Não existe um número honesto para essa probabilidade. Qualquer valor exigiria supor uma chance de fraude antes de olhar os dados, e o resultado seria só reflexo dessa suposição. O que os dados permitem é separar dois tipos de fraude:

1. **Fraude que deixa rastro nos dados publicados:** votos inseridos em seções escolhidas, mesários votando por ausentes, BUs trocados na totalização, arquivos adulterados depois da eleição. Todas as verificações deste projeto buscam isso e nenhuma encontrou:
   - imagem do BU, BU, RDV e log conferem entre si nas 499.207 seções dos dois turnos;
   - os arquivos assinados conferem com as assinaturas das urnas;
   - os totais oficiais conferem com a soma dos BUs;
   - a variação entre turnos não tem a dispersão que uma troca concentrada de 2,2 milhões de votos produziria;
   - nem a ordem de chegada, nem a biometria, nem o eleitorado inflado mostram efeito a favor de Lula.

   Para esse tipo, a probabilidade de uma fraude capaz de inverter o resultado ter passado despercebida é muito baixa. O poder de detecção está medido em cada estudo, por exemplo cerca de 200 mil votos para inserção sem biometria.
2. **Fraude que não deixa rastro estatístico:** um software adulterado que trocasse poucos votos por urna, de forma igual, e assinasse tudo de forma coerente. RDV, BU e log concordariam entre si e com a assinatura. Isso não pode ser descartado pelos dados; só pela verificação do software (código-fonte, compilação e lacração, hashes publicados) e pelos Testes de Integridade feitos no dia da eleição. Os limites dessa verificação estão em [cadeia de confiança](cadeia-de-confianca-2026.md). Os relatórios dos Testes de Integridade saem nos TREs até 24/11/2026 e no TSE até 23/01/2027.

Conclusão: a virada não é matematicamente impossível nem estatisticamente rara. Pela margem do 1º turno, a história do Brasil e de outros países dá algo perto de 50% de chance de virada. A fatia dos votos disponíveis que Lula conquistou é alta, mas próxima da de 2022 e dentro do que acontece em disputas de governador. As fraudes que deixariam rastro não aparecem. A que não deixaria rastro depende da auditoria do software, que este projeto documenta mas não consegue fazer sozinho.
