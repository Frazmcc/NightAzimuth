from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, Query

from .stage20_rc_airports import ResilientAirportLandmarkProvider

router = APIRouter(prefix="/api/v1/airports", tags=["airports"])
_PROVIDER = ResilientAirportLandmarkProvider(timeout_seconds=8.0)


@router.get("")
def airports(
    latitude: float = Query(ge=-90.0, le=90.0),
    longitude: float = Query(ge=-180.0, le=180.0),
    radius_km: float = Query(default=250.0, gt=0.0, le=500.0),
    limit: int = Query(default=12, ge=1, le=30),
) -> dict[str, object]:
    landmarks = _PROVIDER.nearby(latitude, longitude, max_distance_km=radius_km, limit=limit)
    return {"count": len(landmarks), "airports": [asdict(item) for item in landmarks]}
