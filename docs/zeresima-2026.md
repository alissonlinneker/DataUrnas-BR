# Zerésima em todos os logs de urna, 1º e 2º turnos de 2026

> **Resultado:** em todas as seções com log no pacote oficial (499.176 no 1º turno e 499.178 no 2º), a zerésima foi gerada antes do primeiro voto. Nenhum voto foi registrado antes da zerésima, nenhuma zerésima veio depois de "Urna pronta para receber votos" da mesma urna e nenhuma traz data fora dos dias de votação. Só uma seção por turno não tem zerésima no log publicado: SP 71072/0002/0035 (1º turno) e MA 08893/0047/0609 (2º turno). Nas duas, o pacote não traz o log da urna que abriu a votação, falha que já estava documentada em [pacote-nacional-imgbu-logs-2026.md](pacote-nacional-imgbu-logs-2026.md). O que falta é registro, não voto. Nada do que foi encontrado muda votos, assinaturas ou hashes.

## O que foi verificado

A zerésima é o relatório que a urna imprime antes da abertura para mostrar que não há voto gravado. O aplicativo VOTA registra a geração e a impressão no log da urna (`-log.jez`). Para cada seção e turno foram extraídos do log:

- a geração da zerésima, com hora e urna;
- a hora de "Urna pronta para receber votos";
- a hora do primeiro voto ("O voto do eleitor foi computado").

Com isso foram procurados:

- seção sem zerésima;
- zerésima depois do primeiro voto ou depois da abertura;
- zerésima com data errada;
- mais de uma zerésima, e se havia voto antes da segunda;
- voto antes da zerésima.

Só contam as linhas com a data do turno (04/10/2026 ou 25/10/2026). O log do 2º turno acumula os eventos do 1º, e esses eventos ficam fora das contas do 2º turno. As horas são as do relógio da urna. A hora de Brasília é a hora local menos o fuso do município (`analyzer/timezones.get_tz_offset`: AC UTC-5, AM, MT, MS, RO e RR UTC-4, municípios do AM em UTC-5, Fernando de Noronha UTC-2). No exterior (ZZ) fica a hora local do país.

## Textos do log

Os textos abaixo foram tirados de uma amostra de logs do AC antes da leitura nacional. Depois disso, a leitura completa contou **toda** linha que contém "zerésima", sem filtro prévio. O catálogo inteiro tem 38 formas, e todas estão listadas em `data/parquet/2026/zeresima/catalogo_mensagens.csv`. Os números abaixo valem para o dia do turno. O "N" indica onde o log traz um número que varia.

| Aplicativo | Texto | 1º turno: ocorrências (seções) | 2º turno: ocorrências (seções) |
|---|---|---:|---:|
| VOTA | `Aguardando data e hora para emissão da zerésima` | 25.337 (22.126) | 24.786 (21.985) |
| VOTA | `Aguardando confirmação para emissão da zerésima` | 502.004 (499.175) | 501.508 (499.177) |
| VOTA | `Gerando relatório [ZERÉSIMA] [INÍCIO]` | 499.560 (499.175) | 499.475 (499.177) |
| VOTA | `Gerando relatório [ZERÉSIMA] [TÉRMINO]` | 499.558 (499.175) | 499.473 (499.177) |
| VOTA | `Gerando relatório [RESUMO DA ZERÉSIMA] [INÍCIO]` | 499.557 (499.175) | 499.473 (499.177) |
| VOTA | `Imprimindo relatório [ZERÉSIMA] via nº [N]` | 504.173 (499.175) | 502.619 (499.177) |
| VOTA | `Imprimindo relatório [RESUMO DA ZERÉSIMA] via nº [N]` | 505.515 (499.175) | 503.151 (499.177) |
| VOTA | `Mesário indagado se quer imprimir a zerésima` | 12.858 (11.308) | 6.669 (5.835) |
| GAP | `GAP erro N \| Validação do ADH \| Aplicativo de Ajuste de Data e Hora não pode ser executado após a impressão da zerésima. Desligue a urna.` | 23 (14) | 10 (6) |

Fora do dia do turno aparecem só três tipos de linha:

- `Aguardando data e hora para emissão da zerésima`, que a urna escreve sempre que é ligada antes da hora liberada (carga, testes e véspera). Foram 1.117.338 linhas em 496.162 logs do 1º turno.
- A recusa de contingência `A contingência não pode ser feita. A mídia de votação é de seção com zerésima gerada, e o horário desta urna é anterior a N:N do dia da eleição`, com 3 linhas em 1 log de cada turno.
- `Imprimindo relatório [ZERÉSIMA DE APURAÇÃO]` do Sistema de Apuração (aplicativo SA) nos logs do 2º turno: em 6 logs com a data do 1º turno e em 1 log com outra data.

