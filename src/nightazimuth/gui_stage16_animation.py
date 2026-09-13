from __future__ import annotations

from datetime import datetime, timedelta, timezone
import threading
import tkinter as tk
from tkinter import ttk

from .gui_stage16 import Stage16NightAzimuthApp
from .weather import WeatherSnapshot
from .weather_map_stage16 import Stage16WeatherMapRenderer


class AnimatedStage16NightAzimuthApp(Stage16NightAzimuthApp):
    """Stage 16 weather map with a continuous observed-to-forecast timeline."""

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
    WEATHER_TIMELINE_MINUTES = (
        -60,
        -50,
        -40,
        -30,
        -20,
        -10,
        0,
        60,
        120,
        180,
        240,
        300,
        360,
    )
    ANIMATION_INTERVAL_MS = 1800
    LIVE_ORBIT_REFRESH_MS = 120_000

    def __init__(self) -> None:
        self._weather_animation_job: str | None = None
        self._weather_animation_playing = False
        self._weather_animation_step_index = 6
        self._weather_animation_speed = 1.0
        super().__init__()
        # Projected satellite tracks cover three minutes. Refresh the orbital
        # solution in the background before that window expires instead of
        # rebuilding the Live view every few seconds.
        self._auto_refresh_ms = self.LIVE_ORBIT_REFRESH_MS

    def _build_weather_map(self, parent: ttk.Frame) -> None:
        super()._build_weather_map(parent)

        animation = ttk.LabelFrame(parent, text="Animated observing weather — last hour to next 6 hours", padding=(10, 6))
        animation.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        animation.columnconfigure(3, weight=1)

        self.weather_animation_play_button = ttk.Button(
            animation,
            text="▶ Play",
            width=9,
            command=self._toggle_weather_animation,
        )
        self.weather_animation_play_button.grid(row=0, column=0, padx=(0, 6))
        ttk.Button(animation, text="◀", width=3, command=lambda: self._step_weather_animation(-1)).grid(row=0, column=1)
        ttk.Button(animation, text="▶", width=3, command=lambda: self._step_weather_animation(1)).grid(row=0, column=2, padx=(4, 8))

        self.weather_animation_index_var = tk.IntVar(master=self, value=self._weather_animation_step_index)
        self.weather_animation_scale = tk.Scale(
            animation,
            from_=0,
            to=len(self.WEATHER_TIMELINE_MINUTES) - 1,
            orient="horizontal",
            resolution=1,
            showvalue=False,
            variable=self.weather_animation_index_var,
            command=self._on_weather_animation_scrub,
            length=520,
        )
        self.weather_animation_scale.grid(row=0, column=3, sticky="ew")

        ttk.Label(animation, text="Speed:").grid(row=0, column=4, padx=(10, 4))
        self.weather_animation_speed_var = tk.StringVar(master=self, value="1×")
        speed = ttk.Combobox(
            animation,
            state="readonly",
            width=4,
            textvariable=self.weather_animation_speed_var,
            values=("1×", "2×", "4×"),
        )
        speed.grid(row=0, column=5)
        speed.bind("<<ComboboxSelected>>", self._on_weather_animation_speed_changed)

        self.weather_animation_status_var = tk.StringVar(master=self, value="NOW — observed satellite cloud + rain radar")
        ttk.Label(
            animation,
            textvariable=self.weather_animation_status_var,
            font=("Segoe UI", 9, "bold"),
        ).grid(row=1, column=0, columnspan=6, sticky="w", pady=(6, 0))

        ttk.Label(
            animation,
            text="OBSERVED  -60m  -50  -40  -30  -20  -10  |  NOW  |  +1h  +2  +3  +4  +5  +6h  FORECAST",
            font=("Consolas", 8),
        ).grid(row=2, column=0, columnspan=6, sticky="ew", pady=(3, 0))

    def _toggle_weather_animation(self) -> None:
        if self._weather_animation_playing:
            self._stop_weather_animation()
            return
        self._weather_animation_playing = True
        self.weather_animation_play_button.configure(text="Ⅱ Pause")
        self._schedule_weather_animation_tick(immediate=True)

    def _stop_weather_animation(self) -> None:
        self._weather_animation_playing = False
        self.weather_animation_play_button.configure(text="▶ Play")
        if self._weather_animation_job is not None:
            try:
                self.after_cancel(self._weather_animation_job)
            except tk.TclError:
                pass
            self._weather_animation_job = None

    def _schedule_weather_animation_tick(self, *, immediate: bool = False) -> None:
        if not self._weather_animation_playing:
            return
        if self._weather_animation_job is not None:
            try:
                self.after_cancel(self._weather_animation_job)
            except tk.TclError:
                pass
        delay = 1 if immediate else max(250, int(self.ANIMATION_INTERVAL_MS / self._weather_animation_speed))
        self._weather_animation_job = self.after(delay, self._weather_animation_tick)

    def _weather_animation_tick(self) -> None:
        self._weather_animation_job = None
        if not self._weather_animation_playing:
            return
        next_index = (self._weather_animation_step_index + 1) % len(self.WEATHER_TIMELINE_MINUTES)
        self._set_weather_animation_index(next_index, refresh=True)
        self._schedule_weather_animation_tick()

    def _step_weather_animation(self, direction: int) -> None:
        self._stop_weather_animation()
        index = (self._weather_animation_step_index + direction) % len(self.WEATHER_TIMELINE_MINUTES)
        self._set_weather_animation_index(index, refresh=True)

    def _on_weather_animation_scrub(self, value: str) -> None:
        try:
            index = int(round(float(value)))
        except ValueError:
            return
        if index == self._weather_animation_step_index:
            return
        self._stop_weather_animation()
        self._set_weather_animation_index(index, refresh=True)

    def _on_weather_animation_speed_changed(self, _event: object | None = None) -> None:
        raw = self.weather_animation_speed_var.get().replace("×", "")
        try:
            self._weather_animation_speed = max(1.0, float(raw))
        except ValueError:
            self._weather_animation_speed = 1.0
        if self._weather_animation_playing:
            self._schedule_weather_animation_tick()

    def _set_weather_animation_index(self, index: int, *, refresh: bool) -> None:
        index = max(0, min(len(self.WEATHER_TIMELINE_MINUTES) - 1, int(index)))
        self._weather_animation_step_index = index
        if hasattr(self, "weather_animation_index_var"):
            self.weather_animation_index_var.set(index)
        minutes = self.WEATHER_TIMELINE_MINUTES[index]
        self._set_animation_status(minutes)
        if refresh:
            self._refresh_weather_map()

    def _set_animation_status(self, minutes: int) -> None:
        if not hasattr(self, "weather_animation_status_var"):
            return
        if minutes < 0:
            self.weather_animation_status_var.set(
                f"OBSERVED {abs(minutes)} min ago — EUMETSAT cloud + nearest available rain radar"
            )
        elif minutes == 0:
            self.weather_animation_status_var.set("NOW — latest observed EUMETSAT cloud + rain radar")
        else:
            self.weather_animation_status_var.set(
                f"FORECAST +{minutes // 60}h — model cloud + precipitation, not future radar"
            )

    def _animation_minutes(self) -> int:
        return self.WEATHER_TIMELINE_MINUTES[self._weather_animation_step_index]

    def _refresh_weather_map(self) -> None:
        if not hasattr(self, "weather_animation_index_var"):
            super()._refresh_weather_map()
            return
        if not hasattr(self, "weather_map_status_var"):
            return
        profile = self._selected_profile()
        if profile is None:
            super()._refresh_weather_map()
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
            forecast_hours = 0
            radar_time = requested_cloud_time
            self.weather_map_status_var.set(f"Loading observed weather from {abs(minutes)} minutes ago...")
        elif minutes == 0:
            requested_cloud_time = None
            forecast_hours = 0
            radar_time = None
            self.weather_map_status_var.set("Loading latest observed cloud and rain radar...")
        else:
            requested_cloud_time = None
            forecast_hours = minutes // 60
            radar_time = None
            self.weather_map_status_var.set(f"Loading +{forecast_hours}h cloud/rain model forecast...")

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
                forecast_hours,
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
                radar_time_utc=radar_time_utc,
                forecast_hours_ahead=forecast_hours,
            )
            self.after(0, self._apply_stage16_weather_map, profile_key, observer, generation, snapshot)
        except Exception:  # noqa: BLE001
            self.after(0, self._weather_map_failed, generation)

    def _apply_weather(
        self,
        profile_key: tuple[object, ...],
        generation: int,
        snapshot: WeatherSnapshot,
    ) -> None:
        super()._apply_weather(profile_key, generation, snapshot)


def main() -> int:
    app = AnimatedStage16NightAzimuthApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
