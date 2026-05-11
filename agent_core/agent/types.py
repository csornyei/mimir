from dataclasses import dataclass


@dataclass
class RunContext:
    """Execution context threaded through the agent dispatch chain."""

    triggered_by: str
    conversation_id: str | None = None


@dataclass
class AgentResult:
    """Final result returned by run_llm / run_tool_loop."""

    content: str
    thinking: str
    usage: dict
