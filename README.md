# NightAzimuth

**Created by Logic Lurker © 2026**

Location-based live satellite tracking with directional sky identification and observing guidance.

## Current release

**v0.5.0-beta.1 — twilight observing beta**

This beta adds location-aware sunset/twilight timing, live darkness countdowns, offline time-zone resolution, solar-state Live-view backgrounds, and twilight satellite tracking before the stricter dark-sky threshold is reached.

NightAzimuth has progressed through Stage 14. Saved location profiles remain local to the user's PC, the Windows release is validated against a strict output allowlist, and the end-user configuration/operation guide is included with the release build.

Weather/cloud analysis, satellite brightness/magnitude modelling, camera overlay support, aircraft matching, meteor detection, and unidentified-object classification are not implemented yet.

See [`RELEASE_NOTES_v0.5.0-beta.1.md`](RELEASE_NOTES_v0.5.0-beta.1.md) for release details.

## Initial goal

NightAzimuth is a local application that uses an observer's location and current time to determine which satellites are above the horizon, where they are in the sky, and which are realistically likely to be visible.

Visibility will eventually combine orbital geometry, solar illumination, astronomical darkness, and the freshest practical directional cloud information available for the part of the sky being viewed.

## Documentation

- [`docs/NightAzimuth_User_Guide.md`](docs/NightAzimuth_User_Guide.md) — end-user installation, configuration, privacy, terrain and operating guide. This guide is also copied into the Windows release output by `build_windows.ps1`.
- [`docs/STAGE_1_REQUIREMENTS.md`](docs/STAGE_1_REQUIREMENTS.md) — approved product requirements.
- [`docs/STAGE_3_IMPLEMENTATION.md`](docs/STAGE_3_IMPLEMENTATION.md) — core-tracking implementation.
- [`docs/STAGE_4_IMPLEMENTATION.md`](docs/STAGE_4_IMPLEMENTATION.md) — astronomical visibility, pass prediction, CelesTrak behaviour, and Windows EXE build support.
- [`docs/STAGE_5_IMPLEMENTATION.md`](docs/STAGE_5_IMPLEMENTATION.md) — Windows GUI shell and saved location profiles.
- [`docs/STAGE_6_IMPLEMENTATION.md`](docs/STAGE_6_IMPLEMENTATION.md) — live satellite and pass data inside the GUI.
- [`docs/STAGE_7_IMPLEMENTATION.md`](docs/STAGE_7_IMPLEMENTATION.md) — all-sky and forward-looking Live view work.
- [`docs/STAGE_8_IMPLEMENTATION.md`](docs/STAGE_8_IMPLEMENTATION.md) — original practical Live-view elevation/zoom work.
- [`docs/STAGE_9_IMPLEMENTATION.md`](docs/STAGE_9_IMPLEMENTATION.md) — short projected tracks and direction of travel.
- [`docs/STAGE_10_IMPLEMENTATION.md`](docs/STAGE_10_IMPLEMENTATION.md) — real Hipparcos star field and constellation reference layer.
- [`docs/STAGE_11_IMPLEMENTATION.md`](docs/STAGE_11_IMPLEMENTATION.md) — major planet labels and click-to-reveal fainter star names.
- [`docs/STAGE_13_IMPLEMENTATION.md`](docs/STAGE_13_IMPLEMENTATION.md) — live finder redesign, broad satellite coverage, fast-mover ranking and smooth animation.
- [`docs/TERRAIN_HORIZON_PROTOTYPE.md`](docs/TERRAIN_HORIZON_PROTOTYPE.md) — terrain-horizon architecture, privacy model, cache/import behaviour and current limitations.
- [`CREDITS.md`](CREDITS.md) — creator and third-party credits.

## Windows GUI

From `C:\git\NightAzimuth`:

```powershell
git checkout main
git pull
.\build_windows.ps1
.\dist\NightAzimuth.exe
```

The build produces:

```text
dist\NightAzimuth.exe
dist\NightAzimuth_User_Guide.md
```

The GUI provides:

