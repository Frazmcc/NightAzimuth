from __future__ import annotations

from .airport_landmarks import AirportLandmark, airport_in_view
from .stage20_human_vision_live_view import Stage20HumanVisionLiveSkyView
from .stage20_perceptual_projection import project_perceptual_live_view


class Stage20AirportLiveSkyView(Stage20HumanVisionLiveSkyView):
    """Human-vision Live Sky with a restrained major-airport horizon layer."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        self._airport_landmarks: tuple[AirportLandmark, ...] = ()
        super().__init__(*args, **kwargs)

    def set_airport_landmarks(self, airports: tuple[AirportLandmark, ...]) -> None:
        self._airport_landmarks = tuple(airports)
        self.redraw()

    def redraw(self) -> None:
        super().redraw()
        self._draw_airport_landmarks()

    def _draw_airport_landmarks(self) -> None:
        if not self._airport_landmarks:
            return

        left, top, right, bottom = self._plot_bounds()
        width = max(1.0, right - left)
        candidates: list[tuple[float, AirportLandmark]] = []

        for airport in self._airport_landmarks:
            if not airport_in_view(airport, self.facing_deg, self.horizontal_fov_deg):
                continue
            # Airports are orientation references anchored to the terrestrial
            # horizon, not claims that the runway itself is optically visible.
            projection = project_perceptual_live_view(
                airport.bearing_deg,
                max(0.0, self.minimum_elevation_deg),
                self.facing_deg,
                self.horizontal_fov_deg,
                minimum_elevation_deg=self.minimum_elevation_deg,
                maximum_elevation_deg=self.maximum_elevation_deg,
            )
            x = left + projection.x_fraction * width
            candidates.append((x, airport))

        # Nearest airport wins when labels would collide. This deliberately
        # keeps the horizon sparse rather than turning it into a map legend.
        candidates.sort(key=lambda item: item[1].distance_km)
        accepted: list[tuple[float, AirportLandmark]] = []
        for x, airport in candidates:
            if any(abs(x - used_x) < 115.0 for used_x, _ in accepted):
                continue
            accepted.append((x, airport))

        for x, airport in sorted(accepted, key=lambda item: item[0]):
            y = bottom - 10.0
            colour = "#7dd3fc"
            tag = f"airport:{airport.icao}"
            # Minimal runway/terminal glyph.
            self.create_line(
                x - 8,
                y,
                x + 8,
                y,
                fill=colour,
                width=2,
                tags=(tag, "airport-landmark"),
            )
            self.create_line(
                x,
                y - 5,
                x,
                y + 3,
                fill=colour,
                width=1,
                tags=(tag, "airport-landmark"),
            )
            self.create_text(
                x,
                y - 8,
                text=f"{airport.iata} · {airport.name} · {airport.distance_km:.0f} km",
                fill="#bae6fd",
                anchor="s",
                font=("Segoe UI", 7, "bold"),
                tags=(tag, "airport-landmark"),
            )
