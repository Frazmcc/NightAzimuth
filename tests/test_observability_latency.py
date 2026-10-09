from pathlib import Path


HTML = Path("web/index.html").read_text(encoding="utf-8")
LATENCY = Path("web/observability-latency.js").read_text(encoding="utf-8")


def test_latency_interceptor_loads_before_application_requests() -> None:
    assert 'observability-latency.js?v=22.1.2' in HTML
    assert 'observability.js?v=22.1.2' in HTML
    assert HTML.index('observability-latency.js?v=22.1.2') < HTML.index('observability.js?v=22.1.2')
    assert HTML.index('observability.js?v=22.1.2') < HTML.index('app.js?v=22.5.5')
    assert "const previousFetch = window.fetch.bind(window);" in LATENCY
    assert "window.fetch = async function latencyObservedFetch" in LATENCY


def test_server_timing_headers_are_parsed() -> None:
    assert 'response.headers.get("Server-Timing")' in LATENCY
    assert "function parseServerTiming" in LATENCY
    assert "admission_wait" in LATENCY
    assert "provider_" in LATENCY
    assert "shared_wait" in LATENCY


def test_aircraft_route_latency_is_normalized_by_endpoint_family() -> None:
    assert 'path.startsWith("/api/v1/aircraft/route/")' in LATENCY
    assert 'return "/api/v1/aircraft/route";' in LATENCY


def test_endpoint_specific_latency_health_is_rendered_and_published() -> None:
    assert "Endpoint latency health" in LATENCY
    assert "Excellent" in LATENCY
    assert "Elevated" in LATENCY
    assert "Very slow" in LATENCY
    assert "function publishSlowest(slowest)" in LATENCY
    assert "window.NIGHTAZIMUTH_OBSERVABILITY_LATENCY" in LATENCY
    assert 'new CustomEvent("nightazimuth:latency-update")' in LATENCY


def test_health_and_observability_are_not_selected_as_application_slowest() -> None:
    assert 'row.path !== "/api/v1/health"' in LATENCY
    assert 'row.path !== "/api/v1/observability"' in LATENCY
    assert "const slowest = applicationRows[0] || null;" in LATENCY
    assert "|| rows[0]" not in LATENCY


def test_timing_breakdown_tracks_latest_response_even_without_header() -> None:
    assert "stats.timings.push(serverTiming);" in LATENCY
    assert "if (serverTiming.length)" not in LATENCY
    assert "No Server-Timing breakdown exposed by this endpoint yet." in LATENCY
    assert "Latest response" in LATENCY
    assert "timing.durationMs" in LATENCY
