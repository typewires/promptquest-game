const els = {
  origin: document.getElementById("origin"),
  destination: document.getElementById("destination"),
  departureDate: document.getElementById("departureDate"),
  adults: document.getElementById("adults"),
  preference: document.getElementById("preference"),
  analyzeBtn: document.getElementById("analyzeBtn"),
  status: document.getElementById("status"),
  results: document.getElementById("results"),
  meta: document.getElementById("meta"),
  watch: document.getElementById("watch"),
};

function todayPlus(days) {
  const d = new Date();
  d.setDate(d.getDate() + days);
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, "0");
  const dd = String(d.getDate()).padStart(2, "0");
  return `${yyyy}-${mm}-${dd}`;
}

if (!els.departureDate.value) {
  els.departureDate.value = todayPlus(7);
}

function badge(level) {
  const map = {
    low: "bg-emerald-400/15 text-emerald-200 border-emerald-400/20",
    medium: "bg-amber-400/15 text-amber-200 border-amber-400/20",
    high: "bg-rose-400/15 text-rose-200 border-rose-400/20",
  };
  const cls = map[level] || "bg-slate-400/10 text-slate-200 border-white/10";
  return `<span class="inline-flex items-center rounded-full border px-2 py-0.5 text-xs ${cls}">${level.toUpperCase()}</span>`;
}

function fmtPrice(n, currency) {
  try {
    return new Intl.NumberFormat(undefined, { style: "currency", currency }).format(n);
  } catch {
    return `${n} ${currency}`;
  }
}

function weatherCard(title, w) {
  const source = w?.daily?.source ? w.daily.source : "—";
  const day = w?.daily?.day || "—";
  const temp = w?.daily?.temp_max_f != null ? `${w.daily.temp_min_f?.toFixed?.(0) ?? "?"}–${w.daily.temp_max_f?.toFixed?.(0) ?? "?"}°F` : "—";
  const cond = w?.daily?.condition || "—";
  const wind = w?.daily?.wind_speed_max_mph != null ? `${w.daily.wind_speed_max_mph.toFixed(0)} mph wind` : "—";
  const precip = w?.daily?.precipitation_probability_max != null
    ? `${w.daily.precipitation_probability_max.toFixed(0)}% precip`
    : w?.daily?.precipitation_sum_mm != null
      ? `${w.daily.precipitation_sum_mm.toFixed(1)}mm precip`
      : "—";
  return `
    <div class="rounded-2xl border border-white/10 bg-white/5 p-4">
      <div class="flex items-center justify-between">
        <div>
          <p class="text-xs text-slate-300">${title}</p>
          <p class="mt-1 text-sm font-semibold">${w?.airport?.iata ?? ""} · ${w?.airport?.city ?? ""}</p>
        </div>
        <div class="text-right text-xs text-slate-300">
          <div>${day}</div>
          <div class="mt-0.5 opacity-80">${source}</div>
        </div>
      </div>
      <div class="mt-3 flex flex-wrap items-center gap-2 text-sm">
        <span class="rounded-lg bg-black/30 px-2 py-1">${cond}</span>
        <span class="rounded-lg bg-black/30 px-2 py-1">${temp}</span>
        <span class="rounded-lg bg-black/30 px-2 py-1">${wind}</span>
        <span class="rounded-lg bg-black/30 px-2 py-1">${precip}</span>
      </div>
    </div>
  `;
}

function flightCard(f, idx) {
  const price = fmtPrice(f.price_total, f.currency);
  const stops = f.stops === 0 ? "Nonstop" : `${f.stops} stop${f.stops === 1 ? "" : "s"}`;
  const reasons = (f.risk?.drivers || []).slice(0, 3).map((r) => `<li class="text-xs text-slate-300">${r}</li>`).join("");
  const why = f.why ? `<p class="mt-2 text-sm text-slate-200">${f.why}</p>` : "";
  return `
    <div class="rounded-2xl border border-white/10 bg-white/5 p-5">
      <div class="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div class="flex items-center gap-2">
            <p class="text-sm font-semibold">${idx}. ${f.primary_carrier}</p>
            ${badge(f.risk?.risk_level)}
          </div>
          <p class="mt-1 text-xs text-slate-300">${stops} · ${f.duration}</p>
        </div>
        <div class="text-right">
          <p class="text-sm font-semibold">${price}</p>
          <p class="mt-1 text-xs text-slate-300">${f.departure_at?.replace?.("T", " ") ?? ""} → ${f.arrival_at?.replace?.("T", " ") ?? ""}</p>
        </div>
      </div>
      ${why}
      <ul class="mt-3 list-disc pl-5">${reasons}</ul>
      <div class="mt-4 flex flex-wrap gap-2">
        <a class="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm hover:bg-white/10" target="_blank" rel="noreferrer" href="${f.purchase_link}">
          Buy ticket
        </a>
        <button data-offer-id="${f.id}" class="watchBtn rounded-xl bg-gradient-to-r from-indigo-500 to-cyan-400 px-3 py-2 text-sm font-semibold text-slate-950 hover:brightness-110 active:brightness-95">
          Watch
        </button>
      </div>
    </div>
  `;
}

