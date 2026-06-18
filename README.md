# Mimir

Built as both a daily tool and a portfolio project, Mimir is an exercise in designing AI systems that are actually trustworthy: explicit memory you can read and edit, human-in-the-loop for all writes, and an observability stack that tells you exactly what happened and why.

Mimir connects to any OpenAI-compatible local inference server (MLX-LM, llama.cpp, Ollama) and layers a full assistant stack on top: persistent conversations, three-tier memory, a RAG pipeline over your personal documents, a web UI (React SPA) for natural interaction, and a tool-calling loop backed by an MCP server.

---

## Goals & Principles

**Local-first.** All inference runs on hardware you own. The model, embeddings, and memory are entirely under your control.

**Transparent memory.** The assistant's knowledge about you lives in a human-readable Markdown file (`vault/memory.md`) you can open in any editor, read, and correct. No opaque vector databases as the source of truth for facts about yourself. If Mimir learns something wrong, you open the file, fix it, save — done.

**Configurable backbone.** The model, embedding model, and database are all environment variables. Swapping from a 2B model on a laptop to a 26B model on a desktop is a one-line `.env` change.

**Human-in-the-loop for writes.** Read operations are autonomous. Write operations to external systems go through an explicit approval flow before anything executes. This constraint is designed to relax over time as trust is established, not before.

---

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│  Mimir Host                                                  │
│                                                              │
│  ┌─────────────┐    ┌──────────────────────────────────┐     │
│  │  Local LLM  │◄───│  Agent Core (FastAPI)            │     │
│  │  (MLX-LM /  │    │                                  │     │
│  │  llama.cpp) │    │  ┌────────────┐  ┌────────────┐  │     │
│  └─────────────┘    │  │Conversation│  │  Memory    │  │     │
│                     │  │  Manager   │  │Orchestrator│  │     │
│  ┌─────────────┐    │  └────────────┘  └────────────┘  │     │
│  │  pgvector   │◄───│                                  │     │
│  │ (embeddings)│    │  ┌────────────┐  ┌────────────┐  │     │
│  └─────────────┘    │  │    RAG     │  │ Proactive  │  │     │
│                     │  │  Pipeline  │  │ Scheduler  │  │     │
│  ┌─────────────┐    │  └────────────┘  └────────────┘  │     │
│  │   Vault     │◄───│                                  │     │
│  │  (docs/md)  │    └──────────────┬───────────────────┘     │
│  └─────────────┘                   │ MCP client               │
│                                    ▼                         │
│                     ┌──────────────────────────────────┐     │
│                     │  MCP Server (FastMCP)            │     │
│                     │  • web_search (SearXNG)          │     │
│                     │  • get_calendar_events (CalDAV)  │     │
│                     │  • Kubernetes tools              │     │
│                     │  • append_to_semantic_memory     │     │
│                     └──────────────────────────────────┘     │
└──────────────────────────────────────────────────────────────┘
                            │
              ┌─────────────┴─────────────┐
              │                           │
       ┌──────┴──────┐           ┌────────┴───────┐
       │  React SPA  │           │  REST API /    │
       │ (WS + HTTP) │           │  Ingest CLI    │
       └─────────────┘           └────────────────┘
