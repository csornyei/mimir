from datetime import date
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import get_db
from shared.models import HealthAnalysis, HealthSnapshot
from shared.schemas import HealthMetricSummary, HealthWeekDetail, HealthWeekSummary

router = APIRouter(prefix="/health", tags=["health"])


def _safe_get(data: dict[str, Any], *keys: str) -> Any:
    obj: Any = data
    for key in keys:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(key)
    return obj


def _number(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def extract_health_metrics(raw: dict[str, Any]) -> HealthMetricSummary:
    return HealthMetricSummary(
        hrv_avg=_number(_safe_get(raw, "recovery", "hrv", "avg")),
        resting_hr_avg=_number(_safe_get(raw, "recovery", "resting_hr", "avg")),
        sleep_total_h=_number(_safe_get(raw, "sleep_summary", "avg_total_h")),
        sleep_deep_h=_number(_safe_get(raw, "sleep_summary", "avg_deep_h")),
        sleep_rem_h=_number(_safe_get(raw, "sleep_summary", "avg_rem_h")),
        sleep_efficiency_pct=_number(
            _safe_get(raw, "sleep_summary", "avg_efficiency_pct")
        ),
        steps_avg=_number(_safe_get(raw, "training", "steps", "avg")),
        active_kcal_avg=_number(_safe_get(raw, "training", "active_kcal", "avg")),
        exercise_min_avg=_number(_safe_get(raw, "training", "exercise_min", "avg")),
        total_distance_km=_number(_safe_get(raw, "training", "total_distance_km")),
        avg_tdee=_number(_safe_get(raw, "energy", "avg_tdee")),
        vo2_max=_number(_safe_get(raw, "fitness", "vo2_max_current")),
        weight_kg_avg=_number(_safe_get(raw, "body", "weight_kg", "avg")),
        body_fat_pct_avg=_number(_safe_get(raw, "body", "body_fat_pct", "avg")),
    )


def _to_summary(
    snapshot: HealthSnapshot, analysis: HealthAnalysis | None
) -> HealthWeekSummary:
    return HealthWeekSummary(
        week_start=snapshot.week_start,
        week_end=snapshot.week_end,
        created_at=snapshot.created_at,
        has_analysis=analysis is not None,
    )


def _to_detail(
    snapshot: HealthSnapshot, analysis: HealthAnalysis | None
) -> HealthWeekDetail:
    return HealthWeekDetail(
        week_start=snapshot.week_start,
        week_end=snapshot.week_end,
        created_at=snapshot.created_at,
        has_analysis=analysis is not None,
        analysis_md=analysis.analysis_md if analysis else None,
        metrics=extract_health_metrics(snapshot.raw_data),
        snapshot_created_at=snapshot.created_at,
    )


@router.get("/weeks", response_model=list[HealthWeekSummary])
async def list_health_weeks(
    db: AsyncSession = Depends(get_db),
) -> list[HealthWeekSummary]:
    """List health snapshot weeks, newest first."""
    result = await db.execute(
        select(HealthSnapshot, HealthAnalysis)
        .outerjoin(
            HealthAnalysis, HealthAnalysis.week_start == HealthSnapshot.week_start
        )
        .order_by(desc(HealthSnapshot.week_start))
    )
    return [_to_summary(snapshot, analysis) for snapshot, analysis in result.all()]


@router.get("/latest", response_model=HealthWeekDetail)
async def get_latest_health_week(
    db: AsyncSession = Depends(get_db),
) -> HealthWeekDetail:
    """Return the newest health snapshot with analysis when available."""
    result = await db.execute(
        select(HealthSnapshot, HealthAnalysis)
        .outerjoin(
            HealthAnalysis, HealthAnalysis.week_start == HealthSnapshot.week_start
        )
        .order_by(desc(HealthSnapshot.week_start))
        .limit(1)
    )
    row = result.first()
    if row is None:
        raise HTTPException(status_code=404, detail="No health data found")
    snapshot, analysis = row
    return _to_detail(snapshot, analysis)


@router.get("/weeks/{week_start}", response_model=HealthWeekDetail)
async def get_health_week(
    week_start: date,
    db: AsyncSession = Depends(get_db),
) -> HealthWeekDetail:
    """Return health snapshot and analysis for a specific week start date."""
    result = await db.execute(
        select(HealthSnapshot, HealthAnalysis)
        .outerjoin(
            HealthAnalysis, HealthAnalysis.week_start == HealthSnapshot.week_start
        )
        .where(HealthSnapshot.week_start == week_start)
        .limit(1)
    )
    row = result.first()
    if row is None:
        raise HTTPException(status_code=404, detail="Health week not found")
    snapshot, analysis = row
    return _to_detail(snapshot, analysis)
