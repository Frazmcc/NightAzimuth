# Stage 19 — Aircraft / ADS-B Identification

Status: **Draft implementation plan — not yet implemented**

## Goal

Stage 19 adds live aircraft identification to NightAzimuth without turning the application into a general-purpose flight tracker.

The feature exists to answer the observing question:

> **Is the moving light I can see an aircraft, and where should that aircraft appear in my sky?**

Aircraft data is converted into the same observer-centred language already used by NightAzimuth: azimuth, elevation, range, direction of movement, source age and confidence. The implementation must preserve NightAzimuth's existing accuracy-first behaviour and must never present an extrapolated aircraft position as if it were a fresh measured ADS-B position.

Stage 19 remains provider-independent. The initial internet source is **adsb.lol**, with optional local **readsb/dump1090-compatible** input for users who operate their own ADS-B receiver. Paid services, API keys and subscription-only data are not required for the core feature.

## Design principles

- accuracy before visual effect
- no-cost operation by default
- provider-independent internal aircraft model
- local receiver data preferred when it is available, fresh and valid
- explicit source and data-age labelling
- distinguish measured, interpolated and extrapolated positions
- bounded prediction only; stale aircraft must not continue flying indefinitely
- no hidden blending of unrelated sources
- no requirement for OpenSky or ADS-B Exchange
- do not weaken the existing satellite, celestial, weather or terrain behaviour
- keep aircraft identification focused on the observer's sky rather than worldwide flight tracking
- implement one approved sub-stage at a time

## Scope

Stage 19 includes:

- an internal provider-independent aircraft observation model
- adsb.lol live aircraft ingestion
- optional local readsb/dump1090 ingestion
- input validation and normalisation
- source health, observation time and freshness tracking
- source precedence and failover rules
- observer-relative aircraft geometry
- azimuth, elevation and slant range
- smooth aircraft motion between known observations
- bounded dead-reckoning when a fresh position has not yet arrived
- aircraft markers in the existing Live finder
- projected short aircraft tracks
- click-to-select aircraft
- selected-aircraft details
- nearby-aircraft / current-view contacts list
- optional, rate-limited aircraft metadata enrichment
- tests covering geometry, freshness, normalisation and motion behaviour

Stage 19 does **not** include:

- CCTV
- ships or AIS
- road traffic
- military-installation mapping
- ALPR cameras
- radio streams
- a photorealistic 3D globe
- AI or voice control
- tactical sensor effects
- worldwide historical flight replay
- guaranteed identification of every visible light
- camera-image object detection
- meteor classification
- automatic unidentified-event classification

Those capabilities are separate from the aircraft-identification foundation and must not be introduced as incidental scope.

---

# Stage 19A — Provider-independent aircraft data foundation

## Internal observation model

All aircraft providers must normalise their records into one internal model before the GUI or sky geometry consumes them.

A proposed immutable observation structure is:

```python
@dataclass(frozen=True, slots=True)
class AircraftObservation:
    icao24: str
    callsign: str | None

    latitude_deg: float
    longitude_deg: float

    barometric_altitude_m: float | None
    geometric_altitude_m: float | None

    ground_speed_mps: float | None
    track_deg: float | None
    vertical_rate_mps: float | None

    squawk: str | None
    on_ground: bool | None

    position_observed_at: datetime
    contact_observed_at: datetime | None

    source_id: str
    source_label: str
    source_kind: str
```

The exact Python names may change during implementation, but the semantic separation must remain.

## Required normalisation

Providers may use different units and field names. Each provider adapter is responsible for converting its data into NightAzimuth's canonical units:

- latitude / longitude: decimal degrees
- altitude: metres internally
- ground speed: metres per second internally
- vertical rate: metres per second internally
- track: degrees clockwise from true north
- time: timezone-aware UTC `datetime`

The GUI may display user-friendly aviation units such as feet and knots while calculations continue to use canonical units.

## Record validation

Reject a position observation when any of the following applies:

