# Logs do GEDAI-UE no 2º turno de 2026

Relatório descritivo dos logs do GEDAI-UE publicados pelo TSE para o 2º turno de
2026 (pleito 3221, eleição 6258, votação em 25/10/2026) e do cruzamento desses
logs com os boletins de urna (BU) coletados. O texto descreve o que os arquivos
mostram. Onde algo não bate, o caso fica listado para conferência; nenhuma
divergência aqui é tratada como irregularidade.

Script: `scripts/ele2026/gedai_t2.py` (testes em `tests/ele2026/test_gedai_t2.py`).
Processamento feito no servidor de análise; as saídas ficam fora do repositório
(`~/dataurnas-t2/gedai/analise-nacional/` no servidor, com as listas em CSV em
`~/dataurnas-t2/linha_tempo-nacional/`). A primeira versão deste relatório
(`~/dataurnas-t2/gedai/analise/`) cobria 151.642 seções de 14 UFs; esta versão,
de 26/10/2026, cobre a coleta nacional completa.

## 1. Resumo

- O GEDAI-UE é o sistema dos cartórios e TREs que gera as mídias de carga e de
  votação, lê de volta a tabela de correspondência gravada na flash de carga
  depois que as urnas são carregadas e transmite essas correspondências ao TSE.
  O log não registra a carga em si (ela acontece na urna); registra a geração da
  mídia de carga e a leitura posterior das correspondências.
- Foram lidos 4 pacotes por UF (1º turno: 03/10 e 04/10; 2º turno: 24/10 e
  25/10), 18.201 logs de estação, 4.907 estações distintas, nenhum arquivo
  ilegível. Os logs são cumulativos: o pacote do 2º turno traz o histórico da
  estação desde setembro. Em 26/10 às 09:32 UTC o catálogo do portal continuava
  só com esses dois pacotes do 2º turno.
- Há 563.331 códigos de carga distintos nas correspondências (507.937 de seção e
  55.394 de contingência).
- Coleta nacional: 499.207 seções com BU, das 499.248 do país (as 41 restantes
  estão como não instaladas). São 499.178 BUs de urna (493.464 de seção, 5.712
  reservaSecao e 2 reservaEncerrandoSecao) e 29 BUs do Sistema de Apuração, todos
  no exterior.
- Das 499.178 seções com BU de urna, 498.316 (99,83%) têm o código de carga do
  BU no GEDAI, e em todas elas conferem o número interno da urna, o número de
  série da flash de carga, o tipo (seção ou contingência), o município, a zona e,
  para urnas de seção, a seção. 862 BUs têm código de carga ausente dos logs
  publicados, 752 deles em quatro estações: Parauapebas (PA) 358, Guarulhos (SP)
  267, quatro municípios da zona 0339 de MG 96 e Monte Alegre (PA) 31.
- Os 29 BUs do Sistema de Apuração usam dois códigos de carga, ambos presentes no
  GEDAI como carga de contingência do exterior.
- Pela data de carga gravada no próprio BU, 489.699 urnas usadas no 2º turno
  foram carregadas até 30/09, 7.234 entre 01 e 04/10, 1.531 entre 05 e 23/10, 709
  em 24/10 e **5 em 25/10**, dia da eleição (Campo Grande e Três Lagoas, MS;
  Carlópolis e Guarapuava, PR; Atibaia, SP). As cinco cargas de 25/10 foram
  feitas entre 06:55 e 10:04 do horário local da urna, antes da abertura da
  respectiva seção; quatro delas foram lidas no GEDAI na mesma manhã e a de
  Guarapuava não aparece nos logs publicados (seção 7).
- Nos logs, nenhum evento de correspondência ocorre depois das 11:40:18 de
  25/10, e o último evento de qualquer tipo é das 13:29:56 de 25/10. Não há
  evento depois das 17h de 25/10.
- A versão de 25/10 acrescenta à de 24/10 52.105 linhas: 30.605 datadas de
  24/10 (tarde de sábado, depois do corte da versão de 24/10), 3.925 de 25/10 e
  o restante de dias anteriores (estações que só exportaram o log depois). Em
  25/10 há 42 leituras de correspondência e 164 transmissões; dos 16 códigos de
  carga vistos pela primeira vez em 25/10, 6 são os usados nos BUs de seis
  seções.
- 86 BUs (85 de Jaguariaíva, PR, zona 0018) foram gerados por estações que não
  têm log publicado; a carga deles está no GEDAI, lida por outra estação da zona.
- A diferença de catálogo registrada na madrugada de 26/10 (112 recursos na busca
  e 56 na página do conjunto) não existe mais: às 09:32 UTC de 26/10 as duas
  respostas listam 112 recursos.

## 2. Fontes e catálogo do portal

Pacotes baixados do CDN do TSE, com o SHA-512 publicado conferido para todos:

| Pacote | Arquivos | Nome | Logs de estação |
|---|---|---|---|
| 1º turno, 03/10 | 28 zips | `log_gedai_1t_<UF>_031020261345.zip` | 4.748 |
| 1º turno, 04/10 | 28 zips | `log_gedai_1t_<UF>_041020261441.zip` | 4.760 |
| 2º turno, 24/10 | 28 zips | `log_gedai_2t_<UF>_241020261329.zip` | 4.333 |
| 2º turno, 25/10 | 28 zips | `log_gedai_2t_<UF>_251020261327.zip` | 4.360 |

As 28 UFs incluem ZZ (exterior).

Catálogo do conjunto `resultados-2026-logs-do-sistema-de-preparacao-das-urnas-eletronicas-gedai-2-turno`,
em respostas da API do portal guardadas em dois momentos:

| Momento (UTC) | Resposta | `metadata_modified` do conjunto | Recursos listados |
|---|---|---|---|
| 26/10/2026 03:21:33 | `package_search` (índice de busca) | 2026-10-25T17:40:46.916871 | 112 (56 de 24/10 e 56 de 25/10) |
| 26/10/2026 03:21:33 | `package_show` (página do conjunto) | 2026-10-24T17:53:04.025235 | 56 (só os de 24/10) |
| 26/10/2026 09:32:20 | `package_search` | 2026-10-25T17:40:46.916871 | 112 (56 de 24/10 e 56 de 25/10) |
| 26/10/2026 09:32:20 | `package_show` | 2026-10-25T17:40:46.916871 | 112 (56 de 24/10 e 56 de 25/10) |

