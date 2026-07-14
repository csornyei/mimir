from datetime import UTC, date, datetime

from agent_core.routes.health import extract_health_metrics, _to_detail
from shared.models import HealthAnalysis, HealthSnapshot


def test_extract_health_metrics_maps_known_snapshot_fields():
    metrics = extract_health_metrics(
        {
            "recovery": {"hrv": {"avg": 42}, "resting_hr": {"avg": "58"}},
            "sleep_summary": {
                "avg_total_h": 7.4,
                "avg_deep_h": 1.2,
                "avg_rem_h": 1.5,
                "avg_efficiency_pct": 91,
            },
            "training": {
                "steps": {"avg": 8300},
                "active_kcal": {"avg": 620},
                "exercise_min": {"avg": 45},
                "total_distance_km": 38.4,
            },
            "energy": {"avg_tdee": 2600},
            "fitness": {"vo2_max_current": 48.5},
            "body": {"weight_kg": {"avg": 78.2}, "body_fat_pct": {"avg": 17.4}},
        }
    )

    assert metrics.hrv_avg == 42
    assert metrics.resting_hr_avg == 58
    assert metrics.sleep_total_h == 7.4
    assert metrics.steps_avg == 8300
    assert metrics.total_distance_km == 38.4
    assert metrics.vo2_max == 48.5
    assert metrics.body_fat_pct_avg == 17.4


def test_extract_health_metrics_tolerates_missing_and_invalid_values():
    metrics = extract_health_metrics(
        {
            "recovery": {"hrv": {"avg": "not-a-number"}},
            "sleep_summary": {},
            "training": {"steps": {"avg": None}},
        }
    )

    assert metrics.hrv_avg is None
    assert metrics.sleep_total_h is None
    assert metrics.steps_avg is None
    assert metrics.weight_kg_avg is None


def test_health_week_detail_marks_missing_analysis_as_pending():
    created_at = datetime(2026, 7, 13, 8, 30, tzinfo=UTC)
    snapshot = HealthSnapshot(
        week_start=date(2026, 7, 6),
        week_end=date(2026, 7, 12),
        raw_data={"training": {"steps": {"avg": 9000}}},
        created_at=created_at,
    )

    detail = _to_detail(snapshot, None)

    assert detail.week_start == date(2026, 7, 6)
    assert detail.has_analysis is False
    assert detail.analysis_md is None
    assert detail.metrics.steps_avg == 9000
    assert detail.snapshot_created_at == created_at


def test_health_week_detail_includes_analysis_markdown():
    created_at = datetime(2026, 7, 13, 8, 30, tzinfo=UTC)
    snapshot = HealthSnapshot(
        week_start=date(2026, 7, 6),
        week_end=date(2026, 7, 12),
        raw_data={},
        created_at=created_at,
    )
    analysis = HealthAnalysis(
        week_start=date(2026, 7, 6),
        analysis_md="# Weekly Analysis\n\nGood recovery week.",
    )

    detail = _to_detail(snapshot, analysis)

    assert detail.has_analysis is True
    assert "Good recovery" in (detail.analysis_md or "")
