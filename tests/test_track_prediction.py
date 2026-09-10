from datetime import datetime, timezone

import pytest

from nightazimuth.config import ObserverConfig
from nightazimuth import track_prediction
from nightazimuth.track_prediction import TrackPredictor


class _Degrees:
    def __init__(self, values: list[float]) -> None:
        self.degrees = values


class _FakeTopocentric:
    def altaz(self):
        altitude = _Degrees([10.0, 12.0, 14.0, 16.0, 18.0, 20.0, 22.0])
        azimuth = _Degrees([250.0, 252.0, 254.0, 256.0, 258.0, 260.0, 262.0])
        return altitude, azimuth, object()


class _FakeDifference:
    def at(self, _times):
        return _FakeTopocentric()


class _FakeSatellite:
    def __sub__(self, _observer):
        return _FakeDifference()


class _FakeEarthSatellite:
    @classmethod
    def from_omm(cls, _timescale, _fields):
        return _FakeSatellite()


def test_short_track_contains_current_and_three_minute_endpoint(monkeypatch) -> None:
    monkeypatch.setattr(track_prediction, "EarthSatellite", _FakeEarthSatellite)
    predictor = TrackPredictor(ObserverConfig(latitude=55.0, longitude=-4.0))

    tracks = predictor.predict(
        [{"NORAD_CAT_ID": 12345}],
        duration_seconds=180,
        step_seconds=30,
        at=datetime(2026, 9, 10, 21, 0, tzinfo=timezone.utc),
    )

    points = tracks["12345"]
    assert len(points) == 7
    assert points[0].seconds_from_now == 0
    assert points[-1].seconds_from_now == 180
    assert points[0].azimuth_deg == 250.0
    assert points[-1].azimuth_deg == 262.0
    assert points[0].elevation_deg == 10.0
    assert points[-1].elevation_deg == 22.0


def test_invalid_track_duration_is_rejected() -> None:
    predictor = TrackPredictor(ObserverConfig(latitude=55.0, longitude=-4.0))
    with pytest.raises(ValueError, match="duration"):
        predictor.predict([], duration_seconds=0)


def test_invalid_track_step_is_rejected() -> None:
    predictor = TrackPredictor(ObserverConfig(latitude=55.0, longitude=-4.0))
    with pytest.raises(ValueError, match="step"):
        predictor.predict([], step_seconds=0)
