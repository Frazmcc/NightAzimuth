from __future__ import annotations

from collections.abc import Iterator, Mapping
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path
import logging
import threading
from time import perf_counter, time_ns

from fastapi import APIRouter, HTTPException, Query, Response

from .celestrak import CelestrakClient, CelestrakError
from .config import ObserverConfig
from .tracker import SatellitePosition, SatelliteTracker

router = APIRouter(prefix="/api/v1/satellites", tags=["satellites"])
logger = logging.getLogger(__name__)

_API_CACHE = Path("data/cache/api")
_DEFAULT_GROUP = "ACTIVE"
_IDENTIFICATION_GROUPS = ("LAST-30-DAYS", "STATIONS", "VISUAL")
_HOSTED_HOT_GROUPS = frozenset((_DEFAULT_GROUP, *_IDENTIFICATION_GROUPS))
_HOSTED_MERGE_GROUPS = (_DEFAULT_GROUP, *_IDENTIFICATION_GROUPS)
# Reuse a small worker pool across requests. Creating four fresh threads for
# every satellite poll adds avoidable overhead and scales poorly with users.
_GROUP_EXECUTOR = ThreadPoolExecutor(max_workers=4, thread_name_prefix="satellite-catalogue")
# Keep references to the already-parsed hosted catalogues while their exact file
# generation remains inside the CelesTrak client's existing freshness window.
# This does not duplicate ACTIVE in memory and does not cache positions. It only
# avoids four worker submissions and filesystem freshness checks on warm polls.
_GROUP_HOT_CACHE_LOCK = threading.RLock()
_GROUP_HOT_CACHE: dict[str, tuple[int, int, list[dict[str, object]]]] = {}
# Keep a single merged hosted generation. Each element is a tiny mapping view
# over the original CelesTrak dictionary plus virtual source-group metadata, so
# the cache does not retain a second copied ACTIVE catalogue in memory.
_MERGED_CATALOGUE_CACHE_LOCK = threading.RLock()
_MERGED_CATALOGUE_CACHE: tuple[
    object,
    tuple["_CatalogueElementView", ...],
] | None = None
# Building an ACTIVE snapshot temporarily owns SGP4 arrays, thousands of track
# dataclasses and then the JSON-ready payload. On Render's 512 MB free instance,
# overlapping snapshots can multiply that peak. One propagation pipeline at a
# time is appropriate for the service's 0.1 CPU and protects the process from a
# small traffic burst or multiple open browser tabs.
_SATELLITE_PIPELINE_LOCK = threading.Lock()


class _CatalogueElementView(Mapping[str, object]):
    """Read-only orbital record that overlays compact source-group metadata."""

    __slots__ = ("_fields", "_source_groups")

    def __init__(
        self,
        fields: dict[str, object],
        source_groups: tuple[str, ...],
    ) -> None:
        self._fields = fields
        self._source_groups = source_groups

    def __getitem__(self, key: str) -> object:
        if key == "_nightazimuth_groups":
            return self._source_groups
        return self._fields[key]

    def __iter__(self) -> Iterator[str]:
        yield from self._fields
        if "_nightazimuth_groups" not in self._fields:
            yield "_nightazimuth_groups"

    def __len__(self) -> int:
        return len(self._fields) + (0 if "_nightazimuth_groups" in self._fields else 1)


def _clear_hot_group_cache() -> None:
    """Clear hosted catalogue references and merged view (primarily for tests)."""

    global _MERGED_CATALOGUE_CACHE
    with _GROUP_HOT_CACHE_LOCK:
        _GROUP_HOT_CACHE.clear()
    with _MERGED_CATALOGUE_CACHE_LOCK:
        _MERGED_CATALOGUE_CACHE = None


def _hot_group_cache_get(
    client: object,
    group: str,
) -> tuple[list[dict[str, object]], object] | None:
    """Return a still-fresh hosted catalogue without scheduling a worker."""

    if group not in _HOSTED_HOT_GROUPS:
        return None
    max_age_minutes = getattr(client, "cache_max_age_minutes", None)
    if not isinstance(max_age_minutes, (int, float)) or max_age_minutes <= 0:
        return None

    with _GROUP_HOT_CACHE_LOCK:
        cached = _GROUP_HOT_CACHE.get(group)
        if cached is None:
            return None
        modified_ns, size, payload = cached
        max_age_ns = int(float(max_age_minutes) * 60.0 * 1_000_000_000)
        if time_ns() - modified_ns > max_age_ns:
            _GROUP_HOT_CACHE.pop(group, None)
            return None
        return payload, (modified_ns, size)


