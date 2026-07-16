from datetime import UTC, date, datetime

import pytest

from workflows.health_coach.dates import parse_week_start
from workflows.rss_digest.window import resolve_window


def test_resolve_window_infers_previous_six_hour_block() -> None:
    window = resolve_window(now=datetime(2026, 7, 16, 6, 10, tzinfo=UTC))

    assert window.start == datetime(2026, 7, 16, 0, 0, tzinfo=UTC)
    assert window.end == datetime(2026, 7, 16, 6, 0, tzinfo=UTC)
    assert window.label == "00-06"


def test_resolve_window_infers_midnight_block_as_previous_day() -> None:
    window = resolve_window(now=datetime(2026, 7, 16, 0, 10, tzinfo=UTC))

    assert window.start == datetime(2026, 7, 15, 18, 0, tzinfo=UTC)
    assert window.end == datetime(2026, 7, 16, 0, 0, tzinfo=UTC)
    assert window.label == "18-24"


def test_resolve_window_rejects_partial_explicit_window() -> None:
    with pytest.raises(ValueError, match="provided together"):
        resolve_window(start_hour=6)


def test_parse_week_start_accepts_any_date_in_week() -> None:
    assert parse_week_start("2026-05-17") == date(2026, 5, 11)
    assert parse_week_start("2026-05-11") == date(2026, 5, 11)
    assert parse_week_start("") is None
