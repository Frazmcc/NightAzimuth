from __future__ import annotations

import httpx
import tkinter as tk
from tkinter import ttk

from .gui_stage16_animation import AnimatedStage16NightAzimuthApp
from .sky_map import SkySatellite
from .weather import MetNorwayWeatherProvider, WeatherProviderError


class PolishedStage16NightAzimuthApp(AnimatedStage16NightAzimuthApp):
    """Final Stage 16 UI polish for refresh status and safe weather diagnostics."""

    def _build_live_view(self, parent: ttk.Frame) -> None:
        """Build the Live view inside a vertically scrollable container.

        The finder itself keeps mouse-wheel zoom.  When the pointer is over the
        surrounding controls/status panels, the wheel scrolls the whole Live
        page so the sunset/weather text remains reachable on smaller displays.
        A permanent scrollbar is also provided on the right.
        """
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        canvas = tk.Canvas(parent, highlightthickness=0, borderwidth=0)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        content = ttk.Frame(canvas)
        content_window = canvas.create_window((0, 0), window=content, anchor="nw")

        def sync_scroll_region(_event: object | None = None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def match_content_width(event: tk.Event) -> None:
            canvas.itemconfigure(content_window, width=max(1, event.width))

        content.bind("<Configure>", sync_scroll_region, add="+")
        canvas.bind("<Configure>", match_content_width, add="+")

        super()._build_live_view(content)
        self._live_scroll_canvas = canvas

        def is_descendant(widget: tk.Misc | None, ancestor: tk.Misc) -> bool:
            current = widget
            while current is not None:
                if current is ancestor:
                    return True
                current = getattr(current, "master", None)
            return False

        def on_mousewheel(event: tk.Event) -> None:
            # The finder uses the wheel for zoom, so never steal that gesture.
            pointer_widget = self.winfo_containing(self.winfo_pointerx(), self.winfo_pointery())
            if pointer_widget is None or not is_descendant(pointer_widget, canvas):
                return
            if hasattr(self, "live_view") and is_descendant(pointer_widget, self.live_view):
                return
            delta = int(getattr(event, "delta", 0))
            if delta:
                canvas.yview_scroll(-1 if delta > 0 else 1, "units")

        self.bind_all("<MouseWheel>", on_mousewheel, add="+")
        self.after_idle(sync_scroll_region)

    def _apply_tracking_data(
        self,
        profile_name: str,
        live_rows: list[tuple[str, ...]],
        pass_rows: list[tuple[str, ...]],
        sky_satellites: list[SkySatellite],
    ) -> None:
        super()._apply_tracking_data(profile_name, live_rows, pass_rows, sky_satellites)
        if profile_name != self.selected_name:
            return
        self.status_var.set(
            f"Loaded {len(live_rows)} satellites above the horizon and {len(pass_rows)} passes. "
            f"Orbital refresh runs {_format_refresh_interval(self._auto_refresh_ms)} in the background; "
            "Live-view motion remains continuous between refreshes."
        )

    def _load_weather(
        self,
        profile_key: tuple[object, ...],
        observer: object,
        generation: int,
    ) -> None:
        try:
            if self._weather_provider is None:
                self._weather_provider = MetNorwayWeatherProvider(
                    cache_directory=self.cache_directory,
                    cache_max_age_minutes=30,
                )
            snapshot = self._weather_provider.load(observer)
            self.after(0, self._apply_weather, profile_key, generation, snapshot)
        except Exception as exc:  # noqa: BLE001
            self.after(0, self._weather_failed_with_reason, generation, _safe_weather_reason(exc))

    def _weather_failed_with_reason(self, generation: int, reason: str) -> None:
        if generation != self._weather_generation:
            return
        self._weather_snapshot = None
        if hasattr(self, "weather_status_var"):
            self.weather_status_var.set(
                "Weather & cloud: forecast unavailable. "
                f"Reason: {reason}. Retrying automatically; Refresh can also be used manually."
            )


def _format_refresh_interval(milliseconds: int) -> str:
    seconds = max(1, int(milliseconds / 1000))
    if seconds % 60 == 0:
        minutes = seconds // 60
        return f"every {minutes} minute" + ("" if minutes == 1 else "s")
    return f"every {seconds} seconds"


def _safe_weather_reason(exc: Exception) -> str:
    """Return a useful reason without ever exposing a request URL or coordinates."""
    cause: BaseException | None = exc
    if isinstance(exc, WeatherProviderError) and exc.__cause__ is not None:
        cause = exc.__cause__

    if isinstance(cause, httpx.HTTPStatusError):
        return f"MET Norway HTTP {cause.response.status_code}"
    if isinstance(cause, httpx.TimeoutException):
        return "MET Norway request timed out"
    if isinstance(cause, httpx.ConnectError):
        return "unable to connect to MET Norway"
    if isinstance(cause, httpx.HTTPError):
        return "MET Norway network request failed"
    if isinstance(cause, OSError):
        return "local cache/file access failed"
    if isinstance(cause, (ValueError, KeyError, TypeError)):
        return "weather response could not be parsed"
    return type(exc).__name__


def main() -> int:
    app = PolishedStage16NightAzimuthApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
