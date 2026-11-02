-- Esquema do banco ClickHouse do projeto (auditoria dos arquivos públicos de 2026
-- e comparação com 2022). Idempotente: pode ser reaplicado a qualquer momento.
--
-- Aplicar no servidor:
--   docker exec -i dataurnas-clickhouse clickhouse-client --user dataurnas \
--     --password "$(cat ~/dataurnas-ch/.senha)" --multiquery < scripts/ch/schema.sql
--
-- Convenções
-- * uf em minúsculas ('sp'), cd_mun com 5 dígitos ('71072'), zona com 4 ('0001')
--   e secao com 4 ('0123'): o mesmo formato dos arquivos do TSE.
-- * Horários do relógio da urna (abertura, encerramento, emissão do BU) ficam em
--   DateTime('UTC') sem conversão: o valor mostrado é o horário local da urna.
-- * Horários do TSE (recebimento, totalização, geração do aux.json) estão em
--   DateTime('America/Sao_Paulo').
-- * Tabelas ReplacingMergeTree deduplicam pela chave de ordenação na fusão de
--   partes. Consultas que precisam de exatidão usam FINAL (ou as views abaixo).

CREATE DATABASE IF NOT EXISTS dataurnas;

-- ---------------------------------------------------------------------------
-- Controle de carga
-- ---------------------------------------------------------------------------

-- Um registro por arquivo de origem carregado. Para JSONL (totais, alertas)
-- guarda o deslocamento em bytes já lido; a versão mais recente vale.
CREATE TABLE IF NOT EXISTS dataurnas.cargas_arquivos
(
    caminho      String,
    origem       LowCardinality(String),
    tipo_fonte   LowCardinality(String),      -- versoes | votos | totais | alertas
    tamanho      UInt64,
    mtime        Float64,
    sha256       String,
    deslocamento UInt64 DEFAULT 0,             -- JSONL: bytes já processados
    linhas       UInt64,
    status       LowCardinality(String),       -- ok | erro | ignorado
    erro         String DEFAULT '',
    carregado_em DateTime64(3, 'UTC')
)
ENGINE = ReplacingMergeTree(carregado_em)
ORDER BY caminho;

-- ---------------------------------------------------------------------------
-- 2º turno de 2026: versões coletadas
-- ---------------------------------------------------------------------------

-- Metadados de cada versão de arquivo por seção, sem o binário.
-- Deduplicada por (uf, cd_mun, zona, secao, tipo, sha512); quando a mesma versão
-- veio de mais de uma pasta fica a primeira coleta (prioridade maior).
CREATE TABLE IF NOT EXISTS dataurnas.versoes_arquivo
(
    uf             LowCardinality(String),
    cd_mun         String,
    zona           String,
    secao          String,
    tipo           LowCardinality(String),     -- aux | bu | busa | vota | sa
    sha512         String,
    md5            String,
    tamanho        UInt32,
    hash           String,                     -- hash do pacote no aux.json
    nome           String,
    st_secao       LowCardinality(String),
    st_hash        LowCardinality(String),
    dt_recebimento String,
    hr_recebimento String,
    recebimento    Nullable(DateTime('America/Sao_Paulo')),
    modelo_urna_cod Nullable(UInt16),          -- só vota/sa: modelo lido da assinatura
    coletado_em    DateTime('UTC'),
    origem         LowCardinality(String),     -- pasta de coleta
    lote           String,                     -- parte parquet de origem
    prioridade     UInt64                      -- maior = coleta mais antiga
)
ENGINE = ReplacingMergeTree(prioridade)
PARTITION BY uf
ORDER BY (uf, cd_mun, zona, secao, tipo, sha512);

-- Conteúdo binário deduplicado por SHA-512 (BU, assinatura .vsc e aux.json).
CREATE TABLE IF NOT EXISTS dataurnas.arquivos_conteudo
(
    sha512   String,
    tipo     LowCardinality(String),
    tamanho  UInt32,
    md5      String,
    conteudo String CODEC(ZSTD(6))
)
ENGINE = ReplacingMergeTree
PARTITION BY tipo
ORDER BY sha512;