Nos recursos de 25/10 o campo `created` vai de 2026-10-25T17:24:18.815789 a
2026-10-25T17:36:14.123045 (o portal costuma gravar esses campos em UTC; se for
o caso, 14:24 a 14:36 de Brasília). Os recursos de 24/10 foram criados entre
2026-10-24T14:27:59 e 14:36:05. Na madrugada de 26/10 a página do conjunto ainda
refletia a versão de 24/10; seis horas depois, as duas respostas coincidem. A
diferença foi, portanto, atraso de atualização da página do conjunto, e não
ausência dos arquivos. Nenhum pacote do GEDAI posterior ao de 25/10 aparece no
catálogo.

Reconferência (duas requisições, 26/10/2026 09:32 UTC, guardadas em
`~/dataurnas-t2/gedai/gedai_package_show_20261026T0932.json` e
`gedai_package_search_20261026T0932.json`):

```sh
N=resultados-2026-logs-do-sistema-de-preparacao-das-urnas-eletronicas-gedai-2-turno
curl -s "https://dadosabertos.tse.jus.br/api/3/action/package_show?id=$N"
curl -s "https://dadosabertos.tse.jus.br/api/3/action/package_search?q=name:$N"
```

## 3. Formato dos logs

### 3.1 Estrutura dos arquivos

```
log_gedai_2t_BA_251020261327.zip                 pacote da UF (turno, UF, DDMMAAAAHHMM)
  leiame.pdf                                       idêntico em todos os pacotes (datado 05/10/2024)
  gedai-ue-ba-03221-oficial-ZBA173WKS03-<TPM>-<INST>-log.jez     um por estação (zip)
    gedai-ue-ba-oficial-ZBA173WKS03-log.jez          zip
      gedai-ue.log                                     texto ISO-8859-1, quebras CRLF
    gedai-ue-ba-oficial-ZBA173WKS03-log.vsc          assinatura do log (ASN.1/DER)
```

O nome do `.jez` de estação segue o leiame: `gedai-ue-UF-PLEITO-oficial-NM_COMPUTADOR-SERIAL_TPM-SERIAL_INSTALACAO-log.jez`.
O pleito no nome é 03220 nos pacotes do 1º turno e 03221 nos do 2º, mas o
conteúdo é o log inteiro da estação. Os nomes de computador seguem padrões como
`Z<UF><zona>STD<nn>` e `Z<UF><zona>WKS<nn>` (cartórios) e `R<UF>W...` (TRE). O
serial TPM tem 8, 20, 32 ou 40 dígitos hexadecimais.

### 3.2 Linha do log

```
DD/MM/AAAA HH:MM:SS <TAB> NÍVEL <TAB> mensagem <TAB> hash de 16 dígitos hexadecimais
```

Níveis: INFO, ALERTA e ERRO. No pacote de 25/10 há 5.043.335 linhas INFO,
6.701 ALERTA e 27.661 ERRO. O horário é o relógio da estação; o log não informa
fuso.

### 3.3 Eventos relevantes

| Evento | Exemplo (dados trocados por N) |
|---|---|
| Sessão | `Abertura do GEDAI-UE - Versão 8.23.0.0 - Praia da Barra do Cahy`, `Computador: ... | Serial TPM: ... | Serial instalação: ...`, `UF do computador`, `Usuário Windows: N`, `Usuário Odin: N | Perfil Odin: Administrador`, `Fechamento do GEDAI-UE` |
| Processo e pleito | `Abrindo Processo Eleitoral: 01219 - Eleições Gerais 2026`, `Pleito corrente: 03221 - 2° Turno`, `Transição para 2° Turno` |
| Pacotes de dados | `Pacote o06258br00000-ca.jez importado - Versão AAAAMMDDHHMM` |
| Mídia de carga | `Mídia de carga gerada. NS:4DF908B3 Z:0001 | Seções (M:30449) 0888 ...` (NS da flash, zona, município e lista de seções) |
| Mídia de votação | `Mídia de votação gerada. NS:98999540` |
| Correspondência | `Recebida correspondência de seção: município 01392, zona 0001, seção 0003, carga <24 dígitos>, id urna 02047921, mc 88F1D8DF.` |
| | `Recebida correspondência de contingência: município N, zona N, carga N, id urna N, mc N.` |
| | Variações com `Transmitida a`, `Exportada a`, `Cadastrada` e `Definida como atual a` |
| Validação | `A correspondência de código [N] está inválida: Assinatura inválida`, `Nenhuma tabela de correspondência válida foi encontrada` |
| Envio do log | `Realizada a transmissão do log para https://gedai-produtor.tse.jus.br:443/...` |

Como cada campo identifica a urna e a carga:

- `id urna` é o número interno da urna (8 dígitos), o mesmo `numeroInternoUrna`
  do BU.
- `carga` é o código de carga de 24 dígitos, o mesmo `codigoCarga` do BU.
- `mc` é o número de série da flash de carga (8 dígitos hexadecimais), o mesmo
  `NS` da linha `Mídia de carga gerada` e o mesmo `numeroSerieFC` do BU.
- Correspondência de seção traz município, zona e seção; de contingência, só
  município e zona.
- Data e hora são as da leitura da flash pela estação, não as da carga. Uma
  flash leva a tabela de todas as urnas que carregou, e cada nova leitura dela
  repete as correspondências (por isso há 526.622 leituras de seção para 507.937
  códigos).
- O operador aparece como número de usuário (`Usuário Windows`, `Usuário Odin`).
  Há também caminhos de pastas pessoais em mensagens de cópia de segurança. Este
  relatório não reproduz esses identificadores.
- O local é indicado pela UF do computador, pelo nome da estação (que contém a
  zona) e pelos códigos de município e zona das correspondências e mídias.

### 3.4 Ligação com o BU

O BU do 2º turno traz, em `urna.correspondenciaResultado.carga`:
`numeroInternoUrna`, `codigoCarga`, `dataHoraCarga`, `numeroSerieFC` e
`identificadorGeradorMidia` (nome, serial TPM e serial de instalação da estação
GEDAI que gerou a mídia). Traz também `historicoCodigosCarga`, com os códigos de
carga anteriores da seção (urnas `reservaSecao` registram ali a carga da urna
substituída). Esses campos permitem o cruzamento direto com o GEDAI.

