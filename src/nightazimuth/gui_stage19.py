from __future__ import annotations

from datetime import datetime, timezone
import threading
import tkinter as tk

from .aircraft import AircraftObserver, AircraftSnapshot
from .aircraft_adsb_lol import AdsbLolProvider
from .aircraft_hud_finder_view import AircraftTwilightFinderView
from .aircraft_live import SkyAircraft, build_sky_aircraft
from .aircraft_motion import AircraftMotionHistory
from .aircraft_routes import AdsbLolRouteProvider, AircraftRoute, AirportInfo
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
        self._route_provider = AdsbLolRouteProvider()
        self._aircraft_snapshot: AircraftSnapshot | None = None
        self._aircraft_refresh_job: str | None = None
        self._aircraft_generation = 0
        self._aircraft_route_generation = 0
        self._aircraft_fetch_in_progress = False
        self._aircraft_ready = False
        super().__init__()
        self._aircraft_ready = True
        self._refresh_aircraft()

    def _build_live_view(self, parent: tk.Misc) -> None:
        super()._build_live_view(parent)
        old_view = self.live_view
        master = old_view.master
        old_view.destroy()
        self.live_view = AircraftTwilightFinderView(
            master,
            on_select=self._on_live_satellite_selected,
            on_aircraft_select=self._on_live_aircraft_selected,
        )
        self.live_view.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self._apply_live_view_direction(show_error=False)
        self._on_star_layer_changed()

    def _on_location_changed(self, event: object | None = None) -> None:
        super()._on_location_changed(event)
        if not self._aircraft_ready:
            return
        self._aircraft_generation += 1
        self._aircraft_route_generation += 1
        self._aircraft_motion.clear()
        self._aircraft_sources.clear_last_good()
        self._aircraft_snapshot = None
        if hasattr(self, "live_view") and isinstance(self.live_view, AircraftTwilightFinderView):
            self.live_view.set_aircraft([])
        self._refresh_aircraft()

    def _refresh_aircraft(self) -> None:
        if not self._aircraft_ready:
            return
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
        observer = AircraftObserver(profile.latitude, profile.longitude, profile.altitude_m)
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
            snapshot = self._aircraft_sources.fetch_snapshot(observer, self.AIRCRAFT_RADIUS_KM)
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
        self._aircraft_route_generation += 1
        generation = self._aircraft_route_generation
        base_detail = format_aircraft_detail(aircraft)
        if not aircraft.callsign:
            self.live_detail_var.set(base_detail + "\n\nRoute: Unknown")
            return

        self.live_detail_var.set(base_detail + "\n\nRoute: looking up...")
        threading.Thread(
            target=self._load_aircraft_route,
            args=(aircraft, generation),
            daemon=True,
        ).start()

    def _load_aircraft_route(self, aircraft: SkyAircraft, generation: int) -> None:
        route = self._route_provider.lookup(aircraft.callsign)
        self.after(0, self._apply_aircraft_route, aircraft, generation, route)

    def _apply_aircraft_route(
        self,
        aircraft: SkyAircraft,
        generation: int,
        route: AircraftRoute | None,
    ) -> None:
        if not self._aircraft_ready or generation != self._aircraft_route_generation:
            return
        if not isinstance(self.live_view, AircraftTwilightFinderView):
            return
        if self.live_view.selected_icao24 != aircraft.icao24:
            return
        self.live_detail_var.set(format_aircraft_detail(aircraft, route=route))

    def destroy(self) -> None:
        self._aircraft_ready = False
        self._aircraft_route_generation += 1
        if self._aircraft_refresh_job is not None:
            try:
                self.after_cancel(self._aircraft_refresh_job)
            except tk.TclError:
                pass
            self._aircraft_refresh_job = None
        super().destroy()


def format_aircraft_detail(
    aircraft: SkyAircraft,
    *,
    route: AircraftRoute | None = None,
) -> str:
    altitude_ft = aircraft.altitude_m / 0.3048
    speed_knots = (
        None
        if aircraft.ground_speed_mps is None
        else aircraft.ground_speed_mps / 0.514444
    )
    vertical_fpm = (
        None
        if aircraft.vertical_rate_mps is None
        else aircraft.vertical_rate_mps / 0.00508
    )

    lines: list[str] = []
    if aircraft.squawk_alert is not None:
        lines.extend(
            (
                f"⚠ {aircraft.squawk_alert.label}",
                f"Squawk: {aircraft.squawk_alert.code}",
                "",
            )
        )

    if aircraft.military:
        lines.append("MILITARY")
        if aircraft.type_description:
            lines.append(f"Aircraft: {aircraft.type_description}")
        elif aircraft.type_code:
            lines.append(f"Aircraft type: {aircraft.type_code}")
        if aircraft.operator:
            lines.append(f"Operator: {aircraft.operator}")
        if aircraft.registration:
            lines.append(f"Registration: {aircraft.registration}")
        if aircraft.type_code and aircraft.type_description:
            lines.append(f"ICAO type: {aircraft.type_code}")
        lines.append("")

    lines.extend(
        (
            aircraft.callsign or "Aircraft",
            f"ICAO: {aircraft.icao24.upper()}",
            f"Azimuth: {aircraft.azimuth_deg:.1f}°",
            f"Elevation: {aircraft.elevation_deg:.1f}°",
            f"Range: {aircraft.range_km:.1f} km",
            f"Altitude: {altitude_ft:,.0f} ft",
        )
    )
    if speed_knots is not None:
        lines.append(f"Ground speed: {speed_knots:.0f} kt")
    if aircraft.track_deg is not None:
        lines.append(f"Track: {aircraft.track_deg:.0f}°")
    if vertical_fpm is not None:
        lines.append(f"Vertical rate: {vertical_fpm:+.0f} ft/min")
    if aircraft.squawk is not None and aircraft.squawk_alert is None:
        lines.append(f"Squawk: {aircraft.squawk}")
    if not aircraft.military:
        if aircraft.type_description:
            lines.append(f"Aircraft: {aircraft.type_description}")
        elif aircraft.type_code:
            lines.append(f"Aircraft type: {aircraft.type_code}")
        if aircraft.registration:
            lines.append(f"Registration: {aircraft.registration}")
        if aircraft.operator:
            lines.append(f"Operator: {aircraft.operator}")

    lines.extend(
        (
            f"Position: {aircraft.position_state.value}",
            f"Position age: {aircraft.position_age_seconds:.1f} s",
            f"Source: {aircraft.source_label}",
            "",
        )
    )
    lines.extend(format_route_detail(route))
    return "\n".join(lines)


def format_route_detail(route: AircraftRoute | None) -> list[str]:
    if route is None or route.departure is None or route.arrival is None:
        return ["Route: Unknown"]

    lines = ["Route"]
    lines.extend(_format_airport("Departure", route.departure))
    if route.intermediate_airports:
        via = " → ".join(airport.display_code for airport in route.intermediate_airports)
        lines.append(f"Via: {via}")
    lines.extend(_format_airport("Arrival", route.arrival))
    lines.append(f"Route source: {route.source_label}")
    return lines


def _format_airport(label: str, airport: AirportInfo) -> list[str]:
    lines = [
        f"{label}: {airport.display_code}",
        f"  {airport.name}",
    ]
    if airport.location:
        lines.append(f"  Location: {airport.location}")
    lines.append(f"  Country: {airport.display_country}")
    return lines


def main() -> int:
    app = Stage19NightAzimuthApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
