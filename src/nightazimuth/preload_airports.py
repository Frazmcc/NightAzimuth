from __future__ import annotations

from pathlib import Path

from .stage20_rc_airports import ResilientAirportLandmarkProvider


AIRPORT_CACHE = Path("data/cache/api")


def main() -> None:
    """Populate the deploy-time global airport catalogue cache."""

    cache_directory = AIRPORT_CACHE.resolve()
    cache_directory.mkdir(parents=True, exist_ok=True)
    provider = ResilientAirportLandmarkProvider(
        timeout_seconds=20.0,
        cache_directory=cache_directory,
    )
    count = provider.preload()
    if count <= 0:
        raise RuntimeError("Airport catalogue was empty during deployment preload")

    cache_path = cache_directory / "airports" / "ourairports.csv"
    size = cache_path.stat().st_size if cache_path.exists() else 0
    print(
        "NightAzimuth airport catalogue preloaded: "
        f"objects={count} bytes={size} cache={cache_path}"
    )


if __name__ == "__main__":
    main()
