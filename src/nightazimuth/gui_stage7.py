from __future__ import annotations

from dataclasses import replace
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk

from .celestrak import CelestrakClient
from .gui import NightAzimuthApp
from .sky_map import SkySatellite
from .star_field import StarFieldEngine, StarFieldSnapshot
from .star_live_view import StarLiveSkyView
from .track_prediction import TrackPredictor


_CARDINALS = {
    "N": 0.0,
    "NE": 45.0,
    "E": 90.0,
    "SE": 135.0,
    "S": 180.0,
    "SW": 225.0,
    "W": 270.0,
    "NW": 315.0,
}


class Stage7NightAzimuthApp(NightAzimuthApp):
    """Current GUI: all-sky radar plus practical forward-looking Live view."""

    def __init__(self) -> None:
        self._track_load_in_progress = False
        self._track_generation = 0
        self._pending_track_request: tuple[str, list[SkySatellite], int] | None = None
        self._star_load_in_progress = False
        self._pending_star_profile: str | None = None
        self._star_snapshot: StarFieldSnapshot | None = None
        self._star_snapshot_profile: str | None = None
        self._star_snapshot_location_key: tuple[str, float, float, float] | None = None
        self._star_loaded_monotonic = 0.0
        super().__init__()
        self._auto_refresh_ms = 5_000

    def _build_ui(self) -> None:
        self.facing_var = tk.StringVar(master=self, value="N")
        self.fov_var = tk.StringVar(master=self, value="90")
        self.show_stars_var = tk.BooleanVar(master=self, value=True)
        self.show_constellations_var = tk.BooleanVar(master=self, value=False)
        self.live_detail_var = tk.StringVar(
            master=self,
            value="Click a satellite in the live view to see details.",
        )

        super()._build_ui()

        notebook = self._find_notebook(self)
        if notebook is None:
            return

        live_view_tab = ttk.Frame(notebook, padding=8)
        notebook.insert(1, live_view_tab, text="Live view")
        self._build_live_view(live_view_tab)

    def _find_notebook(self, widget: tk.Misc) -> ttk.Notebook | None:
        for child in widget.winfo_children():
            if isinstance(child, ttk.Notebook):
                return child
            nested = self._find_notebook(child)
            if nested is not None:
                return nested
        return None

    def _build_live_view(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        controls = ttk.Frame(parent)
        controls.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        ttk.Label(controls, text="Facing:").pack(side="left")
        facing_entry = ttk.Entry(controls, textvariable=self.facing_var, width=10)
        facing_entry.pack(side="left", padx=(6, 14))
        ttk.Label(controls, text="Enter degrees (0–359) or N, NE, E, SE, S, SW, W, NW").pack(side="left")

        ttk.Label(controls, text="Field of view:").pack(side="left", padx=(24, 6))
        fov_combo = ttk.Combobox(
            controls,
            textvariable=self.fov_var,
            values=("30", "45", "60", "90", "120", "180"),
            width=6,
            state="readonly",
        )
        fov_combo.pack(side="left")
        ttk.Label(controls, text="°").pack(side="left", padx=(2, 8))
        ttk.Button(controls, text="Apply", command=self._apply_live_view_direction).pack(side="left")

        ttk.Separator(controls, orient="vertical").pack(side="left", fill="y", padx=10)
        ttk.Label(controls, text="Zoom:").pack(side="left")
        ttk.Button(controls, text="−", width=3, command=self._zoom_live_out).pack(side="left", padx=(6, 2))
        ttk.Button(controls, text="+", width=3, command=self._zoom_live_in).pack(side="left", padx=2)
        ttk.Button(controls, text="Reset view", command=self._reset_live_zoom).pack(side="left", padx=(4, 0))

        ttk.Separator(controls, orient="vertical").pack(side="left", fill="y", padx=10)
        ttk.Checkbutton(
            controls,
            text="Stars",
            variable=self.show_stars_var,
            command=self._on_star_layer_changed,
        ).pack(side="left")
        ttk.Checkbutton(
            controls,
            text="Constellations",
            variable=self.show_constellations_var,
            command=self._on_star_layer_changed,
        ).pack(side="left", padx=(8, 0))

        content = ttk.Frame(parent)
        content.grid(row=1, column=0, sticky="nsew")
        content.columnconfigure(0, weight=1)
        content.rowconfigure(0, weight=1)

        self.live_view = StarLiveSkyView(content, on_select=self._on_live_satellite_selected)
        self.live_view.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        details = ttk.LabelFrame(content, text="Current view", padding=12, width=280)
        details.grid(row=0, column=1, sticky="ns")
        details.grid_propagate(False)

        ttk.Label(
            details,
            textvariable=self.live_detail_var,
            wraplength=250,
            justify="left",
        ).pack(anchor="nw", fill="x")

        ttk.Label(
            details,
            text=(
                "The practical live view covers 0–60° elevation. "
                "Stars are plotted from the Hipparcos catalogue for the selected location and current time. "
                "Major planets remain labelled independently of the Stars control. "
                "Dashed lines show the next three minutes of satellite movement."
            ),
            wraplength=250,
            justify="left",
        ).pack(side="bottom", anchor="sw")

        self._apply_live_view_direction(show_error=False)
        self._on_star_layer_changed()

    def _parse_facing(self) -> float:
        raw = self.facing_var.get().strip().upper()
        if raw in _CARDINALS:
            return _CARDINALS[raw]
        value = float(raw)
        if not 0.0 <= value < 360.0:
            raise ValueError("Facing direction must be between 0 and 359.999 degrees.")
        return value

    def _apply_live_view_direction(self, *, show_error: bool = True) -> None:
        try:
            facing = self._parse_facing()
            fov = float(self.fov_var.get())
        except ValueError as exc:
            if show_error:
                messagebox.showerror("Invalid live view", str(exc), parent=self)
            return

        self.live_view.set_view(facing, fov)
        self._update_live_view_summary()

    def _zoom_live_in(self) -> None:
        self.live_view.zoom_in()
        self._update_live_view_summary()

    def _zoom_live_out(self) -> None:
        self.live_view.zoom_out()
        self._update_live_view_summary()

    def _reset_live_zoom(self) -> None:
        self.live_view.reset_zoom()
        self._update_live_view_summary()

    def _on_star_layer_changed(self) -> None:
        if not hasattr(self, "live_view"):
            return
        self.live_view.set_star_visibility(
            stars=self.show_stars_var.get(),
            constellations=self.show_constellations_var.get(),
        )
        # Planet positions share the same astronomical snapshot, so keep that
        # snapshot available even when both optional star layers are hidden.
        self._ensure_star_field(self.selected_name)

    def _update_live_view_summary(self) -> None:
        star_status = "On" if self.show_stars_var.get() else "Off"
        constellation_status = "On" if self.show_constellations_var.get() else "Off"
        self.live_detail_var.set(
            f"Facing {self.live_view.facing_deg:.0f}°\n"
            f"Horizontal FOV: {self.live_view.horizontal_fov_deg:.0f}°\n"
            f"Elevation: {self.live_view.minimum_elevation_deg:.0f}–{self.live_view.maximum_elevation_deg:.0f}°\n"
            f"Stars: {star_status}  |  Constellations: {constellation_status}\n\n"
            "Major planets are always shown when they are inside the current view.\n"
            "Yellow = potentially visible satellite. Blue = other tracked satellite.\n"
            "Dashed arrow = predicted movement for the next 3 minutes."
        )

    def _apply_tracking_data(
        self,
        profile_name: str,
        live_rows: list[tuple[str, ...]],
        pass_rows: list[tuple[str, ...]],
        sky_satellites: list[SkySatellite],
    ) -> None:
        super()._apply_tracking_data(profile_name, live_rows, pass_rows, sky_satellites)
        if profile_name != self.selected_name or not hasattr(self, "live_view"):
            return

        self._track_generation += 1
        generation = self._track_generation
        self.live_view.set_satellites(sky_satellites)
        self._start_track_prediction(profile_name, sky_satellites, generation)
        self._ensure_star_field(profile_name)

    def _location_key(
        self,
        profile_name: str | None,
    ) -> tuple[str, float, float, float] | None:
        if not profile_name:
            return None
        profile = next((item for item in self.profiles if item.name == profile_name), None)
        if profile is None:
            return None
        return (
            profile.name,
            profile.latitude,
            profile.longitude,
            profile.altitude_m,
        )

    def _invalidate_stale_star_field(self) -> None:
        current_key = self._location_key(self.selected_name)
        if current_key == self._star_snapshot_location_key:
            return

        self._star_snapshot = None
        self._star_snapshot_profile = None
        self._star_snapshot_location_key = None
        self._star_loaded_monotonic = 0.0

        if hasattr(self, "live_view"):
            self.live_view.set_star_field(None)

    def _on_location_changed(self, _event: object | None = None) -> None:
        super()._on_location_changed(_event)
        self._invalidate_stale_star_field()

    def _refresh_location_selector(self) -> None:
        super()._refresh_location_selector()
        self._invalidate_stale_star_field()

    def _ensure_star_field(self, profile_name: str, *, force: bool = False) -> None:
        if not profile_name:
            return

        location_key = self._location_key(profile_name)
        if location_key is None:
            return

        age = time.monotonic() - self._star_loaded_monotonic
        if (
            not force
            and self._star_snapshot is not None
            and self._star_snapshot_profile == profile_name
            and self._star_snapshot_location_key == location_key
            and age < 60.0
        ):
            return

        if self._star_load_in_progress:
            self._pending_star_profile = profile_name
            return

        profile = next((item for item in self.profiles if item.name == profile_name), None)
        if profile is None:
            return

        self._star_load_in_progress = True
        self._pending_star_profile = None
        observer = self._observer_for_profile(profile)
        threading.Thread(
            target=self._load_star_field,
            args=(profile_name, location_key, observer),
            daemon=True,
        ).start()

    def _load_star_field(
        self,
        profile_name: str,
        location_key: tuple[str, float, float, float],
        observer: object,
    ) -> None:
        try:
            snapshot = StarFieldEngine(
                observer,
                self.cache_directory,
                limiting_magnitude=5.5,
            ).snapshot()
            self.after(
                0,
                self._apply_star_field,
                profile_name,
                location_key,
                snapshot,
            )
        except Exception as exc:  # noqa: BLE001
            self.after(
                0,
                self._star_field_failed,
                profile_name,
                location_key,
                str(exc),
            )

    def _apply_star_field(
        self,
        profile_name: str,
        location_key: tuple[str, float, float, float],
        snapshot: StarFieldSnapshot,
    ) -> None:
        self._star_load_in_progress = False
        if (
            profile_name == self.selected_name
            and location_key == self._location_key(self.selected_name)
        ):
            self._star_snapshot = snapshot
            self._star_snapshot_profile = profile_name
            self._star_snapshot_location_key = location_key
            self._star_loaded_monotonic = time.monotonic()
            self.live_view.set_star_field(snapshot)
        self._start_pending_star_field()

    def _star_field_failed(
        self,
        profile_name: str,
        location_key: tuple[str, float, float, float],
        error: str,
    ) -> None:
        self._star_load_in_progress = False
        if (
            profile_name == self.selected_name
            and location_key == self._location_key(self.selected_name)
        ):
            self.status_var.set(f"Satellite tracking active; celestial field unavailable: {error}")
        self._start_pending_star_field()

    def _start_pending_star_field(self) -> None:
        pending = self._pending_star_profile
        self._pending_star_profile = None
        if pending and pending == self.selected_name:
            self._ensure_star_field(pending, force=True)

    def _start_track_prediction(
        self,
        profile_name: str,
        satellites: list[SkySatellite],
        generation: int,
    ) -> None:
        if not satellites:
            return
        profile = next((item for item in self.profiles if item.name == profile_name), None)
        if profile is None:
            return

        if self._track_load_in_progress:
            self._pending_track_request = (profile_name, satellites, generation)
            return

        self._track_load_in_progress = True
        self._pending_track_request = None
        observer = self._observer_for_profile(profile)
        threading.Thread(
            target=self._load_projected_tracks,
            args=(profile_name, observer, satellites, generation),
            daemon=True,
        ).start()

    def _load_projected_tracks(
        self,
        profile_name: str,
        observer: object,
        satellites: list[SkySatellite],
        generation: int,
    ) -> None:
        try:
            wanted_ids = {satellite.norad_id for satellite in satellites}
            client = CelestrakClient(cache_directory=self.cache_directory, cache_max_age_minutes=120)
            elements = client.load_group("VISUAL")
            relevant = [
                fields
                for fields in elements
                if str(fields.get("NORAD_CAT_ID") or "") in wanted_ids
            ]
            tracks = TrackPredictor(observer).predict(
                relevant,
                duration_seconds=180,
                step_seconds=30,
            )
            self.after(0, self._apply_projected_tracks, profile_name, generation, tracks)
        except Exception as exc:  # noqa: BLE001
            self.after(0, self._projected_track_failed, generation, str(exc))

    def _apply_projected_tracks(
        self,
        profile_name: str,
        generation: int,
        tracks: dict[str, tuple],
    ) -> None:
        self._track_load_in_progress = False

        if profile_name == self.selected_name and generation == self._track_generation:
            selected_norad = self.live_view.selected_norad
            current_satellites = list(self._sky_satellites)
            updated = [
                replace(
                    satellite,
                    future_track=tracks.get(satellite.norad_id, ()),
                )
                for satellite in current_satellites
            ]
            self._sky_satellites = updated
            self.live_view.set_satellites(updated)

            if selected_norad is not None:
                selected = next(
                    (satellite for satellite in updated if satellite.norad_id == selected_norad),
                    None,
                )
                if selected is not None:
                    self._on_live_satellite_selected(selected)

        self._start_pending_track_prediction()

    def _projected_track_failed(self, _generation: int, _error: str) -> None:
        self._track_load_in_progress = False
        self._start_pending_track_prediction()

    def _start_pending_track_prediction(self) -> None:
        pending = self._pending_track_request
        self._pending_track_request = None
        if pending is None:
            return
        profile_name, satellites, generation = pending
        if profile_name == self.selected_name and generation == self._track_generation:
            self._start_track_prediction(profile_name, satellites, generation)

    def _on_live_satellite_selected(self, satellite: SkySatellite) -> None:
        self.live_view.select_norad(satellite.norad_id)

        projection_text = "No short projection available."
        if len(satellite.future_track) >= 2:
            first = satellite.future_track[0]
            last = satellite.future_track[-1]
            projection_text = (
                f"Next {last.seconds_from_now // 60} min:\n"
                f"Azimuth {first.azimuth_deg:.1f}° → {last.azimuth_deg:.1f}°\n"
                f"Elevation {first.elevation_deg:.1f}° → {last.elevation_deg:.1f}°"
            )

        phase_text = (
            "Unknown"
            if satellite.phase_angle_deg is None
            else f"{satellite.phase_angle_deg:.1f}°"
        )
        brightness_text = (
            "Unknown"
            if satellite.brightness_estimate is None
            else f"mag {satellite.brightness_estimate.display_range}"
        )

        self.live_detail_var.set(
            f"{satellite.name}\n\n"
            f"NORAD: {satellite.norad_id}\n"
            f"Azimuth: {satellite.azimuth_deg:.2f}°\n"
            f"Elevation: {satellite.elevation_deg:.2f}°\n"
            f"Range: {satellite.range_km:.0f} km\n"
            f"Phase angle: {phase_text}\n"
            f"Brightness: {brightness_text}\n\n"
            f"{projection_text}\n\n"
            f"Sunlit: {'Yes' if satellite.satellite_sunlit else 'No'}\n"
            f"Dark sky: {'Yes' if satellite.sky_dark else 'No'}\n"
            f"Potentially visible: {'Yes' if satellite.potentially_visible else 'No'}"
        )


def main() -> int:
    app = Stage7NightAzimuthApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
