from __future__ import annotations

import math

from .aircraft_hud_finder_view import _aircraft_display_colour, _aircraft_label_colour
from .aircraft_live import SkyAircraft
from .sky_map import SkySatellite
from .stage20_live_sky_view import ISS_NORAD_ID, Stage20LiveSkyView


class Stage20CleanLiveSkyView(Stage20LiveSkyView):
    """Lower-noise Stage 20 Live Sky with distinct object families."""

    def _draw_stage20_pass_hud(self) -> None:
        # ISS/pass information lives in the lower ISS & Passes drawer.
        return

    def _draw_satellite(self, satellite: SkySatellite, x: float, y: float) -> None:
        selected = satellite.norad_id == self.selected_norad
        is_iss = satellite.norad_id == ISS_NORAD_ID
        priority_ids = self._priority_satellite_ids()

        if is_iss:
            radius = 5.0
            fill = "#fb7185"
        elif satellite.potentially_visible or satellite.twilight_candidate:
            radius = 3.2
            fill = "#f472b6"
        elif satellite.satellite_sunlit:
            radius = 2.4
            fill = "#e879f9"
        else:
            radius = 1.6
            fill = "#a855f7"

        if selected:
            radius = max(radius, 4.5)
        tag = f"live-sat:{satellite.norad_id}"
        self.create_oval(
            x - radius,
            y - radius,
            x + radius,
            y + radius,
            fill=fill,
            outline="#ffffff" if selected or is_iss else fill,
            width=2 if selected or is_iss else 1,
            tags=(tag, "live-satellite"),
        )

        if satellite.norad_id in priority_ids and (
            is_iss or selected or satellite in self._satellites[: self.MAX_FAST_LABELS]
        ):
            label = "ISS" if is_iss else satellite.name
            self.create_text(
                x + 7,
                y - 7,
                text=label,
                fill="#fecdd3" if is_iss else "#f5d0fe",
                anchor="sw",
                font=("Segoe UI", 8, "bold" if is_iss or selected else "normal"),
                tags=(tag,),
            )

        self.tag_bind(
            tag,
            "<Button-1>",
            lambda _event, item=satellite: self._select(item),
        )
        self.tag_bind(tag, "<Enter>", lambda _event: self.config(cursor="hand2"))
        self.tag_bind(tag, "<Leave>", lambda _event: self.config(cursor=""))

    def _draw_aircraft(
        self,
        aircraft: SkyAircraft,
        x: float,
        y: float,
        *,
        show_label: bool,
    ) -> None:
        selected = aircraft.icao24 == self.selected_icao24
        highlighted = aircraft.military or (
            aircraft.squawk_alert is not None and aircraft.squawk_alert.highlighted
        )
        tag = f"live-aircraft:{aircraft.icao24}"
        colour = _aircraft_display_colour(aircraft)
        direction = self._aircraft_screen_direction(aircraft, x, y)
        icon_type = aircraft_icon_type(aircraft)
        self._draw_aircraft_icon(
            x,
            y,
            direction,
            icon_type,
            colour,
            selected=selected,
            highlighted=highlighted,
            tags=(tag, "live-aircraft"),
        )

        if show_label:
            identity = aircraft.callsign or aircraft.icao24.upper()
            prefix = ""
            if aircraft.squawk_alert is not None and aircraft.squawk_alert.highlighted:
                prefix = f"{aircraft.squawk_alert.label} [{aircraft.squawk_alert.code}] • "
            elif aircraft.military:
                prefix = "MIL • "
            type_text = aircraft.type_code or icon_type.upper()
            self.create_text(
                x + 10,
                y - 9,
                text=f"{prefix}{identity} • {type_text}",
                fill=_aircraft_label_colour(aircraft),
                anchor="sw",
                font=(
                    "Segoe UI",
                    8,
                    "bold" if selected or highlighted else "normal",
                ),
                tags=(tag, "live-aircraft"),
            )

        self.tag_bind(
            tag,
            "<Button-1>",
            lambda _event, item=aircraft: self._select_aircraft(item),
        )
        self.tag_bind(tag, "<Enter>", lambda _event: self.config(cursor="hand2"))
        self.tag_bind(tag, "<Leave>", lambda _event: self.config(cursor=""))

    def _draw_aircraft_icon(
        self,
        x: float,
        y: float,
        direction: tuple[float, float],
        icon_type: str,
        colour: str,
        *,
        selected: bool,
        highlighted: bool,
        tags: tuple[str, ...],
    ) -> None:
        dx, dy = direction
        length = math.hypot(dx, dy) or 1.0
        dx, dy = dx / length, dy / length
        sx, sy = -dy, dx
        scale = 8.0 if highlighted else (7.0 if selected else 6.0)
        outline = "#ffffff" if selected or highlighted else colour

        def point(forward: float, side: float) -> tuple[float, float]:
            return (
                x + dx * forward * scale + sx * side * scale,
                y + dy * forward * scale + sy * side * scale,
            )

        if icon_type == "helicopter":
            self.create_oval(
                x - 3,
                y - 3,
                x + 3,
                y + 3,
                fill=colour,
                outline=outline,
                width=2 if highlighted else 1,
                tags=tags,
            )
            a, b = point(0, -1.25), point(0, 1.25)
            self.create_line(*a, *b, fill=outline, width=2, tags=tags)
            tail = point(-1.25, 0)
            self.create_line(x, y, *tail, fill=outline, width=2, tags=tags)
            return

        if icon_type == "glider":
            left, right = point(0, -1.45), point(0, 1.45)
            nose, tail = point(0.75, 0), point(-0.85, 0)
            self.create_line(*left, *right, fill=outline, width=2, tags=tags)
            self.create_line(*tail, *nose, fill=outline, width=2, tags=tags)
            return

        if icon_type == "military":
            nose = point(1.25, 0)
            left = point(-0.35, -0.9)
            tail = point(-0.7, 0)
            right = point(-0.35, 0.9)
            self.create_polygon(
                *nose,
                *left,
                *tail,
                *right,
                fill=colour,
                outline=outline,
                width=2,
                tags=tags,
            )
            return

        if icon_type == "uav":
            self.create_rectangle(
                x - 3,
                y - 3,
                x + 3,
                y + 3,
                fill="",
                outline=outline,
                width=2,
                tags=tags,
            )
            self.create_line(x - 6, y, x + 6, y, fill=outline, width=2, tags=tags)
            return

        nose = point(1.3, 0)
        wing_l = point(-0.1, -1.0)
        tail_l = point(-0.65, -0.35)
        tail = point(-1.0, 0)
        tail_r = point(-0.65, 0.35)
        wing_r = point(-0.1, 1.0)
        self.create_polygon(
            *nose,
            *wing_l,
            *tail_l,
            *tail,
            *tail_r,
            *wing_r,
            fill=colour,
            outline=outline,
            width=2 if selected or highlighted else 1,
            tags=tags,
        )


def aircraft_icon_type(aircraft: SkyAircraft) -> str:
    text = " ".join(
        value.lower()
        for value in (aircraft.type_code, aircraft.type_description)
        if value
    )
    if aircraft.military:
        return "military"
    if any(token in text for token in ("helicopter", "rotor", "gyro")):
        return "helicopter"
    if any(token in text for token in ("glider", "sailplane")):
        return "glider"
    if any(token in text for token in ("uav", "drone", "unmanned")):
        return "uav"
    return "airplane"
