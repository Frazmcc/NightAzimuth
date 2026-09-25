from __future__ import annotations

import argparse
from pathlib import Path

from .celestrak import CelestrakClient
from .config import load_config
from .passes import PassPredictor
from .tracker import SatelliteTracker
from .visibility import VisibilityEngine


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="nightazimuth",
        description="Track satellites above the configured observer horizon.",
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
        help="Maximum number of current satellites to print (default: 25).",
    )
    parser.add_argument(
        "--visible-only",
        action="store_true",
        help="Only show satellites with favourable illumination and dark-sky geometry.",
    )
    parser.add_argument(
        "--passes",
        action="store_true",
        help="Also show upcoming passes within the configured prediction window.",
    )
    parser.add_argument(
        "--pass-limit",
        type=int,
        default=20,
        help="Maximum number of upcoming passes to print (default: 20).",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config_path = args.config.resolve(strict=True)
    config = load_config(config_path)

    client = CelestrakClient(
        cache_directory=config.data.cache_directory,
        cache_max_age_minutes=config.data.cache_max_age_minutes,
    )
    elements = client.load_group(config.data.celestrak_group)
    elements_by_norad = {
        str(item.get("NORAD_CAT_ID") or ""): item
        for item in elements
        if item.get("NORAD_CAT_ID") is not None
    }

    tracker = SatelliteTracker(config.observer)
    positions = tracker.positions_above_horizon(
        elements,
        minimum_elevation_deg=config.tracking.minimum_elevation_deg,
    )

    visibility = VisibilityEngine(
        config.observer,
        cache_directory=config.data.cache_directory,
        darkness_threshold_deg=config.tracking.darkness_threshold_deg,
    )

    # Exact observer coordinates are intentionally not written to stdout. They may
    # identify a private/home observing location and are not required for CLI results.
    print(f"Observer altitude: {config.observer.altitude_m:.0f} m")
    print(
        f"CelesTrak group: {config.data.celestrak_group} | "
        f"Above horizon: {len(positions)}"
    )
    print()
    print(
        f"{'Satellite':31} {'NORAD':>8} {'Az':>8} {'El':>8} {'Range':>9} "
        f"{'Sunlit':>7} {'Dark':>6} {'Potential':>10}"
    )
    print("-" * 101)

    shown = 0
    for item in positions:
        fields = elements_by_norad.get(item.norad_id)
        if fields is None:
            continue

        status = visibility.evaluate(fields)
        if args.visible_only and not status.potentially_visible:
            continue

        print(
            f"{item.name[:31]:31} {item.norad_id:>8} "
            f"{item.azimuth_deg:7.2f}° {item.elevation_deg:7.2f}° "
            f"{item.range_km:8.0f} "
            f"{('YES' if status.satellite_sunlit else 'NO'):>7} "
            f"{('YES' if status.sky_dark else 'NO'):>6} "
            f"{('YES' if status.potentially_visible else 'NO'):>10}"
        )
        shown += 1
        if shown >= max(args.limit, 0):
            break

    if args.passes:
        predictor = PassPredictor(config.observer)
        passes = predictor.predict(
            elements,
            hours=config.tracking.pass_prediction_hours,
            minimum_elevation_deg=config.tracking.pass_minimum_elevation_deg,
        )

        print()
        print(
            f"Upcoming passes: next {config.tracking.pass_prediction_hours:g} h, "
            f"minimum elevation {config.tracking.pass_minimum_elevation_deg:g}°"
        )
        print(
            f"{'Satellite':31} {'NORAD':>8} {'Rise UTC':>20} {'Peak UTC':>20} "
            f"{'Set UTC':>20} {'Max El':>8}"
        )
        print("-" * 116)

        for item in passes[: max(args.pass_limit, 0)]:
            print(
                f"{item.name[:31]:31} {item.norad_id:>8} "
                f"{item.rise_time:%Y-%m-%d %H:%M:%S} "
                f"{item.culmination_time:%Y-%m-%d %H:%M:%S} "
                f"{item.set_time:%Y-%m-%d %H:%M:%S} "
                f"{item.max_elevation_deg:7.2f}°"
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
