from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .aircraft_live import SkyAircraft
from .aircraft_routes import AircraftRoute
from .gui_stage20_realtime import Stage20RealtimeNightAzimuthApp
from .stage20_rc_airports import ResilientAirportLandmarkProvider

DRAWER_AIRCRAFT = "aircraft"


class Stage20ReleaseCandidateApp(Stage20RealtimeNightAzimuthApp):
    """Release-candidate hardening for selected-aircraft detail and airports."""

    def __init__(self) -> None:
        self._rc_airport_provider = ResilientAirportLandmarkProvider()
        self._aircraft_detail_var: tk.StringVar | None = None
        super().__init__()

    def _build_aircraft_controls(self, parent: tk.Misc) -> None:
        super()._build_aircraft_controls(parent)

        # Keep selected-aircraft intelligence with the aircraft priority board.
        # Users should never have to open Live Finder to inspect an aircraft.
        aircraft_frame = self.aircraft_table.master.master
        aircraft_frame.rowconfigure(2, weight=0)
        self._aircraft_detail_var = tk.StringVar(
            master=self,
            value="Select an aircraft above to view route, aircraft type, role, squawk and live tracking.",
        )
        selected_frame = ttk.LabelFrame(
            aircraft_frame,
            text="Selected aircraft",
            padding=(10, 7),
        )
        selected_frame.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        selected_frame.columnconfigure(0, weight=1)
        ttk.Label(
            selected_frame,
            textvariable=self._aircraft_detail_var,
            justify="left",
            anchor="nw",
            wraplength=1500,
            font=("Consolas", 9),
        ).grid(row=0, column=0, sticky="ew")

    def _load_airport_landmarks(
        self,
        profile_key: tuple[object, ...],
        generation: int,
        latitude: float,
        longitude: float,
    ) -> None:
        landmarks = self._rc_airport_provider.nearby(
            latitude,
            longitude,
            max_distance_km=250.0,
            limit=12,
        )
        self.after(0, self._apply_airport_landmarks, profile_key, generation, landmarks)

    def _on_live_aircraft_selected(self, aircraft: SkyAircraft) -> None:
        super()._on_live_aircraft_selected(aircraft)
        self._copy_selected_aircraft_detail()

        # Aircraft information belongs in Aircraft Contacts. Selecting from
        # either the sky or the priority board opens that drawer immediately.
        self._stage20_open_drawer = DRAWER_AIRCRAFT
        self._apply_stage20_drawer_state()

        # Restore Live Finder to its generic observer summary rather than
        # leaving a duplicate copy of the aircraft block there.
        self._update_live_view_summary()

    def _apply_aircraft_route(
        self,
        aircraft: SkyAircraft,
        generation: int,
        route: AircraftRoute | None,
    ) -> None:
        super()._apply_aircraft_route(aircraft, generation, route)
        if getattr(self.live_view, "selected_icao24", None) == aircraft.icao24:
            self._copy_selected_aircraft_detail()
            self._update_live_view_summary()

    def _copy_selected_aircraft_detail(self) -> None:
        if self._aircraft_detail_var is None:
            return
        detail = self.live_detail_var.get().strip()
        if detail:
            self._aircraft_detail_var.set(detail)

    def _on_location_changed(self, event: object | None = None) -> None:
        super()._on_location_changed(event)
        if self._aircraft_detail_var is not None:
            self._aircraft_detail_var.set(
                "Select an aircraft above to view route, aircraft type, role, squawk and live tracking."
            )


def main() -> int:
    app = Stage20ReleaseCandidateApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
