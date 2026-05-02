"""Tests for shared/external/weather/weather.py"""

from unittest.mock import AsyncMock, MagicMock, mock_open, patch

import pytest


# ---------------------------------------------------------------------------
# _wind_direction_to_compass
# ---------------------------------------------------------------------------


def test_wind_direction_north():
    from shared.external.weather.weather import _wind_direction_to_compass

    assert _wind_direction_to_compass(0) == "N"


def test_wind_direction_east():
    from shared.external.weather.weather import _wind_direction_to_compass

    assert _wind_direction_to_compass(90) == "E"


def test_wind_direction_south():
    from shared.external.weather.weather import _wind_direction_to_compass

    assert _wind_direction_to_compass(180) == "S"


def test_wind_direction_west():
    from shared.external.weather.weather import _wind_direction_to_compass

    assert _wind_direction_to_compass(270) == "W"


def test_wind_direction_northeast():
    from shared.external.weather.weather import _wind_direction_to_compass

    assert _wind_direction_to_compass(45) == "NE"


def test_wind_direction_southeast():
    from shared.external.weather.weather import _wind_direction_to_compass

    assert _wind_direction_to_compass(135) == "SE"


def test_wind_direction_southwest():
    from shared.external.weather.weather import _wind_direction_to_compass

    assert _wind_direction_to_compass(225) == "SW"


def test_wind_direction_northwest():
    from shared.external.weather.weather import _wind_direction_to_compass

    assert _wind_direction_to_compass(315) == "NW"


def test_wind_direction_360_wraps_to_north():
    from shared.external.weather.weather import _wind_direction_to_compass

    assert _wind_direction_to_compass(360) == "N"


def test_wind_direction_nne():
    from shared.external.weather.weather import _wind_direction_to_compass

    assert _wind_direction_to_compass(23) == "NNE"


# ---------------------------------------------------------------------------
# _parse_forcast_data
# ---------------------------------------------------------------------------


def _make_forecast_payload(codes: list[int]) -> dict:
    return {
        "daily": {
            "time": ["2026-05-01", "2026-05-02", "2026-05-03"],
            "weather_code": codes,
            "temperature_2m_max": [22.0, 20.0, 18.0],
            "temperature_2m_min": [14.0, 12.0, 10.0],
        }
    }


def test_parse_forecast_translates_known_codes():
    from shared.external.weather.weather import _parse_forcast_data

    result = _parse_forcast_data(_make_forecast_payload([0, 1, 2]))
    assert result["daily"]["weather_code"] == [
        "Clear sky",
        "Mainly clear",
        "Partly cloudy",
    ]


def test_parse_forecast_unknown_code_becomes_unknown():
    from shared.external.weather.weather import _parse_forcast_data

    result = _parse_forcast_data(_make_forecast_payload([999]))
    assert result["daily"]["weather_code"] == ["Unknown"]


def test_parse_forecast_preserves_other_daily_fields():
    from shared.external.weather.weather import _parse_forcast_data

    result = _parse_forcast_data(_make_forecast_payload([0]))
    assert result["daily"]["temperature_2m_max"] == [22.0, 20.0, 18.0]
    assert result["daily"]["time"] == ["2026-05-01", "2026-05-02", "2026-05-03"]


def test_parse_forecast_returns_only_daily_key():
    from shared.external.weather.weather import _parse_forcast_data

    payload = _make_forecast_payload([0])
    payload["extra_key"] = "should be dropped"
    result = _parse_forcast_data(payload)
    assert "extra_key" not in result


# ---------------------------------------------------------------------------
# _parse_today_weather_data
# ---------------------------------------------------------------------------


