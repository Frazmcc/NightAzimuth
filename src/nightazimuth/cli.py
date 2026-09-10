from __future__ import annotations

import argparse
from pathlib import Path

from .celestrak import CelestrakClient
from .config import load_config
from .tracker import SatelliteTracker


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nightazimuth",
        description="List satellites currently above the configured observer horizon.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Path to a NightAzimuth TOML configuration file.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=25,
        help="Maximum number of satellites to print (default: 25).",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config = load_config(args.config)

    client = CelestrakClient(
        cache_directory=config.data.cache_directory,
        cache_max_age_minutes=config.data.cache_max_age_minutes,
    )
    elements = client.load_group(config.data.celestrak_group)

    tracker = SatelliteTracker(config.observer)
    positions = tracker.positions_above_horizon(
        elements,
        minimum_elevation_deg=config.tracking.minimum_elevation_deg,
    )

    print(
        f"Observer: {config.observer.latitude:.5f}, {config.observer.longitude:.5f} "
        f"({config.observer.altitude_m:.0f} m)"
    )
    print(
        f"CelesTrak group: {config.data.celestrak_group} | "
        f"Above horizon: {len(positions)}"
    )
    print()
    print(f"{'Satellite':36} {'NORAD':>8} {'Azimuth':>10} {'Elevation':>11} {'Range km':>10}")
    print("-" * 81)

    for item in positions[: max(args.limit, 0)]:
        print(
            f"{item.name[:36]:36} {item.norad_id:>8} "
            f"{item.azimuth_deg:9.2f}° {item.elevation_deg:10.2f}° {item.range_km:10.0f}"
        )

    return 0
