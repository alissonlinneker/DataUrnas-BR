# RDV x BU x log da urna e padrões de votação no log (2026, 1º e 2º turno)

> **Nenhuma divergência RDV x BU.** Nas 8.000 seções do 2º turno e nas 2.997 seções do 1º turno conferidas aqui, a recontagem voto a voto do RDV dá exatamente o resultado do BU em todos os cargos (Presidente: 13, 22, outros, brancos e nulos), e o RDV, o BU e o log têm o SHA-512 igual ao hash assinado no `.vsc`, com assinatura válida em 100% dos casos. Não há seção a destacar.

## Resumo

| Conferência | 1º turno | 2º turno |
|---|---|---|
| Seções com RDV, BU e `.vsc` baixados | 2.997 | 8.000 |
| RDV = BU em todos os cargos | 2.997 (14.986 linhas seção x cargo) | 8.000 (8.253 linhas) |
| Presidente no RDV: 13 / 22 | 316.077 / 314.305 | 1.162.942 / 962.653 |
| Presidente no BU: 13 / 22 | 316.077 / 314.305 | 1.162.942 / 962.653 |
| Brancos / nulos (RDV = BU) | 13.208 / 21.446 | 24.884 / 52.856 |
| `.vsc` lista o RDV e o SHA-512 confere | 2.997 | 8.000 |
| Assinatura do `.vsc` e do RDV válidas (Ed521) | 2.997 | 8.000 |
| SHA-512 do log confere com o `.vsc` | 2.997 | 2.997 (as 5.003 tardias não têm log nesta amostra) |
| Votos computados no log = comparecimento do BU | 2.997 de 2.997 (717.871 votos) | 2.997 de 2.997 (734.608 votos) |
| Voto antes da "Urna pronta" ou depois do "Inicio do Encerramento" | 0 | 0 |
| Voto computado sem "Eleitor foi habilitado" antes | 0 | 0 |
| Menor intervalo entre dois votos computados da mesma urna | 23 s | 18 s |

1. **RDV x BU: zero divergência em 10.997 pares seção x turno.** Inclui as 5.003 seções do 2º turno que encerraram mais tarde (todas depois das 19:00 de Brasília pelo BU) e as 2.997 da amostra de biometria nos dois turnos. As mesmas 8.000 seções também conferem no 1º turno pela recontagem nacional já publicada (`data/parquet/2026/rdv/`, 499.206 seções, 0 divergências).
2. **O log fecha com o BU, voto por voto.** Cada "O voto do eleitor foi computado" tem uma habilitação antes, cai entre a abertura e o encerramento da mesma urna, e a soma por seção é igual ao comparecimento. A forma de habilitação lida no log bate com os três campos de biometria do BU: no 2º turno, 44.056 eleitores sem digital no log e no BU, 628.135 biométricos no log contra 628.159 no BU e 62.417 manuais contra 62.393 (24 eleitores de diferença em 734.608, efeito de eleitor suspenso e retomado).
3. **Nenhum ritmo impossível.** O ciclo habilitação até voto computado tem mínimo de 3 s com seis cargos no 1º turno e de 2 s com um cargo no 2º; nenhum eleitor ficou abaixo de 2 s por cargo confirmado. Não há dois votos da mesma urna a menos de 18 s.
4. **Habilitação manual em bloco existe, mas tem causa técnica.** Sequências longas de habilitação manual aparecem quase só nas seções em que o leitor de digitais falhava (estrato `extremo_bu` da amostra de biometria, maioria UE2013 e UE2015): sequência máxima de 201 eleitores, ao longo do dia. Fora desse estrato, a fração de seções com p < 0,01 no teste de permutação é 0,9% nos dois turnos, igual ao acaso (1%). Eleitores sem biometria cadastrada, a via mais simples para votar no lugar de um ausente, não formam blocos além do acaso (0,7% e 0,8% com p < 0,01) e não se concentram no fim do dia.
5. **Diferença sistemática 1T x 2T: "Problema ao desmontar a MR".** Mensagem de nível ERRO no dia da eleição em 2.993 das 2.997 urnas do 2º turno (3.404 ocorrências), ausente no dia do 1º turno. Nos logs inspecionados ela surge na inicialização do aplicativo, antes da "Urna pronta para receber votos", e também nos dias de preparação (15 e 17/10); não afeta nenhuma contagem, mas merece explicação do TSE. Sem ela, os erros do dia são 164 no 1º turno e 140 no 2º.

