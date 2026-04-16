from mimir.agent.tools import tool_dispatcher
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
    tool_name = payload.get("tool_name", "unknown")
    args = payload.get("arguments", {})
    result = await tool_dispatcher.dispatch(tool_name, args)
    return str(result)
