from datetime import datetime, timedelta, timezone

from nightazimuth.observing_conditions import format_countdown, sky_state_name


def test_sky_state_names() -> None:
    assert sky_state_name(4) == "Daylight"
    assert sky_state_name(3) == "Civil twilight"
    assert sky_state_name(2) == "Nautical twilight"
    assert sky_state_name(1) == "Astronomical twilight"
    assert sky_state_name(0) == "Dark"


def test_future_countdown() -> None:
    now = datetime(2026, 1, 1, 18, 0, tzinfo=timezone.utc)
    event = now + timedelta(hours=1, minutes=2, seconds=3)
    assert format_countdown(event, now, reached=False) == "in 01:02:03"


def test_reached_countdown() -> None:
    now = datetime(2026, 1, 1, 18, 0, tzinfo=timezone.utc)
    assert format_countdown(now - timedelta(minutes=5), now, reached=True) == "reached"


def test_missing_transition() -> None:
    now = datetime(2026, 1, 1, 18, 0, tzinfo=timezone.utc)
    assert format_countdown(None, now, reached=False) == "no transition"
