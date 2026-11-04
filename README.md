<p align="center">
  <img src="docs/assets/banner.png" alt="DataUrnas-BR: auditoria independente dos arquivos públicos da urna eletrônica" width="100%">
</p>

<p align="center">
  <a href="https://github.com/alissonlinneker/DataUrnas-BR/actions/workflows/ci.yml"><img src="https://github.com/alissonlinneker/DataUrnas-BR/actions/workflows/ci.yml/badge.svg?branch=main" alt="CI"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/licen%C3%A7a-MIT-0B3A5B.svg" alt="Licença MIT"></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.11%20%7C%203.12-0072B2.svg" alt="Python 3.11 e 3.12"></a>
  <a href="https://huggingface.co/spaces/alissonlinneker/dataurnas-br"><img src="https://img.shields.io/badge/demo-Hugging%20Face%20Spaces-E69F00.svg" alt="Demo no Hugging Face Spaces"></a>
</p>

# DataUrnas-BR

Auditoria independente e reprodutível dos **arquivos públicos da urna eletrônica brasileira** publicados pelo Tribunal Superior Eleitoral (TSE).

O projeto baixa os arquivos que cada urna gera ao fim da votação, decodifica o Boletim de Urna (BU), o log e o arquivo de assinatura digital, refaz a totalização a partir dos dados brutos e aplica verificações de consistência lógica, comportamento operacional, padrões estatísticos e, opcionalmente, de integridade criptográfica. Em 2026 o Registro Digital do Voto (RDV) também é decodificado e recontado em todas as seções dos dois turnos; a imagem do BU é baixada e tem o hash conferido, mas não é decodificada. Tudo é feito com dados abertos, código aberto e resultados versionados, para que qualquer pessoa possa repetir o processo e chegar aos mesmos números.

