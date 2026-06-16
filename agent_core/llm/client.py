import json
import re

import openai
from openai import AsyncOpenAI
from opentelemetry import trace

from agent_core.config import agent_config
from shared.logger import logger

_tracer = trace.get_tracer("mimir.llm")


def _extract_tool_calls(content: str) -> list[dict]:
    """Parse raw Gemma 4 tool call tokens from content."""
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
        self._client = AsyncOpenAI(
            base_url=agent_config.llm_base_url,
            api_key=agent_config.api_key or "local",
        )

    async def complete(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        fallbacks: list[list[dict]] | None = None,
    ) -> dict:
        with _tracer.start_as_current_span("llm.complete") as span:
            span.set_attribute("llm.model", agent_config.llm_model)
            span.set_attribute("llm.tools_available", len(tools) if tools else 0)
            return await self._complete(
                span, messages, tools, temperature, max_tokens, fallbacks
            )

    async def _complete(
        self,
        span: trace.Span,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        fallbacks: list[list[dict]] | None = None,
    ) -> dict:
        candidates = [messages] + (fallbacks or [])
        last_413: openai.APIStatusError | None = None

        for attempt, msgs in enumerate(candidates):
            try:
                extra: dict = {}
                if tools:
                    extra["tools"] = tools
                    extra["tool_choice"] = "auto"

                result = await self._client.chat.completions.create(
                    model=agent_config.llm_model,
                    messages=msgs,
                    max_tokens=max_tokens or agent_config.llm_max_tokens,
                    temperature=temperature or agent_config.llm_temperature,
                    **extra,
                )

                if not result.choices:
                    return {
                        "content": '{"error": "No choices returned from LLM"}',
                        "tool_calls": [],
                        "finish_reason": "stop",
                    }

                usage = result.usage
                prompt_tokens = (usage.prompt_tokens if usage else None) or sum(
                    len(m.get("content") or "") // 4 for m in msgs
                )
                completion_tokens = usage.completion_tokens if usage else None
                total_tokens = (usage.total_tokens if usage else None) or (
                    prompt_tokens + (completion_tokens or 0)
                )
                logger.info(
                    "llm_tokens",
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    estimated=not bool(usage),
                )

                if attempt > 0:
                    span.set_attribute("llm.fallback_attempt", attempt)

                choice = result.choices[0]
                message = choice.message
                finish_reason = choice.finish_reason

                if tools and message.tool_calls:
                    tool_calls = [tc.model_dump() for tc in message.tool_calls]
                    span.set_attribute("llm.tool_calls_count", len(tool_calls))
                    return {
                        "content": message.content or "",
                        "tool_calls": tool_calls,
                        "finish_reason": "tool_calls",
                    }
                elif (
                    tools
                    and finish_reason == "stop"
                    and "<|tool_call>" in (message.content or "")
                ):
                    logger.warning(
                        "runtime_tool_parser_broken",
                        fallback="manual_extraction",
                        content_preview=(message.content or "")[:120],
                    )
                    raw_calls = _extract_tool_calls(message.content or "")
                    span.set_attribute("llm.tool_calls_count", len(raw_calls))
                    span.set_attribute("llm.tool_parser_fallback", True)
                    return {
                        "content": message.content or "",
                        "tool_calls": raw_calls,
                        "finish_reason": "tool_calls",
                    }
                else:
                    return {
                        "content": message.content or "",
                        "tool_calls": [],
                        "finish_reason": "stop",
                    }

            except openai.APIStatusError as e:
                if e.status_code == 413:
                    estimated_tokens = sum(len(m.get("content", "")) // 4 for m in msgs)
                    span.set_attribute("llm.payload_too_large", True)
                    span.set_attribute("llm.payload_token_estimate", estimated_tokens)
                    logger.warning(
                        "llm_payload_too_large",
                        attempt=attempt,
                        token_estimate=estimated_tokens,
                        fallbacks_remaining=len(candidates) - attempt - 1,
                    )
                    last_413 = e
                    continue
                span.set_status(trace.StatusCode.ERROR, str(e))
                logger.error(
                    "llm_complete_error",
                    error=str(e),
                    error_type=type(e).__name__,
                    status_code=e.status_code,
                    exc_info=True,
                )
                raise

            except Exception as e:
                span.set_status(trace.StatusCode.ERROR, str(e))
                logger.error(
                    "llm_complete_error",
                    error=str(e),
                    error_type=type(e).__name__,
                    exc_info=True,
                )
                raise

        span.set_status(trace.StatusCode.ERROR, "all payload fallbacks exhausted")
        logger.error(
            "llm_all_fallbacks_exhausted",
            attempts=len(candidates),
            last_error=str(last_413),
        )
        raise last_413 or Exception("All payload fallbacks exhausted")

    async def close(self):
        await self._client.close()


llm_client = LLMClient()
