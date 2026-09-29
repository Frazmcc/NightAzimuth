from __future__ import annotations

from pathlib import Path

from .star_field import _load_static_resources


SKYFIELD_CACHE = Path("data/cache/api/skyfield")


def main() -> None:
    """Download and validate immutable Skyfield resources during deployment build."""

    cache_directory = SKYFIELD_CACHE.resolve()
    cache_directory.mkdir(parents=True, exist_ok=True)
    _load_static_resources(str(cache_directory))

    files = sorted(path for path in cache_directory.rglob("*") if path.is_file())
    total_bytes = sum(path.stat().st_size for path in files)
    print(
        "NightAzimuth sky resources preloaded: "
        f"files={len(files)} bytes={total_bytes} cache={cache_directory}"
    )


if __name__ == "__main__":
    main()
