from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any, Optional

import requests

from backend.app.cache import TTLCache


@dataclass(frozen=True)
class FlightSegment:
    carrier_code: str
    flight_number: str | None
    departure_iata: str
    departure_at: str
    arrival_iata: str
    arrival_at: str


@dataclass(frozen=True)
class FlightOffer:
    id: str
    price_total: float
    currency: str
    duration: str
    stops: int
    segments: list[FlightSegment]

    # convenience fields
    primary_carrier: str
    departure_at: str
    arrival_at: str


class AmadeusClient:
    def __init__(self, *, host: str, client_id: str, client_secret: str, cache: TTLCache[Any]) -> None:
        self.host = host
        self.client_id = client_id
        self.client_secret = client_secret
        self.cache = cache

    def _token(self) -> str:
        cached = self.cache.get("amadeus_token")
        if isinstance(cached, str) and cached:
            return cached

        token_url = f"https://{self.host}/v1/security/oauth2/token"
        data = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        resp = requests.post(token_url, headers=headers, data=data, timeout=15)
        resp.raise_for_status()
        payload = resp.json()

        token = payload.get("access_token")
        expires_in = int(payload.get("expires_in", 1800))
        if not token:
            raise RuntimeError("Amadeus auth failed: missing access_token")

        ttl = max(30, expires_in - 30)
        self.cache.set("amadeus_token", token, ttl_seconds=ttl)
        return token

    def search_flights(
        self,
        *,
        origin: str,
        destination: str,
        departure_date: date,
        adults: int = 1,
        travel_class: str = "ECONOMY",
        currency: str = "USD",
        max_results: int = 25,
        prefer_nonstop: bool = True,
    ) -> list[FlightOffer]:
        cache_key = (
            "amadeus_flights",
            origin.upper(),
            destination.upper(),
            departure_date.isoformat(),
            adults,
            travel_class,
            currency,
            max_results,
            prefer_nonstop,
        )
        cached = self.cache.get(cache_key)
        if isinstance(cached, list) and cached:
            return cached

        url = f"https://{self.host}/v2/shopping/flight-offers"
        headers = {"Authorization": f"Bearer {self._token()}"}

        params: dict[str, Any] = {
            "originLocationCode": origin.upper(),
            "destinationLocationCode": destination.upper(),
            "departureDate": departure_date.isoformat(),
            "adults": adults,
            "currencyCode": currency,
            "max": max_results,
        }
        if travel_class:
            params["travelClass"] = travel_class
        if prefer_nonstop:
            params["nonStop"] = "true"

        resp = requests.get(url, headers=headers, params=params, timeout=20)
        resp.raise_for_status()
        data = (resp.json() or {}).get("data") or []

        offers = [_parse_offer(o) for o in data]
        offers = [o for o in offers if o is not None]
        offers_sorted = sorted(offers, key=lambda o: (o.stops, o.price_total))

        self.cache.set(cache_key, offers_sorted, ttl_seconds=300)
        return offers_sorted

    def lookup_airport(self, *, iata: str) -> dict[str, Any] | None:
        code = (iata or "").strip().upper()
        if len(code) != 3:
            return None

        cache_key = ("amadeus_airport", code)
        cached = self.cache.get(cache_key)
        if isinstance(cached, dict) and cached.get("iata") == code:
            return cached

        url = f"https://{self.host}/v1/reference-data/locations"
        headers = {"Authorization": f"Bearer {self._token()}"}
        params = {"subType": "AIRPORT", "keyword": code, "page[limit]": 10}
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        resp.raise_for_status()

        data = (resp.json() or {}).get("data") or []
        best = None
        for item in data:
            if str(item.get("iataCode") or "").upper() == code:
                best = item
                break
        if not best and data:
            best = data[0]
        if not best:
            return None

        geo = best.get("geoCode") or {}
        lat = geo.get("latitude")
        lon = geo.get("longitude")
        if lat is None or lon is None:
            return None

        address = best.get("address") or {}
        result = {
            "iata": code,
            "name": str(best.get("name") or code),
            "city": str(address.get("cityName") or address.get("cityCode") or code),
            "lat": float(lat),
            "lon": float(lon),
            "source": "amadeus",
        }
        self.cache.set(cache_key, result, ttl_seconds=86400)
        return result


def build_google_flights_link(
    *,
    origin: str,
    destination: str,
    departure_date: date,
    adults: int = 1,
    travel_class: str = "ECONOMY",
) -> str:
    cabin = travel_class.upper()
    # Simple and resilient: a query URL rather than trying to deep-link into an opaque UI state.
    q = f"Flights from {origin.upper()} to {destination.upper()} on {departure_date.isoformat()} for {adults} adults {cabin}"
    return f"https://www.google.com/travel/flights?q={requests.utils.quote(q)}"


def _parse_offer(raw: dict[str, Any]) -> Optional[FlightOffer]:
    try:
        offer_id = str(raw.get("id") or "")
        price_total = float(((raw.get("price") or {}).get("total")) or 0)
        currency = str(((raw.get("price") or {}).get("currency")) or "USD")
        itineraries = raw.get("itineraries") or []
        if not itineraries:
            return None
        first_itin = itineraries[0] or {}
        duration = str(first_itin.get("duration") or "")
        segments_raw = (first_itin.get("segments") or [])
        if not segments_raw:
            return None
        segments: list[FlightSegment] = []
        for seg in segments_raw:
            carrier = str(seg.get("carrierCode") or "")
            number = str(seg.get("number") or "") or None
            dep = seg.get("departure") or {}
            arr = seg.get("arrival") or {}
            segments.append(
                FlightSegment(
                    carrier_code=carrier,
                    flight_number=number,
                    departure_iata=str(dep.get("iataCode") or ""),
                    departure_at=str(dep.get("at") or ""),
                    arrival_iata=str(arr.get("iataCode") or ""),
                    arrival_at=str(arr.get("at") or ""),
                )
            )

        stops = max(0, len(segments) - 1)
        primary_carrier = segments[0].carrier_code
        return FlightOffer(
            id=offer_id,
            price_total=price_total,
            currency=currency,
            duration=duration,
            stops=stops,
            segments=segments,
            primary_carrier=primary_carrier,
            departure_at=segments[0].departure_at,
            arrival_at=segments[-1].arrival_at,
        )
    except Exception:
        return None
