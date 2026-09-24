# NightAzimuth v1.1.0-rc1

**Created by Logic Lurker © 2026**

NightAzimuth 1.1.0-rc1 is a release candidate for the Stage 19 aircraft foundation and Stage 20 visual-experience work. It is intended for real-world Windows testing before promotion to the final v1.1.0 release.

## Release-candidate focus

This build turns Live Sky into a low-noise observer-centred tracking surface while adding aircraft/ADS-B awareness, smoother realtime satellite tracking, selected-satellite intelligence and location-derived airport references.

The release candidate should be tested for stability, layout, refresh continuity and the accuracy of displayed data before v1.1.0 is marked stable.

## Live Sky redesign

- responsive single-page layout that starts maximised and respects Windows/Tk DPI scaling
- Live Sky remains the dominant full-width surface
- Live Finder, Aircraft Contacts, ISS / Passes and Satellite Info are collapsible drawers below Live Sky
- F11 fullscreen support
- large green digital clock using the active observing location's local timezone and UTC offset
- last-good-scene refresh behaviour prevents normal satellite refreshes from intentionally blanking the sky
- weather/cloud controls removed from Live Sky while Weather Map and Forecast remain dedicated tabs

## Human-eye / perceptual sky

- observer-centred spherical/stereographic projection instead of a flat azimuth/elevation plot
- curved sky guides and wide-field peripheral compression
- terrain skyline projected through the same geometry
- subtle horizon airlight and foreground depth cues
- daylight/twilight/night-dependent star limits
- atmospheric extinction toward the horizon
- subtle low-horizon scintillation
- reduced celestial colour saturation during dark adaptation
- Moon position from the Skyfield ephemeris with lightweight glare treatment
- visually distinct aircraft, satellites and natural celestial objects

## Realtime satellite tracking

- all valid in-view satellites can be displayed day or night
- orbital prediction points sampled every second over a rolling short horizon
- marker interpolation at approximately 20 fps for smooth motion
- future tracks repeatedly rebased from the interpolated current position
- selected satellite and ISS receive prediction priority
- up to 240 in-view satellites can receive prediction data while only a small number of useful tracks are drawn automatically
- selected satellite can be clicked again to deselect it and restore normal automatic priorities

## Satellite Info

Selecting a satellite opens the Satellite Info drawer. Where verified information exists, NightAzimuth can show:

- NORAD catalogue ID
- COSPAR / international designator
- owner/country/source description
- object type and operational status
- launch date and site
- current azimuth, elevation and range
- sunlight state, phase angle and supported brightness estimate
- orbital period, inclination, apogee, perigee and radar cross-section
- mission/purpose and public technical notes
- public spacecraft image when a sufficiently confident Wikimedia match exists

CelesTrak SATCAT remains the primary catalogue/orbit metadata source. Missing enrichment is shown as unavailable rather than fabricated.

## ISS and pass awareness

- ISS (NORAD 25544) is treated as a first-class tracked object
- dedicated ISS / Passes drawer
- near-term visual passes within approximately one hour are prioritised for attention
- ISS is retained in the realtime prediction priority set when orbital data is available

## Aircraft / ADS-B

- free ADSB.lol internet source plus the existing provider-independent/local-source architecture
- smooth aircraft interpolation and short forward projection
- transient failed or zero-contact refreshes retain the last populated aircraft scene rather than blanking the layer
- aircraft type-specific vector icons for supported fixed-wing, helicopter/rotorcraft, glider, UAV and military classes
- emergency/special-operation squawks are prioritised ahead of normal traffic
- recognised squawk codes retain the numeric code plus a short plain-English description
- Aircraft Contacts is a fixed-size priority board rather than a long scroll-heavy list

### Selected-aircraft detail

Selected aircraft now show a persistent journey-first detail block directly inside **Aircraft Contacts**, immediately below the priority board. Selecting an aircraft opens Aircraft Contacts automatically; Live Finder is not used for aircraft details.

Where data exists the panel can show:

- callsign / registration
- aircraft manufacturer/model and a defensible type-level capacity hint
- operator and inferred specialist role such as Air Ambulance/HEMS, Police or Coastguard/Search & Rescue
- squawk code and description
- departure airport
- arrival airport
- departure time when a real source supplies it
- live ETA estimate when destination coordinates, position and groundspeed support one
- live altitude, speed, track, vertical rate, range and data freshness

Departure/schedule times that are not available from the free route source are explicitly marked unavailable rather than guessed.

## Dynamic airport horizon references

- airport references are calculated entirely from the active user-selected observing location
- no user location, city, country, airport or coordinate list is hard-coded into NightAzimuth
- global OurAirports public data is used to identify significant airports
- large airports are preferred, followed by scheduled regional airports where major airports are sparse
- only a small number of relevant airports are retained
- labels are filtered by current bearing/FOV and drawn near the terrestrial horizon
- airport loading runs off the UI thread

## Forecast and weather

- Weather Map remains available
- Forecast remains available, including the existing short- and multi-day planning views
- Live Sky no longer carries the old weather/cloud panel or cloud controls

## Privacy and cost

- saved observer profiles remain local to the PC
- no preset real-world user location is included
- location-derived providers can infer the geographic area represented by the specific request they receive
- NightAzimuth does not upload the complete saved profile file or profile name
- no paid API key is required for normal intended use

## Accuracy boundaries

A satellite being above the horizon, sunlit, favourably placed and actually naked-eye visible are different claims. NightAzimuth keeps these concepts separate where possible.

Satellite brightness can vary with attitude, geometry and flares/glints. Unsupported spacecraft remain unknown rather than receiving fabricated values.

Aircraft route and timing data can be incomplete. Live ETA is explicitly an estimate and does not model vectors, holds, descent profile or taxi time. Departure time is not fabricated when the route source does not supply it.

Airport horizon labels are directional geographic references, not a claim that a runway at that distance is optically visible to the unaided eye.

## Installation

The GitHub release workflow will create exactly three downloadable assets when the release tag is approved and pushed:

- `NightAzimuth-v1.1.0-rc1-Windows-x64.exe`
- `NightAzimuth-v1.1.0-rc1-User-Guide.md`
- `NightAzimuth-v1.1.0-rc1-SHA256.txt`

Windows may show a reputation warning because the application is not code-signed.

Existing data under `%APPDATA%\NightAzimuth` is retained when upgrading.

## RC smoke-test checklist

Before promotion to v1.1.0, test:

- launch/maximise/F11
- location switching
- Live Sky continuity during refreshes
- ADS-B continuity
- aircraft selection and persistent rich details in Aircraft Contacts
- emergency/special squawk ordering
- satellite selection/deselection
- smooth fast-LEO satellite movement and tracks
- Satellite Info data/image fallback behaviour
- ISS / Passes drawer
- dynamic airport horizon labels while panning through different bearings
- Forecast and Weather Map tabs
- resizing and Windows DPI scaling

If these remain stable during normal use, v1.1.0-rc1 can be promoted to the final v1.1.0 release.
