# Stage 15 Implementation — Weather & Cloud Foundation

Status: **In testing — not yet accepted**

Stage 15 adds a replaceable point-weather provider, a location-aware weather/cloud panel, and a 2D weather map with optional rain-radar overlay. It deliberately does **not** claim directional cloud knowledge yet; that remains Stage 16.

## Project laws

Two rules apply to this stage and every later stage:

1. A release must contain **no saved/test/private observer location**. A fresh install starts with no configured location. Source, tests, release assets and documentation must not embed real user coordinates. Automated tests use synthetic coordinates only.
2. NightAzimuth must remain **100% free to use**. Stage 15 therefore uses only providers that require no paid account, billing setup or paid API key for the intended use. If provider terms change, the provider must be replaced or disabled rather than introducing a charge.

## Point-weather provider

The first provider is **MET Norway Locationforecast 2.0 (compact)**.

NightAzimuth requests the forecast for the currently selected observer latitude, longitude and altitude. The saved NightAzimuth profile name and `locations.json` file are not sent.

The provider is implemented behind a `WeatherProvider` protocol so a different forecast provider or a spatial cloud source can be added later without redesigning the GUI.

## Weather fields

Stage 15 parses and displays, when supplied by the provider:

- air temperature
- relative humidity
- total cloud fraction
- low cloud fraction
- medium cloud fraction
- high cloud fraction
- fog fraction
- wind speed
- wind direction
- precipitation amount for the next hour
- upcoming hourly cloud and precipitation values

## Refresh and cache behaviour

- Forecast data refreshes every 30 minutes.
- Changing the selected location triggers an immediate weather refresh.
- Forecast JSON is cached under the NightAzimuth cache directory in a `weather` subdirectory.
- The weather cache filename uses a hash derived from the observer coordinates rather than placing readable coordinates in the filename.
- A fresh cache entry is reused before another network request is attempted.
- If the provider request fails and an older cache exists, NightAzimuth falls back to the cached forecast.
- The UI identifies whether displayed data came from a live fetch or the cache and shows source-data age where available.

## 2D weather map

Stage 15 adds a **Weather map** tab for the selected observing location.

The map uses:

- OpenStreetMap standard raster tiles for the base map
- RainViewer public Weather Maps API for recent rain-radar tiles
- a local marker at the selected observing location

The rain overlay has its own checkbox and can be turned off independently. A manual **Refresh map** control is also provided.

Only tiles required for the currently displayed 3 × 3 map area are requested. There is no bulk map download or map prefetch feature.

OpenStreetMap tiles are cached locally for at least seven days before NightAzimuth attempts to refresh them. RainViewer radar metadata is refreshed on a short cache interval and radar tiles are cached by radar-frame timestamp.

Visible attribution is drawn directly onto the map image for both OpenStreetMap contributors and RainViewer when radar is enabled.

## Privacy

Stage 15 necessarily sends the selected observer latitude, longitude and altitude to MET Norway because a location-specific forecast cannot be requested otherwise.

For the Weather map, the application requests map/radar tiles whose tile coordinates are derived from the user-entered observing location. Those providers can therefore infer the geographic area being viewed.

NightAzimuth does not send:

- the saved location/profile name
- the `locations.json` file
- any other saved profiles

No personal or real user coordinates are stored in source code or automated tests. Runtime map/weather caches remain under the user's local application-data/cache directories and are not part of the release output.

## Directional cloud limitation

MET Norway Locationforecast is treated as a **point forecast for the observer location**. Stage 15 does not infer that a given azimuth/elevation is clear from this point forecast.

Likewise, RainViewer is used only as a 2D precipitation-radar layer. It is not treated as a cloud-imagery source.

The Live view includes a disabled **Cloud overlay (Stage 16)** control to make the planned feature explicit without pretending that directional cloud projection already exists.

Stage 16 is reserved for genuine spatial cloud imagery and projection into the Live sky view using observer azimuth/elevation, with source age and confidence shown to the user.

## Viewing quality

Stage 15 does not yet produce a `Very good / Good / Fair / Poor` viewing-quality score. That is intentionally deferred until the project has enough cloud/weather evidence to avoid a misleading score.

## Stage gate

Stage 15 must remain on its feature branch until local testing is complete and the user explicitly accepts the stage.
