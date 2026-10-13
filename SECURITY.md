# Política de segurança

## Versões suportadas

| Versão | Suporte |
|---|---|
| 0.2.x | Sim |
| 0.1.x | Não |

## Como reportar uma vulnerabilidade

**Não abra issue pública para vulnerabilidades.**

Use o reporte privado do GitHub: na página do repositório, vá em **Security > Report a vulnerability**. Inclua:

- descrição do problema e do impacto;
- passos para reproduzir ou prova de conceito;
- versão, commit ou ambiente afetado;
- sugestão de correção, se houver.

Você deve receber uma confirmação em até 7 dias. Depois da análise, combinamos prazo de correção e de divulgação. Quem reportar será creditado, se desejar.

## Escopo

Estão no escopo, por exemplo:

- execução de código ou leitura de arquivos a partir de entradas do painel ou da CLI;
- injeção de SQL nas consultas do painel;
- vazamento de segredos (tokens de deploy, variáveis de ambiente) pela imagem Docker ou pelos workflows;
- falhas que façam o projeto aceitar arquivos adulterados como íntegros (por exemplo, erro na verificação de hash).

Fora do escopo:

- a segurança da urna eletrônica ou dos sistemas do TSE. Vulnerabilidades nesses sistemas devem ser comunicadas ao próprio TSE pelos canais oficiais;
- divergências de interpretação de resultados, que devem ser discutidas em issues comuns;
- negação de serviço contra o Space público de demonstração.

## Boas práticas adotadas

- Workflows com permissões mínimas e ações fixadas por hash de commit.
- Token de deploy passado por cabeçalho HTTP, nunca pela URL.
- `.dockerignore` impede que `.env` e arquivos locais entrem na imagem.
- Consultas SQL parametrizadas para valores vindos de filtros.
