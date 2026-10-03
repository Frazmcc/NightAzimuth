from __future__ import annotations

from threading import Lock
from time import monotonic
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Query

router = APIRouter(prefix="/api/v1/aircraft", tags=["aircraft"])

_PLANESPOTTERS_API = "https://api.planespotters.net/pub/photos/hex/{icao24}"
_USER_AGENT = "NightAzimuth/1.0 (+https://github.com/Frazmcc/NightAzimuth)"
_CACHE_TTL_SECONDS = 3600.0
_CACHE_LOCK = Lock()
_CACHE: dict[tuple[str, str, str], tuple[float, dict[str, object]]] = {}


def _safe_https_url(value: object, *, planespotters_only: bool = True) -> str | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = urlparse(value)
    except ValueError:
        return None
    if parsed.scheme != "https" or not parsed.hostname:
        return None
    if planespotters_only and not (
        parsed.hostname == "planespotters.net"
        or parsed.hostname.endswith(".planespotters.net")
    ):
        return None
    return value


def _normalise_photo(payload: object) -> dict[str, object]:
    if not isinstance(payload, dict):
        return {"available": False}
    photos = payload.get("photos")
    if not isinstance(photos, list) or not photos:
        return {"available": False}
    first = photos[0]
    if not isinstance(first, dict):
        return {"available": False}
    thumbnail = first.get("thumbnail")
    image_url = _safe_https_url(
        thumbnail.get("src") if isinstance(thumbnail, dict) else None
    )
    link = _safe_https_url(first.get("link"))
    if image_url is None:
        return {"available": False}
    photographer = first.get("photographer")
    return {
        "available": True,
        "image_url": image_url,
        "link": link or "https://www.planespotters.net/",
        "photographer": str(photographer).strip() if photographer else None,
        "source": "Planespotters.net",
    }


def _fetch_photo(
    icao24: str,
    registration: str,
    type_code: str,
) -> dict[str, object]:
    params: dict[str, str] = {}
    if registration:
        params["reg"] = registration
    if type_code:
        params["icaoType"] = type_code
    try:
        response = httpx.get(
            _PLANESPOTTERS_API.format(icao24=icao24),
            params=params,
            headers={"User-Agent": _USER_AGENT, "Accept": "application/json"},
            timeout=6.0,
            follow_redirects=True,
        )
        response.raise_for_status()
        return _normalise_photo(response.json())
    except (httpx.HTTPError, ValueError):
        return {"available": False}


@router.get("/photo/{icao24}")
def aircraft_photo(
    icao24: str,
    registration: str = Query(default="", max_length=16),
    type_code: str = Query(default="", max_length=8),
) -> dict[str, object]:
    """Return a real photo for the exact aircraft when Planespotters has one."""

    normalised_hex = icao24.strip().lower()
    if len(normalised_hex) != 6 or any(ch not in "0123456789abcdef" for ch in normalised_hex):
        return {"available": False}

    reg = registration.strip().upper()
    kind = type_code.strip().upper()
    cache_key = (normalised_hex, reg, kind)
    now = monotonic()
    with _CACHE_LOCK:
        cached = _CACHE.get(cache_key)
        if cached is not None and now - cached[0] < _CACHE_TTL_SECONDS:
            return cached[1]

    result = _fetch_photo(normalised_hex, reg, kind)
    with _CACHE_LOCK:
        _CACHE[cache_key] = (now, result)
    return result
