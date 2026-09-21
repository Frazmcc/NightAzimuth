from nightazimuth.airport_landmarks import airport_in_view, relevant_airport_landmarks


def test_glasgow_area_returns_only_major_reference_airports() -> None:
    airports = relevant_airport_landmarks(55.8642, -4.2518, max_distance_km=220.0, limit=4)
    codes = {airport.iata for airport in airports}
    assert codes == {"GLA", "PIK", "EDI", "ABZ"}


def test_airport_visibility_respects_current_view_sector() -> None:
    airports = relevant_airport_landmarks(55.8642, -4.2518, max_distance_km=220.0, limit=4)
    glasgow = next(airport for airport in airports if airport.iata == "GLA")
    assert airport_in_view(glasgow, glasgow.bearing_deg, 60.0)
    assert not airport_in_view(glasgow, (glasgow.bearing_deg + 180.0) % 360.0, 60.0)


def test_airport_selection_is_distance_limited_and_sparse() -> None:
    airports = relevant_airport_landmarks(55.8642, -4.2518, max_distance_km=80.0, limit=4)
    codes = {airport.iata for airport in airports}
    assert "GLA" in codes
    assert "PIK" in codes
    assert "EDI" in codes
    assert "ABZ" not in codes