A geração da zerésima pelo VOTA (`Gerando relatório [ZERÉSIMA] [INÍCIO]`) **nunca** aparece com data diferente dos dois dias de votação.

A zerésima é sempre seguida do resumo da zerésima. As duas linhas de `[INÍCIO]` sem `[TÉRMINO]` em cada turno são gerações interrompidas por erro e repetidas em seguida (caso SC 82597/0055/0005 abaixo).

## Números nacionais

| | 1º turno | 2º turno |
|---|---:|---:|
| Logs (`-log.jez`) no pacote | 499.176 | 499.178 |
| Logs ilegíveis | 0 | 0 |
| Seções com voto no log | 499.176 | 499.178 |
| Seções com exatamente 1 zerésima no dia | 498.792 | 498.879 |
| Seções com 2 zerésimas | 381 | 298 |
| Seções com 3 zerésimas | 2 | 0 |
| **Seções sem zerésima no dia** | **1** | **1** |
| Zerésima depois do primeiro voto (mesma urna, ordem do log) | 0 | 0 |
| Zerésima depois do primeiro voto (pela hora, qualquer urna da seção) | 0 | 1 (diferença de relógio, ver abaixo) |
| Zerésima depois de "Urna pronta" (mesma urna) | 0 | 0 |
| Zerésima depois de "Inicio do Encerramento" (mesma urna) | 0 | 0 |
| Votos antes da primeira zerésima da seção | 0 | 0 |
| Seções com zerésima posterior e voto antes dela | 0 | 0 |
| Zerésima com data fora dos dias de votação | 0 | 0 |
| Zerésima antes das 7h de Brasília | 0 | 0 |
| Seções sem zerésima nos dois turnos | 0 | 0 |

As seções do pacote são 499.207 por turno. Nas que não têm `-log.jez` (31 no 1º turno e 29 no 2º) não há log a examinar. O número é o mesmo das seções do Sistema de Apuração em cada turno ([pacote-nacional-imgbu-logs-2026.md](pacote-nacional-imgbu-logs-2026.md)).

### Horário

O software libera a zerésima às 7h de Brasília. A primeira `Aguardando confirmação para emissão da zerésima` do dia sai às 07:00:00 de Brasília nos dois turnos, e nenhuma é anterior. Antes disso, a urna só escreve `Aguardando data e hora` (22.126 seções no 1º turno ligaram a urna antes da liberação). A zerésima mais cedo foi às 07:00:00 de Brasília.

| Hora da primeira zerésima (Brasília, sem ZZ) | 1º turno | 2º turno |
|---|---|---|
| Mínimo | 07:00:00 | 07:00:00 |
| Percentil 1% | 07:00:34 | 07:00:29 |
| Mediana | 07:27:00 | 07:25:49 |
| Percentil 99% | 08:01:20 | 07:59:34 |
| Máximo | 12:48:12 | 13:03:50 |
| Seções com zerésima às 8h ou depois | 6.656 | 4.573 |
| às 9h ou depois | 73 | 38 |
| às 10h ou depois | 7 | 12 |

Da zerésima até "Urna pronta para receber votos" passam 33,2 minutos na mediana no 1º turno e 34,3 no 2º. O máximo é de 215,9 e 206,8 minutos. A zerésima depois das 8h acompanha uma abertura tardia, porque a urna só abre depois dela. O caso mais extremo é MG 46477/0134/0295, uma seção com 9 votos nos dois turnos: zerésima às 12:48:12 no 1º turno e às 13:03:50 no 2º, com o primeiro voto 9 e 6 minutos depois. No exterior a primeira zerésima foi entre 07:00:02 e 09:14:31 (1º turno) e entre 07:00:02 e 08:50:06 (2º), na hora local.

### Troca de urna

Seções com mais de uma urna no dia: 2.500 no 1º turno e 1.723 no 2º. A urna de contingência recebe a mídia de votação da urna substituída e continua a votação sem nova zerésima. Por isso há 2.153 urnas (2.120 seções) no 1º turno e 1.456 urnas (1.429 seções) no 2º com votos e sem zerésima própria.

Em todas elas, exceto as duas seções da próxima seção deste documento, outra urna da mesma seção gerou a zerésima antes do primeiro voto. A própria urna se recusa a fazer contingência antes da hora quando a mídia é de seção com zerésima gerada (o texto `A contingência não pode ser feita...` acima). Ela também recusa o ajuste de data e hora depois da zerésima (`GAP erro N | Validação do ADH`, 14 seções no 1º turno e 6 no 2º).

