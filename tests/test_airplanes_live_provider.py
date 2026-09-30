from nightazimuth.aircraft import AircraftObserver, AircraftSnapshotState
from nightazimuth.aircraft_adsb_lol import AirplanesLiveProvider


def test_airplanes_live_fallback_is_disabled_without_network_io() -> None:
    provider = AirplanesLiveProvider()

    snapshot = provider.fetch_snapshot(AircraftObserver(51.5, -0.1), 100.0)

    assert snapshot.state == AircraftSnapshotState.UNAVAILABLE
    assert snapshot.source_id == "airplanes-live"
    assert snapshot.source_label == "airplanes.live"
    assert snapshot.observations == ()
    assert snapshot.error is not None
    assert "fallback disabled" in snapshot.error
    assert provider.last_timings["provider_request_ms"] == 0.0
    assert provider.last_timings["provider_total_ms"] == 0.0
