# Stage 15 Implementation — Weather & Cloud Foundation

Status: **In testing — not yet accepted**

Stage 15 adds a replaceable point-weather provider and a location-aware weather/cloud panel to NightAzimuth. It deliberately does **not** claim directional cloud knowledge yet; that remains a later stage.

## Provider

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
- The cache filename uses a hash derived from the observer coordinates rather than placing readable coordinates in the filename.
- A fresh cache entry is reused before another network request is attempted.
- If the provider request fails and an older cache exists, NightAzimuth falls back to the cached forecast.
- The UI identifies whether displayed data came from a live fetch or the cache and shows source-data age where available.

## Privacy

Stage 15 necessarily sends the selected observer latitude, longitude and altitude to the weather provider because a location-specific forecast cannot be requested otherwise.

NightAzimuth does not send:

- the saved location/profile name
- the `locations.json` file
- any other saved profiles

No personal or real user coordinates are stored in source code or automated tests.

## Directional cloud limitation

MET Norway Locationforecast is treated as a **point forecast for the observer location**. Stage 15 does not infer that a given azimuth/elevation is clear from this point forecast.

The Live panel therefore explicitly states that directional cloud estimation is not yet active. A later stage can combine spatial cloud data with the observer's viewing azimuth/elevation.

## Viewing quality

Stage 15 does not yet produce a `Very good / Good / Fair / Poor` viewing-quality score. That is intentionally deferred until the project has enough cloud/weather evidence to avoid a misleading score.

## Stage gate

Stage 15 must remain on its feature branch until local testing is complete and the user explicitly accepts the stage.
