from __future__ import annotations

import threading
import tkinter as tk
from tkinter import ttk

from PIL import ImageTk

from .directional_cloud_hud import DirectionalCloudHudFinderView
from .gui_stage15 import Stage15NightAzimuthApp
from .weather_map_stage16 import Stage16WeatherMapRenderer, Stage16WeatherMapSnapshot


class Stage16NightAzimuthApp(Stage15NightAzimuthApp):
    """Add free spatial cloud imagery and an indicative Live-view cloud overlay."""

    def __init__(self) -> None:
        self._stage16_weather_map_renderer: Stage16WeatherMapRenderer | None = None
        super().__init__()
        if hasattr(self, "weather_map_status_var"):
            self._refresh_weather_map()

    def _build_live_view(self, parent: ttk.Frame) -> None:
        super()._build_live_view(parent)

        old_view = self.live_view
        master = old_view.master
        old_view.destroy()
        self.live_view = DirectionalCloudHudFinderView(
            master,
            on_select=self._on_live_satellite_selected,
        )
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

    def _on_cloud_overlay_changed(self) -> None:
        if hasattr(self, "live_view") and isinstance(self.live_view, DirectionalCloudHudFinderView):
            self.live_view.set_cloud_overlay_enabled(self.show_cloud_overlay_var.get())
        self._update_live_view_summary()

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
        show_radar = bool(self.show_radar_var.get()) if hasattr(self, "show_radar_var") else True
        show_cloud = bool(self.show_cloud_map_var.get()) if hasattr(self, "show_cloud_map_var") else True
        self.weather_map_status_var.set("Loading map, rain radar and spatial cloud imagery...")
        observer = self._observer_for_profile(profile)
        threading.Thread(
            target=self._load_stage16_weather_map,
            args=(profile_key, observer, show_radar, show_cloud, generation),
            daemon=True,
        ).start()

    def _load_stage16_weather_map(
        self,
        profile_key: tuple[object, ...],
        observer: object,
        show_radar: bool,
        show_cloud: bool,
        generation: int,
    ) -> None:
        try:
            if self._stage16_weather_map_renderer is None:
                self._stage16_weather_map_renderer = Stage16WeatherMapRenderer(
                    cache_directory=self.cache_directory
                )
            snapshot = self._stage16_weather_map_renderer.render_stage16(
                observer,
                show_radar=show_radar,
                show_cloud=show_cloud,
                zoom=7,
                radius_tiles=1,
            )
            self.after(
                0,
                self._apply_stage16_weather_map,
                profile_key,
                observer,
                generation,
                snapshot,
            )
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
        if snapshot.radar_enabled and snapshot.radar_time_utc is not None:
            radar_text = f"Rain radar: {snapshot.radar_time_utc.strftime('%Y-%m-%d %H:%M UTC')}"
        elif snapshot.radar_enabled:
            radar_text = "Rain radar requested, but no frame was available."
        else:
            radar_text = "Rain radar: off"

        if snapshot.cloud_enabled:
            cloud_text = "Cloud imagery: EUMETView" + (
                " (cache)" if snapshot.cloud_from_cache else " (live)"
            )
        else:
            cloud_text = "Cloud imagery: off"

        self.weather_map_status_var.set(
            f"Selected location centred on map.\n{radar_text}\n{cloud_text}\n"
            "Cloud imagery is spatial satellite imagery. The Live overlay is indicative because cloud height is estimated."
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

    def _update_live_view_summary(self) -> None:
        super()._update_live_view_summary()
        if not hasattr(self, "live_detail_var"):
            return
        enabled = bool(getattr(self, "show_cloud_overlay_var", None) and self.show_cloud_overlay_var.get())
        state = "On" if enabled else "Off"
        self.live_detail_var.set(
            self.live_detail_var.get()
            + f"\nCloud overlay: {state}\n"
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
