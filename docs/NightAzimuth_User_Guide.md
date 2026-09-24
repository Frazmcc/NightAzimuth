# NightAzimuth User Guide

**Version 1.1.0-rc1 — Release Candidate**  
**Created by Logic Lurker © 2026**

NightAzimuth is a local Windows application for viewing the real sky from a user-selected observing location, tracking satellites and aircraft, and planning observing conditions.

> **Release candidate:** `v1.1.0-rc1` is intended for real-world testing before the final `v1.1.0` release. Report unexpected behaviour before treating it as the final stable build.

> **Privacy:** NightAzimuth contains no hard-coded user location. Saved observing locations remain on the local PC. Location-dependent calculations use only the location selected by the user.

> **Cost:** The application is designed around free/no-key data sources where practical and does not require a paid API subscription for normal use.

## 1. Installation

The release contains:

- `NightAzimuth-v1.1.0-rc1-Windows-x64.exe`
- `NightAzimuth-v1.1.0-rc1-User-Guide.md`
- `NightAzimuth-v1.1.0-rc1-SHA256.txt`

Run the Windows executable directly. Windows may display a reputation warning because the executable is not code-signed.

Existing settings, saved locations and caches under `%APPDATA%\NightAzimuth` are retained when upgrading.

## 2. Configure a location

Open **Settings**, create or edit an observing profile, and enter:

- location name
- latitude in decimal degrees
- longitude in decimal degrees
- altitude in metres

Select **Use this location** to make it active.

NightAzimuth never ships with a fixed local airport list, local coordinates or a preset user location. Terrain, airports, timezone, weather and sky calculations are derived from the active location at runtime.

## 3. Main application layout

The application starts maximised and adapts its layout to the effective Windows/Tk display size and DPI scaling.

The **Live Sky** is the main surface. Supporting information is placed in collapsible drawers below it rather than permanently reducing sky space.

Available drawers include:

- **LIVE FINDER**
- **AIRCRAFT CONTACTS**
- **ISS / PASSES**
- **SATELLITE INFO**

Press **F11** for fullscreen and **Escape** to leave fullscreen.

A large green digital clock in the header shows the local time for the selected observing location together with its UTC offset.

## 4. Live Sky

The Live Sky is designed to resemble the geometry and visual priorities of a person looking at the real sky rather than a flat plotting chart.

It uses an observer-centred spherical/stereographic projection with:

- curved wide-field geometry
- a projected local terrain skyline
- horizon airlight/haze cues
- reduced peripheral emphasis for non-selected objects
- daylight/twilight/night-dependent star visibility
- atmospheric extinction toward the horizon
- subtle stellar scintillation
- dark-adapted celestial colour reduction
- real Moon position from the Skyfield ephemeris

The terrain horizon is a calculated elevation skyline, not a photograph. It does not include buildings, trees, fences or temporary obstructions.

### Moving the view

Use the facing/FOV controls, mouse drag and mouse wheel to move around the sky. Reset View returns to the configured viewing direction and normal zoom.

## 5. Satellites

NightAzimuth uses CelesTrak orbital data and displays real tracked satellites in the current field of view during both day and night.

Visibility estimates affect prominence, not whether an otherwise valid tracked object exists on the display.

Satellite markers use a contrasting colour family so they can be distinguished quickly from aircraft and natural celestial objects.

### Realtime satellite motion

Stage 20 uses a rolling short-horizon orbital prediction model:

- orbital positions are sampled every second
- marker position is interpolated at approximately 20 frames per second
- future tracks are rebased repeatedly from the interpolated current position
- selected satellites and the ISS are prioritised for prediction
- many in-view satellites can receive prediction data while only a limited number of tracks are drawn automatically to avoid clutter

The result is smooth local motion without depending on network refresh frequency for every frame.

### Selecting and deselecting

Click a satellite once to select it.

Selection:

- highlights the satellite
- prioritises its realtime track
- opens **SATELLITE INFO**

Click the **same satellite again** to deselect it. This removes the selected-object priority, closes/clears the Satellite Info state and restores normal automatic priorities without changing display controls the user deliberately selected.

Clicking another satellite switches selection directly to the new object.

## 6. Satellite Info

The **SATELLITE INFO** drawer loads verified information in the background for the selected object.

Where available it can show:

- satellite name
- NORAD catalogue ID
- COSPAR / international designator
- owner/country/source description
- object type and operational status
- launch date and launch site
- current azimuth, elevation and range
- sunlight/shadow state
- phase angle
- supported brightness estimate
- orbital period
- inclination
- apogee and perigee
- radar cross-section
- orbit centre/type
- mission/purpose summary
- public technical or notable feature information
- a public image when a sufficiently confident source match exists

CelesTrak SATCAT provides catalogue/orbital metadata. CelesTrak's current source table is used to resolve owner/source codes dynamically. Wikipedia/Wikimedia is used conservatively for descriptive mission information and public imagery.

If NightAzimuth cannot verify a field or image, it reports the information as unavailable rather than inventing a value or forcing a questionable match.

## 7. ISS and upcoming passes

The International Space Station (NORAD 25544) is treated as a first-class trackable object.

The **ISS / PASSES** drawer shows ISS status and upcoming visual passes. Passes beginning within approximately one hour are prioritised as immediate observing alerts.

