# Como contribuir

Obrigado pelo interesse no DataUrnas-BR. Este guia explica como propor mudanças de forma que elas possam ser revisadas e incorporadas com segurança.

Ao participar, você concorda em seguir o [Código de Conduta](CODE_OF_CONDUCT.md).

## Princípios do projeto

- **Reprodutibilidade acima de tudo.** Toda conclusão precisa poder ser refeita a partir dos arquivos públicos do TSE e do código deste repositório.
- **Neutralidade.** O projeto audita dados; ele não faz campanha nem comentário político. Issues, PRs e textos devem manter tom técnico.
- **Indicador não é prova.** Uma ocorrência sinaliza algo a investigar. Descrições e documentação não devem apresentar indicadores como conclusões.
- **Dados brutos não entram no git.** Os arquivos da urna ficam em `data/raw/` (ignorado). O repositório distribui apenas Parquet derivados.

## Preparando o ambiente

```bash
git clone https://github.com/alissonlinneker/DataUrnas-BR.git
cd DataUrnas-BR
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dashboard,dev]"
```

Verifique que está tudo certo:

```bash
ruff check .
pytest -q
```

O `Makefile` reúne os mesmos passos: `make install`, `make lint` e `make test` (rode `make help` para ver todos os alvos, como `build-db`, `dashboard` e `reconcile-2026`).

Os testes usam fixtures sintéticas geradas a partir das especificações ASN.1 em `spec/`; eles não precisam de rede nem dos dados brutos.

## Fluxo de trabalho

1. Abra uma issue descrevendo o bug ou a proposta, de preferência antes de escrever código para mudanças grandes.
2. Crie um branch a partir da `main` (`fix/descricao-curta`, `feat/descricao-curta`).
3. Escreva testes que cubram a mudança. Correções de bug devem vir com um teste que falhava antes.
4. Rode `ruff check .` e `pytest -q` localmente.
5. Abra o pull request preenchendo o modelo e referenciando a issue (`closes #N`).

## Padrões de código

- Python 3.11 ou superior.
- Lint com `ruff` usando a configuração do `pyproject.toml`.
- Textos voltados ao usuário (mensagens, documentação, painel) em português do Brasil, com acentuação correta.
- Consultas SQL devem usar parâmetros (`?`) para qualquer valor vindo do usuário.
- Requisições ao TSE devem passar pelo `TSEClient`, que aplica limite de taxa e retry. Seja gentil com o servidor público: não aumente concorrência ou taxa padrão sem justificativa.

## Mensagens de commit

Use [Conventional Commits](https://www.conventionalcommits.org/pt-br/) em inglês:

```
feat: add 2026 section reconciliation
fix: count skipped downloads correctly
docs: describe E02 issue code
```

## Novos códigos de inconsistência

Ao criar um código novo:

- escolha a família pela natureza do achado (C, A, M, I ou E) e documente a severidade;
- inclua descrição objetiva e, quando houver, a base legal;
- atualize a tabela de códigos no `README.md` e em `docs/metodologia.md`, com severidade e limiar;
- adicione teste que gere a ocorrência a partir de uma fixture.

## Dados e análises

Mudanças que alteram números publicados (totais, contagens de ocorrências, índices) devem explicar no PR o que mudou, por que e qual o impacto, com antes e depois. Se a mudança exigir recompilar os Parquet, diga isso explicitamente.

## Dúvidas

Abra uma issue com a pergunta. Para vulnerabilidades, siga a [política de segurança](SECURITY.md) e não abra issue pública.
