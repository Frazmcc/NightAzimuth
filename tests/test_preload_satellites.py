from __future__ import annotations

import pytest

import nightazimuth.preload_satellites as preload_satellites
from nightazimuth.celestrak import CelestrakError


def test_preload_satellites_uses_runtime_cache_and_expected_groups(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    calls: list[str] = []
    cache_directories = []

    class FakeClient:
        def __init__(self, cache_directory) -> None:
            cache_directories.append(cache_directory)

        def load_group(self, group: str):
            calls.append(group)
            return [{"NORAD_CAT_ID": len(calls)}]

    monkeypatch.setattr(preload_satellites, "CelestrakClient", FakeClient)

    preload_satellites.main()

    expected_cache = (tmp_path / "data/cache/api").resolve()
    assert expected_cache.is_dir()
    assert cache_directories == [expected_cache]
    assert calls == ["ACTIVE", "LAST-30-DAYS", "STATIONS", "VISUAL"]


def test_preload_satellites_requires_active_catalogue(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    class FailingClient:
        def __init__(self, cache_directory) -> None:
            pass

        def load_group(self, group: str):
            raise CelestrakError(f"{group} unavailable")

    monkeypatch.setattr(preload_satellites, "CelestrakClient", FailingClient)

    with pytest.raises(CelestrakError, match="ACTIVE unavailable"):
        preload_satellites.main()


def test_preload_satellites_rejects_empty_active_catalogue(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    class EmptyClient:
        def __init__(self, cache_directory) -> None:
            pass

        def load_group(self, group: str):
            return []

    monkeypatch.setattr(preload_satellites, "CelestrakClient", EmptyClient)

    with pytest.raises(CelestrakError, match="ACTIVE catalogue was empty"):
        preload_satellites.main()


def test_preload_satellites_allows_optional_group_failure(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    calls: list[str] = []

    class PartiallyFailingClient:
        def __init__(self, cache_directory) -> None:
            pass

        def load_group(self, group: str):
            calls.append(group)
            if group == "VISUAL":
                raise CelestrakError("VISUAL unavailable")
            return [{"NORAD_CAT_ID": len(calls)}]

    monkeypatch.setattr(preload_satellites, "CelestrakClient", PartiallyFailingClient)

    preload_satellites.main()

    assert calls == ["ACTIVE", "LAST-30-DAYS", "STATIONS", "VISUAL"]
