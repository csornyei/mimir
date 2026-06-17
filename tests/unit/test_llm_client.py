from unittest.mock import AsyncMock, MagicMock

import openai
import pytest

from agent_core.llm.client import LLMClient
from agent_core.llm.params import LLMParams


def _make_choice(
    content: str, tool_calls=None, finish_reason: str = "stop"
) -> MagicMock:
    choice = MagicMock()
    choice.finish_reason = finish_reason
    choice.message.content = content
    choice.message.model_extra = {}
    choice.message.tool_calls = tool_calls
    return choice


def _ok_completion(content: str) -> MagicMock:
    resp = MagicMock()
    resp.choices = [_make_choice(content)]
    resp.usage.prompt_tokens = 10
    resp.usage.completion_tokens = 5
    resp.usage.total_tokens = 15
    return resp


def _413_error() -> openai.APIStatusError:
    mock_resp = MagicMock()
    mock_resp.status_code = 413
    mock_resp.headers = {}
    return openai.APIStatusError("413 Payload Too Large", response=mock_resp, body=None)


def _make_client(mock_create: AsyncMock) -> LLMClient:
    client = LLMClient()
    client._client = MagicMock()
    client._client.chat.completions.create = mock_create
    return client


# ---------------------------------------------------------------------------
# complete()
# ---------------------------------------------------------------------------


async def test_complete_returns_content():
    create = AsyncMock(return_value=_ok_completion("Hello there!"))
    client = _make_client(create)

    result = await client.complete([{"role": "user", "content": "Hi"}])

    assert result["content"] == "Hello there!"
    assert result["finish_reason"] == "stop"
    assert result["tool_calls"] == []


async def test_complete_posts_to_correct_endpoint():
    create = AsyncMock(return_value=_ok_completion("ok"))
    client = _make_client(create)

    await client.complete([{"role": "user", "content": "Hi"}])

    create.assert_called_once()


async def test_complete_payload_contains_required_fields():
    create = AsyncMock(return_value=_ok_completion("ok"))
    client = _make_client(create)

    await client.complete([{"role": "user", "content": "Hi"}])

    kwargs = create.call_args[1]
    assert "model" in kwargs
    assert "messages" in kwargs
    assert "max_tokens" in kwargs
    assert "temperature" in kwargs


async def test_complete_no_tools_field_by_default():
    create = AsyncMock(return_value=_ok_completion("ok"))
    client = _make_client(create)

    await client.complete([{"role": "user", "content": "Hi"}])

    kwargs = create.call_args[1]
    # tools and tool_choice should be NOT_GIVEN (falsy), not real values
    from openai import NOT_GIVEN

    assert kwargs.get("tools") is NOT_GIVEN
    assert kwargs.get("tool_choice") is NOT_GIVEN


async def test_complete_adds_tools_when_provided():
    create = AsyncMock(return_value=_ok_completion("ok"))
    client = _make_client(create)

    tools = [{"type": "function", "function": {"name": "my_tool"}}]
    await client.complete([{"role": "user", "content": "Hi"}], tools=tools)

    kwargs = create.call_args[1]
    assert kwargs["tools"] == tools
    assert kwargs["tool_choice"] == "auto"


async def test_complete_propagates_http_error():
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.headers = {}
    create = AsyncMock(
        side_effect=openai.APIStatusError(
            "500 Server Error", response=mock_resp, body=None
        )
    )
    client = _make_client(create)

    with pytest.raises(openai.APIStatusError, match="500"):
        await client.complete([{"role": "user", "content": "Hi"}])


async def test_complete_custom_temperature():
    create = AsyncMock(return_value=_ok_completion("ok"))
    client = _make_client(create)

    await client.complete(
        [{"role": "user", "content": "Hi"}], params=LLMParams(temperature=0.1)
    )

    kwargs = create.call_args[1]
    assert kwargs["temperature"] == 0.1


async def test_complete_custom_max_tokens():
    create = AsyncMock(return_value=_ok_completion("ok"))
    client = _make_client(create)

    await client.complete(
        [{"role": "user", "content": "Hi"}], params=LLMParams(max_tokens=512)
    )

    kwargs = create.call_args[1]
    assert kwargs["max_tokens"] == 512


# ---------------------------------------------------------------------------
# complete() — 413 fallback retry
# ---------------------------------------------------------------------------


async def test_complete_uses_fallback_on_413():
    create = AsyncMock(side_effect=[_413_error(), _ok_completion("fallback response")])
    client = _make_client(create)

    fallback_msgs = [{"role": "user", "content": "shorter"}]
    result = await client.complete(
        [{"role": "user", "content": "Hi"}],
        fallbacks=[fallback_msgs],
    )

    assert result["content"] == "fallback response"
    assert result["finish_reason"] == "stop"
    assert create.call_count == 2


async def test_complete_uses_second_fallback_when_first_also_413():
    create = AsyncMock(
        side_effect=[_413_error(), _413_error(), _ok_completion("minimal response")]
    )
    client = _make_client(create)

    result = await client.complete(
        [{"role": "user", "content": "original"}],
        fallbacks=[
            [{"role": "user", "content": "reduced"}],
            [{"role": "user", "content": "minimal"}],
        ],
    )

    assert result["content"] == "minimal response"
    assert result["finish_reason"] == "stop"
    assert create.call_count == 3


async def test_complete_re_raises_when_all_fallbacks_exhausted():
    create = AsyncMock(side_effect=[_413_error(), _413_error()])
    client = _make_client(create)

    with pytest.raises(openai.APIStatusError) as exc_info:
        await client.complete(
            [{"role": "user", "content": "original"}],
            fallbacks=[[{"role": "user", "content": "fallback"}]],
        )

    assert exc_info.value.status_code == 413


async def test_complete_413_no_fallbacks_re_raises():
    create = AsyncMock(side_effect=_413_error())
    client = _make_client(create)

    with pytest.raises(openai.APIStatusError) as exc_info:
        await client.complete([{"role": "user", "content": "Hi"}])

    assert exc_info.value.status_code == 413
    assert create.call_count == 1


async def test_complete_non_413_http_error_not_retried():
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.headers = {}
    create = AsyncMock(
        side_effect=openai.APIStatusError("500 Error", response=mock_resp, body=None)
    )
    client = _make_client(create)

    fallback_msgs = [{"role": "user", "content": "fallback"}]
    with pytest.raises(openai.APIStatusError) as exc_info:
        await client.complete(
            [{"role": "user", "content": "Hi"}],
            fallbacks=[fallback_msgs],
        )

    assert create.call_count == 1
    assert exc_info.value.status_code == 500


async def test_complete_fallback_uses_correct_messages():
    create = AsyncMock(side_effect=[_413_error(), _ok_completion("ok")])
    client = _make_client(create)

    original = [{"role": "user", "content": "original"}]
    fallback = [{"role": "user", "content": "fallback content"}]
    await client.complete(original, fallbacks=[fallback])

    second_call_kwargs = create.call_args_list[1][1]
    assert second_call_kwargs["messages"] == fallback
