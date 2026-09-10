# NightAzimuth

**Created by Logic Lurker © 2026**

Location-based live satellite tracking with directional sky identification and observing guidance.

## Current release

**v0.2.0-alpha.1 — second alpha pre-release**

This release includes saved locations, live satellite tracking, pass prediction, the all-sky radar-style Sky map, and the forward-looking Live view with practical zooming, projected satellite tracks, a real stellar background, constellation guides, and major-planet identification.

NightAzimuth has progressed through Stage 11. The Live view uses a practical 0–60° observing range, supports zoom, draws a short predicted satellite path, places satellites against a real star-field background, identifies major planets, keeps useful bright reference stars labelled, and reveals fainter star names or Hipparcos identifiers when clicked.

Weather/cloud analysis, directional cloud estimation, satellite brightness/magnitude modelling, camera support, aircraft matching, meteor detection, and unidentified-object classification are not implemented yet.

See [`RELEASE_NOTES_v0.2.0-alpha.1.md`](RELEASE_NOTES_v0.2.0-alpha.1.md) for release details.

## Initial goal

NightAzimuth is a local application that uses an observer's location and current time to determine which satellites are above the horizon, where they are in the sky, and which are realistically likely to be visible.

Visibility will eventually combine orbital geometry, solar illumination, astronomical darkness, and the freshest practical directional cloud information available for the part of the sky being viewed.

## Documentation

- [`docs/STAGE_1_REQUIREMENTS.md`](docs/STAGE_1_REQUIREMENTS.md) — approved product requirements.
- [`docs/STAGE_3_IMPLEMENTATION.md`](docs/STAGE_3_IMPLEMENTATION.md) — core-tracking implementation.
- [`docs/STAGE_4_IMPLEMENTATION.md`](docs/STAGE_4_IMPLEMENTATION.md) — astronomical visibility, pass prediction, CelesTrak behaviour, and Windows EXE build support.
- [`docs/STAGE_5_IMPLEMENTATION.md`](docs/STAGE_5_IMPLEMENTATION.md) — Windows GUI shell and saved location profiles.
- [`docs/STAGE_6_IMPLEMENTATION.md`](docs/STAGE_6_IMPLEMENTATION.md) — live satellite and pass data inside the GUI.
- [`docs/STAGE_7_IMPLEMENTATION.md`](docs/STAGE_7_IMPLEMENTATION.md) — all-sky and forward-looking Live view work.
- [`docs/STAGE_8_IMPLEMENTATION.md`](docs/STAGE_8_IMPLEMENTATION.md) — practical 0–60° Live view and zoom controls.
- [`docs/STAGE_9_IMPLEMENTATION.md`](docs/STAGE_9_IMPLEMENTATION.md) — short projected tracks and direction of travel.
- [`docs/STAGE_10_IMPLEMENTATION.md`](docs/STAGE_10_IMPLEMENTATION.md) — real Hipparcos star field and constellation reference layer.
- [`docs/STAGE_11_IMPLEMENTATION.md`](docs/STAGE_11_IMPLEMENTATION.md) — major planet labels and click-to-reveal fainter star names.
- [`CREDITS.md`](CREDITS.md) — creator and third-party credits.

## Windows GUI

From `C:\git\NightAzimuth`:

```powershell
git checkout main
git pull
.\build_windows.ps1
.\dist\NightAzimuth.exe
```

The GUI provides:

- saved observing locations
- quick location switching
- live radar-style all-sky map
- horizon, zenith, cardinal directions, and elevation rings
- separate forward-looking Live view
- practical 0–60° Live view elevation range
- facing direction by compass point or 0–359° bearing
- selectable horizontal field of view from 30° to 180°
- mouse-wheel zoom
- + / − zoom buttons
- drag-to-select rectangular zoom
- Reset view control
- short 3-minute projected satellite paths
- arrowed direction of travel
- real Hipparcos star-field background
- star brightness represented by marker size
- major planets positioned from the Skyfield ephemeris and permanently labelled when in view
- bright named reference stars labelled automatically, with more labels appearing as you zoom in
- fainter stars identified when clicked
- optional Stellarium constellation lines
- Stars On/Off control; major planets remain independent of this control
- Constellations On/Off control
- clickable satellite markers
- selected satellite details including projected azimuth/elevation movement
- live satellites above the horizon
- azimuth, elevation, and range
- sunlit and dark-sky indicators
- potential astronomical visibility
- upcoming passes for the next 24 hours
- rise, peak, set time, and maximum elevation
- manual refresh
- automatic live refresh

Changing the selected location refreshes the calculations for that observer position. NightAzimuth suppresses the previous location's stellar snapshot while the replacement view is calculated.

## Saved application data

Location profiles are stored under:

```text
%APPDATA%\NightAzimuth\locations.json
```

Orbital, Skyfield, Hipparcos, and constellation cache data are stored under:

```text
%APPDATA%\NightAzimuth\cache\
```

## Visibility terminology

`Potential` means the satellite is illuminated by the Sun while the observer's sky is sufficiently dark. It does **not** mean guaranteed naked-eye visibility.

Cloud, haze, satellite brightness/magnitude, local obstructions, moonlight, and camera sensitivity are not yet included in the result.

The star and planet layers are positional observing references. A plotted star or planet is not a guarantee that local conditions make it visible to the unaided eye.

## Development principles

- Accuracy before features.
- Preserve the distinction between a satellite being geometrically above the horizon and actually being visible.
- Use modern OMM orbital data rather than assuming legacy TLE-only identifiers.
- Keep external data providers replaceable where practical.
- Never embed API keys or other secrets in source control.
- Make data age and confidence clear when displaying time-sensitive information.
- Add camera integration only after the core satellite tracker is reliable.
- Progress one approved stage at a time.

## Technology baseline

The current implementation uses Python 3.11+, Tkinter for the native desktop GUI, Skyfield for satellite, stellar, and planetary astronomy calculations, Pandas for Hipparcos catalogue loading, HTTPX for orbital-data retrieval, and PyInstaller for Windows EXE packaging.

## Credits

**Created by Logic Lurker © 2026**

See [`CREDITS.md`](CREDITS.md) for project and third-party attribution information.

## Licence

No licence has been selected yet.
