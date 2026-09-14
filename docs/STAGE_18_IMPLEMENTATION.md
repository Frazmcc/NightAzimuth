# Stage 18 — GUI Performance and Responsive Map Sizing

Status: **In development — not ready for user acceptance**

## Goal

Stage 18 stabilises the existing desktop interface before camera work begins. It focuses on responsive map sizing, reduced redraw/network churn, and a simpler observed-weather animation.

## Approved direction

- retain the observed cloud and rain-radar timeline covering the previous 24 hours
- remove manual play, pause, step, scrub and speed controls
- start observed-weather playback automatically when the Weather map loads
- loop continuously from 24 hours ago through the latest frame
- keep forecast map choices separate from observed playback
- scale the rendered map to the available window without downloading new tiles for every resize
- debounce resize work so dragging the window remains responsive
- keep all existing dark-mode, cloud-overlay, brightness and privacy behaviour

## Safety and accuracy

The timeline remains labelled as observed history. Forecast frames are never inserted into the loop. Historical radar is shown only where the provider has a sufficiently close frame; unavailable historical radar is not fabricated.

## Acceptance gate

This stage will remain on a draft pull request until automated checks, the Windows build, local visual testing and explicit user approval are complete.
