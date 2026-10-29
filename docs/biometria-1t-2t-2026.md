# Biometria por seção: 1º turno (04/10/2026) comparado com o 2º turno (25/10/2026)

Pergunta: o que os arquivos públicos da urna dizem sobre biometria, e como o uso da biometria mudou de um turno para o outro em cada seção?

Duas fontes, as duas públicas e baixadas do TSE:

1. **Boletim de Urna (BU)**, todas as seções do país. O BU traz três contagens de habilitação do eleitor (seção 1).
2. **Log da urna** (`logd.dat` dentro do `-log.jez`), numa amostra de 2.997 seções com o log dos dois turnos de cada uma (5.994 arquivos). O log registra, eleitor por eleitor, cada pedido de digital, cada falha de reconhecimento e cada habilitação manual (seção 2).

| Arquivo | Para quê |
|---|---|
| `scripts/ele2026/biometria_t1_t2_ch.sql` | exporta do ClickHouse as seções do 2º turno (`v_bu_ultima`) com o 1º turno da mesma seção ao lado (`ref_secoes_2026_t1`), com os campos de biometria do BU |
| `scripts/ele2026/biometria_t1_t2.py` | análise do BU, escolha da amostra, download dos logs, leitura dos eventos do log e todas as tabelas deste relatório |
| `data/parquet/2026/t2/biometria/` (fora do git) | `secoes_biometria.parquet`, `amostra.parquet`, `logs_secoes.parquet`, `logs_vocabulario.csv`, `extremos.csv`, `tab_*.parquet`, `resumo.json`, `tabelas.md` |

Os logs brutos da amostra ficam no servidor de análise, em `~/dataurnas-t2/biometria/brutos/t1/` e `t2/` (826 MB). Todo número abaixo sai de `resumo.json`, `tabelas.md`, `logs_vocabulario.csv` ou `extremos.csv`.

Reprodução (no servidor de análise):

```sh
# 1. BU pareado (ClickHouse) e votos/marcas das viradas
mkdir -p /dev/shm/bio_in /dev/shm/bio_out
ch.sh < scripts/ele2026/biometria_t1_t2_ch.sql > /dev/shm/bio_in/secoes_biometria.parquet
cp data/parquet/2026/t2/viradas/secoes_2026.parquet /dev/shm/bio_in/viradas_secoes_2026.parquet

# 2. análise; com --baixar-logs baixa os -log.jez que faltam (3 req/s, um processo)
python3 scripts/ele2026/biometria_t1_t2.py \
  --bu /dev/shm/bio_in/secoes_biometria.parquet \
  --viradas /dev/shm/bio_in/viradas_secoes_2026.parquet \
  --saida /dev/shm/bio_out --brutos ~/dataurnas-t2/biometria/brutos [--baixar-logs]
```

A amostra é fixa: depois de criado, `amostra.parquet` é reaproveitado. O download de 25 a 27/10/2026 baixou 5.994 logs (852.691.887 bytes) sem nenhum 404, 429 ou falha.

## Resumo

| Item | 1º turno | 2º turno | Variação |
|---|---|---|---|
| Seções com detalhamento de biometria no BU (Brasil) | 497.895 | 497.897 | |
| Comparecimento nessas seções | 124.933.510 | 127.854.631 | +2.921.121 |
| Compareceram **sem biometria cadastrada** | 6.940.334 (5,555%) | 7.251.810 (5,672%) | +0,117 ponto |
| Habilitados **por biometria** | 109.650.927 (87,767%) | 111.970.333 (87,576%) | -0,191 ponto |
| Habilitados **por ano de nascimento**, tendo biometria cadastrada | 8.342.249 (6,677%) | 8.632.488 (6,752%) | +0,074 ponto |
| Entre quem tinha biometria cadastrada, parcela habilitada por ano de nascimento | 7,070% | 7,158% | +0,088 ponto |
| Seções com 100% sem biometria (comparecimento de 20 ou mais) | 0 | 0 | |
| Seções em que mais da metade dos cadastrados foi habilitada por ano de nascimento | 153 | 106 | -47 |

1. **Sim, o log fala de biometria, e muito.** Cada eleitor gera uma sequência de eventos da aplicação VOTA: "Solicita digital. Tentativa [N] de [4]", "Capturada a digital", "Número de tentativas de reconhecimento do dedo" (a digital não bateu), "Timeout de reconhecimento do dedo", "Tipo de habilitação do eleitor [biométrica]" e, quando a digital falha nas quatro tentativas, "Solicitação de dado pessoal do eleitor para habilitação manual", "Ano de nascimento digitado é igual ao do cadastro" e "Mesário N habilitou o eleitor". A lista completa está na seção 2.
2. **O log fecha com o BU.** Nas 5.994 leituras, os votos computados no log são iguais ao comparecimento do BU em 100% das seções, e as três formas de habilitação contadas no log batem com os três campos do BU em 93% a 99,9% das seções; as diferenças vêm de eleitor suspenso e habilitado de novo, que o log conta duas vezes e o BU uma (seção 3).
3. **No país, quase nada mudou entre os turnos.** A parcela sem biometria cadastrada subiu 0,12 ponto e a parcela habilitada por ano de nascimento subiu 0,07 ponto. Na amostra aleatória do log, os pedidos de digital por eleitor ficaram em 1,48 nos dois turnos e as falhas de reconhecimento por eleitor em 0,58.
4. **Os extremos são de urna, não de voto.** Das 140 seções em que a parcela habilitada por ano de nascimento mudou 30 pontos ou mais entre os turnos, 116 usaram urna **UE2013** e 21 a UE2015. A UE2013 é 2,2% das seções pareadas e responde por 130 das 153 seções do 1º turno em que a maioria dos cadastrados foi habilitada por ano de nascimento (119 por 10 mil urnas desse modelo, contra 0,05 por 10 mil nas UE2020 e UE2022). Nessas seções o log mostra 1,62 falha de reconhecimento por eleitor, quase o triplo da amostra aleatória. O padrão é compatível com leitor de digitais que não reconhece, e não com mudança do eleitorado.
5. **Sem relação com o voto, com as seções tardias ou com as 968 seções atípicas de viradas.** A correlação entre a variação da parcela habilitada por ano de nascimento e a variação da fatia do 13 é -0,0085 no país e -0,0009 dentro de cada município (p = 0,51). As 968 seções atípicas têm 13 seções com variação de 10 pontos ou mais; o esperado só pelo tamanho delas é 13,6. As 7.581 seções tardias têm 13, contra 9,6 esperadas.

