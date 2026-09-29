from __future__ import annotations

from pathlib import Path

from .celestrak import CelestrakClient, CelestrakError


SATELLITE_CACHE = Path("data/cache/api")
PRIMARY_GROUP = "ACTIVE"
SUPPLEMENTARY_GROUPS = ("LAST-30-DAYS", "STATIONS", "VISUAL")


def main() -> None:
    """Populate deploy-time CelesTrak caches before the API starts serving traffic."""

    cache_directory = SATELLITE_CACHE.resolve()
    cache_directory.mkdir(parents=True, exist_ok=True)
    client = CelestrakClient(cache_directory)

    primary = client.load_group(PRIMARY_GROUP)
    if not primary:
        raise CelestrakError("CelesTrak ACTIVE catalogue was empty during deployment preload")
    print(f"NightAzimuth satellite preload: group={PRIMARY_GROUP} objects={len(primary)}")

    loaded_groups = [PRIMARY_GROUP]
    unavailable_groups: list[str] = []
    for group in SUPPLEMENTARY_GROUPS:
        try:
            payload = client.load_group(group)
        except (CelestrakError, ValueError) as exc:
            unavailable_groups.append(group)
            print(
                "NightAzimuth satellite preload optional group unavailable: "
                f"group={group} error={exc}"
            )
            continue

        loaded_groups.append(group)
        print(f"NightAzimuth satellite preload: group={group} objects={len(payload)}")

    files = sorted(cache_directory.glob("celestrak_*.json"))
    total_bytes = sum(path.stat().st_size for path in files)
    print(
        "NightAzimuth satellite catalogues preloaded: "
        f"groups={','.join(loaded_groups)} "
        f"unavailable={','.join(unavailable_groups) or 'none'} "
        f"files={len(files)} bytes={total_bytes} cache={cache_directory}"
    )


if __name__ == "__main__":
    main()