```

| Component                | Responsibility                                                                     |
| ------------------------ | ---------------------------------------------------------------------------------- |
| **Agent Core**           | FastAPI service. Owns conversation state, memory assembly, and LLM dispatch        |
| **Conversation Manager** | Per-thread message history persisted to PostgreSQL                                 |
| **Memory Orchestrator**  | Assembles the system prompt from semantic memory, episodic recall, and RAG context |
| **RAG Pipeline**         | Chunks, embeds, and indexes documents; retrieves relevant context per query        |
| **Proactive Scheduler**  | APScheduler jobs: episodic consolidation, morning brief, RSS digest                |
| **MCP Server**           | FastMCP server exposing tools to the agent: search, calendar, Kubernetes, memory   |
| **pgvector**             | Stores document chunk embeddings and episodic memory summaries                     |
| **React SPA**            | Vite + Zustand frontend served by FastAPI. Talks to Agent Core over WebSocket/HTTP |

---

## Tech Stack

- **Python 3.13** with [`uv`](https://github.com/astral-sh/uv) for dependency management
- **FastAPI** — async API framework
- **FastMCP** — MCP server framework
- **PostgreSQL + pgvector** — conversation history, document embeddings, episodic memories
- **SQLAlchemy (async) + Alembic** — ORM and schema migrations
- **APScheduler** — background scheduling for episodic consolidation, morning brief, RSS digest
- **React + Vite + Zustand** — single-page web UI, served as a static build by FastAPI
- **httpx** — async HTTP client for LLM backend communication
- **watchdog** — filesystem event monitoring for automatic document ingestion
- **nomic-embed-text-v1.5** — local embedding model (768 dimensions), runs entirely in-process
- **structlog** — structured logging with console/JSON renderers
- **kr8s** — async Kubernetes client

---

## What's Built

The following features are implemented and working.

### Three-Tier Memory Architecture

Mimir's memory model consists of the following three tiers:

**Semantic memory** is a human-editable Markdown file (`vault/memory.md`) containing facts about you: preferences, projects, current situation. It is injected verbatim into every system prompt. If you edit it, the next message reflects the change instantly — no restart, no cache to clear. The source of truth for facts about you is a plain text file, not an opaque embedding database.

**Episodic memory** stores summaries of past conversations as vector embeddings in pgvector. After a conversation goes idle for a configurable period, the system automatically summarises it in 2–3 sentences and stores the result. Future queries retrieve relevant summaries by cosine similarity and inject them as context. Re-consolidation is supported: new messages in a previously summarised thread trigger an updated summary built from the prior summary plus the new messages.

**Working memory** is the sliding window of recent messages in the current conversation. The window size is computed dynamically: the system measures the system prompt's token footprint, reserves headroom for the model's reply, and fits as many messages as the remaining budget allows — bounded by configurable minimum and maximum values.

### RAG Pipeline

Indexes personal documents and retrieves relevant chunks per query.

- **Sources:** Markdown (`.md`) and PDF (`.pdf`) files
- **Chunking strategies:**
  - Markdown: split by H2/H3 headers, then by word count (~512 tokens, ~50-token overlap)
  - PDF: split by page, then by paragraph (~400 tokens)
- **Idempotent ingestion:** SHA-256 hash per file — re-ingesting an unchanged file is a no-op; changed files delete stale chunks before re-indexing
- **Three ingestion paths:**
  - **File watcher** — `watchdog` monitors the vault directory; creates and modifications trigger background re-ingestion automatically
  - **Upload endpoint** — `POST /api/ingest` for PDFs or documents outside the vault
  - **Bulk script** — `scripts/ingest.py` for full re-indexing from scratch
- **Retrieval:** Cosine similarity via pgvector's HNSW index, configurable score threshold (default 0.7), and a per-request token budget cap that drops lower-scoring chunks first

### Token Budget Management

The system prompt is assembled under explicit token constraints. Each component has an independent cap: semantic memory, episodic context, and RAG context are all bounded and truncated at word boundaries rather than silently overrunning. The conversation window then fills whatever budget remains after the system prompt is assembled. When the LLM server returns HTTP 413 (payload too large), the client automatically retries with progressively stripped-down payloads: full context → no RAG/episodic → minimal system prompt with the last two messages only.

### MCP Server & Tool Calling

The agent runs a multi-step tool loop against an MCP server running as a separate process. The model requests tool calls; the agent core dispatches them; results feed back into the response — up to a configurable step limit.

**Available tools:**

| Tool                        | Description                                                            |
| --------------------------- | ---------------------------------------------------------------------- |
| `web_search`                | Queries a self-hosted SearXNG instance; returns titles, URLs, snippets |
| `get_calendar_events`       | Fetches events from a CalDAV server for a given date range             |
| `list_pods`                 | Lists pods in a Kubernetes namespace                                   |
| `list_deployments`          | Lists deployments in a Kubernetes namespace                            |
| `list_services`             | Lists services in a Kubernetes namespace                               |
| `list_namespaces`           | Lists all namespaces in the cluster                                    |
| `list_nodes`                | Lists all nodes in the cluster                                         |
| `get_pod_logs`              | Streams the last N lines from a pod                                    |
| `describe_resource`         | Returns the full spec/status of any Kubernetes resource                |
| `deploy_pod`                | Creates a new pod (write — requires approval)                          |
| `append_to_semantic_memory` | Appends a timestamped fact to `memory.md` (write — requires approval)  |

**Write tool approval:** Tools annotated with `@write_tool` set `destructiveHint=True` in their MCP schema. The agent core detects this flag and routes the call through the approval flow before executing. The tool schema cache refreshes every `MCP_SCHEMA_CACHE_TTL_SECONDS` seconds (default 300) so newly added tools appear without a restart.

### Write Approval Flow

Any tool marked as destructive triggers an approval request in the web UI before executing. State machine: `PENDING → APPROVED/REJECTED/DISCUSSING → COMPLETED`.

- 10-minute auto-reject timeout for `PENDING` (configurable `APPROVAL_TIMEOUT_MINUTES`)
- Discussion mode: the user can refine an action before approving
- Configurable timeout for `DISCUSSING` state (`APPROVAL_DISCUSS_TIMEOUT_HOURS`; 0 = no timeout)
- After approval, the MCP tool is re-invoked with the authorised `action_id`; the LLM is optionally re-invoked with the tool result (`APPROVAL_REINVOKE_LLM`)

### Web UI

A React single-page app (Vite + Zustand + Tailwind/shadcn) is the primary interface. In production it is built to static assets and served directly by the FastAPI backend; during development the Vite dev server runs alongside the API.

- Streaming chat over a WebSocket (`/ws`) — thinking, tool calls, tool results, and approvals are pushed as typed events
- Per-conversation isolation, persisted to PostgreSQL across restarts
- Inline approval cards for destructive tool calls

### Morning Briefing

A daily job (APScheduler, configurable hour via `MORNING_BRIEF_HOUR`) fetches today's calendar events from CalDAV and asks the LLM to generate a structured briefing, delivered as an ntfy push notification and available in the web UI.

### RSS News Digest

Four times a day (08:00, 12:00, 16:00, 20:00 UTC) the scheduler fetches unread articles from a self-hosted [Miniflux](https://miniflux.app/) instance, asks the LLM to pick the most relevant ones based on your semantic memory and past feedback, and delivers the selection as an ntfy push notification surfaced in the web UI.

- **LLM-based filtering:** the model scores articles against your `memory.md` profile and a rolling feedback summary so picks improve over time
- **Four windows:** overnight (20→08), morning (08→12), midday (12→16), afternoon (16→20)
- **Persistence:** each selected article is stored in `rss_digest_entries` for feedback tracking

---

## Setup

### Prerequisites

- Python 3.13
- [`uv`](https://github.com/astral-sh/uv)
- PostgreSQL with the [pgvector](https://github.com/pgvector/pgvector) extension
- A running OpenAI-compatible inference server (MLX-LM, llama.cpp, Ollama, etc.)
- Node.js (to build the React web UI)
- (Optional) A self-hosted [SearXNG](https://searxng.github.io/searxng/) instance for web search
- (Optional) A CalDAV server for calendar events and morning briefing
- (Optional) A self-hosted [Miniflux](https://miniflux.app/) instance for the RSS digest

### Local Development

**1. Clone and install dependencies**

```bash
git clone <repo-url> mimir
cd mimir
uv sync
```

**2. Configure the environment**

```bash
cp .env.example .env
```

Edit `.env` with your settings. See the Configuration Reference below for all variables. The MCP server reads from a separate `mcp.env` file (same variables for CalDAV, SearXNG, and the database).

**3. Start the database**

The included Docker Compose file provides PostgreSQL with pgvector pre-installed:

```bash
docker compose up postgres -d
```

**4. Run database migrations**

```bash
uv run alembic upgrade head
```

**5. Start the API server**

```bash
uv run fastapi dev agent_core/main.py --port 8000
```

**6. Start the MCP server** (separate terminal)

```bash
uv run python -m mcp_server.server
```

**7. Start the web UI** (separate terminal, for frontend development)

```bash
cd agent_ui
npm install
npm run dev      # Vite dev server on :5173, proxies /api and /ws to :8000
```

For a production-style run, build the SPA (`npm run build`) — the FastAPI server then serves `agent_ui/dist/` directly, so only steps 5 and 6 are needed.

**8. (Optional) Ingest documents**

Place Markdown or PDF files in `vault/` — the file watcher handles new and modified files automatically. For bulk ingestion of an existing collection:

```bash
uv run python scripts/ingest.py --path ./vault
```

### Docker Compose

The included `docker-compose.yml` runs the full stack: API server (which serves the web UI), MCP server, and PostgreSQL with pgvector.

```bash
# Run migrations first
docker compose --profile migrate up migrate

