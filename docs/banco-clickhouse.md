# Banco ClickHouse das versões de 2026

Banco colunar no servidor de processamento que indexa, de forma contínua, tudo o
que os coletores do 2º turno de 2026 guardam (versões de aux.json, BU e assinatura,
totais por abrangência e alertas), com o 1º turno de 2026 e 2022 ao lado para
comparação. Serve de base única para os relatórios: encerramento tardio, viradas,
BU x oficial, linha do tempo da totalização.

## Visão geral

| Item | Valor |
|---|---|
| Servidor | ClickHouse 26.8.35.10 (LTS), imagem oficial `clickhouse/clickhouse-server:26.8.35.10` |
| Contêiner | `dataurnas-clickhouse`, `--restart unless-stopped`, limite de 64 GB de RAM |
| Dados | `~/dataurnas-ch/data` (logs do servidor em `~/dataurnas-ch/logs`) |
| Portas | só em 127.0.0.1 do servidor: HTTP `18123`, nativa `19000` |
| Usuário | `dataurnas`; senha em `~/dataurnas-ch/.senha` (permissão 600, nunca versionada). O usuário `default` foi removido |
| Banco | `dataurnas` |
| Carregador | `~/dataurnas-ch/app/scripts/ch/carregar.py --loop 300`, log em `~/dataurnas-ch/carregador.log` |

Arquivos no repositório:

| Arquivo | Para quê |
|---|---|
| `scripts/ch/subir_clickhouse.sh` | sobe ou recria o contêiner (gera a senha só na primeira vez; mantém os dados) |
| `scripts/ch/schema.sql` | DDL de tabelas e views (idempotente) |
| `scripts/ch/referencias.sql` | recarrega as tabelas de referência a partir de `~/dataurnas-ch/ref` |
| `scripts/ch/carregar.py` | carregador incremental (testes em `tests/ch/test_carregar.py`) |
| `scripts/ch/iniciar_carregador.sh` | inicia o carregador em laço, desligado do terminal |
| `scripts/ch/ch.sh` | atalho para o `clickhouse-client` do contêiner com o usuário do projeto |

## Como conectar

No próprio servidor, pelo cliente do contêiner:

```sh
~/dataurnas-ch/app/scripts/ch/ch.sh "SELECT count() FROM bu_secao FINAL"
~/dataurnas-ch/app/scripts/ch/ch.sh < consulta.sql
# ou, sem o atalho:
docker exec -it dataurnas-clickhouse clickhouse-client --user dataurnas \
  --password "$(cat ~/dataurnas-ch/.senha)" --database dataurnas
```

Do Mac, por túnel SSH (as portas não ficam expostas na rede):

```sh
ssh -N -L 18123:127.0.0.1:18123 -L 19000:127.0.0.1:19000 <servidor>
# HTTP: curl -u "dataurnas:$SENHA" 'http://127.0.0.1:18123/?query=SELECT%201'
# Python: clickhouse_connect.get_client(host="127.0.0.1", port=18123,
#         username="dataurnas", password=SENHA, database="dataurnas")
# DBeaver/DataGrip: driver ClickHouse, host 127.0.0.1, porta 18123
```

A senha fica só no servidor; para usá-la no Mac, copie-a na hora para uma variável
de ambiente, sem gravar em arquivo do projeto.

## Fontes indexadas

| Fonte (no servidor, só leitura) | Tabelas |
|---|---|
| `~/dataurnas-versoes-t2*/bus/parts/versoes-*.parquet` (coletores de Londres) | `versoes_arquivo`, `arquivos_conteudo`, `aux_versoes`, `bu_secao`, `bu_votos` |
| `~/dataurnas-mac/versoes/2026/t2*/bus/parts/versoes-*.parquet` (partes do Mac, rsync a cada 10 min) | idem |
| `.../totais/indice.jsonl` de cada pasta | `totais_versoes` |
| `.../alertas.jsonl` de cada pasta | `alertas` |
| `~/dataurnas-ch/ref/2026/*.parquet` (cópia de `data/parquet/2026/`) | `ref_secoes_2026_t1`, `ref_votos_2026_t1`, `ref_resultado_municipio_2026_t1` |
| `~/dataurnas-ch/ref/2022/*.parquet` (cópia de `data/parquet/`) | `ref_secoes_2022`, `ref_votos_2022` |

