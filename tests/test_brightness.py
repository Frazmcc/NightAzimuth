from __future__ import annotations

import math

import pytest

from nightazimuth.brightness import (
    estimate_apparent_magnitude,
    lambertian_phase_fraction,
    phase_angle_degrees,
)


def test_lambertian_phase_fraction_has_expected_endpoints() -> None:
    assert lambertian_phase_fraction(0.0) == pytest.approx(1.0)
    assert lambertian_phase_fraction(90.0) == pytest.approx(1.0 / math.pi)
    assert lambertian_phase_fraction(180.0) == pytest.approx(1.0e-6)


def test_phase_angle_uses_satellite_centred_vectors() -> None:
    assert phase_angle_degrees((1.0, 0.0, 0.0), (1.0, 0.0, 0.0)) == pytest.approx(0.0)
    assert phase_angle_degrees((1.0, 0.0, 0.0), (0.0, 1.0, 0.0)) == pytest.approx(90.0)
    assert phase_angle_degrees((1.0, 0.0, 0.0), (-1.0, 0.0, 0.0)) == pytest.approx(180.0)


def test_phase_angle_rejects_invalid_vectors() -> None:
    with pytest.raises(ValueError):
        phase_angle_degrees((1.0, 0.0), (1.0, 0.0, 0.0))
    with pytest.raises(ValueError):
        phase_angle_degrees((0.0, 0.0, 0.0), (1.0, 0.0, 0.0))


def test_apparent_magnitude_preserves_intrinsic_value_at_reference_geometry() -> None:
    estimate = estimate_apparent_magnitude(
        4.0,
        range_km=1000.0,
        phase_angle_deg=0.0,
        uncertainty_mag=0.8,
        source="test calibration",
        confidence="Measured prior",
    )

    assert estimate.apparent_magnitude == pytest.approx(4.0)
    assert estimate.brighter_bound == pytest.approx(3.2)
    assert estimate.fainter_bound == pytest.approx(4.8)
    assert estimate.display_range == "3.2 to 4.8"


def test_apparent_magnitude_accounts_for_range_and_phase() -> None:
    estimate = estimate_apparent_magnitude(
        4.0,
        range_km=2000.0,
        phase_angle_deg=90.0,
        uncertainty_mag=1.0,
        source="test calibration",
        confidence="Modelled",
    )

    expected = 4.0 + 5.0 * math.log10(2.0) - 2.5 * math.log10(1.0 / math.pi)
    assert estimate.apparent_magnitude == pytest.approx(expected)
    assert estimate.phase_angle_deg == 90.0
    assert estimate.range_km == 2000.0


@pytest.mark.parametrize("range_km", [0.0, -1.0, math.inf])
def test_apparent_magnitude_rejects_invalid_range(range_km: float) -> None:
    with pytest.raises(ValueError):
        estimate_apparent_magnitude(
            4.0,
            range_km=range_km,
            phase_angle_deg=45.0,
            uncertainty_mag=1.0,
            source="test",
            confidence="test",
        )


def test_phase_angle_clamps_floating_point_cosine() -> None:
    assert phase_angle_degrees((1.0, 0.0, 0.0), (1.0, 0.0, 0.0)) == pytest.approx(0.0)
