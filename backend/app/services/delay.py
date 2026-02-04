from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
import math

from backend.app.airports import Airport


@dataclass(frozen=True)
class DelayEstimate:
    # 0.0 (low) -> 1.0 (high)
    risk: float
    level: str
    rationale: list[str]
    source: str  # "historical-heuristic" (until you wire a real delay API)


def estimate_delay_risk(origin: Airport, destination: Airport, departure_day: date) -> DelayEstimate:
    rationale: list[str] = []

    month = departure_day.month
    base_by_month = {
        1: 0.55,  # winter weather + post-holiday
        2: 0.45,
        3: 0.35,
        4: 0.30,
        5: 0.35,
        6: 0.45,
        7: 0.60,  # summer peak
        8: 0.55,
        9: 0.40,
        10: 0.35,
        11: 0.50,  # thanksgiving travel
        12: 0.65,  # holidays
    }
    risk = base_by_month.get(month, 0.40)

    # Day-of-week pattern: Fri/Sun highest, Tue/Wed lowest (rough heuristic)
    dow = departure_day.weekday()  # Mon=0
    if dow in (4, 6):  # Fri, Sun
        risk += 0.10
        rationale.append("High-travel day of week (Fri/Sun) tends to run tighter on capacity.")
    elif dow in (1, 2):  # Tue, Wed
        risk -= 0.05
        rationale.append("Midweek travel (Tue/Wed) is often less congested.")

    holiday = _near_major_us_holiday(departure_day)
    if holiday:
        risk += 0.15
        rationale.append(f"Near {holiday}, airports often see heavier traffic and more knock-on delays.")

    # Route length proxy (longer routes have more chance of upstream delays propagating)
    distance_km = _haversine_km(origin.lat, origin.lon, destination.lat, destination.lon)
    if distance_km > 3500:
        risk += 0.06
        rationale.append("Long-haul routes can accumulate upstream delays over the day.")
    elif distance_km < 800:
        risk += 0.02

    risk = _clamp01(risk)

    level = "low" if risk < 0.33 else "medium" if risk < 0.66 else "high"
    if not rationale:
        rationale.append("Historical risk heuristic based on seasonality, weekday, holidays, and route length.")
    return DelayEstimate(risk=risk, level=level, rationale=rationale, source="historical-heuristic")


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _near_major_us_holiday(d: date) -> str | None:
    y = d.year
    candidates: list[tuple[str, date]] = [
        ("New Year's Day", date(y, 1, 1)),
        ("Independence Day", date(y, 7, 4)),
        ("Christmas", date(y, 12, 25)),
        ("Thanksgiving", _thanksgiving(y)),
        ("Memorial Day", _last_weekday_of_month(y, 5, weekday=0)),  # Monday
        ("Labor Day", _nth_weekday_of_month(y, 9, weekday=0, n=1)),  # Monday
    ]
    for name, holiday in candidates:
        if abs((d - holiday).days) <= 2:
            return name
    return None


def _thanksgiving(year: int) -> date:
    # 4th Thursday of November
    return _nth_weekday_of_month(year, 11, weekday=3, n=4)


def _nth_weekday_of_month(year: int, month: int, *, weekday: int, n: int) -> date:
    first = date(year, month, 1)
    days_until = (weekday - first.weekday()) % 7
    day = first + timedelta(days=days_until + 7 * (n - 1))
    return day


def _last_weekday_of_month(year: int, month: int, *, weekday: int) -> date:
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    last = next_month - timedelta(days=1)
    days_back = (last.weekday() - weekday) % 7
    return last - timedelta(days=days_back)
