# syntax=docker/dockerfile:1

# ── Stage 1: Download the embedding model ─────────────────────────────────────
# Decoupled from uv.lock — only re-runs when load_embedding_model.py changes.
FROM python:3.13-slim AS model-downloader

ENV HF_HOME=/model-cache

RUN pip install --no-cache-dir sentence-transformers huggingface-hub einops

COPY scripts/load_embedding_model.py .
RUN python load_embedding_model.py

# ── Stage 2: Application ───────────────────────────────────────────────────────
FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.11.5 /uv /uvx /bin/

WORKDIR /app

ENV HF_HOME=/app/.cache/huggingface
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

# Pull the pre-downloaded model from stage 1.
# Changing uv.lock no longer invalidates this layer.
COPY --from=model-downloader /model-cache /app/.cache/huggingface

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-dev --no-install-project

COPY mimir mimir/
COPY scripts scripts/
COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev
