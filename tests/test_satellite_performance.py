from time import time_ns

from fastapi.testclient import TestClient

from nightazimuth.api import app
import nightazimuth.api_satellites as satellites_module


def test_satellite_endpoint_exposes_internal_stage_timings(monkeypatch) -> None:
    class FakeClient:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def load_group(self, _group: str):
            return [{"OBJECT_NAME": "TEST SAT", "NORAD_CAT_ID": "12345"}]

    class FakeTracker:
        def __init__(self, _observer) -> None:
            self.last_timings = {}

        def positions_above_horizon(self, elements, *, minimum_elevation_deg, at):
            assert list(elements)
            assert minimum_elevation_deg == 0.0
            assert at.tzinfo is not None
            self.last_timings = {
                "prepare_ms": 1.0,
                "propagation_ms": 2.0,
                "track_build_ms": 3.0,
            }
            return []

    monkeypatch.setattr("nightazimuth.api_satellites.CelestrakClient", FakeClient)
    monkeypatch.setattr("nightazimuth.api_satellites.SatelliteTracker", FakeTracker)

    response = TestClient(app).get(
        "/api/v1/satellites?latitude=55.86&longitude=-4.25&identification_detail=false"
    )

    assert response.status_code == 200
    timing = response.headers["Server-Timing"]
    for stage in (
        "lock_wait",
        "catalogue_load",
        "catalogue_merge",
        "tracker_init",
        "prepare",
        "propagate",
        "track_build",
        "payload_build",
        "total",
    ):
        assert f"{stage};dur=" in timing
    assert "prepare;dur=1.0" in timing
    assert "propagate;dur=2.0" in timing
    assert "track_build;dur=3.0" in timing


def test_repeat_hosted_group_uses_hot_catalogue_reference(monkeypatch) -> None:
    satellites_module._clear_hot_group_cache()
    payload = [{"OBJECT_NAME": "TEST SAT", "NORAD_CAT_ID": "12345"}]
    generation = (time_ns(), 123)
    load_calls: list[str] = []

    class FakeClient:
        cache_max_age_minutes = 125

        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def load_group_versioned(self, group: str):
            load_calls.append(group)
            return payload, generation

    class FakeTracker:
        def __init__(self, _observer) -> None:
            self.last_timings = {}

        def positions_above_horizon(
            self,
            elements,
            *,
            minimum_elevation_deg,
            at,
            catalogue_cache_key=None,
        ):
            assert list(elements)
            assert minimum_elevation_deg == 0.0
            assert at.tzinfo is not None
            assert catalogue_cache_key is not None
            self.last_timings = {
                "prepare_ms": 0.0,
                "propagation_ms": 0.0,
                "track_build_ms": 0.0,
            }
            return []

    monkeypatch.setattr("nightazimuth.api_satellites.CelestrakClient", FakeClient)
    monkeypatch.setattr("nightazimuth.api_satellites.SatelliteTracker", FakeTracker)

    client = TestClient(app)
    first = client.get(
        "/api/v1/satellites?latitude=55.86&longitude=-4.25&identification_detail=false"
    )
    second = client.get(
        "/api/v1/satellites?latitude=55.86&longitude=-4.25&identification_detail=false"
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert load_calls == ["ACTIVE"]
    satellites_module._clear_hot_group_cache()
