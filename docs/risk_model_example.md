# Risk model (internal developer notes)

This file is meant for **you (the builder)**. The app UI should not display the numeric weights or the full formula — it should only show:
- a **risk level** (low/medium/high)
- a short **natural-language explanation** (OpenAI-generated)
- a few **drivers** (e.g., “thunderstorms at arrival”, “1 connection”)

## What the demo does today

For each flight offer it computes a disruption probability `p` (0–1) and maps it to a `risk_score = round(100*p)`.

Components:
- `weather_p`: derived from forecast/historical at **departure + arrival** (Open‑Meteo)
- `delay_p`: a **historical/seasonal heuristic** (weekday + season + holiday proximity + route length)
- `conn_p`: based on number of stops (missed connection risk)
- `dur_p`: based on itinerary duration (upstream-delay exposure)

Blend:

```
p = clamp01(0.50*weather_p + 0.35*delay_p + 0.12*conn_p + 0.03*dur_p)
risk_score = round(100*p)
```

## Concrete worked example (numbers)

Trip: LAX → JFK, 1 adult, departure date 2026‑02‑10.

Assume Open‑Meteo daily data comes back as:

- LAX daily:
  - weather_code: 3 (Overcast)
  - wind_speed_max_mph: 18
  - precip_probability_max: 10
  - → departure airport probability ≈ `0.05` (benign)
- JFK daily:
  - weather_code: 95 (Thunderstorm)
  - wind_speed_max_mph: 38
  - precip_probability_max: 80
  - → arrival airport base `0.85` (thunderstorms)
  - wind boost `+0.12` (>=35 mph)
  - precip boost `+0.10` (>=80%)
  - → arrival airport probability ≈ `clamp01(0.85 + 0.12 + 0.10) = 1.00`

Then:

- `weather_p = max(dep_p, arr_p)*0.70 + (dep_p+arr_p)*0.15`
  - `= 1.00*0.70 + (0.05+1.00)*0.15`
  - `= 0.70 + 0.1575`
  - `= 0.8575`

Delay heuristic:
- February baseline ≈ 0.45
- Tue/Wed discount −0.05 (if Tue)
- Not near a major holiday
- Route distance LAX↔JFK ≈ 3980km → +0.06
- `delay_p ≈ clamp01(0.45 - 0.05 + 0.06) = 0.46`

Now two different offers:

Offer A (nonstop, 5h55m):
- stops = 0 → `conn_p = 0.05`
- duration 355 min → `dur_p = 0.12`
- Blend:
  - `p = 0.50*0.8575 + 0.35*0.46 + 0.12*0.05 + 0.03*0.12`
  - `p = 0.42875 + 0.161 + 0.006 + 0.0036`
  - `p = 0.59935`
  - `risk_score = 60` → **high** (threshold is 60+)

Offer B (1 stop, 7h40m):
- stops = 1 → `conn_p = 0.18`
- duration 460 min → `dur_p = 0.18`
- Blend:
  - `p = 0.50*0.8575 + 0.35*0.46 + 0.12*0.18 + 0.03*0.18`
  - `p = 0.42875 + 0.161 + 0.0216 + 0.0054`
  - `p = 0.61675`
  - `risk_score = 62` → **high**

In this example, even if Offer B is cheaper, Offer A ranks higher because:
- it has fewer failure points (no connection)
- it’s slightly less exposed to missed-connection risk

### How preference affects ranking (not risk)

Risk is computed the same, but ranking uses a weighted blend:

- `preference=price`: ~70% weight on price, 30% on risk
- `preference=weather`: ~70% weight on risk, 30% on price
- `preference=balanced`: ~55% weight on risk, 45% on price

That way you can still surface “pay a little more for much lower disruption risk.”
