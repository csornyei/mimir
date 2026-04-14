from mimir.models import PendingActionModel
from mimir.logger import logger


async def execute(action: PendingActionModel) -> str:
    """Execute an approved action. Raises on failure — caller must catch and notify user."""
    try:
        result = await _execute_tool_call(action.payload)
        return result
    except Exception as exc:
        logger.error(
            "approval_execution_failed",
            action_id=str(action.id),
            error=str(exc),
        )
        raise


async def _execute_tool_call(payload: dict) -> str:
    """Stub — wire to MCP dispatcher when tools are implemented."""
    tool_name = payload.get("tool_name", "unknown")
    args = payload.get("arguments", {})
    logger.warning("tool_call_stub_executed", tool_name=tool_name, args=args)
    return f"[stub] `{tool_name}` would have been called with: {args}"
