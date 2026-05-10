# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Mimir** is a self-hosted, privacy-first personal AI assistant. All inference runs locally on your hardware. The system combines a FastAPI backend with a Slack interface, persistent conversation storage, a three-tier memory architecture, and a RAG pipeline over personal documents.

**Current Phase:** Phase 3 (starting). Phase 2 is complete. Active work: distributed tracing/observability, conversation-aware memory writes, hybrid RAG.

The primary user interface is now a React SPA (`agent_ui/`) served directly by the FastAPI backend. Slack remains a secondary interface.

---

## Architecture at a Glance

```
┌──────────────────────────────────────────────────────────────┐
│  Mimir Host                                                  │
│                                                              │
│  ┌─────────────┐    ┌──────────────────────────────────┐     │
│  │  Local LLM  │◄───│  Agent Core (FastAPI :8000)      │     │
│  │  (MLX-LM /  │    │  agent_core/                     │     │
│  │  llama.cpp) │    │  • agent/ (tool loop, approval)  │     │
│  └─────────────┘    │  • memory/ (semantic, episodic)  │     │
│                     │  • rag/ (ingest, retrieval)      │     │
│  ┌─────────────┐    │  • scheduler/ (APScheduler jobs) │     │
│  │  pgvector   │◄───│  • routes/ (chat, approvals…)    │     │
│  └─────────────┘    │  • ws/     (WebSocket /ws)       │     │
│                     └──────────────┬───────────────────┘     │
│                                    │ HTTP (MCP client)       │
│  ┌─────────────┐                   ▼                         │
│  │   Vault     │    ┌──────────────────────────────────┐     │
│  │  (docs/md)  │    │  MCP Server (FastMCP :8010)      │     │
│  └─────────────┘    │  mcp_server/                     │     │
│                     │  • search, calendar, k8s, memory │     │
│                     └──────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────┘
                            │
          ┌─────────────────┼──────────────────┐
          │                 │                  │
   ┌──────┴──────┐  ┌───────┴──────┐  ┌────────┴───────┐
   │  Slack Bot  │  │  React SPA   │  │  REST API /    │
   │  slackbot/  │  │  agent_ui/   │  │  Ingest CLI    │
   └─────────────┘  │  (WS + HTTP) │  └────────────────┘
                    └──────────────┘
```

### Top-level packages

| Package       | Responsibility                                                                             |
| ------------- | ------------------------------------------------------------------------------------------ |
| `agent_core/` | FastAPI service. Conversation state, memory assembly, LLM dispatch, RAG, scheduling        |
| `agent_ui/`   | React SPA (Vite + Zustand + Tailwind/shadcn). Built artifact is served by FastAPI.         |
| `mcp_server/` | FastMCP service (port 8010). Exposes tools to the agent: search, calendar, k8s, memory     |
| `slackbot/`   | Slack Bolt app, Socket Mode. Translates Slack events to Agent Core HTTP calls              |
| `shared/`     | Cross-package code: ORM models, DB session, config base class, schemas, telemetry, logging |
| `web_fetch/`  | Standalone web fetcher service                                                             |
| `migrations/` | Alembic migrations (source of truth for DB schema)                                         |

### Key subsystems within `agent_core/`

- **`agent/`** — Tool loop, MCP client, approval state machine, conversation manager
- **`llm/`** — OpenAI-compatible client, embedding client, message/prompt assembly
- **`memory/`** — Semantic (reads `vault/memory.md`) and episodic (pgvector summaries)
- **`prompts/`** — System prompt, briefing, RSS, episodic prompt builders
- **`rag/`** — Ingest (Markdown/PDF), chunking, file watcher, retrieval
- **`routes/`** — FastAPI route handlers (`chat`, `conversations`, `ingest`, `approvals`, `memory`, `digest`, `brief`)
- **`scheduler/`** — APScheduler jobs: episodic consolidation, morning brief, RSS digest
- **`ws/`** — WebSocket endpoint (`/ws`), per-conversation sender registry, message handlers

---

## Development Commands

### Setup

```bash
uv sync                          # Install all dependencies
docker compose up postgres -d    # Start PostgreSQL + pgvector
uv run alembic upgrade head      # Apply all migrations
```

### Running (use `make` targets)

