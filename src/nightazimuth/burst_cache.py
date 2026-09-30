from __future__ import annotations

from collections import OrderedDict
from threading import RLock
from time import monotonic
from typing import Generic, Hashable, TypeVar

T = TypeVar("T")


class BurstResultCache(Generic[T]):
    """Tiny bounded TTL cache for collapsing near-simultaneous identical work.

    This cache is intentionally process-local and short lived. It is designed for
    expensive results that are already admitted serially: after the first request
    finishes, queued requests with the exact same key can reuse that result rather
    than immediately repeating the same CPU work.
    """

    def __init__(self, *, ttl_seconds: float = 2.0, max_entries: int = 32) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        if max_entries <= 0:
            raise ValueError("max_entries must be positive")
        self.ttl_seconds = float(ttl_seconds)
        self.max_entries = int(max_entries)
        self._lock = RLock()
        self._entries: OrderedDict[Hashable, tuple[float, T]] = OrderedDict()

    def get(self, key: Hashable) -> T | None:
        now = monotonic()
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            stored_at, value = entry
            if now - stored_at >= self.ttl_seconds:
                self._entries.pop(key, None)
                return None
            self._entries.move_to_end(key)
            return value

    def put(self, key: Hashable, value: T) -> None:
        with self._lock:
            self._entries.pop(key, None)
            self._entries[key] = (monotonic(), value)
            while len(self._entries) > self.max_entries:
                self._entries.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
