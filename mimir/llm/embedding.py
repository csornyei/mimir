from httpx import AsyncClient

from mimir.agent.config import agent_config
from mimir.logger import logger


class EmbeddingModel:
    def __init__(self, model_name: str = agent_config.embedding_model):
        self._model_name = model_name
        headers = {
            "Content-Type": "application/json",
        }

        self._client = AsyncClient(
            base_url=agent_config.embedding_url, headers=headers, timeout=60.0
        )

    async def embed_query(self, query: str) -> list[float]:
        try:
            response = await self._client.post(
                "/v1/embeddings",
                json={
                    "model": self._model_name,
                    "input": [query],
                    "prompt_name": "query",
                },
            )

            response.raise_for_status()

            resp_body = response.json()

            data = resp_body.get("data", [])
            if not data or not isinstance(data, list) or "embedding" not in data[0]:
                logger.error(
                    "embedding_response_malformed",
                    response_body=resp_body,
                )
                raise ValueError("Malformed embedding response")

            embedding = data[0]["embedding"]
            if not isinstance(embedding, list) or not all(
                isinstance(x, (int, float)) for x in embedding
            ):
                logger.error(
                    "embedding_response_invalid_embedding",
                    embedding=embedding,
                )
                raise ValueError("Invalid embedding format")

            return embedding
        except Exception as e:
            logger.error(
                "response_error",
                status_code=getattr(e, "response", {}).get("status_code"),
                error=str(e),
            )
            logger.error("embedding_query_failed", error=str(e))
            raise e

    async def embed_document(self, documents: list[str]) -> list[list[float]]:
        try:
            response = await self._client.post(
                "/v1/embeddings",
                json={
                    "model": self._model_name,
                    "input": documents,
                    "prompt_name": "document",
                },
            )

            response.raise_for_status()

            resp_body = response.json()
            data = resp_body.get("data", [])
            if not data or not isinstance(data, list) or "embedding" not in data[0]:
                logger.error(
                    "embedding_response_malformed",
                    response_body=resp_body,
                )
                raise ValueError("Malformed embedding response")

            embeddings = []

            for item in data:
                embedding = item.get("embedding")
                if not isinstance(embedding, list) or not all(
                    isinstance(x, (int, float)) for x in embedding
                ):
                    logger.warning(
                        "embedding_response_invalid_embedding",
                        embedding=embedding,
                    )
                embeddings.append(embedding)

            return embeddings
        except Exception as e:
            logger.error("embedding_document_failed", error=str(e))
            raise e


embedding_model = EmbeddingModel()

if __name__ == "__main__":
    test_text = "Hello, world!"
    embedding = embedding_model.embed_query(test_text)
    print(f"Embedding for '{test_text}': {embedding}")
