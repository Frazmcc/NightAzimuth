# NightAzimuth v0.3.0-alpha.1

**Created by Logic Lurker © 2026**

This is the third alpha pre-release of NightAzimuth. It adds automatic terrain-horizon generation to the forward-looking Live view so the app can account for hills and raised terrain around the observer while keeping saved location profiles local to the user's PC.

## Highlights

- automatic 360° terrain-horizon generation after a user enters, saves, edits, or selects an observing location
- local terrain cache reused before any download is attempted
- missing Terrarium elevation tiles downloaded automatically and cached locally
- terrain silhouette rendered directly in the Live view
- stars, planets, satellites, and projected tracks geometrically below the calculated terrain skyline are masked by the terrain layer
- optional import of compatible local Terrarium terrain packs
- terrain calculation runs in the background so the main interface remains responsive
- terrain status messages show when data is loading, generated, or unavailable
- bundled end-user guide covering installation, configuration, privacy, terrain behaviour, and normal operation

## Privacy and release hardening

- fresh releases contain no saved observer location, profile name, personal terrain cache, or user runtime configuration
- saved locations are created only after the user enters them and are stored locally under `%APPDATA%\NightAzimuth\locations.json`
- the saved location profile file and profile name are not uploaded to the terrain provider
- terrain requests use standard z/x/y tile identifiers derived from the entered location; the terrain provider can therefore infer the geographic area represented by the requested tiles
- automated tests use synthetic location fixtures rather than personal saved locations
- the Windows build deletes any previous `dist` directory before building
- release-output validation allows only `NightAzimuth.exe` and `NightAzimuth_User_Guide.md` in `dist`
- the build fails if any unexpected file or directory appears in the release output
- `.gitignore` excludes local runtime configuration, saved locations, caches, build output, and virtual environments

## Existing capabilities retained

- saved observing locations with quick switching
- live CelesTrak VISUAL satellite tracking
- current azimuth, elevation, and range
- Sunlit, dark-sky, and Potential visibility indicators
- upcoming pass prediction with rise, peak, set, and maximum elevation
- all-sky radar-style Sky map
- forward-looking Live view with compass or numeric bearing and 30°–180° horizontal FOV
- practical 0–60° Live view elevation range
- mouse-wheel, button, and drag-to-select zoom controls
- three-minute projected satellite tracks with direction of travel
- real Hipparcos star field
- named bright stars and click-to-identify fainter stars
- optional Stellarium constellation lines
- Mercury, Venus, Mars, Jupiter, Saturn, Uranus, and Neptune positioned from the Skyfield ephemeris
- local caching of orbital and astronomy data
- Windows single-file EXE packaging

## Terrain limitations

The terrain skyline is an elevation model rather than a photograph. It does not currently include buildings, trees, hedges, fences, temporary structures, or small nearby features below the terrain model's resolution.

The current Terrarium/Web Mercator path is intended for locations approximately between 85° south and 85° north.

## Visibility limitation

`Potential` still means astronomically plausible: the satellite is illuminated by the Sun while the observer sky is sufficiently dark. It is **not** a guarantee of naked-eye visibility.

The current Potential result does not yet fully account for weather/cloud, satellite brightness, haze, Moon brightness, camera sensitivity, or nearby non-terrain obstructions.

**Created by Logic Lurker © 2026**