### Mais de uma zerésima

- **1º turno: 383 seções.**
  - 379 com duas ou três urnas diferentes. A urna foi trocada antes de receber votos, e a urna nova gerou a própria zerésima.
  - 4 com duas zerésimas na mesma urna: MA 08915/0018/0089, PI 11070/0041/0181, PE 24171/0028/0162 e SP 71072/0260/0326 (esta com 3 zerésimas em 2 urnas).
- **2º turno: 298 seções.**
  - 296 com urnas diferentes.
  - 2 na mesma urna: SC 82597/0055/0005 e RJ 58041/0154/0236.

Em **nenhuma** das 681 havia voto antes da segunda ou da terceira zerésima, nem pela ordem do log nem pela hora.

Exemplo de repetição na mesma urna, SC 82597/0055/0005 (2º turno, urna 01829335):

1. Às 07:19:33 a primeira geração falha com `Erro inesperado (7043) | O arquivo de destino [/dsk/fe/dinamico/trab2/ze.dat] não pôde ser criado`.
2. A urna é desligada e acusa falta de mídia de votação.
3. Das 08:18 às 08:21 é feita contingência de mídia de votação.
4. A zerésima é gerada e impressa às 08:23:06.
5. A urna abre às 08:26:33 e o primeiro voto é às 08:27:13.

## Casos individuais

### Seções sem zerésima no log publicado

| Turno | Seção | Votos no log | Comparecimento no BU | Urna no log | Abertura no log | Primeiro voto |
|---|---|---:|---:|---|---|---|
| 1º | SP 71072/0002/0035 | 232 | 247 | contingência 02253783 | 10:58:42 | 11:07:16 |
| 2º | MA 08893/0047/0609 | 188 | 224 | contingência 01664037 | 10:57:19 | 10:58:52 |

**SP 71072/0002/0035 (1º turno):**

- A urna 02254720 liga às 10:17. Às 10:19:32 ela acusa `GAP erro 72 | Validação do VOTA | Dados contidos na mídia de votação não correspondem aos dados contidos na urna` e é desligada às 10:52, sem voto e sem zerésima.
- A urna de contingência 02253783 copia o log da mídia externa às 10:55:01. Ela executa a contingência e abre às 10:58:42 sem zerésima, como toda urna de contingência.
- O BU tem 15 votos a mais que o log. Esses votos foram dados de manhã numa terceira urna, a dona da mídia de votação 9F62BC72, e o log dela não está no pacote ([investigacao-log-bu-2026.md](investigacao-log-bu-2026.md), seção D.2).
- A zerésima da seção, se houve, estaria nesse log ausente.

**MA 08893/0047/0609 (2º turno):**

- A urna 01813459 acusa o mesmo `GAP erro 72` às 10:29 e às 10:35.
- A urna de contingência 01664037 executa a contingência às 10:51 e abre às 10:57:19 sem zerésima.
- O log aninhado é da urna de outra seção (0445), e falta o log da urna original da 0609. O BU tem 36 votos a mais que o log ([pacote-nacional-imgbu-logs-2026.md](pacote-nacional-imgbu-logs-2026.md)).
- No 1º turno a mesma seção teve zerésima normal. O log do 2º turno traz a zerésima de 04/10/2026.

Nas duas seções a urna de contingência continuou uma mídia de votação que já tinha votos (BU maior que o log). Isso é coerente com uma zerésima feita de manhã na urna cujo log falta, mas **não dá para confirmar com os arquivos publicados**. Para fechar estes dois casos é preciso pedir ao TSE o log da urna que abriu a votação em cada seção. O pedido de SP 71072/0002/0035 já consta em [relatorio-tse-ocorrencias-2026.md](relatorio-tse-ocorrencias-2026.md).

### Zerésima depois do primeiro voto pela hora: SP 71374/0172/0098 (2º turno)

O log tem duas urnas:

- **Urna de contingência 02325050:**
  - Às 08:21:59 inicia a contingência e copia o log da mídia externa (`023250502510202608221401ME.jez`, marcado como corrompido) às 08:22:14.
  - Gera a zerésima às 08:26:50, abre às 08:27:58 e recebe o primeiro voto às 08:31:20.
- **Urna substituída 02078355**, cujo log foi copiado:
  - Gera zerésima às 08:32:34 e abre às 08:35:04, sem receber voto.
  - É desligada às 08:38:35 e às 08:55:38.

