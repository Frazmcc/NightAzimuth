from __future__ import annotations

from dataclasses import asdict
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Query

from .aircraft import AircraftObserver, AircraftSnapshotState
from .aircraft_adsb_lol import AdsbLolProvider
from .aircraft_live import build_sky_aircraft
from .aircraft_display import aircraft_display_identity, squawk_display
from .aircraft_motion import AircraftMotionHistory
from .aircraft_routes import AdsbLolRouteProvider

router = APIRouter(prefix="/api/v1/aircraft", tags=["aircraft"])
logger = logging.getLogger(__name__)


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
        logger.warning("Aircraft provider unavailable: %s", snapshot.error or "unknown provider error")
        raise HTTPException(status_code=503, detail="Aircraft data is temporarily unavailable")

    route_provider = AdsbLolRouteProvider()
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
        "aircraft": [_contact_payload(contact, route_provider=route_provider) for contact in contacts],
        "geojson": _contacts_geojson(
            contacts=contacts,
            snapshot=snapshot,
            latitude=latitude,
            longitude=longitude,
            altitude_m=altitude_m,
            radius_km=radius_km,
        ),
    }


def _contacts_geojson(
    *,
    contacts: list[object],
    snapshot: object,
    latitude: float,
    longitude: float,
    altitude_m: float,
    radius_km: float,
) -> dict[str, object]:
    """Return geographic features from the same aircraft snapshot used for sky projection."""
    features = []
    for contact in contacts:
        contact_latitude = contact.latitude_deg
        contact_longitude = contact.longitude_deg
        if contact_latitude is None or contact_longitude is None:
            continue
        position_state = contact.position_state
        features.append({
            "type": "Feature",
            "id": contact.icao24,
            "geometry": {"type": "Point", "coordinates": [contact_longitude, contact_latitude]},
            "properties": {
                "icao24": contact.icao24,
                "callsign": contact.callsign,
                "altitude_m": contact.altitude_m,
                "track_deg": contact.track_deg,
                "ground_speed_mps": contact.ground_speed_mps,
                "vertical_rate_mps": contact.vertical_rate_mps,
                "position_state": position_state.value if position_state is not None else "unknown",
                "position_age_seconds": contact.position_age_seconds,
                "source_id": contact.source_id,
                "source_label": contact.source_label,
            },
        })
    return {
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


def _contact_payload(contact: object, *, route_provider: AdsbLolRouteProvider) -> dict[str, object]:
    payload = asdict(contact)
    identity = aircraft_display_identity(contact)
    route = route_provider.lookup(contact.callsign)
    payload["route"] = None if route is None else {
        "departure": _airport_payload(route.departure) if route.departure is not None else None,
        "arrival": _airport_payload(route.arrival) if route.arrival is not None else None,
        "intermediate_airports": [_airport_payload(airport) for airport in route.intermediate_airports],
        "airline_code": route.airline_code,
        "source": route.source_label,
    }
    payload["display"] = {
        "make_model": identity.make_model,
        "capacity": identity.capacity,
        "role": identity.role,
        "squawk": squawk_display(contact),
        "special": bool(identity.role or contact.squawk_alert is not None or contact.military),
    }
    return payload


def _airport_payload(airport: object) -> dict[str, object]:
    payload = asdict(airport)
    payload["display_code"] = airport.display_code
    payload["display_country"] = airport.display_country
    return payload
