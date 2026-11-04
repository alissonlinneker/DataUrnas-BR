# Pacote nacional do TSE (2026): imagem do BU contra o BU e log eleitor a eleitor, nos dois turnos

Pergunta: no pacote que o TSE publicou com todos os arquivos de todas as seções, (A) a imagem do boletim impresso (`-imgbu.dat`) diz o mesmo que o boletim digital (`-bu.dat`)? E (B) o log da urna, lido eleitor a eleitor nas 499 mil seções dos dois turnos, mostra mesário votando no lugar de eleitores ausentes em escala capaz de mudar o resultado?

## Destaques (divergências primeiro)

**A. Imagem do BU x BU: nenhum voto diverge.** Em 998.354 pares seção x turno com os dois arquivos (499.176 no 1º turno e 499.178 no 2º), os votos de Presidente por candidato, brancos, nulos, nominais, total apurado, aptos, comparecimento e as três contagens de habilitação (biométrica, biográfica, sem biometria) são iguais. As 60 seções do Sistema de Apuração (cédula, arquivos `-busa.dat` e `-imgbusa.dat`) também conferem. Somando tudo, o 2º turno dá exatamente o resultado oficial: 13 = 64.256.232, 22 = 59.826.041, brancos 1.430.496, nulos 2.723.305.

Única diferença encontrada, em 9 seções: o **código de identificação da urna** impresso na imagem não é o mesmo gravado no BU. Todas as 9 são urnas de contingência (`reservaSecao`), e os votos são idênticos nos dois lados. Em CE 13552/0033/0322, o log mostra a explicação: a urna 02239306 votou e imprimiu o BU até 17:03; às 18:14 a urna de contingência 02203617 recuperou os dados e gerou o arquivo do BU com o próprio número. Nas outras 8.738 seções de contingência os dois códigos coincidem.

| Turno | Seção (UF/município/zona/seção) | Código no BU | Código na imagem |
|---|---|---|---|
| 1º | BA 34290/0127/0054 | 01656072 | 01670237 |
| 1º | BA 39136/0033/0178 | 01656619 | 01656945 |
| 1º | CE 13552/0033/0322 | 02203617 | 02239306 |
| 1º | PR 76236/0093/0083 | 02060632 | 02089535 |
| 1º | SP 70750/0296/0019 | 01667058 | 01782131 |
| 2º | PA 05290/0036/0441 | 01808117 | 01657575 |
| 2º | PB 19933/0003/0259 | 01667313 | 01799274 |
| 2º | RJ 58971/0068/0154 | 02164896 | 02226870 |
| 2º | RS 84913/0138/0014 | 02334491 | 02282678 |

**B. Log x BU: 16 seções (9 no 1º turno, 7 no 2º) em que os votos do log não somam o comparecimento do BU.** Em 15 delas o log tem **menos** votos que o BU, e o motivo aparece no próprio pacote: falta o log da urna substituída, ou falta o trecho final do log antes de um reinício. Em 1 o log tem **mais** votos, porque o pacote traz o log de outra seção. Em nenhuma o BU e a imagem divergem, e a recontagem nacional do RDV dos dois turnos ([rdv-log-2026.md](rdv-log-2026.md)) já mostrou RDV igual ao BU em todas as seções. Ou seja: o que falta é registro no log, não voto no resultado.

