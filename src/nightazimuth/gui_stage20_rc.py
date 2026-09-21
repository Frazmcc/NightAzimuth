from __future__ import annotations

from .aircraft_live import SkyAircraft
from .gui_stage20_realtime import Stage20RealtimeNightAzimuthApp
from .stage20_rc_airports import ResilientAirportLandmarkProvider

DRAWER_DETAILS = "details"


class Stage20ReleaseCandidateApp(Stage20RealtimeNightAzimuthApp):
    """Release-candidate hardening for selected-aircraft detail and airports."""

    def __init__(self) -> None:
        self._rc_airport_provider = ResilientAirportLandmarkProvider()
        super().__init__()

    def _load_airport_landmarks(
        self,
        profile_key: tuple[object, ...],
        generation: int,
        latitude: float,
        longitude: float,
    ) -> None:
        landmarks = self._rc_airport_provider.nearby(
            latitude,
            longitude,
            max_distance_km=250.0,
            limit=12,
        )
        self.after(0, self._apply_airport_landmarks, profile_key, generation, landmarks)

    def _on_live_aircraft_selected(self, aircraft: SkyAircraft) -> None:
        super()._on_live_aircraft_selected(aircraft)
        # Aircraft information is useful only if it is visible. Selecting from
        # either the sky or contact board therefore opens Live Finder immediately.
        self._stage20_open_drawer = DRAWER_DETAILS
        self._apply_stage20_drawer_state()

    def _update_live_view_summary(self) -> None:
        # The historical Live summary shares live_detail_var with selected-aircraft
        # information. Do not overwrite a selected aircraft's route/model/squawk
        # block while panning, zooming or refreshing the Live Sky.
        selected = getattr(getattr(self, "live_view", None), "selected_icao24", None)
        if selected:
            return
        super()._update_live_view_summary()


def main() -> int:
    app = Stage20ReleaseCandidateApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