As pastas são descobertas pelos padrões `dataurnas-versoes-t2*` e
`dataurnas-mac/versoes/2026/t2*` (relativos ao HOME). Um coletor novo que siga o
mesmo leiaute entra sozinho no ciclo seguinte; o nome da pasta vira a coluna
`origem`. As partes `votos-*.parquet` não são lidas: os votos saem da
decodificação do próprio BU. Os logs GEDAI (`~/dataurnas-t2/gedai/`) e os
resultados derivados do Mac (`~/dataurnas-mac/parquet-t2/`) não estão no banco.

## Convenções

- `uf` em minúsculas, `cd_mun` com 5 dígitos, `zona` e `secao` com 4: o formato do TSE.
- Horários do relógio da urna (`hora_abertura`, `hora_encerramento`,
  `data_hora_emissao`) ficam em `DateTime('UTC')` sem conversão: o valor mostrado
  é o horário local da urna (em AC, AM e demais estados com fuso diferente, o
  horário local daquele estado).
- Horários do TSE (`recebimento`, `totalizado_em`, `gerado_em`) estão em
  `DateTime('America/Sao_Paulo')`. `coletado_em` (momento em que o coletor baixou)
  está em UTC.
- Tabelas `ReplacingMergeTree` deduplicam pela chave de ordenação quando as partes
  se fundem. Até a fusão podem aparecer linhas repetidas (por exemplo, a mesma
  versão vinda de duas pastas): use `FINAL` ou as views, que já fazem isso.

## Tabelas

### Controle

- **`cargas_arquivos`**: um registro por arquivo de origem carregado (`caminho`,
  `origem`, `tipo_fonte`, `tamanho`, `mtime`, `sha256`, `deslocamento` para JSONL,
  `linhas`, `status` = ok, repetida ou erro). A versão mais recente de cada
  caminho vale (use `FINAL`).

### 2º turno de 2026

- **`versoes_arquivo`**: metadados de cada versão de arquivo por seção, sem o
  binário: tipo (`aux`, `bu`, `busa`, `vota`, `sa`), `sha512`, `md5`, `tamanho`,
  hash do pacote, nome, status da seção e do pacote, recebimento, `coletado_em`,
  `origem`, `lote` (parte Parquet) e, nas assinaturas, `modelo_urna_cod`.
  Chave: `(uf, cd_mun, zona, secao, tipo, sha512)`; quando a mesma versão veio de
  mais de uma pasta fica a coleta mais antiga.
- **`arquivos_conteudo`**: binário deduplicado por `sha512` (ZSTD nível 6), com o
  BU, a assinatura `.vsc` e o aux.json de cada versão. Junte com `versoes_arquivo`
  por `sha512` para reprocessar um arquivo.
- **`aux_versoes`**: cada versão de aux.json parseada, uma linha por pacote listado
  (`idx_hash`, `hash`, `st_hash`, recebimento, `arquivos` como `tp:nome`), com o
  status da seção e a data de geração (`gerado_em`). Versão sem pacote: uma linha
  com `idx_hash = 0`.
- **`bu_secao`**: cada versão de BU decodificada (eleição 6258, Presidente):
  horários, aptos, comparecimento, biometria, número interno da urna, código e
  quantidade de cargas, versão do software, tipo de urna, totais de votos. BU que
  não decodifica fica com o motivo em `erro`.
- **`bu_votos`**: votos de Presidente por candidato em cada versão de BU
  (`sha512_bu`, `tipo_voto`, `numero`, `partido`, `votos`).
- **`totais_versoes`**: cada versão dos totais por abrangência (`nivel` br, uf ou
  municipio; `abr` como `br`, `sp`, `sp71072`): seções totalizadas (`st`) e
  totais (`ts`), votos (`tv`, `vb`, `tvn`) e votos por candidato em `cand`
  (`Map`, chave = número).
- **`alertas`**: linhas dos `alertas.jsonl` dos coletores (tipo, seção e o JSON
  original em `dados`).

### Referências

- **`ref_secoes_2026_t1`** e **`ref_votos_2026_t1`**: 1º turno de 2026 por seção
  (517.179 seções; votos de Presidente).
- **`ref_resultado_municipio_2026_t1`**: resultado oficial do 1º turno por município.
- **`ref_secoes_2022`** e **`ref_votos_2022`**: 2022, dois turnos (`turno` 1 ou 2),
  seções com horários, modelo e reinícios; votos de Presidente por seção.

## Views

