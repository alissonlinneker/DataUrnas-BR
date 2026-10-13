# Metodologia

Este documento descreve como o DataUrnas-BR transforma os arquivos públicos da urna eletrônica em indicadores de auditoria. Todas as verificações são determinísticas e podem ser refeitas a partir do código e dos dados do TSE.

## Princípios

1. **Fonte única:** só são usados arquivos publicados pelo TSE. Nenhum dado é corrigido, imputado ou estimado.
2. **Indicador, não conclusão:** cada achado vira uma ocorrência com código e severidade. A severidade expressa a importância de investigar, não a probabilidade de fraude.
3. **Falha de leitura não é evidência:** quando um arquivo está ausente ou não pode ser decodificado, o projeto registra que a verificação não foi possível (códigos E01 e E02), sem tratar isso como adulteração.
4. **Reconciliação com o oficial:** a soma dos BUs é comparada com a totalização do TSE. Divergência é reportada; concordância também.

## Arquivos da urna

| Arquivo (2022) | Arquivo (2026) | Conteúdo | Uso |
|---|---|---|---|
| `.bu` | `-bu.dat` | Boletim de Urna em ASN.1/BER | Votos por cargo e candidato, aptos, comparecimento, biometria, horários |
| `.vscmr` | `-vota.vsc` | Arquivo de assinatura | Hashes SHA-512 dos demais arquivos e modelo da urna |
| `.logjez` | arquivo `.jez` | Log da urna (7z) | Eventos de abertura, encerramento, reinícios, erros, votos |
| `.rdv` | arquivo `.dat` | Registro Digital do Voto | Reservado para uso futuro |
| `.imgbu` | arquivo `.dat` | Imagem do BU impresso | Reservado para uso futuro |

A decodificação ASN.1 usa as especificações oficiais em `spec/v1` (2022) e `spec/v2` (2024 em diante), compiladas com `asn1tools`. Campos do tipo CHOICE são desembrulhados e enumerações são convertidas para nomes legíveis.

## Integridade

Para cada arquivo listado em `arquivosAssinados` no arquivo de assinatura, o projeto localiza o arquivo correspondente no diretório da seção, calcula o SHA-512 e compara com o hash assinado.

| Situação | Código |
|---|---|
| Hash calculado e igual ao assinado | nenhum |
| Hash calculado e diferente do assinado | C01 (crítica) |
| Arquivo assinado ausente ou assinatura ilegível | E01 (informativa) |

A conferência é opcional por ser custosa (`dataurnas analyze batch --hashes`). O projeto **não** verifica a cadeia de certificados nem a assinatura digital em si: verifica que os arquivos publicados correspondem aos hashes que a própria urna assinou.

## Consistência do BU

| Código | Regra |
|---|---|
| C05 | Para algum cargo, total de votos maior que os eleitores aptos da seção |
| A02 | Votos computados maiores que o comparecimento |
| A06 | Comparecimento diferente entre cargos da mesma seção |
| A01 | Eleitores aptos diferentes entre eleições registradas na mesma urna |
| I06 | Urna de reserva ou tipo diferente de `secao` |
| E02 | BU não decodificável, inclusive `tipoVoto` ausente ou desconhecido; a seção sai dos totais |

O caso E02 merece nota: versões anteriores assumiam "nominal" quando o tipo de voto não era reconhecido, o que poderia atribuir votos a candidatos indevidamente. Agora o BU é rejeitado e a seção é listada para conferência manual.

## Log da urna

O log é extraído em memória, com limite de tamanho descompactado, e as linhas são convertidas em eventos.

- **Abertura:** primeira ocorrência de "Urna pronta para receber votos" na data do turno.
- **Encerramento:** "Início do Encerramento".
- **Reinícios:** cada abertura adicional no mesmo dia conta como um reinício (C06: média com 1, alta com 2 ou mais).
- **Filtro por turno:** no 2º turno de 2022 o log acumula os eventos do 1º. Só são considerados eventos da data do turno (02/10/2022 ou 30/10/2022).