> **[Abrir o painel online](https://huggingface.co/spaces/alissonlinneker/dataurnas-br)**, sem instalação.

---

## Sumário

- [Destaques](#destaques)
- [Veredicto da auditoria 2026](#veredicto-da-auditoria-2026)
- [Eleições 2026: Presidente, 1º e 2º turnos](#eleições-2026-presidente-1º-e-2º-turnos)
- [Eleições 2022: cobertura completa](#eleições-2022-cobertura-completa)
- [Arquitetura](#arquitetura)
- [Pipeline](#pipeline)
- [Metodologia](#metodologia)
- [Códigos de inconsistência](#códigos-de-inconsistência)
- [Painel interativo](#painel-interativo)
- [Instalação](#instalação)
- [Uso](#uso)
- [Deploy](#deploy)
- [Estrutura do projeto](#estrutura-do-projeto)
- [Documentação](#documentação)
- [Fontes de dados e legislação](#fontes-de-dados-e-legislação)
- [Limitações](#limitações)
- [Status do projeto e roadmap](#status-do-projeto-e-roadmap)
- [Como citar](#como-citar)
- [Contribuindo](#contribuindo)
- [Licença](#licença)

---

## Destaques

- **2022 completo:** 941.987 seções dos dois turnos da eleição presidencial, em todas as 27 UFs, decodificadas e auditadas.
- **2026 completo, nos dois turnos:** resultado oficial agregado (Brasil, 27 UFs, exterior e 5.757 municípios) e os Boletins de Urna de todas as 499.207 seções instaladas em cada turno. A soma dos BUs reproduz exatamente o resultado oficial: no 1º turno em todas as 28 UFs (27 mais o exterior) e nos 5.757 municípios; no 2º turno, voto a voto no total do Brasil (13: 64.256.232; 22: 59.826.041).
- **[Veredicto da auditoria 2026](#veredicto-da-auditoria-2026):** 26 verificações nos dois turnos, sem nenhuma evidência de manipulação, de contagem errada ou de dado impossível nos arquivos públicos. O limite real também está descrito: o software que rodou em cada urna não é verificável com dados públicos.
- **RDV recontado em todas as seções dos dois turnos:** no 1º turno, 749.119.391 registros de voto em 499.206 seções, iguais ao BU em todos os cargos; no 2º turno, 499.205 seções com RDV, iguais ao BU, e a soma nacional do RDV é exatamente o resultado oficial. Nenhuma divergência. Detalhes na [recontagem do 1º turno](#recontagem-voto-a-voto-pelo-rdv-2026) e na [do 2º turno](#integridade-e-recontagem-do-2º-turno).
- **Integridade dos arquivos de 2026 concluída nos dois turnos:** no 1º turno, 1.497.620 SHA-512 de BU, RDV e log conferem com o valor assinado pela urna; no 2º turno, 5.487.289 assinaturas de hardware de todos os arquivos listados no `.vsc` são válidas. Nenhum hash divergente e nenhuma assinatura inválida. Detalhes no [resultado do 1º turno](#integridade-dos-arquivos-resultado), no [relatório de integridade](docs/relatorio-integridade-2026.md) e nos [certificados do 2º turno](docs/certificados-2turno-2026.md).
- **Resultados assinados pelo TSE conferidos:** as 11.572 assinaturas JWS dos resultados divulgados nos dois turnos (Brasil, 28 UFs e 5.757 municípios) são válidas e iguais à soma dos BUs ([JWS](docs/jws-totalizacao-2026.md)).
- **Auditoria de BU e log de 2026:** nenhuma ocorrência do grupo 1 (indício direto de adulteração) nas 499.207 seções do 1º turno; nenhum valor impossível em 998.414 BUs dos dois turnos; certificados coerentes em todas as seções.
- **Totalização paralela:** os votos são somados a partir dos BUs e reconciliados com os totais oficiais, UF por UF.
- **Verificação criptográfica:** hashes SHA-512 de cada arquivo conferidos contra o arquivo de assinatura da urna. Feita em todas as seções de 2026 e de 2022 (1º e 2º turnos), com verificação da assinatura de cada urna: nenhum hash divergente e nenhuma assinatura inválida nas duas eleições.
- **Dados distribuídos em Parquet (ZSTD):** os 181 GB de arquivos brutos de 2022 viram cerca de 183 MB, prontos para consulta com DuckDB.
- **Painel web** em Streamlit, com filtros por turno, região, UF, município, modelo de urna, severidade e grupo de leitura das inconsistências.

---

## Veredicto da auditoria 2026

<p align="center">
  <img src="docs/assets/2026-veredicto.svg" alt="Resumo do veredicto da auditoria de 2026: 26 verificações nos dois turnos, nenhuma evidência de manipulação, de contagem errada ou de dado impossível; RDV recontado em 499.206 seções no 1º turno e 499.205 no 2º, sem divergência; 11.572 assinaturas JWS dos resultados válidas; margem oficial do 2º turno de 4.430.191 votos" width="100%">
</p>

> **Não foi encontrada nenhuma evidência de manipulação, de contagem errada de votos ou de dado impossível nos arquivos públicos, em nenhum dos dois turnos de 2026.**

O resultado divulgado é exatamente a soma dos boletins assinados pelas urnas. O Registro Digital do Voto (RDV), recontado em todas as seções dos dois turnos, dá exatamente os mesmos números. Os boletins são coerentes por dentro e com o log de cada eleitor, e nenhum padrão estatístico de 2026 foge do que se observou em 2022 com a mesma metodologia.

Isso não prova que o software da urna é honesto. Os arquivos públicos não permitem ligar o programa que rodou em cada urna à lista de hashes lacrada: o `.vsc` assina só os arquivos de resultado, e o log registra o nome de cada pacote verificado e "SUCESSO", nunca o hash. Essa ligação só é feita por amostragem, em cerimônias cujos relatórios não são publicados. Uma alteração aplicada igualmente a todas as urnas também não aparece em testes que comparam grupos de urnas; a proteção contra ela é o Teste de Integridade, cujo relatório do 2º turno ainda não saiu. A próxima verificação independente ao alcance de qualquer pessoa é o **confronto dos BUs do TSE com os boletins impressos** afixados nas seções, lidos pelo QR Code: no 1º turno, 38 de 38 conferiram ([confronto com fontes externas](docs/confronto-fontes-externas.md)); no 2º turno, a Totalização Paralela do CMInd tinha 59 BUs às 22h30 de 25/10 ([verificações externas](docs/verificacoes-externas-2turno-2026.md), seção 3).

Foram encontrados pontos de transparência e de registro que pedem esclarecimento do TSE (13 pendências, listadas no veredicto). Nenhum deles, isolado ou somado, mexe na contagem ou chega perto da margem.

| # | Verificação | Escopo | Resultado | Documento |
|---|---|---|---|---|
| 1 | Coleta versionada dos arquivos, com reconferência por ETag/MD5 | 499.207 seções do 2º turno, 8 voltas completas (25 a 27/10) | 0 arquivos alterados ou removidos; nenhum BU com segunda versão | [Verificações externas](docs/verificacoes-externas-2turno-2026.md) |
| 2 | Assinatura de todos os arquivos de cada seção e cadeia de certificados | 499.207 seções, 5.487.289 assinaturas | 0 inválidas; SHA-512 do BU confere em todas | [Certificados do 2º turno](docs/certificados-2turno-2026.md) |
| 3 | Soma dos BUs x resultado oficial | Brasil, UFs e 5.757 municípios, dois turnos | Igual voto a voto | [Consistência dos BUs](docs/auditoria-consistencia-bu-2026.md) |
| 4 | Totais divulgados ao longo da noite | 12 mil versões coletadas | Nunca diminuíram; sempre fecharam | [Verificações externas](docs/verificacoes-externas-2turno-2026.md) |
| 5 | Valores impossíveis no BU | 998.414 BUs | 0 impossíveis | [Consistência dos BUs](docs/auditoria-consistencia-bu-2026.md) |
| 6 | Recontagem voto a voto pelo RDV x BU | 499.206 seções no 1º turno e 499.205 no 2º | 0 divergências; soma do RDV do 2º turno igual ao oficial | [RDV x BU x log](docs/rdv-log-2026.md) |
| 7 | Log eleitor a eleitor x BU | 2.997 seções, dois turnos | Votos no log = comparecimento em todas; 0 votos fora do horário | [RDV x BU x log](docs/rdv-log-2026.md) |
| 8 | Encerramento tardio (prorrogação até 19h) e impacto na margem | 497.897 seções; logs de 21.317 | 5.129 votos depois das 17h nas tardias; margem nunca inverte (pior cenário 4.398.399) | [Encerramento tardio](docs/encerramento-tardio-2turno-2026.md) |
| 9 | BUs emitidos mais de 1 h depois do encerramento | 368 seções e 368 controles | 0 votos depois do encerramento, 0 reabertura | [Consistência dos BUs](docs/auditoria-consistencia-bu-2026.md) |
| 10 | Viradas por seção do 1º para o 2º turno, com modelo de 2022 | 497.897 seções | 31.341 viradas para o 13 contra 32.604 esperadas | [Viradas](docs/viradas-1t-2t-2026.md) |
| 11 | Estatística forense com 2022 de controle | todas as seções, 2022 e 2026 | Nenhum padrão de 2026 maior que o de 2022 | [Forense estatística](docs/forense-estatistica-2026.md) |
| 12 | Efeito do modelo de urna, troca, recarga, reserva e contingência | 499 mil seções | Nenhum efeito capaz de mover a margem | [Efeito da urna](docs/efeito-urna-2026.md) |
| 13 | Biometria 1º x 2º turno e votos sem digital | 497.895 seções; logs de 2.997 | Variações de décimos de ponto; voto sem digital não favorece nenhum candidato | [Biometria](docs/biometria-1t-2t-2026.md) |
| 14 | Cargas das urnas x logs de preparação GEDAI | 499.207 BUs | 99,83% conferem em todos os campos; 862 sem log | [GEDAI](docs/gedai-2turno-2026.md) |
| 15 | Linha do tempo: emissão, recebimento e totalização | todas as seções | Nenhum BU emitido depois de totalizado | [Verificações externas](docs/verificacoes-externas-2turno-2026.md) |
| 16 | Dados abertos do TSE x BU | dois turnos, todas as seções | 0 divergências de voto | [Dados abertos](docs/confronto-dados-abertos-2026.md) |
| 17 | Lista oficial de hashes x programas verificados nos logs | 32 listas; 6.732 logs | Todos os programas de inicialização estão na lista | [Hash do software](docs/hash-software-urna-2026.md) |
| 18 | Assinatura JWS dos resultados divulgados x soma dos BUs | 5.786 arquivos por turno, dois turnos | 11.572 assinaturas válidas; 0 divergências | [JWS](docs/jws-totalizacao-2026.md) |
| 19 | Alegações externas ("virada única", "vales igualmente espaçados") | 2022 e 2026 | Explicadas pela ordem geográfica de chegada | [Ordem de envio](docs/ordem-de-envio-viradas-2022-2026.md) |
| 20 | Pacote oficial do 2º turno x arquivos guardados na noite da eleição | 998.356 arquivos | Todos idênticos; nenhum total novo depois de 25/10 | [Verificações externas](docs/verificacoes-externas-2turno-2026.md) |
| 21 | Imagem do BU x BU e log eleitor a eleitor x BU no pacote completo | 499.207 seções por turno | Votos iguais em todas; diferenças de log explicadas e sem efeito no voto | [Pacote nacional](docs/pacote-nacional-imgbu-logs-2026.md) |
| 22 | Ordem e horário de chegada dos BUs x voto | 499.205 seções, 2022 de controle | Nenhum sinal de injeção | [Chegada dos BUs](docs/chegada-bus-2026.md) |
| 23 | Plausibilidade da virada (história, pesquisas, transferências, simulação de fraude, eleitorado x população) | Brasil 1994 a 2026 e 31 casos internacionais | Chance de virada perto de 50% pela margem; fraude concentrada apareceria | [Virada e probabilidades](docs/virada-2026-probabilidades.md) |
| 24 | Zerésima em todas as urnas | 998.354 logs, dois turnos | Nenhum voto antes da zerésima; 2 seções sem zerésima no log publicado por falta do log da urna que abriu a votação | [Zerésima](docs/zeresima-2026.md) |
| 25 | Coerência entre cargos no mesmo BU e voto dividido | 787.986 BUs (2026 e 2022) | 0 BUs com cargos incoerentes; voto dividido dentro da faixa de 2022 | [Coerência entre cargos](docs/coerencia-cargos-2026.md) |
| 26 | Últimas seções recebidas no 1º turno (PR, 07/10) | 500 seções do PR | Já somadas no resultado de 05/10; 07/10 é reenvio do mesmo pacote | [Seções tardias do PR](docs/pr-secoes-tardias-1t-2026.md) |

O texto completo, com o que não pode ser verificado e as 13 pendências para o TSE, está em [docs/veredicto-auditoria-2026.md](docs/veredicto-auditoria-2026.md).

---

## Eleições 2026: Presidente, 1º e 2º turnos

Os números de resultado abaixo são os **totais oficiais divulgados pelo TSE**, lidos de `data/parquet/2026/resumo_br.json` (1º turno) e `data/parquet/2026/t2/resumo_br.json` (2º turno). Eles são reproduzidos como referência para a reconciliação feita pelo projeto, sem qualquer interpretação política.

### 2º turno (25/10/2026)

Totalização final de 25/10/2026, 23:26:38 (eleição 6258, pleito 3221), com 499.248 de 499.248 seções totalizadas.

#### Resultado do 2º turno

<p align="center">
  <img src="docs/assets/2026-t2-resultado.svg" alt="Resultado do 2º turno de 2026: Lula (PT) com 64.256.232 votos (51,79% dos válidos), eleito, e Flávio Bolsonaro (PL) com 59.826.041 (48,21%); margem de 4.430.191 votos" width="100%">
</p>

| Nº | Candidato (nome de urna) | Partido | Votos | % dos válidos | Situação |
|---:|---|---|---:|---:|---|
| 13 | LULA | PT | 64.256.232 | 51,79% | Eleito |
| 22 | FLÁVIO BOLSONARO | PL | 59.826.041 | 48,21% | Não eleito |

Margem: **4.430.191 votos**.

#### Resultado por UF no 2º turno

<p align="center">
  <img src="docs/assets/2026-t2-mapa-lider.svg" alt="Mapa do Brasil por UF colorido pelo candidato mais votado no 2º turno de 2026: Lula lidera em 13 UFs (todo o Nordeste, Minas Gerais, Amazonas, Pará e Amapá) e no exterior; Flávio Bolsonaro lidera em 14 (Sul, São Paulo, Rio de Janeiro, Espírito Santo, Centro-Oeste, Distrito Federal, Acre, Rondônia, Roraima e Tocantins). Maior fatia do 13 no Piauí (75,9%) e do 22 em Roraima (72,5%)" width="100%">
</p>

Em relação ao 1º turno, Minas Gerais passou a ter o 13 à frente (50,43% dos votos dos dois candidatos). Os votos por UF e por município estão em `data/parquet/2026/t2/resultado_uf.parquet` e `resultado_municipio.parquet`.

#### Comparecimento no 2º turno

| Métrica | Valor |
|---|---:|
| Eleitorado apto | 158.745.502 |
| Comparecimento | 128.236.074 (80,78%) |
| Abstenção | 30.509.005 (19,22%) |
| Votos válidos (nominais) | 124.082.273 |
| Votos em branco | 1.430.496 (1,12%) |
| Votos nulos | 2.723.305 (2,12%) |
| Seções totalizadas | 499.248 de 499.248 |
| Seções não instaladas | 41 |

<p align="center">
  <img src="docs/assets/2026-t2-comparecimento.svg" alt="Comparecimento por UF no 1º e no 2º turno de 2026: no Brasil (sem o exterior) passou de 79,2% para 81,0%; as maiores altas foram na Bahia (+3,3 pontos), em Pernambuco (+3,0) e em São Paulo (+2,7) e as maiores quedas no Amapá (-8,1), em Roraima (-6,0) e no Acre (-5,7)" width="100%">
</p>

O comparecimento subiu 2.960.239 eleitores em relação ao 1º turno. A [análise de biometria](docs/biometria-1t-2t-2026.md) (seção 9) mostra que o aumento se divide entre os candidatos na mesma proporção, com ou sem digital.

#### Integridade e recontagem do 2º turno

<p align="center">
  <img src="docs/assets/2026-t2-integridade.svg" alt="Integridade dos arquivos do 2º turno de 2026: 499.207 seções verificadas, 5.487.289 assinaturas de hardware válidas e nenhuma inválida; RDV recontado em 499.205 seções sem nenhuma divergência; soma do RDV igual ao resultado oficial" width="100%">
</p>

| Verificação | Resultado |
|---|---:|
| Seções com BU coletadas e conferidas | 499.207 |
| Assinaturas de hardware de todos os arquivos listados no `.vsc` válidas | 5.487.289 |
| Assinaturas inválidas | **0** |
| Certificado da urna assinado pela AC emissora e válido no dia | 499.207 |
| Seções com RDV recontado | 499.205 (as 2 restantes, do exterior, tiveram comparecimento 0) |
| RDV diferente do BU | **0** |
| Soma nacional do RDV: 13 / 22 | 64.256.232 / 59.826.041 (igual ao oficial) |
| Arquivos alterados ou removidos depois de publicados (8 voltas de reconferência) | **0** |

A soma dos BUs do 2º turno é igual ao último total do Brasil em 13, 22, brancos, nulos e comparecimento, e as assinaturas JWS dos resultados divulgados conferem com essa soma em todos os níveis. O método e as tabelas por UF estão na [recontagem nacional](docs/rdv-log-2026.md) (seção 5) e nos [certificados do 2º turno](docs/certificados-2turno-2026.md).

#### Outras verificações do 2º turno

- **Encerramento tardio:** a votação foi prorrogada até 19h por decisão do STF ([prorrogação](docs/prorrogacao-votacao-2turno-2026.md)). Nas 7.580 seções tardias com log, 5.129 votos foram computados depois das 17h; a estimativa para o país é de cerca de 31.792. Mesmo retirando todos do 13, a margem fica em 4.398.399 ([encerramento tardio](docs/encerramento-tardio-2turno-2026.md)).
- **Viradas por seção:** 31.341 seções passaram do 22 para o 13 entre os turnos, contra 32.604 esperadas pelo modelo de 2022 ([viradas](docs/viradas-1t-2t-2026.md)).
- **Equipamento e preparação:** nenhum efeito de modelo, troca, recarga, reserva ou contingência capaz de mover a margem ([efeito da urna](docs/efeito-urna-2026.md)); 99,83% das cargas conferem com os logs GEDAI ([GEDAI](docs/gedai-2turno-2026.md)).
- **Dados abertos:** nenhuma divergência de voto entre os produtos do portal do TSE e os BUs assinados; as divergências são de registro de urna e de marcas de controle ([dados abertos](docs/confronto-dados-abertos-2026.md)).
- **Base de análise:** as versões publicadas foram guardadas e indexadas num banco ClickHouse ([banco](docs/banco-clickhouse.md)).

### 1º turno (04/10/2026)

Totalização de 05/10/2026, 12:51:05 (eleição 6257, pleito 3220).

#### Resultado nacional

<p align="center">
  <img src="docs/assets/2026-ranking.svg" alt="Gráfico de barras com os votos de cada candidato a Presidente no 1º turno de 2026: Flávio Bolsonaro (PL) com 56.104.503 votos (47,03% dos válidos) e Lula (PT) com 53.879.538 (45,16%) vão ao 2º turno; os demais somam menos de 8%" width="100%">
</p>

| Nº | Candidato (nome de urna) | Partido | Votos | % dos válidos | Situação |
|---:|---|---|---:|---:|---|
| 22 | FLÁVIO BOLSONARO | PL | 56.104.503 | 47,03% | 2º turno |
| 13 | LULA | PT | 53.879.538 | 45,16% | 2º turno |
| 70 | ESCRITOR AUGUSTO CURY | AVANTE | 3.448.569 | 2,89% | Não eleito |
| 14 | RENAN SANTOS | MISSÃO | 2.675.887 | 2,24% | Não eleito |
| 55 | RONALDO CAIADO | PSD | 2.605.148 | 2,18% | Não eleito |
| 30 | ZEMA | NOVO | 326.488 | 0,27% | Não eleito |
| 80 | SAMARA | UP | 122.911 | 0,10% | Não eleito |
| 16 | HERTZ DIAS | PSTU | 43.103 | 0,04% | Não eleito |
| 27 | CLARIANA BARAO | DC | 40.043 | 0,03% | Não eleito |
| 21 | EDMILSON COSTA | PCB | 22.693 | 0,02% | Não eleito |
| 35 | VETERINÁRIO WILSON GRASSI | DEMOCRATA | 16.881 | 0,01% | Não eleito |
| 29 | RUI COSTA PIMENTA | PCO | 15.024 | 0,01% | Não eleito |

Os nomes são os de urna publicados pelo TSE, em maiúsculas. O TSE divulga parte deles sem acento; aqui o acento foi restituído apenas onde a grafia do prenome é inequívoca (FLÁVIO). Sobrenomes ficam como registrados.

#### Resultado por UF

<p align="center">
  <img src="docs/assets/2026-mapa-lider.svg" alt="Mapa do Brasil por UF colorido pelo candidato mais votado no 1º turno de 2026: Flávio Bolsonaro lidera em 15 UFs, concentradas no Sul, Sudeste, Centro-Oeste e parte do Norte; Lula lidera em 12 (todo o Nordeste, Amazonas, Pará e Amapá) e também no exterior" width="100%">
</p>

O tom forte indica que o líder teve 50% ou mais dos votos válidos na UF; o tom claro, menos de 50%. Os votos de cada candidato por UF e por município estão em `resultado_uf.parquet` e `resultado_municipio.parquet`.

#### Comparecimento e votos

| Métrica | Valor |
|---|---:|
| Eleitorado apto | 158.745.502 |
| Comparecimento | 125.275.835 (78,92%) |
| Abstenção | 33.469.244 (21,08%) |
| Votos válidos (nominais) | 119.300.788 |
| Votos em branco | 2.300.798 (1,84%) |
| Votos nulos (inclui 5.246 nulos técnicos) | 3.674.249 (2,93%) |
| Seções totalizadas | 499.248 de 499.248 |
| Seções não instaladas | 41 |

Fonte: TSE, [Resultados](https://resultados.tse.jus.br/oficial/), eleição 6257, pleito 3220. Percentuais dos válidos conforme o próprio TSE.

<p align="center">
  <img src="docs/assets/2026-comparecimento.svg" alt="Gráfico de halteres com o comparecimento por UF no 1º turno de 2022 e de 2026: no Brasil (sem o exterior) passou de 79,3% para 79,2%; as maiores altas foram em Rondônia (+2,9 pontos) e Maranhão (+2,4) e as maiores quedas em Mato Grosso do Sul e Distrito Federal (cerca de 1,9 ponto)" width="100%">
</p>

Na comparação com o 1º turno de 2022 (sem o exterior), o comparecimento ficou praticamente estável: 79,3% em 2022 e 79,2% em 2026. Subiu em 11 UFs, caiu em 14 e variou menos de 0,1 ponto em 2 (Tocantins e Pernambuco). Os números de 2022 vêm dos boletins de urna por seção compilados pelo projeto; os de 2026, dos totais oficiais por UF.

#### O que já foi verificado

- A soma dos votos válidos por UF e por município bate exatamente com o total nacional (119.300.788 nas três agregações).
- Os 5.757 municípios (incluindo as cidades do exterior, agrupadas na UF `ZZ`) foram baixados sem nenhuma falha HTTP.
- Os BUs (formato ASN.1 v2, arquivos `-bu.dat`) de todas as 499.207 seções instaladas foram baixados e decodificados, sem nenhuma falha: 502.388 seções processadas, das quais 17.931 agregadas a outra seção e 41 não instaladas no exterior, gerando 3.800.511 linhas de votos.
- A soma dos BUs reproduz **exatamente** o resultado oficial em todas as 28 UFs (27 mais o exterior): votos de cada candidato, brancos, nulos, nulos técnicos e comparecimento (125.275.835 votos). Diferença zero em todos os itens, conferida por `reconcile.py`.
- Modelos de urna identificados pelo arquivo de assinatura: UE2020 (200.463 seções), UE2022 (198.759), UE2015 (88.064) e UE2013 (11.921).

Os esquemas de cada arquivo estão em [docs/dados-2026.md](docs/dados-2026.md).

#### Integridade dos arquivos (2026)

##### Integridade dos arquivos: resultado

> **Concluído** em 499.207 de 499.207 seções instaladas (100%), sem erros pendentes. **C01: zero hashes divergentes em 1.497.620 conferidos; zero assinaturas inválidas.**

Cada urna grava, ao encerrar a votação, o BU, o RDV e o log, e assina com a própria chave um arquivo (`.vsc`) que contém o SHA-512 de cada um deles. O projeto recalculou esses SHA-512 a partir dos arquivos que o TSE publica, comparou com os valores assinados, verificou a assinatura de cada urna e comparou os votos do BU assinado com os do BU lido na coleta de resultados. MD5 e SHA-256 também são catalogados, apenas para conferências futuras: não fazem parte do mecanismo da urna.

| Verificação | Resultado |
|---|---:|
| Seções com arquivos verificados | 499.207 (517.179 linhas, incluindo 17.931 agregadas e 41 não instaladas) |
| SHA-512 de BU, RDV e log iguais ao assinado pela urna | 1.497.620 |
| SHA-512 divergentes (C01) | **0** |
| Assinaturas de urna válidas | 499.207 (Ed521: 399.222; ECDSA P-521: 99.985) |
| Assinaturas inválidas | **0** |
| Votos do BU assinado iguais aos do BU coletado | 499.207 |
| RDV assinado pela urna e não publicado | 1 |
| Imagens do BU listadas no `aux.json` e indisponíveis (HTTP 404) | 2.658 |

<p align="center">
  <img src="docs/assets/2026-integridade.svg" alt="Integridade dos arquivos de urna de 2026: 499.207 seções verificadas em todas as UFs, 1.497.620 SHA-512 iguais ao assinado pela urna, nenhum divergente e 499.207 assinaturas válidas" width="100%">
</p>

**Dois pontos de publicação a informar ao TSE**, nenhum deles com divergência de conteúdo:

- **Um RDV não publicado.** Na seção 0228 da zona 0074 de Lagoa Grande do Maranhão (MA, município 07846), o `.vsc` traz o SHA-512 do `rdv.dat`, mas o `aux.json` lista só o log, o `.vsc` e o BU, e o endereço do RDV responde HTTP 404. O BU e o log dessa seção conferem com o que a urna assinou, a assinatura é válida e os votos do BU são os mesmos da coleta. É o único registro de `arquivo_ausente_tse` no país.
- **2.658 imagens do BU indisponíveis.** Em 2.658 seções (PA 1.613, PR 500, MA 403, BA 135, SP 4, RS 2, SC 1), o `aux.json` lista a imagem do BU (`imgbu.dat`) e o servidor responde HTTP 404. Todas estão com status "Recebida" e foram republicadas entre 05 e 07/10/2026; o BU, o RDV e o log delas foram conferidos normalmente. O registro `ocorrencias_publicacao.jsonl` tem 2.677 entradas porque, em 19 seções do PI, a imagem deixou de constar no `aux.json` quando a seção foi verificada de novo (não passou a ser servida). Detalhes na [investigação das seções "Recebida"](docs/investigacao-secoes-recebidas-2026.md).

São lacunas de publicação, não evidência de adulteração. Os pedidos de esclarecimento estão reunidos em [docs/relatorio-tse-ocorrencias-2026.md](docs/relatorio-tse-ocorrencias-2026.md).

**Auditoria do BU e do log (2026), por grupo de leitura.** Concluída em 499.207 seções: 256.306 ocorrências em 159.777 seções. Esta versão foi regerada com o leitor de log corrigido, que lê também o log da urna substituída nas seções com contingência e descarta cópias repetidas do mesmo log; as diferenças em relação à versão anterior estão em `data/parquet/2026/auditoria/comparacao_versao_anterior.json`.

| Grupo | Resultado |
|---|---|
| 1. Indício direto de adulteração | Nenhuma ocorrência de C01, C05, A02 ou A06. Na conferência dos arquivos, 1 registro: o RDV não publicado descrito acima. |
| 2. Inconsistência a investigar | Nenhuma ocorrência de A01. 2 A03 (votos no log diferentes do BU), nas seções em que o pacote publicado não traz o log da urna que recebeu parte dos votos (BA 39934/0183/0175 e SP 71072/0002/0035; ver a [investigação](docs/investigacao-log-bu-2026.md)). 31 M03 (abertura não encontrada no log), todas em seções com BU do sistema de apuração (votação por cédula), cujo log não tem abertura de urna. |
| 3. Operacional ou estatístico | I04 177.616, I03 35.631, C06 28.255 (23.488 de severidade média e 4.767 alta), I05 3.794, I06 3.064, I01 2.902, I02 2.693, A04 1.015, M04 563, M06 533, A05 88, M05 86, M02 33. |

**Certificados das urnas.** Em todas as 499.207 seções: cada modelo tem uma única AC emissora e um único algoritmo (AC URNA com ECDSA P-521 para UE2013 e UE2015; AC UE2020 e AC UE2022 com Ed521 para os modelos de mesmo nome); nenhuma urna aparece com dois certificados e nenhum certificado aparece em urnas diferentes; o CN (`UEAO` + 8 dígitos) segue o padrão em todas. Há 499.179 certificados distintos porque um certificado de urna de apuração do exterior assina 29 BUs do sistema de apuração. O CN é igual ao número interno da urna registrado na carga do BU em 499.193 seções; as 14 restantes, com hash e assinatura válidos, estão listadas no relatório para confirmação com o TSE. A **validação da cadeia** foi **concluída na amostra de 5%, sorteio determinístico** (24.846 seções de todas as UFs, escolhidas pelo SHA-256 da chave da seção): em 24.846 de 24.846 a assinatura do certificado conferiu com a chave da AC emissora e o certificado estava válido no dia da eleição. A cadeia vai **até a AC intermediária**: os certificados das raízes (AC RAIZ UE e AC RAIZ UE v2) e da AC URNA v2 não estão disponíveis publicamente. Os certificados públicos das AC estão em [`data/certificados/`](data/certificados/README.md); os da AC UE2020 e AC UE2022 conferem byte a byte com o SHA-512 publicado pelo TSE. Uma observação a esclarecer com o TSE: o certificado publicado da AC URNA venceu em 18/07/2026, e há certificado de urna emitido em 03/08/2026 que confere com a mesma chave; a explicação mais provável é um certificado renovado da AC URNA, com a mesma chave, que não foi publicado. Não é indício de adulteração.

**Onde ver os detalhes.**

- [Relatório de integridade](docs/relatorio-integridade-2026.md): totais, tabela por UF, divergências com endereços, arquivos indisponíveis, auditoria por código, certificados e o passo a passo para conferir qualquer seção à mão (gerado por `python scripts/docs/gerar_relatorio_integridade.py`).
- [Catálogo de hashes por arquivo](https://github.com/alissonlinneker/DataUrnas-BR/releases/tag/v0.2.1): MD5, SHA-256 e SHA-512 dos 1.999.485 arquivos, um Parquet por UF nos anexos da versão v0.2.1, conferível com `sha256sum -c SHA256SUMS`.
- No painel, a página **Integridade dos arquivos (2026)** permite consultar cada seção.

##### Recontagem voto a voto pelo RDV (2026)

> **Concluída** em 499.207 seções: **o RDV recontado é igual ao BU em 499.206 seções, em todos os cargos; nenhuma divergência.** A seção restante é a do RDV não publicado pelo TSE (Lagoa Grande do Maranhão).

O Registro Digital do Voto (RDV) guarda cada voto digitado na urna, embaralhado e sem identificação do eleitor. O projeto decodifica o RDV de cada seção (`spec/v2/rdv.asn1`), reconta os registros por cargo (voto nominal pelo número digitado, voto de legenda pelos dois primeiros dígitos, brancos e nulos, inclusive os registrados após suspensão da votação) e compara com o BU do mesmo pacote: votos de cada candidato e legenda, brancos, nulos e o número de registros, que deve ser igual ao comparecimento vezes o número de escolhas do cargo. Antes da recontagem, o SHA-512 de cada arquivo baixado é conferido com o catálogo de integridade.

| Cargo | Seções | Conferem | Divergem | Registros no RDV | Votos no BU |
|---|---:|---:|---:|---:|---:|
| Presidente | 499.206 | 499.206 | 0 | 125.275.616 | 125.275.616 |
| Governador | 497.896 | 497.896 | 0 | 124.768.266 | 124.768.266 |
| Senador (2 vagas) | 497.896 | 497.896 | 0 | 249.536.532 | 249.536.532 |
| Deputado Federal | 497.896 | 497.896 | 0 | 124.768.266 | 124.768.266 |
| Deputado Estadual | 490.927 | 490.927 | 0 | 122.950.345 | 122.950.345 |
| Deputado Distrital | 6.969 | 6.969 | 0 | 1.817.921 | 1.817.921 |
| Eleição 6261 (cargo 25) | 10 | 10 | 0 | 2.445 | 2.445 |

Nas seções cujo BU foi digitado no Sistema de Apuração (votação por cédula, inclusive os boletins do exterior apurados no SA), o RDV é gerado pelo próprio sistema a partir dos dados digitados; ali, RDV igual ao BU confirma a coerência do pacote, mas não é uma conferência independente do voto. Nessas seções o RDV pode trazer a eleição em blocos repetidos, um por urna ou mídia, que são somados antes da comparação.

**Log contra BU, voto a voto no tempo.** No mesmo download, o log de cada seção é lido por inteiro (inclusive o da urna substituída, nas seções com contingência) e os eventos "O voto do eleitor foi computado" do dia da eleição são comparados com o comparecimento do BU. Em 499.207 seções, o log confere com o BU em todas as seções de urna, exceto 9, que somam 59 votos a menos no log; nenhum voto fora da sequência de abertura e encerramento da urna. Nas 31 seções com BU do Sistema de Apuração a comparação não se aplica, porque o log do SA não registra votos. As 9 seções estão explicadas na [investigação log x BU](docs/investigacao-log-bu-2026.md): em 5 a urna travou logo depois do voto para Presidente sem gravar a linha do voto (o voto foi contado), em 3 o pacote publicado não traz o log da urna que recebeu parte dos votos (encaminhadas ao TSE) e em 1 a urna reiniciou 17 vezes no dia. O resultado não é afetado em nenhuma delas: o RDV recontado é igual ao BU.

Os resultados por seção estão em `data/parquet/2026/rdv/` (`recontagem_secoes.parquet`, `log_tempo_secoes.parquet`, `resumo.json`); o código está em `src/dataurnas/parsers/rdv.py`, `src/dataurnas/analyzer/rdv_recontagem.py` e `scripts/ele2026/fetch_rdv.py`.

##### Confronto com fontes externas

A única fonte pública e independente de boletins de 2026 encontrada é a Totalização Paralela do CMInd, que reúne leituras do QR Code dos BUs impressos nas seções. Em 14/10/2026 ela tinha 38 BUs do 1º turno (MG, RS, SC e SP). Os 38 tiveram a assinatura da própria urna verificada no QR Code e **todos conferem** com os dados do TSE: votos de cada candidato a Presidente, brancos, nulos, comparecimento, aptos, número da urna e código de carga. A amostra é pequena e não aleatória; serve para validar o método, não para concluir sobre o país. Detalhes em [docs/confronto-fontes-externas.md](docs/confronto-fontes-externas.md) e no script `scripts/externo/confrontar_bu_externo.py`.

---

## Eleições 2022: cobertura completa

<p align="center">
  <img src="docs/assets/2022-cobertura.svg" alt="Infográfico da cobertura de 2022: 941.987 seções auditadas nos dois turnos, 27 UFs, 72.943.229 registros de votos e 511.121 ocorrências (70.231 de severidade alta, 115.059 média e 325.831 informativa); urnas dos modelos UE2009 a UE2020, com o UE2020 em 40,9% das seções" width="100%">
</p>

| Métrica | Valor |
|---|---:|
| Seções eleitorais processadas | 941.987 |
| 1º turno (02/10/2022) | 470.986 seções |
| 2º turno (30/10/2022) | 471.001 seções |
| Linhas de votos por seção, cargo e candidato | 72.943.229 |
| Totais por cargo e seção | 3.074.096 |
| Ocorrências registradas | 511.121 |
| UFs | 27 |
| Modelos de urna | UE2009, UE2010, UE2011, UE2013, UE2015, UE2020 |
| Versão do software de votação | 8.26.0.0 (Onça-pintada) em 941.986 seções; uma seção sem versão registrada |

A maior parte das ocorrências é informativa (proporção elevada de brancos ou nulos, abstenção alta, urna de reserva) ou operacional (reinícios durante a votação, horários). Nenhuma seção de 2022 registrou mais votos que eleitores aptos (C05). **Integridade dos arquivos de 2022.** A base foi compilada sem a conferência de hashes, por ser uma etapa lenta; a conferência foi feita depois, à parte, a partir dos pacotes de dados abertos do TSE lidos por faixas de bytes (`scripts/ele2022/fetch_integridade.py`). Em 944.051 seções dos dois turnos: 3.776.042 SHA-512 iguais ao valor assinado pela urna, **nenhum divergente**; 944.051 assinaturas de urna válidas, **nenhuma inválida**; votos de Presidente do BU assinado iguais aos da base em 941.653 seções, nenhum diferente. A cadeia de certificados foi validada até a AC intermediária numa amostra estratificada de 5% (47.230 seções), sem nenhuma falha. Há 173 arquivos assinados pela urna e ausentes do pacote de dados abertos (64 seções, a maioria do exterior), listados para pedido de esclarecimento ao TSE. Detalhes em [docs/integridade-2022.md](docs/integridade-2022.md); o catálogo de hashes por arquivo está nos anexos da [v0.2.2](https://github.com/alissonlinneker/DataUrnas-BR/releases/tag/v0.2.2). O resultado é registrado em `data/parquet/metadados.parquet` e passa a valer no índice de confiança do painel depois de recompilar o banco (`make build-db`).

### Logs do 2º turno

Os arquivos `.logjez` do 2º turno **acumulam os eventos do 1º turno**: a urna não limpa o log entre os turnos. O parser filtra os eventos pela data do turno (02/10/2022 ou 30/10/2022). Sem esse filtro, 96% das seções do 2º turno exibiriam falsos reinícios, horário de abertura errado e contagem de votos no log duplicada.

---

## Arquitetura

<p align="center">
  <img src="docs/assets/arquitetura.svg" alt="Diagrama da arquitetura em cinco etapas: API pública do TSE, coleta (downloader e scripts de 2026), decodificação (BU em ASN.1, log da urna e assinatura; RDV e imagem do BU baixados, reservados para uso futuro), verificações (integridade, consistência, log e estatística) e, por fim, DuckDB com Parquet ZSTD e o painel Streamlit" width="100%">
</p>

<details>
<summary>Diagrama detalhado dos módulos (Mermaid)</summary>

```mermaid
flowchart TB
    TSE[("API pública do TSE<br/>resultados.tse.jus.br")]

    subgraph coleta["Coleta"]
        DL["downloader<br/>httpx assíncrono, retry com backoff,<br/>rate limit, escrita atômica"]
        E26["scripts/ele2026<br/>resultados agregados e BU por seção"]
    end

    subgraph decod["Decodificação"]
        BU["parsers.bu<br/>ASN.1/BER v1 e v2"]
        LOG["parsers.log<br/>7z, eventos do log"]
        SIG["parsers.signature<br/>hashes SHA-512"]
    end

    subgraph analise["Análise"]
        INT["integrity<br/>hashes, votos x aptos"]
        LA["log_analyzer<br/>reinícios, horários, A03"]
        ST["statistical<br/>brancos, nulos, biometria"]
        BA["batch<br/>orquestra por seção"]
    end

    subgraph dados["Dados"]
        PQ[("Parquet ZSTD<br/>data/parquet")]
        DB[("DuckDB<br/>secoes, votos, issues, totais_cargo")]
    end

    UI["Painel Streamlit<br/>páginas temáticas"]

    TSE --> DL --> BU & LOG & SIG
    TSE --> E26 --> PQ
    BU & LOG & SIG --> BA
    BA --> INT & LA & ST
    INT & LA & ST --> DB
    DB <--> PQ
    DB --> UI
```

</details>

Mais detalhes em [docs/arquitetura.md](docs/arquitetura.md).

---

## Pipeline

```mermaid
flowchart LR
    A["1. Download<br/>config, seção, aux.json, arquivos"] --> B["2. Decodificação<br/>BU, log, assinatura"]
    B --> C["3. Verificações<br/>integridade, consistência, log, estatística"]
    C --> D["4. Compilação<br/>DuckDB em lote"]
    D --> E["5. Exportação<br/>Parquet ZSTD"]
    E --> F["6. Painel<br/>consultas SQL e gráficos"]
```

1. **Download.** A API do TSE é hierárquica: configuração da eleição, configuração da UF (municípios, zonas e seções), arquivo auxiliar de cada seção (`aux.json`, com os hashes das urnas) e, por fim, os arquivos da urna. Em 2022 são `.bu`, `.rdv`, `.logjez`, `.imgbu` e `.vscmr`; em 2026 o BU é `-bu.dat` (ou `-busa.dat`, do Sistema de Apuração) e a assinatura é `-vota.vsc`. Em 2026 a coleta baixa apenas o BU e, opcionalmente, a assinatura.
2. **Decodificação.** BU e assinatura são ASN.1/BER, decodificados com `asn1tools` a partir das especificações oficiais em `spec/v1` e `spec/v2`. O log é um arquivo 7z com texto. O RDV e a imagem do BU não são decodificados: as especificações do RDV estão em `spec/` para uso futuro.
3. **Verificações.** Cada seção passa por quatro eixos: integridade, consistência, log e estatística. Cada achado vira uma ocorrência com código, severidade, descrição e base legal.
4. **Compilação.** Os resultados entram no DuckDB em transações por lote.
5. **Exportação.** As tabelas são exportadas para Parquet com compressão ZSTD, que é o formato distribuído no repositório.
6. **Painel.** O painel lê os Parquet, monta o banco na primeira execução e responde às consultas.

---

## Metodologia

Resumo abaixo; a descrição completa, com fórmulas e critérios de cada verificação, está em [docs/metodologia.md](docs/metodologia.md).

| Eixo | O que é verificado |
|---|---|
| Integridade (opcional) | SHA-512 de cada arquivo listado no arquivo de assinatura da urna (o que inclui o RDV e a imagem do BU) comparado com o hash assinado. Arquivo ausente ou ilegível vira E01 (não verificável), nunca C01. Não aplicada na base de 2022 distribuída. |
| Consistência | Votos por cargo não excedem eleitores aptos nem o comparecimento; comparecimento igual entre cargos; eleitores aptos iguais entre as eleições registradas no mesmo BU. |
| Log | Abertura e encerramento no horário legal, ajustado ao fuso da UF; reinícios durante a votação; erros, ajustes de hora, substituições; votos contados no log comparados ao BU. |
| Estatística | Lei de Benford (1º e 2º dígito, qui-quadrado e V de Cramér), outliers por z-score nacional e por UF, nulos e brancos, biometria, duração da votação, comparação entre turnos. |
| Reconciliação | Soma dos BUs por UF comparada com o total oficial do TSE (candidatos, brancos, nulos, comparecimento e número de seções). |

O painel também calcula um **índice de confiança de 0 a 100**, média ponderada de sete componentes (integridade de hash, votos acima do eleitorado, Benford, impacto de reinícios, consistência entre turnos, concentração de outliers e biometria). Na base de 2022 distribuída, compilada antes da conferência de hashes, o componente de integridade aparece como "não verificado" até o banco ser recompilado com o registro da conferência feita à parte (nenhum hash divergente). O índice resume os indicadores do projeto; ele não substitui nem contesta a totalização oficial.

### Fusos horários

Os horários do log são locais, e a votação segue o horário de Brasília (8h às 17h). A análise de horário legal converte esses limites para o fuso de cada seção:

| Região | Fuso | Diferença para Brasília |
|---|---|---:|
| AC | UTC-5 | -2 h |
| AM, MT, MS, RO e RR | UTC-4 | -1 h |
| Demais UFs | UTC-3 | 0 |
| Oeste do Amazonas: Amaturá, Atalaia do Norte, Benjamin Constant, Eirunepé, Envira, Guajará, Ipixuna, Itamarati, Jutaí, São Paulo de Olivença e Tabatinga | UTC-5 | -2 h |
| Fernando de Noronha (PE) | UTC-2 | +1 h |

As exceções municipais ficam em `src/dataurnas/analyzer/timezones.py` e são resolvidas pelo código TSE do município, com a UF como alternativa. A base de 2022 distribuída foi compilada antes dessas exceções e usa o fuso da UF para todas as seções; elas passam a valer numa recompilação a partir dos dados brutos.

---

## Códigos de inconsistência

Cada código é classificado em um de três **grupos de leitura**, conforme o que ele pode dizer sobre manipulação. A severidade continua indicando a prioridade de investigar; o grupo indica que tipo de conclusão o achado admite. A classificação tem uma fonte única, `src/dataurnas/dashboard/reference.py` (`GRUPOS` e `ISSUE_CATALOGO`), e aparece no painel em todas as listas de ocorrências, com filtro próprio e um resumo de três quadros no veredicto e na página de 2026.

A letra do código indica a família do achado (C, A, M e I por gravidade; E para falhas de verificação). A severidade abaixo é a atribuída pelo código em `src/dataurnas/analyzer/`; a efetiva fica registrada em cada ocorrência. Os limites de horário são do horário de Brasília convertidos para o fuso local da seção.

| Grupo | O que significa |
|---|---|
| 1. Indício direto de adulteração | Não deveria ocorrer num sistema íntegro. Uma única ocorrência exige explicação. |
| 2. Inconsistência a investigar | Tem explicações legítimas conhecidas e só ganha sentido com o contexto da seção. |
| 3. Operacional ou estatístico | Descreve como o dia de votação transcorreu. Sozinho, não é evidência de manipulação. |

### 1. Indício direto de adulteração

| Código | Severidade | Regra | Referência registrada |
|---|---|---|---|
| C01 | Crítica | Hash SHA-512 de um arquivo diverge do hash assinado | Art. 59, Lei 9.504/97; Cerimônia de Lacração |
| C05 | Crítica | Votos de um cargo excedem os eleitores aptos da seção | Art. 59, Lei 9.504/97 |
| A02 | Alta | Votos computados de um cargo excedem o comparecimento | Integridade da contagem |
| A06 | Alta | Comparecimento diferente entre cargos da mesma eleição na seção | Eleitor vota em todos os cargos na mesma sessão |

Na auditoria de integridade de 2026 (arquivos publicados conferidos com o `.vsc` de cada urna), entram neste grupo as categorias `hash_diverge` (SHA-512 diferente do assinado, equivalente ao C01), `assinatura_invalida` (assinatura da urna inválida), `hash_assinado_ausente` (BU, RDV ou log publicado sem hash assinado) e `arquivo_ausente_tse` (arquivo assinado pela urna que não aparece na publicação).

### 2. Inconsistência a investigar

| Código | Severidade | Regra | Referência registrada | Explicação legítima conhecida |
|---|---|---|---|---|
| A01 | Alta | Eleitores aptos diferentes entre as eleições registradas no mesmo BU, já descontado o voto em trânsito | Caderno de eleitores único por seção | Sem o desconto do trânsito, explicava as 30.572 ocorrências de 2022 |
| A03 | Alta | Votos registrados no log divergem do comparecimento do BU em mais de 2 | Consistência interna | Troca de urna divide o log entre equipamentos |
| E02 | Média | BU não decodificável (por exemplo, tipo de voto ausente ou desconhecido); a seção é excluída dos totais | | Arquivo corrompido, formato novo ou limitação do decodificador |
| E03 | Informativa | Duração negativa no log: encerramento registrado antes da abertura | | Ajuste de relógio ou log de outra urna da seção |
| M03 | Média | Log com mais de 100 entradas e sem evento de abertura | | Log incompleto ou de urna substituída |

Em 2026 entra aqui também `votos_divergem`: os votos do BU assinado não conferem com os do BU lido na coleta de resultados. São duas leituras do mesmo boletim, e a diferença pode vir de uma versão republicada ou de contingência.

### 3. Operacional ou estatístico

| Código | Severidade | Regra | Referência registrada |
|---|---|---|---|
| C06 | Média (1 reinício) ou alta (2 ou mais) | Reinício da urna durante a votação | Procedimento de contingência |
| A04 | Alta | Abertura depois das 8h30 (tolerância de 30 min) | Art. 144 do Código Eleitoral (na base de 2022 consta "Art. 59, Lei 9.504/97") |
| A05 | Alta | Encerramento antes das 17h | Art. 153, Código Eleitoral |
| M01 | Média | Abertura antes das 7h, mais de 1 h antes do horário oficial | Art. 144 do Código Eleitoral |
| M02 | Média | Encerramento depois das 22h | |
| M04 | Média | Mais de 10 erros no log | |
| M05 | Média | Ajustes de hora registrados no log | Integridade da linha do tempo de eventos |
| M06 | Média | Mais de 30% dos eleitores liberados por código, sem biometria | Resolução TSE 23.669/2021 |
| I01 | Informativa | Eventos de substituição ou contingência no log | |
| I02 | Informativa | Mais de 20 alertas de mesário | |
| I03 | Informativa | Nulos acima de 15% dos votos de um cargo | |
| I04 | Informativa | Brancos acima de 10% dos votos de um cargo | |
| I05 | Informativa | Abstenção acima de 40% | |
| I06 | Informativa | Urna de reserva ou tipo diferente de seção | |
| E01 | Informativa | Assinatura ou arquivo assinado não verificável (ausente ou ilegível); não é evidência de adulteração | |

Abertura tardia, encerramento antecipado e reinícios afetam o acesso ao voto ou o andamento da seção, não a contagem dos votos registrados. As análises agregadas do painel (Lei de Benford e outliers estatísticos) também pertencem a este grupo: votos por seção não seguem Benford por natureza e seções atípicas existem em qualquer eleição, de modo que os dois testes têm alta taxa de falso positivo em dados eleitorais.

### O que os arquivos públicos permitem detectar

Os arquivos que o TSE publica permitem conferir se o que foi publicado é o que a urna assinou (hash e assinatura), se cada BU é coerente por dentro (aptos, comparecimento e votos) e se a soma dos BUs reproduz a totalização oficial. Uma alteração feita depois da assinatura, no caminho até a publicação ou na totalização, aparece no grupo 1 ou na reconciliação.

Esses arquivos não alcançam uma manipulação feita dentro da urna antes da assinatura, porque nesse caso o BU, o RDV e o log já nasceriam coerentes entre si e corretamente assinados. Essa hipótese é tratada por outros mecanismos, fora do alcance deste projeto: a inspeção do código-fonte pelas entidades fiscalizadoras, a cerimônia de assinatura digital e lacração dos sistemas, o teste de integridade das urnas no dia da eleição e o Teste Público de Segurança. Os arquivos públicos também não trazem o hash dos programas que rodaram em cada urna ([hash do software](docs/hash-software-urna-2026.md)). A conferência voto a voto do RDV com o BU de cada seção foi feita nos dois turnos de 2026 (ver o [veredicto](#veredicto-da-auditoria-2026)).

### O que não é inconsistência

- Nomes de eleitores no log: comportamento documentado do display do terminal do mesário.
- Urna substituída: procedimento normal de contingência (mais de um hash no `aux.json`).
- Ajuste de hora antes da abertura da votação.
- Abstenção, votos brancos e nulos: direitos do eleitor.

---

## Painel interativo

O painel é uma aplicação Streamlit com várias páginas. A página inicial, **Presidente 2º turno**, apresenta o resultado do 2º turno, com mapa por UF, comparecimento e a integridade dos arquivos:

<table>
  <tr>
    <td width="76%" valign="top"><img src="docs/assets/telas/2026-t2-desktop.png" alt="Página Presidente 2º turno do painel no computador: resultado oficial do 2º turno de 2026, com Lula (PT) 64.256.232 votos (51,79% dos válidos) e Flávio Bolsonaro (PL) 59.826.041 (48,21%), margem de 4.430.191 votos e comparecimento de 80,78%" width="100%"></td>
    <td width="24%" valign="top"><img src="docs/assets/telas/2026-t2-mobile.png" alt="A mesma página do 2º turno de 2026 em tela de celular, com os cartões de indicadores empilhados" width="100%"></td>
  </tr>
  <tr>
    <td align="center"><sub>Computador (1440 x 900)</sub></td>
    <td align="center"><sub>Celular (390 x 844)</sub></td>
  </tr>
</table>

A página **Veredicto da auditoria 2026** resume as verificações, o que não pode ser verificado com dados públicos e as pendências para o TSE:

<p align="center">
  <img src="docs/assets/telas/2026-veredicto.png" alt="Página Veredicto da auditoria 2026 do painel: nenhuma evidência de manipulação, de contagem errada ou de dado impossível nos dois turnos, com a tabela das 26 verificações e o RDV recontado em todas as seções" width="100%">
</p>

A página **Presidente 1º turno** apresenta o resultado do 1º turno de 2026:

<table>
  <tr>
    <td width="76%" valign="top"><img src="docs/assets/telas/2026-desktop.png" alt="Página Presidente 1º turno do painel no computador: resultado oficial do 1º turno de 2026, com cartões de eleitorado, comparecimento, abstenção, votos válidos, brancos e nulos e o gráfico de votos por candidato" width="100%"></td>
    <td width="24%" valign="top"><img src="docs/assets/telas/2026-mobile.png" alt="A mesma página de 2026 em tela de celular, com os cartões de indicadores empilhados em duas colunas" width="100%"></td>
  </tr>
  <tr>
    <td align="center"><sub>Computador (1440 x 900)</sub></td>
    <td align="center"><sub>Celular (390 x 844)</sub></td>
  </tr>
</table>

No mesmo grupo, a página **Integridade dos arquivos (2026)** mostra a conferência de hashes e assinaturas por UF, as divergências, a consulta de qualquer seção (MD5, SHA-256 e SHA-512 calculado e assinado, certificado da urna) e a exportação do catálogo em CSV.

As demais páginas cobrem a auditoria de 2022:

<table>
  <tr>
    <td width="50%" valign="top"><img src="docs/assets/telas/2022-veredicto.png" alt="Página Veredicto final da auditoria de 2022, com indicadores gerais (941.987 seções, 310.993 com alguma ocorrência) e a cobertura dos dados do 1º turno" width="100%"></td>
    <td width="50%" valign="top"><img src="docs/assets/telas/2022-benford.png" alt="Página Lei de Benford da auditoria de 2022, com a distribuição observada e a esperada do primeiro dígito dos votos por candidato" width="100%"></td>
  </tr>
  <tr>
    <td align="center"><sub>Veredicto final</sub></td>
    <td align="center"><sub>Lei de Benford</sub></td>
  </tr>
</table>

Entre as páginas de 2022 estão:

- veredicto e índice de confiança, votação por candidato e cargo, mapa por UF;
- Lei de Benford, outliers, nulos e brancos;
- reinícios, comparação entre turnos, divergência log x BU (A03), biometria, horários, modelos de urna, seções de reserva;
- integridade de hash, explorador de seção, inconsistências por código e por UF.

Os filtros cobrem turno, região, UF, município, modelo e tipo de urna, severidade e código da ocorrência. Os dados podem ser exportados em Excel ou texto.

---

## Instalação

Requisitos: Python 3.11 ou superior e cerca de 3,5 GB livres (Parquet mais o DuckDB gerado).

```bash
git clone https://github.com/alissonlinneker/DataUrnas-BR.git
cd DataUrnas-BR
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[dashboard,dev]"
```

Com `make`, o mesmo resultado sai de `make install`, que cria o `.venv` se ele não existir. Para apenas executar o painel, `pip install -r requirements.txt` seguido de `pip install --no-deps -e .` também funciona.

---

## Uso

### Atalhos com make

O `Makefile` reúne as tarefas mais comuns e usa o Python do `.venv`. `make help` lista todos os alvos.

| Alvo | O que faz |
|---|---|
| `make install` | Cria o `.venv`, se preciso, e instala o pacote em modo editável com painel e ferramentas de desenvolvimento |
| `make lint` | Roda o `ruff check .` |
| `make test` / `make test-cov` | Roda a suíte de testes, sem ou com relatório de cobertura |
| `make build-db` | Reconstrói o DuckDB a partir dos Parquet de `data/parquet` |
| `make dashboard` | Inicia o painel em `http://localhost:8501` (outra porta com `PORT=8502`) |
| `make fetch-2026` | Baixa o resultado oficial agregado e os BUs de 2026 por seção (`fetch-2026-resultados` + `fetch-2026-secoes`) |
| `make consolidate-2026` | Só consolida em Parquet as partes de 2026 já coletadas |
| `make reconcile-2026` | Compara a soma dos BUs de 2026 com o resultado oficial de cada UF |
| `make docker-build` / `make docker-run` | Constrói e roda a imagem Docker do painel em `http://localhost:7860` |
| `make clean` | Remove caches de build, testes e lint |

Variáveis aceitas na linha de comando: `VENV` (padrão `.venv`), `PORT` (padrão 8501), `UFS` para limitar a coleta e a reconciliação de 2026 (por exemplo, `make reconcile-2026 UFS=ac,rr`) e `IMAGE` (padrão `dataurnas-br`).

### Painel

```bash
python scripts/build_db.py          # cria data/db/eleicoes_2022.duckdb a partir dos Parquet
dataurnas dashboard                 # ou: streamlit run src/dataurnas/dashboard/app.py
```

Acesse `http://localhost:8501`. Se o banco ainda não existir, o painel o constrói na primeira execução.

### Linha de comando

```bash
# Download (API do TSE)
dataurnas download list                                  # eleições disponíveis
dataurnas download info df                               # municípios e seções de uma UF
dataurnas download state df --max-secoes 50 --tipo bu --tipo logjez
dataurnas download sample --estados ac,df,rs --secoes 20

# Análise de arquivos e seções
dataurnas analyze bu caminho/arquivo.bu
dataurnas analyze log caminho/arquivo.logjez
dataurnas analyze hashes caminho/da/secao
dataurnas analyze section caminho/da/secao
dataurnas analyze batch --uf df --hashes -o resultado.json

# Banco de dados
dataurnas db build [--incremental] [--batch-size 500]
dataurnas db stats
```

Use `dataurnas --help` ou `dataurnas <comando> --help` para todas as opções. O download completo de 2022 ocupa cerca de 181 GB.

Concorrência e taxa de requisições do downloader têm padrão conservador e podem ser ajustadas por ambiente:

| Variável | Padrão | Efeito |
|---|---:|---|
| `DATAURNAS_MAX_CONCURRENT` | 50 | Downloads simultâneos |
| `DATAURNAS_RATE_LIMIT` | 200 | Requisições por segundo |

### Eleições 2026

```bash
python scripts/ele2026/fetch_resultados.py               # BR, UFs e municípios (Presidente, 1º turno)
python scripts/ele2026/fetch_secoes.py --ufs ac          # BU por seção, com checkpoint e retomada
python scripts/ele2026/fetch_secoes.py --so-consolidar   # consolida as partes em Parquet
python scripts/ele2026/reconcile.py --ufs ac             # soma dos BUs x resultado oficial da UF
```

`reconcile.py` termina com código 1 quando encontra divergência.

### Testes e qualidade

```bash
ruff check .        # ou: make lint
pytest -q           # ou: make test
```

Os testes usam fixtures sintéticas e não dependem dos dados brutos.

---

## Deploy

O painel roda no [Hugging Face Spaces](https://huggingface.co/spaces/alissonlinneker/dataurnas-br) com o SDK Docker. O `Dockerfile` instala as dependências, copia código, especificações e Parquet, constrói o DuckDB durante o build e expõe a porta 7860.

O workflow `.github/workflows/deploy-hf.yml` roda a CI e, se ela passar, publica cada push na `main` no Space, com os Parquet em Git LFS. Configuração única no GitHub (**Settings > Secrets and variables > Actions**):

- secret `HF_TOKEN` (token de escrita do Hugging Face);
- variables `HF_USERNAME` e `SPACE_NAME`.

Para rodar a imagem localmente:

```bash
docker build -t dataurnas-br .
docker run --rm -p 7860:7860 dataurnas-br
```

---

## Estrutura do projeto

```
DataUrnas-BR/
├── Makefile                   # Atalhos: install, lint, test, build-db, dashboard, 2026, Docker
├── Dockerfile                 # Imagem do painel (Hugging Face Spaces)
├── data/parquet/              # Dados distribuídos (2022 na raiz, 2026 em 2026/)
├── docs/
│   ├── README.md              # Índice da documentação
│   ├── metodologia.md         # Verificações, códigos, limiares e índice de confiança
│   ├── arquitetura.md         # Módulos, fluxo de uma seção, banco e deploy
│   ├── dados-2026.md          # Arquivos e esquemas de 2026
│   ├── faq.md                 # Perguntas frequentes
│   ├── veredicto-auditoria-2026.md  # Veredicto da auditoria de 2026 (dois turnos)
│   ├── *-2026.md              # Relatórios de cada verificação de 2026
│   └── assets/                # Banner, gráficos SVG e telas/ (capturas do painel)
├── spec/v1, spec/v2           # Especificações ASN.1 oficiais (2022 e 2024 em diante)
├── scripts/
│   ├── build_db.py            # Constrói o DuckDB a partir dos Parquet
│   ├── download_*.py          # Downloads completos de 2022
│   ├── rebuild_*.py           # Recompilação a partir dos dados brutos
│   ├── ele2026/               # Coleta, reconciliação e auditoria de 2026 (dois turnos)
│   ├── ch/                    # Banco ClickHouse das versões de 2026
│   └── docs/                  # Geração das ilustrações e capturas de tela do README
├── src/dataurnas/
│   ├── cli.py                 # Interface de linha de comando (Click)
│   ├── config.py              # Constantes: API, UFs, eleições
│   ├── models.py              # Modelos de domínio
│   ├── downloader/            # Cliente HTTP, navegação da API, orquestração
│   ├── parsers/               # BU, log e assinatura
│   ├── analyzer/              # Integridade, log, estatística, lote, fusos
│   ├── database/              # DuckDB e montagem de linhas
│   └── dashboard/             # Painel Streamlit (páginas, componentes, análises SQL)
└── tests/                     # Testes com fixtures sintéticas (sem dados brutos)
```

---

## Documentação

| Documento | Conteúdo |
|---|---|
| [docs/README.md](docs/README.md) | Índice de toda a documentação |
| [Metodologia](docs/metodologia.md) | Arquivos da urna, verificações, códigos com severidade e limiares, índice de confiança e reconciliação de 2026 |
| [Arquitetura](docs/arquitetura.md) | Módulos, scripts, fluxo de uma seção, banco de dados e deploy |
| [Dados de 2026](docs/dados-2026.md) | Arquivos Parquet de 2026, forma de coleta, totais oficiais, nulos técnicos e esquemas |
| [Perguntas frequentes](docs/faq.md) | O que o projeto prova e não prova, como reproduzir, BU x RDV, nulos técnicos e cobertura |
| [Relatório de integridade de 2026](docs/relatorio-integridade-2026.md) | Hashes, assinaturas, auditoria por grupo de leitura, certificados e conferência manual de uma seção |
| [Investigação das seções "Recebida"](docs/investigacao-secoes-recebidas-2026.md) | Seções republicadas entre 05 e 07/10/2026 e imagens do BU indisponíveis |
| [Integridade de 2022](docs/integridade-2022.md) | Hashes, assinaturas e cadeia de certificados de 2022 (1º e 2º turnos) e arquivos assinados ausentes do pacote do TSE |
| [Investigação log x BU (2026)](docs/investigacao-log-bu-2026.md) | Seções em que a contagem de votos no log difere do BU: causas, correções do leitor e casos encaminhados ao TSE |
| [Confronto com fontes externas](docs/confronto-fontes-externas.md) | BUs do TSE confrontados com leituras independentes do QR Code dos boletins impressos |
| [Ocorrências para o TSE](docs/relatorio-tse-ocorrencias-2026.md) | Pontos de publicação, de certificação e de log a esclarecer com o TSE |
| [Veredicto da auditoria 2026](docs/veredicto-auditoria-2026.md) | Veredicto dos dois turnos de 2026: 26 verificações, limites e 13 pendências para o TSE |
| [RDV x BU x log (2026)](docs/rdv-log-2026.md) | RDV, BU e log eleitor a eleitor nos dois turnos e recontagem nacional do RDV do 2º turno |
| [Certificados do 2º turno](docs/certificados-2turno-2026.md) | Assinaturas de todos os arquivos e cadeia de certificados nas 499.207 seções do 2º turno |
| [Consistência dos BUs (2026)](docs/auditoria-consistencia-bu-2026.md) | Valores impossíveis, somas, repetições e horários nos BUs dos dois turnos |
| [Verificações externas do 2º turno](docs/verificacoes-externas-2turno-2026.md) | Teste de integridade, hashes, BU impresso, código-fonte e linha do tempo da totalização |
| [Prorrogação da votação](docs/prorrogacao-votacao-2turno-2026.md) | Fontes primárias sobre a prorrogação até 19h no 2º turno |
| [Encerramento tardio](docs/encerramento-tardio-2turno-2026.md) | Seções encerradas depois das 17h, votos depois das 17h e cenários de impacto na margem |
| [Viradas entre turnos](docs/viradas-1t-2t-2026.md) | Viradas de liderança por seção em 2026 contra o modelo de 2022 |
| [Ordem de envio](docs/ordem-de-envio-viradas-2022-2026.md) | Ordem de chegada das seções e a "virada" da curva acumulada em 2022 e 2026 |
| [Virada de 2026 e probabilidades](docs/virada-2026-probabilidades.md) | Aritmética da virada, base histórica de 2º turnos, pesquisas, transferências, simulação de fraude e eleitorado x população |
| [Chegada dos BUs](docs/chegada-bus-2026.md) | Ordem e horário de chegada dos BUs à totalização e o voto de cada seção |
| [Pacote nacional: imagem do BU e logs](docs/pacote-nacional-imgbu-logs-2026.md) | Imagem do BU x BU e log eleitor a eleitor x BU em todas as seções dos dois turnos |
| [Zerésima](docs/zeresima-2026.md) | Zerésima de cada urna nos dois turnos: presença, horário e ordem em relação ao primeiro voto |
| [Coerência entre cargos](docs/coerencia-cargos-2026.md) | Todos os cargos de cada BU do 1º turno, Presidente x Governador no 2º turno e voto dividido, com 2022 de controle |
| [Seções tardias do PR](docs/pr-secoes-tardias-1t-2026.md) | Por que as últimas seções do 1º turno aparecem recebidas em 07/10 |
| [Republicação do pacote do MA](docs/ma-republicacao-2026.md) | O que mudou no zip do MA 1º turno republicado em 03/11 |
| [Cadeia de confiança 2026](docs/cadeia-de-confianca-2026.md) | Software, assinaturas e limites do que é verificável sem código-fonte e compilação reproduzível |
| [Mapa de verificações](docs/mapa-verificacoes-2026.md) | O que foi feito, o que falta e o que depende do TSE |
| [Forense estatística](docs/forense-estatistica-2026.md) | Impressão digital eleitoral, dígitos, swing, transferência, dispersão e comparecimento, com 2022 de controle |
| [Efeito da urna](docs/efeito-urna-2026.md) | Modelo, troca, recarga, reserva e contingência de urna e o voto |
| [Biometria 1º x 2º turno](docs/biometria-1t-2t-2026.md) | Habilitação por biometria no BU e no log e teste de votos inseridos sem digital |
| [GEDAI do 2º turno](docs/gedai-2turno-2026.md) | Logs de preparação GEDAI-UE e códigos de carga x BUs |
| [Dados abertos x BU](docs/confronto-dados-abertos-2026.md) | Produtos do portal de dados abertos e correspondências urna x seção confrontados com os BUs |
| [Hash do software da urna](docs/hash-software-urna-2026.md) | O que os arquivos públicos permitem verificar sobre o software e as listas oficiais de hashes |
| [JWS da totalização](docs/jws-totalizacao-2026.md) | Assinatura dos resultados divulgados e confronto com a soma dos BUs |
| [Banco ClickHouse](docs/banco-clickhouse.md) | Banco das versões coletadas de 2026, com 2022 ao lado |

---

## Fontes de dados e legislação

### Fontes

- [Resultados do TSE](https://resultados.tse.jus.br/oficial/): arquivos de urna e resultados agregados.
- [Portal de Dados Abertos do TSE](https://dadosabertos.tse.jus.br/): dados complementares.
- [Segurança da urna eletrônica](https://www.tse.jus.br/eleicoes/urna-eletronica/seguranca-da-urna): documentação dos formatos e mecanismos de auditoria.

### Legislação

| Norma | Aspecto |
|---|---|
| Lei 9.504/1997, art. 59 | Votação eletrônica e assinatura digital dos arquivos |
| Lei 9.504/1997, art. 59-A | Auditoria e fiscalização dos sistemas |
| Lei 9.504/1997, art. 66 | Fiscalização por partidos e coligações |
| Lei 10.740/2003 | Registro Digital do Voto |
| Código Eleitoral, art. 153 | Encerramento da votação |
| Resolução TSE 23.673/2021 | Fiscalização e auditoria do sistema eletrônico |

---

## Limitações

- O projeto trabalha **somente com os arquivos públicos**. Ele não tem acesso às urnas, ao código-fonte compilado nem às chaves privadas. Por isso não verifica qual software rodou em cada urna: nenhum arquivo público por seção traz o hash dos programas, e a ligação com a lista lacrada só existe nas verificações por amostragem do TSE, cujos relatórios não são publicados. Em 2026 a cadeia de certificados das urnas é conferida até a AC intermediária (AC URNA, AC UE2020 e AC UE2022), não até a raiz, cujos certificados não estão publicados; a assinatura de software (CEPESC) usa algoritmo não publicado e não é verificada.
- Uma ocorrência é um **indicador para investigação**, não uma conclusão. Reinícios, horários e proporções atípicas costumam ter explicação operacional.
- Testes estatísticos como Benford têm alcance limitado em dados eleitorais, cuja distribuição depende do tamanho das seções. Por isso o projeto usa medidas de efeito (V de Cramér) além do p-valor.
- Em 2026, a validação da cadeia de certificados foi feita numa amostra determinística de 5% das seções; a coerência dos certificados (unicidade, CN e emissor por modelo) cobre todas. Arquivos que o TSE não publica (um RDV e 2.658 imagens do BU listadas e indisponíveis) não puderam ser conferidos.
- Seções cujo BU não pôde ser decodificado (E02) ficam fora dos totais e são listadas para conferência.
- A base de 2022 foi compilada sem conferência de hashes, feita depois à parte (nenhum divergente); o componente de integridade do índice de confiança só passa a refleti-la depois de recompilar o banco. Em 2022 a cadeia de certificados foi validada numa amostra de 5% e o RDV não é recontado.
- Testes que comparam grupos de urnas (modelo, troca, região, 2022) não detectam uma alteração aplicada igualmente a todas as urnas; a proteção contra ela é o Teste de Integridade, cujo relatório do 2º turno de 2026 ainda não foi publicado.
- Em 2026 o RDV é decodificado e recontado em todas as seções dos dois turnos; nas seções apuradas no Sistema de Apuração o RDV é gerado pelo próprio sistema, e a conferência com o BU não é independente. Em 2022 o RDV ainda não é recontado. A imagem do BU é baixada e tem o hash conferido, mas não é decodificada.
- Os códigos E01, E02 e E03 e as exceções de fuso por município foram introduzidos na versão 0.2.0; os Parquet de 2022 distribuídos foram compilados antes deles e só passam a refleti-los após uma recompilação a partir dos dados brutos.

---

## Status do projeto e roadmap

| Item | Situação |
|---|---|
| 2022, Presidente, 1º e 2º turnos: BU, log e assinatura por seção | Concluído |
| 2026, Presidente, 1º turno: resultado oficial agregado (Brasil, UFs, exterior e municípios) | Concluído |
| 2026, Presidente, 1º turno: BU por seção e reconciliação com o oficial | Concluído (diferença zero nas 28 UFs) |
| 2026, 1º turno: integridade dos arquivos (SHA-512 e assinatura de cada urna) | Concluído (0 divergentes em 1.497.620; 0 assinaturas inválidas) |
| 2026, 1º turno: auditoria do BU e do log por grupo de leitura | Concluído (nenhuma ocorrência do grupo 1) |
| 2026, 1º turno: coerência dos certificados das urnas | Concluído (todas as seções) |
| 2026, 1º turno: validação da cadeia de certificados até a AC intermediária | Concluído na amostra de 5%, sorteio determinístico |
| 2026, 1º turno: catálogo de hashes por arquivo | Publicado nos anexos da [v0.2.1](https://github.com/alissonlinneker/DataUrnas-BR/releases/tag/v0.2.1) |
| 2022, 1º e 2º turnos: integridade dos arquivos (SHA-512 e assinatura de cada urna) | Concluído (0 divergentes em 3.776.042; 0 assinaturas inválidas) |
| 2022: validação da cadeia de certificados até a AC intermediária | Concluído na amostra de 5% (47.230 seções) |
| Cadeia de certificados até a raiz | Depende da publicação dos certificados raiz pelo TSE |
| 2026, 1º turno: recontagem voto a voto do RDV contra o BU de cada seção | Concluído (0 divergências em 499.206 seções) |
| 2026, 1º turno: confronto com leituras independentes do QR Code (CMInd) | Concluído (38 de 38 conferem) |
| 2026, Presidente, 2º turno: resultado oficial e BU por seção, com coleta versionada | Concluído (soma dos BUs igual ao oficial; 0 arquivos alterados em 8 voltas) |
| 2026, 2º turno: assinaturas e certificados de todas as seções | Concluído (5.487.289 assinaturas válidas; 0 inválidas) |
| 2026, 2º turno: recontagem nacional do RDV | Concluído (0 divergências em 499.205 seções) |
| 2026, dois turnos: consistência, log, encerramento tardio, viradas, forense, efeito da urna, biometria, GEDAI, dados abertos, hashes do software e JWS | Concluído ([veredicto](docs/veredicto-auditoria-2026.md)) |
| 2026, 2º turno: confronto com BUs impressos lidos pelo QR Code | Próxima verificação independente |
| Recontagem pelo RDV em 2022; decodificação da imagem do BU | Futuro |

As mudanças de cada versão ficam no [CHANGELOG](CHANGELOG.md).

---

## Como citar

Use o botão **Cite this repository** do GitHub (gerado a partir de [CITATION.cff](CITATION.cff)) ou:

```bibtex
@software{linneker_dataurnas_br,
  author  = {Linneker, Alisson},
  title   = {DataUrnas-BR: auditoria independente dos arquivos públicos da urna eletrônica},
  year    = {2026},
  version = {0.3.0},
  url     = {https://github.com/alissonlinneker/DataUrnas-BR},
  license = {MIT}
}
```

---

## Contribuindo

Contribuições são bem-vindas. Leia o [guia de contribuição](CONTRIBUTING.md) e o [código de conduta](CODE_OF_CONDUCT.md). Vulnerabilidades devem ser reportadas conforme a [política de segurança](SECURITY.md). As mudanças de cada versão estão no [CHANGELOG](CHANGELOG.md).

### Como regenerar as ilustrações

Os gráficos deste README são SVG gerados a partir dos Parquet em `data/parquet/`, sem bibliotecas de gráficos; as telas do painel são capturadas com o `chrome-headless-shell` do cache do Playwright.

```bash
python scripts/docs/gerar_ilustracoes.py     # docs/assets/*.svg (use --png DIR para conferir em PNG)
python scripts/docs/capturar_telas.py        # docs/assets/telas/*.png (sobe o painel numa porta livre)
```

O segundo script encerra o painel e o navegador ao final e remove os metadados dos PNG. Rode os dois de novo sempre que os dados mudarem.

---

## Licença

[MIT](LICENSE) © 2026 Alisson Linneker. Os dados eleitorais são públicos e pertencem ao TSE.
