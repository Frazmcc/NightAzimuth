# NightAzimuth v1.0.0

**Created by Logic Lurker © 2026**

NightAzimuth 1.0.0 is the first stable major release. It brings the approved work through Stage 18 into one Windows application focused on identifying satellites and understanding the real observing context around them.

## Highlights

### Live satellite finder

- CelesTrak VISUAL and ACTIVE catalogue coverage
- live azimuth, elevation and observer range
- sunlight and dark-sky geometry kept separate from visibility claims
- fast-mover prioritisation in the selected field of view
- one-second projected orbital samples with smooth 20 fps marker interpolation
- short predicted paths and selected-object details
- twilight observing candidates before full darkness

### Sky references and local horizon

- real Hipparcos star field
- named bright stars, major planets and selected galaxies
- Vega orientation reference
- Stellarium constellation guides
- adaptive Auto, Subtle and Strong constellation contrast
- automatic terrain-horizon generation and optional offline Terrarium tile import

### Weather, cloud and planning

- MET Norway point weather and forecast data
- EUMETSAT spatial cloud imagery
- RainViewer precipitation radar where provider frames are available
- directional cloud overlay in the Live finder
- automatically looping observed-weather history from 24 hours ago through Now
- responsive map sizing without repeated tile downloads during window resizing
- separate Forecast tab for next-24-hour and 7-day observing guidance

### Brightness estimates

- real Sun–satellite–observer phase-angle geometry
- source-labelled OneWeb apparent-magnitude ranges using a published empirical phase function
- explicit confidence and flare/glint warning
- unsupported spacecraft remain **Unknown** rather than receiving a fabricated value
- eclipsed spacecraft show **Not sunlit**

### Desktop experience

- screen-aware initial window sizing
- responsive map panels
- System, Light and Dark appearance modes
- scrollable Live view for smaller displays
- background refresh work designed to keep live motion responsive
- safer weather error messages that do not expose observer coordinates

## Accuracy boundaries

Potential means the satellite is sunlit while the observer's sky meets the configured darkness threshold. It is not a guarantee of naked-eye visibility.

Weather, directional cloud and brightness are displayed as separate evidence with their own source and uncertainty. OneWeb brightness is a family-level empirical estimate; spacecraft attitude and brief flares or glints are not predicted. Historical radar/cloud frames depend on upstream availability and are never invented.

Camera input, aircraft/ADS-B matching, meteor detection and unidentified-event classification are not included in v1.0.0.

## Privacy and cost

- saved observer profiles remain local to the PC
- no saved location or personal cache is packaged in the release
- no paid API key or billing account is required
- providers can infer the geographic area represented by location-derived forecast, map, imagery or terrain requests
- the saved profile name and complete locations.json file are not uploaded

## Installation

Download these assets from the GitHub release:

- NightAzimuth-v1.0.0-Windows-x64.exe
- NightAzimuth-v1.0.0-User-Guide.md
- NightAzimuth-v1.0.0-SHA256.txt

Keep the executable and guide together, verify the SHA-256 checksum if desired, and run the executable. Windows may show a reputation warning because the application is not code-signed.

Existing local observing profiles and caches under %APPDATA%\NightAzimuth are retained when upgrading.

## Data and attribution

NightAzimuth uses CelesTrak, Skyfield/JPL ephemeris data, Hipparcos, Stellarium sky-culture data, MET Norway, OpenStreetMap, RainViewer, EUMETSAT/NASA imagery and Terrarium-compatible terrain data. Provider availability, terms and attribution requirements continue to apply.
