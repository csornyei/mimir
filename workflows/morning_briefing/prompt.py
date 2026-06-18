from typing import Any

from shared.prompts.loader import render


def render_morning_briefing_system(weather_data: bool, user: str) -> str:
    return render("morning_briefing_system.j2", weather_data=weather_data, user=user)


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


def build_morning_prompt(
    user: str,
    events: list[dict[str, Any]],
    weather_data: dict[str, Any] | None = None,
    todos: list[dict[str, Any]] | None = None,
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": render_morning_briefing_system(
                weather_data=bool(weather_data), user=user
            ),
        },
        {
            "role": "user",
            "content": render_morning_briefing_user(
                event_text=events, weather_data=weather_data, todo_text=todos
            ),
        },
    ]