```bash
make api      # FastAPI agent core on :8000
make mcp      # MCP server on :8010
make slack    # Slack bot (also scales down the k8s deployment and restores on exit)
make gemma    # Start local LLM via llama-server
```

Or directly:
```bash
uv run fastapi dev agent_core/main.py --port 8000
uv run python -m mcp_server.server
uv run python -m slackbot.bot
uv run python scripts/ingest.py --path ./vault   # Bulk ingest
```

### Frontend (agent_ui)

The SPA is a Vite + React app. In production, `make api` serves the pre-built `agent_ui/dist/` via FastAPI's catch-all route. During frontend development, run the Vite dev server alongside the API:

```bash
cd agent_ui
npm install
npm run dev      # Vite dev server on :5173 (proxies /api and /ws to :8000)
npm run build    # Outputs to agent_ui/dist/
npm run lint     # ESLint
```

### Development & Quality

```bash
uv run pytest                      # All tests (skips integration if no DB)
uv run pytest tests/unit -v        # Unit tests only
uv run pytest -k test_name         # Single test
uv run pytest --cov                # With coverage

uv run ruff check .                # Lint
uv run ruff format .               # Format
uv run ty check                    # Type check

uv run pre-commit run --all-files  # All pre-commit hooks
```

### Database Migrations

```bash
uv run alembic current
uv run alembic revision --autogenerate -m "description"
uv run alembic upgrade head
uv run alembic downgrade -1
```

---

## Core Patterns & Key Design Decisions

### Configuration split (`shared/config.py`, `agent_core/config.py`, `mcp_server/config.py`)

`SharedConfig` (in `shared/`) is the Pydantic `BaseSettings` base class with common settings (DB URL, CalDAV, telemetry). `AgentConfig` extends it with agent-specific settings (LLM, memory budgets, MCP URL, approval timeouts). `MCP_SERVER_CONFIG` in `mcp_server/` extends `SharedConfig` with MCP-specific overrides. All configs read from `.env`. Config is instantiated at module import time — set env vars before importing any mimir module (see `tests/conftest.py`).

### Token Budget Management (`agent_core/llm/messages.py`)

System prompt assembly runs under explicit token caps per component (`RAG_MAX_TOKENS`, `EPISODIC_MAX_TOKENS`, `SEMANTIC_MEMORY_MAX_TOKENS`). The conversation window fills remaining budget, bounded by `CONVERSATION_WINDOW_MIN`/`MAX`.

**Fallback chain:** HTTP 413 → retry without RAG/episodic → retry with minimal system prompt + last 2 messages.

### Three-Tier Memory Architecture

1. **Semantic** — `vault/memory.md`, human-editable, injected verbatim per request. Changes take effect on the next message, no restart needed.
2. **Episodic** — Auto-summarized conversation threads stored as pgvector embeddings. Retrieved by cosine similarity and injected as context.
3. **Working** — Sliding message window, sized dynamically within configured bounds.

### Tool Calling & MCP (`agent_core/agent/`, `mcp_server/`)

The agent runs a multi-step tool loop (`agent_core/agent/tools.py`). Tools are fetched from the MCP server's schema endpoint and cached for `MCP_SCHEMA_CACHE_TTL_SECONDS` seconds. MCP tools are registered via side-effect imports in `mcp_server/server.py`.

Two decorators in `mcp_server/decorators.py`:
- `@traced_tool` — registers a read-only tool with automatic OTel tracing
- `@write_tool` — registers a write tool with `destructiveHint=True` + injects an `action_id` parameter; execution only proceeds if an approved `PendingAction` exists in the DB for that `action_id`

### WebSocket Interface (`agent_core/ws/`, `/ws`)

The React SPA communicates exclusively over WebSocket. The `/ws` endpoint in `agent_core/main.py` is the entry point. `ws/registry.py` holds a per-conversation `WSSender` map so that approval callbacks and scheduler jobs can push events to the correct connection. `ws/handlers/chat.py` drives the full streaming tool loop and emits typed events (`thinking`, `tool_call`, `tool_result`, `approval_required`, `done`, etc.) defined in `shared/schemas.py` (`WSChatRequest`, `ServerEvent`). The Slack bot uses the REST `POST /api/chat` endpoint instead.

### Write Approval Flow (`agent_core/agent/approval/`, `slackbot/approval.py`)

