from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from fastapi import FastAPI

from mimir.db import engine
from mimir.llm.client import llm_client
from mimir.memory.semantic import SemanticMemory
from mimir.rag.watcher import AsyncFileWatcher
from mimir.routes.chat import router as chat_router
from mimir.routes.conversations import router as conversations_router
from mimir.routes.ingest import router as ingest_router
from mimir.scheduler.jobs import consolidate_idle_threads


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        consolidate_idle_threads,
        IntervalTrigger(minutes=5),
        id="consolidate_idle_threads",
        replace_existing=True,
    )
    scheduler.start()

    watcher = AsyncFileWatcher()
    await watcher.start()
    yield
    scheduler.shutdown()
    await watcher.stop()
    await engine.dispose()
    await llm_client.close()


app = FastAPI(lifespan=lifespan)
app.include_router(conversations_router, prefix="/api", tags=["conversations"])
app.include_router(chat_router, prefix="/api", tags=["chat"])
app.include_router(ingest_router, prefix="/api", tags=["ingest"])

semantic_memory = SemanticMemory()


@app.get("/health")
async def health():
    return {"status": "ok"}
