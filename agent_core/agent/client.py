import httpx

from agent_core.config import agent_config
from shared.logger import logger
from shared.schemas import ChatRequest, ChatResponse


async def send_to_agent(
    *,
    conversation_id: str,
    user_id: str,
    message: str,
) -> str:
    """POST to /api/chat and return the response text."""
    async with httpx.AsyncClient(timeout=120) as client:
        payload = ChatRequest(
            conversation_id=conversation_id,
            message=message,
            user_id=user_id,
        )

        logger.debug(
            "sending_to_agent",
            conversation_id=conversation_id,
            user_id=user_id,
        )

        try:
            response = await client.post(
                f"{agent_config.agent_url}/api/chat",
                json=payload.model_dump(),
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as e:
            logger.error(
                "agent_returned_error",
                status_code=e.response.status_code,
                conversation_id=conversation_id,
                response=e.response.text,
            )
            raise
        except httpx.RequestError as e:
            logger.error(
                "agent_unreachable",
                error=str(e),
                conversation_id=conversation_id,
            )
            raise

        return ChatResponse.model_validate(response.json()).response
