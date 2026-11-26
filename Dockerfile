# syntax=docker/dockerfile:1

# ---- front: build do React (Vite) para arquivos estáticos
FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# ---- build: o uv só existe neste estágio
FROM python:3.12-slim AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.6 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
# Dependências primeiro: esta camada é reaproveitada enquanto só o código muda.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY README.md ./
COPY src ./src
RUN uv sync --frozen --no-dev --no-editable

# ---- runtime
FROM python:3.12-slim
LABEL org.opencontainers.image.source="https://github.com/dpontejs/hachibu"
RUN useradd --system --uid 10001 --no-create-home app && mkdir /data && chown app:app /data
COPY --from=build /app/.venv /app/.venv
COPY --from=web /web/dist /app/static
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    DB_PATH=/data/hachibu.db \
    STATIC_DIR=/app/static
WORKDIR /app
USER app
# O SQLite fica aqui; monte um volume para os dados sobreviverem a imagens novas.
VOLUME /data
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2)"]
# Só o Caddy acessa o container, então o IP repassado (usado no limite de login) é confiável.
CMD ["uvicorn", "hachibu.app:from_env", "--factory", "--host", "0.0.0.0", "--port", "8000", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
