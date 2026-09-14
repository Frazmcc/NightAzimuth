from __future__ import annotations

from datetime import datetime, timedelta, timezone
import threading
import tkinter as tk
from tkinter import ttk

from .gui_stage16 import Stage16NightAzimuthApp
from .observing_planner import ObservingPlanner, ViewingGuidance
from .weather import WeatherSnapshot
from .weather_map_stage16 import Stage16WeatherMapRenderer


class AnimatedStage16NightAzimuthApp(Stage16NightAzimuthApp):
    """Stage 16 weather map with observed radar/cloud history plus longer planning."""

    MAP_TIME_CHOICES = {
        "Now": 0,
        "+1 hour": 1,
        "+2 hours": 2,
        "+3 hours": 3,
        "+4 hours": 4,
        "+5 hours": 5,
        "+6 hours": 6,
        "+9 hours": 9,
        "+12 hours": 12,
        "+18 hours": 18,
        "+24 hours": 24,
    }
    # Observed history only. Forecast data is deliberately excluded from this
    # timeline so radar/cloud playback cannot be mistaken for future radar.
    WEATHER_TIMELINE_MINUTES = tuple(range(-24 * 60, 1, 60))
    ANIMATION_INTERVAL_MS = 1800
    LIVE_ORBIT_REFRESH_MS = 120_000

    def __init__(self) -> None:
        self._weather_animation_job: str | None = None
        self._weather_animation_playing = False
        self._weather_animation_step_index = 0
        self._seven_day_generation = 0
        self._seven_day_rows_by_label: dict[str, tuple[ViewingGuidance, ...]] = {}
        super().__init__()
        # Projected satellite tracks cover three minutes. Refresh the orbital
        # solution in the background before that window expires instead of
        # rebuilding the Live view every few seconds.
        self._auto_refresh_ms = self.LIVE_ORBIT_REFRESH_MS

    def _build_weather_map(self, parent: ttk.Frame) -> None:
        super()._build_weather_map(parent)

        self.weather_animation_status_var = tk.StringVar(
            master=self,
            value="OBSERVED 24h ago — automatic history loop loading...",
        )
        details_candidates = [
            item
            for item in parent.grid_slaves(row=1, column=1)
            if isinstance(item, ttk.LabelFrame)
        ]
        if details_candidates:
            details = details_candidates[0]
            ttk.Separator(details, orient="horizontal").pack(side="bottom", fill="x", pady=(8, 6))
            ttk.Label(
                details,
                textvariable=self.weather_animation_status_var,
                wraplength=280,
                justify="left",
                font=("Segoe UI", 9, "bold"),
            ).pack(side="bottom", anchor="sw", fill="x")
        self.after_idle(self._start_weather_animation)

        seven_day = ttk.LabelFrame(parent, text="7-day observing planner", padding=(10, 6))
        seven_day.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        seven_day.columnconfigure(1, weight=1)
        seven_day.rowconfigure(2, weight=1)

        ttk.Label(seven_day, text="Day:").grid(row=0, column=0, sticky="w", padx=(0, 6))
        self.seven_day_day_var = tk.StringVar(master=self, value="")
        self.seven_day_day_combo = ttk.Combobox(
            seven_day,
            textvariable=self.seven_day_day_var,
            state="readonly",
            width=22,
            values=(),
        )
        self.seven_day_day_combo.grid(row=0, column=1, sticky="w")
        self.seven_day_day_combo.bind("<<ComboboxSelected>>", self._on_seven_day_day_selected)

        self.seven_day_status_var = tk.StringVar(
            master=self,
            value="Waiting for the 7-day weather forecast...",
        )
        ttk.Label(
            seven_day,
            textvariable=self.seven_day_status_var,
            justify="left",
        ).grid(row=1, column=0, columnspan=3, sticky="ew", pady=(5, 5))

        columns = ("time", "rating", "confidence", "cloud", "fog", "rain", "sun")
        self.seven_day_tree = ttk.Treeview(
            seven_day,
            columns=columns,
            show="headings",
            height=11,
        )
        headings = {
            "time": "Time",
            "rating": "Rating",
            "confidence": "Confidence",
            "cloud": "Cloud",
            "fog": "Fog",
            "rain": "Rain",
            "sun": "Sun altitude",
        }
        widths = {
            "time": 70,
            "rating": 95,
            "confidence": 110,
            "cloud": 70,
            "fog": 65,
            "rain": 70,
            "sun": 90,
        }
        for column in columns:
            self.seven_day_tree.heading(column, text=headings[column])
            self.seven_day_tree.column(column, width=widths[column], anchor="center")
        self.seven_day_tree.grid(row=2, column=0, columnspan=2, sticky="nsew")
        seven_scroll = ttk.Scrollbar(seven_day, orient="vertical", command=self.seven_day_tree.yview)
        seven_scroll.grid(row=2, column=2, sticky="ns")
        self.seven_day_tree.configure(yscrollcommand=seven_scroll.set)

        ttk.Label(
            seven_day,
            text=(
                "Shows the actual forecast intervals supplied by MET Norway. "
                "Hourly rows are shown where available; later forecast days may use wider provider intervals rather than invented interpolation."
            ),
            wraplength=1150,
            justify="left",
        ).grid(row=3, column=0, columnspan=3, sticky="w", pady=(5, 0))

    def _start_weather_animation(self) -> None:
        """Start or resume automatic observed-history playback."""

        if self._selected_forecast_hours() > 0:
            return
        self._weather_animation_playing = True
        self._schedule_weather_animation_tick()

    def _suspend_weather_animation(self) -> None:
        self._weather_animation_playing = False
        if self._weather_animation_job is not None:
            try:
                self.after_cancel(self._weather_animation_job)
            except tk.TclError:
                pass
            self._weather_animation_job = None

    def _schedule_weather_animation_tick(self) -> None:
        if not self._weather_animation_playing or self._weather_animation_job is not None:
            return
        self._weather_animation_job = self.after(
            self.ANIMATION_INTERVAL_MS,
            self._weather_animation_tick,
        )

    def _weather_animation_tick(self) -> None:
        self._weather_animation_job = None
        if not self._weather_animation_playing:
            return
        next_index = next_weather_timeline_index(
            self._weather_animation_step_index,
            len(self.WEATHER_TIMELINE_MINUTES),
        )
        # The following tick is scheduled only after this frame is applied (or
        # fails), preventing slow downloads from creating a render backlog.
        self._set_weather_animation_index(next_index, refresh=True)

    def _set_weather_animation_index(self, index: int, *, refresh: bool) -> None:
        index = max(0, min(len(self.WEATHER_TIMELINE_MINUTES) - 1, int(index)))
        self._weather_animation_step_index = index
        if hasattr(self, "map_time_var"):
            self.map_time_var.set("Now")
        if hasattr(self, "cloud_frame_combo"):
            self.cloud_frame_combo.configure(state="readonly")
        minutes = self.WEATHER_TIMELINE_MINUTES[index]
        self._set_animation_status(minutes)
        if refresh:
            self._refresh_weather_map()

    def _set_animation_status(self, minutes: int) -> None:
        if not hasattr(self, "weather_animation_status_var"):
            return
        if minutes < 0:
            hours = abs(minutes) // 60
            self.weather_animation_status_var.set(
                f"OBSERVED {hours}h ago — EUMETSAT cloud + actual rain radar when that historical radar frame is available"
            )
        else:
            self.weather_animation_status_var.set("NOW — latest observed EUMETSAT cloud + rain radar")

    def _animation_minutes(self) -> int:
        return self.WEATHER_TIMELINE_MINUTES[self._weather_animation_step_index]

    def _on_map_time_selected(self, _event: object | None = None) -> None:
        future = self._selected_forecast_hours() > 0
        if hasattr(self, "cloud_frame_combo"):
            self.cloud_frame_combo.configure(state="disabled" if future else "readonly")
        self._suspend_weather_animation()
        if future:
            Stage16NightAzimuthApp._refresh_weather_map(self)
        else:
            self._weather_animation_step_index = 0
            self._set_animation_status(self._animation_minutes())
            self._refresh_weather_map()
            self._start_weather_animation()

    def _refresh_weather_map(self) -> None:
        if not hasattr(self, "weather_animation_status_var"):
            super()._refresh_weather_map()
            return
        if not hasattr(self, "weather_map_status_var"):
            return
        profile = self._selected_profile()
        if profile is None:
            super()._refresh_weather_map()
            return
        if self._selected_forecast_hours() > 0:
            Stage16NightAzimuthApp._refresh_weather_map(self)
            return

        minutes = self._animation_minutes()
        self._weather_map_generation += 1
        generation = self._weather_map_generation
        profile_key = (profile.name, profile.latitude, profile.longitude, profile.altitude_m)
        show_radar = bool(self.show_radar_var.get()) if hasattr(self, "show_radar_var") else True
        show_cloud = bool(self.show_cloud_map_var.get()) if hasattr(self, "show_cloud_map_var") else True
        facing = float(self.live_view.facing_deg) if hasattr(self, "live_view") else 0.0
        fov = float(self.live_view.horizontal_fov_deg) if hasattr(self, "live_view") else 90.0
        observer = self._observer_for_profile(profile)

        if minutes < 0:
            requested_cloud_time = datetime.now(timezone.utc) + timedelta(minutes=minutes)
            radar_time = requested_cloud_time
            self.weather_map_status_var.set(
                f"Loading observed cloud/radar from {abs(minutes) // 60} hours ago..."
            )
        else:
            requested_cloud_time = None
            radar_time = None
            self.weather_map_status_var.set("Loading latest observed cloud and rain radar...")

        threading.Thread(
            target=self._load_animated_weather_map,
            args=(
                profile_key,
                observer,
                show_radar,
                show_cloud,
                facing,
                fov,
                requested_cloud_time,
                radar_time,
                generation,
            ),
            daemon=True,
        ).start()

    def _load_animated_weather_map(
        self,
        profile_key: tuple[object, ...],
        observer: object,
        show_radar: bool,
        show_cloud: bool,
        facing_deg: float,
        horizontal_fov_deg: float,
        cloud_time_utc: datetime | None,
        radar_time_utc: datetime | None,
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
                radar_time_utc=radar_time_utc,
                forecast_hours_ahead=0,
            )
            self.after(0, self._apply_stage16_weather_map, profile_key, observer, generation, snapshot)
        except Exception:  # noqa: BLE001
            self.after(0, self._weather_map_failed, generation)

    def _apply_stage16_weather_map(
        self,
        profile_key: tuple[object, ...],
        observer: object,
        generation: int,
        snapshot: object,
    ) -> None:
        super()._apply_stage16_weather_map(profile_key, observer, generation, snapshot)
        if generation == self._weather_map_generation and self._weather_animation_playing:
            self._schedule_weather_animation_tick()

    def _weather_map_failed(self, generation: int) -> None:
        super()._weather_map_failed(generation)
        if generation == self._weather_map_generation and self._weather_animation_playing:
            self._schedule_weather_animation_tick()

    def _apply_weather(
        self,
        profile_key: tuple[object, ...],
        generation: int,
        snapshot: WeatherSnapshot,
    ) -> None:
        super()._apply_weather(profile_key, generation, snapshot)
        if generation == self._weather_generation:
            self._refresh_seven_day_planner(snapshot)

    def _refresh_seven_day_planner(self, snapshot: WeatherSnapshot | None = None) -> None:
        if not hasattr(self, "seven_day_status_var"):
            return
        profile = self._selected_profile()
        weather = snapshot or self._weather_snapshot
        if profile is None or weather is None:
            self._seven_day_rows_by_label = {}
            self.seven_day_status_var.set("Waiting for the 7-day weather forecast...")
            return

        self._seven_day_generation += 1
        generation = self._seven_day_generation
        profile_key = (profile.name, profile.latitude, profile.longitude, profile.altitude_m)
        self.seven_day_status_var.set("Calculating 7-day observing guidance...")
        observer = self._observer_for_profile(profile)
        threading.Thread(
            target=self._load_seven_day_planner,
            args=(profile_key, observer, weather, generation),
            daemon=True,
        ).start()

    def _load_seven_day_planner(
        self,
        profile_key: tuple[object, ...],
        observer: object,
        weather: WeatherSnapshot,
        generation: int,
    ) -> None:
        try:
            rows = ObservingPlanner(observer, cache_directory=self.cache_directory).build(
                weather,
                hours=7 * 24,
                now_utc=datetime.now(timezone.utc),
            )
            self.after(0, self._apply_seven_day_planner, profile_key, generation, rows)
        except Exception:  # noqa: BLE001
            self.after(0, self._seven_day_planner_failed, generation)

    def _apply_seven_day_planner(
        self,
        profile_key: tuple[object, ...],
        generation: int,
        rows: tuple[ViewingGuidance, ...],
    ) -> None:
        if generation != self._seven_day_generation:
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

        grouped: dict[str, list[ViewingGuidance]] = {}
        for row in rows:
            local = self._planner_local_datetime(row.time_utc)
            label = local.strftime("%A %d %b")
            grouped.setdefault(label, []).append(row)

        self._seven_day_rows_by_label = {
            label: tuple(day_rows)
            for label, day_rows in grouped.items()
        }
        labels = tuple(self._seven_day_rows_by_label)
        self.seven_day_day_combo.configure(values=labels)
        current = self.seven_day_day_var.get()
        if current not in self._seven_day_rows_by_label:
            self.seven_day_day_var.set(labels[0] if labels else "")
        self._render_seven_day_day()

    def _seven_day_planner_failed(self, generation: int) -> None:
        if generation != self._seven_day_generation:
            return
        self._seven_day_rows_by_label = {}
        self.seven_day_status_var.set("7-day observing planner unavailable.")
        for item in self.seven_day_tree.get_children():
            self.seven_day_tree.delete(item)

    def _on_seven_day_day_selected(self, _event: object | None = None) -> None:
        self._render_seven_day_day()

    def _render_seven_day_day(self) -> None:
        if not hasattr(self, "seven_day_tree"):
            return
        for item in self.seven_day_tree.get_children():
            self.seven_day_tree.delete(item)

        label = self.seven_day_day_var.get()
        rows = self._seven_day_rows_by_label.get(label, ())
        if not rows:
            self.seven_day_status_var.set("No forecast points are available for this day.")
            return

        good = [row for row in rows if row.rating in {"Very good", "Good"}]
        if good:
            first = self._planner_local_datetime(good[0].time_utc).strftime("%H:%M")
            last = self._planner_local_datetime(good[-1].time_utc).strftime("%H:%M")
            headline = f"{label}: best useful forecast window {first}–{last}."
        else:
            headline = f"{label}: no Good/Very good viewing window in the available forecast."
        self.seven_day_status_var.set(headline)

        for row in rows:
            local = self._planner_local_datetime(row.time_utc)
            cloud = "--" if row.cloud_percent is None else f"{row.cloud_percent:.0f}%"
            fog = "--" if row.fog_percent is None else f"{row.fog_percent:.0f}%"
            rain = "--" if row.precipitation_mm is None else f"{row.precipitation_mm:.1f} mm"
            self.seven_day_tree.insert(
                "",
                tk.END,
                values=(
                    local.strftime("%H:%M"),
                    row.rating,
                    row.confidence,
                    cloud,
                    fog,
                    rain,
                    f"{row.sun_altitude_deg:+.1f}°",
                ),
            )

    def _planner_local_datetime(self, moment: datetime) -> datetime:
        if self._observing_snapshot is not None:
            local = self._observing_snapshot.local_time(moment)
            if local is not None:
                return local
        return moment.astimezone(timezone.utc)


def main() -> int:
    app = AnimatedStage16NightAzimuthApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


def next_weather_timeline_index(current_index: int, frame_count: int) -> int:
    """Advance one observed frame and loop safely at the end."""

    count = max(1, int(frame_count))
    return (int(current_index) + 1) % count