let currentAnalysis = null;
let currentEventSource = null;

async function postJson(path, body) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    const detail = data?.detail || data?.error || res.statusText;
    throw new Error(detail);
  }
  return data;
}

function renderAnalysis(data) {
  currentAnalysis = data;
  els.meta.textContent = `${data.origin} → ${data.destination} · ${data.departure_date}`;

  const weatherRow = `
    <div class="grid gap-4 md:grid-cols-2">
      ${weatherCard("Departure weather", data.weather.origin)}
      ${weatherCard("Arrival weather", data.weather.destination)}
    </div>
  `;

  const summary = data.summary?.overview
    ? `<div class="rounded-2xl border border-white/10 bg-white/5 p-5"><p class="text-sm text-slate-200">${data.summary.overview}</p></div>`
    : "";

  const flights = (data.flights || []).map((f, i) => flightCard(f, i + 1)).join("");

  els.results.innerHTML = weatherRow + summary + flights;
  wireWatchButtons();
}

function wireWatchButtons() {
  document.querySelectorAll(".watchBtn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const offerId = btn.getAttribute("data-offer-id");
      if (!offerId || !currentAnalysis) return;
      try {
        els.watch.textContent = "Starting watch…";
        const payload = await postJson("/api/watch/start", {
          analysis_request: currentAnalysis.request,
          offer_id: offerId,
        });
        startWatchStream(payload.watch_id);
      } catch (e) {
        els.watch.textContent = `Watch error: ${e.message}`;
      }
    });
  });
}

function startWatchStream(watchId) {
  if (currentEventSource) currentEventSource.close();
  currentEventSource = new EventSource(`/api/watch/stream/${watchId}`);
  els.watch.innerHTML = `
    <div class="flex items-center justify-between">
      <div class="text-sm font-semibold text-slate-100">Watching</div>
      <button id="stopWatch" class="rounded-xl border border-white/10 bg-white/5 px-3 py-1.5 text-xs hover:bg-white/10">Stop</button>
    </div>
    <div id="watchBody" class="mt-3 text-sm text-slate-300">Connecting…</div>
  `;
  document.getElementById("stopWatch")?.addEventListener("click", () => {
    currentEventSource?.close();
    currentEventSource = null;
    els.watch.textContent = "Stopped watching.";
  });

  const watchBody = () => document.getElementById("watchBody");

  currentEventSource.onmessage = (ev) => {
    let msg = null;
    try {
      msg = JSON.parse(ev.data);
    } catch {
      msg = { text: ev.data };
    }

    const risk = msg?.selected?.risk;
    const riskLine = risk ? `Risk: <span class="ml-1">${badge(risk.risk_level)}</span> <span class="ml-2 text-xs opacity-80">${risk.risk_score}/100</span>` : "";

    const alt = (msg?.alternatives || []).slice(0, 3).map((a) => {
      const price = fmtPrice(a.price_total, a.currency);
      return `<li class="mt-2">
        <a class="underline underline-offset-4" target="_blank" rel="noreferrer" href="${a.purchase_link}">${a.primary_carrier} · ${price}</a>
        <span class="ml-2">${badge(a.risk?.risk_level)}</span>
      </li>`;
    }).join("");

    const alert = msg?.alert ? `<div class="mt-3 rounded-xl border border-rose-400/20 bg-rose-400/10 p-3 text-sm text-rose-100">${msg.alert}</div>` : "";

    const body = `
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div>${riskLine}</div>
        <div class="text-xs opacity-80">Updated: ${msg?.updated_at ?? "—"}</div>
      </div>
      ${alert}
      ${alt ? `<div class="mt-4"><p class="text-sm font-semibold text-slate-100">Alternatives</p><ul class="mt-2">${alt}</ul></div>` : ""}
    `;
    if (watchBody()) watchBody().innerHTML = body;
  };

  currentEventSource.onerror = () => {
    if (watchBody()) watchBody().textContent = "Stream disconnected. Try again.";
  };
}

els.analyzeBtn.addEventListener("click", async () => {
  els.status.textContent = "Analyzing…";
  els.analyzeBtn.disabled = true;
  try {
    const req = {
      origin: els.origin.value.trim(),
      destination: els.destination.value.trim(),
      departure_date: els.departureDate.value,
      adults: Number(els.adults.value || 1),
      travel_class: "ECONOMY",
      currency: "USD",
      preference: els.preference.value,
    };
    const data = await postJson("/api/analyze", req);
    renderAnalysis(data);
    els.status.textContent = "";
  } catch (e) {
    els.status.textContent = `Error: ${e.message}`;
  } finally {
    els.analyzeBtn.disabled = false;
  }
});
