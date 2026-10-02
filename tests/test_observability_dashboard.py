from pathlib import Path


HTML = Path("web/index.html").read_text(encoding="utf-8")
JS = Path("web/observability.js").read_text(encoding="utf-8")
CSS = Path("web/observability.css").read_text(encoding="utf-8")


def test_observability_is_reachable_from_settings() -> None:
    assert 'id="observability-open"' in HTML
    assert 'id="observability-screen"' in HTML
    assert 'id="observability-close"' in HTML


def test_observability_assets_load_before_application_requests_start() -> None:
    assert 'observability.css?v=22.0.0' in HTML
    assert 'observability-latency.js?v=22.1.2' in HTML
    assert 'observability.js?v=22.1.2' in HTML
    assert HTML.index('observability-latency.js?v=22.1.2') < HTML.index('observability.js?v=22.1.2')
    assert HTML.index('observability.js?v=22.1.2') < HTML.index('app.js?v=21.11.24')


def test_dashboard_uses_versioned_health_and_backend_telemetry_endpoints() -> None:
    assert '`${API_BASE}/api/v1/health`' in JS
    assert '`${API_BASE}/api/v1/observability`' in JS
    assert 'window.fetch = async function observedFetch' in JS
    assert 'PerformanceObserver' in JS


def test_aircraft_response_state_drives_provider_freshness() -> None:
    assert 'source.provider_failover_used' in JS
    assert 'source.fallback_used' in JS
    assert 'source.source_observed_at' in JS
    assert 'function markAircraftUnavailable(status)' in JS
    assert 'state.aircraftCount = 0;' in JS
    assert 'sourceCount: 0' in JS
    assert 'function isAircraftFeedEndpoint(endpoint)' in JS
    assert 'if (isAircraftFeedEndpoint(endpoint))' in JS
    assert 'if (endpoint.startsWith("/api/v1/aircraft"))' not in JS
    assert 'state.lastContactChangeAt' not in JS


def test_browser_endpoint_aggregation_is_bounded_and_normalized() -> None:
    assert 'function normaliseBrowserEndpoint(endpoint)' in JS
    assert '"/api/v1/aircraft/route"' in JS
    assert 'return "/api/other";' in JS
    assert 'const endpointKey = normaliseBrowserEndpoint(record.endpoint);' in JS
    assert 'totals.endpoints.get(endpointKey)' in JS
    assert 'totals.endpoints.set(endpointKey, endpoint)' in JS


def test_cumulative_counts_are_separate_from_bounded_detail_buffers() -> None:
    assert 'totalErrors: 0' in JS
    assert 'totalLongTasks: 0' in JS
    assert 'requestTotals:' in JS
    assert 'state.totalErrors += 1' in JS
    assert 'state.totalLongTasks += 1' in JS
    assert 'latencyHistogram' in JS


def test_visibility_and_polling_follow_dashboard_state() -> None:
    assert 'setText("obs-page-visibility", document.hidden ? "Background" : "Active")' in JS
    assert 'document.addEventListener("visibilitychange", handleVisibilityChange)' in JS
    assert 'if (!API_BASE || document.hidden || !dashboardIsOpen()) return;' in JS
    assert 'function startRefreshTimer()' in JS
    assert 'function stopRefreshTimer()' in JS
    assert 'init.refreshTimer = window.setInterval(refreshHealth, 60_000)' not in JS


def test_backend_empty_endpoint_result_does_not_fall_back_to_browser_rows() -> None:
    assert 'if (Array.isArray(serverRows))' in JS
    assert 'if (Array.isArray(serverRows) && serverRows.length)' not in JS


def test_population_labels_identify_server_vs_browser_data() -> None:
    assert 'function updatePopulationLabels(usingBackend)' in JS
    assert 'Server · rolling 5 minutes' in JS
    assert 'Browser session' in JS


def test_main_renderer_owns_slowest_endpoint_headline() -> None:
    assert 'function renderLatencyHeadline(summary, usingBackend)' in JS
    assert 'window.NIGHTAZIMUTH_OBSERVABILITY_LATENCY?.slowest' in JS
    assert 'label.textContent = "Slowest API endpoint"' in JS
    assert 'window.addEventListener("nightazimuth:latency-update", render)' in JS


def test_static_data_source_placeholder_is_removed_before_dashboard_use() -> None:
    assert 'function removeStaticDataSourcePlaceholder()' in JS
    assert 'row.querySelector("strong")?.textContent === "Data source detail"' in JS
    assert 'removeStaticDataSourcePlaceholder();' in JS


def test_dashboard_preserves_single_viewport_layout() -> None:
    assert "position: fixed;" in CSS
    assert "inset: 0;" in CSS
    assert "overflow: hidden;" in CSS
    assert "grid-template-rows" in CSS
