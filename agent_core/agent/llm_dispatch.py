from collections.abc import Awaitable, Callable

from agent_core.agent.events import AgentEvent, ResponseToken, ThinkingToken
from agent_core.agent.tools import tool_loop
from agent_core.agent.types import AgentResult, RunContext
from agent_core.config import agent_config
from agent_core.llm.client import llm_client
from agent_core.llm.messages import MessageBundle
from agent_core.llm.params import LLMParams

_EMPTY_USAGE: dict = {"prompt_tokens": 0, "completion_tokens": 0}


async def run_llm(
    bundle: MessageBundle,
    tools: list[dict],
    context: RunContext | None = None,
    params: LLMParams | None = None,
    on_event: Callable[[AgentEvent], Awaitable[None]] | None = None,
) -> AgentResult:
    """Dispatch to the tool loop if tools are available, otherwise direct LLM completion."""
    params = params or LLMParams()

    if tools:
        return await tool_loop.run_tool_loop(
            messages=bundle.primary,
            tools=tools,
            context=context,
            params=params,
            max_steps=agent_config.tool_max_steps,
            on_event=on_event,
        )

    # No-tools path: stream when caller provided an on_event callback
    if on_event is not None:

        async def _on_token(delta: str) -> None:
            await on_event(ResponseToken(content=delta))

        async def _on_thinking_token(delta: str) -> None:
            await on_event(ThinkingToken(content=delta))

        result = await llm_client.stream_complete(
            messages=bundle.primary,
            on_token=_on_token,
            on_thinking_token=_on_thinking_token,
            params=params,
            fallbacks=bundle.fallbacks,
        )
    else:
        result = await llm_client.complete(
            messages=bundle.primary,
            params=params,
            fallbacks=bundle.fallbacks,
        )

    return AgentResult(
        content=result["content"],
        thinking=result.get("thinking", ""),
        usage=result.get("usage", _EMPTY_USAGE.copy()),
    )
