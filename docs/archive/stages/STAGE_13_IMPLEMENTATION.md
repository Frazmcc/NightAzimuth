# Stage 13 Implementation — Live Sky Finder and Broad Satellite Coverage

**Created by Logic Lurker © 2026**

Stage 13 redesigns the Live view around real-world naked-eye observing rather than an all-sky chart.

## Live finder

- rectangular observer-facing sky view
- full 0–90° elevation range, including zenith
- click-and-drag panning horizontally and vertically
- mouse-wheel and button zoom retained
- facing direction and horizontal field-of-view controls retained
- terrain skyline remains integrated as a local obstruction layer

## Satellite coverage

Live tracking combines CelesTrak `VISUAL` and `ACTIVE` orbital groups and de-duplicates matching NORAD IDs.

The wider catalogue is used for current live tracking so the app can identify substantially more real satellites than the small VISUAL group alone.

The 24-hour pass-planning view remains intentionally based on the VISUAL group so long-range pass prediction stays practical.

## Fast-mover ranking

Normal Live mode displays up to six potentially-visible satellites in the current field of view.

Candidates are ranked primarily by apparent angular speed measured from their short future tracks. Elevation and range are used as secondary ranking factors. There is no arbitrary maximum range cutoff.

`All tracked` mode can expose the broader potentially-visible set, but uses tiny markers and suppresses most labels/tracks to avoid congestion.

## Smooth movement

Projected satellite positions are calculated every second over a three-minute prediction window.

The on-screen satellite marker is interpolated between prediction points at approximately 50 ms intervals, giving an effective visual update rate of about 20 frames per second without recalculating the full orbit 20 times per second.

Azimuth interpolation follows the shortest path across 0°/360° so north crossings remain smooth.

## Celestial references

- Vega remains a prominent blue-white reference with live azimuth and elevation
- named bright stars are automatically labelled
- narrower fields of view allow progressively richer star labels
- major planets are labelled with current azimuth/elevation
- named galaxy references are included for M31, M33, M81, M82, M51, M101 and M104
- unnamed/fainter stars remain visually subdued so satellite motion remains dominant

## Visibility interpretation

Fast-mover ranking does not replace the existing astronomical `Potential` test.

`Potential` currently means the satellite is sunlit while the observer sky is sufficiently dark. It does not yet model apparent magnitude, reflective orientation, weather/cloud, haze, moonlight, nearby non-terrain obstructions or camera sensitivity.

A satellite may therefore rank highly because it moves quickly across the current view while still being too faint to see with the naked eye.

## Privacy and release behaviour

Stage 13 does not change saved-location privacy or release bundling:

- fresh releases contain no real saved user location
- saved locations remain local under `%APPDATA%\NightAzimuth\locations.json`
- personal terrain/cache/runtime data is not bundled
- terrain requests may reveal the requested geographic area through derived z/x/y tile identifiers
- automated tests use synthetic/non-personal location data
