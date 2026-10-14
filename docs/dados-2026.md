# Dados de 2026: Presidente, 1º turno

Eleição de 04/10/2026. Identificadores no TSE: ciclo `ele2026`, eleição `6257`, pleito `3220`, cargo Presidente (código 1). Os BUs de 2026 usam a especificação ASN.1 v2 (`spec/v2`), com arquivos `-bu.dat` e assinatura `-vota.vsc`.

Todos os arquivos ficam em `data/parquet/2026/` e são gravados em Parquet com compressão ZSTD. Os valores agregados são cópia fiel do que o TSE publica; o projeto não altera nenhum número oficial.

## Arquivos

| Arquivo | Conteúdo | Origem | Situação |
|---|---|---|---|
| `resumo_br.json` | Totais do Brasil, lista de candidatos, checagens de soma e estatísticas da coleta | `fetch_resultados.py` | Completo |
| `candidatos.parquet` | 12 candidatos, vices, partidos, agremiações e resultado nacional | `fetch_resultados.py` | Completo |
| `resultado_uf.parquet` | 28 linhas: 27 UFs e exterior (`zz`) | `fetch_resultados.py` | Completo |
| `resultado_municipio.parquet` | 5.757 municípios, incluindo cidades do exterior | `fetch_resultados.py` | Completo |
| `secoes_2026.parquet` | 517.179 linhas, uma por seção: metadados do `aux.json` e campos do BU (499.207 com BU, 17.931 agregadas, 41 não instaladas) | `fetch_secoes.py` | Completo |
| `votos_presidente_2026.parquet` | 3.800.511 linhas de votos de Presidente por seção e candidato | `fetch_secoes.py` | Completo |
| `secoes_parts/` | Partes intermediárias da coleta, consolidadas nos dois arquivos acima | `fetch_secoes.py` | Temporário |
| `secoes_checkpoint.txt` | Seções já gravadas, usado para retomar a coleta | `fetch_secoes.py` | Temporário |
| `secoes_erros.txt` | Seções com erro na última execução (refeitas na próxima) | `fetch_secoes.py` | Temporário |

## Como os dados são obtidos

1. `fetch_resultados.py` lê os arquivos de resultado do TSE para o Brasil, cada UF e cada município, e grava os três primeiros Parquet mais `resumo_br.json`. Ao final confere que a soma dos votos válidos por UF e por município é igual ao total nacional.
2. `fetch_secoes.py` percorre a configuração de seções de cada UF. Para cada seção lê o `aux.json`, escolhe o hash totalizado, baixa o BU (da urna ou, na falta, do Sistema de Apuração) e, opcionalmente, o arquivo de assinatura para obter o modelo da urna. O BU é decodificado em memória por um pool de processos; nada é gravado em `data/raw`. Seções agregadas e não instaladas recebem uma linha com o `status` correspondente.
3. `reconcile.py` compara, por UF, a soma dos BUs com `resultado_uf.parquet`: votos por candidato, brancos, nulos, comparecimento, votos nominais e número de seções. Sai com código 1 se houver divergência.

## Totais oficiais do 1º turno

| Métrica | Valor |
|---|---:|
| Eleitorado apto | 158.745.502 |
| Comparecimento | 125.275.835 (78,92%) |
| Abstenção | 33.469.244 (21,08%) |
| Votos válidos | 119.300.788 |
| Brancos | 2.300.798 |
| Nulos (inclui 5.246 técnicos) | 3.674.249 |
| Seções | 499.248 totalizadas, 41 não instaladas |

Fonte: TSE, totalização de 05/10/2026 às 12:51:05.

## Relações entre os arquivos

- `resultado_uf.uf` e `resultado_municipio.uf` usam a mesma UF em minúsculas.
- As colunas `v_<número>` dos resultados correspondem a `candidatos.numero`.
- A chave de seção é `(uf, cd_mun, zona, secao)`, comum a `secoes_2026` e `votos_presidente_2026`.
- `secoes_2026.cd_mun` liga a seção a `resultado_municipio.cd_mun`.

Exemplo com DuckDB:

```sql
-- Votos do candidato 22 por UF: soma dos BUs x total oficial
SELECT s.uf,
       SUM(v.votos)      AS votos_bu,
       ANY_VALUE(r.v_22) AS votos_oficial
FROM 'data/parquet/2026/votos_presidente_2026.parquet' v
JOIN 'data/parquet/2026/secoes_2026.parquet' s USING (uf, cd_mun, zona, secao)
JOIN 'data/parquet/2026/resultado_uf.parquet' r ON r.uf = s.uf
WHERE v.tipo_voto = 'nominal' AND v.numero = 22
GROUP BY s.uf
ORDER BY s.uf;
```

