from __future__ import annotations

from dataclasses import dataclass
from threading import Condition
from time import monotonic, perf_counter
from typing import Callable, Hashable

from .config import ObserverConfig
from .weather import WeatherSnapshot


@dataclass(frozen=True, slots=True)
class SharedWeatherSnapshotResult:
    snapshot: WeatherSnapshot
    loader_ms: float
    shared_wait_ms: float
    cache_hit: bool


@dataclass(slots=True)
class _CacheEntry:
    snapshot: WeatherSnapshot | None = None
    expires_at: float = 0.0
    loading: bool = False


class WeatherSnapshotCache:
    """Bounded process-local cache shared by weather and observing endpoints."""

    def __init__(
        self,
        *,
        ttl_seconds: float = 300.0,
        fallback_ttl_seconds: float = 30.0,
        max_entries: int = 32,
    ) -> None:
        if ttl_seconds <= 0 or fallback_ttl_seconds <= 0:
            raise ValueError("weather cache TTLs must be positive")
        if max_entries <= 0:
            raise ValueError("max_entries must be positive")
        self._ttl_seconds = ttl_seconds
        self._fallback_ttl_seconds = fallback_ttl_seconds
        self._max_entries = max_entries
        self._condition = Condition()
        self._entries: dict[Hashable, _CacheEntry] = {}

    def get_or_load(
        self,
        key: Hashable,
        loader: Callable[[], WeatherSnapshot],
    ) -> SharedWeatherSnapshotResult:
        waited_ms = 0.0

        while True:
            with self._condition:
                now = monotonic()
                self._prune_locked(now)
                entry = self._entries.get(key)
                if entry is not None and entry.snapshot is not None and now < entry.expires_at:
                    return SharedWeatherSnapshotResult(
                        snapshot=entry.snapshot,
                        loader_ms=0.0,
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

        load_started = perf_counter()
        try:
            snapshot = loader()
        except Exception:
            with self._condition:
                current = self._entries.get(key)
                if current is entry:
                    self._entries.pop(key, None)
                self._condition.notify_all()
            raise
        loader_ms = (perf_counter() - load_started) * 1000.0

        ttl = self._fallback_ttl_seconds if snapshot.fallback_used else self._ttl_seconds
        with self._condition:
            entry.snapshot = snapshot
            entry.expires_at = monotonic() + ttl
            entry.loading = False
            self._trim_locked(protected_key=key)
            self._condition.notify_all()

        return SharedWeatherSnapshotResult(
            snapshot=snapshot,
            loader_ms=loader_ms,
            shared_wait_ms=waited_ms,
            cache_hit=False,
        )

    def clear(self) -> None:
        with self._condition:
            self._entries.clear()
            self._condition.notify_all()

    def _prune_locked(self, now: float) -> None:
        for key in [
            key
            for key, entry in self._entries.items()
            if not entry.loading and now >= entry.expires_at
        ]:
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


def weather_cache_key(observer: ObserverConfig, provider_factory: object) -> tuple[object, ...]:
    """Match MET Norway's location precision while isolating provider replacements."""
    return (
        provider_factory,
        round(observer.latitude, 5),
        round(observer.longitude, 5),
        round(observer.altitude_m),
    )


API_WEATHER_SNAPSHOT_CACHE = WeatherSnapshotCache()