| Turno | Seção | Votos no log | Comparecimento no BU | O que o pacote mostra |
|---|---|---:|---:|---|
| 1º | BA 39934/0183/0175 | 236 | 272 | três urnas; os logs das duas substituídas trazem 100 e 24 votos, o da última 112 |
| 1º | ES 56995/0053/0211 | 264 | 265 | uma urna, reinício às 17:05 |
| 1º | RJ 58971/0087/0184 | 256 | 258 | uma urna, 18 reinícios |
| 1º | RN 16039/0029/0028 | 241 | 242 | troca de urna às 13:58 |
| 1º | RS 89036/0083/0044 | 278 | 279 | troca de urna; duas cópias do log da substituída |
| 1º | SP 63614/0227/0305 | 289 | 290 | uma urna, reinício às 08:17 |
| 1º | SP 64254/0291/0346 | 277 | 278 | uma urna, reinício às 10:41 |
| 1º | SP 71072/0002/0035 | 232 | 247 | o log da urna substituída só cobre 10:18 a 10:52, sem votos |
| 1º | SP 71072/0260/0037 | 284 | 285 | uma urna, reinício às 13:45 |
| 2º | BA 34711/0021/0178 | 233 | 234 | o log para às 08:37:32, no meio da habilitação de um eleitor, e só volta no reinício das 09:03 |
| 2º | BA 35653/0173/0235 | 204 | 217 | a urna original 01833178 não tem votos no log; falta o trecho de 07:48 a 09:01 |
| 2º | ES 57932/0009/0085 | 612 | 308 | o pacote inclui o log da urna da seção 0112 (304 votos), além do log da própria seção (308) |
| 2º | MA 08893/0047/0609 | 188 | 224 | o log aninhado é da urna da seção 0445, sem votos; falta o log da urna original |
| 2º | PB 21750/0002/0254 | 303 | 304 | uma urna, reinício às 13:03 |
| 2º | PI 11533/0003/0216 | 258 | 259 | uma urna, 6 reinícios |
| 2º | RS 89060/0017/0191 | 90 | 92 | troca de urna às 09:58 |

A seção ES 57932/0009/0112, cujo log aparece dentro do pacote da 0085, tem o próprio pacote correto (304 votos no log e no BU). A MA 08893/0047/0445 também confere (311 e 311).

**Pacote republicado durante a leitura.** Três arquivos do TSE mudaram em 03/11/2026, depois de lidos aqui: 1º turno MA (19:59 GMT), 1º turno MG (21:08 GMT) e 2º turno SP (19:48 GMT, no meio do download). O diretório atual dos três tem os mesmos nomes de seção e de tipo de arquivo, com três diferenças conferidas:

1. MG 1º turno, seção 50075/0047/0041 (Piedade dos Gerais): na versão lida havia um `-imgbu.dat` da urna 02422379 (258 votos: 13 = 98, 22 = 115). A versão nova tirou esse arquivo e deixou só o `-imgbusa.dat` do Sistema de Apuração (278 votos: 13 = 103, 22 = 125), que confere com o `-busa.dat`. A diferença de 20 votos, em todos os candidatos e nulos, é a parte da votação feita em cédula depois da urna; não há BU de urna para comparar.
2. SP 2º turno, seção 64777/0395/0298: o `-log.jez` e o `-vota.vsc` foram regravados em 03/11 12:10. O `.vsc` tem o mesmo CRC da versão de 26/10, e as métricas do log, relidas da versão nova, são iguais às calculadas aqui (268 votos, igual ao BU). Conferido à parte: o SHA-512 do `-log.jez` regravado é o mesmo que a urna assinou no `-vota.vsc` (que não mudou desde 26/10), e as 11 assinaturas ECDSA secp521r1 de arquivo dessa seção são válidas. O conteúdo do log é, portanto, o assinado na noite da eleição; mudou só a entrada no zip.
3. Os `-bu.dat` e `-vota.vsc` de SP 2º turno são todos iguais (CRC) aos do pacote de 26/10 já confrontado em [cadeia-de-confianca-2026.md](cadeia-de-confianca-2026.md).

No MA 1º turno a mudança não aparece no diretório (nenhum membro com data posterior a 20/10). Isso fica como limitação.

**B. Mesário votando no lugar de ausentes: não há sinal em escala.** Resumo dos números do 2º turno, detalhados abaixo:

- Nenhum par de votos da mesma urna com menos de 10 segundos de intervalo, nos dois turnos.
- Sequências de 5 ou mais votos seguidos, todos sem biometria e cada um a menos de 30 s do anterior: **1 no Brasil inteiro** (PE 24570/0147/0393, 6 votos) e 12 no exterior, onde ninguém vota com biometria.
- Votos sem biometria depois das 17h de Brasília: 5.886 no país (5.469 sem o exterior).
- O aumento da fatia de votos sem biometria entre os turnos **não** tem relação com o ganho do 13 sobre o 22, comparando seções do mesmo município (coeficiente praticamente zero, p = 0,88). No 1% de seções com maior aumento, o 13 ganhou 0,18 ponto **a menos** que nas vizinhas.
- A diferença final foi de 4.430.191 votos.

