from __future__ import annotations

from datetime import datetime, timezone
import threading
import tkinter as tk
from tkinter import ttk

from .gui_stage14 import Stage14NightAzimuthApp
from .weather import MetNorwayWeatherProvider, WeatherSnapshot


class Stage15NightAzimuthApp(Stage14NightAzimuthApp):
    """Add location-aware point weather and cloud forecast information."""

    WEATHER_REFRESH_MS = 30 * 60 * 1000

    def __init__(self) -> None:
        self._weather_snapshot: WeatherSnapshot | None = None
        self._weather_provider: MetNorwayWeatherProvider | None = None
        self._weather_generation = 0
        self._weather_refresh_job: str | None = None
        super().__init__()
        self._refresh_weather()

    def _build_live_view(self, parent: ttk.Frame) -> None:
        super()._build_live_view(parent)
        self.weather_status_var = tk.StringVar(master=self, value="Weather & cloud: waiting for location...")
        weather = ttk.LabelFrame(parent, text="Weather & cloud", padding=(10, 6))
        weather.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        ttk.Label(
            weather,
            textvariable=self.weather_status_var,
            justify="left",
            font=("Consolas", 9),
        ).pack(anchor="w", fill="x")

    def _refresh_location_selector(self) -> None:
        super()._refresh_location_selector()
        if hasattr(self, "weather_status_var"):
            self._refresh_weather()

    def _on_location_changed(self, event: object | None = None) -> None:
        super()._on_location_changed(event)
        self._refresh_weather()

    def _refresh_weather(self) -> None:
        if self._weather_refresh_job is not None:
            try:
                self.after_cancel(self._weather_refresh_job)
            except tk.TclError:
                pass
            self._weather_refresh_job = None

        profile = self._selected_profile()
        if profile is None:
            self._weather_snapshot = None
            if hasattr(self, "weather_status_var"):
                self.weather_status_var.set("Weather & cloud: no location configured.")
            return

        self._weather_generation += 1
        generation = self._weather_generation
        profile_key = (profile.name, profile.latitude, profile.longitude, profile.altitude_m)
        if hasattr(self, "weather_status_var"):
            self.weather_status_var.set("Weather & cloud: loading point forecast for selected location...")

        observer = self._observer_for_profile(profile)
        threading.Thread(
            target=self._load_weather,
            args=(profile_key, observer, generation),
            daemon=True,
        ).start()
        self._weather_refresh_job = self.after(self.WEATHER_REFRESH_MS, self._refresh_weather)

    def _load_weather(self, profile_key: tuple[object, ...], observer: object, generation: int) -> None:
        try:
            if self._weather_provider is None:
                self._weather_provider = MetNorwayWeatherProvider(
                    cache_directory=self.cache_directory,
                    cache_max_age_minutes=30,
                )
            snapshot = self._weather_provider.load(observer)
            self.after(0, self._apply_weather, profile_key, generation, snapshot)
        except Exception:  # noqa: BLE001
            self.after(0, self._weather_failed, generation)

    def _apply_weather(
        self,
        profile_key: tuple[object, ...],
        generation: int,
        snapshot: WeatherSnapshot,
    ) -> None:
        if generation != self._weather_generation:
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
        self._weather_snapshot = snapshot
        self._update_weather_status_text()

    def _weather_failed(self, generation: int) -> None:
        if generation != self._weather_generation:
            return
        self._weather_snapshot = None
        if hasattr(self, "weather_status_var"):
            self.weather_status_var.set("Weather & cloud: forecast unavailable.")

    def _update_weather_status_text(self) -> None:
        if not hasattr(self, "weather_status_var"):
            return
        snapshot = self._weather_snapshot
        if snapshot is None:
            return

        now = datetime.now(timezone.utc)
        point = snapshot.current_or_next(now)
        if point is None:
            self.weather_status_var.set("Weather & cloud: no forecast points available.")
            return

        age = snapshot.source_age(now)
        age_text = "unknown" if age is None else _format_age(age.total_seconds())
        cache_text = "cache" if snapshot.from_cache else "live"
        lines = [
            f"Source: {snapshot.source_name}  Data age: {age_text}  Feed: {cache_text}",
            (
                f"Now/next: Temp {_fmt(point.air_temperature_c, '°C')}  "
                f"Humidity {_fmt(point.relative_humidity_percent, '%')}  "
                f"Cloud {_fmt(point.cloud_total_percent, '%')}  "
                f"Fog {_fmt(point.fog_percent, '%')}"
            ),
            (
                f"Cloud layers: low {_fmt(point.cloud_low_percent, '%')}  "
                f"mid {_fmt(point.cloud_medium_percent, '%')}  "
                f"high {_fmt(point.cloud_high_percent, '%')}  "
                f"Rain next hour {_fmt(point.precipitation_next_hour_mm, ' mm')}"
            ),
            (
                f"Wind: {_fmt(point.wind_speed_m_s, ' m/s')} from "
                f"{_fmt(point.wind_from_direction_deg, '°')}"
            ),
            "Next hours: " + " | ".join(self._forecast_summary(snapshot, now)),
            "Point forecast only — directional cloud estimation is planned for Stage 16.",
        ]
        self.weather_status_var.set("\n".join(lines))

    def _forecast_summary(self, snapshot: WeatherSnapshot, now: datetime) -> list[str]:
        summaries: list[str] = []
        for point in snapshot.next_points(4, now):
            local_time = None
            if self._observing_snapshot is not None:
                local_time = self._observing_snapshot.local_time(point.time_utc)
            stamp = (local_time or point.time_utc).strftime("%H:%M")
            summaries.append(
                f"{stamp} cloud {_fmt(point.cloud_total_percent, '%')} rain {_fmt(point.precipitation_next_hour_mm, ' mm')}"
            )
        return summaries or ["unavailable"]


def _fmt(value: float | None, suffix: str) -> str:
    if value is None:
        return "--"
    if suffix in {"%", "°"}:
        return f"{value:.0f}{suffix}"
    return f"{value:.1f}{suffix}"


def _format_age(total_seconds: float) -> str:
    seconds = max(0, int(total_seconds))
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} min"
    hours, remainder = divmod(minutes, 60)
    return f"{hours}h {remainder:02d}m"


def main() -> int:
    app = Stage15NightAzimuthApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
