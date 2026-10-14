# Metodologia

Este documento descreve como o DataUrnas-BR transforma os arquivos públicos da urna eletrônica em indicadores de auditoria. Todas as verificações são determinísticas e podem ser refeitas a partir do código e dos dados do TSE.

## Princípios

1. **Fonte única:** só são usados arquivos publicados pelo TSE. Nenhum dado é corrigido, imputado ou estimado.
2. **Indicador, não conclusão:** cada achado vira uma ocorrência com código e severidade. A severidade expressa a importância de investigar, não a probabilidade de fraude; o [grupo de leitura](#grupos-de-leitura) diz o que o achado pode indicar sobre manipulação.
3. **Falha de leitura não é evidência:** quando um arquivo está ausente ou não pode ser decodificado, o projeto registra que a verificação não foi possível (códigos E01 e E02), sem tratar isso como adulteração.
4. **Reconciliação com o oficial:** a soma dos BUs é comparada com a totalização do TSE. Divergência é reportada; concordância também.

## Grupos de leitura

A severidade de um código diz a prioridade de investigar. O grupo de leitura diz que tipo de conclusão o achado admite. A classificação tem fonte única em `src/dataurnas/dashboard/reference.py` (`GRUPOS`, `ISSUE_CATALOGO` e `INTEGRIDADE_CATEGORIAS`) e aparece no painel e nas tabelas deste documento (coluna **Grupo**).

| Grupo | Critério | Códigos e categorias |
|---|---|---|
| 1. Indício direto de adulteração | Não deveria ocorrer num sistema íntegro; uma única ocorrência exige explicação | C01, C05, A02, A06; em 2026, `hash_diverge`, `assinatura_invalida`, `hash_assinado_ausente` e `arquivo_ausente_tse` |
| 2. Inconsistência a investigar | Há explicações legítimas conhecidas; o achado só ganha sentido com o contexto da seção | A01 (já sem o voto em trânsito), A03 (a troca de urna divide o log), E02, E03, M03; em 2026, `votos_divergem` |
| 3. Operacional ou estatístico | Descreve como o dia de votação transcorreu; sozinho, não é evidência de manipulação | C06, A04, A05, M01, M02, M04, M05, M06, I01 a I06, E01, além das análises agregadas (Benford e outliers) |

Critérios usados nos casos de fronteira:

- **A06** fica no grupo 1 porque, numa mesma eleição, o eleitor vota em todos os cargos na mesma sessão; o comparecimento por cargo é o mesmo em qualquer BU íntegro. A comparação é feita dentro de cada eleição do BU, e por isso o voto em trânsito (que só vale para Presidente, outra eleição no BU) não a afeta.
- **A01** fica no grupo 2: até o desconto do voto em trânsito, todas as ocorrências de 2022 eram explicadas por ele.
- **E01** fica no grupo 3: significa que a verificação não pôde ser feita (arquivo ausente ou ilegível), não que ela falhou.
- **`votos_divergem`** (2026) fica no grupo 2: compara o BU assinado com o BU lido na coleta de resultados, duas leituras do mesmo boletim; a diferença pode vir de versão republicada ou de contingência.
- **`hash_assinado_ausente`** inclui o caso de um conjunto publicado sem `.vsc`. Fica no grupo 1 porque um BU, RDV ou log publicado sem cobertura da assinatura da urna não pode ser autenticado.
- **Benford e outliers** ficam no grupo 3: votos por seção não seguem Benford por natureza e seções atípicas existem em qualquer eleição, de modo que os dois testes têm alta taxa de falso positivo em dados eleitorais.

### O que os arquivos públicos permitem detectar

Os arquivos publicados permitem conferir se o que foi publicado é o que a urna assinou, se cada BU é coerente por dentro e se a soma dos BUs reproduz a totalização oficial. Uma alteração feita depois da assinatura, no caminho até a publicação ou na totalização, aparece no grupo 1 ou na reconciliação.

Eles não alcançam uma manipulação feita dentro da urna antes da assinatura: nesse caso o BU, o RDV e o log já nasceriam coerentes entre si e corretamente assinados. Essa hipótese é tratada por outros mecanismos, fora do alcance do projeto: a inspeção do código-fonte pelas entidades fiscalizadoras, a cerimônia de assinatura digital e lacração dos sistemas, o teste de integridade das urnas no dia da eleição e o Teste Público de Segurança. A conferência voto a voto do RDV com o BU de cada seção está no roadmap (ver o README).

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

| Situação | Código | Severidade | Grupo |
|---|---|---|:---:|
| Hash calculado e igual ao assinado | nenhum | | |
| Hash calculado e diferente do assinado | C01 | crítica | 1 |
| Arquivo assinado ausente ou assinatura ilegível | E01 | informativa | 3 |

A conferência é opcional por ser custosa (`dataurnas analyze batch --hashes`). Nessa conferência (usada em 2022) o projeto **não** verifica a cadeia de certificados nem a assinatura digital em si: verifica que os arquivos publicados correspondem aos hashes que a própria urna assinou. Em 2026 a assinatura também é verificada (ver [Integridade em 2026](#integridade-em-2026)).

A base de 2022 distribuída em `data/parquet` foi compilada sem essa conferência. Por isso a ausência de C01 nessa base não atesta a integridade dos arquivos; para conferir, rode `dataurnas analyze batch --hashes` ou `dataurnas analyze hashes <diretório da seção>` sobre os arquivos brutos, ou recompile com `dataurnas db build --hashes`.

O banco registra se a conferência foi feita na tabela `metadados` (chave `verify_hashes`, `true` ou `false`). `dataurnas db build` grava o valor conforme a opção `--hashes` (padrão: desligada); numa compilação incremental, a base só continua marcada como verificada se a parte anterior também era. `scripts/build_db.py` copia o valor de `metadados.parquet`, quando esse arquivo acompanha os Parquet; sem ele, grava `false`, a menos que a opção `--hashes-verificados` declare que os Parquet vieram de uma compilação verificada. Em bancos antigos, sem a tabela, o painel considera a conferência feita apenas se houver alguma ocorrência C01 ou E01, porque só ela gera esses códigos; caso contrário, trata a base como não verificada.


### Integridade em 2026

Para o 1º turno de 2026 a conferência é feita em todas as seções, numa etapa própria que grava o catálogo em `data/parquet/2026/integridade` (`arquivos_<uf>.parquet`, `secoes.parquet` e `resumo.json`):

1. cada arquivo publicado da seção (`bu.dat`, `rdv.dat`, `log.jez`, `-vota.vsc`, `busa.dat`, imagem do BU) recebe MD5, SHA-256 e SHA-512;
2. o SHA-512 de `bu.dat`, `rdv.dat` e `log.jez` é comparado com o valor assinado no `-vota.vsc` (`hash_confere`); arquivos que a assinatura não cobre ficam com o campo nulo, o que é esperado;
3. a assinatura do `-vota.vsc` é verificada com a chave pública do certificado que o acompanha (`assinatura_valida`), e os dados do certificado (algoritmo, titular, emissor, número de série e SHA-256) ficam registrados para conferência; a validação da cadeia de certificação é feita numa etapa à parte (ver [Consistência dos certificados e cadeia](#consistência-dos-certificados-e-cadeia));
4. o token do `aux.json` (32 bytes em base64url) e a data e hora informadas pelo TSE são registrados, sem comparação, porque o token não é o hash de nenhum arquivo isolado.

MD5 e SHA-256 não fazem parte do mecanismo da urna: ficam no catálogo para facilitar conferências com outras fontes. Uma seção é considerada divergente quando algum SHA-512 difere do assinado, a assinatura é inválida ou os votos não conferem. Um arquivo que a urna assinou e que não aparece na publicação vai para `divergencias.jsonl` (categoria `arquivo_ausente_tse`); um arquivo listado no `aux.json` que responde HTTP 404 fica no catálogo com `disponivel = false` e no registro `ocorrencias_publicacao.jsonl`, sem derrubar a seção. A cobertura é o número de seções verificadas dividido pelas seções instaladas do resultado oficial.

**Resultado (concluído em 14/10/2026):** 499.207 seções verificadas de 499.207 instaladas; 1.497.620 SHA-512 iguais ao assinado e nenhum divergente; 499.207 assinaturas válidas (Ed521 399.222, ECDSA P-521 99.985) e nenhuma inválida; votos do BU assinado iguais aos do BU coletado em todas; nenhum erro pendente. Um RDV assinado e não publicado (MA, município 07846, zona 0074, seção 0228) e 2.658 imagens do BU listadas e indisponíveis, todas em seções com status "Recebida". A auditoria do BU e do log de 2026 não registrou nenhuma ocorrência do grupo 1. O resultado está na página **Integridade dos arquivos (2026)** do painel e no [relatório de integridade](relatorio-integridade-2026.md), que traz também o passo a passo para conferir uma seção à mão.

### Consistência dos certificados e cadeia

> **Concluído.** A coerência dos certificados cobre todas as 499.207 seções verificadas; a validação da cadeia foi concluída na amostra de 5%, sorteio determinístico (24.846 seções). O estado fica em `data/parquet/2026/integridade/certificados_resumo.json` e o detalhe, no [relatório de integridade](relatorio-integridade-2026.md#certificados-das-urnas).

`scripts/ele2026/analisar_certificados.py` confere o certificado de hardware que acompanha cada `-vota.vsc` em três camadas:

1. **Catálogo** (sem rede): distribuição de AC emissora e algoritmo por modelo; unicidade (um certificado, pelo SHA-256 do DER, nunca aparece em urnas diferentes; o par emissor e número de série identifica um único certificado; uma urna não aparece com dois certificados); identidade (o CN `UEAO` + 8 dígitos é igual ao número interno da urna no BU e ao usuário que assinou a parte de hardware); modelo do `.vsc` igual ao do BU.
2. **Certificado completo** (amostra com `--amostra N`, ou todas as seções com `--todas`): validade no dia da eleição (04/10/2026), chave pública não repetida entre urnas, algoritmo da assinatura de hardware igual ao da chave.
3. **Cadeia**: a assinatura do certificado da urna é verificada com a chave pública da AC emissora (ECDSA P-521 com SHA-512 pela biblioteca `cryptography`; Ed521 pela implementação própria em `src/dataurnas/parsers/ed521.py`, conforme os parâmetros da ICP-Brasil). A AC candidata é a de mesmo nome do emissor ou cujo SKI é igual ao AKI do certificado. A partir dela o script sobe a cadeia enquanto encontra o emissor e a assinatura confere; o nível alcançado fica em `nivel_cadeia` (`intermediaria` ou `raiz`).

Os certificados das AC estão em `data/certificados/ac/` (AC URNA, AC UE2020 e AC UE2022), tirados do pacote oficial do TSE com a especificação dos arquivos de assinatura (`formato-arquivos-bu-rdv-ass-digital-v2.zip`, `python/lib/mr_util.py`). Os da AC UE2020 e AC UE2022 conferem byte a byte com o SHA-512 publicado pelo TSE no resumo digital do sistema HOLOCRON de 2026. Os das raízes (AC RAIZ UE, AC RAIZ UE v2) e da AC URNA v2 não estão disponíveis publicamente para download; por isso, hoje, a cadeia é validada **até a AC intermediária**. O SHA-512 oficial desses três arquivos já está no script, que os aceita e sobe até a raiz assim que forem colocados na pasta. Origem, datas e impressões digitais estão em [`data/certificados/README.md`](../data/certificados/README.md).

Resultados em todas as 499.207 seções verificadas: 499.179 certificados distintos (um certificado de urna de apuração do exterior assina 29 BUs do sistema de apuração), nenhuma urna com dois certificados, nenhum certificado em urnas diferentes, pares emissor e número de série tão distintos quanto os certificados, CN no padrão `UEAO` + 8 dígitos em todas e igual ao número interno da urna registrado na carga do BU em 499.193 (as 14 restantes, com hash e assinatura válidos, estão listadas no relatório); UE2013 e UE2015 com AC URNA e ECDSA P-521, UE2020 com AC UE2020 e UE2022 com AC UE2022, ambos com Ed521, sem exceção. **Amostra da cadeia:** `--todas --fracao 0.05` escolhe as seções cujo SHA-256 da chave `uf/cd_mun/zona/secao` fica abaixo do limiar correspondente a 5%, o que dá uma amostra determinística e proporcional em todas as UFs; nas 24.846 seções sorteadas, todos os certificados de urna estavam válidos no dia da eleição e tiveram a assinatura conferida pela AC emissora, sem nenhuma falha de rede.

**Observação sobre a AC URNA.** O certificado publicado da AC URNA tem validade até 18/07/2026, antes da eleição, e há certificado de urna UE2013 emitido em 03/08/2026 cuja assinatura confere com a chave dessa AC. O script registra os dois fatos como observação (`ac_emissora_fora_da_validade_no_dia` e `certificado_emitido_fora_da_validade_da_ac`; no modo completo, `ac_valida_na_eleicao = false`). A explicação mais provável é um certificado renovado da AC URNA, com a mesma chave, que não foi publicado. É um ponto a esclarecer com o TSE, não indício de adulteração: a assinatura de cada certificado de urna confere com a chave da AC.

**Modo completo.** `python scripts/ele2026/analisar_certificados.py --todas` lê o `-vota.vsc` de cada seção com status `ok` de `secoes_2026.parquet`, em fluxo e sem gravar o arquivo bruto: usa o hash já conhecido e o nome padrão do arquivo, e recorre ao `-aux.json` quando falta o hash ou o caminho direto responde 404. A concorrência padrão é 8, com taxa adaptativa que reduz ao receber 429; a verificação Ed521 (cerca de 0,2 s por certificado em Python puro) roda num pool de processos. Cada lote vira uma parte em `certificados_partes/`, e uma nova execução retoma das seções que faltam. A saída é `certificados.parquet`, uma linha por seção (`uf`, `cd_mun`, `zona`, `secao`, `cert_sha256`, `emissor`, `serial`, `not_before`, `not_after`, `valido_na_eleicao`, `cadeia_ok`, `nivel_cadeia`, `motivo` e campos auxiliares), e o bloco `todas` de `certificados_resumo.json`, com a cobertura e a situação (`em andamento` até cobrir todas as seções ou a amostra pedida com `--fracao`; ao terminar a amostra de 5%, `concluído (amostra de 5%)`).

**Assinatura de software (CEPESC).** Cada `.vsc` traz também uma assinatura de software (algoritmo 3, usuário SEVIN) feita com o algoritmo de governo do CEPESC, que não é publicado. Ela é lida, mas não pode ser verificada com informação pública; a conferência do projeto se apoia na assinatura de hardware de cada urna.

## Consistência do BU

| Código | Severidade | Regra | Grupo |
|---|---|---|:---:|
| C05 | crítica | Para algum cargo, total de votos maior que os eleitores aptos da seção | 1 |
| A02 | alta | Votos computados maiores que o comparecimento | 1 |
| A06 | alta | Comparecimento diferente entre cargos da mesma seção | 1 |
| A01 | alta | Eleitores aptos diferentes entre eleições registradas na mesma urna | 2 |
| I06 | informativa | Urna de reserva ou tipo diferente de `secao` | 3 |
| E02 | média | BU não decodificável, inclusive `tipoVoto` ausente ou desconhecido; a seção sai dos totais | 2 |

O caso E02 merece nota: versões anteriores assumiam "nominal" quando o tipo de voto não era reconhecido, o que poderia atribuir votos a candidatos indevidamente. Agora o BU é rejeitado e a seção é listada para conferência manual.

## Log da urna

O log é extraído em memória, com limite de tamanho descompactado, e as linhas são convertidas em eventos.

- **Abertura:** primeira ocorrência de "Urna pronta para receber votos" na data do turno.
- **Encerramento:** "Início do Encerramento".
- **Reinícios:** cada abertura adicional no mesmo dia conta como um reinício (C06: severidade média com 1, alta com 2 ou mais).
- **Filtro por turno:** no 2º turno de 2022 o log acumula os eventos do 1º. Só são considerados eventos da data do turno (02/10/2022 ou 30/10/2022).

| Código | Severidade | Regra (horários de Brasília convertidos para o fuso local) | Grupo |
|---|---|---|:---:|
| M01 | média | Abertura antes das 7h, mais de 1 h antes do horário oficial | 3 |
| A04 | alta | Abertura depois das 8h30 (tolerância de 30 min) | 3 |
| A05 | alta | Encerramento antes das 17h | 3 |
| M02 | média | Encerramento depois das 22h | 3 |
| M03 | média | Log com mais de 100 entradas e sem evento de abertura | 2 |
| C06 | média ou alta | Reinícios durante a votação (ver acima) | 3 |
| M04 | média | Mais de 10 erros | 3 |
| M05 | média | Ajustes de hora registrados | 3 |
| I01 | informativa | Eventos de substituição ou contingência | 3 |
| I02 | informativa | Mais de 20 alertas de mesário | 3 |
| A03 | alta | Votos contados no log diferem do comparecimento do BU em mais de 2 | 2 |
| E03 | informativa | Encerramento registrado antes da abertura (duração negativa) | 2 |

### Fusos

| UF | Fuso | Diferença para Brasília |
|---|---|---|
| AC | UTC-5 | -2 h |
| AM, MT, MS, RO, RR | UTC-4 | -1 h |
| Demais | UTC-3 | 0 |

O fuso é resolvido por município quando há exceção conhecida (`analyzer/timezones.py`): os municípios do oeste do Amazonas (Atalaia do Norte, Benjamin Constant, Eirunepé, Envira, Guajará, Ipixuna e Tabatinga) seguem UTC-5, e Fernando de Noronha (PE) segue UTC-2. A base de 2022 distribuída foi compilada antes dessas exceções e usa o fuso da UF em todas as seções; elas passam a valer numa recompilação a partir dos dados brutos.

## Indicadores estatísticos por seção

| Código | Severidade | Regra | Grupo |
|---|---|---|:---:|
| I03 | informativa | Nulos acima de 15% dos votos de um cargo | 3 |
| I04 | informativa | Brancos acima de 10% dos votos de um cargo | 3 |
| I05 | informativa | Abstenção acima de 40% | 3 |
| M06 | média | Mais de 30% dos eleitores liberados sem biometria | 3 |

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
