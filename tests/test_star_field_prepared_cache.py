from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

import nightazimuth.star_field as star_field


def test_prepared_catalogue_builds_skyfield_star_target_once(monkeypatch) -> None:
    catalogue = pd.DataFrame(
        {
            "magnitude": [1.0, 4.0, 6.0],
            "ra_degrees": [10.0, 20.0, 30.0],
        },
        index=[1, 2, 3],
    )
    edges = (("Tst", 1, 3),)

    monkeypatch.setattr(
        star_field,
        "_load_static_resources",
        lambda _cache_directory: (catalogue, {}, edges, object(), object()),
    )

    calls = 0
    target = object()

    class FakeStar:
        @staticmethod
        def from_dataframe(selected):
            nonlocal calls
            calls += 1
            assert list(selected.index) == [1, 2, 3]
            return target

    monkeypatch.setattr(star_field, "Star", FakeStar)
    star_field._prepared_catalogue.cache_clear()

    first = star_field._prepared_catalogue("cache-key", 5.5)
    second = star_field._prepared_catalogue("cache-key", 5.5)

    assert first is second
    assert first[1] == frozenset({1, 2})
    assert first[2] is target
    assert calls == 1

    star_field._prepared_catalogue.cache_clear()
