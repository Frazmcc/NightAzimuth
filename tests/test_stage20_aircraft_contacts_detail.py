from pathlib import Path


def test_rc_places_selected_aircraft_detail_inside_aircraft_contacts() -> None:
    """Aircraft selection must surface details in Aircraft Contacts, not Live Finder."""
    source = Path("src/nightazimuth/gui_stage20_rc.py").read_text(encoding="utf-8")

    assert 'text="Selected aircraft"' in source
    assert 'DRAWER_AIRCRAFT = "aircraft"' in source
    assert "self._stage20_open_drawer = DRAWER_AIRCRAFT" in source
    assert "self._copy_selected_aircraft_detail()" in source
    assert "self._update_live_view_summary()" in source
    assert "DRAWER_DETAILS" not in source