Pergunta: o registro embaralhado de cada voto (RDV) bate com o Boletim de Urna (BU) e com o log de cada seção, nos dois turnos? E o log, lido eleitor a eleitor, mostra voto fora de hora, ritmo impossível, blocos suspeitos de habilitação manual ou urna em estado incoerente?

| Arquivo | Para quê |
|---|---|
| `scripts/ele2026/rdv_log_auditoria.py` | amostra, download (3 req/s, um processo), recontagem do RDV, conferência com o `.vsc`, leitura do log eleitor a eleitor e relatório |
| `data/parquet/2026/t2/rdv_log/` (fora do git) | `amostra.parquet`, `rdv_secoes.parquet`, `rdv_cargos.parquet`, `logs_secoes.parquet`, `logs_horas.parquet`, `resumo.json`, `tabelas.md` |

Os arquivos brutos (`-rdv.dat`, `-bu.dat`, `-vota.vsc`) ficam no servidor de análise, em `~/dataurnas-t2/rdv_log/brutos/t1/` e `t2/`; os logs são os da amostra de biometria, em `~/dataurnas-t2/biometria/brutos/`. Todo número deste relatório sai de `resumo.json` ou `tabelas.md`.

Reprodução (no servidor de análise; a etapa `amostra` roda onde estão os Parquet de biometria e de impacto):

```sh
python3 scripts/ele2026/rdv_log_auditoria.py amostra
python3 -I scripts/ele2026/rdv_log_auditoria.py baixar --brutos ~/dataurnas-t2/rdv_log/brutos --taxa 3
python3 -I scripts/ele2026/rdv_log_auditoria.py processar --brutos ~/dataurnas-t2/rdv_log/brutos \
    --brutos-log ~/dataurnas-t2/biometria/brutos
python3 scripts/ele2026/rdv_log_auditoria.py relatorio
```

## 1. Amostra

| Parte | Seções | Turnos | Critério |
|---|---|---|---|
| Biometria | 2.997 | 1º e 2º | a mesma amostra de `docs/biometria-1t-2t-2026.md` (2.038 aleatórias, 359 extremos de biometria no BU, 300 atípicas de viradas, 300 tardias), com o log dos dois turnos já no servidor |
| Tardias | 5.003 | 2º | seções com papel `tardia` em `impacto/amostra_logs.parquet` (encerramento depois das 17:30 de Brasília e log já lido), fora da parte de biometria, das mais tardias para as menos tardias até completar 8.000; o corte ficou em 120,63 minutos depois das 17h (19:00 de Brasília). Ficaram de fora 2.270 tardias elegíveis |
| **Total** | **8.000** | | 10.997 pares seção x turno |

Download de 27/10/2026: 32.991 arquivos (`-rdv.dat`, `-bu.dat`, `-vota.vsc`), 799.305.085 bytes, um processo a 3 req/s, sem nenhum 404, 429 ou falha. O nome dos arquivos segue o padrão do `aux.json` (`o03221<uf><mun><zona><seção>-rdv.dat`, conferido numa seção) e o `aux.json` só seria lido em caso de 404, o que não ocorreu. O hash do diretório é o do BU publicado (o mesmo das outras análises do 2º turno).

## 2. RDV x BU

Método (o mesmo da recontagem nacional do 1º turno, `analyzer/rdv_recontagem.py`): o RDV (`spec/v2/rdv.asn1`, `EntidadeResultadoRDV`) é decodificado e cada registro é recontado por cargo: voto nominal pelo número digitado, legenda pelos dois primeiros dígitos, branco e "branco após suspensão" como branco, nulo, "nulo após suspensão" e "nulo por repetição" como nulo. O total de cada cargo é comparado com o BU do mesmo conjunto de arquivos; também se confere registros do RDV = comparecimento x escolhas e a estrutura (seção, cargos repetidos). Para Presidente, o BU é lido também por `bu_to_rows(raw, eleição, 1)` (6257 no 1º turno, 6258 no 2º), a leitura usada no resto do projeto, e comparado campo a campo com o RDV: 13, 22, outros nominais, legenda, brancos, nulos e total.

