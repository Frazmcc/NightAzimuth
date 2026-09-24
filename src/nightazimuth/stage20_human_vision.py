from __future__ import annotations

import math


# Approximate naked-eye stellar limiting magnitudes by solar sky state.
# 0=dark, 1=astronomical, 2=nautical, 3=civil twilight, 4=daylight.
_SKY_LIMITING_MAGNITUDE = {
    0: 5.5,
    1: 4.8,
    2: 3.0,
    3: 1.0,
    4: -4.0,
}


def sky_limiting_magnitude(sky_state_code: int) -> float:
    """Return a conservative naked-eye star limit for the current solar state."""
    return _SKY_LIMITING_MAGNITUDE.get(int(sky_state_code), 5.5)


def atmospheric_extinction_magnitude(elevation_deg: float, *, coefficient: float = 0.22) -> float:
    """Approximate stellar dimming caused by the longer path near the horizon.

    Uses the Kasten-Young optical-airmass approximation and returns only the
    additional extinction relative to the zenith. The result is capped near the
    horizon where simple optical-airmass models become unstable.
    """
    elevation = max(1.0, min(90.0, float(elevation_deg)))
    zenith = 90.0 - elevation
    airmass = 1.0 / (
        math.cos(math.radians(zenith))
        + 0.50572 * ((96.07995 - zenith) ** -1.6364)
    )
    return max(0.0, min(3.5, float(coefficient) * (airmass - 1.0)))


def apparent_star_magnitude(magnitude: float, elevation_deg: float) -> float:
    return float(magnitude) + atmospheric_extinction_magnitude(elevation_deg)


def star_visible_to_adapted_eye(
    magnitude: float,
    elevation_deg: float,
    sky_state_code: int,
) -> bool:
    """Whether a star is plausibly visible to a normally adapted naked eye."""
    return apparent_star_magnitude(magnitude, elevation_deg) <= sky_limiting_magnitude(
        sky_state_code
    )


def star_luminance_fraction(
    magnitude: float,
    elevation_deg: float,
    sky_state_code: int,
) -> float:
    """Return 0..1 display luminance for a visible star.

    This is intentionally display-oriented rather than photometric: logarithmic
    stellar brightness is compressed into the narrow luminance range available
    on a desktop display while retaining relative prominence.
    """
    apparent = apparent_star_magnitude(magnitude, elevation_deg)
    limit = sky_limiting_magnitude(sky_state_code)
    if apparent > limit:
        return 0.0
    margin = max(0.0, limit - apparent)
    return max(0.18, min(1.0, 0.18 + margin / 6.0))


def night_colour_mix(sky_state_code: int) -> float:
    """Return 0..1 fraction of scotopic/desaturated appearance.

    Full darkness strongly reduces colour perception; daylight leaves normal
    colour intact. This is used for the natural-sky layer only, not HUD alerts.
    """
    state = int(sky_state_code)
    if state <= 0:
        return 0.88
    if state == 1:
        return 0.65
    if state == 2:
        return 0.38
    if state == 3:
        return 0.15
    return 0.0


def scintillation_scale(hip_id: int, elevation_deg: float, phase: int) -> float:
    """Small deterministic twinkle factor, strongest near the horizon.

    The amplitude is deliberately tiny to avoid a distracting animation and
    requires no random generator or per-star timers.
    """
    horizon_factor = max(0.0, min(1.0, (35.0 - float(elevation_deg)) / 35.0))
    wave = math.sin((int(hip_id) * 0.173) + int(phase) * 0.9)
    return 1.0 + wave * 0.07 * horizon_factor