- ICAO identifier is missing or unusable
- latitude is missing, non-finite or outside -90..90
- longitude is missing, non-finite or outside -180..180
- observation timestamp is invalid
- source data is malformed beyond safe interpretation

Optional fields must remain `None` rather than being fabricated.

A missing callsign, altitude, track or velocity must not invalidate an otherwise valid position.

## Provider interface

The provider boundary should expose a small common contract, for example:

```python
class AircraftProvider(Protocol):
    provider_id: str
    label: str

    def fetch_snapshot(
        self,
        observer: GeoLocation,
        radius_km: float,
        *,
        cancel_event: threading.Event | None = None,
    ) -> AircraftSnapshot:
        ...
```

A snapshot should contain both observations and source metadata:

```python
@dataclass(frozen=True, slots=True)
class AircraftSnapshot:
    observations: tuple[AircraftObservation, ...]
    source_id: str
    source_label: str
    fetched_at: datetime
    source_observed_at: datetime | None
    coverage_description: str
    stale: bool
    error: str | None = None
```

The rest of NightAzimuth must consume `AircraftSnapshot` / `AircraftObservation`, not adsb.lol-specific JSON.

---

# Stage 19B — Initial providers and source precedence

## Internet source — adsb.lol

The initial public internet source is adsb.lol because it can provide bounded aircraft observations without requiring a paid subscription or API key.

The provider must request only the geographic area required for the current observing location and configured search radius. It must not fetch worldwide traffic merely to display a local sky.

The adapter must normalise at least the fields needed for:

- ICAO identity
- callsign when present
- latitude / longitude
- barometric or geometric altitude when present
- ground speed
- track
- vertical rate
- squawk when present
- ground state when present
- provider observation age / time

## Local receiver source — readsb / dump1090-compatible

NightAzimuth should support a local ADS-B receiver without making one mandatory.

The implementation should target a provider abstraction rather than a particular hardware brand. Compatible JSON exposed by readsb/dump1090-style installations can be adapted into the same internal aircraft model.

No automatic LAN scanning is required for the first implementation. A user-configured local endpoint is safer, simpler and more predictable.

Example configuration concept:

```text
Aircraft source: Auto
Local ADS-B URL: http://192.168.x.x/...
Internet fallback: adsb.lol
```

The actual configuration field and endpoint path must be validated during implementation rather than hard-coded from an assumption.

## Source precedence

Default source mode: **Auto**.

Precedence:

1. configured local receiver, when reachable and fresh
2. adsb.lol
3. last-good snapshot for a short bounded grace period, visibly marked stale
4. no aircraft data

The application must not silently combine two simultaneous aircraft snapshots unless a later stage defines and tests explicit de-duplication rules.

If the local receiver fails, NightAzimuth may fall back to adsb.lol. The GUI must show the active source change.

If both sources fail, the previous snapshot may remain visible only for the configured stale grace period and must be labelled stale.

## No hidden source quality claims

Local receiver data may have lower latency near the observer but can have limited coverage. Internet data may have wider coverage but different latency and aggregation characteristics.

NightAzimuth must report concrete properties such as:

- active source
- source age
- position age
- number of contacts
- configured/estimated coverage description

It must not display unsupported claims such as `more accurate` or `complete coverage`.

---

# Stage 19C — Freshness and source health

## Source time versus fetch time

NightAzimuth must distinguish:

- **source observation time** — when the provider says the aircraft position/contact was observed
- **fetch time** — when NightAzimuth received the response

Receiving a cached HTTP response does not make old aircraft data fresh.

## Per-aircraft age

Where the source provides per-aircraft age values, calculate:

```text
position_age = now - position_observed_at
contact_age  = now - contact_observed_at
```

The UI should expose position age for the selected aircraft.

## Snapshot state

A snapshot should be classified using explicit thresholds defined in configuration/constants and covered by tests.

Suggested semantic states:

```text
LIVE
AGING
STALE
UNAVAILABLE
```

