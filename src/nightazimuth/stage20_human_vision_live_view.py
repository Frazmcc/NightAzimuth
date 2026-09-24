from __future__ import annotations

from datetime import datetime

from .hud_finder_view import automatic_star_label_limit, is_vega_star, vega_locator_text
from .stage20_clean_live_view import Stage20CleanLiveSkyView
from .stage20_human_vision import (
    apparent_star_magnitude,
    night_colour_mix,
    scintillation_scale,
    star_luminance_fraction,
    star_visible_to_adapted_eye,
)
from .star_field import DeepSkyPoint, PlanetPoint, StarPoint


class Stage20HumanVisionLiveSkyView(Stage20CleanLiveSkyView):
    """Natural celestial scene tuned to approximate unaided human vision."""

    def _sky_state_code(self) -> int:
        snapshot = getattr(self.winfo_toplevel(), "_observing_snapshot", None)
        return int(getattr(snapshot, "sky_state_code", 0))

    def _draw_star(self, star: StarPoint, x: float, y: float) -> None:
        selected = star.hip_id == self._selected_star_hip
        sky_state = self._sky_state_code()
        if not selected and not star_visible_to_adapted_eye(
            star.magnitude,
            star.elevation_deg,
            sky_state,
        ):
            return

        luminance = star_luminance_fraction(star.magnitude, star.elevation_deg, sky_state)
        if selected:
            luminance = 1.0
        phase = datetime.now().second // 3
        twinkle = scintillation_scale(star.hip_id, star.elevation_deg, phase)
        radius = max(0.45, min(2.35, (0.5 + luminance * 1.2) * twinkle))
        if selected:
            radius = 3.0

        level = int(max(88, min(240, 82 + luminance * 166)))
        fill = f"#{level:02x}{level:02x}{min(255, level + 8):02x}"
        tag = f"star:{star.hip_id}"
        self.create_oval(
            x - radius,
            y - radius,
            x + radius,
            y + radius,
            fill="#f8fafc" if selected else fill,
            outline="#ffffff" if selected else "",
            width=1,
            tags=(tag, "star-field"),
        )

        apparent = apparent_star_magnitude(star.magnitude, star.elevation_deg)
        label_limit = min(automatic_star_label_limit(self.horizontal_fov_deg), 1.7)
        automatic_label = bool(star.name and apparent <= label_limit and sky_state <= 2)
        if is_vega_star(star) and sky_state <= 2:
            label = vega_locator_text(star)
            automatic_label = True
        else:
            label = star.name or f"HIP {star.hip_id}"
        if selected:
            label = f"{label}  mag {star.magnitude:.2f}"
        if selected or automatic_label:
            self.create_text(
                x + 6,
                y - 6,
                text=label,
                fill="#e2e8f0" if selected else "#94a3b8",
                anchor="sw",
                font=("Segoe UI", 8 if selected else 7, "bold" if selected else "normal"),
                tags=(tag, "star-field"),
            )

        self.tag_bind(tag, "<Button-1>", lambda _event, item=star: self._select_star(item))
        self.tag_bind(tag, "<Enter>", lambda _event: self.config(cursor="hand2"))
        self.tag_bind(tag, "<Leave>", lambda _event: self.config(cursor=""))

    def _draw_planet(self, planet: PlanetPoint, x: float, y: float) -> None:
        selected = planet.name == self._selected_planet
        sky_state = self._sky_state_code()
        night_mix = night_colour_mix(sky_state)
        radius = 4.2 if selected else 2.8
        tag = f"planet:{planet.name}"

        if night_mix > 0.7:
            fill = "#ddd9c7"
            outline = "#f2e8c7"
        elif night_mix > 0.3:
            fill = "#e8cf91"
            outline = "#f3dfa7"
        else:
            fill = "#f2c45d"
            outline = "#fde68a"

        if planet.name.lower() == "moon":
            # Lightweight vector glare rings: visually useful, no bitmap blur or
            # continuous GPU/CPU effect required.
            for extra, colour in ((13.0, "#26354b"), (8.0, "#48546a")):
                self.create_oval(
                    x - radius - extra,
                    y - radius - extra,
                    x + radius + extra,
                    y + radius + extra,
                    outline=colour,
                    width=1,
                    tags=(tag, "planet-glare"),
                )
            radius = 6.0 if selected else 5.0
            fill = "#dedbd0"
            outline = "#f8f5e8"

        self.create_oval(
            x - radius,
            y - radius,
            x + radius,
            y + radius,
            fill=fill,
            outline="#ffffff" if selected else outline,
            width=2 if selected else 1,
            tags=(tag, "planet-field"),
        )
        self.create_text(
            x + radius + 4,
            y - radius - 2,
            text=planet.name,
            fill="#f1e7c4" if sky_state <= 2 else "#fde68a",
            anchor="sw",
            font=("Segoe UI", 8, "bold" if selected else "normal"),
            tags=(tag, "planet-field"),
        )
        self.tag_bind(tag, "<Button-1>", lambda _event, item=planet: self._select_planet(item))
        self.tag_bind(tag, "<Enter>", lambda _event: self.config(cursor="hand2"))
        self.tag_bind(tag, "<Leave>", lambda _event: self.config(cursor=""))

    def _draw_galaxy(self, galaxy: DeepSkyPoint, x: float, y: float) -> None:
        # Galaxy references remain available but visually recede into the
        # natural scene. Their catalogue presence is not a claim of naked-eye
        # visibility from the current site.
        radius = 2.0
        tag = f"galaxy:{galaxy.name}"
        self.create_oval(
            x - radius * 1.6,
            y - radius,
            x + radius * 1.6,
            y + radius,
            outline="#756985",
            width=1,
            tags=(tag, "galaxy-field"),
        )