# Start the full stack
docker compose up -d
```

Set `VAULT_PATH` to mount your document vault into the container:

```bash
VAULT_PATH=/path/to/your/vault docker compose up -d
```

---

## Configuration Reference

All settings are loaded from `.env` via Pydantic Settings. The MCP server reads from `mcp.env`.

### Core

| Variable               | Default                                                       | Description                            |
| ---------------------- | ------------------------------------------------------------- | -------------------------------------- |
| `LLM_BASE_URL`         | `http://localhost:8080`                                       | OpenAI-compatible inference server     |
| `API_KEY`              | _(empty)_                                                     | Bearer token for the LLM server        |
| `LLM_MODEL`            | `google/gemma-4-E2B-it`                                       | Model identifier                       |
| `LLM_MAX_TOKENS`       | `2048`                                                        | Max tokens per completion              |
| `LLM_TEMPERATURE`      | `0.7`                                                         | Sampling temperature                   |
| `LLM_CONTEXT_WINDOW`   | `8192`                                                        | Model context window size (tokens)     |
| `EMBEDDING_MODEL`      | `nomic-ai/nomic-embed-text-v1.5`                              | Local embedding model                  |
| `EMBEDDING_DIMENSION`  | `768`                                                         | Embedding vector dimensions            |
| `SEMANTIC_MEMORY_PATH` | `vault/memory.md`                                             | Path to the semantic memory file       |
| `VAULT_PATH`           | `vault`                                                       | Root directory watched for documents   |
| `DATABASE_URL`         | `postgresql+asyncpg://postgres:postgres@localhost:5432/mimir` | Async PostgreSQL connection string     |
| `AGENT_URL`            | `http://127.0.0.1:8000`                                       | Agent Core URL (internal agent-to-agent calls) |
| `ENV`                  | `development`                                                 | Set to `production` for JSON logging   |

