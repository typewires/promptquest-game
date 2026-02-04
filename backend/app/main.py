from __future__ import annotations

import asyncio
from dataclasses import asdict, dataclass
from datetime import date, datetime
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.app.airports import Airport, resolve_airport
from backend.app.cache import TTLCache
from backend.app.config import settings
from backend.app.services.amadeus import AmadeusClient, build_google_flights_link
from backend.app.services.delay import DelayEstimate, estimate_delay_risk
from backend.app.services.risk import RiskResult, ranking_score, score_offer_risk
from backend.app.services.summarize import summarize_with_openai
from backend.app.services.weather import DailyWeather, fetch_current_weather, fetch_daily_weather


APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"


app = FastAPI(title="Flight Risk Advisor", version="0.1.0")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


cache: TTLCache[Any] = TTLCache(default_ttl_seconds=settings.cache_ttl_seconds)


def _get_amadeus() -> AmadeusClient:
    if not settings.amadeus_client_id or not settings.amadeus_client_secret:
        raise HTTPException(status_code=400, detail="Missing Amadeus credentials (AMADEUS_CLIENT_ID/SECRET).")
    return AmadeusClient(
        host=settings.amadeus_host,
        client_id=settings.amadeus_client_id,
        client_secret=settings.amadeus_client_secret,
        cache=cache,
    )


class WeatherRequest(BaseModel):
    origin: str = Field(..., min_length=3, max_length=3)
    destination: str = Field(..., min_length=3, max_length=3)
    departure_date: str = Field(..., description="YYYY-MM-DD")


class PricesRequest(BaseModel):
    origin: str = Field(..., min_length=3, max_length=3)
    destination: str = Field(..., min_length=3, max_length=3)
    departure_date: str
    adults: int = Field(1, ge=1, le=9)
    travel_class: str = "ECONOMY"
    currency: str = "USD"
    max_results: int = Field(25, ge=1, le=250)
    prefer_nonstop: bool = True


class DelaysRequest(BaseModel):
    origin: str = Field(..., min_length=3, max_length=3)
    destination: str = Field(..., min_length=3, max_length=3)
    departure_date: str


class AnalyzeRequest(BaseModel):
    origin: str = Field(..., min_length=3, max_length=3)
    destination: str = Field(..., min_length=3, max_length=3)
    departure_date: str
    adults: int = Field(1, ge=1, le=9)
    travel_class: str = "ECONOMY"
    currency: str = "USD"
    preference: str = Field("balanced", description="balanced|price|weather")
    max_results: int = Field(40, ge=5, le=250)
    prefer_nonstop: bool = True


@app.get("/")
def index() -> FileResponse:
    return FileResponse(str(STATIC_DIR / "index.html"))


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


def _require_airport(code: str) -> Airport:
    airport = resolve_airport(code)
    if airport:
        return airport

    # Fallback: use Amadeus airport lookup (still "the same APIs" and works for many IATA codes).
    if settings.amadeus_client_id and settings.amadeus_client_secret:
        try:
            amadeus = _get_amadeus()
            found = amadeus.lookup_airport(iata=code)
            if found:
                return Airport(iata=found["iata"], name=found["name"], city=found["city"], lat=found["lat"], lon=found["lon"])
        except Exception:
            # If lookup fails, fall through to a 404 with a clear message.
            pass

    raise HTTPException(status_code=404, detail=f"Unknown airport code: {code}")


def _parse_day(day_str: str) -> date:
    try:
        return date.fromisoformat(day_str)
    except Exception:
        raise HTTPException(status_code=400, detail="departure_date must be YYYY-MM-DD")


def _fmt0(v: Any) -> str:
    try:
        return f"{float(v):.0f}"
    except Exception:
        return "—"


def _cached_weather(airport: Airport, day: date) -> dict[str, Any]:
    key = ("daily_weather", airport.iata, day.isoformat())

    def compute() -> dict[str, Any]:
        daily = fetch_daily_weather(airport.lat, airport.lon, day)
        current = fetch_current_weather(airport.lat, airport.lon)
        return {"airport": asdict(airport), "daily": asdict(daily), "current": current}

    return cache.get_or_set(key, compute, ttl_seconds=600)


