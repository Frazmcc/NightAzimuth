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