## 4. Metadados internos dos zips

| Pacote | Data das entradas no zip | Último `.jez` interno | Último evento |
|---|---|---|---|
| 1t 03/10 | 03/10 16:45:32 a 16:51:16 | 03/10 13:49:06 | 03/10 13:49:06 |
| 1t 04/10 | 04/10 17:41:24 a 17:47:48 | 04/10 14:45:54 | 04/10 14:45:52 |
| 2t 24/10 | 24/10 16:29:02 a 16:33:50 | 24/10 13:32:26 | 24/10 13:32:24 |
| 2t 25/10 | 25/10 16:27:04 a 16:32:18 | 25/10 13:29:58 | 25/10 13:29:56 |

- As entradas do zip externo têm horário 3 horas à frente do carimbo do nome do
  pacote (16:27 para `...1327`), o que é compatível com horário UTC; os `.jez`
  internos e as linhas do log usam o horário local da estação.
- Nenhum zip e nenhuma entrada tem comentário.
- O `leiame.pdf` é o mesmo em todos os pacotes.
- Todas as estações têm o par `.jez` e `.vsc`. A assinatura `.vsc` não foi
  verificada neste trabalho.

## 5. O que a versão de 25/10 acrescenta à de 24/10

Comparação por estação (mesmo computador, serial TPM e serial de instalação):

| Situação | Estações |
|---|---|
| Idêntico | 3.658 |
| Acréscimo no fim do log (o novo começa com o antigo) | 674 |
| Divergente | 1 |
| Só na versão de 25/10 | 27 |
| Só na versão de 24/10 | 0 |

- Linhas novas: 52.105. Por data do evento: 30.605 de 24/10, 3.925 de 25/10,
  1.008 de 23/10 e o restante espalhado de 11/09 a 22/10. As linhas antigas
  entram porque a estação só exporta o log ao fechar o GEDAI; uma estação que
  ficou sem enviar aparece depois com todo o trecho pendente.
- Linhas novas depois das 17h de 25/10: nenhuma.
- Correspondências novas (11.281 eventos, 333 estações, 25 UFs): em 24/10,
  1.769 leituras (1.120 de seção e 649 de contingência), 3.652 transmissões, 128
  exportações e 41 cadastros; 3.225 desses eventos são de 24/10 depois das 13:29,
  horário do corte da versão de 24/10.
- Em 25/10: 195 estações com eventos, 3.925 linhas, entre 01h e 13:29:56, a
  maior parte entre 05h e 13h. Correspondências de 25/10: 27 leituras de seção,
  15 de contingência, 128 transmissões de seção, 36 de contingência e 4 cadastros
  manuais (`Cadastrada`): 1 de seção em RO, 2 de contingência em SE e 1 de
  contingência em SP.
- 27 estações aparecem só na versão de 25/10 (RJ 8, AP 6, BA 3, PI 2, PR 2, RO 2,
  MS, RS, SP e TO 1 cada). Em parte delas o último evento ainda é de setembro ou
  outubro; o envio do log é que ocorreu depois.
- Estação divergente: `ZPE019WKS03` (PE). A versão de 25/10 tem 2 linhas a menos
  que a de 24/10 (a exportação do log às 12:30:44 de 24/10 e o início do envio
  automático às 12:39:53). A versão de 25/10 dessa estação parece ser uma
  exportação anterior. Caso para conferência.
- No 1º turno, a versão de 04/10 acrescenta 60.470 linhas à de 03/10 (911
  estações com acréscimo, 12 novas, nenhuma divergente).

Correspondências de 25/10 por estação (leituras e cadastros):

| UF | Estação | Horário | Município | Zona | Leituras de seção | Leituras de contingência | Cadastros |
|---|---|---|---|---|---|---|---|
| MT | ZMT034WKS60565 | 05:35 a 05:39 | 90590 | 0034 | 1 | 2 | |
| RO | RROWS26980 | 06:20 | 00051 | 0030 | | | 1 de seção |
| SE | RSEWGM06 | 07:09 a 07:17 | 31054 | 0027 | | | 2 de contingência |
| MS | ZMS008WKS01 | 07:30 | 90514 | 0008 | 1 | 1 | |
| MG | ZMG219STD03 | 08:03 | 43516 | 0219 | 2 | 2 | |
| MS | ZMS051WKS02 | 08:07 | 91650 | 0051 | 2 | 1 | |
| SP | ZSP016STD25 | 09:04 a 09:11 | 61816 | 0016 | 4 | 2 | |
| BA | ZBA173WKS03 | 09:13 a 11:23 | 35653 (Ibotirama) | 0173 | 13 | 6 | |
| PR | ZPR056STD02 | 11:18 | 74918 | 0056 | 4 | 1 | |
| SP | ZSP422STD16 | 11:39 | 71072 | 0422 | | | 1 de contingência |

Os 16 códigos de carga lidos pela primeira vez em 25/10 (10 de seção e 6 de
contingência) estão em flashes de carga geradas entre 17 e 25/09. Com a coleta
nacional de BUs, 6 deles são os códigos usados na votação:

| UF | Município | Zona | Seção | Tipo de urna no BU | Carga (BU, horário da urna) | Leitura no GEDAI (estação) |
|---|---|---|---|---|---|---|
| MT | 90590 Chapada dos Guimarães | 0034 | 0120 | seção | 24/10 10:57 | 25/10 05:39 (ZMT034WKS60565) |
| MS | 90514 Campo Grande | 0008 | 0486 | seção | 25/10 06:55 | 25/10 07:30 (ZMS008WKS01) |
| MS | 91650 Três Lagoas | 0051 | 0044 | seção | 25/10 07:36 | 25/10 08:07 (ZMS051WKS02) |
| SP | 61816 Atibaia | 0016 | 0436 | seção | 25/10 07:58 | 25/10 09:04 (ZSP016STD25) |
| PR | 74918 Carlópolis | 0056 | 0037 | seção | 25/10 09:20 | 25/10 11:18 (ZPR056STD02) |
| SP | 71072 São Paulo | 0422 | 0222 | reservaSecao | 01/10 10:57 | 25/10 11:39, cadastro manual (ZSP422STD16) |