@app.post("/api/weather")
def weather(req: WeatherRequest) -> dict[str, Any]:
    day = _parse_day(req.departure_date)
    origin = _require_airport(req.origin)
    dest = _require_airport(req.destination)

    origin_weather = _cached_weather(origin, day)
    dest_weather = _cached_weather(dest, day)

    prompt = (
        "You are a helpful travel assistant. Summarize flight-relevant weather for the given trip.\n\n"
        f"Departure airport: {origin.name} ({origin.iata}), {origin.city}\n"
        f"Date: {day.isoformat()}\n"
        f"Forecast/Historical: {origin_weather['daily']['source']}\n"
        f"Conditions: {origin_weather['daily']['condition']}\n"
        f"Temp (F): {origin_weather['daily']['temp_min_f']}–{origin_weather['daily']['temp_max_f']}\n"
        f"Wind max (mph): {origin_weather['daily']['wind_speed_max_mph']}\n"
        f"Precip prob max (%): {origin_weather['daily']['precipitation_probability_max']}\n"
        f"Precip sum (mm): {origin_weather['daily']['precipitation_sum_mm']}\n\n"
        f"Arrival airport: {dest.name} ({dest.iata}), {dest.city}\n"
        f"Date: {day.isoformat()}\n"
        f"Forecast/Historical: {dest_weather['daily']['source']}\n"
        f"Conditions: {dest_weather['daily']['condition']}\n"
        f"Temp (F): {dest_weather['daily']['temp_min_f']}–{dest_weather['daily']['temp_max_f']}\n"
        f"Wind max (mph): {dest_weather['daily']['wind_speed_max_mph']}\n"
        f"Precip prob max (%): {dest_weather['daily']['precipitation_probability_max']}\n"
        f"Precip sum (mm): {dest_weather['daily']['precipitation_sum_mm']}\n\n"
        "Return 2–4 short sentences. Mention anything that could cause disruption."
    )
    llm = summarize_with_openai(openai_api_key=settings.openai_api_key, model=settings.openai_model, prompt=prompt)
    fallback = (
        f"Departure ({origin.iata}) looks like {origin_weather['daily']['condition']} "
        f"with highs around {_fmt0(origin_weather['daily']['temp_max_f'])}°F and winds up to {_fmt0(origin_weather['daily']['wind_speed_max_mph'])} mph. "
        f"Arrival ({dest.iata}) looks like {dest_weather['daily']['condition']} "
        f"with highs around {_fmt0(dest_weather['daily']['temp_max_f'])}°F and winds up to {_fmt0(dest_weather['daily']['wind_speed_max_mph'])} mph."
    )

    return {"origin": origin_weather, "destination": dest_weather, "summary": llm.get("text") or fallback}


@app.post("/api/delays")
def delays(req: DelaysRequest) -> dict[str, Any]:
    day = _parse_day(req.departure_date)
    origin = _require_airport(req.origin)
    dest = _require_airport(req.destination)

    estimate = estimate_delay_risk(origin, dest, day)

    prompt = (
        "You are a helpful travel assistant. Summarize expected delay risk for the given route/date.\n\n"
        f"Route: {origin.iata} → {dest.iata}\n"
        f"Date: {day.isoformat()}\n"
        f"Delay risk (0-1): {estimate.risk}\n"
        f"Level: {estimate.level}\n"
        f"Signals: {estimate.rationale}\n\n"
        "Return 2–3 short sentences. Be clear this is an estimate if real-time delay data isn't available."
    )
    llm = summarize_with_openai(openai_api_key=settings.openai_api_key, model=settings.openai_model, prompt=prompt)
    fallback = (
        f"Estimated delay risk is {estimate.level} ({estimate.risk:.2f}) based on seasonal/weekday/holiday heuristics. "
        f"Key signals: {', '.join(estimate.rationale[:2])}"
    )
    return {"delay": asdict(estimate), "summary": llm.get("text") or fallback}


