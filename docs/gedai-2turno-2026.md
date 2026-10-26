# Logs do GEDAI-UE no 2º turno de 2026

Relatório descritivo dos logs do GEDAI-UE publicados pelo TSE para o 2º turno de
2026 (pleito 3221, eleição 6258, votação em 25/10/2026) e do cruzamento desses
logs com os boletins de urna (BU) coletados. O texto descreve o que os arquivos
mostram. Onde algo não bate, o caso fica listado para conferência; nenhuma
divergência aqui é tratada como irregularidade.

Script: `scripts/ele2026/gedai_t2.py` (testes em `tests/ele2026/test_gedai_t2.py`).
Processamento feito no servidor de análise; as saídas ficam fora do repositório
(`~/dataurnas-t2/gedai/analise/` no servidor).

## 1. Resumo

- O GEDAI-UE é o sistema dos cartórios e TREs que gera as mídias de carga e de
  votação, lê de volta a tabela de correspondência gravada na flash de carga
  depois que as urnas são carregadas e transmite essas correspondências ao TSE.
  O log não registra a carga em si (ela acontece na urna); registra a geração da
  mídia de carga e a leitura posterior das correspondências.
- Foram lidos 4 pacotes por UF (1º turno: 03/10 e 04/10; 2º turno: 24/10 e
  25/10), 18.201 logs de estação, 4.907 estações distintas, nenhum arquivo
  ilegível. Os logs são cumulativos: o pacote do 2º turno traz o histórico da
  estação desde setembro.
- Há 563.331 códigos de carga distintos nas correspondências (507.937 de seção e
  55.394 de contingência).
- Das 151.642 seções do 2º turno com BU coletado, 151.203 (99,71%) têm o código
  de carga do BU no GEDAI, e em todas elas conferem o número interno da urna, o
  número de série da flash de carga, o tipo (seção ou contingência), o
  município, a zona e, para urnas de seção, a seção. 439 BUs têm código de carga
  ausente dos logs publicados (405 no Pará, 358 deles de uma única zona).
- Pela data de carga gravada no próprio BU, 144.602 urnas usadas no 2º turno
  foram carregadas até 30/09, 6.342 entre 01 e 04/10, 391 entre 05 e 23/10 e 307
  em 24/10. Nenhum BU tem carga em 25/10.
- Nos logs, nenhum evento de correspondência ocorre depois das 11:40:18 de
  25/10, e o último evento de qualquer tipo é das 13:29:56 de 25/10. Não há
  evento depois das 17h de 25/10.
- A versão de 25/10 acrescenta à de 24/10 52.105 linhas: 30.605 datadas de
  24/10 (tarde de sábado, depois do corte da versão de 24/10), 3.925 de 25/10 e
  o restante de dias anteriores (estações que só exportaram o log depois). Em
  25/10 há 42 leituras de correspondência e 164 transmissões; os 16 códigos de
  carga vistos pela primeira vez em 25/10 vêm de mídias de carga geradas em
  setembro e nenhum aparece nos BUs coletados.
- Os arquivos de 25/10 estão no índice de busca do portal (112 recursos), mas não
  na página do conjunto (56 recursos), conforme as respostas guardadas.

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
em duas respostas da API do portal guardadas em 26/10/2026 às 03:21:33 UTC:

| Resposta | `metadata_modified` do conjunto | Recursos listados |
|---|---|---|
| `package_search` (índice de busca) | 2026-10-25T17:40:46.916871 | 112 (56 de 24/10 e 56 de 25/10) |
| `package_show` (página do conjunto) | 2026-10-24T17:53:04.025235 | 56 (só os de 24/10) |

