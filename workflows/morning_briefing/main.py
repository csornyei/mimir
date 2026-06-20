import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Literal, cast
from zoneinfo import ZoneInfo

import httpx
import yaml
from opentelemetry import trace
from opentelemetry.trace import SpanKind, StatusCode

from workflows.config import workflow_config as job_config
from workflows.morning_briefing.prompt import build_morning_prompt
from shared.external.caldav.client import CalDAVClient
from shared.external.ntfy import send_ntfy
from shared.external.weather.weather import get_weather_data
from shared.logger import logger
from shared.schemas import LLMSettings, Message, RawChatRequest
from shared.telemetry import setup_tracing

setup_tracing(service_name=job_config.service_name)

_tracer = trace.get_tracer("mimir.jobs.morning_briefing")

_VALID_MODES: frozenset[str] = frozenset({"precise", "balanced", "creative", "fast"})


def validate_config() -> bool:
    required: dict[str, object] = {
        "timezone": job_config.timezone,
        "caldav_url": job_config.caldav_url,
        "caldav_username": job_config.caldav_username,
        "caldav_password": job_config.caldav_password,
        "weather_config_path": job_config.weather_config_path,
        "llm_model": job_config.llm_model,
        "llm_presets_path": job_config.llm_presets_path,
        "ntfy_url": job_config.ntfy_url,
        "ntfy_morning_brief_topic": job_config.ntfy_morning_brief_topic,
        "mimir_host": job_config.mimir_host,
        "agent_core_api_url": job_config.agent_core_api_url,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        logger.warning(
            "morning_briefing_skipped",
            reason=f"Missing required config fields: {', '.join(missing)}",
        )
        return False
    return True


async def get_calendar_data(
    start: datetime, end: datetime
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    with _tracer.start_as_current_span(
        "fetch_calendar_data", kind=SpanKind.INTERNAL
    ) as span:
        span.set_attribute("caldav_url", job_config.caldav_url or "none")
        span.set_attribute(
            "events_time_range", f"{start.isoformat()} to {end.isoformat()}"
        )
        client = CalDAVClient(
            url=job_config.caldav_url,
            username=job_config.caldav_username,
            password=job_config.caldav_password,
        )
        try:
            results = await asyncio.gather(
                client.get_events(start, end), client.get_todos(end)
            )

            return results[0], results[1]
        except Exception as e:
            span.set_status(StatusCode.ERROR, str(e))
            logger.error(
                "calendar_data_fetch_failed",
                error=str(e),
                error_type=type(e).__name__,
                exc_info=True,
            )
            return [], []


async def get_weather() -> dict[str, Any]:
    with _tracer.start_as_current_span(
        "fetch_weather_data", kind=SpanKind.INTERNAL
    ) as span:
        span.set_attribute(
            "weather_config_path", job_config.weather_config_path or "none"
        )
        config_path = job_config.weather_config_path
        if config_path is not None:
            try:
                return await get_weather_data(config_path)
            except Exception as e:
                span.set_status(StatusCode.ERROR, str(e))
                logger.error(
                    "weather_data_fetch_failed",
                    error=str(e),
                    error_type=type(e).__name__,
                    exc_info=True,
                )
        return {}


def prepare_llm_settings() -> LLMSettings:
    presets = yaml.safe_load(Path(job_config.llm_presets_path).read_text())

    if not isinstance(presets, dict):
        raise ValueError(
            f"Presets file {job_config.llm_presets_path} is empty or not a YAML mapping"
        )

    if "presets" not in presets:
        raise ValueError(f"No presets found in {job_config.llm_presets_path}")

    available_presets: dict[str, Any] = presets["presets"]
    default_preset = presets.get("default_preset", "balanced")
    preset_name = "fast" if "fast" in available_presets else default_preset

    if preset_name not in available_presets:
        raise ValueError(
            f"Preset '{preset_name}' not found in {job_config.llm_presets_path}."
            f" Available: {list(available_presets)}"
        )

    preset = available_presets[preset_name]

    if preset_name not in _VALID_MODES:
        logger.warning(
            "morning_briefing_preset_mode_fallback",
            preset=preset_name,
            fallback_mode="balanced",
        )
    raw_mode = preset_name if preset_name in _VALID_MODES else "balanced"
    mode = cast(Literal["precise", "balanced", "creative", "fast"], raw_mode)

    return LLMSettings(
        mode=mode,
        model=job_config.llm_model,
        enable_thinking=preset.get("enable_thinking", False),
        thinking_budget=preset.get("thinking_budget", 0),
        temperature=preset.get("temperature", 0.5),
        top_p=preset.get("top_p", 1.0),
        min_p=preset.get("min_p", 0.05),
        repetition_penalty=preset.get("repetition_penalty", 1.0),
        max_tokens=preset.get("max_tokens", 1000),
    )


async def send_notification(date: str) -> None:
    with _tracer.start_as_current_span("send_notification", kind=SpanKind.CLIENT):
        click = f"{job_config.mimir_host}/brief" if job_config.mimir_host else None

        if not job_config.ntfy_url or not job_config.ntfy_morning_brief_topic:
            logger.warning(
                "morning_briefing_notification_skipped",
                reason="Missing ntfy_url or ntfy_morning_brief_topic in config",
            )
            return
        await send_ntfy(
            url=job_config.ntfy_url,
            topic=job_config.ntfy_morning_brief_topic,
            message=f"Mimir: your morning brief for {date} is ready",
            title="Mimir - Morning Brief",
            click_url=click,
            tags="sunrise_over_mountains",
        )


async def run_morning_briefing() -> None:
    if not validate_config():
        return

    logger.info("morning_briefing_started")

    try:
        assert job_config.timezone is not None  # guaranteed by validate_config()
        tz = ZoneInfo(job_config.timezone)
        now = datetime.now(tz)
        today_date = now.date().isoformat()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        events, todos = await get_calendar_data(today_start, today_end)

        weather_data = await get_weather()

        conversation_id = f"morning|{today_date}"

        logger.info(
            "morning_briefing_data_fetched",
            events_count=len(events),
            todos_count=len(todos),
            weather_data_available=bool(weather_data),
        )

        messages = build_morning_prompt(
            user=job_config.owner_name,
            events=events,
            weather_data=weather_data,
            todos=todos,
        )

        llm_parameters = prepare_llm_settings()

        payload = RawChatRequest(
            conversation_id=conversation_id,
            user_id="morning_briefing_job",
            messages=[Message(**m) for m in messages],
            llm_parameters=llm_parameters,
        )

        with _tracer.start_as_current_span(
            "call_agent_core_api", kind=SpanKind.CLIENT
        ) as span:
            assert (
                job_config.agent_core_api_url is not None
            )  # guaranteed by validate_config()
            span.set_attribute("agent_core_api_url", job_config.agent_core_api_url)
            try:
                async with httpx.AsyncClient(
                    base_url=job_config.agent_core_api_url, timeout=300.0
                ) as client:
                    response = await client.post("/api/raw", json=payload.model_dump())
                response.raise_for_status()
            except Exception as e:
                span.set_status(StatusCode.ERROR, str(e))
                raise

        logger.info(
            "morning_briefing_persisted",
            conversation_id=conversation_id,
        )

        await send_notification(today_date)

    except Exception as e:
        logger.error(
            "morning_briefing_failed",
            error=str(e),
            error_type=type(e).__name__,
            exc_info=True,
        )


if __name__ == "__main__":
    asyncio.run(run_morning_briefing())
