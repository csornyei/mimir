from contextlib import asynccontextmanager

from fastapi import FastAPI

from mimir.db import engine
from mimir.routes.conversations import router as conversations_router
from mimir.routes.chat import router as chat_router
from mimir.routes.ingest import router as ingest_router

from mimir.memory.semantic import SemanticMemory

from mimir.llm.client import llm_client
from mimir.rag.watcher import AsyncFileWatcher


@asynccontextmanager
async def lifespan(app: FastAPI):
    watcher = AsyncFileWatcher()
    await watcher.start()
    yield
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