-- aux.json parseado: uma linha por pacote (hash) listado em cada versão.
-- Versão sem pacote gera uma linha com idx_hash = 0 e hash vazio.
CREATE TABLE IF NOT EXISTS dataurnas.aux_versoes
(
    uf             LowCardinality(String),
    cd_mun         String,
    zona           String,
    secao          String,
    sha512_aux     String,
    coletado_em    DateTime('UTC'),
    gerado_em      Nullable(DateTime('America/Sao_Paulo')),   -- dg + hg do aux.json
    fase           LowCardinality(String),
    st_secao       LowCardinality(String),
    n_hashes       UInt16,
    idx_hash       UInt16,                     -- 1, 2, ... na ordem do aux.json
    hash           String,
    st_hash        LowCardinality(String),
    dt_recebimento String,
    hr_recebimento String,
    recebimento    Nullable(DateTime('America/Sao_Paulo')),
    arquivos       Array(String),              -- 'tp:nome'
    origem         LowCardinality(String)
)
ENGINE = ReplacingMergeTree
PARTITION BY uf
ORDER BY (uf, cd_mun, zona, secao, sha512_aux, idx_hash);

-- BU decodificado (eleição 6258, Presidente): uma linha por versão de BU.
CREATE TABLE IF NOT EXISTS dataurnas.bu_secao
(
    uf                    LowCardinality(String),
    cd_mun                String,
    zona                  String,
    secao                 String,
    sha512                String,
    tipo_arquivo          LowCardinality(String),  -- bu | busa
    hash                  String,
    st_hash               LowCardinality(String),
    st_secao              LowCardinality(String),
    recebimento           Nullable(DateTime('America/Sao_Paulo')),
    coletado_em           DateTime('UTC'),
    origem                LowCardinality(String),
    erro                  String,                  -- vazio quando decodificou
    spec_version          LowCardinality(String),
    municipio_bu          Nullable(Int32),
    zona_bu               Nullable(Int32),
    secao_bu              Nullable(Int32),
    local_votacao         Nullable(Int32),
    data_hora_emissao     Nullable(DateTime('UTC')),  -- relógio da urna
    hora_abertura         Nullable(DateTime('UTC')),  -- relógio da urna
    hora_encerramento     Nullable(DateTime('UTC')),  -- relógio da urna
    tipo_urna             LowCardinality(String),
    versao_votacao        LowCardinality(String),
    numero_interno_urna   Nullable(Int64),
    codigo_carga          String,
    qtd_codigos_carga     UInt16,
    fase                  LowCardinality(String),
    aptos                 Nullable(Int32),
    aptos_secao           Nullable(Int32),
    aptos_tte             Nullable(Int32),
    comparecimento        Nullable(Int32),
    comparecimento_bu     Nullable(Int32),
    comp_sem_biometria    Nullable(Int32),
    habilitados_biometria Nullable(Int32),
    habilitados_biografia Nullable(Int32),
    votos_nominais        Int32,
    votos_legenda         Int32,
    votos_brancos         Int32,
    votos_nulos           Int32,
    votos_total           Int32,
    tem_presidente        Bool
)
ENGINE = ReplacingMergeTree
PARTITION BY uf
ORDER BY (uf, cd_mun, zona, secao, sha512);

-- Votos de Presidente por candidato em cada versão de BU.
CREATE TABLE IF NOT EXISTS dataurnas.bu_votos
(
    uf          LowCardinality(String),
    cd_mun      String,
    zona        String,
    secao       String,
    sha512_bu   String,
    tipo_voto   LowCardinality(String),   -- nominal | legenda | branco | nulo
    numero      Int32,                    -- 0 para branco e nulo
    partido     Nullable(Int32),
    votos       Int32
)
ENGINE = ReplacingMergeTree
PARTITION BY uf
ORDER BY (uf, cd_mun, zona, secao, sha512_bu, tipo_voto, numero);

-- Cada versão dos totais de Presidente por abrangência (br, uf ou uf+município).
CREATE TABLE IF NOT EXISTS dataurnas.totais_versoes
(
    abr          String,                  -- 'br', 'sp', 'sp71072'
    nivel        LowCardinality(String),  -- br | uf | municipio
    uf           LowCardinality(String),  -- vazio no br
    cd_mun       String,                  -- vazio no br e na uf
    sha256       String,
    coletado_em  DateTime('UTC'),
    dg           String,
    hg           String,
    totalizado_em Nullable(DateTime('America/Sao_Paulo')),
    idg          UInt64,
    st           Nullable(UInt32),        -- seções totalizadas
    ts           Nullable(UInt32),        -- total de seções
    tv           Nullable(UInt64),        -- total de votos
    vb           Nullable(UInt64),        -- brancos
    tvn          Nullable(UInt64),        -- nulos
    cand         Map(String, UInt64),     -- número -> votos apurados
    origem       LowCardinality(String)
)
ENGINE = ReplacingMergeTree
ORDER BY (nivel, abr, sha256);

