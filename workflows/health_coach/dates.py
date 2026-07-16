from datetime import date, timedelta


def parse_week_start(value: str | None) -> date | None:
    if value is None or not value.strip():
        return None

    target_date = date.fromisoformat(value.strip())
    return target_date - timedelta(days=target_date.weekday())
