# Zero-cost terrain horizon prototype

This prototype tests whether NightAzimuth can build a useful 360° terrain skyline for the currently selected saved observing location without using Google Earth or a paid API.

## Data source

The prototype uses the Mapzen / Tilezen Terrain Tiles dataset hosted as an AWS Open Data public dataset:

- dataset: Terrain Tiles
- format: Terrarium PNG elevation tiles
- public S3 endpoint: `elevation-tiles-prod.s3.amazonaws.com`
- no API key or AWS account is required for public access

Source/attribution information:

- https://registry.opendata.aws/terrain-tiles/
- https://github.com/tilezen/joerd/blob/master/docs/attribution.md

## Privacy

The preview tool reads the selected NightAzimuth location from the existing local `%APPDATA%\NightAzimuth\locations.json` file.

The tool does not print the saved latitude/longitude and does not embed the coordinates in the output PNG. The elevation service necessarily receives tile requests corresponding to the surrounding terrain tiles, as with any online terrain-data lookup.

Downloaded elevation tiles are cached locally under `%APPDATA%\NightAzimuth\cache\terrain-tiles`.

## What the preview represents

The preview calculates the highest terrain elevation angle around the observer and draws a 360° skyline from 0° to 60° elevation.

It is a terrain model, not a photograph. It does not include:

- houses or other buildings
- trees and hedges
- fences
- temporary structures
- very small nearby terrain details below the source DEM resolution

A future optional user-supplied panorama could be combined with this mathematical terrain horizon to include local obstructions without paying for imagery or APIs.

## Run the prototype

From an activated NightAzimuth development environment:

```powershell
python .\tools\terrain_horizon_preview.py
start .\terrain_horizon_preview.png
```

The first run may take longer while public terrain tiles are downloaded. Subsequent runs reuse the local tile cache.
