import json
import re
from collections.abc import Awaitable, Callable

from httpx import AsyncClient, HTTPStatusError
from opentelemetry import trace

from agent_core.config import agent_config
from shared.logger import logger

_tracer = trace.get_tracer("mimir.llm")

_THINK_OPEN = "<|channel>thought"
_THINK_CLOSE = "<channel|>"
# Longest tag we need to buffer against chunk boundaries
_MAX_TAG_LEN = max(len(_THINK_OPEN), len(_THINK_CLOSE))

_EMPTY_USAGE: dict = {"prompt_tokens": 0, "completion_tokens": 0}


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


def _split_thinking(content: str) -> tuple[str, str]:
    """Split <think>…</think> block from response content.

    Returns (thinking_content, clean_content).
    """
    start = content.find(_THINK_OPEN)
    if start == -1:
        return "", content
    end = content.find(_THINK_CLOSE, start + len(_THINK_OPEN))
    if end == -1:
        # Unclosed tag — treat everything after <think> as thinking
        thinking = content[start + len(_THINK_OPEN) :].strip()
        clean = content[:start].strip()
        return thinking, clean
    thinking = content[start + len(_THINK_OPEN) : end].strip()
    clean = (content[:start] + content[end + len(_THINK_CLOSE) :]).strip()
    return thinking, clean


