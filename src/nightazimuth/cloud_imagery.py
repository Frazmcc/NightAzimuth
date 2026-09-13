from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
from io import BytesIO
import json
import math
from pathlib import Path
import time
from xml.etree import ElementTree

import httpx
from PIL import Image

EUMETVIEW_WMS_URL = "https://view.eumetsat.int/geoserver/wms"
EUMETVIEW_LAYER = "mtg_fd:rgb_geocolour"
EUMETVIEW_USER_AGENT = "NightAzimuth/0.5 (+https://github.com/Frazmcc/NightAzimuth)"
CACHE_SECONDS = 15 * 60
CAPABILITIES_CACHE_SECONDS = 5 * 60
MAX_INTERVAL_FRAMES = 5000


class CloudImageryError(RuntimeError):
    """Raised when spatial cloud imagery cannot be obtained."""


@dataclass(frozen=True, slots=True)
class CloudImageSnapshot:
    image: Image.Image
    source_name: str
    layer_name: str
    from_cache: bool
    frame_time_utc: datetime | None
    fetched_at_utc: datetime


class EumetViewCloudProvider:
    """Fetch free Meteosat GeoColour imagery through EUMETView WMS."""

    def __init__(self, *, cache_directory: Path, timeout_seconds: float = 30.0) -> None:
        self.cache_directory = Path(cache_directory) / "cloud_imagery"
        self.timeout_seconds = timeout_seconds

    def recent_frame_times(self, *, limit: int = 8) -> tuple[datetime, ...]:
        """Return recent provider frame timestamps discovered from WMS capabilities."""
        times = self._available_frame_times()
        if limit <= 0:
            return ()
        return tuple(times[-limit:])

    def load_region(
        self,
        *,
        min_latitude: float,
        min_longitude: float,
        max_latitude: float,
        max_longitude: float,
        width: int,
        height: int,
        at_time_utc: datetime | None = None,
    ) -> CloudImageSnapshot:
        if width <= 0 or height <= 0:
            raise ValueError("Cloud image dimensions must be positive")
        if min_latitude >= max_latitude or min_longitude >= max_longitude:
            raise ValueError("Cloud image bounding box is invalid")

        frame_time = self._select_frame_time(at_time_utc)
        params = eumetview_getmap_params(
            min_latitude=min_latitude,
            min_longitude=min_longitude,
            max_latitude=max_latitude,
            max_longitude=max_longitude,
            width=width,
            height=height,
            frame_time_utc=frame_time,
        )
        cache_path = self._cache_path(params)
        if _cache_is_fresh(cache_path):
            return CloudImageSnapshot(
                image=_open_image(cache_path),
                source_name="EUMETSAT EUMETView",
                layer_name=EUMETVIEW_LAYER,
                from_cache=True,
                frame_time_utc=frame_time,
                fetched_at_utc=datetime.fromtimestamp(cache_path.stat().st_mtime, tz=timezone.utc),
            )

        try:
            response = httpx.get(
                EUMETVIEW_WMS_URL,
                params=params,
                headers={"User-Agent": EUMETVIEW_USER_AGENT},
                timeout=self.timeout_seconds,
                follow_redirects=True,
            )
            response.raise_for_status()
            image = Image.open(BytesIO(response.content)).convert("RGBA")
            fetched = datetime.now(timezone.utc)
            _write_image(cache_path, image)
            return CloudImageSnapshot(
                image=image,
                source_name="EUMETSAT EUMETView",
                layer_name=EUMETVIEW_LAYER,
                from_cache=False,
                frame_time_utc=frame_time,
                fetched_at_utc=fetched,
            )
        except (httpx.HTTPError, OSError, ValueError) as exc:
            if cache_path.exists():
                return CloudImageSnapshot(
                    image=_open_image(cache_path),
                    source_name="EUMETSAT EUMETView",
                    layer_name=EUMETVIEW_LAYER,
                    from_cache=True,
                    frame_time_utc=frame_time,
                    fetched_at_utc=datetime.fromtimestamp(cache_path.stat().st_mtime, tz=timezone.utc),
                )
            raise CloudImageryError(f"EUMETView cloud imagery unavailable: {exc}") from exc

    def _select_frame_time(self, requested: datetime | None) -> datetime | None:
        available = self._available_frame_times()
        if not available:
            return None
        if requested is None:
            return available[-1]
        target = requested.astimezone(timezone.utc)
        earlier = [value for value in available if value <= target]
        return earlier[-1] if earlier else available[0]

    def _available_frame_times(self) -> tuple[datetime, ...]:
        path = self.cache_directory / "capabilities_times.json"
        if path.exists() and time.time() - path.stat().st_mtime <= CAPABILITIES_CACHE_SECONDS:
            cached = _read_time_cache(path)
            if cached:
                return cached

        try:
            response = httpx.get(
                EUMETVIEW_WMS_URL,
                params={"service": "WMS", "version": "1.3.0", "request": "GetCapabilities"},
                headers={"User-Agent": EUMETVIEW_USER_AGENT},
                timeout=self.timeout_seconds,
                follow_redirects=True,
            )
            response.raise_for_status()
            times = parse_wms_layer_times(response.content, EUMETVIEW_LAYER)
            if times:
                _write_time_cache(path, times)
                return times
        except (httpx.HTTPError, OSError, ValueError, ElementTree.ParseError):
            pass

        if path.exists():
            return _read_time_cache(path)
        return ()

    def _cache_path(self, params: dict[str, str]) -> Path:
        key = "&".join(f"{name}={params[name]}" for name in sorted(params))
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()[:20]
        return self.cache_directory / f"eumetview_{digest}.png"


