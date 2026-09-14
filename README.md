# NightAzimuth

**Created by Logic Lurker © 2026**

Location-based live satellite tracking with directional sky identification and observing guidance.

## Current release

**v1.0.0 — first stable release**

NightAzimuth 1.0 combines live satellite tracking, practical sky-finder guidance, terrain, twilight, point weather, spatial cloud imagery, observed rain-radar history, forecast planning, adaptive constellation contrast, dark mode and source-labelled brightness estimates in one local Windows application.

The application has progressed through approved Stage 18. Saved observing locations and downloaded caches remain local to the user's PC. External providers receive only the requests required for orbital, weather, imagery, map or terrain data; NightAzimuth does not upload the saved profile file or profile name.

Camera overlays, aircraft matching, meteor detection and unidentified-event classification remain future work and are not claimed by this release.

See [`RELEASE_NOTES_v1.0.0.md`](RELEASE_NOTES_v1.0.0.md) for release details.

## Initial goal

NightAzimuth is a local application that uses an observer's location and current time to determine which satellites are above the horizon, where they are in the sky, and which are realistically likely to be visible.

NightAzimuth keeps orbital geometry, solar illumination, astronomical darkness, weather/cloud context and source-labelled brightness estimates distinct so the user can see what each result does—and does not—establish.

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
- [`docs/STAGE_14_IMPLEMENTATION.md`](docs/STAGE_14_IMPLEMENTATION.md) — twilight observing state and local countdowns.
- [`docs/STAGE_15_IMPLEMENTATION.md`](docs/STAGE_15_IMPLEMENTATION.md) — point weather and the initial weather map.
- [`docs/STAGE_16_IMPLEMENTATION.md`](docs/STAGE_16_IMPLEMENTATION.md) — spatial cloud imagery, observed history and forecast guidance.
- [`docs/STAGE_17_IMPLEMENTATION.md`](docs/STAGE_17_IMPLEMENTATION.md) — phase geometry and source-labelled satellite brightness estimates.
- [`docs/STAGE_18_IMPLEMENTATION.md`](docs/STAGE_18_IMPLEMENTATION.md) — responsive maps, forecast-tab layout and animation performance.
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
- optional Stellarium constellation lines with adaptive Auto, Subtle and Strong contrast modes
- System, Light and Dark appearance settings
- Mercury, Venus, Mars, Jupiter, Saturn, Uranus and Neptune positioned from the Skyfield ephemeris and labelled when in view
- named galaxy references for M31, M33, M81, M82, M51, M101 and M104
- clickable satellite markers
- selected satellite details including projected azimuth/elevation movement
- live satellites above the horizon
- azimuth, elevation, and range
- sunlit and dark-sky indicators
- potential astronomical visibility
- point weather, cloud layers, fog, wind and precipitation guidance
- responsive Weather map with EUMETSAT cloud imagery and RainViewer radar
- automatic looping observed-weather history covering the previous 24 hours
- separate Forecast tab with next-24-hour and 7-day observing guidance
- selected-satellite phase angle and source-labelled OneWeb brightness ranges where supported
- explicit Unknown and Not sunlit brightness states where an estimate is not justified
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

The `Potential` flag remains deliberately limited to sunlight and dark-sky geometry. Weather/cloud context and supported brightness estimates are displayed separately; haze, moonlight, camera sensitivity, buildings, trees and other non-terrain obstructions are not folded into that flag.

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