Nos recursos de 25/10 o campo `created` vai de 2026-10-25T17:24:18.815789 a
2026-10-25T17:36:14.123045 (o portal costuma gravar esses campos em UTC; se for
o caso, 14:24 a 14:36 de Brasília). Os recursos de 24/10 foram criados entre
2026-10-24T14:27:59 e 14:36:05. Ou seja, os arquivos de 25/10 existem no CDN e
aparecem na busca, mas a página do conjunto, no momento da coleta, ainda refletia
a versão de 24/10. A diferença pode ser só atraso de cache ou de reindexação do
portal; fica registrada para conferência.

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
contingência) estão em flashes de carga geradas entre 17 e 25/09. Em Ibotirama,
a mesma urna (número interno 1833178) aparece em correspondências das seções
0001, 0002, 0083 e 0235 e em uma de contingência, todas na mesma flash
`688BB468` ou em flashes da mesma zona; isso indica leituras repetidas de
flashes que carregaram várias vezes a mesma urna, mas o log não traz a data das
cargas. Nenhum desses 16 códigos aparece nos BUs coletados. Para MT, MS, MG, SP e
PR não há BU na coleta. Em Ibotirama, as seções 0001, 0002, 0083 e 0235 têm BU
coletado com outro código de carga, que está no GEDAI desde setembro; os códigos
lidos em 25/10 não são, portanto, os que essas seções usaram na votação. Ficam
listados para conferência.

## 6. Cargas por dia

Três medidas diferentes, porque o GEDAI não registra a carga em si:

1. data de carga gravada no BU (`dataHoraCarga`), só para as 151.642 seções com
   BU;
2. primeira leitura do código de carga no GEDAI (todas as UFs);
3. geração de mídias de carga no GEDAI.

| Período | BU, urna de seção | BU, reservaSecao | GEDAI, 1ª leitura de seção | GEDAI, 1ª leitura de contingência | Mídias de carga geradas |
|---|---|---|---|---|---|
| até 30/09 | 142.982 | 1.620 | 495.079 | 47.577 | 25.961 |
| 01 a 04/10 | 6.189 | 153 | 10.647 | 4.188 | 27 |
| 05 a 23/10 | 313 | 78 | 1.445 | 3.420 | 38 |
| 24/10 | 303 | 4 | 756 | 203 | 6 |
| 25/10 | 0 | 0 | 10 | 6 | 0 |
| Total | 149.787 | 1.855 | 507.937 | 55.394 | 26.032 |

- Quase todas as urnas do 2º turno usaram a carga feita em setembro para os dois
  turnos.
- De 05 a 23/10 a maior parte das leituras novas é de contingência (3.420 contra
  1.445), compatível com a preparação de urnas de reserva para o 2º turno.
- Em 25/10 não foi gerada nenhuma mídia de carga.
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

- BUs com carga em 24/10: 307 (303 de seção e 4 reservaSecao), entre 07h e 17h,
  a maioria entre 08h e 12h. Por UF: AC 19, AL 20, AM 20, AP 20, BA 36, CE 36,
  MA 27, PA 27, PB 19, PI 20, RR 20, SE 20, SP 2, TO 21 (SP tem cobertura de BU
  muito pequena). A quantidade próxima de 20 por UF é compatível com a troca das
  urnas sorteadas para o teste de integridade, feito com urnas retiradas das
  seções na véspera. Isso não está nos dados e precisa ser confirmado com as atas
  dos TREs.
- Das 307 cargas de 24/10 dos BUs, 298 estão no GEDAI, todas lidas em 24/10
  entre 08:06 e 18:15; as outras 9 (AC 1, AP 1 e PA 7) não aparecem nos logs
  publicados (seção 8.1).
- GEDAI: 959 códigos lidos pela primeira vez em 24/10 (756 de seção e 203 de
  contingência), em todas as 27 UFs e no exterior. 298 deles aparecem nos BUs
  coletados (294 de seção e 4 reservaSecao); os outros 661 são de UFs sem BU
  coletado, de urnas de contingência não usadas ou de cargas substituídas.
- Mídias de carga geradas em 24/10: 6 (RJ zona 0027, RS zona 0162, SC zona 0002,
  SE zona 0002, RN zona 0067 e SP zona 0052).

