from nightazimuth.star_field import parse_modern_skyculture
from nightazimuth.star_live_view import star_marker_radius


def test_parse_modern_skyculture_extracts_names_and_polyline_edges() -> None:
    document = {
        "constellations": [
            {
                "id": "CON modern_st Tst",
                "lines": [[1, 2, 3], [4, 5]],
            }
        ],
        "common_names": {
            "HIP 1": [{"english": "Alpha Test", "native": "Native Alpha"}],
            "HIP 2": [{"native": "Beta Test"}],
            "NAME Moon": [{"english": "Moon"}],
        },
    }

    names, edges = parse_modern_skyculture(document)

    assert names == {1: "Alpha Test", 2: "Beta Test"}
    assert edges == (
        ("Tst", 1, 2),
        ("Tst", 2, 3),
        ("Tst", 4, 5),
    )


def test_brighter_stars_receive_larger_markers() -> None:
    assert star_marker_radius(-1.0) > star_marker_radius(1.5)
    assert star_marker_radius(1.5) > star_marker_radius(4.5)