### Nulos técnicos

O BU registra como voto `nominal` os votos digitados para o número 28, que não figura entre os candidatos do resultado. Na totalização, o TSE contabiliza esses votos como **nulos técnicos** (`votos_nulos_tecnicos`). Por isso a soma de todos os votos `nominal` dos BUs de uma UF supera `votos_nominais` oficial exatamente pelo número de nulos técnicos (por exemplo, 23 no Acre e 123 no exterior). Para comparar com o oficial, filtre pelos números de `candidatos.parquet`, como faz `reconcile.py`.

Enquanto a coleta não termina, a consulta só faz sentido para as UFs completas; use `reconcile.py` para saber quais estão fechadas.

## Esquemas

Tipos conforme lidos dos próprios arquivos com DuckDB.

### `candidatos.parquet`

| Coluna | Tipo | Descrição |
|---|---|---|
| `numero` | BIGINT | Número do candidato |
| `sq_candidato` | VARCHAR | Sequencial do candidato no TSE |
| `nome` | VARCHAR | Nome civil |
| `nome_urna` | VARCHAR | Nome de urna |
| `data_nascimento` | VARCHAR | Data de nascimento (DD/MM/AAAA) |
| `partido_numero` | BIGINT | Número do partido |
| `partido_sigla` | VARCHAR | Sigla do partido |
| `partido_nome` | VARCHAR | Nome do partido |
| `federacao_numero` | BIGINT | Número da federação, quando houver |
| `agremiacao_tipo` | VARCHAR | `isolado`, `coligacao` ou `federacao` |
| `agremiacao_nome` | VARCHAR | Nome da coligação ou federação |
| `agremiacao_composicao` | VARCHAR | Partidos que compõem a agremiação |
| `vice_nome` | VARCHAR | Nome civil do vice |
| `vice_nome_urna` | VARCHAR | Nome de urna do vice |
| `vice_partido` | VARCHAR | Partido do vice |
| `vice_sq_candidato` | VARCHAR | Sequencial do vice |
| `votos` | BIGINT | Votos do candidato no Brasil |
| `pct_validos` | DOUBLE | Percentual dos votos válidos, como publicado |
| `situacao` | VARCHAR | Situação divulgada (`2º turno`, `Não eleito`) |
| `eleito` | BOOLEAN | Marcador do TSE (verdadeiro também para quem segue ao 2º turno) |
| `destinacao_voto` | VARCHAR | Destinação do voto (`Válido`) |
| `ordem` | BIGINT | Ordem de apresentação no resultado |

### `resultado_uf.parquet`

| Coluna | Tipo | Descrição |
|---|---|---|
| `uf` | VARCHAR | UF em minúsculas (`zz` = exterior) |
| `secoes_total` | BIGINT | Seções previstas |
| `secoes_totalizadas` | BIGINT | Seções totalizadas |
| `secoes_nao_totalizadas` | BIGINT | Seções não totalizadas |
| `secoes_instaladas` | BIGINT | Seções instaladas |
| `secoes_nao_instaladas` | BIGINT | Seções não instaladas |
| `eleitorado` | BIGINT | Eleitorado apto |
| `eleitorado_secoes_totalizadas` | BIGINT | Eleitorado das seções totalizadas |
| `comparecimento` | BIGINT | Comparecimento |
| `abstencao` | BIGINT | Abstenção |
| `pct_comparecimento` | DOUBLE | Percentual de comparecimento |
| `pct_abstencao` | DOUBLE | Percentual de abstenção |
| `votos_total` | BIGINT | Total de votos |
| `votos_validos` | BIGINT | Votos válidos |
| `votos_nominais` | BIGINT | Votos nominais |
| `votos_legenda` | BIGINT | Votos de legenda (zero para Presidente) |
| `votos_brancos` | BIGINT | Votos em branco |
| `votos_nulos` | BIGINT | Votos nulos |
| `votos_nulos_tecnicos` | BIGINT | Nulos técnicos |
| `votos_nulos_total` | BIGINT | Nulos mais nulos técnicos |
| `votos_anulados_apuracao_separada` | BIGINT | Votos anulados com apuração em separado |
| `pct_brancos` | DOUBLE | Percentual de brancos |
| `pct_nulos` | DOUBLE | Percentual de nulos (total) |
| `data_totalizacao` | VARCHAR | Data da totalização |
| `hora_totalizacao` | VARCHAR | Hora da totalização |
| `v_<número>` | BIGINT | Votos de cada candidato (`v_22`, `v_13`, ...) |

