from datetime import datetime, timedelta, timezone

import pytest

from nightazimuth.aircraft import AircraftObservation, AircraftSourceKind
from nightazimuth.aircraft_motion import AircraftMotionHistory, AircraftPositionState


BASE = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)


def _observation(
    *,
    seconds: float,
    lat: float = 55.0,
    lon: float = -4.0,
    altitude: float | None = 1000.0,
    speed: float | None = 100.0,
    track: float | None = 90.0,
    vertical_rate: float | None = 0.0,
) -> AircraftObservation:
    return AircraftObservation(
        icao24="40621d",
        callsign="TEST1",
        latitude_deg=lat,
        longitude_deg=lon,
        barometric_altitude_m=None,
        geometric_altitude_m=altitude,
        ground_speed_mps=speed,
        track_deg=track,
        vertical_rate_mps=vertical_rate,
        squawk=None,
        on_ground=False,
        position_observed_at=BASE + timedelta(seconds=seconds),
        contact_observed_at=None,
        source_id="test",
        source_label="Test",
        source_kind=AircraftSourceKind.INTERNET,
    )


def test_exact_fix_is_measured():
    history = AircraftMotionHistory()
    history.add(_observation(seconds=0))

    resolved = history.resolve("40621d", BASE)

    assert resolved is not None
    assert resolved.state == AircraftPositionState.MEASURED
    assert resolved.latitude_deg == pytest.approx(55.0)


def test_interpolates_between_known_fixes():
    history = AircraftMotionHistory()
    history.add(_observation(seconds=0, lat=55.0, lon=-4.0, altitude=1000.0, track=350.0))
    history.add(_observation(seconds=10, lat=55.1, lon=-3.9, altitude=1200.0, track=10.0))

    resolved = history.resolve("40621d", BASE + timedelta(seconds=5))

    assert resolved is not None
    assert resolved.state == AircraftPositionState.INTERPOLATED
    assert resolved.latitude_deg == pytest.approx(55.05)
    assert resolved.longitude_deg == pytest.approx(-3.95)
    assert resolved.altitude_m == pytest.approx(1100.0)
    assert resolved.track_deg == pytest.approx(0.0)


def test_longitude_interpolation_uses_short_path_across_dateline():
    history = AircraftMotionHistory()
    history.add(_observation(seconds=0, lon=179.0))
    history.add(_observation(seconds=10, lon=-179.0))

    resolved = history.resolve("40621d", BASE + timedelta(seconds=5))

    assert resolved is not None
    assert abs(abs(resolved.longitude_deg) - 180.0) < 1e-6


def test_short_dead_reckoning_moves_aircraft_forward():
    history = AircraftMotionHistory(prediction_limit_seconds=15.0)
    history.add(_observation(seconds=0, lat=0.0, lon=0.0, speed=100.0, track=90.0))

    resolved = history.resolve("40621d", BASE + timedelta(seconds=10))

    assert resolved is not None
    assert resolved.state == AircraftPositionState.EXTRAPOLATED
    assert resolved.longitude_deg > 0.0
    assert abs(resolved.latitude_deg) < 0.001


def test_dead_reckoning_applies_vertical_rate():
    history = AircraftMotionHistory(prediction_limit_seconds=15.0)
    history.add(_observation(seconds=0, altitude=1000.0, vertical_rate=5.0))

    resolved = history.resolve("40621d", BASE + timedelta(seconds=10))

    assert resolved is not None
    assert resolved.altitude_m == pytest.approx(1050.0)


def test_prediction_hard_stops_as_stale():
    history = AircraftMotionHistory(prediction_limit_seconds=15.0)
    history.add(_observation(seconds=0))

    resolved = history.resolve("40621d", BASE + timedelta(seconds=16))

    assert resolved is not None
    assert resolved.state == AircraftPositionState.STALE
    assert resolved.latitude_deg == pytest.approx(55.0)
    assert resolved.longitude_deg == pytest.approx(-4.0)


def test_out_of_order_older_fix_is_ignored():
    history = AircraftMotionHistory()
    history.add(_observation(seconds=10, lat=55.1))
    history.add(_observation(seconds=5, lat=54.0))

    resolved = history.resolve("40621d", BASE + timedelta(seconds=10))

    assert resolved is not None
    assert resolved.latitude_deg == pytest.approx(55.1)


def test_duplicate_timestamp_replaces_fix():
    history = AircraftMotionHistory()
    history.add(_observation(seconds=0, lat=55.0))
    history.add(_observation(seconds=0, lat=56.0))

    resolved = history.resolve("40621d", BASE)

    assert resolved is not None
    assert resolved.latitude_deg == pytest.approx(56.0)


def test_history_is_bounded_by_count():
    history = AircraftMotionHistory(max_fixes_per_aircraft=3, max_history_age_seconds=999.0)
    for second in range(5):
        history.add(_observation(seconds=float(second), lat=55.0 + second / 100.0))

    assert history.resolve("40621d", BASE) is None
    resolved = history.resolve("40621d", BASE + timedelta(seconds=2))
    assert resolved is not None


def test_naive_resolution_time_is_rejected():
    history = AircraftMotionHistory()
    history.add(_observation(seconds=0))

    with pytest.raises(ValueError, match="timezone-aware"):
        history.resolve("40621d", datetime(2026, 9, 21, 12, 0))
