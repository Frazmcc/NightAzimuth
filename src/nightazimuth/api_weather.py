from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from .config import ObserverConfig
from .weather import MetNorwayWeatherProvider, WeatherProviderError

router = APIRouter(prefix="/api/v1/weather", tags=["weather"])

_API_CACHE = Path("data/cache/api")


@router.get("")
def weather(
    latitude: float = Query(ge=-90.0, le=90.0),
    longitude: float = Query(ge=-180.0, le=180.0),
    altitude_m: float = Query(default=0.0),
    forecast_points: int = Query(default=4, ge=1, le=24),
) -> dict[str, object]:
    """Return the current/next weather point and a bounded point forecast."""

    observer = ObserverConfig(latitude, longitude, altitude_m)
    provider = MetNorwayWeatherProvider(cache_directory=_API_CACHE)
    try:
        snapshot = provider.load(observer)
    except WeatherProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    current = snapshot.current_or_next()
    points = snapshot.next_points(forecast_points)
    return {
        "source": snapshot.source_name,
        "fetched_at": snapshot.fetched_at_utc.isoformat(),
        "source_updated_at": (
            snapshot.source_updated_at_utc.isoformat()
            if snapshot.source_updated_at_utc is not None
            else None
        ),
        "from_cache": snapshot.from_cache,
        "observer": {
            "latitude_deg": latitude,
            "longitude_deg": longitude,
            "altitude_m": altitude_m,
        },
        "current": asdict(current) if current is not None else None,
        "forecast": [asdict(point) for point in points],
    }