### `resultado_municipio.parquet`

| Coluna | Tipo | Descrição |
|---|---|---|
| `uf` | VARCHAR | UF em minúsculas (`zz` = exterior) |
| `cd_mun` | VARCHAR | Código do município no TSE |
| `cd_ibge` | VARCHAR | Código IBGE (nulo no exterior) |
| `nome` | VARCHAR | Nome do município |
| `capital` | BOOLEAN | Capital da UF |
| `secoes_total` | BIGINT | Seções previstas |
| `secoes_totalizadas` | BIGINT | Seções totalizadas |
| `secoes_nao_totalizadas` | BIGINT | Seções não totalizadas |
| `secoes_instaladas` | BIGINT | Seções instaladas |
| `secoes_nao_instaladas` | BIGINT | Seções não instaladas |
| `eleitorado` | BIGINT | Eleitorado apto |
| `eleitorado_secoes_totalizadas` | BIGINT | Eleitorado das seções totalizadas |
| `comparecimento` | BIGINT | Comparecimento |
| `abstencao` | BIGINT | Abstenção |
| `pct_comparecimento` | DOUBLE | Percentual de comparecimento |
| `pct_abstencao` | DOUBLE | Percentual de abstenção |
| `votos_total` | BIGINT | Total de votos |
| `votos_validos` | BIGINT | Votos válidos |
| `votos_nominais` | BIGINT | Votos nominais |
| `votos_legenda` | BIGINT | Votos de legenda (zero para Presidente) |
| `votos_brancos` | BIGINT | Votos em branco |
| `votos_nulos` | BIGINT | Votos nulos |
| `votos_nulos_tecnicos` | BIGINT | Nulos técnicos |
| `votos_nulos_total` | BIGINT | Nulos mais nulos técnicos |
| `votos_anulados_apuracao_separada` | BIGINT | Votos anulados com apuração em separado |
| `pct_brancos` | DOUBLE | Percentual de brancos |
| `pct_nulos` | DOUBLE | Percentual de nulos (total) |
| `data_totalizacao` | VARCHAR | Data da totalização |
| `hora_totalizacao` | VARCHAR | Hora da totalização |
| `v_<número>` | BIGINT | Votos de cada candidato (`v_22`, `v_13`, ...) |

### `secoes_2026.parquet`

| Coluna | Tipo | Descrição |
|---|---|---|
| `uf` | VARCHAR | UF em minúsculas (`zz` = exterior) |
| `cd_mun` | VARCHAR | Código do município no TSE |
| `nm_mun` | VARCHAR | Nome do município |
| `zona` | VARCHAR | Zona eleitoral (4 dígitos) |
| `secao` | VARCHAR | Seção (4 dígitos) |
| `status` | VARCHAR | `ok`, `agregada`, `nao_instalada`, `sem_aux` ou `sem_bu` |
| `secao_principal` | VARCHAR | Seção que recebeu os eleitores (quando agregada) |
| `secoes_agregadas` | VARCHAR | Seções agregadas a esta |
| `st_secao` | VARCHAR | Situação da seção no `aux.json` |
| `hash` | VARCHAR | Hash da urna escolhida no `aux.json` |
| `st_hash` | VARCHAR | Situação do hash (`Totalizado`) |
| `n_hashes` | SMALLINT | Quantidade de hashes (mais de um indica substituição) |
| `dt_recebimento` | VARCHAR | Data de recebimento pelo TSE |
| `hr_recebimento` | VARCHAR | Hora de recebimento pelo TSE |
| `spec_version` | VARCHAR | Versão da spec ASN.1 usada (`v2`) |
| `municipio_bu` | INTEGER | Município declarado no BU |
| `zona_bu` | INTEGER | Zona declarada no BU |
| `secao_bu` | INTEGER | Seção declarada no BU |
| `local_votacao` | INTEGER | Local de votação |
| `data_hora_emissao` | VARCHAR | Emissão do BU (AAAAMMDDTHHMMSS) |
| `hora_abertura` | VARCHAR | Abertura registrada no BU |
| `hora_encerramento` | VARCHAR | Encerramento registrado no BU |
| `tipo_urna` | VARCHAR | `secao`, `reservaSecao`, `contingencia` etc. |
| `versao_votacao` | VARCHAR | Versão do software de votação |
| `numero_interno_urna` | BIGINT | Número interno da urna |
| `codigo_carga` | VARCHAR | Código de carga da urna |
| `qtd_codigos_carga` | SMALLINT | Quantidade de códigos de carga no histórico |
| `fase` | VARCHAR | Fase do BU (`oficial`) |
| `modelo_urna_cod` | SMALLINT | Código do modelo lido do arquivo de assinatura |
| `modelo_urna` | VARCHAR | Modelo (`UE2013` a `UE2022`) |
| `aptos` | INTEGER | Eleitores aptos (Presidente) |
| `aptos_secao` | INTEGER | Aptos do caderno da seção |
| `aptos_tte` | INTEGER | Aptos por transferência temporária |
| `comparecimento` | INTEGER | Comparecimento |
| `comparecimento_bu` | INTEGER | Comparecimento geral do BU |
| `comp_sem_biometria` | INTEGER | Comparecimento sem biometria |
| `habilitados_biometria` | INTEGER | Habilitados por biometria |
| `habilitados_biografia` | INTEGER | Habilitados por dados biográficos |
| `votos_nominais` | INTEGER | Votos nominais |
| `votos_legenda` | INTEGER | Votos de legenda (zero para Presidente) |
| `votos_brancos` | INTEGER | Votos em branco |
| `votos_nulos` | INTEGER | Votos nulos |
| `votos_total` | INTEGER | Total de votos |
| `tem_presidente` | BOOLEAN | BU contém o cargo de Presidente |
| `origem_bu` | VARCHAR | `bu` (urna) ou `busa` (Sistema de Apuração); nulo nas partes coletadas antes da criação do campo |

