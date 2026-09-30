from nightazimuth import api_aircraft


def test_aircraft_last_good_window_matches_maximum_position_age() -> None:
    assert (
        api_aircraft._AIRCRAFT_SNAPSHOT_CACHE._fallback_max_age_seconds
        == api_aircraft._MAX_RECENT_POSITION_AGE_SECONDS
        == 45.0
    )
