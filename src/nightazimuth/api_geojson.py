from __future__ import annotations

from math import isfinite
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from .aircraft import AircraftObserver, AircraftSnapshotState
from .aircraft_adsb_lol import AdsbLolProvider
from .aircraft_live import build_sky_aircraft
from .aircraft_motion import AircraftMotionHistory

router = APIRouter(prefix="/api/v1/geojson", tags=["geojson"])


@router.get(
    "/aircraft",
    response_class=JSONResponse,
    responses={200: {"content": {"application/geo+json": {}}}},
)
def aircraft_geojson(
    latitude: float = Query(ge=-90.0, le=90.0),
    longitude: float = Query(ge=-180.0, le=180.0),
    altitude_m: float = 0.0,
    radius_km: float = Query(100.0, gt=0.0, le=463.0),
    include_ground: bool = False,
) -> dict[str, Any]:
    """Return live aircraft as a GeoJSON FeatureCollection for map clients."""

    if not all(isfinite(value) for value in (latitude, longitude, altitude_m, radius_km)):
        raise HTTPException(status_code=422, detail="Query parameters must be finite numbers")

    observer = AircraftObserver(latitude, longitude, altitude_m)
    try:
        snapshot = AdsbLolProvider().fetch_snapshot(observer, radius_km)
    except (AttributeError, KeyError, OverflowError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=503,
            detail="Aircraft overlay is temporarily unavailable",
        ) from exc
    if snapshot.state == AircraftSnapshotState.UNAVAILABLE:
        raise HTTPException(status_code=503, detail="Aircraft overlay is temporarily unavailable")

    contacts = build_sky_aircraft(
        snapshot,
        observer,
        AircraftMotionHistory(),
        minimum_elevation_deg=-90.0,
        include_ground=include_ground,
    )
    features = []
    for contact in contacts:
        if contact.latitude_deg is None or contact.longitude_deg is None:
            continue
        features.append(
            {
                "type": "Feature",
                "id": contact.icao24,
                "geometry": {
                    "type": "Point",
                    "coordinates": [
                        contact.longitude_deg,
                        contact.latitude_deg,
                    ],
                },
                "properties": {
                    "icao24": contact.icao24,
                    "callsign": contact.callsign,
                    "altitude_m": contact.altitude_m,
                    "track_deg": contact.track_deg,
                    "ground_speed_mps": contact.ground_speed_mps,
                    "vertical_rate_mps": contact.vertical_rate_mps,
                    "position_state": contact.position_state.value,
                    "position_age_seconds": contact.position_age_seconds,
                    "source_id": contact.source_id,
                    "source_label": contact.source_label,
                },
            }
        )

    payload = {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "source": {
                "id": snapshot.source_id,
                "label": snapshot.source_label,
                "state": snapshot.state.value,
                "fetched_at": snapshot.fetched_at.isoformat(),
                "source_observed_at": (
                    snapshot.source_observed_at.isoformat()
                    if snapshot.source_observed_at is not None
                    else None
                ),
                "coverage": snapshot.coverage_description,
            },
            "observer": {
                "latitude_deg": latitude,
                "longitude_deg": longitude,
                "altitude_m": altitude_m,
            },
            "radius_km": radius_km,
            "count": len(features),
        },
    }
    return JSONResponse(content=payload, media_type="application/geo+json")
