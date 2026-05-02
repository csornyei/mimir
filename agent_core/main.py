from contextlib import asynccontextmanager

from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from agent_core.config import agent_config
from shared.db import initialize_db, dispose_db
from shared.logger import logger
from agent_core.llm.client import llm_client
from agent_core.memory.semantic import SemanticMemory
from agent_core.rag.watcher import AsyncFileWatcher
from agent_core.routes.approvals import router as approvals_router
from agent_core.routes.chat import router as chat_router
from agent_core.routes.conversations import router as conversations_router
from agent_core.routes.ingest import router as ingest_router
from agent_core.scheduler.jobs import create_scheduler
from agent_core.ws.router import ws_endpoint
from shared.telemetry import setup_tracing

setup_tracing(service_name=agent_config.service_name)


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
app.add_api_websocket_route("/ws", ws_endpoint)

semantic_memory = SemanticMemory()


@app.get("/health")
async def health():
    return {"status": "ok"}
