from nightazimuth.celestial_profile import profile_snapshot_key


class _OwnerWithLocationKey:
    def __init__(self) -> None:
        self.keys = {
            "Home": ("Home", 51.5, -0.1, 30.0),
        }

    def _location_key(self, profile_name: str) -> tuple[str, float, float, float] | None:
        return self.keys.get(profile_name)


def test_profile_snapshot_key_uses_location_key_when_available() -> None:
    owner = _OwnerWithLocationKey()
    assert profile_snapshot_key(owner, "Home") == ("Home", 51.5, -0.1, 30.0)


def test_profile_snapshot_key_falls_back_to_profile_name() -> None:
    owner = object()
    assert profile_snapshot_key(owner, "Home") == "Home"


def test_profile_snapshot_key_is_none_without_selection() -> None:
    owner = _OwnerWithLocationKey()
    assert profile_snapshot_key(owner, None) is None
