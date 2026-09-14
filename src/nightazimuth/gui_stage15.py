from __future__ import annotations

from datetime import datetime, timezone
import threading
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk

from .gui_stage14 import Stage14NightAzimuthApp
from .weather import MetNorwayWeatherProvider, WeatherSnapshot
from .ui_layout import fitted_image_size
from .weather_map import WeatherMapRenderer, WeatherMapSnapshot


class Stage15NightAzimuthApp(Stage14NightAzimuthApp):
    """Add location-aware point weather plus a free 2D rain-radar map."""

    WEATHER_REFRESH_MS = 30 * 60 * 1000

    def __init__(self) -> None:
        self._weather_snapshot: WeatherSnapshot | None = None
        self._weather_provider: MetNorwayWeatherProvider | None = None
        self._weather_generation = 0
        self._weather_refresh_job: str | None = None
        self._weather_map_renderer: WeatherMapRenderer | None = None
        self._weather_map_generation = 0
        self._weather_map_photo: ImageTk.PhotoImage | None = None
        self._weather_map_source_image: Image.Image | None = None
        self._weather_map_resize_job: str | None = None
        super().__init__()
        self._refresh_weather()
        if hasattr(self, "weather_map_status_var"):
            self._refresh_weather_map()

    def _build_ui(self) -> None:
        super()._build_ui()
        notebook = self._find_notebook(self)
        if notebook is None:
            return
        weather_map_tab = ttk.Frame(notebook, padding=8)
        notebook.insert(2, weather_map_tab, text="Weather map")
        self._build_weather_map(weather_map_tab)

    def _build_live_view(self, parent: ttk.Frame) -> None:
        super()._build_live_view(parent)
        controls = next((item for item in parent.grid_slaves(row=0, column=0) if isinstance(item, ttk.Frame)), None)
        if controls is not None:
            ttk.Separator(controls, orient="vertical").pack(side="left", fill="y", padx=10)
            ttk.Checkbutton(
                controls,
                text="Cloud overlay (Stage 16)",
                state="disabled",
            ).pack(side="left")

        self.weather_status_var = tk.StringVar(master=self, value="Weather & cloud: waiting for location...")
        weather = ttk.LabelFrame(parent, text="Weather & cloud", padding=(10, 6))
        weather.grid(row=3, column=0, sticky="ew", pady=(8, 0))
        ttk.Label(
            weather,
            textvariable=self.weather_status_var,
            justify="left",
            font=("Consolas", 9),
        ).pack(anchor="w", fill="x")

    def _build_weather_map(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        controls = ttk.Frame(parent)
        controls.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        self.show_radar_var = tk.BooleanVar(master=self, value=True)
        ttk.Checkbutton(
            controls,
            text="Rain radar",
            variable=self.show_radar_var,
            command=self._refresh_weather_map,
        ).pack(side="left")
        ttk.Checkbutton(
            controls,
            text="Cloud imagery (Stage 16)",
            state="disabled",
        ).pack(side="left", padx=(12, 0))
        ttk.Button(controls, text="Refresh map", command=self._refresh_weather_map).pack(side="right")

        map_frame = ttk.Frame(parent)
        map_frame.grid(row=1, column=0, sticky="nsew", padx=(0, 10))
        map_frame.columnconfigure(0, weight=1)
        map_frame.rowconfigure(0, weight=1)
        self.weather_map_frame = map_frame
        map_frame.bind("<Configure>", self._on_weather_map_resize, add="+")
        self.weather_map_label = ttk.Label(map_frame, anchor="center")
        self.weather_map_label.grid(row=0, column=0, sticky="nsew")

        details = ttk.LabelFrame(parent, text="Weather map", padding=12, width=310)
        details.grid(row=1, column=1, sticky="ns")
        details.grid_propagate(False)
        self.weather_map_status_var = tk.StringVar(
            master=self,
            value="Select an observing location to load the map.",
        )
        ttk.Label(
            details,
            textvariable=self.weather_map_status_var,
            wraplength=280,
            justify="left",
        ).pack(anchor="nw", fill="x")
        ttk.Label(
            details,
            text=(
                "The white cross marks the selected observing location.\n\n"
                "Base map: © OpenStreetMap contributors.\n"
                "Rain radar: RainViewer.\n\n"
                "Only map tiles needed for the current view are requested. Repeated map tiles are cached locally. "
                "Cloud imagery and projection into the Live sky view remain Stage 16."
            ),
            wraplength=280,
            justify="left",
        ).pack(side="bottom", anchor="sw")

    def _refresh_location_selector(self) -> None:
        super()._refresh_location_selector()
        if hasattr(self, "weather_status_var"):
            self._refresh_weather()
        if hasattr(self, "weather_map_status_var"):
            self._refresh_weather_map()

    def _on_location_changed(self, event: object | None = None) -> None:
        super()._on_location_changed(event)
        self._refresh_weather()
        if hasattr(self, "weather_map_status_var"):
            self._refresh_weather_map()

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

    def _refresh_weather_map(self) -> None:
        if not hasattr(self, "weather_map_status_var"):
            return
        profile = self._selected_profile()
        if profile is None:
            self._weather_map_generation += 1
            self._weather_map_photo = None
            self._weather_map_source_image = None
            self.weather_map_label.configure(image="")
            self.weather_map_status_var.set("No location configured. Open Settings to add one.")
            return

        self._weather_map_generation += 1
        generation = self._weather_map_generation
        profile_key = (profile.name, profile.latitude, profile.longitude, profile.altitude_m)
        show_radar = bool(self.show_radar_var.get())
        self.weather_map_status_var.set("Loading 2D map and rain radar for the selected location...")
        observer = self._observer_for_profile(profile)
        threading.Thread(
            target=self._load_weather_map,
            args=(profile_key, observer, show_radar, generation),
            daemon=True,
        ).start()

    def _load_weather_map(
        self,
        profile_key: tuple[object, ...],
        observer: object,
        show_radar: bool,
        generation: int,
    ) -> None:
        try:
            if self._weather_map_renderer is None:
                self._weather_map_renderer = WeatherMapRenderer(cache_directory=self.cache_directory)
            snapshot = self._weather_map_renderer.render(
                observer,
                show_radar=show_radar,
                zoom=7,
                radius_tiles=1,
            )
            self.after(0, self._apply_weather_map, profile_key, generation, snapshot)
        except Exception:  # noqa: BLE001
            self.after(0, self._weather_map_failed, generation)

    def _apply_weather_map(
        self,
        profile_key: tuple[object, ...],
        generation: int,
        snapshot: WeatherMapSnapshot,
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

        self._show_weather_map_image(snapshot.image)
        if snapshot.radar_enabled and snapshot.radar_time_utc is not None:
            radar_text = f"Rain radar frame: {snapshot.radar_time_utc.strftime('%Y-%m-%d %H:%M UTC')}"
        elif snapshot.radar_enabled:
            radar_text = "Rain radar requested, but no radar frame was available."
        else:
            radar_text = "Rain radar: off"
        self.weather_map_status_var.set(
            f"Selected location centred on map.\n{radar_text}\n"
            "Map requests contain only the area needed for this view; saved profile names are not sent."
        )

    def _show_weather_map_image(self, image: Image.Image) -> None:
        """Display a map scaled to the panel while retaining the full source image."""

        self._weather_map_source_image = image.copy()
        self._render_weather_map_for_current_size()

    def _on_weather_map_resize(self, _event: object | None = None) -> None:
        """Debounce resize work so dragging the window remains responsive."""

        if self._weather_map_resize_job is not None:
            try:
                self.after_cancel(self._weather_map_resize_job)
            except tk.TclError:
                pass
        self._weather_map_resize_job = self.after(120, self._render_weather_map_for_current_size)

    def _render_weather_map_for_current_size(self) -> None:
        self._weather_map_resize_job = None
        source = self._weather_map_source_image
        if source is None or not hasattr(self, "weather_map_frame"):
            return
        available_width = self.weather_map_frame.winfo_width()
        available_height = self.weather_map_frame.winfo_height()
        if available_width < 40 or available_height < 40:
            return
        width, height = fitted_image_size(
            source.width,
            source.height,
            available_width,
            available_height,
        )
        if (width, height) == source.size:
            displayed = source
        else:
            displayed = source.resize((width, height), Image.Resampling.LANCZOS)
        self._weather_map_photo = ImageTk.PhotoImage(displayed)
        self.weather_map_label.configure(image=self._weather_map_photo)

    def _weather_map_failed(self, generation: int) -> None:
        if generation != self._weather_map_generation:
            return
        self.weather_map_status_var.set(
            "Weather map unavailable. Existing satellite tracking and point weather remain usable."
        )


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
