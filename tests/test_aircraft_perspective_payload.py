from pathlib import Path


AIRCRAFT_LIVE = Path("src/nightazimuth/aircraft_live.py").read_text(encoding="utf-8")
PROVIDER = Path("src/nightazimuth/aircraft_adsb_lol.py").read_text(encoding="utf-8")


def test_adsb_attitude_fields_are_forwarded_into_live_sky_payload() -> None:
    mappings = {
        "true_heading_deg": 'record.get("true_heading")',
        "magnetic_heading_deg": 'record.get("mag_heading")',
        "track_rate_deg_s": 'record.get("track_rate")',
        "roll_deg": 'record.get("roll")',
    }
    for field, provider_source in mappings.items():
        assert provider_source in PROVIDER
        assert f"{field}=observation.{field}" in AIRCRAFT_LIVE


def test_attitude_addition_does_not_require_a_second_provider_request() -> None:
    # These fields are normalised from the existing ADS-B record. No extra
    # provider URL or fetch path should be introduced for attitude rendering.
    assert PROVIDER.count("https://api.adsb.lol/v2/point/") == 1
    assert "attitude" not in PROVIDER.lower().replace("aircraft attitude", "")