## 1. Os campos de biometria do BU

O BU de 2026 segue a spec v2 (`spec/v2/bu.asn1`). Dentro de `EntidadeResultadoUrna` há o campo opcional `detalhamentoComparecimento`, do tipo:

```asn1
-- Detalhamento do comparecimento de eleitores levando em consideração a forma de habilitação.
DetalhamentoComparecimento ::= SEQUENCE {
    qtdEleitoresCompareceramSemBiometria    QtdEleitores, -- ... compareceram e que não tinham biometria cadastrada.
    qtdEleitoresHabilitadosPorBiometria     QtdEleitores, -- ... foram habilitados com reconhecimento biométrico.
    qtdEleitoresHabilitadosPorBiografia     QtdEleitores  -- ... compareceram, que tinham biometria cadastrada e que foram habilitados por ano de nascimento.
}
```

| Campo no projeto | Campo do BU | O que conta | O que **não** é |
|---|---|---|---|
| `comp_sem_biometria` | `qtdEleitoresCompareceramSemBiometria` | eleitores que votaram e **não tinham digital no cadastro** da Justiça Eleitoral; a urna não pede digital a eles | não é "liberado sem biometria por falha"; é falta de cadastro biométrico, uma característica do eleitorado da seção |
| `habilitados_biometria` | `qtdEleitoresHabilitadosPorBiometria` | eleitores cuja digital foi reconhecida pela urna | |
| `habilitados_biografia` | `qtdEleitoresHabilitadosPorBiografia` | eleitores **com** digital cadastrada que a urna não reconheceu e que foram habilitados à mão, pela conferência do ano de nascimento e pela digital do mesário | é o indicador de falha da biometria |
| `comparecimento_bu` | `qtdEleitoresCompareceram` | eleitores que votaram | |

Nos dois turnos, em todas as seções com detalhamento, as três contagens somam exatamente o comparecimento do BU (0 seções inconsistentes no 1º e no 2º turno). Por isso as taxas deste relatório usam o comparecimento do BU:

- **taxa sem biometria** = `comp_sem_biometria / comparecimento`;
- **taxa de habilitação biométrica** = `habilitados_biometria / comparecimento`;
- **taxa de biografia entre cadastrados** = `habilitados_biografia / (habilitados_biometria + habilitados_biografia)`: entre quem a urna deveria reconhecer, quantos acabaram habilitados à mão.

A spec v1 (2022) tinha outros dois campos, `qtdEleitoresLibCodigo` (habilitados manualmente) e `qtdEleitoresCompBiometrico`, que não separam o eleitor sem cadastro do eleitor com cadastro não reconhecido. O parser (`parsers/bu.py`) mapeia o primeiro para `habilitados_biografia` e o segundo para `habilitados_biometria` quando lê um BU v2.

Cobertura: no Brasil, 497.897 seções têm detalhamento no 2º turno e 497.895 no 1º (2 seções do 1º turno vieram sem o campo). **As 1.310 seções do exterior (UF ZZ; 1.281 com BU de urna e 29 do Sistema de Apuração) não trazem o detalhamento em nenhum dos dois turnos** e ficam fora das tabelas.

## 2. Os eventos de biometria no log

O `-log.jez` é um ZIP com o `logd.dat`, texto em latin-1 com seis colunas separadas por tabulação: data e hora, nível, número da urna, aplicação, mensagem e hash da linha. Os eventos do eleitor são da aplicação `VOTA`. **O log do 2º turno traz também os eventos do 1º** (a urna acumula o log desde a carga); por isso só entram as linhas com a data do turno (04/10/2026 ou 25/10/2026). Na troca de urna, o pacote traz o log da urna substituída como ZIP aninhado e os dois são lidos (`parsers/log.py`, `textos_zip`).

### A sequência de um eleitor

Trecho literal de um log do 1º turno (seção AC, 01120, zona 0008, seção 0008), primeiro com reconhecimento na 2ª tentativa e depois com habilitação manual:

