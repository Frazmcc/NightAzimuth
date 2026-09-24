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
    """Return whether a satellite should be offered as a strong observing candidate."""
    return satellite.potentially_visible or satellite.twilight_candidate


def _satellite_priority(satellite: SkySatellite) -> tuple[float, float, float]:
    """Prefer obvious motion, then elevation, then shorter range."""
    return (
        -apparent_angular_speed_deg_s(satellite),
        -satellite.elevation_deg,
        satellite.range_km,
    )


def select_twilight_finder_satellites(
    satellites: list[SkySatellite],
    *,
    selected_norad: str | None = None,
    limit: int = 6,
    show_all: bool = False,
) -> list[SkySatellite]:
    """Choose observing candidates, but never leave a populated sky untracked.

    Strong naked-eye/twilight candidates remain the preferred contacts. If the
    current sky window contains real tracked satellites but none meet the
    observing criteria, the best tracked satellite is retained as a fallback so
    Live Sky never appears dead merely because conditions are poor or it is
    daylight. Nothing is fabricated: the fallback must already exist in the
    supplied tracked-satellite list.
    """
    candidates = [satellite for satellite in satellites if is_live_observing_candidate(satellite)]
    if show_all:
        chosen = list(candidates)
    else:
        chosen = sorted(candidates, key=_satellite_priority)[: max(1, int(limit))]

    if not chosen and satellites:
        chosen = [min(satellites, key=_satellite_priority)]

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
            self.refresh_constellation_style()

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
