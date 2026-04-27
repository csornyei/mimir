from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import HTTPStatusError, Request, Response

from mimir.llm.client import LLMClient


def _413_error() -> HTTPStatusError:
    req = Request("POST", "http://test/v1/chat/completions")
    resp = Response(413, request=req)
    return HTTPStatusError("413 Payload Too Large", request=req, response=resp)


def _http_error(status: int) -> HTTPStatusError:
    req = Request("POST", "http://test/v1/chat/completions")
    resp = Response(status, request=req)
    return HTTPStatusError(f"{status} Error", request=req, response=resp)


def _413_response() -> MagicMock:
    resp = MagicMock()
    resp.status_code = 413
    resp.text = "Request too large"
    resp.raise_for_status.side_effect = _413_error()
    return resp


def _make_client(mock_http: AsyncMock) -> LLMClient:
    """Create a LLMClient instance with its internal httpx client replaced."""
    client = LLMClient()
    client._client = mock_http
    return client


def _ok_response(content: str) -> MagicMock:
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    resp.status_code = 200
    resp.text = f'{{"choices": [{{"message": {{"content": "{content}"}}}}]}}'
    resp.json.return_value = {"choices": [{"message": {"content": content}}]}
    return resp


# ---------------------------------------------------------------------------
# complete()
# ---------------------------------------------------------------------------


async def test_complete_returns_content(mocker):
    mocker.patch("mimir.llm.client.embedding_model")
    http = AsyncMock()
    http.post.return_value = _ok_response("Hello there!")
    client = _make_client(http)

    result = await client.complete([{"role": "user", "content": "Hi"}])

    assert result["content"] == "Hello there!"
    assert result["finish_reason"] == "stop"
    assert result["tool_calls"] == []


async def test_complete_posts_to_correct_endpoint(mocker):
    mocker.patch("mimir.llm.client.embedding_model")
    http = AsyncMock()
    http.post.return_value = _ok_response("ok")
    client = _make_client(http)

    await client.complete([{"role": "user", "content": "Hi"}])

    http.post.assert_called_once()
    endpoint = http.post.call_args[0][0]
    assert endpoint == "/v1/chat/completions"


async def test_complete_payload_contains_required_fields(mocker):
    mocker.patch("mimir.llm.client.embedding_model")
    http = AsyncMock()
    http.post.return_value = _ok_response("ok")
    client = _make_client(http)

    await client.complete([{"role": "user", "content": "Hi"}])

    payload = http.post.call_args[1]["json"]
    assert "model" in payload
    assert "messages" in payload
    assert "max_tokens" in payload
    assert "temperature" in payload


async def test_complete_no_tools_field_by_default(mocker):
    mocker.patch("mimir.llm.client.embedding_model")
    http = AsyncMock()
    http.post.return_value = _ok_response("ok")
    client = _make_client(http)

    await client.complete([{"role": "user", "content": "Hi"}])

    payload = http.post.call_args[1]["json"]
    assert "tools" not in payload
    assert "tool_choice" not in payload


async def test_complete_adds_tools_when_provided(mocker):
    mocker.patch("mimir.llm.client.embedding_model")
    http = AsyncMock()
    http.post.return_value = _ok_response("ok")
    client = _make_client(http)

    tools = [{"type": "function", "function": {"name": "my_tool"}}]
    await client.complete([{"role": "user", "content": "Hi"}], tools=tools)

    payload = http.post.call_args[1]["json"]
    assert payload["tools"] == tools
    assert payload["tool_choice"] == "auto"


async def test_complete_propagates_http_error(mocker):
    mocker.patch("mimir.llm.client.embedding_model")
    http = AsyncMock()
    resp = MagicMock()
    resp.status_code = 500
    resp.text = "Internal Server Error"
    resp.raise_for_status.side_effect = Exception("500 Server Error")
    http.post.return_value = resp
    client = _make_client(http)

    with pytest.raises(Exception, match="500"):
        await client.complete([{"role": "user", "content": "Hi"}])


async def test_complete_custom_temperature(mocker):
    mocker.patch("mimir.llm.client.embedding_model")
    http = AsyncMock()
    http.post.return_value = _ok_response("ok")
    client = _make_client(http)

    await client.complete([{"role": "user", "content": "Hi"}], temperature=0.1)

    payload = http.post.call_args[1]["json"]
    assert payload["temperature"] == 0.1


