# NightAzimuth User Guide

**Installation, Configuration and Use**  
**Created by Logic Lurker © 2026**

This guide explains what a normal Windows user needs to configure and how to use NightAzimuth.

> **Privacy:** A fresh NightAzimuth installation contains no saved user location. A location is stored only after the user enters and saves it. Saved location profiles remain on the local PC.

## 1. What NightAzimuth does

NightAzimuth is a Windows desktop application that uses an observer location and the current time to show satellites that are above the horizon, where they are in the sky, and whether conditions are astronomically suitable for seeing them.

Current features include:

- all-sky radar-style Sky map
- forward-looking Live finder with facing direction, field-of-view, mouse panning and zoom controls
- full 0–90° elevation coverage, including directly overhead
- broad live satellite coverage using CelesTrak VISUAL + ACTIVE catalogues
- current satellite azimuth, elevation and range
- fast-mover ranking to highlight satellites moving most quickly across the current view
- sunlit twilight satellite candidates after sunset before the stricter dark-sky threshold is reached
- three-minute projected satellite tracks sampled every second
- smooth satellite marker movement interpolated at approximately 20 frames per second
- location-aware sunset, civil-twilight, nautical-twilight and complete-darkness countdowns
- current Sun altitude and sky-state display
- Live-view background colour that reflects daylight, twilight or darkness
- offline time-zone lookup for the active observing location
- real Hipparcos star field, named bright stars, constellation guides, major planets and selected named galaxies
- Vega emphasised as a visual reference
- upcoming VISUAL-group passes for the next 24 hours
- automatic terrain-horizon generation for the selected observing location
- local caching of downloaded orbital, astronomical and terrain data

## 2. Installation and first launch

For a normal Windows release:

1. Copy the NightAzimuth Windows executable and accompanying user guide to a folder you can access.
2. Run `NightAzimuth.exe`.
3. On first launch, no observing location is preconfigured.
4. Open **Settings** and add your observing location before using satellite or terrain calculations.

A fresh copy of NightAzimuth should not contain a user's latitude, longitude, altitude, saved profile name or terrain cache. Those are created only after the user supplies location information.

### Internet access

NightAzimuth uses internet data sources for current orbital data and, when required, missing terrain tiles. The star/planet layer can also populate local astronomical catalogue and ephemeris caches on first use. Downloaded data is cached locally so it does not need to be fetched again every time.

Sunset, twilight, Sun-altitude and time-zone calculations are performed locally once the required astronomical/time-zone data is available. NightAzimuth does not use a paid sunset or timezone API.

## 3. Configure your observing location

For normal use, configure NightAzimuth through the **Settings** window. You do not need to manually edit a configuration file to add a location.

### Add a location

1. Select **Settings** in the top-right of the main window.
2. Select **New**.
3. Enter a **Location name**. This is only the local label shown inside NightAzimuth.
4. Enter **Latitude** in decimal degrees.
5. Enter **Longitude** in decimal degrees.
6. Enter **Altitude (m)** in metres above sea level.
7. Select **Save location**.
8. Select **Use this location** to make it the active observer position.

| Field | What to enter | Format |
|---|---|---|
| Location name | Any local label you recognise | Text |
| Latitude | Decimal degrees; north positive, south negative | `<decimal latitude>` |
| Longitude | Decimal degrees; east positive, west negative | `<decimal longitude>` |
| Altitude | Metres above sea level | `<metres>` |

Enter the coordinates for the observing position you actually want NightAzimuth to use. The release itself does not provide a preset real-world observer location.

### Edit or switch locations

- To edit a saved location, select it in Settings, change the values and save it.
- To switch locations quickly, use the **Location** drop-down in the main window.
- Changing the active location refreshes satellite, star, planet, galaxy, terrain, sunset/twilight and time-zone calculations for the new observer position.
- Old celestial and terrain overlays are cleared while the replacement view is calculated.

## 4. Terrain horizon

After a user enters a location, NightAzimuth automatically builds a 360° terrain skyline for that observer position. The skyline is used in Live view so hills and raised terrain can mask objects that are geometrically behind them.

### What happens automatically

1. NightAzimuth checks the local terrain cache first.
2. If a required terrain tile is already cached, it is reused.
3. If a required tile is missing, NightAzimuth downloads the Terrarium elevation tile needed for that area.
4. Downloaded tiles are saved locally under the NightAzimuth application-data folder.
5. The terrain horizon is calculated in the background.
6. Live view shows `Terrain: generated` when the calculation completes.

### Terrain privacy

The saved `locations.json` file and the local profile name are not uploaded. Terrain requests use standard map-tile identifiers derived from the user-entered location. A terrain service can therefore infer the geographic area of the requested tiles.

### Optional offline terrain pack

