from __future__ import annotations

from datetime import datetime

from fastapi.testclient import TestClient

from nightazimuth import __version__
from nightazimuth.api import API_VERSION, app


def test_health_endpoint_contract() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["api_version"] == "v1"
    assert payload["api_version"] == API_VERSION
    assert payload["application_version"] == __version__

    timestamp = datetime.fromisoformat(payload["timestamp"])
    assert timestamp.utcoffset().total_seconds() == 0


def test_health_endpoint_does_not_require_configuration() -> None:
    client = TestClient(app)

    response = client.get("/api/v1/health")

    assert response.status_code == 200


def test_cors_allows_hosted_frontend() -> None:
    client = TestClient(app)

    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "https://nightazimuth.bismo.me",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "https://nightazimuth.bismo.me"


def test_cors_does_not_allow_unlisted_origin() -> None:
    client = TestClient(app)

    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "https://example.invalid",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert "access-control-allow-origin" not in response.headers


def test_api_rejects_oversized_query_string() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/health?" + ("x=" + "a" * 2050))
    assert response.status_code == 414
    assert response.json() == {"detail": "Query string too long"}


def test_api_security_headers_and_openapi_location() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["permissions-policy"] == "geolocation=(), camera=(), microphone=()"
    assert client.get("/api/openapi.json").status_code == 200
    assert client.get("/api/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 404
