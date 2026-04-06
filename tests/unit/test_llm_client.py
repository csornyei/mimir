from unittest.mock import AsyncMock, MagicMock

import pytest

from mimir.llm.client import LLMClient


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

    assert result == "Hello there!"


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
# embed() / embed_batch()
# ---------------------------------------------------------------------------


async def test_embed_delegates_to_embedding_model(mocker):
    mock_em = mocker.patch("mimir.llm.client.embedding_model")
    mock_em.embed.return_value = [0.1, 0.2, 0.3]
    http = AsyncMock()
    client = _make_client(http)

    result = await client.embed("hello")

    mock_em.embed.assert_called_once_with("hello")
    assert result == [0.1, 0.2, 0.3]


async def test_embed_batch_delegates_to_embedding_model(mocker):
    mock_em = mocker.patch("mimir.llm.client.embedding_model")
    mock_em.embed_batch.return_value = [[0.1, 0.2], [0.3, 0.4]]
    http = AsyncMock()
    client = _make_client(http)

    result = await client.embed_batch(["hello", "world"])

    mock_em.embed_batch.assert_called_once_with(["hello", "world"])
    assert result == [[0.1, 0.2], [0.3, 0.4]]
