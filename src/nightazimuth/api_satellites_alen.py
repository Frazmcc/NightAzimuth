"""ALEN-compatible satellite trajectory feed.

Keeps the legacy NightAzimuth /api/v1/satellites contract untouched.
The upstream endpoint supplies the same SGP4 sampled trajectories ALEN uses.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, HTTPException, Query

router = APIRouter(prefix="/api/v1/satellites", tags=["satellites"])
_ALEN_URL = "https://alen-api-lquw.onrender.com/api/v1/satellites"
_ALLOWED_GROUPS = frozenset((
    "last-30-days", "stations", "visual", "starlink", "oneweb",
    "kuiper", "active", "weather", "resource", "science", "geodetic",
))


def _valid_trajectory(point: object) -> bool:
    if not isinstance(point, dict):
        return False
    try:
        offset = float(point["offset_seconds"])
        az = float(point["azimuth_deg"])
        elevation = float(point["elevation_deg"])
        distance = float(point["range_km"])
    except (KeyError, TypeError, ValueError, OverflowError):
        return False
    return (
        all(math.isfinite(v) for v in (offset, az, elevation, distance))
        and 0 <= offset <= 30
        and 0 <= az <= 360
        and -90 <= elevation <= 90
        and distance > 0
    )


def _validate_payload(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        raise ValueError("Expected an ALEN satellite response object")
    satellites = payload.get("satellites")
    diagnostics = payload.get("diagnostics")
    if not isinstance(satellites, list) or not isinstance(diagnostics, dict):
        raise ValueError("ALEN satellite response schema mismatch")
    sample_at = diagnostics.get("position_sample_at")
    if not isinstance(sample_at, str):
        raise ValueError("Satellite sample timestamp missing")
    try:
        sampled = datetime.fromisoformat(sample_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Invalid satellite sample timestamp") from exc
    if sampled.tzinfo is None:
        raise ValueError("Satellite sample timestamp must be timezone-aware")
    sample_age = (datetime.now(timezone.utc) - sampled.astimezone(timezone.utc)).total_seconds()
    if not -5 <= sample_age <= 30:
        raise ValueError("Satellite trajectory sample is stale or in the future")
    if len(satellites) > 500:
        raise ValueError("Satellite result exceeds supported limit")
    for satellite in satellites:
        if not isinstance(satellite, dict):
            raise ValueError("Invalid satellite entry")
        trajectory = satellite.get("trajectory")
        if (
            not isinstance(trajectory, list)
            or len(trajectory) < 2
            or len(trajectory) > 16
            or not all(_valid_trajectory(point) for point in trajectory)
        ):
            raise ValueError("Missing or invalid satellite trajectory")
        offsets = [float(point["offset_seconds"]) for point in trajectory]
        if offsets[0] != 0 or offsets != sorted(set(offsets)):
            raise ValueError("Satellite trajectory offsets must increase from zero")
    return payload


@router.get("/alen")
def alen_satellites(
    lat: float = Query(ge=-90, le=90),
    lon: float = Query(ge=-180, le=180),
    altitude_m: float = Query(default=0.0, ge=-500, le=20000),
    groups: str = Query(default="last-30-days,stations,visual", max_length=200),
    limit: int = Query(default=260, ge=1, le=500),
) -> dict[str, object]:
    """ALEN trajectory contract, proxied without modifying positions or timing."""
    selected = [group.strip().lower() for group in groups.split(",") if group.strip()]
    if not selected or len(selected) > 12 or any(group not in _ALLOWED_GROUPS for group in selected):
        raise HTTPException(status_code=422, detail="Unsupported satellite groups")
    params = dict(lat=lat, lon=lon, altitude_m=altitude_m, groups=",".join(selected), limit=limit)
    try:
        with httpx.Client(timeout=httpx.Timeout(10.0, connect=3.0), follow_redirects=False) as client:
            response = client.get(_ALEN_URL, params=params)
            response.raise_for_status()
            return _validate_payload(response.json())
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(status_code=503, detail="ALEN satellite trajectory feed unavailable") from exc
