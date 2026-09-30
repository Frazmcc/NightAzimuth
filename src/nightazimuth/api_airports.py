from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from time import perf_counter

from fastapi import APIRouter, Query, Response

from .stage20_rc_airports import ResilientAirportLandmarkProvider

router = APIRouter(prefix="/api/v1/airports", tags=["airports"])
_API_CACHE = Path("data/cache/api")
_PROVIDER = ResilientAirportLandmarkProvider(
    timeout_seconds=8.0,
    cache_directory=_API_CACHE,
)


def _server_timing(*, provider_ms: float, payload_ms: float, total_ms: float) -> str:
    return (
        f"provider;dur={provider_ms:.1f}, "
        f"payload;dur={payload_ms:.1f}, "
        f"total;dur={total_ms:.1f}"
    )


@router.get("")
def airports(
    response: Response,
    latitude: float = Query(ge=-90.0, le=90.0),
    longitude: float = Query(ge=-180.0, le=180.0),
    radius_km: float = Query(default=250.0, gt=0.0, le=500.0),
    limit: int = Query(default=12, ge=1, le=30),
) -> dict[str, object]:
    request_started = perf_counter()
    provider_started = perf_counter()
    landmarks = _PROVIDER.nearby(
        latitude,
        longitude,
        max_distance_km=radius_km,
        limit=limit,
    )
    provider_ms = (perf_counter() - provider_started) * 1000.0
    payload_started = perf_counter()
    payload = {"count": len(landmarks), "airports": [asdict(item) for item in landmarks]}
    payload_ms = (perf_counter() - payload_started) * 1000.0
    total_ms = (perf_counter() - request_started) * 1000.0
    response.headers["Server-Timing"] = _server_timing(
        provider_ms=provider_ms,
        payload_ms=payload_ms,
        total_ms=total_ms,
    )
    return payload
