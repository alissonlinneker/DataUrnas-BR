# Perguntas frequentes

Respostas curtas para as dúvidas mais comuns sobre o DataUrnas-BR. Os detalhes técnicos estão em [metodologia.md](metodologia.md), [arquitetura.md](arquitetura.md) e [dados-2026.md](dados-2026.md).

## O que o projeto faz?

Baixa os arquivos públicos da urna eletrônica que o TSE divulga (Boletim de Urna, log e arquivo de assinatura), decodifica cada um deles, refaz a soma dos votos a partir dos dados brutos e aplica verificações determinísticas de integridade, consistência, log e estatística. Cada achado vira uma ocorrência com código, severidade e descrição. Os resultados ficam em Parquet e podem ser explorados no painel.

## O que o projeto prova?

Prova apenas o que pode ser conferido nos arquivos publicados:

- que a soma dos BUs decodificados confere, ou não, com a totalização oficial divulgada pelo TSE;
- que cada BU é internamente coerente (votos, comparecimento e eleitores aptos);
- que os eventos do log de cada urna têm os horários e as contagens registrados;
- quando a conferência de hashes é executada, que os arquivos publicados correspondem aos hashes que a própria urna assinou.

## O que o projeto não prova?

- **Não prova fraude nem ausência de fraude.** Uma ocorrência é um indicador para investigar, e a severidade expressa a prioridade dessa investigação, não a probabilidade de irregularidade.
- **Não audita o software da urna** nem os sistemas do TSE. O projeto trabalha só com os arquivos que a urna produz.
- **Não valida a cadeia de certificados até a raiz.** Em 2022 a conferência de integridade compara hashes. Em 2026 também verifica a assinatura de cada urna com o certificado que a acompanha e confere esse certificado com a autoridade certificadora intermediária que o emitiu, mas não chega à raiz, cujo certificado não está publicado (ver abaixo).
- **Não identifica eleitores.** Nenhum arquivo usado contém o voto associado a uma pessoa.
- **Não substitui a totalização oficial.** O índice de confiança do painel resume indicadores do projeto e depende dos pesos escolhidos.

## Todos os códigos indicam fraude?

Não. Cada código é classificado em um de três grupos de leitura, conforme o que ele pode dizer sobre manipulação:

1. **Indício direto de adulteração** (C01, C05, A02, A06 e, em 2026, hash divergente, assinatura inválida, arquivo publicado sem hash assinado e arquivo assinado ausente da publicação): não deveria ocorrer num sistema íntegro, e uma única ocorrência exige explicação. Mesmo assim é um indício a apurar, não uma prova.
2. **Inconsistência a investigar** (A01, A03, E02, E03, M03 e, em 2026, votos do BU que não conferem com a coleta): há explicações legítimas conhecidas, como a troca de urna, que divide o log entre equipamentos (A03). Só o contexto da seção permite concluir algo.
3. **Operacional ou estatístico** (C06, A04, A05, M01, M02, M04, M05, M06, I01 a I06, E01, Benford e outliers): descreve como o dia de votação transcorreu. Reinícios, atrasos, falhas de biometria e abstenção alta não são, sozinhos, evidência de manipulação, e os testes estatísticos têm alta taxa de falso positivo em dados eleitorais.

