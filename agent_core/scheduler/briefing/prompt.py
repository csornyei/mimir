from typing import Any

from agent_core.prompts import (
    render_morning_briefing_system,
    render_morning_briefing_user,
)


def build_morning_prompt(
    events: list[dict[str, Any]],
    weather_data: dict[str, Any] | None = None,
    todos: list[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": render_morning_briefing_system(weather_data=bool(weather_data)),
        },
        {
            "role": "user",
            "content": render_morning_briefing_user(
                event_text=events, weather_data=weather_data, todo_text=todos
            ),
        },
    ]
