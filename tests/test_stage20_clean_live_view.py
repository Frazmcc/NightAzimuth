from types import SimpleNamespace

from nightazimuth.stage20_clean_live_view import aircraft_icon_type


def _aircraft(
    *,
    military: bool = False,
    type_code: str | None = None,
    description: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        military=military,
        type_code=type_code,
        type_description=description,
    )


def test_military_aircraft_gets_military_icon() -> None:
    assert aircraft_icon_type(_aircraft(military=True, type_code="F16")) == "military"


def test_helicopter_description_gets_helicopter_icon() -> None:
    assert aircraft_icon_type(_aircraft(description="Rotorcraft helicopter")) == "helicopter"


def test_glider_description_gets_glider_icon() -> None:
    assert aircraft_icon_type(_aircraft(description="Sailplane glider")) == "glider"


def test_uav_description_gets_uav_icon() -> None:
    assert aircraft_icon_type(_aircraft(description="Unmanned UAV")) == "uav"


def test_unknown_fixed_wing_defaults_to_airplane_icon() -> None:
    assert aircraft_icon_type(_aircraft(type_code="A320")) == "airplane"