-- Alertas dos coletores (uma linha por linha de alertas.jsonl).
CREATE TABLE IF NOT EXISTS dataurnas.alertas
(
    origem   LowCardinality(String),
    sha256   String,                       -- da linha, para deduplicar
    em       Nullable(DateTime('UTC')),
    tipo     LowCardinality(String),
    secao    String,                       -- 'uf/mun/zona/secao' quando houver
    dados    String                        -- linha JSON original
)
ENGINE = ReplacingMergeTree
ORDER BY (origem, tipo, sha256);

-- ---------------------------------------------------------------------------
-- Referências: 1º turno de 2026 e 2022 (carregadas por scripts/ch/referencias.sql)
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS dataurnas.ref_secoes_2026_t1
(
    uf LowCardinality(String), cd_mun String, nm_mun String, zona String, secao String,
    status LowCardinality(String), secao_principal Nullable(String),
    secoes_agregadas Nullable(String), st_secao LowCardinality(String),
    hash Nullable(String), st_hash LowCardinality(Nullable(String)), n_hashes Nullable(Int16),
    dt_recebimento Nullable(String), hr_recebimento Nullable(String),
    spec_version LowCardinality(Nullable(String)),
    municipio_bu Nullable(Int32), zona_bu Nullable(Int32), secao_bu Nullable(Int32),
    local_votacao Nullable(Int32),
    data_hora_emissao Nullable(DateTime('UTC')),
    hora_abertura Nullable(DateTime('UTC')),
    hora_encerramento Nullable(DateTime('UTC')),
    tipo_urna LowCardinality(Nullable(String)), versao_votacao LowCardinality(Nullable(String)),
    numero_interno_urna Nullable(Int64), codigo_carga Nullable(String),
    qtd_codigos_carga Nullable(Int16), fase LowCardinality(Nullable(String)),
    modelo_urna_cod Nullable(Int16), modelo_urna LowCardinality(Nullable(String)),
    aptos Nullable(Int32), aptos_secao Nullable(Int32), aptos_tte Nullable(Int32),
    comparecimento Nullable(Int32), comparecimento_bu Nullable(Int32),
    comp_sem_biometria Nullable(Int32), habilitados_biometria Nullable(Int32),
    habilitados_biografia Nullable(Int32),
    votos_nominais Nullable(Int32), votos_legenda Nullable(Int32),
    votos_brancos Nullable(Int32), votos_nulos Nullable(Int32), votos_total Nullable(Int32),
    tem_presidente Nullable(Bool), origem_bu Nullable(String)
)
ENGINE = MergeTree
ORDER BY (uf, cd_mun, zona, secao);

CREATE TABLE IF NOT EXISTS dataurnas.ref_votos_2026_t1
(
    uf LowCardinality(String), cd_mun String, zona String, secao String,
    tipo_voto LowCardinality(String), numero Int32, partido Nullable(Int32), votos Int32
)
ENGINE = MergeTree
ORDER BY (uf, cd_mun, zona, secao, tipo_voto, numero);

-- Resultado oficial do 1º turno de 2026 por município (votos por candidato em v_*).
CREATE TABLE IF NOT EXISTS dataurnas.ref_resultado_municipio_2026_t1
(
    uf LowCardinality(String), cd_mun String, cd_ibge String, nome String, capital Bool,
    secoes_total Int64, secoes_totalizadas Int64, eleitorado Int64, comparecimento Int64,
    votos_total Int64, votos_validos Int64, votos_brancos Int64, votos_nulos_total Int64,
    data_totalizacao String, hora_totalizacao String,
    v_13 Int64, v_22 Int64
)
ENGINE = MergeTree
ORDER BY (uf, cd_mun);

