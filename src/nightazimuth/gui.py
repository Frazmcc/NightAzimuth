from __future__ import annotations

from pathlib import Path
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from . import COPYRIGHT, __version__
from .appearance import APPEARANCE_MODES, AppearancePreferenceStore, appearance_uses_dark_mode
from .celestrak import CelestrakClient, CelestrakError
from .config import ObserverConfig
from .location_profiles import LocationProfile, LocationProfileStore
from .passes import PassPredictor
from .sky_map import SkyMap, SkySatellite
from .tracker import SatelliteTracker
from .visibility import VisibilityEngine


class NightAzimuthApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("NightAzimuth")
        self.geometry("1220x780")
        self.minsize(1000, 650)

        self.store = LocationProfileStore()
        self.appearance_store = AppearancePreferenceStore(self.store.path.parent / "preferences.json")
        self.appearance_mode = self.appearance_store.load()
        self._default_ttk_theme = ttk.Style(self).theme_use()
        self._apply_appearance_theme()

        self.profiles, self.selected_name = self.store.load()
        self._refresh_in_progress = False
        self._sky_satellites: list[SkySatellite] = []
        self._auto_refresh_job: str | None = None
        self._auto_refresh_ms = 30_000

        self._build_ui()
        self.apply_appearance(self)
        self._refresh_location_selector()
        if self._selected_profile() is not None:
            self.after(250, self.refresh_data)

    @property
    def cache_directory(self) -> Path:
        return self.store.path.parent / "cache"

    def set_appearance_mode(self, mode: str) -> None:
        """Persist and immediately apply the selected application appearance."""

        self.appearance_mode = self.appearance_store.save(mode)
        self._apply_appearance_theme()
        self.apply_appearance(self)

    def _apply_appearance_theme(self) -> None:
        dark = appearance_uses_dark_mode(self.appearance_mode)
        style = ttk.Style(self)
        if dark:
            if style.theme_use() != "clam":
                style.theme_use("clam")
            background = "#111827"
            surface = "#1f2937"
            field = "#0f172a"
            foreground = "#e5e7eb"
            selected = "#2563eb"
            style.configure(".", background=background, foreground=foreground)
            style.configure("TFrame", background=background)
            style.configure("TLabel", background=background, foreground=foreground)
            style.configure("TLabelframe", background=background, foreground=foreground)
            style.configure("TLabelframe.Label", background=background, foreground=foreground)
            style.configure("TButton", background=surface, foreground=foreground, bordercolor="#4b5563")
            style.map("TButton", background=[("active", "#374151"), ("pressed", "#4b5563")])
            style.configure("TCheckbutton", background=background, foreground=foreground)
            style.map("TCheckbutton", background=[("active", background)])
            style.configure("TEntry", fieldbackground=field, foreground=foreground, insertcolor=foreground)
            style.configure(
                "TCombobox",
                fieldbackground=field,
                background=surface,
                foreground=foreground,
                arrowcolor=foreground,
            )
            style.map(
                "TCombobox",
                fieldbackground=[("readonly", field)],
                foreground=[("readonly", foreground)],
                selectbackground=[("readonly", field)],
                selectforeground=[("readonly", foreground)],
            )
            style.configure("TNotebook", background=background, borderwidth=0)
            style.configure("TNotebook.Tab", background=surface, foreground=foreground, padding=(8, 4))
            style.map(
                "TNotebook.Tab",
                background=[("selected", "#374151"), ("active", "#2b3647")],
            )
            style.configure(
                "Treeview",
                background=field,
                fieldbackground=field,
                foreground=foreground,
                bordercolor="#374151",
            )
            style.map(
                "Treeview",
                background=[("selected", selected)],
                foreground=[("selected", "#ffffff")],
            )
            style.configure("Treeview.Heading", background=surface, foreground=foreground)
            style.map("Treeview.Heading", background=[("active", "#374151")])
            style.configure("TScrollbar", background=surface, troughcolor=field, arrowcolor=foreground)
            style.configure("TScale", background=background, troughcolor=field)
            self.option_add("*TCombobox*Listbox.background", field)
            self.option_add("*TCombobox*Listbox.foreground", foreground)
            self.option_add("*TCombobox*Listbox.selectBackground", selected)
            self.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
        else:
            if style.theme_use() != self._default_ttk_theme:
                style.theme_use(self._default_ttk_theme)
            background = "#f0f0f0"
            self.option_add("*TCombobox*Listbox.background", "#ffffff")
            self.option_add("*TCombobox*Listbox.foreground", "#000000")
            self.option_add("*TCombobox*Listbox.selectBackground", "#0078d7")
            self.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
        self.configure(background=background)

    def apply_appearance(self, widget: tk.Misc) -> None:
        """Apply colours to classic Tk widgets not controlled by ttk styles."""

        dark = appearance_uses_dark_mode(self.appearance_mode)
        background = "#111827" if dark else "#f0f0f0"
        field = "#0f172a" if dark else "#ffffff"
        foreground = "#e5e7eb" if dark else "#000000"
        selected = "#2563eb" if dark else "#0078d7"

        if isinstance(widget, (tk.Tk, tk.Toplevel)):
            widget.configure(background=background)
        elif isinstance(widget, tk.Listbox):
            widget.configure(
                background=field,
                foreground=foreground,
                selectbackground=selected,
                selectforeground="#ffffff",
            )
        elif isinstance(widget, tk.Scale):
            widget.configure(
                background=background,
                foreground=foreground,
                troughcolor=field,
                highlightbackground=background,
            )
        elif isinstance(widget, tk.Canvas) and widget is getattr(self, "_live_scroll_canvas", None):
            widget.configure(background=background)

        for child in widget.winfo_children():
            self.apply_appearance(child)

    def _build_ui(self) -> None:
        header = ttk.Frame(self, padding=12)
        header.pack(fill="x")

        branding = ttk.Frame(header)
        branding.pack(side="left")
        ttk.Label(branding, text="NightAzimuth", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(branding, text=COPYRIGHT, font=("Segoe UI", 8)).pack(anchor="w")

        ttk.Label(header, text="Location:").pack(side="left", padx=(30, 6))
        self.location_var = tk.StringVar()
        self.location_combo = ttk.Combobox(header, textvariable=self.location_var, state="readonly", width=28)
        self.location_combo.pack(side="left")
        self.location_combo.bind("<<ComboboxSelected>>", self._on_location_changed)

        self.refresh_button = ttk.Button(header, text="Refresh", command=self.refresh_data)
        self.refresh_button.pack(side="right", padx=(8, 0))
        ttk.Button(header, text="Settings", command=self.open_settings).pack(side="right", padx=(8, 0))
        ttk.Button(header, text="Credits", command=self.open_credits).pack(side="right")

        body = ttk.Frame(self, padding=(12, 0, 12, 12))
        body.pack(fill="both", expand=True)

        self.location_summary = ttk.Label(body, text="No location configured.")
        self.location_summary.pack(anchor="w", pady=(0, 8))

        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(body, textvariable=self.status_var).pack(anchor="w", pady=(0, 8))

        notebook = ttk.Notebook(body)
        notebook.pack(fill="both", expand=True)

        sky_tab = ttk.Frame(notebook, padding=8)
        live_tab = ttk.Frame(notebook, padding=8)
        passes_tab = ttk.Frame(notebook, padding=8)
        notebook.add(sky_tab, text="Sky map")
        notebook.add(live_tab, text="Live satellites")
        notebook.add(passes_tab, text="Upcoming passes")

        self._build_sky_map(sky_tab)
        self._build_live_table(live_tab)
        self._build_pass_table(passes_tab)

        ttk.Label(
            body,
            text=(
                "Potentially visible means the satellite is sunlit while your sky is sufficiently dark. "
                "It does not yet include cloud, haze, magnitude, local obstructions, or camera sensitivity."
            ),
            wraplength=1160,
        ).pack(anchor="w", pady=(8, 0))
        ttk.Separator(body, orient="horizontal").pack(fill="x", pady=(8, 4))
        ttk.Label(body, text=COPYRIGHT, font=("Segoe UI", 8)).pack(anchor="e")

    def _build_sky_map(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(0, weight=1)

        self.sky_map = SkyMap(parent, on_select=self._on_map_satellite_selected)
        self.sky_map.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        details = ttk.LabelFrame(parent, text="Selected satellite", padding=12, width=300)
        details.grid(row=0, column=1, sticky="ns")
        details.grid_propagate(False)
        self.satellite_detail_var = tk.StringVar(
            value="Click a satellite marker to see its current position and visibility information."
        )
        ttk.Label(details, textvariable=self.satellite_detail_var, wraplength=270, justify="left").pack(
            anchor="nw", fill="x"
        )

        ttk.Label(
            details,
            text="Map: horizon = outer edge, zenith = centre. Yellow = potentially visible; blue = other above-horizon satellites.",
            wraplength=270,
            justify="left",
        ).pack(anchor="sw", side="bottom")

    def _build_live_table(self, parent: ttk.Frame) -> None:
        columns = ("name", "norad", "az", "el", "range", "sunlit", "dark", "potential")
        self.live_tree = ttk.Treeview(parent, columns=columns, show="headings", height=18)
        headings = {
            "name": "Satellite", "norad": "NORAD", "az": "Azimuth", "el": "Elevation",
            "range": "Range km", "sunlit": "Sunlit", "dark": "Dark sky", "potential": "Potential",
        }
        widths = {
            "name": 260, "norad": 80, "az": 90, "el": 90, "range": 90,
            "sunlit": 75, "dark": 75, "potential": 90,
        }
        for column in columns:
            self.live_tree.heading(column, text=headings[column])
            self.live_tree.column(column, width=widths[column], anchor="center")
        self.live_tree.column("name", anchor="w")
        self.live_tree.bind("<<TreeviewSelect>>", self._on_table_satellite_selected)

        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=self.live_tree.yview)
        self.live_tree.configure(yscrollcommand=scrollbar.set)
        self.live_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _build_pass_table(self, parent: ttk.Frame) -> None:
        columns = ("name", "norad", "rise", "peak", "set", "maxel")
        self.pass_tree = ttk.Treeview(parent, columns=columns, show="headings", height=18)
        headings = {
            "name": "Satellite", "norad": "NORAD", "rise": "Rise UTC",
            "peak": "Peak UTC", "set": "Set UTC", "maxel": "Max elevation",
        }
        widths = {"name": 260, "norad": 80, "rise": 170, "peak": 170, "set": 170, "maxel": 110}
        for column in columns:
            self.pass_tree.heading(column, text=headings[column])
            self.pass_tree.column(column, width=widths[column], anchor="center")
        self.pass_tree.column("name", anchor="w")

        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=self.pass_tree.yview)
        self.pass_tree.configure(yscrollcommand=scrollbar.set)
        self.pass_tree.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    def _refresh_location_selector(self) -> None:
        names = [profile.name for profile in self.profiles]
        self.location_combo["values"] = names
        if self.selected_name not in names:
            self.selected_name = names[0] if names else None
        self.location_var.set(self.selected_name or "")
        self._update_location_summary()

    def _update_location_summary(self) -> None:
        profile = self._selected_profile()
        if profile is None:
            self.location_summary.config(text="No location configured. Open Settings to add one.")
            return
        self.location_summary.config(
            text=(
                f"Selected location: {profile.name}  |  Latitude {profile.latitude:.5f}, "
                f"Longitude {profile.longitude:.5f}, Altitude {profile.altitude_m:.0f} m"
            )
        )

    def _selected_profile(self) -> LocationProfile | None:
        return next((profile for profile in self.profiles if profile.name == self.selected_name), None)

    def _observer_for_profile(self, profile: LocationProfile) -> ObserverConfig:
        return ObserverConfig(latitude=profile.latitude, longitude=profile.longitude, altitude_m=profile.altitude_m)

    def _on_location_changed(self, _event: object | None = None) -> None:
        selected = self.location_var.get().strip()
        self.selected_name = selected or None
        self.store.save(self.profiles, self.selected_name)
        self._update_location_summary()
        self.refresh_data()

    def refresh_data(self) -> None:
        if self._refresh_in_progress:
            return
        profile = self._selected_profile()
        if profile is None:
            messagebox.showinfo("Location required", "Open Settings and add an observing location first.", parent=self)
            return

        if self._auto_refresh_job is not None:
            self.after_cancel(self._auto_refresh_job)
            self._auto_refresh_job = None

        self._refresh_in_progress = True
        self.refresh_button.config(state="disabled")
        self.status_var.set("Refreshing orbital data and calculations...")
        threading.Thread(target=self._load_tracking_data, args=(profile,), daemon=True).start()

    def _load_tracking_data(self, profile: LocationProfile) -> None:
        try:
            observer = self._observer_for_profile(profile)
            client = CelestrakClient(cache_directory=self.cache_directory, cache_max_age_minutes=120)
            elements = client.load_group("VISUAL")
            elements_by_norad = {
                str(item.get("NORAD_CAT_ID") or ""): item
                for item in elements if item.get("NORAD_CAT_ID") is not None
            }

            tracker = SatelliteTracker(observer)
            positions = tracker.positions_above_horizon(elements)
            visibility = VisibilityEngine(observer, cache_directory=self.cache_directory, darkness_threshold_deg=-6.0)

            live_rows: list[tuple[str, ...]] = []
            sky_satellites: list[SkySatellite] = []
            for item in positions:
                fields = elements_by_norad.get(item.norad_id)
                if fields is None:
                    continue
                status = visibility.evaluate(fields)
                sky_satellites.append(
                    SkySatellite(
                        name=item.name,
                        norad_id=item.norad_id,
                        azimuth_deg=item.azimuth_deg,
                        elevation_deg=item.elevation_deg,
                        range_km=item.range_km,
                        satellite_sunlit=status.satellite_sunlit,
                        sky_dark=status.sky_dark,
                        potentially_visible=status.potentially_visible,
                    )
                )
                live_rows.append(
                    (
                        item.name, item.norad_id, f"{item.azimuth_deg:.2f}°", f"{item.elevation_deg:.2f}°",
                        f"{item.range_km:.0f}", "YES" if status.satellite_sunlit else "NO",
                        "YES" if status.sky_dark else "NO", "YES" if status.potentially_visible else "NO",
                    )
                )

            predictor = PassPredictor(observer)
            passes = predictor.predict(elements, hours=24.0, minimum_elevation_deg=10.0)
            pass_rows = [
                (
                    item.name, item.norad_id, item.rise_time.strftime("%Y-%m-%d %H:%M:%S"),
                    item.culmination_time.strftime("%Y-%m-%d %H:%M:%S"),
                    item.set_time.strftime("%Y-%m-%d %H:%M:%S"), f"{item.max_elevation_deg:.2f}°",
                )
                for item in passes
            ]
            self.after(0, self._apply_tracking_data, profile.name, live_rows, pass_rows, sky_satellites)
        except (CelestrakError, OSError, ValueError) as exc:
            self.after(0, self._show_refresh_error, str(exc))
        except Exception as exc:  # noqa: BLE001
            self.after(0, self._show_refresh_error, f"Unexpected error: {exc}")

    def _apply_tracking_data(
        self,
        profile_name: str,
        live_rows: list[tuple[str, ...]],
        pass_rows: list[tuple[str, ...]],
        sky_satellites: list[SkySatellite],
    ) -> None:
        if profile_name != self.selected_name:
            self._refresh_in_progress = False
            self.refresh_button.config(state="normal")
            self.refresh_data()
            return

        for tree in (self.live_tree, self.pass_tree):
            for row in tree.get_children():
                tree.delete(row)

        for row in live_rows:
            self.live_tree.insert("", tk.END, iid=f"sat-{row[1]}", values=row)
        for row in pass_rows:
            self.pass_tree.insert("", tk.END, values=row)

        self._sky_satellites = sky_satellites
        self.sky_map.set_satellites(sky_satellites)
        self.satellite_detail_var.set(
            "Click a satellite marker to see its current position and visibility information."
        )
        self.status_var.set(
            f"Loaded {len(live_rows)} satellites above the horizon and {len(pass_rows)} passes. "
            "Sky map refreshes every 30 seconds."
        )
        self._refresh_in_progress = False
        self.refresh_button.config(state="normal")
        self._schedule_auto_refresh()

    def _schedule_auto_refresh(self) -> None:
        if self._auto_refresh_job is not None:
            self.after_cancel(self._auto_refresh_job)
        self._auto_refresh_job = self.after(self._auto_refresh_ms, self.refresh_data)

    def _on_map_satellite_selected(self, satellite: SkySatellite) -> None:
        self._show_satellite_details(satellite)
        iid = f"sat-{satellite.norad_id}"
        if self.live_tree.exists(iid):
            self.live_tree.selection_set(iid)
            self.live_tree.see(iid)

    def _on_table_satellite_selected(self, _event: object | None = None) -> None:
        selection = self.live_tree.selection()
        if not selection:
            return
        values = self.live_tree.item(selection[0], "values")
        if len(values) < 2:
            return
        norad_id = str(values[1])
        satellite = next((item for item in self._sky_satellites if item.norad_id == norad_id), None)
        if satellite is not None:
            self.sky_map.select_norad(norad_id)
            self._show_satellite_details(satellite)

    def _show_satellite_details(self, satellite: SkySatellite) -> None:
        self.satellite_detail_var.set(
            f"{satellite.name}\n\n"
            f"NORAD: {satellite.norad_id}\n"
            f"Azimuth: {satellite.azimuth_deg:.2f}°\n"
            f"Elevation: {satellite.elevation_deg:.2f}°\n"
            f"Range: {satellite.range_km:.0f} km\n\n"
            f"Sunlit: {'Yes' if satellite.satellite_sunlit else 'No'}\n"
            f"Dark sky: {'Yes' if satellite.sky_dark else 'No'}\n"
            f"Potentially visible: {'Yes' if satellite.potentially_visible else 'No'}"
        )

    def _show_refresh_error(self, error: str) -> None:
        self.status_var.set("Refresh failed")
        self._refresh_in_progress = False
        self.refresh_button.config(state="normal")
        self._schedule_auto_refresh()
        messagebox.showerror("NightAzimuth refresh failed", error, parent=self)

    def open_settings(self) -> None:
        SettingsWindow(self)

    def open_credits(self) -> None:
        messagebox.showinfo(
            "NightAzimuth Credits",
            f"NightAzimuth {__version__}\n\n{COPYRIGHT}\n\nSatellite tracking and observing utility.",
            parent=self,
        )


