from __future__ import annotations

import tkinter as tk
from tkinter import messagebox, ttk

from .location_profiles import LocationProfile, LocationProfileStore


class NightAzimuthApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("NightAzimuth")
        self.geometry("860x560")
        self.minsize(760, 480)

        self.store = LocationProfileStore()
        self.profiles, self.selected_name = self.store.load()

        self._build_ui()
        self._refresh_location_selector()

    def _build_ui(self) -> None:
        header = ttk.Frame(self, padding=12)
        header.pack(fill="x")

        ttk.Label(header, text="NightAzimuth", font=("Segoe UI", 18, "bold")).pack(side="left")

        ttk.Label(header, text="Location:").pack(side="left", padx=(30, 6))
        self.location_var = tk.StringVar()
        self.location_combo = ttk.Combobox(
            header,
            textvariable=self.location_var,
            state="readonly",
            width=28,
        )
        self.location_combo.pack(side="left")
        self.location_combo.bind("<<ComboboxSelected>>", self._on_location_changed)

        ttk.Button(header, text="Settings", command=self.open_settings).pack(side="right")

        body = ttk.Frame(self, padding=20)
        body.pack(fill="both", expand=True)

        ttk.Label(
            body,
            text="Satellite tracking dashboard",
            font=("Segoe UI", 15, "bold"),
        ).pack(anchor="w")
        ttk.Label(
            body,
            text=(
                "Stage 5 introduces the graphical application shell and saved location settings. "
                "The live sky map and weather layers will be added in later approved stages."
            ),
            wraplength=760,
        ).pack(anchor="w", pady=(8, 18))

        self.location_summary = ttk.Label(body, text="No location configured.")
        self.location_summary.pack(anchor="w", pady=(0, 12))

        info = ttk.LabelFrame(body, text="Current status", padding=16)
        info.pack(fill="x", pady=8)
        ttk.Label(
            info,
            text=(
                "Use Settings to add one or more observing locations. The selected location is "
                "remembered automatically and will be used by the graphical tracker in later stages."
            ),
            wraplength=720,
        ).pack(anchor="w")

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
                f"Selected location: {profile.name}  |  "
                f"Latitude {profile.latitude:.5f}, Longitude {profile.longitude:.5f}, "
                f"Altitude {profile.altitude_m:.0f} m"
            )
        )

    def _selected_profile(self) -> LocationProfile | None:
        for profile in self.profiles:
            if profile.name == self.selected_name:
                return profile
        return None

    def _on_location_changed(self, _event: object | None = None) -> None:
        selected = self.location_var.get().strip()
        self.selected_name = selected or None
        self.store.save(self.profiles, self.selected_name)
        self._update_location_summary()

    def open_settings(self) -> None:
        SettingsWindow(self)


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

        self._build_ui()
        self._refresh_list()

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

        form.columnconfigure(1, weight=1)

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
            self.app.profiles[selection[0]] = profile
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


def main() -> int:
    app = NightAzimuthApp()
    app.mainloop()
    return 0
