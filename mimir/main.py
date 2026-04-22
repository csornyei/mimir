from contextlib import asynccontextmanager

from fastapi import FastAPI

from mimir.config import config
from mimir.db import initialize_db, dispose_db
from mimir.logger import logger
from mimir.llm.client import llm_client
from mimir.memory.semantic import SemanticMemory
from mimir.rag.watcher import AsyncFileWatcher
from mimir.routes.approvals import router as approvals_router
from mimir.routes.chat import router as chat_router
from mimir.routes.conversations import router as conversations_router
from mimir.routes.ingest import router as ingest_router
from mimir.scheduler.jobs import create_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_db(config.database_url)
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
app.include_router(conversations_router, prefix="/api", tags=["conversations"])
app.include_router(chat_router, prefix="/api", tags=["chat"])
app.include_router(ingest_router, prefix="/api", tags=["ingest"])
app.include_router(approvals_router, prefix="/api", tags=["approvals"])

semantic_memory = SemanticMemory()


@app.get("/health")
async def health():
    return {"status": "ok"}