Os arquivos públicos também têm um limite: mostram se o que foi publicado é o que a urna assinou e se os números são coerentes, mas não alcançam uma manipulação feita dentro da urna antes da assinatura. Essa hipótese é coberta por outros mecanismos (inspeção do código-fonte, cerimônia de assinatura digital e lacração, teste de integridade no dia da eleição e Teste Público de Segurança). Os critérios estão em [metodologia.md](metodologia.md#grupos-de-leitura); no painel, o grupo aparece ao lado de cada ocorrência e pode ser usado como filtro.

## Os certificados das urnas são confiáveis?

O que dá para conferir com dados públicos foi conferido, e não apareceu falha de assinatura nem de cadeia. A coerência dos certificados cobre todas as 499.207 seções verificadas; a validação da cadeia foi **concluída na amostra de 5%, sorteio determinístico** (24.846 seções de todas as UFs). Os números estão no [relatório de integridade](relatorio-integridade-2026.md#certificados-das-urnas).

- **Um certificado por urna.** Nenhuma urna aparece com dois certificados e nenhum certificado aparece em urnas diferentes. São 499.179 certificados distintos para 499.207 seções porque um certificado de urna de apuração do exterior assina 29 BUs do sistema de apuração (votação por cédula).
- **O certificado é da urna da seção.** O nome no certificado (`UEAO` + 8 dígitos) segue o padrão em todas as seções e é igual ao número interno da urna registrado na carga do BU em 499.193. Nas 14 restantes, o hash e a assinatura conferem; a explicação provável é troca de equipamento depois da carga, e elas estão listadas no relatório para confirmação com o TSE.
- **Emissor e algoritmo coerentes com o modelo.** UE2013 e UE2015 têm certificado da AC URNA com ECDSA P-521; UE2020 e UE2022, das AC UE2020 e AC UE2022 com Ed521, sem exceção.
- **Emitido pela AC indicada.** Nas 24.846 seções da amostra, a assinatura de todos os certificados de urna conferiu com a chave pública da AC emissora, e todos estavam válidos no dia da eleição.

Os limites: a cadeia é conferida **até a AC intermediária**. Os certificados das raízes (AC RAIZ UE e AC RAIZ UE v2) e da AC URNA v2 não estão disponíveis publicamente para download, então não dá para fechar a cadeia até a raiz. Os certificados intermediários usados estão em [`data/certificados/`](../data/certificados/README.md), com a origem; os da AC UE2020 e AC UE2022 conferem byte a byte com o hash publicado pelo TSE.

Há uma observação a esclarecer com o TSE: o certificado publicado da AC URNA venceu em 18/07/2026, antes da eleição, e há certificado de urna emitido em 03/08/2026 que confere com a chave dessa mesma AC. A explicação mais provável é que a AC URNA tenha um certificado renovado, com a mesma chave, que não foi publicado. Isso não é indício de adulteração: a assinatura de cada certificado de urna confere com a chave da AC, e a assinatura de cada arquivo confere com o certificado da urna.

## E a assinatura de software (CEPESC)?

Cada arquivo de assinatura (`.vsc`) tem duas assinaturas: a de **hardware**, feita pela própria urna com a chave do seu certificado (Ed521 ou ECDSA P-521), e a de **software**, feita com o algoritmo do CEPESC (Centro de Pesquisa e Desenvolvimento para a Segurança das Comunicações). O algoritmo do CEPESC é de uso governamental e não é publicado, então essa assinatura não pode ser verificada por quem só tem os arquivos públicos. O projeto lê a assinatura de software, mas a conferência de integridade se apoia na de hardware, que é verificável e cobre o BU, o RDV e o log.

## Como reproduzir os resultados?

Com Python 3.11 ou superior:

```bash
git clone https://github.com/alissonlinneker/DataUrnas-BR.git
cd DataUrnas-BR
make install      # cria o .venv e instala o pacote com painel e testes
make build-db     # reconstrói o DuckDB a partir dos Parquet versionados
make dashboard    # abre o painel em http://localhost:8501
```

Para refazer tudo a partir dos arquivos do TSE, use `dataurnas download state <uf>` (ou os scripts `scripts/download_full*.py`) e depois `dataurnas db build`. O download completo de 2022 ocupa cerca de 181 GB e leva muitas horas; os limites de concorrência e de taxa são propositalmente conservadores para não sobrecarregar o servidor público.

Para 2026: `make fetch-2026` coleta o resultado oficial e os BUs por seção, e `make reconcile-2026` compara a soma dos BUs com o resultado oficial de cada UF.

## Qual a diferença entre BU e RDV?

| | Boletim de Urna (BU) | Registro Digital do Voto (RDV) |
|---|---|---|
| Conteúdo | Totais da seção: votos por candidato, brancos, nulos, eleitores aptos, comparecimento, biometria e horários | Cada voto registrado individualmente, em ordem embaralhada, sem identificação do eleitor |
| Finalidade | É o documento usado na totalização | Permite recontar os votos da seção de forma independente |
| Uso no projeto | Base de todas as somas, verificações de consistência e reconciliações | Ainda não utilizado; as especificações ASN.1 estão em `spec/` para uso futuro |

## O que são nulos técnicos?

São votos digitados para um número que não corresponde a candidato apto na totalização. O BU registra esses votos como `nominal` para o número digitado; o TSE os contabiliza como nulos técnicos. Em 2026, os votos no número 28 aparecem nos BUs como nominais e entram na totalização como nulos técnicos, que somaram 5.246 no Brasil. Por isso a soma de todos os votos nominais dos BUs de uma UF supera o total oficial de votos nominais exatamente por esse número, e a reconciliação filtra pelos números de `candidatos.parquet`. Os detalhes estão em [dados-2026.md](dados-2026.md#nulos-técnicos).

## Qual é a cobertura dos dados?

- **2022 (Presidente, 1º e 2º turnos):** 941.987 seções das 27 UFs nos dois turnos, com BU, log e assinatura decodificados. Seções do exterior não fazem parte dessa base.
- **2026 (Presidente, 1º turno):** o resultado agregado oficial do Brasil, das 27 UFs, do exterior e de 5.757 municípios está completo, e os BUs de todas as 499.207 seções instaladas foram coletados e somados (diferença zero nas 28 UFs). A integridade dos arquivos (SHA-512 e assinatura de cada urna) e a auditoria do BU e do log também cobrem as 499.207 seções; a validação da cadeia de certificados, uma amostra determinística de 5%.

Seções sem BU decodificável (código E02) ficam fora dos totais e são listadas para conferência manual. Falhas de leitura são registradas como falhas de verificação (códigos E), nunca como evidência de adulteração.

## A ausência de ocorrências C01 em 2022 significa que os hashes foram conferidos?

Não. A base de 2022 distribuída nos Parquet foi compilada sem a conferência de hashes, que é opcional por ser custosa. Para conferir, rode `dataurnas analyze batch --hashes` ou `dataurnas analyze hashes <diretório da seção>` sobre os arquivos brutos.

## A urna usa MD5? Por que o catálogo de 2026 tem MD5?

A urna não usa MD5. O mecanismo oficial é o SHA-512: a urna calcula o SHA-512 do BU, do RDV e do log e grava esses valores num arquivo de assinatura (`.vsc`), assinado com a chave da própria urna. O projeto recalcula o SHA-512 dos arquivos publicados pelo TSE, compara com os valores assinados e verifica a assinatura. O catálogo de 2026 guarda também MD5 e SHA-256 de cada arquivo apenas por conveniência, para facilitar a comparação com outras fontes que usem esses algoritmos; eles não entram na conclusão. Os resultados estão no [relatório de integridade](relatorio-integridade-2026.md).

## Qual foi o resultado da verificação de integridade de 2026?

Nas 499.207 seções instaladas, os 1.497.620 SHA-512 de BU, RDV e log recalculados a partir dos arquivos publicados são iguais aos que as urnas assinaram: **nenhum divergente (C01)**. As 499.207 assinaturas de urna são válidas, nenhuma inválida, e os votos de cada BU assinado são os mesmos do BU lido na coleta. A auditoria do BU e do log não registrou nenhuma ocorrência do grupo 1.

Ficaram dois pontos de publicação, sem divergência de conteúdo: um RDV que a urna assinou e o TSE não publicou (seção 0228 da zona 0074, Lagoa Grande do Maranhão, MA) e 2.658 imagens do BU listadas no `aux.json` que o servidor responde com HTTP 404, todas em seções com status "Recebida". São lacunas a informar ao TSE, não evidência de adulteração; a relação está em [relatorio-tse-ocorrencias-2026.md](relatorio-tse-ocorrencias-2026.md). O catálogo com os hashes de cada um dos 1.999.485 arquivos está nos anexos da versão [v0.2.1](https://github.com/alissonlinneker/DataUrnas-BR/releases/tag/v0.2.1).

## Reinícios de urna indicam problema?

Não necessariamente. Um reinício durante a votação (código C06) pode ter causas operacionais, como falha de energia ou procedimento de contingência. O projeto conta os reinícios e testa se a distribuição de votos difere entre seções com e sem reinício; o resultado desse teste está no painel, junto com o tamanho do efeito (V de Cramér).

## A Lei de Benford serve para detectar fraude em eleições?

Não de forma isolada. Votos por seção não seguem Benford por natureza, porque o tamanho das seções é limitado. O projeto usa o teste para comparar candidatos, UFs e turnos entre si e reporta o V de Cramér como medida de efeito, já que, com centenas de milhares de seções, o qui-quadrado rejeita a hipótese nula com qualquer desvio mínimo.

## Encontrei um número diferente do oficial. O que fazer?

Abra uma issue com a UF, o município, a zona, a seção e o turno, o comando ou a página do painel usada e o valor esperado. Se a diferença vier do código do projeto, ela será corrigida e registrada no [CHANGELOG](../CHANGELOG.md). Veja também o [guia de contribuição](../CONTRIBUTING.md).
