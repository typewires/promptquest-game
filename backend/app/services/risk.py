from __future__ import annotations

from dataclasses import dataclass
import math
import re

from backend.app.services.amadeus import FlightOffer
from backend.app.services.delay import DelayEstimate
from backend.app.services.weather import DailyWeather


@dataclass(frozen=True)
class RiskResult:
    risk_score: int  # 0..100 (higher = worse)
    risk_level: str  # low/medium/high
    drivers: list[str]


def score_offer_risk(*, offer: FlightOffer, origin_weather: DailyWeather, dest_weather: DailyWeather, delay: DelayEstimate) -> RiskResult:
    weather_p, weather_drivers = _weather_disruption_probability(origin_weather, dest_weather)
    delay_p = delay.risk
    conn_p = _connection_disruption_probability(offer.stops)
    dur_p = _duration_disruption_probability(_duration_minutes(offer.duration))

    # Blend: weather dominates cancellations; delay dominates day-to-day disruption; connections add missed-connection risk.
    p = _clamp01(0.50 * weather_p + 0.35 * delay_p + 0.12 * conn_p + 0.03 * dur_p)

    score = int(round(100 * p))
    level = "low" if score < 30 else "medium" if score < 60 else "high"

    drivers = []
    drivers.extend(weather_drivers[:2])
    if offer.stops > 0:
        drivers.append(f"{offer.stops} connection(s) increases missed-connection risk.")
    if delay.level != "low":
        drivers.append(f"Historical delay risk looks {delay.level} for this date/route.")
    if not drivers:
        drivers.append("No major disruption signals from forecast + seasonal delay heuristic.")

    return RiskResult(risk_score=score, risk_level=level, drivers=drivers[:4])


def ranking_score(
    *,
    price_total: float,
    min_price: float,
    max_price: float,
    risk_score: int,
    preference: str,
) -> float:
    price_norm = 0.0 if max_price <= min_price else (price_total - min_price) / (max_price - min_price)
    risk_norm = risk_score / 100.0

    pref = (preference or "balanced").lower()
    if pref == "price":
        w_price, w_risk = 0.70, 0.30
    elif pref == "weather":
        w_price, w_risk = 0.30, 0.70
    else:  # balanced
        w_price, w_risk = 0.45, 0.55
    return (w_price * price_norm) + (w_risk * risk_norm)


def _weather_disruption_probability(origin: DailyWeather, dest: DailyWeather) -> tuple[float, list[str]]:
    origin_p, origin_drivers = _airport_weather_probability(origin, label="Departure")
    dest_p, dest_drivers = _airport_weather_probability(dest, label="Arrival")
    p = _clamp01(max(origin_p, dest_p) * 0.70 + (origin_p + dest_p) * 0.15)
    drivers = origin_drivers + dest_drivers
    return p, drivers


def _airport_weather_probability(w: DailyWeather, *, label: str) -> tuple[float, list[str]]:
    drivers: list[str] = []
    code = w.weather_code
    wind = w.wind_speed_max_mph or 0.0
    precip_prob = w.precipitation_probability_max
    precip_sum = w.precipitation_sum_mm

    base = 0.05
    if code in (95, 96, 99):
        base = 0.85
        drivers.append(f"{label}: thunderstorms can cause ground stops and reroutes.")
    elif code in (75, 86):
        base = 0.80
        drivers.append(f"{label}: heavy snow raises de-icing/closure risk.")
    elif code in (65, 82, 67):
        base = 0.65
        drivers.append(f"{label}: heavy precipitation increases delay/cancellation risk.")
    elif code in (45, 48):
        base = 0.55
        drivers.append(f"{label}: fog/low visibility can reduce arrival rates.")
    elif code in (73, 85):
        base = 0.50
        drivers.append(f"{label}: snow showers can slow turns and taxi.")
    elif code in (63, 81):
        base = 0.40
    elif code in (61, 80, 71):
        base = 0.25

    wind_boost = 0.0
    if wind >= 45:
        wind_boost = 0.20
        drivers.append(f"{label}: very strong winds can trigger operational constraints.")
    elif wind >= 35:
        wind_boost = 0.12
    elif wind >= 25:
        wind_boost = 0.06

    precip_boost = 0.0
    if precip_prob is not None:
        if precip_prob >= 80:
            precip_boost = 0.10
        elif precip_prob >= 60:
            precip_boost = 0.06
    elif precip_sum is not None:
        if precip_sum >= 15:
            precip_boost = 0.10
        elif precip_sum >= 7:
            precip_boost = 0.06

    return _clamp01(base + wind_boost + precip_boost), drivers


def _connection_disruption_probability(stops: int) -> float:
    if stops <= 0:
        return 0.05
    # one connection is a meaningful jump; further connections stack.
    return _clamp01(0.18 + 0.12 * (stops - 1))


def _duration_disruption_probability(minutes: int) -> float:
    if minutes <= 0:
        return 0.05
    # Longer flights tend to be later in the day and exposed to upstream delays.
    if minutes >= 360:
        return 0.18
    if minutes >= 240:
        return 0.12
    if minutes >= 150:
        return 0.08
    return 0.05


_DUR_RE = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?")


def _duration_minutes(iso_duration: str) -> int:
    m = _DUR_RE.fullmatch((iso_duration or "").strip())
    if not m:
        return 0
    hours = int(m.group(1) or 0)
    mins = int(m.group(2) or 0)
    return (hours * 60) + mins


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))