### 25/10 (dia da eleição)

- Nenhum BU coletado tem carga datada de 25/10.
- No GEDAI, 16 códigos lidos pela primeira vez em 25/10, em BA, MG, MS, MT, PR e
  SP, nenhum deles nos BUs coletados (ver seção 5).
- Nenhuma mídia de carga gerada em 25/10.
- Nenhum evento depois das 17h de 25/10 (o pacote foi fechado às 13:29 locais).

## 8. Cruzamento BU x GEDAI

BUs do 2º turno coletados: 151.642 seções (149.787 de urna de seção e 1.855
reservaSecao). A cobertura é desigual: AC, AL, AM, AP, BA, CE, MA, PA, PB, PI,
RR, SE, TO e ZZ estão quase completos; SP tem 1.033 seções; DF, ES, GO, MG, MS,
MT, PE, PR, RJ, RN, RO, RS e SC não têm BU na coleta usada.

| Verificação | Verificadas | Conferem | Não conferem |
|---|---|---|---|
| Código de carga do BU presente no GEDAI | 151.642 | 151.203 | 439 |
| Número interno da urna | 151.203 | 151.203 | 0 |
| Número de série da flash de carga (`numeroSerieFC` x `mc`) | 151.203 | 151.203 | 0 |
| Tipo (seção ou contingência) | 151.203 | 151.203 | 0 |
| Município e zona da carga | 151.203 | 151.203 | 0 |
| Seção (urnas de seção) | 149.364 | 149.364 | 0 |
| Estação geradora do BU existe nos logs (nome, TPM e instalação) | 151.642 | 151.642 | 0 |

- Nenhum código de carga do GEDAI aparece com mais de um número interno de urna.
- A estação geradora da mídia (no BU) é a mesma que leu a correspondência em
  86.751 casos; nos outros 64.452 a leitura foi feita em outra estação, o que é
  normal quando a mídia é gerada num computador e lida em outro.
- Tempo entre a carga (BU) e a primeira leitura no GEDAI: mediana de 6,2 horas,
  percentil 90 de 27 horas, máximo de 577 horas (24 dias); nenhuma leitura
  anterior à carga.
- Histórico de cargas do BU: 440 seções têm algum código do histórico ausente do
  GEDAI (439 são o próprio código atual; 1 é código anterior de reservaSecao).

### 8.1 BUs com código de carga fora do GEDAI (439)

| UF | Estação geradora | Seções | Data da carga no BU |
|---|---|---|---|
| PA | ZPA106STD083 | 358 | 22/09 |
| PA | ZPA019STD90 | 31 | 24/09 |
| AM | ZAM050WKS36855 | 28 | 28/09 |
| PA | ZPA107STD082 | 4 | 15/10 |
| PA | outras 10 estações | 12 | 03/10 a 24/10 |
| SE | RSEWGM04 | 2 (reservaSecao) | 19/10 |
| AM | RAMWSEVIN44126 | 1 | 03/10 |
| AC | ZAC001STD25 | 1 | 24/10 |
| AP | RAPWGM09 | 1 | 24/10 |
| BA | ZBA137WKS01 | 1 (reservaSecao) | 15/10 |

- 423 são urnas de seção e 16 reservaSecao. Todas foram geradas em estações que
  existem nos logs publicados.
- Parauapebas (PA, 05835), zona 0106: 358 BUs. As mídias de carga dessas urnas
  aparecem geradas no log de `ZPA106STD083`, mas nenhum log publicado tem
  qualquer correspondência da zona 0106 (a zona 0075 do mesmo município tem 504
  leituras). As duas estações da zona não registram atividade entre 19/09 e
  13/10. A leitura das correspondências da zona provavelmente ocorreu em outra
  estação cujo log não está publicado, ou num trecho de log que não foi
  exportado. Fica para conferência com o TRE-PA.
