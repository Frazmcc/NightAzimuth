from __future__ import annotations

from datetime import datetime, timezone
import tkinter as tk

from .gui_stage20 import Stage20NightAzimuthApp
from .sky_map import SkySatellite
from .stage20_live_sky_view import ISS_NORAD_ID, Stage20LiveSkyView


class Stage20SatelliteNightAzimuthApp(Stage20NightAzimuthApp):
    """Stage 20 Live Sky with all satellites, ISS persistence and pass alerts."""

    def _build_live_view(self, parent: tk.Misc) -> None:
        super()._build_live_view(parent)
        old_view = self.live_view
        master = old_view.master
        old_view.destroy()
        self.live_view = Stage20LiveSkyView(
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
        self._apply_live_view_direction(show_error=False)
        self._on_star_layer_changed()

    def _apply_tracking_data(
        self,
        profile_name: str,
        live_rows: list[tuple[str, ...]],
        pass_rows: list[tuple[str, ...]],
        sky_satellites: list[SkySatellite],
    ) -> None:
        super()._apply_tracking_data(profile_name, live_rows, pass_rows, sky_satellites)
        if profile_name != self.selected_name or not isinstance(self.live_view, Stage20LiveSkyView):
            return

        # Pass prediction is intentionally based on CelesTrak's VISUAL group.
        # Reusing those NORAD IDs lets the day/night Live Sky distinguish
        # plausible visual targets without hiding the rest of the active fleet.
        self.live_view.set_visual_candidate_ids(
            row[1] for row in pass_rows if len(row) >= 2
        )
        alerts, iss_status = build_local_pass_hud(
            pass_rows,
            current_satellites=getattr(self, "_sky_satellites", ()),
        )
        self.live_view.set_pass_alerts(alerts, iss_status=iss_status)


def build_local_pass_hud(
    pass_rows: list[tuple[str, ...]],
    *,
    current_satellites: object = (),
    now: datetime | None = None,
) -> tuple[tuple[str, ...], str]:
    moment = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    parsed: list[tuple[float, str, str, str]] = []
    iss_future: tuple[float, str] | None = None

    for row in pass_rows:
        if len(row) < 6:
            continue
        name, norad, rise_text, _peak_text, _set_text, max_elevation = row[:6]
        try:
            rise = datetime.strptime(str(rise_text), "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        except ValueError:
            continue
        seconds = (rise - moment).total_seconds()
        if seconds < 0:
            continue
        if str(norad) == ISS_NORAD_ID and (iss_future is None or seconds < iss_future[0]):
            iss_future = (seconds, str(max_elevation))
        if seconds <= 3600:
            parsed.append((seconds, str(name), str(norad), str(max_elevation)))

    parsed.sort(key=lambda item: (item[2] != ISS_NORAD_ID, item[0]))
    alerts = tuple(
        _format_pass_alert(name, norad, seconds, maximum)
        for seconds, name, norad, maximum in parsed[:4]
    )

    satellites = list(current_satellites) if current_satellites is not None else []
    iss = next((item for item in satellites if getattr(item, "norad_id", None) == ISS_NORAD_ID), None)
    if iss is not None:
        iss_status = (
            f"ISS • ABOVE HORIZON • Az {iss.azimuth_deg:.0f}° • "
            f"El {iss.elevation_deg:.0f}° • {iss.range_km:.0f} km"
        )
    elif iss_future is not None:
        seconds, maximum = iss_future
        iss_status = f"ISS • BELOW HORIZON • next pass {_countdown_text(seconds)} • max {maximum}"
    else:
        iss_status = "ISS • BELOW HORIZON • no ≥10° pass in next 24h"

    return alerts, iss_status


def _format_pass_alert(name: str, norad: str, seconds: float, maximum: str) -> str:
    identity = "ISS" if norad == ISS_NORAD_ID else name
    return f"{identity}  in {_countdown_text(seconds)}  •  max {maximum}"


def _countdown_text(seconds: float) -> str:
    total_minutes = max(0, int(round(seconds / 60.0)))
    if total_minutes < 60:
        return f"{total_minutes}m"
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours}h {minutes:02d}m"


def main() -> int:
    app = Stage20SatelliteNightAzimuthApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
