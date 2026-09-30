# Current NightAzimuth Architecture

This document describes the **current hosted NightAzimuth architecture**. Historical stage documents are kept under `docs/archive/` and should not be treated as current operating instructions.

## Production endpoints

- Web frontend: `https://nightazimuth.co.uk`
- Public API: `https://api.nightazimuth.co.uk`

## High-level design

```text
Browser
  |
  v
Static web frontend
  |
  v
FastAPI service
  |
  +-- astronomy / sky
  +-- satellites
  +-- aircraft / ADS-B
  +-- airports
  +-- weather
  +-- observing guidance
```

The frontend is static and contains no provider credentials. The browser talks only to the NightAzimuth API for hosted data.

## Web frontend

The production browser client lives in `web/` and is deployed separately from the Python API.

Important client behaviour includes:

- progressive startup rather than launching every heavy request simultaneously
- one observer-specific aircraft acquisition for the current configured radar distance
- sky and satellite loading scheduled in sequence to reduce CPU spikes
- browser-side interaction, panning, zoom, selection and layer control

## Hosted API

The API is implemented in `src/nightazimuth/` using FastAPI.

The current public contract is read-only. CORS is restricted to the NightAzimuth web origin for browser use. The API does not expose credentials, uploads or user account state.

## Astronomy admission and burst sharing

Sky and satellite calculations can be expensive on the free API service.

To prevent many simultaneous users from exhausting the process:

- heavy astronomy requests use bounded admission control
- identical near-simultaneous sky results can be reused from a short burst cache
- identical near-simultaneous satellite results can be reused from a short burst cache
- burst caches are process-local, bounded and intentionally very short-lived

The purpose is to collapse a startup burst, not to serve long-lived stale sky positions.

## Aircraft architecture

Browsers do not independently query ADS-B providers.

NightAzimuth acts as the aircraft data broker:

1. an active geographic region requests a wider raw aircraft snapshot
2. that snapshot is cached briefly
3. nearby users reuse the same snapshot
4. the API performs each user's exact radius/elevation filtering from the shared data
5. provider requests are paced and bounded
6. a secondary provider may be used after primary failure
7. a recent last-known-good snapshot can bridge a short upstream interruption

This architecture dramatically reduces provider request multiplication when many users are in the same area.

## Provider resilience

Provider integrations are treated as replaceable data sources rather than being embedded into UI logic.

Aircraft currently uses ADSB.lol as the primary source with adsb.fi as a failover path. Request pacing, bounded retry and recent-snapshot fallback protect the user-facing API from transient failures.

## Shared/static data

Where possible, NightAzimuth avoids repeated network or parsing work for data that changes slowly or is deployment-local.

Examples include:

- preloaded airport data
- prepared satellite reference/catalogue data
- shared Skyfield resources
- weather snapshot sharing
- process-local bounded caches

## Deployment

The API deployment is defined in `render.yaml`.

Production startup preloads static resources before traffic is accepted. The service currently runs within the free hosting design target.

The frontend is deployed from `web/` through the repository's Pages workflow and custom domain configuration.

## Validation

Hosted changes are protected by automated validation including:

- Python compile
- Ruff
- JavaScript syntax validation
- DOM contract smoke tests
- pytest
- CodeQL
- exact-commit production API smoke checks

The Task 6 capacity programme validated a production-style 50-user Live Sky gate with 300/300 successful requests, zero server errors and HTTP 200 health after the run.

## Cost constraint

The current design target is **£0 operating cost**.

No paid Render scaling, paid Redis/KV or similar service is a required architectural dependency. Any future paid infrastructure should be an explicit product decision driven by measured need.

## Legacy desktop architecture

Tkinter/PyInstaller desktop code remains in the repository for history and experimentation. It is not the primary production architecture. See `LEGACY_DESKTOP.md`.