```text
04/10/2026 06:45:38  Identificador do eleitor digitado pelo mesário
04/10/2026 06:45:38  Identificador digitado pelo mesário foi: (Título de eleitor)
04/10/2026 06:45:38  Foto do eleitor apresentada
04/10/2026 06:45:46  Solicita digital. Tentativa [1] de [4]
04/10/2026 06:45:49  Capturada a digital. Tentativa [1] de [4]
04/10/2026 06:45:51  Número de tentativas de reconhecimento do dedo. Tentativa [1] de [4]
04/10/2026 06:45:53  Solicita digital. Tentativa [2] de [4]
04/10/2026 06:45:56  Capturada a digital. Tentativa [2] de [4]
04/10/2026 06:46:03  Tipo de habilitação do eleitor [biométrica]
04/10/2026 06:46:03  Eleitor foi habilitado
...
04/10/2026 06:47:33  Identificador do eleitor digitado pelo mesário
04/10/2026 06:47:53  Solicita digital. Tentativa [1] de [4]
04/10/2026 06:48:21  Capturada a digital. Tentativa [1] de [4]
04/10/2026 06:48:23  Número de tentativas de reconhecimento do dedo. Tentativa [1] de [4]
   (tentativas 2 e 3 iguais)
04/10/2026 06:49:22  Solicita digital. Tentativa [4] de [4]
04/10/2026 06:49:39  Timeout de reconhecimento do dedo. Tentativa [4] de [4]
04/10/2026 06:49:43  Solicitação de dado pessoal do eleitor para habilitação manual
04/10/2026 06:49:58  Dado digitado confere
04/10/2026 06:49:58  Solicita digital do mesário
04/10/2026 06:50:08  Biometria do mesário NNNNNNNNNNNN encontrada em eleitores
04/10/2026 06:50:08  Mesário NNNNNNNNNNNN habilitou o eleitor
04/10/2026 06:50:13  Eleitor foi habilitado
```

O número do mesário (título de eleitor) foi trocado por N acima.

"Número de tentativas de reconhecimento do dedo. Tentativa [k] de [4]" aparece depois de uma captura que **não** foi reconhecida; a captura reconhecida é seguida direto de "Tipo de habilitação do eleitor [biométrica]". A urna dá até 4 tentativas. O eleitor sem digital cadastrada passa de "Foto do eleitor apresentada" a "Eleitor foi habilitado" sem nenhum "Solicita digital".

O script (`ler_log`) separa cada eleitor pelo evento "Identificador do eleitor digitado pelo mesário" e fecha o episódio em "Eleitor foi habilitado", classificando:

| Classe no log | Regra | Campo do BU correspondente |
|---|---|---|
| habilitação biométrica | houve "Tipo de habilitação do eleitor [biométrica]" | `habilitados_biometria` |
| manual após digital | houve pedido de digital e depois habilitação manual (dado pessoal ou "Mesário N habilitou o eleitor") | `habilitados_biografia` |
| sem digital | habilitado sem nenhum "Solicita digital" | `comp_sem_biometria` |
| não habilitado | o episódio terminou sem "Eleitor foi habilitado" (identificador inválido, eleitor não encontrado, cancelamento) | nenhum |

Nas 5.994 leituras, "Tipo de habilitação do eleitor [...]" só aparece com o valor `[biométrica]`; não existe tipo "manual" escrito no log, por isso a habilitação manual é reconhecida pelos eventos de dado pessoal e de mesário.

### Textos exatos e contagens na amostra

Mensagens da VOTA ligadas à identificação e à habilitação, na amostra de 2.997 seções, com os números trocados por N (`logs_vocabulario.csv`, que tem a lista inteira, 78 mensagens):

| Nível | Mensagem | Ocorrências 1º | Seções 1º | Ocorrências 2º | Seções 2º |
|---|---|---|---|---|---|
| INFO | Solicita digital. Tentativa [N] de [N] | 1.115.969 | 2.997 | 1.124.961 | 2.997 |
| INFO | Capturada a digital. Tentativa [N] de [N] | 1.097.277 | 2.997 | 1.104.126 | 2.997 |
| INFO | Eleitor foi habilitado | 718.162 | 2.997 | 734.658 | 2.997 |
| INFO | Tipo de habilitação do eleitor [biométrica] | 609.323 | 2.997 | 628.197 | 2.997 |
| INFO | Número de tentativas de reconhecimento do dedo. Tentativa [N] de [N] | 487.946 | 2.996 | 475.917 | 2.997 |
| INFO | Batimento de digitais retornou o score N | 237.695 | 2.917 | 205.417 | 2.898 |
| INFO | Solicitação de dado pessoal do eleitor para habilitação manual | 69.417 | 2.993 | 64.232 | 2.986 |
| INFO | Dado digitado confere | 67.251 | 2.991 | 62.752 | 2.985 |
| INFO | Solicita digital do mesário | 68.583 | 2.991 | 63.884 | 2.985 |
| INFO | Ano de nascimento digitado é igual ao do cadastro | 42.170 | 2.716 | 44.060 | 2.734 |
| INFO | Mesário N habilitou o eleitor | 38.029 | 2.514 | 38.929 | 2.665 |
| INFO | Timeout de reconhecimento do dedo. Tentativa [N] de [N] | 17.750 | 2.551 | 20.245 | 2.531 |
| INFO | Habilitação cancelada durante confirmação de dado do eleitor | 4.078 | 1.741 | 2.814 | 1.447 |
| ALERTA | Habilitação cancelada durante reconhecimento biométrico | 2.566 | 968 | 1.235 | 609 |
| INFO | Digital capturada não corresponde a digital do eleitor: Polegar Direito [score N], Polegar Esquerdo [score N], Indicador Direito [score N], Indicador Esquerdo [score N] | 2.263 | 1.229 | 2.111 | 1.160 |
| INFO | Dado digitado não confere | 1.740 | 845 | 1.253 | 717 |
| INFO | Dado digitado está incompleto | 1.687 | 747 | 1.371 | 648 |
| ALERTA | Ano de nascimento digitado é diferente do cadastro | 1.175 | 581 | 822 | 479 |
| ALERTA | Ano de nascimento inválido | 82 | 62 | 41 | 37 |
| INFO | Eleitor foi suspenso pelo mesário | 476 | 374 | 42 | 42 |
| ALERTA | Mesário indagado se eleitor está votando | 8.276 | 1.959 | 1.095 | 714 |
| ERRO | Captura da digital do eleitor \| Falha na captura da digital (N) \| Ocorreu um erro durante captura da digital do eleitor. Desligue e ligue a urna. Se o erro persistir, substitua a urna. | 37 | 18 | 42 | 15 |
| WHAT | WHAT: void api::CFingerScanner::Open():N:N - ERROR opening the biometric reader - -N | 10 | 2 | 6 | 3 |
| INFO | Gerando relatório [ELEITORES HABILITADOS BIOGRAFICAMENTE] [INÍCIO] | 2.996 | 2.996 | 2.996 | 2.996 |

