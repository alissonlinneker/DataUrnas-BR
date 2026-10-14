# Changelog

Todas as mudanças relevantes deste projeto são registradas aqui.

O formato segue o [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e o projeto adota o [Versionamento Semântico](https://semver.org/lang/pt-BR/).

## [Não publicado]

### Adicionado

- Parser do Registro Digital do Voto de 2026 (`parsers/rdv.py`, spec v2) e recontagem do RDV contra o BU da mesma seção em todos os cargos (`scripts/ele2026/fetch_rdv.py`, `analyzer/rdv_recontagem.py`), com conferência dos registros contra o comparecimento, da estrutura do RDV e do SHA-512 contra o catálogo de integridade. No Acre e em Roraima (3.789 seções, 4.920.752 registros), todas as seções e cargos conferem.
- Auditoria de BU e log de 2026 regerada no mesmo download, com o log de contingência lido por inteiro (`data/parquet/2026/auditoria_v2/`, mesmo esquema da publicada, e `comparacao.json` com as diferenças por coluna e por código).
- Linha do tempo dos votos no log por seção: votos computados x comparecimento do BU, votos antes das 8h de Brasília, fora da sequência de abertura e encerramento, pico por minuto, intervalos e lacunas. Resultados em `data/parquet/2026/rdv/`.

### Corrigido

- Log de 2026 com troca de urna: o `-log.jez` traz o log da urna substituída como `.jez` aninhado, e o parser lia esse ZIP aninhado como texto em vez do `logd.dat`. Agora lê os dois logs, o da urna substituída primeiro. A auditoria de BU e log já publicada (`secoes_log_2026.parquet`) registra `votos_log` 0 em 7.675 seções com log; nas 21 de AC e RR conferidas, a causa é essa. A versão corrigida sai em `auditoria_v2/`.

## [0.2.1] - 2026-10-14

### Adicionado

- Verificação de integridade dos arquivos de urna de 2026 em todas as seções (`scripts/ele2026/fetch_integridade.py`): SHA-512 do BU, do RDV e do log recalculado a partir dos arquivos publicados e comparado ao valor assinado no `.vsc`, verificação da assinatura de hardware de cada urna (Ed521 da ICP-Brasil, em `parsers/ed521.py`, e ECDSA P-521) e comparação dos votos do BU assinado com os do BU coletado. Resultado em 499.207 seções: 1.497.620 SHA-512 iguais ao assinado, nenhum divergente, 499.207 assinaturas válidas e nenhuma inválida.
- Catálogo por arquivo (`arquivos_<uf>.parquet`, com MD5, SHA-256, SHA-512, SHA-512 assinado, token, `disponivel` e `http_status`), resumo por seção (`secoes.parquet`) e `resumo.json` em `data/parquet/2026/integridade`. O catálogo de 1.999.485 arquivos é publicado como anexos desta versão, um Parquet por UF com `SHA256SUMS` (`scripts/ele2026/publicar_catalogo.py`), e o painel baixa sob demanda a UF consultada.
- Auditoria de BU e log de 2026 (`data/parquet/2026/auditoria/issues_2026.parquet` e `secoes_log_2026.parquet`): nenhuma ocorrência do grupo 1 nas 499.207 seções.
- Grupos de leitura dos códigos de ocorrência (indício direto de adulteração, inconsistência a investigar, operacional ou estatístico), com fonte única em `dashboard/reference.py`, filtro no painel e resumo em três quadros; inclui as categorias da conferência de integridade de 2026.
- Análise dos certificados das urnas (`scripts/ele2026/analisar_certificados.py`): unicidade, CN igual ao número interno da urna, emissor e algoritmo por modelo e validação da cadeia até a AC intermediária com os certificados públicos das AC em `data/certificados/`. Validação da cadeia concluída na amostra de 5%, sorteio determinístico pelo SHA-256 da chave da seção (24.846 seções, todas com cadeia conferida e certificado válido no dia da eleição); resultado em `certificados_resumo.json` e `certificados.parquet`.
- Registro de lacunas de publicação (`ocorrencias_publicacao.jsonl`, `scripts/ele2026/registrar_ocorrencias_publicacao.py`): arquivos listados no `aux.json` que o servidor do TSE responde com HTTP 404. Na passagem final, 2.658 imagens do BU em seções com status "Recebida"; e um RDV assinado pela urna e não publicado (`divergencias.jsonl`, categoria `arquivo_ausente_tse`).
- Página **Integridade dos arquivos (2026)** no painel, com consulta por seção e totais por UF.
- Documentos `docs/relatorio-integridade-2026.md` (gerado por `scripts/docs/gerar_relatorio_integridade.py`), `docs/investigacao-secoes-recebidas-2026.md` e `docs/relatorio-tse-ocorrencias-2026.md`.

### Corrigido

- Verificação de integridade: um arquivo listado no `aux.json` que responde HTTP 404 não derruba mais a seção; vira linha com `disponivel = false`, e o restante da seção continua sendo conferido.
- Deploy: o Space passa a receber os agregados do painel pré-calculados, e o build deixa de estourar o tempo limite.
- Relatório de integridade: o passo a passo de conferência manual usa o diretório de publicação correto (o campo `hash` do `aux.json`, que é o token em hexadecimal) e o leitor de assinatura de 2026 (`verificar_vsc`).

## [0.2.0] - 2026-10-13

### Adicionado

- Eleições 2026 (Presidente, 1º turno, 04/10/2026): resultado oficial agregado do Brasil, das 27 UFs, do exterior e de 5.757 municípios em `data/parquet/2026/` (`candidatos`, `resultado_uf`, `resultado_municipio`, `resumo_br.json`).
- Coleta dos Boletins de Urna de 2026 por seção (`scripts/ele2026/fetch_secoes.py`), com checkpoint, retomada, gravação em partes Parquet e consolidação deduplicada em `secoes_2026.parquet` e `votos_presidente_2026.parquet`.
- Reconciliação da soma dos BUs com o resultado oficial por UF (`scripts/ele2026/reconcile.py`).
- Módulo `downloader/ele2026.py` com URLs e transformações da API de 2026 (spec ASN.1 v2).
- Página inicial do painel com o resultado do 1º turno de 2026 e painel reorganizado em várias páginas, componentes e estado compartilhado.
- Novos códigos de ocorrência: E01 (assinatura não verificável), E02 (BU não decodificável, seção excluída dos totais) e E03 (duração negativa no log).
- Módulo `analyzer/timezones.py` com o fuso de cada UF e `database/rows.py` com a montagem única das linhas do banco.
- Suíte de testes com fixtures sintéticas geradas a partir das especificações ASN.1 (parsers, analisadores, banco, CLI, downloader e transformações de 2026).
- Integração contínua (`ci.yml`) com ruff e pytest em Python 3.11 e 3.12; o deploy passa a depender dela.
- `requirements-dev.txt`, extras `dashboard` e `dev` no `pyproject.toml` e configuração do ruff.
- `.dockerignore`, configuração do Streamlit em `.streamlit/config.toml`, `HEALTHCHECK` e usuário sem privilégios na imagem Docker.
- `Makefile` com os alvos de uso comum (instalação, lint, testes, banco, painel, coleta e reconciliação de 2026, Docker) e opção `dataurnas --version`.
- Documentação em `docs/` (índice, metodologia, arquitetura, dados de 2026 e perguntas frequentes), identidade visual, licença, guia de contribuição, código de conduta, política de segurança, `CITATION.cff`, modelos de issue e PR e Dependabot.

### Alterado

- Downloader: retry com backoff exponencial e jitter para 5xx, 408, 429 e erros de transporte (incluindo `ConnectTimeout` e `RemoteProtocolError`), respeitando `Retry-After`; escrita atômica via arquivo `.part` e `os.replace`; resultado explícito por arquivo (`DownloadResult`); padrões de concorrência (50) e taxa (200 req/s) conservadores e configuráveis por `DATAURNAS_MAX_CONCURRENT` e `DATAURNAS_RATE_LIMIT`.
- Compilação do DuckDB em transações por lote, com remoção das linhas filhas antes de reprocessar uma seção e modo incremental (`dataurnas db build --incremental`).
- `scripts/rebuild_parallel.py` passa a reutilizar a montagem de linhas do pacote em vez de duplicá-la.
- CLI valida a UF com a lista oficial de estados.
- Metadados do pacote completos no `pyproject.toml` (autor, palavras-chave, classificadores e links do projeto).
- Acentuação corrigida em mensagens, textos de ajuda, comentários e docstrings.
- Dockerfile copia uma lista explícita de arquivos e constrói o banco durante o build.
- Workflow de deploy envia o token por cabeçalho HTTP e roda a CI antes de publicar.

### Corrigido

- Verificação de hash: o parser de assinatura lia um campo com nome errado e nenhuma comparação era feita. Agora usa `arquivosAssinados` e localiza o arquivo assinado no diretório da seção.
- Hash não verificável (arquivo ausente ou ilegível) deixa de ser reportado como C01 e passa a ser E01.
- `tipoVoto` desconhecido no BU deixa de ser contado como voto nominal; o BU é rejeitado e a seção recebe E02.
- Modelo da urna lido corretamente do arquivo de assinatura, em todas as variantes de codificação.
- Contagem de arquivos ignorados no relatório de download, que nunca era incrementada.
- Cliente HTTP falhava ao ser criado quando o pacote opcional `h2` não estava instalado.
- Leitura do log em memória, com limite de tamanho descompactado.
- Números de candidato tratados conforme a circunscrição do cargo (nacional, estadual ou municipal).

### Segurança

- `.env` e arquivos locais não entram mais na imagem Docker.
- Ações do GitHub fixadas por hash de commit e permissões mínimas nos workflows.

## [0.1.0] - 2026-02-19

### Adicionado

- Auditoria independente das Eleições Presidenciais de 2022: 941.987 seções dos dois turnos, em todas as UFs.
- Downloader assíncrono da API hierárquica do TSE.
- Parsers de BU e assinatura (ASN.1/BER, specs v1 e v2) e de log (7z).
- Verificações de integridade, consistência, log e estatística, com códigos de ocorrência e base legal.
- Correção do acúmulo de eventos do 1º turno nos logs do 2º turno.
- Banco DuckDB, exportação Parquet com ZSTD e painel Streamlit com filtros e exportação.
- Deploy no Hugging Face Spaces via GitHub Actions.

[Não publicado]: https://github.com/alissonlinneker/DataUrnas-BR/compare/v0.2.1...HEAD
[0.2.1]: https://github.com/alissonlinneker/DataUrnas-BR/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/alissonlinneker/DataUrnas-BR/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/alissonlinneker/DataUrnas-BR/releases/tag/v0.1.0
