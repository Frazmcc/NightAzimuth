# NightAzimuth

**Created by Logic Lurker © 2026**

NightAzimuth is a live, observer-centred sky application for identifying satellites, aircraft, stars, planets, galaxies, airports and observing conditions from a chosen location.

## Use NightAzimuth

**Web app:** https://nightazimuth.co.uk  
**Public API:** https://api.nightazimuth.co.uk

The hosted web application is the primary and recommended NightAzimuth experience. It receives new features, performance work and production validation first.

> The older Windows executable is retained only as a historical/legacy build. It is not feature-equivalent to the current web application and is no longer the recommended way to use NightAzimuth. See [`docs/LEGACY_DESKTOP.md`](docs/LEGACY_DESKTOP.md).

## Current status

NightAzimuth is actively developed and deployed as a static browser frontend backed by a versioned FastAPI service.

The production architecture has completed the Task 5 performance programme and Task 6 free-tier scalability programme. The current production-style capacity gate has validated **50 simultaneous Live Sky users** with **300/300 successful API requests, zero server errors and production health remaining HTTP 200** after the test.

The project remains intentionally cost-conscious. The current architecture is designed to operate at **£0 infrastructure cost** using free hosting/provider tiers where practical. No paid scaling service or Redis dependency is required by the current design.

## What the web app provides

- observer latitude/longitude settings
- wide-field Live Sky with configurable field of view
- click-and-drag sky navigation and zoom
- horizon-limited view with no below-horizon sky area
- independent layer controls for stars, constellations, planets, satellites, aircraft and airports
- selectable stars, planets, satellites and aircraft with object information
- live satellite positions and short projected tracks
- aircraft contacts with callsign/type/telemetry/squawk information where available
- special-aircraft awareness for military, air ambulance, police and coastguard/search-and-rescue signals where supported by source data
- airport horizon references derived from the observer location
- point weather and observing guidance
- responsive desktop/mobile browser layout

NightAzimuth deliberately separates geometry, source data and inference. Missing route, schedule, brightness or classification information is shown as unavailable rather than invented.

## Architecture

```text
Browser
  |
  | HTTPS
  v
nightazimuth.co.uk
  |
  v
api.nightazimuth.co.uk
  |
  +-- sky / stars / planets / galaxies
  +-- satellites / orbital data
  +-- aircraft / ADS-B
  +-- airports
  +-- weather
  +-- observing guidance
```

Important scaling behaviour includes:

- progressive browser startup rather than launching all heavy astronomy work at once
- bounded server-side astronomy admission control
- short exact-request burst sharing for near-simultaneous sky/satellite requests
- regional shared aircraft snapshots so nearby users do not independently hit ADS-B providers
- request pacing, bounded retry and provider failover for aircraft data
- last-known-good aircraft snapshots within the accepted data-age window
- bounded process-local caches for weather, airports and other reusable data
- production preloading of static astronomy/airport resources

See [`docs/CURRENT_ARCHITECTURE.md`](docs/CURRENT_ARCHITECTURE.md) and [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md).

## Repository layout

- `web/` — production browser frontend deployed to `nightazimuth.co.uk`
- `src/nightazimuth/` — Python/FastAPI backend and astronomy/data logic
- `tests/` — automated regression and API tests
- `docs/` — current user, architecture, status and security-related documentation
- `docs/archive/` — historical implementation-stage and release documentation
- `.github/workflows/` — CI, CodeQL, Pages and production smoke validation
- `render.yaml` — Render API deployment definition
- `build_windows.ps1` — legacy desktop build helper; not the recommended product path

## Documentation

Start here:

- [`docs/NightAzimuth_User_Guide.md`](docs/NightAzimuth_User_Guide.md) — current web user guide
- [`docs/CURRENT_ARCHITECTURE.md`](docs/CURRENT_ARCHITECTURE.md) — current hosted architecture and data flow
- [`docs/PROJECT_STATUS.md`](docs/PROJECT_STATUS.md) — completed performance/scalability work and present project state
- [`docs/LEGACY_DESKTOP.md`](docs/LEGACY_DESKTOP.md) — status of the old Windows executable
- [`SECURITY.md`](SECURITY.md) — security/privacy policy
- [`CREDITS.md`](CREDITS.md) — third-party software/data attribution

Historical stage documents and old desktop release notes are kept under `docs/archive/` for project history and should not be read as current operating instructions.

## Development and quality gates

Changes should pass the repository quality gates before reaching `main`:

- Python compile checks
- Ruff correctness checks
- hosted JavaScript syntax validation
- hosted DOM contract smoke tests
- pytest regression suite
- Windows legacy packaging check where still retained by CI
- CodeQL analysis
- exact-commit production API smoke validation for hosted API changes

Production load testing is performed cautiously and only when a measured capacity question justifies it.

## Data and privacy principles

- No real user location is hard-coded into the application.
- Browser/API requests use the observer coordinates required to calculate the requested view.
- Do not commit API keys, credentials, private coordinates or personal runtime data.
- External data providers may infer the geographic area represented by a location-dependent request.
- NightAzimuth does not need user accounts for the current read-only public API.

## Accuracy boundaries

NightAzimuth is an identification and observing aid, not an authoritative aviation, navigation or safety service.

A satellite being above the horizon, sunlit and actually visible to the naked eye are different claims. Aircraft route and timing information may be incomplete or delayed. Weather and visibility remain subject to local conditions that a remote data source cannot fully represent.

## Historical desktop application

The repository still contains Tkinter/PyInstaller desktop code and `build_windows.ps1` because they are part of NightAzimuth's development history and may still be useful for experimentation.

New public releases should **not** automatically publish a Windows EXE unless the desktop product is deliberately brought back to feature parity with the web application. Existing EXE releases remain available as historical artifacts.

## Licence

No project licence has been selected yet.