| Código | Regra (horários de Brasília convertidos para o fuso local) |
|---|---|
| M01 | Abertura antes das 8h |
| A04 | Abertura depois das 8h30 |
| A05 | Encerramento antes das 17h |
| M02 | Encerramento depois das 22h |
| M03 | Log com mais de 100 entradas e sem evento de abertura |
| M04 | Mais de 10 erros |
| M05 | Ajustes de hora registrados |
| I01 | Eventos de substituição ou contingência |
| I02 | Mais de 20 alertas de mesário |
| A03 | Votos contados no log diferem do comparecimento do BU em mais de 2 |
| E03 | Encerramento registrado antes da abertura (duração negativa) |

### Fusos

| UF | Fuso | Diferença para Brasília |
|---|---|---|
| AC | UTC-5 | -2 h |
| AM, MT, MS, RO, RR | UTC-4 | -1 h |
| Demais | UTC-3 | 0 |

## Indicadores estatísticos por seção

| Código | Regra |
|---|---|
| I03 | Nulos acima de 15% dos votos de um cargo |
| I04 | Brancos acima de 10% dos votos de um cargo |
| I05 | Abstenção acima de 40% |
| M06 | Mais de 30% dos eleitores liberados sem biometria |

## Análises agregadas

### Lei de Benford

Distribuição esperada do primeiro dígito: `P(d) = log10(1 + 1/d)`, d = 1..9. Do segundo dígito: `P(d) = Σ_{k=1..9} log10(1 + 1/(10k + d))`, d = 0..9.

O projeto calcula o qui-quadrado entre observado e esperado e, como amostras com centenas de milhares de seções rejeitam a hipótese nula com qualquer desvio mínimo, reporta também o **V de Cramér**, `V = √(χ² / (n · (k - 1)))`, como medida de efeito. Valores abaixo de 0,02 indicam aderência muito alta.

Ressalva importante: votos por seção não seguem Benford por natureza, porque o tamanho das seções é limitado. O teste serve como comparação entre candidatos, UFs e turnos, não como prova isolada.

### Outliers

Para abstenção, biometria, comparecimento, nulos e brancos: `z = (x - μ) / σ`, com sinalização para `|z| > 3`. Há uma variante nacional e outra calculada dentro de cada UF.

### Reinícios e votação

Teste qui-quadrado de independência entre ocorrência de reinício e distribuição de votos por candidato, com V de Cramér, segmentado por UF e modelo de urna.

### Comparação entre turnos

Variação de comparecimento por seção (sinalizada acima de 10%), migração de votos por UF e seções presentes em apenas um turno.

### Circunscrição dos números de candidato

O número de um candidato só é único dentro da circunscrição do cargo: nacional (Presidente), estadual (Governador, Senador, deputados) ou municipal (Prefeito, Vereador). As agregações usam essa chave para não misturar candidatos diferentes com o mesmo número.

## Índice de confiança

Média ponderada de sete componentes, de 0 (risco máximo) a 100:

| Componente | Peso |
|---|---:|
| Integridade de hash (C01) | 20 |
| Votos acima do eleitorado (C05) | 15 |
| Aderência a Benford | 15 |
| Impacto de reinícios | 15 |
| Consistência entre turnos | 15 |
| Concentração de outliers | 10 |
| Biometria | 10 |

O índice resume os indicadores do projeto e depende dos pesos escolhidos. Ele não substitui nem contesta a totalização oficial.

## Reconciliação de 2026

`scripts/ele2026/reconcile.py` compara, para cada UF com BUs coletados:

- votos por candidato (soma dos BUs x `v_<número>` do resultado oficial);
- brancos, nulos e comparecimento;
- votos nominais;
- número de seções com BU x seções instaladas.

Votos nominais para números que não constam da lista de candidatos são contabilizados pelo TSE como nulos técnicos; a reconciliação leva isso em conta (ver [dados-2026.md](dados-2026.md)).

## O que não é inconsistência

- Nomes de eleitores no log (comportamento documentado do terminal do mesário).
- Substituição de urna (procedimento de contingência).
- Ajuste de hora antes da abertura.
- Abstenção, votos brancos e nulos.