| View | Conteúdo |
|---|---|
| `v_bu_ultima` | última versão de BU de cada seção (recebimento mais recente; empate, a coletada por último), só as decodificadas |
| `v_bu_versoes_por_secao` | quantas versões e pacotes cada seção teve, com o primeiro e o último recebimento |
| `v_votos_t2_secao` | votos da última versão por seção: `votos_13`, `votos_22`, `brancos`, `nulos`, `total`, aptos, comparecimento, encerramento |
| `v_votos_t1_secao` | o mesmo para o 1º turno (com `votos_outros`) |
| `v_comparacao_t1_t2` | seção a seção: aptos, comparecimento e votos nos dois turnos, líder de cada turno e `virada` |
| `v_totais_ultima` | versão mais recente dos totais de cada abrangência |
| `v_bu_municipio_x_oficial` | soma dos BUs por município x último total publicado, com as diferenças |
| `v_contagem_uf` | seções com BU, versões e BUs com erro por UF |

## Consultas para os relatórios

Encerramento tardio. O BU traz o horário local da urna, e o encerramento normal
acontece segundos depois das 17h00 locais; para comparar com o horário legal
(17h00 de Brasília) converta pelo fuso. A conversão simplificada abaixo usa o fuso
da UF; os 11 municípios do oeste do AM em UTC-5 e Fernando de Noronha (UTC-2)
pedem a tabela `FUSO_MUNICIPIO` de `scripts/ele2026/analisar_encerramento_t2.py`.
O exterior (`zz`) fica de fora.

```sql
WITH hora_encerramento + toIntervalHour(multiIf(uf = 'ac', 2,
         uf IN ('am', 'mt', 'ms', 'ro', 'rr'), 1, 0)) AS enc_brasilia
SELECT uf,
       count() AS secoes,
       countIf(formatDateTime(enc_brasilia, '%H:%i:%S') > '17:30:00') AS depois_17h30,
       countIf(formatDateTime(enc_brasilia, '%H:%i:%S') > '18:00:00') AS depois_18h,
       max(enc_brasilia) AS ultimo
FROM v_bu_ultima
WHERE uf != 'zz'
GROUP BY uf
ORDER BY depois_17h30 DESC;

-- distribuição por faixa de 10 minutos depois das 17h30 de Brasília
WITH hora_encerramento + toIntervalHour(multiIf(uf = 'ac', 2,
         uf IN ('am', 'mt', 'ms', 'ro', 'rr'), 1, 0)) AS enc_brasilia
SELECT toStartOfInterval(enc_brasilia, INTERVAL 10 MINUTE) AS faixa, count()
FROM v_bu_ultima
WHERE uf != 'zz' AND formatDateTime(enc_brasilia, '%H:%i:%S') > '17:30:00'
GROUP BY faixa ORDER BY faixa;
```

Viradas de liderança entre os turnos de 2026:

```sql
SELECT uf, count() AS secoes, countIf(virada) AS viradas,
       countIf(virada AND lider_t1 = '13') AS de_13_para_22,
       countIf(virada AND lider_t1 = '22') AS de_22_para_13
FROM v_comparacao_t1_t2
WHERE aptos_t1 > 0
GROUP BY uf ORDER BY viradas DESC;
```

Viradas em 2022 (linha de base), direto das referências:

```sql
WITH s AS (
    SELECT turno, uf, cd_mun, zona, secao,
           sumIf(votos, numero = 13) AS v13, sumIf(votos, numero = 22) AS v22
    FROM ref_votos_2022 WHERE tipo_voto = 'nominal'
    GROUP BY turno, uf, cd_mun, zona, secao
)
SELECT a.uf, count() AS secoes,
       countIf((a.v13 > a.v22) != (b.v13 > b.v22) AND a.v13 != a.v22 AND b.v13 != b.v22) AS viradas
FROM s AS a
INNER JOIN s AS b USING (uf, cd_mun, zona, secao)
WHERE a.turno = 1 AND b.turno = 2
GROUP BY a.uf ORDER BY viradas DESC;
```

BU x oficial por município (diferenças diferentes de zero ou seções faltando):

```sql
SELECT *
FROM v_bu_municipio_x_oficial
WHERE dif_13 != 0 OR dif_22 != 0 OR secoes_bu != secoes_totalizadas_oficial
ORDER BY abs(dif_13) + abs(dif_22) DESC
LIMIT 50;
```

Linha do tempo da totalização (seções totalizadas e votos no Brasil a cada versão):

