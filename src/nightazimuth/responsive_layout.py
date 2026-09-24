from __future__ import annotations

from dataclasses import dataclass


REFERENCE_TK_SCALING = 96.0 / 72.0


@dataclass(frozen=True, slots=True)
class ResponsiveLayout:
    """Logical-screen metrics used to keep Stage 20 inside one visible page."""

    logical_width: float
    logical_height: float
    density: float
    compact: bool
    table_rows: int
    details_width: int
    outer_padding: int
    panel_padding: int
    hud_inset: int


def calculate_responsive_layout(
    screen_width_px: int,
    screen_height_px: int,
    tk_scaling: float,
) -> ResponsiveLayout:
    """Return UI metrics from physical pixels and Tk/OS DPI scaling.

    Tk font sizes are specified in points and therefore already respect the OS
    DPI setting.  The layout calculations use *logical* screen dimensions so a
    4K display at 200% scaling behaves like a roomy 1080p workspace rather than
    producing an oversized interface.
    """
    scaling = max(0.5, float(tk_scaling))
    dpi_factor = scaling / REFERENCE_TK_SCALING
    logical_width = max(640.0, float(screen_width_px) / dpi_factor)
    logical_height = max(480.0, float(screen_height_px) / dpi_factor)

    fit = min(logical_width / 1600.0, logical_height / 900.0)
    density = min(1.25, max(0.78, fit))
    compact = logical_width < 1450.0 or logical_height < 820.0

    if logical_height < 720.0:
        table_rows = 2
    elif logical_height < 820.0:
        table_rows = 3
    elif logical_height < 980.0:
        table_rows = 4
    elif logical_height < 1200.0:
        table_rows = 5
    else:
        table_rows = 7

    details_width = int(min(360.0, max(220.0, logical_width * (0.17 if compact else 0.18))))
    outer_padding = max(4, round(8 * density))
    panel_padding = max(4, round(7 * density))
    hud_inset = max(8, round(14 * density))

    return ResponsiveLayout(
        logical_width=logical_width,
        logical_height=logical_height,
        density=density,
        compact=compact,
        table_rows=table_rows,
        details_width=details_width,
        outer_padding=outer_padding,
        panel_padding=panel_padding,
        hud_inset=hud_inset,
    )
