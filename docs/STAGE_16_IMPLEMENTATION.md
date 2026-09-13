# Stage 16 Implementation — Directional Cloud Overlay

Status: **In testing — not yet accepted**

Stage 16 adds genuine spatial satellite imagery to NightAzimuth and projects an indicative cloud layer into the forward-looking Live view.

## Hard project laws

These rules remain mandatory:

1. No saved, private or test observer location is packaged, committed or shipped. A fresh install starts with no configured location. Automated tests use synthetic coordinates only.
2. NightAzimuth remains free to use. Stage 16 introduces no paid API key, billing account or paid service.

## Spatial cloud source

Stage 16 uses the public EUMETSAT EUMETView WMS service with the Meteosat GeoColour layer.

NightAzimuth requests only the map region needed around the currently selected observer location. It does not send the saved NightAzimuth profile name, `locations.json`, or any other saved profile.

Downloaded cloud imagery is cached locally under the NightAzimuth cache directory. Cache filenames are hash based and do not contain readable coordinates.

## Weather map

The Weather map gains a working **Cloud imagery** checkbox.

When enabled, the map combines:

- OpenStreetMap base map
- optional RainViewer precipitation radar
- EUMETView Meteosat GeoColour imagery
- the local observer marker

The map displays attribution for the active imagery source.

## Live cloud overlay

The Live finder gains a working **Cloud overlay** checkbox.

When enabled, NightAzimuth projects the nearby Meteosat cloud imagery into the current azimuth/elevation view using:

- the selected observer location
- the current Live facing direction and field of view
- the current Live elevation range
- a representative cloud-layer altitude

The overlay is intentionally subdued so satellite markers and celestial references remain readable.

## Accuracy limitation

The Live overlay is an **indicative spatial cloud estimate**, not a precise 3D cloud reconstruction.

The source imagery is spatial satellite imagery, but the conversion from geographic cloud position into azimuth/elevation requires an assumed representative cloud altitude. Real cloud height varies by cloud type and weather system. The UI therefore must not claim exact cloud/elevation alignment or guaranteed visibility.

A later refinement can use cloud-top-height products where a free and suitable source is available.

## Privacy

Runtime requests can reveal the geographic region around the location the user entered, because spatial weather imagery cannot be requested without specifying a region. This is disclosed honestly.

NightAzimuth does not send:

- profile names
- `locations.json`
- other saved locations
- packaged test locations

The release output continues to contain only the application and approved documentation, not runtime weather/map/cloud caches.

## Cost

The Stage 16 design uses EUMETView's public OGC access and introduces no paid service, subscription or billing requirement.

If a provider later changes its terms so that a paid account is required, that provider must be replaced or the feature disabled rather than introducing a cost.

## Stage gate

Stage 16 remains on its feature branch until local testing is complete, CI succeeds and the user explicitly says **Accept**.
