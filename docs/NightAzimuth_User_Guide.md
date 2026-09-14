# NightAzimuth User Guide

**Installation, Configuration and Use**  
**Created by Logic Lurker © 2026**

This guide explains what a normal Windows user needs to configure and how to use NightAzimuth.

> **Privacy:** A fresh NightAzimuth installation contains no saved user location. A location is stored only after the user enters and saves it. Saved location profiles remain on the local PC.

> **Cost:** NightAzimuth is designed to remain free to use. Current weather, map and radar integrations do not require a paid API key or billing account for the intended use.

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
- current point weather including cloud layers, fog, wind and precipitation
- 2D Weather map with an optional recent rain-radar overlay
- local caching of downloaded orbital, astronomical, weather, map, radar and terrain data

## 2. Installation and first launch

For a normal Windows release:

1. Copy the NightAzimuth Windows executable and accompanying user guide to a folder you can access.
2. Run `NightAzimuth.exe`.
3. On first launch, no observing location is preconfigured.
4. Open **Settings** and add your observing location before using satellite, terrain, weather or map calculations.

A fresh copy of NightAzimuth should not contain a user's latitude, longitude, altitude, saved profile name, weather cache, map cache or terrain cache. Those are created only after the user supplies location information.

### Internet access

NightAzimuth uses internet data sources for current orbital data, point weather, map tiles, recent rain-radar tiles and, when required, missing terrain tiles. The star/planet layer can also populate local astronomical catalogue and ephemeris caches on first use. Downloaded data is cached locally so it does not need to be fetched again every time.

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
- Changing the active location refreshes satellite, star, planet, galaxy, terrain, twilight, weather and map calculations for the new observer position.
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
- **Constellation contrast:** `Auto` adapts line colour and thickness to darkness, twilight, daylight and the cloud overlay. Use `Subtle` for a quieter reference layer or `Strong` when you need maximum visibility.
- **All tracked:** exposes the broader potentially-visible satellite set for identification. Leave this off for the cleanest observing view.
- **Cloud overlay:** projects the selected spatial cloud frame into the Live view as an indicative directional layer. When it is enabled, `Auto` raises constellation contrast so the guide lines remain readable.

### What is shown in Live view

- **Vega** is shown as a blue-white reference with current azimuth and elevation.
- Major planets are shown in yellow with name, azimuth and elevation.
- Bright named stars are labelled automatically; more names appear when the field of view is narrower.
- Fainter unnamed stars remain visually subdued so they do not overwhelm satellite tracking.
- Named galaxy references are shown for M31, M33, M81, M82, M51, M101 and M104 when they are above the horizon and inside the current view.
- Satellite markers are deliberately small.
- Normal mode shows up to six potentially-visible or twilight satellite candidates in the current field of view, ranked to favour faster apparent movement.
- Satellite labels include the object name and estimated angular speed when track data is available.
- Thin projected paths show the next three minutes of movement.
- Satellite orbital positions are sampled every second and the on-screen marker is smoothly interpolated between those points.
- The terrain silhouette represents the calculated local skyline for the selected location.

### Sunset and darkness

The Live view shows the current Sun altitude and local-time countdowns for sunset, end of civil twilight, end of nautical twilight and complete astronomical darkness. These values recalculate for the active saved location.

### Weather & cloud panel

The Live view also shows point-weather information for the active observing location. When available this includes:

- air temperature
- humidity
- total cloud percentage
- low, medium and high cloud percentages
- fog percentage
- wind speed and direction
- precipitation amount for the next hour
- a short upcoming hourly cloud/rain summary
- weather source, source-data age, and whether the value came from a live fetch or local cache

This is a point forecast for the observing location. It is **not yet directional cloud information**.

### Weather map

The **Weather map** tab centres a 2D map on the active observing location.

- The white cross marks the selected observing location.
- **Rain radar** toggles the recent RainViewer precipitation-radar overlay.
- **Refresh map** immediately rebuilds the currently displayed map.
- **Cloud imagery (Stage 16)** is visible but disabled until genuine spatial cloud imagery is implemented.
- The base map is provided by OpenStreetMap and the rain-radar overlay is provided by RainViewer.
- Attribution is displayed directly on the map.

NightAzimuth requests only the map tiles required for the currently displayed view. It does not bulk-download map regions. Repeated OpenStreetMap tiles are cached locally for at least seven days before refresh, and radar tiles are cached by frame timestamp.

Because map/radar tile coordinates are derived from the selected observing location, those providers can infer the geographic area being viewed. The saved NightAzimuth profile name and `locations.json` file are not sent.

### Fast movers

Normal Live mode is intended to help identify satellites that are visibly moving across the sky. It ranks candidates primarily by apparent angular speed, then uses elevation and range as additional ranking factors.

This does not mean the top-ranked object is guaranteed to be visible. It means NightAzimuth considers it one of the more useful moving candidates in the part of the sky you are currently looking at.

### All tracked mode

