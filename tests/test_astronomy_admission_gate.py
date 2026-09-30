from nightazimuth.api import _ASTRONOMY_PATHS, _ASTRONOMY_REQUEST_GATE


def test_heavy_astronomy_endpoints_share_one_admission_gate() -> None:
    assert _ASTRONOMY_PATHS == frozenset(("/api/v1/sky", "/api/v1/satellites"))
    assert _ASTRONOMY_REQUEST_GATE._value == 1


def test_lightweight_endpoints_are_not_admission_limited() -> None:
    assert "/api/v1/aircraft" not in _ASTRONOMY_PATHS
    assert "/api/v1/airports" not in _ASTRONOMY_PATHS
    assert "/api/v1/weather" not in _ASTRONOMY_PATHS
    assert "/api/v1/observing" not in _ASTRONOMY_PATHS
    assert "/api/v1/health" not in _ASTRONOMY_PATHS
