# Security Policy

NightAzimuth is currently an alpha-stage project created by Logic Lurker © 2026.

## Supported versions

Security fixes are currently considered only for the latest published alpha release and the current `main` branch.

## Reporting a vulnerability

Please do **not** post suspected security vulnerabilities, secrets, credentials, tokens, private observing coordinates, or other sensitive information in a public GitHub issue.

When GitHub private vulnerability reporting is enabled for this repository, use the repository **Security** tab to report vulnerabilities privately.

For ordinary bugs that do not involve sensitive information, use a normal GitHub issue and include the NightAzimuth version, Windows version, steps to reproduce, and any non-sensitive error message.

## Secrets and local data

NightAzimuth must not store API keys, passwords, tokens, personal runtime configuration, build output, saved user locations, or cached runtime data in source control.

A fresh release must not contain a real user's saved location, profile name, terrain cache, orbital cache, generated runtime files, or any other personal runtime data. Saved locations are created only after a user enters them and are stored locally under `%APPDATA%\NightAzimuth\locations.json`.

Terrain requests made after the user enters a location use map-tile identifiers derived from the selected area. The saved profile file and profile name are not uploaded, but the terrain provider can infer the geographic area represented by the requested tiles.

The Windows release build starts from a clean `dist` directory and validates an explicit release-output allowlist before completing.
