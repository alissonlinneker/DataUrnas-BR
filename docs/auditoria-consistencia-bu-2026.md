# Consistência interna e valores impossíveis nos BUs de 2026 (Presidente, 1º e 2º turno)

Auditoria de todas as seções com boletim de urna (BU) da eleição presidencial de 2026: 1º turno em 04/10/2026 e 2º turno em 25/10/2026. A pergunta é uma só: há, dentro dos próprios BUs, algum número impossível, alguma soma que não fecha, alguma repetição ou algum horário que só se explique por fraude, manipulação ou contagem errada? Cada checagem foi feita nos dois turnos, com 2022 como linha de base quando existe dado equivalente.

Escopo: o que está nos BUs decodificados e no resultado oficial do 1º turno. Não entram aqui (já feitos em outros relatórios): hashes e assinaturas ([certificados](certificados-2turno-2026.md)), viradas de liderança ([viradas](viradas-1t-2t-2026.md)), encerramento tardio e prorrogação ([encerramento](encerramento-tardio-2turno-2026.md), [prorrogação](prorrogacao-votacao-2turno-2026.md)), GEDAI, linha do tempo, biometria ([biometria](biometria-1t-2t-2026.md)) e ordem de envio.

## Resultado em uma tabela

Gravidade: **explicável** (há explicação benigna documentada ou demonstrada nos dados); **precisa esclarecimento** (os dados públicos não bastam para explicar; um documento da mesa ou o log da urna resolveria); **indício sério** (algo que só se explica por manipulação).

| # | Checagem | Resultado | Gravidade |
|---|---|---|---|
| 1 | Comparecimento acima dos aptos, total do cargo diferente do comparecimento, soma por tipo ou por candidato diferente do total, voto negativo, voto de legenda | 0 seções nos dois turnos | nenhum achado |
| 2 | Soma dos BUs do 1º turno x resultado oficial por município | igual nos 5.757 municípios em 13, 22, válidos, brancos, nulos, comparecimento e eleitorado | nenhum achado |
| 3 | Soma dos BUs do 2º turno x último total do Brasil | igual em 13, 22, brancos, nulos e comparecimento (128.236.074) | nenhum achado |
| 4 | Seções do 2º turno sem par no 1º e vice-versa | 0 e 0; as 41 seções não instaladas são as mesmas nos dois turnos | nenhum achado |
| 5 | Aptos que mudam entre turnos | 55.722 seções; total idêntico (158.745.079); toda a mudança fecha pelo voto em trânsito | explicável |
| 6 | BUs com o mesmo vetor de votos em seções distintas | 1.180 pares no 2º turno, espalhados pelo país, nenhum repetido no 1º turno, nenhum na mesma urna | explicável (coincidência) |
| 7 | Mesmo número interno de urna em seções diferentes no mesmo turno | 0 entre BUs de urna; só os 2 equipamentos do Sistema de Apuração do exterior | explicável |
| 8 | BU de contingência (Sistema de Apuração) | 29 no 2º turno e 31 no 1º; votos coerentes; Belo Horizonte 0039/0168 no 1º turno teve apuração mista (BU impresso da urna 2409879 digitado no SA mais 20 cédulas), com comparecimento baixo | explicável, com **1 seção a esclarecer** (urna 2409879 sem log nem BU publicados) |
| 9 | Comparecimento de 100% | 12 seções no 2º turno, 15 no 1º; 3 seções com 100% nos dois turnos sem voto em trânsito | explicável, com **3 seções a esclarecer** |
| 10 | Zero voto para um dos finalistas | 106 seções sem voto no 22 e 4 sem voto no 13 no 2º turno (2022: 141 e 2); 90 das 106 já tinham até 2 votos no 22 no 1º turno | explicável, com **1 seção a esclarecer** |
| 11 | Emissão do BU antes da abertura, antes do encerramento ou fora do dia; abertura antes das 8h de Brasília; encerramento antes das 17h de Brasília | 0 em todos os casos, nos dois turnos | nenhum achado |
| 12 | Abertura antes das 7h locais | 2.826 seções, todas nos fusos UTC-5 (6h locais = 8h de Brasília) | explicável |
| 13 | Abertura às 9h de Brasília ou depois | 84 no 2º turno (47 com urna de reserva), 213 no 1º | explicável (operacional), com **1 zona a esclarecer** |
| 14 | BU emitido mais de 1 hora depois do encerramento | **368 seções no 2º turno contra 6 no 1º**, 301 delas nas capitais SP, RJ, BA e PE. O log mostra 0 voto depois do encerramento, 0 reabertura e 1 BU por seção: a urna ficou parada na tela de registro de mesários (352) ou foi reiniciada/trocada (16) | explicável quanto à contagem; motivo da espera depende da ata |
| 15 | Tipo de urna e fase | fase "oficial" em 100%; contingência só em BU do Sistema de Apuração; reserva subiu de 3.033 para 5.714, em proporção parecida com a de 2022 | explicável |

Nenhuma checagem produziu indício sério. Os dois pontos que mais pedem resposta da Justiça Eleitoral são o atraso de emissão do BU em 368 seções do 2º turno (item 14) e o comparecimento baixo da seção 0039/0168 de Belo Horizonte no 1º turno, de apuração mista no Sistema de Apuração (item 8). Os logs resolveram a parte de contagem dos dois (ver a última seção). Nenhum dos dois altera a contagem de forma detectável: nas 368 seções o voto se moveu entre os turnos como nas vizinhas, e a seção de Belo Horizonte tem soma e comparecimento coerentes dentro do próprio BU.

## Dados e método

| Item | Valor |
|---|---|
| Banco | ClickHouse do servidor de processamento, banco `dataurnas` ([descrição](banco-clickhouse.md)) |
| 2º turno | `v_bu_ultima` (última versão de BU de cada seção), `v_votos_t2_secao`, `bu_votos`, `aux_versoes`, `v_totais_ultima` |
| 1º turno | `ref_secoes_2026_t1`, `ref_votos_2026_t1`, `v_votos_t1_secao`, `ref_resultado_municipio_2026_t1` |
| 2022 | `ref_secoes_2022`, `ref_votos_2022` |
| Consultas | `scripts/ele2026/auditoria_consistencia.sql` (roda inteiro, do começo ao fim, em uma sessão) |
| Data da consulta | 27/10/2026 |

Base de seções:

| | 1º turno | 2º turno |
|---|---:|---:|
| Seções com BU | 499.207 | 499.207 |
| BU da urna (`bu.dat`) | 499.176 | 499.178 |
| BU do Sistema de Apuração (`busa.dat`, contingência) | 31 | 29 |
| Seções não instaladas | 41 | 41 |
| Versões de BU por seção | 1 | 1 (nenhuma seção teve BU substituído) |
| BUs com erro de decodificação | 0 | 0 |
| SHA-512 distintos | | 499.207 (nenhum BU repetido) |

Convenções importantes:

- `hora_abertura`, `hora_encerramento` e `data_hora_emissao` estão no relógio **local** da urna, gravados como `DateTime('UTC')`. Para comparar com o horário oficial (8h às 17h de Brasília nos dois turnos), soma-se o deslocamento do fuso: +2 h no AC e em 11 municípios do oeste do AM, +1 h no restante do AM e em MT, MS, RO e RR, -1 h em Fernando de Noronha, 0 no resto. É a mesma tabela de `scripts/ele2026/analisar_encerramento_t2.py`. O exterior (`zz`) fica no horário de cada país e não é convertido.
- `aptos` = `aptos_secao` + `aptos_tte`. O segundo termo é o eleitor habilitado a votar em trânsito naquela seção; o primeiro, o eleitor inscrito nela.
- `comparecimento` é o do cargo Presidente; `comparecimento_bu` é o campo geral `qtdEleitoresCompareceram`.
- No 1º turno, voto `nominal` no número 28 é nulo técnico (não havia candidato 28); o TSE o soma aos nulos. As comparações com o oficial já fazem esse ajuste.

## 1. Valores impossíveis e somas internas

| Teste | 1º turno | 2º turno |
|---|---:|---:|
| Comparecimento do cargo acima dos aptos | 0 | 0 |
| Comparecimento geral do BU acima dos aptos | 0 | 0 |
| Votos do cargo diferentes do comparecimento | 0 | 0 |
| Nominais + legenda + brancos + nulos diferente do total | 0 | 0 |
| Soma das linhas de voto por candidato diferente do total do BU | 0 | 0 |
| Aptos diferente de aptos da seção + aptos em trânsito | 0 | 0 |
| Sem biometria acima do comparecimento | 0 | 0 |
| Habilitados (biometria + ano de nascimento) acima dos aptos | 0 | 0 |
| Linha de voto negativa | 0 | 0 |
| Voto de legenda para Presidente | 0 | 0 |
| Número votado fora dos candidatos | 5.246 votos no 28 (nulo técnico) | 0 (só 13, 22, branco e nulo) |
| Identificação (município, zona, seção) no BU diferente da chave | 31 | 29 |
| Comparecimento geral diferente do comparecimento do cargo | 30 | 27 |

As duas últimas linhas são todas de BU do Sistema de Apuração (item 2): nele o número da seção vem como 0 e o comparecimento geral não é preenchido. Em nenhum BU de urna esses campos divergem.

Totais do 2º turno, soma das 499.207 seções: 64.256.232 votos no 13, 59.826.041 no 22, 1.430.496 brancos e 2.723.305 nulos, total 128.236.074, igual ao comparecimento somado e ao último total do Brasil publicado pelo TSE (499.248 de 499.248 seções, 25/10/2026 23:22:22). Totais do 1º turno: comparecimento 125.275.835, brancos 2.300.798, nulos 3.669.003 mais 5.246 nulos técnicos (3.674.249), iguais ao oficial.

## 2. BUs de contingência (Sistema de Apuração)

Contingência é a seção que votou, toda ou em parte, por cédula, e cujo BU foi gerado no Sistema de Apuração (`busa.dat`, tipo `contingencia`).

| | 1º turno | 2º turno |
|---|---:|---:|
| Seções | 31 | 29 |
| No exterior | 29 | 29 |
| No Brasil | 2 (MG) | 0 |
| Mesmas seções nos dois turnos | 29 | 29 |
| Equipamentos (número interno) | 1808076 no exterior; 2254078 e 2458923 em MG | 1808076 (20 seções) e 1762246 (9 seções) |
| Votos do cargo = comparecimento | todas | todas |
| Comparecimento acima dos aptos | 0 | 0 |

Particularidades dos BUs de contingência, presentes em todos eles e em nenhum BU de urna: `secao_bu` = 0, `comparecimento_bu` = 0, sem horário de abertura e de encerramento, e o mesmo número interno em várias seções. Isso é o formato do BU gerado pelo Sistema de Apuração, que apura várias seções no mesmo equipamento; os votos e o comparecimento do cargo continuam preenchidos e coerentes. As 29 seções do exterior com cédula são as mesmas nos dois turnos, e o comparecimento delas variou entre turnos como o do restante do exterior (37,3% para 41,6% no exterior inteiro).

Duas seções de contingência do exterior têm comparecimento zero:

| Seção | Aptos | 1º turno | 2º turno | Leitura |
|---|---:|---:|---:|---|
| zz 29564 (Ciudad Guayana) 0001/0091 | 72 | 0 | 0 | explicável: seção única da cidade, sem comparecimento nos dois turnos |
| zz 30686 (Trípoli) 0001/0443 | 30 | 2 | 0 | explicável: seção única da cidade, 2 eleitores no 1º turno |

Comparecimento zero não é impossível no BU e não esconde voto: aptos ficam no BU, votos ficam em zero.

