from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from time import perf_counter

from fastapi import APIRouter, HTTPException, Query, Response

from .config import ObserverConfig
from .weather import MetNorwayWeatherProvider, WeatherProviderError
from .weather_snapshot_cache import API_WEATHER_SNAPSHOT_CACHE, weather_cache_key

router = APIRouter(prefix="/api/v1/weather", tags=["weather"])

_API_CACHE = Path("data/cache/api")


def _server_timing(*, wait_ms: float, load_ms: float, payload_ms: float, total_ms: float) -> str:
    return (
        f"weather_wait;dur={wait_ms:.1f}, "
        f"weather_load;dur={load_ms:.1f}, "
        f"payload;dur={payload_ms:.1f}, "
        f"total;dur={total_ms:.1f}"
    )


@router.get("")
def weather(
    response: Response,
    latitude: float = Query(ge=-90.0, le=90.0),
    longitude: float = Query(ge=-180.0, le=180.0),
    altitude_m: float = Query(default=0.0),
    forecast_points: int = Query(default=4, ge=1, le=168),
) -> dict[str, object]:
    """Return the current/next weather point and a bounded point forecast."""

    request_started = perf_counter()
    observer = ObserverConfig(latitude, longitude, altitude_m)

    def load_snapshot():
        return MetNorwayWeatherProvider(cache_directory=_API_CACHE).load(observer)

    try:
        shared = API_WEATHER_SNAPSHOT_CACHE.get_or_load(
            weather_cache_key(observer, MetNorwayWeatherProvider),
            load_snapshot,
        )
    except (WeatherProviderError, ValueError, OSError) as exc:
        total_ms = (perf_counter() - request_started) * 1000.0
        raise HTTPException(
            status_code=503,
            detail="Weather data is temporarily unavailable",
            headers={
                "Server-Timing": _server_timing(
                    wait_ms=0.0,
                    load_ms=total_ms,
                    payload_ms=0.0,
                    total_ms=total_ms,
                )
            },
        ) from exc

    snapshot = shared.snapshot
    payload_started = perf_counter()
    current = snapshot.current_or_next()
    points = snapshot.next_points(forecast_points)
    payload = {
        "source": snapshot.source_name,
        "fetched_at": snapshot.fetched_at_utc.isoformat(),
        "source_updated_at": (
            snapshot.source_updated_at_utc.isoformat()
            if snapshot.source_updated_at_utc is not None
            else None
        ),
        "from_cache": snapshot.from_cache,
        "fallback_used": snapshot.fallback_used,
        "observer": {
            "latitude_deg": latitude,
            "longitude_deg": longitude,
            "altitude_m": altitude_m,
        },
        "current": asdict(current) if current is not None else None,
        "forecast": [asdict(point) for point in points],
    }
    payload_ms = (perf_counter() - payload_started) * 1000.0
    total_ms = (perf_counter() - request_started) * 1000.0
    response.headers["Server-Timing"] = _server_timing(
        wait_ms=shared.shared_wait_ms,
        load_ms=shared.loader_ms,
        payload_ms=payload_ms,
        total_ms=total_ms,
    )
    return payload
