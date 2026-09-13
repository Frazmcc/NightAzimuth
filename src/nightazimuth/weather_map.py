from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import time
from typing import Any

import httpx
from PIL import Image, ImageDraw

from .config import ObserverConfig

OSM_TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
RAINVIEWER_MAPS_URL = "https://api.rainviewer.com/public/weather-maps.json"
MAP_USER_AGENT = "NightAzimuth/0.5 (+https://github.com/Frazmcc/NightAzimuth)"
TILE_SIZE = 256
OSM_CACHE_SECONDS = 7 * 24 * 60 * 60
RAINVIEWER_METADATA_CACHE_SECONDS = 5 * 60


class WeatherMapError(RuntimeError):
    """Raised when the weather map cannot be rendered."""


@dataclass(frozen=True, slots=True)
class WeatherMapSnapshot:
    image: Image.Image
    radar_time_utc: datetime | None
    radar_enabled: bool
    zoom: int


class WeatherMapRenderer:
    """Render a small OSM map with an optional RainViewer past-radar overlay."""

    def __init__(self, *, cache_directory: Path, timeout_seconds: float = 20.0) -> None:
        self.cache_directory = Path(cache_directory) / "weather_map"
        self.timeout_seconds = timeout_seconds

    def render(
        self,
        observer: ObserverConfig,
        *,
        show_radar: bool = True,
        zoom: int = 7,
        radius_tiles: int = 1,
    ) -> WeatherMapSnapshot:
        if not 0 <= zoom <= 19:
            raise ValueError("Map zoom must be between 0 and 19")
        if radius_tiles < 0 or radius_tiles > 2:
            raise ValueError("Map tile radius must be between 0 and 2")

        centre_x, centre_y = latlon_to_tile_fraction(observer.latitude, observer.longitude, zoom)
        centre_tile_x = math.floor(centre_x)
        centre_tile_y = math.floor(centre_y)
        start_x = centre_tile_x - radius_tiles
        start_y = centre_tile_y - radius_tiles
        tiles_across = radius_tiles * 2 + 1
        map_size = tiles_across * TILE_SIZE
        base = Image.new("RGB", (map_size, map_size), "#d9dde1")

        world_width = 1 << zoom
        for row in range(tiles_across):
            for column in range(tiles_across):
                tile_x = (start_x + column) % world_width
                tile_y = start_y + row
                if tile_y < 0 or tile_y >= world_width:
                    continue
                tile = self._load_osm_tile(zoom, tile_x, tile_y)
                base.paste(tile.convert("RGB"), (column * TILE_SIZE, row * TILE_SIZE))

        radar_time: datetime | None = None
        if show_radar:
            radar_frame = self._latest_radar_frame()
            if radar_frame is not None:
                host, frame_path, frame_time = radar_frame
                radar_time = datetime.fromtimestamp(frame_time, tz=timezone.utc)
                overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
                for row in range(tiles_across):
                    for column in range(tiles_across):
                        tile_x = (start_x + column) % world_width
                        tile_y = start_y + row
                        if tile_y < 0 or tile_y >= world_width:
                            continue
                        radar_tile = self._load_radar_tile(host, frame_path, frame_time, zoom, tile_x, tile_y)
                        overlay.alpha_composite(radar_tile.convert("RGBA"), (column * TILE_SIZE, row * TILE_SIZE))
                base = Image.alpha_composite(base.convert("RGBA"), overlay).convert("RGB")

        marker_x = (centre_x - start_x) * TILE_SIZE
        marker_y = (centre_y - start_y) * TILE_SIZE
        draw = ImageDraw.Draw(base)
        r = 8
        draw.ellipse((marker_x - r, marker_y - r, marker_x + r, marker_y + r), fill="white", outline="black", width=2)
        draw.line((marker_x - 12, marker_y, marker_x + 12, marker_y), fill="black", width=2)
        draw.line((marker_x, marker_y - 12, marker_x, marker_y + 12), fill="black", width=2)

        attribution = "© OpenStreetMap contributors"
        if show_radar:
            attribution += "  |  Radar: RainViewer"
        if radar_time is not None:
            attribution += f"  |  {radar_time.strftime('%H:%M UTC')}"
        text_box = draw.textbbox((0, 0), attribution)
        width = text_box[2] - text_box[0]
        height = text_box[3] - text_box[1]
        x = max(4, map_size - width - 8)
        y = map_size - height - 8
        draw.rectangle((x - 4, y - 2, x + width + 4, y + height + 2), fill="white")
        draw.text((x, y), attribution, fill="black")

        return WeatherMapSnapshot(image=base, radar_time_utc=radar_time, radar_enabled=show_radar, zoom=zoom)

    def _load_osm_tile(self, zoom: int, x: int, y: int) -> Image.Image:
        path = self.cache_directory / "osm" / str(zoom) / str(x) / f"{y}.png"
        if _cache_is_fresh(path, OSM_CACHE_SECONDS):
            return _open_image(path)
        try:
            response = httpx.get(
                OSM_TILE_URL.format(z=zoom, x=x, y=y),
                headers={"User-Agent": MAP_USER_AGENT},
                timeout=self.timeout_seconds,
                follow_redirects=True,
            )
            response.raise_for_status()
            _write_bytes(path, response.content)
            return _open_image(path)
        except (httpx.HTTPError, OSError) as exc:
            if path.exists():
                return _open_image(path)
            raise WeatherMapError(f"OpenStreetMap tile unavailable: {exc}") from exc

    def _latest_radar_frame(self) -> tuple[str, str, int] | None:
        path = self.cache_directory / "rainviewer" / "weather-maps.json"
        payload: dict[str, Any] | None = None
        if _cache_is_fresh(path, RAINVIEWER_METADATA_CACHE_SECONDS):
            payload = _read_json(path)
        else:
            try:
                response = httpx.get(
                    RAINVIEWER_MAPS_URL,
                    headers={"User-Agent": MAP_USER_AGENT, "Accept": "application/json"},
                    timeout=self.timeout_seconds,
                    follow_redirects=True,
                )
                response.raise_for_status()
                raw = response.json()
                if isinstance(raw, dict):
                    payload = raw
                    _write_json(path, raw)
            except (httpx.HTTPError, OSError, ValueError, json.JSONDecodeError):
                if path.exists():
                    payload = _read_json(path)

        if not payload:
            return None
        host = payload.get("host")
        radar = payload.get("radar")
        past = radar.get("past") if isinstance(radar, dict) else None
        if not isinstance(host, str) or not isinstance(past, list) or not past:
            return None
        frame = past[-1]
        if not isinstance(frame, dict):
            return None
        frame_path = frame.get("path")
        frame_time = frame.get("time")
        if not isinstance(frame_path, str) or not isinstance(frame_time, int):
            return None
        return host.rstrip("/"), frame_path, frame_time

    def _load_radar_tile(
        self,
        host: str,
        frame_path: str,
        frame_time: int,
        zoom: int,
        x: int,
        y: int,
    ) -> Image.Image:
        path = self.cache_directory / "rainviewer" / "tiles" / str(frame_time) / str(zoom) / str(x) / f"{y}.png"
        if path.exists():
            return _open_image(path)
        url = radar_tile_url(host, frame_path, zoom, x, y)
        try:
            response = httpx.get(
                url,
                headers={"User-Agent": MAP_USER_AGENT},
                timeout=self.timeout_seconds,
                follow_redirects=True,
            )
            response.raise_for_status()
            _write_bytes(path, response.content)
            return _open_image(path)
        except (httpx.HTTPError, OSError) as exc:
            if path.exists():
                return _open_image(path)
            raise WeatherMapError(f"RainViewer radar tile unavailable: {exc}") from exc