```sql
SELECT totalizado_em, st, ts, round(100 * st / ts, 2) AS pct_secoes,
       cand['13'] AS v13, cand['22'] AS v22,
       round(100 * cand['13'] / (cand['13'] + cand['22']), 3) AS pct_13
FROM totais_versoes FINAL
WHERE nivel = 'br'
ORDER BY idg;

-- recebimento dos BUs por faixa de 5 minutos (horário de Brasília)
SELECT toStartOfFiveMinutes(recebimento) AS faixa, count() AS secoes,
       sum(votos_13) AS v13, sum(votos_22) AS v22
FROM v_bu_ultima AS u
INNER JOIN v_votos_t2_secao AS v USING (uf, cd_mun, zona, secao)
GROUP BY faixa ORDER BY faixa;
```

Seções com mais de uma versão de BU e o que mudou:

```sql
SELECT uf, cd_mun, zona, secao, versoes, pacotes, tipos,
       primeiro_recebimento, ultimo_recebimento
FROM v_bu_versoes_por_secao
WHERE versoes > 1
ORDER BY versoes DESC;

SELECT b.uf, b.cd_mun, b.zona, b.secao, b.sha512, b.recebimento,
       groupArray((v.numero, v.votos)) AS votos
FROM bu_secao AS b FINAL
INNER JOIN bu_votos AS v FINAL ON v.sha512_bu = b.sha512 AND v.uf = b.uf
WHERE (b.uf, b.cd_mun, b.zona, b.secao) IN
      (SELECT uf, cd_mun, zona, secao FROM v_bu_versoes_por_secao WHERE versoes > 1)
GROUP BY b.uf, b.cd_mun, b.zona, b.secao, b.sha512, b.recebimento
ORDER BY b.uf, b.cd_mun, b.zona, b.secao, b.recebimento;
```

Software, carga e modelo de urna:

```sql
SELECT versao_votacao, tipo_urna, count() FROM v_bu_ultima GROUP BY 1, 2 ORDER BY 3 DESC;

SELECT modelo_urna_cod, count()
FROM versoes_arquivo FINAL
WHERE tipo IN ('vota', 'sa')
GROUP BY modelo_urna_cod ORDER BY modelo_urna_cod;
```

Recuperar o binário de uma versão (por exemplo, para reprocessar um BU):

```sql
SELECT c.conteudo
FROM versoes_arquivo AS a FINAL
INNER JOIN arquivos_conteudo AS c FINAL USING (sha512)
WHERE a.uf = 'sp' AND a.cd_mun = '71072' AND a.zona = '0001' AND a.secao = '0001'
  AND a.tipo = 'bu'
FORMAT RawBLOB;
```

## Operação

Subir ou recriar o servidor (idempotente, preserva dados e senha):

```sh
ssh <servidor> 'bash -s' < scripts/ch/subir_clickhouse.sh
```

Aplicar o esquema e recarregar as referências:

```sh
ssh <servidor> '~/dataurnas-ch/app/scripts/ch/ch.sh' < scripts/ch/schema.sql
ssh <servidor> '~/dataurnas-ch/app/scripts/ch/ch.sh' < scripts/ch/referencias.sql
```

Atualizar o código do carregador no servidor e reiniciá-lo:

```sh
rsync -a --delete --exclude __pycache__ --relative \
  pyproject.toml src/dataurnas spec scripts/ch <servidor>:dataurnas-ch/app/
ssh <servidor> 'kill "$(cat ~/dataurnas-ch/carregador.pid)"; ~/dataurnas-ch/app/scripts/ch/iniciar_carregador.sh'
```

O ambiente Python do carregador fica em `~/dataurnas-ch/venv` (asn1tools,
pyarrow, cryptography, httpx, py7zr, click e clickhouse-connect). O código fica em
`~/dataurnas-ch/app`, fora de `/work`, para não ser apagado pela sincronização dos
jobs remotos.

Acompanhar o carregador:

```sh
tail -f ~/dataurnas-ch/carregador.log
cat ~/dataurnas-ch/carregador-estado.json      # resumo do último ciclo
~/dataurnas-ch/app/scripts/ch/ch.sh "SELECT status, count() FROM cargas_arquivos FINAL GROUP BY status"
```

Cada ciclo (a cada 5 min) faz:

1. Lê o registro `cargas_arquivos` e lista as fontes, ignorando `*.tmp`, arquivos
   ocultos (temporários do rsync) e partes modificadas há menos de 10 s.
2. Lê as linhas novas dos JSONL a partir do último deslocamento, só até a última
   quebra de linha (a linha em escrita fica para o ciclo seguinte).
3. Calcula o SHA-256 de cada parte nova; parte idêntica a outra já carregada (cópia
   em outra pasta) só é registrada como `repetida`.
