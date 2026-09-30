# Security Policy

NightAzimuth is an actively developed hosted web application created by Logic Lurker © 2026.

## Supported code

Security fixes are considered for the current `main` branch and the deployed hosted application.

Historical Windows executable releases are legacy artifacts and are not the primary supported product.

## Reporting a vulnerability

Do **not** post suspected vulnerabilities, credentials, tokens, private observing coordinates or other sensitive information in a public GitHub issue.

When GitHub private vulnerability reporting is enabled, use the repository **Security** tab.

For ordinary non-sensitive bugs, a normal GitHub issue is appropriate. Include the affected web feature/API endpoint, approximate time, reproduction steps and any non-sensitive error text. Do not include a private home/observer location if a public test location can reproduce the issue.

## Hosted architecture

The public browser frontend is static and must never contain provider credentials or secrets.

The hosted API is currently read-only and does not provide user accounts, uploads or privileged write operations. Browser CORS is restricted to the production NightAzimuth origin, but CORS is not treated as authentication.

If future work adds account state, private data, write operations or privileged provider access, that capability must introduce suitable authentication/authorisation before production exposure.

## Secrets and repository hygiene

Do not commit:

- API keys
- passwords/tokens
- private user coordinates
- personal runtime configuration
- generated caches containing personal context
- local environment files containing secrets
- build output unless deliberately published as an approved artifact

Public configuration such as the NightAzimuth API origin may be stored in the static frontend because it is not a secret.

## Location privacy

Observer coordinates are necessarily used for location-dependent calculations. The NightAzimuth API and upstream providers may therefore infer the geographic area represented by a request.

CI/load tests use fixed public test locations rather than real user coordinates. Logs should avoid recording precise user locations unless technically necessary and explicitly justified.

## Provider and fallback data

Time-sensitive aircraft, satellite and weather data can be delayed, incomplete or temporarily unavailable. Fallback/cached data must remain bounded by the application's accepted data-age rules and should be labelled through response metadata/telemetry where relevant.

## Legacy desktop build

The old Windows/Tkinter build remains in source control for historical reference. It should not be assumed to receive the same security hardening or hosted fixes as the current web application unless desktop support is explicitly restored.