## Fonte e método

| Item | Valor |
|---|---|
| Arquivos | `https://cdn.tse.jus.br/estatistica/sead/eleicoes/eleicoes2026/arqurnatot/bu_imgbu_logjez_rdv_vscmr_2026_<1t\|2t>_<UF>.zip`, 28 UFs (incluindo ZZ, exterior), 56 arquivos, 219 GB |
| Seções | 499.207 por turno (o pacote tem uma linha de arquivos por seção) |
| Leitura | cada zip baixado para a memória do servidor de análise (`/dev/shm`), processado e apagado; nada gravado no disco além dos resultados por seção |
| Rede | no máximo 4 conexões simultâneas ao CDN do TSE, sem troca de IP; arquivos que não estavam no cache do CDN vieram a cerca de 0,6 MB/s por conexão, e a leitura completa levou cerca de 12 horas |
| Código | `scripts/ele2026/pacote_nacional.py` e o parser novo `src/dataurnas/parsers/imgbu.py` |

### A. Imagem do BU

O `-imgbu.dat` é um envelope ASN.1 (`EntidadeEnvelopeGenerico`, `spec/v2/bu.asn1`) cujo conteúdo é o texto do boletim impresso, em latin-1, seguido dos blocos do QR code ("BU DIGITAL"), do certificado e da assinatura. O parser lê só o texto antes de "BU DIGITAL": o cabeçalho (aptos, comparecimento, as três habilitações, faltosos, código da urna, horários) e o bloco de PRESIDENTE (candidato, número, votos, aptos, nominais, brancos, nulos, total apurado). Trecho real (AC, Bujari, 2º turno):

```text
Comparecimento                    0232
        Habilitação biométrica    0210
        Habilitação biográfica    0014
        Habilitação sem biometria 0008
...
--------------PRESIDENTE--------------
  LULA                        13  0068
  FLAVIO BOLSONARO            22  0149
Brancos                           0002
Nulos                             0013
Total Apurado                     0232
```

O `-bu.dat` é decodificado pelo parser do projeto (`parsers/bu.py`). Os campos comparados:

| Imagem | BU |
|---|---|
| votos por candidato a Presidente | `votosVotaveis` nominais do cargo Presidente |
| Brancos, Nulos, Total de votos Nominais | votos branco, nulo e soma dos nominais |
| Total Apurado; Comparecimento do cabeçalho | `qtdComparecimento` do cargo |
| Eleitores aptos (bloco e cabeçalho) | `qtdEleitoresAptos` |
| Habilitação biométrica, biográfica, sem biometria | `detalhamentoComparecimento` (três campos) |
| Código identificação UE | `numeroInternoUrna` da carga |

As seções do Sistema de Apuração não têm `-bu.dat` nem `-imgbu.dat`; para elas foram lidos `-busa.dat` e `-imgbusa.dat` por HTTP Range (subcomando `sa`). A impressão do Sistema de Apuração não traz comparecimento nem habilitações no cabeçalho; só os campos impressos entram.

### B. Log eleitor a eleitor

O `-log.jez` é um ZIP com o `logd.dat` e, na troca de urna, os logs das urnas substituídas como ZIPs aninhados (lidos por `parsers/log.py`, `textos_zip`). Só entram as linhas com a data do turno (04/10/2026 ou 25/10/2026): o log do 2º turno traz também os eventos do 1º.

Cada eleitor começa em "Identificador do eleitor digitado pelo mesário" e termina em "Eleitor foi habilitado". A classe da habilitação segue as regras de [biometria-1t-2t-2026.md](biometria-1t-2t-2026.md):

| Classe | Regra no log | Campo do BU |
|---|---|---|
| biométrica | "Tipo de habilitação do eleitor [biométrica]" | habilitados por biometria |
| biográfica | houve "Solicita digital" e depois dado pessoal ou "Mesário N habilitou o eleitor" | habilitados por biografia |
| sem digital | habilitado sem nenhum "Solicita digital" (eleitor sem biometria cadastrada, liberado pelo título ou documento) | compareceram sem biometria |
| outro | pediu digital, sem tipo biométrico e sem habilitação manual | nenhum |