Eventos de biometria do **mesário** (cadastro do mesário na urna e uso da digital dele para habilitar o eleitor): "Pedido de leitura da biometria do mesário N" (24.161 e 24.145), "Biometria coletada não é do mesário N (N)" (137.933 e 120.504), "Biometria do mesário N encontrada nos arquivos coletados (N)" (32.099 e 32.335), "Digital coletada bate com uma digital gravada após o registro inicial de mesário. Não é possível associar a habilitação a um mesário." (16.811 e 13.711), "Capturada a digital do mesário" e "Não encontrou digital coletada em nenhum dos arquivos, vai salvar a digital em novo arquivo." (11.835 e 9.764), "Realizada a conferência da biometria do mesário" (5.309 e 5.489).

A queda de "Eleitor foi suspenso pelo mesário" (476 para 42) e de "Mesário indagado se eleitor está votando" (8.276 para 1.095) acompanha a mudança da cédula: no 1º turno o eleitor dava seis votos (deputado federal, deputado estadual, dois para senador, governador e presidente), no 2º um ou dois, e o eleitor que demora na cabine é suspenso.

## 3. Conferência do log com o BU

| Conferência por seção (2.997 seções) | 1º turno | 2º turno |
|---|---|---|
| "O voto do eleitor foi computado" = comparecimento do BU | 2.997 | 2.997 |
| habilitações biométricas do log = `habilitados_biometria` | 2.791 | 2.936 |
| manual após digital = `habilitados_biografia` | 2.959 | 2.988 |
| sem digital = `comp_sem_biometria` | 2.975 | 2.994 |

| Soma na amostra | 1º turno, log | 1º turno, BU | 2º turno, log | 2º turno, BU |
|---|---|---|---|---|
| votos computados / comparecimento | 717.871 | 717.871 | 734.608 | 734.608 |
| habilitação biométrica | 609.306 | 609.099 | 628.173 | 628.159 |
| manual após digital / biografia | 66.670 | 66.627 | 62.402 | 62.393 |
| sem digital / sem biometria | 42.169 | 42.145 | 44.059 | 44.056 |
| habilitados de outra forma | 17 | | 24 | |

O log tem 291 habilitações a mais que votos no 1º turno (718.162 contra 717.871) e 50 a mais no 2º (734.658 contra 734.608). São eleitores suspensos e habilitados de novo: o log registra as duas habilitações e o BU conta o eleitor uma vez. As diferenças das linhas acima têm a mesma ordem de grandeza e caem junto com as suspensões no 2º turno. A conclusão é que **os três campos do BU são a contagem dos eventos do log**, e a leitura do log é usada a seguir só para o que o BU não tem: número de tentativas, falhas e tempos.

## 4. BU nacional, por região, UF, modelo e tipo de urna

Base: as 497.895 seções do Brasil com detalhamento nos dois turnos (`tabelas.md`, seções `uf`, `regiao`, `modelo_mesma_urna`, `tipo_urna_t2`).

### Região

| Região | Seções | Sem biometria 1º | Sem biometria 2º | Biografia entre cadastrados 1º | Biografia entre cadastrados 2º | Variação (pontos) |
|---|---|---|---|---|---|---|
| Centro-Oeste | 38.048 | 3,978% | 4,043% | 6,840% | 6,580% | -0,260 |
| Nordeste | 140.828 | 4,513% | 4,564% | 7,261% | 7,530% | +0,268 |
| Norte | 43.769 | 3,734% | 3,650% | 5,563% | 5,638% | +0,075 |
| Sudeste | 203.235 | 7,321% | 7,501% | 6,909% | 6,993% | +0,085 |
| Sul | 72.015 | 4,484% | 4,603% | 8,139% | 8,030% | -0,109 |

### UF

