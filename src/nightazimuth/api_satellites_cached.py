from __future__ import annotations

from fastapi import APIRouter, Query, Response

from .api_satellites import satellites as _base_satellites
from .burst_cache import BurstResultCache

router = APIRouter(prefix="/api/v1/satellites", tags=["satellites"])
_BURST_CACHE: BurstResultCache[dict[str, object]] = BurstResultCache(
    ttl_seconds=2.0,
    max_entries=32,
)


@router.get("")
def satellites(
    response: Response = None,
    latitude: float = Query(ge=-90.0, le=90.0),
    longitude: float = Query(ge=-180.0, le=180.0),
    altitude_m: float = Query(default=0.0),
    minimum_elevation_deg: float = Query(default=0.0, ge=0.0, le=90.0),
    group: str = Query(default="ACTIVE", min_length=1, max_length=64),
    identification_detail: bool = Query(default=True),
) -> dict[str, object]:
    """Reuse near-simultaneous identical satellite results for burst protection."""

    cache_key = (
        latitude,
        longitude,
        altitude_m,
        minimum_elevation_deg,
        group.strip().upper(),
        identification_detail,
    )
    cached = _BURST_CACHE.get(cache_key)
    if cached is not None:
        if response is not None:
            response.headers["Server-Timing"] = 'burst_cache;desc="hit";dur=0.0'
        return cached

    payload = _base_satellites(
        response=response,
        latitude=latitude,
        longitude=longitude,
        altitude_m=altitude_m,
        minimum_elevation_deg=minimum_elevation_deg,
        group=group,
        identification_detail=identification_detail,
    )
    _BURST_CACHE.put(cache_key, payload)
    if response is not None:
        existing = response.headers.get("Server-Timing")
        marker = 'burst_cache;desc="miss";dur=0.0'
        response.headers["Server-Timing"] = f"{marker}, {existing}" if existing else marker
    return payload
