(() => {
  "use strict";

  const previousFetch = window.fetch.bind(window);
  const endpointStats = new Map();
  const MAX_SAMPLES_PER_ENDPOINT = 120;
  const MAX_TIMING_SNAPSHOTS = 20;

  function endpointPath(input) {
    try {
      const raw = typeof input === "string" ? input : input?.url || "";
      return new URL(raw, location.href).pathname;
    } catch {
      return String(input || "unknown").split("?")[0];
    }
  }

  function percentile(values, p) {
    if (!values.length) return 0;
    const sorted = [...values].sort((a, b) => a - b);
    const index = Math.min(sorted.length - 1, Math.max(0, Math.ceil((p / 100) * sorted.length) - 1));
    return sorted[index];
  }

  function parseServerTiming(header) {
    if (!header) return [];
    const entries = [];
    for (const token of header.split(",")) {
      const parts = token.trim().split(";").map((part) => part.trim()).filter(Boolean);
      if (!parts.length) continue;
      const name = parts[0];
      let durationMs = null;
      for (const part of parts.slice(1)) {
        const match = part.match(/^dur=([0-9.]+)$/i);
        if (match) durationMs = Number(match[1]);
      }
      if (Number.isFinite(durationMs)) entries.push({ name, durationMs });
    }
    return entries;
  }

  function ensureEndpoint(path) {
    let stats = endpointStats.get(path);
    if (!stats) {
      stats = { calls: 0, errors: 0, durations: [], timings: [] };
      endpointStats.set(path, stats);
    }
    return stats;
  }

  function record(path, status, durationMs, serverTiming) {
    if (!path.startsWith("/api/")) return;
    const stats = ensureEndpoint(path);
    stats.calls += 1;
    if (status >= 400 || status === 0) stats.errors += 1;
    stats.durations.push(durationMs);
    if (stats.durations.length > MAX_SAMPLES_PER_ENDPOINT) stats.durations.shift();
    stats.timings.push(serverTiming);
    if (stats.timings.length > MAX_TIMING_SNAPSHOTS) stats.timings.shift();
    render();
  }

  window.fetch = async function latencyObservedFetch(input, init) {
    const path = endpointPath(input);
    const started = performance.now();
    try {
      const response = await previousFetch(input, init);
      record(path, response.status, performance.now() - started, parseServerTiming(response.headers.get("Server-Timing")));
      return response;
    } catch (error) {
      record(path, 0, performance.now() - started, []);
      throw error;
    }
  };

  function latencyState(ms) {
    if (ms < 250) return { label: "Excellent", cls: "obs-good" };
    if (ms < 750) return { label: "Good", cls: "obs-good" };
    if (ms < 1500) return { label: "Elevated", cls: "obs-warn" };
    if (ms < 2500) return { label: "Slow", cls: "obs-warn" };
    return { label: "Very slow", cls: "obs-bad" };
  }

  function timingSummary(stats) {
    const latest = stats.timings.at(-1) || [];
    return latest
      .filter((item) => item.name !== "total")
      .sort((a, b) => b.durationMs - a.durationMs)
      .slice(0, 4);
  }

  function humanTimingName(name) {
    return name
      .replace(/^provider_/, "Provider ")
      .replace(/^provider_failover_/, "Failover ")
      .replace(/^admission_wait$/, "Admission queue")
      .replace(/^shared_wait$/, "Shared cache wait")
      .replace(/^radius_slice$/, "Radius filtering")
      .replace(/^projection$/, "Sky projection")
      .replace(/^payload$/, "Payload build")
      .replace(/_/g, " ")
      .replace(/\b\w/g, (char) => char.toUpperCase());
  }

  function installPanel() {
    if (document.getElementById("obs-endpoint-health")) return;
    const table = document.getElementById("obs-endpoints-body")?.closest("table");
    const card = table?.closest(".obs-card");
    if (!card) return;

    const panel = document.createElement("div");
    panel.id = "obs-endpoint-health";
    panel.className = "obs-endpoint-health";

    const head = document.createElement("div");
    head.className = "obs-latency-head";
    const title = document.createElement("strong");
    title.textContent = "Endpoint latency health";
    const subtitle = document.createElement("span");
    subtitle.className = "obs-subtle";
    subtitle.textContent = "Browser-observed · Server-Timing where exposed";
    head.append(title, subtitle);

    const rows = document.createElement("div");
    rows.id = "obs-latency-rows";
    rows.className = "obs-latency-rows";

    const breakdown = document.createElement("div");
    breakdown.id = "obs-timing-breakdown";
    breakdown.className = "obs-timing-breakdown";

    panel.append(head, rows, breakdown);
    card.append(panel);
  }

  function publishSlowest(slowest) {
    window.NIGHTAZIMUTH_OBSERVABILITY_LATENCY = {
      slowest: slowest ? {
        path: slowest.path,
        p95: slowest.p95,
        state: latencyState(slowest.p95),
      } : null,
    };
    window.dispatchEvent(new CustomEvent("nightazimuth:latency-update"));
  }

  function render() {
    installPanel();

    const rowsEl = document.getElementById("obs-latency-rows");
    const breakdownEl = document.getElementById("obs-timing-breakdown");
    if (!rowsEl || !breakdownEl) return;

    const rows = [...endpointStats.entries()]
      .filter(([path]) => path.startsWith("/api/v1/"))
      .map(([path, stats]) => ({
        path,
        stats,
        p95: percentile(stats.durations, 95),
        errorRate: stats.calls ? (stats.errors / stats.calls) * 100 : 0,
      }))
      .sort((a, b) => b.p95 - a.p95)
      .slice(0, 6);

    rowsEl.replaceChildren();
    for (const row of rows) {
      const state = latencyState(row.p95);
      const item = document.createElement("div");
      item.className = "obs-latency-row";
      const name = document.createElement("strong");
      name.textContent = row.path.replace("/api/v1/", "") || row.path;
      const p95 = document.createElement("span");
      p95.textContent = `${Math.round(row.p95)} ms`;
      p95.className = state.cls;
      const status = document.createElement("span");
      status.textContent = state.label;
      status.className = state.cls;
      const calls = document.createElement("span");
      calls.textContent = `${row.stats.calls} calls`;
      item.append(name, p95, status, calls);
      rowsEl.append(item);
    }

    const applicationRows = rows.filter((row) => row.path !== "/api/v1/health" && row.path !== "/api/v1/observability");
    const slowest = applicationRows[0] || null;
    publishSlowest(slowest);

    breakdownEl.replaceChildren();
    if (!slowest) {
      const empty = document.createElement("div");
      empty.className = "obs-subtle";
      empty.textContent = "Waiting for application endpoint activity.";
      breakdownEl.append(empty);
      return;
    }

    const timings = timingSummary(slowest.stats);
    const title = document.createElement("div");
    title.className = "obs-latency-head";
    const titleLabel = document.createElement("strong");
    titleLabel.textContent = `${slowest.path.replace("/api/v1/", "")} timing breakdown`;
    const titleMeta = document.createElement("span");
    titleMeta.className = "obs-subtle";
    titleMeta.textContent = "Latest response";
    title.append(titleLabel, titleMeta);
    breakdownEl.append(title);

    if (!timings.length) {
      const empty = document.createElement("div");
      empty.className = "obs-subtle";
      empty.textContent = "No Server-Timing breakdown exposed by this endpoint yet.";
      breakdownEl.append(empty);
      return;
    }

    for (const timing of timings) {
      const item = document.createElement("div");
      item.className = "obs-timing-row";
      const label = document.createElement("span");
      label.textContent = humanTimingName(timing.name);
      const value = document.createElement("strong");
      value.textContent = `${Math.round(timing.durationMs)} ms`;
      item.append(label, value);
      breakdownEl.append(item);
    }
  }

  function installStyles() {
    if (document.getElementById("obs-latency-styles")) return;
    const style = document.createElement("style");
    style.id = "obs-latency-styles";
    style.textContent = `
      .obs-endpoint-health{margin-top:.55rem;padding-top:.55rem;border-top:1px solid rgba(116,168,205,.12)}
      .obs-latency-head{display:flex;justify-content:space-between;gap:.6rem;align-items:center;margin-bottom:.35rem;font-size:.66rem}
      .obs-latency-rows{display:grid;gap:.22rem}
      .obs-latency-row{display:grid;grid-template-columns:minmax(0,1.4fr) .75fr .8fr .65fr;gap:.45rem;align-items:center;padding:.24rem .32rem;border-radius:7px;background:rgba(255,255,255,.018);font-size:.61rem}
      .obs-latency-row strong{text-transform:capitalize;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
      .obs-latency-row span{text-align:right;white-space:nowrap}
      .obs-timing-breakdown{margin-top:.45rem;padding-top:.4rem;border-top:1px solid rgba(116,168,205,.08)}
      .obs-timing-row{display:flex;justify-content:space-between;gap:.6rem;padding:.2rem .3rem;font-size:.6rem;color:#8ea7bb}
      .obs-timing-row strong{color:#cfe3f4;font-weight:650}
    `;
    document.head.append(style);
  }

  function init() {
    installStyles();
    render();
    window.addEventListener("nightazimuth:observability-update", render);
    window.setInterval(render, 2000);
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init, { once: true }); else init();
})();