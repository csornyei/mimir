FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.11.5 /uv /uvx /bin/

WORKDIR /app

ENV HF_HOME=/app/.cache/huggingface
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1

# Which workflow module to run, e.g. "morning_briefing.main" or "rss_digest.fetcher".
ARG module

RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-dev --no-install-project --group workflows

COPY shared/ ./shared/
COPY workflows/ ./workflows/
COPY config/ ./config/
COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --group workflows

ENV WORKFLOW_MODULE=${module}
ENTRYPOINT ["sh", "-c", "uv run python -m workflows.${WORKFLOW_MODULE} \"$@\"", "--"]
