# NightAzimuth Credits

**Created by Logic Lurker © 2026**

NightAzimuth is a location-based live sky application developed under the Logic Lurker name.

## Current hosted stack

NightAzimuth uses open-source software and public/free data services including, where applicable:

- Python
- FastAPI
- Uvicorn
- HTTPX
- Skyfield
- SGP4
- Pandas
- browser JavaScript/HTML/CSS
- CelesTrak orbital/catalogue data
- ESA Hipparcos star catalogue data through Skyfield
- Stellarium sky-culture/constellation reference data
- MET Norway Locationforecast data
- OurAirports public airport data
- ADSB.lol aircraft/ADS-B data
- adsb.fi aircraft/ADS-B fallback data

The hosted frontend and API are deployed separately. Third-party hosting platforms and DNS/CDN services are subject to their own terms.

## Astronomy and satellite data

CelesTrak is used for satellite orbital/catalogue information. Skyfield/SGP4 are used for astronomy/orbit calculations.

Hipparcos and Stellarium-derived reference data support stellar and constellation presentation.

A plotted or predicted object remains subject to the accuracy and freshness of the underlying catalogue/orbit data.

## Aircraft data

Aircraft data is obtained through provider integrations rather than directly from each browser.

ADSB.lol is the primary hosted ADS-B source in the current architecture, with adsb.fi available as a failover path. Provider data remains subject to the provider's availability, terms and source limitations.

NightAzimuth does not claim that ADS-B data is complete, authoritative or suitable for aviation safety decisions.

## Airports

OurAirports public data is used to build the global airport reference catalogue. Airport horizon labels are geographic/directional references rather than claims of optical runway visibility.

## Weather

Weather forecast data is provided through MET Norway and remains subject to MET Norway terms and attribution requirements.

Historical desktop-stage code may also contain support for OpenStreetMap map tiles, RainViewer radar and EUMETSAT imagery. Those integrations are retained as part of project history unless currently used by the hosted application.

Map data © OpenStreetMap contributors where OpenStreetMap data/tiles are used.

## Legacy desktop dependencies

The historical Windows application also uses/used components such as:

- Tkinter
- Pillow
- timezonefinder
- PyInstaller

These remain in the repository because the desktop implementation is preserved for history/experimentation, but the Windows executable is not the primary supported NightAzimuth product.

## General attribution

Third-party components, catalogues, APIs and imagery remain subject to their own licences, terms, attribution requirements and acceptable-use policies.
