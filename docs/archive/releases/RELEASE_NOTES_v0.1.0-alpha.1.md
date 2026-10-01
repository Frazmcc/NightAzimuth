# NightAzimuth v0.1.0-alpha.1

**Created by Logic Lurker © 2026**

This is the first packaged pre-release of NightAzimuth.

## Included

- Windows desktop GUI
- saved observing locations with latitude, longitude, and altitude
- quick switching between saved locations
- live CelesTrak satellite data using the VISUAL catalogue
- current azimuth, elevation, and range
- sunlit and dark-sky status
- astronomical `Potential` visibility flag
- upcoming pass prediction with rise, peak, set, and maximum elevation
- all-sky radar-style Sky map
- forward-looking Live view
- facing direction by compass point or bearing
- selectable 30° to 180° horizontal field of view
- clickable satellite markers and satellite details
- automatic live refresh in the Stage 7 GUI
- local orbital and Skyfield caching
- Windows EXE build through `build_windows.ps1`
- Logic Lurker creator branding and credits

## Important limitations

`Potential` means that the satellite is sunlit while the observer's sky is sufficiently dark. It does not guarantee naked-eye visibility.

This release does not yet include:

- cloud or weather analysis
- directional cloud estimation
- apparent magnitude / brightness modelling
- local obstruction modelling
- Moon effects on visibility
- camera integration
- aircraft matching
- meteor detection
- unidentified-object classification

## Data

Satellite orbital data are obtained from CelesTrak and cached locally. Skyfield astronomy data are also cached locally under the user's NightAzimuth application-data directory.

## Release status

This is an **alpha pre-release** intended for testing and early use. Behaviour and interfaces may change in later versions.