A classe é ligada ao "O voto do eleitor foi computado" seguinte. "Sem biometria" no relatório é tudo que não é biométrico. Com a linha do tempo dos votos de cada urna:

- **sequência rápida**: 5 ou mais votos seguidos na mesma urna, cada um a menos de 30 s do anterior; contada também a sequência só de votos sem biometria;
- **maior sequência sem biometria**: o maior número de votos seguidos sem biometria, em qualquer ritmo;
- **última hora** e **depois das 17h**: hora local convertida para Brasília pelo fuso do município (`analyzer/timezones.py`); no exterior, o horário local do país;
- **fora do horário, reinícios e trocas de urna**: rotina `analisar_log_tempo` de `analyzer/rdv_recontagem.py` (voto antes das 8h, antes de "Urna pronta", depois de "Inicio do Encerramento", com outra data, relógio invertido; reinício = mais de uma "Urna pronta para receber votos" no dia; troca = votos de mais de uma urna);
- **eventos**: todas as linhas com nível diferente de INFO, agrupadas por mensagem (números trocados por N).

### Teste de swing

Swing de uma seção = fatia do 13 entre 13 e 22 no 2º turno menos a mesma fatia no 1º. Para cada indicador do log, a variação entre turnos (fatia de votos sem biometria, fatia de votos em sequência rápida, fatia de votos sem biometria em sequência rápida, fatia de votos sem biometria na última hora e depois das 17h) entra numa regressão do swing com efeito fixo de município (cada seção comparada com as do próprio município) e erro padrão agrupado por município. Base: seções com pelo menos 20 votos nos dois turnos.

## A. Resultado: imagem do BU x BU

| | 1º turno | 2º turno |
|---|---:|---:|
| Seções no pacote | 499.207 | 499.207 |
| Com `-bu.dat` e `-imgbu.dat` | 499.176 | 499.178 |
| Imagem com bloco de Presidente | 499.176 | 499.178 |
| Erros de leitura (BU ou imagem) | 0 | 0 |
| Votos, brancos, nulos, aptos, comparecimento e habilitações iguais | 499.176 | 499.178 |
| Diferença só no código da urna (contingência) | 5 | 4 |
| Seções do Sistema de Apuração (`busa`/`imgbusa`) | 31 | 29 |
| Sistema de Apuração: imagem = BU | 31 | 29 |

| Soma nacional (Presidente) | 1º turno | 2º turno |
|---|---:|---:|
| 13, urnas (BU = imagem) | 53.878.914 | 64.255.787 |
| 22, urnas (BU = imagem) | 56.103.951 | 59.825.688 |
| 13, Sistema de Apuração | 624 | 445 |
| 22, Sistema de Apuração | 552 | 353 |
| **13, total** | **53.879.538** | **64.256.232** |
| **22, total** | **56.104.503** | **59.826.041** |
| Brancos (urnas + apuração) | 2.300.798 | 1.430.496 |
| Nulos (urnas + apuração) | 3.669.003 | 2.723.305 |
| Comparecimento (urnas + apuração) | 125.275.835 | 128.236.074 |

Das 60 seções do Sistema de Apuração, 58 são do exterior (29 por turno) e 2 de MG no 1º turno (41238/0039/0168 e 50075/0047/0041).

## B. Resultado: log eleitor a eleitor

### Log x BU

| | 1º turno | 2º turno |
|---|---:|---:|
| Seções com log | 499.176 | 499.178 |
| Logs lidos sem erro | 499.176 | 499.178 |
| Votos no log = comparecimento do BU | 499.167 | 499.171 |
| Votos no log diferentes do BU | 9 | 7 |
| Soma dos votos no log | 125.274.428 | 128.235.493 |
| Soma do comparecimento nos BUs de urna | 125.274.487 | 128.235.243 |

A soma do log no 2º turno passa a do BU em 250 votos por causa da seção ES 57932/0009/0085 (304 votos de outra seção a mais) menos os 54 que faltam nas outras seis.

Nas seções do Brasil (o BU do exterior não traz as três contagens de habilitação: lá ninguém vota com biometria), a classe lida no log bate com o BU seção a seção:

| Seções do Brasil | 1º turno | 2º turno |
|---|---:|---:|
| Seções | 497.895 | 497.897 |
| sem digital no log = "sem biometria" do BU | 497.893 | 497.895 |
| biográfica no log = "biografia" do BU | 497.892 | 497.893 |
| biométrica no log = "biometria" do BU | 493.887 | 493.558 |
| Soma: biométrica no log / no BU | 109.646.855 / 109.650.927 | 111.966.019 / 111.970.333 |
| Soma: biográfica no log / no BU | 8.342.245 / 8.342.249 | 8.632.485 / 8.632.488 |
| Soma: sem digital no log / sem biometria no BU | 6.940.329 / 6.940.334 | 7.252.021 / 7.251.810 |
| Classe "outro" no log | 4.020 | 4.356 |

A diferença na classe biométrica tem o tamanho da classe "outro" (eleitor que pôs o dedo e foi habilitado sem a linha "Tipo de habilitação [biométrica]"): o BU conta esses eleitores como biométricos.

### Biometria, ritmo e horário

| Brasil e exterior | 1º turno | 2º turno |
|---|---:|---:|
| Votos sem biometria | 15.627.573 (12,47%) | 16.269.474 (12,69%) |
| Votos sem biometria, sem o exterior | 15.286.596 (12,24%) | 15.888.862 (12,43%) |
| Intervalos de voto da mesma urna abaixo de 10 s | 0 | 0 |
| Intervalos abaixo de 30 s | 3.962 | 1.580.240 |
| Sequências rápidas (5 ou mais votos, cada um a menos de 30 s) | 3, em 3 seções | 4.378, em 3.689 seções |
| Votos nessas sequências | 15 | 23.569 |
| Votos sem biometria nessas sequências | 10 | 733 |
| Sequências rápidas só de votos sem biometria, no Brasil | 0 | 1 (PE 24570/0147/0393, 6 votos) |
| Sequências rápidas só de votos sem biometria, no exterior | 2 | 12 |
| Maior sequência rápida | 5 | 12 |
| Votos na última hora (16h a 17h de Brasília) | 11.200.346 | 6.643.153 |
| Sem biometria na última hora | 1.378.087 (12,30%) | 840.183 (12,65%) |
| Votos depois das 17h de Brasília | 3.727.772 | 34.747 |
| Sem biometria depois das 17h | 444.785 (11,93%) | 5.886 (16,94%) |

No 2º turno, com um só cargo, o ciclo do eleitor é bem mais curto, por isso intervalos abaixo de 30 s ficam comuns; abaixo de 10 s não há nenhum. A maior sequência rápida tem 12 votos. Nas sequências rápidas, só 3,1% dos votos são sem biometria (733 de 23.569), contra 12,7% no dia inteiro: o ritmo rápido vem de eleitores com biometria, não de liberações manuais. Os votos depois das 17h no 1º turno são as filas do encerramento tardio (ver [encerramento-tardio-2turno-2026.md](encerramento-tardio-2turno-2026.md)).

A fatia sem biometria depois das 17h do 2º turno (16,9%, ou 15,9% sem o exterior) é maior que a do dia (12,4%). Mesmo se todo o excedente fosse irregular, seriam cerca de 1.200 votos no país.

### Fora do horário, reinícios, trocas de urna

| | 1º turno | 2º turno |
|---|---:|---:|
| Seções com voto antes das 8h | 0 | 0 |
| Seções com voto antes de "Urna pronta" | 0 | 0 |
| Seções com voto depois de "Inicio do Encerramento" | 0 | 0 |
| Seções com voto em outra data | 0 | 0 |
| Seções com relógio invertido entre votos | 0 | 0 |
| Seções com reinício (mais de uma "Urna pronta") | 28.255 | 24.625 |
| Seções com votos em mais de uma urna (troca) | 2.101 | 1.417 |

### Eventos de erro

Mensagens de nível ERRO mais frequentes (lista completa, com ALERTA e os demais níveis, em `eventos_nao_info.csv`):

