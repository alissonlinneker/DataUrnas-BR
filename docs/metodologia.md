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

| Situação | Código | Severidade |
|---|---|---|
| Hash calculado e igual ao assinado | nenhum | |
| Hash calculado e diferente do assinado | C01 | crítica |
| Arquivo assinado ausente ou assinatura ilegível | E01 | informativa |

A conferência é opcional por ser custosa (`dataurnas analyze batch --hashes`). Nessa conferência (usada em 2022) o projeto **não** verifica a cadeia de certificados nem a assinatura digital em si: verifica que os arquivos publicados correspondem aos hashes que a própria urna assinou. Em 2026 a assinatura também é verificada (ver [Integridade em 2026](#integridade-em-2026)).

A base de 2022 distribuída em `data/parquet` foi compilada sem essa conferência. Por isso a ausência de C01 nessa base não atesta a integridade dos arquivos; para conferir, rode `dataurnas analyze batch --hashes` ou `dataurnas analyze hashes <diretório da seção>` sobre os arquivos brutos, ou recompile com `dataurnas db build --hashes`.

O banco registra se a conferência foi feita na tabela `metadados` (chave `verify_hashes`, `true` ou `false`). `dataurnas db build` grava o valor conforme a opção `--hashes` (padrão: desligada); numa compilação incremental, a base só continua marcada como verificada se a parte anterior também era. `scripts/build_db.py` copia o valor de `metadados.parquet`, quando esse arquivo acompanha os Parquet; sem ele, grava `false`, a menos que a opção `--hashes-verificados` declare que os Parquet vieram de uma compilação verificada. Em bancos antigos, sem a tabela, o painel considera a conferência feita apenas se houver alguma ocorrência C01 ou E01, porque só ela gera esses códigos; caso contrário, trata a base como não verificada.


### Integridade em 2026

Para o 1º turno de 2026 a conferência é feita em todas as seções, numa etapa própria que grava o catálogo em `data/parquet/2026/integridade` (`arquivos_<uf>.parquet`, `secoes.parquet` e `resumo.json`):

1. cada arquivo publicado da seção (`bu.dat`, `rdv.dat`, `log.jez`, `-vota.vsc`, `busa.dat`, imagem do BU) recebe MD5, SHA-256 e SHA-512;
2. o SHA-512 de `bu.dat`, `rdv.dat` e `log.jez` é comparado com o valor assinado no `-vota.vsc` (`hash_confere`); arquivos que a assinatura não cobre ficam com o campo nulo, o que é esperado;
3. a assinatura do `-vota.vsc` é verificada com a chave pública do certificado que o acompanha (`assinatura_valida`), e os dados do certificado (algoritmo, titular, emissor, número de série e SHA-256) ficam registrados para conferência; a validação da cadeia de certificação não faz parte desta etapa;
4. o token do `aux.json` (32 bytes em base64url) e a data e hora informadas pelo TSE são registrados, sem comparação, porque o token não é o hash de nenhum arquivo isolado.

MD5 e SHA-256 não fazem parte do mecanismo da urna: ficam no catálogo para facilitar conferências com outras fontes. Uma seção é considerada divergente quando algum SHA-512 difere do assinado, a assinatura é inválida ou os votos não conferem. A cobertura é o número de seções verificadas dividido pelas seções instaladas do resultado oficial. O resultado está na página **Integridade dos arquivos (2026)** do painel e no [relatório de integridade](relatorio-integridade-2026.md), que traz também o passo a passo para conferir uma seção à mão.

## Consistência do BU

| Código | Severidade | Regra |
|---|---|---|
| C05 | crítica | Para algum cargo, total de votos maior que os eleitores aptos da seção |
| A02 | alta | Votos computados maiores que o comparecimento |
| A06 | alta | Comparecimento diferente entre cargos da mesma seção |
| A01 | alta | Eleitores aptos diferentes entre eleições registradas na mesma urna |
| I06 | informativa | Urna de reserva ou tipo diferente de `secao` |
| E02 | média | BU não decodificável, inclusive `tipoVoto` ausente ou desconhecido; a seção sai dos totais |

O caso E02 merece nota: versões anteriores assumiam "nominal" quando o tipo de voto não era reconhecido, o que poderia atribuir votos a candidatos indevidamente. Agora o BU é rejeitado e a seção é listada para conferência manual.

## Log da urna

O log é extraído em memória, com limite de tamanho descompactado, e as linhas são convertidas em eventos.

- **Abertura:** primeira ocorrência de "Urna pronta para receber votos" na data do turno.
- **Encerramento:** "Início do Encerramento".
- **Reinícios:** cada abertura adicional no mesmo dia conta como um reinício (C06: severidade média com 1, alta com 2 ou mais).
- **Filtro por turno:** no 2º turno de 2022 o log acumula os eventos do 1º. Só são considerados eventos da data do turno (02/10/2022 ou 30/10/2022).

| Código | Severidade | Regra (horários de Brasília convertidos para o fuso local) |
|---|---|---|
| M01 | média | Abertura antes das 7h, mais de 1 h antes do horário oficial |
| A04 | alta | Abertura depois das 8h30 (tolerância de 30 min) |
| A05 | alta | Encerramento antes das 17h |
| M02 | média | Encerramento depois das 22h |
| M03 | média | Log com mais de 100 entradas e sem evento de abertura |
| C06 | média ou alta | Reinícios durante a votação (ver acima) |
| M04 | média | Mais de 10 erros |
| M05 | média | Ajustes de hora registrados |
| I01 | informativa | Eventos de substituição ou contingência |
| I02 | informativa | Mais de 20 alertas de mesário |
| A03 | alta | Votos contados no log diferem do comparecimento do BU em mais de 2 |
| E03 | informativa | Encerramento registrado antes da abertura (duração negativa) |

### Fusos

| UF | Fuso | Diferença para Brasília |
|---|---|---|
| AC | UTC-5 | -2 h |
| AM, MT, MS, RO, RR | UTC-4 | -1 h |
| Demais | UTC-3 | 0 |

O fuso é resolvido por município quando há exceção conhecida (`analyzer/timezones.py`): os municípios do oeste do Amazonas (Atalaia do Norte, Benjamin Constant, Eirunepé, Envira, Guajará, Ipixuna e Tabatinga) seguem UTC-5, e Fernando de Noronha (PE) segue UTC-2. A base de 2022 distribuída foi compilada antes dessas exceções e usa o fuso da UF em todas as seções; elas passam a valer numa recompilação a partir dos dados brutos.

## Indicadores estatísticos por seção

| Código | Severidade | Regra |
|---|---|---|
| I03 | informativa | Nulos acima de 15% dos votos de um cargo |
| I04 | informativa | Brancos acima de 10% dos votos de um cargo |
| I05 | informativa | Abstenção acima de 40% |
| M06 | média | Mais de 30% dos eleitores liberados sem biometria |

## Análises agregadas

### Lei de Benford

Distribuição esperada do primeiro dígito: `P(d) = log10(1 + 1/d)`, d = 1..9. Do segundo dígito: `P(d) = Σ_{k=1..9} log10(1 + 1/(10k + d))`, d = 0..9.

O projeto calcula o qui-quadrado entre observado e esperado e, como amostras com centenas de milhares de seções rejeitam a hipótese nula com qualquer desvio mínimo, reporta também o **V de Cramér**, `V = √(χ² / (n · (k - 1)))`, como medida de efeito. No índice de confiança, V abaixo de 0,05 conta como conforme, de 0,05 a 0,10 como aceitável, de 0,10 a 0,20 como ponto de atenção e a partir de 0,20 como não conforme.

Ressalva importante: votos por seção não seguem Benford por natureza, porque o tamanho das seções é limitado. O teste serve como comparação entre candidatos, UFs e turnos, não como prova isolada.

### Outliers

`z = (x - μ) / σ`, com sinalização para `|z| > 3`. Abstenção, liberação sem biometria e duração da votação têm uma variante nacional e outra calculada dentro de cada UF. Nulos, brancos e a participação de cada candidato são avaliados dentro de cada UF.

### Reinícios e votação

Teste qui-quadrado de independência entre ocorrência de reinício e distribuição de votos por candidato, com V de Cramér, segmentado por UF e modelo de urna.

### Comparação entre turnos

Variação do comparecimento por UF entre as seções presentes nos dois turnos, migração de votos por UF e seções presentes em apenas um turno.

### Circunscrição dos números de candidato

O número de um candidato só é único dentro da circunscrição do cargo: nacional (Presidente), estadual (Governador, Senador, deputados) ou municipal (Prefeito, Vereador). As agregações usam essa chave para não misturar candidatos diferentes com o mesmo número.

## Índice de confiança

Média ponderada de sete componentes, de 0 (risco máximo) a 100:

| Componente | Peso |
|---|---:|
| Integridade de hash (C01) | 25 |
| Votos acima do eleitorado (C05) | 20 |
| Aderência a Benford | 15 |
| Impacto de reinícios | 15 |
| Consistência entre turnos | 10 |
| Biometria | 10 |
| Concentração de outliers | 5 |

A implementação está em `compute_confidence_score` (`dashboard/analysis.py`). Cada componente recebe uma nota de 0 a 100 por faixas fixas; o índice é a média dessas notas ponderada pelos pesos acima.

O componente de integridade de hash só recebe nota quando a base passou pela conferência de SHA-512 (ver [Integridade](#integridade)). Se não passou e não há ocorrências C01, ele aparece como "Não verificado", sem nota, e fica fora da média: o índice passa a ser a média ponderada dos seis componentes restantes, dividida pela soma dos pesos deles (75), o que mantém a escala de 0 a 100. É o caso da base de 2022 distribuída, e a página de veredicto mostra uma nota explicando a exclusão. Ocorrências C01 existentes sempre contam, com ou sem conferência completa, porque são evidência concreta. Quando a base foi verificada, o cálculo é o original, com os sete componentes e pesos somando 100.

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