| Item | 1º turno | 2º turno |
|---|---|---|
| Pares seção x turno | 2.997 | 8.000 |
| RDV decodificado e estrutura válida | 2.997 | 8.000 |
| Registros do RDV | 4.298.941 | 2.261.688 |
| Comparecimento do BU | 717.871 | 2.203.335 |
| Linhas seção x cargo conferidas / iguais | 14.986 / 14.986 | 8.253 / 8.253 |
| Presidente: seções com RDV = BU em todos os campos | 2.997 | 8.000 |
| Presidente, total RDV / BU | 717.871 / 717.871 | 2.203.335 / 2.203.335 |
| 13 (RDV = BU) | 316.077 | 1.162.942 |
| 22 (RDV = BU) | 314.305 | 962.653 |
| Outros nominais (RDV = BU) | 52.835 | 0 |
| Brancos (RDV = BU) | 13.208 | 24.884 |
| Nulos (RDV = BU) | 21.446 | 52.856 |

No 2º turno os registros do RDV passam do comparecimento porque 252 seções também votaram Governador (e uma votou Prefeito, eleição suplementar na mesma urna); por cargo, registros = comparecimento em todas. Cargos conferidos no 1º turno: Presidente, Governador, Senador e Deputado Federal (2.997 cada), Deputado Estadual (2.968), Deputado Distrital (29) e um cargo de consulta (código 25).

Tipo de urna no RDV: no 2º turno, 7.915 seções de urna da seção, 220 de urna de reserva (`reservaSecao`) e 1 `reservaEncerrandoSecao`; todas conferem. Nenhuma seção da amostra tem BU do Sistema de Apuração (`-busa.dat`), então todas as conferências são de RDV gerado pela própria urna.

### Assinatura (`-vota.vsc`)

Para cada par, `parsers/signature.verificar_vsc` confere: o SHA-512 do conteúdo assinado contra o hash autoassinado (partes de software e de hardware), a assinatura de hardware do conteúdo com a chave do certificado embutido e a assinatura individual de cada arquivo listado. Depois, o SHA-512 do RDV, do BU e do log baixados é comparado com o hash assinado de cada um.

| Item | 1º turno | 2º turno |
|---|---|---|
| `.vsc` com assinatura válida (Ed521) | 2.997 | 8.000 |
| `.vsc` lista o `-rdv.dat` | 2.997 | 8.000 |
| SHA-512 do RDV = hash assinado; assinatura do RDV válida | 2.997 | 8.000 |
| SHA-512 do BU = hash assinado; assinatura do BU válida | 2.997 | 8.000 |
| SHA-512 do log = hash assinado | 2.997 | 2.997 |

A cadeia do certificado até a AC da urna não é validada (os certificados das AC não vêm nos arquivos); ver `docs/certificados-2turno-2026.md`.

## 3. O log eleitor a eleitor

Logs: os 5.994 `-log.jez` da amostra de biometria (2.997 seções, dois turnos), todos com SHA-512 igual ao assinado no `.vsc`. Só as linhas com a data do turno entram (o log do 2º turno acumula o do 1º). Para cada eleitor, o script segue a sequência "Identificador do eleitor digitado pelo mesário", pedidos de digital, "Tipo de habilitação do eleitor [...]", "Mesário N habilitou o eleitor", "Eleitor foi habilitado", "Voto confirmado para [cargo]" e "O voto do eleitor foi computado", e classifica a habilitação em:

- **biométrica**: "Tipo de habilitação do eleitor [biométrica]";
- **manual**: houve pedido de digital, ela não foi reconhecida e o eleitor foi habilitado pelo ano de nascimento (com mesário identificado pela digital ou não);
- **sem digital**: nenhum pedido de digital, ou seja, eleitor sem biometria cadastrada, habilitado pelo documento.