The exact thresholds must be selected after observing real provider behaviour. They must not be guessed into the UI without testing.

## Backoff

Repeated provider failures must use bounded retry/backoff rather than tight polling loops.

Requirements:

- no retry storm
- cancellation when location changes or application exits
- source errors do not block satellite rendering
- last-good data may remain temporarily available with an explicit stale label
- a later successful snapshot clears the error and stale state

---

# Stage 19D — Observer-relative aircraft geometry

Aircraft latitude, longitude and altitude are not directly useful to somebody looking into the sky. NightAzimuth must convert aircraft positions into observer-centred geometry.

For each usable aircraft position calculate:

- geodetic observer position
- geodetic aircraft position
- Earth-centred/ECEF coordinates or an equivalently robust local transform
- local East/North/Up vector
- azimuth
- elevation
- slant range

## Altitude choice

Preferred altitude for sky geometry:

1. geometric altitude when valid and appropriate
2. otherwise barometric altitude with an explicit internal provenance marker
3. if neither is available, do not fabricate elevation

The implementation must document the consequences of barometric versus geometric altitude rather than silently treating them as equivalent.

## Terrain horizon

The existing NightAzimuth terrain horizon remains authoritative for terrain masking.

Aircraft below the calculated local terrain horizon may be omitted from the practical visible-aircraft view or marked terrain-masked according to the same design principles used for other sky objects.

Terrain masking does not account for buildings, trees or other local obstructions.

## Ground aircraft

Ground traffic is generally not useful in the sky finder.

Default behaviour should exclude `on_ground=True` contacts from the sky view while allowing a diagnostics mode to expose them if required for testing.

---

# Stage 19E — Motion model

## Why interpolation is required

ADS-B/network snapshots arrive more slowly than NightAzimuth redraws the Live finder. Rendering each new fix directly would make aircraft jump from point to point.

Stage 19 therefore stores a short history of valid position fixes per aircraft.

## Position history

Maintain a bounded deque per ICAO address containing enough recent fixes for interpolation and short prediction.

Example conceptual record:

```python
@dataclass(slots=True)
class AircraftFix:
    observed_at: datetime
    latitude_deg: float
    longitude_deg: float
    altitude_m: float | None
    ground_speed_mps: float | None
    track_deg: float | None
    vertical_rate_mps: float | None
```

History must be bounded by both count and age so disappeared aircraft cannot accumulate indefinitely.

## Delayed interpolation

Where practical, render aircraft slightly behind wall-clock time so the display can interpolate between two known measurements rather than constantly extrapolating from the newest one.

Conceptually:

```text
known fix A ---------------- known fix B
                    ^
              display time
```

The delay should be tied to observed provider cadence rather than copied blindly from another project.

## Interpolation

When display time falls between two valid fixes:

- interpolate position between the known observations
- interpolate altitude when both endpoints provide usable altitude
- interpolate heading using circular-angle interpolation rather than ordinary numeric interpolation
- mark the displayed position state as `INTERPOLATED`

## Bounded dead-reckoning

When display time is newer than the latest position and the aircraft has sufficient kinematic information, NightAzimuth may project the position forward briefly using:

- latest known position
- ground speed
- track
- vertical rate when available

Prediction must stop at a strict maximum horizon.

An aircraft must never continue indefinitely merely because it once had a valid speed and heading.

The displayed state must be `ESTIMATED` / `EXTRAPOLATED`, not measured.

## Position-state labels

Internally and in selected-aircraft details, distinguish:

```text
MEASURED
INTERPOLATED
EXTRAPOLATED
STALE
```

A practical UI may simplify the wording, but the semantic state must remain available to the model and tests.

## Snap correction

When a new measured fix arrives after short extrapolation, do not visibly teleport the aircraft back to the new fix unless the discrepancy is too large for a safe blend.

Use a short correction blend for reasonable errors. Large discontinuities should reset the motion history and render the new measured position directly.

Thresholds must be testable constants.

---

# Stage 19F — Live Finder aircraft layer

