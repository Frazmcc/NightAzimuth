from __future__ import annotations

from io import BytesIO
import threading
import tkinter as tk
from tkinter import ttk

from PIL import Image, ImageTk

from .celestrak import CelestrakClient, CelestrakError
from .gui_stage20_clean import Stage20CleanNightAzimuthApp
from .live_catalog import merge_orbital_catalogues
from .satellite_metadata import SatelliteMetadata, SatelliteMetadataProvider
from .sky_map import SkySatellite
from .stage20_live_sky_view import ISS_NORAD_ID
from .stage20_realtime_satellite_view import Stage20RealtimeSatelliteLiveSkyView
from .track_prediction import TrackPredictor

DRAWER_SATELLITE = "satellite"


class Stage20RealtimeNightAzimuthApp(Stage20CleanNightAzimuthApp):
    """Stage 20 with continuous satellite motion and selected-object intelligence."""

    MAX_REALTIME_PREDICTIONS = 240
    REALTIME_PREDICTION_SECONDS = 90

    def __init__(self) -> None:
        self._satellite_metadata_provider = SatelliteMetadataProvider()
        self._satellite_info_generation = 0
        self._satellite_info_panel: ttk.LabelFrame | None = None
        self._satellite_info_text_var: tk.StringVar | None = None
        self._satellite_info_image_label: ttk.Label | None = None
        self._satellite_info_photo: ImageTk.PhotoImage | None = None
        super().__init__()
        self._remove_prank_button()

    def _build_live_view(self, parent: tk.Misc) -> None:
        super()._build_live_view(parent)
        old_view = self.live_view
        master = old_view.master
        old_view.destroy()
        self.live_view = Stage20RealtimeSatelliteLiveSkyView(
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
        self._build_satellite_info_drawer(master)
        self._apply_live_view_direction(show_error=False)
        self._on_star_layer_changed()
        self._update_airport_landmarks()

    def _remove_prank_button(self) -> None:
        button = getattr(self, "stage20_prank_button", None)
        if button is not None:
            try:
                button.destroy()
            except tk.TclError:
                pass

    def _build_satellite_info_drawer(self, master: tk.Misc) -> None:
        self._satellite_info_text_var = tk.StringVar(
            master=self,
            value="Select a satellite in Live Sky to load verified information.",
        )
        panel = ttk.LabelFrame(master, text="Satellite information", padding=(10, 7))
        panel.columnconfigure(1, weight=1)

        self._satellite_info_image_label = ttk.Label(
            panel,
            text="No satellite selected",
            anchor="center",
            width=28,
        )
        self._satellite_info_image_label.grid(row=0, column=0, sticky="nw", padx=(0, 14))
        ttk.Label(
            panel,
            textvariable=self._satellite_info_text_var,
            justify="left",
            anchor="nw",
            wraplength=980,
            font=("Consolas", 9),
        ).grid(row=0, column=1, sticky="nsew")
        self._satellite_info_panel = panel

        self.stage20_satellite_info_button = ttk.Button(
            self.stage20_drawer_bar,
            text="▸  SATELLITE INFO",
            command=lambda: self._toggle_stage20_drawer(DRAWER_SATELLITE),
        )
        self.stage20_satellite_info_button.pack(side="left", padx=(6, 0))

    def _apply_stage20_drawer_state(self) -> None:
        super()._apply_stage20_drawer_state()
        panel = self._satellite_info_panel
        if panel is not None:
            panel.grid_remove()
        if hasattr(self, "stage20_satellite_info_button"):
            self.stage20_satellite_info_button.configure(
                text=(
                    "▾  SATELLITE INFO"
                    if self._stage20_open_drawer == DRAWER_SATELLITE
                    else "▸  SATELLITE INFO"
                )
            )
        if self._stage20_open_drawer == DRAWER_SATELLITE and panel is not None:
            panel.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(5, 0))

    def _on_live_satellite_selected(self, satellite: SkySatellite) -> None:
        super()._on_live_satellite_selected(satellite)
        self._stage20_open_drawer = DRAWER_SATELLITE
        self._apply_stage20_drawer_state()
        self._show_satellite_loading_state(satellite)

        self._satellite_info_generation += 1
        generation = self._satellite_info_generation
        threading.Thread(
            target=self._load_satellite_information,
            args=(satellite, generation),
            daemon=True,
        ).start()

        # Ensure any clicked object enters the next realtime prediction set even
        # when it was not one of the automatic closest/highest satellites.
        self._start_track_prediction(
            self.selected_name,
            list(getattr(self, "_sky_satellites", ())),
            self._track_generation,
        )

    def _show_satellite_loading_state(self, satellite: SkySatellite) -> None:
        if self._satellite_info_text_var is not None:
            self._satellite_info_text_var.set(
                _format_live_satellite_header(satellite)
                + "\n\nLoading catalogue, mission and image information..."
            )
        self._set_satellite_image(None, "Loading image...")

    def _load_satellite_information(self, satellite: SkySatellite, generation: int) -> None:
        metadata = self._satellite_metadata_provider.lookup(satellite.norad_id, satellite.name)
        image_bytes = self._satellite_metadata_provider.fetch_image(metadata.image_url)
        self.after(0, self._apply_satellite_information, satellite, generation, metadata, image_bytes)

    def _apply_satellite_information(
        self,
        satellite: SkySatellite,
        generation: int,
        metadata: SatelliteMetadata,
        image_bytes: bytes | None,
    ) -> None:
        if generation != self._satellite_info_generation:
            return
        if getattr(self.live_view, "selected_norad", None) != satellite.norad_id:
            return
        if self._satellite_info_text_var is not None:
            self._satellite_info_text_var.set(format_satellite_information(satellite, metadata))
        self._set_satellite_image(image_bytes, "No verified public image available")

    def _set_satellite_image(self, image_bytes: bytes | None, fallback: str) -> None:
        label = self._satellite_info_image_label
        if label is None:
            return
        self._satellite_info_photo = None
        if image_bytes:
            try:
                image = Image.open(BytesIO(image_bytes)).convert("RGB")
                image.thumbnail((240, 150), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(image)
                self._satellite_info_photo = photo
                label.configure(image=photo, text="")
                return
            except (OSError, ValueError):
                pass
        label.configure(image="", text=fallback)

    def _start_track_prediction(
        self,
        profile_name: str,
        satellites: list[SkySatellite],
        generation: int,
    ) -> None:
        if not satellites or not hasattr(self, "live_view"):
            return
        profile = next((item for item in self.profiles if item.name == profile_name), None)
        if profile is None:
            return

        in_view = list(self.live_view._satellites_in_current_view())  # noqa: SLF001
        selected_id = getattr(self.live_view, "selected_norad", None)
        by_id = {item.norad_id: item for item in satellites}

        candidates = sorted(
            in_view,
            key=lambda item: (
                item.norad_id != selected_id,
                item.norad_id != ISS_NORAD_ID,
                item.range_km,
                -item.elevation_deg,
            ),
        )[: self.MAX_REALTIME_PREDICTIONS]
        included = {item.norad_id for item in candidates}
        for required_id in (selected_id, ISS_NORAD_ID):
            if required_id and required_id not in included and required_id in by_id:
                candidates.append(by_id[required_id])
                included.add(required_id)

        if not candidates:
            return
        if self._track_load_in_progress:
            self._pending_track_request = (profile_name, candidates, generation)
            return

        self._track_load_in_progress = True
        self._pending_track_request = None
        observer = self._observer_for_profile(profile)
        threading.Thread(
            target=self._load_projected_tracks,
            args=(profile_name, observer, candidates, generation),
            daemon=True,
        ).start()

    def _load_projected_tracks(
        self,
        profile_name: str,
        observer: object,
        satellites: list[SkySatellite],
        generation: int,
    ) -> None:
        try:
            wanted_ids = {satellite.norad_id for satellite in satellites}
            client = CelestrakClient(cache_directory=self.cache_directory, cache_max_age_minutes=120)
            visual_elements = client.load_group("VISUAL")
            try:
                active_elements = client.load_group("ACTIVE")
            except CelestrakError:
                active_elements = []
            elements = merge_orbital_catalogues(visual_elements, active_elements)
            relevant = [
                fields
                for fields in elements
                if str(fields.get("NORAD_CAT_ID") or "") in wanted_ids
            ]
            tracks = TrackPredictor(observer).predict(
                relevant,
                duration_seconds=self.REALTIME_PREDICTION_SECONDS,
                step_seconds=1,
            )
            self.after(0, self._apply_projected_tracks, profile_name, generation, tracks)
        except Exception as exc:  # noqa: BLE001
            self.after(0, self._projected_track_failed, generation, str(exc))

    def destroy(self) -> None:
        self._satellite_info_generation += 1
        super().destroy()


def format_satellite_information(satellite: SkySatellite, metadata: SatelliteMetadata) -> str:
    lines = [
        metadata.name,
        f"NORAD: {metadata.norad_id}",
        f"COSPAR / International designator: {metadata.international_designator or 'Unavailable'}",
        f"Country / owner: {metadata.owner_code or 'Unavailable'}",
        f"Object type: {metadata.object_type or 'Unavailable'}",
        f"Operational status: {metadata.operational_status or 'Unavailable'}",
        f"Launch: {metadata.launch_date or 'Unavailable'}  •  Site: {metadata.launch_site or 'Unavailable'}",
        "",
        "CURRENT OBSERVER GEOMETRY",
        f"Azimuth: {satellite.azimuth_deg:.2f}°  •  Elevation: {satellite.elevation_deg:.2f}°",
        f"Range: {satellite.range_km:,.0f} km  •  Sunlit: {'Yes' if satellite.satellite_sunlit else 'No'}",
    ]
    if satellite.phase_angle_deg is not None:
        lines.append(f"Phase angle: {satellite.phase_angle_deg:.1f}°")
    if satellite.brightness_estimate is not None:
        estimate = satellite.brightness_estimate
        lines.append(
            f"Brightness estimate: mag {estimate.brighter_bound:.1f} to {estimate.dimmer_bound:.1f}"
        )

    lines.extend(("", "ORBIT / TECHNICAL"))
    technical = (
        ("Period", metadata.period_minutes, "min"),
        ("Inclination", metadata.inclination_deg, "°"),
        ("Apogee", metadata.apogee_km, "km"),
        ("Perigee", metadata.perigee_km, "km"),
        ("Radar cross section", metadata.radar_cross_section_m2, "m²"),
    )
    for label, value, unit in technical:
        lines.append(f"{label}: {'Unavailable' if value is None else f'{value:,.2f} {unit}'}")
    if metadata.orbit_center or metadata.orbit_type:
        lines.append(
            f"Orbit: {metadata.orbit_center or 'Unknown'} / {metadata.orbit_type or 'Unknown'}"
        )

    lines.extend(("", "PURPOSE / MISSION"))
    lines.append(metadata.purpose or "No verified mission summary available.")
    lines.extend(("", "SPECIAL FEATURES / NOTES"))
    lines.append(metadata.technical_notes or "No verified public technical summary available.")
    lines.extend(("", f"Sources: {metadata.information_source or 'CelesTrak SATCAT'}"))
    return "\n".join(lines)


def _format_live_satellite_header(satellite: SkySatellite) -> str:
    return (
        f"{satellite.name}\n"
        f"NORAD: {satellite.norad_id}\n"
        f"Azimuth: {satellite.azimuth_deg:.2f}°  •  Elevation: {satellite.elevation_deg:.2f}°\n"
        f"Range: {satellite.range_km:,.0f} km"
    )


def main() -> int:
    app = Stage20RealtimeNightAzimuthApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
