# Stage 21 — Hosted NightAzimuth & API Foundation

Stage 21 adds a hosted HTTP interface alongside the existing NightAzimuth desktop application. It does not replace the Tkinter desktop experience or change the validated Stage 19/20 tracking behaviour.

## Architecture contract

NightAzimuth core Python engines remain the authoritative implementation for satellite, aircraft, weather and observing calculations. They may be consumed by two interfaces:

1. The existing Windows/Tkinter desktop application.
2. A versioned HTTP API under `/api/v1`.

A future hosted web frontend and external client software can consume the HTTP API without scraping desktop widgets or duplicating provider logic.

## Stage 21 principles

- Preserve the existing desktop application as a first-class interface.
- Keep API code independent of Tkinter.
- Reuse the existing core models and provider abstractions rather than duplicating tracking logic.
- Keep external providers replaceable.
- Prefer no-cost hosting where practical, but do not select a hosting provider until runtime and refresh requirements are measured.
- Use explicit units, timestamps, freshness/staleness state and provider/source metadata in live-data responses.
- Start with REST snapshots. Add WebSocket or SSE only if measured client requirements justify them.
- Do not expose secrets, local user data, cache paths or desktop-specific state.
- Keep the API versioned from its first public endpoint.

## Planned increments

### 21.1 API foundation

- Add the minimum HTTP runtime dependency.
- Create an API application module that does not import Tkinter.
- Implement `GET /api/v1/health`.
- Add tests for the health and API-version contract.
- Validate through CI and CodeQL.

### 21.2 Satellite endpoints

Expose current satellite data through the existing CelesTrak/tracker/visibility engines with explicit timestamps, units and source metadata.

### 21.3 Aircraft endpoints

Expose the provider-independent Stage 19 aircraft model, including geographic filtering where appropriate.

### 21.4 Weather endpoints

Expose weather snapshots through the existing weather provider abstraction.

### 21.5 Observing-condition endpoints

Expose observing guidance derived from the existing observing-condition engine.

### 21.6 GeoJSON overlays

Define stable GeoJSON representations for map-capable clients where that is more appropriate than domain JSON.

### 21.7 Hosted web frontend

Build a separate static web frontend against the public API. This is independent of the Stage 20 desktop resource contract and does not embed a browser engine in the desktop application.

### 21.8 API hosting

Measure actual runtime, caching, refresh and connection requirements before selecting a provider. Prefer a zero-cost option when it satisfies the measured requirements.

### 21.9 DNS and HTTPS

Integrate the hosted frontend/API with the NightAzimuth domain layout only after hosting is validated.

### 21.10 Security, tests and documentation

Define CORS, authentication requirements, rate controls, OpenAPI documentation and deployment validation before public production use.

### 21.11 Production validation

Validate hosted behaviour, stale/partial data handling, provider failure modes and desktop/API consistency.

## Initial API contract

The first endpoint is deliberately provider-independent:

`GET /api/v1/health`

It exists only to prove that the NightAzimuth package can run safely behind an HTTP service without starting the desktop GUI or contacting an upstream data provider.

No live-data endpoint is part of the initial foundation commit.

## Deferred decisions

The following are intentionally not selected in 21.1:

- production API hosting provider;
- public API authentication model;
- WebSocket/SSE support;
- final public hostname;
- client-software integration details;
- licence for public distribution/API reuse.

These require evidence or an explicit project decision before implementation.
