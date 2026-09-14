from __future__ import annotations


def responsive_window_geometry(screen_width: int, screen_height: int) -> tuple[int, int, int, int]:
    """Return a large screen-aware window size and centred position."""

    screen_w = max(800, int(screen_width))
    screen_h = max(600, int(screen_height))
    width = min(1700, max(1000, int(screen_w * 0.90)))
    height = min(1000, max(650, int(screen_h * 0.88)))
    width = min(width, screen_w)
    height = min(height, screen_h)
    return width, height, max(0, (screen_w - width) // 2), max(0, (screen_h - height) // 2)


def fitted_image_size(
    source_width: int,
    source_height: int,
    available_width: int,
    available_height: int,
) -> tuple[int, int]:
    """Fit an image inside available bounds without changing its aspect ratio."""

    source_w = max(1, int(source_width))
    source_h = max(1, int(source_height))
    available_w = max(1, int(available_width))
    available_h = max(1, int(available_height))
    scale = min(available_w / source_w, available_h / source_h)
    return max(1, int(source_w * scale)), max(1, int(source_h * scale))