ISS remains prioritised in the satellite prediction system when orbital data is available.

## 8. Aircraft / ADS-B

Aircraft are shown using a separate visual family from satellites. Where type information allows, NightAzimuth uses different vector silhouettes for fixed-wing aircraft, helicopters/rotorcraft, gliders, UAVs and other supported classes.

ADS-B data is refreshed in the background. A transient failed or zero-contact refresh does not intentionally wipe an already populated aircraft scene; the last populated snapshot can be retained while fresh data is obtained.

### Aircraft priority board

The **AIRCRAFT CONTACTS** drawer is a fixed-size priority board rather than a long list that requires scrolling.

Ordering is designed to surface important traffic first:

1. emergency/special squawks
2. other recognised special-operation traffic
3. military traffic
4. relevant normal traffic

Recognised squawk codes remain visible with a short plain-English description.

### Selected aircraft information

Where data exists, selected-aircraft details can include:

- callsign
- squawk and description
- operator / role
- aircraft make/model
- capacity hint where a defensible type-level value/range exists
- departure airport
- arrival airport
- departure time when a source genuinely supplies one
- estimated arrival time when it can be calculated from available route/position/speed information
- altitude, speed, track, range and other live telemetry

NightAzimuth does not fabricate airline schedule data. Missing departure/schedule information is shown as unavailable.

Role inference supports recognised metadata signals such as Air Ambulance/HEMS, Police, Coastguard/Search and Rescue, military and related specialist operations.

## 9. Airport horizon references

Airport labels are a small horizon-reference layer, not a general airport map.

NightAzimuth obtains a global public airport dataset and calculates relevant airport distance/bearing from the currently selected observing location. Only a limited number of meaningful airports that fit the current view/range are considered, and overlapping labels are suppressed.

No local airport, city, country or coordinate list is hard-coded into the application.

## 10. Stars, planets, Moon and galaxies

Natural celestial objects are visually distinct from satellites and aircraft.

- stars use a neutral/white visual family
- planets use a warmer presentation
- galaxies are subdued reference objects
- the Moon uses its real ephemeris position and a lightweight glare treatment

Star visibility responds to sky state and atmospheric extinction. A plotted celestial object is still not a guarantee that local weather, light pollution or eyesight makes it visible unaided.

## 11. Weather Map and Forecast

Weather/cloud controls were removed from the **Live Sky** to reduce visual noise, but the dedicated weather functionality remains available.

### Weather Map

The Weather Map keeps the map/radar presentation separate from Live Sky and may include supported precipitation/cloud imagery and historical provider frames.

### Forecast

The **Forecast** tab remains available for observing planning, including next-24-hour and multi-day guidance based on supported provider data.

NightAzimuth does not invent missing historical or forecast frames.

## 12. Refresh continuity

Live Sky is designed around a last-good-scene rule. Background refreshes should not intentionally clear an existing populated scene before replacement data is ready.

This applies particularly to satellite and ADS-B handoffs so normal network refresh behaviour does not produce a blank main display.

A deliberate observing-location change is different: location-derived data is recalculated for the newly selected observer.

## 13. Privacy and local data

Typical local data is stored beneath `%APPDATA%\NightAzimuth`.

Examples include:

- `locations.json` for saved observing profiles
- application preferences
- orbital/astronomical cache data
- weather/map cache data
- terrain tiles

Do not share `locations.json` if it contains a private observing position.

External providers may infer the geographic area represented by a location-derived request because weather, airport, map and terrain queries require geographic context. NightAzimuth does not upload the complete saved profile file or profile name as part of those requests.

## 14. Accuracy boundaries

NightAzimuth separates several concepts that should not be treated as equivalent:

- geometrically above the horizon
- illuminated by the Sun
- favourable observing geometry
- expected naked-eye visibility
- weather/cloud conditions
- brightness estimates

Satellite brightness can vary with attitude, geometry, flares/glints and spacecraft design. Unsupported objects remain unknown rather than receiving fabricated brightness values.

Aircraft route/timing data can also be incomplete or delayed. Live ETA values are estimates unless explicitly supplied by an authoritative schedule source.

## 15. Troubleshooting

If the Live Sky appears stale, first allow the current background refresh to finish, then use **Refresh** if required.

If aircraft briefly stop updating, the previous scene may intentionally remain visible while ADS-B recovers. Check the status/freshness information rather than assuming retained markers are newly received positions.

If a satellite track is missing, select the satellite once. Selected satellites are forced into the realtime prediction priority set when orbital data is available.

If a Satellite Info image or mission description is unavailable, the catalogue/orbit information can still be valid; enrichment is deliberately fail-soft.

If terrain or airport labels do not appear immediately after changing location, allow the background location-derived calculations to complete.

## 16. Release-candidate feedback

For `v1.1.0-rc1`, concentrate testing on:

- application launch and maximised layout
- F11 fullscreen
- location switching
- Live Sky continuity during refreshes
- aircraft/ADS-B continuity
- aircraft priority and squawk descriptions
- satellite selection/deselection
- smooth satellite marker and track motion
- Satellite Info enrichment
- ISS/pass information
- airport horizon references
- Forecast and Weather Map tabs
- resizing and Windows display scaling

If these remain stable in normal use, the release candidate can be promoted to the final `v1.1.0` release.
