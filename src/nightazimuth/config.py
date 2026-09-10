from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import tomllib


@dataclass(frozen=True, slots=True)
class ObserverConfig:
    latitude: float
    longitude: float
    altitude_m: float = 0.0


@dataclass(frozen=True, slots=True)
class TrackingConfig:
    minimum_elevation_deg: float = 0.0


@dataclass(frozen=True, slots=True)
class DataConfig:
    celestrak_group: str = "ACTIVE"
    cache_directory: Path = Path("data/cache")
    cache_max_age_minutes: int = 120


@dataclass(frozen=True, slots=True)
class AppConfig:
    observer: ObserverConfig
    tracking: TrackingConfig
    data: DataConfig


def load_config(path: str | Path) -> AppConfig:
    config_path = Path(path)
    with config_path.open("rb") as handle:
        raw = tomllib.load(handle)

    observer = raw.get("observer", {})
    tracking = raw.get("tracking", {})
    data = raw.get("data", {})

    return AppConfig(
        observer=ObserverConfig(
            latitude=float(observer["latitude"]),
            longitude=float(observer["longitude"]),
            altitude_m=float(observer.get("altitude_m", 0.0)),
        ),
        tracking=TrackingConfig(
            minimum_elevation_deg=float(tracking.get("minimum_elevation_deg", 0.0)),
        ),
        data=DataConfig(
            celestrak_group=str(data.get("celestrak_group", "ACTIVE")).upper(),
            cache_directory=Path(data.get("cache_directory", "data/cache")),
            cache_max_age_minutes=int(data.get("cache_max_age_minutes", 120)),
        ),
    )