| UF | Seções | Sem biometria 1º | Sem biometria 2º | Variação | Biografia entre cadastrados 1º | 2º | Variação |
|---|---|---|---|---|---|---|---|
| AC | 2.270 | 3,661% | 3,378% | -0,283 | 5,180% | 5,168% | -0,012 |
| AL | 7.101 | 3,647% | 3,584% | -0,063 | 6,774% | 7,221% | +0,447 |
| AM | 8.157 | 4,465% | 4,339% | -0,127 | 5,642% | 5,673% | +0,030 |
| AP | 1.914 | 3,729% | 3,564% | -0,166 | 4,570% | 4,747% | +0,178 |
| BA | 35.476 | 4,721% | 4,804% | +0,083 | 7,650% | 7,830% | +0,179 |
| CE | 23.765 | 4,020% | 4,041% | +0,021 | 7,172% | 7,426% | +0,254 |
| DF | 6.969 | 3,140% | 3,169% | +0,029 | 4,992% | 4,650% | -0,342 |
| ES | 9.844 | 20,910% | 21,081% | +0,171 | 8,136% | 7,963% | -0,173 |
| GO | 15.686 | 4,428% | 4,455% | +0,027 | 7,117% | 6,947% | -0,169 |
| MA | 18.093 | 3,686% | 3,646% | -0,039 | 6,218% | 6,534% | +0,316 |
| MG | 52.060 | 11,205% | 11,515% | +0,310 | 7,530% | 7,693% | +0,163 |
| MS | 7.106 | 4,099% | 4,255% | +0,156 | 8,154% | 7,569% | -0,585 |
| MT | 8.287 | 3,762% | 3,862% | +0,100 | 6,986% | 6,862% | -0,124 |
| PA | 20.827 | 4,044% | 3,992% | -0,052 | 5,633% | 5,790% | +0,158 |
| PB | 10.712 | 3,019% | 3,002% | -0,017 | 7,186% | 7,491% | +0,305 |
| PE | 21.418 | 7,667% | 7,802% | +0,135 | 6,774% | 7,077% | +0,303 |
| PI | 10.225 | 2,036% | 1,997% | -0,040 | 8,832% | 9,186% | +0,354 |
| PR | 27.142 | 0,674% | 0,696% | +0,022 | 7,530% | 7,037% | -0,493 |
| RJ | 37.675 | 7,072% | 7,224% | +0,152 | 7,587% | 8,025% | +0,438 |
| RN | 8.115 | 3,748% | 3,755% | +0,006 | 8,217% | 8,415% | +0,198 |
| RO | 4.698 | 1,633% | 1,613% | -0,020 | 6,348% | 6,369% | +0,021 |
| RR | 1.519 | 3,066% | 2,947% | -0,119 | 3,964% | 4,222% | +0,258 |
| RS | 27.547 | 7,916% | 8,120% | +0,204 | 8,934% | 9,200% | +0,266 |
| SC | 17.326 | 5,141% | 5,306% | +0,165 | 7,965% | 7,930% | -0,035 |
| SE | 5.923 | 3,637% | 3,602% | -0,035 | 7,016% | 7,229% | +0,213 |
| SP | 103.656 | 4,348% | 4,495% | +0,147 | 6,296% | 6,245% | -0,051 |
| TO | 4.384 | 2,841% | 2,782% | -0,059 | 5,436% | 5,088% | -0,348 |

Nenhuma UF variou mais de 0,59 ponto em qualquer das duas taxas. A taxa sem biometria é alta e estável no ES (21%) e em MG (11%), o que é característica do cadastro desses estados, não do dia da votação.

### Modelo de urna

O BU não traz o modelo; ele vem da assinatura (`-vota.vsc`) do 1º turno. A tabela usa só as 493.484 seções em que o número interno da urna é o mesmo nos dois turnos, para que o modelo valha para os dois.

| Modelo | Seções | Sem biometria 1º | 2º | Biografia entre cadastrados 1º | 2º | Variação |
|---|---|---|---|---|---|---|
| UE2013 | 10.391 | 6,969% | 7,085% | 11,491% | 11,452% | -0,039 |
| UE2015 | 86.433 | 6,158% | 6,288% | 10,098% | 10,239% | +0,140 |
| UE2020 | 198.923 | 5,432% | 5,550% | 6,291% | 6,369% | +0,079 |
| UE2022 | 197.737 | 5,340% | 5,446% | 6,261% | 6,332% | +0,071 |

A habilitação por ano de nascimento é quase o dobro nas urnas mais antigas (UE2013 e UE2015) nos dois turnos. A mesma diferença aparece no log (seção 5).

### Tipo de urna no 2º turno

| Tipo no BU do 2º turno | Seções | Biografia entre cadastrados 1º | 2º |
|---|---|---|---|
| secao | 492.223 | 7,045% | 7,136% |
| reservaSecao (urna trocada no dia) | 5.670 | 9,280% | 9,000% |
| reservaEncerrandoSecao | 2 | 10,876% | 8,092% |

## 5. Log: tentativas e falhas por eleitor

Amostra estratificada, sem repetição (`escolher_amostra`): 359 seções extremas do BU (maiores subidas e quedas da biografia entre cadastrados e da taxa sem biometria), 300 das 968 seções atípicas de viradas, 300 das 7.581 seções tardias (encerramento às 17:31 de Brasília ou depois no 2º turno) e 2.038 seções aleatórias com a mesma distribuição por UF do país. Só entram seções com BU de urna (não SA), comparecimento de 20 ou mais nos dois turnos e fora do exterior. A ordem aleatória é o SHA-256 de `2026/biometria/<chave da seção>`.

Os números nacionais saem do estrato **aleatório** (2.038 seções, 511.619 habilitações no 1º turno e 522.862 no 2º):

