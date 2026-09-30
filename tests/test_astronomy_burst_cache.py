from __future__ import annotations

from fastapi import Response

from nightazimuth.burst_cache import BurstResultCache
from nightazimuth import api_satellites_cached


def test_burst_cache_reuses_and_expires(monkeypatch):
    now = 100.0
    monkeypatch.setattr("nightazimuth.burst_cache.monotonic", lambda: now)
    cache = BurstResultCache[dict[str, int]](ttl_seconds=2.0, max_entries=4)

    payload = {"value": 1}
    cache.put(("key",), payload)
    assert cache.get(("key",)) is payload

    now = 102.0
    assert cache.get(("key",)) is None


def test_burst_cache_evicts_oldest_entry():
    cache = BurstResultCache[int](ttl_seconds=60.0, max_entries=2)
    cache.put("a", 1)
    cache.put("b", 2)
    cache.put("c", 3)

    assert cache.get("a") is None
    assert cache.get("b") == 2
    assert cache.get("c") == 3


def test_identical_satellite_requests_reuse_recent_payload(monkeypatch):
    calls = 0
    payload = {"count": 1, "satellites": []}

    def fake_satellites(**kwargs):
        nonlocal calls
        calls += 1
        response = kwargs["response"]
        response.headers["Server-Timing"] = "propagate;dur=123.4"
        return payload

    monkeypatch.setattr(api_satellites_cached, "_base_satellites", fake_satellites)
    api_satellites_cached._BURST_CACHE.clear()

    first_response = Response()
    first = api_satellites_cached.satellites(
        response=first_response,
        latitude=51.5,
        longitude=-0.1,
        altitude_m=0.0,
        minimum_elevation_deg=0.0,
        group="ACTIVE",
        identification_detail=True,
    )
    second_response = Response()
    second = api_satellites_cached.satellites(
        response=second_response,
        latitude=51.5,
        longitude=-0.1,
        altitude_m=0.0,
        minimum_elevation_deg=0.0,
        group="active",
        identification_detail=True,
    )

    assert calls == 1
    assert first is payload
    assert second is payload
    assert 'burst_cache;desc="miss"' in first_response.headers["Server-Timing"]
    assert 'burst_cache;desc="hit"' in second_response.headers["Server-Timing"]
