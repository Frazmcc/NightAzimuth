# Zero-cost terrain horizon

NightAzimuth can build a useful 360° terrain skyline without Google Earth or a paid API.

## Privacy model

A fresh NightAzimuth installation contains no saved user location. A location exists only after the user enters and saves one.

Saved observing locations remain in the local NightAzimuth application-data folder. The saved `locations.json` file and local profile name are not uploaded to the terrain service.

When terrain for a user-entered location is required, NightAzimuth converts the requested area into standard Terrarium z/x/y tile identifiers and downloads only missing tiles. Because those tile identifiers are derived from the selected observer position, the terrain provider can infer the geographic area covered by the request.

Downloaded Terrarium tiles are cached beneath:

`%APPDATA%\NightAzimuth\terrain\terrarium`

using the layout:

`<terrain-directory>/<zoom>/<x>/<y>.png`

The application reuses cached tiles before making another terrain request.

## Automatic generation when a location is entered

NightAzimuth automatically recalculates the terrain horizon when the user saves, edits, or selects an observing location.

The calculation runs in the background using the selected latitude, longitude and altitude. Required terrain tiles are read from the local cache first. Missing tiles are downloaded and then cached locally for later reuse.

The calculated horizon is kept in memory and displayed directly in the Live view. No separate preview command is required for normal use.

If required terrain data cannot be downloaded, NightAzimuth shows a terrain status message and leaves the terrain overlay unavailable until data can be loaded.

## Live-view behaviour

The calculated terrain skyline is drawn as a silhouette in the Live view. Sky objects geometrically below the local terrain skyline are masked by that silhouette, matching what the observer can actually see behind hills or raised terrain.

The terrain model does not include:

- houses or other buildings
- trees and hedges
- fences
- temporary structures
- very small nearby terrain details below the source elevation-model resolution

A future optional user-supplied panorama could add those local obstructions while keeping that panorama data local.

## Optional offline terrain-pack import

Open **Settings** and choose **Import offline terrain pack...** to import an already-downloaded Terrarium tile directory from the local PC.

The import process:

- validates the local Terrarium tile structure
- copies valid tiles into NightAzimuth's local terrain directory
- makes no network request during the import itself
- triggers a new terrain calculation for the currently selected location after import

Imported tiles and automatically downloaded tiles use the same local cache layout.

## Coverage

The current Terrarium/Web Mercator path covers approximately 85° south to 85° north. Polar locations outside that range would need a different elevation format in a later implementation.

## Synthetic demo mode

The standalone preview tool still provides a synthetic test mode:

```powershell
python .\tools\terrain_horizon_preview.py --demo --output .\terrain_horizon_demo.png
start .\terrain_horizon_demo.png
```

Demo mode does not read saved NightAzimuth locations, terrain files, or network resources.
