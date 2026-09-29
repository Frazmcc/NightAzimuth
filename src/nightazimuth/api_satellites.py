from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
import logging
import threading
from time import perf_counter

from fastapi import APIRouter, HTTPException, Query, Response

from .celestrak import CelestrakClient, CelestrakError
from .config import ObserverConfig
from .tracker import SatelliteTracker

router = APIRouter(prefix="/api/v1/satellites", tags=["satellites"])
logger = logging.getLogger(__name__)

_API_CACHE = Path("data/cache/api")
_DEFAULT_GROUP = "ACTIVE"
_IDENTIFICATION_GROUPS = ("LAST-30-DAYS", "STATIONS", "VISUAL")
# Reuse a small worker pool across requests. Creating four fresh threads for
# every satellite poll adds avoidable overhead and scales poorly with users.
_GROUP_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="satellite-catalogue")
# Building an ACTIVE snapshot temporarily owns a copied catalogue, SGP4 arrays,
# thousands of track dataclasses and then the JSON-ready payload.  On Render's
# 512 MB free instance, overlapping snapshots can multiply that peak even though
# the steady-state catalogue cache is bounded.  One propagation pipeline at a
# time is appropriate for the service's 0.1 CPU and protects the process from a
# small traffic burst or multiple open browser tabs.
_SATELLITE_PIPELINE_LOCK = threading.Lock()


def _load_group_with_generation(
    client: object,
    group: str,
) -> tuple[list[dict[str, object]], object | None]:
    """Load a group with a cheap generation token when the client supports it."""

    versioned_loader = getattr(client, "load_group_versioned", None)
    if callable(versioned_loader):
        payload, generation = versioned_loader(group)
        return payload, generation

    loader = getattr(client, "load_group")
    return loader(group), None


@router.get("")
def satellites(
    response: Response = None,
    latitude: float = Query(ge=-90.0, le=90.0),
    longitude: float = Query(ge=-180.0, le=180.0),
    altitude_m: float = Query(default=0.0),
    minimum_elevation_deg: float = Query(default=0.0, ge=0.0, le=90.0),
    group: str = Query(default=_DEFAULT_GROUP, min_length=1, max_length=64),
    identification_detail: bool = Query(default=True),
) -> dict[str, object]:
    """Return every known catalogue satellite above the requested horizon.

    The hosted Live Sky defaults to CelesTrak's ACTIVE catalogue instead of the
    much smaller VISUAL catalogue.  No brightness or likely-visibility filter is
    applied: if an active catalogue object is geometrically above the requested
    horizon it is eligible to be returned and the browser decides whether it is
    inside the user's current field of view.

    Small supplementary groups are still loaded for identification metadata
    (recent launch, station, and bright-object membership) and deduplicated by
    catalogue identity.  Batch SGP4 propagation in SatelliteTracker keeps the
    larger catalogue practical without reverting to per-object propagation.
    """

    request_started = perf_counter()
    lock_started = perf_counter()
    timings: dict[str, float] = {}
    with _SATELLITE_PIPELINE_LOCK:
        timings["lock_wait_ms"] = (perf_counter() - lock_started) * 1000.0
        payload = _build_satellite_snapshot(
            latitude=latitude,
            longitude=longitude,
            altitude_m=altitude_m,
            minimum_elevation_deg=minimum_elevation_deg,
            group=group,
            identification_detail=identification_detail,
            timings=timings,
        )

    total_ms = (perf_counter() - request_started) * 1000.0
    timings["total_ms"] = total_ms
    if response is not None:
        response.headers["Server-Timing"] = (
            f"lock_wait;dur={timings.get('lock_wait_ms', 0.0):.1f}, "
            f"catalogue_load;dur={timings.get('catalogue_load_ms', 0.0):.1f}, "
            f"catalogue_merge;dur={timings.get('catalogue_merge_ms', 0.0):.1f}, "
            f"tracker_init;dur={timings.get('tracker_init_ms', 0.0):.1f}, "
            f"prepare;dur={timings.get('prepare_ms', 0.0):.1f}, "
            f"propagate;dur={timings.get('propagation_ms', 0.0):.1f}, "
            f"track_build;dur={timings.get('track_build_ms', 0.0):.1f}, "
            f"payload_build;dur={timings.get('payload_build_ms', 0.0):.1f}, "
            f"total;dur={total_ms:.1f}"
        )
    logger.info(
        "satellite_request total_ms=%.1f lock_wait_ms=%.1f catalogue_load_ms=%.1f "
        "catalogue_merge_ms=%.1f tracker_init_ms=%.1f prepare_ms=%.1f "
        "propagation_ms=%.1f track_build_ms=%.1f payload_build_ms=%.1f "
        "catalog_count=%d returned_count=%d",
        total_ms,
        timings.get("lock_wait_ms", 0.0),
        timings.get("catalogue_load_ms", 0.0),
        timings.get("catalogue_merge_ms", 0.0),
        timings.get("tracker_init_ms", 0.0),
        timings.get("prepare_ms", 0.0),
        timings.get("propagation_ms", 0.0),
        timings.get("track_build_ms", 0.0),
        timings.get("payload_build_ms", 0.0),
        int(payload.get("catalog_count", 0)),
        int(payload.get("count", 0)),
    )
    return payload


