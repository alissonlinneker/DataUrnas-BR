# Log x BU: investigação das seções divergentes (eleição 2026, 1º turno, pleito 3220)

Data da verificação: 15/10/2026.

Na recontagem nacional, a contagem de votos no log de cada seção (eventos "O voto do eleitor foi computado" do dia da eleição) foi comparada com o comparecimento do BU. Na primeira rodada, 45 seções divergiram (soma -591). Os arquivos dessas 45 seções, e da seção vizinha BA 39934/0183/0181, foram baixados de novo do TSE (`https://resultados.tse.jus.br/oficial/ele2026/arquivo-urna/3220/dados/...`) e examinados linha a linha. Este documento registra o que foi encontrado.

**Situação depois das correções:** o leitor de log foi corrigido (item B) e as seções com BU do Sistema de Apuração saíram da comparação (item A). Restam **9 seções de urna** com log diferente do BU, soma **-59**, todas explicadas abaixo (itens C, D e E). Em todas as seções o RDV recontado é igual ao BU e o SHA-512 do pacote confere com o valor assinado: nenhuma das causas afeta o resultado, só a trilha de eventos do log.

## Resumo

| Causa | Seções | Diferença na primeira rodada | Classificação |
|---|---:|---:|---|
| A. BU do Sistema de Apuração, sem log de urna (2 MG com cédulas, 28 do exterior com BUEx digitado) | 30 | -1.348 | esperado; ajuste de método |
| B. Logs aninhados duplicados (cópias MI e ME do mesmo log, ou a mesma ME copiada por duas urnas) | 7 | +815 | **erro do leitor de log do projeto, corrigido** |
| C. Urna travou logo após "Voto confirmado para [Presidente]"; a linha "computado" não foi gravada, o voto foi contado | 5 | -5 | comportamento da urna |
| D. Pacote de log publicado não traz o log da urna que recebeu parte dos votos (mídia trocada ou urna intermediária) | 3 | -51 (rs/0044 já somado em B; após a correção fica -1) | **inconsistência a reportar ao TSE** (só no log) |
| E. Urna com 17 reinícios no dia; 2 votos do BU sem "computado" no log | 1 | -2 | falha da urna; pedir esclarecimento |
| **Total** | **45** | **-591** | |

Em todas as 45 seções (e na vizinha 0181) o `processar_secao` do projeto,
rodado de novo sobre os arquivos baixados, reproduziu exatamente os números da
primeira rodada e deu **RDV = BU em todos os cargos** (`rdv_confere=True`,
registros do RDV = comparecimento x escolhas). Nenhuma das causas acima afeta o
resultado da seção: o que diverge é só a trilha de eventos do log.

Depois das correções dos itens A e B, as divergências log x BU que sobram são
9 seções de urna (as 5 do item C, as 3 do item D e a do item E), total -59.

---

## A. BU do Sistema de Apuração (30 seções): esperado

### A.1 Minas Gerais (2)

| Seção | Comparecimento | Log | Diferença |
|---|---:|---:|---:|
| mg/41238/0039/0168 | 281 | 0 | -281 |
| mg/50075/0047/0041 | 278 | 0 | -278 |

- O aux.json só tem o conjunto `busa`, `logsa`, `sa`, `rdv`. Não há
  `-bu.dat` nem `-log.jez` da urna.
- O `-logsa.jez` é o log do SA (urnas 02254078 e 02458923), com
  "Tipo de apuração selecionada (DIGITAÇÃO DO BU MAIS CÉDULAS)" e
  "Motivo da apuração: Urna encerrada com eleitores na fila". O BU da urna foi
  digitado e as cédulas apuradas no SA. Nenhum evento "O voto do eleitor foi
  computado" existe nesse log, por definição.
- RDV: `origem=sa`, `tipo_urna=contingencia`, confere com o BU.
- Ressalva de método: nessas seções o RDV é gerado pelo próprio SA a partir dos
  dados digitados, então RDV = BU não é uma conferência independente.

### A.2 Exterior (28)

Todas com o mesmo padrão (baixadas e conferidas as 28, não só 3 ou 4):

