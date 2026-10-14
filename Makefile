# Tarefas comuns do DataUrnas-BR. Rode `make help` para a lista.
#
# Variáveis que podem ser sobrescritas na linha de comando:
#   VENV   diretório do ambiente virtual (padrão: .venv)
#   PORT   porta do painel (padrão: 8501)
#   UFS    UFs separadas por vírgula, para fetch-2026-secoes e reconcile-2026 (ex.: UFS=ac,rr)
#   IMAGE  nome da imagem Docker (padrão: dataurnas-br)

VENV   ?= .venv
PYTHON ?= python3
PY     := $(VENV)/bin/python
PORT   ?= 8501
UFS    ?=
IMAGE  ?= dataurnas-br

UFS_ARG := $(if $(UFS),--ufs $(UFS),)

.DEFAULT_GOAL := help

.PHONY: help venv install lint format-check test test-cov build-db dashboard \
	fetch-2026 fetch-2026-resultados fetch-2026-secoes consolidate-2026 reconcile-2026 \
	docker-build docker-run clean

help: ## Lista os alvos disponíveis
	@awk 'BEGIN {FS = ":.*## "} /^[a-zA-Z0-9_-]+:.*## / {printf "  %-24s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

$(PY):
	$(PYTHON) -m venv $(VENV)
	$(PY) -m pip install --upgrade pip

venv: $(PY) ## Cria o ambiente virtual (padrão: .venv)

install: $(PY) ## Instala o pacote em modo editável com painel e ferramentas de desenvolvimento
	$(PY) -m pip install -e ".[dashboard,dev]"

lint: ## Roda o ruff
	$(PY) -m ruff check .

test: ## Roda a suíte de testes
	$(PY) -m pytest -q

test-cov: ## Roda os testes com relatório de cobertura
	$(PY) -m pytest -q --cov=dataurnas --cov-report=term-missing

build-db: ## Reconstrói o DuckDB a partir dos Parquet de data/parquet
	$(PY) scripts/build_db.py

dashboard: ## Inicia o painel Streamlit (padrão: http://localhost:8501)
	$(PY) -m dataurnas.cli dashboard --port $(PORT)

fetch-2026: fetch-2026-resultados fetch-2026-secoes ## Coleta o resultado oficial e os BUs por seção de 2026

fetch-2026-resultados: ## Baixa o resultado agregado oficial de 2026 (Brasil, UFs e municípios)
	$(PY) scripts/ele2026/fetch_resultados.py

fetch-2026-secoes: ## Coleta os BUs de 2026 por seção, com retomada (UFS=ac,rr para limitar)
	$(PY) scripts/ele2026/fetch_secoes.py $(UFS_ARG)

consolidate-2026: ## Só consolida as partes já coletadas de 2026
	$(PY) scripts/ele2026/fetch_secoes.py --so-consolidar

reconcile-2026: ## Compara a soma dos BUs de 2026 com o resultado oficial por UF
	$(PY) scripts/ele2026/reconcile.py $(UFS_ARG)

docker-build: ## Constrói a imagem Docker do painel
	docker build -t $(IMAGE) .

docker-run: ## Roda a imagem Docker em http://localhost:7860
	docker run --rm -p 7860:7860 $(IMAGE)

clean: ## Remove caches de build, testes e lint
	rm -rf build dist .pytest_cache .ruff_cache .coverage htmlcov
	find . -path ./$(VENV) -prune -o -type d -name __pycache__ -prune -exec rm -rf {} +
