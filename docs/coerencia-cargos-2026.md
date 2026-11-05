# Coerência entre cargos dentro do mesmo BU (2026)

Até aqui só o cargo de Presidente tinha sido decodificado dos boletins de urna (BU) de 2026. Este relatório decodifica todos os cargos de cada BU do pacote nacional do TSE e faz duas perguntas:

1. Dentro de um mesmo BU, os cargos concordam entre si? Todo eleitor que assina a folha vota em todos os cargos da cédula, então o comparecimento tem de ser o mesmo em todos eles, os aptos têm de bater, e cada cargo tem de fechar: nominais + brancos + nulos (+ legenda nos cargos proporcionais) = comparecimento, ou duas vezes o comparecimento no Senado, que em 2026 elegeu duas vagas por UF.
2. No 2º turno das UFs com disputa de governador, a divisão de voto entre Presidente e Governador seção a seção tem algum padrão implausível, e como isso se compara com 2022?

## Resultado em uma tabela

| # | Checagem | 1º turno 2026 | 2º turno 2026 (6 UFs) | 2º turno 2022 (12 UFs, base) |
|---|---|---|---|---|
| 1 | BUs lidos | 499.207 (499.176 de urna + 31 do Sistema de Apuração), 0 falhas | 39.739, 0 falhas | 249.040 (4 do Sistema de Apuração), 0 falhas |
| 2 | Cargo que não fecha (soma dos votos diferente de vagas x comparecimento) | **0** | **0** | **0** |
| 3 | Comparecimento diferente entre cargos da mesma eleição | **0** | **0** | **0** |
| 4 | Comparecimento federal x estadual diferente sem explicação | **0** | **0** | **0** |
| 5 | Aptos da seção (`qtdEleitoresAptosSecao`) diferentes entre eleições | **0** | **0** | **0** (campo ausente na spec de 2022) |
| 6 | Comparecimento acima dos aptos; aptos diferente de seção + trânsito | 0; 0 | 0; 0 | 0; 0 |
| 7 | Voto de legenda em cargo majoritário; voto negativo; tipo de voto desconhecido | 0; 0; 0 | 0; 0; 0 | 0; 0; 0 |
| 8 | Número de candidato com dígitos errados para o cargo, ou partido diferente dos 2 primeiros dígitos | 0 | 0 | 0 |
| 9 | Cargo repetido no BU; cargo faltando ou sobrando para a UF | 0; 0 | 0; 0 | 0; 0 |
| 10 | Soma dos BUs x arquivo oficial `detalhe_votacao_munzona` (aptos, comparecimento e brancos por município, zona e cargo) | igual em todas as combinações com BU | igual em todas | igual em todas, salvo 1 zona com seção não instalada |
| 11 | Seções com comparecimento do Presidente maior que o dos cargos estaduais | 17.237, todas explicadas pelo voto em trânsito de outra UF (165.584 votos só para Presidente) | 1.818 (24.727 votos) | 11.038 (92.371 votos) |
| 12 | Seções com resíduo de voto dividido Presidente x Governador acima de 4 desvios | não se aplica | 158 de 39.739 (0,40%) | 604 de 249.040 (0,24%) |

**Nenhum BU tem cargos em desacordo.** Em 787.986 BUs lidos (os três conjuntos somados), nenhum cargo deixou de fechar, nenhum comparecimento divergiu dentro de uma eleição e toda diferença entre a eleição federal e a estadual cabe exatamente no número de eleitores em trânsito de outra UF, que só votam para Presidente. Nenhuma divergência altera voto.

## Dados e método

| Item | Valor |
|---|---|
| Fonte | Pacote nacional do TSE, `https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes{2026,2022}/arqurnatot/bu_imgbu_logjez_rdv_vscmr_{ano}_{1t,2t}_{UF}.zip` |
| Leitura | Só os membros de BU (`-bu.dat` e `-busa.dat` em 2026, `.bu` e `.busa` em 2022), um pedido HTTP Range por membro a partir do diretório central do zip, com conferência do CRC-32; no máximo 4 conexões simultâneas ao CDN |
| Decodificação | `src/dataurnas/parsers` (ASN.1 BER, spec v2 em 2026, v1 em 2022), lendo cada bloco `resultadosVotacao` com o seu `tipoCargo` e o seu `qtdComparecimento` |
| Código | `scripts/ele2026/coerencia_cargos.py` (subcomandos `extrair` e `relatorio`) |
| Processamento | servidor de análise; saída bruta em `~/dataurnas-coerencia/` (um parquet por ano, turno e UF) |
| Saídas no repositório | `data/parquet/2026/coerencia_cargos/` |
| Escopo do 2º turno | as 6 UFs com 2º turno de governador em 2026 (AC, AM, DF, ES, RN, TO, conforme `data/parquet/historico/disputas_2t_2026.csv`) e as 12 de 2022 (AL, AM, BA, ES, MS, PB, PE, RO, RS, SC, SE, SP) |
| Data da leitura | 04/11/2026 |