class LLMClient:
    def __init__(self) -> None:
        headers = {
            "Content-Type": "application/json",
        }

        if agent_config.api_key:
            headers["Authorization"] = f"Bearer {agent_config.api_key}"

        self._client = AsyncClient(
            base_url=agent_config.llm_base_url, headers=headers, timeout=120.0
        )

    def _build_payload(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        top_p: float | None = None,
        min_p: float | None = None,
        repetition_penalty: float | None = None,
        enable_thinking: bool | None = None,
        thinking_budget: int | None = None,
    ) -> dict:
        payload: dict = {
            "model": agent_config.llm_model,
            "messages": messages,
            "max_tokens": max_tokens or agent_config.llm_max_tokens,
            "temperature": temperature or agent_config.llm_temperature,
        }
        if top_p is not None:
            payload["top_p"] = top_p
        if min_p is not None:
            payload["min_p"] = min_p
        if repetition_penalty is not None:
            payload["repetition_penalty"] = repetition_penalty
        if enable_thinking is not None:
            payload["enable_thinking"] = enable_thinking
            payload["thinking_start_token"] = "<|channel>thought"
            payload["thinking_end_token"] = "<channel|>"
        if thinking_budget is not None:
            payload["thinking_budget"] = thinking_budget
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        return payload

    async def complete(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        top_p: float | None = None,
        min_p: float | None = None,
        repetition_penalty: float | None = None,
        enable_thinking: bool | None = None,
        thinking_budget: int | None = None,
        fallbacks: list[list[dict]] | None = None,
    ) -> dict:
        with _tracer.start_as_current_span("llm.complete") as span:
            span.set_attribute("llm.model", agent_config.llm_model)
            span.set_attribute("llm.tools_available", len(tools) if tools else 0)
            return await self._complete(
                span,
                messages,
                tools,
                temperature,
                max_tokens,
                top_p,
                min_p,
                repetition_penalty,
                enable_thinking,
                thinking_budget,
                fallbacks,
            )

    async def stream_complete(
        self,
        messages: list[dict],
        on_token: Callable[[str], Awaitable[None]],
        on_thinking_token: Callable[[str], Awaitable[None]] | None = None,
        tools: list[dict] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        top_p: float | None = None,
        min_p: float | None = None,
        repetition_penalty: float | None = None,
        enable_thinking: bool | None = None,
        thinking_budget: int | None = None,
        fallbacks: list[list[dict]] | None = None,
    ) -> dict:
        """Stream an LLM response, calling on_token/on_thinking_token for each delta.

        Returns the same dict shape as complete() once the stream ends.
        Tool call deltas are accumulated silently and returned in tool_calls.
        """
        with _tracer.start_as_current_span("llm.stream_complete") as span:
            span.set_attribute("llm.model", agent_config.llm_model)
            span.set_attribute("llm.streaming", True)
            span.set_attribute("llm.tools_available", len(tools) if tools else 0)
            candidates = [messages] + (fallbacks or [])
            last_err: HTTPStatusError | None = None

            for attempt, msgs in enumerate(candidates):
                try:
                    payload = self._build_payload(
                        msgs,
                        tools=tools,
                        temperature=temperature,
                        max_tokens=max_tokens,
                        top_p=top_p,
                        min_p=min_p,
                        repetition_penalty=repetition_penalty,
                        enable_thinking=enable_thinking,
                        thinking_budget=thinking_budget,
                    )
                    payload["stream"] = True

                    result = await self._stream_request(
                        span, payload, on_token, on_thinking_token
                    )
                    if attempt > 0:
                        span.set_attribute("llm.fallback_attempt", attempt)
                    return result

                except HTTPStatusError as e:
                    if e.response.status_code == 413:
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
                        status_code=e.response.status_code,
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
        payload: dict,
        on_token: Callable[[str], Awaitable[None]],
        on_thinking_token: Callable[[str], Awaitable[None]] | None,
    ) -> dict:
        """Execute one SSE streaming request and return the accumulated result."""
        in_think = False
        content_acc = ""
        thinking_acc = ""
        pending = ""  # lookahead buffer for tag-boundary chunks
        usage_chunk: dict | None = None
        # tool call accumulator: delta index → partial call dict
        tool_calls_acc: dict[int, dict] = {}

        async with self._client.stream(
            "POST", "/v1/chat/completions", json=payload
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue

                if chunk.get("usage"):
                    usage_chunk = chunk["usage"]

                choices = chunk.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta", {})

                # Accumulate tool call deltas silently (no streaming to client)
                for tc_delta in delta.get("tool_calls") or []:
                    idx: int = tc_delta.get("index", 0)
                    if idx not in tool_calls_acc:
                        tool_calls_acc[idx] = {
                            "id": tc_delta.get("id", ""),
                            "function": {
                                "name": tc_delta.get("function", {}).get("name", ""),
                                "arguments": "",
                            },
                        }
                    tool_calls_acc[idx]["function"]["arguments"] += tc_delta.get(
                        "function", {}
                    ).get("arguments", "")

                delta_content: str = delta.get("content") or ""
                if not delta_content:
                    continue

                pending += delta_content
                (
                    pending,
                    in_think,
                    content_acc,
                    thinking_acc,
                ) = await self._process_pending(
                    pending,
                    in_think,
                    content_acc,
                    thinking_acc,
                    on_token,
                    on_thinking_token,
                    partial=True,
                )

        # Flush remaining content buffer
        if pending:
            _, _in_think, content_acc, thinking_acc = await self._process_pending(
                pending,
                in_think,
                content_acc,
                thinking_acc,
                on_token,
                on_thinking_token,
                partial=False,
            )

        tool_calls = [tool_calls_acc[i] for i in sorted(tool_calls_acc)]

        # Gemma 4 fallback: tool calls embedded as tokens in content
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
            "prompt_tokens": (usage_chunk or {}).get("prompt_tokens", 0),
            "completion_tokens": (usage_chunk or {}).get("completion_tokens", 0)
            or len(content_acc) // 4,
        }

        span.set_attribute("llm.streamed_content_len", len(content_acc))
        span.set_attribute("llm.streamed_thinking_len", len(thinking_acc))
        span.set_attribute("llm.tool_calls_count", len(tool_calls))
        span.set_attribute("llm.finish_reason", finish_reason)
        span.set_attribute("llm.prompt_tokens", usage_dict["prompt_tokens"])
        span.set_attribute("llm.completion_tokens", usage_dict["completion_tokens"])
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

    async def _process_pending(
        self,
        pending: str,
        in_think: bool,
        content_acc: str,
        thinking_acc: str,
        on_token: Callable[[str], Awaitable[None]],
        on_thinking_token: Callable[[str], Awaitable[None]] | None,
        *,
        partial: bool,
    ) -> tuple[str, bool, str, str]:
        """Route buffered content to the appropriate callback.

        Returns (remaining_pending, in_think, content_acc, thinking_acc).
        """
        while pending:
            if in_think:
                idx = pending.find(_THINK_CLOSE)
                if idx != -1:
                    before = pending[:idx]
                    if before:
                        thinking_acc += before
                        if on_thinking_token:
                            await on_thinking_token(before)
                    in_think = False
                    pending = pending[idx + len(_THINK_CLOSE) :]
                else:
                    safe = len(pending) - _MAX_TAG_LEN if partial else len(pending)
                    if safe > 0:
                        flush = pending[:safe]
                        thinking_acc += flush
                        if on_thinking_token:
                            await on_thinking_token(flush)
                        pending = pending[safe:]
                    break
            else:
                idx = pending.find(_THINK_OPEN)
                if idx != -1:
                    before = pending[:idx]
                    if before:
                        content_acc += before
                        await on_token(before)
                    in_think = True
                    pending = pending[idx + len(_THINK_OPEN) :]
                else:
                    safe = len(pending) - _MAX_TAG_LEN if partial else len(pending)
                    if safe > 0:
                        flush = pending[:safe]
                        content_acc += flush
                        await on_token(flush)
                        pending = pending[safe:]
                    break

        return pending, in_think, content_acc, thinking_acc

    async def _complete(
        self,
        span: trace.Span,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
        top_p: float | None = None,
        min_p: float | None = None,
        repetition_penalty: float | None = None,
        enable_thinking: bool | None = None,
        thinking_budget: int | None = None,
        fallbacks: list[list[dict]] | None = None,
    ) -> dict:
        candidates = [messages] + (fallbacks or [])
        last_413: HTTPStatusError | None = None

        for attempt, msgs in enumerate(candidates):
            try:
                payload = self._build_payload(
                    msgs,
                    tools=tools,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p,
                    min_p=min_p,
                    repetition_penalty=repetition_penalty,
                    enable_thinking=enable_thinking,
                    thinking_budget=thinking_budget,
                )

                response = await self._client.post("/v1/chat/completions", json=payload)
                response.raise_for_status()
                result = response.json()

                logger.debug("llm_response_content", content=result)

                if "choices" not in result or len(result["choices"]) == 0:
                    return {
                        "content": '{"error": "No choices returned from LLM"}',
                        "thinking": "",
                        "tool_calls": [],
                        "finish_reason": "stop",
                        "usage": _EMPTY_USAGE.copy(),
                    }

                usage = result.get("usage") or {}
                prompt_tokens = usage.get("prompt_tokens") or sum(
                    len(m.get("content") or "") // 4 for m in msgs
                )
                completion_tokens = usage.get("completion_tokens") or 0
                total_tokens = usage.get("total_tokens") or (
                    prompt_tokens + completion_tokens
                )
                logger.info(
                    "llm_tokens",
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=total_tokens,
                    estimated=not bool(usage),
                )

                span.set_attribute("llm.prompt_tokens", prompt_tokens)
                span.set_attribute("llm.completion_tokens", completion_tokens)
                span.set_attribute("llm.total_tokens", total_tokens)
                span.set_attribute("llm.tokens_estimated", not bool(usage))
                if attempt > 0:
                    span.set_attribute("llm.fallback_attempt", attempt)

                usage_dict = {
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                }

                choice = result["choices"][0]
                message = choice.get("message", {})
                finish_reason = choice.get("finish_reason", "stop")
                raw_content: str = message.get("content", "")
                thinking, clean_content = _split_thinking(raw_content)

                if tools and message.get("tool_calls"):
                    tool_calls = message.get("tool_calls", [])
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
                    tools and finish_reason == "stop" and "<|tool_call>" in raw_content
                ):
                    logger.warning(
                        "runtime_tool_parser_broken",
                        fallback="manual_extraction",
                        content_preview=raw_content[:120],
                    )
                    raw_calls = _extract_tool_calls(raw_content)
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

            except HTTPStatusError as e:
                if e.response.status_code == 413:
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
                    status_code=e.response.status_code,
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
        await self._client.aclose()


llm_client = LLMClient()
