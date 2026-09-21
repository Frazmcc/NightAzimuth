from datetime import datetime, timedelta, timezone

from nightazimuth.stage20_header import format_utc_offset, local_clock_text
from nightazimuth.stage20_prank import prank_delays_ms


def test_clock_offset_formatting_handles_whole_and_half_hours() -> None:
    assert format_utc_offset(timedelta(hours=1)) == "UTC+1"
    assert format_utc_offset(timedelta(hours=-5)) == "UTC-5"
    assert format_utc_offset(timedelta(hours=5, minutes=30)) == "UTC+5:30"


def test_local_clock_text_uses_requested_timezone_and_offset() -> None:
    moment = datetime(2026, 1, 15, 12, 34, 56, tzinfo=timezone.utc)
    assert local_clock_text("Europe/London", now_utc=moment) == "12:34:56  UTC+0"


def test_prank_instances_are_staggered_and_bounded() -> None:
    delays = prank_delays_ms()
    assert len(delays) == 3
    assert delays[0] == 0
    assert delays[0] < delays[1] < delays[2]
