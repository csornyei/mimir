from datetime import datetime

from mimir.agent.config import agent_config


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
- For any action that modifies state (write, delete, deploy), call the tool directly — the system handles approval automatically.
- You have a context window of {context_window} tokens. Be concise when the situation allows.

{tool_instructions}

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
        date = (
            m["started_at"].strftime("%Y-%m-%d") if m["started_at"] else "unknown date"
        )
        lines.append(f"- ({date}) {m['summary']}")
    return "\n".join(lines)


def build_tool_instructions(tools: list[dict] | None = None) -> str:
    """Build tool use instructions based on available tools.

    Args:
        tools: List of OpenAI-format tool schemas, or None if no tools available

    Returns:
        Formatted tool instruction block for system prompt
    """
    if not tools:
        return """## Tool Capabilities

You currently have no tools available for this conversation. Answer based on your knowledge and memory only.
Do not make up tool results. If you don't have the data, say so."""

    read_tools = []
    write_tools = []
    for tool in tools:
        if "function" in tool:
            name = tool["function"]["name"]
        elif "name" in tool:
            name = tool["name"]
        else:
            continue
        if tool.get("destructive", False):
            write_tools.append(name)
        else:
            read_tools.append(name)

    sections = []
    if read_tools:
        sections.append(f"Read tools: {', '.join(sorted(read_tools))}")
    if write_tools:
        sections.append(
            f"Write tools (require approval): {', '.join(sorted(write_tools))}"
        )
    tools_list = "\n".join(sections)

    write_note = (
        "\n- Write tools trigger an automatic approval flow — call them directly and the system will pause for user confirmation."
        if write_tools
        else ""
    )

    return f"""## Tool Capabilities

You have access to the following tools:
{tools_list}

- Always call the most relevant tool before answering questions.
- If a tool returns an error, acknowledge it clearly and try an alternative approach.
- Do not make up tool results. If you don't have the data, say so.
- Call all necessary tools before giving your final answer.{write_note}"""


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
    tool_instructions = build_tool_instructions(tools)

    return SYSTEM_TEMPLATE.format(
        owner=owner,
        datetime=datetime.now().strftime("%Y-%m-%d %H:%M"),
        semantic_memory=sem_mem,
        episodic_context=ep_ctx,
        rag_context=rag_context or "No relevant documents retrieved.",
        context_window=context_window,
        tool_instructions=tool_instructions,
    )
