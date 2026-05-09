FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.11.5 /uv /uvx /bin/

WORKDIR /app

ENV HF_HOME=/app/.cache/huggingface
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1


RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-dev --no-install-project --group agent

COPY agent_core agent_core/
COPY scripts scripts/
COPY shared shared/
COPY config config/
COPY agent_ui/dist agent_ui/dist/
COPY pyproject.toml uv.lock ./

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev --group agent
