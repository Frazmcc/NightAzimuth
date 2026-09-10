# Security Policy

NightAzimuth is currently an alpha-stage project created by Logic Lurker © 2026.

## Supported versions

Security fixes are currently considered only for the latest published alpha release and the current `main` branch.

## Reporting a vulnerability

Please do **not** post suspected security vulnerabilities, secrets, credentials, tokens, or other sensitive information in a public GitHub issue.

When GitHub private vulnerability reporting is enabled for this repository, use the repository **Security** tab to report vulnerabilities privately.

For ordinary bugs that do not involve sensitive information, use a normal GitHub issue and include the NightAzimuth version, Windows version, steps to reproduce, and any non-sensitive error message.

## Secrets and local data

NightAzimuth must not store API keys, passwords, tokens, personal runtime configuration, build output, or cached runtime data in source control. Local user settings and caches are kept outside the repository or covered by `.gitignore`.