As métricas de horário vêm de `analisar_log_tempo` (o mesmo código da recontagem nacional).

### 3.1 Contagem e horário

| Item | 1º turno | 2º turno |
|---|---|---|
| Votos computados no log | 717.871 | 734.608 |
| Comparecimento do BU | 717.871 | 734.608 |
| Seções com log diferente do BU | 0 | 0 |
| Votos antes da "Urna pronta para receber votos" | 0 | 0 |
| Votos depois do "Inicio do Encerramento" | 0 | 0 |
| Votos com data diferente do dia | 0 | 0 |
| Voto computado sem habilitação antes | 0 | 0 |
| Votos com zero cargos confirmados | 0 | 0 |
| Votos antes das 8h de Brasília | 20 (1 seção) | 37 (1 seção) |
| Inversões de relógio, "Data e hora atualizada" ou ajuste de hora no dia | 0 | 0 |
| Seções com mais de 60 min sem voto | 66 | 151 |

Os votos "antes das 8h" são todos da seção AM 02755 (São Paulo de Olivença), zona 0022, seção 0070: urna pronta às 06:00:01 e primeiro voto às 06:03 no horário local. O município fica no fuso UTC-5 (lista já usada em `docs/encerramento-tardio-2turno-2026.md`), mas `analyzer/timezones.py` o trata como UTC-4; com o fuso certo, o primeiro voto foi às 08:03 de Brasília. É erro da tabela de fusos do projeto, não da urna. As lacunas de 60 minutos do 2º turno ficam no fim da tarde, quando quase não havia eleitor (votação de um cargo, sem fila): em 135 das 151 seções o último voto foi depois das 15h locais.

**Votos computados por hora de Brasília** (soma das 2.997 seções; a hora é a da urna convertida pelo fuso do município):

| Hora | 1º turno | 2º turno |
|---|---|---|
| 8h | 67.905 | 122.656 |
| 9h | 77.843 | 115.032 |
| 10h | 83.083 | 110.086 |
| 11h | 85.701 | 94.259 |
| 12h | 83.842 | 73.867 |
| 13h | 80.284 | 64.232 |
| 14h | 77.047 | 60.448 |
| 15h | 73.226 | 56.362 |
| 16h | 64.756 | 37.319 |
| 17h | 18.824 | 281 |
| 18h | 4.369 | 66 |
| 19h | 770 | 0 |
| 20h e depois | 221 | 0 |

No 2º turno, com um só cargo e sem fila, a votação se concentrou na manhã e praticamente acabou às 17h: 347 votos depois das 17h de Brasília nas 2.997 seções, contra 24.184 no 1º turno. Inclui as 300 seções tardias da amostra de biometria: nelas também não há voto computado depois das 19h, ou seja, o encerramento tardio dessas seções não corresponde a votos tardios no log (ver `docs/encerramento-tardio-2turno-2026.md`).

### 3.2 Ritmo

| Item | 1º turno | 2º turno |
|---|---|---|
| Cargos confirmados por eleitor (moda por seção) | 6 em 2.994 seções | 1 em 2.765, 2 em 231 |
| Ciclo habilitação até voto computado, mínimo | 3 s | 2 s |
| Mediana por seção (mediana das seções) | 56 s | 11 s |
| Eleitores com ciclo < 5 s | 9 | 6.273 |
| Eleitores com ciclo < 15 s | 1.380 | 566.260 |
| Eleitores com menos de 2 s por cargo confirmado | 0 | 0 |
| Eleitores com menos de 3 s por cargo confirmado | 20 (20 seções) | 9 (9 seções) |
| Menor intervalo entre dois votos computados (mesma urna) | 23 s | 18 s |
| Intervalos < 10 s entre votos | 0 | 0 |
| Máximo de votos num minuto / em 10 min / em 60 min | 3 / 14 / 68 | 3 / 21 / 101 |