### `votos_presidente_2026.parquet`

| Coluna | Tipo | Descrição |
|---|---|---|
| `uf` | VARCHAR | UF em minúsculas (`zz` = exterior) |
| `cd_mun` | VARCHAR | Código do município no TSE |
| `zona` | VARCHAR | Zona eleitoral (4 dígitos) |
| `secao` | VARCHAR | Seção (4 dígitos) |
| `tipo_voto` | VARCHAR | `nominal`, `branco`, `nulo` ou `legenda` |
| `numero` | INTEGER | Número digitado (nulo para branco e nulo) |
| `partido` | INTEGER | Número do partido (nulo para branco e nulo) |
| `votos` | INTEGER | Quantidade de votos na seção para o tipo e o número |


## Recontagem do RDV e linha do tempo do log

`scripts/ele2026/fetch_rdv.py` baixa em memória, para cada seção com RDV publicado, o `-rdv.dat`, o `-bu.dat` e o `-log.jez` do mesmo conjunto de arquivos (nomes, diretório e SHA-512 vêm do catálogo de integridade `arquivos_<uf>.parquet`; com `--fonte aux`, do `aux.json`). Confere o SHA-512 de cada arquivo com o catálogo, reconta o RDV cargo a cargo e compara com o BU, e mede no log o horário de cada voto computado. Nada é gravado em disco além dos resultados em `data/parquet/2026/rdv/`.

### Estrutura do RDV (spec v2)

O `-rdv.dat` é uma `EntidadeResultadoRDV` em BER (`spec/v2/rdv.asn1`), sem o envelope genérico do BU:

- `cabecalho`: `dataGeracao` e `idEleitoral` (`idPleito` 3220).
- `urna`: tipo, versão do software, carga (número interno, código de carga), `tipoArquivo` e número de série da flash.
- `rdv`: `pleito`, `fase`, `identificacao` (município, zona, local, seção), `historicoCodigosCarga` e `eleicoes`, um CHOICE entre `eleicoesVota` (urna) e `eleicoesSA` (Sistema de Apuração).
- Cada eleição traz `votosCargos`; cada cargo traz `idCargo`, `quantidadeEscolhas` e a lista `votos`, um registro `{tipoVoto, digitacao}` por escolha, embaralhado e sem vínculo com o eleitor.