-- 2022: seções dos dois turnos (base local do projeto, 941.986 seções).
CREATE TABLE IF NOT EXISTS dataurnas.ref_secoes_2022
(
    turno UInt8, uf LowCardinality(String), regiao LowCardinality(String),
    cd_mun String, zona String, secao String,
    modelo_urna LowCardinality(String), tipo_urna LowCardinality(String),
    versao_sw LowCardinality(String), fuso_offset Int8, emissao String,
    eleitores_aptos Int32, comparecimento Int32, comp_biometrico Int32,
    hora_abertura Nullable(DateTime('UTC')), hora_encerramento Nullable(DateTime('UTC')),
    duracao_min Int32, reboots Int32, is_reserva Bool, n_issues Int32
)
ENGINE = MergeTree
PARTITION BY turno
ORDER BY (turno, uf, cd_mun, zona, secao);

-- 2022: votos de Presidente por seção e turno.
CREATE TABLE IF NOT EXISTS dataurnas.ref_votos_2022
(
    turno UInt8, uf LowCardinality(String), cd_mun String, zona String, secao String,
    tipo_voto LowCardinality(String), numero Int32, partido Nullable(Int32), votos Int32
)
ENGINE = MergeTree
PARTITION BY turno
ORDER BY (turno, uf, cd_mun, zona, secao, tipo_voto, numero);

-- ---------------------------------------------------------------------------
-- Views
-- ---------------------------------------------------------------------------

-- Última versão de BU por seção: a de recebimento mais recente no TSE (empate:
-- a coletada por último). Só versões decodificadas sem erro.
CREATE OR REPLACE VIEW dataurnas.v_bu_ultima AS
SELECT *
FROM dataurnas.bu_secao FINAL
WHERE erro = ''
ORDER BY uf, cd_mun, zona, secao, recebimento DESC NULLS LAST, coletado_em DESC
LIMIT 1 BY uf, cd_mun, zona, secao;

-- Quantas versões de BU cada seção teve (útil para achar republicações).
CREATE OR REPLACE VIEW dataurnas.v_bu_versoes_por_secao AS
SELECT uf, cd_mun, zona, secao,
       count() AS versoes,
       uniqExact(hash) AS pacotes,
       groupArray(tipo_arquivo) AS tipos,
       min(recebimento) AS primeiro_recebimento,
       max(recebimento) AS ultimo_recebimento
FROM dataurnas.bu_secao FINAL
WHERE erro = ''
GROUP BY uf, cd_mun, zona, secao;

-- Votos da última versão de BU, uma linha por seção (13 e 22 no 2º turno).
CREATE OR REPLACE VIEW dataurnas.v_votos_t2_secao AS
SELECT u.uf AS uf, u.cd_mun AS cd_mun, u.zona AS zona, u.secao AS secao,
       any(u.sha512) AS sha512_bu,
       any(u.aptos) AS aptos,
       any(u.comparecimento) AS comparecimento,
       any(u.hora_encerramento) AS hora_encerramento,
       sumIf(v.votos, v.tipo_voto = 'nominal' AND v.numero = 13) AS votos_13,
       sumIf(v.votos, v.tipo_voto = 'nominal' AND v.numero = 22) AS votos_22,
       sumIf(v.votos, v.tipo_voto = 'branco') AS brancos,
       sumIf(v.votos, v.tipo_voto = 'nulo') AS nulos,
       sum(v.votos) AS total
FROM dataurnas.v_bu_ultima AS u
INNER JOIN (SELECT * FROM dataurnas.bu_votos FINAL) AS v
    ON v.uf = u.uf AND v.cd_mun = u.cd_mun AND v.zona = u.zona
   AND v.secao = u.secao AND v.sha512_bu = u.sha512
GROUP BY u.uf, u.cd_mun, u.zona, u.secao;

-- 1º turno de 2026 por seção, no mesmo formato.
CREATE OR REPLACE VIEW dataurnas.v_votos_t1_secao AS
SELECT s.uf AS uf, s.cd_mun AS cd_mun, s.zona AS zona, s.secao AS secao,
       any(s.aptos) AS aptos, any(s.comparecimento) AS comparecimento,
       any(s.hora_encerramento) AS hora_encerramento,
       sumIf(v.votos, v.tipo_voto = 'nominal' AND v.numero = 13) AS votos_13,
       sumIf(v.votos, v.tipo_voto = 'nominal' AND v.numero = 22) AS votos_22,
       sumIf(v.votos, v.tipo_voto = 'nominal' AND v.numero NOT IN (13, 22)) AS votos_outros,
       sumIf(v.votos, v.tipo_voto = 'branco') AS brancos,
       sumIf(v.votos, v.tipo_voto = 'nulo') AS nulos,
       sum(v.votos) AS total