O limiar de 15 s pedido para "ritmo impossível" não serve para o 2º turno: com um só cargo, o eleitor digita dois números e confirma, e 77% dos eleitores levaram menos de 15 s entre a habilitação e o voto computado (a mediana das seções é 11 s). A medida usada é o tempo por cargo confirmado. Ninguém ficou abaixo de 2 s por cargo; os 29 casos entre 2 e 3 s por cargo são um eleitor por seção (2 s para um cargo no 2º turno, 15 a 17 s para seis cargos no 1º), compatíveis com eleitor rápido ou voto em branco. O intervalo entre votos consecutivos, que inclui a identificação do eleitor seguinte pelo mesário, nunca fica abaixo de 18 s; o pico de 101 votos numa hora (36 s por eleitor) é de seção grande na manhã do 2º turno. Não há sequência de votos sem a presença de eleitor.

### 3.3 Habilitação manual em sequência

A preocupação: mesário habilitando à mão, em bloco, eleitores ausentes. Para cada seção, a ordem dos eleitores no log é embaralhada 400 vezes e se mede a probabilidade de a maior sequência de habilitações do tipo ser tão longa quanto a observada (p de permutação; menor valor possível 0,0025). Sob ordem aleatória, cerca de 1% das seções testadas teria p < 0,01.

| Tipo | Estrato | Seções testadas (1T / 2T) | p < 0,01 (1T / 2T) | Maior sequência (1T / 2T) | Sequência de 5 ou mais no fim do dia (1T / 2T) |
|---|---|---|---|---|---|
| Manual | extremo de biometria no BU | 276 / 282 | 92 / 76 | 201 / 139 | 44 / 28 |
| Manual | demais | 1.580 / 1.590 | 15 (0,95%) / 14 (0,88%) | 32 / 58 | 1 / 1 |
| Sem digital | extremo de biometria no BU | 204 / 196 | 5 / 5 | 14 / 12 | 2 / 1 |
| Sem digital | demais | 1.064 / 1.098 | 7 (0,66%) / 9 (0,82%) | 15 / 17 | 2 / 0 |

- **Fora das seções com leitor problemático, a habilitação manual se distribui como acaso** nos dois turnos. As seções com p < 0,01 nesse grupo têm sequências curtas (3 a 8 eleitores), espalhadas ao longo do dia, quase todas de manhã (`tabelas.md`).
- **As sequências longas são de leitor de digitais.** Estão no estrato de seções em que o BU já mostrava a maioria habilitada por ano de nascimento (130 das 153 seções desse tipo no 1º turno usavam UE2013, `docs/biometria-1t-2t-2026.md`). Nelas a sequência dura horas (por exemplo ES 56995/0026/0651 no 1º turno: 274 de 279 eleitores manuais, 201 seguidos) e costuma terminar com a troca da urna. Cada eleitor manual passa pelas quatro tentativas de digital, pela conferência do ano de nascimento e pela digital do mesário, num ciclo de cerca de um minuto.
- **Sem biometria cadastrada, que é a via sem digital alguma, não há bloco além do acaso** e não há concentração no fim do dia: 22 eleitores sem digital depois das 17h no 2º turno, em 2.997 seções.
- O único caso de sequência manual que termina o dia fora do estrato de leitor é PA 04723/0080/0254 no 2º turno (seção da lista de atípicas de viradas): os 7 últimos eleitores, das 15:26 às 15:59, habilitados à mão, cada um com quatro tentativas de digital, conferência do dado e digital do mesário registradas. É compatível com cansaço do leitor no fim do dia; numa seção de 162 eleitores com 16 manuais, p = 0,0025. Não é prova de nada, mas é a seção a olhar primeiro se o TSE abrir as imagens de digitais das habilitações manuais (`wsqman.jez`, gerado pela urna e não publicado).

Habilitação manual no total: 9,28% dos eleitores no 1º turno e 8,50% no 2º; sem digital, 5,87% e 6,00%. A correlação da taxa manual da mesma seção entre os turnos é 0,45; 55 seções subiram 20 pontos ou mais e 119 caíram 20 pontos ou mais, todas no estrato de leitor problemático (troca de urna entre os turnos).

### 3.4 Reinícios, erros, carga e oficialização

