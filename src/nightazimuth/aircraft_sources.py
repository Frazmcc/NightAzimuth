from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

from .aircraft import (
    AircraftObserver,
    AircraftProvider,
    AircraftSnapshot,
    AircraftSnapshotState,
)


class AircraftSourceCoordinator:
    """Choose one authoritative aircraft source and preserve bounded last-good data."""

    def __init__(
        self,
        *,
        internet_provider: AircraftProvider,
        local_provider: AircraftProvider | None = None,
        stale_grace_seconds: float = 90.0,
    ) -> None:
        if stale_grace_seconds < 0:
            raise ValueError("stale_grace_seconds must be non-negative")
        self._internet_provider = internet_provider
        self._local_provider = local_provider
        self._stale_grace = timedelta(seconds=stale_grace_seconds)
        self._last_good: AircraftSnapshot | None = None

    def fetch_snapshot(
        self,
        observer: AircraftObserver,
        radius_km: float,
        *,
        now: datetime | None = None,
    ) -> AircraftSnapshot:
        current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)

        if self._local_provider is not None:
            local = self._local_provider.fetch_snapshot(observer, radius_km)
            if _usable(local):
                self._remember(local)
                return local

        internet = self._internet_provider.fetch_snapshot(observer, radius_km)
        if _usable(internet):
            self._remember(internet)
            return internet

        cached = self._last_good
        if cached is not None and current - cached.fetched_at <= self._stale_grace:
            age = max(0.0, (current - cached.fetched_at).total_seconds())
            return replace(
                cached,
                state=AircraftSnapshotState.STALE,
                error=f"live aircraft sources unavailable; showing last-good data ({age:.0f}s old)",
            )

        return AircraftSnapshot(
            observations=(),
            source_id=internet.source_id,
            source_label=internet.source_label,
            fetched_at=internet.fetched_at,
            source_observed_at=internet.source_observed_at,
            coverage_description=internet.coverage_description,
            state=AircraftSnapshotState.UNAVAILABLE,
            error=internet.error or "aircraft data unavailable",
        )

    def clear_last_good(self) -> None:
        self._last_good = None

    def _remember(self, snapshot: AircraftSnapshot) -> None:
        if snapshot.state in {AircraftSnapshotState.LIVE, AircraftSnapshotState.AGING}:
            self._last_good = snapshot


def _usable(snapshot: AircraftSnapshot) -> bool:
    return snapshot.state in {AircraftSnapshotState.LIVE, AircraftSnapshotState.AGING}
