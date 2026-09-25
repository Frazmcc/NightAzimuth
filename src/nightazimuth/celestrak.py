from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any

import httpx


CELESTRAK_GP_URL = "https://celestrak.org/NORAD/elements/gp.php"
_SAFE_GROUP_RE = re.compile(r"^[A-Z0-9_-]{1,64}$")


class CelestrakError(RuntimeError):
    """Raised when orbital data cannot be loaded from CelesTrak or cache."""


class CelestrakClient:
    def __init__(
        self,
        cache_directory: Path,
        cache_max_age_minutes: int = 120,
        timeout_seconds: float = 30.0,
    ) -> None:
        self.cache_directory = cache_directory
        self.cache_max_age_minutes = cache_max_age_minutes
        self.timeout_seconds = timeout_seconds

    def load_group(self, group: str) -> list[dict[str, Any]]:
        normalized_group = group.strip().upper()
        if not normalized_group:
            raise ValueError("CelesTrak group must not be empty")
        if not _SAFE_GROUP_RE.fullmatch(normalized_group):
            raise ValueError("CelesTrak group may contain only letters, numbers, hyphens, and underscores")

        cache_path = self._cache_path(normalized_group)
        if self._cache_is_fresh(cache_path):
            return self._read_cache(cache_path)

        try:
            data = self._download_group(normalized_group)
        except httpx.HTTPStatusError as exc:
            # CelesTrak deliberately returns 403 when its one-download-per-update
            # policy is triggered. Never retry automatically. If we have an older
            # successful cache, use it; otherwise stop and surface the server message.
            if cache_path.exists():
                return self._read_cache(cache_path)

            response_text = exc.response.text.strip()
            detail = response_text[:500] if response_text else str(exc)
            raise CelestrakError(
                f"CelesTrak returned HTTP {exc.response.status_code} for group "
                f"{normalized_group}. NightAzimuth will not retry automatically. "
                f"Server message: {detail}"
            ) from exc
        except (httpx.HTTPError, ValueError, json.JSONDecodeError) as exc:
            if cache_path.exists():
                return self._read_cache(cache_path)
            raise CelestrakError(
                f"Unable to load CelesTrak group {normalized_group}: {exc}"
            ) from exc

        self._write_cache(cache_path, data)
        return data

    def _download_group(self, group: str) -> list[dict[str, Any]]:
        response = httpx.get(
            CELESTRAK_GP_URL,
            params={"GROUP": group, "FORMAT": "JSON"},
            timeout=self.timeout_seconds,
            follow_redirects=True,
            headers={
                "User-Agent": "NightAzimuth/0.1 (+https://github.com/Frazmcc/NightAzimuth)",
                "Accept": "application/json",
            },
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise ValueError("CelesTrak returned an unexpected JSON structure")
        return payload

    def _cache_path(self, group: str) -> Path:
        filename = f"celestrak_{group.lower()}.json"
        return self.cache_directory.joinpath(filename)

    def _cache_is_fresh(self, path: Path) -> bool:
        if not path.exists():
            return False
        modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        age_seconds = (datetime.now(timezone.utc) - modified).total_seconds()
        return age_seconds <= self.cache_max_age_minutes * 60

    @staticmethod
    def _read_cache(path: Path) -> list[dict[str, Any]]:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, list):
            raise CelestrakError(f"Invalid orbital-data cache: {path}")
        return payload

    @staticmethod
    def _write_cache(path: Path, data: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(path.suffix + ".tmp")
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
        temp_path.replace(path)
