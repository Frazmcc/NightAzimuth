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

### 21.10 Security, tests and documentation — COMPLETE

CORS, authentication requirements, rate-control strategy, OpenAPI exposure, bounded public input, defensive response headers, sanitized provider failures, filesystem-path validation, sensitive CLI output handling, and regression/security validation are now defined and implemented. CI and CodeQL are required merge gates.

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

## Stage 21.8 hosting assessment

The current API is a stateless FastAPI/ASGI service on Python 3.11+ with outbound HTTPS provider calls and a small local cache. It does not currently require a database, worker process, WebSocket or SSE connection. The static frontend performs bounded REST snapshot requests.

For the first hosted validation, Render Free is selected as the deployment target. Its free web service provides 512 MB RAM, supports Python web services, custom domains and managed TLS, and supplies 750 free instance-hours per workspace per month. The main trade-off is idle spin-down after 15 minutes, with a cold start that can take about a minute. The filesystem is ephemeral, so NightAzimuth must continue to treat its API cache as disposable.

Koyeb remains a viable zero-cost fallback: its free web instance also provides 512 MB RAM and scales to zero after one hour, but the free instance is explicitly positioned for testing/hobby use. Railway's current free plan provides only $1/month of resource credit after its trial, so it is less predictable for the project's strict no-cost requirement.

The repository includes a Render Blueprint in `render.yaml`. It installs the API optional dependency set, starts Uvicorn on the platform-provided port, and uses `/api/v1/health` for health checks. No DNS, CORS or production-security policy is changed in this increment; those remain gated by Stages 21.9 and 21.10.


## Stage 21.10 security and public API policy

The hosted API is a public, read-only snapshot service. It does not accept credentials, write operations, uploads, or user content. Browser CORS is restricted to `https://nightazimuth.co.uk`; CORS is not treated as authentication. Endpoint parameters remain bounded by FastAPI validation and the application rejects query strings larger than 2048 bytes before endpoint parsing.

Authentication is intentionally not required for the current read-only public data contract. If a later stage adds private data, write operations, account state, or privileged provider access, authentication becomes mandatory before that capability is exposed.

Application-level request quotas are deferred until production traffic can be measured. Hosting-edge controls should be preferred over process-local counters because free hosting may restart or scale the process. Provider-facing code must continue to cache and avoid automatic retry storms. OpenAPI is exposed at `/api/openapi.json` with interactive documentation at `/api/docs` for the versioned `/api/v1` contract.

Security validation requires CI and CodeQL to pass. Precise observer coordinates must not be unnecessarily written to CLI logs/output, and provider-controlled identifiers must be validated before they can influence filesystem paths.


### Stage 21.10 completion record

Stage 21.10 is complete at repository level. The public API is GET-only, browser CORS is origin-restricted, oversized query strings are rejected, defensive browser response headers are applied, provider diagnostics are not returned through the satellite failure contract, and exact observer coordinates are no longer printed by the CLI. CelesTrak group identifiers are allowlisted before they can influence cache filenames. CI and CodeQL pass on the security changes.

The remaining rate-control decision is intentionally operational rather than an unfinished application feature: process-local counters are unsuitable for an ephemeral/free hosted service, so edge/platform controls will be evaluated from measured traffic during Stage 21.11 production validation.

Stage 21.11 is therefore the active hosted stage. It requires deployment and real-environment validation of health, endpoint behaviour, stale/partial provider handling, browser access, DNS/HTTPS, cold-start/resource behaviour, and the no-cost operating constraint.
