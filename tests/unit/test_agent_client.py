"""Tests for mimir.agent.client."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import HTTPStatusError, Request, Response

from mimir.agent.client import send_to_agent


def _make_response(status: int, body: dict) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    if status >= 400:
        req = Request("POST", "http://test/api/chat")
        raw = Response(status, request=req)
        resp.raise_for_status.side_effect = HTTPStatusError(
            f"{status}", request=req, response=raw
        )
    else:
        resp.raise_for_status = MagicMock()
        resp.json.return_value = body
    return resp


async def test_send_to_agent_returns_response_text(mocker):
    mocker.patch("mimir.agent.client.config.agent_url", "http://localhost:8000")

    mock_client = AsyncMock()
    mock_client.post.return_value = _make_response(
        200, {"response": "Hello!", "conversation_id": "C1|T1"}
    )
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("mimir.agent.client.httpx.AsyncClient", return_value=mock_client):
        result = await send_to_agent(
            conversation_id="C1|T1",
            user_id="U999",
            message="Hello",
        )

    assert result == "Hello!"


async def test_send_to_agent_raises_on_http_error(mocker):
    mocker.patch("mimir.agent.client.config.agent_url", "http://localhost:8000")

    mock_client = AsyncMock()
    mock_client.post.return_value = _make_response(500, {})
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    with patch("mimir.agent.client.httpx.AsyncClient", return_value=mock_client):
        with pytest.raises(HTTPStatusError):
            await send_to_agent(
                conversation_id="C1|T1",
                user_id="U999",
                message="Hello",
            )