## Layer behaviour

Aircraft are added to the existing forward-looking Live finder as an optional layer. They must not replace or interfere with satellites, stars, constellations, planets or terrain.

Suggested controls:

```text
[✓] Satellites
[✓] Aircraft
[✓] Stars
[✓] Constellations
```

The exact layout should fit the existing GUI rather than creating a separate flight-tracker window.

## Aircraft marker

A marker should communicate direction without excessive decoration.

Initial marker requirements:

- compact aircraft/glyph marker
- orientation follows track when known
- callsign shown when available and when label density permits
- otherwise ICAO identifier or generic aircraft label
- selected aircraft visually distinguished
- terrain-masked/stale contacts are not presented as equally current, visible targets

## Decluttering

The Live finder must remain usable in busy airspace.

Apply label-density rules based on:

- current field of view
- distance from the centre of the view
- selection state
- aircraft age
- available screen space

Selected aircraft always retains its label.

## Short projected path

Display a short projected aircraft path derived from the same bounded motion model.

The path is a **projection**, not an asserted future route.

Do not infer destination, airway or flight plan from current track alone.

---

# Stage 19G — Aircraft selection and detail panel

Clicking an aircraft marker selects that contact without disabling normal sky panning.

Selected-aircraft details should include fields when available:

```text
Callsign
ICAO 24-bit address
Registration / aircraft type (if enriched)

Altitude
Ground speed
Track / heading label
Vertical rate

Azimuth
Elevation
Slant range
Apparent angular movement when calculable

Position state
Position age
Active source
Source freshness
```

Unknown fields are shown as Unknown or omitted. Values must not be invented.

## Follow / centre action

Provide an explicit action to centre/follow the selected aircraft in the Live finder.

Follow mode should release when:

- the user explicitly pans away
- the aircraft disappears beyond the stale/prediction limit
- the source becomes unavailable beyond the allowed grace period
- the selected observing location changes

A background refresh must never seize camera/view control after the user has manually moved away.

---

# Stage 19H — Nearby aircraft / Contacts

Add an observer-focused aircraft list rather than a worldwide traffic roster.

Two useful filters are:

- **Nearby** — within the configured aircraft radius and above the practical horizon rules
- **In current view** — aircraft whose azimuth/elevation lies inside the current Live-finder field of view

Suggested columns/fields:

```text
Callsign     Type       Range       Elevation      Age
BAW123       A320       18.2 km      31.4°         2.1 s
```

Aircraft type appears only when enrichment has resolved it.

Selecting a row selects the same aircraft marker in the Live finder.

Sort options may later include:

- closest angular match to centre of view
- nearest range
- highest elevation
- callsign

The initial implementation should use the simplest useful ordering and avoid unnecessary controls.

---

# Stage 19I — Optional aircraft metadata enrichment

Basic aircraft identification must work without enrichment.

Enrichment exists only to improve a selected or currently relevant contact with information such as:

- registration
- aircraft type code
- aircraft model
- operator
- route, only if an acceptable source and licence can be established

## Queue requirements

Do not query metadata services for every aircraft indiscriminately.

Use a bounded priority queue:

1. selected aircraft
2. aircraft in the current Live-finder view
3. optional nearby candidates within a strict budget
4. everything else receives no lookup

The queue must include:

- maximum concurrent requests
- minimum dispatch spacing
- duplicate suppression/cache
- request cancellation on shutdown/location lifecycle where practical
- negative-result caching for a sensible period
- provider-specific rate limits

Metadata enrichment errors must never stop the core ADS-B layer.

## Licensing gate

No metadata provider is approved merely because another project uses it.

Before enabling an enrichment source in NightAzimuth:

- verify current provider terms
- verify rate limits
- verify redistribution/display restrictions
- document required attribution
- confirm that the no-cost use case remains acceptable

If those conditions are unclear, the enrichment feature remains disabled or limited to clearly permitted local/static data.

---

# Stage 19J — Source attribution and provenance UI

