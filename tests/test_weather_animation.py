from datetime import datetime, timezone

from nightazimuth.gui_stage16_animation import AnimatedStage16NightAzimuthApp
from nightazimuth.weather_map import WeatherMapRenderer


def test_weather_animation_spans_last_hour_to_next_six_hours() -> None:
    offsets = AnimatedStage16NightAzimuthApp.WEATHER_TIMELINE_MINUTES
    assert offsets[0] == -60
    assert offsets[6] == 0
    assert offsets[-1] == 360
    assert offsets[:7] == (-60, -50, -40, -30, -20, -10, 0)
    assert offsets[7:] == (60, 120, 180, 240, 300, 360)


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
