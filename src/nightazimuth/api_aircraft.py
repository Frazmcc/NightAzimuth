from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
import logging
from time import perf_counter

from fastapi import APIRouter, HTTPException, Query, Response

from .aircraft import AircraftObserver, AircraftSnapshotState
from .aircraft_adsb_lol import AdsbLolProvider
from .aircraft_live import build_sky_aircraft
from .aircraft_display import aircraft_display_identity, squawk_display
from .aircraft_motion import AircraftMotionHistory, AircraftPositionState
from .aircraft_snapshot_cache import AircraftSnapshotCache, slice_snapshot_radius

router = APIRouter(prefix="/api/v1/aircraft", tags=["aircraft"])
logger = logging.getLogger(__name__)

_MAX_RECENT_POSITION_AGE_SECONDS = 45.0
_LIVE_SKY_SHARED_RADIUS_KM = 400.0
_AIRCRAFT_SNAPSHOT_CACHE = AircraftSnapshotCache(
    ttl_seconds=1.0,
    max_entries=4,
    fallback_max_age_seconds=30.0,
)


def _server_timing(timings: dict[str, float], total_ms: float) -> str:
    return (
        f"shared_wait;dur={timings.get('shared_wait_ms', 0.0):.1f}, "
        f"radius_slice;dur={timings.get('radius_slice_ms', 0.0):.1f}, "
        f"provider_client;dur={timings.get('provider_client_ms', 0.0):.1f}, "
        f"provider_wait;dur={timings.get('provider_wait_ms', 0.0):.1f}, "
        f"provider_request;dur={timings.get('provider_request_ms', 0.0):.1f}, "
        f"provider_decode;dur={timings.get('provider_decode_ms', 0.0):.1f}, "
        f"provider_close;dur={timings.get('provider_close_ms', 0.0):.1f}, "
        f"provider_normalize;dur={timings.get('provider_normalize_ms', 0.0):.1f}, "
        f"provider_total;dur={timings.get('provider_total_ms', 0.0):.1f}, "
        f"projection;dur={timings.get('projection_ms', 0.0):.1f}, "
        f"payload;dur={timings.get('payload_ms', 0.0):.1f}, "
        f"total;dur={total_ms:.1f}"
    )


def _upstream_radius_km(radius_km: float) -> float:
    # The hosted Live Sky starts a 200 km above-horizon request and a 400 km
    # radar request together. Fetch the broader view once so the 200 km view can
    # be derived locally from the same provider snapshot.
    if abs(radius_km - 200.0) < 1e-9 or abs(radius_km - 400.0) < 1e-9:
        return _LIVE_SKY_SHARED_RADIUS_KM
    return radius_km


def _snapshot_cache_key(observer: AircraftObserver, upstream_radius_km: float) -> tuple[object, ...]:
    # The provider URL is rounded to six decimal places, so use the same
    # precision for cache identity. Include the provider factory object so test
    # monkeypatches and future provider changes cannot reuse an incompatible entry.
    return (
        AdsbLolProvider,
        round(observer.latitude_deg, 6),
        round(observer.longitude_deg, 6),
        round(upstream_radius_km, 3),
    )


