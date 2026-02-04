from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Airport:
    iata: str
    name: str
    city: str
    lat: float
    lon: float


# Small built-in map for demo. Extend this (or swap to a real airport DB) for production.
_BUILTIN_AIRPORTS: dict[str, Airport] = {
    "JFK": Airport(
        iata="JFK",
        name="John F. Kennedy International",
        city="New York",
        lat=40.6413,
        lon=-73.7781,
    ),
    "LAX": Airport(
        iata="LAX",
        name="Los Angeles International",
        city="Los Angeles",
        lat=33.9416,
        lon=-118.4085,
    ),
    "SFO": Airport(iata="SFO", name="San Francisco International", city="San Francisco", lat=37.6213, lon=-122.3790),
    "ORD": Airport(iata="ORD", name="O'Hare International", city="Chicago", lat=41.9742, lon=-87.9073),
    "ATL": Airport(iata="ATL", name="Hartsfield–Jackson Atlanta International", city="Atlanta", lat=33.6407, lon=-84.4277),
    "DFW": Airport(iata="DFW", name="Dallas/Fort Worth International", city="Dallas", lat=32.8998, lon=-97.0403),
    "DEN": Airport(iata="DEN", name="Denver International", city="Denver", lat=39.8561, lon=-104.6737),
    "SEA": Airport(iata="SEA", name="Seattle–Tacoma International", city="Seattle", lat=47.4502, lon=-122.3088),
    "MIA": Airport(iata="MIA", name="Miami International", city="Miami", lat=25.7959, lon=-80.2870),
    "BOS": Airport(iata="BOS", name="Logan International", city="Boston", lat=42.3656, lon=-71.0096),
}


def resolve_airport(iata: str) -> Airport | None:
    code = (iata or "").strip().upper()
    if len(code) != 3:
        return None
    return _BUILTIN_AIRPORTS.get(code)