### Estrutura do BU de 2026

O BU de 2026 traz duas eleições, cada uma com os seus aptos:

| Eleição (1º turno) | Bloco | Cargos |
|---|---|---|
| 6257, federal | majoritário | Presidente |
| 6259, estadual | proporcional | Deputado Federal, Deputado Estadual (Deputado Distrital no DF), com voto de legenda |
| 6259, estadual | majoritário | Senador, Governador |

No 2º turno são as eleições 6258 (Presidente) e 6260 (Governador). Seções do exterior (ZZ) só têm a eleição federal. O comparecimento é gravado uma vez por bloco, não por cargo, e a checagem 3 compara todos os blocos da mesma eleição.

A regra do Senado não foi suposta: a razão entre a soma dos votos e o comparecimento foi medida em cada linha (`razao_votos_comparecimento.csv`). Ela vale exatamente 2,0 nas 497.897 seções com Senador e exatamente 1,0 em todas as linhas de todos os outros cargos, nos três conjuntos.

### Por que o comparecimento do Presidente pode ser maior

O eleitor em trânsito habilitado em outra UF vota só para Presidente. Por isso o BU grava aptos maiores na eleição federal (`qtdEleitoresAptosTTE` maior) e o comparecimento federal pode ser maior que o estadual. A regra aplicada foi:

- `qtdEleitoresAptosSecao` igual nas duas eleições (quando o campo existe);
- `0 <= comparecimento_federal - comparecimento_outra_eleição <= aptos_federal - aptos_outra_eleição`.

Uma seção que violasse qualquer das duas condições seria divergência. Nenhuma violou.

## 1º turno de 2026

### Cargos decodificados

| Cargo | Seções | Aptos (soma dos BUs) | Comparecimento | Brancos |
|---|---|---|---|---|
| Presidente | 499.207 | 158.745.079 | 125.275.835 | 2.300.798 |
| Governador | 497.897 | 157.646.356 | 124.768.485 | 5.067.116 |
| Senador (2 votos por eleitor) | 497.897 | 157.646.356 | 124.768.485 | 18.678.856 |
| Deputado Federal | 497.897 | 157.646.356 | 124.768.485 | 6.445.372 |
| Deputado Estadual | 490.928 | 155.402.368 | 122.950.564 | 6.872.914 |
| Deputado Distrital (DF) | 6.969 | 2.243.988 | 1.817.921 | 77.934 |

Os 1.310 BUs do exterior (1.281 de urna e 29 do Sistema de Apuração) só têm Presidente, como esperado. As demais 497.897 seções têm exatamente os 5 cargos da sua UF.

A diferença de comparecimento entre Presidente e os cargos estaduais, 507.350, fecha por inteiro: 341.766 do exterior (só Presidente) e 165.584 eleitores em trânsito de outra UF, espalhados por 17.237 seções. Os maiores volumes de trânsito por UF foram SP (37.736), RJ (13.935), SC (13.609) e PR (11.842).

### Confronto com o resultado oficial

A soma dos BUs por município, zona e cargo foi comparada com `detalhe_votacao_munzona_2026` (TSE, gerado em 03/11/2026). Em todas as 31.743 combinações de município, zona e cargo que têm BU, aptos, comparecimento e brancos são iguais, em todos os seis cargos. Sobram 40 combinações do exterior que estão no arquivo oficial e não têm BU: são seções não instaladas (comparecimento 0 em todas; 423 aptos no total). O arquivo oficial lista 499.248 seções principais e 41 não instaladas; 499.248 menos 41 dá os 499.207 BUs lidos.

A primeira leitura considerava só `-bu.dat` e deixou de fora 31 BUs do Sistema de Apuração (`-busa.dat`): as 29 seções do exterior e as duas de MG já descritas em [pacote nacional](pacote-nacional-imgbu-logs-2026.md) (41238/0039/0168 e 50075/0047/0041). O confronto com o arquivo oficial acusou a falta delas, e depois de incluídas as diferenças zeraram. Esses 31 BUs também fecham em todos os cargos.