Settings also provides **Import offline terrain pack...** for users who already have a compatible Terrarium tile folder. Imported tiles are copied into NightAzimuth's local terrain directory and can be reused by the automatic terrain calculation.

### Terrain limitations

The calculated skyline models terrain elevation, not a photograph. It does not include houses, trees, hedges, fences or temporary obstructions. Small nearby features below the terrain model's resolution may not be represented.

Current Terrarium/Web Mercator handling is intended for locations roughly between 85° south and 85° north.

## 5. Using the main views

### Sky map

The **Sky map** is an all-sky radar-style view. The outer edge represents the horizon and the centre represents the zenith. Click a satellite marker to see its current details.

### Live finder

The **Live** view is the main observing screen. It is designed to behave more like a sky finder than a static chart.

- **Facing:** enter a bearing from 0–359° or use `N`, `NE`, `E`, `SE`, `S`, `SW`, `W` or `NW`.
- **Field of view:** choose 30°, 45°, 60°, 90°, 120° or 180°.
- **Move the view:** hold the left mouse button on empty sky and drag horizontally or vertically.
- **Elevation:** the finder can move from the horizon at 0° all the way to the zenith at 90°.
- **Zoom:** use the mouse wheel or + / − buttons.
- **Reset view:** returns to the configured facing direction and the normal full 0–90° elevation range.
- **Stars:** toggles the star layer.
- **Constellations:** toggles constellation guide lines.
- **All tracked:** exposes the broader observing-candidate set for identification. Leave this off for the cleanest observing view.

### Sunset and darkness panel

The Live view includes a **Sunset and darkness** panel based on the currently selected observing location. It shows:

- current sky state
- current Sun altitude
- local time zone for the observing location
- sunset time and countdown
- civil twilight end and countdown
- nautical twilight end and countdown
- complete darkness (astronomical darkness) and countdown

The countdown updates continuously. The underlying observing conditions are recalculated periodically and whenever the active location changes.

Event times are displayed in the local time zone for the selected observing location, not simply the computer's current time zone.

### Solar-state background

The Live finder background changes to reflect the current solar state for the selected location:

- daylight
- civil twilight
- nautical twilight
- astronomical twilight
- dark

The colours are intentionally muted so satellite markers, the HUD grid and celestial labels remain readable.

### What is shown in Live view

- **Vega** is shown as a blue-white reference with current azimuth and elevation.
- Major planets are shown in yellow with name, azimuth and elevation.
- Bright named stars are labelled automatically; more names appear when the field of view is narrower.
- Fainter unnamed stars remain visually subdued so they do not overwhelm satellite tracking.
- Named galaxy references are shown for M31, M33, M81, M82, M51, M101 and M104 when they are above the horizon and inside the current view.
- Satellite markers are deliberately small.
- Normal mode shows up to six useful observing candidates in the current field of view, ranked to favour faster apparent movement.
- During civil twilight after sunset, a sunlit satellite may appear in the Live finder before the stricter `Potential` condition becomes true.
- Satellite labels include the object name and estimated angular speed when track data is available.
- Thin projected paths show the next three minutes of movement.
- Satellite orbital positions are sampled every second and the on-screen marker is smoothly interpolated between those points.
- The terrain silhouette represents the calculated local skyline for the selected location.

### Fast movers

Normal Live mode is intended to help identify satellites that are visibly moving across the sky. It ranks candidates primarily by apparent angular speed, then uses elevation and range as additional ranking factors.

This does not mean the top-ranked object is guaranteed to be visible. It means NightAzimuth considers it one of the more useful moving candidates in the part of the sky you are currently looking at.

### All tracked mode

Enable **All tracked** only when you want to expose the wider observing-candidate set. This mode uses tiny markers and suppresses most labels and tracks to avoid clutter. Select an individual satellite if you want its detailed highlight.

### Live satellites

The **Live satellites** table lists tracked satellites currently above the horizon. It includes satellite name, NORAD ID, azimuth, elevation, range, whether the satellite is sunlit, whether the sky is dark enough, and the `Potential` result.

The Live finder uses both the VISUAL and ACTIVE catalogues. This broader coverage is intended to improve identification of real moving satellites that may not be included in the smaller VISUAL group.

### Upcoming passes

The **Upcoming passes** tab shows predicted VISUAL-group passes for the next 24 hours, including rise time, peak time, set time and maximum elevation.

### Refresh

NightAzimuth refreshes live data automatically. Use **Refresh** when you want an immediate update.

## 6. Understanding visibility results

> **Important:** `Potential` does not mean the satellite is guaranteed to be visible to the naked eye.

In the current implementation, `Potential` means the satellite is illuminated by the Sun while the observer's sky is sufficiently dark. It is an astronomical suitability indicator rather than a guarantee.

The Live finder can also show a sunlit satellite during civil twilight after sunset. This is a useful observing candidate, but it does not receive the stricter `Potential` status until the dark-sky threshold is met.