def _make_today_payload(
    today: str = "2026-05-01",
    tomorrow: str = "2026-05-02",
) -> dict:
    return {
        "current": {
            "temperature_2m": 22.0,
            "wind_speed_10m": 15.0,
            "wind_direction_10m": 90,
            "wind_gusts_10m": 20.0,
            "precipitation": 0.0,
            "weather_code": 1,
            "rain": 0.0,
            "snowfall": 0.0,
        },
        "hourly": {
            "time": [
                f"{today}T00:00",
                f"{today}T01:00",
                f"{today}T02:00",
                f"{tomorrow}T00:00",
            ],
            "temperature_2m": [20.0, 21.0, 22.0, 18.0],
            "relative_humidity_2m": [60, 62, 64, 70],
            "apparent_temperature": [19.0, 20.0, 21.0, 17.0],
            "precipitation_probability": [10, 10, 20, 30],
            "precipitation": [0.0, 0.0, 0.1, 0.5],
            "rain": [0.0, 0.0, 0.1, 0.5],
            "snowfall": [0.0, 0.0, 0.0, 0.0],
            "weather_code": [0, 1, 3, 61],
            "cloud_cover": [10, 20, 50, 80],
            "wind_speed_10m": [10.0, 12.0, 15.0, 20.0],
            "wind_direction_10m": [0, 90, 180, 270],
            "wind_gusts_10m": [15.0, 18.0, 22.0, 30.0],
            "uv_index": [0.0, 1.0, 3.0, 0.0],
        },
    }


def test_parse_today_translates_current_weather_code():
    from shared.external.weather.weather import _parse_today_weather_data

    result = _parse_today_weather_data(_make_today_payload())
    assert result["current"]["weather_code"] == "Mainly clear"


def test_parse_today_translates_current_wind_direction():
    from shared.external.weather.weather import _parse_today_weather_data

    result = _parse_today_weather_data(_make_today_payload())
    assert result["current"]["wind_direction_10m"] == "E"


def test_parse_today_trims_hourly_to_today_only():
    from shared.external.weather.weather import _parse_today_weather_data

    result = _parse_today_weather_data(_make_today_payload())
    assert all(t.startswith("2026-05-01") for t in result["hourly"]["time"])
    assert len(result["hourly"]["time"]) == 3


def test_parse_today_translates_hourly_weather_codes():
    from shared.external.weather.weather import _parse_today_weather_data

    result = _parse_today_weather_data(_make_today_payload())
    assert result["hourly"]["weather_code"] == ["Clear sky", "Mainly clear", "Overcast"]


def test_parse_today_translates_hourly_wind_directions():
    from shared.external.weather.weather import _parse_today_weather_data

    result = _parse_today_weather_data(_make_today_payload())
    assert result["hourly"]["wind_direction_10m"] == ["N", "E", "S"]


def test_parse_today_all_hourly_keys_trimmed():
    from shared.external.weather.weather import _parse_today_weather_data

    result = _parse_today_weather_data(_make_today_payload())
    for key, values in result["hourly"].items():
        assert len(values) == 3, f"key '{key}' has {len(values)} entries, expected 3"


def test_parse_today_hourly_all_same_day_is_not_trimmed():
    from shared.external.weather.weather import _parse_today_weather_data

    payload = _make_today_payload()
    payload["hourly"]["time"] = ["2026-05-01T00:00", "2026-05-01T12:00"]
    for key in list(payload["hourly"].keys()):
        if key != "time":
            payload["hourly"][key] = payload["hourly"][key][:2]
    result = _parse_today_weather_data(payload)
    assert len(result["hourly"]["time"]) == 2


# ---------------------------------------------------------------------------
# _get_forecast (HTTP layer)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_forecast_returns_parsed_data_on_success():
    from shared.external.weather.weather import _get_forecast

    payload = {
        "daily": {
            "time": ["2026-05-01"],
            "weather_code": [0],
            "temperature_2m_max": [22.0],
            "temperature_2m_min": [14.0],
        }
    }
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = payload

    with patch(
        "shared.external.weather.weather._client.get",
        new=AsyncMock(return_value=mock_response),
    ):
        result = await _get_forecast(47.5, 19.0)

    assert result["daily"]["weather_code"] == ["Clear sky"]


@pytest.mark.asyncio
async def test_get_forecast_returns_empty_dict_on_http_error():
    import httpx

    from shared.external.weather.weather import _get_forecast

    with patch(
        "shared.external.weather.weather._client.get",
        new=AsyncMock(side_effect=httpx.HTTPError("timeout")),
    ):
        result = await _get_forecast(47.5, 19.0)

    assert result == {}


