from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from agent_core.config import agent_config
from shared.db import initialize_db, dispose_db
from shared.logger import logger
from agent_core.llm.client import llm_client
from agent_core.memory.semantic import SemanticMemory
from agent_core.rag.watcher import AsyncFileWatcher
from agent_core.routes.approvals import router as approvals_router
from agent_core.routes.brief import router as brief_router
from agent_core.routes.chat import router as chat_router
from agent_core.routes.conversations import router as conversations_router
from agent_core.routes.digest import router as digest_router
from agent_core.routes.ingest import router as ingest_router
from agent_core.routes.memory import router as memory_router
from agent_core.scheduler.jobs import create_scheduler
from agent_core.ws.router import ws_endpoint
from shared.telemetry import setup_tracing

setup_tracing(service_name=agent_config.service_name)

_DIST_DIR = Path(__file__).parent.parent / "agent_ui" / "dist"


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_db(agent_config.database_url)
    scheduler = create_scheduler()
    scheduler.start()
    logger.info("agent_api_started")

    watcher = AsyncFileWatcher()
    await watcher.start()
    yield
    scheduler.shutdown()
    await watcher.stop()
    await dispose_db()
    await llm_client.close()
    logger.info("agent_api_stopped")


app = FastAPI(lifespan=lifespan)
FastAPIInstrumentor().instrument_app(app)
app.include_router(conversations_router, prefix="/api", tags=["conversations"])
app.include_router(chat_router, prefix="/api", tags=["chat"])
app.include_router(ingest_router, prefix="/api", tags=["ingest"])
app.include_router(approvals_router, prefix="/api", tags=["approvals"])
app.include_router(memory_router, prefix="/api", tags=["memory"])
app.include_router(digest_router, prefix="/api", tags=["digest"])
app.include_router(brief_router, prefix="/api", tags=["brief"])
app.add_api_websocket_route("/ws", ws_endpoint)

semantic_memory = SemanticMemory()


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/{full_path:path}", include_in_schema=False)
async def spa_fallback(full_path: str) -> FileResponse:
    """Serve the SPA for all non-API routes; fall back to index.html for unknown paths."""
    dist = _DIST_DIR.resolve()
    try:
        candidate = (dist / full_path).resolve()
        candidate.relative_to(dist)  # raises ValueError if path escapes dist
    except ValueError:
        return FileResponse(dist / "index.html")
    if candidate.exists() and candidate.is_file():
        return FileResponse(candidate)
    return FileResponse(dist / "index.html")
