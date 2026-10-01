from pathlib import Path


CONFIG = Path("web/config.js").read_text(encoding="utf-8")
LATENCY = Path("web/observability-latency.js").read_text(encoding="utf-8")


def test_latency_interceptor_loads_before_application_requests() -> None:
    assert 'observability-latency.js?v=22.1.0' in CONFIG
    assert "document.write" in CONFIG
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
    assert 'label.textContent = "Slowest API endpoint"' in LATENCY
    assert "Excellent" in LATENCY
    assert "Elevated" in LATENCY
    assert "Very slow" in LATENCY


def test_health_endpoint_is_not_selected_as_slowest_application_endpoint() -> None:
    assert 'path !== "/api/v1/health"' in LATENCY
    assert 'path !== "/api/v1/observability"' in LATENCY


def test_timing_breakdown_uses_real_response_headers_only() -> None:
    assert "No Server-Timing breakdown exposed by this endpoint yet." in LATENCY
    assert "Latest response" in LATENCY
    assert "timing.durationMs" in LATENCY