NightAzimuth should extend its existing source-labelled design to aircraft.

At minimum, the aircraft status area should expose:

```text
Aircraft source: adsb.lol
Contacts: 84
Last source observation: 12:24:37
Data age: 2.4 s
Status: LIVE
```

When using a local receiver:

```text
Aircraft source: Local ADS-B
Endpoint: configured local receiver
Status: LIVE
```

Do not display private credentials or unnecessarily expose the user's configured endpoint in screenshots/logs.

Required provider attribution should be added to `CREDITS.md` and, where required by the provider, displayed in the application.

---

# Stage 19K — Configuration

Initial aircraft settings should remain small.

Suggested settings:

```text
Enable aircraft layer        Yes / No
Aircraft source              Auto / Local / adsb.lol
Local ADS-B endpoint         optional
Search radius                sensible bounded choices
Show aircraft callsigns      Yes / No
```

Advanced motion/freshness thresholds should remain internal constants unless users have a genuine operational reason to change them.

Do not expose implementation knobs simply because they exist.

---

# Stage 19L — Privacy and security

## Privacy

Internet aircraft queries are necessarily derived from the selected observing area. The provider can therefore infer the geographic area represented by the request.

NightAzimuth must continue its existing rule:

- do not upload saved profile names
- do not upload the saved locations file
- send only the coordinates/area required to obtain the requested aircraft data

Local ADS-B mode can avoid external aircraft-location requests when it is the active source.

## Network security

- no embedded API keys
- no arbitrary execution based on provider content
- strict JSON/content validation
- bounded response sizes where practical
- reasonable connection/read timeouts
- no uncontrolled redirect or retry loops
- cancellation during location change and shutdown

A user-configured local HTTP endpoint must be treated as untrusted network input.

---

# Stage 19M — Performance

Aircraft must not degrade the existing smooth Live finder.

Requirements:

- network acquisition occurs off the Tkinter UI thread
- coordinate transforms are batched where practical
- no redraw per aircraft network record
- one snapshot update should result in one coherent model update
- animation uses existing scheduled redraw principles rather than spawning per-aircraft timers
- history and metadata caches are bounded
- contacts outside the configured search/horizon/view rules are culled before expensive label work
- changing observing location cancels or supersedes work for the old location

Aircraft animation should reuse the existing principle of model state calculated at a modest cadence and smooth display interpolation at the GUI render cadence.

---

# Stage 19N — Testing

Stage 19 is not complete without automated tests.

## Provider normalisation tests

Cover:

- valid adsb.lol record
- ground aircraft
- missing callsign
- missing altitude
- geometric versus barometric altitude
- knots-to-m/s conversion
- ft/min-to-m/s conversion
- malformed numeric values
- missing position
- stale timestamps
- duplicate ICAO observations

## Geometry tests

Use known observer/aircraft coordinates to verify:

- north/east/south/west azimuth cases
- aircraft overhead / near zenith
- below-horizon geometry
- slant range
- altitude changes
- longitude wrap / edge cases where relevant

Tolerances must be explicit.

## Motion tests

Cover:

- interpolation between two fixes
- circular heading interpolation across 359° → 1°
- vertical interpolation
- bounded extrapolation
- no extrapolation without sufficient velocity/track data
- extrapolation stops at the stale horizon
- large discontinuity resets history
- correction blending for a small discrepancy

## Source lifecycle tests

Cover:

- local source healthy
- local source failure → adsb.lol fallback
- stale last-good snapshot
- recovery from stale state
- location change cancels old request
- late response from previous location cannot replace current location state
- application shutdown cancels/ignores pending work

## UI/model tests

Cover where practical:

- aircraft layer toggle
- selected aircraft survives normal refresh when still present
- selected aircraft clears after expiry
- manual pan releases follow mode
- status shows active source and age
- measured/interpolated/extrapolated state is preserved in the selected-aircraft model

---

# Acceptance gates

Stage 19 should progress through explicit sub-stage gates rather than one large merge.

