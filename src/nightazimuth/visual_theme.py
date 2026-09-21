from __future__ import annotations

import tkinter as tk
from tkinter import ttk


PALETTE = {
    "window": "#050b12",
    "panel": "#09131f",
    "panel_raised": "#0d1a28",
    "panel_hover": "#122538",
    "border": "#1d3b4d",
    "border_bright": "#2f6578",
    "text": "#d8f3f8",
    "text_muted": "#7ea1ad",
    "accent": "#37d5e7",
    "accent_soft": "#163943",
    "selected": "#16485a",
    "military": "#4f8cff",
    "special": "#f59e0b",
    "critical": "#ef4444",
}

UI_FONT = ("Segoe UI", 9)
UI_FONT_BOLD = ("Segoe UI Semibold", 9)
HUD_FONT = ("Consolas", 9)
HUD_FONT_BOLD = ("Consolas", 9, "bold")


def apply_stage20_theme(root: tk.Misc) -> ttk.Style:
    """Apply the lightweight Stage 20 dark HUD theme to existing ttk widgets."""
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    root.option_add("*Font", UI_FONT)
    root.option_add("*Background", PALETTE["window"])
    root.option_add("*Foreground", PALETTE["text"])

    style.configure(".", background=PALETTE["window"], foreground=PALETTE["text"], font=UI_FONT)
    style.configure("TFrame", background=PALETTE["window"])
    style.configure("TLabel", background=PALETTE["window"], foreground=PALETTE["text"])
    style.configure(
        "TLabelframe",
        background=PALETTE["panel"],
        bordercolor=PALETTE["border"],
        relief="solid",
        borderwidth=1,
    )
    style.configure(
        "TLabelframe.Label",
        background=PALETTE["panel"],
        foreground=PALETTE["accent"],
        font=UI_FONT_BOLD,
    )
    style.configure(
        "TButton",
        background=PALETTE["panel_raised"],
        foreground=PALETTE["text"],
        bordercolor=PALETTE["border"],
        focusthickness=0,
        padding=(10, 5),
    )
    style.map(
        "TButton",
        background=[("active", PALETTE["panel_hover"]), ("pressed", PALETTE["accent_soft"])],
        foreground=[("disabled", PALETTE["text_muted"])],
        bordercolor=[("focus", PALETTE["border_bright"])],
    )
    style.configure(
        "TCheckbutton",
        background=PALETTE["window"],
        foreground=PALETTE["text"],
        indicatorbackground=PALETTE["panel_raised"],
        indicatorforeground=PALETTE["accent"],
        padding=(4, 3),
    )
    style.map(
        "TCheckbutton",
        background=[("active", PALETTE["window"])],
        foreground=[("disabled", PALETTE["text_muted"])],
        indicatorbackground=[("selected", PALETTE["accent_soft"])],
    )
    style.configure(
        "TCombobox",
        fieldbackground=PALETTE["panel_raised"],
        background=PALETTE["panel_raised"],
        foreground=PALETTE["text"],
        arrowcolor=PALETTE["accent"],
        bordercolor=PALETTE["border"],
        selectbackground=PALETTE["selected"],
        selectforeground=PALETTE["text"],
        padding=3,
    )
    style.configure(
        "TEntry",
        fieldbackground=PALETTE["panel_raised"],
        foreground=PALETTE["text"],
        insertcolor=PALETTE["accent"],
        bordercolor=PALETTE["border"],
        padding=4,
    )
    style.configure("TNotebook", background=PALETTE["window"], borderwidth=0)
    style.configure(
        "TNotebook.Tab",
        background=PALETTE["panel"],
        foreground=PALETTE["text_muted"],
        padding=(14, 7),
        borderwidth=0,
    )
    style.map(
        "TNotebook.Tab",
        background=[("selected", PALETTE["panel_raised"]), ("active", PALETTE["panel_hover"])],
        foreground=[("selected", PALETTE["accent"]), ("active", PALETTE["text"])],
    )
    style.configure(
        "Night.Treeview",
        background=PALETTE["panel"],
        fieldbackground=PALETTE["panel"],
        foreground=PALETTE["text"],
        bordercolor=PALETTE["border"],
        rowheight=27,
        font=HUD_FONT,
    )
    style.map(
        "Night.Treeview",
        background=[("selected", PALETTE["selected"])],
        foreground=[("selected", "#ffffff")],
    )
    style.configure(
        "Night.Treeview.Heading",
        background=PALETTE["panel_raised"],
        foreground=PALETTE["accent"],
        bordercolor=PALETTE["border"],
        relief="flat",
        font=UI_FONT_BOLD,
        padding=(6, 6),
    )
    style.map(
        "Night.Treeview.Heading",
        background=[("active", PALETTE["panel_hover"])],
    )
    style.configure(
        "HudBadge.TLabel",
        background=PALETTE["panel_raised"],
        foreground=PALETTE["accent"],
        font=HUD_FONT_BOLD,
        padding=(8, 5),
    )
    style.configure(
        "HudTelemetry.TLabel",
        background=PALETTE["panel_raised"],
        foreground=PALETTE["text"],
        font=HUD_FONT,
        padding=(8, 5),
    )
    style.configure(
        "HudMuted.TLabel",
        background=PALETTE["panel"],
        foreground=PALETTE["text_muted"],
        font=HUD_FONT,
    )
    return style
