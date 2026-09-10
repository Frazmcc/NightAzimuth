from pathlib import Path

from nightazimuth.config import load_config


def test_load_config(tmp_path: Path) -> None:
    config_path = tmp_path / "nightazimuth.toml"
    config_path.write_text(
        """
[observer]
latitude = 55.8642
longitude = -4.2518
altitude_m = 40.0

[tracking]
minimum_elevation_deg = 5.0

[data]
celestrak_group = "stations"
cache_directory = "cache"
cache_max_age_minutes = 90
""".strip(),
        encoding="utf-8",
    )

    config = load_config(config_path)

    assert config.observer.latitude == 55.8642
    assert config.observer.longitude == -4.2518
    assert config.observer.altitude_m == 40.0
    assert config.tracking.minimum_elevation_deg == 5.0
    assert config.data.celestrak_group == "STATIONS"
    assert config.data.cache_directory == Path("cache")
    assert config.data.cache_max_age_minutes == 90