| Mensagem (números trocados por N) | 1º turno: ocorrências / seções | 2º turno: ocorrências / seções |
|---|---|---|
| Problema ao desmontar a MR | ausente | 531.983 / 497.702 |
| Captura da digital do eleitor, falha na captura da digital | 4.270 / 1.977 | 3.732 / 1.745 |
| Não foi possível exibir imagem no LCD do terminal do mesário | 2.077 / 1.460 | 2.714 / 1.829 |
| Erro ao tentar configurar LED do MT | 742 / 741 | 728 / 725 |
| Erro inesperado, ERROR opening the biometric reader | 589 / 217 | 479 / 188 |
| Erro inesperado, ERROR starting image acquisition | 497 / 417 | 414 / 349 |
| Erro inesperado durante a votação, o voto do eleitor NÃO foi registrado | 368 / 260 | 334 / 242 |
| Impressora com atolamento de papel | 201 / 175 | abaixo das 12 primeiras |

"Problema ao desmontar a MR" já tinha sido visto na amostra ([rdv-log-2026.md](rdv-log-2026.md)): aparece na inicialização do aplicativo, antes da "Urna pronta", e agora se confirma em praticamente todas as urnas do 2º turno. "O voto do eleitor NÃO foi registrado" é a mensagem da urna que trava com o eleitor na cabine: o voto daquele eleitor não entra e a urna é reiniciada.

## 1º x 2º turno e teste de swing

Base: 499.115 seções com pelo menos 20 votos nos dois turnos, 5.687 municípios. Swing médio: +2,903 pontos para o 13.

| Indicador (variação do 1º para o 2º turno) | Coeficiente | Erro padrão | p | Leitura |
|---|---:|---:|---:|---|
| Fatia de votos sem biometria | -0,000229 | 0,001570 | 0,88 | sem relação: 10 pontos a mais de votos sem biometria mudam o swing em -0,002 ponto |
| Fatia de votos em sequência rápida | -0,042257 | 0,018966 | 0,026 | 1 ponto a mais de votos em sequência rápida, swing 0,04 ponto menor para o 13 |
| Fatia de votos sem biometria em sequência rápida | -0,325629 | 0,212587 | 0,13 | sem relação (só 8 seções com valor diferente de zero) |
| Fatia sem biometria na última hora e depois das 17h | -0,012658 | 0,007293 | 0,083 | sem relação |
| 1% de seções com maior aumento sem biometria (4.992 seções, aumento de 5,8 pontos ou mais) | -0,001778 | 0,000364 | 0,000001 | swing 0,18 ponto **menor** para o 13 que nas outras seções do município |
| Seções com alguma sequência rápida no 2º turno (3.689) | -0,000798 | 0,000453 | 0,078 | sem relação |

Coeficientes em fração (0,01 = 1 ponto). A regressão conjunta dos quatro indicadores dá os mesmos sinais e tamanhos (`resumo.json`, `pareamento.regressoes.conjunto`).

Swing por decil da variação da fatia sem biometria (diferença para a média do próprio município):

| Decil | Variação média da fatia sem biometria | Swing médio | Swing menos a média do município |
|---|---:|---:|---:|
| 1 | -3,98 pontos | +2,715 | -0,061 |
| 2 | -1,99 | +2,922 | -0,005 |
| 3 | -1,20 | +2,977 | +0,018 |
| 4 | -0,61 | +3,007 | +0,039 |
| 5 | -0,10 | +2,952 | +0,021 |
| 6 | +0,39 | +3,004 | +0,034 |
| 7 | +0,90 | +2,957 | +0,007 |
| 8 | +1,50 | +2,941 | +0,007 |
| 9 | +2,29 | +2,887 | +0,010 |
| 10 | +4,18 | +2,666 | -0,072 |

Os dois extremos (seções que perderam ou ganharam mais votos sem biometria) têm swing um pouco menor que o resto do município; no meio, nada. É o padrão de seção com leitor biométrico com problema num turno e não no outro, e não favorece nenhum dos dois candidatos.

**Escala.** Para pesar a pergunta "mesário votando por ausentes": o 1% de seções com maior aumento de votos sem biometria tem cerca de 1,3 milhão de votos; o efeito medido (0,18 ponto contra o 13 na fatia entre 13 e 22) equivale a cerca de 4.400 votos na diferença entre os dois, no sentido do 22, e a diferença final foi de 4.430.191. Sequências rápidas só de votos sem biometria, que seriam o rastro mais direto de alguém votando em série no lugar de outros, somam 6 votos no Brasil no 2º turno.

