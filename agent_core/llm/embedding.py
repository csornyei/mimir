from typing import Literal

from httpx import AsyncClient

from agent_core.config import agent_config
from shared.logger import logger


class EmbeddingModel:
    def __init__(self, model_name: str = agent_config.embedding_model):
        self._model_name = model_name
        headers = {
            "Content-Type": "application/json",
        }

        self._client = AsyncClient(
            base_url=agent_config.embedding_url, headers=headers, timeout=60.0
        )

    async def embed(
        self, query: list[str], prefix: Literal["search_document", "search_query"]
    ) -> list[list[float]]:
        try:
            response = await self._client.post(
                "/api/embed",
                json={
                    "model": self._model_name,
                    "input": [f"{prefix}: {q}" for q in query],
                },
            )

            response.raise_for_status()

            body = response.json()

            embeddings = body["embeddings"]

            return embeddings
        except Exception as e:
            logger.error(
                "embedding_failed",
                error=str(e),
                error_type=type(e).__name__,
                status_code=getattr(getattr(e, "response", None), "status_code", None),
                exc_info=True,
            )
            raise

    async def embed_query(self, query: str) -> list[float]:
        try:
            embeddings = await self.embed([query], "search_query")

            if len(embeddings) != 1:
                logger.error(
                    "embedding_error",
                    query="***".join([query[:5], query[-5:]]),
                    embeddings_count=len(embeddings),
                )
                raise ValueError()

            return embeddings[0]
        except Exception as e:
            logger.error(
                "embedding_query_failed",
                error=str(e),
                error_type=type(e).__name__,
                status_code=getattr(getattr(e, "response", None), "status_code", None),
                exc_info=True,
            )
            raise

    async def embed_document(self, documents: list[str]) -> list[list[float]]:
        try:
            embeddings = await self.embed(documents, "search_document")

            return embeddings
        except Exception as e:
            logger.error(
                "embedding_document_failed",
                error=str(e),
                error_type=type(e).__name__,
                status_code=getattr(getattr(e, "response", None), "status_code", None),
                document_count=len(documents),
                exc_info=True,
            )
            raise

    async def embed_single_document(self, document: str) -> list[float]:
        try:
            embeddings = await self.embed_document([document])

            if len(embeddings) != 1:
                logger.error(
                    "embedding_single_document_error",
                    document="***".join([document[:5], document[-5:]]),
                    embeddings_count=len(embeddings),
                )
                raise ValueError()

            return embeddings[0]
        except Exception as e:
            logger.error(
                "embedding_single_document_failed",
                error=str(e),
                error_type=type(e).__name__,
                status_code=getattr(getattr(e, "response", None), "status_code", None),
                document="***".join([document[:5], document[-5:]]),
                exc_info=True,
            )
            raise


embedding_model = EmbeddingModel()

if __name__ == "__main__":
    from asyncio import run as asyncio_run

    test_text = "Hello, world!"
    embedding = asyncio_run(embedding_model.embed([test_text], "search_query"))
    print(f"Embedding for '{test_text}': {embedding}")