| Indicador (estrato aleatório) | 1º turno | 2º turno |
|---|---|---|
| Pedidos de digital por eleitor habilitado | 1,480 | 1,483 |
| Digitais não reconhecidas por eleitor habilitado | 0,577 | 0,578 |
| Timeouts de reconhecimento por mil habilitados | 22,61 | 26,71 |
| Habilitação biométrica | 87,971% | 87,802% |
| Manual após digital, entre cadastrados | 7,006% | 7,082% |
| Sem digital | 5,400% | 5,503% |
| Reconhecidos na 1ª tentativa, entre os biométricos | 75,07% | 74,50% |
| Tentativas por eleitor reconhecido | 1,369 | 1,377 |
| Habilitações canceladas por mil | 8,74 | 5,50 |

Por região (estrato aleatório), reconhecimento na 1ª tentativa: Centro-Oeste 75,6% e 75,5%, Nordeste 74,4% e 73,1%, Norte 76,5% e 75,7%, Sudeste 75,4% e 75,3%, Sul 74,3% e 74,0%. Timeouts por mil: Sul 44,3 e 49,8, nas demais regiões entre 16 e 28.

Por modelo (estrato aleatório, mesma urna nos dois turnos):

| Modelo | Seções | Reconhecidos na 1ª tentativa 1º | 2º | Falhas por habilitado 1º | 2º | Timeouts por mil 1º | 2º |
|---|---|---|---|---|---|---|---|
| UE2013 | 41 | 71,6% | 71,1% | 0,792 | 0,810 | 31,3 | 35,4 |
| UE2015 | 348 | 69,1% | 69,3% | 0,779 | 0,779 | 4,5 | 3,8 |
| UE2020 | 776 | 76,4% | 75,7% | 0,524 | 0,523 | 27,1 | 33,2 |
| UE2022 | 856 | 76,4% | 75,6% | 0,530 | 0,532 | 25,7 | 29,7 |

Por estrato:

| Estrato | Seções | Falhas por habilitado 1º | 2º | Manual entre cadastrados 1º | 2º |
|---|---|---|---|---|---|
| aleatória | 2.038 | 0,577 | 0,578 | 7,01% | 7,08% |
| atípicos de viradas | 300 | 0,634 | 0,646 | 7,89% | 8,08% |
| tardias | 300 | 0,549 | 0,551 | 6,42% | 6,67% |
| extremos do BU | 359 | 1,624 | 1,277 | 37,66% | 27,72% |

Pareado por seção, a variação das falhas por habilitado (2º menos 1º) tem mediana -0,0006 e média -0,0011 no estrato aleatório, +0,006 nos atípicos e 0,000 nas tardias. Ela acompanha a variação da biografia do BU (correlação de Pearson 0,953 nas 2.997 seções), o que confirma que a biografia alta é falha de reconhecimento registrada eleitor a eleitor.

## 6. Distribuição da variação por seção e seções extremas

Base: 497.835 seções do Brasil com comparecimento de 20 ou mais nos dois turnos.

| Variação, em pontos (2º menos 1º) | p0,1 | p1 | p5 | p25 | mediana | p75 | p95 | p99 | p99,9 |
|---|---|---|---|---|---|---|---|---|---|
| Taxa sem biometria | -2,50 | -1,43 | -0,79 | -0,14 | 0,00 | 0,35 | 1,17 | 2,02 | 3,30 |
| Biografia entre cadastrados | -10,35 | -5,97 | -3,66 | -1,29 | 0,05 | 1,43 | 3,75 | 5,95 | 9,63 |

- Taxa sem biometria: só 53 seções variaram 5 pontos ou mais e 2 variaram 10 pontos ou mais; o máximo foi 12,4 pontos, em seções pequenas (a maior queda, AM 02003/0067/0039, tem 37 e 26 eleitores). Nenhuma seção teve 100% sem biometria em qualquer turno.
- Biografia entre cadastrados: 974 seções variaram 10 pontos ou mais (399 subiram, 575 caíram), 140 variaram 30 pontos ou mais e 78 variaram 50 pontos ou mais.
- Biometria de 70% ou mais do comparecimento no 1º turno e 10% ou menos no 2º: 8 seções. O contrário (quase zero no 1º e 70% ou mais no 2º): 17 seções.

Perfil das 140 seções com variação de 30 pontos ou mais na biografia: 116 UE2013, 21 UE2015, 2 UE2020 e 1 UE2022; em 60 delas a urna do 2º turno não é a do 1º; 85 têm BU de urna de reserva (`reservaSecao`) no 2º turno; 1 é atípica de viradas, 3 são tardias e 5 viraram. A variação média da fatia do 13 nelas foi 2,66 pontos, contra 2,91 nas demais.

Seções em que mais da metade dos cadastrados foi habilitada por ano de nascimento: 153 no 1º turno (130 UE2013, 21 UE2015) e 106 no 2º (80 UE2013, 26 UE2015). Por 10 mil urnas de cada modelo, no 1º turno: UE2013 119,4; UE2015 2,4; UE2020 e UE2022 0,05. 70 seções estão nos dois turnos; das 83 que só aparecem no 1º, em 41 a urna foi trocada para o 2º turno.

### A biometria some no 2º turno (maiores subidas da biografia)

