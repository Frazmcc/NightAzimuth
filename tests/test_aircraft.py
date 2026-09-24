from datetime import datetime, timedelta, timezone

import pytest

from nightazimuth.aircraft import (
    AircraftObservation,
    AircraftObserver,
    AircraftSnapshotState,
    AircraftSourceKind,
    classify_snapshot_age,
)


def _observation(**overrides):
    values = {
        "icao24": "40621d",
        "callsign": " BAW123 ",
        "latitude_deg": 51.5,
        "longitude_deg": -0.1,
        "barometric_altitude_m": 3000.0,
        "geometric_altitude_m": 3050.0,
        "ground_speed_mps": 120.0,
        "track_deg": 361.0,
        "vertical_rate_mps": 2.0,
        "squawk": " 1234 ",
        "on_ground": False,
        "position_observed_at": datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc),
        "contact_observed_at": datetime(2026, 9, 21, 12, 0, 1, tzinfo=timezone.utc),
        "source_id": "test",
        "source_label": "Test",
        "source_kind": AircraftSourceKind.INTERNET,
    }
    values.update(overrides)
    return AircraftObservation(**values)


def test_observer_rejects_invalid_coordinates():
    with pytest.raises(ValueError):
        AircraftObserver(91.0, 0.0)
    with pytest.raises(ValueError):
        AircraftObserver(0.0, 181.0)


def test_observation_normalises_identity_and_track():
    observation = _observation()
    assert observation.icao24 == "40621d"
    assert observation.callsign == "BAW123"
    assert observation.squawk == "1234"
    assert observation.track_deg == pytest.approx(1.0)
    assert observation.preferred_altitude_m == 3050.0


def test_observation_rejects_naive_timestamp():
    with pytest.raises(ValueError):
        _observation(position_observed_at=datetime(2026, 9, 21, 12, 0))


def test_position_age_uses_observation_time_not_fetch_time():
    observation = _observation()
    now = observation.position_observed_at + timedelta(seconds=7.5)
    assert observation.position_age_seconds(now) == pytest.approx(7.5)


def test_snapshot_age_classification_has_explicit_states():
    assert classify_snapshot_age(5) == AircraftSnapshotState.LIVE
    assert classify_snapshot_age(30) == AircraftSnapshotState.AGING
    assert classify_snapshot_age(60) == AircraftSnapshotState.STALE
    assert classify_snapshot_age(None) == AircraftSnapshotState.AGING
