from __future__ import annotations

import hashlib
from pathlib import Path

from nightazimuth import preload_sky


def _expected_blob_sha(payload: bytes) -> str:
    return hashlib.sha1(f"blob {len(payload)}\0".encode() + payload).hexdigest()


def test_git_blob_sha_is_canonical(tmp_path: Path) -> None:
    target = tmp_path / "resource.dat"
    target.write_bytes(b"sample")
    assert preload_sky._git_blob_sha1(target) == _expected_blob_sha(b"sample")


def test_cached_verified_resource_skips_network(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "resource.dat"
    target.write_bytes(b"cached")

    def disallow_network(*args, **kwargs):
        raise AssertionError("A verified cache must not access the network")

    monkeypatch.setattr(preload_sky.httpx, "stream", disallow_network)
    preload_sky._seed_resource(
        tmp_path, "resource.dat", "https://example.invalid/resource.dat",
        _expected_blob_sha(b"cached"),
    )
    assert target.read_bytes() == b"cached"


def test_download_rejects_tampered_resource(tmp_path: Path, monkeypatch) -> None:
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def raise_for_status(self):
            return None

        def iter_bytes(self, *, chunk_size: int):
            yield b"tampered"

    monkeypatch.setattr(preload_sky.httpx, "stream", lambda *args, **kwargs: FakeResponse())
    monkeypatch.setattr(preload_sky.time, "sleep", lambda seconds: None)

    try:
        preload_sky._seed_resource(
            tmp_path, "resource.dat", "https://example.invalid/resource.dat",
            _expected_blob_sha(b"authentic"),
        )
    except RuntimeError:
        pass
    else:
        raise AssertionError("A resource with an invalid Git SHA must be rejected")

    assert not (tmp_path / "resource.dat").exists()
