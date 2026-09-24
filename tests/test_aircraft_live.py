from datetime import datetime, timedelta, timezone

from nightazimuth.aircraft import (
    AircraftObservation,
    AircraftObserver,
    AircraftSnapshot,
    AircraftSnapshotState,
    AircraftSourceKind,
)
from nightazimuth.aircraft_live import build_sky_aircraft
from nightazimuth.aircraft_motion import AircraftMotionHistory, AircraftPositionState


BASE = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)


def _observation(
    *,
    icao24: str = "40621d",
    lat: float = 0.0,
    lon: float = 0.01,
    altitude: float | None = 1000.0,
    on_ground: bool = False,
    seconds_old: float = 0.0,
) -> AircraftObservation:
    return AircraftObservation(
        icao24=icao24,
        callsign="TEST1",
        latitude_deg=lat,
        longitude_deg=lon,
        barometric_altitude_m=None,
        geometric_altitude_m=altitude,
        ground_speed_mps=100.0,
        track_deg=90.0,
        vertical_rate_mps=0.0,
        squawk=None,
        on_ground=on_ground,
        position_observed_at=BASE - timedelta(seconds=seconds_old),
        contact_observed_at=None,
        source_id="test",
        source_label="Test source",
        source_kind=AircraftSourceKind.INTERNET,
    )


def _snapshot(*observations: AircraftObservation) -> AircraftSnapshot:
    return AircraftSnapshot(
        observations=tuple(observations),
        source_id="test",
        source_label="Test source",
        fetched_at=BASE,
        source_observed_at=BASE,
        coverage_description="test",
        state=AircraftSnapshotState.LIVE,
    )


def test_builds_above_horizon_view_contact():
    history = AircraftMotionHistory()
    contacts = build_sky_aircraft(
        _snapshot(_observation()),
        AircraftObserver(0.0, 0.0, 0.0),
        history,
        at=BASE,
    )

    assert len(contacts) == 1
    contact = contacts[0]
    assert contact.icao24 == "40621d"
    assert contact.source_label == "Test source"
    assert contact.position_state == AircraftPositionState.MEASURED
    assert contact.azimuth_deg > 89.0
    assert contact.elevation_deg > 0.0
    assert contact.future_track[0].seconds_from_now == 0.0
    assert len(contact.future_track) >= 2


def test_projected_track_moves_east_for_eastbound_aircraft():
    contacts = build_sky_aircraft(
        _snapshot(_observation()),
        AircraftObserver(0.0, 0.0, 0.0),
        AircraftMotionHistory(prediction_limit_seconds=15.0),
        at=BASE,
        projection_seconds=(5.0, 10.0, 15.0),
    )

    track = contacts[0].future_track
    assert [point.seconds_from_now for point in track] == [0.0, 5.0, 10.0, 15.0]
    assert track[-1].azimuth_deg > 89.0


def test_ground_contacts_are_excluded_by_default():
    contacts = build_sky_aircraft(
        _snapshot(_observation(on_ground=True)),
        AircraftObserver(0.0, 0.0, 0.0),
        AircraftMotionHistory(),
        at=BASE,
    )

    assert contacts == []


def test_contact_without_altitude_is_not_fabricated():
    contacts = build_sky_aircraft(
        _snapshot(_observation(altitude=None)),
        AircraftObserver(0.0, 0.0, 0.0),
        AircraftMotionHistory(),
        at=BASE,
    )

    assert contacts == []


def test_stale_prediction_is_hidden_by_default():
    history = AircraftMotionHistory(prediction_limit_seconds=5.0)
    old = _observation(seconds_old=10.0)
    contacts = build_sky_aircraft(
        _snapshot(old),
        AircraftObserver(0.0, 0.0, 0.0),
        history,
        at=BASE,
    )

    assert contacts == []


def test_stale_prediction_can_be_exposed_for_diagnostics():
    history = AircraftMotionHistory(prediction_limit_seconds=5.0)
    old = _observation(seconds_old=10.0)
    contacts = build_sky_aircraft(
        _snapshot(old),
        AircraftObserver(0.0, 0.0, 0.0),
        history,
        at=BASE,
        include_stale=True,
    )

    assert len(contacts) == 1
    assert contacts[0].position_state == AircraftPositionState.STALE
    assert contacts[0].position_age_seconds == 10.0
