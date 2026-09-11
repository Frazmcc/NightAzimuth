from __future__ import annotations

from pathlib import Path
import threading
from tkinter import filedialog, ttk

from .gui import SettingsWindow
from .gui_stage7 import Stage7NightAzimuthApp
from .terrain_horizon import (
    MissingTerrainDataError,
    OfflineTerrariumElevationSource,
    TerrainPackError,
    calculate_horizon_profile,
    import_terrarium_pack,
)
from .terrain_star_live_view import TerrainStarLiveSkyView


class Stage12SettingsWindow(SettingsWindow):
    """Settings window with privacy-safe local terrain-pack import."""

    def __init__(self, app: Stage12NightAzimuthApp) -> None:
        super().__init__(app)
        self.geometry("620x500")

    def _build_ui(self) -> None:
        super()._build_ui()

        terrain = ttk.LabelFrame(self, text="Offline terrain", padding=10)
        terrain.pack(fill="x", padx=16, pady=(0, 14))
        ttk.Label(
            terrain,
            text=(
                "Terrain packs are imported from a folder already on this PC. "
                "NightAzimuth never uses your saved coordinates to download terrain."
            ),
            wraplength=560,
            justify="left",
        ).pack(anchor="w")

        self.terrain_import_status = ttk.Label(
            terrain,
            text="No terrain download is performed by NightAzimuth.",
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
        selected = filedialog.askdirectory(
            parent=self,
            title="Select offline Terrarium terrain-pack folder",
        )
        if not selected:
            return

        source = Path(selected)
        destination = self.app.store.path.parent / "terrain" / "terrarium"
        self.terrain_import_button.config(state="disabled")
        self.terrain_import_status.config(text="Importing local terrain pack...")
        threading.Thread(
            target=self._import_terrain_pack,
            args=(source, destination),
            daemon=True,
        ).start()

    def _import_terrain_pack(self, source: Path, destination: Path) -> None:
        try:
            summary = import_terrarium_pack(source, destination)
        except (TerrainPackError, OSError, ValueError):
            self.after(0, self._terrain_import_failed)
            return
        self.after(0, self._terrain_import_complete, summary.tile_count, summary.zoom_levels)

    def _terrain_import_failed(self) -> None:
        self.terrain_import_button.config(state="normal")
        self.terrain_import_status.config(
            text="Import failed. Select a valid local Terrarium tile folder."
        )

    def _terrain_import_complete(self, tile_count: int, zoom_levels: tuple[int, ...]) -> None:
        self.terrain_import_button.config(state="normal")
        zoom_text = ", ".join(str(level) for level in zoom_levels)
        self.terrain_import_status.config(
            text=f"Imported {tile_count} terrain tiles. Available zoom levels: {zoom_text}."
        )
        self.app._terrain_pack_changed()


class Stage12NightAzimuthApp(Stage7NightAzimuthApp):
    """Current GUI with automatic, local-only terrain horizon generation."""

    def __init__(self) -> None:
        self._terrain_load_in_progress = False
        self._pending_terrain_profile: str | None = None
        self._terrain_location_key: tuple[str, float, float, float] | None = None
        self._terrain_horizon: tuple = ()
        super().__init__()

    @property
    def terrain_directory(self) -> Path:
        return self.store.path.parent / "terrain" / "terrarium"

    def _build_ui(self) -> None:
        super()._build_ui()

        # Stage 7 creates the celestial live view. Replace only that canvas with
        # the terrain-aware subclass so all existing controls and behaviour stay
        # unchanged.
        old_live_view = self.live_view
        parent = old_live_view.master
        old_live_view.destroy()
        self.live_view = TerrainStarLiveSkyView(
            parent,
            on_select=self._on_live_satellite_selected,
        )
        self.live_view.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self._apply_live_view_direction(show_error=False)
        self._on_star_layer_changed()

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
            if current_key is None:
                self.live_view.set_terrain_status("Terrain: waiting for location")
            else:
                self.live_view.set_terrain_status("Terrain: checking local data")

    def _terrain_pack_changed(self) -> None:
        self._terrain_location_key = None
        self._terrain_horizon = ()
        if hasattr(self, "live_view") and isinstance(self.live_view, TerrainStarLiveSkyView):
            self.live_view.set_terrain_horizon(None)
            self.live_view.set_terrain_status("Terrain: checking imported pack")
        self._ensure_terrain_horizon(self.selected_name, force=True)

    def _ensure_terrain_horizon(self, profile_name: str | None, *, force: bool = False) -> None:
        if not profile_name:
            return

        location_key = self._location_key(profile_name)
        if location_key is None:
            return
        if not force and location_key == self._terrain_location_key:
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
            self.live_view.set_terrain_status("Terrain: generating locally...")

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
            zoom = self._select_local_terrain_zoom()
            source = OfflineTerrariumElevationSource(self.terrain_directory, zoom=zoom)
            horizon = calculate_horizon_profile(
                source,
                observer_latitude=latitude,
                observer_longitude=longitude,
                observer_altitude_m=altitude_m,
                observer_height_m=1.7,
                azimuth_step_deg=1.0,
                max_distance_km=80.0,
            )
        except FileNotFoundError:
            self.after(
                0,
                self._terrain_horizon_failed,
                profile_name,
                location_key,
                "Terrain: offline pack not installed",
            )
            return
        except MissingTerrainDataError:
            self.after(
                0,
                self._terrain_horizon_failed,
                profile_name,
                location_key,
                "Terrain: installed pack does not cover this location",
            )
            return
        except (OSError, ValueError):
            self.after(
                0,
                self._terrain_horizon_failed,
                profile_name,
                location_key,
                "Terrain: local pack unavailable",
            )
            return

        self.after(
            0,
            self._apply_terrain_horizon,
            profile_name,
            location_key,
            horizon,
        )

    def _select_local_terrain_zoom(self) -> int:
        directory = self.terrain_directory
        if not directory.is_dir():
            raise FileNotFoundError(directory)

        levels = sorted(
            int(child.name)
            for child in directory.iterdir()
            if child.is_dir()
            and child.name.isdigit()
            and 0 <= int(child.name) <= 14
        )
        if not levels:
            raise ValueError("No supported local terrain zoom level is installed.")
        return levels[-1]

    def _apply_terrain_horizon(
        self,
        profile_name: str,
        location_key: tuple[str, float, float, float],
        horizon: tuple,
    ) -> None:
        self._terrain_load_in_progress = False
        if (
            profile_name == self.selected_name
            and location_key == self._location_key(self.selected_name)
        ):
            self._terrain_location_key = location_key
            self._terrain_horizon = horizon
            if isinstance(self.live_view, TerrainStarLiveSkyView):
                self.live_view.set_terrain_horizon(horizon)
                self.live_view.set_terrain_status("Terrain: generated locally")
        self._start_pending_terrain_horizon()

    def _terrain_horizon_failed(
        self,
        profile_name: str,
        location_key: tuple[str, float, float, float],
        status: str,
    ) -> None:
        self._terrain_load_in_progress = False
        if (
            profile_name == self.selected_name
            and location_key == self._location_key(self.selected_name)
        ):
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