## Seções para conferência

Lista completa, com os números dos dois lados, em `data/parquet/2026/pacote_nacional/secoes_conferencia.csv` (coluna `lista`). Além das 9 e 16 seções dos destaques:

**Maior aumento de votos sem biometria (2º turno contra 1º).** São seções em que quase todos os eleitores foram habilitados manualmente **depois de tentar a digital**, o padrão de leitor que não reconhece. Exemplo: BA 34290/0127/0336, com 243 habilitações biográficas, 34 sem digital e só 4 biométricas em 281 votos; swing +0,9 ponto.

| Seção | Fatia sem biometria 1º | 2º | Swing (pontos) | Votos 2º |
|---|---:|---:|---:|---:|
| BA 34290/0127/0336 | 17,0% | 98,6% | +0,9 | 281 |
| SP 70750/0174/0447 | 17,5% | 95,9% | -1,1 | 218 |
| RJ 58637/0221/0178 | 17,6% | 94,9% | +4,8 | 216 |
| GO 96539/0110/0116 | 13,7% | 90,5% | +3,2 | 178 |
| BA 34290/0127/0335 | 22,1% | 97,8% | +2,3 | 314 |
| RS 89770/0088/0113 | 22,6% | 97,6% | +2,5 | 294 |
| RJ 60011/0188/0082 | 25,6% | 96,3% | +5,4 | 269 |
| RJ 60011/0008/0074 | 33,7% | 99,0% | +5,2 | 300 |

**Sequências rápidas só de votos sem biometria.** No Brasil, PE 24570/0147/0393 (2º turno, 6 votos; a seção tem 41% de votos sem biometria nos dois turnos e swing +2,0). No exterior: ZZ 29661/0001/3315 (4 sequências no 2º e 1 no 1º turno), ZZ 30155/0001/0699 (3), ZZ 30481/0001/0404, ZZ 39063/0001/3194, ZZ 39063/0001/3244, ZZ 99490/0001/3329, ZZ 29432/0001/3212 e ZZ 30341/0001/1876 (1º turno).

**Mais votos sem biometria depois das 17h (2º turno).** ZZ 29955/0001/3785 (33), 3705 (28) e 3649 (26), no horário local do país; no Brasil, MA 08060/0106/0163 (10), RS 85316/0142/0263 (7), BA 38490/0004/0579, BA 39314/0197/0050, MG 51918/0248/0032 e PI 11290/0028/0127 (5 cada).

**Maior swing em valor absoluto**, sem marca no log: AC 01139/0007/0067 (+41,6 pontos, 73 votos), AM 02097/0018/0037 (+36,4), AC 01554/0003/0160 (-35,5), AM 02399/0045/0063 (+29,9), AC 01031/0003/0095 (+29,5). Todas têm fatia sem biometria estável entre os turnos e nenhuma sequência rápida sem biometria.

## Resposta à pergunta

1. A imagem impressa e o BU digital trazem os mesmos votos em todas as seções dos dois turnos. A única diferença é o número da urna em 9 seções de contingência, explicada pela recuperação dos dados por outra urna.
2. O log fecha com o BU em 499.167 seções do 1º turno e 499.171 do 2º. As 16 exceções são falhas de composição do log no pacote: log da urna substituída ausente, trecho perdido antes de um reinício, ou log de outra seção incluído. Nenhuma tem voto a mais no BU sem explicação: o RDV de todas as seções já conferiu com o BU.
3. Não há rastro de mesário votando em série no lugar de ausentes. Não existe voto da mesma urna a menos de 10 s do anterior. Sequências rápidas só sem biometria: uma no Brasil (6 votos). A variação do voto sem biometria entre os turnos não favorece nenhum candidato; no extremo, os números apontam levemente contra o 13. O volume compatível com qualquer hipótese de fraude por esse caminho fica na casa de milhares de votos, contra uma diferença de 4,43 milhões.

## Limitações

