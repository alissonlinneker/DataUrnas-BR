# Documentação

| Documento | Conteúdo |
|---|---|
| [Metodologia](metodologia.md) | Arquivos da urna, verificações, códigos de ocorrência com severidade e limiares, análises agregadas, índice de confiança e reconciliação de 2026 |
| [Arquitetura](arquitetura.md) | Módulos, scripts, fluxo de uma seção, banco de dados, decisões de projeto e deploy |
| [Dados de 2026](dados-2026.md) | Arquivos Parquet de 2026, forma de coleta, totais oficiais, nulos técnicos e esquemas |
| [Relatório de integridade 2026](relatorio-integridade-2026.md) | Hashes SHA-512 e assinaturas dos arquivos de urna de 2026: cobertura, totais por UF, divergências e como conferir uma seção |
| [Integridade 2022](integridade-2022.md) | Hashes SHA-512 e assinaturas dos arquivos de urna de 2022 (1º e 2º turnos): totais por turno e UF, divergências e lista dos arquivos assinados e ausentes do pacote do TSE |
| [Investigação log x BU 2026](investigacao-log-bu-2026.md) | Seções em que a contagem de votos no log difere do BU: causas, correções do leitor e casos encaminhados ao TSE |
| [Confronto com fontes externas](confronto-fontes-externas.md) | BUs do TSE confrontados com leituras independentes do QR Code dos boletins impressos |
| [Ocorrências para o TSE](relatorio-tse-ocorrencias-2026.md) | Pontos de publicação, de certificação e de log a esclarecer com o TSE |
| [Veredicto da auditoria 2026](veredicto-auditoria-2026.md) | Veredicto dos dois turnos de 2026: 20 verificações, o que não pode ser verificado e 12 pendências para o TSE |
| [RDV x BU x log (2026)](rdv-log-2026.md) | RDV, BU e log eleitor a eleitor nos dois turnos e recontagem nacional do RDV do 2º turno |
| [Certificados do 2º turno](certificados-2turno-2026.md) | Assinaturas de todos os arquivos e cadeia de certificados nas 499.207 seções do 2º turno |
| [Consistência dos BUs (2026)](auditoria-consistencia-bu-2026.md) | Valores impossíveis, somas, repetições e horários nos BUs dos dois turnos |
| [Verificações externas do 2º turno](verificacoes-externas-2turno-2026.md) | Teste de integridade, hashes, BU impresso, código-fonte e linha do tempo da totalização |
| [Roteiro do 2º turno](roteiro-2turno-2026.md) | Roteiro de coleta do 2º turno de 2026, que repete a do 1º turno |
| [Prorrogação da votação](prorrogacao-votacao-2turno-2026.md) | Fontes primárias sobre a prorrogação até 19h no 2º turno |
| [Encerramento tardio](encerramento-tardio-2turno-2026.md) | Seções encerradas depois das 17h, votos depois das 17h e cenários de impacto na margem |
| [Viradas entre turnos](viradas-1t-2t-2026.md) | Viradas de liderança por seção em 2026 contra o modelo de 2022 |
| [Ordem de envio](ordem-de-envio-viradas-2022-2026.md) | Ordem de chegada das seções e a "virada" da curva acumulada em 2022 e 2026 |
| [Forense estatística](forense-estatistica-2026.md) | Impressão digital eleitoral, dígitos, swing, transferência, dispersão e comparecimento, com 2022 de controle |
| [Efeito da urna](efeito-urna-2026.md) | Modelo, troca, recarga, reserva e contingência de urna e o voto |
| [Biometria 1º x 2º turno](biometria-1t-2t-2026.md) | Habilitação por biometria no BU e no log e teste de votos inseridos sem digital |
| [GEDAI do 2º turno](gedai-2turno-2026.md) | Logs de preparação GEDAI-UE e códigos de carga x BUs |
| [Dados abertos x BU](confronto-dados-abertos-2026.md) | Produtos do portal de dados abertos e correspondências urna x seção confrontados com os BUs |
| [Cadeia de confiança 2026](cadeia-de-confianca-2026.md) | Software, assinaturas e limites: o que é verificável, o que não é com dados públicos e o que é impossível sem código-fonte e compilação reproduzível |
| [Hash do software da urna](hash-software-urna-2026.md) | O que os arquivos públicos permitem verificar sobre o software e as listas oficiais de hashes |
| [JWS da totalização](jws-totalizacao-2026.md) | Assinatura dos resultados divulgados e confronto com a soma dos BUs |
| [Banco ClickHouse](banco-clickhouse.md) | Banco das versões coletadas de 2026, com 2022 ao lado |
| [Perguntas frequentes](faq.md) | O que o projeto prova e não prova, como reproduzir, BU x RDV, nulos técnicos e cobertura |

Documentos na raiz do repositório:

- [README](../README.md): visão geral, instalação e uso.
- [CONTRIBUTING](../CONTRIBUTING.md): ambiente de desenvolvimento, fluxo de trabalho e padrões.
- [CHANGELOG](../CHANGELOG.md): histórico de versões.
- [SECURITY](../SECURITY.md): como reportar vulnerabilidades.
- [CODE_OF_CONDUCT](../CODE_OF_CONDUCT.md): código de conduta.
- [CITATION.cff](../CITATION.cff): como citar o projeto.

As especificações ASN.1 oficiais dos arquivos da urna estão em [`spec/`](../spec): `v1` para 2022 e `v2` para 2024 em diante.