## Gate 19A/19B — Data foundation

Required before Live-finder work:

- provider protocol implemented
- adsb.lol adapter implemented
- optional local adapter design confirmed against a real supported output format
- normalisation tests pass
- freshness state implemented
- source precedence tests pass

## Gate 19C/19D — Geometry

Required before aircraft are drawn:

- observer-relative azimuth/elevation/range validated
- altitude provenance handled explicitly
- terrain/horizon interaction documented
- geometry tests pass

## Gate 19E — Motion

Required before smooth animation is enabled:

- interpolation tests pass
- extrapolation horizon tested
- stale aircraft cannot drift indefinitely
- position-state labelling works

## Gate 19F/19G — Live Finder

Required before user approval:

- aircraft layer can be enabled/disabled independently
- markers remain legible with satellites/stars present
- selection/details work
- follow mode never overrides explicit user navigation
- source age/status visible

## Gate 19H/19I — Contacts/enrichment

Required before metadata enrichment ships:

- contacts list is observer-focused and bounded
- enrichment queue cannot create request storms
- enrichment provider terms reviewed and documented
- core aircraft layer works when enrichment is completely unavailable

## Final Stage 19 gate

Before merge/release:

- full automated suite passes
- Ruff checks pass
- Windows PyInstaller build passes
- release-output allowlist passes
- local visual testing completed
- local receiver tested if that adapter is included in the release
- adsb.lol behaviour tested against real data
- source attribution/credits updated
- user guide updated
- explicit approval received

---

# Proposed module structure

The implementation should prefer small modules rather than growing the GUI controller into an aircraft subsystem.

A possible structure is:

```text
nightazimuth/
    aircraft/
        __init__.py
        models.py
        geometry.py
        motion.py
        freshness.py
        manager.py
        providers/
            __init__.py
            base.py
            adsb_lol.py
            readsb.py
        enrichment/
            __init__.py
            manager.py
```

The actual package path should match the current repository layout when implementation begins. The important boundary is that provider parsing, geometry, motion and GUI presentation remain separable and independently testable.

---

# Relationship to future unidentified-event classification

Stage 19 supplies one evidence source for later unidentified-event work.

A future classifier may compare a user-observed direction/time against:

- satellites
- aircraft
- planets/stars
- meteor candidates
- other known sources

Stage 19 must not claim that a nearby aircraft automatically explains an observation.

The correct future evidence language is closer to:

```text
Aircraft candidate: BAW123
Angular separation from reported direction: 1.2°
Aircraft position age: 2.0 s
Aircraft position state: INTERPOLATED
```

rather than:

```text
Confirmed aircraft
```

unless the evidence is sufficient for that conclusion.

---

# Reference architecture review

The Stage 19 design was informed by inspection of the `Frazmcc/gods-eye-view` repository, particularly its separation of:

- ADS-B provider normalisation
- source acquisition/freshness from rendering
- bounded aircraft position history
- interpolation and dead-reckoning
- selected-contact tracking
- rate-limited metadata enrichment
- per-layer lifecycle management
- explicit data-source attribution

NightAzimuth does **not** copy the broader God's Eye View product scope. It adapts the useful engineering patterns to NightAzimuth's existing observer-centred astronomical identification model.

Any source code copied rather than independently implemented must be reviewed for licence and attribution requirements before merge. Third-party data-provider terms must be reviewed separately from source-code licensing.

---

# Intended Stage 19 result

When Stage 19 is complete, a user looking at a moving light should be able to open the existing Live finder and see an aircraft candidate in the same sky coordinate system as satellites and celestial references.

A selected aircraft should answer:

```text
What is it?
Where is it in my sky?
How far away is it?
Which direction is it moving?
How old is the source position?
Is the displayed position measured, interpolated or estimated?
Which source supplied the data?
```

That is the Stage 19 boundary.

NightAzimuth remains an observing and identification tool, not a general-purpose surveillance globe or flight-tracking application.