- Em Três Lagoas e Carlópolis a mesma leitura traz dois códigos de seção para a
  mesma urna (2001864 e 1797363); o BU usa um deles e o outro não aparece em BU.
- Em São Paulo, zona 0422, o código de contingência usado pela urna reservaSecao
  da seção 0222 só entra no GEDAI por cadastro manual (`Cadastrada`) às 11:39 de
  25/10, com a votação em andamento; a carga é de 01/10 e a mídia foi gerada em
  outra estação da zona (ZSP422STD04).
- Os outros 10 códigos não aparecem em BU: 2 de contingência em MG (43516, zona
  0219), o segundo código de Três Lagoas, o segundo de Carlópolis e 6 de
  Ibotirama (BA 35653, zona 0173). Em Ibotirama, a mesma urna (número interno
  1833178) aparece em correspondências das seções 0001, 0002, 0083 e 0235 e em
  uma de contingência, todas na flash `688BB468` ou em flashes da mesma zona;
  isso indica leituras repetidas de flashes que carregaram várias vezes a mesma
  urna, mas o log não traz a data das cargas. As seções 0001, 0002, 0083 e 0235
  de Ibotirama têm BU com outro código de carga, que está no GEDAI desde
  setembro.

## 6. Cargas por dia

Três medidas diferentes, porque o GEDAI não registra a carga em si:

1. data de carga gravada no BU (`dataHoraCarga`), para as 499.178 seções com BU
   de urna;
2. primeira leitura do código de carga no GEDAI (todas as UFs);
3. geração de mídias de carga no GEDAI.

| Período | BU, urna de seção | BU, reservaSecao | GEDAI, 1ª leitura de seção | GEDAI, 1ª leitura de contingência | Mídias de carga geradas |
|---|---|---|---|---|---|
| até 30/09 | 484.604 | 5.095 | 495.079 | 47.577 | 25.961 |
| 01 a 04/10 | 6.890 | 344 | 10.647 | 4.188 | 27 |
| 05 a 23/10 | 1.267 | 264 | 1.445 | 3.420 | 38 |
| 24/10 | 698 | 11 | 756 | 203 | 6 |
| 25/10 | 5 | 0 | 10 | 6 | 0 |
| Total | 493.464 | 5.714 | 507.937 | 55.394 | 26.032 |

- Na coluna reservaSecao estão também as 2 urnas `reservaEncerrandoSecao`
  (carregadas em 22 e 26/09).
- Quase todas as urnas do 2º turno (98,1%) usaram a carga feita em setembro para
  os dois turnos.
- De 05 a 23/10 a maior parte das leituras novas no GEDAI é de contingência
  (3.420 contra 1.445), compatível com a preparação de urnas de reserva para o 2º
  turno.
- Em 25/10 não foi gerada nenhuma mídia de carga. As 5 cargas de 25/10 dos BUs
  usaram flashes geradas em setembro (seção 7).
- Nas leituras de outubro (a partir de 05/10), 15.146 estão em sessões com pleito
  corrente 03221 e 175 com 03220.

Primeiras leituras no GEDAI por dia, de 13/10 a 25/10:

| Dia | Seção | Contingência |
|---|---|---|
| 13/10 | 23 | 41 |
| 14/10 | 98 | 202 |
| 15/10 | 231 | 364 |
| 16/10 | 294 | 498 |
| 17/10 | 178 | 434 |
| 18/10 | 141 | 280 |
| 19/10 | 165 | 491 |
| 20/10 | 106 | 353 |
| 21/10 | 102 | 326 |
| 22/10 | 59 | 217 |
| 23/10 | 47 | 206 |
| 24/10 | 756 | 203 |
| 25/10 | 10 | 6 |

## 7. Cargas em 24 e 25/10

### 24/10 (sábado, véspera)

- BUs com carga em 24/10: 709 (698 de seção e 11 reservaSecao), entre 07h e
  18h, a maioria entre 08h e 12h (531 das 709). Por UF: AC 19, AL 20, AM 20,
  AP 20, BA 36, CE 36, DF 20, ES 20, GO 29, MA 27, MG 34, MS 20, MT 20, PA 27,
  PB 19, PE 26, PI 20, PR 32, RJ 33, RN 22, RO 19, RR 20, RS 27, SC 30, SE 20,
  SP 72, TO 21. A quantidade próxima de 20 por UF é compatível com a troca das
  urnas sorteadas para o teste de integridade, feito com urnas retiradas das
  seções na véspera. Isso não está nos dados e precisa ser confirmado com as atas
  dos TREs.
- Das 709 cargas de 24/10 dos BUs, 675 estão no GEDAI: 674 lidas em 24/10, entre
  08:06 e 18:25, e 1 lida em 25/10 às 05:39 (Chapada dos Guimarães, MT). As
  outras 34 não aparecem nos logs publicados (PA 7, PR 7, RO 4, SP 4, RS 3, MG 2,
  MT 2, SC 2, AC 1, AP 1, RJ 1).
- GEDAI: 959 códigos lidos pela primeira vez em 24/10 (756 de seção e 203 de
  contingência), em todas as 27 UFs. 674 deles aparecem nos BUs (663 de seção e
  11 reservaSecao); os outros 285 são de urnas de contingência não usadas ou de
  cargas substituídas.
- Mídias de carga geradas em 24/10: 6 (RJ zona 0027, RS zona 0162, SC zona 0002,
  SE zona 0002, RN zona 0067 e SP zona 0052).

### 25/10 (dia da eleição)

Cinco BUs têm data de carga em 25/10. Todas são urnas de seção (não
reservaSecao), com um único código no histórico de cargas do BU, e a carga foi
feita antes da abertura da seção:

| UF | Município | Zona | Seção | Carga (horário da urna) | Abertura (horário da urna) | Encerramento (Brasília) | Estação geradora da mídia | Leitura no GEDAI |
|---|---|---|---|---|---|---|---|---|
| MS | 90514 Campo Grande | 0008 | 0486 | 06:55 | 07:26 | 17:01:19 | RMSWGM04 | 07:30 (ZMS008WKS01) |
| MS | 91650 Três Lagoas | 0051 | 0044 | 07:36 | 08:13 | 17:00:29 | RMSWGM11 | 08:07 (ZMS051WKS02) |
| SP | 61816 Atibaia | 0016 | 0436 | 07:58 | 08:32 | 17:00:35 | ZSP016STD25 | 09:04 (ZSP016STD25) |
| PR | 74918 Carlópolis | 0056 | 0037 | 09:20 | 10:02 | 17:01:04 | ZPR056STD02 | 11:18 (ZPR056STD02) |
| PR | 75833 Guarapuava | 0043 | 0397 | 10:04 | 10:51 | 17:00:47 | ZPR043STD01 | ausente dos logs |