- Conjunto único `busa`, `logsa`, `sa`, `rdv`; sem log de urna publicado.
- O `-logsa.jez` é o log acumulado de **uma única urna de SA (01808076,
  UE2015)**, município 29467, zona 0001, que digitou **30 BUEx** entre 17:33 e
  21:50 de 04/10/2026 ("Tipo de apuração selecionada (DIGITAÇÃO DE BUEx)",
  "Motivo da apuração: Outros", só o cargo Presidente). O arquivo cresce de
  uma seção para a próxima (363 linhas na primeira, 2.001 na última).
- As 30 seções digitadas são as 28 da lista mais zz/29564/0091 (comparecimento
  0, por isso diferença 0) e uma repetição da zz/30163/0647 ("Apuração
  cancelada" às 21:19:41 e refeita às 21:20:08).
- Não é problema de data, fuso ou formato: o exterior votou em 04/10, o log do
  SA tem as datas certas; simplesmente não existe voto computado num log de
  digitação.
- RDV: `origem=sa`, `tipo_urna=contingencia`, registros = comparecimento (1
  cargo), confere com o BU. Mesma ressalva do item A.1: o RDV vem da digitação.

### Ajuste aplicado

Nas seções cujo BU veio do Sistema de Apuração, só existe o log do SA, que não registra votos. A comparação log x BU passou a ser marcada como não aplicável nelas (`origem_log = "logsa"`), em vez de divergência. São 31 seções: as 30 acima e uma do exterior com comparecimento 0. Nelas o RDV também é gerado pelo SA a partir dos dados digitados, de modo que RDV igual ao BU não é uma conferência independente.

---

## B. Duplicação de logs aninhados (7 seções): erro do leitor de log do projeto, corrigido

### Causa

`textos_zip` (`src/dataurnas/parsers/log.py:38-64`) devolve o texto de **todos**
os `.jez` aninhados mais o `logd.dat` e `texto_log`
(`src/dataurnas/analyzer/rdv_recontagem.py:227-234`) junta tudo. Há dois casos em
que o pacote traz o mesmo log mais de uma vez:

1. **Log corrompido preservado em dupla**: quando a urna acusa "Identificados
   arquivos de log corrompidos na MI e ME", ela guarda o log antigo como
   `<urna><ddmmaaaahhmmss>01MI.jez` e `...02ME.jez` (cópia da memória interna e
   da mídia externa). São o mesmo log; às vezes a cópia MI está truncada e a ME
   tem algumas linhas a mais.
2. **A mesma ME copiada por duas urnas de contingência**: cada urna que lê a ME
   grava uma cópia (`<urna><ddmmaaaahhmmss>01ME.jez` ou `...-01.jez`). Se a
   primeira tentativa de contingência falha e outra urna é usada, o pacote
   final traz as duas cópias do mesmo log.

As linhas repetidas são idênticas byte a byte, inclusive o código de
verificação da última coluna (conferido: união por linha completa = união sem a
última coluna). Dentro de cada arquivo não há linha repetida.

A concatenação na ordem do nome do arquivo também é a origem da flag
`log_relogio_inverso` dessas 7 seções (a segunda cópia recomeça às 8h) e do
inchaço de `aberturas`.

### Conferência seção a seção (votos computados por arquivo interno)

| Seção | Arquivos internos (votos) | Soma | União por linha | BU | Situação |
|---|---|---:|---:|---:|---|
| pr/75353/0002/0574 | 01MI 61, 02ME 61 (iguais), 03ME 20, logd 243 | 385 | 324 | 324 | dup. corrompido MI/ME |
| mg/44458/0103/0221 | -01 0, 01MI 64, 02ME 69, 03MI 1, 04ME 1, logd 155 | 290 | 225 | 225 | dup. corrompido; MI truncada (64 de 69) |
| rs/89036/0083/0044 | -01 90, 01ME 90 (iguais), logd 188 | 368 | 278 | 279 | duas cópias da ME; sobra -1 (ver D.3) |
| pr/76570/0010/0273 | 01MI 125, 02ME 125, logd 102 | 352 | 227 | 227 | dup. corrompido MI/ME |
| pa/04855/0031/0087 | 01ME 138, -01 138 (iguais), logd 158 | 434 | 296 | 296 | duas cópias da ME (urnas 01654514 e 01656272) |
| mg/47830/0165/0031 | 01MI 157, 02ME 157, logd 37 | 351 | 194 | 194 | dup. corrompido MI/ME |
| rj/58041/0155/0190 | 01MI 180, 02ME 180, logd 106 | 466 | 286 | 286 | dup. corrompido MI/ME |

Hipóteses descartadas: votos de outra data (todos os votos são de 04/10/2026,
`votos_outras_datas=0`), log acumulado de urna reaproveitada, votos de
treinamento ou simulação (nenhum voto fora de 04/10 e todos depois da
"Urna pronta para receber votos"). A hipótese certa era a do `.jez` aninhado.

### Correção aplicada

O leitor de log (`src/dataurnas/parsers/log.py`) passou a ordenar os `.jez` aninhados pela data e hora embutida no nome (`<8 dígitos da urna><ddmmaaaahhmmss>`), em vez de só pelo nome, que começa pelo número da urna e misturava a ordem das urnas, e a descartar linhas idênticas repetidas entre cópias do mesmo log. Linhas iguais de urnas diferentes, ou repetidas dentro do mesmo log, continuam contando.

Resultado nas 7 seções, depois do reprocessamento:

| Seção | Antes: diferença / inversões de relógio / aberturas | Depois |
|---|---|---|
| pr/75353/0002/0574 | +61 / 1 / 11 | 0 / 0 / 7 |
| mg/44458/0103/0221 | +65 / 1 / 10 | 0 / 0 / 6 |
| rs/89036/0083/0044 | +89 / 1 / 7 | -1 / 0 / 4 |
| pr/76570/0010/0273 | +125 / 1 / 9 | 0 / 0 / 5 |
| pa/04855/0031/0087 | +138 / 1 / 3 | 0 / 0 / 2 |
| mg/47830/0165/0031 | +157 / 1 / 14 | 0 / 0 / 8 |
| rj/58041/0155/0190 | +180 / 1 / 5 | 0 / 0 / 3 |

As cerca de 28 mil seções com mais de uma urna ou abertura no log foram reprocessadas com o leitor corrigido; nenhuma outra tinha log repetido. A auditoria de BU e log publicada foi regerada: saíram os 7 A03 falsos, os C06 dessas seções passaram a contar os reinícios corretos, e a ordenação corrigiu a hora de abertura de 19 seções, eliminando 18 alertas A04 falsos.

---

## C. Linha "computado" perdida em travamento logo após o voto para Presidente (5 seções): comportamento da urna

Em cada uma há exatamente um ciclo de eleitor com habilitação e os 6 votos
confirmados (Dep. Federal, Dep. Estadual, Senador x2, Governador, Presidente),
seguido de silêncio de vários minutos e reinício, sem a linha
"O voto do eleitor foi computado". O voto foi gravado: o BU tem exatamente 1 a
mais, o RDV confere com o BU e, em 4 das 5, logo após o reinício aparece
"O eleitor identificado já votou" (o eleitor tentou de novo e a urna recusou).

| Seção | Dif | Último evento do ciclo | Reinício | "Já votou" depois |
|---|---:|---|---|---|
| es/56995/0053/0211 | -1 | Presidente 16:57:06 | logd 17:01:42 (abrupto) | 17:06:23 |
| sp/63614/0227/0305 | -1 | Presidente 08:09:49 | logd 08:14:25 (abrupto) | não |
| sp/64254/0291/0346 | -1 | Presidente 10:33:58 | logd 10:36:47 (abrupto) | 10:42:11 |
| sp/71072/0260/0037 | -1 | Presidente 13:25:01; "Erro gravando EG/Eleitores na Mídia Interna" 13:25:02 | desligada pela chave 13:41:19 | 4 vezes, 13:45 a 13:48 |
| rn/16039/0029/0028 | -1 | Presidente 10:09:15 | logd 10:18:15 (abrupto) | 10:21:24 |

Contagem de ciclos (habilitados / computados / Presidente confirmado):
es 265/264/265, sp63614 290/289/290, sp64254 278/277/278, sp71072_0260
285/284/285. Fecha 1 a 1.

No rn há outros ciclos interrompidos que **não** entraram no BU, coerentes:
11:45 e 12:01 (até Governador, urna desligada pela chave; o eleitor das 12:01
foi habilitado de novo às 12:14 e votou completo) e uma suspensão pelo mesário
às 12:56:43 ("Eleitor votou parcialmente e em seguida foi suspenso", com
"Atribuido voto nulo por suspensão" em Dep. Estadual, Senador x2, Governador e
Presidente). A suspensão gera também a linha "computado", então o método atual
já conta esse eleitor. O RDV do rn tem exatamente esses 5 `nuloAposSuspensao`
(Dep. Estadual 1, Senador 2, Governador 1, Presidente 1).

Conclusão: o voto é persistido antes de a linha de log ser gravada; um
travamento nesse intervalo deixa o voto sem a linha. Não é bug do parser nem
indício contra o resultado. Ponto a mencionar ao TSE como fragilidade de
registro (o log não é atômico com o voto), com destaque para o
"Erro gravando EG/Eleitores na Mídia Interna" do sp/71072/0260/0037.

Melhoria possível no método (opcional): marcar como "voto provável sem linha"
o ciclo que tem "Voto confirmado para [Presidente]" seguido de reinício sem
"computado", e reportar a diferença residual depois disso.

---

## D. Log de urna ausente ou trocado no pacote publicado (3 seções): inconsistência a reportar ao TSE

Em todas, BU e RDV conferem e o hash do pacote confere com o catálogo assinado.
O problema é a trilha de auditoria: o `-log.jez` publicado não contém o log da
urna que recebeu parte dos votos.

### D.1 ba/39934/0183/0175 (log 236, BU 272, dif -36): mídia externa da seção 0181 no pacote da 0175

Linha do tempo reconstruída do pacote da 0175 e do pacote da vizinha 0181:

- O `.jez` aninhado da 0175 (`024291180410202614245201ME.jez`) começa com o
  log da urna **02423907**, que é a urna da **seção 0181**
  ("Seção Eleitoral: 0181", MV A23FBB23): 74 votos de 08:00 a 11:20, reinício,
  26 votos até 12:25. Esses 100 votos são da 0181.
- A 0181 fez contingência às 12:33 para a urna 02293617 (+163 votos). O pacote
  da 0181 tem os mesmos 100 votos da 02423907 e fecha: 100 + 163 = 263 = BU
  (baixado e conferido).
- Às 13:19:40 a urna 02423907 (da 0181, já substituída) é ligada com a **MV da
  0175** (008B59DC): "Serial da MV original da urna que está registrada na MI:
  A23FBB23" / "Serial da MV: 008B59DC". Não chega a abrir votação.
- Às 13:23:37 a urna **02424441**, que é a urna original da 0175 (MI com MV
  original 008B59DC), passa a escrever **na mesma mídia externa**, com
  "Resultado da verificação da mídia externa estática : 1" (nas demais urnas o
  resultado é 0), faz "reinício da votação" e recebe 24 votos até 14:19.
- Às 14:24 a urna de contingência 02429118 copia essa ME e recebe 112 votos até
  o encerramento.

Conta: BU 272 = X + 24 + 112, logo X = **136 votos da urna 02424441 entre 08:00
e cerca de 13:19 cujo log não está no pacote**. O pacote traz em lugar deles os
100 votos da 0181. 100 - 136 = -36.

Interpretação: as mídias externas das urnas das seções 0181 e 0175 (mesmo local)
foram trocadas; a urna da 0175 aceitou a ME de outra seção com a verificação
estática acusando 1 e a contingência copiou a ME errada. Não há sinal de voto
cruzado entre seções: a MV da 0175 (008B59DC) acompanhou só as urnas da 0175, a
0181 fecha com o próprio BU, e RDV = BU nas duas.

A reportar: o log publicado da 0175 está trocado e incompleto (136 votos sem
trilha). O log da manhã deve estar na MI da urna 02424441 e na ME original da
0175; pedir ao TSE esses arquivos.

Efeito colateral nas nossas métricas: `n_urnas_log=3`, `aberturas=4` e
`hora_pronta=08:00:01` da 0175 vêm da urna da 0181.

### D.2 sp/71072/0002/0035 (log 232, BU 247, dif -15): log da urna original ausente

- O `.jez` aninhado (`0225378304102026105501-01.jez`, copiado pela urna de
  contingência 02253783 às 10:55:01) é o log da urna **02254720**. Essa urna foi
  carregada em 29/09 para a 0035 com a MV 7FBB29C7 e, em 04/10, não tem nenhum
  evento antes das 10:18: liga às 10:17 com **outra MV (9F62BC72, gerada em
  27/09)**, acusa MV original diferente, inicia a aplicação e é desligada às
  10:52 sem receber votos.
- A urna de contingência 02253783 faz "reinício da votação" às 10:58:42 com a
  MV 9F62BC72 e recebe 232 votos.
- Logo, os **15 votos** entre 08:00 e cerca de 10:17 foram dados numa terceira
  urna (a que tinha a MV 9F62BC72), cujo log não veio no pacote. A ME copiada
  foi a da 02254720, não a da urna que votou.

A reportar: log da urna que abriu a votação ausente; 15 votos sem trilha.
Efeito nas nossas métricas: `hora_pronta=10:58:42` e `aberturas=1` sugerem
abertura tardia, mas é reinício após contingência; a abertura real não está no
log publicado.

### D.3 rs/89036/0083/0044 (dif +89 no parquet; -1 depois da correção B): log de urna intermediária ausente (provável)

- Urna original 01801772: 29 + 29 + 32 = 90 votos (três aberturas, desligada
  pela chave às 09:05, 10:04 e 11:04; erro "Não foi possível exibir imagem no
  LCD do terminal do mesário").
- Às 11:11:50 a urna **01675257** copia a ME (`016752570410202611115001ME.jez`),
  ou seja, foi usada como contingência. O log dela não está no pacote.
- 11:41 a 11:44: a urna original é ligada de novo com a MV 66D75BC9 e desligada
  sem votos. 12:00: contingência para 01651842, "reinício da votação" às 12:09:47,
  188 votos.
- Habilitados = computados = 278 em todo o log publicado, sem ciclo
  interrompido. BU 279. O único intervalo sem log de urna com a MV da seção é
  o da 01675257 (11:11 a cerca de 11:40). Hipótese mais provável: 1 voto nessa
  urna, sem trilha no pacote.

A reportar com prioridade menor: log da urna 01675257 ausente.

---

## E. rj/58971/0087/0184 (log 256, BU 258, dif -2): urna com falhas repetidas

- Uma única urna (02172702) o dia todo, **18 "Urna pronta"** e 25 inícios do
  logd em 04/10. Muitos reinícios são abruptos (início do logd logo depois de
  linhas de voto, sem "Fechando o arquivo de Log") e há um erro de interface
  ("WHAT: virtual api::CMovie ...") às 13:58. Não houve contingência.
- 268 habilitações, 256 computados, 12 ciclos interrompidos sem Presidente
  confirmado (0 a 5 cargos confirmados). Não há tipo `*AposSuspensao` no RDV,
  então os votos contados estão completos.
- Conclusão provável: 10 desses eleitores votaram de novo depois do reinício e
  2 terminaram o voto (que foi gravado) mas as linhas finais se perderam no
  travamento. Candidatos mais fortes: 15:44:47 (Governador às 15:45:40,
  reinício às 15:47:59) e 12:50:09 (Dep. Estadual às 12:50:34, reinício às
  12:54:30). O log publicado não permite fechar a conta.
- Nota do parser: as 64 primeiras linhas do logd.dat têm data 04/10/2026
  11:33:42, mas foram escritas na carga de 21/09 antes do acerto de relógio
  ("Data e hora atualizada" para 21/09). Não afetam votos nem aberturas.

Classificação: falha de hardware ou software da urna, sem indício contra o
resultado (RDV = BU). Vale citar ao TSE como urna que deveria ter ido para
contingência e cujo log não concilia 2 votos.

---

## Conclusões

1. **Nenhuma inconsistência de resultado.** RDV igual ao BU nas 45 seções e na vizinha; hashes conferem.
2. **Erro do leitor de log do projeto (7 seções):** logs aninhados repetidos contados duas vezes. Corrigido, com os dados regerados.
3. **Método (31 seções):** o BU do Sistema de Apuração não tem eventos de voto no log; essas seções saíram da comparação.
4. **Comportamento esperado da urna (5 seções, -5):** travamento logo após o voto para Presidente, com o voto contado.
5. **Encaminhado ao TSE** no [pedido de esclarecimentos](relatorio-tse-ocorrencias-2026.md) (trilha de log, não resultado):
   - BA 39934/0183/0175: log trocado com o da seção 0181 (troca de mídia externa), cerca de 136 votos sem log publicado e 100 votos de outra seção no pacote;
   - SP 71072/0002/0035: log da urna que abriu a votação ausente, 15 votos sem log;
   - RS 89036/0083/0044: log da urna de contingência intermediária 01675257 ausente, 1 voto provável sem log;
   - RJ 58971/0087/0184: urna com 17 reinícios sem contingência, 2 votos não conciliáveis pelo log.
