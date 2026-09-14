from nightazimuth.ui_layout import fitted_image_size, responsive_window_geometry


def test_responsive_window_uses_most_of_full_hd_without_exceeding_cap() -> None:
    assert responsive_window_geometry(1920, 1080) == (1700, 950, 110, 65)


def test_responsive_window_never_exceeds_small_screen() -> None:
    width, height, x, y = responsive_window_geometry(1024, 700)
    assert (width, height) == (1000, 650)
    assert (x, y) == (12, 25)


def test_fitted_image_size_preserves_aspect_ratio() -> None:
    assert fitted_image_size(768, 768, 1000, 500) == (500, 500)
    assert fitted_image_size(1200, 600, 800, 800) == (800, 400)
