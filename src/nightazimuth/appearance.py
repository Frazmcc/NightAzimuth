from __future__ import annotations

import json
import os
from pathlib import Path


APPEARANCE_MODES = ("System", "Light", "Dark")


def normalise_appearance_mode(value: object) -> str:
    """Return a supported appearance mode, defaulting safely to System."""

    candidate = str(value or "").strip().casefold()
    return {
        "system": "System",
        "light": "Light",
        "dark": "Dark",
    }.get(candidate, "System")


def system_uses_dark_mode() -> bool:
    """Read the current Windows application-theme preference when available."""

    if os.name != "nt":
        return False
    try:
        import winreg

        path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
            value, _kind = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return int(value) == 0
    except (OSError, TypeError, ValueError):
        return False


def appearance_uses_dark_mode(mode: object) -> bool:
    """Resolve Light, Dark, or the current operating-system preference."""

    normalised = normalise_appearance_mode(mode)
    if normalised == "Dark":
        return True
    if normalised == "Light":
        return False
    return system_uses_dark_mode()


class AppearancePreferenceStore:
    """Persist non-location UI preferences separately from observer profiles."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or self.default_path()

    @staticmethod
    def default_path() -> Path:
        base = Path(os.environ.get("APPDATA", Path.home()))
        return base / "NightAzimuth" / "preferences.json"

    def load(self) -> str:
        if not self.path.exists():
            return "System"
        try:
            with self.path.open("r", encoding="utf-8") as handle:
                raw = json.load(handle)
        except (OSError, json.JSONDecodeError, TypeError):
            return "System"
        return normalise_appearance_mode(raw.get("appearance"))

    def save(self, mode: object) -> str:
        selected = normalise_appearance_mode(mode)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(".tmp")
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump({"appearance": selected}, handle, indent=2)
        temp_path.replace(self.path)
        return selected
