# Stage 11 — Celestial Object Labelling

Status: Ready for user testing

Created by Logic Lurker © 2026

## Scope

Stage 11 improves the Live view as an observing aid by identifying major planets and reducing unnecessary star-label clutter.

Implemented:

- Mercury, Venus, Mars, Jupiter, Saturn, Uranus and Neptune calculated for the selected observer and current time
- major planets shown only when above the observer's horizon and inside the current Live view
- major planet names always displayed beside their marker
- very bright named stars continue to be labelled automatically
- fainter stars are displayed without permanent names
- clicking a fainter star reveals its proper name when available, otherwise its Hipparcos identifier
- a selected star also shows its apparent magnitude
- clicking the same star again hides the temporary label
- celestial labels follow the existing facing direction, FOV and zoom controls
- satellites and projected satellite tracks remain visually dominant
- the all-sky Sky map remains unchanged

## Display intent

The Live view is intended to resemble a practical observing reference rather than a densely labelled planetarium chart. Major planets and the brightest reference stars are immediately identifiable, while the larger background star field remains available without covering the screen in text.

## Deferred

Stage 11 does not yet add the Moon, dwarf planets, asteroids, comets, deep-sky objects, planet brightness/phase modelling, weather/cloud analysis or camera overlay.