- Em 36 dos 439 casos o log da estação geradora termina antes da data de carga
  do BU (por exemplo cargas de 24/10 em estações cujo log publicado acaba em
  setembro ou em 16/10); nesses casos a leitura, se houve, não está no trecho
  publicado.
- Em 50 casos a mesma flash de carga tem outras correspondências lidas no
  GEDAI, mas não a desta urna.

## 9. Cargas do GEDAI sem BU

Das 507.937 cargas de seção vistas no GEDAI:

| Situação | Cargas |
|---|---|
| Usada no BU da seção | 149.364 |
| Presente só no histórico de cargas do BU (urna substituída por reservaSecao) | 1.845 |
| Seção com BU coletado, mas com outra carga | 2.657 |
| Seção sem BU na coleta | 354.071 |

- Nas 2.657 cargas de seção não usadas em seção com BU, 2.350 foram lidas antes
  da carga que o BU usou (carga refeita ou urna trocada antes da eleição). Em 307
  casos as duas cargas foram lidas no mesmo momento ou a não usada foi lida
  depois; ficam para conferência no arquivo `cargas_gedai_secao.parquet`.
- As 354.071 cargas de seções sem BU coletado se concentram nas UFs fora da
  coleta (SP 104.654, MG 52.666, RJ 38.337, RS 27.925, PR 27.790, PE 21.683,
  entre outras) e não indicam falta de BU no TSE.
- Das 55.394 cargas de contingência, 1.855 aparecem como carga de urna
  reservaSecao nos BUs coletados. As demais são urnas de reserva não usadas ou de
  UFs sem coleta.

## 10. Urnas de contingência (reservaSecao)

- 1.855 BUs de reservaSecao, todos com identificação de contingência na carga.
- 1.446 usaram urna de contingência do mesmo município e zona da seção; 324 da
  mesma zona e outro município; 85 de outra zona.
- Em todos, município e zona da carga conferem com o GEDAI.

## 11. Seções que encerraram depois das 17:30

Seções com BU e `minutos_apos_17h_bsb` acima de 30 no parquet de encerramento:
1.485 (BA 1.048, PB 316, SE 55, CE 14, MA 14, PI 14, AM 8, PA 8, AL 7, AP 1).

- Todas têm a carga no GEDAI, com urna e flash conferindo.
- 1.444 são urnas de seção e 41 reservaSecao (2,76%, contra 1,22% no total de
  BUs). Na BA a proporção de reservaSecao é 1,8% entre as tardias e 1,3% entre as
  demais; em Salvador, 1,2% e 0,5%; na PB, 4,7% e 1,3%.
- Carga em outubro: 34 das 1.485 (2,3%), contra 4,6% no conjunto. Por período:
  1.451 até 30/09, 26 entre 01 e 04/10, 5 entre 05 e 23/10 e 3 em 24/10.
- Tardias com carga a partir de 05/10:

| UF | Município | Zona | Seção | Tipo | Carga (BU) | 1ª leitura GEDAI | Minutos após 17h |
|---|---|---|---|---|---|---|---|
| CE | 13897 | 0112 | 0428 | seção | 24/10 10:47 | 24/10 14:35 | 35,7 |
| BA | 38490 Salvador | 0005 | 0100 | seção | 15/10 10:24 | 15/10 11:45 | 124,5 |
| BA | 38490 Salvador | 0005 | 0367 | seção | 24/10 10:59 | 24/10 12:11 | 121,2 |
| BA | 38490 Salvador | 0007 | 0351 | seção | 17/10 10:19 | 17/10 12:29 | 125,2 |
| BA | 38490 Salvador | 0010 | 0086 | seção | 24/10 11:09 | 24/10 11:28 | 121,6 |
| BA | 38873 | 0036 | 0199 | reservaSecao | 20/10 11:46 | 20/10 15:38 | 111,9 |
| BA | 36854 Lauro de Freitas | 0180 | 0413 | seção | 15/10 19:54 | 16/10 12:27 | 121,2 |
| SE | 31054 | 0002 | 0991 | seção | 19/10 15:41 | 19/10 16:12 | 120,4 |

