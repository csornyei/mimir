from mimir.models import ActionType, PendingActionModel
from mimir.logger import logger


async def execute(action: PendingActionModel) -> str:
    """Execute an approved action. Raises on failure — caller must catch and notify user."""
    try:
        match action.action_type:
            case ActionType.tool_call:
                return await _execute_tool_call(action.payload)
            case ActionType.memory_write:
                return await _execute_memory_write(action.payload)
            case _:
                raise ValueError(f"Unknown action_type: {action.action_type!r}")
    except Exception as exc:
        logger.error(
            "approval_execution_failed",
            action_id=str(action.id),
            action_type=action.action_type,
            error=str(exc),
        )
        raise


async def _execute_tool_call(payload: dict) -> str:
    """Stub — wire to MCP dispatcher when tools are implemented."""
    tool_name = payload.get("tool_name", "unknown")
    args = payload.get("arguments", {})
    logger.warning("tool_call_stub_executed", tool_name=tool_name, args=args)
    return f"[stub] `{tool_name}` would have been called with: {args}"


async def _execute_memory_write(payload: dict) -> str:
    from mimir.memory.semantic import SemanticMemory

    operation = payload.get("operation")
    content = payload.get("content", "")
    if operation == "append":
        SemanticMemory().append_fact(content)
        return "Memory updated — appended to `memory.md`."
    elif operation == "overwrite":
        raise NotImplementedError("memory_write overwrite is not yet implemented")
    else:
        raise ValueError(f"Unknown memory_write operation: {operation!r}")
