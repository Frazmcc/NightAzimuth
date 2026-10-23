from __future__ import annotations

import hashlib
import os
import tempfile
import time
from pathlib import Path

import httpx

from .star_field import _load_static_resources


SKYFIELD_CACHE = Path("data/cache/api/skyfield")

# Immutable, upstream-verified input snapshots. Skyfield's default Hipparcos
# mirror has occasionally become unreachable during Render builds.
SKY_RESOURCES = (
    (
        "hip_main.dat",
        "https://raw.githubusercontent.com/skyfielders/python-skyfield/"
        "31a6ed7584cd09b6e48e07546a4b5921e1cd5bb4/ci/hip_main.dat",
        "a994a9f85efeacb50ccdd7203bbfeb3f9ae53f14",
    ),
    (
        "stellarium-modern-st-index.json",
        "https://raw.githubusercontent.com/Stellarium/stellarium/"
        "2b10b1a3bb534eb4e7586751054bf67b36c22e53/"
        "skycultures/modern_st/index.json",
        "3130f685e7e6ae303b31fce0a0371b54e8810d49",
    ),
    (
        "de421.bsp",
        "https://raw.githubusercontent.com/skyfielders/python-skyfield/"
        "31a6ed7584cd09b6e48e07546a4b5921e1cd5bb4/ci/de421.bsp",
        "ed5b5830e54bbc09cf3ba4ade3c729a279029f06",
    ),
)


def _git_blob_sha1(path: Path) -> str:
    """Verify fetched bytes against GitHub's immutable git-blob SHA-1."""
    digest = hashlib.sha1()  # noqa: S324 -- Git object identity, not a password
    digest.update(f"blob {path.stat().st_size}\\0".encode())
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _seed_resource(cache: Path, filename: str, url: str, expected_sha: str) -> None:
    destination = cache / filename
    if destination.is_file() and _git_blob_sha1(destination) == expected_sha:
        print(f"Sky resource verified in cache: {filename}", flush=True)
        return

    for attempt in range(1, 3):
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(dir=cache, delete=False) as output:
                temporary = Path(output.name)
                with httpx.stream(
                    "GET",
                    url,
                    follow_redirects=True,
                    timeout=httpx.Timeout(30.0, connect=10.0),
                ) as response:
                    response.raise_for_status()
                    for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                        output.write(chunk)

            if _git_blob_sha1(temporary) != expected_sha:
                raise RuntimeError(f"Unexpected SHA-1 for sky resource {filename}")
            os.replace(temporary, destination)
            print(f"Downloaded and verified sky resource: {filename}", flush=True)
            return
        except (httpx.HTTPError, OSError, RuntimeError) as exc:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
            if attempt == 2:
                raise RuntimeError(f"Could not preload sky resource {filename}") from exc
            print(f"Retrying sky resource {filename}: {exc}", flush=True)
            time.sleep(1)


def main() -> None:
    """Preload verified astronomical resources, with bounded downloads."""
    cache_directory = SKYFIELD_CACHE.resolve()
    cache_directory.mkdir(parents=True, exist_ok=True)
    for filename, url, expected_sha in SKY_RESOURCES:
        _seed_resource(cache_directory, filename, url, expected_sha)

    _load_static_resources(str(cache_directory))

    files = sorted(path for path in cache_directory.rglob("*") if path.is_file())
    total_bytes = sum(path.stat().st_size for path in files)
    print(
        "NightAzimuth sky resources preloaded: "
        f"files={len(files)} bytes={total_bytes} cache={cache_directory}",
        flush=True,
    )


if __name__ == "__main__":
    main()
