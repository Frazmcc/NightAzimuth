from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import isfinite
from typing import Any

import httpx

from .aircraft import (
    AircraftObservation,
    AircraftObserver,
    AircraftSnapshot,
    AircraftSnapshotState,
    AircraftSourceKind,
    classify_snapshot_age,
)

KNOT_TO_MPS = 0.514444
FOOT_TO_M = 0.3048
FPM_TO_MPS = 0.00508


class AdsbLolProvider:
    provider_id = "adsb-lol"
    label = "adsb.lol"
    source_kind = AircraftSourceKind.INTERNET

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        timeout_seconds: float = 8.0,
        user_agent: str = "NightAzimuth/1.0 (+https://github.com/Frazmcc/NightAzimuth)",
    ) -> None:
        self._client = client
        self._timeout_seconds = timeout_seconds
        self._user_agent = user_agent

    def fetch_snapshot(self, observer: AircraftObserver, radius_km: float) -> AircraftSnapshot:
        if not isfinite(radius_km) or radius_km <= 0:
            raise ValueError("radius_km must be a positive finite number")

        radius_nm = max(1, min(250, round(radius_km / 1.852)))
        # /v2/point is the provider's documented point-radius endpoint.  The older
        # /v2/lat/.../lon/.../dist/... alias is still documented, but using the
        # canonical endpoint keeps NightAzimuth aligned with the current schema.
        url = (
            "https://api.adsb.lol/v2/point/"
            f"{observer.latitude_deg:.6f}/{observer.longitude_deg:.6f}/{radius_nm}"
        )
        fetched_at = datetime.now(timezone.utc)
        owns_client = self._client is None
        client = self._client or httpx.Client(
            timeout=self._timeout_seconds,
            headers={"User-Agent": self._user_agent, "Accept": "application/json"},
            follow_redirects=True,
        )
        try:
            response = client.get(url)
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            return AircraftSnapshot(
                observations=(),
                source_id=self.provider_id,
                source_label=self.label,
                fetched_at=fetched_at,
                source_observed_at=None,
                coverage_description=f"bounded observer area, {radius_nm} NM radius",
                state=AircraftSnapshotState.UNAVAILABLE,
                error=f"adsb.lol unavailable: {exc}",
            )
        finally:
            if owns_client:
                client.close()

        source_time = _payload_time(payload, fallback=fetched_at)
        observations = tuple(
            observation
            for record in payload.get("ac", [])
            if isinstance(record, dict)
            if (observation := _normalise_record(record, source_time)) is not None
        )
        age_seconds = max(0.0, (fetched_at - source_time).total_seconds())
        return AircraftSnapshot(
            observations=observations,
            source_id=self.provider_id,
            source_label=self.label,
            fetched_at=fetched_at,
            source_observed_at=source_time,
            coverage_description=f"bounded observer area, {radius_nm} NM radius",
            state=classify_snapshot_age(age_seconds),
            error=None,
        )


def _normalise_record(record: dict[str, Any], snapshot_time: datetime) -> AircraftObservation | None:
    icao24 = str(record.get("hex") or "").strip().lower()
    if not icao24:
        return None

    lat = _finite(record.get("lat"))
    lon = _finite(record.get("lon"))
    seen_pos = _nonnegative(record.get("seen_pos"))

    # The current adsb.lol V2 schema can supply a recent `lastPosition` object
    # when the aircraft record has no top-level lat/lon.  Those contacts are
    # useful for identification and were previously discarded completely.
    last_position = record.get("lastPosition")
    if (lat is None or lon is None) and isinstance(last_position, dict):
        fallback_lat = _finite(last_position.get("lat"))
        fallback_lon = _finite(last_position.get("lon"))
        if fallback_lat is not None and fallback_lon is not None:
            lat = fallback_lat
            lon = fallback_lon
            fallback_seen_pos = _nonnegative(last_position.get("seen_pos"))
            if fallback_seen_pos is not None:
                seen_pos = fallback_seen_pos

    if lat is None or lon is None:
        return None
    if not -90.0 <= lat <= 90.0 or not -180.0 <= lon <= 180.0:
        return None

    if seen_pos is None:
        seen_pos = _nonnegative(record.get("seen")) or 0.0
    seen = _nonnegative(record.get("seen"))
    if seen is None:
        seen = seen_pos

    on_ground = record.get("alt_baro") == "ground"
    barometric_altitude_m = None
    if not on_ground:
        altitude_ft = _finite(record.get("alt_baro"))
        if altitude_ft is not None:
            barometric_altitude_m = altitude_ft * FOOT_TO_M

    geometric_altitude_m = None
    geometric_ft = _finite(record.get("alt_geom"))
    if geometric_ft is not None:
        geometric_altitude_m = geometric_ft * FOOT_TO_M

    ground_speed_mps = None
    speed_knots = _finite(record.get("gs"))
    if speed_knots is not None and speed_knots >= 0:
        ground_speed_mps = speed_knots * KNOT_TO_MPS

    vertical_rate_mps = None
    vertical_fpm = _finite(record.get("baro_rate"))
    if vertical_fpm is None:
        vertical_fpm = _finite(record.get("geom_rate"))
    if vertical_fpm is not None:
        vertical_rate_mps = vertical_fpm * FPM_TO_MPS

    db_flags = int(_finite(record.get("dbFlags")) or 0)
    try:
        return AircraftObservation(
            icao24=icao24,
            callsign=str(record.get("flight") or "").strip() or None,
            latitude_deg=lat,
            longitude_deg=lon,
            barometric_altitude_m=barometric_altitude_m,
            geometric_altitude_m=geometric_altitude_m,
            ground_speed_mps=ground_speed_mps,
            track_deg=_finite(record.get("track")),
            vertical_rate_mps=vertical_rate_mps,
            squawk=str(record.get("squawk") or "").strip() or None,
            on_ground=on_ground,
            position_observed_at=snapshot_time - timedelta(seconds=seen_pos),
            contact_observed_at=snapshot_time - timedelta(seconds=seen),
            source_id=AdsbLolProvider.provider_id,
            source_label=AdsbLolProvider.label,
            source_kind=AircraftSourceKind.INTERNET,
            registration=str(record.get("r") or "").strip() or None,
            type_code=str(record.get("t") or "").strip() or None,
            type_description=str(record.get("desc") or "").strip() or None,
            operator=str(record.get("ownOp") or "").strip() or None,
            military=bool(db_flags & 1),
        )
    except ValueError:
        return None


def _payload_time(payload: dict[str, Any], *, fallback: datetime) -> datetime:
    value = _finite(payload.get("now"))
    if value is None:
        return fallback
    if value > 10_000_000_000:
        value /= 1000.0
    try:
        return datetime.fromtimestamp(value, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return fallback


def _finite(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if isfinite(number) else None


def _nonnegative(value: Any) -> float | None:
    number = _finite(value)
    return None if number is None else max(0.0, number)
