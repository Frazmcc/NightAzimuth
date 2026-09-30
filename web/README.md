# NightAzimuth hosted web frontend

This directory contains the **primary production NightAzimuth client** deployed at:

**https://nightazimuth.co.uk**

The browser talks to the public API at:

**https://api.nightazimuth.co.uk**

## Purpose

The frontend is intentionally static and provider-independent. It contains no upstream API credentials and no direct ADS-B/orbital/weather provider logic.

Hosted data is obtained through the NightAzimuth API, which performs provider access, observer-specific calculations, caching, resilience and request sharing.

## Current startup model

The browser does not launch all heavy requests at once.

Current startup behaviour is deliberately progressive:

- lightweight data requests start immediately
- aircraft acquisition uses the current configured radar distance rather than the older 200/400 km dual-startup pattern
- sky work is slightly spread between clients
- satellite loading follows sky instead of competing with it immediately

This scheduling is part of the production scalability design and should be preserved unless a replacement is measured to be better.

## Main hosted data

The frontend consumes versioned `/api/v1` endpoints for data such as:

- aircraft
- airports
- weather
- observing guidance
- sky/stars/planets/galaxies
- satellites

Observer-relative positions remain observer-relative. The frontend must not invent geographic positions for data the API does not provide.

## Domain layout

- `nightazimuth.co.uk` — static browser frontend over HTTPS
- `api.nightazimuth.co.uk` — hosted FastAPI service over HTTPS

`config.js` contains the public API origin only. Never add secrets to `web/`; everything deployed here is public.

## Deployment

The repository Pages workflow publishes the static frontend. `web/CNAME` contains the production custom domain.

The API is deployed separately through `render.yaml`.

## Development rules

- keep provider credentials out of the browser
- keep observer-specific source requests behind the API where sharing/resilience matters
- preserve layer toggles, panning, zoom and object-selection usability
- do not reintroduce below-horizon blank sky
- do not reintroduce the old simultaneous heavy-startup burst without measured evidence
- keep `config.js` limited to non-secret public configuration

For current architecture and capacity information see:

- `../docs/CURRENT_ARCHITECTURE.md`
- `../docs/PROJECT_STATUS.md`
