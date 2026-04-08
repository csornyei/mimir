import asyncio

from httpx import AsyncClient, HTTPStatusError

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
        fallbacks: list[list[dict]] | None = None,
    ) -> str:
        candidates = [messages] + (fallbacks or [])
        last_413: HTTPStatusError | None = None

        for attempt, msgs in enumerate(candidates):
            try:
                payload = {
                    "model": config.llm_model,
                    "messages": msgs,
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

            except HTTPStatusError as e:
                if e.response.status_code == 413:
                    estimated_tokens = sum(
                        len(m.get("content", "")) // 4 for m in msgs
                    )
                    logger.warning(
                        "llm_payload_too_large",
                        attempt=attempt,
                        token_estimate=estimated_tokens,
                        fallbacks_remaining=len(candidates) - attempt - 1,
                    )
                    last_413 = e
                    continue
                logger.error("Error in LLMClient.complete", error=str(e))
                raise

            except Exception as e:
                logger.error("Error in LLMClient.complete", error=str(e))
                raise

        logger.error(
            "All payload fallbacks exhausted",
            attempts=len(candidates),
        )
        raise last_413

    async def embed(self, input: str) -> list[float]:
        return await asyncio.to_thread(embedding_model.embed, input)

    async def embed_batch(self, inputs: list[str]) -> list[list[float]]:
        return await asyncio.to_thread(embedding_model.embed_batch, inputs)

    async def close(self):
        await self._client.aclose()


llm_client = LLMClient()
