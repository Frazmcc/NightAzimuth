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
    assert 'observability.js?v=22.0.0' in HTML
    assert HTML.index('observability.js?v=22.0.0') < HTML.index('app.js?v=21.11.7')


def test_dashboard_uses_versioned_health_and_backend_telemetry_endpoints() -> None:
    assert '`${API_BASE}/api/v1/health`' in JS
    assert '`${API_BASE}/api/v1/observability`' in JS
    assert 'window.fetch = async function observedFetch' in JS
    assert 'PerformanceObserver' in JS
    assert 'unhandledrejection' in JS


def test_dashboard_surfaces_aircraft_provider_metadata_from_real_responses() -> None:
    assert 'source.provider_failover_used' in JS
    assert 'source.fallback_used' in JS
    assert 'source.source_observed_at' in JS
    assert 'response.clone().json()' in JS
    assert 'state.lastContactChangeAt' not in JS
    assert 'sourceFreshnessText()' in JS


def test_dashboard_tracks_cumulative_session_counts_while_bounding_detail_buffers() -> None:
    assert 'totalErrors: 0' in JS
    assert 'totalLongTasks: 0' in JS
    assert 'requestTotals:' in JS
    assert 'state.totalErrors += 1' in JS
    assert 'state.totalLongTasks += 1' in JS
    assert 'latencyHistogram' in JS
    assert 'if (state.errors.length > MAX_ERRORS)' in JS
    assert 'if (state.longTasks.length > MAX_LONG_TASKS)' in JS


def test_dashboard_visibility_status_is_live() -> None:
    assert 'setText("obs-page-visibility", document.hidden ? "Background" : "Active")' in JS
    assert 'document.addEventListener("visibilitychange", handleVisibilityChange)' in JS


def test_health_polling_only_runs_while_dashboard_is_visible() -> None:
    assert 'if (!API_BASE || document.hidden || !dashboardIsOpen()) return;' in JS
    assert 'function startRefreshTimer()' in JS
    assert 'function stopRefreshTimer()' in JS
    assert 'if (!dashboardIsOpen() || document.hidden) return;' in JS
    assert 'refreshHealth();\n      startRefreshTimer();' in JS
    assert 'observeContacts();\n    render();' in JS
    assert 'init.refreshTimer = window.setInterval(refreshHealth, 60_000)' not in JS


def test_dashboard_does_not_invent_unavailable_server_metrics() -> None:
    assert "Data source detail" in HTML
    assert "Not exposed yet" in HTML
    assert "server CPU" not in HTML.lower()
    assert "messages/sec" not in HTML.lower()


def test_dashboard_preserves_single_viewport_layout() -> None:
    assert "position: fixed;" in CSS
    assert "inset: 0;" in CSS
    assert "overflow: hidden;" in CSS
    assert "grid-template-rows" in CSS
