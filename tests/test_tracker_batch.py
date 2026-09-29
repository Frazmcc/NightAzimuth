from __future__ import annotations

from datetime import UTC, datetime

from nightazimuth.config import ObserverConfig
import nightazimuth.tracker as tracker_module
from nightazimuth.tracker import SatelliteTracker, _clear_prepared_catalogue_cache


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
    _clear_prepared_catalogue_cache()
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
    _clear_prepared_catalogue_cache()
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


def test_prepared_satrec_generation_is_reused_until_orbital_data_changes(monkeypatch) -> None:
    _clear_prepared_catalogue_cache()
    at = datetime(2020, 10, 13, 4, 52, 48, tzinfo=UTC)
    observer = ObserverConfig(latitude=51.5, longitude=-0.1, altitude_m=25.0)
    original_initialize = tracker_module.omm.initialize
    initialize_calls = 0

    def counting_initialize(satrec, fields) -> None:
        nonlocal initialize_calls
        initialize_calls += 1
        original_initialize(satrec, fields)

    monkeypatch.setattr(tracker_module.omm, "initialize", counting_initialize)

    first = SatelliteTracker(observer)
    first.positions_above_horizon(
        [VANGUARD_OMM],
        minimum_elevation_deg=-90.0,
        at=at,
    )
    assert initialize_calls == 1
    assert first.last_timings["prepare_cache_hit"] == 0.0

    second = SatelliteTracker(observer)
    second.positions_above_horizon(
        [dict(VANGUARD_OMM)],
        minimum_elevation_deg=-90.0,
        at=at,
    )
    assert initialize_calls == 1
    assert second.last_timings["prepare_cache_hit"] == 1.0

    changed = dict(VANGUARD_OMM)
    changed["MEAN_ANOMALY"] = float(changed["MEAN_ANOMALY"]) + 0.0001
    third = SatelliteTracker(observer)
    third.positions_above_horizon(
        [changed],
        minimum_elevation_deg=-90.0,
        at=at,
    )
    assert initialize_calls == 2
    assert third.last_timings["prepare_cache_hit"] == 0.0


def test_future_track_propagation_runs_only_for_currently_visible_satellites(monkeypatch) -> None:
    _clear_prepared_catalogue_cache()
    at = datetime(2020, 10, 13, 4, 52, 48, tzinfo=UTC)
    observer = ObserverConfig(latitude=51.5, longitude=-0.1, altitude_m=25.0)
    original_satrec_array = tracker_module.SatrecArray
    calls: list[tuple[int, int]] = []

    class RecordingSatrecArray:
        def __init__(self, satrecs) -> None:
            satrec_list = list(satrecs)
            self._count = len(satrec_list)
            self._inner = original_satrec_array(satrec_list)

        def sgp4(self, julian_days, julian_fractions):
            calls.append((self._count, len(julian_days)))
            return self._inner.sgp4(julian_days, julian_fractions)

    monkeypatch.setattr(tracker_module, "SatrecArray", RecordingSatrecArray)
    tracker = SatelliteTracker(observer)

    hidden = tracker.positions_above_horizon(
        [VANGUARD_OMM],
        minimum_elevation_deg=91.0,
        at=at,
    )
    assert hidden == []
    assert calls == [(1, 1)]

    calls.clear()
    visible = tracker.positions_above_horizon(
        [VANGUARD_OMM],
        minimum_elevation_deg=-90.0,
        at=at,
    )
    assert len(visible) == 1
    assert len(visible[0].track) == 7
    assert calls == [(1, 1), (1, 6)]
