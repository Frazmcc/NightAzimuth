from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from urllib.parse import quote

import httpx


@dataclass(frozen=True, slots=True)
class SatelliteMetadata:
    norad_id: str
    name: str
    international_designator: str | None = None
    object_type: str | None = None
    operational_status: str | None = None
    owner_code: str | None = None
    launch_date: str | None = None
    launch_site: str | None = None
    decay_date: str | None = None
    period_minutes: float | None = None
    inclination_deg: float | None = None
    apogee_km: float | None = None
    perigee_km: float | None = None
    radar_cross_section_m2: float | None = None
    orbit_center: str | None = None
    orbit_type: str | None = None
    purpose: str | None = None
    technical_notes: str | None = None
    image_url: str | None = None
    information_url: str | None = None
    information_source: str | None = None


@dataclass(frozen=True, slots=True)
class _CachedMetadata:
    value: SatelliteMetadata
    expires_at: datetime


class SatelliteMetadataProvider:
    """Fail-soft public metadata enrichment for a selected satellite."""

    SATCAT_URL = "https://celestrak.org/satcat/records.php"
    WIKI_SEARCH_URL = "https://en.wikipedia.org/w/rest.php/v1/search/page"
    WIKI_SUMMARY_URL = "https://en.wikipedia.org/api/rest_v1/page/summary"

    def __init__(
        self,
        *,
        client: httpx.Client | None = None,
        timeout_seconds: float = 5.0,
        cache_hours: float = 12.0,
    ) -> None:
        self._client = client
        self._timeout_seconds = timeout_seconds
        self._cache_age = timedelta(hours=max(1.0, cache_hours))
        self._cache: dict[str, _CachedMetadata] = {}
        self._lock = Lock()

    def lookup(self, norad_id: str, fallback_name: str) -> SatelliteMetadata:
        key = str(norad_id).strip()
        now = datetime.now(timezone.utc)
        with self._lock:
            cached = self._cache.get(key)
            if cached is not None and cached.expires_at > now:
                return cached.value

        satcat = self._fetch_satcat(key)
        canonical_name = _text(satcat.get("OBJECT_NAME")) or fallback_name.strip() or f"NORAD {key}"
        wiki = self._fetch_wikipedia(canonical_name, key)
        metadata = SatelliteMetadata(
            norad_id=key,
            name=canonical_name,
            international_designator=_text(satcat.get("OBJECT_ID")),
            object_type=_text(satcat.get("OBJECT_TYPE")),
            operational_status=_text(satcat.get("OPS_STATUS_CODE")),
            owner_code=_text(satcat.get("OWNER")),
            launch_date=_text(satcat.get("LAUNCH_DATE")),
            launch_site=_text(satcat.get("LAUNCH_SITE")),
            decay_date=_text(satcat.get("DECAY_DATE")),
            period_minutes=_number(satcat.get("PERIOD")),
            inclination_deg=_number(satcat.get("INCLINATION")),
            apogee_km=_number(satcat.get("APOGEE")),
            perigee_km=_number(satcat.get("PERIGEE")),
            radar_cross_section_m2=_number(satcat.get("RCS")),
            orbit_center=_text(satcat.get("ORBIT_CENTER")),
            orbit_type=_text(satcat.get("ORBIT_TYPE")),
            purpose=wiki.get("description"),
            technical_notes=wiki.get("extract"),
            image_url=wiki.get("image_url"),
            information_url=wiki.get("page_url"),
            information_source="CelesTrak SATCAT + Wikipedia" if wiki else "CelesTrak SATCAT",
        )
        with self._lock:
            self._cache[key] = _CachedMetadata(metadata, now + self._cache_age)
        return metadata

    def fetch_image(self, url: str | None) -> bytes | None:
        if not url:
            return None
        owns_client = self._client is None
        client = self._client or httpx.Client(
            timeout=self._timeout_seconds,
            headers={"User-Agent": "NightAzimuth/1.0 satellite-info"},
            follow_redirects=True,
        )
        try:
            response = client.get(url)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").lower()
            if not content_type.startswith("image/"):
                return None
            return bytes(response.content)
        except httpx.HTTPError:
            return None
        finally:
            if owns_client:
                client.close()

    def _fetch_satcat(self, norad_id: str) -> dict[str, object]:
        owns_client = self._client is None
        client = self._client or httpx.Client(
            timeout=self._timeout_seconds,
            headers={"User-Agent": "NightAzimuth/1.0 satellite-info", "Accept": "application/json"},
            follow_redirects=True,
        )
        try:
            response = client.get(self.SATCAT_URL, params={"CATNR": norad_id, "FORMAT": "JSON"})
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, list) and payload and isinstance(payload[0], dict):
                return payload[0]
        except (httpx.HTTPError, ValueError):
            pass
        finally:
            if owns_client:
                client.close()
        return {}

    def _fetch_wikipedia(self, name: str, norad_id: str) -> dict[str, str]:
        owns_client = self._client is None
        client = self._client or httpx.Client(
            timeout=self._timeout_seconds,
            headers={"User-Agent": "NightAzimuth/1.0 satellite-info"},
            follow_redirects=True,
        )
        try:
            search = client.get(
                self.WIKI_SEARCH_URL,
                params={"q": f'"{name}" satellite {norad_id}', "limit": 3},
            )
            search.raise_for_status()
            payload = search.json()
            pages = payload.get("pages") if isinstance(payload, dict) else None
            if not isinstance(pages, list) or not pages:
                return {}
            title = _best_wiki_title(pages, name)
            if not title:
                return {}
            summary = client.get(f"{self.WIKI_SUMMARY_URL}/{quote(title, safe='')}")
            summary.raise_for_status()
            data = summary.json()
            if not isinstance(data, dict):
                return {}
            extract = _text(data.get("extract"))
            if extract and len(extract) > 900:
                extract = extract[:897].rsplit(" ", 1)[0] + "..."
            thumbnail = data.get("thumbnail")
            original = data.get("originalimage")
            image_url = None
            if isinstance(original, dict):
                image_url = _text(original.get("source"))
            if image_url is None and isinstance(thumbnail, dict):
                image_url = _text(thumbnail.get("source"))
            content_urls = data.get("content_urls")
            page_url = None
            if isinstance(content_urls, dict):
                desktop = content_urls.get("desktop")
                if isinstance(desktop, dict):
                    page_url = _text(desktop.get("page"))
            return {
                key: value
                for key, value in {
                    "description": _text(data.get("description")),
                    "extract": extract,
                    "image_url": image_url,
                    "page_url": page_url,
                }.items()
                if value
            }
        except (httpx.HTTPError, ValueError):
            return {}
        finally:
            if owns_client:
                client.close()


def _best_wiki_title(pages: list[object], name: str) -> str | None:
    wanted = _normalise_name(name)
    scored: list[tuple[int, str]] = []
    for page in pages:
        if not isinstance(page, dict):
            continue
        title = _text(page.get("title"))
        if not title:
            continue
        normal = _normalise_name(title)
        score = 0
        if normal == wanted:
            score += 10
        if wanted and wanted in normal:
            score += 5
        description = (_text(page.get("description")) or "").lower()
        excerpt = (_text(page.get("excerpt")) or "").lower()
        if any(term in description or term in excerpt for term in ("satellite", "spacecraft", "space station", "orbiter")):
            score += 4
        scored.append((score, title))
    if not scored:
        return None
    score, title = max(scored, key=lambda item: item[0])
    return title if score >= 4 else None


def _normalise_name(value: str) -> str:
    return "".join(character.lower() for character in value if character.isalnum())


def _text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _number(value: object) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
