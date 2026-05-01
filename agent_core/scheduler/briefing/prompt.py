from typing import Any

from agent_core.prompts import (
    render_morning_briefing_system,
    render_morning_briefing_user,
)


def _format_events(events: list[dict[str, Any]]) -> str:
    if not events:
        return "No events scheduled for today."
    lines = []
    for e in events:
        start = e.get("start") or "?"
        end = e.get("end") or "?"
        summary = e.get("summary") or "(no title)"
        location = e.get("location")
        line = f"- {start} to {end}: {summary}"
        if location:
            line += f" @ {location}"
        lines.append(line)
    return "\n".join(lines)


def build_morning_prompt(
    events: list[dict[str, Any]], weather_data: dict[str, Any] | None = None
) -> list[dict[str, str]]:
    event_text = _format_events(events)
    return [
        {
            "role": "system",
            "content": render_morning_briefing_system(weather_data=bool(weather_data)),
        },
        {
            "role": "user",
            "content": render_morning_briefing_user(
                event_text=event_text, weather_data=weather_data
            ),
        },
    ]
