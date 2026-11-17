# syntax=docker/dockerfile:1
# Build with: docker build -f gcp/Dockerfile --build-context cloud-runtime=gcp/runtime backend
# Only backend/ is sent as context; the repository's .env never reaches Docker.
FROM python:3.14-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
ENV UV_LINK_MODE=copy UV_PROJECT_ENVIRONMENT=/app/.venv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project

FROM python:3.14-slim AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PATH="/app/.venv/bin:$PATH"
WORKDIR /app
COPY --from=builder --chown=10001:10001 /app/.venv /app/.venv
COPY --chown=10001:10001 app ./app
COPY --chown=10001:10001 migrations ./migrations
COPY --chown=10001:10001 alembic.ini ./
COPY --from=cloud-runtime --chown=10001:10001 baseline.sql ./
COPY --from=cloud-runtime --chown=10001:10001 migrate.py ./gcp_migrate.py
USER 10001:10001
EXPOSE 8080
# No Lambda base, runtime interface, handler or adapter. A migration job uses
# the same image with its command overridden to `python gcp_migrate.py`.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --log-level ${LOG_LEVEL:-info}"]
