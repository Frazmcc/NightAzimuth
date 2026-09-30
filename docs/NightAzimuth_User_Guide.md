# NightAzimuth User Guide

**Current product: hosted web application**  
**Created by Logic Lurker © 2026**

NightAzimuth is an observer-centred live sky application for identifying satellites, aircraft and natural sky objects from a chosen location.

Use the current application at:

**https://nightazimuth.co.uk**

The older Windows executable is a legacy build and is not feature-equivalent to the web application. See [`LEGACY_DESKTOP.md`](LEGACY_DESKTOP.md).

## 1. Getting started

Open `nightazimuth.co.uk` in a modern browser.

NightAzimuth needs an observer position to calculate what is above your horizon and where objects appear in your sky. Open **Settings** and enter the required latitude/longitude. Where the browser offers a location option, you can use it instead of typing coordinates manually.

NightAzimuth does not ship with a fixed personal location.

## 2. Live Sky

Live Sky is the main observing surface.

You can:

- click and drag to look around the sky
- move through the full 360° horizontal view
- zoom in and out
- set a numeric field of view and apply it
- look upward without an artificial vertical ceiling
- pan down only as far as the horizon

NightAzimuth intentionally does not render a meaningless blank region below the horizon.

A wide field of view such as 120° is useful for general identification. Narrower fields of view are useful when examining a specific object.

## 3. Layers

The browser experience separates major object types into layers. Depending on the current build, these include:

- Constellations
- Stars
- Planets
- Satellites
- Aircraft
- Airports

Turn off layers you do not need when you want a cleaner view.

## 4. Selecting objects

Objects that support interaction can be selected to display more information.

The intended interaction is:

1. first click selects the object and centres/follows it
2. clicking the selected object again deselects it
3. after deselection, normal panning is restored immediately

Selection should never permanently lock manual sky movement.

## 5. Stars, planets and galaxies

NightAzimuth renders natural celestial references from astronomy data rather than placing decorative objects at arbitrary screen positions.

A plotted star/planet/galaxy means that its calculated direction is represented in the current sky model. It does **not** guarantee naked-eye visibility. Daylight, cloud, haze, light pollution and local obstructions still matter.

## 6. Satellites

Satellite positions are calculated relative to your observer location.

NightAzimuth can display satellites above the horizon together with short projected tracks and identifying information where the source data supports it.

The application keeps orbital geometry separate from visibility claims:

- above the horizon
- illuminated by the Sun
- favourable geometry
- likely naked-eye visibility

are not the same thing.

Starlink and other large constellations are treated as real tracked orbital objects rather than static artwork.

## 7. Aircraft

Aircraft data is obtained through NightAzimuth's hosted API rather than every browser directly contacting the ADS-B provider.

NightAzimuth uses a shared regional snapshot model:

- the backend obtains a wider aircraft snapshot for an active region
- the snapshot is reused briefly for users in the same area
- each user's exact distance/elevation filtering is then calculated for that observer
- a recent last-known-good snapshot may be used briefly if the upstream provider has a transient failure

This reduces provider load while keeping observer-specific results.

Where available, aircraft details can include:

- callsign/registration
- type/model
- operator/role
- squawk and plain-English meaning
- altitude
- speed
- track
- vertical rate
- range/data freshness
- departure/arrival information when a real source supplies it

NightAzimuth does not invent missing airline schedule or route data.

Special roles may be highlighted when the source data gives defensible evidence, including:

- Military
- Air Ambulance / HEMS
- Police
- Coastguard / Search and Rescue

## 8. Aircraft list and radar behaviour

The aircraft list is designed to help locate contacts in Live Sky. Selecting an aircraft from the list should centre/highlight the same contact in the sky view.

The current web experience uses a local aircraft/radar distance setting rather than the old desktop-era large default acquisition ranges.

## 9. Airports

Airport references are calculated from the observer position using global airport data. They are directional/horizon references, not a claim that the physical runway is optically visible.

Airport distance filtering is intended to keep the layer useful instead of filling the horizon with distant labels.

## 10. Weather and observing guidance

NightAzimuth provides point weather and observing guidance through the hosted API.

Weather data can help with observing decisions, but it cannot represent every local cloud edge, obstruction or visibility effect at your exact viewing position.

## 11. Refresh and performance behaviour

The web client deliberately avoids starting every expensive request at exactly the same instant.

Heavy astronomy work is progressively scheduled, while the API also applies short-lived request sharing and bounded admission control. This is designed to keep the free hosted service responsive when several users open Live Sky together.

The current production capacity programme has validated 50 simultaneous production-style Live Sky users with zero server errors during the accepted test gate.

## 12. Privacy

NightAzimuth currently has no user-account system.

Observer coordinates are sent only where needed for location-dependent calculations. External providers used by the backend may infer the general geographic area represented by a request.

Do not post private observing coordinates, credentials, API keys or other sensitive information in public GitHub issues.

## 13. If the API appears unavailable

The browser frontend uses:

`https://api.nightazimuth.co.uk`

If Live Sky has missing data:

1. check that the page itself loaded normally
2. try a normal refresh once
3. verify the observer coordinates are valid
4. check whether only one data layer is affected or the entire application
5. if reporting a bug, include the affected layer, approximate time and visible error message without including private coordinates

Transient ADS-B failures should not normally blank an already usable aircraft scene because the backend includes short-lived sharing/retry/fallback protection.

## 14. Accuracy and safety

NightAzimuth is an observing/identification aid. It is **not** an authoritative aviation, navigation, collision-avoidance, emergency-response or safety system.

Aircraft positions can be delayed or incomplete. Satellite predictions depend on orbital source freshness. Weather providers cannot model all local conditions. Always use appropriate authoritative sources where safety depends on the answer.

## 15. Legacy Windows build

Historical GitHub releases include a Windows `.exe`. Those files remain available so the development history is not erased, but the current web application has moved substantially beyond the desktop release in functionality, deployment and scalability.

For normal use, choose the web application.