- saved observing locations
- quick location switching
- automatic terrain-horizon generation for the selected location
- terrain masking for sky objects below the calculated local skyline
- optional import of compatible local Terrarium terrain packs
- live radar-style all-sky map
- separate forward-looking Live finder
- full 0–90° Live-view elevation range, including zenith
- click-and-drag sky panning horizontally and vertically
- facing direction by compass point or 0–359° bearing
- selectable horizontal field of view from 30° to 180°
- mouse-wheel zoom
- + / − zoom buttons
- Reset view control
- broad live satellite tracking using CelesTrak VISUAL + ACTIVE catalogues
- default fast-mover ranking in the current field of view
- sunlit twilight satellite candidates after sunset before the dark-sky threshold is reached
- small named satellite markers with apparent angular speed when available
- optional All tracked diagnostic mode
- smooth satellite motion using one-second orbital samples interpolated at about 20 fps
- short 3-minute projected satellite paths sampled every second
- location-aware sunset, civil twilight, nautical twilight and complete-darkness countdowns
- current Sun altitude and sky-state display
- offline local time-zone resolution for the selected observing location
- Live-view background colour that follows daylight/twilight/dark state
- real Hipparcos star-field background
- Vega emphasised as a blue-white visual reference with live azimuth/elevation
- bright named reference stars labelled automatically, with more labels appearing as you zoom in
- fainter stars identified when clicked
- optional Stellarium constellation lines
- Mercury, Venus, Mars, Jupiter, Saturn, Uranus and Neptune positioned from the Skyfield ephemeris and labelled when in view
- named galaxy references for M31, M33, M81, M82, M51, M101 and M104
- clickable satellite markers
- selected satellite details including projected azimuth/elevation movement
- live satellites above the horizon
- azimuth, elevation, and range
- sunlit and dark-sky indicators
- potential astronomical visibility
- upcoming VISUAL-group passes for the next 24 hours
- rise, peak, set time, and maximum elevation
- manual refresh
- automatic live refresh

Changing the selected location refreshes satellite, celestial, terrain, sunset/twilight and time-zone calculations for that observer position. NightAzimuth suppresses the previous location's stellar and terrain snapshots while replacement data is calculated.

## Saved application data

Location profiles are stored under:

```text
%APPDATA%\NightAzimuth\locations.json
```

Orbital, Skyfield, Hipparcos, and constellation cache data are stored under:

```text
%APPDATA%\NightAzimuth\cache\
```

Terrain tiles generated for user-entered locations are cached under:

```text
%APPDATA%\NightAzimuth\terrain\terrarium\
```

A fresh release does not include saved user locations or personal terrain/cache data. Terrain tile requests are derived from the location the user enters, so the terrain provider can infer the geographic area represented by those requested tiles; the saved NightAzimuth profile file and profile name are not uploaded.

Sunset/twilight and time-zone calculations are performed locally from the selected observing location. No paid sunset or timezone API is used.

## Visibility terminology

`Potential` means the satellite is illuminated by the Sun while the observer's sky is sufficiently dark. It does **not** mean guaranteed naked-eye visibility.

The Live finder can also show sunlit satellites during civil twilight after sunset. These are observing candidates, but they do not receive the stricter `Potential` status until the dark-sky threshold is met.

Cloud, haze, satellite brightness/magnitude, non-terrain local obstructions, moonlight, and camera sensitivity are not yet included in the result.

Fast-mover ranking prioritises apparent movement across the current Live view. It improves practical identification but is not a brightness model.

The star, planet and galaxy layers are positional observing references. A plotted object is not a guarantee that local conditions make it visible to the unaided eye.

## Development principles

- Accuracy before features.
- Preserve the distinction between a satellite being geometrically above the horizon and actually being visible.
- Use modern OMM orbital data rather than assuming legacy TLE-only identifiers.
- Keep external data providers replaceable where practical.
- Never embed API keys or other secrets in source control.
- Never bundle saved user locations, personal runtime data, or caches in a release.
- Make data age and confidence clear when displaying time-sensitive information.
- Add camera integration only after the core satellite tracker is reliable.
- Progress one approved stage at a time.

## Technology baseline

The current implementation uses Python 3.11+, Tkinter for the native desktop GUI, Skyfield for satellite, stellar, planetary, solar and deep-sky coordinate calculations, `timezonefinder` for offline coordinate-to-time-zone lookup, Pandas for Hipparcos catalogue loading, HTTPX for orbital/terrain data retrieval, Pillow for Terrarium elevation-tile decoding, and PyInstaller for Windows EXE packaging.

## Credits

**Created by Logic Lurker © 2026**

See [`CREDITS.md`](CREDITS.md) for project and third-party attribution information.

## Licence

No licence has been selected yet.
