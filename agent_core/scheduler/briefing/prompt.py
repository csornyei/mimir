from typing import Any


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
    system = (
        "You are Mimir, a personal AI assistant. "
        "Write a friendly and concise morning briefing. "
        "Mention every calendar event for today. "
        "Include a brief summary of the weather forecast and what to expect today and for the rest of the week. "
        "Be warm, practical, and brief. "
        "Your response will be added after a greeting that includes \"Good morning\", the user's name and a header that says 'Here's your briefing for today'."
    )
    event_text = _format_events(events)

    weather_text = (
        f"Here is the weather forecast:\n\n{weather_data}\n\n" if weather_data else ""
    )
    user = f"Here are today's calendar events:\n\n{event_text}\n\n{weather_text}\nPlease write the morning briefing."
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
