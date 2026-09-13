# NightAzimuth v0.5.0-beta.1

**Created by Logic Lurker © 2026**

This beta release adds location-aware twilight timing and improves real-world observing behaviour before full darkness.

## Highlights

- live **Sunset and darkness** panel for the selected observing location
- current Sun altitude and current sky state
- local-time countdowns to sunset, end of civil twilight, end of nautical twilight and complete astronomical darkness
- offline timezone resolution for the selected observing location
- observing-condition calculations refresh automatically and recalculate when the active location changes
- Live finder background colour now follows the solar state: daylight, civil twilight, nautical twilight, astronomical twilight and dark
- sunlit satellites can now appear in the Live finder during civil twilight after sunset instead of waiting for the stricter dark-sky threshold
- existing `Potential` meaning is retained: sunlit satellite + observer sky at or below the configured dark-sky threshold
- no paid sunset, timezone or observing-conditions API has been introduced

## Sunset, twilight and darkness

NightAzimuth now calculates observing conditions locally from the selected observer position and current time using Skyfield and the JPL DE421 ephemeris.

The Live view shows:

- **Sunset**
- **Civil twilight ends**
- **Nautical twilight ends**
- **Complete darkness** (astronomical darkness)
- the current Sun altitude
- the current sky state
- the local time zone for the selected observing location

The displayed event times are converted to the local time zone for the active observing location. Time-zone lookup is performed locally using the bundled `timezonefinder` database.

Changing, editing or selecting a different observing location recalculates these values for the new observer position.

## Twilight satellite tracking

Previous beta behaviour required the existing `Potential` condition before a satellite could enter normal Live finder selection. That meant a satellite could be above the horizon and illuminated during twilight but remain absent from the finder until the sky reached the configured dark-sky threshold.

This release keeps the stricter `Potential` indicator unchanged, but additionally allows a **sunlit satellite during civil twilight after sunset** to be considered by the Live finder.

This better reflects real observing conditions because satellites at orbital altitude can remain illuminated after the observer is already in shadow.

A twilight candidate is still not a guarantee of naked-eye visibility. Satellite brightness, reflective attitude, haze, cloud and other factors are not yet fully modelled.

## Solar-state Live background

The Live finder background now changes with the current solar state for the selected location. The colours are deliberately muted so the green HUD, satellite markers and celestial labels remain readable while still providing an immediate visual indication of whether the observer is in daylight, twilight or darkness.

## Data and privacy

No new paid service is required.

- sunset and twilight calculations are local
- Sun position is calculated locally from Skyfield / JPL DE421
- time-zone lookup is local through `timezonefinder`
- saved observing locations remain in `%APPDATA%\NightAzimuth\locations.json`
- the application release contains no saved user location, profile name, terrain cache or runtime configuration
- terrain behaviour and privacy remain unchanged from the previous beta

## Existing features retained

This release retains the v0.4.0-beta.1 observing foundation:

- CelesTrak VISUAL + ACTIVE live catalogue coverage
- apparent-angular-speed fast-mover ranking
- smooth 20 fps marker interpolation from one-second orbital samples
- three-minute projected tracks
- full 0–90° elevation range
- mouse panning and zoom
- terrain-horizon masking
- Vega reference
- named bright stars
- major planets
- selected galaxy references
- 24-hour VISUAL-group pass planning

## Visibility limitation

`Potential` remains an astronomical suitability indicator, not a naked-eye visibility guarantee.

NightAzimuth does not yet fully model:

- satellite apparent magnitude
- reflective orientation or flares
- cloud and haze
- Moon brightness
- buildings, trees and other non-terrain obstructions
- camera sensitivity

## Release status

This remains a **beta pre-release**. The core observing workflow is established, but continued field testing and visibility-model refinement are still required before a 1.0 release.

**Created by Logic Lurker © 2026**
