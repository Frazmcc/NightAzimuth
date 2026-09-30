from time import time_ns

from fastapi.testclient import TestClient

from nightazimuth.api import app
import nightazimuth.api_satellites as satellites_module
from nightazimuth.config import ObserverConfig
import nightazimuth.tracker as tracker_module
from nightazimuth.tracker import SatelliteTracker


def test_satellite_endpoint_exposes_internal_stage_timings(monkeypatch) -> None:
    class FakeClient:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def load_group(self, _group: str):
            return [{"OBJECT_NAME": "TEST SAT", "NORAD_CAT_ID": "12345"}]

    class FakeTracker:
        def __init__(self, _observer) -> None:
            self.init_timings = {
                "tracker_timescale_ms": 4.0,
                "tracker_observer_ms": 5.0,
            }
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
        "tracker_timescale",
        "tracker_observer",
        "prepare",
        "propagate",
        "track_build",
        "payload_build",
        "total",
    ):
        assert f"{stage};dur=" in timing
    assert "tracker_timescale;dur=4.0" in timing
    assert "tracker_observer;dur=5.0" in timing
    assert "prepare;dur=1.0" in timing
    assert "propagate;dur=2.0" in timing
    assert "track_build;dur=3.0" in timing


def test_real_tracker_records_init_timing_breakdown() -> None:
    tracker = SatelliteTracker(
        ObserverConfig(latitude=55.86, longitude=-4.25, altitude_m=50.0)
    )

    assert tracker.init_timings["tracker_timescale_ms"] >= 0.0
    assert tracker.init_timings["tracker_observer_ms"] >= 0.0
    assert tracker.init_timings["tracker_init_internal_ms"] >= 0.0
    assert tracker.init_timings["tracker_init_internal_ms"] >= tracker.init_timings[
        "tracker_timescale_ms"
    ]
    assert tracker.init_timings["tracker_init_internal_ms"] >= tracker.init_timings[
        "tracker_observer_ms"
    ]


def test_satellite_trackers_reuse_one_process_timescale(monkeypatch) -> None:
    tracker_module._clear_timescale_cache()
    calls = 0
    shared = object()

    def fake_timescale():
        nonlocal calls
        calls += 1
        return shared

    monkeypatch.setattr(tracker_module.load, "timescale", fake_timescale)
    observer = ObserverConfig(latitude=55.86, longitude=-4.25, altitude_m=50.0)

    try:
        first = SatelliteTracker(observer)
        second = SatelliteTracker(observer)

        assert calls == 1
        assert first._timescale is shared
        assert second._timescale is shared
    finally:
        tracker_module._clear_timescale_cache()


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


def test_repeat_hosted_detail_reuses_zero_copy_merged_catalogue(monkeypatch) -> None:
    satellites_module._clear_hot_group_cache()
    payload = [{"OBJECT_NAME": "TEST SAT", "NORAD_CAT_ID": "12345"}]
    modified_ns = time_ns()
    load_calls: list[str] = []
    merge_build_calls = 0
    seen_element_ids: list[tuple[int, ...]] = []

    class FakeClient:
        cache_max_age_minutes = 125

        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def load_group_versioned(self, group: str):
            load_calls.append(group)
            size = {
                "ACTIVE": 100,
                "LAST-30-DAYS": 101,
                "STATIONS": 102,
                "VISUAL": 103,
            }[group]
            return payload, (modified_ns, size)

    original_build = satellites_module._build_merged_catalogue

    def counted_build(requested_groups, group_payloads):
        nonlocal merge_build_calls
        merge_build_calls += 1
        return original_build(requested_groups, group_payloads)

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
            element_list = list(elements)
            assert len(element_list) == 1
            assert set(element_list[0]["_nightazimuth_groups"]) == {
                "ACTIVE",
                "LAST-30-DAYS",
                "STATIONS",
                "VISUAL",
            }
            assert minimum_elevation_deg == 0.0
            assert at.tzinfo is not None
            assert catalogue_cache_key is not None
            seen_element_ids.append(tuple(id(element) for element in element_list))
            self.last_timings = {
                "prepare_ms": 0.0,
                "propagation_ms": 0.0,
                "track_build_ms": 0.0,
            }
            return []

    monkeypatch.setattr("nightazimuth.api_satellites.CelestrakClient", FakeClient)
    monkeypatch.setattr("nightazimuth.api_satellites.SatelliteTracker", FakeTracker)
    monkeypatch.setattr("nightazimuth.api_satellites._build_merged_catalogue", counted_build)

    client = TestClient(app)
    first = client.get("/api/v1/satellites?latitude=55.86&longitude=-4.25")
    second = client.get("/api/v1/satellites?latitude=55.86&longitude=-4.25")

    assert first.status_code == 200
    assert second.status_code == 200
    assert set(load_calls) == {"ACTIVE", "LAST-30-DAYS", "STATIONS", "VISUAL"}
    assert len(load_calls) == 4
    assert merge_build_calls == 1
    assert seen_element_ids[0] == seen_element_ids[1]
    assert "_nightazimuth_groups" not in payload[0]
    satellites_module._clear_hot_group_cache()