Em 2026 há duas eleições: 6257 (Presidente) e 6259 (Governador, Senador com duas escolhas, Deputado Federal, Deputado Estadual ou Distrital). Cada cargo tem `comparecimento x quantidadeEscolhas` registros. Equivalência com o BU: `nominal` pelo número digitado; `legenda` pelos dois primeiros dígitos (partido); `branco` e `brancoAposSuspensao` como branco; `nulo`, `nuloAposSuspensao` e `nuloPorRepeticao` como nulo; `nuloCargoSemCandidato` e `nuloAposSuspensaoCargoSemCandidato` como `cargoSemCandidato` (agrupado em nulo se o BU não tiver o tipo). O parser fica em `src/dataurnas/parsers/rdv.py`.

### Log de contingência

Na troca de urna o `-log.jez` traz o `logd.dat` da urna que encerrou a votação e, como `.jez` aninhado (outro ZIP), o log da urna substituída. A linha do tempo lê os dois; os votos de cada urna são separados pelo identificador da urna.

### `rdv/recontagem_secoes.parquet`

Uma linha por seção e cargo.

| Coluna | Tipo | Descrição |
|---|---|---|
| `uf`, `cd_mun`, `zona`, `secao` | VARCHAR | Identificação da seção |
| `id_eleicao` | INTEGER | 6257 ou 6259 |
| `cargo`, `codigo_cargo` | VARCHAR, SMALLINT | Cargo |
| `qtd_escolhas` | SMALLINT | Escolhas por eleitor (Senador: 2) |
| `registros_rdv` | INTEGER | Registros do cargo no RDV |
| `comparecimento_bu` | INTEGER | Comparecimento do BU na eleição |
| `votos_rdv`, `votos_bu` | INTEGER | Total recontado no RDV e total do BU |
| `nominais_*`, `legenda_*`, `brancos_*`, `nulos_*` | INTEGER | Mesmos totais por tipo, RDV e BU |
| `n_votaveis` | INTEGER | Números distintos votados no RDV |
| `confere` | BOOLEAN | Mesma contagem por candidato, legenda, brancos e nulos e registros = comparecimento x escolhas |
| `detalhes` | VARCHAR | JSON com as diferenças (`{"nominal:22": [rdv, bu]}`), nulo quando confere |

### `rdv/log_tempo_secoes.parquet`

Uma linha por seção. Horários em hora local da urna; abertura oficial às 8h e fim às 17h de Brasília, convertidos pelo fuso do município (`fuso_offset`).

| Coluna | Descrição |
|---|---|
| `votos_log`, `comparecimento_bu`, `diferenca_log_bu` | Eventos "O voto do eleitor foi computado" no dia da eleição e comparação com o BU |
| `votos_outras_datas` | Votos computados com outra data |
| `n_urnas_log`, `aberturas` | Urnas com voto no log e eventos "Urna pronta para receber votos" |
| `hora_pronta`, `hora_encerramento`, `primeiro_voto`, `ultimo_voto` | Marcos do dia |
| `votos_antes_8h`, `votos_apos_17h` | Votos antes da abertura oficial e depois das 17h (legais: eleitores na fila) |
| `votos_antes_pronta`, `votos_apos_encerramento` | Votos fora da sequência de eventos da mesma urna |
| `max_votos_minuto`, `minuto_pico` | Pico por minuto |
| `intervalo_min_s`, `intervalo_mediana_s`, `intervalos_lt_10s`, `intervalos_lt_5s` | Intervalos entre votos consecutivos da mesma urna |
| `maior_lacuna_min`, `lacunas_60min` | Lacunas sem voto |
| `inversoes_relogio`, `ajustes_hora` | Hora menor que a do voto anterior e eventos de ajuste de hora |
| `hist_intervalos` | Contagem por faixa de intervalo (faixas em `resumo.json`) |
| `flags`, `grupo` | Categorias marcadas e o grupo de leitura mais grave (1, 2 ou 3) |

Grupos de leitura (`dashboard/reference.py`, `RDV_CATEGORIAS`): divergência RDV x BU, registros diferentes do comparecimento, estrutura inválida e hash diferente são grupo 1; contagem do log diferente do BU, voto fora de sequência ou com outra data, RDV não decodificado e divergência com BU do Sistema de Apuração são grupo 2; voto antes das 8h, intervalos curtos, lacunas e relógio invertido são grupo 3.

`rdv/resumo.json` traz os totais, os números por UF e por cargo, a soma nacional de Presidente pelo RDV comparada com `votos_presidente_2026.parquet`, as categorias encontradas e o histograma de intervalos. `rdv/divergencias.jsonl` recebe cada divergência do RDV na hora em que aparece (com `fsync`), e o log `data/ele2026_rdv.log` repete a linha com o prefixo `DIVERGENCIA_RDV `.
