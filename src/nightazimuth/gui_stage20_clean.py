from __future__ import annotations

from collections.abc import Iterator
import tkinter as tk
from tkinter import ttk

from .aircraft import AircraftSnapshot
from .aircraft_live import SkyAircraft
from .gui_stage20_satellites import Stage20SatelliteNightAzimuthApp, build_local_pass_hud
from .sky_map import SkySatellite
from .stage20_clean_live_view import Stage20CleanLiveSkyView

DRAWER_ISS = "iss"


class Stage20CleanNightAzimuthApp(Stage20SatelliteNightAzimuthApp):
    """Low-noise Stage 20 presentation with resilient live contacts."""

    def __init__(self) -> None:
        self._stage20_iss_panel: ttk.LabelFrame | None = None
        self._stage20_iss_text_var: tk.StringVar | None = None
        super().__init__()

    def _build_live_view(self, parent: tk.Misc) -> None:
        super()._build_live_view(parent)
        old_view = self.live_view
        master = old_view.master
        old_view.destroy()
        self.live_view = Stage20CleanLiveSkyView(
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
        self._build_iss_drawer(master)
        self._apply_live_view_direction(show_error=False)
        self._on_star_layer_changed()

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
