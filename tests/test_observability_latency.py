from pathlib import Path


HTML = Path("web/index.html").read_text(encoding="utf-8")
LATENCY = Path("web/observability-latency.js").read_text(encoding="utf-8")


def test_latency_interceptor_loads_before_application_requests() -> None:
    assert 'observability-latency.js?v=22.1.2' in HTML
    assert 'observability.js?v=22.1.2' in HTML
    assert HTML.index('observability-latency.js?v=22.1.2') < HTML.index('observability.js?v=22.1.2')
    assert HTML.index('observability.js?v=22.1.2') < HTML.index('app.js?v=21.11.7')
    assert "const previousFetch = window.fetch.bind(window);" in LATENCY
    assert "window.fetch = async function latencyObservedFetch" in LATENCY


def test_server_timing_headers_are_parsed() -> None:
    assert 'response.headers.get("Server-Timing")' in LATENCY
    assert "function parseServerTiming" in LATENCY
    assert "admission_wait" in LATENCY
    assert "provider_" in LATENCY
    assert "shared_wait" in LATENCY


def test_endpoint_specific_latency_health_is_rendered() -> None:
    assert "Endpoint latency health" in LATENCY
    assert "Excellent" in LATENCY
    assert "Elevated" in LATENCY
    assert "Very slow" in LATENCY


def test_health_endpoint_is_not_selected_for_timing_breakdown() -> None:
    assert 'row.path !== "/api/v1/health"' in LATENCY
    assert 'row.path !== "/api/v1/observability"' in LATENCY


def test_timing_breakdown_tracks_latest_response_even_without_header() -> None:
    assert "stats.timings.push(serverTiming);" in LATENCY
    assert "if (serverTiming.length)" not in LATENCY
    assert "No Server-Timing breakdown exposed by this endpoint yet." in LATENCY
    assert "Latest response" in LATENCY
    assert "timing.durationMs" in LATENCY
