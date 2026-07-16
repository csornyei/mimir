from dataclasses import dataclass
from datetime import UTC, datetime, timedelta


@dataclass(frozen=True)
class RssWindow:
    start: datetime
    end: datetime
    label: str


def _label(start_hour: int, end_hour: int) -> str:
    display_end = 24 if end_hour == 0 else end_hour
    return f"{start_hour:02d}-{display_end:02d}"


def resolve_window(
    *,
    start_hour: int | None = None,
    end_hour: int | None = None,
    label: str | None = None,
    window_hours: int = 6,
    now: datetime | None = None,
) -> RssWindow:
    if (start_hour is None) != (end_hour is None):
        raise ValueError("--start and --end must be provided together")
    if window_hours <= 0 or 24 % window_hours != 0:
        raise ValueError("--window-hours must be a positive divisor of 24")

    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    current = current.astimezone(UTC)

    if start_hour is None or end_hour is None:
        end_hour = (current.hour // window_hours) * window_hours
        start_hour = (end_hour - window_hours) % 24

    if start_hour not in range(24) or end_hour not in range(24):
        raise ValueError("--start and --end must be UTC hours in the range 0-23")

    window_end = current.replace(hour=end_hour, minute=0, second=0, microsecond=0)
    if start_hour > end_hour:
        window_start = window_end.replace(hour=start_hour) - timedelta(days=1)
    else:
        window_start = window_end.replace(hour=start_hour)

    return RssWindow(
        start=window_start,
        end=window_end,
        label=label or _label(start_hour, end_hour),
    )
