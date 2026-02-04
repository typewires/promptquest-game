from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Literal

import requests


# Open-Meteo weather code map
WEATHER_CODES: dict[int, str] = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}


@dataclass(frozen=True)
class DailyWeather:
    source: Literal["forecast", "historical"]
    day: date
    weather_code: int | None
    condition: str
    temp_max_f: float | None
    temp_min_f: float | None
    precipitation_probability_max: float | None
    precipitation_sum_mm: float | None
    wind_speed_max_mph: float | None


def _c_to_f(temp_c: float) -> float:
    return (temp_c * 9 / 5) + 32


def _mps_to_mph(speed_mps: float) -> float:
    return speed_mps * 2.23694


def choose_weather_source(target_day: date, *, max_forecast_days: int = 14) -> Literal["forecast", "historical"]:
    today = date.today()
    if today <= target_day <= today + timedelta(days=max_forecast_days):
        return "forecast"
    return "historical"


def fetch_daily_weather(lat: float, lon: float, target_day: date) -> DailyWeather:
    source = choose_weather_source(target_day)

    if source == "forecast":
        url = "https://api.open-meteo.com/v1/forecast"
        params: dict[str, Any] = {
            "latitude": lat,
            "longitude": lon,
            "timezone": "auto",
            "start_date": target_day.isoformat(),
            "end_date": target_day.isoformat(),
            "daily": ",".join(
                [
                    "weather_code",
                    "temperature_2m_max",
                    "temperature_2m_min",
                    "precipitation_probability_max",
                    "wind_speed_10m_max",
                ]
            ),
        }
    else:
        url = "https://archive-api.open-meteo.com/v1/archive"
        params = {
            "latitude": lat,
            "longitude": lon,
            "timezone": "auto",
            "start_date": target_day.isoformat(),
            "end_date": target_day.isoformat(),
            "daily": ",".join(
                [
                    "weather_code",
                    "temperature_2m_max",
                    "temperature_2m_min",
                    "precipitation_sum",
                    "wind_speed_10m_max",
                ]
            ),
        }

    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    payload = resp.json()
    daily = payload.get("daily") or {}

    code_val = _first(daily.get("weather_code"))
    temp_max_c = _first(daily.get("temperature_2m_max"))
    temp_min_c = _first(daily.get("temperature_2m_min"))
    precip_prob = _first(daily.get("precipitation_probability_max"))
    precip_sum = _first(daily.get("precipitation_sum"))
    wind_max = _first(daily.get("wind_speed_10m_max"))

    condition = WEATHER_CODES.get(int(code_val), "Unknown") if code_val is not None else "Unknown"
    return DailyWeather(
        source=source,
        day=target_day,
        weather_code=int(code_val) if code_val is not None else None,
        condition=condition,
        temp_max_f=_c_to_f(float(temp_max_c)) if temp_max_c is not None else None,
        temp_min_f=_c_to_f(float(temp_min_c)) if temp_min_c is not None else None,
        precipitation_probability_max=float(precip_prob) if precip_prob is not None else None,
        precipitation_sum_mm=float(precip_sum) if precip_sum is not None else None,
        wind_speed_max_mph=_mps_to_mph(float(wind_max)) if wind_max is not None else None,
    )


def fetch_current_weather(lat: float, lon: float) -> dict[str, Any]:
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "timezone": "auto",
        "current": ",".join(["temperature_2m", "weather_code", "wind_speed_10m"]),
    }
    resp = requests.get(url, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    current = data.get("current") or {}

    code_val = current.get("weather_code")
    condition = WEATHER_CODES.get(int(code_val), "Unknown") if code_val is not None else "Unknown"
    temp_c = current.get("temperature_2m")
    wind_mps = current.get("wind_speed_10m")
    return {
        "temperature_f": _c_to_f(float(temp_c)) if temp_c is not None else None,
        "condition": condition,
        "wind_speed_mph": _mps_to_mph(float(wind_mps)) if wind_mps is not None else None,
        "weather_code": int(code_val) if code_val is not None else None,
    }


def _first(value: Any) -> Any:
    if isinstance(value, list) and value:
        return value[0]
    return value
