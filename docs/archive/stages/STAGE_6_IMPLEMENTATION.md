# Stage 6 — GUI Live Satellite Data

## Scope

Stage 6 connects the graphical application introduced in Stage 5 to the existing Stage 4 satellite-tracking engine.

Implemented in this stage:

- live satellite data inside the Windows GUI
- use the currently selected saved location profile as the observer position
- refresh satellite positions on demand
- automatic refresh when the selected saved location changes
- display current azimuth, elevation, range, sunlit status, dark-sky status, and potential astronomical visibility
- display upcoming passes for the next 24 hours
- display rise, peak, set time, and maximum elevation
- run orbital-data loading and calculations in a background thread so the GUI remains responsive
- store runtime orbital/ephemeris cache under the user's NightAzimuth application-data directory
- continue using the VISUAL CelesTrak group by default

## GUI tabs

### Live satellites

The live table shows:

- satellite name
- NORAD catalogue ID
- azimuth
- elevation
- range in kilometres
- whether the satellite is sunlit
- whether the observer's sky is dark enough
- whether the geometry is potentially favourable for observation

`Potential` remains an astronomical-geometry indicator only. It does not yet include cloud, haze, brightness/magnitude, local obstructions, moonlight, or camera sensitivity.

### Upcoming passes

The pass table shows:

- satellite name
- NORAD catalogue ID
- rise time in UTC
- peak time in UTC
- set time in UTC
- maximum elevation

The current Stage 6 GUI predicts the next 24 hours and uses a 10-degree minimum pass elevation.

## Saved locations

Stage 6 continues to use the Stage 5 location profiles stored under:

```text
%APPDATA%\NightAzimuth\locations.json
```

The selected location drives all GUI calculations.

## Runtime cache

The GUI stores orbital and Skyfield cache data under:

```text
%APPDATA%\NightAzimuth\cache\
```

This keeps runtime data outside the Git repository and makes the packaged EXE independent of the working directory.

## View the current app

From `C:\git\NightAzimuth`:

```powershell
git checkout stage-6-gui-live-data
git pull
.\build_windows.ps1
.\dist\NightAzimuth.exe
```

## Explicitly excluded from Stage 6

Stage 6 does not yet implement:

- radar-style sky map
- weather or cloud integration
- directional cloud estimation
- brightness/magnitude modelling
- camera support
- aircraft matching
- meteor detection
- unidentified-object classification

## Acceptance condition

Stage 6 is complete when the user confirms that the Windows GUI correctly loads the selected location, shows live satellite data, shows upcoming passes, refreshes successfully, and approves the stage for merge.
