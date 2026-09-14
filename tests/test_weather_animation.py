from datetime import datetime, timezone

from nightazimuth.gui_stage16_animation import (
    AnimatedStage16NightAzimuthApp,
    next_weather_timeline_index,
)
from nightazimuth.weather_map import WeatherMapRenderer


def test_weather_animation_spans_last_24_hours_to_now() -> None:
    offsets = AnimatedStage16NightAzimuthApp.WEATHER_TIMELINE_MINUTES

    assert offsets == tuple(range(-24 * 60, 1, 60))
    assert offsets[0] == -1440
    assert offsets[-1] == 0
    assert len(offsets) == 25


def test_animation_map_choices_include_each_next_six_hours() -> None:
    choices = AnimatedStage16NightAzimuthApp.MAP_TIME_CHOICES
    assert choices["Now"] == 0
    for hour in range(1, 7):
        label = "+1 hour" if hour == 1 else f"+{hour} hours"
        assert choices[label] == hour


def test_radar_frame_selection_uses_nearest_observed_frame(tmp_path) -> None:
    renderer = WeatherMapRenderer(cache_directory=tmp_path)
    renderer._radar_frames = lambda: (  # type: ignore[method-assign]
        ("https://example.invalid", "/a", 1_700_000_000),
        ("https://example.invalid", "/b", 1_700_000_600),
        ("https://example.invalid", "/c", 1_700_001_200),
    )
    requested = datetime.fromtimestamp(1_700_000_720, tz=timezone.utc)
    selected = renderer._radar_frame_at(requested)
    assert selected is not None
    assert selected[1] == "/b"


def test_weather_animation_loops_after_latest_frame() -> None:
    assert next_weather_timeline_index(0, 25) == 1
    assert next_weather_timeline_index(24, 25) == 0
