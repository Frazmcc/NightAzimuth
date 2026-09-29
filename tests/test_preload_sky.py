from __future__ import annotations

import nightazimuth.preload_sky as preload_sky


def test_preload_sky_uses_runtime_cache_path(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    loaded: list[str] = []
    monkeypatch.setattr(preload_sky, "_load_static_resources", loaded.append)

    preload_sky.main()

    expected = (tmp_path / "data/cache/api/skyfield").resolve()
    assert expected.is_dir()
    assert loaded == [str(expected)]