Enable **All tracked** only when you want to expose the wider potentially-visible candidate set. This mode uses tiny markers and suppresses most labels and tracks to avoid clutter. Select an individual satellite if you want its detailed highlight.

### Live satellites

The **Live satellites** table lists tracked satellites currently above the horizon. It includes satellite name, NORAD ID, azimuth, elevation, range, whether the satellite is sunlit, whether the sky is dark enough, and the `Potential` result.

The Live finder uses both the VISUAL and ACTIVE catalogues. This broader coverage is intended to improve identification of real moving satellites that may not be included in the smaller VISUAL group.

### Upcoming passes

The **Upcoming passes** tab shows predicted VISUAL-group passes for the next 24 hours, including rise time, peak time, set time and maximum elevation.

### Refresh

NightAzimuth refreshes live data automatically. Use **Refresh** when you want an immediate orbital-data update. Weather and the Weather map also have their own refresh behaviour.

## 6. Understanding visibility results

> **Important:** `Potential` does not mean the satellite is guaranteed to be visible to the naked eye.

In the current implementation, `Potential` means the satellite is illuminated by the Sun while the observer's sky is sufficiently dark. It is an astronomical suitability indicator rather than a guarantee.

The Live finder may also show sunlit satellite candidates during civil twilight after sunset before the stricter `Potential` threshold is reached.

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
| Point-weather cache | `%APPDATA%\NightAzimuth\cache\weather\` |
| 2D map / rain-radar cache | `%APPDATA%\NightAzimuth\cache\weather_map\` |
| Terrain tile cache | `%APPDATA%\NightAzimuth\terrain\terrarium\` |

- No saved location exists in a fresh release.
- Location profiles are stored locally in `locations.json` only after the user enters them.
- Do not share `locations.json` if it contains a private observing position.
- No real/private test coordinates are intended to be present in source, tests, documentation, installer/build output or release assets.
- Deleting local cache folders removes downloaded cache data; NightAzimuth can repopulate required data when it runs again.
- Weather requests send the selected latitude, longitude and altitude because a location-specific forecast requires them.
- Terrain, map and radar requests may reveal the requested geographic area because tile identifiers are derived from the entered location.
- Saved NightAzimuth profile names and the complete `locations.json` file are not uploaded to these providers.

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
| `celestrak_group` | `VISUAL` | Base CelesTrak group used by source/config-driven workflows. The GUI additionally combines ACTIVE data for live tracking. |
| `cache_directory` | `data/cache` | Cache path for source/config-driven workflows. |
| `cache_max_age_minutes` | 120 | Maximum age before cached orbital data is refreshed. |

For ordinary Windows users, use Settings inside the app for location configuration. Do not edit source configuration files unless you are running or developing the source version.

## 9. Troubleshooting

| Symptom | What to do |
|---|---|
| No location configured | Open Settings, add a location, save it, then choose **Use this location**. |
| `Terrain: loading required data...` | Wait for the first terrain download/calculation to complete. First use can take longer than later cached runs. |
| `Terrain: data download unavailable` | Check the PC's internet connection and try Refresh or reselect the location. |
| Terrain does not match nearby houses or trees | Expected: the terrain layer models elevation, not buildings, vegetation or other local objects. |
| Weather says forecast unavailable | Check internet access. If an older weather cache exists, NightAzimuth will attempt to use it. |
| Weather map unavailable | Check internet access and try **Refresh map**. Satellite tracking and point weather remain usable if the map source is unavailable. |
| Rain radar is empty | The selected area may have no current radar returns or RainViewer coverage may be unavailable. Turn the radar layer off to confirm the base map still loads. |
| No satellites in the current Live view | Drag to a different part of the sky, widen the field of view, reset the view, or check the Sky map / Live satellites table. |
| Too few satellite candidates | Make sure **All tracked** is available for diagnostic use; normal mode intentionally limits the display to the most useful fast movers. |
| Too many satellite markers | Turn **All tracked** off. |
| Star or planet layer is slow on first use | Initial catalogue or ephemeris data may still be populating the local cache. |
| A saved location is sensitive | Keep `%APPDATA%\NightAzimuth\locations.json` private and do not include it in support bundles or source-control uploads. |

## 10. Quick-reference workflow

1. Run NightAzimuth.
2. Open Settings.
3. Add the observing location and save it.
4. Select **Use this location**.
5. Allow NightAzimuth to refresh orbital/astronomical/weather data and generate the terrain horizon.
6. Open **Live view**.
7. Set **Facing** and **Field of view** to approximately match the part of the sky you are observing.
8. Drag the view with the mouse to follow the sky area you are actually looking at.
9. Review the Weather & cloud panel for point conditions.
10. Open **Weather map** when you want the 2D map and recent rain-radar view.
11. Leave **All tracked** off for a clean fast-mover view.
12. Use Vega, named stars, planets and galaxy references for orientation.
13. Follow named satellite markers and their smooth projected movement.
14. Use **Upcoming passes** to plan later observations.
