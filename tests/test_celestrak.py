from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import threading
import time

import pytest

from nightazimuth.celestrak import (
    CelestrakClient,
    _clear_parsed_cache,
    _parsed_cache_entry_count,
)


def test_fresh_cache_is_loaded_without_network(tmp_path: Path) -> None:
    payload = [{"OBJECT_NAME": "TEST SAT", "NORAD_CAT_ID": 12345}]
    client = CelestrakClient(cache_directory=tmp_path, cache_max_age_minutes=120)
    cache_path = client._cache_path("STATIONS")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(payload), encoding="utf-8")

    assert client.load_group("STATIONS") == payload


def test_group_rejects_path_characters(tmp_path: Path) -> None:
    client = CelestrakClient(cache_directory=tmp_path)
    with pytest.raises(ValueError, match="letters, numbers"):
        client.load_group("../stations")
    with pytest.raises(ValueError, match="letters, numbers"):
        client.load_group("stations/../../escape")


@pytest.mark.parametrize(
    "group",
    ["../stations", "stations/../../escape", r"..\\stations", "stations.json", ""],
)
def test_cache_path_rejects_untrusted_path_components(tmp_path: Path, group: str) -> None:
    client = CelestrakClient(cache_directory=tmp_path)

    with pytest.raises(ValueError):
        client._cache_path(group)


def test_cache_path_is_resolved_beneath_cache_root(tmp_path: Path) -> None:
    client = CelestrakClient(cache_directory=tmp_path / "cache")

    path = client._cache_path("VISUAL")

    assert path.parent == (tmp_path / "cache").resolve()
    assert path.name.startswith("celestrak_")
    assert path.suffix == ".json"
    assert "visual" not in path.name
    assert path.is_relative_to(client.cache_directory)


def test_provider_timeout_defaults_to_ten_seconds(tmp_path: Path) -> None:
    client = CelestrakClient(cache_directory=tmp_path)

    assert client.timeout_seconds == 10.0


def test_default_cache_window_exceeds_provider_update_interval(tmp_path: Path) -> None:
    client = CelestrakClient(cache_directory=tmp_path)

    assert client.cache_max_age_minutes == 125


def test_cold_start_uses_mirror_when_provider_fails(tmp_path: Path, monkeypatch) -> None:
    payload = [{"OBJECT_NAME": "MIRROR SAT", "NORAD_CAT_ID": 54321}]
    client = CelestrakClient(cache_directory=tmp_path)

    def fail_provider(group: str):
        raise __import__("httpx").ConnectError("provider unavailable")

    monkeypatch.setattr(client, "_download_group", fail_provider)
    monkeypatch.setattr(client, "_download_mirror", lambda group: payload)

    assert client.load_group("VISUAL") == payload
    assert client._read_cache(client._cache_path("VISUAL")) == payload


def test_parsed_cache_is_reused_while_file_is_unchanged(tmp_path: Path) -> None:
    payload = [{"OBJECT_NAME": "ACTIVE SAT", "NORAD_CAT_ID": 10001}]
    client = CelestrakClient(cache_directory=tmp_path)
    cache_path = client._cache_path("ACTIVE")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(payload), encoding="utf-8")
    _clear_parsed_cache()

    first = client._read_cache(cache_path)
    second = client._read_cache(cache_path)

    assert first == payload
    assert second is first
    assert _parsed_cache_entry_count() == 1


def test_parsed_cache_replaces_old_file_generation_in_place(tmp_path: Path) -> None:
    old_payload = [{"OBJECT_NAME": "OLD ACTIVE", "NORAD_CAT_ID": 10001}]
    new_payload = [{"OBJECT_NAME": "NEW ACTIVE", "NORAD_CAT_ID": 10002}]
    client = CelestrakClient(cache_directory=tmp_path)
    cache_path = client._cache_path("ACTIVE")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text(json.dumps(old_payload), encoding="utf-8")
    _clear_parsed_cache()

    old = client._read_cache(cache_path)
    assert old == old_payload
    assert _parsed_cache_entry_count() == 1

    client._write_cache(cache_path, new_payload)
    current = client._read_cache(cache_path)

    assert current is new_payload
    assert current != old
    # The old ACTIVE generation must not remain as a second cache entry.
    assert _parsed_cache_entry_count() == 1


def test_parsed_cache_has_a_hard_entry_limit(tmp_path: Path) -> None:
    _clear_parsed_cache()
    client = CelestrakClient(cache_directory=tmp_path)

    for index in range(12):
        path = tmp_path / f"catalogue-{index}.json"
        path.write_text(json.dumps([{"NORAD_CAT_ID": index}]), encoding="utf-8")
        client._read_cache(path)

    assert _parsed_cache_entry_count() <= 8


def test_concurrent_refresh_downloads_a_group_only_once(tmp_path: Path, monkeypatch) -> None:
    payload = [{"OBJECT_NAME": "ACTIVE SAT", "NORAD_CAT_ID": 10001}]
    client = CelestrakClient(cache_directory=tmp_path)
    calls = 0
    guard = threading.Lock()

    def download_once(group: str):
        nonlocal calls
        assert group == "ACTIVE"
        with guard:
            calls += 1
        time.sleep(0.05)
        return payload

    monkeypatch.setattr(client, "_download_group", download_once)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _index: client.load_group("ACTIVE"), range(2)))

    assert results == [payload, payload]
    assert calls == 1