| Seção (UF/município/zona/seção) | Modelo 1º | Mesma urna | Tipo 2º | Biometria 1º | Biografia 1º | Biometria 2º | Biografia 2º | Fatia do 13, 1º e 2º |
|---|---|---|---|---|---|---|---|---|
| BA/34290/0127/0336 | UE2013 | não | secao | 224 | 18 | 4 | 243 | 80,6% e 81,6% |
| RJ/58637/0221/0178 | UE2015 | não | reservaSecao | 187 | 21 | 11 | 188 | 41,5% e 46,3% |
| BA/34290/0127/0335 | UE2013 | sim | secao | 219 | 39 | 7 | 281 | 81,1% e 83,4% |
| RJ/60011/0188/0082 | UE2015 | não | reservaSecao | 195 | 37 | 10 | 228 | 59,7% e 65,1% |
| SP/70750/0174/0447 | UE2013 | sim | secao | 174 | 34 | 9 | 205 | 49,4% e 48,3% |
| GO/96539/0110/0116 | UE2013 | sim | secao | 157 | 21 | 17 | 157 | 36,8% e 40,0% |
| RS/89770/0088/0113 | UE2015 | não | reservaSecao | 226 | 61 | 7 | 282 | 17,5% e 20,0% |
| RJ/60011/0008/0074 | UE2013 | sim | reservaSecao | 181 | 69 | 3 | 269 | 59,7% e 65,0% |
| PR/74993/0159/0009 | UE2013 | sim | secao | 137 | 54 | 13 | 196 | 44,4% e 49,3% |

### A biometria volta no 2º turno (maiores quedas da biografia)

| Seção | Modelo 1º | Mesma urna | Tipo 2º | Biometria 1º | Biografia 1º | Biometria 2º | Biografia 2º | Fatia do 13, 1º e 2º |
|---|---|---|---|---|---|---|---|---|
| ES/56995/0026/0651 | UE2013 | não | reservaSecao | 4 | 274 | 287 | 23 | 55,2% e 57,0% |
| BA/38830/0162/0153 | UE2013 | sim | secao | 10 | 189 | 187 | 13 | 94,6% e 94,4% |
| MA/08494/0093/0326 | UE2013 | não | reservaSecao | 6 | 200 | 175 | 19 | 58,8% e 60,1% |
| ES/56995/0053/0043 | UE2013 | sim | secao | 1 | 82 | 75 | 10 | 42,3% e 46,2% |
| BA/38946/0178/0179 | UE2013 | não | reservaSecao | 10 | 258 | 245 | 26 | 74,9% e 77,7% |
| CE/13951/0025/0117 | UE2013 | não | reservaSecao | 13 | 226 | 228 | 20 | 79,8% e 81,1% |
| ES/56995/0026/0559 | UE2013 | sim | secao | 5 | 169 | 158 | 19 | 40,2% e 45,3% |
| SP/71579/0324/0235 | UE2013 | não | secao | 15 | 260 | 269 | 25 | 49,3% e 53,4% |
| RS/87807/0152/0142 | UE2013 | não | reservaSecao | 8 | 176 | 161 | 18 | 17,2% e 18,1% |

Nos dois quadros a fatia do 13 se move dentro do que o resto do país moveu (média nacional de +2,9 pontos) e a taxa sem biometria quase não muda, o que mostra que o eleitorado que compareceu é o mesmo. O que muda é a urna reconhecer ou não a digital. Há agrupamento por local: ES/56995 (9 seções com biografia majoritária no 1º turno), BA/36854 (9 nos dois turnos) e RJ/60011 (6 no 2º turno). A lista completa, com as marcas de atípico e tardia, está em `extremos.csv` (listas `biog_sobe`, `biog_cai`, `sem_bio_sobe`, `sem_bio_cai`, `bio_alta_para_quase_zero`).

## 7. Relação com o voto, com as seções tardias e com as viradas atípicas

Base: as mesmas 497.835 seções. "Fatia do 13" = 13 ÷ (13 + 22), como em `docs/viradas-1t-2t-2026.md`; a variação é 2º menos 1º.

| Correlação | Pearson | p | Spearman | p |
|---|---|---|---|---|
| variação da biografia x variação da fatia do 13 (país) | -0,0085 | < 0,000001 | -0,0123 | < 0,000001 |
| idem, dentro da UF | -0,0009 | 0,55 | -0,0031 | 0,031 |
| idem, dentro do município | -0,0009 | 0,51 | -0,0018 | 0,20 |
| variação da taxa sem biometria x variação da fatia do 13 (país) | 0,0179 | < 0,000001 | 0,0179 | < 0,000001 |
| idem, dentro da UF | -0,0031 | 0,031 | 0,0005 | 0,73 |
| idem, dentro do município | 0,0032 | 0,026 | 0,0036 | 0,011 |
| variação das falhas por habilitado no log x variação da fatia (2.997 seções) | 0,0271 | 0,14 | 0,0036 | 0,84 |
| idem, dentro da UF | 0,0194 | 0,29 | 0,0269 | 0,14 |

Com meio milhão de seções, correlações de 0,01 já dão p pequeno; o que importa é o tamanho. Dentro do município, a variação da biografia explica menos de 0,0001% da variação da fatia do 13. Por decil da variação da biografia, a variação média da fatia do 13 fica entre 2,64 e 3,02 pontos em todos os dez decis, sem tendência (`resumo.json`, `decis_d_biog_x_delta_fatia`).

