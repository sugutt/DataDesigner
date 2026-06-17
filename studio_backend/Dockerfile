FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
COPY alembic.ini ./
COPY packages ./packages
COPY studio_backend ./studio_backend
COPY scripts ./scripts

RUN uv sync --all-packages --group studio --frozen

ENV PATH="/app/.venv/bin:${PATH}"

EXPOSE 8000
