from agent_core.scheduler.briefing.prompt import build_morning_prompt


SAMPLE_EVENTS = [
    {
        "uid": "uid-1",
        "summary": "Team Standup",
        "start": "2026-04-17T09:00:00+02:00",
        "end": "2026-04-17T09:30:00+02:00",
        "description": None,
        "location": "Room A",
    },
    {
        "uid": "uid-2",
        "summary": "Project Review",
        "start": "2026-04-17T14:00:00+02:00",
        "end": "2026-04-17T15:00:00+02:00",
        "description": "Quarterly check-in",
        "location": None,
    },
]


def test_build_morning_prompt_returns_two_messages():
    messages = build_morning_prompt(SAMPLE_EVENTS)
    assert len(messages) == 2


def test_build_morning_prompt_message_roles():
    messages = build_morning_prompt(SAMPLE_EVENTS)
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"


def test_build_morning_prompt_user_message_contains_event_summaries():
    messages = build_morning_prompt(SAMPLE_EVENTS)
    user_content = messages[1]["content"]
    assert "Team Standup" in user_content
    assert "Project Review" in user_content


def test_build_morning_prompt_user_message_contains_location():
    messages = build_morning_prompt(SAMPLE_EVENTS)
    assert "Room A" in messages[1]["content"]


def test_build_morning_prompt_no_events_still_returns_two_messages():
    messages = build_morning_prompt([])
    assert len(messages) == 2
    assert messages[0]["role"] == "system"
    assert messages[1]["role"] == "user"


def test_build_morning_prompt_no_events_notes_empty_schedule():
    messages = build_morning_prompt([])
    assert (
        "no events" in messages[1]["content"].lower()
        or "nothing" in messages[1]["content"].lower()
    )


def test_build_morning_prompt_with_todos_includes_todo_section():
    todos = [
        {"summary": "Buy groceries", "due": "2026-05-01", "status": "NEEDS-ACTION"}
    ]
    messages = build_morning_prompt(SAMPLE_EVENTS, todos=todos)
    assert "to-do" in messages[1]["content"].lower()


def test_build_morning_prompt_without_todos_omits_todo_section():
    messages = build_morning_prompt(SAMPLE_EVENTS)
    assert "to-do" not in messages[1]["content"].lower()
