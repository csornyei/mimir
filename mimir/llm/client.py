import asyncio
import json
import re

from httpx import AsyncClient, HTTPStatusError

from mimir.config import config
from mimir.logger import logger
from mimir.llm.embedding import embedding_model


def _extract_tool_calls(content: str) -> list[dict]:
    """Parse raw Gemma 4 tool call tokens from content.

    Fallback for when runtime parser is broken.
    Format: <|tool_call>call:tool_name{arg1:<|"|>value<|"|>,arg2:value}<tool_call|>
    """
    tool_call_re = re.compile(
        r"<\|tool_call>call:(\w+)\{(.*?)\}<tool_call\|>", re.DOTALL
    )
    string_arg_re = re.compile(r'(\w+):<\|"\|>(.*?)<\|"\|>')
    plain_arg_re = re.compile(r"(\w+):([^,}]+)")

    calls = []
    for name, args_str in tool_call_re.findall(content):
        args = {}
        for k, v in string_arg_re.findall(args_str):
            args[k] = v
        for k, v in plain_arg_re.findall(args_str):
            if k not in args:
                raw = v.strip()
                try:
                    args[k] = int(raw)
                except ValueError:
                    try:
                        args[k] = float(raw)
                    except ValueError:
                        args[k] = {"true": True, "false": False}.get(raw.lower(), raw)
        calls.append({"name": name, "arguments": json.dumps(args)})
    return calls


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
    ) -> dict:
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

                if tools:
                    payload["tools"] = tools
                    payload["tool_choice"] = "auto"

                response = await self._client.post("/v1/chat/completions", json=payload)

                logger.debug(
                    "Received response from LLM",
                    status_code=response.status_code,
                )

                response.raise_for_status()

                result = response.json()
                if "choices" not in result or len(result["choices"]) == 0:
                    return {
                        "content": '{"error": "No choices returned from LLM"}',
                        "tool_calls": [],
                        "finish_reason": "stop",
                    }

                usage = result.get("usage") or {}
                prompt_tokens = usage.get("prompt_tokens") or sum(
                    len(m.get("content") or "") // 4 for m in msgs
                )
                completion_tokens = usage.get("completion_tokens")
                logger.info(
                    "llm_tokens",
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=usage.get("total_tokens"),
                    estimated=not bool(usage),
                )

                choice = result["choices"][0]
                message = choice.get("message", {})
                finish_reason = choice.get("finish_reason", "stop")

                # Check if runtime parser worked (only relevant if tools provided)
                if (
                    tools
                    and finish_reason == "tool_calls"
                    and message.get("tool_calls")
                ):
                    # Parser worked, return message with tool_calls
                    return {
                        "content": message.get("content", ""),
                        "tool_calls": message.get("tool_calls", []),
                        "finish_reason": "tool_calls",
                    }
                # Parser broken, try to extract from content
                elif (
                    tools
                    and finish_reason == "stop"
                    and "<|tool_call>" in message.get("content", "")
                ):
                    logger.warning(
                        "runtime_tool_parser_broken",
                        fallback="manual_extraction",
                    )
                    raw_calls = _extract_tool_calls(message.get("content", ""))
                    return {
                        "content": message.get("content", ""),
                        "tool_calls": raw_calls,
                        "finish_reason": "tool_calls",
                    }
                # No tool calls (normal response)
                else:
                    return {
                        "content": message.get("content", ""),
                        "tool_calls": [],
                        "finish_reason": "stop",
                    }

            except HTTPStatusError as e:
                if e.response.status_code == 413:
                    estimated_tokens = sum(len(m.get("content", "")) // 4 for m in msgs)
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
        raise last_413 or Exception("All payload fallbacks exhausted")

    async def embed(self, input: str) -> list[float]:
        return await asyncio.to_thread(embedding_model.embed, input)

    async def embed_batch(self, inputs: list[str]) -> list[list[float]]:
        return await asyncio.to_thread(embedding_model.embed_batch, inputs)

    async def close(self):
        await self._client.aclose()


llm_client = LLMClient()
