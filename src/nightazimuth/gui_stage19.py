from __future__ import annotations

from datetime import datetime, timezone
import threading
import tkinter as tk

from .aircraft import AircraftObserver, AircraftSnapshot
from .aircraft_adsb_lol import AdsbLolProvider
from .aircraft_hud_finder_view import AircraftTwilightFinderView
from .aircraft_live import SkyAircraft, build_sky_aircraft
from .aircraft_motion import AircraftMotionHistory
from .aircraft_sources import AircraftSourceCoordinator
from .gui_stage16_polish import PolishedStage16NightAzimuthApp


class Stage19NightAzimuthApp(PolishedStage16NightAzimuthApp):
    """Add observer-centred aircraft identification without changing satellite logic."""

    AIRCRAFT_REFRESH_MS = 5_000
    AIRCRAFT_RETRY_MS = 10_000
    AIRCRAFT_RADIUS_KM = 200.0

    def __init__(self) -> None:
        self._aircraft_provider = AdsbLolProvider()
        self._aircraft_sources = AircraftSourceCoordinator(
            internet_provider=self._aircraft_provider,
            stale_grace_seconds=90.0,
        )
        self._aircraft_motion = AircraftMotionHistory(
            max_fixes_per_aircraft=8,
            max_history_age_seconds=120.0,
            prediction_limit_seconds=15.0,
        )
        self._aircraft_snapshot: AircraftSnapshot | None = None
        self._aircraft_refresh_job: str | None = None
        self._aircraft_generation = 0
        self._aircraft_fetch_in_progress = False
        super().__init__()
        self._refresh_aircraft()

    def _build_live_view(self, parent: tk.Misc) -> None:
        super()._build_live_view(parent)

        old_view = self.live_view
        master = old_view.master
        grid_info = old_view.grid_info()
        old_view.destroy()

        self.live_view = AircraftTwilightFinderView(
            master,
            on_select=self._on_live_satellite_selected,
            on_aircraft_select=self._on_live_aircraft_selected,
        )
        self.live_view.grid(**grid_info)
        self._apply_live_view_direction(show_error=False)
        self._on_star_layer_changed()

    def _on_location_changed(self, event: object | None = None) -> None:
        super()._on_location_changed(event)
        self._aircraft_generation += 1
        self._aircraft_motion.clear()
        self._aircraft_sources.clear_last_good()
        self._aircraft_snapshot = None
        if hasattr(self, "live_view") and isinstance(self.live_view, AircraftTwilightFinderView):
            self.live_view.set_aircraft([])
        self._refresh_aircraft()

    def _refresh_aircraft(self) -> None:
        if self._aircraft_refresh_job is not None:
            try:
                self.after_cancel(self._aircraft_refresh_job)
            except tk.TclError:
                pass
            self._aircraft_refresh_job = None

        if self._aircraft_fetch_in_progress:
            self._aircraft_refresh_job = self.after(1_000, self._refresh_aircraft)
            return

        profile = self._selected_profile()
        if profile is None:
            if hasattr(self, "live_view") and isinstance(self.live_view, AircraftTwilightFinderView):
                self.live_view.set_aircraft([])
            self._aircraft_refresh_job = self.after(self.AIRCRAFT_RETRY_MS, self._refresh_aircraft)
            return

        self._aircraft_generation += 1
        generation = self._aircraft_generation
        profile_key = (profile.name, profile.latitude, profile.longitude, profile.altitude_m)
        observer = AircraftObserver(
            latitude_deg=profile.latitude,
            longitude_deg=profile.longitude,
            altitude_m=profile.altitude_m,
        )
        self._aircraft_fetch_in_progress = True
        threading.Thread(
            target=self._load_aircraft,
            args=(profile_key, observer, generation),
            daemon=True,
        ).start()

    def _load_aircraft(
        self,
        profile_key: tuple[object, ...],
        observer: AircraftObserver,
        generation: int,
    ) -> None:
        try:
            snapshot = self._aircraft_sources.fetch_snapshot(
                observer,
                self.AIRCRAFT_RADIUS_KM,
            )
            contacts = build_sky_aircraft(
                snapshot,
                observer,
                self._aircraft_motion,
                at=datetime.now(timezone.utc),
            )
            self.after(
                0,
                self._apply_aircraft_snapshot,
                profile_key,
                generation,
                snapshot,
                contacts,
            )
        except Exception as exc:  # noqa: BLE001
            self.after(0, self._aircraft_refresh_failed, generation, type(exc).__name__)

    def _apply_aircraft_snapshot(
        self,
        profile_key: tuple[object, ...],
        generation: int,
        snapshot: AircraftSnapshot,
        contacts: list[SkyAircraft],
    ) -> None:
        self._aircraft_fetch_in_progress = False
        if generation != self._aircraft_generation:
            self._aircraft_refresh_job = self.after(0, self._refresh_aircraft)
            return

        profile = self._selected_profile()
        current_key = None if profile is None else (
            profile.name,
            profile.latitude,
            profile.longitude,
            profile.altitude_m,
        )
        if current_key != profile_key:
            self._aircraft_refresh_job = self.after(0, self._refresh_aircraft)
            return

        self._aircraft_snapshot = snapshot
        if hasattr(self, "live_view") and isinstance(self.live_view, AircraftTwilightFinderView):
            self.live_view.set_aircraft(contacts)
        self._aircraft_refresh_job = self.after(self.AIRCRAFT_REFRESH_MS, self._refresh_aircraft)

    def _aircraft_refresh_failed(self, generation: int, _reason: str) -> None:
        self._aircraft_fetch_in_progress = False
        if generation != self._aircraft_generation:
            return
        self._aircraft_refresh_job = self.after(self.AIRCRAFT_RETRY_MS, self._refresh_aircraft)

    def _on_live_aircraft_selected(self, aircraft: SkyAircraft) -> None:
        altitude_ft = aircraft.altitude_m / 0.3048
        speed_knots = None
        if aircraft.ground_speed_mps is not None:
            speed_knots = aircraft.ground_speed_mps / 0.514444
        vertical_fpm = None
        if aircraft.vertical_rate_mps is not None:
            vertical_fpm = aircraft.vertical_rate_mps / 0.00508

        lines = [
            aircraft.callsign or "Aircraft",
            f"ICAO: {aircraft.icao24.upper()}",
            f"Azimuth: {aircraft.azimuth_deg:.1f}°",
            f"Elevation: {aircraft.elevation_deg:.1f}°",
            f"Range: {aircraft.range_km:.1f} km",
            f"Altitude: {altitude_ft:,.0f} ft",
        ]
        if speed_knots is not None:
            lines.append(f"Ground speed: {speed_knots:.0f} kt")
        if aircraft.track_deg is not None:
            lines.append(f"Track: {aircraft.track_deg:.0f}°")
        if vertical_fpm is not None:
            lines.append(f"Vertical rate: {vertical_fpm:+.0f} ft/min")
        lines.extend(
            (
                f"Position: {aircraft.position_state.value}",
                f"Position age: {aircraft.position_age_seconds:.1f} s",
                f"Source: {aircraft.source_label}",
            )
        )
        self.live_detail_var.set("\n".join(lines))

    def destroy(self) -> None:
        if self._aircraft_refresh_job is not None:
            try:
                self.after_cancel(self._aircraft_refresh_job)
            except tk.TclError:
                pass
            self._aircraft_refresh_job = None
        super().destroy()


def main() -> int:
    app = Stage19NightAzimuthApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
