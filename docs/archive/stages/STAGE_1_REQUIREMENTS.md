# Stage 1 Requirements

Status: **Approved**

This document records the agreed starting requirements for NightAzimuth. These requirements define the intended v0.1 scope and should not be treated as implemented functionality until later stages add and test it.

## Core purpose

NightAzimuth will be a local, location-based live satellite tracker that helps an observer determine which satellites are above the horizon, where they are in the sky, and which are realistically likely to be visible.

The first functional versions will not require a camera.

## Observer and time

NightAzimuth will:

- Use a saved observer latitude, longitude, and altitude.
- Use the current date and time automatically for live tracking.
- Allow the observer location to be configured precisely rather than relying on coarse IP geolocation.
- Provide an in-app Settings area where observer coordinates can be entered and edited without manually changing configuration files.
- Support multiple saved observer/location profiles, each with a friendly name such as `Home`, `Garden`, or `Dark Sky Site`.
- Allow the active observer location to be changed quickly from within the app.
- Remember the last selected observer profile between launches.
- Allow latitude, longitude, and altitude to be stored per saved profile.
- Keep observer/location data local to the user's installation unless a future explicitly approved feature adds synchronisation.

## Satellite tracking

NightAzimuth is intended to calculate and display, for relevant catalogue objects:

- Satellite name.
- Catalogue/NORAD identifier or equivalent supported catalogue identifier.
- Current azimuth.
- Current elevation.
- Direction of travel.
- Orbital altitude.
- Range from the observer.
- Angular movement where practical.
- Rise time.
- Maximum-elevation time and elevation.
- Set time.
- Whether the satellite is illuminated by the Sun.
- Whether observing conditions make visual detection plausible.
- Age/freshness of the orbital data used.

## Sky display

A later implementation will provide a live radar-style sky view where:

- The horizon forms the outside edge.
- The zenith is at the centre.
- Cardinal directions are clearly labelled.
- Satellite positions update live.
- Individual satellites can be selected for more detail.

## Filtering

Planned filters include:

- All satellites.
- Potentially visible satellites only.
- Sunlit satellites only.
- Bright satellites.
- Space stations / ISS.
- Starlink.
- OneWeb.
- Weather satellites.
- Navigation satellites.
- Geostationary satellites.
- Other supported satellite groups.

The exact provider group names and catalogue coverage will be selected during implementation.

## Directional identification

NightAzimuth will include a "What am I looking at?" capability.

The user will be able to provide a viewing azimuth and elevation, optionally with a tolerance, and receive candidate satellite matches near that direction at the selected time.

## Visibility versus geometry

NightAzimuth must not treat "above the horizon" as equivalent to "visible".

Visibility assessment should eventually consider at least:

- Satellite elevation.
- Solar illumination of the satellite.
- Observer twilight/darkness conditions.
- Atmospheric/weather conditions.
- Cloud conditions.
- Data freshness and uncertainty.

Any visibility result must be presented as an estimate rather than certainty where the available data cannot support certainty.

## Weather and cloud awareness

Weather is part of the initial product scope because cloud can determine whether an otherwise visible satellite can actually be observed.

NightAzimuth should eventually combine:

- Current weather information where available.
- Hourly forecast information.
- Cloud information.
- Visibility.
- Precipitation probability/conditions.
- Fog or similar obscuration where available.
- Astronomical darkness / Sun altitude.

## Directional, near-real-time cloud requirement

A single whole-location cloud percentage is not sufficient for NightAzimuth.

The cloud system should aim to use the freshest practical spatial cloud information available and estimate cloud conditions for the specific part of the sky being viewed.

The intended model is:

1. Observer location is known.
2. Viewing azimuth and elevation are known.
3. Spatial cloud data is obtained from one or more replaceable providers.
4. NightAzimuth estimates whether cloud is likely to intersect that line of sight.
5. The result includes source, data age, and confidence where possible.

The implementation should support interchangeable cloud/weather providers so that a forecast provider can later be supplemented or replaced by a more immediate cloud-imagery source without redesigning the rest of the application.

## Viewing quality

NightAzimuth should eventually derive a viewing-quality assessment from astronomy and weather information, for example:

- Very good.
- Good.
- Fair.
- Poor.

The thresholds must not be treated as fixed until tested against real observing conditions.

A future feature may identify the best observing windows by combining darkness, cloud/weather conditions, and predicted satellite passes.

## Data handling

NightAzimuth should:

- Cache external data locally where appropriate.
- Respect upstream provider usage policies and refresh intervals.
- Make data freshness visible to the user.
- Never store API keys directly in committed source code or committed configuration.

## Explicitly out of scope for the first tracker

The initial tracker will not yet:

- Require or process a camera feed.
- Automatically detect moving objects in video.
- Classify unidentified aerial phenomena.
- Match aircraft through ADS-B.
- Detect meteors.
- Record unidentified-event evidence packages.

These may be considered in later approved stages after the satellite tracker is accurate and reliable.

## Development rule

NightAzimuth is developed using stage gates. The project must only progress to the next stage after the current stage has been reviewed and explicitly approved.
