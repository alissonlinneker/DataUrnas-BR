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
- **Não valida a cadeia de certificados** nem a assinatura digital em si; a conferência de integridade compara hashes.
- **Não identifica eleitores.** Nenhum arquivo usado contém o voto associado a uma pessoa.
- **Não substitui a totalização oficial.** O índice de confiança do painel resume indicadores do projeto e depende dos pesos escolhidos.

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
- **2026 (Presidente, 1º turno):** o resultado agregado oficial do Brasil, das 27 UFs, do exterior e de 5.757 municípios está completo. A coleta dos BUs por seção é feita UF a UF; `make reconcile-2026` mostra quais UFs já foram coletadas e se a soma confere.

Seções sem BU decodificável (código E02) ficam fora dos totais e são listadas para conferência manual. Falhas de leitura são registradas como falhas de verificação (códigos E), nunca como evidência de adulteração.

## A ausência de ocorrências C01 em 2022 significa que os hashes foram conferidos?

Não. A base de 2022 distribuída nos Parquet foi compilada sem a conferência de hashes, que é opcional por ser custosa. Para conferir, rode `dataurnas analyze batch --hashes` ou `dataurnas analyze hashes <diretório da seção>` sobre os arquivos brutos.

## Reinícios de urna indicam problema?

Não necessariamente. Um reinício durante a votação (código C06) pode ter causas operacionais, como falha de energia ou procedimento de contingência. O projeto conta os reinícios e testa se a distribuição de votos difere entre seções com e sem reinício; o resultado desse teste está no painel, junto com o tamanho do efeito (V de Cramér).

## A Lei de Benford serve para detectar fraude em eleições?

Não de forma isolada. Votos por seção não seguem Benford por natureza, porque o tamanho das seções é limitado. O projeto usa o teste para comparar candidatos, UFs e turnos entre si e reporta o V de Cramér como medida de efeito, já que, com centenas de milhares de seções, o qui-quadrado rejeita a hipótese nula com qualquer desvio mínimo.

## Encontrei um número diferente do oficial. O que fazer?

Abra uma issue com a UF, o município, a zona, a seção e o turno, o comando ou a página do painel usada e o valor esperado. Se a diferença vier do código do projeto, ela será corrigida e registrada no [CHANGELOG](../CHANGELOG.md). Veja também o [guia de contribuição](../CONTRIBUTING.md).
