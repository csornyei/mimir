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


def build_morning_prompt(events: list[dict[str, Any]]) -> list[dict[str, str]]:
    system = (
        "You are Mimir, a personal AI assistant. "
        "Write a friendly and concise morning briefing. "
        "Mention every calendar event for today. "
        "Be warm, practical, and brief."
    )
    event_text = _format_events(events)
    user = f"Here are today's calendar events:\n\n{event_text}\n\nPlease write the morning briefing."
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
