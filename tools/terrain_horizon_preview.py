from __future__ import annotations

import argparse
import os
from pathlib import Path

from PIL import Image, ImageDraw

from nightazimuth.location_profiles import LocationProfileStore
from nightazimuth.terrain_horizon import (
    MissingTerrainDataError,
    OfflineTerrariumElevationSource,
    calculate_horizon_profile,
)

WIDTH = 1800
HEIGHT = 520
LEFT = 70
RIGHT = 30
TOP = 35
BOTTOM = 65
MAX_ELEVATION_DEG = 60.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create an offline terrain-horizon preview.")
    parser.add_argument("--profile")
    parser.add_argument("--output", default="terrain_horizon_preview.png")
    parser.add_argument("--max-distance-km", type=float, default=80.0)
    parser.add_argument("--azimuth-step", type=float, default=1.0)
    parser.add_argument("--zoom", type=int, default=10)
    parser.add_argument("--observer-height-m", type=float, default=1.7)
    parser.add_argument("--terrain-directory", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    store = LocationProfileStore()
    profiles, selected = store.load()
    profile_name = args.profile or selected
    if not profile_name:
        raise SystemExit("No saved NightAzimuth location is selected.")

    profile = next((item for item in profiles if item.name == profile_name), None)
    if profile is None:
        raise SystemExit("The requested saved location profile was not found.")

    appdata = Path(os.environ.get("APPDATA", Path.home()))
    terrain_directory = args.terrain_directory or appdata / "NightAzimuth" / "terrain" / "terrarium"
    source = OfflineTerrariumElevationSource(terrain_directory, zoom=args.zoom)

    print("Creating terrain horizon from local terrain data only.")
    print("No terrain-related network request will be made.")

    try:
        horizon = calculate_horizon_profile(
            source,
            observer_latitude=profile.latitude,
            observer_longitude=profile.longitude,
            observer_altitude_m=profile.altitude_m,
            observer_height_m=args.observer_height_m,
            azimuth_step_deg=args.azimuth_step,
            max_distance_km=args.max_distance_km,
        )
    except MissingTerrainDataError as exc:
        raise SystemExit(str(exc)) from None

    output = Path(args.output).resolve()
    draw_preview(horizon, output)
    print(f"Preview created: {output}")
    return 0


def draw_preview(horizon: tuple, output: Path) -> None:
    image = Image.new("RGB", (WIDTH, HEIGHT), "#08111f")
    draw = ImageDraw.Draw(image)

    plot_left = LEFT
    plot_right = WIDTH - RIGHT
    plot_top = TOP
    plot_bottom = HEIGHT - BOTTOM
    plot_width = plot_right - plot_left
    plot_height = plot_bottom - plot_top

    for elevation in range(0, 61, 10):
        y = plot_bottom - (elevation / MAX_ELEVATION_DEG) * plot_height
        draw.line((plot_left, y, plot_right, y), fill="#334155", width=1)
        draw.text((8, y - 6), f"{elevation}°", fill="#94a3b8")

    for azimuth in range(0, 361, 30):
        x = plot_left + (azimuth / 360.0) * plot_width
        draw.line((x, plot_top, x, plot_bottom), fill="#1e293b", width=1)
        draw.text((x - 10, plot_bottom + 15), cardinal_label(azimuth), fill="#cbd5e1")

    skyline: list[tuple[float, float]] = []
    for point in horizon:
        x = plot_left + (point.azimuth_deg / 360.0) * plot_width
        elevation = max(0.0, min(MAX_ELEVATION_DEG, point.elevation_deg))
        y = plot_bottom - (elevation / MAX_ELEVATION_DEG) * plot_height
        skyline.append((x, y))

    if skyline:
        polygon = [(plot_left, plot_bottom), *skyline, (plot_right, plot_bottom)]
        draw.polygon(polygon, fill="#243447")
        draw.line(skyline, fill="#a3b18a", width=3)

    draw.rectangle((plot_left, plot_top, plot_right, plot_bottom), outline="#475569", width=2)
    draw.text((plot_left, 8), "NightAzimuth offline terrain-horizon preview", fill="#f8fafc")
    draw.text(
        (plot_left, HEIGHT - 30),
        "Terrain only: trees, buildings and other nearby obstructions are not included.",
        fill="#94a3b8",
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)


def cardinal_label(azimuth: int) -> str:
    names = {
        0: "N",
        30: "30°",
        60: "60°",
        90: "E",
        120: "120°",
        150: "150°",
        180: "S",
        210: "210°",
        240: "240°",
        270: "W",
        300: "300°",
        330: "330°",
        360: "N",
    }
    return names.get(azimuth, f"{azimuth}°")


if __name__ == "__main__":
    raise SystemExit(main())
