FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# HF Spaces executa o contêiner com o usuário uid 1000
RUN useradd --create-home --uid 1000 app
WORKDIR /app

# Dependências primeiro (camada reaproveitada entre builds)
COPY requirements.txt .
RUN pip install -r requirements.txt

# Código e dados distribuídos (lista explícita; o .dockerignore cobre o resto)
COPY pyproject.toml README.md ./
COPY src ./src
COPY spec ./spec
COPY scripts/build_db.py ./scripts/build_db.py
COPY data/parquet ./data/parquet
COPY .streamlit ./.streamlit

# Instalação editável: mantém spec/ e data/ resolvidos a partir de /app
RUN pip install --no-deps -e . \
    && python scripts/build_db.py --no-live \
    && chown -R app:app /app

USER app

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:7860/_stcore/health', timeout=4).status == 200 else 1)"

CMD ["streamlit", "run", "src/dataurnas/dashboard/app.py", \
     "--server.port=7860", \
     "--server.address=0.0.0.0"]
