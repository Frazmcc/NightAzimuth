from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timezone
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
# Public callers can choose a valid group string, so use a bounded set of lock
# stripes instead of an ever-growing lock dictionary keyed by request input.
_CACHE_LOCKS = tuple(threading.RLock() for _ in range(16))

# Keep only the newest parsed payload for each cache file.  The previous
# functools.lru_cache key included file mtime/size, which meant every CelesTrak
# refresh retained another complete parsed ACTIVE catalogue until the 32-entry
# LRU eventually evicted it.  ACTIVE is large enough for those stale generations
# to exhaust a 512 MB hosted instance over time.
_PARSED_CACHE_MAX_ENTRIES = 8
_PARSED_CACHE_LOCK = threading.RLock()
_PARSED_CACHE: OrderedDict[
    str, tuple[int, int, list[dict[str, Any]]]
] = OrderedDict()
CatalogueGeneration = tuple[int, int]


def _cache_lock(path: Path) -> threading.RLock:
    return _CACHE_LOCKS[hash(path.resolve()) % len(_CACHE_LOCKS)]


def _remember_cached_json(
    path_string: str,
    modified_ns: int,
    size: int,
    payload: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    with _PARSED_CACHE_LOCK:
        # Assignment by pathname replaces the previous generation immediately,
        # so an updated ACTIVE file cannot leave its old parsed list resident.
        _PARSED_CACHE[path_string] = (modified_ns, size, payload)
        _PARSED_CACHE.move_to_end(path_string)
        while len(_PARSED_CACHE) > _PARSED_CACHE_MAX_ENTRIES:
            _PARSED_CACHE.popitem(last=False)
    return payload


def _read_cached_json(
    path_string: str,
    modified_ns: int,
    size: int,
) -> list[dict[str, Any]]:
    with _PARSED_CACHE_LOCK:
        cached = _PARSED_CACHE.get(path_string)
        if cached is not None and cached[0] == modified_ns and cached[1] == size:
            _PARSED_CACHE.move_to_end(path_string)
            return cached[2]

    path = Path(path_string)
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, list):
        raise CelestrakError(f"Invalid orbital-data cache: {path}")
    return _remember_cached_json(path_string, modified_ns, size, payload)


def _clear_parsed_cache() -> None:
    """Clear the in-process parsed catalogue cache (primarily for tests)."""
    with _PARSED_CACHE_LOCK:
        _PARSED_CACHE.clear()


def _parsed_cache_entry_count() -> int:
    with _PARSED_CACHE_LOCK:
        return len(_PARSED_CACHE)


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
        payload, _generation = self.load_group_versioned(group)
        return payload

    def load_group_versioned(
        self,
        group: str,
    ) -> tuple[list[dict[str, Any]], CatalogueGeneration]:
        """Load one group together with the exact on-disk cache generation used."""

        normalized_group = group.strip().upper()
        if not normalized_group:
            raise ValueError("CelesTrak group must not be empty")
        if not _SAFE_GROUP_RE.fullmatch(normalized_group):
            raise ValueError("CelesTrak group may contain only letters, numbers, hyphens, and underscores")

        cache_path = self._cache_path(normalized_group)
        # A stale/missing group can be requested by several public API calls at
        # once. Serialize work for a cache stripe so duplicate downloads/writes
        # cannot race; the fixed stripes keep lock memory bounded. Returning the
        # generation while this same lock is held guarantees that the token
        # describes the exact payload returned to the caller.
        with _cache_lock(cache_path):
            if self._cache_is_fresh(cache_path):
                data = self._read_cache(cache_path)
                return data, self._cache_generation(cache_path)

            try:
                data = self._download_group(normalized_group)
            except httpx.HTTPStatusError as exc:
                # CelesTrak deliberately returns 403 when its one-download-per-update
                # policy is triggered. Never retry automatically. If we have an older
                # successful cache, use it; otherwise stop and surface the server message.
                if cache_path.exists():
                    data = self._read_cache(cache_path)
                    return data, self._cache_generation(cache_path)
                mirror_data = self._download_mirror(normalized_group)
                if mirror_data is not None:
                    self._write_cache(cache_path, mirror_data)
                    return mirror_data, self._cache_generation(cache_path)

                response_text = exc.response.text.strip()
                detail = response_text[:500] if response_text else str(exc)
                raise CelestrakError(
                    f"CelesTrak returned HTTP {exc.response.status_code} for group "
                    f"{normalized_group}. NightAzimuth will not retry automatically. "
                    f"Server message: {detail}"
                ) from exc
            except (httpx.HTTPError, ValueError, json.JSONDecodeError) as exc:
                if cache_path.exists():
                    data = self._read_cache(cache_path)
                    return data, self._cache_generation(cache_path)
                mirror_data = self._download_mirror(normalized_group)
                if mirror_data is not None:
                    self._write_cache(cache_path, mirror_data)
                    return mirror_data, self._cache_generation(cache_path)
                raise CelestrakError(
                    f"Unable to load CelesTrak group {normalized_group}: {exc}"
                ) from exc

            self._write_cache(cache_path, data)
            return data, self._cache_generation(cache_path)

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
    def _cache_generation(path: Path) -> CatalogueGeneration:
        stat = path.stat()
        return stat.st_mtime_ns, stat.st_size

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
            stat = path.stat()
            # The downloaded list is already parsed. Store that exact object as
            # the newest generation and release any previous one immediately.
            _remember_cached_json(
                str(path.resolve()),
                stat.st_mtime_ns,
                stat.st_size,
                data,
            )
        finally:
            if temp_path is not None:
                temp_path.unlink(missing_ok=True)