| Grupo (comparecimento de 20 ou mais) | Seções | Variação média da taxa sem biometria (pontos) | Variação média da biografia entre cadastrados (pontos) | Seções com variação da biografia de 10 pontos ou mais | Esperado pelo tamanho das seções |
|---|---|---|---|---|---|
| Todas | 497.835 | +0,096 | +0,055 | 974 | |
| Atípicas de viradas | 968 | +0,005 | -0,022 | 13 | 13,6 |
| Tardias (17:31 de Brasília ou depois) | 7.581 | +0,142 | +0,206 | 13 | 9,6 |
| Com virada de liderança | 31.890 | +0,140 | +0,042 | 47 | 57,2 |

O "esperado pelo tamanho" aplica a cada seção do grupo a frequência de variação de 10 pontos ou mais observada no país entre seções com o mesmo número de cadastrados (faixas de 0 a 25, 25 a 50, 50 a 100, 100 a 150, 150 a 200, 200 a 250, 250 a 300 e mais de 300). Seção pequena tem taxa mais ruidosa, e as atípicas são menores (comparecimento médio de 171,6 contra 256,8). Feito esse ajuste, nenhum grupo concentra variação de biometria.

- **Atípicas de viradas (968):** a variação da biografia é igual à do resto (-0,02 contra +0,06 ponto, z = -0,61). Nenhuma das 968 tem maioria habilitada por ano de nascimento no 2º turno. Elas têm biografia um pouco mais alta que o resto **nos dois turnos** (8,56% e 8,54% contra 7,29% e 7,35% na média por seção), uma diferença de nível que já existia no 1º turno e não mudou.
- **Tardias (7.581):** a biografia subiu 0,21 ponto, contra 0,05 no resto (z = 5,6), e a taxa sem biometria subiu 0,14 contra 0,095 (z = 6,7). São diferenças de um décimo de ponto. No log, as 300 tardias da amostra têm as mesmas falhas por habilitado nos dois turnos (0,549 e 0,551).
- **Viradas:** a taxa sem biometria é maior nas seções que viraram (6,7% contra 5,5% no 1º turno), outra diferença de nível que já existia antes; a variação entre turnos difere em 0,05 ponto.

## 8. Limites

- O log foi lido numa amostra de 2.997 seções (0,6% do país). Os indicadores nacionais do log vêm das 2.038 seções aleatórias; os estratos de atípicos, tardias e extremos servem para comparação e não representam o país.
- O modelo da urna vem da assinatura do 1º turno. Quando o número interno da urna difere entre os turnos ou falta (4.411 seções pareadas), o modelo do 2º turno pode ser outro; por isso a tabela por modelo usa só a mesma urna.
- "Leitor que não reconhece" é a leitura mais simples do padrão (falhas por eleitor altas, concentração em UE2013, normalização quando a urna é trocada), mas os arquivos públicos não dizem a causa. A urna registra erro de hardware do leitor só em poucas seções da amostra ("ERROR opening the biometric reader" em 2 seções no 1º turno e 3 no 2º; "Falha na captura da digital" em 18 e 15).
- O exterior não tem detalhamento de biometria no BU e ficou fora.
- Os campos do BU são o que a urna contou. Nada aqui verifica a identidade de eleitores; o log não traz número de título nem de CPF do eleitor, só o tipo de identificador digitado.

## 9. Teste de votos inseridos sem biometria (29/10/2026)

Pergunta: o aumento de comparecimento do 1º para o 2º turno tem cara de votos inseridos pelo mesário em nome de ausentes? Quem não tem biometria cadastrada, ou é habilitado pelo ano de nascimento, pode votar sem digital, então um voto inserido apareceria nesses dois campos do BU. Script: `scripts/ele2026/injecao_nao_biometricos.py`, sobre `secoes_biometria.parquet` (497.895 seções pareadas com detalhamento nos dois turnos).

| Item | Resultado |
|---|---|
| Aumento de comparecimento 1T para 2T | +2.920.461 |
| desse aumento, habilitados por digital | +2.318.918 (79,4%) |
| desse aumento, sem digital (sem biometria cadastrada ou por ano de nascimento) | +601.543 (20,6%) |
| Parcela sem digital no comparecimento | 12,23% no 1º turno, 12,42% no 2º |
| Seções com comparecimento de 98% ou mais dos aptos | 60 no 1º, 66 no 2º |
| Seções com 100% de comparecimento | 15 no 1º, 12 no 2º |

Dentro de cada município (diferença de cada seção para a média do município, por eleitor apto), cada eleitor a mais habilitado **sem digital** acompanha +0,103 voto no 13 e +0,073 no 22 (59% e 41%); cada eleitor a mais habilitado **por digital** acompanha +0,307 no 13 e +0,201 no 22 (60% e 40%). O eleitor extra sem digital divide o voto na mesma proporção do eleitor extra com digital, que o mesário não consegue simular. Se houvesse votos inseridos sem digital a favor de um candidato, a primeira divisão seria puxada para ele e se afastaria da segunda.

As 62 seções em que a parcela sem digital subiu 15 pontos ou mais tiveram a fatia do 13 subindo de 49,98% para 52,66% (+2,7 pontos), igual ao país (48,98% para 51,78%, +2,8 pontos); 58 delas usam UE2013 ou UE2015, o mesmo padrão de leitor que não reconhece da seção 6.

Conclusão: o voto sem digital não favorece nenhum candidato além do que o voto com digital favorece, e o comparecimento extremo não aumentou. Limite: o teste pega inserção que mude o voto de forma desigual entre seções; uma inserção pequena e espalhada igualmente não aparece no BU, e a identidade de quem votou (falecido, ausente) não está em nenhum arquivo público.
