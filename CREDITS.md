# NightAzimuth Credits

**Created by Logic Lurker © 2026**

NightAzimuth is a location-based satellite tracking application developed under the Logic Lurker name.

## Core third-party components

NightAzimuth currently uses:

- Python
- Tkinter
- Skyfield
- SGP4
- Pandas
- HTTPX
- Pillow
- PyInstaller
- CelesTrak General Perturbations orbital data
- ESA Hipparcos star catalogue data, loaded through Skyfield
- Stellarium modern sky-culture data for constellation line definitions and proper star names
- MET Norway Locationforecast 2.0 for point weather and cloud forecast data
- OpenStreetMap standard raster tiles for the Stage 15 weather-map base layer
- RainViewer public Weather Maps API for recent precipitation-radar tiles
- EUMETSAT EUMETView Meteosat GeoColour imagery for Stage 16 spatial cloud visualisation
- Anthony Mallama's published OneWeb photometry and empirical phase function for source-labelled OneWeb brightness estimates
- ADSB.lol live aircraft data for the optional Stage 19 aircraft layer (ODbL 1.0)

Weather forecast data is provided by the Norwegian Meteorological Institute (MET Norway) and remains subject to its provider terms and attribution requirements.

Map data © OpenStreetMap contributors. Use of OpenStreetMap-hosted tiles is subject to the OpenStreetMap Foundation tile usage policy.

Rain radar data is provided through RainViewer and is subject to RainViewer's public API terms and attribution requirements.

Stage 16 cloud imagery is provided through EUMETSAT EUMETView. The GeoColour product combines EUMETSAT Meteosat imagery with NASA Black Marble background information for its night-time presentation; both EUMETSAT and NASA are credited as requested by the product description.

The OneWeb apparent-magnitude model is based on Anthony Mallama, *OneWeb Satellite Brightness — Characterized From 80,000 Visible Light Magnitudes* (arXiv:2203.05513). NightAzimuth widens the published scatter when presenting its family-level estimate and does not claim measured photometry for a predicted pass.

When the optional internet aircraft layer is enabled, nearby aircraft data is provided by ADSB.lol and licensed under the Open Data Commons Open Database License (ODbL) 1.0. NightAzimuth displays the attribution in the Live finder and does not persist an aircraft-position database. A user-configured local readsb/dump1090 receiver is also supported.

Third-party components and data remain subject to their own licences, terms, and attribution requirements.
