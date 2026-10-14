FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# HF Spaces executa o contêiner com o usuário uid 1000. O diretório da
# aplicação já nasce dele, sem chown recursivo depois do build: num chown -R,
# o overlayfs copia para a camada nova cada arquivo vindo de um COPY anterior
# (os Parquet seriam duplicados na imagem) e o passo percorre o banco inteiro.
RUN useradd --create-home --uid 1000 app \
    && mkdir -p /app/data/db \
    && chown app:app /app /app/data /app/data/db
WORKDIR /app

# Dependências primeiro (camada reaproveitada entre builds)
COPY requirements.txt .
RUN pip install -r requirements.txt

# Código e dados distribuídos (lista explícita; o .dockerignore cobre o resto).
# data/parquet inclui agregados/, os agg_* pré-calculados com manifesto: o
# build só os importa, sem recalcular sobre os 72 milhões de votos.
COPY --chown=app:app pyproject.toml README.md ./
COPY --chown=app:app src ./src
COPY --chown=app:app spec ./spec
COPY --chown=app:app scripts/build_db.py ./scripts/build_db.py
COPY --chown=app:app data/parquet ./data/parquet
COPY --chown=app:app .streamlit ./.streamlit

# Instalação editável (precisa de root para o site-packages): mantém spec/ e
# data/ resolvidos a partir de /app
RUN pip install --no-deps -e .

# O banco é gerado já como o usuário final, direto no caminho definitivo
# (--no-live: sem segunda cópia de ~1,8 GB)
USER app
RUN python scripts/build_db.py --no-live

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:7860/_stcore/health', timeout=4).status == 200 else 1)"

CMD ["streamlit", "run", "src/dataurnas/dashboard/app.py", \
     "--server.port=7860", \
     "--server.address=0.0.0.0"]
