from collections.abc import Awaitable, Callable

from agent_core.agent.tools import tool_loop
from agent_core.config import agent_config
from agent_core.llm.client import llm_client
from agent_core.llm.messages import MessageBundle

_EMPTY_USAGE: dict = {"prompt_tokens": 0, "completion_tokens": 0}


async def run_llm(
    bundle: MessageBundle,
    tools: list[dict],
    triggered_by: str,
    conversation_id: str | None = None,
    on_token: Callable[[str], Awaitable[None]] | None = None,
    on_thinking_token: Callable[[str], Awaitable[None]] | None = None,
    on_tool_call: Callable[[str, dict, dict], Awaitable[None]] | None = None,
    on_tool_start: Callable[[str, dict, str], Awaitable[None]] | None = None,
    on_tool_done: Callable[[str, str, str], Awaitable[None]] | None = None,
    on_approval_required: Callable[[str, str, dict], Awaitable[None]] | None = None,
    temperature: float | None = None,
    max_tokens: int | None = None,
    top_p: float | None = None,
    min_p: float | None = None,
    repetition_penalty: float | None = None,
    enable_thinking: bool | None = None,
    thinking_budget: int | None = None,
) -> tuple[str, str, dict]:
    """Dispatch to the tool loop if tools are available, otherwise direct LLM completion.

    Returns (content, thinking, usage).
    """
    if tools:
        return await tool_loop.run_tool_loop(
            messages=bundle.primary,
            tools=tools,
            max_steps=agent_config.tool_max_steps,
            triggered_by=triggered_by,
            conversation_id=conversation_id,
            on_token=on_token,
            on_thinking_token=on_thinking_token,
            on_tool_call=on_tool_call,
            on_tool_start=on_tool_start,
            on_tool_done=on_tool_done,
            on_approval_required=on_approval_required,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            min_p=min_p,
            repetition_penalty=repetition_penalty,
            enable_thinking=enable_thinking,
            thinking_budget=thinking_budget,
        )

    # No-tools path: use streaming when caller provides an on_token callback
    if on_token is not None:
        result = await llm_client.stream_complete(
            messages=bundle.primary,
            on_token=on_token,
            on_thinking_token=on_thinking_token,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            min_p=min_p,
            repetition_penalty=repetition_penalty,
            enable_thinking=enable_thinking,
            thinking_budget=thinking_budget,
            fallbacks=bundle.fallbacks,
        )
    else:
        result = await llm_client.complete(
            messages=bundle.primary,
            tools=None,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            min_p=min_p,
            repetition_penalty=repetition_penalty,
            enable_thinking=enable_thinking,
            thinking_budget=thinking_budget,
            fallbacks=bundle.fallbacks,
        )

    return (
        result["content"],
        result.get("thinking", ""),
        result.get("usage", _EMPTY_USAGE.copy()),
    )
