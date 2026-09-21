from nightazimuth.responsive_layout import calculate_responsive_layout


def test_1366x768_workspace_uses_compact_single_page_density():
    layout = calculate_responsive_layout(1366, 768, 96.0 / 72.0)
    assert layout.compact is True
    assert layout.table_rows <= 3
    assert 220 <= layout.details_width <= 280
    assert layout.density < 1.0


def test_1080p_workspace_keeps_balanced_density():
    layout = calculate_responsive_layout(1920, 1080, 96.0 / 72.0)
    assert layout.compact is False
    assert layout.table_rows >= 5
    assert 280 <= layout.details_width <= 360
    assert layout.density >= 1.0


def test_4k_at_200_percent_behaves_like_roomy_1080p_not_giant_ui():
    layout = calculate_responsive_layout(3840, 2160, 2 * (96.0 / 72.0))
    assert layout.logical_width == 1920
    assert layout.logical_height == 1080
    assert layout.compact is False
    assert layout.table_rows == 5


def test_very_high_dpi_does_not_make_layout_overflow():
    layout = calculate_responsive_layout(2560, 1440, 2.0)
    assert layout.logical_width < 1800
    assert layout.details_width <= 360
    assert layout.outer_padding >= 4
    assert layout.hud_inset >= 8