O log da 02078355 foi copiado às 08:22:14 pelo relógio da 02325050, mas a última linha dele está marcada 08:55:38. Logo, o relógio da 02078355 estava pelo menos 33 minutos adiantado em relação ao da 02325050. Pela ordem real dos fatos, a zerésima da 02078355 veio antes da contingência e antes de qualquer voto. Pela ordem do log e por urna, nenhuma zerésima desta seção vem depois de voto. É diferença de relógio entre urnas, não voto antes da zerésima.

## Comparação com a amostra anterior

Na amostra de 6.732 logs (3.729 seções) de [hash-software-urna-2026.md](hash-software-urna-2026.md), o resumo da zerésima aparecia em 6.731 logs. A leitura nacional confirma o padrão: só 1 log por turno, entre 499 mil, fica sem zerésima, e os dois casos são pacotes em que falta o log da urna que abriu a votação. A amostra não guarda a lista de seções, por isso não dá para dizer se o log sem zerésima dela é o de SP 71072/0002/0035.

Os dois turnos têm o mesmo comportamento: liberação às 7h de Brasília, mediana da zerésima perto de 07:26 e nenhum voto antes da zerésima. O 2º turno teve menos zerésimas repetidas (298 contra 383 seções) e menos zerésimas depois das 8h (4.573 contra 6.656).

O log do 2º turno também traz a zerésima do 1º turno (data 04/10/2026) em 497.590 seções. As demais tiveram urna trocada entre os turnos.

## Conferência cruzada

Os mesmos logs já tinham sido lidos por `scripts/ele2026/pacote_nacional.py` (`~/dataurnas-pacote-nacional/secoes_<uf>_<turno>.parquet`). O conjunto de seções com log é idêntico: 499.176 e 499.178, sem seção a mais ou a menos dos dois lados. A hora de "Urna pronta", a hora do primeiro voto e o número de votos do log coincidem nas 998.354 seções x turno. São 0 diferenças nas três colunas.

## Método e reprodução

Script: `scripts/ele2026/zeresima.py`.

1. `volume` lê só o diretório central dos 56 zips por HTTP Range.
2. `processar` baixa por HTTP Range apenas os trechos que contêm os `-log.jez`. Membros vizinhos vêm numa única requisição de até 8 MB, junto com os arquivos pequenos entre eles. No máximo 4 conexões ficam abertas ao mesmo tempo. Cada membro é conferido pelo CRC-32 do diretório central.
3. Os logs são abertos com `analyzer/rdv_recontagem.texto_log`, que inclui os logs aninhados das urnas substituídas e descarta linhas repetidas.
4. `relatorio` gera os resumos.

Volume:

| | Bytes |
|---|---:|
| Pacote completo (56 zips, 4.992.203 membros) | 219.202.414.224 |
| Só os 998.354 `-log.jez` | 143.792.831.238 |
| Lido de fato (25.651 requisições) | 211.932.150.672 |

Ler membro por membro baixaria menos bytes, mas exigiria cerca de 1 milhão de requisições. A leitura em blocos levou 40 minutos no servidor de análise, a cerca de 90 MB/s somando as 4 conexões, com o CDN do TSE já em cache.

```sh
uv run python scripts/ele2026/zeresima.py volume --saida ~/dataurnas-zeresima
uv run python scripts/ele2026/zeresima.py processar --saida ~/dataurnas-zeresima
uv run python scripts/ele2026/zeresima.py relatorio --saida ~/dataurnas-zeresima \
    --pacote ~/dataurnas-pacote-nacional --repo data/parquet/2026/zeresima
```

Saídas em `data/parquet/2026/zeresima/`:

- `resumo.json`: todos os números deste documento.
- `anomalias.csv`: uma linha por seção e tipo de achado, com horas, contagens e nome do membro.
- `catalogo_mensagens.csv`: todas as formas de mensagem com "zerésima", por turno e por classe de data.
- `volume.json`: tamanhos por zip.

## Limites

- O log registra que a zerésima foi gerada e impressa, não o conteúdo dela. O relatório impresso fica na seção e não é publicado. O que se confere aqui é a ordem dos eventos, não os zeros impressos.
- As horas são as do relógio de cada urna. A comparação entre urnas de uma mesma seção depende de os relógios estarem acertados (ver SP 71374/0172/0098). A checagem por urna, pela ordem do log, não depende disso.
- Seção sem log no pacote não pode ser examinada. Nas duas seções sem zerésima, o que falta é o log da urna que abriu a votação.
