# Stage 11 — Celestial object labelling

**Created by Logic Lurker © 2026**

Stage 11 extends the Stage 10 Live view with major-planet identification and a less cluttered star-labelling model.

## Implemented

- Mercury, Venus, Mars, Jupiter, Saturn, Uranus, and Neptune are calculated for the selected observer and current time using the existing Skyfield DE421 ephemeris.
- Major planets are permanently labelled whenever they are physically inside the current Live view.
- Planet rendering is independent of the optional Stars checkbox.
- Named bright stars are labelled automatically.
- The automatic star-name threshold becomes progressively fainter as the Live view is zoomed in.
- At a 90° horizontal FOV, named stars down to approximately magnitude 3 are shown automatically as useful visual references.
- Fainter/smaller stars remain marker-only until selected.
- Clicking near a faint star reveals its proper name when available, otherwise its Hipparcos identifier, together with apparent magnitude.
- Clicking the selected star again hides the temporary label.
- Faint-star selection uses coordinate-based proximity detection rather than an invisible Tkinter canvas hit target.
- Celestial selections are cleared when the observer profile changes so a selection cannot leak into a different location's sky.
- Existing satellite markers and predicted tracks remain visually dominant.
- Facing direction, horizontal FOV, 0–60° practical elevation, and all zoom controls continue to apply to the celestial reference layer.

## Release-readiness work

For v0.2.0-alpha.1 the project also gained a Windows GitHub Actions CI workflow that installs the package, performs correctness-focused Ruff checks, and runs the automated Pytest suite on pull requests and `main`.

The public project description was corrected so it no longer claims weather/cloud functionality that is not yet implemented.

## Unchanged

The all-sky Sky map remains unchanged by Stage 11.

The star and planet layers are observing references. Their presence on the display does not guarantee naked-eye visibility under local weather, haze, moonlight, or light-pollution conditions.
