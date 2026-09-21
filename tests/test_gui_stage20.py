from nightazimuth.gui_stage20 import compose_live_hud_status
from nightazimuth.visual_theme import PALETTE


def test_live_hud_status_is_compact_and_information_first():
    text = compose_live_hud_status(
        aircraft_state="live",
        aircraft_count=7,
        sun_altitude_deg=-12.34,
    )

    assert text == "● LIVE  •  ADSB LIVE  •  7 AC  •  SUN -12.3°"


def test_live_hud_status_handles_missing_optional_sources():
    assert compose_live_hud_status(
        aircraft_state=None,
        aircraft_count=None,
        sun_altitude_deg=None,
    ) == "● LIVE"


def test_live_hud_status_never_displays_negative_aircraft_count():
    text = compose_live_hud_status(
        aircraft_state="aging",
        aircraft_count=-4,
        sun_altitude_deg=None,
    )
    assert "0 AC" in text


def test_stage20_palette_preserves_alert_hierarchy():
    assert PALETTE["critical"] != PALETTE["special"]
    assert PALETTE["special"] != PALETTE["military"]
    assert PALETTE["accent"] != PALETTE["window"]
