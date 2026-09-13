from __future__ import annotations

from .hud_finder_view import apparent_angular_speed_deg_s
from .sky_map import SkySatellite
from .smooth_hud_finder_view import SmoothHudFinderView


def is_live_observing_candidate(satellite: SkySatellite) -> bool:
    """Return whether a satellite should be offered in the observing finder."""
    return satellite.potentially_visible or satellite.twilight_candidate


def select_twilight_finder_satellites(
    satellites: list[SkySatellite],
    *,
    selected_norad: str | None = None,
    limit: int = 6,
    show_all: bool = False,
) -> list[SkySatellite]:
    candidates = [satellite for satellite in satellites if is_live_observing_candidate(satellite)]
    if show_all:
        chosen = candidates
    else:
        chosen = sorted(
            candidates,
            key=lambda satellite: (
                -apparent_angular_speed_deg_s(satellite),
                -satellite.elevation_deg,
                satellite.range_km,
            ),
        )[: max(1, int(limit))]

    if selected_norad is not None and all(satellite.norad_id != selected_norad for satellite in chosen):
        selected = next((satellite for satellite in satellites if satellite.norad_id == selected_norad), None)
        if selected is not None:
            chosen.append(selected)
    return chosen


class TwilightSmoothHudFinderView(SmoothHudFinderView):
    """Stage 14 finder that includes sunlit satellites during twilight."""

    def _rebuild_display_satellites(self) -> None:
        in_view = self._satellites_in_current_view()
        self._satellites = select_twilight_finder_satellites(
            in_view,
            selected_norad=None,
            limit=self.DEFAULT_CANDIDATE_LIMIT,
            show_all=self._show_all_tracked,
        )
        if self._selected_norad is not None and all(
            satellite.norad_id != self._selected_norad for satellite in self._satellites
        ):
            selected = next(
                (satellite for satellite in self._all_satellites if satellite.norad_id == self._selected_norad),
                None,
            )
            if selected is not None:
                self._satellites.append(selected)
        self.redraw()