### Memory & Context

| Variable                          | Default | Description                                     |
| --------------------------------- | ------- | ----------------------------------------------- |
| `EPISODIC_IDLE_MINUTES`           | `30`    | Inactivity window before consolidation triggers |
| `EPISODIC_RETRIEVAL_K`            | `3`     | Episodic memories retrieved per query           |
| `EPISODIC_NEW_MESSAGES_THRESHOLD` | `5`     | Min new messages to trigger re-consolidation    |
| `RAG_MAX_TOKENS`                  | `2000`  | Token budget for injected RAG context           |
| `EPISODIC_MAX_TOKENS`             | `600`   | Token budget for injected episodic context      |
| `SEMANTIC_MEMORY_MAX_TOKENS`      | `1500`  | Token budget for injected semantic memory       |
| `CONVERSATION_WINDOW_MIN`         | `2`     | Minimum messages kept in context                |
| `CONVERSATION_WINDOW_MAX`         | `20`    | Maximum messages kept in context                |

### Tool Calling & MCP

| Variable                       | Default                 | Description                                       |
| ------------------------------ | ----------------------- | ------------------------------------------------- |
| `MCP_URL`                      | `http://localhost:8010` | MCP server base URL                               |
| `MCP_SCHEMA_CACHE_TTL_SECONDS` | `300`                   | How long to cache tool schemas before re-fetching |
| `TOOL_MAX_STEPS`               | `5`                     | Maximum tool-calling iterations per request       |
| `TOOL_CALL_TIMEOUT_SECONDS`    | `30`                    | Timeout for a single tool call                    |

### Approval Flow

| Variable                         | Default | Description                                                         |
| -------------------------------- | ------- | ------------------------------------------------------------------- |
| `APPROVAL_TIMEOUT_MINUTES`       | `10`    | Minutes before a PENDING approval is auto-rejected (0 = no timeout) |
| `APPROVAL_DISCUSS_TIMEOUT_HOURS` | `24`    | Hours before a DISCUSSING approval times out (0 = never)            |
| `APPROVAL_REINVOKE_LLM`          | `true`  | Re-invoke the LLM with the tool result after approval               |

