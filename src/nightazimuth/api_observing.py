from __future__ import annotations

from pathlib import Path
from time import perf_counter

from fastapi import APIRouter, HTTPException, Query, Response

from .config import ObserverConfig
from .observing_planner import ObservingPlanner
from .weather import MetNorwayWeatherProvider, WeatherProviderError
from .weather_snapshot_cache import API_WEATHER_SNAPSHOT_CACHE, weather_cache_key

router = APIRouter(prefix="/api/v1", tags=["observing"])
_API_CACHE = Path("data/cache/api")


def _server_timing(
    *,
    wait_ms: float,
    load_ms: float,
    planner_init_ms: float,
    planner_build_ms: float,
    payload_ms: float,
    total_ms: float,
) -> str:
    return (
        f"weather_wait;dur={wait_ms:.1f}, "
        f"weather_load;dur={load_ms:.1f}, "
        f"planner_init;dur={planner_init_ms:.1f}, "
        f"planner_build;dur={planner_build_ms:.1f}, "
        f"payload;dur={payload_ms:.1f}, "
        f"total;dur={total_ms:.1f}"
    )


@router.get("/observing")
def observing_conditions(
    response: Response,
    latitude: float = Query(..., ge=-90.0, le=90.0),
    longitude: float = Query(..., ge=-180.0, le=180.0),
    altitude_m: float = 0.0,
    hours: int = Query(24, ge=1, le=48),
) -> dict[str, object]:
    """Return observing guidance derived from NightAzimuth astronomy and weather engines."""

    request_started = perf_counter()
    observer = ObserverConfig(
        latitude=latitude,
        longitude=longitude,
        altitude_m=altitude_m,
    )

    def load_snapshot():
        return MetNorwayWeatherProvider(cache_directory=_API_CACHE).load(observer)

    try:
        shared = API_WEATHER_SNAPSHOT_CACHE.get_or_load(
            weather_cache_key(observer, MetNorwayWeatherProvider),
            load_snapshot,
        )
        planner_init_started = perf_counter()
        planner = ObservingPlanner(observer, cache_directory=_API_CACHE)
        planner_init_ms = (perf_counter() - planner_init_started) * 1000.0
        planner_build_started = perf_counter()
        guidance = planner.build(shared.snapshot, hours=hours)
        planner_build_ms = (perf_counter() - planner_build_started) * 1000.0
    except (WeatherProviderError, OSError, ValueError, KeyError, TypeError) as exc:
        total_ms = (perf_counter() - request_started) * 1000.0
        raise HTTPException(
            status_code=503,
            detail="Observing guidance is temporarily unavailable",
            headers={
                "Server-Timing": _server_timing(
                    wait_ms=0.0,
                    load_ms=total_ms,
                    planner_init_ms=0.0,
                    planner_build_ms=0.0,
                    payload_ms=0.0,
                    total_ms=total_ms,
                )
            },
        ) from exc

    weather = shared.snapshot
    payload_started = perf_counter()
    payload = {
        "calculated_from": weather.fetched_at_utc.isoformat(),
        "weather_source": weather.source_name,
        "weather_from_cache": weather.from_cache,
        "weather_fallback_used": weather.fallback_used,
        "observer": {
            "latitude_deg": observer.latitude,
            "longitude_deg": observer.longitude,
            "altitude_m": observer.altitude_m,
        },
        "hours": hours,
        "count": len(guidance),
        "guidance": [
            {
                "time": item.time_utc.isoformat(),
                "rating": item.rating,
                "confidence": item.confidence,
                "sun_altitude_deg": item.sun_altitude_deg,
                "cloud_percent": item.cloud_percent,
                "fog_percent": item.fog_percent,
                "precipitation_mm": item.precipitation_mm,
                "reasons": list(item.reasons),
            }
            for item in guidance
        ],
    }
    payload_ms = (perf_counter() - payload_started) * 1000.0
    total_ms = (perf_counter() - request_started) * 1000.0
    response.headers["Server-Timing"] = _server_timing(
        wait_ms=shared.shared_wait_ms,
        load_ms=shared.loader_ms,
        planner_init_ms=planner_init_ms,
        planner_build_ms=planner_build_ms,
        payload_ms=payload_ms,
        total_ms=total_ms,
    )
    return payload
