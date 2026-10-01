(() => {
  "use strict";

  const state = {
    startedAt: performance.now(),
    requests: [],
    errors: [],
    longTasks: [],
    aircraftCount: 0,
    lastContactChangeAt: null,
    health: null,
    healthLatencyMs: null,
    healthCheckedAt: null,
    backendTelemetry: null,
    aircraftTelemetry: null,
  };

  const MAX_REQUESTS = 240;
  const MAX_ERRORS = 40;
  const MAX_LONG_TASKS = 80;
  const API_BASE = (window.NIGHTAZIMUTH_CONFIG?.apiBaseUrl || "").replace(/\/$/, "");
  const nativeFetch = window.fetch.bind(window);

  function nowIso() { return new Date().toISOString(); }

  function endpointLabel(input) {
    try {
      const raw = typeof input === "string" ? input : input?.url || "";
      const url = new URL(raw, location.href);
      return `${url.pathname}${url.search ? "?…" : ""}`;
    } catch {
      return String(input || "unknown").slice(0, 60);
    }
  }

  function captureAircraftTelemetry(payload) {
    const source = payload?.source;
    if (!source || typeof source !== "object") return;
    state.aircraftTelemetry = {
      id: source.id || null,
      label: source.label || source.id || "Unknown",
      state: source.state || "unknown",
      fallbackUsed: Boolean(source.fallback_used),
      failoverUsed: Boolean(source.provider_failover_used),
      regionalShared: Boolean(source.regional_shared),
      sourceObservedAt: source.source_observed_at || null,
      sourceCount: Number(payload.source_observation_count || 0),
      freshCount: Number(payload.fresh_contact_count || 0),
      returnedCount: Number(payload.count || 0),
      observedAt: payload.observed_at || null,
    };
  }

  window.fetch = async function observedFetch(input, init) {
    const started = performance.now();
    const endpoint = endpointLabel(input);
    const record = {
      time: nowIso(),
      endpoint,
      method: String(init?.method || "GET").toUpperCase(),
      status: 0,
      ok: false,
      durationMs: 0,
    };
    try {
      const response = await nativeFetch(input, init);
      record.status = response.status;
      record.ok = response.ok;
      if (response.ok && endpoint.startsWith("/api/v1/aircraft")) {
        response.clone().json().then(captureAircraftTelemetry).catch(() => {});
      }
      return response;
    } catch (error) {
      record.error = error?.message || String(error);
      throw error;
    } finally {
      record.durationMs = Math.max(0, performance.now() - started);
      state.requests.push(record);
      if (state.requests.length > MAX_REQUESTS) state.requests.splice(0, state.requests.length - MAX_REQUESTS);
      window.dispatchEvent(new CustomEvent("nightazimuth:observability-update"));
    }
  };

  function captureError(kind, message, source = "client") {
    state.errors.unshift({ time: nowIso(), kind, source, message: String(message || "Unknown error") });
    if (state.errors.length > MAX_ERRORS) state.errors.length = MAX_ERRORS;
    window.dispatchEvent(new CustomEvent("nightazimuth:observability-update"));
  }

  window.addEventListener("error", (event) => captureError("error", event.message || event.error?.message || "Unhandled error", event.filename || "client"));
  window.addEventListener("unhandledrejection", (event) => captureError("promise", event.reason?.message || event.reason || "Unhandled promise rejection", "client"));

  try {
    const observer = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) state.longTasks.push({ time: nowIso(), durationMs: entry.duration });
      if (state.longTasks.length > MAX_LONG_TASKS) state.longTasks.splice(0, state.longTasks.length - MAX_LONG_TASKS);
    });
    observer.observe({ type: "longtask", buffered: true });
  } catch {
    // Long Task API is optional.
  }

  function percentile(values, p) {
    if (!values.length) return 0;
    const sorted = [...values].sort((a, b) => a - b);
    const index = Math.min(sorted.length - 1, Math.max(0, Math.ceil((p / 100) * sorted.length) - 1));
    return sorted[index];
  }

  function recentRequests(windowMs = 60_000) {
    const cutoff = Date.now() - windowMs;
    return state.requests.filter((item) => Date.parse(item.time) >= cutoff);
  }

  function requestSummary() {
    const completed = state.requests.filter((item) => item.status || item.error);
    const successful = completed.filter((item) => item.ok).length;
    const errors = completed.filter((item) => !item.ok).length;
    const durations = completed.map((item) => item.durationMs);
    return {
      rpm: recentRequests().length,
      successRate: completed.length ? (successful / completed.length) * 100 : 100,
      errorRate: completed.length ? (errors / completed.length) * 100 : 0,
      p95: percentile(durations, 95),
      p50: percentile(durations, 50),
    };
  }

  function topEndpoints() {
    const serverRows = state.backendTelemetry?.api?.top_endpoints;
    if (Array.isArray(serverRows) && serverRows.length) {
      return serverRows.slice(0, 5).map((row) => ({
        endpoint: row.path,
        count: row.requests,
        p95: Number(row.p95_ms || 0),
        errorRate: Number(row.error_rate || 0),
      }));
    }
    const buckets = new Map();
    for (const req of state.requests) {
      if (!buckets.has(req.endpoint)) buckets.set(req.endpoint, { endpoint: req.endpoint, count: 0, errors: 0, durations: [] });
      const bucket = buckets.get(req.endpoint);
      bucket.count += 1;
      if (!req.ok) bucket.errors += 1;
      bucket.durations.push(req.durationMs);
    }
    return [...buckets.values()].map((b) => ({
      endpoint: b.endpoint,
      count: b.count,
      p95: percentile(b.durations, 95),
      errorRate: b.count ? (b.errors / b.count) * 100 : 0,
    })).sort((a, b) => b.count - a.count).slice(0, 5);
  }

  async function refreshHealth() {
    if (!API_BASE) return;
    const started = performance.now();
    try {
      const [healthResponse, telemetryResponse] = await Promise.all([
        nativeFetch(`${API_BASE}/api/v1/health`, { cache: "no-store" }),
        nativeFetch(`${API_BASE}/api/v1/observability`, { cache: "no-store" }),
      ]);
      const healthPayload = await healthResponse.json();
      state.health = { ok: healthResponse.ok && healthPayload?.status === "ok", status: healthResponse.status, payload: healthPayload };
      if (telemetryResponse.ok) state.backendTelemetry = await telemetryResponse.json();
    } catch (error) {
      state.health = { ok: false, status: 0, error: error?.message || String(error) };
    } finally {
      state.healthLatencyMs = performance.now() - started;
      state.healthCheckedAt = Date.now();
      render();
    }
  }

  function getMemoryMb() {
    const bytes = performance.memory?.usedJSHeapSize;
    return Number.isFinite(bytes) ? bytes / 1024 / 1024 : null;
  }

  function getUptimeText(secondsOverride = null) {
    const seconds = secondsOverride == null ? Math.max(0, (performance.now() - state.startedAt) / 1000) : Math.max(0, secondsOverride);
    if (seconds < 60) return `${Math.floor(seconds)}s`;
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return `${minutes}m`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours}h ${minutes % 60}m`;
    return `${Math.floor(hours / 24)}d ${hours % 24}h`;
  }

  function contactFreshnessText() {
    if (!state.lastContactChangeAt) return "Waiting";
    const age = Math.max(0, Date.now() - state.lastContactChangeAt);
    if (age < 1000) return "<1s ago";
    if (age < 60_000) return `${Math.floor(age / 1000)}s ago`;
    return `${Math.floor(age / 60_000)}m ago`;
  }

  function sourceFreshnessText() {
    const value = state.aircraftTelemetry?.sourceObservedAt;
    if (!value) return "Not observed yet";
    const age = Math.max(0, Date.now() - Date.parse(value));
    if (age < 1000) return "<1s old";
    if (age < 60_000) return `${Math.floor(age / 1000)}s old`;
    return `${Math.floor(age / 60_000)}m old`;
  }

  function setText(id, value) { const el = document.getElementById(id); if (el) el.textContent = value; }
  function setClass(id, cls) {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.remove("obs-good", "obs-warn", "obs-bad", "obs-blue");
    if (cls) el.classList.add(cls);
  }

  function sparkPath(values, width = 420, height = 120) {
    if (!values.length) return "";
    const max = Math.max(...values, 1);
    const min = Math.min(...values, 0);
    const range = Math.max(1, max - min);
    return values.map((value, index) => {
      const x = values.length === 1 ? 0 : (index / (values.length - 1)) * width;
      const y = height - ((value - min) / range) * (height - 8) - 4;
      return `${index === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(" ");
  }

  function renderRequestChart() {
    const path = document.getElementById("obs-request-line");
    if (!path) return;
    const buckets = new Array(24).fill(0);
    const windowMs = 12 * 60_000;
    const cutoff = Date.now() - windowMs;
    for (const req of state.requests) {
      const time = Date.parse(req.time);
      if (time < cutoff) continue;
      const ratio = (time - cutoff) / windowMs;
      buckets[Math.min(23, Math.max(0, Math.floor(ratio * 24)))] += 1;
    }
    path.setAttribute("d", sparkPath(buckets));
  }

  function escapeHtml(value) {
    return String(value ?? "").replaceAll("&", "&amp;").replaceAll("<", "&lt;").replaceAll(">", "&gt;").replaceAll('"', "&quot;").replaceAll("'", "&#039;");
  }

  function renderEndpoints() {
    const body = document.getElementById("obs-endpoints-body");
    if (!body) return;
    const rows = topEndpoints();
    body.innerHTML = rows.length ? rows.map((row) => `
      <tr><td title="${escapeHtml(row.endpoint)}">${escapeHtml(row.endpoint)}</td><td class="num">${row.count}</td><td class="num">${row.p95.toFixed(0)} ms</td><td class="num ${row.errorRate > 5 ? "obs-bad" : row.errorRate > 0 ? "obs-warn" : "obs-good"}">${row.errorRate.toFixed(1)}%</td></tr>`).join("") : '<tr><td colspan="4" class="obs-subtle">Waiting for API activity…</td></tr>';
  }

  function renderErrors() {
    const body = document.getElementById("obs-errors-body");
    if (!body) return;
    const rows = state.errors.slice(0, 5);
    body.innerHTML = rows.length ? rows.map((row) => `
      <tr><td>${new Date(row.time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}</td><td>${escapeHtml(row.kind)}</td><td title="${escapeHtml(row.message)}">${escapeHtml(row.message)}</td></tr>`).join("") : '<tr><td colspan="3" class="obs-good">No JavaScript errors captured in this session.</td></tr>';
  }

  function renderHostedService() {
    const apiCell = document.getElementById("obs-hosted-api");
    if (!apiCell) return;
    const list = apiCell.closest(".obs-list");
    if (!list) return;
    list.querySelectorAll("[data-observability-extra]").forEach((node) => node.remove());
    const aircraft = state.aircraftTelemetry;
    const backend = state.backendTelemetry;
    const rows = [
      ["API process uptime", backend ? getUptimeText(Number(backend.process_uptime_seconds || 0)) : "Waiting"],
      ["ADS-B source", aircraft?.label || "Waiting for aircraft data"],
      ["ADS-B source state", aircraft?.state || "Unknown"],
      ["ADS-B source freshness", sourceFreshnessText()],
      ["Aircraft source / returned", aircraft ? `${aircraft.sourceCount} / ${aircraft.returnedCount}` : "—"],
      ["Fresh contacts", aircraft ? String(aircraft.freshCount) : "—"],
      ["Regional cache", aircraft ? (aircraft.regionalShared ? "Shared regional snapshot" : "Observer-specific") : "—"],
      ["Fallback cache", aircraft ? (aircraft.fallbackUsed ? "In use" : "Not in use") : "—"],
      ["Provider failover", aircraft ? (aircraft.failoverUsed ? "Active" : "Primary provider") : "—"],
    ];
    for (const [label, value] of rows) {
      const row = document.createElement("div");
      row.className = "obs-row";
      row.dataset.observabilityExtra = "1";
      const strong = document.createElement("strong");
      strong.textContent = label;
      const span = document.createElement("span");
      span.textContent = value;
      row.append(strong, span);
      list.append(row);
    }
  }

  function render() {
    if (!document.getElementById("observability-screen")) return;
    const clientSummary = requestSummary();
    const serverSummary = state.backendTelemetry?.api;
    const summary = serverSummary ? {
      rpm: Number(serverSummary.requests_last_minute || 0),
      successRate: Number(serverSummary.success_rate ?? 100),
      errorRate: Number(serverSummary.error_rate || 0),
      p95: Number(serverSummary.p95_ms || 0),
      p50: Number(serverSummary.p50_ms || 0),
    } : clientSummary;
    const healthOk = Boolean(state.health?.ok);
    const online = navigator.onLine;
    const memory = getMemoryMb();
    const longTaskP95 = percentile(state.longTasks.map((t) => t.durationMs), 95);

    setText("obs-health", state.health ? (healthOk ? "Healthy" : "Degraded") : "Checking");
    setClass("obs-health", state.health ? (healthOk ? "obs-good" : "obs-bad") : "obs-warn");
    setText("obs-health-foot", state.health?.payload?.application_version ? `API ${state.health.payload.application_version}` : "Hosted API");
    setText("obs-aircraft", String(state.aircraftCount));
    setText("obs-aircraft-foot", `Last contact update ${contactFreshnessText()}`);
    setText("obs-api-p95", `${summary.p95.toFixed(0)} ms`);
    setClass("obs-api-p95", summary.p95 > 1000 ? "obs-bad" : summary.p95 > 400 ? "obs-warn" : "obs-blue");
    setText("obs-request-rate", `${summary.rpm}/min`);
    setText("obs-client-errors", String(state.errors.length));
    setClass("obs-client-errors", state.errors.length ? "obs-bad" : "obs-good");
    setText("obs-session-uptime", getUptimeText());
    setText("obs-api-success", `${summary.successRate.toFixed(1)}%`);
    setText("obs-api-error-rate", `${summary.errorRate.toFixed(1)}%`);
    setText("obs-api-p50", `${summary.p50.toFixed(0)} ms`);
    setText("obs-api-latency", state.healthLatencyMs == null ? "—" : `${state.healthLatencyMs.toFixed(0)} ms`);
    setText("obs-network", online ? "Online" : "Offline");
    setClass("obs-network", online ? "obs-good" : "obs-bad");
    setText("obs-memory", memory == null ? "Unavailable" : `${memory.toFixed(0)} MB`);
    setText("obs-longtask-p95", state.longTasks.length ? `${longTaskP95.toFixed(0)} ms` : "0 ms");
    setText("obs-longtasks", String(state.longTasks.length));
    setText("obs-feed-freshness", state.aircraftTelemetry ? sourceFreshnessText() : contactFreshnessText());
    setText("obs-health-last", state.healthCheckedAt ? new Date(state.healthCheckedAt).toLocaleTimeString() : "—");
    setText("obs-hosted-api", state.backendTelemetry ? "Telemetry connected" : "Health check");

    const apiPill = document.getElementById("obs-api-pill");
    if (apiPill) {
      apiPill.textContent = state.health ? (healthOk ? "Connected" : "Unavailable") : "Checking";
      apiPill.className = `obs-pill${state.health && !healthOk ? " bad" : ""}`;
    }

    renderRequestChart();
    renderEndpoints();
    renderErrors();
    renderHostedService();
  }

  function observeContacts() {
    const contacts = document.getElementById("contacts");
    if (!contacts) return;
    const update = () => {
      const candidateRows = contacts.querySelectorAll("button, [data-aircraft], .contact, .aircraft-contact");
      state.aircraftCount = candidateRows.length;
      if (!state.aircraftCount) {
        const text = document.getElementById("aircraft-detail")?.textContent || "";
        const match = text.match(/(\d+)\s+(?:aircraft|contacts?)/i);
        if (match) state.aircraftCount = Number(match[1]);
      }
      state.lastContactChangeAt = Date.now();
      render();
    };
    const observer = new MutationObserver(update);
    observer.observe(contacts, { childList: true, subtree: true, characterData: true });
    update();
  }

  function openDashboard() {
    const screen = document.getElementById("observability-screen");
    const settings = document.getElementById("settings-panel");
    if (!screen) return;
    if (settings) settings.hidden = true;
    screen.hidden = false;
    refreshHealth();
    render();
  }

  function closeDashboard() { const screen = document.getElementById("observability-screen"); if (screen) screen.hidden = true; }

  function init() {
    document.getElementById("observability-open")?.addEventListener("click", openDashboard);
    document.getElementById("observability-close")?.addEventListener("click", closeDashboard);
    document.getElementById("observability-refresh")?.addEventListener("click", refreshHealth);
    document.getElementById("obs-auto-refresh")?.addEventListener("change", (event) => {
      window.clearInterval(init.refreshTimer);
      const seconds = Number(event.target.value || 0);
      if (seconds > 0) init.refreshTimer = window.setInterval(refreshHealth, seconds * 1000);
    });
    document.addEventListener("visibilitychange", render);
    window.addEventListener("online", render);
    window.addEventListener("offline", render);
    window.addEventListener("nightazimuth:observability-update", render);
    observeContacts();
    refreshHealth();
    init.refreshTimer = window.setInterval(refreshHealth, 60_000);
    window.setInterval(render, 1_000);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true }); else init();
})();
