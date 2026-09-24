from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from .aircraft import AircraftObserver, AircraftSnapshotState
from .aircraft_adsb_lol import AdsbLolProvider
from .aircraft_live import build_sky_aircraft
from .aircraft_motion import AircraftMotionHistory

router = APIRouter(prefix="/api/v1/geojson", tags=["geojson"])


@router.get("/aircraft")
def aircraft_geojson(
    latitude: float = Query(ge=-90.0, le=90.0),
    longitude: float = Query(ge=-180.0, le=180.0),
    altitude_m: float = 0.0,
    radius_km: float = Query(100.0, gt=0.0, le=463.0),
    include_ground: bool = False,
) -> dict[str, Any]:
    """Return live aircraft as a GeoJSON FeatureCollection for map clients."""

    observer = AircraftObserver(latitude, longitude, altitude_m)
    snapshot = AdsbLolProvider().fetch_snapshot(observer, radius_km)
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
                    "ground_speed_m_s": contact.ground_speed_m_s,
                    "vertical_rate_m_s": contact.vertical_rate_m_s,
                    "on_ground": contact.on_ground,
                    "position_state": contact.position_state.value,
                    "position_age_seconds": contact.position_age_seconds,
                    "source_id": contact.source_id,
                    "source_label": contact.source_label,
                },
            }
        )

    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "source": {
                "id": snapshot.source_id,
                "label": snapshot.source_label,
                "state": snapshot.state.value,
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