The current Potential result does not yet fully account for:

- cloud and haze
- satellite brightness or apparent magnitude
- reflective orientation or flares
- moonlight
- camera sensitivity
- buildings, trees and other local obstructions

Terrain is drawn in Live view as a local geometric obstruction layer, but it remains separate from the current Potential calculation.

Fast-mover ranking is also separate from brightness. A satellite can move quickly but still be too faint to see with the naked eye.

## 7. Local files, privacy and cache data

| Purpose | Default Windows location |
|---|---|
| Saved locations | `%APPDATA%\NightAzimuth\locations.json` |
| Orbital / astronomical cache | `%APPDATA%\NightAzimuth\cache\` |
| Terrain tile cache | `%APPDATA%\NightAzimuth\terrain\terrarium\` |

- No saved location is required to exist before the user configures one.
- Location profiles are stored locally in `locations.json`.
- Do not share `locations.json` if it contains a private observing position.
- Deleting local cache folders removes downloaded cache data; NightAzimuth can repopulate required data when it runs again.
- Terrain requests may reveal the requested geographic area to the terrain provider because the tile identifiers are derived from the entered location.
- Sunset/twilight and time-zone calculations use the selected location locally and do not require a paid external lookup service.

## 8. Advanced configuration for source/development use

The normal Windows GUI uses saved location profiles and does not require a user to create a TOML configuration file. The project also contains a TOML configuration loader used by lower-level/source workflows.

Illustrative structure:

```toml
[observer]
latitude = <decimal latitude>
longitude = <decimal longitude>
altitude_m = <metres>

[tracking]
minimum_elevation_deg = 0
pass_minimum_elevation_deg = 10
pass_prediction_hours = 24
darkness_threshold_deg = -6

[data]
celestrak_group = "VISUAL"
cache_directory = "data/cache"
cache_max_age_minutes = 120
```

| Setting | Default | Meaning |
|---|---:|---|
| `minimum_elevation_deg` | 0 | Minimum elevation used by tracking configuration. |
| `pass_minimum_elevation_deg` | 10 | Minimum elevation used for pass predictions. |
| `pass_prediction_hours` | 24 | How far ahead pass predictions extend. |
| `darkness_threshold_deg` | -6 | Sun-angle threshold used for the dark-sky test. |
| `celestrak_group` | `VISUAL` | Base CelesTrak group used by source/config-driven workflows. The current GUI additionally combines ACTIVE data for live tracking. |
| `cache_directory` | `data/cache` | Cache path for source/config-driven workflows. |
| `cache_max_age_minutes` | 120 | Maximum age before cached orbital data is refreshed. |

For ordinary Windows users, use Settings inside the app for location configuration. Do not edit source configuration files unless you are running or developing the source version.

## 9. Troubleshooting

| Symptom | What to do |
|---|---|
| No location configured | Open Settings, add a location, save it, then choose **Use this location**. |
| Sunset/darkness values look wrong after moving location | Confirm the correct saved location is selected; switching location forces a recalculation for that observer position. |
| `Terrain: loading required data...` | Wait for the first terrain download/calculation to complete. First use can take longer than later cached runs. |
| `Terrain: data download unavailable` | Check the PC's internet connection and try Refresh or reselect the location. |
| Terrain does not match nearby houses or trees | Expected: the terrain layer models elevation, not buildings, vegetation or other local objects. |
| No satellites in the current Live view | Drag to a different part of the sky, widen the field of view, reset the view, or check the Sky map / Live satellites table. During daylight, normal Live mode can still be intentionally sparse because twilight/dark observing conditions are not yet present. |
| Too few satellite candidates | Make sure **All tracked** is available for diagnostic use; normal mode intentionally limits the display to the most useful fast movers. |
| Too many satellite markers | Turn **All tracked** off. |
| Star or planet layer is slow on first use | Initial catalogue or ephemeris data may still be populating the local cache. |
| A saved location is sensitive | Keep `%APPDATA%\NightAzimuth\locations.json` private and do not include it in support bundles or source-control uploads. |

## 10. Quick-reference workflow

1. Run NightAzimuth.
2. Open Settings.
3. Add the observing location and save it.
4. Select **Use this location**.
5. Allow NightAzimuth to refresh orbital/astronomical data and generate the terrain horizon.
6. Open **Live view**.
7. Check the **Sunset and darkness** panel to see the current sky state and countdowns.
8. Set **Facing** and **Field of view** to approximately match the part of the sky you are observing.
9. Drag the view with the mouse to follow the sky area you are actually looking at.
10. Leave **All tracked** off for a clean fast-mover view.
11. Use Vega, named stars, planets and galaxy references for orientation.
12. Follow named satellite markers and their smooth projected movement.
13. Use **Upcoming passes** to plan later observations.