### Eleição municipal suplementar

Em 10 seções de PE (município 30015, zona 4) o BU tem uma terceira eleição (6261) com um cargo de código 25, que o parser não nomeia, ou seja, uma eleição municipal suplementar no mesmo dia. Ela também fecha: comparecimento igual ao da eleição estadual em 3 seções e menor em 7, sempre dentro da diferença de aptos (eleitores de fora do município não votam nela). Essa eleição não consta do arquivo `detalhe_votacao_munzona` das eleições gerais.

## 2º turno de 2026

| UF | Seções | Comparecimento Governador = Presidente | Diferente, explicado por trânsito | Votos só para Presidente | Diferente sem explicação |
|---|---|---|---|---|---|
| AC | 2.270 | 2.225 | 45 | 320 | 0 |
| AM | 8.157 | 7.531 | 626 | 2.199 | 0 |
| DF | 6.969 | 6.572 | 397 | 13.957 | 0 |
| ES | 9.844 | 9.686 | 158 | 3.560 | 0 |
| RN | 8.115 | 7.582 | 533 | 3.313 | 0 |
| TO | 4.384 | 4.325 | 59 | 1.378 | 0 |
| **Total** | **39.739** | **37.921** | **1.818** | **24.727** | **0** |

Governador e Presidente fecham em todas as 39.739 seções. Somados, os BUs dão para Presidente 12.504.794 aptos, 10.110.793 de comparecimento e 106.804 brancos, e para Governador 12.478.054, 10.086.066 e 228.427. Os seis números são iguais aos do arquivo oficial, e o número de seções é igual ao de seções principais do arquivo oficial nas seis UFs. A diferença de comparecimento entre os dois cargos (24.727) é exatamente a soma dos votos em trânsito só para Presidente.

Em TO, as 34 seções do município 95338 (zona 32) tiveram no mesmo dia uma eleição suplementar de prefeito (eleição 6286). O prefeito fecha nas 34 (7.703 de comparecimento); em 33 delas o comparecimento é igual ao do Presidente e em 1 é menor por um eleitor em trânsito.

## 2º turno de 2022 (linha de base)

As 249.040 seções das 12 UFs com 2º turno de governador em 2022 passaram em todas as checagens: 0 divergências. O comparecimento do Presidente foi maior que o do Governador em 11.038 seções, sempre dentro da diferença de aptos (92.371 votos só para Presidente). Houve eleição suplementar de prefeito em 871 seções (PE, RO, RS, SC e SP), todas coerentes. Contra o `detalhe_votacao_munzona_2022`, comparecimento e brancos batem em todas as combinações; a única diferença é de aptos em AM, município 2550, zona 68 (84 no Presidente e 81 no Governador), que tem uma seção não instalada sem BU.

## Voto dividido Presidente x Governador no 2º turno

### Método

Para cada seção: `p` = parte do 13 nos votos 13 + 22 para Presidente; `g` = parte, entre os dois finalistas a Governador, do candidato cuja votação anda junto com a do 13 (o sinal da correlação decide qual). O modelo, por UF, é

`logit(g) = efeito do município + beta x logit(p)`

com logit empírico (meio voto somado a cada lado), mínimos quadrados ponderados pelo inverso da variância binomial e efeito fixo de município. O resíduo de cada seção é padronizado pela variância binomial do Governador mais beta² vezes a do Presidente, multiplicada por um fator de sobredispersão estimado de forma robusta (mediana dos resíduos ao quadrado dividida pela mediana de uma qui-quadrado com 1 grau de liberdade). Uma seção só é marcada quando se afasta da relação Presidente x Governador do seu próprio município muito além do que o resto da UF mostra.

Uma primeira versão em escala linear marcava como atípicas seções com 99% para o 13 e 99% para o governador alinhado, porque a reta ajustada passava de 100%. A escala logit elimina esse artefato; os números abaixo são da versão logit.

Também foram contadas as seções com padrão oposto extremo (pelo menos 50 votos válidos nos dois cargos, um lado com 90% ou mais e o outro com 10% ou menos) e as seções com zero voto para um finalista.

### Resultado por UF

