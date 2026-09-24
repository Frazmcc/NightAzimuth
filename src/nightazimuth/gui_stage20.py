from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .aircraft_hud_finder_view import AircraftTwilightFinderView
from .gui_stage16_animation import AnimatedStage16NightAzimuthApp
from .gui_stage19 import Stage19NightAzimuthApp
from .responsive_layout import ResponsiveLayout, calculate_responsive_layout
from .sky_map import SkySatellite
from .visual_theme import PALETTE, apply_stage20_theme


DRAWER_NONE = "none"
DRAWER_DETAILS = "details"
DRAWER_AIRCRAFT = "aircraft"


class Stage20NightAzimuthApp(Stage19NightAzimuthApp):
    """Cinematic, responsive presentation layer over the Stage 19 engines."""

    HUD_REFRESH_MS = 500
    HUD_BACKGROUND_REFRESH_MS = 2_000
    RESIZE_DEBOUNCE_MS = 120

    def __init__(self) -> None:
        self._stage20_fullscreen = False
        self._stage20_hud_job: str | None = None
        self._stage20_resize_job: str | None = None
        self._stage20_layout: ResponsiveLayout | None = None
        self._stage20_layout_signature: tuple[bool, int, int] | None = None
        self._stage20_open_drawer = DRAWER_NONE
        self._stage20_details_panel: ttk.LabelFrame | None = None
        self._stage20_aircraft_panel: ttk.LabelFrame | None = None
        super().__init__()

        self._stage20_layout = self._layout_for_dimensions(
            self.winfo_screenwidth(),
            self.winfo_screenheight(),
        )
        apply_stage20_theme(
            self,
            density=self._stage20_layout.density,
            compact=self._stage20_layout.compact,
        )
        self.configure(background=PALETTE["window"])
        self.title("NightAzimuth — Live Sky Intelligence")

        min_width = min(980, max(760, int(self.winfo_screenwidth() * 0.68)))
        min_height = min(680, max(540, int(self.winfo_screenheight() * 0.68)))
        self.minsize(min_width, min_height)
        self.after_idle(self._maximise_for_screen)

        self.bind("<F11>", self._toggle_fullscreen, add="+")
        self.bind("<Escape>", self._leave_fullscreen, add="+")
        self.bind("<Configure>", self._on_stage20_configure, add="+")
        self._install_live_hud_chrome()
        self._restyle_live_controls()
        self.after_idle(lambda: self._apply_responsive_layout(force=True))
        self._schedule_stage20_hud_tick()

    def _build_live_view(self, parent: tk.Misc) -> None:
        """Build a single-page Live experience with the sky as the primary surface."""
        AnimatedStage16NightAzimuthApp._build_live_view(self, parent)

        old_view = self.live_view
        master = old_view.master
        old_view.destroy()
        self.live_view = AircraftTwilightFinderView(
            master,
            on_select=self._on_live_satellite_selected,
            on_aircraft_select=self._on_live_aircraft_selected,
        )
        self.live_view.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self._build_aircraft_controls(master)
        self._reflow_live_panels(master)
        self._apply_live_view_direction(show_error=False)
        self._on_star_layer_changed()

    def _reflow_live_panels(self, master: tk.Misc) -> None:
        """Put details/contacts below Live Sky and keep them collapsed by default."""
        details = next(
            (
                item
                for item in master.grid_slaves()
                if isinstance(item, ttk.LabelFrame) and str(item.cget("text")).lower() == "live finder"
            ),
            None,
        )
        aircraft = next(
            (
                item
                for item in master.grid_slaves()
                if isinstance(item, ttk.LabelFrame) and str(item.cget("text")).lower() == "aircraft"
            ),
            None,
        )
        self._stage20_details_panel = details
        self._stage20_aircraft_panel = aircraft

        master.columnconfigure(0, weight=1)
        master.columnconfigure(1, weight=0)
        master.rowconfigure(0, weight=1)
        master.rowconfigure(1, weight=0)
        master.rowconfigure(2, weight=0)

        self.live_view.grid_configure(
            row=0,
            column=0,
            columnspan=2,
            sticky="nsew",
            padx=0,
            pady=0,
        )

        if details is not None:
            details.grid_forget()
            details.grid_propagate(True)
            try:
                details.configure(width=1, padding=(10, 7))
            except tk.TclError:
                pass
            children = details.winfo_children()
            if len(children) >= 2:
                children[0].pack_configure(side="left", anchor="nw", fill="x", expand=True, padx=(0, 12))
                children[1].pack_configure(side="left", anchor="nw", fill="x", expand=True)

        if aircraft is not None:
            aircraft.grid_forget()

        self.stage20_drawer_bar = ttk.Frame(master)
        self.stage20_drawer_bar.grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(6, 0),
        )
        self.stage20_details_button = ttk.Button(
            self.stage20_drawer_bar,
            text="▸  LIVE FINDER",
            command=lambda: self._toggle_stage20_drawer(DRAWER_DETAILS),
        )
        self.stage20_details_button.pack(side="left")
        self.stage20_aircraft_button = ttk.Button(
            self.stage20_drawer_bar,
            text="▸  AIRCRAFT CONTACTS",
            command=lambda: self._toggle_stage20_drawer(DRAWER_AIRCRAFT),
        )
        self.stage20_aircraft_button.pack(side="left", padx=(6, 0))
        ttk.Label(
            self.stage20_drawer_bar,
            text="Live Sky remains active while panels are open",
            style="HudMuted.TLabel",
        ).pack(side="right")

    def _toggle_stage20_drawer(self, drawer: str) -> None:
        self._stage20_open_drawer = DRAWER_NONE if self._stage20_open_drawer == drawer else drawer
        self._apply_stage20_drawer_state()

    def _apply_stage20_drawer_state(self) -> None:
        details = self._stage20_details_panel
        aircraft = self._stage20_aircraft_panel
        if details is not None:
            details.grid_remove()
        if aircraft is not None:
            aircraft.grid_remove()

        self.stage20_details_button.configure(
            text=("▾  LIVE FINDER" if self._stage20_open_drawer == DRAWER_DETAILS else "▸  LIVE FINDER")
        )
        self.stage20_aircraft_button.configure(
            text=(
                "▾  AIRCRAFT CONTACTS"
                if self._stage20_open_drawer == DRAWER_AIRCRAFT
                else "▸  AIRCRAFT CONTACTS"
            )
        )

        if self._stage20_open_drawer == DRAWER_DETAILS and details is not None:
            details.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(5, 0))
        elif self._stage20_open_drawer == DRAWER_AIRCRAFT and aircraft is not None:
            aircraft.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(5, 0))
        self.after_idle(lambda: self._apply_responsive_layout(force=True))

    def _apply_tracking_data(
        self,
        profile_name: str,
        live_rows: list[tuple[str, ...]],
        pass_rows: list[tuple[str, ...]],
        sky_satellites: list[SkySatellite],
    ) -> None:
        """Atomically replace the scene; never blank a previously good Live Sky."""
        if (
            profile_name == self.selected_name
            and should_hold_last_good_scene(
                incoming_satellite_count=len(sky_satellites),
                current_satellite_count=len(getattr(self, "_sky_satellites", ())),
            )
        ):
            self._refresh_in_progress = False
            self.refresh_button.config(state="normal")
            self.status_var.set(
                "Refresh returned no usable satellite positions — holding the last good Live Sky while retrying."
            )
            self._schedule_auto_refresh()
            return

        # All expensive work has completed in the background before this UI-thread
        # handoff, so the old scene remains visible until this single replacement.
        super()._apply_tracking_data(profile_name, live_rows, pass_rows, sky_satellites)

    def _layout_for_dimensions(self, width: int, height: int) -> ResponsiveLayout:
        try:
            tk_scaling = float(self.tk.call("tk", "scaling"))
        except (tk.TclError, TypeError, ValueError):
            tk_scaling = 96.0 / 72.0
        return calculate_responsive_layout(width, height, tk_scaling)

    def _maximise_for_screen(self) -> None:
        try:
            self.state("zoomed")
        except tk.TclError:
            width = max(800, int(self.winfo_screenwidth() * 0.94))
            height = max(600, int(self.winfo_screenheight() * 0.90))
            x = max(0, (self.winfo_screenwidth() - width) // 2)
            y = max(0, (self.winfo_screenheight() - height) // 2)
            self.geometry(f"{width}x{height}+{x}+{y}")

    def _on_stage20_configure(self, event: tk.Event) -> None:
        if event.widget is not self:
            return
        if self._stage20_resize_job is not None:
            try:
                self.after_cancel(self._stage20_resize_job)
            except tk.TclError:
                pass
        self._stage20_resize_job = self.after(
            self.RESIZE_DEBOUNCE_MS,
            self._apply_responsive_layout,
        )

    def _apply_responsive_layout(self, *, force: bool = False) -> None:
        self._stage20_resize_job = None
        width = max(1, self.winfo_width())
        height = max(1, self.winfo_height())
        layout = self._layout_for_dimensions(width, height)
        signature = (layout.compact, round(layout.density * 20), layout.table_rows)
        if not force and signature == self._stage20_layout_signature:
            return

        self._stage20_layout = layout
        self._stage20_layout_signature = signature
        apply_stage20_theme(self, density=layout.density, compact=layout.compact)

        if hasattr(self, "aircraft_table"):
            max_drawer_rows = 3 if layout.compact else 5
            self.aircraft_table.configure(
                style="Night.Treeview",
                height=min(layout.table_rows, max_drawer_rows),
            )

        if self._stage20_details_panel is not None:
            children = self._stage20_details_panel.winfo_children()
            wrap = max(260, int(width * 0.42))
            for child in children:
                if isinstance(child, ttk.Label):
                    try:
                        child.configure(wraplength=wrap)
                    except tk.TclError:
                        pass

        self._position_live_hud(layout)

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
        self.stage20_status_var = tk.StringVar(master=self, value="● LIVE")
        self.stage20_status_badge = ttk.Label(
            self.live_view,
            textvariable=self.stage20_status_var,
            style="HudTelemetry.TLabel",
        )
        self.stage20_view_var = tk.StringVar(master=self, value="AZ 000.0°  •  FOV 90°")
        self.stage20_view_badge = ttk.Label(
            self.live_view,
            textvariable=self.stage20_view_var,
            style="HudTelemetry.TLabel",
        )
        self.stage20_fullscreen_hint = ttk.Label(
            self.live_view,
            text="F11  FULLSCREEN",
            style="HudBadge.TLabel",
        )
        layout = self._stage20_layout or self._layout_for_dimensions(
            self.winfo_screenwidth(),
            self.winfo_screenheight(),
        )
        self._position_live_hud(layout)

    def _position_live_hud(self, layout: ResponsiveLayout) -> None:
        if not hasattr(self, "stage20_live_badge"):
            return
        inset = layout.hud_inset
        self.stage20_live_badge.place(x=inset, y=inset)
        self.stage20_status_badge.place(relx=1.0, x=-inset, y=inset, anchor="ne")
        self.stage20_view_badge.place(relx=0.5, rely=1.0, y=-inset, anchor="s")
        self.stage20_fullscreen_hint.place(
            relx=1.0,
            rely=1.0,
            x=-inset,
            y=-inset,
            anchor="se",
        )

    def _restyle_live_controls(self) -> None:
        if hasattr(self, "aircraft_table"):
            self.aircraft_table.configure(style="Night.Treeview")

    def _toggle_fullscreen(self, _event: object | None = None) -> str:
        self._stage20_fullscreen = not self._stage20_fullscreen
        self.attributes("-fullscreen", self._stage20_fullscreen)
        self.after_idle(lambda: self._apply_responsive_layout(force=True))
        return "break"

    def _leave_fullscreen(self, _event: object | None = None) -> str:
        if self._stage20_fullscreen:
            self._stage20_fullscreen = False
            self.attributes("-fullscreen", False)
            self.after_idle(lambda: self._apply_responsive_layout(force=True))
        return "break"

    def _schedule_stage20_hud_tick(self) -> None:
        if self._stage20_hud_job is not None:
            return
        delay = self.HUD_REFRESH_MS if self.state() == "normal" else self.HUD_BACKGROUND_REFRESH_MS
        self._stage20_hud_job = self.after(delay, self._stage20_hud_tick)

    def _stage20_hud_tick(self) -> None:
        self._stage20_hud_job = None
        if not self.winfo_exists():
            return
        if self.state() in {"normal", "zoomed"}:
            self._update_stage20_hud()
        self._schedule_stage20_hud_tick()

    def _update_stage20_hud(self) -> None:
        if hasattr(self, "live_view"):
            facing = getattr(self.live_view, "facing_deg", 0.0)
            fov = getattr(self.live_view, "horizontal_fov_deg", 90.0)
            self.stage20_view_var.set(f"AZ {facing:05.1f}°  •  FOV {fov:.0f}°")

        aircraft_state: str | None = None
        aircraft_count: int | None = None
        snapshot = getattr(self, "_aircraft_snapshot", None)
        if snapshot is not None:
            aircraft_state = snapshot.state.value
            if getattr(self, "aircraft_layer_var", None) is not None and self.aircraft_layer_var.get():
                try:
                    aircraft_count = self.live_view.visible_aircraft_count
                except AttributeError:
                    aircraft_count = None

        sun_altitude: float | None = None
        observing = getattr(self, "_observing_snapshot", None)
        if observing is not None:
            sun_altitude = getattr(observing, "sun_altitude_deg", None)

        self.stage20_status_var.set(
            compose_live_hud_status(
                aircraft_state=aircraft_state,
                aircraft_count=aircraft_count,
                sun_altitude_deg=sun_altitude,
            )
        )

    def destroy(self) -> None:
        for job_name in ("_stage20_hud_job", "_stage20_resize_job"):
            job = getattr(self, job_name, None)
            if job is not None:
                try:
                    self.after_cancel(job)
                except tk.TclError:
                    pass
                setattr(self, job_name, None)
        super().destroy()


def should_hold_last_good_scene(*, incoming_satellite_count: int, current_satellite_count: int) -> bool:
    """Return whether an empty refresh should preserve an already populated sky."""
    return incoming_satellite_count <= 0 and current_satellite_count > 0


def compose_live_hud_status(
    *,
    aircraft_state: str | None,
    aircraft_count: int | None,
    sun_altitude_deg: float | None,
) -> str:
    parts = ["● LIVE"]
    if aircraft_state:
        parts.append(f"ADSB {aircraft_state.upper()}")
    if aircraft_count is not None:
        parts.append(f"{max(0, aircraft_count)} AC")
    if sun_altitude_deg is not None:
        parts.append(f"SUN {sun_altitude_deg:+.1f}°")
    return "  •  ".join(parts)


def main() -> int:
    app = Stage20NightAzimuthApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
