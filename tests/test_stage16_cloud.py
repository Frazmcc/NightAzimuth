from datetime import datetime, timezone

from PIL import Image

from nightazimuth.cloud_imagery import (
    EUMETVIEW_LAYER,
    eumetview_getmap_params,
    parse_wms_layer_times,
)
from nightazimuth.cloud_projection import (
    CloudRegion,
    destination_latlon,
    line_of_sight_cloud_distance_km,
    project_cloud_region,
)
from nightazimuth.weather_map_stage16 import map_bbox_for_view, tile_fraction_to_latlon


def test_eumetview_request_uses_only_spatial_parameters() -> None:
    params = eumetview_getmap_params(
        min_latitude=9.0,
        min_longitude=19.0,
        max_latitude=11.0,
        max_longitude=21.0,
        width=512,
        height=512,
    )
    assert params["layers"] == EUMETVIEW_LAYER
    assert params["request"] == "GetMap"
    assert params["crs"] == "CRS:84"
    assert params["bbox"] == "19.00000,9.00000,21.00000,11.00000"
    assert "profile" not in params
    assert "name" not in params


def test_eumetview_request_can_pin_exact_frame_time() -> None:
    frame = datetime(2026, 9, 13, 20, 40, tzinfo=timezone.utc)
    params = eumetview_getmap_params(
        min_latitude=9.0,
        min_longitude=19.0,
        max_latitude=11.0,
        max_longitude=21.0,
        width=256,
        height=256,
        frame_time_utc=frame,
    )
    assert params["time"] == "2026-09-13T20:40:00Z"


def test_wms_capabilities_extracts_recent_layer_times() -> None:
    xml = b"""<?xml version='1.0' encoding='UTF-8'?>
    <WMS_Capabilities xmlns='http://www.opengis.net/wms'>
      <Capability><Layer><Layer>
        <Name>mtg_fd:rgb_geocolour</Name>
        <Dimension name='time'>2026-09-13T20:00:00Z/2026-09-13T20:30:00Z/PT10M</Dimension>
      </Layer></Layer></Capability>
    </WMS_Capabilities>"""
    values = parse_wms_layer_times(xml, EUMETVIEW_LAYER)
    assert [value.strftime("%H:%M") for value in values] == ["20:00", "20:10", "20:20", "20:30"]


def test_wms_long_interval_keeps_the_newest_provider_frame() -> None:
    xml = b"""<?xml version='1.0' encoding='UTF-8'?>
    <WMS_Capabilities xmlns='http://www.opengis.net/wms'>
      <Capability><Layer><Layer>
        <Name>mtg_fd:rgb_geocolour</Name>
        <Dimension name='time'>2024-01-01T00:00:00Z/2026-09-14T00:00:00Z/PT10M</Dimension>
      </Layer></Layer></Capability>
    </WMS_Capabilities>"""
    values = parse_wms_layer_times(xml, EUMETVIEW_LAYER)
    assert values[-1] == datetime(2026, 9, 14, 0, 0, tzinfo=timezone.utc)
    assert len(values) <= 5000


def test_cloud_distance_decreases_as_elevation_rises() -> None:
    low = line_of_sight_cloud_distance_km(10.0)
    high = line_of_sight_cloud_distance_km(60.0)
    assert low > high > 0.0


def test_destination_latlon_moves_north_for_zero_azimuth() -> None:
    latitude, longitude = destination_latlon(10.0, 20.0, 0.0, 10.0)
    assert latitude > 10.0
    assert abs(longitude - 20.0) < 0.02


def test_project_cloud_region_returns_rgba_texture() -> None:
    source = Image.new("RGB", (64, 64), (230, 235, 245))
    region = CloudRegion(
        image=source,
        min_latitude=8.0,
        min_longitude=18.0,
        max_latitude=12.0,
        max_longitude=22.0,
        source_name="synthetic",
    )
    projected = project_cloud_region(
        region,
        observer_latitude=10.0,
        observer_longitude=20.0,
        facing_deg=0.0,
        horizontal_fov_deg=90.0,
        minimum_elevation_deg=5.0,
        maximum_elevation_deg=90.0,
        width=40,
        height=20,
    )
    assert projected.mode == "RGBA"
    assert projected.size == (40, 20)
    assert projected.getchannel("A").getextrema()[1] > 0


def test_weather_map_bbox_contains_synthetic_observer() -> None:
    south, west, north, east = map_bbox_for_view(10.0, 20.0, zoom=7, radius_tiles=1)
    assert south < 10.0 < north
    assert west < 20.0 < east


def test_tile_fraction_roundtrip_shape() -> None:
    latitude, longitude = tile_fraction_to_latlon(64.0, 64.0, 7)
    assert -90.0 < latitude < 90.0
    assert -180.0 <= longitude <= 180.0