| Ano | UF | Seções | Governador alinhado ao 13 x outro | 13 na UF | Alinhado na UF | r entre seções | r dentro do município | beta (logit) | abs(z) > 4 | % | abs(z) > 6 | Opostos extremos |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026 | AC | 2.270 | 11 Mailza Assis x 10 Alan Rick | 33,4% | 66,2% | 0,32 | 0,42 | 0,27 | 11 | 0,48 | 0 | 0 |
| 2026 | AM | 8.157 | 55 Omar Aziz x 22 Professora Maria do Carmo | 54,0% | 61,4% | 0,95 | 0,91 | 0,86 | 64 | 0,79 | 12 | 0 |
| 2026 | DF | 6.969 | 13 Leandro Grass x 11 Celina Leão | 45,7% | 42,8% | 0,94 | 0,94 | 0,98 | 9 | 0,13 | 0 | 0 |
| 2026 | ES | 9.844 | 15 Ricardo Ferraço x 10 Lorenzo Pazolini | 43,6% | 47,8% | 0,79 | 0,83 | 0,68 | 30 | 0,30 | 2 | 0 |
| 2026 | RN | 8.115 | 13 Cadu de Lula x 44 Allyson | 65,7% | 50,8% | 0,70 | 0,68 | 0,52 | 24 | 0,30 | 6 | 0 |
| 2026 | TO | 4.384 | 44 Professora Dorinha x 45 Vicentinho Júnior | 48,6% | 35,5% | 0,14 | -0,08 | -0,02 | 20 | 0,46 | 2 | 3 |
| 2022 | AL | 6.626 | 15 x 44 | 58,7% | 52,3% | 0,85 | 0,69 | 0,57 | 18 | 0,27 | 1 | 0 |
| 2022 | AM | 7.453 | 15 x 44 | 51,1% | 43,4% | 0,59 | 0,62 | 0,28 | 49 | 0,66 | 3 | 5 |
| 2022 | BA | 34.424 | 13 x 44 | 72,1% | 52,8% | 0,73 | 0,84 | 0,69 | 76 | 0,22 | 1 | 0 |
| 2022 | ES | 9.239 | 40 x 22 | 42,0% | 53,8% | 0,89 | 0,89 | 0,79 | 42 | 0,46 | 5 | 0 |
| 2022 | MS | 6.912 | 45 x 28 | 40,5% | 56,9% | 0,79 | 0,84 | 0,60 | 27 | 0,39 | 4 | 0 |
| 2022 | PB | 9.602 | 40 x 45 | 66,6% | 52,5% | 0,75 | 0,51 | 0,40 | 28 | 0,29 | 4 | 0 |
| 2022 | PE | 20.572 | 77 x 45 | 66,9% | 41,3% | 0,78 | 0,77 | 0,67 | 102 | 0,50 | 13 | 0 |
| 2022 | RO | 4.198 | 44 x 22 | 29,3% | 52,5% | 0,36 | 0,33 | 0,23 | 97 | 2,31 | 32 | 0 |
| 2022 | RS | 27.201 | 45 x 22 | 43,7% | 57,1% | 0,93 | 0,87 | 0,70 | 31 | 0,11 | 2 | 0 |
| 2022 | SC | 16.242 | 13 x 22 | 30,7% | 29,3% | 0,99 | 0,98 | 0,98 | 32 | 0,20 | 4 | 0 |
| 2022 | SE | 5.498 | 13 x 55 | 67,2% | 48,3% | 0,74 | 0,71 | 0,55 | 29 | 0,53 | 1 | 0 |
| 2022 | SP | 101.073 | 13 x 10 | 44,8% | 44,7% | 0,99 | 0,98 | 0,99 | 73 | 0,07 | 2 | 0 |

Somando as UFs: em 2026, 158 seções com abs(z) > 4 (0,40%) e 22 com abs(z) > 6 (0,055%); em 2022, 604 (0,24%) e 72 (0,029%). A taxa agregada de 2022 é puxada para baixo por SP (101 mil seções, 0,07%), onde a disputa estadual repetiu a nacional. Por UF, as taxas de 2026 (0,13% a 0,79%) ficam dentro da faixa de 2022 (0,07% a 2,31%). Em todas as UFs dos dois anos há mais resíduos extremos do que uma normal daria (coluna `esperado_normal_z4` do CSV), o que é esperado em dado eleitoral real: candidatos têm redutos locais que o efeito de município não captura.

Leitura por UF em 2026:

- **DF, AM, ES e RN**: Governador e Presidente andam muito juntos (r de 0,70 a 0,95), o padrão de uma disputa estadual alinhada à nacional, como SC, SP e RS em 2022.
- **AC**: correlação fraca (0,32). O candidato que acompanha o 13 é Mailza Assis (PP), e ela teve 66,2% com o 13 em 33,4%; o voto para governador quase não seguiu o presidencial.
- **TO**: nenhum dos finalistas ao governo (UNIÃO x PSDB) se alinha ao 13 ou ao 22 (r = 0,14 entre seções, -0,08 dentro do município). Sem alinhamento, o modelo não tem o que prever, e as 20 seções marcadas são flutuações em torno de uma relação nula.
- **AM**: 25 seções com pelo menos 100 votos deram zero à candidata 22 ao governo, e 28 seções deram zero ao 22 para Presidente. São os mesmos lugares de voto quase unânime no 13 e no 55 (Omar Aziz), coerentes entre os dois cargos. Em 2022, AM teve 20 seções com zero para o 22 a Presidente.

### Seções com resíduo acima de 6 desvios em 2026

`p13`, `p22`: votos para Presidente; `gA`: candidato a Governador alinhado ao 13; `gB`: o outro; `ajuste`: parte de `gA` prevista pelo modelo.

| UF | Município | Zona | Seção | p13 | p22 | gA | gB | gA observado | ajuste | z |
|---|---|---|---|---|---|---|---|---|---|---|
| AM | 2151 | 14 | 32 | 81 | 97 | 172 | 7 | 96,1% | 67,0% | 9,4 |
| AM | 2151 | 14 | 41 | 103 | 97 | 187 | 14 | 93,0% | 71,4% | 8,5 |
| RN | 17590 | 34 | 235 | 191 | 116 | 36 | 279 | 11,4% | 38,1% | -8,4 |
| AM | 2020 | 45 | 76 | 16 | 101 | 100 | 20 | 83,3% | 46,1% | 8,1 |
| RN | 17590 | 34 | 228 | 205 | 45 | 59 | 203 | 22,5% | 50,8% | -7,5 |
| AM | 2194 | 13 | 33 | 166 | 143 | 281 | 32 | 89,8% | 76,1% | 7,3 |
| AM | 2216 | 21 | 71 | 225 | 95 | 308 | 18 | 94,5% | 82,8% | 7,3 |
| TO | 95214 | 18 | 64 | 119 | 32 | 126 | 21 | 85,7% | 40,4% | 7,1 |
| AM | 2518 | 12 | 24 | 187 | 20 | 170 | 38 | 81,7% | 93,8% | -7,1 |
| RN | 17353 | 68 | 90 | 217 | 42 | 122 | 143 | 46,0% | 70,4% | -6,9 |
| AM | 2453 | 48 | 14 | 193 | 70 | 258 | 4 | 98,5% | 86,8% | 6,8 |
| AM | 2194 | 13 | 40 | 174 | 127 | 281 | 29 | 90,6% | 78,6% | 6,7 |
| AM | 2356 | 17 | 18 | 175 | 145 | 233 | 89 | 72,4% | 56,7% | 6,7 |
| TO | 95214 | 18 | 38 | 136 | 31 | 128 | 40 | 76,2% | 40,3% | 6,6 |
| AM | 2534 | 6 | 59 | 91 | 102 | 147 | 42 | 77,8% | 58,4% | 6,5 |
| ES | 57053 | 1 | 624 | 155 | 130 | 88 | 197 | 30,9% | 50,6% | -6,4 |
| ES | 57053 | 1 | 488 | 169 | 110 | 95 | 177 | 34,9% | 54,9% | -6,3 |
| RN | 17590 | 33 | 277 | 230 | 75 | 78 | 234 | 25,0% | 45,8% | -6,3 |
| AM | 2690 | 4 | 154 | 237 | 24 | 211 | 50 | 80,8% | 91,9% | -6,3 |
| RN | 17590 | 34 | 237 | 191 | 61 | 61 | 200 | 23,4% | 46,1% | -6,3 |
| RN | 18376 | 51 | 115 | 196 | 125 | 78 | 240 | 24,5% | 44,0% | -6,2 |
| AM | 2194 | 13 | 50 | 113 | 136 | 125 | 103 | 54,8% | 70,5% | -6,1 |

Concentrações de seções com abs(z) > 4 em 2026: ES 57053 (20 de 799 seções), RN 17590 (11 de 564), DF 97012 (9 de 6.969), AM 2194, 2534 e 2577 (6 cada). Em 2022 as maiores concentrações foram maiores: RO 35 (71 de 1.159), SP 71072 (41) e PE 23817 (19).

