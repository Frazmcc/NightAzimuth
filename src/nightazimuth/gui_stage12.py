from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import threading
import tkinter as tk
from tkinter import filedialog, ttk

from .gui import SettingsWindow
from .gui_stage7 import Stage7NightAzimuthApp
from .terrain_horizon import (
    CachedTerrariumElevationSource,
    TerrainDownloadError,
    TerrainPackError,
    calculate_horizon_profile,
    import_terrarium_pack,
)
from .terrain_star_live_view import TerrainStarLiveSkyView


@dataclass(frozen=True, slots=True)
class VerticalSkyWindow:
    sky_angle_deg: float
    facing_deg: float
    minimum_elevation_deg: float
    maximum_elevation_deg: float


def vertical_sky_window(
    sky_angle_deg: float,
    *,
    base_facing_deg: float,
    elevation_span_deg: float = 60.0,
) -> VerticalSkyWindow:
    """Map a 0..180 vertical sky sweep onto a valid astronomical elevation window.

    0° is the horizon in the selected facing direction, 90° is the zenith, and
    180° is the opposite horizon. Astronomical elevation itself remains 0..90°;
    after passing the zenith the rendered facing direction is rotated by 180°.
    """
    angle = max(0.0, min(180.0, float(sky_angle_deg)))
    span = max(5.0, min(90.0, float(elevation_span_deg)))
    target_elevation = angle if angle <= 90.0 else 180.0 - angle
    facing = base_facing_deg % 360.0 if angle <= 90.0 else (base_facing_deg + 180.0) % 360.0

    minimum = target_elevation - span / 2.0
    maximum = minimum + span
    if minimum < 0.0:
        maximum -= minimum
        minimum = 0.0
    if maximum > 90.0:
        minimum -= maximum - 90.0
        maximum = 90.0
    minimum = max(0.0, minimum)
    maximum = min(90.0, maximum)

    return VerticalSkyWindow(angle, facing, minimum, maximum)


class Stage12SettingsWindow(SettingsWindow):
    def __init__(self, app: Stage12NightAzimuthApp) -> None:
        super().__init__(app)
        self.geometry("620x500")

    def _build_ui(self) -> None:
        super()._build_ui()
        terrain = ttk.LabelFrame(self, text="Terrain horizon", padding=10)
        terrain.pack(fill="x", padx=16, pady=(0, 14))
        ttk.Label(
            terrain,
            text="Terrain is generated automatically after a location is entered. Downloaded terrain is cached locally.",
            wraplength=560,
            justify="left",
        ).pack(anchor="w")
        self.terrain_import_status = ttk.Label(
            terrain,
            text="You can also import a local Terrarium terrain pack.",
            wraplength=560,
            justify="left",
        )
        self.terrain_import_status.pack(anchor="w", pady=(6, 6))
        self.terrain_import_button = ttk.Button(
            terrain,
            text="Import offline terrain pack...",
            command=self._choose_terrain_pack,
        )
        self.terrain_import_button.pack(anchor="w")

    def _choose_terrain_pack(self) -> None:
        selected = filedialog.askdirectory(parent=self, title="Select offline Terrarium terrain-pack folder")
        if not selected:
            return
        source = Path(selected)
        destination = self.app.terrain_directory
        self.terrain_import_button.config(state="disabled")
        self.terrain_import_status.config(text="Importing local terrain pack...")
        threading.Thread(target=self._import_terrain_pack, args=(source, destination), daemon=True).start()

    def _import_terrain_pack(self, source: Path, destination: Path) -> None:
        try:
            summary = import_terrarium_pack(source, destination)
        except (TerrainPackError, OSError, ValueError):
            self.after(0, self._terrain_import_failed)
            return
        self.after(0, self._terrain_import_complete, summary.tile_count, summary.zoom_levels)

    def _terrain_import_failed(self) -> None:
        self.terrain_import_button.config(state="normal")
        self.terrain_import_status.config(text="Import failed. Select a valid local Terrarium tile folder.")

    def _terrain_import_complete(self, tile_count: int, zoom_levels: tuple[int, ...]) -> None:
        self.terrain_import_button.config(state="normal")
        zoom_text = ", ".join(str(level) for level in zoom_levels)
        self.terrain_import_status.config(
            text=f"Imported {tile_count} terrain tiles. Available zoom levels: {zoom_text}."
        )
        self.app._terrain_cache_changed()


