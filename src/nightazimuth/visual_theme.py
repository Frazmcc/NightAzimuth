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


def _font_size(density: float, *, base: int, minimum: int) -> int:
    return max(minimum, round(base * min(1.18, max(0.82, density))))


def apply_stage20_theme(
    root: tk.Misc,
    *,
    density: float = 1.0,
    compact: bool = False,
) -> ttk.Style:
    """Apply the lightweight Stage 20 dark HUD theme to existing ttk widgets."""
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    ui_size = _font_size(density, base=9, minimum=8)
    hud_size = _font_size(density, base=9, minimum=8)
    row_height = max(21, round((24 if compact else 27) * density))
    button_pad_x = max(6, round((7 if compact else 10) * density))
    button_pad_y = max(3, round((3 if compact else 5) * density))
    tab_pad_x = max(8, round((10 if compact else 14) * density))
    tab_pad_y = max(4, round((5 if compact else 7) * density))

    ui_font = ("Segoe UI", ui_size)
    ui_font_bold = ("Segoe UI Semibold", ui_size)
    hud_font = ("Consolas", hud_size)
    hud_font_bold = ("Consolas", hud_size, "bold")

    root.option_add("*Font", ui_font)
    root.option_add("*Background", PALETTE["window"])
    root.option_add("*Foreground", PALETTE["text"])

    style.configure(".", background=PALETTE["window"], foreground=PALETTE["text"], font=ui_font)
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
        font=ui_font_bold,
    )
    style.configure(
        "TButton",
        background=PALETTE["panel_raised"],
        foreground=PALETTE["text"],
        bordercolor=PALETTE["border"],
        focusthickness=0,
        padding=(button_pad_x, button_pad_y),
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
        padding=(max(3, round(4 * density)), max(2, round(3 * density))),
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
        padding=max(2, round(3 * density)),
    )
    style.configure(
        "TEntry",
        fieldbackground=PALETTE["panel_raised"],
        foreground=PALETTE["text"],
        insertcolor=PALETTE["accent"],
        bordercolor=PALETTE["border"],
        padding=max(3, round(4 * density)),
    )
    style.configure("TNotebook", background=PALETTE["window"], borderwidth=0)
    style.configure(
        "TNotebook.Tab",
        background=PALETTE["panel"],
        foreground=PALETTE["text_muted"],
        padding=(tab_pad_x, tab_pad_y),
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
        rowheight=row_height,
        font=hud_font,
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
        font=ui_font_bold,
        padding=(max(4, round(6 * density)), max(4, round(6 * density))),
    )
    style.map(
        "Night.Treeview.Heading",
        background=[("active", PALETTE["panel_hover"])],
    )
    style.configure(
        "HudBadge.TLabel",
        background=PALETTE["panel_raised"],
        foreground=PALETTE["accent"],
        font=hud_font_bold,
        padding=(max(5, round(8 * density)), max(3, round(5 * density))),
    )
    style.configure(
        "HudTelemetry.TLabel",
        background=PALETTE["panel_raised"],
        foreground=PALETTE["text"],
        font=hud_font,
        padding=(max(5, round(8 * density)), max(3, round(5 * density))),
    )
    style.configure(
        "HudMuted.TLabel",
        background=PALETTE["panel"],
        foreground=PALETTE["text_muted"],
        font=hud_font,
    )
    return style
