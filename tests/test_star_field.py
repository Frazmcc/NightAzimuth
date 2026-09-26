from io import StringIO
import json

import pandas as pd

import nightazimuth.star_field as star_field
from nightazimuth.star_field import GALAXY_CATALOGUE, parse_modern_skyculture
from nightazimuth.star_live_view import automatic_star_label_limit, star_marker_radius


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


def test_static_sky_resources_are_loaded_once_per_process_cache(tmp_path, monkeypatch) -> None:
    loader_creations = 0

    class FakeLoader:
        def __init__(self, cache_directory, *, verbose, expire):
            nonlocal loader_creations
            loader_creations += 1

        def open(self, url, filename=None):
            if url == star_field.MODERN_SKYCULTURE_URL:
                return StringIO(json.dumps({"common_names": {}, "constellations": []}))
            return StringIO("unused")

        def __call__(self, filename):
            return object()

        def timescale(self):
            return object()

    monkeypatch.setattr(star_field, "Loader", FakeLoader)
    monkeypatch.setattr(
        star_field.hipparcos,
        "load_dataframe",
        lambda _handle: pd.DataFrame(
            {"ra_degrees": [10.0, None], "magnitude": [1.0, 2.0]},
            index=[1, 2],
        ),
    )
    star_field._load_static_resources.cache_clear()

    cache_key = str(tmp_path.resolve())
    first = star_field._load_static_resources(cache_key)
    second = star_field._load_static_resources(cache_key)

    assert first is second
    assert loader_creations == 1
    star_field._load_static_resources.cache_clear()


def test_brighter_stars_receive_larger_markers() -> None:
    assert star_marker_radius(-1.0) > star_marker_radius(1.5)
    assert star_marker_radius(1.5) > star_marker_radius(4.5)


def test_star_labels_become_richer_as_live_view_zooms_in() -> None:
    assert automatic_star_label_limit(150.0) == 2.0
    assert automatic_star_label_limit(90.0) == 3.0
    assert automatic_star_label_limit(60.0) == 3.5
    assert automatic_star_label_limit(30.0) == 4.0
    assert automatic_star_label_limit(20.0) == 5.0


def test_ninety_degree_view_labels_more_named_stars_than_wide_view() -> None:
    assert automatic_star_label_limit(90.0) > automatic_star_label_limit(150.0)


def test_galaxy_reference_catalogue_contains_named_targets() -> None:
    names = {name for name, _ra_hours, _dec_degrees in GALAXY_CATALOGUE}

    assert "Andromeda Galaxy (M31)" in names
    assert "Triangulum Galaxy (M33)" in names
    assert len(names) == len(GALAXY_CATALOGUE)