### Seção a esclarecer: Belo Horizonte, zona 0039, seção 0168

No 1º turno, a seção mg 41238 0039/0168 foi apurada no Sistema de Apuração (equipamento 2254078; apuração mista, ver a última seção) e teve 281 eleitores de 501 aptos (56,1%). No 2º turno, com urna (2401024), teve 365 (72,9%). As 14 seções do mesmo local de votação tiveram entre 69,0% e 79,1% no 1º turno. Em 2022 a mesma seção teve 68,4% e 75,2%. A distância para o esperado é de cerca de 80 eleitores no 1º turno.

| Seção | Aptos | 1º turno | 2º turno |
|---|---:|---:|---:|
| 0039/0168 (contingência no 1º) | 501 | 281 (56,1%) | 365 (72,9%) |
| 0039/0169 | 496 | 342 (69,0%) | 380 (76,6%) |
| 0039/0425 | 493 | 359 (72,8%) | 414 (84,0%) |
| 0039/0511 | 493 | 383 (77,7%) | 413 (83,8%) |
| demais 11 seções do local | 485 a 494 | 71,6% a 79,1% | 75,6% a 83,0% |

Explicação benigna possível: a urna falhou durante o dia, a mesa passou a cédula e parte dos eleitores desistiu ou não esperou. Explicação que precisa ser descartada: votos dados na urna que falhou e que não entraram na apuração (a recuperação dos votos da mídia da urna original é parte do procedimento de contingência). O BU não diz qual das duas aconteceu. **Precisa esclarecimento**: ata da mesa e log do Sistema de Apuração dessa seção. A outra seção de contingência do Brasil no 1º turno, Piedade dos Gerais (mg 50075 0047/0041), teve 73,4% (278 de 379), igual ao município (74,3%), e não chama atenção.

## 3. Comparecimento de 100% ou perto disso

| | 2026 1º turno | 2026 2º turno | 2022 1º turno | 2022 2º turno |
|---|---:|---:|---:|---:|
| Comparecimento igual aos aptos | 15 | 12 | 32 | 4 |
| Comparecimento de 98% ou mais | 60 | 66 | 796 | 16 |

(Na base de 2022 o 1º turno tem 644 seções com comparecimento acima dos aptos, porque a coluna de aptos daquela base não soma os eleitores em trânsito; por isso o 98% de 2022 no 1º turno fica inflado. Em 2026 não há nenhuma.)

As 12 seções do 2º turno com 100%:

| Seção | Aptos | Em trânsito | Sem biometria | Habilitados por ano de nascimento | 13 x 22 | 1º turno |
|---|---:|---:|---:|---:|---|---|
| BA Pindobaçu (37931) 0115/0210 | 37 | 0 | 0 | 3 | 34 x 3 | 35 de 37 |
| BA Vitória da Conquista (39659) 0041/0400 | 53 | 53 | 1 | 0 | 38 x 14 | 53 de 53 |
| CE Santana do Acaraú (15415) 0044/0193 | 69 | 0 | 1 | 5 | 55 x 13 | 69 de 69 |
| CE Deputado Irapuan Pinheiro (15989) 0055/0160 | 127 | 0 | 2 | 25 | 104 x 21 | 127 de 127 |
| MA Cururupu (07714) 0014/0196 | 51 | 0 | 0 | 4 | 42 x 8 | 49 de 51 |
| MG Jaíba (40282) 0063/0194 | 103 | 2 | 1 | 18 | 94 x 9 | 100 de 103 |
| MG Rio Pardo de Minas (51110) 0237/0371 | 40 | 0 | 0 | 3 | 32 x 5 | 39 de 40 |
| MS Caarapó (90557) 0028/0100 | 26 | 5 | 0 | 0 | 19 x 7 | 20 de 26 |
| PA Baião (04235) 0035/0238 | 51 | 0 | 0 | 0 | 38 x 11 | 51 de 51 |
| RN Caraúbas (16454) 0036/0069 | 163 | 1 | 0 | 23 | 134 x 25 | 162 de 164 |
| SE São Cristóvão (32336) 0021/0286 | 80 | 1 | 0 | 5 | 57 x 22 | 78 de 80 |
| TO Tocantinópolis (96210) 0009/0184 | 62 | 0 | 0 | 0 | 59 x 0 | 60 de 62 |

As 15 do 1º turno: BA 38750 0143/0230, BA 39659 0041/0400, CE 13307 0067/0275, CE 15415 0044/0193, CE 15970 0055/0163, CE 15989 0055/0160, MG 40690 0016/0347, MG 43591 0085/0151, PA 04235 0035/0238, PA 04430 0025/0364, PA 05258 0003/0153, PA 05452 0053/0266 (só trânsito), RR 03107 0007/0124, SP 61557 0299/0229 (só trânsito), SP 61565 0190/0154 (só trânsito).

Leitura: nas 12 seções do 2º turno, 771 dos 862 eleitores (89%) foram identificados pela digital, 86 foram habilitados por ano de nascimento depois de a digital não ser reconhecida e 5 votaram sem biometria cadastrada. A digital exige a presença física do eleitor, o que torna improvável voto em nome de ausente na grande maioria desses comparecimentos. Seção pequena com 100% acontece (2022 teve 32 no 1º turno). A de Vitória da Conquista é de eleitores em trânsito, que pediram para votar ali e por isso comparecem quase todos. **Precisam esclarecimento**, com baixa prioridade, as três seções sem trânsito com 100% nos dois turnos: Santana do Acaraú 0044/0193 (69), Deputado Irapuan Pinheiro 0055/0160 (127) e Baião 0035/0238 (51). A explicação benigna mais comum é um cadastro recém-revisado em comunidade pequena, com quem se mudou já transferido; a lista de eleitores da seção e a ata confirmariam.

### Quedas e altas fortes de comparecimento entre turnos

Seções do Brasil com 50 aptos ou mais no 2º turno:

| Variação do comparecimento (1º para 2º turno) | 2026 | 2022 |
|---|---:|---:|
| Queda de 30 pontos ou mais | 42 | 300 |
| Queda de 20 pontos ou mais | 283 | 688 |
| Alta de 20 pontos ou mais | 8 | 6 |
| Alta de 30 pontos ou mais | 0 | 3 |

Há menos casos extremos que em 2022. As 42 quedas de 30 pontos ou mais estão concentradas em municípios ribeirinhos e de acesso difícil: AC (Marechal Thaumaturgo, Porto Walter, Sena Madureira, Jordão, Tarauacá, Cruzeiro do Sul, Mâncio Lima), AP (Itaubal, Cutias, Pracuúba, Mazagão, Macapá), RR (Rorainópolis, Normandia, Caracaraí) e AM (Novo Airão). Explicável por transporte e clima. Dois casos fogem do padrão e entram como **a esclarecer, baixa prioridade**:

- PR Inácio Martins (75990) 0034/0133: 170 de 215 no 1º turno, **18 de 215 (8,4%)** no 2º, com abertura às 10:05. Na mesma zona, as seções 0014, 0117 e 0189 abriram entre 10:02 e 10:49 e a 0182 às 10:58; a 0117 caiu de 83,7% para 51,7%. Compatível com o problema de chuva e falta de energia que a campanha do 22 relatou no PR (ver [prorrogação](prorrogacao-votacao-2turno-2026.md)), mas o BU não diz a causa.
- RJ Mangaratiba (58513) 0054/0140: 89 de 131 no 1º turno, **18 de 131 (13,7%)** no 2º, com abertura normal às 8h; a 0054/0126 caiu de 78,2% para 45,4%.

O aumento nacional do comparecimento (+2.960.239 eleitores, +2,4%, contra +0,5% em 2022) já está descrito e decomposto em [viradas](viradas-1t-2t-2026.md).

## 4. Zero voto para um dos finalistas

| | Seções | Sem voto no 22 (com voto no 13) | Sem voto no 13 (com voto no 22) | Sem voto no 22, 100 votos ou mais no 13 | Votos do 13 nessas seções |
|---|---:|---:|---:|---:|---:|
| 2022, 1º turno | 470.819 | 159 | 1 | 66 | 17.511 |
| 2022, 2º turno | 470.834 | 141 | 2 | 63 | 16.418 |
| 2026, 1º turno | 499.206 | 81 | 8 | 40 | 9.549 |
| 2026, 2º turno | 499.205 | 106 | 4 | 64 | 14.860 |

O padrão de 2026 é do mesmo tamanho do de 2022 e está nos mesmos tipos de lugar: terras indígenas e comunidades do AM (Atalaia do Norte, São Gabriel da Cachoeira, Santa Isabel do Rio Negro, Tabatinga, Benjamin Constant, São Paulo de Olivença), RR (Uiramutã, sete seções), quilombolas e comunidades da Baixada Maranhense (Alcântara, Turiaçu, Serrano do Maranhão, Santa Helena), TO (Goiatins, Tocantínia, Tocantinópolis) e aldeias do PA e do MT (Parauapebas, São Félix do Xingu, Confresa, Peixoto de Azevedo). As 4 seções sem voto no 13 são de comunidades de colonização alemã ou italiana no RS (Cândido Godói, Arroio do Padre) e de duas seções do PA (Jacareacanga, Chaves).

Persistência:

| | Sem voto no 22 | Sem voto no 13 |
|---|---:|---:|
| Seções no 2º turno | 106 | 4 |
| O mesmo finalista teve até 2 votos no 1º turno | 90 | 4 |
| O mesmo finalista teve 0 no 1º turno | 50 | 4 |
| Seções com a mesma chave em 2022 | 61 | 4 |
| Dessas, o mesmo candidato teve até 5 votos no 2º turno de 2022 | 56 | 3 |
| Maior número de votos do finalista no 1º turno de 2026 | 16 | 0 |