def latlon_to_tile_fraction(latitude: float, longitude: float, zoom: int) -> tuple[float, float]:
    """Convert WGS84 latitude/longitude into Web Mercator fractional tile coordinates."""
    latitude = max(-85.05112878, min(85.05112878, latitude))
    longitude = ((longitude + 180.0) % 360.0) - 180.0
    scale = float(1 << zoom)
    x = (longitude + 180.0) / 360.0 * scale
    latitude_rad = math.radians(latitude)
    y = (1.0 - math.asinh(math.tan(latitude_rad)) / math.pi) / 2.0 * scale
    return x, y


def radar_tile_url(host: str, frame_path: str, zoom: int, x: int, y: int) -> str:
    """Build the public RainViewer universal-blue radar tile URL."""
    return f"{host.rstrip('/')}{frame_path}/256/{zoom}/{x}/{y}/2/1_1.png"


def _cache_is_fresh(path: Path, maximum_age_seconds: int) -> bool:
    return path.exists() and time.time() - path.stat().st_mtime <= maximum_age_seconds


def _open_image(path: Path) -> Image.Image:
    with Image.open(path) as image:
        return image.copy()


def _write_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(content)
    temporary.replace(path)


def _read_json(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    return raw if isinstance(raw, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload), encoding="utf-8")
    temporary.replace(path)
