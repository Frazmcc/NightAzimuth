import json
from pathlib import Path

import pytest

from nightazimuth.celestrak import CelestrakClient


def test_fresh_cache_is_loaded_without_network(tmp_path: Path) -> None:
    payload = [{"OBJECT_NAME": "TEST SAT", "NORAD_CAT_ID": 12345}]
    cache_path = tmp_path / "celestrak_stations.json"
    cache_path.write_text(json.dumps(payload), encoding="utf-8")

    client = CelestrakClient(cache_directory=tmp_path, cache_max_age_minutes=120)

    assert client.load_group("STATIONS") == payload


def test_group_rejects_path_characters(tmp_path: Path) -> None:
    client = CelestrakClient(cache_directory=tmp_path)
    with pytest.raises(ValueError, match="letters, numbers"):
        client.load_group("../stations")
    with pytest.raises(ValueError, match="letters, numbers"):
        client.load_group("stations/../../escape")
