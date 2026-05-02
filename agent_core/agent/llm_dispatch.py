from agent_core.agent.tools import tool_loop
from agent_core.config import agent_config
from agent_core.llm.client import llm_client
from agent_core.llm.messages import MessageBundle


async def run_llm(bundle: MessageBundle, tools: list[dict], triggered_by: str) -> str:
    """Dispatch to the tool loop if tools are available, otherwise direct LLM completion."""
    if tools:
        return await tool_loop.run_tool_loop(
            messages=bundle.primary,
            tools=tools,
            max_steps=agent_config.tool_max_steps,
            triggered_by=triggered_by,
        )

    response = await llm_client.complete(
        messages=bundle.primary,
        tools=None,
        fallbacks=bundle.fallbacks,
    )
    return response["content"]
