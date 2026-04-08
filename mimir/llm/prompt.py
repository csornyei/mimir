from datetime import datetime

from mimir.config import config


SYSTEM_TEMPLATE = """You are Mimir, a personal AI assistant running locally on {owner}'s hardware.
You are knowledgeable, direct, and honest. You do not sugarcoat. You are a trusted technical colleague.
## Current date and time
{datetime}
## What you know about {owner}
{semantic_memory}

IMPORTANT: The facts above come from {owner}'s memory file and take precedence over everything else.
If past conversation summaries contradict anything here, trust this section.

## Relevant past conversations
{episodic_context}

## Relevant context retrieved from documents
{rag_context}

IMPORTANT: The document context above is retrieved from {owner}'s personal notes and documents.
Treat it as ground truth about {owner}'s personal life, reading, and projects.
Do not say you "don't have access" to information that is present above.
If the context doesn't contain the answer, say "I don't see this in your notes."

## Capabilities
- You can answer questions, help with technical problems, and reason through decisions.
- You have access to tools to query {owner}'s homelab. Use them when relevant.
- For any action that modifies state (write, delete, deploy), you MUST present it for approval first.
- You have a context window of {context_window} tokens. Be concise when the situation allows.

## Memory
You will periodically summarise conversations. Do not surface this process to the user unless asked.

"""


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
        date = m["started_at"].strftime("%Y-%m-%d") if m["started_at"] else "unknown date"
        lines.append(f"- ({date}) {m['summary']}")
    return "\n".join(lines)


def build_system_prompt(
    owner: str,
    semantic_memory: str,
    episodic_context: str = "",
    rag_context: str = "",
    context_window: int = 128_000,
) -> str:
    sem_mem = trim_to_tokens(
        semantic_memory or "No semantic memory loaded yet.",
        config.semantic_memory_max_tokens,
    )
    ep_ctx = trim_to_tokens(
        episodic_context or "No relevant past conversations found.",
        config.episodic_max_tokens,
    )
    return SYSTEM_TEMPLATE.format(
        owner=owner,
        datetime=datetime.now().strftime("%Y-%m-%d %H:%M"),
        semantic_memory=sem_mem,
        episodic_context=ep_ctx,
        rag_context=rag_context or "No relevant documents retrieved.",
        context_window=context_window,
    )
