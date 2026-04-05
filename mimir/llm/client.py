import asyncio

from httpx import AsyncClient

from mimir.config import config
from mimir.logger import logger
from mimir.llm.embedding import embedding_model


class LLMClient:
    def __init__(self):
        headers = {
            "Content-Type": "application/json",
        }

        if config.api_key:
            headers["Authorization"] = f"Bearer {config.api_key}"

        self._client = AsyncClient(
            base_url=config.llm_base_url, headers=headers, timeout=120.0
        )

    async def complete(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        try:
            payload = {
                "model": config.llm_model,
                "messages": messages,
                "max_tokens": max_tokens or config.llm_max_tokens,
                "temperature": temperature or config.llm_temperature,
            }

            logger.info("Sending request to LLM", payload=payload)

            if tools:
                payload["tools"] = tools
                payload["tool_choice"] = "auto"

            response = await self._client.post("/v1/chat/completions", json=payload)

            logger.info(
                "Received response from LLM",
                status_code=response.status_code,
                response=response.text,
            )

            response.raise_for_status()

            result = response.json()

            logger.info("Received response from LLM", result=result)
            if "choices" in result and len(result["choices"]) > 0:
                return result["choices"][0]["message"]["content"]

            return {"error": "No choices returned from LLM"}
        except Exception as e:
            logger.error("Error in LLMClient.complete", error=str(e))
            raise

    async def embed(self, input: str) -> list[float]:
        return await asyncio.to_thread(embedding_model.embed, input)

    async def embed_batch(self, inputs: list[str]) -> list[list[float]]:
        return await asyncio.to_thread(embedding_model.embed_batch, inputs)

    async def close(self):
        await self._client.aclose()


llm_client = LLMClient()
