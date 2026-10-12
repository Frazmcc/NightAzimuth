"""Contract tests for the opt-in ALEN-compatible satellite API."""
from datetime import datetime, timezone, timedelta

from fastapi.testclient import TestClient

from nightazimuth.api import app
from nightazimuth import api_satellites_alen as bridge


def sample_payload(age_seconds=1):
    now=datetime.now(timezone.utc)-timedelta(seconds=age_seconds)
    return {
        "satellites": [{
            "norad": 25544,
            "name": "ISS",
            "azimuth_deg": 359,
            "elevation_deg": 35,
            "trajectory": [
                {"offset_seconds": 0, "azimuth_deg": 359, "elevation_deg": 35, "range_km": 450},
                {"offset_seconds": 2, "azimuth_deg": 1, "elevation_deg": 35.3, "range_km": 449},
            ],
        }],
        "diagnostics": {"position_sample_at": now.isoformat()},
    }


def test_bridge_preserves_alen_trajectory_and_wrap(monkeypatch):
    payload=sample_payload()
    class Response:
        def raise_for_status(self): pass
        def json(self): return payload
    class Client:
        def __init__(self, *args, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def get(self, url, params):
            assert url == bridge._ALEN_URL
            assert params["groups"] == "last-30-days,stations,visual"
            return Response()
    monkeypatch.setattr(bridge.httpx,"Client",Client)
    result=TestClient(app).get("/api/v1/satellites/alen?lat=55.86&lon=-4.25")
    assert result.status_code == 200
    assert result.json() == payload


def test_bridge_rejects_stale_and_invalid_trajectory():
    from pytest import raises
    with raises(ValueError, match="stale"):
        bridge._validate_payload(sample_payload(age_seconds=100))
    payload=sample_payload()
    payload["satellites"][0]["trajectory"][1]["offset_seconds"]=-1
    with raises(ValueError, match="trajectory"):
        bridge._validate_payload(payload)


def test_bridge_rejects_unsupported_groups():
    result=TestClient(app).get("/api/v1/satellites/alen?lat=55&lon=-4&groups=unknown")
    assert result.status_code == 422
