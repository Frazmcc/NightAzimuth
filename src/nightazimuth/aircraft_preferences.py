from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path

from .aircraft_providers import DEFAULT_LOCAL_READSB_URL, validate_local_receiver_url


AIRCRAFT_SOURCES = ("ADSB.lol (free internet)", "Local readsb/dump1090")


@dataclass(frozen=True, slots=True)
class AircraftPreferences:
    source: str = AIRCRAFT_SOURCES[0]
    local_receiver_url: str = DEFAULT_LOCAL_READSB_URL
    radius_nm: float = 40.0


class AircraftPreferenceStore:
    """Persist aircraft-source settings without storing aircraft positions."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or self.default_path()

    @staticmethod
    def default_path() -> Path:
        base = Path(os.environ.get("APPDATA", Path.home()))
        return base / "NightAzimuth" / "aircraft-preferences.json"

    def load(self) -> AircraftPreferences:
        if not self.path.exists():
            return AircraftPreferences()
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                raw = json.load(handle)
            source = str(raw.get("source") or "")
            if source not in AIRCRAFT_SOURCES:
                source = AIRCRAFT_SOURCES[0]
            url = validate_local_receiver_url(raw.get("local_receiver_url"))
            radius = float(raw.get("radius_nm", 40.0))
            if not 1.0 <= radius <= 250.0:
                radius = 40.0
            return AircraftPreferences(source=source, local_receiver_url=url, radius_nm=radius)
        except (OSError, ValueError, TypeError, json.JSONDecodeError):
            return AircraftPreferences()

    def save(self, preferences: AircraftPreferences) -> AircraftPreferences:
        if preferences.source not in AIRCRAFT_SOURCES:
            raise ValueError("Unsupported aircraft source.")
        validate_local_receiver_url(preferences.local_receiver_url)
        if not 1.0 <= preferences.radius_nm <= 250.0:
            raise ValueError("Aircraft search radius must be between 1 and 250 nautical miles.")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(".tmp")
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(asdict(preferences), handle, indent=2)
        temp_path.replace(self.path)
        return preferences
