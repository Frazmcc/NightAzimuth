from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from .config import ObserverConfig
from .observing_planner import ObservingPlanner
from .weather import MetNorwayWeatherProvider, WeatherProviderError

router = APIRouter(prefix="/api/v1", tags=["observing"])
_API_CACHE = Path("data/cache/api")


@router.get("/observing")
def observing_conditions(
    latitude: float = Query(..., ge=-90.0, le=90.0),
    longitude: float = Query(..., ge=-180.0, le=180.0),
    altitude_m: float = 0.0,
    hours: int = Query(24, ge=1, le=48),
) -> dict[str, object]:
    """Return observing guidance derived from NightAzimuth astronomy and weather engines."""

    observer = ObserverConfig(
        latitude=latitude,
        longitude=longitude,
        altitude_m=altitude_m,
    )
    provider = MetNorwayWeatherProvider(cache_directory=_API_CACHE)
    try:
        weather = provider.load(observer)
        planner = ObservingPlanner(observer, cache_directory=_API_CACHE)
        guidance = planner.build(weather, hours=hours)
    except (WeatherProviderError, OSError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(
            status_code=503,
            detail="Observing guidance is temporarily unavailable",
        ) from exc

    return {
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
