# Stage 16 Implementation — Directional Cloud Overlay and Observing Planner

Status: **Approved and merged**

Stage 16 extends the Stage 15 weather foundation with spatial cloud imagery, an indicative cloud projection in the Live finder, and transparent 12–24 hour observing guidance.

## Hard project laws

These constraints remain non-negotiable:

1. A fresh NightAzimuth installation contains no saved user location. No real/private testing location is committed, packaged, documented, or included in automated tests or release assets. Tests use synthetic coordinates only.
2. NightAzimuth remains free to use. Stage 16 must not introduce a paid API key, billing account, subscription, or paid provider requirement.

## Spatial cloud imagery

The current Stage 16 implementation uses EUMETSAT EUMETView Meteosat GeoColour imagery through WMS.

- Only the geographic region required for the active user-entered location is requested.
- Saved profile names and `locations.json` are not sent.
- Cloud-image cache filenames are derived from request hashes rather than readable coordinates.
- The Weather map has a working **Cloud imagery** control.
- The Live finder has a working **Cloud overlay** control.

## Live cloud overlay

The Live cloud layer is deliberately labelled as an estimate. NightAzimuth projects spatial satellite imagery into the current azimuth/elevation view using an assumed representative cloud altitude; this is not a precise 3D cloud reconstruction.

Current refinements include:

- adjustable cloud-overlay opacity
- N/NE/E/SE/S/SW/W/NW compass cues where those bearings fall inside the current Live field of view
- the 2D Weather map displays a green wedge for the current Live facing direction and horizontal field of view
- the wedge updates when the user applies a different Live facing/FOV

## 12–24 hour observing planner

Stage 16 now builds transparent hourly viewing guidance from the existing point-weather forecast plus calculated Sun altitude.

The planner considers:

- daylight / civil / nautical / astronomical twilight / full astronomical darkness
- total forecast cloud percentage
- fog fraction when available
- next-hour precipitation when available
- forecast horizon, which is shown separately as confidence

The user interface displays a two-hour sampling across up to the next 24 hours while retaining hourly guidance internally.

The rating is intentionally explainable rather than opaque. It is currently a planning aid based on astronomy and point weather; it is not a guarantee of visual conditions and does not yet claim exact future cloud-edge positions on the 2D map.

## Completed Stage 16 scope

The accepted implementation:

- selects recent EUMETView cloud frames and displays observation time, age and staleness
- refreshes cloud imagery in the background and retains recent frames for movement context
- keeps observed imagery and provider forecast samples clearly distinguished
- provides forecast samples out to roughly 24 hours using MET Norway data
- shows hourly observing guidance while keeping darkness, cloud, precipitation and confidence explainable
- adds cloud opacity, compass-direction cues and the Live-view field-of-view wedge on the Weather map

Forecast guidance remains a point-weather planning aid. It is not presented as future radar or a precise prediction of individual cloud edges.

## Privacy and release behaviour

Runtime location-derived weather/cloud/map requests occur only after a user has entered a location. Runtime caches stay on the user's PC and are not part of release output.

No real/private coordinates are stored in source code, tests, documentation, or packaged release assets.

## Stage gate

Stage 16 passed its automated checks, Windows build and local visual review, and was explicitly accepted before merge.
