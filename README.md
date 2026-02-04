# Flight Risk Advisor (demo)

This is a FastAPI web app that:
- Converts **origin/destination IATA codes → lat/lon** (demo includes a small airport map).
- Pulls **weather** from Open‑Meteo (forecast if within ~2 weeks, otherwise historical).
- Pulls **flight prices** (and basic itinerary info) from **Amadeus**.
- Computes a **risk score** that trades off price vs disruption risk (weather + delay heuristic + connections).
- Uses **OpenAI Responses API** to summarize weather/prices/risk in plain English.
- Includes a simple “watch mode” that streams updated risk as forecasts change.

## 1) Create the Python env (.venv)

From the repo root:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

> If you already have a `.venv` you want to reuse, just activate it and install the requirements.

## 2) Add your API keys (.env)

1. Copy the example env file:
   ```bash
   cp .env.example .env
   ```
2. Edit `.env` and set:
   - `OPENAI_API_KEY`
   - `AMADEUS_CLIENT_ID`
   - `AMADEUS_CLIENT_SECRET`
   - `AMADEUS_HOST` (keep `test.api.amadeus.com` for the free test environment)

## 3) Run the app locally

```bash
uvicorn backend.app.main:app --reload --port 8000
```

Open:
- http://localhost:8000

## 4) Demo: LAX → JFK

In the UI:
1. Origin: `LAX`
2. Destination: `JFK`
3. Pick a date (try within 14 days to see forecast mode)
4. Click **Analyze flights**

You should see:
- Departure + arrival weather cards
- Top 5 flights ranked by your preference
- A summary (from OpenAI if configured)

### API demo (curl)

Weather:
```bash
curl -s http://localhost:8000/api/weather \
  -H 'Content-Type: application/json' \
  -d '{"origin":"LAX","destination":"JFK","departure_date":"2026-02-10"}' | python -m json.tool
```

Delays (heuristic for now):
```bash
curl -s http://localhost:8000/api/delays \
  -H 'Content-Type: application/json' \
  -d '{"origin":"LAX","destination":"JFK","departure_date":"2026-02-10"}' | python -m json.tool
```

Prices (Amadeus flight offers):
```bash
curl -s http://localhost:8000/api/prices \
  -H 'Content-Type: application/json' \
  -d '{"origin":"LAX","destination":"JFK","departure_date":"2026-02-10","adults":1,"travel_class":"ECONOMY","currency":"USD","prefer_nonstop":true}' | python -m json.tool
```

Full analysis:
```bash
curl -s http://localhost:8000/api/analyze \
  -H 'Content-Type: application/json' \
  -d '{"origin":"LAX","destination":"JFK","departure_date":"2026-02-10","adults":1,"travel_class":"ECONOMY","currency":"USD","preference":"balanced"}' | python -m json.tool
```

## Notes on “delay info”

This demo includes a **historical/seasonal heuristic** (weekday + season + holiday proximity + route length) because:
- “Real-time delay tracking” usually requires a **flight status** provider (often paid) and a specific flight number.
- Amadeus has additional APIs beyond flight offers; if you have access, we can wire in true delay/status.

## Risk scoring (developer note)

The app computes a 0–100 risk score per offer (higher = worse). Internally it blends:
- Weather disruption probability (forecast/historical at both endpoints)
- Delay risk estimate (heuristic today; swap to real delay/status later)
- Connection risk (stops)
- Duration risk (longer itineraries)

The UI intentionally shows only “low/medium/high” + brief drivers — not the raw formula weights.

For a worked numeric example (internal), see `docs/risk_model_example.md`.
