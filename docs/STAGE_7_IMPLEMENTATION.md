# Stage 7 — Live Radar-Style Sky Map

## Scope

Stage 7 adds a graphical all-sky radar view to the NightAzimuth Windows application while reusing the existing Stage 6 tracking, visibility, pass-prediction, saved-location, and caching layers.

Implemented in this stage:

- new **Sky map** tab in the Windows GUI
- circular all-sky projection with horizon at the outer edge
- zenith at the centre
- north at top, east at right, south at bottom, west at left
- 30-degree and 60-degree elevation reference rings
- current satellites plotted using real topocentric azimuth and elevation
- potentially-visible satellites distinguished from other above-horizon satellites
- selectable satellite markers
- selected-satellite details showing name, NORAD ID, azimuth, elevation, range, sunlit state, dark-sky state, and potential-visibility state
- synchronization between sky-map marker selection and the existing live-satellite table
- automatic data refresh every 30 seconds
- manual Refresh button retained
- projection logic separated into a testable helper
- automated tests for zenith, cardinal directions, and mid-elevation projection

## Projection

The map uses an azimuthal all-sky display intended for practical visual observing:

- azimuth 0° = north
- azimuth 90° = east
- azimuth 180° = south
- azimuth 270° = west
- elevation 0° = horizon circle
- elevation 90° = zenith / centre

The radial distance from the centre is linear with `(90° - elevation)`.

## Visibility colours

- yellow marker: astronomically potentially visible
- blue marker: other satellite currently above the horizon
- white outline: currently selected marker

`Potentially visible` still means only that the satellite is sunlit while the observer sky is sufficiently dark. Weather, cloud, haze, local obstructions, brightness/magnitude, and camera sensitivity are not included yet.

## Windows test commands

From `C:\git\NightAzimuth`:

```powershell
git checkout stage-7-live-sky-map
git pull
.\.venv\Scripts\Activate.ps1
pytest
.\build_windows.ps1
.\dist\NightAzimuth.exe
```

## Acceptance condition

Stage 7 is complete when the user confirms that the sky map displays correctly, satellite positions appear sensible relative to the live satellite table, marker selection works, automatic refresh behaves correctly, and the stage is approved for merge.

Created by Logic Lurker © 2026.
