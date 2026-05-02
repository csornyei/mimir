"""Tests for agent_core/prompts — Jinja2 template rendering."""

from agent_core.prompts import (
    render_episodic_consolidation_initial,
    render_episodic_consolidation_update,
    render_morning_briefing_system,
    render_morning_briefing_user,
    render_rss_filter_system,
    render_rss_filter_user,
    render_system_prompt,
    render_tool_instructions,
)


# ---------------------------------------------------------------------------
# render_system_prompt
# ---------------------------------------------------------------------------


def test_system_prompt_contains_owner():
    result = render_system_prompt(
        owner="Alice",
        datetime="2026-01-01 08:00",
        semantic_memory="Alice likes Python",
        episodic_context="No past context.",
        rag_context="No docs.",
        context_window=128_000,
        tool_instructions="No tools.",
    )
    assert "Alice" in result


def test_system_prompt_contains_datetime():
    result = render_system_prompt(
        owner="Bob",
        datetime="2026-05-01 09:30",
        semantic_memory="x",
        episodic_context="x",
        rag_context="x",
        context_window=32_000,
        tool_instructions="x",
    )
    assert "2026-05-01 09:30" in result


def test_system_prompt_contains_all_sections():
    result = render_system_prompt(
        owner="Bob",
        datetime="2026-05-01 09:00",
        semantic_memory="Bob works remotely.",
        episodic_context="Talked about Docker.",
        rag_context="Project notes here.",
        context_window=64_000,
        tool_instructions="Read tools: list_pods",
    )
    assert "Bob works remotely." in result
    assert "Talked about Docker." in result
    assert "Project notes here." in result
    assert "64000" in result
    assert "Read tools: list_pods" in result


# ---------------------------------------------------------------------------
# render_tool_instructions
# ---------------------------------------------------------------------------


def test_tool_instructions_no_tools():
    result = render_tool_instructions(None)
    assert "no tools available" in result.lower()


def test_tool_instructions_empty_list():
    result = render_tool_instructions([])
    assert "no tools available" in result.lower()


def test_tool_instructions_with_read_tools():
    tools = [
        {"name": "list_pods", "destructive": False},
        {"name": "list_nodes", "destructive": False},
    ]
    result = render_tool_instructions(tools)
    assert "list_pods" in result
    assert "list_nodes" in result
    assert "Read tools" in result


def test_tool_instructions_with_write_tools():
    tools = [{"name": "delete_pod", "destructive": True}]
    result = render_tool_instructions(tools)
    assert "delete_pod" in result
    assert "Write tools" in result
    assert "approval" in result.lower()


def test_tool_instructions_write_tools_include_approval_note():
    tools = [{"name": "restart_service", "destructive": True}]
    result = render_tool_instructions(tools)
    assert "approval flow" in result.lower() or "approval" in result.lower()


def test_tool_instructions_no_write_note_when_only_read():
    tools = [{"name": "list_services", "destructive": False}]
    result = render_tool_instructions(tools)
    assert "approval flow" not in result


def test_tool_instructions_function_format_tools():
    tools = [{"function": {"name": "get_weather"}, "destructive": False}]
    result = render_tool_instructions(tools)
    assert "get_weather" in result


# ---------------------------------------------------------------------------
# render_morning_briefing_system
# ---------------------------------------------------------------------------


def test_morning_briefing_system_without_weather():
    result = render_morning_briefing_system(weather_data=False)
    assert "morning briefing" in result.lower()
    assert "weather" not in result.lower()


def test_morning_briefing_system_with_weather():
    result = render_morning_briefing_system(weather_data=True)
    assert "weather" in result.lower()


# ---------------------------------------------------------------------------
# render_morning_briefing_user
# ---------------------------------------------------------------------------


def test_morning_briefing_user_contains_events():
    result = render_morning_briefing_user(
        event_text=[
            {
                "summary": "Standup",
                "start": "2026-05-01T10:00:00+00:00",
                "location": "Room A",
            }
        ],
        weather_data=None,
        todo_text=None,
    )
    assert "Standup" in result
    assert "Room A" in result


def test_morning_briefing_user_without_weather_omits_forecast():
    result = render_morning_briefing_user(
        event_text=[
            {
                "summary": "Meeting",
                "start": "2026-05-01T10:00:00+00:00",
                "location": "Room B",
            }
        ],
        weather_data=None,
        todo_text=None,
    )
    assert "weather forecast" not in result.lower()


def test_morning_briefing_user_with_weather_includes_forecast():
    result = render_morning_briefing_user(
        event_text=[
            {
                "summary": "Meeting",
                "start": "2026-05-01T10:00:00+00:00",
                "location": "Room B",
            }
        ],
        weather_data={"summary": "Sunny, 24°C"},
        todo_text=None,
    )
    assert "weather forecast" in result.lower()
    assert "Sunny" in result


