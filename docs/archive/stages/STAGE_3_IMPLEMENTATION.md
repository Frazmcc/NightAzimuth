# Stage 3 — Core satellite tracking

## Scope

Stage 3 implements only the first functional NightAzimuth tracking layer:

- observer latitude, longitude, and altitude
- current UTC time
- CelesTrak GP orbital data in OMM JSON format
- local orbital-data caching
- SGP4 propagation through Skyfield
- topocentric azimuth, elevation, and range
- filtering of satellites below a configurable minimum elevation
- a simple command-line output for verification

## Deliberately excluded

The following remain out of scope until separately approved:

- cloud and weather integration
- solar illumination / satellite brightness
- astronomical darkness
- pass prediction
- directional field-of-view filtering
- graphical sky map
- camera integration
- aircraft, meteor, or unknown-object classification

## Data source

NightAzimuth requests CelesTrak GP data using the `GROUP` selector and `FORMAT=JSON`.
The JSON payload uses OMM field names and is loaded into Skyfield with
`EarthSatellite.from_omm()`.

The default group in the example configuration is `ACTIVE`. The group is configurable so smaller groups such as `STATIONS` can be used during testing.

## Cache behaviour

Orbital data is cached locally. The default cache lifetime is 120 minutes. If a refresh attempt fails but a previous cache file exists, NightAzimuth falls back to that cached copy rather than failing immediately.

A later stage should expose cache age and data freshness visibly to the user.

## Running the Stage 3 tracker

Create a local configuration file from the example and enter the observer coordinates:

```bash
python -m pip install -e .
nightazimuth --config config/nightazimuth.toml
```

The command prints the satellites currently above the configured minimum elevation, sorted from highest to lowest elevation.

Example columns:

- satellite name
- NORAD catalogue ID
- azimuth in degrees
- elevation in degrees
- range in kilometres

## Stage 3 acceptance condition

Stage 3 is considered successful when NightAzimuth can take an observer location and current time, load current CelesTrak orbital data, and return the satellites geometrically above that observer's horizon with azimuth, elevation, and range.

This stage does **not** claim that an above-horizon satellite is visible to the eye. Visibility is intentionally reserved for later stages.