- As flashes de carga usadas foram geradas em setembro, entre 17/09 e 25/09 (a
  de Guarapuava, `68100584`, em 21/09 na própria ZPR043STD01); nenhuma mídia de
  carga foi gerada em 25/10.
- Em Guarapuava o código de carga não está em nenhum log publicado; o log da
  estação geradora (ZPR043STD01) termina em 24/10 às 07:35.
- Nas cinco seções o encerramento ocorreu entre 17:00:29 e 17:01:19 de Brasília.
  O BU não informa o motivo da carga no dia da eleição; a abertura depois do
  horário normal é compatível com troca ou recarga da urna antes do início da
  votação. Ficam listadas para conferência com as atas das seções.
- No GEDAI, 16 códigos lidos pela primeira vez em 25/10 (seção 5), 6 deles
  usados em BUs.
- Nenhum evento depois das 17h de 25/10 (o pacote foi fechado às 13:29 locais).

## 8. Cruzamento BU x GEDAI

BUs de urna do 2º turno: 499.178 seções (493.464 de seção, 5.712 reservaSecao e
2 reservaEncerrandoSecao), em todas as 27 UFs e no exterior. Os 29 BUs do
Sistema de Apuração (exterior) ficam fora desta tabela e são tratados no fim da
seção.

| Verificação | Verificadas | Conferem | Não conferem |
|---|---|---|---|
| Código de carga do BU presente no GEDAI | 499.178 | 498.316 | 862 |
| Número interno da urna | 498.316 | 498.316 | 0 |
| Número de série da flash de carga (`numeroSerieFC` x `mc`) | 498.316 | 498.316 | 0 |
| Tipo (seção ou contingência) | 498.316 | 498.316 | 0 |
| Município e zona da carga | 498.316 | 498.316 | 0 |
| Seção (urnas de seção) | 492.628 | 492.628 | 0 |
| Estação geradora do BU existe nos logs (nome, TPM e instalação) | 499.178 | 499.092 | 86 |

- Nenhum código de carga do GEDAI aparece com mais de um número interno de urna.
- A estação geradora da mídia (no BU) é a mesma que leu a correspondência em
  327.940 casos; nos outros 170.376 a leitura foi feita em outra estação, o que é
  normal quando a mídia é gerada num computador e lida em outro.
- Tempo entre a carga (BU) e a primeira leitura no GEDAI: mediana de 5,0 horas,
  percentil 90 de 27,5 horas, máximo de 577 horas (24 dias).
- Em 14 seções a primeira leitura no GEDAI tem horário anterior à carga gravada
  no BU, de 0,1 a 20,5 minutos: todas em Botucatu (SP 62499), zona 0026, cargas
  de 26/09 lidas na estação ZSP026STD11 (lista em `gedai_leitura_antes_da_carga.csv`).
  Uma leitura não pode preceder a carga; a explicação mais simples é diferença
  entre o relógio da estação e o das urnas, que o log não permite confirmar.
- Histórico de cargas do BU: 866 seções têm algum código do histórico ausente do
  GEDAI (862 são o próprio código atual; 4 são códigos anteriores).
- Estações geradoras sem log publicado: `ZPR018STD02` gerou a mídia de 85 BUs de
  Jaguariaíva (PR 76333, zona 0018, cargas de 23/09) e `ZMG112STD02` a de 1 BU de
  Toledo (MG 53813, zona 0112, carga de 16/10). Nos 86 casos o código de carga
  está no GEDAI, lido por outra estação (em Jaguariaíva, `ZPR018STD01`, com 95
  leituras da zona). Nenhum log das duas estações geradoras foi publicado.
- Sistema de Apuração: os 29 BUs do exterior (tipo de arquivo `busa`) usam duas
  urnas, 1808076 e 1762246, com os códigos `723283724025687430931213` e
  `905001904443682739040437`. Os dois códigos estão no GEDAI como carga de
  contingência do exterior (município 29467, zona 0001), lidos em 18/09.

### 8.1 BUs com código de carga fora do GEDAI (862)

| UF | Estação geradora | Seções | Município (zona) | Data da carga no BU | Leituras da zona no GEDAI | Fim do log da estação geradora |
|---|---|---|---|---|---|---|
| PA | ZPA106STD083 | 358 | 05835 Parauapebas (0106) | 22/09 | 0 | 23/10 12:55 |
| SP | ZSP176STD16 | 267 | 64777 Guarulhos (0176) | 23 a 27/09 | 221 | 29/09 18:50 |
| MG | ZMG339STD02 | 96 | 47090 Jequeri, 50032 Piedade de Ponte Nova, 53252 Sericita, 54097 Urucânia (0339) | 19 e 20/09 | 0 | 18/09 19:46 |
| PA | ZPA019STD90 | 31 | 04952 Monte Alegre (0019) | 24/09 | 248 | 24/10 15:51 |
| AM | ZAM050WKS36855 | 28 | 02470 Juruá (0050) | 28/09 | 0 | 28/09 09:24 |
| DF | ZDF012WKS01 | 13 | 97012 Brasília (0001) | 29/09 | 295 | 25/10 12:17 |
| ES | ZES034STD01 | 5 | 56251 Cariacica (0034) | 15/10 | 556 | 15/10 16:19 |
| PA | ZPA107STD082 | 4 | 04154 (0107) | 15/10 | 372 | 24/10 11:35 |
| RO | RROWS27107 | 3 | 00035 e 00310 (0017 e 0020) | 24/10 | 438 | 18/09 19:32 |
| outras 51 estações | | 57 | 14 UFs | 03/10 a 25/10, quase todas em 24/10 | | |

- 836 são urnas de seção e 26 reservaSecao. Por UF: PA 405, SP 273, MG 103,
  AM 29, DF 13, PR 12, ES 5, SC 5, RO 4, RS 4, MT 2, RJ 2, SE 2, AC 1, AP 1, BA 1.
