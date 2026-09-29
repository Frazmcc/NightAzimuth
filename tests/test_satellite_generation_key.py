from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from nightazimuth.api import app
from nightazimuth.celestrak import CelestrakClient
import nightazimuth.tracker as tracker_module


def test_versioned_group_load_returns_exact_cache_generation(tmp_path: Path) -> None:
    payload = [{"OBJECT_NAME": "ACTIVE SAT", "NORAD_CAT_ID": 10001}]
    client = CelestrakClient(cache_directory=tmp_path, cache_max_age_minutes=120)
    cache_path = client._cache_path("ACTIVE")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(payload), encoding="utf-8")

    loaded, generation = client.load_group_versioned("ACTIVE")
    stat = cache_path.stat()

    assert loaded == payload
    assert generation == (stat.st_mtime_ns, stat.st_size)


def test_satellite_endpoint_passes_versioned_catalogue_key_to_tracker(monkeypatch) -> None:
    observed_keys: list[object | None] = []

    class FakeClient:
        def __init__(self, *_args, **_kwargs) -> None:
            pass

        def load_group_versioned(self, group: str):
            assert group == "ACTIVE"
            return [{"OBJECT_NAME": "TEST SAT", "NORAD_CAT_ID": "12345"}], (123, 456)

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
            observed_keys.append(catalogue_cache_key)
            return []

    monkeypatch.setattr("nightazimuth.api_satellites.CelestrakClient", FakeClient)
    monkeypatch.setattr("nightazimuth.api_satellites.SatelliteTracker", FakeTracker)

    response = TestClient(app).get(
        "/api/v1/satellites?latitude=55.86&longitude=-4.25&identification_detail=false"
    )

    assert response.status_code == 200
    assert observed_keys == [(('ACTIVE', (123, 456)),)]


def test_explicit_generation_key_does_not_hash_catalogue_content(monkeypatch) -> None:
    tracker_module._clear_prepared_catalogue_cache()
    elements = [{"OBJECT_NAME": "TEST SAT", "NORAD_CAT_ID": "12345"}]
    build_calls = 0

    def fail_fingerprint(_elements):
        raise AssertionError("explicit catalogue generation must bypass content hashing")

    def fake_build(prepared_elements, cache_key):
        nonlocal build_calls
        build_calls += 1
        assert prepared_elements is elements
        return tracker_module._PreparedCatalogue(
            cache_key=cache_key,
            element_count=len(prepared_elements),
            valid_indices=(),
            satrecs=(),
        )

    monkeypatch.setattr(tracker_module, "_catalogue_fingerprint", fail_fingerprint)
    monkeypatch.setattr(tracker_module, "_build_prepared_catalogue", fake_build)

    first, first_hit = tracker_module._prepared_catalogue_for(
        elements,
        cache_key=(("ACTIVE", (123, 456)),),
    )
    second, second_hit = tracker_module._prepared_catalogue_for(
        elements,
        cache_key=(("ACTIVE", (123, 456)),),
    )

    assert first_hit is False
    assert second_hit is True
    assert second is first
    assert build_calls == 1
