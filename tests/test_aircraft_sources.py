from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from nightazimuth.aircraft import (
    AircraftObserver,
    AircraftSnapshot,
    AircraftSnapshotState,
    AircraftSourceKind,
)
from nightazimuth.aircraft_sources import AircraftSourceCoordinator


@dataclass
class FakeProvider:
    provider_id: str
    label: str
    source_kind: AircraftSourceKind
    snapshot: AircraftSnapshot

    def fetch_snapshot(self, observer: AircraftObserver, radius_km: float) -> AircraftSnapshot:
        return self.snapshot


def _snapshot(
    source_id: str,
    state: AircraftSnapshotState,
    fetched_at: datetime,
    *,
    source_kind: AircraftSourceKind = AircraftSourceKind.INTERNET,
) -> AircraftSnapshot:
    return AircraftSnapshot(
        observations=(),
        source_id=source_id,
        source_label=source_id,
        fetched_at=fetched_at,
        source_observed_at=fetched_at,
        coverage_description="test coverage",
        state=state,
        error=None if state != AircraftSnapshotState.UNAVAILABLE else "failed",
    )


def test_local_source_has_precedence_when_usable():
    now = datetime.now(timezone.utc)
    local = FakeProvider(
        "local",
        "local",
        AircraftSourceKind.LOCAL,
        _snapshot("local", AircraftSnapshotState.LIVE, now, source_kind=AircraftSourceKind.LOCAL),
    )
    internet = FakeProvider(
        "internet",
        "internet",
        AircraftSourceKind.INTERNET,
        _snapshot("internet", AircraftSnapshotState.LIVE, now),
    )
    coordinator = AircraftSourceCoordinator(internet_provider=internet, local_provider=local)

    result = coordinator.fetch_snapshot(AircraftObserver(55.86, -4.25), 100.0, now=now)
    assert result.source_id == "local"


def test_internet_is_used_when_local_source_is_unavailable():
    now = datetime.now(timezone.utc)
    local = FakeProvider(
        "local",
        "local",
        AircraftSourceKind.LOCAL,
        _snapshot("local", AircraftSnapshotState.UNAVAILABLE, now),
    )
    internet = FakeProvider(
        "internet",
        "internet",
        AircraftSourceKind.INTERNET,
        _snapshot("internet", AircraftSnapshotState.LIVE, now),
    )
    coordinator = AircraftSourceCoordinator(internet_provider=internet, local_provider=local)

    result = coordinator.fetch_snapshot(AircraftObserver(55.86, -4.25), 100.0, now=now)
    assert result.source_id == "internet"


def test_last_good_snapshot_is_only_used_inside_bounded_stale_grace():
    now = datetime.now(timezone.utc)
    internet = FakeProvider(
        "internet",
        "internet",
        AircraftSourceKind.INTERNET,
        _snapshot("internet", AircraftSnapshotState.LIVE, now),
    )
    coordinator = AircraftSourceCoordinator(internet_provider=internet, stale_grace_seconds=30)
    observer = AircraftObserver(55.86, -4.25)

    first = coordinator.fetch_snapshot(observer, 100.0, now=now)
    assert first.state == AircraftSnapshotState.LIVE

    internet.snapshot = _snapshot(
        "internet",
        AircraftSnapshotState.UNAVAILABLE,
        now + timedelta(seconds=5),
    )
    stale = coordinator.fetch_snapshot(observer, 100.0, now=now + timedelta(seconds=20))
    assert stale.state == AircraftSnapshotState.STALE
    assert stale.error is not None

    unavailable = coordinator.fetch_snapshot(observer, 100.0, now=now + timedelta(seconds=31))
    assert unavailable.state == AircraftSnapshotState.UNAVAILABLE
    assert unavailable.observations == ()
