from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import StrEnum
from math import isfinite
from typing import Protocol


class AircraftSourceKind(StrEnum):
    INTERNET = "internet"
    LOCAL = "local"


class AircraftSnapshotState(StrEnum):
    LIVE = "live"
    AGING = "aging"
    STALE = "stale"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True, slots=True)
class AircraftObserver:
    latitude_deg: float
    longitude_deg: float
    altitude_m: float = 0.0

    def __post_init__(self) -> None:
        if not isfinite(self.latitude_deg) or not -90.0 <= self.latitude_deg <= 90.0:
            raise ValueError("observer latitude must be finite and between -90 and 90 degrees")
        if not isfinite(self.longitude_deg) or not -180.0 <= self.longitude_deg <= 180.0:
            raise ValueError("observer longitude must be finite and between -180 and 180 degrees")
        if not isfinite(self.altitude_m):
            raise ValueError("observer altitude must be finite")


@dataclass(frozen=True, slots=True)
class AircraftObservation:
    icao24: str
    callsign: str | None
    latitude_deg: float
    longitude_deg: float
    barometric_altitude_m: float | None
    geometric_altitude_m: float | None
    ground_speed_mps: float | None
    track_deg: float | None
    vertical_rate_mps: float | None
    squawk: str | None
    on_ground: bool | None
    position_observed_at: datetime
    contact_observed_at: datetime | None
    source_id: str
    source_label: str
    source_kind: AircraftSourceKind

    def __post_init__(self) -> None:
        icao = self.icao24.strip().lower()
        if not icao or len(icao) > 8 or any(ch not in "0123456789abcdef" for ch in icao):
            raise ValueError("icao24 must be a non-empty hexadecimal identifier")
        object.__setattr__(self, "icao24", icao)
        if not isfinite(self.latitude_deg) or not -90.0 <= self.latitude_deg <= 90.0:
            raise ValueError("aircraft latitude must be finite and between -90 and 90 degrees")
        if not isfinite(self.longitude_deg) or not -180.0 <= self.longitude_deg <= 180.0:
            raise ValueError("aircraft longitude must be finite and between -180 and 180 degrees")
        _require_utc(self.position_observed_at, "position_observed_at")
        if self.contact_observed_at is not None:
            _require_utc(self.contact_observed_at, "contact_observed_at")
        for name in (
            "barometric_altitude_m",
            "geometric_altitude_m",
            "ground_speed_mps",
            "track_deg",
            "vertical_rate_mps",
        ):
            value = getattr(self, name)
            if value is not None and not isfinite(value):
                raise ValueError(f"{name} must be finite when supplied")
        if self.track_deg is not None:
            object.__setattr__(self, "track_deg", self.track_deg % 360.0)
        callsign = (self.callsign or "").strip() or None
        squawk = (self.squawk or "").strip() or None
        object.__setattr__(self, "callsign", callsign)
        object.__setattr__(self, "squawk", squawk)

    @property
    def preferred_altitude_m(self) -> float | None:
        if self.geometric_altitude_m is not None:
            return self.geometric_altitude_m
        return self.barometric_altitude_m

    def position_age_seconds(self, now: datetime | None = None) -> float:
        current = _utc_now(now)
        return max(0.0, (current - self.position_observed_at).total_seconds())

    def contact_age_seconds(self, now: datetime | None = None) -> float | None:
        if self.contact_observed_at is None:
            return None
        current = _utc_now(now)
        return max(0.0, (current - self.contact_observed_at).total_seconds())


@dataclass(frozen=True, slots=True)
class AircraftSnapshot:
    observations: tuple[AircraftObservation, ...]
    source_id: str
    source_label: str
    fetched_at: datetime
    source_observed_at: datetime | None
    coverage_description: str
    state: AircraftSnapshotState
    error: str | None = None

    def __post_init__(self) -> None:
        _require_utc(self.fetched_at, "fetched_at")
        if self.source_observed_at is not None:
            _require_utc(self.source_observed_at, "source_observed_at")

    @property
    def stale(self) -> bool:
        return self.state in {AircraftSnapshotState.STALE, AircraftSnapshotState.UNAVAILABLE}

    def source_age_seconds(self, now: datetime | None = None) -> float | None:
        if self.source_observed_at is None:
            return None
        current = _utc_now(now)
        return max(0.0, (current - self.source_observed_at).total_seconds())


class AircraftProvider(Protocol):
    provider_id: str
    label: str
    source_kind: AircraftSourceKind

    def fetch_snapshot(
        self,
        observer: AircraftObserver,
        radius_km: float,
    ) -> AircraftSnapshot:
        ...


def classify_snapshot_age(
    age_seconds: float | None,
    *,
    live_seconds: float = 15.0,
    aging_seconds: float = 45.0,
) -> AircraftSnapshotState:
    if age_seconds is None:
        return AircraftSnapshotState.AGING
    if age_seconds < 0:
        age_seconds = 0.0
    if age_seconds <= live_seconds:
        return AircraftSnapshotState.LIVE
    if age_seconds <= aging_seconds:
        return AircraftSnapshotState.AGING
    return AircraftSnapshotState.STALE


def _require_utc(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must be timezone-aware")


def _utc_now(value: datetime | None = None) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)
    _require_utc(value, "now")
    return value.astimezone(timezone.utc)
