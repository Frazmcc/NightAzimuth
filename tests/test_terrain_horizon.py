from __future__ import annotations

from nightazimuth.terrain_horizon import (
    apparent_elevation_deg,
    calculate_horizon_profile,
    destination_point,
)


class FakeElevationSource:
    def elevation_m(self, latitude: float, longitude: float) -> float:
        del latitude
        return 250.0 if longitude > 0.0 else 100.0


def test_destination_point_north_increases_latitude() -> None:
    latitude, longitude = destination_point(0.0, 0.0, 0.0, 1_000.0)
    assert latitude > 0.0
    assert abs(longitude) < 0.001


def test_apparent_elevation_is_positive_for_higher_nearby_terrain() -> None:
    angle = apparent_elevation_deg(100.0, 200.0, 1_000.0)
    assert angle > 5.0


def test_horizon_profile_finds_higher_terrain_to_east() -> None:
    horizon = calculate_horizon_profile(
        FakeElevationSource(),
        observer_latitude=0.0,
        observer_longitude=0.0,
        observer_altitude_m=100.0,
        observer_height_m=0.0,
        azimuth_step_deg=90.0,
        max_distance_km=1.0,
    )

    by_azimuth = {round(point.azimuth_deg): point.elevation_deg for point in horizon}
    assert by_azimuth[90] > by_azimuth[270]