- Em 3 zonas não há nenhuma correspondência da zona em nenhum log publicado:
  Parauapebas zona 0106 (358 BUs; a zona 0075 do mesmo município tem 504
  leituras), a zona 0339 de MG (96 BUs em quatro municípios), Juruá zona 0050 (28
  BUs). Nesses três casos, junto com Guarulhos zona 0176 (267 BUs, com leituras
  parciais da zona), estão 749 dos 862 casos.
- Em 162 dos 862 casos o log publicado da estação geradora termina antes da data
  de carga do BU (por exemplo, ZMG339STD02 termina em 18/09 e as cargas são de
  19 e 20/09; ZAM050WKS36855 termina às 09:24 de 28/09, dia das cargas); nesses
  casos a leitura, se houve, não está no trecho publicado.
- Em 170 casos a mesma flash de carga tem outras correspondências lidas no
  GEDAI, mas não a desta urna.
- Por data de carga: 796 em setembro, 9 em 03/10, 22 entre 13 e 23/10, 34 em
  24/10 e 1 em 25/10 (Guarapuava).
- Lista completa em `gedai_bu_carga_fora_gedai.csv`.

## 9. Cargas do GEDAI sem BU

Das 507.937 cargas de seção vistas no GEDAI:

| Situação | Cargas |
|---|---|
| Usada no BU da seção | 492.628 |
| Presente só no histórico de cargas do BU (urna substituída por reservaSecao) | 5.701 |
| Seção com BU, mas com outra carga | 9.607 |
| Seção sem BU de urna | 1 |

- Nas 9.607 cargas de seção não usadas, 8.516 foram lidas antes da carga que o BU
  usou (carga refeita ou urna trocada antes da eleição). Em 1.036 casos as duas
  cargas foram lidas no mesmo momento ou a não usada foi lida depois, e em 55 a
  carga usada não tem leitura no GEDAI (está entre os 862 da seção 8.1); ficam
  para conferência no arquivo `cargas_gedai_secao.parquet`.
- A única carga de seção sem BU de urna é a da seção 0647 da zona 0001 de Moscou
  (ZZ 30163, urna 1760980). Essa seção tem BU do Sistema de Apuração, e não BU de
  urna.
- Das 55.394 cargas de contingência, 5.688 aparecem como carga de urna
  reservaSecao ou reservaEncerrandoSecao nos BUs. As demais são urnas de reserva
  não usadas.

## 10. Urnas de contingência (reservaSecao)

- 5.714 BUs de urna de reserva (5.712 reservaSecao e 2 reservaEncerrandoSecao),
  todos com identificação de contingência na carga.
- 4.542 usaram urna de contingência do mesmo município e zona da seção; 1.002 da
  mesma zona e outro município; 170 de outra zona.
- Nos 5.688 com carga no GEDAI, município e zona da carga conferem; 26 têm a carga
  fora do GEDAI.

## 11. Seções que encerraram depois das 17:30

Seções com BU de urna e encerramento depois das 17:30 de Brasília: 7.611. O
encerramento vem da última versão do BU no banco ClickHouse (`v_bu_ultima`),
convertido para Brasília pelo fuso do município (mesma tabela de
`scripts/ele2026/analisar_encerramento_t2.py`; exterior fora). Por UF: RJ 3.320,
SP 1.974, BA 1.051, PE 716, PB 316, SE 55, DF 33, PA 19, MA 17, MG 17, CE 14,
PI 14, MT 13, AM 9, RS 9, AL 7, RN 7, GO 5, ES 4, PR 3, SC 3, RO 2, AC 1, AP 1,
MS 1.

- 7.610 têm a carga no GEDAI, com urna e flash conferindo. A exceção é Cariacica
  (ES 56251, zona 0034, seção 0142), urna reservaSecao carregada em 15/10, com
  encerramento às 19:00:26.
- 7.489 são urnas de seção, 121 reservaSecao e 1 reservaEncerrandoSecao (1,60%
  de urnas de reserva, contra 1,14% no total de BUs). Por UF, proporção de urnas
  de reserva entre as tardias e entre as demais: RJ 1,48% e 1,48%; SP 0,81% e
  0,90%; BA 1,81% e 1,34%; PE 0,98% e 1,13%; PB 4,75% e 1,27%.
- Carga em outubro: 79 das 7.611 (1,04%), contra 1,9% no conjunto. Por período:
  7.532 até 30/09, 41 entre 01 e 04/10, 28 entre 05 e 23/10 e 10 em 24/10.
  Nenhuma seção tardia tem carga em 25/10.
- Tardias com carga a partir de 05/10 (38):

