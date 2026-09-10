from pathlib import Path

from nightazimuth.location_profiles import LocationProfile, LocationProfileStore


def test_location_profiles_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "locations.json"
    store = LocationProfileStore(path)
    profiles = [
        LocationProfile(
            name="Test Observatory",
            latitude=0.0,
            longitude=0.0,
            altitude_m=100.0,
        ),
        LocationProfile(
            name="Test Field Site",
            latitude=10.0,
            longitude=20.0,
            altitude_m=200.0,
        ),
    ]

    store.save(profiles, "Test Field Site")
    loaded_profiles, selected = store.load()

    assert loaded_profiles == profiles
    assert selected == "Test Field Site"


def test_missing_location_file_returns_empty(tmp_path: Path) -> None:
    store = LocationProfileStore(tmp_path / "missing.json")

    profiles, selected = store.load()

    assert profiles == []
    assert selected is None