| Item | 1º turno | 2º turno |
|---|---|---|
| Seções com mais de uma "Urna pronta para receber votos" | 254 | 219 |
| Seções com urna religada durante a votação | 189 | 153 |
| Seções com mais de uma urna no log (substituição) | 64 | 70 |
| Eventos ERRO no dia (sem "Problema ao desmontar a MR") | 164 em 88 seções | 140 |
| "Problema ao desmontar a MR" no dia | 0 | 3.404 em 2.993 seções |
| "Turno da UE" no dia | 1º turno em 2.992 seções | 2º turno em 2.912; 1º e 2º em 82 |
| Código de carga do BU presente no log | 2.997 | 2.997 |
| Carga no dia da eleição | 0 | 0 |

- Os erros do dia são de periférico: falha de captura da digital, leitor biométrico que não abre, LED e LCD do terminal do mesário, impressora, mídia externa ausente. Os reinícios durante a votação se concentram onde o leitor falhava: 181 dos 342 pares seção x turno com urna religada são do estrato de extremos de biometria, que é 12% da amostra.
- As 82 seções com "Turno da UE: 1º turno" no dia do 2º turno são inicializações em que o aplicativo lê primeiro a configuração gravada e em seguida passa a "ELEIÇÃO OFICIAL SEGUNDO TURNO"; 70 delas tiveram troca de urna. Em todas, a votação ocorreu com o aplicativo do 2º turno.
- Código de carga: o código do BU está gravado no log ("Código de carga ... gravado na tabela de correspondência") em 100% das seções, e nenhuma carga ocorreu no dia da eleição. Entre os turnos, 2.877 seções mantiveram o código; 120 mudaram: 112 por troca da urna e 8 por nova carga da mesma urna entre 15 e 23/10 (sete delas em ES 56995, zonas 0026 e 0053, região de leitor problemático no 1º turno).
- "Problema ao desmontar a MR" é a única diferença sistemática entre os turnos: aparece em quase todas as urnas no 2º turno e não aparece no 1º. A MR é a mídia de resultado; a mensagem surge na inicialização do aplicativo, também nos dias de preparação, e nenhuma contagem do log ou do BU difere nessas seções.

## 4. Conclusão

| Achado | Gravidade |
|---|---|
| RDV x BU: 0 divergência em 10.997 pares seção x turno, todos os cargos | nenhuma |
| RDV, BU e log com SHA-512 igual ao assinado e assinatura Ed521 válida | nenhuma |
| Log = BU em votos (1.452.479 votos) e nas três formas de habilitação (diferença de 24 eleitores em 734.608) | nenhuma |
| Nenhum voto fora da sequência abertura/encerramento, sem habilitação ou em outra data | nenhuma |
| Nenhum ritmo fisicamente impossível; menor intervalo entre votos 18 s | nenhuma |
| Sequências longas de habilitação manual, explicadas por leitor de digitais (UE2013 e UE2015) | baixa (operacional) |
| PA 04723/0080/0254 (2T): 7 últimos eleitores habilitados à mão | baixa, a verificar com `wsqman.jez` |
| "Problema ao desmontar a MR" em 2.993 das 2.997 urnas no 2º turno | baixa, pedir explicação ao TSE |
| AM 02755 com votos "antes das 8h": erro da tabela de fusos do projeto | nenhuma (corrigir `timezones.py`) |

Nesta amostra, nada nos arquivos públicos da urna indica voto inserido, alterado ou removido: o RDV, que é o registro de cada voto, soma exatamente o BU; o log registra um eleitor habilitado para cada voto, no horário de votação; e as assinaturas fecham. O que esses arquivos não podem mostrar é se o eleitor habilitado era de fato quem dizia ser quando a habilitação foi manual ou sem biometria cadastrada; para isso seria preciso o caderno de votação e as imagens de digitais das habilitações manuais, que a urna grava mas o TSE não publica.

Limites: amostra de 8.000 seções no 2º turno (1,6% do país), com peso das seções que encerraram tarde; o log eleitor a eleitor cobre 2.997 seções; o RDV é embaralhado por desenho e não permite ligar voto a eleitor nem a horário.