@app.post("/api/prices")
def prices(req: PricesRequest) -> dict[str, Any]:
    day = _parse_day(req.departure_date)
    origin = _require_airport(req.origin)
    dest = _require_airport(req.destination)

    amadeus = _get_amadeus()
    offers = amadeus.search_flights(
        origin=origin.iata,
        destination=dest.iata,
        departure_date=day,
        adults=req.adults,
        travel_class=req.travel_class,
        currency=req.currency,
        max_results=req.max_results,
        prefer_nonstop=req.prefer_nonstop,
    )

    simplified = []
    for o in offers[:10]:
        simplified.append(
            {
                "id": o.id,
                "primary_carrier": o.primary_carrier,
                "duration": o.duration,
                "stops": o.stops,
                "price_total": o.price_total,
                "currency": o.currency,
                "departure_at": o.departure_at,
                "arrival_at": o.arrival_at,
                "purchase_link": build_google_flights_link(
                    origin=origin.iata,
                    destination=dest.iata,
                    departure_date=day,
                    adults=req.adults,
                    travel_class=req.travel_class,
                ),
            }
        )

    prompt = (
        "You are a helpful travel assistant. Summarize pricing options.\n\n"
        f"Route: {origin.iata} → {dest.iata}\n"
        f"Date: {day.isoformat()}\n"
        f"Top offers: {simplified}\n\n"
        "Return 2–4 short sentences: price range, nonstop vs stops, and any notable trade-offs."
    )
    llm = summarize_with_openai(openai_api_key=settings.openai_api_key, model=settings.openai_model, prompt=prompt)
    if simplified:
        low = min(o["price_total"] for o in simplified)
        high = max(o["price_total"] for o in simplified)
        fallback = f"Prices range from about {low:.0f}–{high:.0f} {req.currency} across the top results."
    else:
        fallback = "No flight offers found for these inputs."
    return {"offers": simplified, "summary": llm.get("text") or fallback}


