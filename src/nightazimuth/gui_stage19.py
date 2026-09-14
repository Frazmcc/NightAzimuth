from __future__ import annotations

from datetime import datetime, timezone
import threading
import tkinter as tk
from tkinter import messagebox, ttk

import httpx

from . import COPYRIGHT, __version__
from .aircraft import AircraftDataError, AircraftSightline, AircraftSnapshot, aircraft_sightline
from .aircraft_hud import AircraftHudFinderView
from .aircraft_preferences import AIRCRAFT_SOURCES, AircraftPreferences, AircraftPreferenceStore
from .aircraft_providers import (
    AdsbLolAircraftProvider,
    LocalReadsbAircraftProvider,
    validate_local_receiver_url,
)
from .gui_stage16_polish import PolishedStage16NightAzimuthApp


class Stage19NightAzimuthApp(PolishedStage16NightAzimuthApp):
    """Add a free, freshness-gated aircraft sightline layer to the Live finder."""

    AIRCRAFT_REFRESH_MS = 15_000

    def __init__(self) -> None:
        self._aircraft_generation = 0
        self._aircraft_refresh_job: str | None = None
        self._aircraft_refresh_in_progress = False
        self._aircraft_snapshot: AircraftSnapshot | None = None
        self._selected_aircraft: AircraftSightline | None = None
        self._aircraft_internet_confirmed = False
        super().__init__()

    def _build_live_view(self, parent: ttk.Frame) -> None:
        super()._build_live_view(parent)
        self.aircraft_preference_store = AircraftPreferenceStore(
            self.store.path.parent / "aircraft-preferences.json"
        )
        self.aircraft_preferences = self.aircraft_preference_store.load()
        self.show_aircraft_var = tk.BooleanVar(master=self, value=False)

        old_view = self.live_view
        master = old_view.master
        old_view.destroy()
        self.live_view = AircraftHudFinderView(
            master,
            on_select=self._on_live_satellite_selected,
            on_aircraft_select=self._on_aircraft_selected,
        )
        self.live_view.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        self._apply_live_view_direction(show_error=False)
        self._on_star_layer_changed()
        if hasattr(self, "show_all_tracked_var"):
            self.live_view.set_show_all_tracked(self.show_all_tracked_var.get())
        if hasattr(self, "show_cloud_overlay_var"):
            self.live_view.set_cloud_overlay_enabled(self.show_cloud_overlay_var.get())
        if hasattr(self, "cloud_opacity_var"):
            self.live_view.set_cloud_opacity(float(self.cloud_opacity_var.get()) / 100.0)

        layout_parent = master.master
        controls = next(
            (item for item in layout_parent.grid_slaves(row=0, column=0) if isinstance(item, ttk.Frame)),
            None,
        )
        if controls is not None:
            ttk.Separator(controls, orient="vertical").pack(side="left", fill="y", padx=10)
            ttk.Checkbutton(
                controls,
                text="Aircraft",
                variable=self.show_aircraft_var,
                command=self._on_aircraft_layer_changed,
            ).pack(side="left")
            ttk.Button(
                controls,
                text="Aircraft settings…",
                command=self.open_aircraft_settings,
            ).pack(side="left", padx=(6, 0))

        self.aircraft_status_var = tk.StringVar(master=self)
        details = next(
            (item for item in master.grid_slaves(row=0, column=1) if isinstance(item, ttk.LabelFrame)),
            None,
        )
        if details is not None:
            ttk.Separator(details, orient="horizontal").pack(fill="x", pady=(10, 8))
            ttk.Label(
                details,
                textvariable=self.aircraft_status_var,
                wraplength=250,
                justify="left",
            ).pack(anchor="nw", fill="x")
        self._set_aircraft_off_status()

    def _on_aircraft_layer_changed(self) -> None:
        enabled = self.show_aircraft_var.get()
        internet = self.aircraft_preferences.source == AIRCRAFT_SOURCES[0]
        if enabled and internet and not self._aircraft_internet_confirmed:
            accepted = messagebox.askyesno(
                "Enable free aircraft data?",
                "ADSB.lol will receive the selected latitude and longitude so it can return nearby "
                "aircraft. NightAzimuth does not send the location name or save aircraft history.\n\n"
                "Aircraft data is informational only—not for navigation or collision avoidance.\n\n"
                "Continue?",
                parent=self,
            )
            if not accepted:
                self.show_aircraft_var.set(False)
                enabled = False
            else:
                self._aircraft_internet_confirmed = True

        self.live_view.set_aircraft_enabled(enabled)
        if enabled:
            self._refresh_aircraft()
        else:
            self._cancel_aircraft_refresh()
            self._aircraft_generation += 1
            self._aircraft_snapshot = None
            self._selected_aircraft = None
            self.live_view.clear_aircraft()
            self._set_aircraft_off_status()

    def _refresh_aircraft(self) -> None:
        self._cancel_aircraft_refresh()
        if not self.show_aircraft_var.get():
            return
        if self._aircraft_refresh_in_progress:
            self._schedule_aircraft_refresh()
            return
        profile = self._selected_profile()
        if profile is None:
            self.aircraft_status_var.set("Aircraft: select an observing location.")
            self._schedule_aircraft_refresh()
            return

        self._aircraft_generation += 1
        generation = self._aircraft_generation
        profile_key = (profile.name, profile.latitude, profile.longitude, profile.altitude_m)
        preferences = self.aircraft_preferences
        self._aircraft_refresh_in_progress = True
        self.aircraft_status_var.set(
            f"Aircraft: refreshing {preferences.source}…\n"
            "Informational only—not for navigation or collision avoidance."
        )
        threading.Thread(
            target=self._load_aircraft,
            args=(profile_key, generation, preferences),
            daemon=True,
        ).start()

    def _load_aircraft(
        self,
        profile_key: tuple[object, ...],
        generation: int,
        preferences: AircraftPreferences,
    ) -> None:
        try:
            if preferences.source == AIRCRAFT_SOURCES[1]:
                provider = LocalReadsbAircraftProvider(preferences.local_receiver_url)
            else:
                provider = AdsbLolAircraftProvider()
            snapshot = provider.load(
                float(profile_key[1]),
                float(profile_key[2]),
                preferences.radius_nm,
            )
            self.after(0, self._apply_aircraft, profile_key, generation, snapshot)
        except Exception as exc:  # noqa: BLE001
            self.after(0, self._aircraft_failed, generation, _safe_aircraft_reason(exc))

    def _apply_aircraft(
        self,
        profile_key: tuple[object, ...],
        generation: int,
        snapshot: AircraftSnapshot,
    ) -> None:
        if generation != self._aircraft_generation:
            self._aircraft_refresh_in_progress = False
            if self.show_aircraft_var.get():
                self._refresh_aircraft()
            return
        self._aircraft_refresh_in_progress = False
        if not self.show_aircraft_var.get():
            return
        profile = self._selected_profile()
        current_key = None if profile is None else (
            profile.name,
            profile.latitude,
            profile.longitude,
            profile.altitude_m,
        )
        if current_key != profile_key or profile is None:
            self._refresh_aircraft()
            return

        sightlines = tuple(
            line
            for aircraft in snapshot.aircraft
            if (
                line := aircraft_sightline(
                    aircraft,
                    observer_latitude=profile.latitude,
                    observer_longitude=profile.longitude,
                    observer_altitude_m=profile.altitude_m,
                )
            ).elevation_deg >= 0.0
        )
        self._aircraft_snapshot = snapshot
        self._selected_aircraft = None
        self.live_view.set_aircraft(
            sightlines,
            observer_latitude=profile.latitude,
            observer_longitude=profile.longitude,
            observer_altitude_m=profile.altitude_m,
        )
        self._render_aircraft_status(total=len(sightlines))
        self._schedule_aircraft_refresh()

    def _aircraft_failed(self, generation: int, reason: str) -> None:
        if generation != self._aircraft_generation:
            self._aircraft_refresh_in_progress = False
            if self.show_aircraft_var.get():
                self._refresh_aircraft()
            return
        self._aircraft_refresh_in_progress = False
        if not self.show_aircraft_var.get():
            return
        self._aircraft_snapshot = None
        self._selected_aircraft = None
        self.live_view.clear_aircraft()
        self.aircraft_status_var.set(
            f"Aircraft unavailable: {reason}\n"
            "No old positions are being shown. Retrying automatically.\n"
            "Informational only—not for navigation or collision avoidance."
        )
        self._schedule_aircraft_refresh()

    def _schedule_aircraft_refresh(self) -> None:
        self._cancel_aircraft_refresh()
        if self.show_aircraft_var.get():
            self._aircraft_refresh_job = self.after(
                self.AIRCRAFT_REFRESH_MS,
                self._refresh_aircraft,
            )

    def _cancel_aircraft_refresh(self) -> None:
        if self._aircraft_refresh_job is not None:
            try:
                self.after_cancel(self._aircraft_refresh_job)
            except tk.TclError:
                pass
            self._aircraft_refresh_job = None

    def _on_aircraft_selected(self, sightline: AircraftSightline) -> None:
        self._selected_aircraft = sightline
        self._render_aircraft_status(total=len(self._aircraft_snapshot.aircraft) if self._aircraft_snapshot else 0)

    def _render_aircraft_status(self, *, total: int) -> None:
        snapshot = self._aircraft_snapshot
        if snapshot is None:
            self._set_aircraft_off_status()
            return
        age = max(0, int((datetime.now(timezone.utc) - snapshot.fetched_at_utc).total_seconds()))
        lines = [
            f"Aircraft: {total} above horizon; {self.live_view.aircraft_in_view_count} in view",
            f"Source: {snapshot.source_name}  Fetch age: {age}s",
            snapshot.attribution,
        ]
        if self._selected_aircraft is not None:
            item = self._selected_aircraft
            aircraft = item.aircraft
            altitude_ft = aircraft.altitude_m / 0.3048
            track = "—" if aircraft.ground_track_deg is None else f"{aircraft.ground_track_deg:.0f}°"
            heading = "—" if aircraft.true_heading_deg is None else f"{aircraft.true_heading_deg:.0f}°"
            speed = "—" if aircraft.ground_speed_knots is None else f"{aircraft.ground_speed_knots:.0f} kt"
            lines.extend(
                [
                    "",
                    f"{aircraft.callsign}  ICAO {aircraft.hex_id.upper()}",
                    f"Az {item.azimuth_deg:.1f}°  El {item.elevation_deg:.1f}°  Range {item.slant_range_km:.1f} km",
                    f"Altitude {altitude_ft:,.0f} ft ({aircraft.altitude_source})",
                    f"Ground track {track}  True heading {heading}  Speed {speed}",
                    f"Position age at fetch: {aircraft.position_age_seconds:.1f}s",
                ]
            )
        lines.extend(
            [
                "",
                "Dashed arrow = 30s track/speed projection, not a flight plan.",
                "Informational only—not for navigation or collision avoidance.",
            ]
        )
        self.aircraft_status_var.set("\n".join(lines))

    def _set_aircraft_off_status(self) -> None:
        preferences = getattr(self, "aircraft_preferences", AircraftPreferences())
        if preferences.source == AIRCRAFT_SOURCES[0]:
            source = "ADSB.lol (free, ODbL 1.0). Enabling sends selected coordinates."
        else:
            source = "Local readsb/dump1090 receiver."
        if hasattr(self, "aircraft_status_var"):
            self.aircraft_status_var.set(f"Aircraft layer: Off\nConfigured source: {source}")

    def _on_location_changed(self, event: object | None = None) -> None:
        super()._on_location_changed(event)
        if hasattr(self, "show_aircraft_var") and self.show_aircraft_var.get():
            self._aircraft_generation += 1
            self._refresh_aircraft()

    def open_aircraft_settings(self) -> None:
        AircraftSettingsWindow(self)

    def apply_aircraft_preferences(self, preferences: AircraftPreferences) -> None:
        self.aircraft_preferences = self.aircraft_preference_store.save(preferences)
        self.show_aircraft_var.set(False)
        self._aircraft_internet_confirmed = False
        self._on_aircraft_layer_changed()

    def open_credits(self) -> None:
        messagebox.showinfo(
            "NightAzimuth Credits",
            f"NightAzimuth {__version__}\n\n{COPYRIGHT}\n\n"
            "Satellite tracking and observing utility.\n\n"
            "Optional internet aircraft data: ADSB.lol, licensed ODbL 1.0.",
            parent=self,
        )


