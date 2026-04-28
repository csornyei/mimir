import functools
import inspect
from uuid import UUID

from mcp.types import ToolAnnotations
from opentelemetry import trace
from sqlalchemy import select

from shared.db import get_session
from shared.logger import logger
from shared.models import ActionStatus, PendingActionModel
from mcp_server.app import mcp

_tracer = trace.get_tracer("mimir.mcp")


def traced_tool(func):
    """Register an MCP tool with automatic tracing."""

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        with _tracer.start_as_current_span(f"mcp.tool.{func.__name__}") as span:
            span.set_attribute("mcp.tool.name", func.__name__)
            try:
                result = await func(*args, **kwargs)
                if isinstance(result, dict) and result.get("error"):
                    span.set_status(trace.StatusCode.ERROR, result["error"])
                return result
            except Exception as e:
                span.set_status(trace.StatusCode.ERROR, str(e))
                raise

    return mcp.tool()(wrapper)


def write_tool(func):
    """Register an MCP tool that requires user approval before execution.

    Replaces @mcp.tool() + @require_approval. Sets destructiveHint=True so the
    agent can detect write tools from the schema without any config.
    """
    sig = inspect.signature(func)
    action_id_param = inspect.Parameter(
        "action_id",
        kind=inspect.Parameter.KEYWORD_ONLY,
        annotation=str,
    )
    new_sig = sig.replace(parameters=list(sig.parameters.values()) + [action_id_param])

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        with _tracer.start_as_current_span(f"mcp.tool.{func.__name__}") as span:
            span.set_attribute("mcp.tool.name", func.__name__)

            if "action_id" not in kwargs:
                logger.error("write_tool_missing_action_id", tool_name=func.__name__)
                result = {"error": "Missing required parameter: action_id"}
                span.set_status(trace.StatusCode.ERROR, result["error"])
                return result

            action_id = kwargs.pop("action_id")
            span.set_attribute("approval.action_id", action_id)
            logger.debug(
                "write_tool_called",
                tool_name=func.__name__,
                args=args,
                kwargs=kwargs,
                action_id=action_id,
            )

            try:
                action_uuid = UUID(action_id)
            except ValueError:
                logger.error("write_tool_invalid_action_id", action_id=action_id)
                result = {"error": f"Invalid action_id format: {action_id}"}
                span.set_status(trace.StatusCode.ERROR, result["error"])
                return result

            async with get_session() as session:
                logger.debug(
                    "write_tool: querying for approved action", action_id=action_id
                )
                query_result = await session.scalars(
                    select(PendingActionModel)
                    .where(
                        PendingActionModel.id == action_uuid,
                        PendingActionModel.status == ActionStatus.approved,
                    )
                    .with_for_update()
                )
                action = query_result.first()

                logger.debug(
                    "write_tool: action query result",
                    action_id=action_id,
                    action_found=action is not None,
                )

                if action is None:
                    logger.warning(
                        "write_tool_no_approved_action",
                        action_id=action_id,
                        tool_name=func.__name__,
                    )
                    result = {"error": f"No approved action found with id {action_id}."}
                    span.set_status(trace.StatusCode.ERROR, result["error"])
                    return result

                try:
                    tool_result = await func(*args, **kwargs)
                    logger.debug(
                        "write_tool_execution_succeeded",
                        action_id=action_id,
                        tool_name=func.__name__,
                    )
                    if isinstance(tool_result, dict) and tool_result.get("error"):
                        span.set_status(trace.StatusCode.ERROR, tool_result["error"])
                except Exception as e:
                    logger.error(
                        "write_tool_execution_failed",
                        action_id=action_id,
                        tool_name=func.__name__,
                        error=str(e),
                        error_type=type(e).__name__,
                        exc_info=True,
                    )
                    span.set_status(trace.StatusCode.ERROR, str(e))
                    return {"error": f"Tool execution failed: {e}"}
                finally:
                    await session.commit()

            return tool_result

    wrapper.__signature__ = new_sig  # ty: ignore
    return mcp.tool(annotations=ToolAnnotations(destructiveHint=True))(wrapper)
