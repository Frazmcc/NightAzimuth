import json
from pathlib import Path

import pytest

from nightazimuth.celestrak import CelestrakClient


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
