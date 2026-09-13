from __future__ import annotations

from .hud_finder_view import apparent_angular_speed_deg_s
from .sky_map import SkySatellite
from .smooth_hud_finder_view import SmoothHudFinderView


_SKY_STATE_BACKGROUNDS = {
    0: "#08111f",  # Dark
    1: "#10182f",  # Astronomical twilight
    2: "#182645",  # Nautical twilight
    3: "#2a3a5b",  # Civil twilight
    4: "#35566f",  # Daylight
}


def live_view_background_for_sky_state(sky_state_code: int) -> str:
    """Return a subdued live-view background for the current solar sky state."""
    return _SKY_STATE_BACKGROUNDS.get(int(sky_state_code), _SKY_STATE_BACKGROUNDS[0])


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
    """Stage 14 finder that includes twilight satellites and solar-state colouring."""

    def __init__(self, *args: object, **kwargs: object) -> None:
        self._last_sky_background: str | None = None
        super().__init__(*args, **kwargs)
        self._apply_observing_background()

    def _apply_observing_background(self) -> None:
        snapshot = getattr(self.winfo_toplevel(), "_observing_snapshot", None)
        sky_state_code = getattr(snapshot, "sky_state_code", 0)
        background = live_view_background_for_sky_state(sky_state_code)
        if background != self._last_sky_background:
            self.configure(background=background)
            self._last_sky_background = background

    def _animation_tick(self) -> None:
        self._apply_observing_background()
        super()._animation_tick()

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
