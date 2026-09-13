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

    def __init__(self) -> None:
        self._weather_animation_job: str | None = None
        self._weather_animation_playing = False
        self._weather_animation_step_index = 6
        self._weather_animation_speed = 1.0
        super().__init__()

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
        ).grid(row=1, column=0, columnspan=6, sticky="w", pady=(5, 0))
        ttk.Label(
            animation,
            text="OBSERVED: EUMETSAT cloud + RainViewer radar   |   NOW   |   FORECAST: model cloud + precipitation",
        ).grid(row=2, column=0, columnspan=6, sticky="w")

    def _toggle_weather_animation(self) -> None:
        self._weather_animation_playing = not self._weather_animation_playing
        self.weather_animation_play_button.configure(
            text="⏸ Pause" if self._weather_animation_playing else "▶ Play"
        )
        if self._weather_animation_playing:
            self._schedule_weather_animation_tick(immediate=True)
        else:
            self._cancel_weather_animation_job()

    def _cancel_weather_animation_job(self) -> None:
        if self._weather_animation_job is not None:
            try:
                self.after_cancel(self._weather_animation_job)
            except tk.TclError:
                pass
            self._weather_animation_job = None

    def _schedule_weather_animation_tick(self, *, immediate: bool = False) -> None:
        self._cancel_weather_animation_job()
        if not self._weather_animation_playing:
            return
        delay = 1 if immediate else max(250, int(self.ANIMATION_INTERVAL_MS / self._weather_animation_speed))
        self._weather_animation_job = self.after(delay, self._weather_animation_tick)

    def _weather_animation_tick(self) -> None:
        self._weather_animation_job = None
        if not self._weather_animation_playing:
            return
        next_index = (self._weather_animation_step_index + 1) % len(self.WEATHER_TIMELINE_MINUTES)
        self._set_weather_animation_index(next_index, refresh=True)
        self._schedule_weather_animation_tick()

    def _step_weather_animation(self, amount: int) -> None:
        self._weather_animation_playing = False
        self._cancel_weather_animation_job()
        if hasattr(self, "weather_animation_play_button"):
            self.weather_animation_play_button.configure(text="▶ Play")
        target = (self._weather_animation_step_index + amount) % len(self.WEATHER_TIMELINE_MINUTES)
        self._set_weather_animation_index(target, refresh=True)

    def _on_weather_animation_scrub(self, value: str) -> None:
        self._weather_animation_playing = False
        self._cancel_weather_animation_job()
        if hasattr(self, "weather_animation_play_button"):
            self.weather_animation_play_button.configure(text="▶ Play")
        self._set_weather_animation_index(int(round(float(value))), refresh=True)

    def _on_weather_animation_speed_changed(self, _event: object | None = None) -> None:
        raw = self.weather_animation_speed_var.get().replace("×", "")
        self._weather_animation_speed = float(raw or "1")
        if self._weather_animation_playing:
            self._schedule_weather_animation_tick()

    def _set_weather_animation_index(self, index: int, *, refresh: bool) -> None:
        index = max(0, min(len(self.WEATHER_TIMELINE_MINUTES) - 1, int(index)))
        self._weather_animation_step_index = index
        if hasattr(self, "weather_animation_index_var") and self.weather_animation_index_var.get() != index:
            self.weather_animation_index_var.set(index)

        offset = self.WEATHER_TIMELINE_MINUTES[index]
        if offset < 0:
            if hasattr(self, "map_time_var"):
                self.map_time_var.set("Now")
            label = f"OBSERVED {abs(offset)} min ago — EUMETSAT cloud + RainViewer radar"
        elif offset == 0:
            if hasattr(self, "map_time_var"):
                self.map_time_var.set("Now")
            if hasattr(self, "cloud_frame_var"):
                self.cloud_frame_var.set("Latest")
            label = "NOW — latest observed satellite cloud + rain radar"
        else:
            hours = offset // 60
            choice = "+1 hour" if hours == 1 else f"+{hours} hours"
            if hasattr(self, "map_time_var"):
                self.map_time_var.set(choice)
            label = f"FORECAST +{hours}h — model cloud + precipitation; not future radar"

        if hasattr(self, "weather_animation_status_var"):
            self.weather_animation_status_var.set(label)
        if refresh:
            self._refresh_weather_map()

    def _selected_cloud_time(self) -> datetime | None:
        offset = self.WEATHER_TIMELINE_MINUTES[self._weather_animation_step_index]
        if offset < 0:
            return datetime.now(timezone.utc) + timedelta(minutes=offset)
        if offset == 0 and self._weather_animation_playing:
            return None
        return super()._selected_cloud_time()

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

            offset = self.WEATHER_TIMELINE_MINUTES[self._weather_animation_step_index]
            radar_time_utc = None
            if offset < 0 and forecast_hours == 0:
                radar_time_utc = datetime.now(timezone.utc) + timedelta(minutes=offset)

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
                radar_time_utc=radar_time_utc,
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