| UF | Município | Zona | Seção | Tipo | Carga (BU) | 1ª leitura GEDAI | Minutos após 17h |
|---|---|---|---|---|---|---|---|
| BA | 36854 Lauro de Freitas | 0180 | 0413 | seção | 15/10 19:54 | 16/10 12:27 | 121,2 |
| BA | 38490 Salvador | 0005 | 0100 | seção | 15/10 10:24 | 15/10 11:45 | 124,5 |
| BA | 38490 Salvador | 0005 | 0367 | seção | 24/10 10:59 | 24/10 12:11 | 121,2 |
| BA | 38490 Salvador | 0007 | 0351 | seção | 17/10 10:19 | 17/10 12:29 | 125,2 |
| BA | 38490 Salvador | 0010 | 0086 | seção | 24/10 11:09 | 24/10 11:28 | 121,6 |
| BA | 38873 São Miguel das Matas | 0036 | 0199 | reservaSecao | 20/10 11:46 | 20/10 15:38 | 111,9 |
| CE | 13897 Fortaleza | 0112 | 0428 | seção | 24/10 10:47 | 24/10 14:35 | 35,7 |
| ES | 56251 Cariacica | 0034 | 0142 | reservaSecao | 15/10 13:20 | ausente | 120,4 |
| PE | 23574 Cabo de Santo Agostinho | 0121 | 0203 | seção | 15/10 10:24 | 15/10 11:42 | 121,3 |
| PE | 24538 Itapetim | 0099 | 0026 | seção | 20/10 09:07 | 20/10 09:58 | 120,5 |
| PE | 25097 Passira | 0091 | 0074 | seção | 17/10 09:13 | 17/10 09:49 | 120,8 |
| PE | 25313 Recife | 0002 | 0068 | seção | 14/10 10:19 | 14/10 10:50 | 120,3 |
| PR | 77771 Ponta Grossa | 0014 | 0051 | reservaSecao | 13/10 15:29 | 13/10 17:25 | 122,1 |
| RJ | 58653 Niterói | 0144 | 0242 | seção | 20/10 09:53 | 20/10 13:07 | 53,0 |
| RJ | 58971 São Gonçalo | 0036 | 0434 | seção | 19/10 10:53 | 19/10 14:16 | 120,8 |
| RJ | 58971 São Gonçalo | 0087 | 0224 | seção | 24/10 10:54 | 24/10 10:58 | 125,9 |
| RJ | 60011 Rio de Janeiro | 0122 | 0011 | seção | 24/10 11:51 | 24/10 12:10 | 125,3 |
| RJ | 60011 Rio de Janeiro | 0214 | 0325 | reservaSecao | 15/10 10:21 | 15/10 14:47 | 122,3 |
| RJ | 60011 Rio de Janeiro | 0242 | 0118 | reservaSecao | 16/10 11:40 | 16/10 12:21 | 121,2 |
| SE | 31054 Aracaju | 0002 | 0991 | seção | 19/10 15:41 | 19/10 16:12 | 120,4 |
| SP | 66893 Mauá | 0217 | 0175 | seção | 15/10 16:33 | 15/10 16:51 | 121,7 |
| SP | 71072 São Paulo | 0002 | 0349 | seção | 15/10 13:21 | 15/10 13:33 | 120,4 |
| SP | 71072 São Paulo | 0002 | 0352 | seção | 15/10 13:16 | 15/10 13:33 | 120,5 |
| SP | 71072 São Paulo | 0006 | 0061 | seção | 24/10 09:22 | 24/10 10:08 | 126,1 |
| SP | 71072 São Paulo | 0006 | 0206 | seção | 24/10 11:03 | 24/10 11:22 | 120,9 |
| SP | 71072 São Paulo | 0006 | 0310 | seção | 24/10 09:32 | 24/10 10:09 | 126,4 |
| SP | 71072 São Paulo | 0006 | 0315 | seção | 24/10 09:41 | 24/10 10:09 | 126,5 |
| SP | 71072 São Paulo | 0257 | 0026 | seção | 14/10 13:58 | 14/10 17:05 | 41,6 |
| SP | 71072 São Paulo | 0257 | 0032 | seção | 24/10 12:22 | 24/10 12:45 | 47,2 |
| SP | 71072 São Paulo | 0257 | 0225 | seção | 18/10 14:28 | 19/10 15:35 | 61,2 |
| SP | 71072 São Paulo | 0280 | 0746 | seção | 17/10 10:02 | 17/10 10:23 | 117,4 |
| SP | 71072 São Paulo | 0280 | 0792 | seção | 17/10 14:19 | 17/10 14:43 | 121,6 |
| SP | 71072 São Paulo | 0352 | 0221 | seção | 22/10 10:18 | 22/10 15:21 | 120,5 |
| SP | 71072 São Paulo | 0381 | 0027 | seção | 15/10 15:24 | 16/10 15:51 | 121,3 |
| SP | 71072 São Paulo | 0381 | 0217 | seção | 17/10 13:12 | 22/10 16:07 | 125,0 |
| SP | 71072 São Paulo | 0381 | 0559 | seção | 20/10 09:57 | 20/10 11:07 | 124,2 |
| SP | 71072 São Paulo | 0404 | 0048 | seção | 16/10 16:21 | 16/10 17:15 | 35,3 |
| SP | 71072 São Paulo | 0418 | 0073 | seção | 16/10 10:31 | 16/10 10:35 | 120,9 |

Fora Cariacica, a carga dessas seções está registrada no GEDAI como em qualquer
outra seção. O atraso no encerramento não aparece associado a cargas de última
hora.

## 12. Salvador, Lauro de Freitas e Feira de Santana

| Município | Seções com BU | reservaSecao | Carga no GEDAI | Carga até 30/09 | 01 a 04/10 | 05 a 23/10 | 24/10 | 25/10 | Tardias (após 17:30) | Tardias com carga em outubro |
|---|---|---|---|---|---|---|---|---|---|---|
| 38490 Salvador | 5.124 | 32 | 5.124 | 5.084 | 8 | 20 | 12 | 0 | 772 | 6 |
| 36854 Lauro de Freitas | 413 | 26 | 413 | 406 | 3 | 4 | 0 | 0 | 46 | 1 |
| 35157 Feira de Santana | 1.218 | 20 | 1.218 | 1.197 | 0 | 18 | 3 | 0 | 63 | 0 |

- Nos três municípios todas as seções com BU têm a carga no GEDAI, com urna,
  flash e seção conferindo.
- Seções no GEDAI: Salvador 5.124 (5.216 cargas de seção e 366 de contingência),
  Lauro de Freitas 413 (442 e 79), Feira de Santana 1.218 (1.243 e 196).
- Salvador: das 40 cargas de outubro usadas nos BUs, as 32 feitas a partir de
  05/10 foram lidas no GEDAI entre 15/10 e 24/10, em estações das zonas 0001, 0004 a 0011, 0013, 0015 a 0019. Única
  mídia de carga gerada em outubro: zona 0014, 13/10, 24 seções. Doze cargas são
  de 24/10, todas lidas no mesmo dia.
- Lauro de Freitas: 4 cargas entre 15/10 19:53 e 20:47 (zona 0180, duas
  reservaSecao), lidas em 16/10 por volta de 12:27.
- Feira de Santana: 18 cargas entre 16 e 23/10 nas zonas 0154 a 0157 (6
  reservaSecao, quatro delas carregadas em 23/10 entre 09:35 e 09:56) e 3 em 24/10.
  Feira de Santana tem 351 primeiras leituras entre 01 e 04/10, mais do que os
  outros dois municípios.
- Nenhuma seção desses municípios tem carga em 25/10 nem código fora do GEDAI.

## 13. Itens para conferência

1. Cinco urnas de seção carregadas em 25/10, dia da eleição, antes da abertura:
   Campo Grande (MS) 0008/0486, Três Lagoas (MS) 0051/0044, Atibaia (SP)
   0016/0436, Carlópolis (PR) 0056/0037 e Guarapuava (PR) 0043/0397. A de
   Guarapuava não tem o código de carga em nenhum log publicado.
