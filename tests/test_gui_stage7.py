from nightazimuth.gui import NightAzimuthApp
from nightazimuth.gui_stage7 import Stage7NightAzimuthApp
from nightazimuth.location_profiles import LocationProfile


class _FakeLiveView:
    def __init__(self) -> None:
        self.snapshots: list[object | None] = []

    def set_star_field(self, snapshot: object | None) -> None:
        self.snapshots.append(snapshot)


def test_invalidate_stale_star_field_clears_live_view_immediately() -> None:
    app = Stage7NightAzimuthApp.__new__(Stage7NightAzimuthApp)
    app.selected_name = "Home"
    app.profiles = [LocationProfile(name="Home", latitude=56.0, longitude=-3.0, altitude_m=120.0)]
    app._star_snapshot = object()
    app._star_snapshot_profile = "Home"
    app._star_snapshot_location_key = ("Home", 55.0, -4.0, 100.0)
    app._star_loaded_monotonic = 12.5
    app.live_view = _FakeLiveView()

    app._invalidate_stale_star_field()

    assert app._star_snapshot is None
    assert app._star_snapshot_profile is None
    assert app._star_snapshot_location_key is None
    assert app._star_loaded_monotonic == 0.0
    assert app.live_view.snapshots == [None]


def test_location_change_path_invalidates_stale_star_field(monkeypatch) -> None:
    app = Stage7NightAzimuthApp.__new__(Stage7NightAzimuthApp)
    calls: list[str] = []

    def fake_base_on_location_changed(self, event=None) -> None:
        calls.append("super")

    def fake_invalidate() -> None:
        calls.append("invalidate")

    monkeypatch.setattr(NightAzimuthApp, "_on_location_changed", fake_base_on_location_changed)
    app._invalidate_stale_star_field = fake_invalidate

    app._on_location_changed()

    assert calls == ["super", "invalidate"]
