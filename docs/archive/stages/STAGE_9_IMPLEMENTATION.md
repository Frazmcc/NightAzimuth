# Stage 9 — Projected Tracks and Direction of Travel

Status: Ready for user testing

Created by Logic Lurker © 2026

## Scope

Stage 9 makes the practical Live view more useful for real observing by showing where a tracked satellite is expected to move over the next few minutes.

Implemented:

- short-horizon topocentric track prediction using the same OMM orbital data and observer coordinates as the live tracker
- default prediction window of 3 minutes
- predicted samples every 30 seconds
- dashed projected path in the Live view
- arrow at the end of the visible projected path to show direction of travel
- selected-satellite details show current-to-future azimuth and elevation
- predictions are calculated only for satellites currently relevant to the live above-horizon set
- prediction work runs in a background thread so the GUI remains responsive
- prediction failure does not interrupt the working current-position tracker
- the all-sky Sky map remains unchanged

## Purpose

The Live view should answer two questions at a glance:

1. Where is the satellite now?
2. Where should I look next?

The existing upcoming-pass table remains the long-horizon planning tool. Stage 9's short track is intentionally limited to a few minutes so that it stays readable when observing outdoors.

## Deferred

Stage 9 does not yet add:

- brightness or apparent magnitude modelling
- weather/cloud analysis
- directional cloud estimation
- camera overlay
- aircraft or meteor matching
- unidentified-track classification

These remain for later approved stages.
