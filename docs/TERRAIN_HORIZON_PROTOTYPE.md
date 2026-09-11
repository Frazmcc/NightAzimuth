# Zero-cost offline terrain horizon

NightAzimuth can build a useful 360° terrain skyline without Google Earth, a paid API, or any location-derived network request.

## Privacy model

Saved observing locations remain local to the user's computer. Terrain lookup is local-only: NightAzimuth does not contact a terrain server and does not request map tiles based on the selected location.

Offline Terrarium tiles are stored beneath:

`%APPDATA%\NightAzimuth\terrain\terrarium`

using the layout:

`<terrain-directory>/<zoom>/<x>/<y>.png`

Tile identifiers remain local file-system data and are not transmitted by this feature.

## Automatic generation when a location is entered

Once an offline terrain pack has been installed, NightAzimuth automatically recalculates the terrain horizon when the user saves, edits, or selects an observing location.

The calculation runs locally in the background using the saved latitude, longitude and altitude. The result is kept in memory and displayed directly in the Live view. No separate preview command is required for normal use.

If the installed pack does not cover the selected location, NightAzimuth shows a local status message and does not fall back to an online lookup.

## Live-view behaviour

The calculated terrain skyline is drawn as a silhouette in the Live view. Sky objects geometrically below the local terrain skyline are masked by that silhouette, matching what the observer can actually see behind hills or raised terrain.

The terrain model does not include:

- houses or other buildings
- trees and hedges
- fences
- temporary structures
- very small nearby terrain details below the source elevation-model resolution

A future optional user-supplied panorama could add those local obstructions while keeping the data local.

## Offline terrain-pack import

Open **Settings** and choose **Import offline terrain pack...** to import an already-downloaded Terrarium tile directory from the local PC.

The import process:

- validates the local Terrarium tile structure
- copies valid tiles into NightAzimuth's local terrain directory
- does not read a saved observer profile while importing
- makes no network request
- triggers a new local terrain calculation for the currently selected location after import

NightAzimuth deliberately does not decide which terrain pack to download from the user's coordinates. Selecting or obtaining a regional terrain pack remains independent of the private saved observing location.

## Coverage

The current Terrarium/Web Mercator path covers approximately 85° south to 85° north. Polar locations outside that range would need a different offline elevation format in a later implementation.

## Synthetic demo mode

The standalone preview tool still provides a privacy-safe synthetic test mode:

```powershell
python .\tools\terrain_horizon_preview.py --demo --output .\terrain_horizon_demo.png
start .\terrain_horizon_demo.png
```

Demo mode does not read saved NightAzimuth locations, terrain files, or network resources.
