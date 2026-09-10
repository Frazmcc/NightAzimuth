from pathlib import Path

from nightazimuth.config import load_config


def test_stage4_tracking_defaults(tmp_path: Path) -> None:
    config_path = tmp_path / "nightazimuth.toml"
    config_path.write_text(
        """
[observer]
latitude = 55.8642
longitude = -4.2518
altitude_m = 50

[tracking]
minimum_elevation_deg = 0

[data]
cache_directory = "data/cache"
""".strip(),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.tracking.pass_minimum_elevation_deg == 10.0
    assert config.tracking.pass_prediction_hours == 24.0
    assert config.tracking.darkness_threshold_deg == -6.0
