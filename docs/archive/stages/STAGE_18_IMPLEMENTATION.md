# Stage 18 — GUI Performance and Responsive Map Sizing

Status: **Approved and merged — 14 September 2026**

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

Stage 18 remained on a draft pull request until automated checks, the Windows build, local visual testing and explicit user approval were complete.

## Implemented result

- the initial window uses approximately 90% of the available display, subject to sensible size caps
- the Weather map expands and contracts with its panel while preserving aspect ratio
- window resize events are debounced for 120 ms
- resizing reuses the in-memory rendered map and does not trigger tile downloads
- manual animation controls have been removed
- observed playback starts automatically at 24 hours ago
- the frame after Now loops back to 24 hours ago
- the next animation frame is scheduled only after the current render succeeds or fails, preventing background-thread backlog

## Automated validation

- 114 tests passed
- Ruff correctness checks passed
- Windows PyInstaller build passed
- release output allowlist passed

Local visual testing was completed and the stage was explicitly approved before merge.

## Layout revision after visual review

The Weather map was still too small because the 24-hour and 7-day planner panels consumed most of the tab height. Both planning sections now live in a dedicated **Forecast** tab. The Weather map tab is reserved for the map, layer/time controls and compact map status, allowing the radar image to use the main content area.
