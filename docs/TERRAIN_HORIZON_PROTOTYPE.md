# Zero-cost offline terrain horizon prototype

This prototype tests whether NightAzimuth can build a useful 360° terrain skyline without Google Earth, a paid API, or any location-derived network request.

## Privacy model

Real saved observing locations are read from the existing local NightAzimuth profile store and used only on the user's own computer.

Terrain lookup is local-only. NightAzimuth does not contact a terrain server and does not request map tiles based on the selected location.

The preview does not include the saved profile name or observer coordinates in the image.

The terrain pack is expected beneath:

`%APPDATA%\NightAzimuth\terrain\terrarium`

or another local directory supplied with `--terrain-directory`.

The local terrain files use the standard Terrarium tile layout:

`<terrain-directory>/<zoom>/<x>/<y>.png`

Tile names are local file-system data only and are never transmitted by this prototype.

## Synthetic demo mode

A separate `--demo` mode exists specifically so the rendering pipeline can be tested without touching any saved NightAzimuth location data.

Demo mode:

- does not read `%APPDATA%\NightAzimuth\locations.json`
- does not use a saved profile name
- uses fixed synthetic observer coordinates at 0°, 0°
- generates the terrain mathematically in memory
- reads no terrain files
- makes no network requests
- writes only the generated preview image

Run the privacy-safe demo with:

```powershell
python .\tools\terrain_horizon_preview.py --demo --output .\terrain_horizon_demo.png
start .\terrain_horizon_demo.png
```

This is the recommended first test before any real offline terrain pack is installed.

## Local terrain-pack import

NightAzimuth can inspect and import an already-downloaded local Terrarium tile directory without reading a saved observer profile and without making any network request.

The import process validates the local tile layout before copying it into NightAzimuth's local terrain directory. It does not determine which pack a user needs from their saved coordinates.

This separation is deliberate: selecting or obtaining a regional terrain pack must remain independent of the private saved observing location.

## Coverage

The real offline terrain path can be used by any NightAzimuth user provided their installed terrain pack covers their observing location.

If a required tile is missing, the calculation stops with a generic message. It does not fall back to an online service and does not reveal the missing tile identifier.

The current Web Mercator tile format covers latitudes between approximately 85° south and 85° north. Polar locations outside that range would need a different offline elevation format in a later implementation.

## What the preview represents

The preview calculates the highest terrain elevation angle around the observer and draws a 360° skyline from 0° to 60° elevation.

It is a terrain model, not a photograph. It does not include:

- houses or other buildings
- trees and hedges
- fences
- temporary structures
- very small nearby terrain details below the source DEM resolution

A future optional user-supplied panorama could be combined with this mathematical terrain horizon to include local obstructions while keeping that data local.

## Terrain data

The prototype deliberately does not download terrain data itself. This avoids revealing a user's area through location-derived requests.

Offline terrain packs can be created from free/open elevation datasets outside NightAzimuth and copied into the local terrain directory before use. Packaging or distributing regional packs can be considered separately before this feature is integrated into the application.

The current prototype therefore proves the private calculation path and local import path, not automatic terrain acquisition. Automatic location-based terrain downloading is intentionally excluded.

## Run against a real saved location later

Only after an appropriate offline terrain pack has been installed:

```powershell
python .\tools\terrain_horizon_preview.py
start .\terrain_horizon_preview.png
```

If the local terrain pack does not cover the selected observing location, the tool exits without making a network request.
