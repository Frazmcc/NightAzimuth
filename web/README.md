# NightAzimuth hosted web frontend

Stage 21.7 is a static, provider-independent browser client for the NightAzimuth HTTP API.

Set `apiBaseUrl` in `config.js` to the deployed API origin. Do not put provider credentials or secrets in this file: static-site contents are public.

It consumes `/api/v1/geojson/aircraft`, `/api/v1/weather`, and `/api/v1/observing`. It contains no upstream-provider logic. A static host such as GitHub Pages can serve this directory after the API host and CORS policy are selected in later Stage 21 increments.

## Stage 21.9 domain layout

The intended public domain layout is:

- `nightazimuth.bismo.me` — static browser frontend, served with HTTPS.
- `api.nightazimuth.bismo.me` — Render-hosted FastAPI service, served with HTTPS.

The browser configuration points only to the public API hostname. DNS must not be changed until the corresponding hosted service has been created and its platform hostname is known.

For the API, add `api.nightazimuth.bismo.me` as a custom domain on the Render web service first, then create the DNS record Render requests and verify it in Render. Render automatically provisions and renews TLS and redirects HTTP to HTTPS.

For a GitHub Pages frontend, configure `nightazimuth.bismo.me` as the repository Pages custom domain before creating its DNS CNAME. The CNAME should point directly to the account's GitHub Pages hostname, not to a repository path. Enforce HTTPS after GitHub confirms the certificate is available.

Do not use wildcard DNS records. Keep the frontend and API records explicit so ownership and routing remain unambiguous.
