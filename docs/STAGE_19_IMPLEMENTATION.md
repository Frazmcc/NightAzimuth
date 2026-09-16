# Stage 19 — Free aircraft sightline overlay

Status: **In development — not accepted or merged**

## Goal

Add nearby aircraft to the existing observer-facing Live view using the selected
location, current facing direction, field of view, observer altitude, and each
aircraft's reported position, altitude, ground track and ground speed.

## Non-negotiable constraints

- No required API key, subscription, billing account or paid provider.
- The aircraft layer defaults to **Off**. Enabling an internet source sends the
  selected latitude and longitude to that source.
- Aircraft data is informational only and must not be used for navigation,
  collision avoidance, flight operations or emergency decisions.
- The UI must display the source and age of the data.
- Old positions are excluded rather than shown as current.
- Heading and ground track are not interchangeable. The overlay uses ground
  track for projected movement and labels it as track.
- Geometric altitude is preferred when present. Barometric altitude is a
  labelled fallback, not silently treated as geometric height.

## Sources

### Default internet source: ADSB.lol

ADSB.lol documents that its API is available to everyone and that the API data
is licensed under ODbL 1.0. NightAzimuth uses the readsb-compatible point
endpoint without a key, polls conservatively only while the layer is enabled,
keeps only the latest transient snapshot, and provides visible attribution.

- API: https://api.adsb.lol
- Documentation: https://www.adsb.lol/docs/open-data/api/
- Licence: ODbL 1.0

### Optional local source: readsb/dump1090

A local receiver can provide lower latency and avoids sending the selected
location to an aircraft internet service. The configured URL is stored only in
the user's local NightAzimuth preferences.

### Explicitly not required

ADS-B Exchange is not a Stage 19 provider because its technical API is a paid
service. OpenSky is not used because its current automated live-data terms
require a written agreement. This keeps the released feature genuinely
zero-cost rather than relying on a temporary or ambiguous free tier.

## Geometry and accuracy

NightAzimuth converts observer and aircraft WGS84 geodetic positions to
Earth-centred, Earth-fixed coordinates, rotates their difference into the
observer's local East/North/Up frame, and derives:

- true azimuth from local north;
- geometric elevation angle;
- ground distance;
- slant range.

The calculation uses the saved observer altitude. Aircraft altitude uses
`alt_geom` when available and otherwise the explicitly labelled
`alt_baro` fallback. It does not currently correct barometric altitude for
local pressure.

A short movement cue is calculated from reported ground track, ground speed and
vertical rate. It is a projection, not a flight-plan prediction.

## Freshness policy

- Records without a usable latitude, longitude or airborne altitude are skipped.
- Position age uses `seen_pos` when supplied and falls back to `seen`.
- Positions older than 30 seconds are excluded.
- Polling is conservative and never overlaps.
- A failed refresh does not relabel old data as current.

## Privacy

The internet source receives the selected latitude and longitude only after the
aircraft layer is enabled. The application does not upload the profile name or
persist aircraft history. A local receiver is the privacy-first option.

## Acceptance gate

Stage 19 remains on a draft pull request until:

1. parser and geometry tests pass;
2. lint and Windows packaging pass;
3. the source, freshness and limitations are visible in the GUI;
4. the user completes visual testing and explicitly approves the stage.