class SettingsWindow(tk.Toplevel):
    def __init__(self, app: NightAzimuthApp) -> None:
        super().__init__(app)
        self.app = app
        self.title("NightAzimuth Settings")
        self.geometry("620x420")
        self.resizable(False, False)
        self.transient(app)
        self.grab_set()

        self.name_var = tk.StringVar()
        self.latitude_var = tk.StringVar()
        self.longitude_var = tk.StringVar()
        self.altitude_var = tk.StringVar(value="0")
        self.appearance_var = tk.StringVar(value=app.appearance_mode)

        self._build_ui()
        self._refresh_list()
        self.app.apply_appearance(self)

    def _build_ui(self) -> None:
        outer = ttk.Frame(self, padding=16)
        outer.pack(fill="both", expand=True)
        left = ttk.Frame(outer)
        left.pack(side="left", fill="y", padx=(0, 20))

        ttk.Label(left, text="Saved locations", font=("Segoe UI", 11, "bold")).pack(anchor="w")
        self.location_list = tk.Listbox(left, width=25, height=15)
        self.location_list.pack(fill="y", pady=(8, 8))
        self.location_list.bind("<<ListboxSelect>>", self._load_selected)
        ttk.Button(left, text="New", command=self._new_profile).pack(fill="x", pady=2)
        ttk.Button(left, text="Delete", command=self._delete_profile).pack(fill="x", pady=2)

        form = ttk.Frame(outer)
        form.pack(side="left", fill="both", expand=True)
        ttk.Label(form, text="Location name").grid(row=0, column=0, sticky="w", pady=6)
        ttk.Entry(form, textvariable=self.name_var, width=34).grid(row=0, column=1, sticky="ew", pady=6)
        ttk.Label(form, text="Latitude").grid(row=1, column=0, sticky="w", pady=6)
        ttk.Entry(form, textvariable=self.latitude_var).grid(row=1, column=1, sticky="ew", pady=6)
        ttk.Label(form, text="Longitude").grid(row=2, column=0, sticky="w", pady=6)
        ttk.Entry(form, textvariable=self.longitude_var).grid(row=2, column=1, sticky="ew", pady=6)
        ttk.Label(form, text="Altitude (m)").grid(row=3, column=0, sticky="w", pady=6)
        ttk.Entry(form, textvariable=self.altitude_var).grid(row=3, column=1, sticky="ew", pady=6)
        ttk.Label(
            form,
            text="Use decimal degrees. North/east are positive; south/west are negative.",
            wraplength=330,
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(4, 14))
        ttk.Button(form, text="Save location", command=self._save_profile).grid(
            row=5, column=0, columnspan=2, sticky="ew", pady=4
        )
        ttk.Button(form, text="Use this location", command=self._use_profile).grid(
            row=6, column=0, columnspan=2, sticky="ew", pady=4
        )

        ttk.Separator(form, orient="horizontal").grid(
            row=7, column=0, columnspan=2, sticky="ew", pady=(14, 8)
        )
        ttk.Label(form, text="Appearance").grid(row=8, column=0, sticky="w", pady=6)
        appearance = ttk.Combobox(
            form,
            textvariable=self.appearance_var,
            values=APPEARANCE_MODES,
            state="readonly",
            width=12,
        )
        appearance.grid(row=8, column=1, sticky="w", pady=6)
        appearance.bind("<<ComboboxSelected>>", self._on_appearance_changed)
        ttk.Label(
            form,
            text="System follows the Windows app theme when NightAzimuth starts.",
            wraplength=330,
        ).grid(row=9, column=0, columnspan=2, sticky="w", pady=(0, 4))
        form.columnconfigure(1, weight=1)

    def _on_appearance_changed(self, _event: object | None = None) -> None:
        self.app.set_appearance_mode(self.appearance_var.get())

    def _refresh_list(self) -> None:
        self.location_list.delete(0, tk.END)
        for profile in self.app.profiles:
            self.location_list.insert(tk.END, profile.name)

    def _new_profile(self) -> None:
        self.location_list.selection_clear(0, tk.END)
        self.name_var.set("")
        self.latitude_var.set("")
        self.longitude_var.set("")
        self.altitude_var.set("0")

    def _load_selected(self, _event: object | None = None) -> None:
        selection = self.location_list.curselection()
        if not selection:
            return
        profile = self.app.profiles[selection[0]]
        self.name_var.set(profile.name)
        self.latitude_var.set(str(profile.latitude))
        self.longitude_var.set(str(profile.longitude))
        self.altitude_var.set(str(profile.altitude_m))

    def _validated_profile(self) -> LocationProfile | None:
        name = self.name_var.get().strip()
        if not name:
            messagebox.showerror("Invalid location", "Enter a location name.", parent=self)
            return None
        try:
            latitude = float(self.latitude_var.get())
            longitude = float(self.longitude_var.get())
            altitude = float(self.altitude_var.get() or "0")
        except ValueError:
            messagebox.showerror("Invalid location", "Coordinates and altitude must be numbers.", parent=self)
            return None
        if not -90 <= latitude <= 90:
            messagebox.showerror("Invalid latitude", "Latitude must be between -90 and 90.", parent=self)
            return None
        if not -180 <= longitude <= 180:
            messagebox.showerror("Invalid longitude", "Longitude must be between -180 and 180.", parent=self)
            return None
        return LocationProfile(name=name, latitude=latitude, longitude=longitude, altitude_m=altitude)

    def _save_profile(self) -> None:
        profile = self._validated_profile()
        if profile is None:
            return
        selection = self.location_list.curselection()
        if selection:
            old_name = self.app.profiles[selection[0]].name
            self.app.profiles[selection[0]] = profile
            if self.app.selected_name == old_name:
                self.app.selected_name = profile.name
        else:
            existing = next((i for i, p in enumerate(self.app.profiles) if p.name == profile.name), None)
            if existing is None:
                self.app.profiles.append(profile)
            else:
                self.app.profiles[existing] = profile
        if self.app.selected_name is None:
            self.app.selected_name = profile.name
        self.app.store.save(self.app.profiles, self.app.selected_name)
        self._refresh_list()
        self.app._refresh_location_selector()

    def _use_profile(self) -> None:
        profile = self._validated_profile()
        if profile is None:
            return
        self._save_profile()
        self.app.selected_name = profile.name
        self.app.store.save(self.app.profiles, self.app.selected_name)
        self.app._refresh_location_selector()
        self.destroy()
        self.app.refresh_data()

    def _delete_profile(self) -> None:
        selection = self.location_list.curselection()
        if not selection:
            return
        profile = self.app.profiles.pop(selection[0])
        if self.app.selected_name == profile.name:
            self.app.selected_name = self.app.profiles[0].name if self.app.profiles else None
        self.app.store.save(self.app.profiles, self.app.selected_name)
        self._refresh_list()
        self.app._refresh_location_selector()
        self._new_profile()
        if self.app.selected_name:
            self.app.refresh_data()


def main() -> int:
    app = NightAzimuthApp()
    app.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