class AircraftSettingsWindow(tk.Toplevel):
    def __init__(self, app: Stage19NightAzimuthApp) -> None:
        super().__init__(app)
        self.app = app
        self.title("Aircraft Data Settings")
        self.geometry("650x360")
        self.resizable(False, False)
        self.transient(app)
        self.grab_set()
        preferences = app.aircraft_preferences
        self.source_var = tk.StringVar(value=preferences.source)
        self.url_var = tk.StringVar(value=preferences.local_receiver_url)
        self.radius_var = tk.StringVar(value=f"{preferences.radius_nm:g}")
        self._build_ui()
        app.apply_appearance(self)

    def _build_ui(self) -> None:
        frame = ttk.Frame(self, padding=18)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Aircraft data", font=("Segoe UI", 12, "bold")).grid(
            row=0, column=0, columnspan=2, sticky="w", pady=(0, 10)
        )
        ttk.Label(frame, text="Source").grid(row=1, column=0, sticky="w", pady=6)
        source = ttk.Combobox(
            frame,
            textvariable=self.source_var,
            values=AIRCRAFT_SOURCES,
            state="readonly",
            width=30,
        )
        source.grid(row=1, column=1, sticky="ew", pady=6)
        ttk.Label(frame, text="Local aircraft.json URL").grid(row=2, column=0, sticky="w", pady=6)
        ttk.Entry(frame, textvariable=self.url_var).grid(row=2, column=1, sticky="ew", pady=6)
        ttk.Label(frame, text="Search radius (nautical miles)").grid(row=3, column=0, sticky="w", pady=6)
        ttk.Entry(frame, textvariable=self.radius_var, width=12).grid(row=3, column=1, sticky="w", pady=6)
        ttk.Label(
            frame,
            text=(
                "ADSB.lol requires no key or payment and is licensed ODbL 1.0. Enabling it sends "
                "the selected latitude/longitude to ADSB.lol. A local readsb/dump1090 receiver "
                "usually gives lower latency and sends no observer location to an aircraft service.\n\n"
                "Positions older than 30 seconds are excluded. Aircraft data is informational only "
                "and must not be used for navigation, collision avoidance or flight operations."
            ),
            wraplength=600,
            justify="left",
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(12, 14))
        ttk.Button(frame, text="Save", command=self._save).grid(
            row=5, column=0, columnspan=2, sticky="ew"
        )
        frame.columnconfigure(1, weight=1)

    def _save(self) -> None:
        try:
            radius = float(self.radius_var.get())
            if not 1.0 <= radius <= 250.0:
                raise ValueError("Search radius must be between 1 and 250 nautical miles.")
            url = validate_local_receiver_url(self.url_var.get())
            preferences = AircraftPreferences(
                source=self.source_var.get(),
                local_receiver_url=url,
                radius_nm=radius,
            )
            self.app.apply_aircraft_preferences(preferences)
        except ValueError as exc:
            messagebox.showerror("Invalid aircraft settings", str(exc), parent=self)
            return
        self.destroy()


def _safe_aircraft_reason(exc: Exception) -> str:
    cause: BaseException | None = exc
    if isinstance(exc, AircraftDataError) and exc.__cause__ is not None:
        cause = exc.__cause__
    if isinstance(cause, httpx.HTTPStatusError):
        return f"HTTP {cause.response.status_code}"
    if isinstance(cause, httpx.TimeoutException):
        return "request timed out"
    if isinstance(cause, httpx.ConnectError):
        return "could not connect to the configured source"
    if isinstance(exc, AircraftDataError):
        return str(exc)
    return "unexpected provider response"


def main() -> int:
    app = Stage19NightAzimuthApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())