# ---------------------------------------------------------------------------
# _get_today_weather (HTTP layer)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_today_weather_returns_parsed_data_on_success():
    from shared.external.weather.weather import _get_today_weather

    payload = _make_today_payload()
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = payload

    with patch(
        "shared.external.weather.weather._client.get",
        new=AsyncMock(return_value=mock_response),
    ):
        result = await _get_today_weather(47.5, 19.0)

    assert result["current"]["weather_code"] == "Mainly clear"


@pytest.mark.asyncio
async def test_get_today_weather_returns_empty_dict_on_http_error():
    import httpx

    from shared.external.weather.weather import _get_today_weather

    with patch(
        "shared.external.weather.weather._client.get",
        new=AsyncMock(side_effect=httpx.HTTPError("timeout")),
    ):
        result = await _get_today_weather(47.5, 19.0)

    assert result == {}


# ---------------------------------------------------------------------------
# get_weather_data (integration of file + HTTP)
# ---------------------------------------------------------------------------

_SAMPLE_CONFIG = """
locations:
  - name: Budapest
    latitude: 47.5
    longitude: 19.0
"""

_FORECAST_PAYLOAD = {
    "daily": {
        "time": ["2026-05-01"],
        "weather_code": [0],
        "temperature_2m_max": [22.0],
        "temperature_2m_min": [14.0],
    }
}


@pytest.mark.asyncio
async def test_get_weather_data_returns_entry_per_location():
    from shared.external.weather.weather import get_weather_data

    with (
        patch("builtins.open", mock_open(read_data=_SAMPLE_CONFIG)),
        patch(
            "shared.external.weather.weather._get_forecast",
            new=AsyncMock(return_value={"daily": _FORECAST_PAYLOAD["daily"]}),
        ),
        patch(
            "shared.external.weather.weather._get_today_weather",
            new=AsyncMock(return_value={"current": {}, "hourly": {}}),
        ),
    ):
        result = await get_weather_data("dummy/path.yaml")

    assert "Budapest" in result


@pytest.mark.asyncio
async def test_get_weather_data_includes_coordinates():
    from shared.external.weather.weather import get_weather_data

    with (
        patch("builtins.open", mock_open(read_data=_SAMPLE_CONFIG)),
        patch(
            "shared.external.weather.weather._get_forecast",
            new=AsyncMock(return_value={}),
        ),
        patch(
            "shared.external.weather.weather._get_today_weather",
            new=AsyncMock(return_value={}),
        ),
    ):
        result = await get_weather_data("dummy/path.yaml")

    assert result["Budapest"]["coordinates"] == {"latitude": 47.5, "longitude": 19.0}


@pytest.mark.asyncio
async def test_get_weather_data_includes_units():
    from shared.external.weather.weather import get_weather_data

    with (
        patch("builtins.open", mock_open(read_data=_SAMPLE_CONFIG)),
        patch(
            "shared.external.weather.weather._get_forecast",
            new=AsyncMock(return_value={}),
        ),
        patch(
            "shared.external.weather.weather._get_today_weather",
            new=AsyncMock(return_value={}),
        ),
    ):
        result = await get_weather_data("dummy/path.yaml")

    assert result["Budapest"]["units"]["temperature"] == "°C"


@pytest.mark.asyncio
async def test_get_weather_data_multiple_locations():
    from shared.external.weather.weather import get_weather_data

    config = """
locations:
  - name: Budapest
    latitude: 47.5
    longitude: 19.0
  - name: Vienna
    latitude: 48.2
    longitude: 16.4
"""
    with (
        patch("builtins.open", mock_open(read_data=config)),
        patch(
            "shared.external.weather.weather._get_forecast",
            new=AsyncMock(return_value={}),
        ),
        patch(
            "shared.external.weather.weather._get_today_weather",
            new=AsyncMock(return_value={}),
        ),
    ):
        result = await get_weather_data("dummy/path.yaml")

    assert "Budapest" in result
    assert "Vienna" in result