def _remember_hot_group(
    group: str,
    payload: list[dict[str, object]],
    generation: object | None,
) -> None:
    """Remember only the four bounded hosted groups and exact file generations."""

    if group not in _HOSTED_HOT_GROUPS:
        return
    if (
        not isinstance(generation, tuple)
        or len(generation) != 2
        or not all(isinstance(value, int) for value in generation)
    ):
        return
    modified_ns, size = generation
    with _GROUP_HOT_CACHE_LOCK:
        _GROUP_HOT_CACHE[group] = (modified_ns, size, payload)


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


def _catalogue_identity(fields: Mapping[str, object]) -> str:
    return str(
        fields.get("NORAD_CAT_ID")
        or fields.get("OBJECT_ID")
        or fields.get("OBJECT_NAME")
        or ""
    ).strip()


def _build_merged_catalogue(
    requested_groups: list[str],
    group_payloads: dict[str, list[dict[str, object]]],
) -> tuple[_CatalogueElementView, ...]:
    """Deduplicate groups into zero-copy orbital record views."""

    base_fields: dict[str, dict[str, object]] = {}
    source_groups: dict[str, list[str]] = {}
    ordered_keys: list[str] = []

    for requested_group in requested_groups:
        for fields in group_payloads.get(requested_group, []):
            key = _catalogue_identity(fields)
            if not key:
                continue
            if key not in base_fields:
                base_fields[key] = fields
                source_groups[key] = [requested_group]
                ordered_keys.append(key)
            elif requested_group not in source_groups[key]:
                source_groups[key].append(requested_group)

    return tuple(
        _CatalogueElementView(base_fields[key], tuple(source_groups[key]))
        for key in ordered_keys
    )


def _merged_catalogue_for(
    cache_key: object,
    requested_groups: list[str],
    group_payloads: dict[str, list[dict[str, object]]],
) -> tuple[tuple[_CatalogueElementView, ...], bool]:
    """Return the one cached merged hosted generation, replacing it on refresh."""

    global _MERGED_CATALOGUE_CACHE

    with _MERGED_CATALOGUE_CACHE_LOCK:
        cached = _MERGED_CATALOGUE_CACHE
        if cached is not None and cached[0] == cache_key:
            return cached[1], True

        merged = _build_merged_catalogue(requested_groups, group_payloads)
        _MERGED_CATALOGUE_CACHE = (cache_key, merged)
        return merged, False


