import asyncio

import httpx
import yaml

_client = httpx.AsyncClient(
    timeout=10.0, base_url="https://api.open-meteo.com/v1/forecast"
)


_wmo_weather_codes = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Drizzle: Light intensity",
    53: "Drizzle: Moderate intensity",
    55: "Drizzle: Dense intensity",
    56: "Freezing Drizzle: Light intensity",
    57: "Freezing Drizzle: Dense intensity",
    61: "Rain: Slight intensity",
    63: "Rain: Moderate intensity",
    65: "Rain: Heavy intensity",
    66: "Freezing Rain: Light intensity",
    67: "Freezing Rain: Heavy intensity",
    71: "Snow fall: Slight intensity",
    73: "Snow fall: Moderate intensity",
    75: "Snow fall: Heavy intensity",
    77: "Snow grains",
    80: "Rain showers: Slight intensity",
    81: "Rain showers: Moderate intensity",
    82: "Rain showers: Violent intensity",
    85: "Snow showers slight",
    86: "Snow showers heavy",
    95: "Thunderstorm: Slight or moderate",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


def _wind_direction_to_compass(degrees: int) -> str:
    directions = [
        "N",
        "NNE",
        "NE",
        "ENE",
        "E",
        "ESE",
        "SE",
        "SSE",
        "S",
        "SSW",
        "SW",
        "WSW",
        "W",
        "WNW",
        "NW",
        "NNW",
    ]
    index = round(degrees / 22.5) % 16
    return directions[index]


def _parse_forcast_data(forecast: dict) -> dict:
    parsed_forecast = {"daily": forecast["daily"]}

    for i, code in enumerate(parsed_forecast["daily"]["weather_code"]):
        parsed_forecast["daily"]["weather_code"][i] = _wmo_weather_codes.get(
            code, "Unknown"
        )

    return parsed_forecast


async def _get_forecast(latitude: float, longitude: float) -> dict:
    try:
        response = await _client.get(
            "",
            params={
                "latitude": latitude,
                "longitude": longitude,
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,wind_speed_10m_max,wind_gusts_10m_max,uv_index_max,rain_sum,showers_sum,snowfall_sum,precipitation_probability_max",
                "timezone": "auto",
                "forecast_days": 7,
            },
            timeout=60,
        )
        response.raise_for_status()

        data = response.json()
        return _parse_forcast_data(data)
    except httpx.HTTPError as e:
        print(f"HTTP error occurred: {e}")
        return {}


def _parse_today_weather_data(weather: dict) -> dict:
    parsed_weather = {"current": weather["current"], "hourly": weather["hourly"]}

    parsed_weather["current"]["weather_code"] = _wmo_weather_codes.get(
        parsed_weather["current"]["weather_code"], "Unknown"
    )
    parsed_weather["current"]["wind_direction_10m"] = _wind_direction_to_compass(
        parsed_weather["current"]["wind_direction_10m"]
    )

    today = parsed_weather["hourly"]["time"][0][:10]  # "2026-05-01"
    cutoff = next(
        (
            i
            for i, t in enumerate(parsed_weather["hourly"]["time"])
            if not t.startswith(today)
        ),
        len(parsed_weather["hourly"]["time"]),
    )
    for key in parsed_weather["hourly"]:
        parsed_weather["hourly"][key] = parsed_weather["hourly"][key][:cutoff]

    for i, code in enumerate(parsed_weather["hourly"]["weather_code"]):
        parsed_weather["hourly"]["weather_code"][i] = _wmo_weather_codes.get(
            code, "Unknown"
        )

    for i, direction in enumerate(parsed_weather["hourly"]["wind_direction_10m"]):
        parsed_weather["hourly"]["wind_direction_10m"][i] = _wind_direction_to_compass(
            direction
        )

    return parsed_weather


async def _get_today_weather(latitude: float, longitude: float) -> dict:
    try:
        response = await _client.get(
            "",
            params={
                "latitude": latitude,
                "longitude": longitude,
                "current": "temperature_2m,wind_speed_10m,wind_direction_10m,wind_gusts_10m,precipitation,weather_code,rain,snowfall",
                "hourly": "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation_probability,precipitation,rain,snowfall,weather_code,cloud_cover,wind_speed_10m,wind_direction_10m,wind_gusts_10m,uv_index",
                "timezone": "auto",
                "forecast_hours": 24,
            },
            timeout=60,
        )
        response.raise_for_status()
        data = response.json()

        return _parse_today_weather_data(data)
    except httpx.HTTPError as e:
        print(f"HTTP error occurred: {e}")
        return {}


async def get_weather_data(config_path: str) -> dict:
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    weather_data = {}
    for location in config["locations"]:
        latitude = location["latitude"]
        longitude = location["longitude"]
        [forecast, today_weather] = await asyncio.gather(
            _get_forecast(latitude, longitude),
            _get_today_weather(latitude, longitude),
        )
        weather_data[location["name"]] = {
            "coordinates": {"latitude": latitude, "longitude": longitude},
            "forecast": forecast,
            "today_weather": today_weather,
            "units": {
                "temperature": "°C",
                "wind_speed": "km/h",
                "precipitation": "mm",
                "precipitation_probability": "%",
                "cloud_cover": "%",
                "uv_index": "index",
                "snowfall": "cm",
            },
        }

    return weather_data


if __name__ == "__main__":
    import asyncio

    weather_data = asyncio.run(get_weather_data("config/weather_config.yaml"))
    print(weather_data)