def _build_satellite_snapshot(
    *,
    latitude: float,
    longitude: float,
    altitude_m: float,
    minimum_elevation_deg: float,
    group: str,
    identification_detail: bool,
    timings: dict[str, float] | None = None,
) -> dict[str, object]:
    observed_at = datetime.now(UTC)
    observer = ObserverConfig(
        latitude=latitude,
        longitude=longitude,
        altitude_m=altitude_m,
    )
    client = CelestrakClient(_API_CACHE)

    primary_group = group.strip().upper()
    requested_groups = [primary_group]
    if identification_detail:
        requested_groups.extend(
            candidate for candidate in _IDENTIFICATION_GROUPS if candidate not in requested_groups
        )

    catalogue_load_started = perf_counter()
    group_payloads: dict[str, list[dict[str, object]]] = {}
    group_generations: dict[str, object | None] = {}
    failures: list[tuple[str, Exception]] = []
    future_groups = {
        _GROUP_EXECUTOR.submit(
            _load_group_with_generation,
            client,
            requested_group,
        ): requested_group
        for requested_group in requested_groups
    }
    for future in as_completed(future_groups):
        requested_group = future_groups[future]
        try:
            payload, generation = future.result()
            group_payloads[requested_group] = payload
            group_generations[requested_group] = generation
        except (CelestrakError, ValueError) as exc:
            failures.append((requested_group, exc))
            logger.warning("Satellite group %s unavailable: %s", requested_group, exc)
    if timings is not None:
        timings["catalogue_load_ms"] = (perf_counter() - catalogue_load_started) * 1000.0

    if primary_group not in group_payloads:
        raise HTTPException(
            status_code=503,
            detail="Primary satellite catalogue is temporarily unavailable",
        )

    catalogue_merge_started = perf_counter()
    merged: dict[str, dict[str, object]] = {}
    for requested_group in requested_groups:
        for fields in group_payloads.get(requested_group, []):
            key = str(
                fields.get("NORAD_CAT_ID")
                or fields.get("OBJECT_ID")
                or fields.get("OBJECT_NAME")
                or ""
            ).strip()
            if not key:
                continue
            if key not in merged:
                merged[key] = dict(fields)
                merged[key]["_nightazimuth_groups"] = [requested_group]
            else:
                groups = merged[key].setdefault("_nightazimuth_groups", [])
                if isinstance(groups, list) and requested_group not in groups:
                    groups.append(requested_group)

    available_groups = [
        requested_group
        for requested_group in requested_groups
        if requested_group in group_payloads
    ]
    unavailable_groups = [requested_group for requested_group, _exc in failures]
    catalog_count = len(merged)
    if timings is not None:
        timings["catalogue_merge_ms"] = (perf_counter() - catalogue_merge_started) * 1000.0

    catalogue_cache_key: object | None = None
    if all(group_generations.get(group_name) is not None for group_name in available_groups):
        catalogue_cache_key = tuple(
            (group_name, group_generations.get(group_name))
            for group_name in requested_groups
        )

    tracker_init_started = perf_counter()
    tracker = SatelliteTracker(observer)
    if timings is not None:
        timings["tracker_init_ms"] = (perf_counter() - tracker_init_started) * 1000.0

    if catalogue_cache_key is None:
        positions = tracker.positions_above_horizon(
            merged.values(),
            minimum_elevation_deg=minimum_elevation_deg,
            at=observed_at,
        )
    else:
        positions = tracker.positions_above_horizon(
            merged.values(),
            minimum_elevation_deg=minimum_elevation_deg,
            at=observed_at,
            catalogue_cache_key=catalogue_cache_key,
        )
    if timings is not None:
        timings.update(getattr(tracker, "last_timings", {}))

    # Convert to the response shape before returning, then explicitly release the
    # catalogue copies and dataclass graph.  FastAPI/Starlette serialisation and
    # gzip happen after this function returns; keeping both object graphs alive
    # until then needlessly raises peak RSS for the largest endpoint.
    payload_build_started = perf_counter()
    satellite_payloads = [asdict(position) for position in positions]
    count = len(satellite_payloads)
    del positions
    del merged
    del group_payloads
    del group_generations
    del future_groups
    if timings is not None:
        timings["payload_build_ms"] = (perf_counter() - payload_build_started) * 1000.0

    return {
        "observed_at": observed_at.isoformat(),
        "source": "CelesTrak orbital data",
        "group": primary_group,
        "catalog_scope": "all active satellites" if primary_group == "ACTIVE" else primary_group,
        "brightness_filtered": False,
        "groups": available_groups,
        "unavailable_groups": unavailable_groups,
        "catalog_count": catalog_count,
        "observer": {
            "latitude_deg": latitude,
            "longitude_deg": longitude,
            "altitude_m": altitude_m,
        },
        "minimum_elevation_deg": minimum_elevation_deg,
        "count": count,
        "satellites": satellite_payloads,
    }