async def test_complete_custom_max_tokens(mocker):
    mocker.patch("mimir.llm.client.embedding_model")
    http = AsyncMock()
    http.post.return_value = _ok_response("ok")
    client = _make_client(http)

    await client.complete([{"role": "user", "content": "Hi"}], max_tokens=512)

    payload = http.post.call_args[1]["json"]
    assert payload["max_tokens"] == 512


# ---------------------------------------------------------------------------
# complete() — 413 fallback retry
# ---------------------------------------------------------------------------


async def test_complete_uses_fallback_on_413(mocker):
    mocker.patch("mimir.llm.client.embedding_model")
    http = AsyncMock()
    # First attempt → 413, second attempt (fallback) → 200
    http.post.side_effect = [_413_response(), _ok_response("fallback response")]
    client = _make_client(http)

    fallback_msgs = [{"role": "user", "content": "shorter"}]
    result = await client.complete(
        [{"role": "user", "content": "Hi"}],
        fallbacks=[fallback_msgs],
    )

    assert result["content"] == "fallback response"
    assert result["finish_reason"] == "stop"
    assert http.post.call_count == 2


async def test_complete_uses_second_fallback_when_first_also_413(mocker):
    mocker.patch("mimir.llm.client.embedding_model")
    http = AsyncMock()
    # First two attempts → 413, third → 200
    http.post.side_effect = [
        _413_response(),
        _413_response(),
        _ok_response("minimal response"),
    ]
    client = _make_client(http)

    result = await client.complete(
        [{"role": "user", "content": "original"}],
        fallbacks=[
            [{"role": "user", "content": "reduced"}],
            [{"role": "user", "content": "minimal"}],
        ],
    )

    assert result["content"] == "minimal response"
    assert result["finish_reason"] == "stop"
    assert http.post.call_count == 3


async def test_complete_re_raises_when_all_fallbacks_exhausted(mocker):
    mocker.patch("mimir.llm.client.embedding_model")
    http = AsyncMock()
    http.post.side_effect = [_413_response(), _413_response()]
    client = _make_client(http)

    with pytest.raises(HTTPStatusError) as exc_info:
        await client.complete(
            [{"role": "user", "content": "original"}],
            fallbacks=[[{"role": "user", "content": "fallback"}]],
        )

    assert exc_info.value.response.status_code == 413


async def test_complete_413_no_fallbacks_re_raises(mocker):
    mocker.patch("mimir.llm.client.embedding_model")
    http = AsyncMock()
    http.post.return_value = _413_response()
    client = _make_client(http)

    with pytest.raises(HTTPStatusError) as exc_info:
        await client.complete([{"role": "user", "content": "Hi"}])

    assert exc_info.value.response.status_code == 413
    assert http.post.call_count == 1


async def test_complete_non_413_http_error_not_retried(mocker):
    mocker.patch("mimir.llm.client.embedding_model")
    http = AsyncMock()
    resp = MagicMock()
    resp.status_code = 500
    resp.text = "Internal Server Error"
    resp.raise_for_status.side_effect = _http_error(500)
    http.post.return_value = resp
    client = _make_client(http)

    fallback_msgs = [{"role": "user", "content": "fallback"}]
    with pytest.raises(HTTPStatusError) as exc_info:
        await client.complete(
            [{"role": "user", "content": "Hi"}],
            fallbacks=[fallback_msgs],
        )

    # Must not have tried the fallback
    assert http.post.call_count == 1
    assert exc_info.value.response.status_code == 500


async def test_complete_fallback_uses_correct_messages(mocker):
    mocker.patch("mimir.llm.client.embedding_model")
    http = AsyncMock()
    http.post.side_effect = [_413_response(), _ok_response("ok")]
    client = _make_client(http)

    original = [{"role": "user", "content": "original"}]
    fallback = [{"role": "user", "content": "fallback content"}]
    await client.complete(original, fallbacks=[fallback])

    # Second call should use the fallback messages
    second_call_payload = http.post.call_args_list[1][1]["json"]
    assert second_call_payload["messages"] == fallback
