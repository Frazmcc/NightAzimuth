from pathlib import Path


SATELLITE_JS = Path("web/satellite-motion.js").read_text(encoding="utf-8")
LAYOUT_JS = Path("web/live-sky-layout.js").read_text(encoding="utf-8")
CONTACTS_JS = Path("web/live-contacts-view.js").read_text(encoding="utf-8")
AIRCRAFT_JS = Path("web/aircraft-sensitivity.js").read_text(encoding="utf-8")


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


def test_location_change_invalidates_an_inflight_refresh() -> None:
    assert "refreshGeneration++" in LAYOUT_JS
    assert "if(refreshInFlight){setTimeout(rerun,50);return}" in LAYOUT_JS


def test_background_tabs_do_not_keep_polling_live_data() -> None:
    assert "if(document.hidden)return;" in LAYOUT_JS
    assert "if(document.hidden||aircraftRefreshInFlight" in AIRCRAFT_JS
    assert 'document.addEventListener("visibilitychange"' in LAYOUT_JS
    assert 'document.addEventListener("visibilitychange"' in AIRCRAFT_JS


def test_initial_aircraft_load_is_not_duplicated() -> None:
    assert "refreshAircraftFast();\nsetInterval" not in AIRCRAFT_JS
    assert "setInterval(refreshAircraftFast,AIRCRAFT_REFRESH_MS)" in AIRCRAFT_JS


def test_satellite_redraws_do_not_rebuild_unchanged_contact_rows() -> None:
    assert "lastRenderSignature" in CONTACTS_JS
    assert "if(signature===lastRenderSignature)return" in CONTACTS_JS
