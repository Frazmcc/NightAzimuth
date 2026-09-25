from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query

from .aircraft import AircraftObserver, AircraftSnapshotState
from .aircraft_adsb_lol import AdsbLolProvider
from .aircraft_live import build_sky_aircraft
from .aircraft_motion import AircraftMotionHistory

router = APIRouter(prefix="/api/v1/aircraft", tags=["aircraft"])


@router.get("")
def aircraft(
    latitude: float = Query(ge=-90.0, le=90.0),
    longitude: float = Query(ge=-180.0, le=180.0),
    altitude_m: float = Query(default=0.0),
    radius_km: float = Query(default=100.0, gt=0.0, le=463.0),
    minimum_elevation_deg: float = Query(default=0.0, ge=-90.0, le=90.0),
    include_ground: bool = Query(default=False),
) -> dict[str, object]:
    """Return live aircraft projected into the observer's sky."""

    observed_at = datetime.now(UTC)
    observer = AircraftObserver(latitude, longitude, altitude_m)
    snapshot = AdsbLolProvider().fetch_snapshot(observer, radius_km)

    if snapshot.state == AircraftSnapshotState.UNAVAILABLE:
        raise HTTPException(status_code=503, detail=snapshot.error or "aircraft data unavailable")

    contacts = build_sky_aircraft(
        snapshot,
        observer,
        AircraftMotionHistory(),
        at=observed_at,
        minimum_elevation_deg=minimum_elevation_deg,
        include_ground=include_ground,
    )
    return {
        "observed_at": observed_at.isoformat(),
        "source": {
            "id": snapshot.source_id,
            "label": snapshot.source_label,
            "state": snapshot.state.value,
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
        "minimum_elevation_deg": minimum_elevation_deg,
        "count": len(contacts),
        "aircraft": [asdict(contact) for contact in contacts],
        "geojson": _contacts_geojson(contacts),
    }


def _contacts_geojson(contacts: list[object]) -> dict[str, object]:
    """Return geographic features from the same aircraft snapshot used for sky projection."""
    features = []
    for contact in contacts:
        latitude = getattr(contact, "latitude_deg", None)
        longitude = getattr(contact, "longitude_deg", None)
        if latitude is None or longitude is None:
            continue
        position_state = getattr(contact, "position_state", None)
        features.append({
            "type": "Feature",
            "id": getattr(contact, "icao24"),
            "geometry": {"type": "Point", "coordinates": [longitude, latitude]},
            "properties": {
                "icao24": getattr(contact, "icao24"),
                "callsign": getattr(contact, "callsign"),
                "altitude_m": getattr(contact, "altitude_m"),
                "position_state": position_state.value if position_state is not None else "unknown",
            },
        })
    return {"type": "FeatureCollection", "features": features}