def test_morning_briefing_user_with_todos_includes_todo_section():
    todos = [{"summary": "Buy groceries", "due": "2026-05-01"}]
    result = render_morning_briefing_user(
        event_text=[
            {
                "summary": "Meeting",
                "start": "2026-05-01T10:00:00+00:00",
                "location": "Room B",
            }
        ],
        weather_data=None,
        todo_text=todos,
    )
    assert "to-do" in result.lower()


def test_morning_briefing_user_without_todos_omits_todo_section():
    result = render_morning_briefing_user(
        event_text=[
            {
                "summary": "Meeting",
                "start": "2026-05-01T10:00:00+00:00",
                "location": "Room B",
            }
        ],
        weather_data=None,
        todo_text=None,
    )
    assert "to-do" not in result.lower()


# ---------------------------------------------------------------------------
# render_rss_filter_system
# ---------------------------------------------------------------------------


def test_rss_filter_system_contains_n_picks():
    result = render_rss_filter_system(n_picks=7)
    assert "7" in result


def test_rss_filter_system_requests_json():
    result = render_rss_filter_system(n_picks=5)
    assert "JSON" in result


# ---------------------------------------------------------------------------
# render_rss_filter_user
# ---------------------------------------------------------------------------


def _entry(
    entry_id: int = 1,
    title: str = "Test Article",
    feed_name: str = "Tech Blog",
    category: str = "Technology",
    summary: str | None = "A brief summary.",
) -> dict:
    return {
        "id": entry_id,
        "title": title,
        "url": f"https://example.com/{entry_id}",
        "feed_name": feed_name,
        "category": category,
        "summary": summary,
    }


def test_rss_filter_user_contains_entry_title():
    result = render_rss_filter_user(
        entries=[_entry()],
        semantic_memory="",
        feedback_summary="No feedback recorded yet.",
        n_picks=5,
    )
    assert "Test Article" in result


def test_rss_filter_user_with_semantic_memory():
    result = render_rss_filter_user(
        entries=[_entry()],
        semantic_memory="User loves Python.",
        feedback_summary="No feedback recorded yet.",
        n_picks=5,
    )
    assert "About the user" in result
    assert "User loves Python." in result


def test_rss_filter_user_omits_memory_section_when_empty():
    result = render_rss_filter_user(
        entries=[_entry()],
        semantic_memory="",
        feedback_summary="No feedback recorded yet.",
        n_picks=5,
    )
    assert "About the user" not in result


def test_rss_filter_user_with_feedback():
    result = render_rss_filter_user(
        entries=[_entry()],
        semantic_memory="",
        feedback_summary="User prefers short reads.",
        n_picks=5,
    )
    assert "Past feedback" in result
    assert "User prefers short reads." in result


def test_rss_filter_user_omits_feedback_when_no_data():
    result = render_rss_filter_user(
        entries=[_entry()],
        semantic_memory="",
        feedback_summary="No feedback recorded yet.",
        n_picks=5,
    )
    assert "Past feedback" not in result


def test_rss_filter_user_entry_without_summary():
    result = render_rss_filter_user(
        entries=[_entry(summary=None)],
        semantic_memory="",
        feedback_summary="No feedback recorded yet.",
        n_picks=5,
    )
    assert "Test Article" in result


# ---------------------------------------------------------------------------
# render_episodic_consolidation_initial
# ---------------------------------------------------------------------------


def test_episodic_initial_contains_transcript():
    result = render_episodic_consolidation_initial(
        transcript="USER: hi\nASSISTANT: hello"
    )
    assert "USER: hi" in result
    assert "ASSISTANT: hello" in result


def test_episodic_initial_asks_for_summary():
    result = render_episodic_consolidation_initial(transcript="some text")
    assert "summarise" in result.lower() or "summary" in result.lower()


# ---------------------------------------------------------------------------
# render_episodic_consolidation_update
# ---------------------------------------------------------------------------


def test_episodic_update_contains_prior_summary():
    result = render_episodic_consolidation_update(
        prior_summary="Previously talked about Kubernetes.",
        transcript="USER: what about Helm?\nASSISTANT: Helm is a package manager.",
    )
    assert "Previously talked about Kubernetes." in result


def test_episodic_update_contains_new_transcript():
    result = render_episodic_consolidation_update(
        prior_summary="Prior summary here.",
        transcript="USER: what about Helm?\nASSISTANT: Helm is a package manager.",
    )
    assert "Helm" in result


def test_episodic_update_asks_for_updated_summary():
    result = render_episodic_consolidation_update(
        prior_summary="Old summary.",
        transcript="New messages.",
    )
    assert "updated" in result.lower()