FROM dataurnas.ref_secoes_2026_t1 AS s
INNER JOIN dataurnas.ref_votos_2026_t1 AS v
    ON v.uf = s.uf AND v.cd_mun = s.cd_mun AND v.zona = s.zona AND v.secao = s.secao
GROUP BY s.uf, s.cd_mun, s.zona, s.secao;

-- Comparação 1º x 2º turno de 2026 por seção (líder 13 x 22 em cada turno).
CREATE OR REPLACE VIEW dataurnas.v_comparacao_t1_t2 AS
SELECT t2.uf AS uf, t2.cd_mun AS cd_mun, t2.zona AS zona, t2.secao AS secao,
       t1.aptos AS aptos_t1, t2.aptos AS aptos_t2,
       t1.comparecimento AS comparecimento_t1, t2.comparecimento AS comparecimento_t2,
       t1.votos_13 AS votos_13_t1, t1.votos_22 AS votos_22_t1, t1.votos_outros AS votos_outros_t1,
       t2.votos_13 AS votos_13_t2, t2.votos_22 AS votos_22_t2,
       t1.brancos + t1.nulos AS brancos_nulos_t1, t2.brancos + t2.nulos AS brancos_nulos_t2,
       multiIf(t1.votos_13 > t1.votos_22, '13', t1.votos_22 > t1.votos_13, '22', 'empate') AS lider_t1,
       multiIf(t2.votos_13 > t2.votos_22, '13', t2.votos_22 > t2.votos_13, '22', 'empate') AS lider_t2,
       lider_t1 != lider_t2 AND lider_t1 != 'empate' AND lider_t2 != 'empate' AS virada,
       t1.hora_encerramento AS encerramento_t1, t2.hora_encerramento AS encerramento_t2
FROM dataurnas.v_votos_t2_secao AS t2
LEFT JOIN dataurnas.v_votos_t1_secao AS t1
    ON t1.uf = t2.uf AND t1.cd_mun = t2.cd_mun AND t1.zona = t2.zona AND t1.secao = t2.secao;

-- Versão mais recente dos totais de cada abrangência.
CREATE OR REPLACE VIEW dataurnas.v_totais_ultima AS
SELECT *
FROM dataurnas.totais_versoes FINAL
ORDER BY nivel, abr, idg DESC, coletado_em DESC
LIMIT 1 BY nivel, abr;

-- Soma dos BUs (última versão) por município x último total oficial publicado.
CREATE OR REPLACE VIEW dataurnas.v_bu_municipio_x_oficial AS
SELECT b.uf AS uf, b.cd_mun AS cd_mun,
       b.secoes_bu, o.st AS secoes_totalizadas_oficial, o.ts AS secoes_total_oficial,
       b.votos_13 AS bu_13, o.cand['13'] AS oficial_13,
       b.votos_22 AS bu_22, o.cand['22'] AS oficial_22,
       b.brancos AS bu_brancos, o.vb AS oficial_brancos,
       b.nulos AS bu_nulos, o.tvn AS oficial_nulos,
       toInt64(b.votos_13) - toInt64(o.cand['13']) AS dif_13,
       toInt64(b.votos_22) - toInt64(o.cand['22']) AS dif_22,
       o.totalizado_em AS totalizado_em
FROM
(
    SELECT uf, cd_mun, count() AS secoes_bu,
           sum(votos_13) AS votos_13, sum(votos_22) AS votos_22,
           sum(brancos) AS brancos, sum(nulos) AS nulos
    FROM dataurnas.v_votos_t2_secao
    GROUP BY uf, cd_mun
) AS b
LEFT JOIN (SELECT * FROM dataurnas.v_totais_ultima WHERE nivel = 'municipio') AS o
    ON o.uf = b.uf AND o.cd_mun = b.cd_mun;

-- Contagem de seções com BU por UF (validação rápida da carga).
CREATE OR REPLACE VIEW dataurnas.v_contagem_uf AS
SELECT uf,
       uniqExact(cd_mun, zona, secao) AS secoes_com_bu,
       count() AS versoes_bu,
       countIf(erro != '') AS bu_com_erro
FROM dataurnas.bu_secao FINAL
GROUP BY uf
ORDER BY uf;
