# NightAzimuth hosted web frontend

Stage 21.7 is a static, provider-independent browser client for the NightAzimuth HTTP API.

Set `apiBaseUrl` in `config.js` to the deployed API origin. Do not put provider credentials or secrets in this file: static-site contents are public.

It consumes `/api/v1/geojson/aircraft`, `/api/v1/weather`, and `/api/v1/observing`. It contains no upstream-provider logic. A static host such as GitHub Pages can serve this directory after the API host and CORS policy are selected in later Stage 21 increments.
