from __future__ import annotations

import math

from .aircraft_hud_finder_view import _aircraft_display_colour, _aircraft_label_colour
from .aircraft_live import SkyAircraft
from .sky_map import SkySatellite
from .stage20_live_sky_view import ISS_NORAD_ID, Stage20LiveSkyView
from .stage20_perceptual_projection import project_perceptual_live_view


class Stage20CleanLiveSkyView(Stage20LiveSkyView):
    """Lower-noise Stage 20 Live Sky with human-oriented perception cues."""

    def _draw_stage20_pass_hud(self) -> None:
        # ISS/pass information lives in the lower ISS & Passes drawer.
        return

    def _draw_grid(self, left: float, top: float, right: float, bottom: float) -> None:
        """Draw a curved spherical reference field instead of a flat chart grid."""

        plot_width = max(right - left, 1.0)
        plot_height = max(bottom - top, 1.0)
        grid = "#25364a"
        muted = "#718096"
        text = "#dbeafe"

        # Atmospheric airlight is strongest close to the terrestrial horizon.
        haze_top = bottom - plot_height * 0.18
        self.create_rectangle(
            left,
            haze_top,
            right,
            bottom,
            fill="#142334",
            outline="",
            stipple="gray25",
            tags=("perceptual-atmosphere",),
        )

        minimum = self.minimum_elevation_deg
        maximum = self.maximum_elevation_deg
        span = maximum - minimum
        elevation_step = 10.0 if span >= 30.0 else 5.0
        first = math.ceil(minimum / elevation_step) * elevation_step
        elevations = [minimum]
        value = first
        while value < maximum:
            if value > minimum:
                elevations.append(value)
            value += elevation_step
        elevations.append(maximum)

        half_fov = self.horizontal_fov_deg / 2.0
        for elevation in elevations:
            points: list[float] = []
            for index in range(49):
                fraction = index / 48.0
                azimuth = self.facing_deg - half_fov + self.horizontal_fov_deg * fraction
                projection = project_perceptual_live_view(
                    azimuth,
                    elevation,
                    self.facing_deg,
                    self.horizontal_fov_deg,
                    minimum_elevation_deg=minimum,
                    maximum_elevation_deg=maximum,
                )
                points.extend(
                    (
                        left + projection.x_fraction * plot_width,
                        top + projection.y_fraction * plot_height,
                    )
                )
            if len(points) >= 4:
                self.create_line(*points, fill=grid, width=1, tags=("sky-grid",))

        # Sparse azimuth meridians provide orientation without turning the sky
        # back into graph paper.
        for offset_fraction in (-0.5, 0.0, 0.5):
            azimuth = self.facing_deg + half_fov * offset_fraction
            points = []
            for index in range(37):
                elevation = minimum + span * index / 36.0
                projection = project_perceptual_live_view(
                    azimuth,
                    elevation,
                    self.facing_deg,
                    self.horizontal_fov_deg,
                    minimum_elevation_deg=minimum,
                    maximum_elevation_deg=maximum,
                )
                points.extend(
                    (
                        left + projection.x_fraction * plot_width,
                        top + projection.y_fraction * plot_height,
                    )
                )
            if len(points) >= 4:
                self.create_line(*points, fill=grid, width=1, tags=("sky-grid",))

        self.create_text(
            (left + right) / 2,
            bottom + 18,
            text=f"Facing {self.facing_deg:.0f}°",
            fill=text,
            font=("Segoe UI", 10, "bold"),
        )
        self.create_text(
            left,
            top - 10,
            text=(
                f"Elevation {minimum:.0f}–{maximum:.0f}°  •  "
                f"Field {self.horizontal_fov_deg:.0f}°"
            ),
            fill=muted,
            anchor="w",
            font=("Segoe UI", 8),
        )

    def _draw_terrain(self, left: float, top: float, right: float, bottom: float) -> None:
        """Render the real local skyline through the same spherical projection."""

        if not self._terrain_horizon:
            return
        plot_width = max(right - left, 1.0)
        plot_height = max(bottom - top, 1.0)
        half_fov = self.horizontal_fov_deg / 2.0
        skyline: list[tuple[float, float]] = []
        for point in self._terrain_horizon:
            offset = (point.azimuth_deg - self.facing_deg + 180.0) % 360.0 - 180.0
            if abs(offset) > half_fov:
                continue
            elevation = max(
                self.minimum_elevation_deg,
                min(self.maximum_elevation_deg, point.elevation_deg),
            )
            projection = project_perceptual_live_view(
                point.azimuth_deg,
                elevation,
                self.facing_deg,
                self.horizontal_fov_deg,
                minimum_elevation_deg=self.minimum_elevation_deg,
                maximum_elevation_deg=self.maximum_elevation_deg,
            )
            skyline.append(
                (
                    left + projection.x_fraction * plot_width,
                    top + projection.y_fraction * plot_height,
                )
            )
        skyline.sort(key=lambda point: point[0])
        if len(skyline) < 2:
            return

        polygon = [
            (left, bottom),
            (left, skyline[0][1]),
            *skyline,
            (right, skyline[-1][1]),
            (right, bottom),
        ]
        flattened = [coordinate for point in polygon for coordinate in point]
        skyline_flat = [coordinate for point in skyline for coordinate in point]

        # Broad faint airlight behind the ridge gives a natural distance cue
        # without pretending that the terrain data contains full 3D surfaces.
        self.create_line(
            *skyline_flat,
            fill="#607386",
            width=6,
            stipple="gray25",
            tags=("terrain-airlight",),
        )
        self.create_polygon(
            *flattened,
            fill="#101820",
            outline="",
            tags=("terrain-horizon",),
        )
        self.create_line(
            *skyline_flat,
            fill="#82947a",
            width=2,
            tags=("terrain-horizon",),
        )

    def _draw_satellite(self, satellite: SkySatellite, x: float, y: float) -> None:
        selected = satellite.norad_id == self.selected_norad
        is_iss = satellite.norad_id == ISS_NORAD_ID
        priority_ids = self._priority_satellite_ids()
        peripheral_scale = 1.0 if selected or is_iss else self._peripheral_scale(x, y)

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
        radius *= peripheral_scale

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

        self.tag_bind(tag, "<Button-1>", lambda _event, item=satellite: self._select(item))
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
            peripheral_scale=(1.0 if selected or highlighted else self._peripheral_scale(x, y)),
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
                font=("Segoe UI", 8, "bold" if selected or highlighted else "normal"),
                tags=(tag, "live-aircraft"),
            )

        self.tag_bind(tag, "<Button-1>", lambda _event, item=aircraft: self._select_aircraft(item))
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
        peripheral_scale: float = 1.0,
        tags: tuple[str, ...],
    ) -> None:
        dx, dy = direction
        length = math.hypot(dx, dy) or 1.0
        dx, dy = dx / length, dy / length
        sx, sy = -dy, dx
        scale = (8.0 if highlighted else (7.0 if selected else 6.0)) * peripheral_scale
        outline = "#ffffff" if selected or highlighted else colour

        def point(forward: float, side: float) -> tuple[float, float]:
            return (
                x + dx * forward * scale + sx * side * scale,
                y + dy * forward * scale + sy * side * scale,
            )

        if icon_type == "helicopter":
            radius = 3.0 * peripheral_scale
            self.create_oval(
                x - radius,
                y - radius,
                x + radius,
                y + radius,
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
            radius = 3.0 * peripheral_scale
            self.create_rectangle(
                x - radius,
                y - radius,
                x + radius,
                y + radius,
                fill="",
                outline=outline,
                width=2,
                tags=tags,
            )
            self.create_line(
                x - 6 * peripheral_scale,
                y,
                x + 6 * peripheral_scale,
                y,
                fill=outline,
                width=2,
                tags=tags,
            )
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

    def _peripheral_scale(self, x: float, y: float) -> float:
        left, top, right, bottom = self._plot_bounds()
        half_width = max((right - left) / 2.0, 1.0)
        half_height = max((bottom - top) / 2.0, 1.0)
        centre_x = (left + right) / 2.0
        centre_y = (top + bottom) / 2.0
        eccentricity = min(
            1.0,
            math.hypot((x - centre_x) / half_width, (y - centre_y) / half_height),
        )
        return 1.0 - 0.25 * eccentricity


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
