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
| [Perguntas frequentes](faq.md) | O que o projeto prova e não prova, como reproduzir, BU x RDV, nulos técnicos e cobertura |

Documentos na raiz do repositório:

- [README](../README.md): visão geral, instalação e uso.
- [CONTRIBUTING](../CONTRIBUTING.md): ambiente de desenvolvimento, fluxo de trabalho e padrões.
- [CHANGELOG](../CHANGELOG.md): histórico de versões.
- [SECURITY](../SECURITY.md): como reportar vulnerabilidades.
- [CODE_OF_CONDUCT](../CODE_OF_CONDUCT.md): código de conduta.
- [CITATION.cff](../CITATION.cff): como citar o projeto.

As especificações ASN.1 oficiais dos arquivos da urna estão em [`spec/`](../spec): `v1` para 2022 e `v2` para 2024 em diante.
