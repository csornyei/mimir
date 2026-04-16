from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
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
from mimir.scheduler.jobs import consolidate_idle_threads, process_approval_timeouts


@asynccontextmanager
async def lifespan(app: FastAPI):
    initialize_db(config.database_url)
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        consolidate_idle_threads,
        IntervalTrigger(minutes=5),
        id="consolidate_idle_threads",
        replace_existing=True,
    )
    scheduler.add_job(
        process_approval_timeouts,
        IntervalTrigger(minutes=1),
        id="process_approval_timeouts",
        replace_existing=True,
    )
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