Ou seja, o zero do 2º turno é quase sempre a continuação de um número muito baixo no 1º turno e em 2022, não uma mudança brusca. A lista completa está no [apêndice A](#apêndice-a-seções-do-2º-turno-com-zero-voto-para-um-finalista).

Casos que mais se afastam do próprio histórico:

| Seção | 1º turno (13 x 22, outros) | 2º turno (13 x 22) | Leitura |
|---|---|---|---|
| AM Maués (02615) 0005/0176 | 310 x 16, 3 | 333 x 0 | **a esclarecer, baixa**: 16 eleitores do 22 no 1º turno e nenhum no 2º, numa seção de 382 aptos e comparecimento estável (331 para 337) |
| MA Turiaçu (09415) 0039/0206 | 86 x 5, 0 | 91 x 0 | explicável: 2022 teve 76 x 1 |
| PA Parauapebas (05835) 0106/0330 | 126 x 2, 0 | 212 x 0 | explicável: +84 eleitores, todos no 13, seção de aldeia (zero no 22 também na 0106/0365, que foi de 145 para 198 eleitores); mobilização ou transporte para o 2º turno |
| PA São Félix do Xingu (05452) 0053/0218 | 214 x 1, 1 | 273 x 0 | explicável: mesmo perfil, 2022 teve 194 x 0 |

## 5. Pareamento entre turnos e aptos

| Teste | Resultado |
|---|---:|
| Seções do 2º turno com BU sem par no 1º | 0 |
| Seções do 1º turno com BU sem par no 2º | 0 |
| Seções no aux.json do 2º turno sem BU | 41, todas "Nao instalada", as mesmas 41 não instaladas do 1º turno |
| Seções agregadas no 1º turno que aparecem no 2º | 0 |
| Seções com a mesma urna (número interno) nos dois turnos | 494.772 (99,1%) |
| Soma dos aptos, 1º turno | 158.745.079 |
| Soma dos aptos, 2º turno | 158.745.079 |
| Seções com aptos diferentes entre turnos | 55.722 (2022: 58.714) |
| Seções com aptos da própria seção diferentes | 47.207 |
| Seções em que só os aptos em trânsito mudaram | 9.079 |
| Variação somada dos aptos da própria seção | +11.039 |
| Variação somada dos aptos em trânsito | -11.039 |
| Maior variação dos aptos da própria seção | -5 a +5 |
| Maior variação dos aptos em trânsito | -84 a +46 |
| Seções só de eleitores em trânsito (aptos da seção = 0) | 389 nos dois turnos |

As 41 seções não instaladas ficam em 40 cidades do exterior e somam 423 eleitores; com elas, o eleitorado oficial do 1º turno (158.745.502) fecha exatamente com a soma dos aptos dos BUs (158.745.079 + 423).

Por que os aptos mudam: o eleitor pede o voto em trânsito para um turno, para o outro ou para os dois. Quem vota em trânsito sai dos aptos da seção de origem e entra nos aptos em trânsito da seção de destino. A prova de que não há outra causa está nos números: o total do país não muda nem por um eleitor; o que sai de `aptos_tte` (-11.039) é exatamente o que entra em `aptos_secao` (+11.039); a variação dos aptos da própria seção nunca passa de 5 eleitores; e todas as 23 seções com variação de 30 aptos ou mais são de trânsito (só de trânsito, como as de Olinda, Recife, Macapá, São Luís, Maceió, Chapecó e Guarulhos, ou com a parte própria inalterada ou alterada em 1 eleitor, como Porto Seguro 0121/0228 e 0230, com 238 aptos próprios nos dois turnos e trânsito de 150 para 91). Por UF a soma não é zero porque o trânsito pode cruzar UF (DF +675 e SP +699, compensados nas demais). O exterior ganhou 149 aptos na própria seção: eleitor do exterior que votou em trânsito no Brasil no 1º turno e não no 2º.

Consequência coerente: em 30 seções o comparecimento do 1º turno é maior que os aptos do 2º, e em 6 o do 2º é maior que os aptos do 1º; todas são seções em que o trânsito mudou (por exemplo, Olinda 0117/0016: 220 aptos e 210 votantes no 1º turno, 136 aptos no 2º). Explicável.

Urnas entre turnos: 81 urnas que votaram numa seção no 1º turno aparecem em outra no 2º (33 delas como urna de reserva; 28 em outro município). É o reaproveitamento de urna depois da troca por defeito ou da recarga para outro local; nenhum desses números aparece em duas seções no mesmo turno (item 7).

## 6. BUs com o mesmo vetor de votos

Procurou-se, no 2º turno, seções diferentes com exatamente os mesmos aptos, comparecimento, votos no 13, votos no 22, brancos e nulos.

| | 2022, 2º turno | 2026, 2º turno |
|---|---:|---:|
| Seções | 470.834 | 499.205 |
| Pares de seções idênticas em aptos, comparecimento e votos | 551 | 1.180 |
| Grupos (seções com o mesmo vetor) | 551 | 1.172 (2.348 seções; no máximo 3 por grupo) |

O número de 2026 é o dobro do de 2022, por isso foi decomposto. Pares de seções com a mesma chave:

| Chave | 2022 | 2026 | 2026 ÷ 2022 |
|---|---:|---:|---:|
| comparecimento | 573.949.840 | 690.312.108 | 1,20 |
| aptos e comparecimento | 8.499.874 | 10.857.967 | 1,28 |
| comparecimento, 13 e 22 | 212.096 | 361.260 | 1,70 |
| comparecimento, 13, 22, brancos e nulos | 36.983 | 73.596 | 1,99 |
| aptos, comparecimento, 13, 22, brancos e nulos | 551 | 1.180 | 2,14 |

O excesso aparece em etapas que têm causa visível: em 2026 há 6% mais seções, as seções são menores e mais parecidas entre si (comparecimento médio 256,9 com desvio 54,1, contra 263,2 e 58,1 em 2022), e brancos mais nulos caíram de 12,1 para 8,3 por seção. Com menos brancos e nulos, fixado o comparecimento, 13 e 22 ficam quase determinados um pelo outro, e coincidir fica mais fácil. Dado o comparecimento, 13 e 22, a chance de brancos e nulos também coincidirem é 0,174 em 2022 e 0,204 em 2026; dados todos os votos, a chance de os aptos coincidirem é 0,0149 e 0,0160. Nenhuma etapa salta.

O que separaria coincidência de cópia é a estrutura dos pares, e ela é a de coincidência:

| Teste nos 1.180 pares de 2026 | Resultado |
|---|---:|
| Mesma UF | 210 (17,8%) |
| Mesmo município | 32 |
| Mesma zona | 13 |
| Mesmo local de votação | 8 |
| Mesma urna | 0 |
| Par que também é idêntico no 1º turno | 0 |
| Comparecimento | 36 a 353 (mediana 262) |

Um BU copiado de outra seção apareceria no mesmo local ou na mesma zona e tenderia a se repetir no outro turno. Aqui 82% dos pares estão em UFs diferentes e nenhum se repete no 1º turno. No 1º turno, com 12 candidatos, só 1 par de seções tem o vetor completo idêntico. **Explicável**, coincidência estatística.

Os 8 pares no mesmo local de votação: AM 02518 0012/0007 e 0012/0115; CE 15695 0081/0036 e 0081/0179; MG 54011 0326/0227 e 0326/0233; PB 19372 0061/0124 e 0061/0249; PE 23370 0035/0003 e 0035/0004; RJ 58041 0153/0130 e 0153/0144; RJ 58122 0138/0002 e 0138/0050; SP 63134 0303/0102 e 0303/0112. Cada seção tem urna própria (números internos diferentes em todos os pares) e BU com SHA-512 próprio e assinado pela própria urna ([certificados](certificados-2turno-2026.md)).

## 7. Número interno da urna repetido

| | 1º turno | 2º turno |
|---|---:|---:|
| Números internos em mais de uma seção, BU de urna | 0 | 0 |
| Números internos em mais de uma seção, BU do Sistema de Apuração | 1 (1808076, 29 seções do exterior) | 2 (1808076 em 20 seções, 1762246 em 9) |
| Seções com número interno vazio ou zero | 0 | 0 |

Explicável: o Sistema de Apuração do exterior é um equipamento que apura várias seções.

## 8. Horários

Horários convertidos para Brasília no Brasil; exterior no horário local.

| Teste | 1º turno, Brasil | 1º turno, exterior | 2º turno, Brasil | 2º turno, exterior |
|---|---:|---:|---:|---:|
| Seções | 497.897 | 1.310 | 497.897 | 1.310 |
| Sem abertura e encerramento (contingência) | 2 | 29 | 0 | 29 |
| Abertura, encerramento ou emissão fora do dia da eleição | 0 | 0 | 0 | 0 |
| Abertura antes das 8h de Brasília | 0 | 0 | 0 | 0 |
| Abertura antes das 7h locais | 2.826 | 0 | 2.826 | 0 |
| Abertura às 8h10 de Brasília ou depois | 6.560 | 45 | 1.814 | 18 |
| Abertura às 9h de Brasília ou depois | 213 | 1 | 84 | 2 |
| Encerramento antes das 17h de Brasília | 0 | 0 | 0 | 0 |
| Emissão do BU antes do encerramento | 0 | 0 | 0 | 0 |
| Emissão do BU antes da abertura | 0 | 0 | 0 | 0 |
| Encerramento antes da abertura | 0 | 0 | 0 | 0 |
| **Emissão mais de 1 hora depois do encerramento** | **6** | 0 | **368** | 0 |
| Primeira abertura | 08:00:00 | 08:00:00 | 08:00:00 | 08:00:00 |
| Última abertura | 12:55:30 | 09:17:14 | 13:08:44 | 09:03:34 |

Abertura antes das 7h locais: todas as 2.826 são do AC e dos 11 municípios do oeste do AM, em UTC-5, onde 8h de Brasília são 6h locais. Em Fernando de Noronha (10 seções) a abertura está às 9h locais, que também são 8h de Brasília. Nenhuma urna abriu antes do horário. **Explicável.**

Duração (abertura a encerramento, Brasil, minutos):

| Turno | Tipo | Seções | 0,1% | 1% | Mediana | 99% | 99,9% | Mínimo | Máximo |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 1º | urna da seção | 494.891 | 521 | 535 | 544 | 676 | 735 | 246 | 914 |
| 1º | reserva | 3.004 | 428 | 479 | 547 | 732 | 798 | 382 | 867 |
| 2º | urna da seção | 492.225 | 523 | 537 | 541 | 660 | 666 | 233 | 765 |
| 2º | reserva | 5.670 | 432 | 489 | 541 | 660 | 665 | 361 | 904 |

A duração normal é de 540 minutos (8h às 17h). Durações curtas vêm de abertura atrasada; as longas, do encerramento depois das 17h, tratado em [encerramento tardio](encerramento-tardio-2turno-2026.md) e [prorrogação](prorrogacao-votacao-2turno-2026.md). Nenhuma duração negativa ou zerada.

### Abertura atrasada

No 2º turno, 84 seções do Brasil abriram às 9h de Brasília ou depois: 47 com urna de reserva (a urna original falhou e a substituta abriu depois) e 37 com a urna original. O comparecimento médio das 47 de reserva (81,3%) é igual ao do país (81,0%); o das 37 com urna original é menor (75,6%), como se espera de quem ficou fechado parte da manhã. No 1º turno foram 213. As 16 aberturas do 2º turno às 10h ou depois:

| Seção | Tipo | Abertura (Brasília) | Comparecimento |
|---|---|---|---|
| MG 46477 0134/0295 | urna da seção | 13:08:44 | 9 de 25 |
| ES 56413 0033/0049 | urna da seção | 11:00:53 | 173 de 225 |
| PA 05010 0022/0259 | reserva | 11:00:22 | 80 de 104 |
| PR 75990 0034/0182 | urna da seção | 10:58:53 | 98 de 138 |
| PR 75833 0043/0397 | urna da seção | 10:51:03 | 38 de 65 |
| PR 75990 0034/0117 | urna da seção | 10:49:09 | 105 de 203 |
| PR 75990 0034/0014 | urna da seção | 10:41:51 | 192 de 273 |
| ES 56413 0033/0083 | urna da seção | 10:28:40 | 128 de 161 |
| BA 38717 0178/0118 | reserva | 10:23:25 | 310 de 370 |
| CE 13552 0033/0379 | urna da seção | 10:22:40 | 224 de 268 |
| BA 33073 0074/0241 | reserva | 10:14:40 | 311 de 383 |
| MA 08974 0070/0165 | reserva | 10:07:57 | 165 de 211 |
| PR 75990 0034/0133 | urna da seção | 10:05:01 | 18 de 215 |
| BA 34134 0170/0105 | reserva | 10:03:45 | 336 de 400 |
| PR 74918 0056/0037 | urna da seção | 10:02:54 | 278 de 324 |
| PR 75990 0034/0189 | urna da seção | 10:02:45 | 121 de 214 |

A zona 0034 de Inácio Martins (PR) concentra 5 das 16, todas com a urna original. **Explicável** como operacional no geral; Inácio Martins **a esclarecer** (item 3).

### Emissão do BU mais de 1 hora depois do encerramento (precisa esclarecimento)

Depois do encerramento a urna emite o BU em segundos ou poucos minutos: a mediana do atraso é de 1 a 2,5 minutos em todas as UFs e nos dois turnos. No 1º turno, 6 seções passaram de 1 hora. No 2º turno, **368**:

| UF | Seções com BU de urna | Atraso mediano (s) | 99% (s) | Mais de 30 min | Mais de 1 h | 1º turno, mais de 1 h |
|---|---:|---:|---:|---:|---:|---:|
| SP | 103.656 | 116 | 341 | 250 | **130** | 0 |
| RJ | 37.675 | 126 | 642 | 201 | **113** | 3 |
| BA | 35.476 | 124 | 453 | 123 | **66** | 1 |
| PE | 21.418 | 122 | 509 | 86 | **44** | 0 |
| PB | 10.712 | 119 | 295 | 7 | 6 | 0 |
| MG | 52.062 | 122 | 274 | 3 | 3 | 0 |
| SE | 5.923 | 118 | 297 | 3 | 2 | 1 |
| AC, PA, RN, RS | | | | | 1 cada | 0 |
| demais UFs | | | | 0 a 2 | 0 | 0 a 1 |

Características das 368:

- 359 com a urna original, 8 com urna de reserva, 1 com urna de reserva que encerrou a seção.
- 301 em quatro capitais: São Paulo (71072) 125, Rio de Janeiro (60011) 88, Salvador (38490) 59, Recife (25313) 29. Concentradas por zona: Salvador 0002 (29 seções), São Paulo 0328 (26), São Paulo 0004 (22), Rio 0009 (16), Recife 0009 (14), São Paulo 0257 (13), Salvador 0006 (12).
- O encerramento é normal: 309 entre 17:00 e 17:09 locais, 53 entre 17:10 e 17:19, 4 entre 17:20 e 17:59, 1 às 19:00 (PB) e 1 às 15:02 locais no AC (17:02 de Brasília). A emissão vem entre 18:02 e 20:48 locais. O maior atraso é de 165 minutos (Volta Redonda, RJ 59250 0090/0232: encerramento 17:00:46, emissão 19:45:31).
- O recebimento pelo TSE de todas as 368 ficou entre 20:37:47 e 21:54:18 de Brasília (mediana 21:07:39), depois da retomada da totalização.
- A janela coincide com a decisão do STF que prorrogou a votação (divulgada às 17h03), a pausa da totalização (17h06) e as orientações dos TREs (TRE-SP às 17h18), descritas em [prorrogação](prorrogacao-votacao-2turno-2026.md).

Isso mudou o voto? Os dados dizem que não de forma detectável. Comparadas com as demais 31.086 seções das mesmas zonas, as 368 tiveram o mesmo comparecimento (77,64% para 80,43%, contra 77,66% para 80,51%) e uma variação da fatia do 13 entre turnos um pouco **menor** (+2,55 contra +3,06 pontos). O mesmo vale em cada capital (São Paulo +2,06 contra +2,70; Rio +3,58 contra +3,67; Salvador +1,76 contra +2,37; Recife +2,25 contra +2,27). E a urna não aceita voto depois do encerramento: o BU emitido mais tarde só pode conter os votos dados até o encerramento.

Explicação benigna possível: depois de encerrar, a mesa demorou a confirmar a emissão (impressora, falta de papel, espera por orientação sobre a prorrogação, chegada do juiz ou do técnico). Explicação que precisa ser descartada: urna mantida ligada e manipulada entre o encerramento e a emissão. Os BUs assinados excluem alteração do arquivo depois da emissão, mas não dizem o que aconteceu na urna nesse intervalo. **Precisa esclarecimento**: o log de cada urna (`logd.dat`) registra, minuto a minuto, o encerramento, os pedidos e as impressões do BU. Nenhuma das 368 está na amostra de logs já baixada pelo projeto (2.997 seções); a análise exige baixar os 368 logs, o que não foi feito aqui. Lista completa no [apêndice B](#apêndice-b-seções-do-2º-turno-com-bu-emitido-mais-de-1-hora-depois-do-encerramento).

## 9. Tipo de urna e fase

| Tipo de urna | 1º turno | 2º turno |
|---|---:|---:|
| `secao` (urna original) | 496.143 | 493.464 |
| `reservaSecao` (urna de reserva) | 3.033 | 5.712 |
| `reservaEncerrandoSecao` | 0 | 2 |
| `contingencia` (só em `busa.dat`) | 31 | 29 |
| Fase diferente de "oficial" | 0 | 0 |
| Versão de software diferente de 10.23.0.0 | 0 | 0 |

Nenhum BU de urna com tipo `contingencia` e nenhum `busa.dat` com outro tipo. A urna de reserva quase dobrou do 1º para o 2º turno (3.033 para 5.714 seções, 0,61% para 1,14%), em proporção parecida com a de 2022 (10.077 para 17.931 seções, 1,78 vezes; em 2026, 1,88 vezes). **Explicável**: urnas que falharam no 1º turno são trocadas e a substituição é registrada como reserva no 2º.

## Conclusão

Nos 998.414 BUs dos dois turnos (499.207 por turno) não há número impossível. Cada BU fecha por dentro (comparecimento, aptos, total do cargo, soma por tipo e por candidato), a soma dos BUs reproduz o resultado oficial do 1º turno em todos os municípios e o total do Brasil no 2º, os aptos fecham entre turnos até o último eleitor, nenhuma urna aparece em duas seções e nenhum horário fica fora do dia ou antes da abertura. As repetições de vetor de votos e as seções com zero voto para um finalista têm o tamanho e a geografia esperados pela linha de base de 2022.

Ficam para esclarecimento, em ordem de prioridade:

1. **368 seções do 2º turno com BU emitido mais de 1 hora depois do encerramento** (6 no 1º turno), 301 nas capitais SP, RJ, BA e PE. Os logs mostram 0 voto depois do encerramento e nenhuma reabertura; resta saber, pela ata, por que a mesa esperou na tela de registro de mesários.
2. **Belo Horizonte 0039/0168 no 1º turno**, apuração mista (BU impresso da urna 2409879 digitado no Sistema de Apuração mais 20 cédulas), com cerca de 80 eleitores a menos que o esperado. O log e o BU da urna 2409879 não foram publicados; resolve com a ata da mesa e esses arquivos.
3. Baixa prioridade: Maués 0005/0176 (16 votos do 22 no 1º turno, 0 no 2º); comparecimento de 100% nos dois turnos em Santana do Acaraú 0044/0193, Deputado Irapuan Pinheiro 0055/0160 e Baião 0035/0238; quedas para 8,4% em Inácio Martins 0034/0133 e para 13,7% em Mangaratiba 0054/0140.

Nenhum desses pontos, isolado ou somado, chega perto de alterar o resultado: o maior deles soma 368 seções, 0,07% do total, que votaram como as vizinhas.

## Limitações

- Só o cargo Presidente foi decodificado no 2º turno. Coerência entre cargos (governador, nos estados que tiveram 2º turno) não foi verificada aqui.
- O BU não guarda o motivo de atraso, troca de urna ou contingência. Esses motivos estão no log da urna e na ata da mesa; os logs só existem no projeto para uma amostra de 2.997 seções e não foram baixados novos logs para este relatório.
- A comparação com 2022 usa a base local de 2022 (`ref_secoes_2022`), cuja coluna de aptos não soma os eleitores em trânsito no 1º turno. Por isso as contagens de 2022 que dependem de aptos (100% e 98% de comparecimento no 1º turno) são só indicativas.
- O pareamento com 2022 é pela chave UF, município, zona e seção. Seção renumerada ou agregada entre 2022 e 2026 fica sem par (45 das 106 seções sem voto no 22).
- O horário de Brasília das urnas do exterior não é calculado; os testes de horário do exterior usam o horário local.

## Apêndice A: seções do 2º turno com zero voto para um finalista

Colunas: UF, município, zona/seção, 2º turno de 2026 (13 x 22), brancos mais nulos no 2º turno, 1º turno de 2026 (13 x 22 e os demais candidatos), 2º turno de 2022 na mesma chave (13 x 22). As 106 primeiras não têm voto no 22; as 4 últimas não têm voto no 13.

| UF | Município | Zona/seção | 2026 2º turno | Brancos e nulos | 2026 1º turno | 2022 2º turno |
|---|---|---|---|---:|---|---|
| AC | CRUZEIRO DO SUL (01074) | 0004/0457 | 137 x 0 | 14 | 151 x 0 (outros 0) | sem par |
| AC | JORDÃO (01104) | 0005/0065 | 126 x 0 | 7 | 127 x 1 (outros 1) | 122 x 5 |
| AC | JORDÃO (01104) | 0005/0125 | 123 x 0 | 5 | 138 x 4 (outros 2) | sem par |
| AM | ATALAIA DO NORTE (02054) | 0042/0026 | 302 x 0 | 7 | 283 x 1 (outros 6) | 257 x 1 |
| AM | ATALAIA DO NORTE (02054) | 0042/0028 | 136 x 0 | 1 | 126 x 1 (outros 6) | 127 x 0 |
| AM | ATALAIA DO NORTE (02054) | 0042/0029 | 325 x 0 | 10 | 274 x 4 (outros 6) | 175 x 0 |
| AM | ATALAIA DO NORTE (02054) | 0042/0030 | 142 x 0 | 2 | 132 x 3 (outros 1) | 107 x 1 |
| AM | ATALAIA DO NORTE (02054) | 0042/0037 | 122 x 0 | 6 | 105 x 0 (outros 1) | 107 x 0 |
| AM | BARREIRINHA (02119) | 0026/0062 | 261 x 0 | 11 | 257 x 0 (outros 8) | 301 x 1 |
| AM | BENJAMIN CONSTANT (02135) | 0020/0089 | 238 x 0 | 8 | 242 x 0 (outros 0) | 321 x 8 |
| AM | BENJAMIN CONSTANT (02135) | 0020/0117 | 231 x 0 | 12 | 237 x 1 (outros 1) | sem par |
| AM | CARAUARI (02216) | 0021/0096 | 113 x 0 | 0 | 112 x 1 (outros 0) | 91 x 0 |
| AM | SANTA ISABEL DO RIO NEGRO (02372) | 0030/0022 | 236 x 0 | 14 | 213 x 0 (outros 8) | 196 x 0 |
| AM | SANTA ISABEL DO RIO NEGRO (02372) | 0030/0026 | 229 x 0 | 16 | 195 x 0 (outros 8) | 156 x 0 |
| AM | SANTA ISABEL DO RIO NEGRO (02372) | 0030/0030 | 72 x 0 | 4 | 51 x 1 (outros 2) | sem par |
| AM | JAPURÁ (02453) | 0048/0012 | 224 x 0 | 8 | 221 x 0 (outros 2) | 156 x 2 |
| AM | JURUÁ (02470) | 0050/0019 | 149 x 0 | 19 | 129 x 3 (outros 10) | 42 x 4 |
| AM | MAUÉS (02615) | 0005/0176 | 333 x 0 | 4 | 310 x 16 (outros 3) | sem par |
| AM | MAUÉS (02615) | 0005/0179 | 123 x 0 | 1 | 126 x 1 (outros 0) | sem par |
| AM | PARINTINS (02690) | 0004/0130 | 220 x 0 | 5 | 246 x 3 (outros 1) | 190 x 1 |
| AM | PARINTINS (02690) | 0004/0280 | 88 x 0 | 1 | 98 x 0 (outros 0) | sem par |
| AM | SANTO ANTÔNIO DO IÇÁ (02739) | 0047/0009 | 329 x 0 | 1 | 319 x 4 (outros 1) | 318 x 1 |
| AM | SANTO ANTÔNIO DO IÇÁ (02739) | 0047/0087 | 315 x 0 | 1 | 308 x 2 (outros 2) | sem par |
| AM | SÃO PAULO DE OLIVENÇA (02755) | 0022/0071 | 298 x 0 | 7 | 295 x 1 (outros 2) | 359 x 2 |
| AM | SÃO PAULO DE OLIVENÇA (02755) | 0022/0114 | 244 x 0 | 7 | 231 x 0 (outros 7) | sem par |
| AM | SÃO GABRIEL DA CACHOEIRA (02836) | 0019/0001 | 167 x 0 | 5 | 171 x 1 (outros 0) | 173 x 1 |
| AM | SÃO GABRIEL DA CACHOEIRA (02836) | 0019/0065 | 224 x 0 | 7 | 223 x 0 (outros 1) | 204 x 0 |
| AM | SÃO GABRIEL DA CACHOEIRA (02836) | 0019/0087 | 222 x 0 | 1 | 223 x 0 (outros 0) | 162 x 0 |
| AM | SÃO GABRIEL DA CACHOEIRA (02836) | 0019/0092 | 215 x 0 | 4 | 233 x 0 (outros 1) | 195 x 0 |
| AM | SÃO GABRIEL DA CACHOEIRA (02836) | 0019/0120 | 126 x 0 | 1 | 129 x 0 (outros 1) | sem par |
| AM | URUCURITUBA (02879) | 0003/0252 | 101 x 0 | 2 | 112 x 4 (outros 1) | 97 x 2 |
| AM | TABATINGA (98477) | 0036/0061 | 354 x 0 | 11 | 351 x 3 (outros 4) | 274 x 1 |
| AM | TABATINGA (98477) | 0036/0096 | 338 x 0 | 9 | 340 x 0 (outros 2) | 155 x 2 |
| BA | ÉRICO CARDOSO (33090) | 0111/0250 | 44 x 0 | 0 | 43 x 0 (outros 1) | 51 x 1 |
| BA | BARRA DO MENDES (33596) | 0176/0151 | 69 x 0 | 2 | 63 x 0 (outros 1) | 71 x 1 |
| BA | IAÇU (35378) | 0193/0116 | 40 x 0 | 4 | 35 x 0 (outros 1) | 38 x 1 |
| BA | SENTO SÉ (39039) | 0096/0119 | 62 x 0 | 6 | 64 x 0 (outros 1) | sem par |
| CE | AQUIRAZ (13196) | 0066/0334 | 32 x 0 | 1 | 28 x 2 (outros 1) | 81 x 10 |
| CE | PORANGA (15210) | 0040/0208 | 54 x 0 | 0 | 54 x 0 (outros 0) | 32 x 1 |
| ES | ARACRUZ (56111) | 0020/0232 | 41 x 0 | 0 | 33 x 0 (outros 0) | sem par |
| MA | ÁGUA DOCE DO MARANHÃO (07005) | 0012/0145 | 189 x 0 | 4 | 170 x 4 (outros 3) | 150 x 5 |
| MA | ALCÂNTARA (07030) | 0052/0085 | 79 x 0 | 3 | 77 x 0 (outros 0) | sem par |
| MA | ALCÂNTARA (07030) | 0052/0086 | 44 x 0 | 0 | 44 x 1 (outros 0) | sem par |
| MA | BARREIRINHAS (07331) | 0056/0254 | 95 x 0 | 4 | 99 x 0 (outros 1) | sem par |
| MA | CURURUPU (07714) | 0014/0195 | 54 x 0 | 0 | 50 x 0 (outros 1) | sem par |
| MA | MARANHÃOZINHO (07927) | 0101/0078 | 176 x 0 | 5 | 182 x 0 (outros 1) | 307 x 0 |
| MA | GRAJAÚ (07935) | 0015/0405 | 102 x 0 | 3 | 95 x 0 (outros 0) | sem par |
| MA | MONTES ALTOS (08397) | 0103/0080 | 298 x 0 | 0 | 287 x 2 (outros 0) | 264 x 0 |
| MA | SERRANO DO MARANHÃO (08524) | 0107/0087 | 83 x 0 | 1 | 82 x 3 (outros 0) | 60 x 0 |
| MA | SERRANO DO MARANHÃO (08524) | 0107/0089 | 74 x 0 | 1 | 74 x 1 (outros 1) | 68 x 0 |
| MA | PRIMEIRA CRUZ (08850) | 0032/0090 | 42 x 0 | 5 | 46 x 1 (outros 2) | 42 x 0 |
| MA | PRIMEIRA CRUZ (08850) | 0032/0193 | 42 x 0 | 1 | 49 x 1 (outros 1) | 41 x 3 |
| MA | SANTA HELENA (08958) | 0083/0170 | 54 x 0 | 0 | 52 x 0 (outros 0) | sem par |
| MA | SANTA HELENA (08958) | 0083/0179 | 55 x 0 | 1 | 51 x 0 (outros 0) | sem par |
| MA | SÃO BENTO (09075) | 0038/0167 | 96 x 0 | 1 | 94 x 2 (outros 0) | 87 x 0 |
| MA | TURIAÇU (09415) | 0039/0058 | 164 x 0 | 2 | 166 x 2 (outros 1) | 148 x 0 |
| MA | TURIAÇU (09415) | 0039/0162 | 157 x 0 | 1 | 171 x 1 (outros 4) | 215 x 6 |
| MA | TURIAÇU (09415) | 0039/0195 | 73 x 0 | 1 | 68 x 1 (outros 0) | sem par |
| MA | TURIAÇU (09415) | 0039/0206 | 91 x 0 | 1 | 86 x 5 (outros 0) | 76 x 1 |
| MA | VIANA (09490) | 0020/0258 | 100 x 0 | 1 | 97 x 1 (outros 0) | sem par |
| MG | LUISLÂNDIA (41009) | 0050/0224 | 69 x 0 | 2 | 74 x 0 (outros 0) | 72 x 6 |
| MG | SALINAS (51390) | 0244/0256 | 47 x 0 | 2 | 41 x 0 (outros 0) | 53 x 2 |
| MS | ARAL MOREIRA (91715) | 0019/0313 | 56 x 0 | 0 | 52 x 0 (outros 0) | sem par |
| MT | CONFRESA (90280) | 0028/0200 | 309 x 0 | 0 | 296 x 0 (outros 1) | sem par |
| MT | BARRA DO GARÇAS (90352) | 0009/0531 | 119 x 0 | 4 | 109 x 3 (outros 4) | sem par |
| MT | PEIXOTO DE AZEVEDO (98817) | 0033/0255 | 179 x 0 | 2 | 156 x 0 (outros 3) | 116 x 0 |
| MT | PORTO ALEGRE DO NORTE (98850) | 0028/0191 | 61 x 0 | 0 | 61 x 0 (outros 0) | 55 x 0 |
| MT | GUARANTÃ DO NORTE (99058) | 0044/0284 | 145 x 0 | 0 | 144 x 3 (outros 3) | 89 x 3 |
| PA | ALENQUER (04073) | 0021/0234 | 60 x 0 | 0 | 65 x 2 (outros 1) | 70 x 1 |
| PA | ALMEIRIM (04090) | 0055/0128 | 156 x 0 | 1 | 156 x 0 (outros 0) | 133 x 2 |
| PA | ALTAMIRA (04111) | 0018/0516 | 52 x 0 | 1 | 54 x 0 (outros 0) | sem par |
| PA | ALTAMIRA (04111) | 0018/0519 | 35 x 0 | 0 | 21 x 0 (outros 0) | sem par |
| PA | AVEIRO (04197) | 0034/0660 | 106 x 0 | 0 | 102 x 0 (outros 0) | sem par |
| PA | NOVO REPARTIMENTO (04421) | 0101/0152 | 18 x 0 | 0 | 18 x 0 (outros 0) | sem par |
| PA | MOJU (04936) | 0037/0120 | 41 x 0 | 0 | 48 x 3 (outros 0) | 49 x 0 |
| PA | ORIXIMINÁ (05053) | 0038/0243 | 35 x 0 | 1 | 37 x 1 (outros 0) | sem par |
| PA | ORIXIMINÁ (05053) | 0038/0259 | 133 x 0 | 0 | 142 x 2 (outros 0) | 99 x 5 |
| PA | ORIXIMINÁ (05053) | 0038/0260 | 152 x 0 | 0 | 144 x 0 (outros 0) | 111 x 0 |
| PA | PARAGOMINAS (05096) | 0042/0214 | 54 x 0 | 1 | 46 x 1 (outros 1) | 44 x 1 |
| PA | SÃO FÉLIX DO XINGU (05452) | 0053/0217 | 145 x 0 | 0 | 130 x 1 (outros 0) | 129 x 2 |
| PA | SÃO FÉLIX DO XINGU (05452) | 0053/0218 | 273 x 0 | 0 | 214 x 1 (outros 1) | 194 x 0 |
| PA | VISEU (05657) | 0014/0236 | 64 x 0 | 4 | 68 x 0 (outros 0) | sem par |
| PA | PARAUAPEBAS (05835) | 0106/0330 | 212 x 0 | 0 | 126 x 2 (outros 0) | sem par |
| PA | PARAUAPEBAS (05835) | 0106/0365 | 197 x 0 | 1 | 141 x 0 (outros 0) | sem par |
| PB | SAPÉ (22071) | 0004/0290 | 10 x 0 | 0 | 11 x 1 (outros 0) | sem par |
| PE | FLORESTA (24139) | 0072/0119 | 227 x 0 | 3 | 217 x 1 (outros 3) | sem par |
| PI | TERESINA (12190) | 0097/0168 | 16 x 0 | 0 | 13 x 0 (outros 1) | sem par |
| PR | ORTIGUEIRA (77275) | 0167/0096 | 314 x 0 | 3 | 299 x 1 (outros 3) | 223 x 0 |
| RO | PORTO VELHO (00035) | 0006/0516 | 104 x 0 | 2 | 100 x 0 (outros 2) | 87 x 6 |
| RR | CAROEBE (03000) | 0004/0141 | 44 x 0 | 0 | 66 x 2 (outros 0) | sem par |
| RR | UIRAMUTÃ (03107) | 0007/0061 | 189 x 0 | 0 | 185 x 0 (outros 0) | 234 x 1 |
| RR | UIRAMUTÃ (03107) | 0007/0062 | 216 x 0 | 1 | 215 x 1 (outros 0) | 236 x 1 |
| RR | UIRAMUTÃ (03107) | 0007/0063 | 256 x 0 | 0 | 259 x 2 (outros 1) | 176 x 0 |
| RR | UIRAMUTÃ (03107) | 0007/0104 | 138 x 0 | 1 | 145 x 1 (outros 0) | 98 x 1 |
| RR | UIRAMUTÃ (03107) | 0007/0108 | 126 x 0 | 2 | 131 x 1 (outros 0) | sem par |
| RR | UIRAMUTÃ (03107) | 0007/0113 | 190 x 0 | 2 | 186 x 3 (outros 0) | sem par |
| RR | UIRAMUTÃ (03107) | 0007/0124 | 48 x 0 | 0 | 51 x 0 (outros 0) | sem par |
| RS | VIAMÃO (89630) | 0059/0590 | 39 x 0 | 0 | 36 x 1 (outros 0) | sem par |
| RS | VIAMÃO (89630) | 0059/0591 | 65 x 0 | 1 | 65 x 0 (outros 0) | sem par |
| TO | PARANÃ (95214) | 0018/0087 | 33 x 0 | 2 | 37 x 0 (outros 0) | sem par |
| TO | GOIATINS (95338) | 0032/0060 | 108 x 0 | 14 | 106 x 0 (outros 1) | 90 x 4 |
| TO | GOIATINS (95338) | 0032/0061 | 162 x 0 | 18 | 172 x 1 (outros 1) | 290 x 2 |
| TO | GOIATINS (95338) | 0032/0084 | 174 x 0 | 8 | 174 x 1 (outros 0) | sem par |
| TO | TOCANTÍNIA (96199) | 0005/0055 | 196 x 0 | 5 | 190 x 1 (outros 0) | 254 x 5 |
| TO | TOCANTINÓPOLIS (96210) | 0009/0184 | 59 x 0 | 3 | 59 x 0 (outros 1) | sem par |
| TO | TOCANTINÓPOLIS (96210) | 0009/0192 | 155 x 0 | 19 | 159 x 0 (outros 0) | sem par |
| PA | JACAREACANGA (04200) | 0102/0044 | 0 x 50 | 0 | 0 x 49 (outros 0) | 1 x 72 |
| PA | CHAVES (04499) | 0017/0041 | 0 x 48 | 1 | 0 x 52 (outros 1) | 0 x 39 |
| RS | CÂNDIDO GODÓI (85839) | 0166/0081 | 0 x 82 | 3 | 0 x 81 (outros 0) | 2 x 91 |
| RS | ARROIO DO PADRE (89028) | 0034/0433 | 0 x 116 | 2 | 0 x 108 (outros 5) | 7 x 73 |

## Apêndice B: seções do 2º turno com BU emitido mais de 1 hora depois do encerramento

368 seções, agrupadas por UF, município e zona. Entre parênteses, o atraso em minutos entre o encerramento e a emissão do BU. Códigos de município do TSE: 71072 São Paulo, 60011 Rio de Janeiro, 38490 Salvador, 25313 Recife.

| UF/município/zona | Seções | Seção (atraso em minutos) |
|---|---:|---|
| ac/01082/0004 | 1 | 0440 (118) |
| ba/35157/0155 | 1 | 0140 (66) |
| ba/35157/0156 | 1 | 0189 (69) |
| ba/35319/0131 | 1 | 0113 (120) |
| ba/36854/0180 | 2 | 0054 (106), 0537 (114) |
| ba/38059/0200 | 1 | 0051 (116) |
| ba/38458/0087 | 1 | 0047 (109) |
| ba/38490/0001 | 1 | 0381 (82) |
| ba/38490/0002 | 29 | 0019 (79), 0022 (79), 0023 (78), 0024 (80), 0026 (61), 0027 (68), 0032 (67), 0102 (90), 0113 (89), 0114 (91), 0142 (96), 0368 (116), 0375 (64), 0382 (61), 0392 (91), 0421 (70), 0423 (78), 0424 (69), 0429 (67), 0436 (75), 0437 (71), 0449 (71), 0450 (60), 0488 (67), 0505 (61), 0513 (78), 0538 (67), 0543 (68), 0544 (66) |
| ba/38490/0005 | 4 | 0249 (75), 0341 (72), 0406 (120), 0409 (118) |
| ba/38490/0006 | 12 | 0007 (72), 0053 (76), 0054 (72), 0058 (78), 0069 (82), 0079 (85), 0259 (88), 0281 (77), 0317 (90), 0456 (68), 0479 (76), 0486 (63) |
| ba/38490/0007 | 3 | 0182 (74), 0212 (69), 0214 (83) |
| ba/38490/0009 | 2 | 0185 (70), 0248 (110) |
| ba/38490/0010 | 1 | 0900 (75) |
| ba/38490/0013 | 2 | 0111 (115), 0328 (65) |
| ba/38490/0017 | 1 | 0413 (74) |
| ba/38490/0018 | 2 | 0335 (112), 0339 (64) |
| ba/38490/0019 | 2 | 0073 (115), 0343 (90) |
| mg/40592/0097 | 1 | 0234 (96) |
| mg/41238/0039 | 1 | 0472 (146) |
| mg/52132/0250 | 1 | 0099 (74) |
| pa/04278/0098 | 1 | 0294 (79) |
| pb/20516/0001 | 3 | 0066 (116), 0315 (75), 0331 (113) |
| pb/20516/0076 | 3 | 0383 (108), 0419 (76), 0444 (93) |
| pe/23574/0121 | 2 | 0047 (116), 0130 (105) |
| pe/24112/0067 | 1 | 0038 (78) |
| pe/24910/0010 | 2 | 0110 (94), 0113 (115) |
| pe/24910/0117 | 2 | 0104 (63), 0105 (64) |
| pe/25097/0091 | 1 | 0051 (89) |
| pe/25313/0004 | 1 | 0021 (62) |
| pe/25313/0005 | 4 | 0016 (81), 0246 (70), 0511 (78), 0528 (64) |
| pe/25313/0006 | 1 | 0372 (75) |
| pe/25313/0008 | 4 | 0082 (70), 0129 (75), 0270 (74), 0355 (66) |
| pe/25313/0009 | 14 | 0008 (116), 0058 (116), 0299 (116), 0311 (113), 0342 (67), 0380 (83), 0387 (75), 0388 (74), 0391 (77), 0395 (75), 0396 (75), 0455 (63), 0474 (65), 0499 (117) |
| pe/25313/0149 | 5 | 0039 (83), 0045 (64), 0047 (78), 0048 (66), 0052 (65) |
| pe/25356/0028 | 1 | 0067 (63) |
| pe/25593/0052 | 1 | 0109 (73) |
| pe/26131/0067 | 1 | 0104 (116) |
| pe/26271/0102 | 4 | 0039 (68), 0045 (71), 0050 (76), 0051 (71) |
| rj/58017/0116 | 2 | 0173 (120), 0202 (117) |
| rj/58122/0138 | 5 | 0024 (77), 0122 (113), 0177 (111), 0202 (112), 0269 (96) |
| rj/58130/0096 | 1 | 0542 (111) |
| rj/58432/0107 | 1 | 0025 (125) |
| rj/58530/0055 | 1 | 0444 (94) |
| rj/58599/0112 | 1 | 0046 (73) |
| rj/58653/0072 | 1 | 0454 (95) |
| rj/58653/0144 | 1 | 0311 (61) |
| rj/58777/0065 | 4 | 0044 (118), 0045 (118), 0048 (119), 0437 (118) |
| rj/58971/0036 | 1 | 0422 (116) |
| rj/58971/0087 | 1 | 0231 (77) |
| rj/58971/0132 | 1 | 0049 (85) |
| rj/58971/0135 | 1 | 0317 (101) |
| rj/58998/0037 | 3 | 0097 (114), 0156 (109), 0188 (76) |
| rj/59250/0090 | 1 | 0232 (165) |
| rj/60011/0004 | 1 | 0018 (118) |
| rj/60011/0007 | 5 | 0024 (111), 0033 (116), 0034 (114), 0460 (74), 0514 (115) |
| rj/60011/0009 | 16 | 0192 (116), 0213 (116), 0228 (113), 0230 (115), 0260 (114), 0287 (115), 0293 (105), 0296 (106), 0313 (114), 0317 (81), 0319 (113), 0320 (114), 0321 (113), 0323 (115), 0327 (114), 0472 (114) |
| rj/60011/0014 | 2 | 0403 (63), 0460 (117) |
| rj/60011/0017 | 2 | 0159 (112), 0495 (113) |
| rj/60011/0023 | 1 | 0538 (91) |
| rj/60011/0024 | 3 | 0064 (72), 0066 (73), 0070 (84) |
| rj/60011/0025 | 2 | 0632 (94), 0828 (90) |
| rj/60011/0119 | 1 | 0405 (117) |
| rj/60011/0120 | 1 | 0262 (119) |
| rj/60011/0122 | 3 | 0029 (128), 0030 (126), 0304 (132) |
| rj/60011/0123 | 7 | 0054 (70), 0071 (116), 0152 (119), 0153 (118), 0168 (115), 0173 (68), 0237 (116) |
| rj/60011/0125 | 1 | 0345 (60) |
| rj/60011/0169 | 3 | 0002 (114), 0169 (116), 0173 (112) |
| rj/60011/0170 | 1 | 0259 (67) |
| rj/60011/0179 | 1 | 0266 (122) |
| rj/60011/0180 | 1 | 0028 (64) |
| rj/60011/0182 | 1 | 0038 (117) |
| rj/60011/0185 | 4 | 0051 (115), 0144 (61), 0227 (120), 0230 (117) |
| rj/60011/0191 | 3 | 0036 (78), 0042 (77), 0043 (79) |
| rj/60011/0204 | 1 | 0216 (74) |
| rj/60011/0214 | 6 | 0030 (78), 0032 (75), 0048 (64), 0104 (75), 0129 (117), 0204 (74) |
| rj/60011/0216 | 3 | 0071 (69), 0074 (71), 0120 (63) |
| rj/60011/0238 | 2 | 0068 (111), 0131 (119) |
| rj/60011/0242 | 8 | 0001 (74), 0071 (62), 0087 (77), 0104 (83), 0146 (66), 0150 (86), 0151 (91), 0164 (118) |
| rj/60011/0243 | 3 | 0203 (77), 0215 (74), 0229 (78) |
| rj/60011/0245 | 2 | 0275 (85), 0283 (124) |
| rj/60011/0246 | 4 | 0139 (111), 0141 (73), 0156 (67), 0166 (74) |
| rn/18813/0009 | 1 | 0144 (92) |
| rs/85251/0092 | 1 | 0018 (75) |
| se/31712/0013 | 1 | 0151 (116) |
| se/32018/0004 | 1 | 0053 (78) |
| sp/61654/0014 | 1 | 0250 (135) |
| sp/62910/0033 | 1 | 0409 (88) |
| sp/64157/0401 | 1 | 0432 (94) |
| sp/66893/0217 | 1 | 0143 (60) |
| sp/68594/0318 | 1 | 0141 (72) |
| sp/71072/0001 | 8 | 0135 (61), 0155 (88), 0168 (99), 0169 (100), 0304 (96), 0312 (82), 0354 (70), 0511 (94) |
| sp/71072/0002 | 10 | 0031 (111), 0036 (115), 0049 (113), 0061 (119), 0397 (105), 0406 (104), 0417 (89), 0476 (104), 0499 (100), 0561 (103) |
| sp/71072/0004 | 22 | 0010 (71), 0083 (115), 0085 (116), 0086 (117), 0114 (101), 0122 (66), 0159 (112), 0167 (117), 0168 (115), 0169 (116), 0176 (117), 0179 (116), 0180 (119), 0181 (117), 0310 (114), 0315 (111), 0324 (118), 0328 (69), 0423 (116), 0452 (115), 0453 (114), 0456 (119) |
| sp/71072/0248 | 1 | 0402 (72) |
| sp/71072/0250 | 2 | 0147 (68), 0204 (76) |
| sp/71072/0251 | 4 | 0289 (83), 0296 (71), 0319 (79), 0324 (67) |
| sp/71072/0252 | 1 | 0208 (117) |
| sp/71072/0253 | 4 | 0057 (108), 0084 (99), 0458 (67), 0573 (120) |
| sp/71072/0254 | 5 | 0177 (65), 0178 (67), 0184 (72), 0351 (73), 0369 (71) |
| sp/71072/0256 | 1 | 0213 (62) |
| sp/71072/0257 | 13 | 0078 (75), 0136 (103), 0142 (74), 0144 (79), 0145 (104), 0271 (114), 0272 (115), 0273 (115), 0274 (115), 0275 (115), 0276 (115), 0470 (69), 0474 (116) |
| sp/71072/0259 | 1 | 0655 (113) |
| sp/71072/0328 | 26 | 0003 (97), 0005 (98), 0007 (75), 0010 (101), 0011 (100), 0018 (90), 0025 (91), 0036 (73), 0194 (94), 0199 (94), 0200 (93), 0203 (93), 0204 (94), 0206 (95), 0208 (93), 0445 (94), 0448 (94), 0730 (116), 0738 (115), 0760 (115), 0824 (93), 0864 (63), 0920 (112), 0921 (112), 0939 (105), 0978 (114) |
| sp/71072/0346 | 8 | 0562 (113), 0579 (113), 0696 (116), 0707 (118), 0708 (117), 0732 (62), 0733 (64), 0737 (62) |
| sp/71072/0350 | 1 | 0424 (81) |
| sp/71072/0351 | 1 | 0281 (77) |
| sp/71072/0352 | 3 | 0124 (70), 0277 (86), 0605 (118) |
| sp/71072/0375 | 1 | 0723 (113) |
| sp/71072/0381 | 5 | 0141 (103), 0292 (65), 0449 (63), 0729 (62), 0774 (69) |
| sp/71072/0422 | 8 | 0008 (79), 0056 (64), 0101 (66), 0238 (119), 0266 (72), 0297 (75), 0315 (72), 0317 (61) |

## Resolução dos itens 14 e 8a pelos logs

Esta seção lê o log da urna (`logd.dat`, dentro do `-log.jez`) das 368 seções do item 14 e o log do Sistema de Apuração da seção 0039/0168 de Belo Horizonte (item 8a). Script: `scripts/ele2026/emissao_tardia_logs.py`; saídas em `data/parquet/2026/t2/emissao_tardia/` (fora do git) e brutos no servidor de análise (`~/dataurnas-t2/emissao_tardia/`).

### Dados e método

- **Amostra.** As 368 seções do apêndice B (emissão mais de 1 hora depois do encerramento, refeitas a partir de `secoes_encerramento.parquet`, mesma lista) e 368 seções de **controle**: em cada zona, o mesmo número de seções com emissão até 10 minutos depois do encerramento, escolhidas por ordem pseudoaleatória fixa (sha256 da chave da seção). Todas as 368 tiveram controle na própria zona.
- **Download.** Em 27/10/2026, do pleito 3221: o `aux.json` de cada seção e o log de cada hash listado. Um processo, no máximo 2,5 requisições por segundo, 1.482 requisições, nenhuma falha e nenhum 404. Para BH 0039/0168, todos os arquivos publicados no 1º turno (pleito 3220) e no 2º (3221).
- **Correspondência entre BU e log.** A hora de encerramento do BU é a hora da linha `Procedimento de encerramento confirmado`; a hora de emissão é a da linha `Gerando relatório [BU] [INÍCIO]` (ou, quando o BU sai do Recuperador de Dados em outra urna, a da geração do `bu.dat`). Nas 736 seções as duas horas batem com o BU com diferença máxima de 1 segundo. O número de linhas `O voto do eleitor foi computado` do dia é igual ao comparecimento do BU nas 736.
- **Intervalo analisado.** Todas as linhas do log de 25/10/2026 entre o encerramento e a emissão do BU, por horário. "Maior espera" é o maior intervalo entre duas ações do operador ou do sistema, sem contar as linhas que a urna grava sozinha a cada 30 minutos (espaço em mídia, memória e tensão da rede e da bateria).

### Resposta a cada hipótese

| Pergunta | 368 tardias | 368 controles |
|---|---:|---:|
| Votos computados depois da hora de encerramento do BU | **0** | 0 |
| Nova `Urna pronta para receber votos` depois do encerramento (reabertura) | **0** | 0 |
| BU gerado mais de uma vez no dia (`Gerando relatório [BU] [INÍCIO]` ou `bu.dat`) | 0 (1 em todas) | 0 (1 em todas) |
| Mais de um hash publicado no `aux.json` | 0 | 0 |
| Seções com via extra do BU impressa (2 a 5 vias) | 8 | 14 |
| Seções com desligamento e religamento da urna no intervalo | 16 (31 ligações) | 0 |
| Seções em que a urna ficou sem a rede elétrica em algum momento do intervalo | 19 | 2 |
| Seções com erro que interrompeu o aplicativo (`Não é possível continuar a execução`) | 3 | 0 |
| Seções com troca de urna (outra urna emitiu o BU) | 2 | 0 |
| Seções que passaram pela tela de registro de mesários depois do encerramento | 368 | 368 |
| Mesários registrados depois do encerramento | 1.332 (em 353 seções) | 1.366 (em 361 seções) |

Classificação de cada seção pelo evento mais grave encontrado no intervalo (a ordem de prioridade é a da tabela):

| Classe | Tardias | Controles |
|---|---:|---:|
| Voto computado depois do encerramento | 0 | 0 |
| Reabertura da votação | 0 | 0 |
| Troca de urna antes da emissão | 2 | 0 |
| Urna desligada e religada antes da emissão | 14 | 0 |
| Urna ligada, sem reinício, na tela de registro de mesários | 352 | 368 |

**O log registra zero voto depois do encerramento nas 368 seções**, zero reabertura e um único BU por seção. Nada no log indica voto aceito, contagem refeita ou BU substituído entre o encerramento e a emissão.

### O que aconteceu nas 352 seções sem reinício

Na urna de 2026 o encerramento tem duas etapas. A primeira é `Procedimento de encerramento confirmado`: daí em diante a urna não aceita mais voto, e é essa a hora que vai para o BU como encerramento. Logo em seguida a urna pergunta `Operador indagado se ocorrerá registro de mesários` e abre a tela `Registrando mesários após a votação`, onde cada mesário se identifica por título e biometria. Só quando o operador fecha essa tela (`Operador encerrou ciclo de registro de mesários`) vêm `Inicio do Encerramento` e, um segundo depois, a geração do BU. Nos controles esse passo leva segundos: a maior espera mediana é de 0,3 minuto (máximo 4,2) e o atraso total mediano entre encerramento e emissão é de 2,0 minutos (máximo 7,8).

Nas 352 seções a urna ficou parada nessa tela de registro de mesários:

| Medida (352 seções) | Valor |
|---|---|
| Maior espera sem nenhuma ação | mediana 72,6 min; mínimo 16,9; máximo 122,8 |
| Fração do atraso total ocupada pela maior espera | mediana 92,9% |
| Início da espera (Brasília) | de 17:02:32 a 18:15:29, mediana 17:10:55 |
| Retomada (Brasília) | de 17:41:36 a 19:10:58, mediana 18:30:50 |
| Emissão do BU (Brasília) | de 18:02:19 a 19:12:08 |
| Retomadas às 19:00:00 de Brasília ou depois | 73 |

Retomada por faixa de horário de Brasília: 17:30 a 17:44, 1; 17:45 a 17:59, 16; 18:00 a 18:14, 83; 18:15 a 18:29, 77; 18:30 a 18:44, 47; 18:45 a 18:59, 93; 19:00 a 19:14, 35. Nenhuma das 352 retomou depois de 19:10:58 de Brasília.

Última linha antes da espera: `Operador confirmou o registro de mesários` (151), `Operador indagado se continua registrando mesários` (86), `Operador indagado se finaliza registro mesários` (46), `Pedido de leitura da biometria do mesário` (25), `Registrando mesários após a votação` (16), `Digitado título inválido para o registro de mesário` (12), `Operador indagado se ocorrerá registro de mesários` (7) e outras 9. Primeira linha depois da espera: `Pedido de leitura da biometria do mesário` (128), `Operador confirmou o registro de mesários` (75), `Operador indagado se finaliza registro mesários` (45), `Operador cancelou o registro de mesários` (44), `Digitado título inválido para o registro de mesário` (27), `Operador encerrou ciclo de registro de mesários` (18) e outras 15. Ou seja, a espera começa e termina dentro do registro de mesários, com a urna aguardando um comando do operador.

Exemplos (hora local, que nos quatro casos é a de Brasília):

| Seção | Eventos |
|---|---|
| SP 71072 0328/0730 | 17:07:58 `Procedimento de encerramento confirmado`; 17:08:05 `Registrando mesários após a votação`; 17:08:36 `Mesário 424334810108 registrado`; 17:10:13 `Operador confirmou o registro de mesários`; **nenhuma linha de operador até** 19:01:28 `Pedido de leitura da biometria do mesário 338764790183`; 3 mesários registrados entre 19:01:38 e 19:03:05; 19:03:15 `Operador encerrou ciclo de registro de mesários`; 19:03:16 `Inicio do Encerramento`; 19:03:17 `Gerando relatório [BU] [INÍCIO]` |
| RJ 60011 0009/0192 | 17:05:43 `Procedimento de encerramento confirmado`; 17:05:44 `Operador indagado se ocorrerá registro de mesários`; **nenhuma linha de operador até** 19:00:12 `Operador confirmou o registro de mesários`; 3 mesários registrados; 19:01:39 `Operador encerrou ciclo de registro de mesários`; 19:01:41 `Gerando relatório [BU] [INÍCIO]` |
| PE 25313 0009/0499 | 17:05:12 `Procedimento de encerramento confirmado`; 17:05:41 `Mesário 060728040833 registrado`; 17:06:16 `Operador indagado se finaliza registro mesários`; 17:09:50 `Operador confirmou o registro de mesários`; **nenhuma linha de operador até** 19:00:01 `Pedido de leitura da biometria do mesário 106805000825`; 3 mesários registrados entre 19:00:06 e 19:02:12; 19:02:28 `Operador encerrou ciclo de registro de mesários`; 19:02:29 `Gerando relatório [BU] [INÍCIO]` |
| BA 38490 0002/0019 | 17:11:56 `Procedimento de encerramento confirmado`; 17:12:24 `Mesário 147002490540 registrado`; 17:12:28 `Operador confirmou o registro de mesários`; **nenhuma linha de operador até** 18:28:12 `Pedido de leitura da biometria do mesário 176925810531`; 2 mesários registrados (18:28:17 e 18:30:02) e 4 títulos inválidos; 18:30:41 `Operador encerrou ciclo de registro de mesários`; 18:30:43 `Gerando relatório [BU] [INÍCIO]` |
| Controle SP 71072 0328/0001 | 19:00:31 `Procedimento de encerramento confirmado`; 4 mesários registrados entre 19:01:02 e 19:02:34; 19:02:52 `Operador encerrou ciclo de registro de mesários`; 19:02:54 `Gerando relatório [BU] [INÍCIO]` |

Durante as esperas a urna continuou gravando as linhas automáticas de 30 em 30 minutos, o que mostra que ficou ligada e com o aplicativo de votação aberto, sem voto computado.

Nas mesmas zonas, 78 dos 368 controles encerraram às 19:00 de Brasília ou depois, isto é, continuaram recebendo votos até o horário da prorrogação e emitiram o BU em seguida. As 368 tardias fizeram o contrário: 367 confirmaram o encerramento até 17:59 de Brasília (336 até 17:10) e só fecharam o registro de mesários e emitiram o BU depois. O log não registra o motivo da espera (orientação recebida pela mesa, ausência de mesário, decisão do presidente da mesa); registra só que a urna estava encerrada para votos e parada na tela de registro de mesários. A coincidência da retomada com o horário de 19h e com a [prorrogação](prorrogacao-votacao-2turno-2026.md) é temporal; o motivo é matéria da ata da mesa.

### As 16 seções com reinício ou troca de urna

Todas com fuso UTC-3 (hora local = Brasília).

| Seção | Encerramento | Emissão | O que o log registra no intervalo |
|---|---|---|---|
| BA 38490 0002/0032 | 17:11:51 | 18:18:53 | registro de mesários aberto; 17:18:19 `Urna desligada pela chave`; religada 17:21:26; volta ao registro 17:27:03; 4 mesários registrados entre 17:28:09 e 18:18:38; BU 18:18:53 |
| BA 38490 0002/0513 | 17:09:56 | 18:27:53 | 3 mesários até 17:11:33; 18:21:46 desligada pela chave; religada 18:22:23; 1 mesário; BU 18:27:53 |
| BA 38490 0006/0058 | 17:09:39 | 18:27:24 | 1 mesário 17:10:07; 17:41:25 desligada pela chave; religada 17:41:58; aplicativo aberto 17:44:18; volta ao registro só 18:25:26; BU 18:27:24 |
| BA 38490 0006/0486 | 17:10:54 | 18:13:44 | 4 mesários até 17:13:33; 18:07:02 desligada pela chave; religada 18:07:33; BU 18:13:44 |
| MG 40592 0097/0234 | 17:00:49 | 18:36:09 | urna religada às 17:03:31 sem registro de desligamento, já `Urna operando com bateria interna` e `Bateria interna com carga crítica`; registro de mesários aberto 17:08:51; nova ligação às 18:30:35, sem registro de desligamento, com `Urna operando com bateria externa`; BU 18:36:09 |
| MG 41238 0039/0472 | 17:01:55 | 19:27:13 | 17:06:12 desligada pela chave; ligada 17:06:55 sem nenhuma linha seguinte; nova ligação 19:22:29, `Urna ligada desconectada da rede CA em [0.00V]`; BU 19:27:13 |
| MG 52132 0250/0099 | 17:03:04 | 18:17:29 | 3 mesários até 17:04:24; 17:06:09 `Erro inesperado (5330) ERROR starting image acquisition` (leitor biométrico); 17:10:22 desligada pela chave; religada 18:14:23; BU 18:17:29 |
| PA 04278 0098/0294 (reserva) | 17:04:07 | 18:23:28 | urna 02156713: 17:06:11 erro 5330 do leitor biométrico; 8 desligamentos pela chave e 7 religamentos até 18:09:46, com 7 erros no total (5330, 5328 e 5326, este `ERROR opening the biometric reader`); às 18:15:46 liga a urna 02192172, que lê a mídia da anterior, registra 2 mesários e emite o BU 18:23:28 |
| PB 20516 0076/0383 | 19:00:38 | 20:48:40 | 19:00:38 `Gravando o estado da urna (1175) Ocorreu um erro durante a sincronização`; 4 desligamentos pela chave e religamentos (19:02, 19:37, 20:06, 20:19); aplicativo de votação aberto 20:26:59; BU 20:48:40 |
| PE 25356 0028/0067 | 17:59:07 | 19:02:03 | 18:01:03 desligada pela chave; religada 18:05:20; registro aberto 18:10:56; 4 mesários entre 19:00:27 e 19:01:56; BU 19:02:03 |
| RJ 58432 0107/0025 | 17:08:08 | 19:13:39 | 4 mesários até 17:10:22; 17:17:41 `Urna ligada desconectada da rede CA em [0.00V]`, 17:19:59 bateria `[CRÍTICA]`; sem linha até nova ligação 19:09:23 (com rede elétrica); BU 19:13:39 |
| RJ 59250 0090/0232 | 17:00:46 | 19:45:31 | 17:00:55 desligada pela chave na pergunta do registro de mesários; ligada 17:02:56 sem nenhuma linha seguinte; nova ligação 19:33:28; BU 19:45:31 |
| RJ 60011 0009/0213 | 17:07:58 | 19:03:22 | 17:32:54 desligada pela chave; religada 17:34:14; registro aberto 17:40:00; 3 mesários entre 19:00:49 e 19:03:02; BU 19:03:22 |
| RJ 60011 0122/0304 | 17:04:29 | 19:16:03 | 18:12:17 desligada pela chave; religada 18:13:04; 15 segundos na bateria às 18:58:37; 4 mesários entre 19:14:00 e 19:15:46; BU 19:16:03 |
| SP 61654 0014/0250 (reserva que encerrou a seção) | 17:02:28 | 19:17:53 | urna 01786184: 17:06:10 desligada pela chave no registro de mesários; às 18:57:43 liga a urna de contingência 01794345; 19:14:17 `Iniciando aplicação RECUPERADOR DE DADOS`; 19:15:44 `Recuperando urna de votação com resultado não gerado`; BU impresso e `bu.dat` gerado às 19:17:53 |
| SP 71072 0004/0324 | 17:04:40 | 19:02:14 | 2 mesários até 17:05:18; 17:27:53 desligada pela chave; religada 17:28:29; registro aberto só 19:01:06; 2 mesários; BU 19:02:14 |

Em nenhuma das 16 o log registra voto depois do encerramento ou nova abertura. Em 4 delas a urna voltou a ser ligada sem nenhum registro de desligamento antes (nem `Urna desligada pela chave`, nem `Desligando a urna`, nem `Fechando o arquivo de Log`), isto é, parou sem o desligamento normal: MG 40592 0234 (duas vezes), MG 41238 0472, RJ 58432 0025 e RJ 59250 0232. Na de São Paulo 61654 o BU não foi gerado pela urna da seção: o Recuperador de Dados leu a mídia de votação da urna original, que já tinha o encerramento confirmado.

### Energia

Em 19 tardias e 2 controles a urna registrou, no intervalo, `Urna operando na bateria interna` ou `Urna ligada desconectada da rede CA`. Em 13 dessas 19 tardias a urna não reiniciou e continuou na tela de registro de mesários; entre elas estão as três seções da zona 0065 de RJ 58777 (0044, 0045 e 0048), que passaram à bateria entre 18:47:23 e 18:50:47. Falta de energia ou cabo desligado aparece, portanto, em uma minoria das 368 e não explica o padrão; e em nenhuma delas houve voto depois do encerramento.

### Conclusão do item 14

O atraso de emissão nas 368 seções não é voto tardio, reabertura nem BU refeito. Em 352 a urna ficou encerrada para votos e parada, ligada, na tela de registro de mesários, por 17 a 123 minutos (mediana 73), e a mesa só voltou a operar a urna entre 17:41 e 19:11 de Brasília, com o BU emitido entre 18:02 e 19:12; em 16 a espera envolve desligamentos, falta de rede elétrica, erros do leitor biométrico ou da gravação de estado e, em 2, troca de urna. O conteúdo do BU (votos até o encerramento) é confirmado pelo log, com o número de votos do log igual ao comparecimento do BU em todas as 368. Gravidade revista: **explicável** quanto à integridade da contagem; o motivo da espera da mesa continua dependendo da ata.

### Item 8a: Belo Horizonte, zona 0039, seção 0168, 1º turno

Arquivos publicados no 1º turno (um único hash, recebido em 04/10/2026 às 22:15:29): `-logsa.jez`, `-sa.vsc`, `-rdv.dat` e `-busa.dat`. Não há `-log.jez` nem `-bu.dat` de urna de votação. A seção não foi apurada só por cédula: o BU do SA é do tipo `saMistaBUImpressoCedula`, com `tipoapuracao` = `mistaBU`, ou seja, **BU impresso de urna digitado no SA mais cédulas**.

O que dizem o BU e o RDV do SA:

| Campo | Valor |
|---|---|
| Equipamento do SA | 2254078, urna de contingência carregada em 22/09/2026 para a "seção 0000" da zona 0039 |
| Urna de origem (`numeroInternoUrnaOrigem`) | **2409879** |
| Junta e turma | 1 e 1 |
| Motivo no BU (`motivoApuracao`) | valor 5 do enumerado `MotivoApuracaoMistaComBU`, que a especificação chama `urnaChegouAposInicioVotacao` |
| Motivo no log do SA | `Motivo da apuração: Urna encerrada com eleitores na fila` |
| Histórico de códigos de carga | 754795141680322122516390 e 178937178903421025448475 (este é o da urna 2254078) |
| Emissão do BU do SA | 04/10/2026 22:07:21 |
| Bloco do RDV com origem `bu` (urna 2409879) | 261 eleitores; Presidente: 13 = 118, 22 = 111, 30 = 3, 55 = 7, 70 = 5, 14 = 1, branco 3, nulo 13 |
| Bloco do RDV com origem `cedula` | 20 eleitores; Presidente: 13 = 12, 22 = 6, 30 = 1, branco 1 |
| Total do BU | 281 (13 = 130, 22 = 117, 30 = 4, 55 = 7, 70 = 5, 14 = 1, branco 4, nulo 13), igual à soma dos dois blocos |

O nome do enumerado no BU e o texto do log não coincidem; os dois estão registrados como acima, e este relatório não escolhe entre eles.

Linha do tempo do log do SA (04/10/2026, hora local de Brasília):

| Hora | Evento |
|---|---|
| 20:31:49 | urna 2254078 ligada |
| 20:33:41 | `Iniciando aplicação - SISTEMA DE APURAÇÃO OFICIAL PRIMEIRO TURNO` |
| 20:34:58 | `Início dos trabalhos do SA`; zerésima de apuração impressa |
| 20:36:13 | `Tipo de apuração selecionada (DIGITAÇÃO DO BU MAIS CÉDULAS)` |
| 20:39:03 | seção em apuração: município 41238, zona 0039, seção 0168 |
| 20:40:14 a 20:46:02 | `Código verificador aceito`; digitação dos códigos de carga |
| 20:47:35 | `Apuração cancelada` |
| 20:48:03 | `Tipo de apuração selecionada (RECEPÇÃO DE MÍDIA DE RESULTADO MAIS CÉDULAS)`; `Solicitada inserção de mídia com resultado parcial gerado pelo RED` |
| 20:48:13 | volta a `DIGITAÇÃO DO BU MAIS CÉDULAS`; 20:48:41 seção 0168 de novo |
| 20:49:29 a 20:51:06 | `Código verificador aceito`; digitação dos códigos de carga; `Código verificador aceito` |
| 20:58:58 | `Informações complementares gravadas` |
| 20:59:15 | `Motivo da apuração: Urna encerrada com eleitores na fila`; zerésima da seção impressa |
| 21:00:56 a 21:45:25 | `Início da digitação de BU`: Dep. Fed. (21:00:56 a 21:18:19), Dep. Est. (até 21:41:26), Sen. (até 21:43:10), Gov. (até 21:44:20), Pres. (21:44:20 a 21:45:25) |
| 21:45:28 a 22:07:19 | apuração das cédulas: majoritária federal (até 21:52:32), majoritária estadual (até 22:00:00), proporcional (até 22:07:19) |
| 22:07:21 | BU gerado; 2 vias impressas |
| 22:09:13 | `busa.dat`, `rdv.dat`, `imgbusa.dat` e `hash.dat` gravados |

O log do SA não registra voto de urna (`O voto do eleitor foi computado`): 0 linhas, como esperado num equipamento de apuração.

Leitura: dos 281 eleitores, **261 votaram na urna 2409879** e entraram pela digitação do BU impresso dessa urna; **20 votaram em cédula** e foram apurados no SA. A urna 2409879 não aparece como origem de nenhum BU publicado no 1º ou no 2º turno (consulta a `ref_secoes_2026_t1` e `v_bu_ultima`: 0 linhas), e o log dela não foi publicado. No 2º turno a seção usou a urna 2401024, carregada em 15/10/2026, cujo log só tem datas de 15/10, 19/10 e 25/10 e registra 365 votos, igual ao BU.

Isto resolve o mecanismo: a apuração da seção foi mista, o BU impresso da urna original foi digitado e as cédulas foram apuradas no SA. O comparecimento de 56,1% se divide em 52,1% na urna (261 de 501) e 4,0% em cédula (20). Continua **precisando esclarecimento** o que o log do SA não mostra: a hora em que a urna 2409879 foi encerrada, quantos eleitores estavam na fila e por que o motivo do BU e o do log divergem. Isso está na ata da mesa e no log da urna 2409879, que não foi publicado.