class Stage12NightAzimuthApp(Stage7NightAzimuthApp):
    TERRAIN_ZOOM = 10

    def __init__(self) -> None:
        self._terrain_load_in_progress = False
        self._pending_terrain_profile: str | None = None
        self._terrain_location_key: tuple[str, float, float, float] | None = None
        self._terrain_horizon: tuple = ()
        self._vertical_sky_angle_deg = 30.0
        self._vertical_scale: ttk.Scale | None = None
        self._vertical_scale_value: tk.DoubleVar | None = None
        self._vertical_scale_label: tk.StringVar | None = None
        super().__init__()

    @property
    def terrain_directory(self) -> Path:
        return self.store.path.parent / "terrain" / "terrarium"

    def _build_ui(self) -> None:
        super()._build_ui()
        old_live_view = self.live_view
        parent = old_live_view.master
        old_live_view.destroy()
        self.live_view = TerrainStarLiveSkyView(parent, on_select=self._on_live_satellite_selected)
        self.live_view.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        details = next(
            (child for child in parent.winfo_children() if isinstance(child, ttk.LabelFrame)),
            None,
        )
        if details is not None:
            details.grid_configure(row=0, column=2, sticky="ns")

        elevation_control = ttk.Frame(parent, padding=(2, 0, 8, 0))
        elevation_control.grid(row=0, column=1, sticky="ns")
        ttk.Label(elevation_control, text="180°", anchor="center").pack(fill="x")
        self._vertical_scale_value = tk.DoubleVar(master=self, value=self._vertical_sky_angle_deg)
        self._vertical_scale = ttk.Scale(
            elevation_control,
            from_=180.0,
            to=0.0,
            orient="vertical",
            variable=self._vertical_scale_value,
            command=self._on_vertical_sky_angle_changed,
            length=360,
        )
        self._vertical_scale.pack(side="top", fill="y", expand=True, pady=4)
        ttk.Label(elevation_control, text="0°", anchor="center").pack(fill="x")
        self._vertical_scale_label = tk.StringVar(master=self, value="30°")
        ttk.Label(
            elevation_control,
            textvariable=self._vertical_scale_label,
            anchor="center",
            font=("Segoe UI", 9, "bold"),
        ).pack(fill="x", pady=(6, 0))
        ttk.Label(
            elevation_control,
            text="Sky\nangle",
            anchor="center",
            justify="center",
        ).pack(fill="x", pady=(2, 0))

        self._apply_live_view_direction(show_error=False)
        self._apply_vertical_sky_angle()
        self._on_star_layer_changed()

    def _apply_live_view_direction(self, *, show_error: bool = True) -> None:
        super()._apply_live_view_direction(show_error=show_error)
        if hasattr(self, "live_view"):
            self._apply_vertical_sky_angle(update_summary=False)
            self._update_live_view_summary()

    def _on_vertical_sky_angle_changed(self, value: str) -> None:
        self._vertical_sky_angle_deg = max(0.0, min(180.0, float(value)))
        self._apply_vertical_sky_angle()

    def _apply_vertical_sky_angle(self, *, update_summary: bool = True) -> None:
        if not hasattr(self, "live_view"):
            return
        span = self.live_view.maximum_elevation_deg - self.live_view.minimum_elevation_deg
        window = vertical_sky_window(
            self._vertical_sky_angle_deg,
            base_facing_deg=self.live_view._base_facing_deg,
            elevation_span_deg=span,
        )
        self.live_view._facing_deg = window.facing_deg
        self.live_view._minimum_elevation_deg = window.minimum_elevation_deg
        self.live_view._maximum_elevation_deg = window.maximum_elevation_deg
        if self._vertical_scale_label is not None:
            self._vertical_scale_label.set(f"{window.sky_angle_deg:.0f}°")
        self.live_view.redraw()
        if update_summary:
            self._update_live_view_summary()

    def _reset_live_zoom(self) -> None:
        self._vertical_sky_angle_deg = 30.0
        if self._vertical_scale_value is not None:
            self._vertical_scale_value.set(self._vertical_sky_angle_deg)
        super()._reset_live_zoom()
        self._apply_vertical_sky_angle()

    def _update_live_view_summary(self) -> None:
        super()._update_live_view_summary()
        current = self.live_detail_var.get()
        hemisphere = "selected facing horizon" if self._vertical_sky_angle_deg <= 90.0 else "opposite horizon"
        self.live_detail_var.set(
            current
            + f"\nVertical sky angle: {self._vertical_sky_angle_deg:.0f}° ({hemisphere})\n"
            + "0° = facing horizon  |  90° = zenith  |  180° = opposite horizon"
        )

    def open_settings(self) -> None:
        Stage12SettingsWindow(self)

    def _refresh_location_selector(self) -> None:
        super()._refresh_location_selector()
        self._invalidate_stale_terrain_horizon()
        self._ensure_terrain_horizon(self.selected_name)

    def _on_location_changed(self, _event: object | None = None) -> None:
        super()._on_location_changed(_event)
        self._invalidate_stale_terrain_horizon()
        self._ensure_terrain_horizon(self.selected_name)

    def _invalidate_stale_terrain_horizon(self) -> None:
        current_key = self._location_key(self.selected_name)
        if current_key == self._terrain_location_key:
            return
        self._terrain_location_key = None
        self._terrain_horizon = ()
        if hasattr(self, "live_view") and isinstance(self.live_view, TerrainStarLiveSkyView):
            self.live_view.set_terrain_horizon(None)
            self.live_view.set_terrain_status(
                "Terrain: waiting for location" if current_key is None else "Terrain: preparing"
            )

    def _terrain_cache_changed(self) -> None:
        self._terrain_location_key = None
        self._terrain_horizon = ()
        self._ensure_terrain_horizon(self.selected_name, force=True)

    def _ensure_terrain_horizon(self, profile_name: str | None, *, force: bool = False) -> None:
        if not profile_name:
            return
        location_key = self._location_key(profile_name)
        if location_key is None or (not force and location_key == self._terrain_location_key):
            return
        if self._terrain_load_in_progress:
            self._pending_terrain_profile = profile_name
            return
        profile = next((item for item in self.profiles if item.name == profile_name), None)
        if profile is None:
            return
        self._terrain_load_in_progress = True
        self._pending_terrain_profile = None
        if isinstance(self.live_view, TerrainStarLiveSkyView):
            self.live_view.set_terrain_status("Terrain: loading required data...")
        threading.Thread(
            target=self._load_terrain_horizon,
            args=(profile_name, location_key, profile.latitude, profile.longitude, profile.altitude_m),
            daemon=True,
        ).start()

    def _load_terrain_horizon(
        self,
        profile_name: str,
        location_key: tuple[str, float, float, float],
        latitude: float,
        longitude: float,
        altitude_m: float,
    ) -> None:
        try:
            source = CachedTerrariumElevationSource(self.terrain_directory, zoom=self.TERRAIN_ZOOM)
            horizon = calculate_horizon_profile(
                source,
                observer_latitude=latitude,
                observer_longitude=longitude,
                observer_altitude_m=altitude_m,
                observer_height_m=1.7,
                azimuth_step_deg=1.0,
                max_distance_km=80.0,
            )
        except TerrainDownloadError:
            self.after(0, self._terrain_horizon_failed, profile_name, location_key, "Terrain: data download unavailable")
            return
        except (OSError, ValueError):
            self.after(0, self._terrain_horizon_failed, profile_name, location_key, "Terrain: local cache unavailable")
            return
        self.after(0, self._apply_terrain_horizon, profile_name, location_key, horizon)

    def _apply_terrain_horizon(self, profile_name: str, location_key: tuple[str, float, float, float], horizon: tuple) -> None:
        self._terrain_load_in_progress = False
        if profile_name == self.selected_name and location_key == self._location_key(self.selected_name):
            self._terrain_location_key = location_key
            self._terrain_horizon = horizon
            if isinstance(self.live_view, TerrainStarLiveSkyView):
                self.live_view.set_terrain_horizon(horizon)
                self.live_view.set_terrain_status("Terrain: generated")
        self._start_pending_terrain_horizon()

    def _terrain_horizon_failed(self, profile_name: str, location_key: tuple[str, float, float, float], status: str) -> None:
        self._terrain_load_in_progress = False
        if profile_name == self.selected_name and location_key == self._location_key(self.selected_name):
            self._terrain_location_key = location_key
            self._terrain_horizon = ()
            if isinstance(self.live_view, TerrainStarLiveSkyView):
                self.live_view.set_terrain_horizon(None)
                self.live_view.set_terrain_status(status)
        self._start_pending_terrain_horizon()

    def _start_pending_terrain_horizon(self) -> None:
        pending = self._pending_terrain_profile
        self._pending_terrain_profile = None
        if pending and pending == self.selected_name:
            self._ensure_terrain_horizon(pending, force=True)


def main() -> int:
    app = Stage12NightAzimuthApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
