import json
import re
from collections.abc import Awaitable, Callable

import openai
from openai import AsyncOpenAI, NOT_GIVEN
from opentelemetry import trace

from agent_core.config import agent_config
from agent_core.llm.params import LLMParams
from shared.logger import logger

_tracer = trace.get_tracer("mimir.llm")

_EMPTY_USAGE: dict = {"prompt_tokens": 0, "completion_tokens": 0}


def _extract_tool_calls(content: str) -> list[dict]:
    """Parse raw Gemma 4 tool call tokens from content (fallback for non-native tool calling)."""
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


def extract_content(message) -> str:
    """Extract text content from a chat completion message.

    Guards against the mlx-vlm empty-content-when-thinking bug: when enable_thinking
    is active the server may return only a reasoning field with content absent entirely.
    """
    if message.content:
        return message.content
    extra = message.model_extra or {}
    reasoning = extra.get("reasoning") or extra.get("reasoning_content") or ""
    if reasoning:
        logger.warning(
            "llm_empty_content_fallback",
            fallback="reasoning_field",
            reasoning_preview=reasoning[:80],
        )
        return reasoning
    return ""


class LLMClient:
    def __init__(self) -> None:
        self._client = AsyncOpenAI(
            base_url=agent_config.llm_base_url,
            api_key=agent_config.api_key,
            timeout=120.0,
        )

    def _build_payload(
        self,
        messages: list[dict],
        params: LLMParams,
        tools: list[dict] | None = None,
    ) -> dict:
        kwargs: dict = {
            "model": params.model or agent_config.llm_model,
            "messages": messages,
            "max_tokens": params.max_tokens or agent_config.llm_max_tokens,
            "temperature": (
                params.temperature
                if params.temperature is not None
                else agent_config.llm_temperature
            ),
            "tools": tools or NOT_GIVEN,
            "tool_choice": "auto" if tools else NOT_GIVEN,
        }
        if params.top_p is not None:
            kwargs["top_p"] = params.top_p

        extra: dict = {
            # Always explicit — never rely on server default (empty-content-when-thinking bug)
            "enable_thinking": params.enable_thinking
            if params.enable_thinking is not None
            else False,
        }
        if params.min_p is not None:
            extra["min_p"] = params.min_p
        if params.repetition_penalty is not None:
            extra["repetition_penalty"] = params.repetition_penalty
        # thinking_budget intentionally omitted — no-op on mlx-vlm server path; use max_tokens instead

        kwargs["extra_body"] = extra
        return kwargs

    async def complete(
        self,
        messages: list[dict],
        params: LLMParams | None = None,
        tools: list[dict] | None = None,
        fallbacks: list[list[dict]] | None = None,
    ) -> dict:
        params = params or LLMParams()
        effective_model = params.model or agent_config.llm_model
        with _tracer.start_as_current_span("llm.complete") as span:
            span.set_attribute("llm.model", effective_model)
            span.set_attribute("llm.tools_available", len(tools) if tools else 0)
            return await self._complete(span, messages, params, tools, fallbacks)

    async def stream_complete(
        self,
        messages: list[dict],
        on_token: Callable[[str], Awaitable[None]],
        on_thinking_token: Callable[[str], Awaitable[None]] | None = None,
        on_tool_pending: Callable[[str, str], Awaitable[None]] | None = None,
        params: LLMParams | None = None,
        tools: list[dict] | None = None,
        fallbacks: list[list[dict]] | None = None,
    ) -> dict:
        """Stream an LLM response, calling on_token/on_thinking_token for each delta.

        Returns the same dict shape as complete() once the stream ends.
        Tool call deltas are accumulated silently and returned in tool_calls.
        """
        params = params or LLMParams()
        effective_model = params.model or agent_config.llm_model
        with _tracer.start_as_current_span("llm.stream_complete") as span:
            span.set_attribute("llm.model", effective_model)
            span.set_attribute("llm.streaming", True)
            span.set_attribute("llm.tools_available", len(tools) if tools else 0)
            candidates = [messages] + (fallbacks or [])
            last_err: openai.APIStatusError | None = None

            for attempt, msgs in enumerate(candidates):
                try:
                    kwargs = self._build_payload(msgs, params, tools)
                    result = await self._stream_request(
                        span, kwargs, on_token, on_thinking_token, on_tool_pending
                    )
                    if attempt > 0:
                        span.set_attribute("llm.fallback_attempt", attempt)
                    return result

                except openai.APIStatusError as e:
                    if e.status_code == 413:
                        span.set_attribute("llm.payload_too_large", True)
                        logger.warning(
                            "llm_stream_payload_too_large",
                            attempt=attempt,
                            fallbacks_remaining=len(candidates) - attempt - 1,
                        )
                        last_err = e
                        continue
                    span.set_status(trace.StatusCode.ERROR, str(e))
                    logger.error(
                        "llm_stream_error",
                        error=str(e),
                        error_type=type(e).__name__,
                        status_code=e.status_code,
                        exc_info=True,
                    )
                    raise
                except Exception as e:
                    span.set_status(trace.StatusCode.ERROR, str(e))
                    logger.error(
                        "llm_stream_error",
                        error=str(e),
                        error_type=type(e).__name__,
                        exc_info=True,
                    )
                    raise

            span.set_status(trace.StatusCode.ERROR, "all streaming fallbacks exhausted")
            raise last_err or Exception("All streaming fallbacks exhausted")

    async def _stream_request(
        self,
        span: trace.Span,
        kwargs: dict,
        on_token: Callable[[str], Awaitable[None]],
        on_thinking_token: Callable[[str], Awaitable[None]] | None,
        on_tool_pending: Callable[[str, str], Awaitable[None]] | None = None,
    ) -> dict:
        content_acc = ""
        thinking_acc = ""
        usage_chunk = None
        tool_calls_acc: dict[int, dict] = {}

        stream = await self._client.chat.completions.create(
            stream=True,
            stream_options={"include_usage": True},
            **kwargs,
        )
        async for chunk in stream:
            if not chunk.choices:
                if chunk.usage:
                    usage_chunk = chunk.usage
                continue

            delta = chunk.choices[0].delta

            for tc_delta in delta.tool_calls or []:
                idx: int = tc_delta.index or 0
                if idx not in tool_calls_acc:
                    call_id = tc_delta.id or ""
                    name = (tc_delta.function.name if tc_delta.function else None) or ""
                    tool_calls_acc[idx] = {
                        "id": call_id,
                        "function": {"name": name, "arguments": ""},
                    }
                    if on_tool_pending and name:
                        await on_tool_pending(name, call_id)
                if tc_delta.function and tc_delta.function.arguments:
                    tool_calls_acc[idx]["function"]["arguments"] += (
                        tc_delta.function.arguments
                    )

            # Thinking tokens — mlx-vlm extension; check both known field names defensively
            delta_extra = delta.model_extra or {}
            delta_thinking: str = (
                delta_extra.get("reasoning")
                or delta_extra.get("reasoning_content")
                or ""
            )
            delta_content: str = delta.content or ""

            if delta_thinking:
                thinking_acc += delta_thinking
                if on_thinking_token:
                    await on_thinking_token(delta_thinking)

            if delta_content:
                content_acc += delta_content
                await on_token(delta_content)

        tool_calls = [tool_calls_acc[i] for i in sorted(tool_calls_acc)]

        # Fallback: tool calls embedded as tokens in content (non-native tool calling)
        if not tool_calls and "<|tool_call>" in content_acc:
            logger.warning(
                "runtime_tool_parser_broken",
                fallback="manual_extraction_stream",
                content_preview=content_acc[:120],
            )
            tool_calls = _extract_tool_calls(content_acc)
            span.set_attribute("llm.tool_parser_fallback", True)

        finish_reason = "tool_calls" if tool_calls else "stop"

        usage_dict = {
            "prompt_tokens": (usage_chunk.prompt_tokens if usage_chunk else 0) or 0,
            "completion_tokens": (usage_chunk.completion_tokens if usage_chunk else 0)
            or len(content_acc) // 4,
        }

        span.set_attribute("llm.streamed_content_len", len(content_acc))
        span.set_attribute("llm.streamed_thinking_len", len(thinking_acc))
        span.set_attribute("llm.tool_calls_count", len(tool_calls))
        span.set_attribute("llm.finish_reason", finish_reason)
        logger.info(
            "llm_stream_tokens",
            prompt_tokens=usage_dict["prompt_tokens"],
            completion_tokens=usage_dict["completion_tokens"],
            estimated=usage_chunk is None,
        )

        return {
            "content": content_acc,
            "thinking": thinking_acc,
            "tool_calls": tool_calls,
            "finish_reason": finish_reason,
            "usage": usage_dict,
        }

    async def _complete(
        self,
        span: trace.Span,
        messages: list[dict],
        params: LLMParams,
        tools: list[dict] | None = None,
        fallbacks: list[list[dict]] | None = None,
    ) -> dict:
        candidates = [messages] + (fallbacks or [])
        last_413: openai.APIStatusError | None = None

        for attempt, msgs in enumerate(candidates):
            try:
                kwargs = self._build_payload(msgs, params, tools)
                result = await self._client.chat.completions.create(**kwargs)

                logger.debug("llm_response_content", content=result.model_dump())

                if not result.choices:
                    return {
                        "content": '{"error": "No choices returned from LLM"}',
                        "thinking": "",
                        "tool_calls": [],
                        "finish_reason": "stop",
                        "usage": _EMPTY_USAGE.copy(),
                    }

                usage = result.usage
                prompt_tokens = (usage.prompt_tokens if usage else None) or sum(
                    len(m.get("content") or "") // 4 for m in msgs
                )
                completion_tokens = (usage.completion_tokens if usage else None) or 0
                total_tokens = (usage.total_tokens if usage else None) or (
                    prompt_tokens + completion_tokens
                )
                logger.info(
                    "llm_tokens",
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    estimated=usage is None,
                )

                if attempt > 0:
                    span.set_attribute("llm.fallback_attempt", attempt)

                usage_dict = {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                }

                choice = result.choices[0]
                message = choice.message
                finish_reason = choice.finish_reason or "stop"
                extra = message.model_extra or {}
                thinking: str = (
                    extra.get("reasoning") or extra.get("reasoning_content") or ""
                )
                clean_content = extract_content(message)

                if tools and message.tool_calls:
                    tool_calls = [
                        {
                            "id": tc.id,
                            "type": tc.type,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in message.tool_calls
                    ]
                    span.set_attribute("llm.finish_reason", "tool_calls")
                    span.set_attribute("llm.tool_calls_count", len(tool_calls))
                    return {
                        "content": clean_content,
                        "thinking": thinking,
                        "tool_calls": tool_calls,
                        "finish_reason": "tool_calls",
                        "usage": usage_dict,
                    }
                elif (
                    tools
                    and finish_reason == "stop"
                    and "<|tool_call>" in clean_content
                ):
                    logger.warning(
                        "runtime_tool_parser_broken",
                        fallback="manual_extraction",
                        content_preview=clean_content[:120],
                    )
                    raw_calls = _extract_tool_calls(clean_content)
                    span.set_attribute("llm.finish_reason", "tool_calls")
                    span.set_attribute("llm.tool_calls_count", len(raw_calls))
                    span.set_attribute("llm.tool_parser_fallback", True)
                    return {
                        "content": clean_content,
                        "thinking": thinking,
                        "tool_calls": raw_calls,
                        "finish_reason": "tool_calls",
                        "usage": usage_dict,
                    }
                else:
                    span.set_attribute("llm.finish_reason", "stop")
                    return {
                        "content": clean_content,
                        "thinking": thinking,
                        "tool_calls": [],
                        "finish_reason": "stop",
                        "usage": usage_dict,
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

    async def close(self) -> None:
        await self._client.close()


llm_client = LLMClient()
