from __future__ import annotations

from dataclasses import dataclass
from math import asin, cos, radians, sin, sqrt
from threading import Condition
from time import monotonic, perf_counter
from typing import Callable, Hashable

from .aircraft import AircraftObserver, AircraftSnapshot

_EARTH_RADIUS_KM = 6371.0088


@dataclass(frozen=True, slots=True)
class SharedAircraftSnapshotResult:
    snapshot: AircraftSnapshot
    provider_timings: dict[str, float]
    shared_wait_ms: float
    cache_hit: bool


@dataclass(slots=True)
class _CacheEntry:
    snapshot: AircraftSnapshot | None = None
    expires_at: float = 0.0
    loading: bool = False


class AircraftSnapshotCache:
    """Bounded short-lived single-flight cache for live aircraft snapshots.

    The cache is deliberately tiny and short lived. Its purpose is to let the two
    simultaneous Live Sky aircraft views share one provider request, not to make
    aircraft positions stale for a meaningful amount of time.
    """

    def __init__(self, *, ttl_seconds: float = 1.0, max_entries: int = 4) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        if max_entries <= 0:
            raise ValueError("max_entries must be positive")
        self._ttl_seconds = ttl_seconds
        self._max_entries = max_entries
        self._condition = Condition()
        self._entries: dict[Hashable, _CacheEntry] = {}

    def get_or_fetch(
        self,
        key: Hashable,
        fetcher: Callable[[], tuple[AircraftSnapshot, dict[str, float]]],
    ) -> SharedAircraftSnapshotResult:
        waited_ms = 0.0

        while True:
            with self._condition:
                now = monotonic()
                self._prune_locked(now)
                entry = self._entries.get(key)
                if entry is not None and entry.snapshot is not None and now < entry.expires_at:
                    return SharedAircraftSnapshotResult(
                        snapshot=entry.snapshot,
                        provider_timings={},
                        shared_wait_ms=waited_ms,
                        cache_hit=True,
                    )

                if entry is not None and entry.loading:
                    wait_started = perf_counter()
                    self._condition.wait()
                    waited_ms += (perf_counter() - wait_started) * 1000.0
                    continue

                if entry is None:
                    entry = _CacheEntry()
                    self._entries[key] = entry
                entry.loading = True
                entry.snapshot = None
                entry.expires_at = 0.0
                break

        try:
            snapshot, timings = fetcher()
        except Exception:
            with self._condition:
                current = self._entries.get(key)
                if current is entry:
                    self._entries.pop(key, None)
                self._condition.notify_all()
            raise

        with self._condition:
            entry.snapshot = snapshot
            entry.expires_at = monotonic() + self._ttl_seconds
            entry.loading = False
            self._trim_locked(protected_key=key)
            self._condition.notify_all()

        return SharedAircraftSnapshotResult(
            snapshot=snapshot,
            provider_timings=dict(timings),
            shared_wait_ms=waited_ms,
            cache_hit=False,
        )

    def clear(self) -> None:
        with self._condition:
            self._entries.clear()
            self._condition.notify_all()

    def _prune_locked(self, now: float) -> None:
        expired = [
            key
            for key, entry in self._entries.items()
            if not entry.loading and entry.snapshot is not None and now >= entry.expires_at
        ]
        for key in expired:
            self._entries.pop(key, None)

    def _trim_locked(self, *, protected_key: Hashable) -> None:
        if len(self._entries) <= self._max_entries:
            return
        removable = sorted(
            (
                (entry.expires_at, key)
                for key, entry in self._entries.items()
                if key != protected_key and not entry.loading
            ),
            key=lambda item: item[0],
        )
        for _expires_at, key in removable:
            if len(self._entries) <= self._max_entries:
                break
            self._entries.pop(key, None)


def provider_effective_radius_km(radius_km: float) -> float:
    """Return the radius adsb.lol actually receives after NM rounding."""
    radius_nm = max(1, min(250, round(radius_km / 1.852)))
    return radius_nm * 1.852


def slice_snapshot_radius(
    snapshot: AircraftSnapshot,
    observer: AircraftObserver,
    radius_km: float,
) -> AircraftSnapshot:
    """Restrict a broader provider snapshot to the caller's original radius."""
    effective_radius_km = provider_effective_radius_km(radius_km)
    observations = tuple(
        observation
        for observation in snapshot.observations
        if _surface_distance_km(
            observer.latitude_deg,
            observer.longitude_deg,
            observation.latitude_deg,
            observation.longitude_deg,
        )
        <= effective_radius_km
    )
    radius_nm = max(1, min(250, round(radius_km / 1.852)))
    return AircraftSnapshot(
        observations=observations,
        source_id=snapshot.source_id,
        source_label=snapshot.source_label,
        fetched_at=snapshot.fetched_at,
        source_observed_at=snapshot.source_observed_at,
        coverage_description=f"bounded observer area, {radius_nm} NM radius",
        state=snapshot.state,
        error=snapshot.error,
    )


def _surface_distance_km(
    latitude_a_deg: float,
    longitude_a_deg: float,
    latitude_b_deg: float,
    longitude_b_deg: float,
) -> float:
    latitude_a = radians(latitude_a_deg)
    latitude_b = radians(latitude_b_deg)
    delta_latitude = latitude_b - latitude_a
    delta_longitude = radians(longitude_b_deg - longitude_a_deg)
    sin_latitude = sin(delta_latitude / 2.0)
    sin_longitude = sin(delta_longitude / 2.0)
    haversine = (
        sin_latitude * sin_latitude
        + cos(latitude_a) * cos(latitude_b) * sin_longitude * sin_longitude
    )
    return 2.0 * _EARTH_RADIUS_KM * asin(min(1.0, sqrt(haversine)))