@router.get("")
def aircraft(
    response: Response,
    latitude: float = Query(ge=-90.0, le=90.0),
    longitude: float = Query(ge=-180.0, le=180.0),
    altitude_m: float = Query(default=0.0),
    radius_km: float = Query(default=100.0, gt=0.0, le=463.0),
    minimum_elevation_deg: float = Query(default=0.0, ge=-90.0, le=90.0),
    include_ground: bool = Query(default=False),
) -> dict[str, object]:
    """Return recent aircraft projected into the observer's sky.

    ADS-B providers commonly return individual position fixes a few tens of seconds old.
    A fix older than the 15-second motion-prediction window is retained for identification
    for up to 45 seconds, but remains explicitly marked as stale instead of being silently
    dropped or over-extrapolated.
    """

    request_started = perf_counter()
    timings: dict[str, float] = {}
    observed_at = datetime.now(UTC)
    observer = AircraftObserver(latitude, longitude, altitude_m)
    upstream_radius_km = _upstream_radius_km(radius_km)

    def fetch_snapshot():
        provider = AdsbLolProvider()
        provider_snapshot = provider.fetch_snapshot(observer, upstream_radius_km)
        return provider_snapshot, getattr(provider, "last_timings", {})

    shared = _AIRCRAFT_SNAPSHOT_CACHE.get_or_fetch(
        _snapshot_cache_key(observer, upstream_radius_km),
        fetch_snapshot,
    )
    timings.update(shared.provider_timings)
    timings["shared_wait_ms"] = shared.shared_wait_ms

    slice_started = perf_counter()
    if upstream_radius_km > radius_km:
        snapshot = slice_snapshot_radius(shared.snapshot, observer, radius_km)
    else:
        snapshot = shared.snapshot
    timings["radius_slice_ms"] = (perf_counter() - slice_started) * 1000.0

    if snapshot.state == AircraftSnapshotState.UNAVAILABLE:
        total_ms = (perf_counter() - request_started) * 1000.0
        timing_header = _server_timing(timings, total_ms)
        logger.warning(
            "aircraft_provider_unavailable radius_km=%.1f upstream_radius_km=%.1f "
            "shared_cache_hit=%s shared_wait_ms=%.1f total_ms=%.1f "
            "provider_client_ms=%.1f provider_wait_ms=%.1f provider_request_ms=%.1f "
            "provider_decode_ms=%.1f provider_close_ms=%.1f provider_total_ms=%.1f error=%s",
            radius_km,
            upstream_radius_km,
            shared.cache_hit,
            shared.shared_wait_ms,
            total_ms,
            timings.get("provider_client_ms", 0.0),
            timings.get("provider_wait_ms", 0.0),
            timings.get("provider_request_ms", 0.0),
            timings.get("provider_decode_ms", 0.0),
            timings.get("provider_close_ms", 0.0),
            timings.get("provider_total_ms", 0.0),
            snapshot.error or "unknown provider error",
        )
        raise HTTPException(
            status_code=503,
            detail="Aircraft data is temporarily unavailable",
            headers={"Server-Timing": timing_header},
        )

    projection_started = perf_counter()
    contacts = build_sky_aircraft(
        snapshot,
        observer,
        AircraftMotionHistory(),
        at=observed_at,
        minimum_elevation_deg=minimum_elevation_deg,
        include_ground=include_ground,
        include_stale=True,
        maximum_position_age_seconds=_MAX_RECENT_POSITION_AGE_SECONDS,
    )
    fresh_contact_count = sum(
        contact.position_state != AircraftPositionState.STALE for contact in contacts
    )
    timings["projection_ms"] = (perf_counter() - projection_started) * 1000.0

    payload_started = perf_counter()
    contact_payloads = [_contact_payload(contact) for contact in contacts]
    geojson = _contacts_geojson(
        contacts=contacts,
        snapshot=snapshot,
        latitude=latitude,
        longitude=longitude,
        altitude_m=altitude_m,
        radius_km=radius_km,
    )
    payload = {
        "observed_at": observed_at.isoformat(),
        "source": {
            "id": snapshot.source_id,
            "label": snapshot.source_label,
            "state": snapshot.state.value,
            "fallback_used": shared.fallback_used,
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
        "source_observation_count": len(snapshot.observations),
        "fresh_contact_count": fresh_contact_count,
        "maximum_position_age_seconds": _MAX_RECENT_POSITION_AGE_SECONDS,
        "count": len(contacts),
        "aircraft": contact_payloads,
        "geojson": geojson,
    }
    timings["payload_ms"] = (perf_counter() - payload_started) * 1000.0
    total_ms = (perf_counter() - request_started) * 1000.0
    response.headers["Server-Timing"] = _server_timing(timings, total_ms)
    logger.info(
        "aircraft_request radius_km=%.1f upstream_radius_km=%.1f shared_cache_hit=%s "
        "fallback_used=%s shared_wait_ms=%.1f total_ms=%.1f provider_client_ms=%.1f "
        "provider_wait_ms=%.1f provider_request_ms=%.1f provider_decode_ms=%.1f "
        "provider_close_ms=%.1f provider_normalize_ms=%.1f provider_total_ms=%.1f "
        "projection_ms=%.1f payload_ms=%.1f source_count=%d returned_count=%d",
        radius_km,
        upstream_radius_km,
        shared.cache_hit,
        shared.fallback_used,
        shared.shared_wait_ms,
        total_ms,
        timings.get("provider_client_ms", 0.0),
        timings.get("provider_wait_ms", 0.0),
        timings.get("provider_request_ms", 0.0),
        timings.get("provider_decode_ms", 0.0),
        timings.get("provider_close_ms", 0.0),
        timings.get("provider_normalize_ms", 0.0),
        timings.get("provider_total_ms", 0.0),
        timings.get("projection_ms", 0.0),
        timings.get("payload_ms", 0.0),
        len(snapshot.observations),
        len(contacts),
    )
    return payload


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


def _contact_payload(contact: object) -> dict[str, object]:
    payload = asdict(contact)
    identity = aircraft_display_identity(contact)
    payload["display"] = {
        "make_model": identity.make_model,
        "capacity": identity.capacity,
        "role": identity.role,
        "squawk": squawk_display(contact),
        "special": bool(identity.role or contact.squawk_alert is not None or contact.military),
    }
    return payload