Os 3 casos de padrão oposto extremo em 2026 são todos de TO 95338, zona 32 (seções 61, 70 e 84): 98% a 100% para o 13 a Presidente e 94% a 96% para Vicentinho Júnior (45) ao governo. É o mesmo município que teve a eleição suplementar de prefeito no dia. Em 2022, os 5 casos foram todos de AM (2054/42/26 e 30, 2453/48/12, 2631/43/41 e 47), com o mesmo desenho: quase unanimidade no 13 e no candidato a governador não alinhado.

### O que isso significa

Voto dividido não é erro de contagem: o eleitor escolhe cada cargo separadamente, e um candidato a governador com base local forte pode ter, em um bairro ou aldeia, uma votação que não acompanha a presidencial. Os resíduos marcados mostram onde isso acontece com mais força; não indicam fraude, porque:

- a contagem de cada seção marcada fecha nos dois cargos (checagens 2 a 9) e a soma bate com o resultado oficial;
- o resíduo extremo aparece nos dois sentidos (governador alinhado acima e abaixo do previsto) e a sua frequência por UF em 2026 está dentro da faixa de 2022;
- as seções se agrupam em poucos municípios, como se espera de redutos eleitorais, e não em um padrão espalhado que favoreça um só lado.

Para quem quiser conferir no campo, os grupos mais densos de 2026 são ES 57053 (zona 1) e RN 17590 (zonas 33 e 34), onde o governador alinhado ao 13 teve 20 a 28 pontos menos que o previsto, e AM 2151, 2194 e 2020, onde teve mais.

## Limites

- O 2º turno foi lido só nas 6 UFs com disputa de governador. Nas outras 21 UFs e no exterior o BU do 2º turno tem só Presidente, já auditado em [consistência dos BUs](auditoria-consistencia-bu-2026.md).
- 2022 entrou só como base do 2º turno (12 UFs); o 1º turno de 2022 não foi relido aqui.
- A leitura é da versão final do pacote nacional (datas `Last-Modified` gravadas em `resumo.json`), não das versões intermediárias guardadas durante a apuração.
- O modelo de voto dividido controla só o município. Ele não sabe de bairro, local de votação ou aldeia, então parte dos resíduos extremos é heterogeneidade local que um modelo mais fino absorveria.
- O cargo de código 25 da eleição suplementar de PE não foi identificado pelo nome; só a sua coerência interna foi verificada.

## Arquivos

| Arquivo | Conteúdo |
|---|---|
| `scripts/ele2026/coerencia_cargos.py` | extração (HTTP Range, membro a membro) e relatório |
| `data/parquet/2026/coerencia_cargos/resumo.json` | todas as contagens deste relatório, por ano, turno e UF, membros lidos e falhas |
| `data/parquet/2026/coerencia_cargos/divergencias.parquet` | linhas de seções com alguma divergência (vazio: nenhuma seção divergiu) |
| `data/parquet/2026/coerencia_cargos/razao_votos_comparecimento.csv` | razão votos/comparecimento por ano, turno e cargo |
| `data/parquet/2026/coerencia_cargos/conferencia_oficial_2026.csv`, `..._2022.csv` | combinações de município, zona e cargo em que BU e arquivo oficial diferem ou só um deles existe |
| `data/parquet/2026/coerencia_cargos/split_ticket_uf.csv` | tabela por UF do voto dividido |
| `data/parquet/2026/coerencia_cargos/split_ticket_outliers.parquet` | seções com abs(z) > 4 ou padrão oposto extremo, 2026 e 2022 |
| `data/parquet/2026/coerencia_cargos/split_ticket_outliers_municipio.csv` | contagem de seções marcadas por município |

Para refazer, no servidor de análise:

```sh
S=scripts/ele2026/coerencia_cargos.py; O=~/dataurnas-coerencia
uv run python $S extrair --ano 2026 --turno 1 --saida $O
uv run python $S extrair --ano 2026 --turno 1 --sa --saida $O
uv run python $S extrair --ano 2026 --turno 2 --ufs AC,AM,DF,ES,RN,TO --saida $O
uv run python $S extrair --ano 2026 --turno 2 --ufs AC,AM,DF,ES,RN,TO --sa --saida $O
uv run python $S extrair --ano 2022 --turno 2 --ufs AL,AM,BA,ES,MS,PB,PE,RO,RS,SC,SE,SP --saida $O
uv run python $S extrair --ano 2022 --turno 2 --ufs AL,AM,BA,ES,MS,PB,PE,RO,RS,SC,SE,SP --sa --saida $O
uv run python $S relatorio --saida $O --detalhe ~/dataurnas-historico/zip
```
