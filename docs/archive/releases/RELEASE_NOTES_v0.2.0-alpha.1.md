# NightAzimuth v0.2.0-alpha.1

**Created by Logic Lurker © 2026**

This is the second public alpha release of NightAzimuth. It expands the forward-looking observing experience introduced in v0.1.0-alpha.1 with practical zooming, short satellite path prediction, a real stellar reference layer, constellation guides, and major-planet identification.

## Highlights

- practical Live view limited to 0–60° elevation for more comfortable human observing
- mouse-wheel, button, and drag-to-select zoom controls
- short three-minute projected satellite tracks sampled every 30 seconds
- arrowheads showing satellite direction of travel
- projected azimuth/elevation information for selected satellites
- real Hipparcos star-field background calculated for the selected observer and current time
- apparent star brightness represented by marker size
- named bright-star labels that become progressively richer as the view is zoomed in
- optional Stellarium constellation guide lines
- Mercury, Venus, Mars, Jupiter, Saturn, Uranus, and Neptune positioned from the Skyfield DE421 ephemeris
- major planets permanently labelled whenever they are physically inside the current Live view
- faint stars remain uncluttered until clicked, then reveal their proper name where available or Hipparcos identifier plus apparent magnitude
- celestial labels follow the current facing direction, horizontal field of view, elevation window, zoom, time, and observer location
- satellites and projected tracks remain visually dominant over the star/planet reference layers

## Reliability and release-readiness fixes

- prevents stale projected-track worker results from replacing newer live satellite positions
- keeps selected-satellite details synchronized when prediction results arrive
- shows incoming projected tracks for satellites that will enter the current view
- labels clipped track endpoints with the real visible prediction offset instead of always showing +3m
- prevents a previous location's star field being shown after switching observer profiles
- clears stale celestial selections when changing observer profile
- keeps major planets visible even when the optional Stars layer is switched off
- replaces unreliable transparent Tkinter star hit targets with coordinate-based click detection for faint stars
- Windows build script stops a running NightAzimuth.exe before rebuilding and fails correctly when PyInstaller fails
- corrected public project description so it does not claim weather/cloud functionality that is not yet implemented

## Existing capabilities retained

- saved observing locations
- live CelesTrak VISUAL satellite tracking
- current azimuth, elevation, and range
- Sunlit, dark-sky, and Potential visibility indicators
- upcoming pass prediction with rise, peak, set, and maximum elevation
- all-sky radar-style Sky map
- forward-looking Live view with compass or numeric bearing and 30°–180° horizontal FOV
- local caching of orbital and astronomy data
- Windows single-file EXE packaging

## Alpha limitations

`Potential` still means astronomically plausible: the satellite is illuminated by the Sun while the observer sky is sufficiently dark. It is **not** a guarantee of naked-eye visibility.

The following are not yet included in the visibility result:

- weather or cloud analysis
- directional cloud estimation
- satellite magnitude/brightness modelling
- haze and atmospheric transparency
- local obstructions
- Moon brightness effects
- camera integration
- aircraft matching
- meteor detection
- unidentified-object classification

The stellar and planetary reference layers depend on cached/downloaded astronomy data and should not be interpreted as proof that every plotted object is visible to the unaided eye under local observing conditions.

**Created by Logic Lurker © 2026**