- O log mostra a habilitação e o voto computado, não quem estava na cabine. Habilitação manual com digital do mesário é um procedimento previsto; o que se mede aqui é se ela aparece em padrão e escala anormais.
- "Sem biometria" junta o eleitor sem biometria cadastrada (liberado pelo título ou documento) e o que tinha biometria e foi habilitado por dado pessoal depois de a digital falhar. Os dois são contados separadamente nas colunas `log_votos_sem_digital` e `log_votos_biog` dos arquivos por seção.
- O limite de 30 s e o mínimo de 5 votos para sequência rápida são escolhas; os intervalos abaixo de 10 s (zero) não dependem delas.
- O teste de swing compara seções do mesmo município; não controla outras diferenças entre seções vizinhas (local de votação, perfil do eleitor). Vários testes foram feitos; os dois coeficientes com p abaixo de 0,05 têm sinal contrário ao 13 e tamanho de centésimos de ponto.
- Três arquivos foram republicados pelo TSE durante a leitura (MA 1º turno, MG 1º turno, SP 2º turno). As diferenças encontradas estão nos destaques; para o MA 1º turno, o que mudou não é visível no diretório do zip e não foi possível conferir sem baixar o arquivo de novo.
- No exterior o BU não tem as contagens de habilitação e todos os votos são sem biometria; por isso os números sem o exterior aparecem separados.

## Como reproduzir

No servidor de análise (o Mac só orquestra):

```sh
cd ~/dataurnas-ch/app
# 1) baixa cada zip para a memória (/dev/shm), processa e apaga; pula UF e turno já feitos.
#    Duas execuções em paralelo somando 4 conexões: SP e RJ com 3, as demais com 1,
#    estas na ordem da velocidade medida no CDN (as que estão em cache primeiro).
uv run python scripts/ele2026/pacote_nacional.py processar --ufs SP,RJ --workers 44 --paralelo 3 --downloads 3
uv run python scripts/ele2026/pacote_nacional.py processar \
    --ufs AL,AM,AP,BA,CE,DF,ES,GO,MA,MS,MT,PA,PB,PE,PI,PR,RN,RO,RR,RS,SC,SE,TO,ZZ \
    --workers 44 --paralelo 2 --downloads 1 --por-velocidade
# (AC foi feito antes, sozinho, como teste de ponta a ponta)
# 2) seções do Sistema de Apuração (busa x imgbusa), por HTTP Range
uv run python scripts/ele2026/pacote_nacional.py sa
# 3) resumo nacional, pareamento 1º x 2º e teste de swing
uv run python scripts/ele2026/pacote_nacional.py relatorio --repo ~/dataurnas-pacote-nacional/resumo_repo
```

Testes: `pytest -q tests/test_imgbu_parser.py tests/ele2026/test_pacote_nacional.py`.

## Arquivos

| Arquivo | Conteúdo |
|---|---|
| `scripts/ele2026/pacote_nacional.py` | download, leitura por seção (A e B), Sistema de Apuração e relatório |
| `src/dataurnas/parsers/imgbu.py` | parser da imagem do BU (`-imgbu.dat`, `-imgbusa.dat`) |
| `tests/test_imgbu_parser.py`, `tests/ele2026/test_pacote_nacional.py` | testes do parser, das classes de habilitação, das sequências rápidas e da comparação A |
| `data/parquet/2026/pacote_nacional/resumo.json` | todos os números deste relatório |
| `data/parquet/2026/pacote_nacional/tabelas.md` | tabela por UF e turno e decis do swing |
| `data/parquet/2026/pacote_nacional/por_uf.csv` | votos, votos sem biometria, sequências rápidas e divergências por UF e turno |
| `data/parquet/2026/pacote_nacional/secoes_conferencia.csv` | seções divergentes, sem arquivo e extremas, com os números dos dois lados |
| `data/parquet/2026/pacote_nacional/eventos_nao_info.csv` | mensagens de nível ERRO, ALERTA e outros, com ocorrências e seções, por turno |
| servidor de análise, `~/dataurnas-pacote-nacional/` | `secoes_<uf>_<turno>.parquet` (uma linha por seção, 100 MB no total), `eventos_<uf>_<turno>.parquet`, `sa_secoes.parquet`, `pareamento_t1_t2.parquet`, `cd_republicados.parquet` e os logs de progresso |
