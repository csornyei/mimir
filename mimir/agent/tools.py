import asyncio
import json
from typing import Any

from mimir.agent.mcp_client import call_tool
from mimir.config import config
from mimir.logger import logger
from mimir.llm.client import llm_client


class ToolDispatcher:
    """Dispatch tool calls to the MCP server and handle responses."""

    async def dispatch(self, tool_name: str, args: dict[str, Any]) -> dict[str, Any]:
        try:
            logger.info("dispatching_tool", tool_name=tool_name, args=args)
            result = await call_tool(tool_name, args)
            logger.info("tool_executed", tool_name=tool_name, result=result)
            return result

        except asyncio.TimeoutError:
            error_msg = (
                f"Tool {tool_name} timed out after {config.tool_call_timeout_seconds}s"
            )
            logger.error("tool_timeout", tool_name=tool_name)
            return {"error": error_msg}

        except Exception as e:
            error_msg = f"Tool execution failed: {str(e)}"
            logger.error("tool_execution_error", tool_name=tool_name, error=str(e))
            return {"error": error_msg}

    async def run_tool_loop(
        self,
        messages: list[dict],
        tools: list[dict],
        max_steps: int | None = None,
    ) -> str:
        """Run the agentic tool loop: call LLM, dispatch tools, repeat.

        Args:
            messages: Conversation history (system + user messages)
            tools: Available tool schemas (OpenAI format)
            max_steps: Max iterations (default from config)

        Returns:
            Final text response from the model
        """
        max_steps = max_steps or config.tool_max_steps
        messages = messages.copy()  # Don't mutate caller's list

        for step in range(max_steps):
            logger.info("tool_loop_step", step=step + 1, max_steps=max_steps)

            # Call LLM with tools
            response = await llm_client.complete(
                messages=messages,
                tools=tools,
            )

            # Extract message components from response dict
            finish_reason = response.get("finish_reason", "stop")
            content = response.get("content", "")
            tool_calls = response.get("tool_calls", [])

            # Add assistant's response to messages
            assistant_msg = {
                "role": "assistant",
                "content": content,
            }
            if tool_calls:
                assistant_msg["tool_calls"] = tool_calls
            messages.append(assistant_msg)

            # No tool calls, return final response
            if not tool_calls or finish_reason == "stop":
                logger.info("tool_loop_final_response", step=step + 1)
                return content

            # Execute all tool calls in this step
            tool_results = []
            for tc in tool_calls:
                tool_name = tc.get("function", {}).get("name") or tc.get("name")
                args_str = tc.get("function", {}).get("arguments") or tc.get(
                    "arguments", "{}"
                )

                # Parse arguments
                try:
                    if isinstance(args_str, str):
                        args = json.loads(args_str)
                    else:
                        args = args_str
                except json.JSONDecodeError:
                    args = {}

                # Dispatch tool
                result = await self.dispatch(tool_name, args)

                # Add result to messages
                tool_results.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.get("id", ""),
                        "name": tool_name,
                        "content": json.dumps(result),
                    }
                )

            # Add all tool results to messages
            messages.extend(tool_results)

        # Exceeded max steps
        logger.warning("tool_loop_max_steps_exceeded", max_steps=max_steps)
        return (
            "I reached the maximum number of tool steps. "
            "Please try a more specific request."
        )

    async def close(self):
        pass  # No persistent resources to clean up


# Global dispatcher instance
tool_dispatcher = ToolDispatcher()