def _offer_to_public_dict(o: Any, *, purchase_link: str, risk: RiskResult, why: str | None = None) -> dict[str, Any]:
    return {
        "id": o.id,
        "primary_carrier": o.primary_carrier,
        "duration": o.duration,
        "stops": o.stops,
        "price_total": o.price_total,
        "currency": o.currency,
        "departure_at": o.departure_at,
        "arrival_at": o.arrival_at,
        "purchase_link": purchase_link,
        "risk": asdict(risk),
        "why": why,
    }


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest) -> dict[str, Any]:
    day = _parse_day(req.departure_date)
    origin = _require_airport(req.origin)
    dest = _require_airport(req.destination)

    # Weather (cached)
    origin_weather = _cached_weather(origin, day)
    dest_weather = _cached_weather(dest, day)
    origin_daily = DailyWeather(**origin_weather["daily"])
    dest_daily = DailyWeather(**dest_weather["daily"])

    # Delays (heuristic for now)
    delay_est = estimate_delay_risk(origin, dest, day)

    # Prices / offers
    amadeus = _get_amadeus()
    offers = amadeus.search_flights(
        origin=origin.iata,
        destination=dest.iata,
        departure_date=day,
        adults=req.adults,
        travel_class=req.travel_class,
        currency=req.currency,
        max_results=req.max_results,
        prefer_nonstop=req.prefer_nonstop,
    )
    if not offers and req.prefer_nonstop:
        offers = amadeus.search_flights(
            origin=origin.iata,
            destination=dest.iata,
            departure_date=day,
            adults=req.adults,
            travel_class=req.travel_class,
            currency=req.currency,
            max_results=req.max_results,
            prefer_nonstop=False,
        )

    if not offers:
        return {
            "origin": origin.iata,
            "destination": dest.iata,
            "departure_date": day.isoformat(),
            "request": req.model_dump(),
            "weather": {"origin": origin_weather, "destination": dest_weather},
            "delay": asdict(delay_est),
            "flights": [],
            "summary": {"overview": "No flights found."},
        }

    min_price = min(o.price_total for o in offers)
    max_price = max(o.price_total for o in offers)
    purchase_link = build_google_flights_link(
        origin=origin.iata,
        destination=dest.iata,
        departure_date=day,
        adults=req.adults,
        travel_class=req.travel_class,
    )

    # Score + rank
    scored: list[tuple[float, Any, RiskResult]] = []
    for o in offers:
        risk = score_offer_risk(
            offer=o,
            origin_weather=origin_daily,
            dest_weather=dest_daily,
            delay=delay_est,
        )
        score = ranking_score(
            price_total=o.price_total,
            min_price=min_price,
            max_price=max_price,
            risk_score=risk.risk_score,
            preference=req.preference,
        )
        scored.append((score, o, risk))
    scored.sort(key=lambda t: t[0])
    top = scored[:5]

    # One OpenAI call to produce per-flight "why" plus an overview (JSON).
    flights_for_prompt = []
    for _, o, risk in top:
        flights_for_prompt.append(
            {
                "id": o.id,
                "carrier": o.primary_carrier,
                "duration": o.duration,
                "stops": o.stops,
                "price_total": o.price_total,
                "currency": o.currency,
                "risk_level": risk.risk_level,
                "risk_score": risk.risk_score,
                "drivers": risk.drivers,
            }
        )

    prompt = (
        "You are a flight-shopping assistant. You help users choose a flight considering price and disruption risk.\n"
        "Write concise, plain-English output.\n\n"
        f"Trip: {origin.iata} → {dest.iata} on {day.isoformat()}\n"
        f"Preference: {req.preference}\n\n"
        f"Departure weather: {origin_weather['daily']}\n"
        f"Arrival weather: {dest_weather['daily']}\n"
        f"Delay estimate: {asdict(delay_est)}\n\n"
        f"Top options (ranked): {flights_for_prompt}\n\n"
        "Return JSON ONLY with this shape:\n"
        "{\n"
        '  "overview": "2-4 sentence summary focusing on trade-offs and risk.",\n'
        '  "flights": [{"id":"...", "why":"1-2 sentences for why this option is ranked here."}]\n'
        "}\n"
    )

    llm = summarize_with_openai(openai_api_key=settings.openai_api_key, model=settings.openai_model, prompt=prompt)
    summary_data = llm.get("data") if llm.get("ok") else None

    why_by_id: dict[str, str] = {}
    if isinstance(summary_data, dict):
        for item in summary_data.get("flights") or []:
            if isinstance(item, dict) and item.get("id") and item.get("why"):
                why_by_id[str(item["id"])] = str(item["why"])

    flights_out = []
    for _, o, risk in top:
        flights_out.append(_offer_to_public_dict(o, purchase_link=purchase_link, risk=risk, why=why_by_id.get(o.id)))

    overview = summary_data.get("overview") if isinstance(summary_data, dict) else llm.get("text")
    if not overview:
        overview = "Showing top options ranked by your preference."

    return {
        "origin": origin.iata,
        "destination": dest.iata,
        "departure_date": day.isoformat(),
        "request": req.model_dump(),
        "weather": {"origin": origin_weather, "destination": dest_weather},
        "delay": asdict(delay_est),
        "flights": flights_out,
        "summary": {"overview": overview},
    }


@dataclass
class _WatchSession:
    created_at: float
    analysis_request: dict[str, Any]
    offer_id: str
    last_risk_score: int | None = None


WATCHES: dict[str, _WatchSession] = {}


class WatchStartRequest(BaseModel):
    analysis_request: dict[str, Any]
    offer_id: str


