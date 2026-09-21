from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .gui_stage19 import Stage19NightAzimuthApp
from .visual_theme import PALETTE, apply_stage20_theme


class Stage20NightAzimuthApp(Stage19NightAzimuthApp):
    """Cinematic, instrument-like presentation layer over the Stage 19 engines."""

    HUD_REFRESH_MS = 500

    def __init__(self) -> None:
        self._stage20_fullscreen = False
        self._stage20_hud_job: str | None = None
        super().__init__()
        apply_stage20_theme(self)
        self.configure(background=PALETTE["window"])
        self.title("NightAzimuth — Live Sky Intelligence")
        self.minsize(1100, 720)
        self.bind("<F11>", self._toggle_fullscreen, add="+")
        self.bind("<Escape>", self._leave_fullscreen, add="+")
        self._install_live_hud_chrome()
        self._restyle_live_controls()
        self._schedule_stage20_hud_tick()

    def _install_live_hud_chrome(self) -> None:
        if not hasattr(self, "live_view"):
            return

        try:
            self.live_view.configure(
                highlightthickness=1,
                highlightbackground=PALETTE["border"],
                highlightcolor=PALETTE["accent"],
                borderwidth=0,
            )
        except tk.TclError:
            pass

        self.stage20_live_badge = ttk.Label(
            self.live_view,
            text="NIGHTAZIMUTH // LIVE SKY",
            style="HudBadge.TLabel",
        )
        self.stage20_live_badge.place(x=14, y=14)

        self.stage20_status_var = tk.StringVar(master=self, value="● LIVE")
        self.stage20_status_badge = ttk.Label(
            self.live_view,
            textvariable=self.stage20_status_var,
            style="HudTelemetry.TLabel",
        )
        self.stage20_status_badge.place(relx=1.0, x=-14, y=14, anchor="ne")

        self.stage20_view_var = tk.StringVar(master=self, value="AZ 000.0°  •  FOV 90°")
        self.stage20_view_badge = ttk.Label(
            self.live_view,
            textvariable=self.stage20_view_var,
            style="HudTelemetry.TLabel",
        )
        self.stage20_view_badge.place(relx=0.5, rely=1.0, y=-14, anchor="s")

    def _restyle_live_controls(self) -> None:
        if hasattr(self, "aircraft_table"):
            self.aircraft_table.configure(style="Night.Treeview")

        # Give the scrollable Live page the same continuous dark surface as the HUD.
        canvas = getattr(self, "_live_scroll_canvas", None)
        if canvas is not None:
            try:
                canvas.configure(
                    background=PALETTE["window"],
                    highlightthickness=0,
                    borderwidth=0,
                )
            except tk.TclError:
                pass

    def _toggle_fullscreen(self, _event: object | None = None) -> str:
        self._stage20_fullscreen = not self._stage20_fullscreen
        self.attributes("-fullscreen", self._stage20_fullscreen)
        return "break"

    def _leave_fullscreen(self, _event: object | None = None) -> str:
        if self._stage20_fullscreen:
            self._stage20_fullscreen = False
            self.attributes("-fullscreen", False)
        return "break"

    def _schedule_stage20_hud_tick(self) -> None:
        if self._stage20_hud_job is None:
            self._stage20_hud_job = self.after(self.HUD_REFRESH_MS, self._stage20_hud_tick)

    def _stage20_hud_tick(self) -> None:
        self._stage20_hud_job = None
        if not self.winfo_exists():
            return
        self._update_stage20_hud()
        self._schedule_stage20_hud_tick()

    def _update_stage20_hud(self) -> None:
        if hasattr(self, "live_view"):
            facing = getattr(self.live_view, "facing_deg", 0.0)
            fov = getattr(self.live_view, "horizontal_fov_deg", 90.0)
            self.stage20_view_var.set(f"AZ {facing:05.1f}°  •  FOV {fov:.0f}°")

        parts = ["● LIVE"]
        snapshot = getattr(self, "_aircraft_snapshot", None)
        if snapshot is not None:
            parts.append(f"ADSB {snapshot.state.value.upper()}")
            if getattr(self, "aircraft_layer_var", None) is not None and self.aircraft_layer_var.get():
                try:
                    parts.append(f"{self.live_view.visible_aircraft_count} AC")
                except AttributeError:
                    pass

        observing = getattr(self, "_observing_snapshot", None)
        if observing is not None:
            sun_altitude = getattr(observing, "sun_altitude_deg", None)
            if sun_altitude is not None:
                parts.append(f"SUN {sun_altitude:+.1f}°")

        self.stage20_status_var.set("  •  ".join(parts))

    def destroy(self) -> None:
        if self._stage20_hud_job is not None:
            try:
                self.after_cancel(self._stage20_hud_job)
            except tk.TclError:
                pass
            self._stage20_hud_job = None
        super().destroy()


def main() -> int:
    app = Stage20NightAzimuthApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