When the agent detects a tool call with `destructiveHint=True`, it routes through the approval state machine instead of executing directly. State: `PENDING → APPROVED/REJECTED/DISCUSSING → COMPLETED/FAILED`.

- Auto-reject timeout: `APPROVAL_TIMEOUT_MINUTES` (default 10 min) for `PENDING`
- Discussion mode timeout: `APPROVAL_DISCUSS_TIMEOUT_HOURS` (default 24h)
- After approval, MCP tool is re-invoked with the `action_id`; LLM is optionally re-invoked with the result (`APPROVAL_REINVOKE_LLM`)

### Database & Async (`shared/db.py`, `shared/models.py`)

- Fully async: SQLAlchemy (async) + asyncpg
- All ORM models live in `shared/models.py`: `ConversationModel`, `MessageModel`, `EpisodicMemoryModel`, `DocumentChunk`, `PendingActionModel`, `RssDigestEntry`
- Migrations in `migrations/versions/`

### Conversation Isolation

Conversations are keyed by `{channel_id}|{thread_ts}` in Slack. DMs use message `ts` as the thread suffix. This persists conversations across process restarts.

### Push Notifications (`shared/external/ntfy.py`)

Scheduler jobs (morning brief, RSS digest) can push notifications via ntfy. Configured through `NTFY_URL`, `NTFY_DIGEST_TOPIC`, `NTFY_MORNING_BRIEF_TOPIC`, and `NTFY_MESSAGES_TOPIC` in `.env`. All calls are fire-and-forget; failures are logged and never raised.

### Observability

Structured logging via `structlog` (`shared/logger.py`). OpenTelemetry tracing via `shared/telemetry.py`. Set `OTEL_EXPORTER_OTLP_ENDPOINT` to export traces (e.g. Grafana Alloy). Set `ENV=production` for JSON log output.

---

## Testing Strategy

- `@pytest.mark.integration` — requires live PostgreSQL
- LLM is mocked at the `llm_client` boundary for unit tests
- Contract tests (real LLM) and behavioural evals (LLM-as-judge) are planned but not yet implemented

---

## Adding New MCP Tools

1. Create tool function in `mcp_server/tools/` using `@traced_tool` (read) or `@write_tool` (write)
2. Import the module (side-effect) in `mcp_server/server.py`
3. Write tools require no additional wiring — the `@write_tool` decorator handles the approval gate

## Adding a New API Endpoint

1. Create route handler in `agent_core/routes/`
2. Register router in `agent_core/main.py` via `app.include_router()`

## Adding a Database Model

1. Define model in `shared/models.py`
2. `uv run alembic revision --autogenerate -m "description"`
3. `uv run alembic upgrade head`

---

## Important Gotchas

- **Async everywhere:** All DB calls, HTTP calls, and scheduler jobs are async.
- **Socket Mode:** Slack bot uses Socket Mode — no public inbound webhook, no open port.
- **Config at import time:** Env vars must be set before any mimir module import. See `tests/conftest.py`.
- **MCP tool registration is via side-effects:** Tools only exist if their module is imported in `mcp_server/server.py`.
- **`write_tool` injects `action_id`:** The decorator modifies the function signature; MCP callers must pass `action_id` as a kwarg pointing to an approved `PendingAction` UUID.
- **Pre-commit hooks:** ruff (check + format), ty (type check) run before commit.

---

## Useful References

- **All config variables:** `agent_core/config.py` (extends `shared/config.py`)
- **DB schema:** `migrations/versions/` + `shared/models.py`
- **System prompt assembly:** `agent_core/llm/messages.py` + `agent_core/prompts/system.py`
- **MCP tool decorators:** `mcp_server/decorators.py`
- **Approval flow entry:** `agent_core/agent/approval/manager.py`
- **REST chat flow (Slack):** `agent_core/routes/chat.py` → `agent_core/agent/llm_dispatch.py` → `agent_core/agent/tools.py`
- **WS chat flow (SPA):** `agent_core/ws/router.py` → `agent_core/ws/handlers/chat.py` → `agent_core/agent/tools.py`
- **WebSocket event types:** `shared/schemas.py` (`WSChatRequest`, `LLMSettings`) + `agent_ui/src/types/index.ts` (`ServerEvent`, `ClientEvent`)