4. Decodifica as partes em paralelo (48 processos por padrão) e insere em lotes de
   até 400 mil linhas ou 768 MB de conteúdo. Os dados entram antes do registro da
   carga: se o processo cair no meio, a parte é relida e a deduplicação das tabelas
   evita repetição.

Parte que falha na leitura fica com `status = 'erro'` e é tentada de novo a cada
ciclo. Uma trava (`~/dataurnas-ch/carregador.lock`) impede dois carregadores ao
mesmo tempo.

## Validação da carga inicial (26/10/2026, 04h15 UTC)

A carga inicial leu 412 partes (cerca de 13 GB de Parquet) em 118 s com 48
processos; os ciclos seguintes levam poucos segundos. Seções com BU por UF
(`v_contagem_uf`), conferidas com uma contagem independente feita direto nos
Parquet com pyarrow (mesmas seções, por UF):

| UF | Seções | UF | Seções | UF | Seções |
|---|---:|---|---:|---|---:|
| ac | 2.249 | ma | 18.093 | rn | 8.115 |
| al | 7.078 | pa | 20.827 | ro | 4.698 |
| am | 8.001 | pb | 10.712 | rr | 1.519 |
| ap | 1.911 | pe | 21.418 | se | 5.923 |
| ba | 35.475 | pi | 10.225 | sp | 60.958 |
| ce | 23.765 | to | 4.384 | zz | 1.310 |

- Total: 246.661 seções com BU, 246.661 versões de BU, nenhum BU com erro de
  decodificação e nenhuma seção com mais de uma versão de BU até aqui.
- Por origem: 150.638 seções nas partes do Mac (N/NE; os relatórios locais
  falavam em cerca de 145 mil antes das últimas partes chegarem), 58.611 na coleta
  anterior de SP e 37.412 no coletor atual de Londres. N/NE somam 184.393 seções.
- `v_votos_t2_secao`: 246.659 seções (duas sem votos de Presidente), 36.141.272
  votos no 13 e 24.647.801 no 22.
- `v_comparacao_t1_t2`: todas as 246.659 seções acham o par no 1º turno; 11.830
  viradas (174 de 13 para 22, 11.656 de 22 para 13).
- `v_bu_municipio_x_oficial`: 2.930 municípios com BU; nos 2.851 em que as seções
  com BU são todas as totalizadas no último total publicado, a soma dos BUs bate
  exatamente com o oficial para o 13 e o 22.
- `v_totais_ultima`: o Brasil está com 499.248 de 499.248 seções totalizadas; os
  últimos totais municipais coletados somam 412.683 seções (a coleta municipal é
  menos frequente que a de UF e Brasil).
- `alertas`: nenhum `alertas.jsonl` existia nas pastas no momento da carga; a
  tabela recebe as linhas assim que os coletores criarem o arquivo.
- Referências: 517.179 seções e 3.800.511 linhas de votos no 1º turno de 2026;
  941.987 seções e 5.366.047 linhas de votos de Presidente em 2022.
- Espaço: `arquivos_conteudo` ocupa 13,7 GiB (BU e assinatura quase não
  comprimem); as demais tabelas somam menos de 500 MiB.

## Limitações

- O carregador roda com `setsid nohup`, não como serviço: não volta sozinho depois
  de um reinício do servidor (o ClickHouse volta, por `--restart unless-stopped`).
  Depois de um reinício, rode `iniciar_carregador.sh` de novo. O systemd de usuário
  não foi usado porque a sessão do usuário não tem `linger` habilitado.
- Até a fusão de partes, as tabelas podem ter linhas repetidas; consultas exatas
  precisam de `FINAL` ou das views.
- `v_bu_ultima` escolhe a versão pelo recebimento no TSE. Seção com pacote
  substituto (`busa`) e original pode exigir análise caso a caso
  (`v_bu_versoes_por_secao`).
- `v_votos_t2_secao` e `v_bu_municipio_x_oficial` olham só os candidatos 13 e 22
  (os do 2º turno); brancos e nulos vêm separados.
- Os totais vêm do `indice.jsonl` dos coletores (resumo com seções, votos e votos
  por candidato). O JSON completo de cada versão continua em `totais/<abr>/` e não
  foi indexado.
- As referências são cópias estáticas dos Parquet do repositório; se eles forem
  refeitos, copie de novo para `~/dataurnas-ch/ref` e rode `referencias.sql`.
- Logs GEDAI e resultados derivados do Mac não estão no banco.
- O processo do carregador mantém alguns GB de memória residente depois de uma
  carga grande (8 GB após a inicial); os ciclos incrementais são pequenos.