### Integrations

| Variable                   | Default  | Description                                           |
| -------------------------- | -------- | ----------------------------------------------------- |
| `CALDAV_URL`               | _(none)_ | CalDAV server URL (morning brief + calendar MCP tool) |
| `CALDAV_USERNAME`          | _(none)_ | CalDAV username                                       |
| `CALDAV_PASSWORD`          | _(none)_ | CalDAV password                                       |
| `MORNING_BRIEF_HOUR`       | `7`      | UTC hour to generate the morning briefing             |
| `MINIFLUX_URL`             | _(none)_ | Miniflux instance URL                                 |
| `MINIFLUX_USERNAME`        | _(none)_ | Miniflux username                                     |
| `MINIFLUX_PASSWORD`        | _(none)_ | Miniflux password                                     |
| `RSS_DIGEST_MIN_ENTRIES`   | `10`     | Minimum articles before a digest window is posted     |
| `RSS_DIGEST_PICKS`         | `10`     | Number of articles the LLM selects per digest         |

### Observability

| Variable                      | Default  | Description                                         |
| ----------------------------- | -------- | --------------------------------------------------- |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | _(none)_ | OTLP endpoint for trace export (e.g. Grafana Alloy) |

---

## API

| Method  | Path                      | Description                                    |
| ------- | ------------------------- | ---------------------------------------------- |
| `POST`  | `/api/chat`               | Send a message; returns the assistant's reply  |
| `GET`   | `/api/conversations`      | List all conversations, ordered by last active |
| `GET`   | `/api/conversations/{id}` | Paginated message history for a conversation   |
| `POST`  | `/api/ingest`             | Upload a Markdown or PDF file for RAG indexing |
| `GET`   | `/api/approvals`          | List pending actions (filterable by message/thread ts) |
| `GET`   | `/api/approvals/{id}`     | Get a specific pending action                  |
| `POST`  | `/api/approvals`          | Create a pending action                        |
| `PATCH` | `/api/approvals/{id}`     | Update a pending action's status               |
| `GET`   | `/health`                 | Health check                                   |

---

## Testing

Testing an LLM-powered system breaks most traditional software testing assumptions — the same input doesn't produce the same output, and correctness is often a matter of quality judgment rather than a binary assertion. Mimir's testing strategy will use three tiers that answer different questions:

**Tier 1 — Unit & Integration tests (deterministic logic):** The LLM is mocked at the `llm_client` boundary. Everything else — prompt assembly, chunking, memory reads/writes, conversation window management, retrieval scoring — is deterministic and testable in the traditional sense.

### Planned tiers:

**Tier 2 — Contract tests (structural LLM behaviour):** Run against a real local inference server. Not evaluating response quality — verifying structural contracts the system depends on: does the model issue a tool call rather than hallucinating an answer when tools are available? Does the model follow a direct instruction consistently? These will be gated behind an explicit test marker.

**Tier 3 — Behavioural evals (output quality):** Uses the LLM-as-judge pattern: a second LLM call evaluates whether the system's response meets natural-language quality criteria. Example criteria: does the response use metric units when memory says metric-only? does it avoid recommending Windows when memory says no Windows? does it surface the correct project blocker when that information was in the RAG context? Each eval case runs multiple times; majority-pass requirement means a consistently failing case signals real behavioural instability, not test flakiness. Results are persisted over time for regression detection and model comparison.

| Tier               | What it tests                        | LLM          | Speed          |
| ------------------ | ------------------------------------ | ------------ | -------------- |
| Unit / Integration | Deterministic logic around the LLM   | Mocked       | Fast (seconds) |
| Contract           | Structural LLM behaviour             | Real (local) | Slow (minutes) |
| Behavioural evals  | Output quality against real criteria | Real + judge | Slow (minutes) |

```bash
# Run all tests
uv run pytest
```

---

## Development

```bash
# Lint and format
uv run ruff check .
uv run ruff format .

# Type check
uv run ty check

# Create a new Alembic migration
uv run alembic revision --autogenerate -m "description"

# Apply migrations
uv run alembic upgrade head
```