2. Parauapebas (PA 05835), zona 0106: 358 BUs com código de carga ausente de
   todos os logs publicados; sem nenhuma correspondência da zona nos logs.
3. Guarulhos (SP 64777), zona 0176: 267 BUs com código de carga fora do GEDAI;
   o log da estação geradora `ZSP176STD16` termina em 29/09.
4. Zona 0339 de MG (Jequeri, Piedade de Ponte Nova, Sericita e Urucânia): 96 BUs
   fora do GEDAI, sem correspondência da zona nos logs; o log da estação geradora
   termina em 18/09, antes das cargas.
5. Juruá (AM 02470), zona 0050: 28 BUs fora do GEDAI, sem correspondência da
   zona nos logs.
6. Outras 113 seções com código de carga fora do GEDAI, em 14 UFs (arquivo
   `gedai_bu_carga_fora_gedai.csv`).
7. Estações geradoras sem nenhum log publicado: `ZPR018STD02` (85 BUs de
   Jaguariaíva, PR) e `ZMG112STD02` (1 BU de Toledo, MG).
8. Código de contingência usado pela urna reservaSecao de São Paulo 0422/0222,
   que só entra no GEDAI por cadastro manual às 11:39 de 25/10.
9. Os 10 códigos de carga lidos pela primeira vez em 25/10 que não aparecem em
   BU, sobretudo os de Ibotirama (BA 35653, zona 0173), onde a mesma urna aparece
   em correspondências de várias seções.
10. Botucatu (SP 62499), zona 0026: 14 leituras no GEDAI com horário anterior à
    carga gravada no BU.
11. Estação `ZPE019WKS03` (PE), cuja versão de 25/10 é menor que a de 24/10.
12. 1.036 cargas de seção não usadas no BU e lidas ao mesmo tempo ou depois da
    carga usada.

A diferença de catálogo do portal (item 6 da versão anterior) foi resolvida: a
página do conjunto passou a listar os 112 recursos (seção 2).

## 14. Limitações

- O GEDAI registra a leitura das correspondências, não a carga. A data de carga
  vem do BU.
- A coleta de BU usada aqui (ClickHouse e partes Parquet de 26/10) cobre 499.207
  das 499.248 seções; as 41 restantes estão como não instaladas.
- O pacote mais recente foi fechado às 13:29 de 25/10. Leituras de
  correspondência feitas depois disso, se houver, não estão publicadas.
- Os horários do log são do relógio de cada estação, sem fuso explícito. O
  horário de carga do BU é o da urna. Nos estados com fuso diferente de Brasília
  as comparações de horário foram feitas no horário local, sem conversão.
- Os logs publicados não cobrem todas as estações que geraram mídias ou leram
  correspondências (casos de Parauapebas, da zona 0339 de MG, de Juruá e das
  estações sem log publicado).
- A assinatura `.vsc` dos logs e o hash por linha não foram verificados.
- O horário de encerramento usado para marcar as seções tardias vem do BU
  (`v_bu_ultima`), não do log da urna.

## 15. Reprodução

No servidor de análise, com os pacotes do GEDAI e as partes de BU disponíveis.
A extração dos logs (`extrair`) não mudou desde a primeira versão; as etapas
`bus` e `cruzar` foram refeitas com todas as pastas de partes:

```sh
python3 scripts/ele2026/gedai_t2.py extrair \
    --gedai ~/dataurnas-t2/gedai/1t ~/dataurnas-t2/gedai/2t ~/dataurnas-t2/gedai/2t_2510 \
    --saida <saida> --workers 80
python3 scripts/ele2026/gedai_t2.py bus \
    --bus ~/dataurnas-versoes-t2/bus/parts ~/dataurnas-versoes-t2-nne/bus/parts \
          ~/dataurnas-mac/versoes/2026/t2/bus/parts ~/dataurnas-mac/versoes/2026/t2-sseco/bus/parts \
    --saida <saida> --workers 64
python3 scripts/ele2026/gedai_t2.py cruzar --saida <saida> \
    --encerramento <saida>/enc_nacional.parquet
```

A etapa `bus` leu 871 partes e 501.425 versões de BU (499.178 seções, nenhum BU
ilegível) em 18 s; `cruzar` levou 80 s.

O arquivo de encerramento nacional saiu do ClickHouse:

```sql
SELECT uf, cd_mun, zona, secao,
  multiIf(cd_mun IN ('02020','02054','02135','02291','02313','02399','02496',
                     '02755','02917','98370','98477'), 2,
          cd_mun = '30015', -1, uf = 'ac', 2,
          uf IN ('am','mt','ms','ro','rr'), 1, 0) AS desloc_h,
  toString(hora_encerramento + toIntervalHour(desloc_h)) AS encerramento_bsb,
  round(dateDiff('second', toDateTime('2026-10-25 17:00:00', 'UTC'),
        hora_encerramento + toIntervalHour(desloc_h)) / 60, 2) AS minutos_apos_17h_bsb
FROM v_bu_ultima WHERE uf != 'zz'
INTO OUTFILE '/var/lib/clickhouse/user_files/enc_nacional_gl.parquet' TRUNCATE FORMAT Parquet;
```

BUs do Sistema de Apuração e seus códigos de carga:

```sql
SELECT uf, cd_mun, zona, secao, codigo_carga, numero_interno_urna, recebimento
FROM v_bu_ultima WHERE tipo_arquivo = 'busa' ORDER BY uf, cd_mun, zona, secao;
```

Saídas: `arquivos.parquet`, `correspondencias.parquet`,
`correspondencias_unicas.parquet`, `midias_carga.parquet`, `eventos_dia.parquet`,
`diff_versoes.parquet`, `bus_carga.parquet`, `cargas_gedai.parquet`,
`cargas_gedai_secao.parquet`, `cargas_gedai_24_25.parquet`,
`cruzamento_bus.parquet`, `pacotes.json` e `resumo.json`. Listas em CSV (também
copiadas para `data/parquet/2026/t2/linha_tempo/nacional/`, fora do git):
`gedai_bu_carga_fora_gedai.csv` (862), `gedai_bu_carga_2510.csv` (5),
`gedai_bu_gerador_sem_log.csv` (86) e `gedai_leitura_antes_da_carga.csv` (14).
