from __future__ import annotations

from datetime import datetime, timezone
import threading
import tkinter as tk
from tkinter import ttk

from PIL import ImageTk

from .directional_cloud_hud import DirectionalCloudHudFinderView
from .gui_stage15 import Stage15NightAzimuthApp
from .observing_planner import ObservingPlanner, ViewingGuidance
from .weather import WeatherSnapshot
from .weather_map_stage16 import Stage16WeatherMapRenderer, Stage16WeatherMapSnapshot


class Stage16NightAzimuthApp(Stage15NightAzimuthApp):
    """Add free spatial cloud imagery and 12–24 hour observing guidance."""

    CLOUD_REFRESH_MS = 5 * 60 * 1000
    CLOUD_STALE_MINUTES = 25
    MAP_TIME_CHOICES = {
        "Now": 0,
        "+1 hour": 1,
        "+3 hours": 3,
        "+6 hours": 6,
        "+9 hours": 9,
        "+12 hours": 12,
        "+18 hours": 18,
        "+24 hours": 24,
    }

    def __init__(self) -> None:
        self._stage16_weather_map_renderer: Stage16WeatherMapRenderer | None = None
        self._planner_generation = 0
        self._planner_rows: tuple[ViewingGuidance, ...] = ()
        self._cloud_refresh_job: str | None = None
        self._cloud_frame_lookup: dict[str, datetime | None] = {"Latest": None}
        super().__init__()
        if hasattr(self, "weather_map_status_var"):
            self._refresh_weather_map()
        self._schedule_cloud_refresh()

    def _build_live_view(self, parent: ttk.Frame) -> None:
        super()._build_live_view(parent)
        old_view = self.live_view
        master = old_view.master
        old_view.destroy()
        self.live_view = DirectionalCloudHudFinderView(master, on_select=self._on_live_satellite_selected)
        self.live_view.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self._apply_live_view_direction(show_error=False)
        self._on_star_layer_changed()

        self.show_cloud_overlay_var = tk.BooleanVar(master=self, value=False)
        checkbox = _find_checkbutton(parent, "Cloud overlay (Stage 16)")
        if checkbox is not None:
            checkbox.configure(
                text="Cloud overlay",
                state="normal",
                variable=self.show_cloud_overlay_var,
                command=self._on_cloud_overlay_changed,
            )

        controls = next((item for item in parent.grid_slaves(row=0, column=0) if isinstance(item, ttk.Frame)), None)
        if controls is not None:
            ttk.Label(controls, text="Cloud opacity:").pack(side="left", padx=(10, 4))
            self.cloud_opacity_var = tk.DoubleVar(master=self, value=45.0)
            ttk.Scale(
                controls,
                from_=10.0,
                to=90.0,
                orient="horizontal",
                length=90,
                variable=self.cloud_opacity_var,
                command=self._on_cloud_opacity_changed,
            ).pack(side="left")

    def _build_weather_map(self, parent: ttk.Frame) -> None:
        super()._build_weather_map(parent)
        self.show_cloud_map_var = tk.BooleanVar(master=self, value=True)
        checkbox = _find_checkbutton(parent, "Cloud imagery (Stage 16)")
        if checkbox is not None:
            checkbox.configure(
                text="Cloud imagery",
                state="normal",
                variable=self.show_cloud_map_var,
                command=self._refresh_weather_map,
            )

        controls = next((item for item in parent.grid_slaves(row=0, column=0) if isinstance(item, ttk.Frame)), None)
        if controls is not None:
            ttk.Label(controls, text="Map time:").pack(side="left", padx=(12, 4))
            self.map_time_var = tk.StringVar(master=self, value="Now")
            map_time = ttk.Combobox(
                controls,
                textvariable=self.map_time_var,
                state="readonly",
                width=10,
                values=tuple(self.MAP_TIME_CHOICES),
            )
            map_time.pack(side="left")
            map_time.bind("<<ComboboxSelected>>", self._on_map_time_selected)

            ttk.Label(controls, text="Cloud frame:").pack(side="left", padx=(12, 4))
            self.cloud_frame_var = tk.StringVar(master=self, value="Latest")
            self.cloud_frame_combo = ttk.Combobox(
                controls,
                textvariable=self.cloud_frame_var,
                state="readonly",
                width=17,
                values=("Latest",),
            )
            self.cloud_frame_combo.pack(side="left")
            self.cloud_frame_combo.bind("<<ComboboxSelected>>", self._on_cloud_frame_selected)

        self.planner_status_var = tk.StringVar(
            master=self,
            value="24-hour observing planner: waiting for weather and location...",
        )
        planner = ttk.LabelFrame(parent, text="12–24 hour observing planner", padding=(10, 6))
        planner.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        ttk.Label(
            planner,
            textvariable=self.planner_status_var,
            justify="left",
            font=("Consolas", 9),
        ).pack(anchor="w", fill="x")

    def _schedule_cloud_refresh(self) -> None:
        if self._cloud_refresh_job is not None:
            try:
                self.after_cancel(self._cloud_refresh_job)
            except tk.TclError:
                pass
        self._cloud_refresh_job = self.after(self.CLOUD_REFRESH_MS, self._cloud_refresh_tick)

    def _cloud_refresh_tick(self) -> None:
        self._cloud_refresh_job = None
        if self._selected_forecast_hours() == 0 and (
            getattr(self, "cloud_frame_var", None) is None or self.cloud_frame_var.get() == "Latest"
        ):
            self._refresh_weather_map()
        self._schedule_cloud_refresh()

    def _on_map_time_selected(self, _event: object | None = None) -> None:
        future = self._selected_forecast_hours() > 0
        if hasattr(self, "cloud_frame_combo"):
            self.cloud_frame_combo.configure(state="disabled" if future else "readonly")
        self._refresh_weather_map()

    def _selected_forecast_hours(self) -> int:
        if not hasattr(self, "map_time_var"):
            return 0
        return self.MAP_TIME_CHOICES.get(self.map_time_var.get(), 0)

    def _on_cloud_frame_selected(self, _event: object | None = None) -> None:
        if self._selected_forecast_hours() == 0:
            self._refresh_weather_map()

    def _selected_cloud_time(self) -> datetime | None:
        if not hasattr(self, "cloud_frame_var"):
            return None
        return self._cloud_frame_lookup.get(self.cloud_frame_var.get())

    def _apply_live_view_direction(self, *, show_error: bool = True) -> None:
        super()._apply_live_view_direction(show_error=show_error)
        if hasattr(self, "weather_map_status_var"):
            self._refresh_weather_map()

    def _on_cloud_overlay_changed(self) -> None:
        if hasattr(self, "live_view") and isinstance(self.live_view, DirectionalCloudHudFinderView):
            self.live_view.set_cloud_overlay_enabled(self.show_cloud_overlay_var.get())
        self._update_live_view_summary()

    def _on_cloud_opacity_changed(self, _value: object | None = None) -> None:
        if hasattr(self, "live_view") and isinstance(self.live_view, DirectionalCloudHudFinderView):
            self.live_view.set_cloud_opacity(float(self.cloud_opacity_var.get()) / 100.0)

    def _apply_weather(self, profile_key: tuple[object, ...], generation: int, snapshot: WeatherSnapshot) -> None:
        super()._apply_weather(profile_key, generation, snapshot)
        if generation == self._weather_generation:
            self._refresh_observing_planner(snapshot)

    def _refresh_observing_planner(self, snapshot: WeatherSnapshot | None = None) -> None:
        if not hasattr(self, "planner_status_var"):
            return
        profile = self._selected_profile()
        weather = snapshot or self._weather_snapshot
        if profile is None or weather is None:
            self._planner_rows = ()
            self.planner_status_var.set("24-hour observing planner: waiting for weather and location...")
            return
        self._planner_generation += 1
        generation = self._planner_generation
        profile_key = (profile.name, profile.latitude, profile.longitude, profile.altitude_m)
        self.planner_status_var.set("Calculating 24-hour viewing guidance...")
        observer = self._observer_for_profile(profile)
        threading.Thread(
            target=self._load_observing_planner,
            args=(profile_key, observer, weather, generation),
            daemon=True,
        ).start()

    def _load_observing_planner(
        self,
        profile_key: tuple[object, ...],
        observer: object,
        weather: WeatherSnapshot,
        generation: int,
    ) -> None:
        try:
            rows = ObservingPlanner(observer, cache_directory=self.cache_directory).build(
                weather,
                hours=24,
                now_utc=datetime.now(timezone.utc),
            )
            self.after(0, self._apply_observing_planner, profile_key, generation, rows)
        except Exception:  # noqa: BLE001
            self.after(0, self._planner_failed, generation)

    def _apply_observing_planner(
        self,
        profile_key: tuple[object, ...],
        generation: int,
        rows: tuple[ViewingGuidance, ...],
    ) -> None:
        if generation != self._planner_generation:
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
        self._planner_rows = rows
        self.planner_status_var.set(self._format_planner(rows))

    def _planner_failed(self, generation: int) -> None:
        if generation == self._planner_generation:
            self._planner_rows = ()
            self.planner_status_var.set("24-hour observing planner unavailable.")

    def _format_planner(self, rows: tuple[ViewingGuidance, ...]) -> str:
        if not rows:
            return "No hourly forecast points are currently available."
        good = [row for row in rows if row.rating in {"Very good", "Good"}]
        if good:
            first = self._planner_local_time(good[0].time_utc)
            last = self._planner_local_time(good[-1].time_utc)
            headline = f"Best useful window in available forecast: {first}–{last}"
        else:
            headline = "No Good/Very good viewing window in the available forecast."
        lines = [headline, "Time   Rating      Conf.          Cloud  Rain   Sun alt"]
        for row in rows[::2][:12]:
            stamp = self._planner_local_time(row.time_utc)
            cloud = "--" if row.cloud_percent is None else f"{row.cloud_percent:.0f}%"
            rain = "--" if row.precipitation_mm is None else f"{row.precipitation_mm:.1f}mm"
            lines.append(
                f"{stamp:<5}  {row.rating:<10}  {row.confidence:<13}  {cloud:>5}  {rain:>5}  {row.sun_altitude_deg:>+6.1f}°"
            )
        lines.append(
            "Guidance is transparent: darkness + point cloud + fog + precipitation. "
            "Future cloud edges are forecast, not future satellite/radar observations."
        )
        return "\n".join(lines)

    def _planner_local_time(self, moment: datetime) -> str:
        if self._observing_snapshot is not None:
            local = self._observing_snapshot.local_time(moment)
            if local is not None:
                return local.strftime("%H:%M")
        return moment.strftime("%H:%M")

    def _refresh_weather_map(self) -> None:
        if not hasattr(self, "weather_map_status_var"):
            return
        profile = self._selected_profile()
        if profile is None:
            self._weather_map_generation += 1
            self._weather_map_photo = None
            self.weather_map_label.configure(image="")
            self.weather_map_status_var.set("No location configured. Open Settings to add one.")
            if hasattr(self, "live_view") and isinstance(self.live_view, DirectionalCloudHudFinderView):
                self.live_view.set_cloud_region(None)
            return

        self._weather_map_generation += 1
        generation = self._weather_map_generation
        profile_key = (profile.name, profile.latitude, profile.longitude, profile.altitude_m)
        forecast_hours = self._selected_forecast_hours()
        show_radar = bool(self.show_radar_var.get()) if hasattr(self, "show_radar_var") else True
        show_cloud = bool(self.show_cloud_map_var.get()) if hasattr(self, "show_cloud_map_var") else True
        facing = float(self.live_view.facing_deg) if hasattr(self, "live_view") else 0.0
        fov = float(self.live_view.horizontal_fov_deg) if hasattr(self, "live_view") else 90.0
        requested_cloud_time = self._selected_cloud_time()
        if forecast_hours:
            self.weather_map_status_var.set(f"Loading +{forecast_hours}h spatial cloud/rain forecast...")
        else:
            self.weather_map_status_var.set("Loading map, rain radar and timestamped spatial cloud imagery...")
        observer = self._observer_for_profile(profile)
        threading.Thread(
            target=self._load_stage16_weather_map,
            args=(
                profile_key,
                observer,
                show_radar,
                show_cloud,
                facing,
                fov,
                requested_cloud_time,
                forecast_hours,
                generation,
            ),
            daemon=True,
        ).start()

    def _load_stage16_weather_map(
        self,
        profile_key: tuple[object, ...],
        observer: object,
        show_radar: bool,
        show_cloud: bool,
        facing_deg: float,
        horizontal_fov_deg: float,
        cloud_time_utc: datetime | None,
        forecast_hours: int,
        generation: int,
    ) -> None:
        try:
            if self._stage16_weather_map_renderer is None:
                self._stage16_weather_map_renderer = Stage16WeatherMapRenderer(cache_directory=self.cache_directory)
            snapshot = self._stage16_weather_map_renderer.render_stage16(
                observer,
                show_radar=show_radar,
                show_cloud=show_cloud,
                zoom=7,
                radius_tiles=1,
                facing_deg=facing_deg,
                horizontal_fov_deg=horizontal_fov_deg,
                cloud_time_utc=cloud_time_utc,
                forecast_hours_ahead=forecast_hours,
            )
            self.after(0, self._apply_stage16_weather_map, profile_key, observer, generation, snapshot)
        except Exception:  # noqa: BLE001
            self.after(0, self._weather_map_failed, generation)

    def _apply_stage16_weather_map(
        self,
        profile_key: tuple[object, ...],
        observer: object,
        generation: int,
        snapshot: Stage16WeatherMapSnapshot,
    ) -> None:
        if generation != self._weather_map_generation:
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

        self._weather_map_photo = ImageTk.PhotoImage(snapshot.image)
        self.weather_map_label.configure(image=self._weather_map_photo)
        if snapshot.recent_cloud_times_utc:
            self._update_cloud_frame_choices(snapshot.recent_cloud_times_utc)

        if snapshot.forecast_hours_ahead > 0:
            valid = (
                snapshot.forecast_valid_time_utc.strftime("%Y-%m-%d %H:%M UTC")
                if snapshot.forecast_valid_time_utc is not None
                else "unknown"
            )
            self.weather_map_status_var.set(
                f"FORECAST +{snapshot.forecast_hours_ahead}h — valid {valid}\n"
                "Spatial cloud/rain field: MET Norway Locationforecast sampled across the displayed map.\n"
                "Rain radar and current EUMETSAT satellite imagery are intentionally hidden in future mode.\n"
                "This is a model forecast for planning, not an exact prediction of future cloud edges."
            )
            return

        if snapshot.radar_enabled and snapshot.radar_time_utc is not None:
            radar_text = f"Rain radar: {snapshot.radar_time_utc.strftime('%Y-%m-%d %H:%M UTC')}"
        elif snapshot.radar_enabled:
            radar_text = "Rain radar requested, but no frame was available."
        else:
            radar_text = "Rain radar: off"

        cloud_text = self._cloud_status_text(snapshot)
        self.weather_map_status_var.set(
            f"Selected location centred on map.\n{radar_text}\n{cloud_text}\n"
            "Green wedge = current Live-view facing/FOV. Use Cloud frame to step backward through recent satellite frames and see movement.\n"
            "Use Map time for +1 to +24 hour model forecast frames. Live cloud elevation alignment remains an estimate."
        )

        if hasattr(self, "live_view") and isinstance(self.live_view, DirectionalCloudHudFinderView):
            self.live_view.set_cloud_region(
                snapshot.cloud_region,
                observer_latitude=observer.latitude,
                observer_longitude=observer.longitude,
            )
            self.live_view.set_cloud_overlay_enabled(
                bool(self.show_cloud_overlay_var.get()) if hasattr(self, "show_cloud_overlay_var") else False
            )
            if hasattr(self, "cloud_opacity_var"):
                self.live_view.set_cloud_opacity(float(self.cloud_opacity_var.get()) / 100.0)

    def _update_cloud_frame_choices(self, values: tuple[datetime, ...]) -> None:
        lookup: dict[str, datetime | None] = {"Latest": None}
        now = datetime.now(timezone.utc)
        for value in reversed(values):
            minutes = max(0, int((now - value).total_seconds() // 60))
            label = f"{value.strftime('%H:%M UTC')}  (-{minutes}m)"
            lookup[label] = value
        self._cloud_frame_lookup = lookup
        if hasattr(self, "cloud_frame_combo"):
            self.cloud_frame_combo.configure(values=tuple(lookup))
            if self.cloud_frame_var.get() not in lookup:
                self.cloud_frame_var.set("Latest")

    def _cloud_status_text(self, snapshot: Stage16WeatherMapSnapshot) -> str:
        if not snapshot.cloud_enabled:
            return "Cloud imagery: off"
        source = "cache" if snapshot.cloud_from_cache else "live"
        if snapshot.cloud_time_utc is None:
            return f"Cloud imagery: EUMETView ({source}); exact provider frame time unavailable"
        age_minutes = max(0, int((datetime.now(timezone.utc) - snapshot.cloud_time_utc).total_seconds() // 60))
        stale = "  WARNING: stale frame" if age_minutes > self.CLOUD_STALE_MINUTES else ""
        return (
            f"Cloud imagery: EUMETView ({source})  Frame {snapshot.cloud_time_utc.strftime('%Y-%m-%d %H:%M UTC')}  "
            f"Age {age_minutes} min{stale}"
        )

    def _update_live_view_summary(self) -> None:
        super()._update_live_view_summary()
        if not hasattr(self, "live_detail_var"):
            return
        enabled = bool(getattr(self, "show_cloud_overlay_var", None) and self.show_cloud_overlay_var.get())
        state = "On" if enabled else "Off"
        opacity = int(self.cloud_opacity_var.get()) if hasattr(self, "cloud_opacity_var") else 45
        self.live_detail_var.set(
            self.live_detail_var.get()
            + f"\nCloud overlay: {state} ({opacity}% opacity)\n"
            + "Compass cues show N/NE/E/SE/S/SW/W/NW where they fall inside the current field of view.\n"
            + "Cloud alignment is an estimate from Meteosat imagery using an assumed representative cloud altitude."
        )


def _find_checkbutton(widget: tk.Misc, text: str) -> ttk.Checkbutton | None:
    for child in widget.winfo_children():
        if isinstance(child, ttk.Checkbutton) and str(child.cget("text")) == text:
            return child
        nested = _find_checkbutton(child, text)
        if nested is not None:
            return nested
    return None


def main() -> int:
    app = Stage16NightAzimuthApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
