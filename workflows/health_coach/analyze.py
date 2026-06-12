import argparse
import asyncio
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import httpx
from opentelemetry import trace
from opentelemetry.trace import SpanKind
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db import dispose_db, get_session, initialize_db
from shared.external.ntfy import send_ntfy
from shared.logger import logger
from shared.models import HealthAnalysis, HealthSnapshot
from shared.prompts.loader import render
from shared.schemas import LLMSettings, Message, RawChatRequest
from shared.telemetry import setup_tracing
from workflows.config import workflow_config as config

setup_tracing(service_name=config.service_name)
_tracer = trace.get_tracer("mimir.workflows.health_coach.analyze")


def validate_config() -> bool:
    required = [
        ("health_coach_endpoint_url", config.health_coach_endpoint_url),
        ("agent_core_api_url", config.agent_core_api_url),
        ("database_url", config.database_url),
    ]
    missing = [name for name, value in required if not value]
    if missing:
        logger.warning(
            "health_analyze_skipped",
            reason=f"Missing required config: {', '.join(missing)}",
        )
        return False
    return True


def get_week_start(tz: str) -> date:
    today = datetime.now(ZoneInfo(tz)).date()
    return today - timedelta(days=today.weekday()) - timedelta(weeks=1)


def _safe_get(data: dict[str, Any], *keys: str) -> Any:
    obj: Any = data
    for key in keys:
        if not isinstance(obj, dict):
            return None
        obj = obj.get(key)
    return obj


def _extract_metrics(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "hrv_avg": _safe_get(raw, "recovery", "hrv", "avg"),
        "resting_hr_avg": _safe_get(raw, "recovery", "resting_hr", "avg"),
        "sleep_total_h": _safe_get(raw, "sleep_summary", "avg_total_h"),
        "sleep_deep_h": _safe_get(raw, "sleep_summary", "avg_deep_h"),
        "sleep_rem_h": _safe_get(raw, "sleep_summary", "avg_rem_h"),
        "sleep_efficiency_pct": _safe_get(raw, "sleep_summary", "avg_efficiency_pct"),
        "steps_avg": _safe_get(raw, "training", "steps", "avg"),
        "active_kcal_avg": _safe_get(raw, "training", "active_kcal", "avg"),
        "exercise_min_avg": _safe_get(raw, "training", "exercise_min", "avg"),
        "total_distance_km": _safe_get(raw, "training", "total_distance_km"),
        "avg_tdee": _safe_get(raw, "energy", "avg_tdee"),
        "vo2_max": _safe_get(raw, "fitness", "vo2_max_current"),
        "vo2_max_prior": _safe_get(raw, "fitness", "vo2_max_prior"),
        "weight_kg_avg": _safe_get(raw, "body", "weight_kg", "avg"),
        "body_fat_pct_avg": _safe_get(raw, "body", "body_fat_pct", "avg"),
    }


def _delta(current: Any, previous: Any) -> dict[str, Any] | None:
    if current is None or previous is None:
        return None
    try:
        diff = round(float(current) - float(previous), 2)
        prev_f = float(previous)
        pct = round(diff / prev_f * 100, 1) if prev_f != 0 else None
        return {"diff": diff, "pct": pct}
    except (TypeError, ValueError):
        return None


def compute_deltas(
    weeks: list[HealthSnapshot],
    three_months_ago: HealthSnapshot | None,
) -> dict[str, Any]:
    """Compute structured deltas from a list of weekly snapshots (ascending order)."""
    current = _extract_metrics(weeks[-1].raw_data)
    prev = _extract_metrics(weeks[-2].raw_data) if len(weeks) >= 2 else {}

    rolling: dict[str, list[float]] = {}
    for w in weeks:
        for key, val in _extract_metrics(w.raw_data).items():
            if val is not None:
                try:
                    rolling.setdefault(key, []).append(float(val))
                except (TypeError, ValueError):
                    pass
    rolling_avg = {k: round(sum(v) / len(v), 2) for k, v in rolling.items() if v}

    three_mo = _extract_metrics(three_months_ago.raw_data) if three_months_ago else {}

    return {
        "current": current,
        "week_over_week": {k: _delta(current.get(k), prev.get(k)) for k in current},
        "rolling_4w_avg": rolling_avg,
        "vs_3_months_ago": {
            k: _delta(current.get(k), three_mo.get(k)) for k in current
        },
        "weeks_of_history": len(weeks),
    }


async def fetch_health_data(week_start: date) -> dict[str, Any]:
    week_end = week_start + timedelta(days=6)
    with _tracer.start_as_current_span(
        "fetch_health_data", kind=SpanKind.CLIENT
    ) as span:
        span.set_attribute("week_start", str(week_start))
        span.set_attribute("week_end", str(week_end))
        assert config.health_coach_endpoint_url is not None
        url = f"{config.health_coach_endpoint_url}/api/v1/health/summary"
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.get(
                url, params={"end_date": str(week_end), "summary_type": "week"}
            )
        response.raise_for_status()
    return response.json()  # type: ignore[no-any-return]


async def upsert_snapshot(
    session: AsyncSession, week_start: date, raw_data: dict[str, Any]
) -> None:
    week_end = week_start + timedelta(days=6)
    stmt = pg_insert(HealthSnapshot).values(
        week_start=week_start,
        week_end=week_end,
        raw_data=raw_data,
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["week_start"],
        set_={"raw_data": stmt.excluded.raw_data, "week_end": stmt.excluded.week_end},
    )
    await session.execute(stmt)


