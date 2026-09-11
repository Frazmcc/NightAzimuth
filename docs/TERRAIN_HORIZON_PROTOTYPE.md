# Zero-cost offline terrain horizon prototype

This prototype tests whether NightAzimuth can build a useful 360° terrain skyline without Google Earth, a paid API, or any location-derived network request.

## Privacy model

Real saved observing locations are read from the existing local NightAzimuth profile store and used only on the user's own computer.

Terrain lookup is local-only. NightAzimuth does not contact a terrain server and does not request map tiles based on the selected location.

The preview does not include the saved profile name or observer coordinates in the image.

The managed terrain pack is stored beneath:

`%APPDATA%\NightAzimuth\terrain\terrarium`

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

## Importing an offline terrain pack

A user can import a terrain pack that has already been obtained separately. The import command validates the local tile structure and copies only valid Terrarium PNG tiles into NightAzimuth's managed terrain directory.

The import process does not read a saved observer profile and does not make a network request.

```powershell
python .\tools\terrain_horizon_preview.py --import-pack "C:\path\to\terrain-pack"
```

Expected pack layout:

```text
terrain-pack\
  10\
    500\
      330.png
      331.png
```

The example tile numbers above are illustrative only.

## Coverage

The real offline terrain path can be used by any NightAzimuth user provided their installed terrain pack covers their observing location.

If a required tile is missing, the calculation stops with a generic message. It does not fall back to an online service and does not reveal the missing tile identifier.

The current Web Mercator tile format covers latitudes between approximately 85° south and 85° north. Polar locations outside that range would need a different offline elevation format in a later implementation.

## What the preview represents

The preview calculates the highest terrain elevation angle around the observer and draws a 360° skyline from 0° to 60° elevation.

It is a terrain model, not a photograph. It does not include houses, trees, hedges, fences, temporary structures, or very small nearby terrain details below the source DEM resolution.

A future optional user-supplied panorama could be combined with this mathematical terrain horizon while keeping that data local.

## Run against a real saved location later

Only after an appropriate offline terrain pack has been imported:

```powershell
python .\tools\terrain_horizon_preview.py
start .\terrain_horizon_preview.png
```

If the local terrain pack does not cover the selected observing location, the tool exits without making a network request.
