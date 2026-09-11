from nightazimuth.live_catalog import merge_orbital_catalogues, norad_ids


def test_merge_orbital_catalogues_deduplicates_by_norad() -> None:
    visual = [
        {"NORAD_CAT_ID": "100", "OBJECT_NAME": "Bright One"},
        {"NORAD_CAT_ID": "200", "OBJECT_NAME": "Bright Two"},
    ]
    active = [
        {"NORAD_CAT_ID": "200", "OBJECT_NAME": "Duplicate Active"},
        {"NORAD_CAT_ID": "300", "OBJECT_NAME": "Active Three"},
    ]

    merged = merge_orbital_catalogues(visual, active)

    assert [item["NORAD_CAT_ID"] for item in merged] == ["100", "200", "300"]
    assert merged[1]["OBJECT_NAME"] == "Bright Two"


def test_merge_ignores_missing_norad_ids() -> None:
    merged = merge_orbital_catalogues(
        [{"OBJECT_NAME": "No ID"}],
        [{"NORAD_CAT_ID": "400", "OBJECT_NAME": "Valid"}],
    )

    assert norad_ids(merged) == {"400"}
