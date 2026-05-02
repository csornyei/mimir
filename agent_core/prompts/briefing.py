from typing import Any

from agent_core.prompts.loader import render


def render_morning_briefing_system(weather_data: bool) -> str:
    return render("morning_briefing_system.j2", weather_data=weather_data)


def render_morning_briefing_user(
    event_text: list[dict[str, Any]],
    weather_data: dict[str, Any] | None,
    todo_text: list[dict[str, Any]] | None,
) -> str:
    return render(
        "morning_briefing_user.j2",
        event_text=event_text,
        weather_data=weather_data,
        todo_text=todo_text,
    )
