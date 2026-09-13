# Stage 16 Implementation — Directional Cloud Overlay and Observing Planner

Status: **In testing — not yet accepted as complete**

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

## Still outstanding before Stage 16 completion

- explicitly select the newest EUMETView cloud frame and display its observation timestamp and age
- automatic near-real-time cloud refresh with stale-frame warning
- recent cloud-frame timeline to show movement
- spatial forecast cloud/precipitation frames on the 2D map for future hours
- free/open ECMWF forecast integration where practical, with attribution and no-charge access only
- add useful satellite-pass opportunity information into hourly guidance
- keep future imagery clearly labelled as forecast rather than future radar/satellite observation

## Privacy and release behaviour

Runtime location-derived weather/cloud/map requests occur only after a user has entered a location. Runtime caches stay on the user's PC and are not part of release output.

No real/private coordinates are stored in source code, tests, documentation, or packaged release assets.

## Stage gate

PR #24 remains draft and unmerged until the outstanding Stage 16 work is complete, CI succeeds, local testing is complete, and the user explicitly accepts the completed stage.
