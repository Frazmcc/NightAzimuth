from __future__ import annotations

from datetime import datetime, timezone
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
import tempfile
import threading
from typing import Any

import httpx


CELESTRAK_GP_URL = "https://celestrak.org/NORAD/elements/gp.php"
SATVISOR_MIRROR_URL = "https://raw.githubusercontent.com/satvisorcom/satvisor-data/master/celestrak/json/{group}.json"
_SAFE_GROUP_RE = re.compile(r"^[A-Z0-9_-]{1,64}$")
_CACHE_LOCKS_GUARD = threading.Lock()
_CACHE_LOCKS: dict[str, threading.RLock] = {}


def _cache_lock(path: Path) -> threading.RLock:
    key = str(path.resolve())
    with _CACHE_LOCKS_GUARD:
        return _CACHE_LOCKS.setdefault(key, threading.RLock())


@lru_cache(maxsize=32)
def _read_cached_json(path_string: str, modified_ns: int, size: int) -> list[dict[str, Any]]:
    # modified_ns and size are intentionally part of the key so replacing a
    # cache file automatically invalidates the parsed in-process entry.
    del modified_ns, size
    path = Path(path_string)
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise CelestrakError(f"Invalid orbital-data cache: {path}")
    return payload


class CelestrakError(RuntimeError):
    """Raised when orbital data cannot be loaded from CelesTrak or cache."""


class CelestrakClient:
    def __init__(
        self,
        cache_directory: Path,
        cache_max_age_minutes: int = 125,
        timeout_seconds: float = 10.0,
    ) -> None:
        self.cache_directory = cache_directory.resolve()
        self.cache_max_age_minutes = cache_max_age_minutes
        self.timeout_seconds = timeout_seconds

    def load_group(self, group: str) -> list[dict[str, Any]]:
        normalized_group = group.strip().upper()
        if not normalized_group:
            raise ValueError("CelesTrak group must not be empty")
        if not _SAFE_GROUP_RE.fullmatch(normalized_group):
            raise ValueError("CelesTrak group may contain only letters, numbers, hyphens, and underscores")

        cache_path = self._cache_path(normalized_group)
        # A stale/missing group can be requested by several public API calls at
        # once. Serialize work per group so only one request downloads/writes it;
        # different groups can still load concurrently in api_satellites.
        with _cache_lock(cache_path):
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
                mirror_data = self._download_mirror(normalized_group)
                if mirror_data is not None:
                    self._write_cache(cache_path, mirror_data)
                    return mirror_data

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
                mirror_data = self._download_mirror(normalized_group)
                if mirror_data is not None:
                    self._write_cache(cache_path, mirror_data)
                    return mirror_data
                raise CelestrakError(
                    f"Unable to load CelesTrak group {normalized_group}: {exc}"
                ) from exc

            self._write_cache(cache_path, data)
            return data

    def _download_mirror(self, group: str) -> list[dict[str, Any]] | None:
        try:
            response = httpx.get(
                SATVISOR_MIRROR_URL.format(group=group.lower()),
                timeout=self.timeout_seconds,
                follow_redirects=True,
                headers={
                    "User-Agent": "NightAzimuth/0.1 (+https://github.com/Frazmcc/NightAzimuth)",
                    "Accept": "application/json",
                },
            )
            response.raise_for_status()
            payload = response.json()
            return payload if isinstance(payload, list) else None
        except (httpx.HTTPError, ValueError, json.JSONDecodeError):
            return None

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
        # Keep every cache file beneath the configured cache root even if this
        # helper is called directly. load_group() also validates provider group
        # names, but the path boundary is enforced here at the filesystem sink.
        if not _SAFE_GROUP_RE.fullmatch(group):
            raise ValueError(
                "CelesTrak group may contain only letters, numbers, hyphens, and underscores"
            )
        # Convert the validated provider identifier to a fixed digest before it
        # reaches pathlib. No caller-controlled characters are used in the path.
        cache_key = hashlib.sha256(group.encode("ascii")).hexdigest()
        filename = f"celestrak_{cache_key}.json"
        candidate = (self.cache_directory / filename).resolve()
        if not candidate.is_relative_to(self.cache_directory):
            raise ValueError("CelesTrak cache path escapes the configured cache directory")
        return candidate

    def _cache_is_fresh(self, path: Path) -> bool:
        if not path.exists():
            return False
        modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        age_seconds = (datetime.now(timezone.utc) - modified).total_seconds()
        return age_seconds <= self.cache_max_age_minutes * 60

    @staticmethod
    def _read_cache(path: Path) -> list[dict[str, Any]]:
        stat = path.stat()
        return _read_cached_json(str(path.resolve()), stat.st_mtime_ns, stat.st_size)

    @staticmethod
    def _write_cache(path: Path, data: list[dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                dir=path.parent,
                prefix=f"{path.name}.",
                suffix=".tmp",
                delete=False,
            ) as handle:
                temp_path = Path(handle.name)
                json.dump(data, handle, separators=(",", ":"))
            temp_path.replace(path)
            temp_path = None
            _read_cached_json.cache_clear()
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
