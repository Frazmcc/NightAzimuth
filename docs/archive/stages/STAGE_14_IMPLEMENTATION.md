# Stage 14 — Twilight Observing State and Local Countdowns

Status: **Approved and merged**

## Goal

Stage 14 extends the live observing view beyond a simple dark/not-dark distinction. It makes the current solar state visible, shows local transition times, and allows useful sunlit-satellite tracking during twilight without weakening the stricter Potential definition.

## Implemented result

- calculates sunset, civil twilight, nautical twilight and complete astronomical darkness for the selected observer location
- resolves the location's time zone locally
- displays current Sun altitude and the active daylight/twilight/dark-sky state
- shows countdowns to the next relevant solar transitions
- changes the Live-view background across daylight, twilight and dark-sky states
- includes sunlit twilight satellite candidates after sunset
- keeps Potential reserved for a sunlit satellite under the configured dark-sky threshold
- refreshes the solar-state display as time and selected location change

## Accuracy and privacy

Solar events are calculated locally from the user-entered observer location. No sunset or time-zone web API is required. A plotted twilight candidate is not guaranteed to be bright enough to see; weather, local obstructions and spacecraft brightness remain separate evidence.

No saved observer profile or private test location is packaged with the application.

## Stage gate

Stage 14 passed its automated checks, Windows build and local visual review, and was explicitly accepted before merge.
