from __future__ import annotations

from collections.abc import Iterator
import threading
import tkinter as tk
from tkinter import ttk

from .aircraft import AircraftSnapshot
from .aircraft_live import SkyAircraft
from .aircraft_routes import AircraftRoute
from .airport_landmarks import AirportLandmark, relevant_airport_landmarks
from .gui_stage19 import aircraft_contact_row, filter_aircraft_contacts
from .gui_stage20_satellites import Stage20SatelliteNightAzimuthApp, build_local_pass_hud
from .sky_map import SkySatellite
from .stage20_aircraft_detail import format_stage20_aircraft_detail
from .stage20_airport_live_view import Stage20AirportLiveSkyView
from .stage20_header import local_clock_text, timezone_name_for_coordinates
from .stage20_perceptual_projection import project_perceptual_live_view
from .stage20_prank import open_prank_instance, prank_delays_ms

DRAWER_ISS = "iss"


class Stage20CleanNightAzimuthApp(Stage20SatelliteNightAzimuthApp):
    """Low-noise Stage 20 presentation with resilient live contacts."""

    def __init__(self) -> None:
        self._stage20_iss_panel: ttk.LabelFrame | None = None
        self._stage20_iss_text_var: tk.StringVar | None = None
        self._stage20_clock_job: str | None = None
        self._stage20_clock_timezone = "UTC"
        self._stage20_prank_active = False
        self._stage20_airport_generation = 0
        _install_perceptual_projection()
        super().__init__()
        self._install_stage20_header_extras()
        self._update_stage20_clock_timezone()
        self._schedule_stage20_clock_tick()

    def _build_live_view(self, parent: tk.Misc) -> None:
        super()._build_live_view(parent)
        old_view = self.live_view
        master = old_view.master
        old_view.destroy()
        self.live_view = Stage20AirportLiveSkyView(
            master,
            on_select=self._on_live_satellite_selected,
            on_aircraft_select=self._on_live_aircraft_selected,
        )
        self.live_view.grid(
            row=0,
            column=0,
            columnspan=2,
            sticky="nsew",
            padx=0,
            pady=0,
        )
        self._remove_weather_cloud_live_controls(parent)
        self._remove_aircraft_table_scrollbar()
        self._build_iss_drawer(master)
        self._apply_live_view_direction(show_error=False)
        self._on_star_layer_changed()
        self._update_airport_landmarks()

    def _install_stage20_header_extras(self) -> None:
        header = self.location_combo.master

        clock_frame = ttk.Frame(header)
        clock_frame.pack(side="left", fill="x", expand=True, padx=(22, 10))
        self.stage20_clock_var = tk.StringVar(master=self, value="--:--:--  UTC+0")
        self.stage20_clock_label = tk.Label(
            clock_frame,
            textvariable=self.stage20_clock_var,
            background="#050b12",
            foreground="#39ff14",
            activebackground="#050b12",
            activeforeground="#39ff14",
            font=("Consolas", 22, "bold"),
            padx=12,
            pady=2,
            borderwidth=1,
            relief="solid",
            highlightthickness=0,
        )
        self.stage20_clock_label.pack(anchor="center")

        self.stage20_prank_button = tk.Button(
            header,
            text="DON NOT PRESS",
            command=self._start_stage20_prank,
            background="#b91c1c",
            foreground="#ffffff",
            activebackground="#ef4444",
            activeforeground="#ffffff",
            font=("Segoe UI", 9, "bold"),
            padx=10,
            pady=4,
            relief="raised",
            cursor="hand2",
        )
        self.stage20_prank_button.pack(side="right", padx=(8, 0))

    def _update_stage20_clock_timezone(self) -> None:
        profile = self._selected_profile()
        if profile is None:
            self._stage20_clock_timezone = "UTC"
            return
        try:
            self._stage20_clock_timezone = timezone_name_for_coordinates(
                profile.latitude,
                profile.longitude,
            )
        except Exception:  # noqa: BLE001
            self._stage20_clock_timezone = "UTC"

    def _schedule_stage20_clock_tick(self) -> None:
        if self._stage20_clock_job is None:
            self._stage20_clock_job = self.after(200, self._stage20_clock_tick)

    def _stage20_clock_tick(self) -> None:
        self._stage20_clock_job = None
        if hasattr(self, "stage20_clock_var"):
            try:
                self.stage20_clock_var.set(local_clock_text(self._stage20_clock_timezone))
            except Exception:  # noqa: BLE001
                self.stage20_clock_var.set("--:--:--  UTC+0")
        self._stage20_clock_job = self.after(250, self._stage20_clock_tick)

    def _start_stage20_prank(self) -> None:
        if self._stage20_prank_active:
            return
        self._stage20_prank_active = True
        self.stage20_prank_button.configure(state="disabled", text="I DID WARN YOU")
        for instance, delay in enumerate(prank_delays_ms(), start=1):
            self.after(
                delay,
                lambda index=instance: threading.Thread(
                    target=open_prank_instance,
                    args=(index,),
                    daemon=True,
                ).start(),
            )
        self.after(7_500, self._reset_stage20_prank_button)

    def _reset_stage20_prank_button(self) -> None:
        self._stage20_prank_active = False
        if hasattr(self, "stage20_prank_button") and self.stage20_prank_button.winfo_exists():
            self.stage20_prank_button.configure(state="normal", text="DON NOT PRESS")

    def _on_location_changed(self, event: object | None = None) -> None:
        super()._on_location_changed(event)
        self._update_stage20_clock_timezone()
        self._update_airport_landmarks()

    def _update_airport_landmarks(self) -> None:
        if not hasattr(self, "live_view") or not isinstance(self.live_view, Stage20AirportLiveSkyView):
            return
        self._stage20_airport_generation += 1
        generation = self._stage20_airport_generation
        profile = self._selected_profile()
        if profile is None:
            self.live_view.set_airport_landmarks(())
            return
        profile_key = (profile.name, profile.latitude, profile.longitude)
        threading.Thread(
            target=self._load_airport_landmarks,
            args=(profile_key, generation, profile.latitude, profile.longitude),
            daemon=True,
        ).start()

    def _load_airport_landmarks(
        self,
        profile_key: tuple[object, ...],
        generation: int,
        latitude: float,
        longitude: float,
    ) -> None:
        landmarks = relevant_airport_landmarks(
            latitude,
            longitude,
            max_distance_km=220.0,
            limit=4,
        )
        self.after(0, self._apply_airport_landmarks, profile_key, generation, landmarks)

    def _apply_airport_landmarks(
        self,
        profile_key: tuple[object, ...],
        generation: int,
        landmarks: tuple[AirportLandmark, ...],
    ) -> None:
        if generation != self._stage20_airport_generation:
            return
        profile = self._selected_profile()
        current_key = None if profile is None else (profile.name, profile.latitude, profile.longitude)
        if current_key != profile_key:
            return
        if isinstance(self.live_view, Stage20AirportLiveSkyView):
            self.live_view.set_airport_landmarks(landmarks)

    def _remove_aircraft_table_scrollbar(self) -> None:
        panel = getattr(self, "_stage20_aircraft_panel", None)
        if panel is None:
            return
        for widget in _walk_widgets(panel):
            if isinstance(widget, ttk.Scrollbar):
                widget.grid_remove()
                try:
                    self.aircraft_table.configure(yscrollcommand="")
                except tk.TclError:
                    pass

    def _build_iss_drawer(self, master: tk.Misc) -> None:
        self._stage20_iss_text_var = tk.StringVar(master=self, value="ISS: waiting for orbital data...")
        panel = ttk.LabelFrame(master, text="ISS & upcoming passes", padding=(10, 7))
        ttk.Label(panel, textvariable=self._stage20_iss_text_var, justify="left", font=("Consolas", 9)).pack(anchor="w", fill="x")
        self._stage20_iss_panel = panel
        self.stage20_iss_button = ttk.Button(
            self.stage20_drawer_bar,
            text="▸  ISS / PASSES",
            command=lambda: self._toggle_stage20_drawer(DRAWER_ISS),
        )
        self.stage20_iss_button.pack(side="left", padx=(6, 0))

    def _apply_stage20_drawer_state(self) -> None:
        super()._apply_stage20_drawer_state()
        if self._stage20_iss_panel is not None:
            self._stage20_iss_panel.grid_remove()
        if hasattr(self, "stage20_iss_button"):
            self.stage20_iss_button.configure(
                text="▾  ISS / PASSES" if self._stage20_open_drawer == DRAWER_ISS else "▸  ISS / PASSES"
            )
        if self._stage20_open_drawer == DRAWER_ISS and self._stage20_iss_panel is not None:
            self._stage20_iss_panel.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(5, 0))

    def _apply_tracking_data(
        self,
        profile_name: str,
        live_rows: list[tuple[str, ...]],
        pass_rows: list[tuple[str, ...]],
        sky_satellites: list[SkySatellite],
    ) -> None:
        super()._apply_tracking_data(profile_name, live_rows, pass_rows, sky_satellites)
        if profile_name != self.selected_name or self._stage20_iss_text_var is None:
            return
        alerts, iss_status = build_local_pass_hud(pass_rows, current_satellites=getattr(self, "_sky_satellites", ()))
        lines = [iss_status]
        if alerts:
            lines.extend(("", "Passes within 60 minutes:"))
            lines.extend(f"  {item}" for item in alerts)
        else:
            lines.extend(("", "No tracked visual-catalogue passes within 60 minutes."))
        self._stage20_iss_text_var.set("\n".join(lines))

    def _apply_aircraft_snapshot(
        self,
        profile_key: tuple[object, ...],
        generation: int,
        snapshot: AircraftSnapshot,
        contacts: list[SkyAircraft],
    ) -> None:
        if not contacts and self._aircraft_contacts:
            self._aircraft_fetch_in_progress = False
            if generation != self._aircraft_generation:
                self._aircraft_refresh_job = self.after(0, self._refresh_aircraft)
                return
            profile = self._selected_profile()
            current_key = None if profile is None else (profile.name, profile.latitude, profile.longitude, profile.altitude_m)
            if current_key != profile_key:
                self._aircraft_refresh_job = self.after(0, self._refresh_aircraft)
                return
            self._aircraft_snapshot = snapshot
            self._refresh_aircraft_contacts_panel(force=True)
            if hasattr(self, "aircraft_status_var"):
                self.aircraft_status_var.set("STALE • no fresh ADS-B contacts; holding last known positions")
            self._aircraft_refresh_job = self.after(self.AIRCRAFT_RETRY_MS, self._refresh_aircraft)
            return
        super()._apply_aircraft_snapshot(profile_key, generation, snapshot, contacts)

    def _on_live_aircraft_selected(self, aircraft: SkyAircraft) -> None:
        if hasattr(self, "aircraft_table") and self.aircraft_table.exists(aircraft.icao24):
            self.aircraft_table.selection_set(aircraft.icao24)
            self.aircraft_table.focus(aircraft.icao24)
        self._aircraft_route_generation += 1
        generation = self._aircraft_route_generation
        base_detail = format_stage20_aircraft_detail(aircraft)
        if not aircraft.callsign:
            self.live_detail_var.set(base_detail)
            return
        self.live_detail_var.set(base_detail + "\n\nJourney data: looking up route...")
        threading.Thread(target=self._load_aircraft_route, args=(aircraft, generation), daemon=True).start()

    def _apply_aircraft_route(
        self,
        aircraft: SkyAircraft,
        generation: int,
        route: AircraftRoute | None,
    ) -> None:
        if not self._aircraft_ready or generation != self._aircraft_route_generation:
            return
        if self.live_view.selected_icao24 != aircraft.icao24:
            return
        self.live_detail_var.set(format_stage20_aircraft_detail(aircraft, route=route))

    def _refresh_aircraft_contacts_panel(self, *, force: bool = False) -> None:
        if not hasattr(self, "aircraft_table"):
            return
        if not self.aircraft_layer_var.get():
            visible: list[SkyAircraft] = []
        else:
            visible = self.live_view.aircraft_in_current_view()
        visible = prioritise_aircraft_board(visible)
        max_rows = self._stage20_aircraft_row_limit()
        shown = visible[:max_rows]
        rows = tuple(aircraft_contact_row(item) for item in shown)
        if force or rows != self._aircraft_table_signature:
            selected_icao = self.live_view.selected_icao24
            self.aircraft_table.delete(*self.aircraft_table.get_children())
            for aircraft, row in zip(shown, rows, strict=True):
                self.aircraft_table.insert("", "end", iid=aircraft.icao24, values=row)
            if selected_icao and self.aircraft_table.exists(selected_icao):
                self.aircraft_table.selection_set(selected_icao)
                self.aircraft_table.focus(selected_icao)
            self._aircraft_table_signature = rows
        filtered_total = len(filter_aircraft_contacts(self._aircraft_contacts, self.aircraft_filter_var.get()))
        hidden = max(0, len(visible) - len(shown))
        if not self.aircraft_layer_var.get():
            status = "Aircraft layer off"
        elif self._aircraft_snapshot is None:
            status = "Aircraft: waiting for data..."
        else:
            state = self._aircraft_snapshot.state.value.upper()
            suffix = f" • {hidden} more on Live Sky" if hidden else ""
            status = f"{state} • {len(shown)} priority contacts shown / {filtered_total} filtered{suffix}"
        self.aircraft_status_var.set(status)

    def _stage20_aircraft_row_limit(self) -> int:
        layout = getattr(self, "_stage20_layout", None)
        if layout is None:
            return 5
        return max(3, min(int(layout.table_rows), 6 if not layout.compact else 4))

    def _remove_weather_cloud_live_controls(self, parent: tk.Misc) -> None:
        for widget in list(_walk_widgets(parent)):
            try:
                text = str(widget.cget("text")).strip().lower()
            except tk.TclError:
                continue
            if isinstance(widget, ttk.LabelFrame) and text == "weather & cloud":
                widget.destroy()
                continue
            if any(phrase in text for phrase in ("cloud overlay", "cloud opacity")):
                widget.destroy()

    def destroy(self) -> None:
        self._stage20_airport_generation += 1
        if self._stage20_clock_job is not None:
            try:
                self.after_cancel(self._stage20_clock_job)
            except tk.TclError:
                pass
            self._stage20_clock_job = None
        super().destroy()


def prioritise_aircraft_board(contacts: list[SkyAircraft]) -> list[SkyAircraft]:
    return sorted(
        contacts,
        key=lambda aircraft: (
            -(aircraft.squawk_alert.priority if aircraft.squawk_alert is not None else 0),
            -int(aircraft.squawk_alert is not None),
            -int(aircraft.military),
            aircraft.range_km,
            -aircraft.elevation_deg,
            aircraft.icao24,
        ),
    )


def _install_perceptual_projection() -> None:
    from . import aircraft_hud_finder_view
    from . import gui_stage13
    from . import gui_stage14
    from . import hud_finder_view
    from . import live_view
    from . import smooth_hud_finder_view
    from . import star_live_view

    modules = (
        live_view,
        hud_finder_view,
        star_live_view,
        smooth_hud_finder_view,
        aircraft_hud_finder_view,
        gui_stage13,
        gui_stage14,
    )
    for module in modules:
        if hasattr(module, "project_live_view"):
            module.project_live_view = project_perceptual_live_view


def _walk_widgets(parent: tk.Misc) -> Iterator[tk.Misc]:
    for child in parent.winfo_children():
        yield child
        yield from _walk_widgets(child)


def main() -> int:
    app = Stage20CleanNightAzimuthApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
