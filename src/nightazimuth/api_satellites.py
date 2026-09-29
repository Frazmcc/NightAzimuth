from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
import logging
import threading

from fastapi import APIRouter, HTTPException, Query

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


@router.get("")
def satellites(
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

    with _SATELLITE_PIPELINE_LOCK:
        return _build_satellite_snapshot(
            latitude=latitude,
            longitude=longitude,
            altitude_m=altitude_m,
            minimum_elevation_deg=minimum_elevation_deg,
            group=group,
            identification_detail=identification_detail,
        )


def _build_satellite_snapshot(
    *,
    latitude: float,
    longitude: float,
    altitude_m: float,
    minimum_elevation_deg: float,
    group: str,
    identification_detail: bool,
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

    group_payloads: dict[str, list[dict[str, object]]] = {}
    failures: list[tuple[str, Exception]] = []
    future_groups = {
        _GROUP_EXECUTOR.submit(client.load_group, requested_group): requested_group
        for requested_group in requested_groups
    }
    for future in as_completed(future_groups):
        requested_group = future_groups[future]
        try:
            group_payloads[requested_group] = future.result()
        except (CelestrakError, ValueError) as exc:
            failures.append((requested_group, exc))
            logger.warning("Satellite group %s unavailable: %s", requested_group, exc)

    if primary_group not in group_payloads:
        raise HTTPException(
            status_code=503,
            detail="Primary satellite catalogue is temporarily unavailable",
        )

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

    tracker = SatelliteTracker(observer)
    positions = tracker.positions_above_horizon(
        merged.values(),
        minimum_elevation_deg=minimum_elevation_deg,
        at=observed_at,
    )

    # Convert to the response shape before returning, then explicitly release the
    # catalogue copies and dataclass graph.  FastAPI/Starlette serialisation and
    # gzip happen after this function returns; keeping both object graphs alive
    # until then needlessly raises peak RSS for the largest endpoint.
    satellite_payloads = [asdict(position) for position in positions]
    count = len(satellite_payloads)
    del positions
    del merged
    del group_payloads
    del future_groups

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
