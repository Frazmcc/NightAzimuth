# Stage 10 — Real Star-Field Background and Constellation Reference Layer

Status: Ready for user testing

Created by Logic Lurker © 2026

## Scope

Stage 10 adds a real astronomical reference layer behind the practical Live view so the user can match satellite positions against the stars actually present in that part of the sky.

Implemented:

- real star positions from the Hipparcos catalogue
- topocentric star positions calculated for the selected observer location and current UTC time
- apparent magnitude used to vary star marker size
- named bright stars shown selectively to avoid clutter
- modern Stellarium constellation line definitions
- Stars On/Off control
- Constellations On/Off control
- constellation lines and stars remain behind satellite markers and predicted tracks
- star layer follows the existing facing direction, horizontal FOV, 0–60° elevation view, and zoom controls
- star calculations run in a background thread
- star field refreshes independently at approximately one-minute intervals
- star-layer failure does not stop satellite tracking
- first use downloads and caches the Hipparcos catalogue and Stellarium modern sky-culture data
- existing all-sky Sky map remains unchanged

## Data sources

NightAzimuth uses Skyfield's Hipparcos loader for stellar coordinates, proper motion, and apparent magnitude data. Constellation line definitions and proper star names are sourced from Stellarium's modern sky-culture JSON data.

The astronomical data files are cached in NightAzimuth's normal runtime cache directory under `%APPDATA%\\NightAzimuth\\cache`.

## Display behaviour

The Live view defaults to:

- Stars: On
- Constellations: Off
- limiting stellar magnitude: 5.5

At wide fields of view, only the brightest named stars receive labels. When zoomed to 45° horizontal FOV or narrower, additional named stars are labelled to make visual matching easier.

## Purpose

The Live view should now answer three practical observing questions:

1. Where is the satellite now?
2. Where is it moving over the next few minutes?
3. Which stars can I use as reference points to find it in the real sky?

## Deferred

Stage 10 does not add weather/cloud analysis, Moon brightness effects, local horizon obstructions, camera overlays, aircraft matching, meteor detection, or unidentified-object classification. These remain later-stage work.