def eumetview_getmap_params(
    *,
    min_latitude: float,
    min_longitude: float,
    max_latitude: float,
    max_longitude: float,
    width: int,
    height: int,
    frame_time_utc: datetime | None = None,
) -> dict[str, str]:
    """Build a WMS 1.3.0 GetMap request without embedding profile names."""
    params = {
        "service": "WMS",
        "version": "1.3.0",
        "request": "GetMap",
        "layers": EUMETVIEW_LAYER,
        "styles": "",
        "crs": "CRS:84",
        "bbox": f"{min_longitude:.5f},{min_latitude:.5f},{max_longitude:.5f},{max_latitude:.5f}",
        "width": str(width),
        "height": str(height),
        "format": "image/png",
        "transparent": "true",
    }
    if frame_time_utc is not None:
        params["time"] = frame_time_utc.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return params


def parse_wms_layer_times(payload: bytes, layer_name: str) -> tuple[datetime, ...]:
    """Extract WMS time-dimension values for one named layer."""
    root = ElementTree.fromstring(payload)
    for layer in root.iter():
        if _local_name(layer.tag) != "Layer":
            continue
        name = next(
            (
                child.text.strip()
                for child in layer
                if _local_name(child.tag) == "Name" and child.text
            ),
            None,
        )
        if name != layer_name:
            continue
        for child in layer:
            if _local_name(child.tag) not in {"Dimension", "Extent"}:
                continue
            if child.attrib.get("name", "").lower() != "time" or not child.text:
                continue
            return _parse_time_dimension(child.text)
    return ()


def _parse_time_dimension(value: str) -> tuple[datetime, ...]:
    result: set[datetime] = set()
    for raw in value.replace("\n", "").split(","):
        token = raw.strip()
        if not token:
            continue
        if "/" in token:
            parts = token.split("/")
            if len(parts) == 3:
                start = _parse_iso_time(parts[0])
                end = _parse_iso_time(parts[1])
                step = _parse_iso_duration(parts[2])
                if start is not None and end is not None and step is not None and step.total_seconds() > 0:
                    span_seconds = max(0.0, (end - start).total_seconds())
                    step_seconds = step.total_seconds()
                    frame_count = int(math.floor(span_seconds / step_seconds)) + 1
                    first_index = max(0, frame_count - MAX_INTERVAL_FRAMES)
                    for index in range(first_index, frame_count):
                        current = start + step * index
                        if current <= end:
                            result.add(current)
            continue
        parsed = _parse_iso_time(token)
        if parsed is not None:
            result.add(parsed)
    return tuple(sorted(result))


def _parse_iso_time(value: str) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _parse_iso_duration(value: str) -> timedelta | None:
    token = value.strip().upper()
    if not token.startswith("PT"):
        return None
    token = token[2:]
    hours = minutes = seconds = 0.0
    number = ""
    for char in token:
        if char.isdigit() or char == ".":
            number += char
            continue
        if not number:
            return None
        amount = float(number)
        number = ""
        if char == "H":
            hours = amount
        elif char == "M":
            minutes = amount
        elif char == "S":
            seconds = amount
        else:
            return None
    return timedelta(hours=hours, minutes=minutes, seconds=seconds)


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _cache_is_fresh(path: Path) -> bool:
    return path.exists() and time.time() - path.stat().st_mtime <= CACHE_SECONDS


def _open_image(path: Path) -> Image.Image:
    with Image.open(path) as image:
        return image.convert("RGBA").copy()


def _write_image(path: Path, image: Image.Image) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp.png")
    image.save(temporary, format="PNG")
    temporary.replace(path)


def _write_time_cache(path: Path, values: tuple[datetime, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(
        json.dumps([value.isoformat() for value in values]),
        encoding="utf-8",
    )
    temporary.replace(path)


def _read_time_cache(path: Path) -> tuple[datetime, ...]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ()
    if not isinstance(raw, list):
        return ()
    values = [_parse_iso_time(str(item)) for item in raw]
    return tuple(value for value in values if value is not None)
