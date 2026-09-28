from __future__ import annotations

from datetime import UTC, datetime

from nightazimuth.config import ObserverConfig
from nightazimuth.tracker import SatelliteTracker


VANGUARD_OMM = {
    "ARG_OF_PERICENTER": 162.2516,
    "BSTAR": -2.2483e-05,
    "CENTER_NAME": "EARTH",
    "CLASSIFICATION_TYPE": "U",
    "ECCENTRICITY": 0.1845686,
    "ELEMENT_SET_NO": 999,
    "EPHEMERIS_TYPE": 0,
    "EPOCH": "2020-10-13T04:52:48.472320",
    "INCLINATION": 34.2443,
    "MEAN_ANOMALY": 205.2356,
    "MEAN_ELEMENT_THEORY": "SGP4",
    "MEAN_MOTION": 10.84869164,
    "MEAN_MOTION_DDOT": 0.0,
    "MEAN_MOTION_DOT": -1.6e-07,
    "NORAD_CAT_ID": 5,
    "OBJECT_ID": "1958-002B",
    "OBJECT_NAME": "VANGUARD 1",
    "RA_OF_ASC_NODE": 225.5254,
    "REF_FRAME": "TEME",
    "REV_AT_EPOCH": 21814,
    "TIME_SYSTEM": "UTC",
}


def test_batch_tracker_propagates_omm_and_builds_track() -> None:
    tracker = SatelliteTracker(ObserverConfig(latitude=0.0, longitude=0.0, altitude_m=0.0))
    at = datetime(2020, 10, 13, 4, 52, 48, tzinfo=UTC)

    positions = tracker.positions_above_horizon(
        [VANGUARD_OMM],
        minimum_elevation_deg=-90.0,
        at=at,
    )

    assert len(positions) == 1
    position = positions[0]
    assert position.name == "VANGUARD 1"
    assert position.norad_id == "5"
    assert position.object_id == "1958-002B"
    assert position.launch_id == "1958-002"
    assert 0.0 <= position.azimuth_deg < 360.0
    assert -90.0 <= position.elevation_deg <= 90.0
    assert position.range_km > 0.0
    assert len(position.track) == 7
    assert position.track[0].time_utc.startswith("2020-10-13T04:52:48")
    assert position.track[-1].time_utc.startswith("2020-10-13T04:53:48")


def test_batch_tracker_handles_multiple_catalogue_objects() -> None:
    second = dict(VANGUARD_OMM)
    second["OBJECT_NAME"] = "VANGUARD COPY"
    second["NORAD_CAT_ID"] = 6
    second["OBJECT_ID"] = "1958-002C"

    tracker = SatelliteTracker(ObserverConfig(latitude=51.5, longitude=-0.1, altitude_m=25.0))
    at = datetime(2020, 10, 13, 4, 52, 48, tzinfo=UTC)

    positions = tracker.positions_above_horizon(
        [VANGUARD_OMM, second],
        minimum_elevation_deg=-90.0,
        at=at,
    )

    assert {position.norad_id for position in positions} == {"5", "6"}
    assert all(len(position.track) == 7 for position in positions)
