from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import isfinite
from threading import BoundedSemaphore, Lock
from time import monotonic, perf_counter, sleep
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
_DEFAULT_TIMEOUT_SECONDS = 8.0
_DEFAULT_USER_AGENT = "NightAzimuth/1.0 (+https://github.com/Frazmcc/NightAzimuth)"
_SHARED_CLIENT_LOCK = Lock()
_SHARED_CLIENT: httpx.Client | None = None
_PROVIDER_REQUEST_CONCURRENCY = 1
_PROVIDER_REQUEST_GATE = BoundedSemaphore(_PROVIDER_REQUEST_CONCURRENCY)
_PROVIDER_MIN_START_INTERVAL_SECONDS = 0.75
_PROVIDER_RETRY_DELAY_SECONDS = 0.75
_PROVIDER_MAX_ATTEMPTS = 2
_PROVIDER_SCHEDULE_LOCK = Lock()
_PROVIDER_NEXT_REQUEST_AT = 0.0
_RETRYABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})


def shared_adsb_http_client() -> httpx.Client:
    """Return the process-wide HTTP client used by hosted aircraft providers.

    httpx.Client maintains connection pools per origin, so one long-lived client
    can safely reuse connections for the primary and secondary readsb-compatible
    providers without rebuilding TLS state on every Live Sky refresh.
    """

    global _SHARED_CLIENT
    with _SHARED_CLIENT_LOCK:
        if _SHARED_CLIENT is None or _SHARED_CLIENT.is_closed:
            _SHARED_CLIENT = httpx.Client(
                timeout=_DEFAULT_TIMEOUT_SECONDS,
                headers={"User-Agent": _DEFAULT_USER_AGENT, "Accept": "application/json"},
                follow_redirects=True,
            )
        return _SHARED_CLIENT


def prewarm_shared_adsb_http_client() -> None:
    """Create the default aircraft-provider connection pool without making a request."""

    shared_adsb_http_client()


def close_shared_adsb_http_client() -> None:
    """Close and discard the process-wide aircraft-provider connection pool."""

    global _SHARED_CLIENT
    with _SHARED_CLIENT_LOCK:
        client = _SHARED_CLIENT
        _SHARED_CLIENT = None
    if client is not None and not client.is_closed:
        client.close()


def _wait_for_provider_start_slot() -> float:
    """Space process-wide provider request starts to avoid bursty regional traffic."""

    global _PROVIDER_NEXT_REQUEST_AT
    with _PROVIDER_SCHEDULE_LOCK:
        now = monotonic()
        delay = max(0.0, _PROVIDER_NEXT_REQUEST_AT - now)
        if delay > 0.0:
            sleep(delay)
            now = monotonic()
        _PROVIDER_NEXT_REQUEST_AT = now + _PROVIDER_MIN_START_INTERVAL_SECONDS
    return delay * 1000.0


def _retryable_provider_error(error: Exception) -> bool:
    if isinstance(error, httpx.HTTPStatusError):
        return error.response.status_code in _RETRYABLE_STATUS_CODES
    return isinstance(error, httpx.TransportError)


