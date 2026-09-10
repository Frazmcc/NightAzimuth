from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from .gui import NightAzimuthApp
from .live_view import LiveSkyView
from .sky_map import SkySatellite


_CARDINALS = {
    "N": 0.0,
    "NE": 45.0,
    "E": 90.0,
    "SE": 135.0,
    "S": 180.0,
    "SW": 225.0,
    "W": 270.0,
    "NW": 315.0,
}


class Stage7NightAzimuthApp(NightAzimuthApp):
    """Stage 7 GUI with the original all-sky radar plus a forward-looking live view."""

    def __init__(self) -> None:
        self.facing_var = tk.StringVar(value="N")
        self.fov_var = tk.StringVar(value="90")
        self.live_detail_var = tk.StringVar(value="Click a satellite in the live view to see details.")
        super().__init__()
        # A forward-looking view benefits from faster position updates than the all-sky prototype.
        self._auto_refresh_ms = 5_000

    def _build_ui(self) -> None:
        super()._build_ui()

        notebook = self._find_notebook(self)
        if notebook is None:
            return

        live_view_tab = ttk.Frame(notebook, padding=8)
        notebook.insert(1, live_view_tab, text="Live view")
        self._build_live_view(live_view_tab)

    def _find_notebook(self, widget: tk.Misc) -> ttk.Notebook | None:
        for child in widget.winfo_children():
            if isinstance(child, ttk.Notebook):
                return child
            nested = self._find_notebook(child)
            if nested is not None:
                return nested
        return None

    def _build_live_view(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        controls = ttk.Frame(parent)
        controls.grid(row=0, column=0, sticky="ew", pady=(0, 8))

        ttk.Label(controls, text="Facing:").pack(side="left")
        facing_entry = ttk.Entry(controls, textvariable=self.facing_var, width=10)
        facing_entry.pack(side="left", padx=(6, 14))
        ttk.Label(controls, text="Enter degrees (0–359) or N, NE, E, SE, S, SW, W, NW").pack(side="left")

        ttk.Label(controls, text="Field of view:").pack(side="left", padx=(24, 6))
        fov_combo = ttk.Combobox(
            controls,
            textvariable=self.fov_var,
            values=("30", "45", "60", "90", "120", "180"),
            width=6,
            state="readonly",
        )
        fov_combo.pack(side="left")
        ttk.Label(controls, text="°").pack(side="left", padx=(2, 8))
        ttk.Button(controls, text="Apply", command=self._apply_live_view_direction).pack(side="left")

        content = ttk.Frame(parent)
        content.grid(row=1, column=0, sticky="nsew")
        content.columnconfigure(0, weight=1)
        content.rowconfigure(0, weight=1)

        self.live_view = LiveSkyView(content, on_select=self._on_live_satellite_selected)
        self.live_view.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        details = ttk.LabelFrame(content, text="Current view", padding=12, width=280)
        details.grid(row=0, column=1, sticky="ns")
        details.grid_propagate(False)

        ttk.Label(
            details,
            textvariable=self.live_detail_var,
            wraplength=250,
            justify="left",
        ).pack(anchor="nw", fill="x")

        ttk.Label(
            details,
            text=(
                "This is the portion of sky directly in front of you. "
                "0° = north, 90° = east, 180° = south, 270° = west. "
                "The display refreshes approximately every 5 seconds."
            ),
            wraplength=250,
            justify="left",
        ).pack(side="bottom", anchor="sw")

        self._apply_live_view_direction(show_error=False)

    def _parse_facing(self) -> float:
        raw = self.facing_var.get().strip().upper()
        if raw in _CARDINALS:
            return _CARDINALS[raw]
        value = float(raw)
        if not 0.0 <= value < 360.0:
            raise ValueError("Facing direction must be between 0 and 359.999 degrees.")
        return value

    def _apply_live_view_direction(self, *, show_error: bool = True) -> None:
        try:
            facing = self._parse_facing()
            fov = float(self.fov_var.get())
        except ValueError as exc:
            if show_error:
                messagebox.showerror("Invalid live view", str(exc), parent=self)
            return

        self.live_view.set_view(facing, fov)
        self.live_detail_var.set(
            f"Facing {facing:.0f}° with a {fov:.0f}° horizontal field of view.\n\n"
            "Yellow = potentially visible. Blue = other tracked satellites."
        )

    def _apply_tracking_data(
        self,
        profile_name: str,
        live_rows: list[tuple[str, ...]],
        pass_rows: list[tuple[str, ...]],
        sky_satellites: list[SkySatellite],
    ) -> None:
        super()._apply_tracking_data(profile_name, live_rows, pass_rows, sky_satellites)
        if profile_name == self.selected_name and hasattr(self, "live_view"):
            self.live_view.set_satellites(sky_satellites)

    def _on_live_satellite_selected(self, satellite: SkySatellite) -> None:
        self.live_view.select_norad(satellite.norad_id)
        self.live_detail_var.set(
            f"{satellite.name}\n\n"
            f"NORAD: {satellite.norad_id}\n"
            f"Azimuth: {satellite.azimuth_deg:.2f}°\n"
            f"Elevation: {satellite.elevation_deg:.2f}°\n"
            f"Range: {satellite.range_km:.0f} km\n\n"
            f"Sunlit: {'Yes' if satellite.satellite_sunlit else 'No'}\n"
            f"Dark sky: {'Yes' if satellite.sky_dark else 'No'}\n"
            f"Potentially visible: {'Yes' if satellite.potentially_visible else 'No'}"
        )


def main() -> int:
    app = Stage7NightAzimuthApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
