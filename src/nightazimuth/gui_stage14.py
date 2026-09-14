from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import threading
import tkinter as tk
from tkinter import ttk

from .brightness import estimate_supported_satellite
from .celestrak import CelestrakClient, CelestrakError
from .gui_stage13 import Stage13NightAzimuthApp
from .live_catalog import merge_orbital_catalogues
from .live_view import project_live_view
from .location_profiles import LocationProfile
from .observing_conditions import (
    ObservingConditions,
    ObservingConditionsEngine,
    format_countdown,
)
from .passes import PassPredictor
from .sky_map import SkySatellite
from .track_prediction import TrackPredictor
from .tracker import SatelliteTracker
from .twilight_hud_finder_view import TwilightSmoothHudFinderView, is_live_observing_candidate
from .visibility import VisibilityEngine


class Stage14NightAzimuthApp(Stage13NightAzimuthApp):
    """Add location-aware twilight timing and twilight satellite tracking."""

    OBSERVING_REFRESH_MS = 60_000
    OBSERVING_TICK_MS = 1_000
    SUNSET_ALTITUDE_DEG = -0.8333

    def __init__(self) -> None:
        self._observing_snapshot: ObservingConditions | None = None
        self._observing_engine: ObservingConditionsEngine | None = None
        self._observing_generation = 0
        self._observing_refresh_job: str | None = None
        self._observing_tick_job: str | None = None
        super().__init__()
        self._schedule_observing_tick()

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

        self.live_view = TwilightSmoothHudFinderView(content, on_select=self._on_live_satellite_selected)
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
                "Normal mode shows fast sunlit satellite candidates in the sky section you are looking at, including "
                "civil twilight after sunset. Satellite positions are predicted every second and animated smoothly. "
                "The stricter Potential flag still requires the sky-dark threshold."
            ),
            wraplength=250,
            justify="left",
        ).pack(side="bottom", anchor="sw")

        self.observing_status_var = tk.StringVar(master=self, value="Observing conditions: waiting for location...")
        observing = ttk.LabelFrame(parent, text="Sunset and darkness", padding=(10, 6))
        observing.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        ttk.Label(
            observing,
            textvariable=self.observing_status_var,
            justify="left",
            font=("Consolas", 9),
        ).pack(anchor="w", fill="x")

        self._apply_live_view_direction(show_error=False)
        self._on_star_layer_changed()

    def _refresh_location_selector(self) -> None:
        super()._refresh_location_selector()
        if hasattr(self, "observing_status_var"):
            self._refresh_observing_conditions()

    def _on_location_changed(self, event: object | None = None) -> None:
        super()._on_location_changed(event)
        self._refresh_observing_conditions()

    def _refresh_observing_conditions(self) -> None:
        if self._observing_refresh_job is not None:
            try:
                self.after_cancel(self._observing_refresh_job)
            except tk.TclError:
                pass
            self._observing_refresh_job = None

        profile = self._selected_profile()
        if profile is None:
            self._observing_snapshot = None
            if hasattr(self, "observing_status_var"):
                self.observing_status_var.set("Observing conditions: no location configured.")
            return

        self._observing_generation += 1
        generation = self._observing_generation
        profile_key = (profile.name, profile.latitude, profile.longitude, profile.altitude_m)
        if hasattr(self, "observing_status_var") and self._observing_snapshot is None:
            self.observing_status_var.set("Observing conditions: calculating for selected location...")

        observer = self._observer_for_profile(profile)
        threading.Thread(
            target=self._load_observing_conditions,
            args=(profile_key, observer, generation),
            daemon=True,
        ).start()
        self._observing_refresh_job = self.after(self.OBSERVING_REFRESH_MS, self._refresh_observing_conditions)

    def _load_observing_conditions(self, profile_key: tuple[object, ...], observer: object, generation: int) -> None:
        try:
            if self._observing_engine is None:
                self._observing_engine = ObservingConditionsEngine(cache_directory=self.cache_directory)
            snapshot = self._observing_engine.calculate(observer)
            self.after(0, self._apply_observing_conditions, profile_key, generation, snapshot)
        except Exception as exc:  # noqa: BLE001
            self.after(0, self._observing_conditions_failed, generation, str(exc))

    def _apply_observing_conditions(
        self,
        profile_key: tuple[object, ...],
        generation: int,
        snapshot: ObservingConditions,
    ) -> None:
        if generation != self._observing_generation:
            return
        profile = self._selected_profile()
        current_key = None if profile is None else (
            profile.name,
            profile.latitude,
            profile.longitude,
            profile.altitude_m,
        )
        if current_key != profile_key:
            return
        self._observing_snapshot = snapshot
        self._update_observing_status_text()

    def _observing_conditions_failed(self, generation: int, _error: str) -> None:
        if generation != self._observing_generation:
            return
        self._observing_snapshot = None
        if hasattr(self, "observing_status_var"):
            self.observing_status_var.set("Observing conditions: calculation unavailable.")

    def _schedule_observing_tick(self) -> None:
        if self._observing_tick_job is None:
            self._observing_tick_job = self.after(self.OBSERVING_TICK_MS, self._observing_tick)

    def _observing_tick(self) -> None:
        self._observing_tick_job = None
        self._update_observing_status_text()
        self._schedule_observing_tick()

    def _update_observing_status_text(self) -> None:
        if not hasattr(self, "observing_status_var"):
            return
        snapshot = self._observing_snapshot
        if snapshot is None:
            return

        now = datetime.now(timezone.utc)
        state = snapshot.sky_state_code
        lines = [
            f"Sky: {snapshot.sky_state_name:<24}  Sun altitude: {snapshot.sun_altitude_deg:+6.2f}°  Time zone: {snapshot.timezone_name}",
            self._observing_event_line("Sunset", snapshot.sunset_utc, now, reached=state < 4, snapshot=snapshot),
            self._observing_event_line(
                "Civil twilight ends",
                snapshot.civil_twilight_end_utc,
                now,
                reached=state <= 2,
                snapshot=snapshot,
            ),
            self._observing_event_line(
                "Nautical twilight ends",
                snapshot.nautical_twilight_end_utc,
                now,
                reached=state <= 1,
                snapshot=snapshot,
            ),
            self._observing_event_line(
                "Complete darkness",
                snapshot.astronomical_darkness_utc,
                now,
                reached=state == 0,
                snapshot=snapshot,
            ),
        ]
        self.observing_status_var.set("\n".join(lines))

    @staticmethod
    def _observing_event_line(
        label: str,
        event_utc: datetime | None,
        now: datetime,
        *,
        reached: bool,
        snapshot: ObservingConditions,
    ) -> str:
        local = snapshot.local_time(event_utc)
        local_text = "--:--:--" if local is None else local.strftime("%H:%M:%S")
        countdown = format_countdown(event_utc, now, reached=reached)
        return f"{label:<24} {local_text}  {countdown}"

    def _load_tracking_data(self, profile: LocationProfile) -> None:
        try:
            observer = self._observer_for_profile(profile)
            client = CelestrakClient(cache_directory=self.cache_directory, cache_max_age_minutes=120)
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
                twilight_candidate = (
                    status.satellite_sunlit
                    and -6.0 < status.sun_altitude_deg <= self.SUNSET_ALTITUDE_DEG
                )
                satellite = SkySatellite(
                    name=item.name,
                    norad_id=item.norad_id,
                    azimuth_deg=item.azimuth_deg,
                    elevation_deg=item.elevation_deg,
                    range_km=item.range_km,
                    satellite_sunlit=status.satellite_sunlit,
                    sky_dark=status.sky_dark,
                    potentially_visible=status.potentially_visible,
                    twilight_candidate=twilight_candidate,
                    phase_angle_deg=status.phase_angle_deg,
                    brightness_estimate=(
                        estimate_supported_satellite(
                            item.name,
                            range_km=item.range_km,
                            phase_angle_deg=status.phase_angle_deg,
                        )
                        if status.satellite_sunlit
                        else None
                    ),
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

            self.after(0, self._apply_tracking_data, profile.name, live_rows, pass_rows, sky_satellites)
        except (CelestrakError, OSError, ValueError) as exc:
            self.after(0, self._show_refresh_error, str(exc))
        except Exception as exc:  # noqa: BLE001
            self.after(0, self._show_refresh_error, f"Unexpected error: {exc}")

    def _start_track_prediction(
        self,
        profile_name: str,
        satellites: list[SkySatellite],
        generation: int,
    ) -> None:
        if not satellites or not hasattr(self, "live_view"):
            return

        in_view = [
            satellite
            for satellite in satellites
            if is_live_observing_candidate(satellite)
            and project_live_view(
                satellite.azimuth_deg,
                satellite.elevation_deg,
                self.live_view.facing_deg,
                self.live_view.horizontal_fov_deg,
                minimum_elevation_deg=self.live_view.minimum_elevation_deg,
                maximum_elevation_deg=self.live_view.maximum_elevation_deg,
            ).visible
        ]
        pool = in_view or [satellite for satellite in satellites if is_live_observing_candidate(satellite)] or satellites
        candidates = sorted(pool, key=lambda satellite: (satellite.range_km, -satellite.elevation_deg))[
            : self.LIVE_TRACK_LIMIT
        ]
        super(Stage13NightAzimuthApp, self)._start_track_prediction(profile_name, candidates, generation)

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
            relevant = [fields for fields in elements if str(fields.get("NORAD_CAT_ID") or "") in wanted_ids]
            tracks = TrackPredictor(observer).predict(
                relevant,
                duration_seconds=180,
                step_seconds=1,
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
            updated = [replace(satellite, future_track=tracks.get(satellite.norad_id, ())) for satellite in current_satellites]
            self._sky_satellites = updated
            self.live_view.set_satellites(updated)
            self.live_view.set_show_all_tracked(self.show_all_tracked_var.get())
            if selected_norad is not None:
                selected = next((satellite for satellite in updated if satellite.norad_id == selected_norad), None)
                if selected is not None:
                    self._on_live_satellite_selected(selected)
        self._start_pending_track_prediction()

    def _update_live_view_summary(self) -> None:
        if not hasattr(self, "live_view"):
            return
        all_status = "On" if getattr(self, "show_all_tracked_var", None) and self.show_all_tracked_var.get() else "Off"
        self.live_detail_var.set(
            f"Facing {self.live_view.facing_deg:.0f}°\n"
            f"Horizontal FOV: {self.live_view.horizontal_fov_deg:.0f}°\n"
            f"Elevation: {self.live_view.minimum_elevation_deg:.0f}–{self.live_view.maximum_elevation_deg:.0f}°\n\n"
            "Fast-mover live mode\n"
            "VEGA = blue-white reference\n"
            "Yellow = named planet\n"
            "Green = sunlit twilight/dark-sky satellite candidate\n"
            "1-second orbital samples + 20 fps interpolation = smooth marker motion\n"
            "Satellite label includes apparent angular speed when a track is available\n"
            "Thin path = predicted movement\n"
            f"All tracked: {all_status}\n\n"
            "Potential remains the stricter sunlit + dark-sky indicator."
        )


def main() -> int:
    app = Stage14NightAzimuthApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