class AdsbLolProvider:
    provider_id = "adsb-lol"
    label = "adsb.lol"
    source_kind = AircraftSourceKind.INTERNET
    api_base = "https://api.adsb.lol"
    max_attempts = _PROVIDER_MAX_ATTEMPTS

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
        user_agent: str = _DEFAULT_USER_AGENT,
    ) -> None:
        self._client = client
        self._timeout_seconds = timeout_seconds
        self._user_agent = user_agent
        self.last_timings: dict[str, float] = {}

    def _client_for_request(self) -> tuple[httpx.Client, bool]:
        if self._client is not None:
            return self._client, False
        if (
            self._timeout_seconds == _DEFAULT_TIMEOUT_SECONDS
            and self._user_agent == _DEFAULT_USER_AGENT
        ):
            return shared_adsb_http_client(), False
        return (
            httpx.Client(
                timeout=self._timeout_seconds,
                headers={"User-Agent": self._user_agent, "Accept": "application/json"},
                follow_redirects=True,
            ),
            True,
        )

    def fetch_snapshot(self, observer: AircraftObserver, radius_km: float) -> AircraftSnapshot:
        if not isfinite(radius_km) or radius_km <= 0:
            raise ValueError("radius_km must be a positive finite number")

        total_started = perf_counter()
        self.last_timings = {
            "provider_throttle_ms": 0.0,
            "provider_retry_wait_ms": 0.0,
            "provider_retry_count": 0.0,
        }
        radius_nm = max(1, min(250, round(radius_km / 1.852)))
        url = (
            f"{self.api_base}/v2/point/"
            f"{observer.latitude_deg:.6f}/{observer.longitude_deg:.6f}/{radius_nm}"
        )
        fetched_at = datetime.now(timezone.utc)

        client_started = perf_counter()
        client, owns_client = self._client_for_request()
        self.last_timings["provider_client_ms"] = (perf_counter() - client_started) * 1000.0
        failure: Exception | None = None
        payload: dict[str, Any] | None = None

        # Regional sharing reduces duplicates, while the process-wide gate and start
        # schedule ensure geographically separate cold regions still cannot burst any
        # aircraft provider. The primary provider gets one transient retry; secondary
        # failover intentionally uses one attempt so failover stays bounded.
        wait_started = perf_counter()
        _PROVIDER_REQUEST_GATE.acquire()
        self.last_timings["provider_wait_ms"] = (perf_counter() - wait_started) * 1000.0
        request_elapsed_ms = 0.0
        try:
            for attempt in range(self.max_attempts):
                self.last_timings["provider_throttle_ms"] += _wait_for_provider_start_slot()
                request_started = perf_counter()
                try:
                    response = client.get(url)
                    response.raise_for_status()
                    request_elapsed_ms += (perf_counter() - request_started) * 1000.0
                    failure = None
                    break
                except httpx.HTTPError as exc:
                    request_elapsed_ms += (perf_counter() - request_started) * 1000.0
                    failure = exc
                    if attempt + 1 >= self.max_attempts or not _retryable_provider_error(exc):
                        break
                    retry_started = perf_counter()
                    sleep(_PROVIDER_RETRY_DELAY_SECONDS)
                    self.last_timings["provider_retry_wait_ms"] += (
                        perf_counter() - retry_started
                    ) * 1000.0
                    self.last_timings["provider_retry_count"] += 1.0
        finally:
            self.last_timings["provider_request_ms"] = request_elapsed_ms
            _PROVIDER_REQUEST_GATE.release()

        if failure is None:
            decode_started = perf_counter()
            try:
                payload = response.json()
                self.last_timings["provider_decode_ms"] = (
                    perf_counter() - decode_started
                ) * 1000.0
            except ValueError as exc:
                failure = exc
                self.last_timings["provider_decode_ms"] = (
                    perf_counter() - decode_started
                ) * 1000.0
        else:
            self.last_timings["provider_decode_ms"] = 0.0

        close_started = perf_counter()
        if owns_client:
            client.close()
        self.last_timings["provider_close_ms"] = (perf_counter() - close_started) * 1000.0

        if failure is not None:
            self.last_timings["provider_normalize_ms"] = 0.0
            self.last_timings["provider_total_ms"] = (
                perf_counter() - total_started
            ) * 1000.0
            return AircraftSnapshot(
                observations=(),
                source_id=self.provider_id,
                source_label=self.label,
                fetched_at=fetched_at,
                source_observed_at=None,
                coverage_description=f"bounded observer area, {radius_nm} NM radius",
                state=AircraftSnapshotState.UNAVAILABLE,
                error=f"{self.label} unavailable: {failure}",
            )

        assert payload is not None
        normalize_started = perf_counter()
        source_time = _payload_time(payload, fallback=fetched_at)
        observations = tuple(
            observation
            for record in payload.get("ac", [])
            if isinstance(record, dict)
            if (
                observation := _normalise_record(
                    record,
                    source_time,
                    source_id=self.provider_id,
                    source_label=self.label,
                )
            )
            is not None
        )
        self.last_timings["provider_normalize_ms"] = (
            perf_counter() - normalize_started
        ) * 1000.0
        age_seconds = max(0.0, (fetched_at - source_time).total_seconds())
        snapshot = AircraftSnapshot(
            observations=observations,
            source_id=self.provider_id,
            source_label=self.label,
            fetched_at=fetched_at,
            source_observed_at=source_time,
            coverage_description=f"bounded observer area, {radius_nm} NM radius",
            state=classify_snapshot_age(age_seconds),
            error=None,
        )
        self.last_timings["provider_total_ms"] = (
            perf_counter() - total_started
        ) * 1000.0
        return snapshot


class AirplanesLiveProvider(AdsbLolProvider):
    """Secondary documented readsb-compatible provider used only after primary failure."""

    provider_id = "airplanes-live"
    label = "airplanes.live"
    api_base = "https://api.airplanes.live"
    max_attempts = 1


def _normalise_record(
    record: dict[str, Any],
    snapshot_time: datetime,
    *,
    source_id: str,
    source_label: str,
) -> AircraftObservation | None:
    icao24 = str(record.get("hex") or "").strip().lower()
    if not icao24:
        return None

    lat = _finite(record.get("lat"))
    lon = _finite(record.get("lon"))
    seen_pos = _nonnegative(record.get("seen_pos"))

    # Current readsb V2 schemas can supply a recent lastPosition object when an
    # aircraft record has no top-level lat/lon. Retain those useful contacts.
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
            source_id=source_id,
            source_label=source_label,
            source_kind=AircraftSourceKind.INTERNET,
            registration=str(record.get("r") or "").strip() or None,
            type_code=str(record.get("t") or "").strip() or None,
            type_description=str(record.get("desc") or "").strip() or None,
            operator=str(record.get("ownOp") or "").strip() or None,
            military=bool(db_flags & 1),
            category=str(record.get("category") or "").strip() or None,
            pia=bool(db_flags & 4),
            ladd=bool(db_flags & 8),
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
