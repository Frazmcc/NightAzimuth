# NightAzimuth Project Status

Last consolidated after completion of the hosted performance and scalability programme.

## Primary product

The hosted web application at `https://nightazimuth.co.uk` is the primary NightAzimuth product.

The Windows executable is legacy/historical and is not considered feature-equivalent to the hosted application.

## Task 5 — performance optimisation

**Status: COMPLETE / FROZEN**

Task 5 improved production startup/API performance and observability, including work such as:

- direct satellite serialization
- astronomy resource reuse/prewarm
- aircraft provider timing instrumentation
- aircraft snapshot sharing
- shared HTTP connection pooling
- transient aircraft fallback
- shared weather snapshots
- preloaded airport catalogue
- static/runtime prewarm

Task 5 is intentionally frozen. It should not be reopened without a new measured bottleneck.

## Task 6 — free-tier scalability

**Status: COMPLETE / FROZEN**

Task 6 started after early production testing showed that a small number of simultaneous startup users could exhaust the free API process or multiply aircraft provider requests.

The completed architecture now includes:

- progressive browser startup
- global astronomy admission control
- short-lived exact-request sky/satellite burst sharing
- regional aircraft snapshots
- ADS-B provider pacing and bounded retries
- ADS-B provider failover
- last-known-good aircraft reuse within the accepted data-age window
- corrected production-style capacity harness

### Final accepted capacity gate

Production-style test:

- 50 simultaneous Live Sky users
- 300 API requests
- 300 successful
- 0 server errors
- overall p50 approximately 8.9 seconds
- overall p95 approximately 17.5 seconds
- overall p99 approximately 23.0 seconds
- production health remained HTTP 200 immediately afterward

This exceeds the original requirement to support at least 20 simultaneous active users while keeping the current £0 architecture.

A 100-user production stress test was deliberately not run simply to obtain a larger number. Further production load should be justified by a real capacity requirement or measured bottleneck.

## Repository state at Task 6 closure

At closure:

- CI was green
- pytest was green
- Ruff/compile/frontend syntax/DOM checks were green
- Windows legacy packaging check was green
- CodeQL was green
- exact-commit production smoke was green
- no Task 6 implementation PRs remained open

## Next work

Future work should be product-driven rather than continuing blind infrastructure optimisation.

Good triggers for new work include:

- a reproducible Live Sky bug
- a missing/incorrect data layer
- a measured latency regression
- provider changes
- user experience improvements
- a new capacity requirement beyond the validated gate

Do not introduce Redis, paid scaling or additional infrastructure simply because it is available.
