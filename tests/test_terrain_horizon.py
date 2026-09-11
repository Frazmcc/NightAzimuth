from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from nightazimuth.terrain_horizon import (
    CachedTerrariumElevationSource,
    MissingTerrainDataError,
    OfflineTerrariumElevationSource,
    SyntheticDemoElevationSource,
    TerrainDownloadError,
    TerrainPackError,
    _tile_pixel,
    apparent_elevation_deg,
    calculate_horizon_profile,
    destination_point,
    import_terrarium_pack,
    inspect_terrarium_pack,
)


class FakeElevationSource:
    def elevation_m(self, latitude: float, longitude: float) -> float:
        del latitude
        return 250.0 if longitude > 0.0 else 100.0


def _terrarium_png_bytes(elevation_m: int = 100) -> bytes:
    encoded = 32768 + elevation_m
    red = encoded // 256
    green = encoded % 256
    buffer = BytesIO()
    Image.new("RGB", (256, 256), (red, green, 0)).save(buffer, format="PNG")
    return buffer.getvalue()


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


def test_offline_source_reads_local_terrarium_tile(tmp_path: Path) -> None:
    latitude = 0.0
    longitude = 0.0
    zoom = 1
    tile_x, tile_y, _pixel_x, _pixel_y = _tile_pixel(latitude, longitude, zoom)
    path = tmp_path / str(zoom) / str(tile_x) / f"{tile_y}.png"
    path.parent.mkdir(parents=True)
    Image.new("RGB", (256, 256), (128, 100, 0)).save(path)
    source = OfflineTerrariumElevationSource(tmp_path, zoom=zoom)
    assert source.elevation_m(latitude, longitude) == pytest.approx(100.0)


def test_offline_source_never_falls_back_when_tile_is_missing(tmp_path: Path) -> None:
    source = OfflineTerrariumElevationSource(tmp_path, zoom=10)
    with pytest.raises(MissingTerrainDataError, match="No network request was made"):
        source.elevation_m(0.0, 0.0)


def test_cached_source_downloads_missing_tile_then_reuses_local_cache(tmp_path: Path) -> None:
    requested: list[str] = []

    def fetch_tile(url: str) -> bytes:
        requested.append(url)
        return _terrarium_png_bytes(125)

    source = CachedTerrariumElevationSource(tmp_path, zoom=1, tile_fetcher=fetch_tile)
    assert source.elevation_m(0.0, 0.0) == pytest.approx(125.0)
    assert len(requested) == 1

    def must_not_fetch(_url: str) -> bytes:
        raise AssertionError("terrain cache should have been reused")

    cached_source = CachedTerrariumElevationSource(tmp_path, zoom=1, tile_fetcher=must_not_fetch)
    assert cached_source.elevation_m(0.0, 0.0) == pytest.approx(125.0)


def test_cached_source_reports_download_failure_without_exposing_location(tmp_path: Path) -> None:
    def fetch_tile(_url: str) -> bytes:
        raise OSError("network unavailable")

    source = CachedTerrariumElevationSource(tmp_path, zoom=1, tile_fetcher=fetch_tile)
    with pytest.raises(TerrainDownloadError, match="could not be downloaded"):
        source.elevation_m(0.0, 0.0)


def test_synthetic_demo_source_produces_varied_local_terrain() -> None:
    source = SyntheticDemoElevationSource()
    centre = source.elevation_m(0.0, 0.0)
    east = source.elevation_m(0.01, 0.05)
    west = source.elevation_m(0.01, -0.05)
    assert centre > 0.0
    assert east != pytest.approx(west)


def test_synthetic_demo_horizon_is_complete_and_non_flat() -> None:
    horizon = calculate_horizon_profile(
        SyntheticDemoElevationSource(),
        observer_latitude=0.0,
        observer_longitude=0.0,
        observer_altitude_m=70.0,
        observer_height_m=1.7,
        azimuth_step_deg=30.0,
        max_distance_km=20.0,
    )
    assert len(horizon) == 36
    assert len({round(point.elevation_deg, 3) for point in horizon}) > 1


def test_terrain_pack_inspection_and_import(tmp_path: Path) -> None:
    source = tmp_path / "source"
    destination = tmp_path / "destination"
    tile = source / "1" / "1" / "1.png"
    tile.parent.mkdir(parents=True)
    Image.new("RGB", (256, 256), (128, 100, 0)).save(tile)

    summary = inspect_terrarium_pack(source)
    assert summary.tile_count == 1
    assert summary.zoom_levels == (1,)

    imported = import_terrarium_pack(source, destination)
    assert imported == summary
    assert (destination / "1" / "1" / "1.png").is_file()


def test_empty_terrain_pack_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(TerrainPackError):
        inspect_terrarium_pack(tmp_path)
