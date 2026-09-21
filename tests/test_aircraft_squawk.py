from nightazimuth.aircraft_squawk import (
    SquawkCategory,
    SquawkPriority,
    classify_squawk,
    normalise_squawk,
)


def test_emergency_codes_are_critical():
    for code in ("7400", "7500", "7600", "7700"):
        alert = classify_squawk(code)
        assert alert is not None
        assert alert.category == SquawkCategory.EMERGENCY
        assert alert.priority == SquawkPriority.CRITICAL


def test_search_and_rescue_0023_is_highlighted():
    alert = classify_squawk("0023")
    assert alert is not None
    assert alert.label == "SEARCH & RESCUE"
    assert alert.category == SquawkCategory.SEARCH_RESCUE
    assert alert.priority == SquawkPriority.IMPORTANT


def test_police_range_is_classified():
    for code in ("0041", "0050", "0061"):
        alert = classify_squawk(code)
        assert alert is not None
        assert alert.category == SquawkCategory.POLICE
        assert alert.priority == SquawkPriority.IMPORTANT


def test_key_special_operations_are_classified():
    expected = {
        "0024": SquawkCategory.CALIBRATION,
        "0026": SquawkCategory.SPECIAL_TASK,
        "0030": SquawkCategory.LOST,
        "0032": SquawkCategory.POLICE,
        "0033": SquawkCategory.PARACHUTING,
        "0036": SquawkCategory.TOWING_INSPECTION,
        "0037": SquawkCategory.ROYAL,
        "7007": SquawkCategory.OPEN_SKIES,
    }
    for code, category in expected.items():
        alert = classify_squawk(code)
        assert alert is not None
        assert alert.category == category


def test_normal_conspicuity_and_fmc_style_codes_are_not_elevated():
    assert classify_squawk("7000") is None
    assert classify_squawk("2000") is None
    assert classify_squawk("2620") is None


def test_invalid_squawk_is_rejected():
    assert normalise_squawk("8888") is None
    assert normalise_squawk("770") is None
    assert normalise_squawk(None) is None
