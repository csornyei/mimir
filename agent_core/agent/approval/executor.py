from opentelemetry import trace
from opentelemetry.trace import StatusCode

from agent_core.agent.dispatcher import tool_dispatcher
from shared.models import PendingActionModel
from shared.logger import logger

_tracer = trace.get_tracer("mimir.agent.approval.executor")


async def execute(action: PendingActionModel) -> str:
    """Execute an approved action. Raises on failure — caller must catch and notify user."""
    with _tracer.start_as_current_span("approval.execute") as span:
        span.set_attribute("approval.action_id", str(action.id))
        tool_name = action.payload.get("tool_name", "unknown")
        span.set_attribute("approval.tool_name", tool_name)
        try:
            logger.debug(
                "approval_execution_started",
                action_id=str(action.id),
                status=str(action.status),
            )
            result = await _execute_tool_call(action.payload, action.id)
            span.set_attribute("approval.outcome", "executed")
            return result
        except Exception as exc:
            logger.error(
                "approval_execution_failed",
                action_id=str(action.id),
                tool_name=tool_name,
                error=str(exc),
                error_type=type(exc).__name__,
                exc_info=True,
            )
            span.set_status(StatusCode.ERROR, str(exc))
            span.set_attribute("approval.outcome", "failed")
            raise


async def _execute_tool_call(payload: dict, action_id) -> str:
    tool_name = payload.get("tool_name", "unknown")
    args = payload.get("arguments", {})
    dispatch_args = {**args, "action_id": str(action_id)}
    result = await tool_dispatcher.dispatch(tool_name, dispatch_args)
    return str(result)
