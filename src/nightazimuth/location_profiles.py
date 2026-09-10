from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
import os


@dataclass(frozen=True, slots=True)
class LocationProfile:
    name: str
    latitude: float
    longitude: float
    altitude_m: float = 0.0


class LocationProfileStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or self.default_path()

    @staticmethod
    def default_path() -> Path:
        base = Path(os.environ.get("APPDATA", Path.home()))
        return base / "NightAzimuth" / "locations.json"

    def load(self) -> tuple[list[LocationProfile], str | None]:
        if not self.path.exists():
            return [], None

        with self.path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)

        profiles = [
            LocationProfile(
                name=str(item["name"]),
                latitude=float(item["latitude"]),
                longitude=float(item["longitude"]),
                altitude_m=float(item.get("altitude_m", 0.0)),
            )
            for item in raw.get("profiles", [])
        ]
        selected = raw.get("selected")
        return profiles, str(selected) if selected else None

    def save(self, profiles: list[LocationProfile], selected: str | None) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "selected": selected,
            "profiles": [asdict(profile) for profile in profiles],
        }
        temp_path = self.path.with_suffix(".tmp")
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        temp_path.replace(self.path)
