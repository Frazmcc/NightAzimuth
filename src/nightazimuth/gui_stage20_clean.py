from __future__ import annotations

from collections.abc import Iterator
import tkinter as tk
from tkinter import ttk

from .aircraft import AircraftSnapshot
from .aircraft_live import SkyAircraft
from .gui_stage19 import aircraft_contact_row, filter_aircraft_contacts
from .gui_stage20_satellites import Stage20SatelliteNightAzimuthApp, build_local_pass_hud
from .sky_map import SkySatellite
from .stage20_aircraft_detail import format_stage20_aircraft_detail
from .stage20_human_vision_live_view import Stage20HumanVisionLiveSkyView
from .stage20_perceptual_projection import project_perceptual_live_view

DRAWER_ISS = "iss"


class Stage20CleanNightAzimuthApp(Stage20SatelliteNightAzimuthApp):
    """Low-noise Stage 20 presentation with resilient live contacts."""

    def __init__(self) -> None:
        self._stage20_iss_panel: ttk.LabelFrame | None = None
        self._stage20_iss_text_var: tk.StringVar | None = None
        _install_perceptual_projection()
        super().__init__()

    def _build_live_view(self, parent: tk.Misc) -> None:
        super()._build_live_view(parent)
        old_view = self.live_view
        master = old_view.master
        old_view.destroy()
        self.live_view = Stage20HumanVisionLiveSkyView(
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
        # Keep Weather Map and Forecast as dedicated tabs. Only the Live Sky
        # weather/cloud panel and controls are removed for the lower-noise view.
        self._remove_weather_cloud_live_controls(parent)
        self._remove_aircraft_table_scrollbar()
        self._build_iss_drawer(master)
        self._apply_live_view_direction(show_error=False)
        self._on_star_layer_changed()

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
        self._stage20_iss_text_var = tk.StringVar(
            master=self,
            value="ISS: waiting for orbital data...",
        )
        panel = ttk.LabelFrame(master, text="ISS & upcoming passes", padding=(10, 7))
        ttk.Label(
            panel,
            textvariable=self._stage20_iss_text_var,
            justify="left",
            font=("Consolas", 9),
        ).pack(anchor="w", fill="x")
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
                text=(
                    "▾  ISS / PASSES"
                    if self._stage20_open_drawer == DRAWER_ISS
                    else "▸  ISS / PASSES"
                )
            )
        if self._stage20_open_drawer == DRAWER_ISS and self._stage20_iss_panel is not None:
            self._stage20_iss_panel.grid(
                row=2,
                column=0,
                columnspan=2,
                sticky="ew",
                pady=(5, 0),
            )

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
        alerts, iss_status = build_local_pass_hud(
            pass_rows,
            current_satellites=getattr(self, "_sky_satellites", ()),
        )
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
        # Do not let a transient zero-contact ADS-B response wipe a populated sky.
        if not contacts and self._aircraft_contacts:
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
            self._refresh_aircraft_contacts_panel(force=True)
            if hasattr(self, "aircraft_status_var"):
                self.aircraft_status_var.set(
                    "STALE • no fresh ADS-B contacts; holding last known positions"
                )
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
        threading.Thread(
            target=self._load_aircraft_route,
            args=(aircraft, generation),
            daemon=True,
        ).start()

    def _apply_aircraft_route(self, aircraft: SkyAircraft, generation: int, route: object) -> None:
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
            if any(
                phrase in text
                for phrase in (
                    "cloud overlay",
                    "cloud opacity",
                )
            ):
                widget.destroy()


def prioritise_aircraft_board(contacts: list[SkyAircraft]) -> list[SkyAircraft]:
    """Pin emergency/special operations first, then military, then useful normals."""
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
    """Route all Stage 20 sky layers through one spherical projection."""

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
