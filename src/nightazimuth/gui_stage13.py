from __future__ import annotations

from dataclasses import replace
import threading
import tkinter as tk
from tkinter import ttk

from .celestrak import CelestrakClient, CelestrakError
from .gui_stage12 import Stage12NightAzimuthApp
from .hud_finder_view import HudFinderView
from .live_catalog import merge_orbital_catalogues
from .location_profiles import LocationProfile
from .passes import PassPredictor
from .sky_map import SkySatellite
from .track_prediction import TrackPredictor
from .tracker import SatelliteTracker
from .visibility import VisibilityEngine


class Stage13NightAzimuthApp(Stage12NightAzimuthApp):
    """Sparse live finder with broad active-satellite background tracking."""

    LIVE_TRACK_LIMIT = 60

    def __init__(self) -> None:
        super().__init__()
        # Broad ACTIVE-catalogue calculations are intentionally slower than the
        # earlier small VISUAL-only set. Fifteen seconds remains useful outdoors
        # without repeatedly recalculating thousands of orbital elements.
        self._auto_refresh_ms = 15_000

    def _build_live_view(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        controls = ttk.Frame(parent)
        controls.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        ttk.Label(controls, text="Facing:").pack(side="left")
        facing_entry = ttk.Entry(controls, textvariable=self.facing_var, width=10)
        facing_entry.pack(side="left", padx=(6, 12))
        ttk.Label(controls, text="0–359° or N, NE, E, SE, S, SW, W, NW").pack(side="left")

        ttk.Label(controls, text="Field of view:").pack(side="left", padx=(20, 6))
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
        ttk.Button(controls, text="Reset", command=self._reset_live_zoom).pack(side="left", padx=(4, 0))

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

        self.show_all_tracked_var = tk.BooleanVar(master=self, value=False)
        ttk.Checkbutton(
            controls,
            text="All tracked",
            variable=self.show_all_tracked_var,
            command=self._on_show_all_tracked_changed,
        ).pack(side="left", padx=(8, 0))

        content = ttk.Frame(parent)
        content.grid(row=1, column=0, sticky="nsew")
        content.columnconfigure(0, weight=1)
        content.rowconfigure(0, weight=1)

        self.live_view = HudFinderView(content, on_select=self._on_live_satellite_selected)
        self.live_view.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        details = ttk.LabelFrame(content, text="Live finder", padding=12, width=280)
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
                "The finder is deliberately sparse so it can later sit over a real sky/camera image. "
                "Vega stays prominent, major planets remain labelled, and the default finder shows only the strongest "
                "current satellite candidates. Enable All tracked only when you want the full potentially-visible set."
            ),
            wraplength=250,
            justify="left",
        ).pack(side="bottom", anchor="sw")

        self._apply_live_view_direction(show_error=False)
        self._on_star_layer_changed()

    def _on_show_all_tracked_changed(self) -> None:
        if not hasattr(self, "live_view"):
            return
        self.live_view.set_show_all_tracked(self.show_all_tracked_var.get())
        self._update_live_view_summary()

    def _update_live_view_summary(self) -> None:
        if not hasattr(self, "live_view"):
            return
        all_status = "On" if getattr(self, "show_all_tracked_var", None) and self.show_all_tracked_var.get() else "Off"
        self.live_detail_var.set(
            f"Facing {self.live_view.facing_deg:.0f}°\n"
            f"Horizontal FOV: {self.live_view.horizontal_fov_deg:.0f}°\n"
            f"Elevation: {self.live_view.minimum_elevation_deg:.0f}–{self.live_view.maximum_elevation_deg:.0f}°\n\n"
            "Sparse HUD mode\n"
            "VEGA = blue-white reference\n"
            "Green = potentially visible satellite\n"
            "Selected object = labelled + projected path\n"
            f"All tracked: {all_status}\n\n"
            "Default mode ranks candidates by elevation and then range, with no hard distance cutoff."
        )

    def _load_tracking_data(self, profile: LocationProfile) -> None:
        try:
            observer = self._observer_for_profile(profile)
            client = CelestrakClient(cache_directory=self.cache_directory, cache_max_age_minutes=120)

            # Keep VISUAL first so its records win on duplicates, then add the
            # much broader ACTIVE catalogue for live identification coverage.
            visual_elements = client.load_group("VISUAL")
            try:
                active_elements = client.load_group("ACTIVE")
            except CelestrakError:
                active_elements = []
            live_elements = merge_orbital_catalogues(visual_elements, active_elements)
            elements_by_norad = {
                str(item.get("NORAD_CAT_ID") or ""): item
                for item in live_elements
                if item.get("NORAD_CAT_ID") is not None
            }

            tracker = SatelliteTracker(observer)
            positions = tracker.positions_above_horizon(live_elements)
            visibility = VisibilityEngine(
                observer,
                cache_directory=self.cache_directory,
                darkness_threshold_deg=-6.0,
            )

            live_rows: list[tuple[str, ...]] = []
            sky_satellites: list[SkySatellite] = []
            for item in positions:
                fields = elements_by_norad.get(item.norad_id)
                if fields is None:
                    continue
                status = visibility.evaluate(fields)
                satellite = SkySatellite(
                    name=item.name,
                    norad_id=item.norad_id,
                    azimuth_deg=item.azimuth_deg,
                    elevation_deg=item.elevation_deg,
                    range_km=item.range_km,
                    satellite_sunlit=status.satellite_sunlit,
                    sky_dark=status.sky_dark,
                    potentially_visible=status.potentially_visible,
                )
                sky_satellites.append(satellite)
                live_rows.append(
                    (
                        item.name,
                        item.norad_id,
                        f"{item.azimuth_deg:.2f}°",
                        f"{item.elevation_deg:.2f}°",
                        f"{item.range_km:.0f}",
                        "YES" if status.satellite_sunlit else "NO",
                        "YES" if status.sky_dark else "NO",
                        "YES" if status.potentially_visible else "NO",
                    )
                )

            predictor = PassPredictor(observer)
            passes = predictor.predict(visual_elements, hours=24.0, minimum_elevation_deg=10.0)
            pass_rows = [
                (
                    item.name,
                    item.norad_id,
                    item.rise_time.strftime("%Y-%m-%d %H:%M:%S"),
                    item.culmination_time.strftime("%Y-%m-%d %H:%M:%S"),
                    item.set_time.strftime("%Y-%m-%d %H:%M:%S"),
                    f"{item.max_elevation_deg:.2f}°",
                )
                for item in passes
            ]

            self.after(
                0,
                self._apply_tracking_data,
                profile.name,
                live_rows,
                pass_rows,
                sky_satellites,
            )
        except (CelestrakError, OSError, ValueError) as exc:
            self.after(0, self._show_refresh_error, str(exc))
        except Exception as exc:  # noqa: BLE001
            self.after(0, self._show_refresh_error, f"Unexpected error: {exc}")

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
        self.live_view.set_show_all_tracked(self.show_all_tracked_var.get())
        # Tracking data proves a selected observer is active. Re-check terrain here
        # so the HUD cannot remain stuck on "waiting for location" after a valid refresh.
        self._ensure_terrain_horizon(profile_name)

    def _start_track_prediction(
        self,
        profile_name: str,
        satellites: list[SkySatellite],
        generation: int,
    ) -> None:
        candidates = sorted(
            satellites,
            key=lambda satellite: (
                not satellite.potentially_visible,
                -satellite.elevation_deg,
            ),
        )[: self.LIVE_TRACK_LIMIT]
        super()._start_track_prediction(profile_name, candidates, generation)

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
            visual_elements = client.load_group("VISUAL")
            try:
                active_elements = client.load_group("ACTIVE")
            except CelestrakError:
                active_elements = []
            elements = merge_orbital_catalogues(visual_elements, active_elements)
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
                replace(satellite, future_track=tracks.get(satellite.norad_id, ()))
                for satellite in current_satellites
            ]
            self._sky_satellites = updated
            self.live_view.set_satellites(updated)
            self.live_view.set_show_all_tracked(self.show_all_tracked_var.get())
            if selected_norad is not None:
                selected = next(
                    (satellite for satellite in updated if satellite.norad_id == selected_norad),
                    None,
                )
                if selected is not None:
                    self._on_live_satellite_selected(selected)
        self._start_pending_track_prediction()


def main() -> int:
    app = Stage13NightAzimuthApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
