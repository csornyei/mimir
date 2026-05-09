from dataclasses import dataclass

from opentelemetry import trace
from sqlalchemy.ext.asyncio import AsyncSession

from agent_core.agent.context import ChatContext
from agent_core.config import AgentConfig
from agent_core.llm.prompt import build_system_prompt, token_estimate
from shared.logger import logger

_tracer = trace.get_tracer("mimir.llm.messages")


def calculate_window_size(system_tokens: int, config: AgentConfig) -> int:
    """Compute conversation history window size from remaining token budget."""
    budget = config.llm_context_window - config.llm_max_tokens - 256 - system_tokens
    n = budget // 200
    return max(config.conversation_window_min, min(config.conversation_window_max, n))


@dataclass
class MessageBundle:
    primary: list[dict]
    fallbacks: list[list[dict]]


async def build_messages(
    context: ChatContext,
    conversation_id: str,
    db: AsyncSession,
    config: AgentConfig,
) -> MessageBundle:
    """Build the full message list and degraded fallbacks for 413 recovery."""
    from agent_core.agent.conversation import conversation_manager

    with _tracer.start_as_current_span("chat.prompt_assembly") as span:
        system_prompt = build_system_prompt(
            owner=config.owner_name,
            semantic_memory=context.semantic_memory,
            episodic_context=context.episodic_context,
            rag_context=context.rag_context,
            context_window=config.llm_context_window,
            tools=context.tools,
        )

        system_tokens = token_estimate(system_prompt)
        n = calculate_window_size(system_tokens, config)
        if n < config.conversation_window_max:
            logger.warning(
                "conversation_window_reduced", n=n, system_tokens=system_tokens
            )

        conversation_messages = await conversation_manager.window(
            db, conversation_id, n
        )

        span.set_attribute("prompt.system_tokens", system_tokens)
        span.set_attribute("prompt.window_size", n)

        system_prompt_reduced = build_system_prompt(
            owner=config.owner_name,
            semantic_memory=context.semantic_memory,
            context_window=config.llm_context_window,
            tools=context.tools,
        )
        system_prompt_minimal = build_system_prompt(
            owner=config.owner_name,
            semantic_memory="",
            context_window=config.llm_context_window,
            tools=context.tools,
        )

        primary = [{"role": "system", "content": system_prompt}] + conversation_messages
        fallback_reduced = [
            {"role": "system", "content": system_prompt_reduced}
        ] + conversation_messages[-5:]
        fallback_minimal = [
            {"role": "system", "content": system_prompt_minimal}
        ] + conversation_messages[-config.conversation_window_min :]

        return MessageBundle(
            primary=primary, fallbacks=[fallback_reduced, fallback_minimal]
        )