@app.post("/api/watch/start")
def watch_start(req: WatchStartRequest) -> dict[str, Any]:
    watch_id = uuid4().hex
    WATCHES[watch_id] = _WatchSession(
        created_at=datetime.utcnow().timestamp(),
        analysis_request=req.analysis_request,
        offer_id=req.offer_id,
        last_risk_score=None,
    )
    return {"watch_id": watch_id}


@app.get("/api/watch/stream/{watch_id}")
async def watch_stream(watch_id: str) -> StreamingResponse:
    session = WATCHES.get(watch_id)
    if not session:
        raise HTTPException(status_code=404, detail="Unknown watch id")

    async def event_gen():
        while True:
            try:
                analysis_req = AnalyzeRequest(**session.analysis_request)
                day = _parse_day(analysis_req.departure_date)
                origin = _require_airport(analysis_req.origin)
                dest = _require_airport(analysis_req.destination)

                origin_weather = _cached_weather(origin, day)
                dest_weather = _cached_weather(dest, day)
                origin_daily = DailyWeather(**origin_weather["daily"])
                dest_daily = DailyWeather(**dest_weather["daily"])

                delay_est = estimate_delay_risk(origin, dest, day)

                amadeus = _get_amadeus()
                offers = amadeus.search_flights(
                    origin=origin.iata,
                    destination=dest.iata,
                    departure_date=day,
                    adults=analysis_req.adults,
                    travel_class=analysis_req.travel_class,
                    currency=analysis_req.currency,
                    max_results=analysis_req.max_results,
                    prefer_nonstop=analysis_req.prefer_nonstop,
                )
                if not offers and analysis_req.prefer_nonstop:
                    offers = amadeus.search_flights(
                        origin=origin.iata,
                        destination=dest.iata,
                        departure_date=day,
                        adults=analysis_req.adults,
                        travel_class=analysis_req.travel_class,
                        currency=analysis_req.currency,
                        max_results=analysis_req.max_results,
                        prefer_nonstop=False,
                    )

                purchase_link = build_google_flights_link(
                    origin=origin.iata,
                    destination=dest.iata,
                    departure_date=day,
                    adults=analysis_req.adults,
                    travel_class=analysis_req.travel_class,
                )
                min_price = min((o.price_total for o in offers), default=0.0)
                max_price = max((o.price_total for o in offers), default=0.0)

                scored: list[tuple[float, Any, RiskResult]] = []
                selected_public = None
                for o in offers:
                    risk = score_offer_risk(offer=o, origin_weather=origin_daily, dest_weather=dest_daily, delay=delay_est)
                    score = ranking_score(
                        price_total=o.price_total,
                        min_price=min_price,
                        max_price=max_price,
                        risk_score=risk.risk_score,
                        preference=analysis_req.preference,
                    )
                    scored.append((score, o, risk))
                    if o.id == session.offer_id:
                        selected_public = _offer_to_public_dict(o, purchase_link=purchase_link, risk=risk)

                scored.sort(key=lambda t: t[0])
                alternatives = [
                    _offer_to_public_dict(o, purchase_link=purchase_link, risk=risk)
                    for _, o, risk in scored
                    if o.id != session.offer_id
                ][:3]

                alert = None
                if selected_public and selected_public.get("risk"):
                    new_score = int(selected_public["risk"]["risk_score"])
                    if session.last_risk_score is not None and new_score >= session.last_risk_score + 10:
                        alert = (
                            f"Risk increased from {session.last_risk_score}/100 to {new_score}/100. "
                            "Consider switching to a lower-risk alternative."
                        )
                    session.last_risk_score = new_score

                payload = {
                    "updated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
                    "selected": selected_public,
                    "alternatives": alternatives if alert else [],
                    "alert": alert,
                }
                yield f"data: {json.dumps(payload)}\n\n"
                await asyncio.sleep(max(5, settings.watch_poll_seconds))
            except Exception as e:
                payload = {"updated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z", "error": str(e)}
                yield f"data: {json.dumps(payload)}\n\n"
                await asyncio.sleep(max(5, settings.watch_poll_seconds))

    return StreamingResponse(event_gen(), media_type="text/event-stream")
