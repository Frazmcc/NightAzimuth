from datetime import datetime, timezone

from nightazimuth.gui_stage20_satellites import build_local_pass_hud
from nightazimuth.sky_map import SkySatellite


def _row(name: str, norad: str, rise: str, maximum: str = "65.00°") -> tuple[str, ...]:
    return (
        name,
        norad,
        rise,
        rise,
        rise,
        maximum,
    )


def test_pass_hud_prioritises_iss_and_only_alerts_within_one_hour() -> None:
    now = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)
    rows = [
        _row("VISUAL-1", "111", "2026-09-21 12:20:00", "40.00°"),
        _row("ISS (ZARYA)", "25544", "2026-09-21 12:45:00", "78.00°"),
        _row("TOO-LATE", "333", "2026-09-21 13:01:00", "50.00°"),
    ]

    alerts, iss_status = build_local_pass_hud(rows, now=now)

    assert alerts[0].startswith("ISS  in 45m")
    assert any("VISUAL-1  in 20m" in item for item in alerts)
    assert all("TOO-LATE" not in item for item in alerts)
    assert "next pass 45m" in iss_status


def test_iss_above_horizon_overrides_next_pass_countdown() -> None:
    now = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)
    iss = SkySatellite(
        name="ISS (ZARYA)",
        norad_id="25544",
        azimuth_deg=123.4,
        elevation_deg=34.5,
        range_km=612.0,
        satellite_sunlit=True,
        sky_dark=False,
        potentially_visible=False,
    )
    rows = [_row("ISS (ZARYA)", "25544", "2026-09-21 12:40:00", "70.00°")]

    _alerts, status = build_local_pass_hud(rows, current_satellites=[iss], now=now)

    assert "ABOVE HORIZON" in status
    assert "Az 123°" in status
    assert "El 34°" in status


def test_iss_status_remains_present_when_no_pass_is_within_day() -> None:
    now = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)

    alerts, status = build_local_pass_hud([], now=now)

    assert alerts == ()
    assert status == "ISS • BELOW HORIZON • no ≥10° pass in next 24h"
