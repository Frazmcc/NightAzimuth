from __future__ import annotations

from nightazimuth.gui_stage20_realtime import (
    format_satellite_information,
    next_satellite_selection,
)
from nightazimuth.satellite_metadata import SatelliteMetadata
from nightazimuth.sky_map import SkySatellite
from nightazimuth.stage20_realtime_satellite_view import _remaining_track_points
from nightazimuth.track_prediction import TrackPoint


def _satellite() -> SkySatellite:
    return SkySatellite(
        name="TEST SAT",
        norad_id="12345",
        azimuth_deg=350.0,
        elevation_deg=20.0,
        range_km=700.0,
        satellite_sunlit=True,
        sky_dark=True,
        potentially_visible=True,
        future_track=(
            TrackPoint(0, 350.0, 20.0),
            TrackPoint(10, 10.0, 30.0),
            TrackPoint(20, 20.0, 40.0),
        ),
    )


def test_remaining_track_starts_at_interpolated_now_and_keeps_future_points() -> None:
    points = _remaining_track_points(_satellite(), 5.0)
    assert len(points) == 3
    assert abs(points[0][0] - 0.0) < 0.001
    assert abs(points[0][1] - 25.0) < 0.001
    assert points[1] == (10.0, 30.0)
    assert points[2] == (20.0, 40.0)


def test_second_click_on_selected_satellite_deselects_it() -> None:
    assert next_satellite_selection("12345", "12345") is None


def test_clicking_different_satellite_switches_selection() -> None:
    assert next_satellite_selection("12345", "67890") == "67890"
    assert next_satellite_selection(None, "67890") == "67890"


def test_satellite_information_includes_catalogue_orbit_and_mission_context() -> None:
    metadata = SatelliteMetadata(
        norad_id="12345",
        name="TEST SAT",
        international_designator="2026-001A",
        object_type="PAY",
        operational_status="+",
        owner_code="UK",
        launch_date="2026-01-01",
        launch_site="TEST",
        period_minutes=95.2,
        inclination_deg=51.6,
        apogee_km=430.0,
        perigee_km=410.0,
        radar_cross_section_m2=12.5,
        orbit_center="EA",
        orbit_type="ORB",
        purpose="Earth observation satellite",
        technical_notes="Carries a high-resolution imaging payload.",
        information_source="CelesTrak SATCAT + Wikipedia",
    )
    text = format_satellite_information(_satellite(), metadata)
    assert "NORAD: 12345" in text
    assert "2026-001A" in text
    assert "Country / owner: UK" in text
    assert "95.20 min" in text
    assert "51.60 °" in text
    assert "Earth observation satellite" in text
    assert "high-resolution imaging payload" in text


def test_satellite_information_is_explicit_when_enrichment_is_missing() -> None:
    metadata = SatelliteMetadata(norad_id="12345", name="TEST SAT")
    text = format_satellite_information(_satellite(), metadata)
    assert "Country / owner: Unavailable" in text
    assert "No verified mission summary available." in text
    assert "No verified public technical summary available." in text
