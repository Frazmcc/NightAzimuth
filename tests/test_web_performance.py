from pathlib import Path


SATELLITE_JS = Path("web/satellite-motion.js").read_text(encoding="utf-8")
LAYOUT_JS = Path("web/live-sky-layout.js").read_text(encoding="utf-8")
CONTACTS_JS = Path("web/live-contacts-view.js").read_text(encoding="utf-8")
AIRCRAFT_JS = Path("web/aircraft-sensitivity.js").read_text(encoding="utf-8")
RADAR_JS = Path("web/aircraft-radar.js").read_text(encoding="utf-8")
HTML = Path("web/index.html").read_text(encoding="utf-8")


def _function_body(source: str, start_marker: str, end_marker: str) -> str:
    start = source.index(start_marker)
    end = source.index(end_marker, start)
    return source[start:end]


def test_satellite_track_dates_are_not_reparsed_every_animation_tick() -> None:
    interpolate = _function_body(
        SATELLITE_JS,
        "function interpolateTrack",
        "function updateTrainCounts",
    )

    assert "preparedTracks=new WeakMap()" in SATELLITE_JS
    assert "function preparedTrack" in SATELLITE_JS
    assert "Date.parse" not in interpolate
    assert "TRAIN_COUNT_UPDATE_MS=5000" in SATELLITE_JS


def test_satellite_paths_skip_catalogue_objects_outside_the_view() -> None:
    assert "!skyXY(Number(satellite.azimuth_deg),Number(satellite.elevation_deg),w,h)" in SATELLITE_JS
    assert "if(!document.hidden" in SATELLITE_JS


def test_sky_projection_uses_cached_layout_measurement() -> None:
    projection = _function_body(
        LAYOUT_JS,
        "skyXY=function",
        "elevationCentre=clampElevationCentre",
    )

    assert "cachedBottomReserve" in projection
    assert "offsetHeight" not in projection
    assert "ResizeObserver" in LAYOUT_JS


def test_sky_projection_stays_between_horizon_and_zenith() -> None:
    assert "Math.min(90-halfVertical,requested)" in LAYOUT_JS
    assert "elevationCentre=clampElevationCentre(elevationCentre)" in LAYOUT_JS


def test_sky_redraws_are_coalesced_to_animation_frames() -> None:
    assert "if(drawFrame!==null)return" in LAYOUT_JS
    assert "requestAnimationFrame" in LAYOUT_JS


def test_slow_api_data_is_cached_by_observer_and_query_with_bounded_memory() -> None:
    assert "const responseCache=new Map()" in LAYOUT_JS
    assert "const MAX_RESPONSE_CACHE=48" in LAYOUT_JS
    assert "while(responseCache.size>MAX_RESPONSE_CACHE)" in LAYOUT_JS
    assert 'path==="/api/v1/airports"?60*60*1000' in LAYOUT_JS
    assert 'path==="/api/v1/weather"||path==="/api/v1/observing"?5*60*1000' in LAYOUT_JS
    assert "effectiveParams" in LAYOUT_JS


def test_heavy_astronomy_requests_are_progressively_scheduled() -> None:
    assert 'path==="/api/v1/sky"||path==="/api/v1/satellites"' in LAYOUT_JS
    assert "let astronomyTail=Promise.resolve()" in LAYOUT_JS
    assert 'path==="/api/v1/satellites"?250:0' in LAYOUT_JS
    assert "observerSpreadMs(params)" in LAYOUT_JS
    assert "scheduleRequest(path,params" in LAYOUT_JS


def test_location_change_invalidates_an_inflight_refresh() -> None:
    assert "refreshGeneration++" in LAYOUT_JS
    assert "if(refreshInFlight){setTimeout(rerun,50);return}" in LAYOUT_JS


def test_background_tabs_do_not_keep_polling_live_data() -> None:
    assert "if(document.hidden)return;" in LAYOUT_JS
    assert "if(document.hidden||aircraftRefreshInFlight" in AIRCRAFT_JS
    assert 'document.addEventListener("visibilitychange"' in LAYOUT_JS
    assert 'document.addEventListener("visibilitychange"' in AIRCRAFT_JS


def test_startup_populates_the_bounded_local_radar_without_waiting_for_first_interval() -> None:
    assert "const AIRCRAFT_RADIUS_MILES=50" in AIRCRAFT_JS
    assert "const AIRCRAFT_RADIUS_KM=AIRCRAFT_RADIUS_MILES*1.609344" in AIRCRAFT_JS
    assert "minimum_elevation_deg:-90" in AIRCRAFT_JS
    assert "refreshAircraftFast();\nsetInterval(refreshAircraftFast,AIRCRAFT_REFRESH_MS)" in AIRCRAFT_JS
    assert "aircraft-sensitivity.js?v=21.11.21" in HTML


def test_aircraft_distance_units_can_be_changed_in_settings() -> None:
    assert 'id="distance-units"' in HTML
    assert '<option value="miles" selected>Miles</option>' in HTML
    assert '<option value="km">Kilometres</option>' in HTML
    assert 'localStorage.setItem("nightazimuth.distanceUnit",unit)' in RADAR_JS
    assert 'unit==="km"?rangeValue:rangeValue*KM_PER_MILE' in RADAR_JS
    assert "aircraft-radar.js?v=21.11.13" in HTML


def test_airports_share_distance_units_and_are_limited_to_50_miles() -> None:
    assert "const AIRPORT_RADIUS_MILES=50" in LAYOUT_JS
    assert "const AIRPORT_RADIUS_KM=AIRPORT_RADIUS_MILES*KM_PER_MILE" in LAYOUT_JS
    assert 'localStorage.getItem("nightazimuth.distanceUnit")==="km"?"km":"miles"' in LAYOUT_JS
    assert 'path==="/api/v1/airports"?' in LAYOUT_JS
    assert "radius_km:LOCAL_RADIUS_KM" in LAYOUT_JS
    assert "distanceKm>AIRPORT_RADIUS_KM" in LAYOUT_JS
    assert "Math.round(km/KM_PER_MILE)" in LAYOUT_JS
    assert 'window.addEventListener("nightazimuth:distance-unit",()=>drawSky())' in LAYOUT_JS


def test_changed_camera_runtime_is_cache_busted() -> None:
    assert "camera-settings.js?v=21.11.19" in HTML


def test_satellite_redraws_do_not_rebuild_unchanged_contact_rows() -> None:
    assert "lastRenderSignature" in CONTACTS_JS
    assert "if(signature===lastRenderSignature)return" in CONTACTS_JS
