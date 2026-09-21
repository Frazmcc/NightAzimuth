from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import isfinite
from typing import Any
from urllib.parse import urlparse

import httpx

from .aircraft import AircraftObservation, AircraftObserver, AircraftSnapshot, AircraftSnapshotState, AircraftSourceKind, classify_snapshot_age
from .aircraft_adsb_lol import FOOT_TO_M, FPM_TO_MPS, KNOT_TO_MPS


class ReadsbProvider:
    provider_id = "readsb-local"
    label = "Local ADS-B receiver"
    source_kind = AircraftSourceKind.LOCAL

    def __init__(self, endpoint_url: str, *, client: httpx.Client | None = None, timeout_seconds: float = 3.0) -> None:
        parsed = urlparse(endpoint_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("local ADS-B endpoint must be an absolute http(s) URL")
        self.endpoint_url = endpoint_url
        self._client = client
        self._timeout_seconds = timeout_seconds

    def fetch_snapshot(self, observer: AircraftObserver, radius_km: float) -> AircraftSnapshot:
        del observer, radius_km
        fetched_at = datetime.now(timezone.utc)
        owns_client = self._client is None
        client = self._client or httpx.Client(timeout=self._timeout_seconds, follow_redirects=True)
        try:
            response = client.get(self.endpoint_url)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            return AircraftSnapshot((), self.provider_id, self.label, fetched_at, None, "local receiver coverage", AircraftSnapshotState.UNAVAILABLE, f"local ADS-B receiver unavailable: {exc}")
        finally:
            if owns_client:
                client.close()
        source_time = _payload_time(payload, fetched_at)
        rows = payload.get("aircraft", []) if isinstance(payload, dict) else []
        observations = tuple(observation for row in rows if isinstance(row, dict) if (observation := _normalise_readsb_record(row, source_time)) is not None)
        age_seconds = max(0.0, (fetched_at - source_time).total_seconds())
        return AircraftSnapshot(observations, self.provider_id, self.label, fetched_at, source_time, "local receiver coverage", classify_snapshot_age(age_seconds), None)


def _normalise_readsb_record(record: dict[str, Any], source_time: datetime) -> AircraftObservation | None:
    icao24 = str(record.get("hex") or "").strip().lower()
    lat = _finite(record.get("lat")); lon = _finite(record.get("lon"))
    if not icao24 or lat is None or lon is None or not -90.0 <= lat <= 90.0 or not -180.0 <= lon <= 180.0:
        return None
    seen_pos = _nonnegative(record.get("seen_pos"))
    if seen_pos is None: seen_pos = _nonnegative(record.get("seen")) or 0.0
    seen = _nonnegative(record.get("seen")); seen = seen_pos if seen is None else seen
    on_ground = record.get("alt_baro") == "ground"
    barometric_altitude_m = None
    if not on_ground:
        altitude_ft = _finite(record.get("alt_baro"))
        if altitude_ft is not None: barometric_altitude_m = altitude_ft * FOOT_TO_M
    geometric_altitude_m = _scaled(record.get("alt_geom"), FOOT_TO_M)
    ground_speed_mps = _scaled(record.get("gs"), KNOT_TO_MPS, nonnegative=True)
    vertical_fpm = _finite(record.get("baro_rate"))
    if vertical_fpm is None: vertical_fpm = _finite(record.get("geom_rate"))
    vertical_rate_mps = vertical_fpm * FPM_TO_MPS if vertical_fpm is not None else None
    db_flags = int(_finite(record.get("dbFlags")) or 0)
    try:
        return AircraftObservation(
            icao24=icao24, callsign=str(record.get("flight") or "").strip() or None,
            latitude_deg=lat, longitude_deg=lon,
            barometric_altitude_m=barometric_altitude_m, geometric_altitude_m=geometric_altitude_m,
            ground_speed_mps=ground_speed_mps, track_deg=_finite(record.get("track")), vertical_rate_mps=vertical_rate_mps,
            squawk=str(record.get("squawk") or "").strip() or None, on_ground=on_ground,
            position_observed_at=source_time - timedelta(seconds=seen_pos), contact_observed_at=source_time - timedelta(seconds=seen),
            source_id=ReadsbProvider.provider_id, source_label=ReadsbProvider.label, source_kind=AircraftSourceKind.LOCAL,
            registration=str(record.get("r") or "").strip() or None,
            type_code=str(record.get("t") or "").strip() or None,
            type_description=str(record.get("desc") or "").strip() or None,
            operator=str(record.get("ownOp") or "").strip() or None,
            military=bool(db_flags & 1),
        )
    except ValueError:
        return None


def _payload_time(payload: Any, fallback: datetime) -> datetime:
    if not isinstance(payload, dict): return fallback
    value = _finite(payload.get("now"))
    if value is None: return fallback
    if value > 10_000_000_000: value /= 1000.0
    try: return datetime.fromtimestamp(value, tz=timezone.utc)
    except (OverflowError, OSError, ValueError): return fallback


def _finite(value: Any) -> float | None:
    if value is None or value == "": return None
    try: number = float(value)
    except (TypeError, ValueError): return None
    return number if isfinite(number) else None


def _nonnegative(value: Any) -> float | None:
    number = _finite(value)
    return None if number is None else max(0.0, number)


def _scaled(value: Any, factor: float, *, nonnegative: bool = False) -> float | None:
    number = _finite(value)
    if number is None or (nonnegative and number < 0): return None
    return number * factor
