from __future__ import annotations

from dataclasses import dataclass
import hashlib
from io import BytesIO
from pathlib import Path
import time

import httpx
from PIL import Image

EUMETVIEW_WMS_URL = "https://view.eumetsat.int/geoserver/wms"
EUMETVIEW_LAYER = "mtg_fd:rgb_geocolour"
EUMETVIEW_USER_AGENT = "NightAzimuth/0.5 (+https://github.com/Frazmcc/NightAzimuth)"
CACHE_SECONDS = 15 * 60


class CloudImageryError(RuntimeError):
    """Raised when spatial cloud imagery cannot be obtained."""


@dataclass(frozen=True, slots=True)
class CloudImageSnapshot:
    image: Image.Image
    source_name: str
    layer_name: str
    from_cache: bool


class EumetViewCloudProvider:
    """Fetch free Meteosat GeoColour imagery through EUMETView WMS."""

    def __init__(self, *, cache_directory: Path, timeout_seconds: float = 30.0) -> None:
        self.cache_directory = Path(cache_directory) / "cloud_imagery"
        self.timeout_seconds = timeout_seconds

    def load_region(
        self,
        *,
        min_latitude: float,
        min_longitude: float,
        max_latitude: float,
        max_longitude: float,
        width: int,
        height: int,
    ) -> CloudImageSnapshot:
        if width <= 0 or height <= 0:
            raise ValueError("Cloud image dimensions must be positive")
        if min_latitude >= max_latitude or min_longitude >= max_longitude:
            raise ValueError("Cloud image bounding box is invalid")

        params = eumetview_getmap_params(
            min_latitude=min_latitude,
            min_longitude=min_longitude,
            max_latitude=max_latitude,
            max_longitude=max_longitude,
            width=width,
            height=height,
        )
        cache_path = self._cache_path(params)
        if _cache_is_fresh(cache_path):
            return CloudImageSnapshot(
                image=_open_image(cache_path),
                source_name="EUMETSAT EUMETView",
                layer_name=EUMETVIEW_LAYER,
                from_cache=True,
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
            _write_image(cache_path, image)
            return CloudImageSnapshot(
                image=image,
                source_name="EUMETSAT EUMETView",
                layer_name=EUMETVIEW_LAYER,
                from_cache=False,
            )
        except (httpx.HTTPError, OSError, ValueError) as exc:
            if cache_path.exists():
                return CloudImageSnapshot(
                    image=_open_image(cache_path),
                    source_name="EUMETSAT EUMETView",
                    layer_name=EUMETVIEW_LAYER,
                    from_cache=True,
                )
            raise CloudImageryError(f"EUMETView cloud imagery unavailable: {exc}") from exc

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
) -> dict[str, str]:
    """Build a WMS 1.3.0 GetMap request without embedding profile names."""
    return {
        "service": "WMS",
        "version": "1.3.0",
        "request": "GetMap",
        "layers": EUMETVIEW_LAYER,
        "styles": "",
        "crs": "EPSG:4326",
        # WMS 1.3.0 EPSG:4326 axis order is latitude,longitude.
        "bbox": f"{min_latitude:.5f},{min_longitude:.5f},{max_latitude:.5f},{max_longitude:.5f}",
        "width": str(width),
        "height": str(height),
        "format": "image/png",
        "transparent": "true",
    }


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
