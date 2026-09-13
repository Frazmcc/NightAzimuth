from __future__ import annotations

import httpx

from .gui_stage16_animation import AnimatedStage16NightAzimuthApp
from .location_profiles import LocationProfile
from .sky_map import SkySatellite
from .weather import MetNorwayWeatherProvider, WeatherProviderError


class PolishedStage16NightAzimuthApp(AnimatedStage16NightAzimuthApp):
    """Final Stage 16 UI polish for refresh status and safe weather diagnostics."""

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
