from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence


@dataclass(frozen=True, slots=True)
class BrightnessEstimate:
    """An explicitly uncertain satellite apparent-magnitude estimate."""

    apparent_magnitude: float
    brighter_bound: float
    fainter_bound: float
    phase_angle_deg: float
    range_km: float
    source: str
    confidence: str

    @property
    def display_range(self) -> str:
        return f"{self.brighter_bound:.1f} to {self.fainter_bound:.1f}"


def lambertian_phase_fraction(phase_angle_deg: float) -> float:
    """Return the illuminated flux fraction for an ideal diffuse sphere."""

    angle = math.radians(max(0.0, min(180.0, float(phase_angle_deg))))
    fraction = (math.sin(angle) + (math.pi - angle) * math.cos(angle)) / math.pi
    return max(1.0e-6, min(1.0, fraction))


def phase_angle_degrees(
    satellite_to_sun: Sequence[float],
    satellite_to_observer: Sequence[float],
) -> float:
    """Return the Sun-satellite-observer phase angle from two 3D vectors."""

    if len(satellite_to_sun) != 3 or len(satellite_to_observer) != 3:
        raise ValueError("Phase-angle vectors must contain exactly three components")
    sun = tuple(float(value) for value in satellite_to_sun)
    observer = tuple(float(value) for value in satellite_to_observer)
    sun_length = math.sqrt(sum(value * value for value in sun))
    observer_length = math.sqrt(sum(value * value for value in observer))
    if sun_length <= 0.0 or observer_length <= 0.0:
        raise ValueError("Phase-angle vectors must have non-zero length")
    cosine = sum(a * b for a, b in zip(sun, observer, strict=True)) / (
        sun_length * observer_length
    )
    return math.degrees(math.acos(max(-1.0, min(1.0, cosine))))


def estimate_apparent_magnitude(
    intrinsic_full_phase_magnitude: float,
    *,
    range_km: float,
    phase_angle_deg: float,
    uncertainty_mag: float,
    source: str,
    confidence: str,
) -> BrightnessEstimate:
    """Estimate magnitude from a 1000-km full-phase intrinsic magnitude.

    The estimate applies inverse-square range scaling and an ideal Lambertian
    diffuse-sphere phase function. The caller must supply an uncertainty that
    reflects the calibration source and unmodelled attitude/specular effects.
    """

    distance = float(range_km)
    if not math.isfinite(distance) or distance <= 0.0:
        raise ValueError("Satellite range must be a positive finite value")
    uncertainty = float(uncertainty_mag)
    if not math.isfinite(uncertainty) or uncertainty < 0.0:
        raise ValueError("Magnitude uncertainty must be a finite non-negative value")

    phase = max(0.0, min(180.0, float(phase_angle_deg)))
    phase_fraction = lambertian_phase_fraction(phase)
    magnitude = (
        float(intrinsic_full_phase_magnitude)
        + 5.0 * math.log10(distance / 1000.0)
        - 2.5 * math.log10(phase_fraction)
    )
    return BrightnessEstimate(
        apparent_magnitude=magnitude,
        brighter_bound=magnitude - uncertainty,
        fainter_bound=magnitude + uncertainty,
        phase_angle_deg=phase,
        range_km=distance,
        source=str(source),
        confidence=str(confidence),
    )
