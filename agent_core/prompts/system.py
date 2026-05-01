from agent_core.prompts.loader import render


def render_tool_instructions(tools: list[dict] | None = None) -> str:
    if not tools:
        return render("tool_instructions_no_tools.j2")

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

    return render(
        "tool_instructions_with_tools.j2",
        read_tools=read_tools,
        write_tools=write_tools,
    )


def render_system_prompt(
    owner: str,
    datetime: str,
    semantic_memory: str,
    episodic_context: str,
    rag_context: str,
    context_window: int,
    tool_instructions: str,
) -> str:
    return render(
        "system_prompt.j2",
        owner=owner,
        datetime=datetime,
        semantic_memory=semantic_memory,
        episodic_context=episodic_context,
        rag_context=rag_context,
        context_window=context_window,
        tool_instructions=tool_instructions,
    )
