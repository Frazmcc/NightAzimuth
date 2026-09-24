from __future__ import annotations

from collections.abc import Iterable

from .aircraft_hud_finder_view import AircraftTwilightFinderView
from .hud_finder_view import apparent_angular_speed_deg_s
from .sky_map import SkySatellite
from .terrain_star_live_view import terrain_profile_for_view

ISS_NORAD_ID = "25544"


class Stage20LiveSkyView(AircraftTwilightFinderView):
    """Stage 20 Live Sky: all in-view satellites with strong priority cues."""

    MAX_FAST_LABELS = 6

    def __init__(self, *args: object, **kwargs: object) -> None:
        self._pass_alerts: tuple[str, ...] = ()
        self._iss_status = "ISS: waiting for orbital data"
        self._visual_candidate_ids: set[str] = set()
        super().__init__(*args, **kwargs)

    def set_pass_alerts(self, alerts: Iterable[str], *, iss_status: str) -> None:
        self._pass_alerts = tuple(alerts)
        self._iss_status = iss_status
        self.redraw()

    def set_visual_candidate_ids(self, norad_ids: Iterable[str]) -> None:
        self._visual_candidate_ids = {str(value).strip() for value in norad_ids if str(value).strip()}
        self.redraw()

    def _ideal_visual_candidate(self, satellite: SkySatellite) -> bool:
        if satellite.norad_id == ISS_NORAD_ID:
            return True
        if satellite.potentially_visible or satellite.twilight_candidate:
            return True
        if satellite.norad_id in self._visual_candidate_ids:
            return True
        estimate = satellite.brightness_estimate
        return estimate is not None and estimate.brighter_bound <= 6.5

    def _priority_satellite_ids(self) -> set[str]:
        fast = sorted(
            self._satellites,
            key=lambda item: (
                -apparent_angular_speed_deg_s(item),
                -item.elevation_deg,
                item.range_km,
            ),
        )[: self.MAX_FAST_LABELS]
        result = {item.norad_id for item in fast}
        result.update(item.norad_id for item in self._satellites if self._ideal_visual_candidate(item))
        result.add(ISS_NORAD_ID)
        if self.selected_norad:
            result.add(self.selected_norad)
        return result

    def _rebuild_display_satellites(self) -> None:
        # Every real satellite in the current field is rendered. Visibility
        # estimates affect prominence and labels, never inclusion.
        in_view = self._satellites_in_current_view()
        self._satellites = sorted(
            in_view,
            key=lambda item: (
                item.norad_id != ISS_NORAD_ID,
                not self._ideal_visual_candidate(item),
                not item.satellite_sunlit,
                -apparent_angular_speed_deg_s(item),
                -item.elevation_deg,
                item.range_km,
            ),
        )
        if self.selected_norad and all(item.norad_id != self.selected_norad for item in self._satellites):
            selected = next(
                (item for item in self._all_satellites if item.norad_id == self.selected_norad),
                None,
            )
            if selected is not None:
                self._satellites.append(selected)
        self.redraw()

    def _draw_satellite(self, satellite: SkySatellite, x: float, y: float) -> None:
        selected = satellite.norad_id == self.selected_norad
        is_iss = satellite.norad_id == ISS_NORAD_ID
        ideal_visual = self._ideal_visual_candidate(satellite)
        priority_ids = self._priority_satellite_ids()

        if is_iss:
            radius = 6.0
            fill = "#facc15"
            outline = "#ffffff"
        elif ideal_visual:
            radius = 4.0
            fill = "#4ade80"
            outline = "#dcfce7" if selected else fill
        elif satellite.satellite_sunlit:
            radius = 2.5
            fill = "#38bdf8"
            outline = "#ffffff" if selected else fill
        else:
            radius = 1.7
            fill = "#64748b"
            outline = "#ffffff" if selected else fill

        if selected:
            radius = max(radius, 5.0)

        tag = f"live-sat:{satellite.norad_id}"
        self.create_oval(
            x - radius,
            y - radius,
            x + radius,
            y + radius,
            fill=fill,
            outline=outline,
            width=2 if selected or is_iss else 1,
            tags=(tag, "live-satellite"),
        )

        if satellite.norad_id in priority_ids:
            label = "ISS" if is_iss else satellite.name
            if ideal_visual and not is_iss:
                label += "  •  VISUAL CANDIDATE"
            speed = apparent_angular_speed_deg_s(satellite)
            if speed > 0.0 and (is_iss or selected or satellite in self._satellites[: self.MAX_FAST_LABELS]):
                label += f"  •  {speed:.2f}°/s"
            self.create_text(
                x + 8,
                y - 8,
                text=label,
                fill="#fde68a" if is_iss else ("#bbf7d0" if ideal_visual else "#bae6fd"),
                anchor="sw",
                font=("Segoe UI", 8, "bold" if is_iss or selected or ideal_visual else "normal"),
                tags=(tag,),
            )

        self.tag_bind(tag, "<Button-1>", lambda _event, item=satellite: self._select(item))
        self.tag_bind(tag, "<Enter>", lambda _event: self.config(cursor="hand2"))
        self.tag_bind(tag, "<Leave>", lambda _event: self.config(cursor=""))

    def _draw_track(self, satellite: SkySatellite, left: float, top: float, right: float, bottom: float) -> None:
        if satellite.norad_id not in self._priority_satellite_ids():
            return
        super()._draw_track(satellite, left, top, right, bottom)

    def redraw(self) -> None:
        super().redraw()
        self._draw_stage20_pass_hud()

    def _draw_stage20_pass_hud(self) -> None:
        left, top, right, _bottom = self._plot_bounds()
        width = max(right - left, 1.0)

        self.create_text(
            left + 10,
            top + 38,
            text=self._iss_status,
            fill="#fde68a",
            anchor="nw",
            font=("Segoe UI", 9, "bold"),
            tags=("stage20-pass-hud",),
        )

        if not self._pass_alerts:
            return

        alert_text = "UPCOMING PASS ≤ 60 MIN\n" + "\n".join(self._pass_alerts[:4])
        box_width = min(width * 0.58, 560.0)
        x0 = left + 8
        y0 = top + 60
        x1 = x0 + box_width
        line_count = 1 + min(4, len(self._pass_alerts))
        y1 = y0 + 24 + line_count * 18
        self.create_rectangle(
            x0,
            y0,
            x1,
            y1,
            fill="#23170a",
            outline="#f59e0b",
            width=2,
            tags=("stage20-pass-hud",),
        )
        self.create_text(
            x0 + 10,
            y0 + 9,
            text=alert_text,
            fill="#fef3c7",
            anchor="nw",
            font=("Consolas", 9, "bold"),
            tags=("stage20-pass-hud",),
        )
        self.tag_raise("stage20-pass-hud")

    def _draw_terrain(self, left: float, top: float, right: float, bottom: float) -> None:
        profile = terrain_profile_for_view(
            self._terrain_horizon,
            facing_deg=self.facing_deg,
            horizontal_fov_deg=self.horizontal_fov_deg,
            minimum_elevation_deg=self.minimum_elevation_deg,
            maximum_elevation_deg=self.maximum_elevation_deg,
        )
        if not profile:
            return

        plot_width = max(right - left, 1.0)
        plot_height = max(bottom - top, 1.0)
        skyline = [
            (left + x_fraction * plot_width, top + y_fraction * plot_height)
            for x_fraction, y_fraction in profile
        ]
        polygon = [
            (left, bottom),
            (left, skyline[0][1]),
            *skyline,
            (right, skyline[-1][1]),
            (right, bottom),
        ]
        self.create_polygon(
            *[coordinate for point in polygon for coordinate in point],
            fill="#111a22",
            outline="",
            tags=("terrain-horizon",),
        )
        if len(skyline) >= 2:
            self.create_line(
                *[coordinate for point in skyline for coordinate in point],
                fill="#9fb97f",
                width=3,
                tags=("terrain-horizon",),
            )
        self.create_text(
            left + 10,
            bottom - 10,
            text="LOCAL LANDSCAPE HORIZON",
            fill="#b7c9a4",
            anchor="sw",
            font=("Segoe UI", 8, "bold"),
            tags=("terrain-horizon",),
        )