---

## Roadmap

The project is developed in phases. Current status: **Phase 2 complete, Phase 3 starting**.

### Phase 2 — Complete

- ✅ Web UI — React SPA over WebSocket, streaming responses, per-conversation isolation
- ✅ Conversation persistence — PostgreSQL-backed, survives process restarts, Alembic migrations
- ✅ RAG pipeline — Markdown and PDF ingestion, file watcher, upload endpoint, cosine retrieval
- ✅ Episodic memory — automatic post-conversation summarisation, vector storage, retrieval, re-consolidation
- ✅ Token budget management — per-component caps, dynamic conversation window, 413 fallback chain
- ✅ MCP server + tool calling loop — multi-step loop, schema caching, write detection
- ✅ Write approval flow — approval-gated state machine, discussion mode, auto-timeout
- ✅ Web search — SearXNG integration via MCP tool
- ✅ Calendar integration — CalDAV client, MCP tool, injected into morning brief
- ✅ Morning briefing — daily LLM-generated brief with today's calendar, delivered via push notification
- ✅ RSS news digest — Miniflux + LLM filtering, four digest windows per day, feedback loop
- ✅ Kubernetes tools — read-only cluster inspection (pods, deployments, services, nodes, logs)

### Phase 3 — Planned: Intelligence & Measurement

**Distributed tracing and quality tracking.** To answer basic operation questions (How often do tool calls fail? Is retrieval quality improving or degrading over time? Are the RAG chunks actually being used in responses?) the system requires observability. Using Grafana-OTel stack (Alloy, Tempo, Prometheus and Loki) will provide a deep understanding on how the system behaves and makes finding bugs and issues easier. Custom metric collection, user feedback for response quality, usage patterns, RAG retrieval and memory relevance heuristics, will help calibrating the different parameters and prompts for the agent.

**Conversation-aware memory writes.** After each conversation ends, the consolidation job runs a second LLM pass to extract durable facts — life changes, new preferences, project decisions — and proposes them as additions to `memory.md` via the same approval flow. This bridges the gap between episodic summaries (narratives) and semantic memory (actionable facts). The extraction prompt distinguishes between durable facts worth persisting and transient details that belong only in episodic summaries.

**Hybrid RAG with BM25 + reranking.** Pure vector similarity has known blind spots: it handles semantic paraphrases well but fumbles on exact terms, proper nouns, error codes, and config key references. Adding PostgreSQL's native `tsvector` full-text search as a second retrieval path (no new infrastructure) and merging the two result sets via Reciprocal Rank Fusion covers both failure modes. A later upgrade path to a lightweight cross-encoder reranker for higher-quality merging.

**Self-evaluation and quality tracking.** Structured instrumentation to measure whether the system is actually getting better or worse over time: thumbs-up/down reactions on responses stored to a ratings table, RAG retrieval relevance tracking (which chunks were injected vs. actually referenced in the response), memory suggestion acceptance rate, and tool call success rate. Surfaced as a Grafana dashboard. Enables data-driven decisions about what to improve next rather than subjective impression.

**Three-tier test suite.** Full implementation of the testing strategy described above: deterministic unit/integration tests with mocked LLM, contract tests verifying structural model behaviour, and an LLM-as-judge eval harness with persistent result tracking for regression detection across model upgrades and prompt changes.

### Phase 4 — Planned: Future Directions

**Multi-file semantic memory with routing.** Once `memory.md` grows beyond ~3,000 tokens, split into domain-specific files (`memory_work.md`, `memory_personal.md`, `memory_hobbies.md`, etc.) with a core file always loaded and domain files selectively injected based on embedding similarity between the user's query and each file's description.

**Structured memory — knowledge graph layer.** Store facts as subject/predicate/object triples enabling relationship traversal ("what do I know related to the energy sector?") that flat files can't express. The Markdown file becomes a generated view of the graph, keeping it human-readable while the graph is the source of truth.

**Observation mode.** Passive activity context from the vault file watcher and git webhooks — a rolling `## Recent activity` section in the system prompt reflecting what you've been working on without you having to explain it. Particularly useful when starting a conversation mid-task.