async def get_historical(
    session: AsyncSession, week_start: date
) -> tuple[list[HealthSnapshot], HealthSnapshot | None]:
    four_weeks_ago = week_start - timedelta(weeks=3)
    recent_rows = await session.execute(
        select(HealthSnapshot)
        .where(HealthSnapshot.week_start >= four_weeks_ago)
        .where(HealthSnapshot.week_start <= week_start)
        .order_by(HealthSnapshot.week_start)
    )
    recent = list(recent_rows.scalars().all())

    target_3mo = week_start - timedelta(weeks=13)
    three_mo_rows = await session.execute(
        select(HealthSnapshot)
        .where(HealthSnapshot.week_start >= target_3mo - timedelta(weeks=1))
        .where(HealthSnapshot.week_start <= target_3mo + timedelta(weeks=1))
    )
    candidates = list(three_mo_rows.scalars().all())
    three_months_ago = (
        min(candidates, key=lambda s: abs((s.week_start - target_3mo).days))
        if candidates
        else None
    )
    return recent, three_months_ago


async def upsert_analysis(
    session: AsyncSession, week_start: date, analysis_md: str
) -> None:
    stmt = pg_insert(HealthAnalysis).values(
        week_start=week_start, analysis_md=analysis_md
    )
    stmt = stmt.on_conflict_do_update(
        index_elements=["week_start"],
        set_={"analysis_md": stmt.excluded.analysis_md},
    )
    await session.execute(stmt)


async def call_llm(
    client: httpx.AsyncClient,
    week_start: date,
    metrics: dict[str, Any],
    deltas: dict[str, Any],
    workouts: list[dict[str, Any]],
) -> str:
    week_end = week_start + timedelta(days=6)
    system_content = render("health_analysis_system.j2", user=config.owner_name)
    user_content = render(
        "health_analysis_user.j2",
        user=config.owner_name,
        week_start=str(week_start),
        week_end=str(week_end),
        metrics=metrics,
        deltas=deltas,
        workouts=workouts,
    )
    payload = RawChatRequest(
        conversation_id=f"health_analyze|{week_start}",
        user_id="health_coach_job",
        messages=[
            Message(role="system", content=system_content),
            Message(role="user", content=user_content),
        ],
        llm_parameters=LLMSettings(
            mode="balanced",
            model=config.llm_model,
            enable_thinking=False,
            thinking_budget=0,
            temperature=0.3,
            max_tokens=2000,
        ),
    )
    with _tracer.start_as_current_span(
        "call_llm_analyze", kind=SpanKind.CLIENT
    ) as span:
        span.set_attribute("week_start", str(week_start))
        response = await client.post("/api/raw", json=payload.model_dump())
        response.raise_for_status()
    return response.json().get("content", "")  # type: ignore[no-any-return]


async def run(week_start: date) -> None:
    assert config.health_coach_endpoint_url is not None
    assert config.agent_core_api_url is not None

    with _tracer.start_as_current_span(
        "health_analyze", kind=SpanKind.INTERNAL
    ) as span:
        span.set_attribute("week_start", str(week_start))

        with _tracer.start_as_current_span("fetch_and_store_snapshot"):
            raw_data = await fetch_health_data(week_start)
            async with get_session() as session:
                await upsert_snapshot(session, week_start, raw_data)

        with _tracer.start_as_current_span("load_history"):
            async with get_session() as session:
                recent_weeks, three_months_ago = await get_historical(
                    session, week_start
                )

        if not recent_weeks:
            logger.error("health_analyze_no_history", week_start=str(week_start))
            return

        deltas = compute_deltas(recent_weeks, three_months_ago)
        workouts: list[dict[str, Any]] = (
            _safe_get(raw_data, "training", "workouts") or []
        )

        with _tracer.start_as_current_span("llm_analyze", kind=SpanKind.CLIENT):
            async with httpx.AsyncClient(
                base_url=config.agent_core_api_url, timeout=300.0
            ) as client:
                analysis_md = await call_llm(
                    client, week_start, deltas["current"], deltas, workouts
                )

        async with get_session() as session:
            await upsert_analysis(session, week_start, analysis_md)

        logger.info("health_analyze_stored", week_start=str(week_start))

        if config.ntfy_url:
            click = f"{config.mimir_host}/" if config.mimir_host else None
            await send_ntfy(
                url=config.ntfy_url,
                topic=config.ntfy_health_topic,
                message=f"Weekly health analysis ready — week of {week_start}",
                title="Mimir - Health Analysis",
                click_url=click,
                tags="chart_with_upwards_trend",
            )

        print(str(week_start))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Health coach analyze pod")
    parser.add_argument(
        "--week-start",
        type=str,
        default=None,
        help="ISO date (YYYY-MM-DD) of the Monday to analyze. Defaults to last completed week.",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    if not validate_config():
        return

    if args.week_start:
        try:
            week_start = date.fromisoformat(args.week_start)
        except ValueError as exc:
            logger.error(
                "health_analyze_invalid_date", date=args.week_start, error=str(exc)
            )
            return
    else:
        week_start = get_week_start(config.timezone or "UTC")

    async def _run() -> None:
        initialize_db(config.database_url)
        try:
            await run(week_start)
        except Exception as e:
            logger.error(
                "health_analyze_failed",
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
        finally:
            await dispose_db()

    asyncio.run(_run())


if __name__ == "__main__":
    main()
