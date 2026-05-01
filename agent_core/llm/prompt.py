from datetime import datetime

from agent_core.config import agent_config
from agent_core.prompts import render_system_prompt, render_tool_instructions


def token_estimate(text: str) -> int:
    """Rough token count: 1 token ≈ 4 characters. Model-agnostic."""
    return len(text) // 4


def trim_to_tokens(text: str, max_tokens: int) -> str:
    """
    Truncate *text* so it fits within *max_tokens*.
    Cuts at a word boundary (no mid-word splits) and appends '[... truncated]'.
    Returns the original string unchanged if it already fits.
    """
    if max_tokens <= 0:
        return "[... truncated]"
    if token_estimate(text) <= max_tokens:
        return text
    max_chars = max_tokens * 4
    truncated = text[:max_chars]
    last_space = truncated.rfind(" ")
    if last_space > 0:
        truncated = truncated[:last_space]
    return truncated + " [... truncated]"


def format_episodic_context(memories: list[dict]) -> str:
    if not memories:
        return "No relevant past conversations found."
    lines = []
    for m in memories:
        date = (
            m["started_at"].strftime("%Y-%m-%d") if m["started_at"] else "unknown date"
        )
        lines.append(f"- ({date}) {m['summary']}")
    return "\n".join(lines)


def build_tool_instructions(tools: list[dict] | None = None) -> str:
    return render_tool_instructions(tools)


def build_system_prompt(
    owner: str,
    semantic_memory: str,
    episodic_context: str = "",
    rag_context: str = "",
    context_window: int = 128_000,
    tools: list[dict] | None = None,
) -> str:
    sem_mem = trim_to_tokens(
        semantic_memory or "No semantic memory loaded yet.",
        agent_config.semantic_memory_max_tokens,
    )
    ep_ctx = trim_to_tokens(
        episodic_context or "No relevant past conversations found.",
        agent_config.episodic_max_tokens,
    )
    tool_instructions = render_tool_instructions(tools)

    return render_system_prompt(
        owner=owner,
        datetime=datetime.now().strftime("%Y-%m-%d %H:%M"),
        semantic_memory=sem_mem,
        episodic_context=ep_ctx,
        rag_context=rag_context or "No relevant documents retrieved.",
        context_window=context_window,
        tool_instructions=tool_instructions,
    )
