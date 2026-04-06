from datetime import datetime

import pytest
from pydantic import ValidationError

from mimir.schemas import (
    ChatRequest,
    ChatResponse,
    ConversationDetail,
    ConversationSummary,
    MessageResponse,
)


# ---------------------------------------------------------------------------
# ChatRequest
# ---------------------------------------------------------------------------


def test_chat_request_valid():
    req = ChatRequest(conversation_id="conv-1", user_id="u1", message="hello")
    assert req.conversation_id == "conv-1"
    assert req.user_id == "u1"
    assert req.message == "hello"


def test_chat_request_missing_conversation_id():
    with pytest.raises(ValidationError):
        ChatRequest(user_id="u1", message="hello")


def test_chat_request_missing_user_id():
    with pytest.raises(ValidationError):
        ChatRequest(conversation_id="conv-1", message="hello")


def test_chat_request_missing_message():
    with pytest.raises(ValidationError):
        ChatRequest(conversation_id="conv-1", user_id="u1")


# ---------------------------------------------------------------------------
# ChatResponse
# ---------------------------------------------------------------------------


def test_chat_response_valid():
    resp = ChatResponse(response="hi there", conversation_id="conv-1")
    assert resp.response == "hi there"
    assert resp.conversation_id == "conv-1"


def test_chat_response_missing_field():
    with pytest.raises(ValidationError):
        ChatResponse(response="hi")


# ---------------------------------------------------------------------------
# ConversationSummary
# ---------------------------------------------------------------------------


def test_conversation_summary_valid():
    now = datetime.now()
    s = ConversationSummary(id="abc", created_at=now, last_active=now)
    assert s.id == "abc"


# ---------------------------------------------------------------------------
# MessageResponse
# ---------------------------------------------------------------------------


def test_message_response_valid():
    now = datetime.now()
    m = MessageResponse(id=1, role="user", content="Hello", timestamp=now)
    assert m.role == "user"
    assert m.content == "Hello"


# ---------------------------------------------------------------------------
# ConversationDetail
# ---------------------------------------------------------------------------


def test_conversation_detail_valid():
    now = datetime.now()
    detail = ConversationDetail(
        id="abc",
        created_at=now,
        last_active=now,
        messages=[],
        total=0,
        limit=20,
        offset=0,
    )
    assert detail.total == 0
    assert detail.limit == 20
    assert detail.offset == 0
    assert detail.messages == []


def test_conversation_detail_with_messages():
    now = datetime.now()
    msg = MessageResponse(id=1, role="user", content="Hi", timestamp=now)
    detail = ConversationDetail(
        id="abc",
        created_at=now,
        last_active=now,
        messages=[msg],
        total=1,
        limit=20,
        offset=0,
    )
    assert len(detail.messages) == 1
    assert detail.total == 1
