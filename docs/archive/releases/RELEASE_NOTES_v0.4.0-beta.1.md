# NightAzimuth v0.4.0-beta.1

**Created by Logic Lurker © 2026**

This is the first beta pre-release of NightAzimuth. It moves the project beyond the alpha phase and focuses the Live view on real-world naked-eye observing: a human-facing sky finder, much broader satellite coverage, smooth satellite movement, and clearer celestial reference labels.

## Highlights

- first **beta** release of NightAzimuth
- redesigned forward-looking Live finder for real-world observing
- full **0–90° elevation range**, including the zenith directly overhead
- click-and-drag panning across azimuth and elevation
- mouse-wheel and button zoom retained
- smooth satellite animation using 1-second orbital prediction samples interpolated at approximately 20 frames per second
- live tracking now combines CelesTrak **VISUAL** and **ACTIVE** catalogues and de-duplicates by NORAD ID
- no arbitrary maximum-range cutoff is applied to live satellite candidates
- normal Live mode prioritises satellites with the fastest apparent angular movement across the current field of view
- up to six fast-mover candidates are shown by default to avoid clutter
- satellite markers are smaller and labelled with satellite name and apparent angular speed when available
- short three-minute projected paths are calculated at one-second granularity
- optional **All tracked** mode exposes the broader potentially-visible set using deliberately small, low-clutter markers
- Vega remains a strong blue-white visual reference with live azimuth and elevation
- named bright stars are automatically labelled again, with richer labels as the user zooms in
- major planets are labelled with live azimuth and elevation
- named galaxy references added for M31, M33, M81, M82, M51, M101 and M104
- existing terrain-horizon masking remains integrated with the Live finder

## Live satellite coverage

Previous alpha releases concentrated primarily on CelesTrak's smaller VISUAL group. This beta adds the much broader ACTIVE catalogue for live tracking so NightAzimuth has a significantly better chance of identifying satellites that a user can actually see moving across the sky.

The broader catalogue is filtered for the current observer and Live view. Normal mode does not draw every tracked object at once; instead it ranks potentially-visible candidates by apparent angular motion, elevation and range so the most useful fast-moving objects remain prominent.

The 24-hour pass-planning view intentionally remains based on the smaller VISUAL catalogue to keep long-range pass calculations practical.

## Smooth movement

Satellite future positions are predicted at one-second intervals over a three-minute window. The displayed marker is interpolated between prediction points approximately every 50 ms. This produces smooth motion across the finder while avoiding unnecessary full orbital recalculation many times per second.

Azimuth interpolation follows the shortest path through 0°/360°, so satellites crossing north should continue smoothly instead of jumping across the screen.

## Celestial references

The Live finder keeps the star field visually subdued so moving targets remain easy to follow, while still providing useful orientation references:

- Vega is permanently emphasised when visible
- named bright stars are labelled automatically
- more named stars appear as the field of view narrows
- Mercury, Venus, Mars, Jupiter, Saturn, Uranus and Neptune remain positioned from the Skyfield ephemeris and are labelled when visible
- a compact built-in set of named galaxy references is plotted from fixed J2000 celestial coordinates and transformed for the current observer/time

These labels are positional references. A plotted star, planet or galaxy is not a guarantee that local conditions make it visible to the unaided eye.

## Terrain and privacy retained

The beta retains the Stage 12 terrain-horizon system:

- automatic 360° terrain-horizon generation after the user enters, saves, edits or selects an observing location
- local terrain cache reused before any download is attempted
- missing Terrarium elevation tiles downloaded automatically and cached locally
- terrain silhouette masks sky objects geometrically below the calculated skyline
- saved user locations remain local under `%APPDATA%\NightAzimuth\locations.json`
- a fresh release contains no saved observer location, personal profile name, terrain cache or runtime configuration
- the saved `locations.json` file and profile name are not uploaded to the terrain provider
- terrain requests use z/x/y tile identifiers derived from the entered location, so the provider can infer the represented geographic area

## Visibility limitation

`Potential` still means astronomically plausible: the satellite is illuminated by the Sun while the observer sky is sufficiently dark. It is **not** a guarantee of naked-eye visibility.

The current Potential result does not yet fully model:

- satellite apparent magnitude or reflective behaviour
- cloud and haze
- Moon brightness
- nearby non-terrain obstructions such as buildings and trees
- camera sensitivity

The new fast-mover ranking improves practical identification of moving objects, but it is not yet a full brightness-probability model.

## Release status

This release is labelled **beta** because the core application and observing workflow are now established and usable, while real-world accuracy, visibility ranking and usability still require continued field testing before a 1.0 release.

**Created by Logic Lurker © 2026**