Nada no GEDAI distingue essas seções das demais: a carga está registrada como em
qualquer outra seção. O atraso no encerramento não aparece associado a cargas de
última hora.

## 12. Salvador, Lauro de Freitas e Feira de Santana

| Município | Seções com BU | reservaSecao | Carga no GEDAI | Carga até 30/09 | 01 a 04/10 | 05 a 23/10 | 24/10 | 25/10 | Tardias (após 17:30) | Tardias com carga em outubro |
|---|---|---|---|---|---|---|---|---|---|---|
| 38490 Salvador | 5.123 | 32 | 5.123 | 5.083 | 8 | 20 | 12 | 0 | 772 | 6 |
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

1. Parauapebas (PA 05835), zona 0106: 358 BUs com código de carga ausente de
   todos os logs publicados; sem nenhuma correspondência da zona nos logs.
2. Outras 81 seções com código de carga fora do GEDAI, em PA, AM, SE, AC, AP e
   BA (arquivo `cruzamento_bus.parquet`, coluna `carga_no_gedai`).
3. Os 16 códigos de carga lidos pela primeira vez em 25/10, sobretudo os de
   Ibotirama (BA 35653, zona 0173), onde a mesma urna aparece em correspondências
   de várias seções.
4. Estação `ZPE019WKS03` (PE), cuja versão de 25/10 é menor que a de 24/10.
5. 307 cargas de seção não usadas no BU e lidas ao mesmo tempo ou depois da
   carga usada.
6. Página do conjunto no portal sem os 56 recursos de 25/10 que aparecem na
   busca.

## 14. Limitações

- O GEDAI registra a leitura das correspondências, não a carga. A data de carga
  vem do BU, que só existe para as seções coletadas.
- A coleta de BU do 2º turno usada aqui (cópia de 26/10) cobre 151.642 seções e
  deixa de fora 13 UFs inteiras; os números de cruzamento valem para as UFs
  cobertas.
- O pacote mais recente foi fechado às 13:29 de 25/10. Leituras de
  correspondência feitas depois disso, se houver, não estão publicadas.
- Os horários do log são do relógio de cada estação, sem fuso explícito. O
  horário de carga do BU é o da urna. Nos estados com fuso diferente de Brasília
  as comparações de horário foram feitas no horário local, sem conversão.
- Os logs publicados não cobrem necessariamente todas as estações que leram
  correspondências (caso de Parauapebas).
- A assinatura `.vsc` dos logs e o hash por linha não foram verificados.
- O parquet de encerramento é parcial e foi usado só para marcar as seções
  tardias.

## 15. Reprodução

No servidor de análise, com os pacotes do GEDAI e as partes de BU disponíveis:

```sh
python3 scripts/ele2026/gedai_t2.py tudo \
    --gedai ~/dataurnas-t2/gedai/1t ~/dataurnas-t2/gedai/2t ~/dataurnas-t2/gedai/2t_2510 \
    --bus ~/dataurnas-mac/versoes/2026/t2/bus/parts ~/dataurnas-mac/versoes/2026/t2-sseco/bus/parts \
    --encerramento ~/dataurnas-mac/parquet-t2/encerramento/secoes_encerramento.parquet \
    --saida ~/dataurnas-t2/gedai/analise --workers 80
```

Saídas: `arquivos.parquet`, `correspondencias.parquet`,
`correspondencias_unicas.parquet`, `midias_carga.parquet`, `eventos_dia.parquet`,
`diff_versoes.parquet`, `bus_carga.parquet`, `cargas_gedai.parquet`,
`cargas_gedai_secao.parquet`, `cargas_gedai_24_25.parquet`,
`cruzamento_bus.parquet`, `pacotes.json` e `resumo.json`. A execução completa
levou 100 segundos com 80 processos.