def _satellite_payload(position: SatellitePosition) -> dict[str, object]:
    """Convert one tracker result without dataclasses.asdict deepcopy recursion."""

    return {
        "name": position.name,
        "norad_id": position.norad_id,
        "azimuth_deg": position.azimuth_deg,
        "elevation_deg": position.elevation_deg,
        "range_km": position.range_km,
        "object_id": position.object_id,
        "launch_id": position.launch_id,
        "category": position.category,
        "source_groups": position.source_groups,
        "epoch_utc": position.epoch_utc,
        "inclination_deg": position.inclination_deg,
        "period_minutes": position.period_minutes,
        "eccentricity": position.eccentricity,
        "track": tuple(
            {
                "time_utc": point.time_utc,
                "azimuth_deg": point.azimuth_deg,
                "elevation_deg": point.elevation_deg,
                "range_km": point.range_km,
            }
            for point in position.track
        ),
    }


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
    much smaller VISUAL catalogue. No brightness or likely-visibility filter is
    applied: if an active catalogue object is geometrically above the requested
    horizon it is eligible to be returned and the browser decides whether it is
    inside the user's current field of view.

    Small supplementary groups are still loaded for identification metadata
    (recent launch, station, and bright-object membership) and deduplicated by
    catalogue identity. Batch SGP4 propagation in SatelliteTracker keeps the
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
        "catalogue_hot_hits=%d merge_cache_hit=%d catalog_count=%d returned_count=%d",
        total_ms,
        timings.get("lock_wait_ms", 0.0),
        timings.get("catalogue_load_ms", 0.0),
        timings.get("catalogue_merge_ms", 0.0),
        timings.get("tracker_init_ms", 0.0),
        timings.get("prepare_ms", 0.0),
        timings.get("propagation_ms", 0.0),
        timings.get("track_build_ms", 0.0),
        timings.get("payload_build_ms", 0.0),
        int(timings.get("catalogue_hot_hit_count", 0.0)),
        int(timings.get("catalogue_merge_cache_hit", 0.0)),
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
    future_groups = {}
    hot_hit_count = 0
    for requested_group in requested_groups:
        cached = _hot_group_cache_get(client, requested_group)
        if cached is not None:
            payload, generation = cached
            group_payloads[requested_group] = payload
            group_generations[requested_group] = generation
            hot_hit_count += 1
            continue
        future = _GROUP_EXECUTOR.submit(
            _load_group_with_generation,
            client,
            requested_group,
        )
        future_groups[future] = requested_group

    for future in as_completed(future_groups):
        requested_group = future_groups[future]
        try:
            payload, generation = future.result()
            group_payloads[requested_group] = payload
            group_generations[requested_group] = generation
            _remember_hot_group(requested_group, payload, generation)
        except (CelestrakError, ValueError) as exc:
            failures.append((requested_group, exc))
            logger.warning("Satellite group %s unavailable: %s", requested_group, exc)
    if timings is not None:
        timings["catalogue_load_ms"] = (perf_counter() - catalogue_load_started) * 1000.0
        timings["catalogue_hot_hit_count"] = float(hot_hit_count)

    if primary_group not in group_payloads:
        raise HTTPException(
            status_code=503,
            detail="Primary satellite catalogue is temporarily unavailable",
        )

    available_groups = [
        requested_group
        for requested_group in requested_groups
        if requested_group in group_payloads
    ]
    unavailable_groups = [requested_group for requested_group, _exc in failures]

    catalogue_cache_key: object | None = None
    if all(group_generations.get(group_name) is not None for group_name in available_groups):
        catalogue_cache_key = tuple(
            (group_name, group_generations.get(group_name))
            for group_name in requested_groups
        )

    catalogue_merge_started = perf_counter()
    merge_cache_hit = False
    can_cache_hosted_merge = (
        tuple(requested_groups) == _HOSTED_MERGE_GROUPS
        and available_groups == requested_groups
        and catalogue_cache_key is not None
    )
    if can_cache_hosted_merge:
        merged_elements, merge_cache_hit = _merged_catalogue_for(
            catalogue_cache_key,
            requested_groups,
            group_payloads,
        )
    else:
        merged_elements = _build_merged_catalogue(requested_groups, group_payloads)
    catalog_count = len(merged_elements)
    if timings is not None:
        timings["catalogue_merge_ms"] = (perf_counter() - catalogue_merge_started) * 1000.0
        timings["catalogue_merge_cache_hit"] = 1.0 if merge_cache_hit else 0.0

    tracker_init_started = perf_counter()
    tracker = SatelliteTracker(observer)
    if timings is not None:
        timings["tracker_init_ms"] = (perf_counter() - tracker_init_started) * 1000.0

    if catalogue_cache_key is None:
        positions = tracker.positions_above_horizon(
            merged_elements,
            minimum_elevation_deg=minimum_elevation_deg,
            at=observed_at,
        )
    else:
        positions = tracker.positions_above_horizon(
            merged_elements,
            minimum_elevation_deg=minimum_elevation_deg,
            at=observed_at,
            catalogue_cache_key=catalogue_cache_key,
        )
    if timings is not None:
        timings.update(getattr(tracker, "last_timings", {}))

    # Convert to the response shape before returning, then release request-local
    # references. The cached merged view retains only tiny wrappers over the same
    # parsed dictionaries already owned by the bounded CelesTrak cache.
    payload_build_started = perf_counter()
    satellite_payloads = [_satellite_payload(position) for position in positions]
    count = len(satellite_payloads)
    del positions
    del merged_elements
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