# Stage 20 — NightAzimuth Visual Experience

Stage 20 is a presentation layer over the validated Stage 19 tracking engines. It aims for a cinematic astronomical-instrument experience without replacing the provider, geometry, prediction, route, squawk or aircraft identity logic underneath it.

## Visual contract

- The application must fit within one visible page at the user's effective display resolution.
- The Live page must not require vertical scrolling.
- The application starts maximised and remains usable when resized smaller.
- Windows/Tk DPI scaling is authoritative for physical text size; Stage 20 adapts layout density from logical screen size rather than fighting the user's display scaling setting.
- Low-resolution workspaces reduce table rows, panel widths, padding and widget density before allowing content to overflow.
- High-DPI/4K displays grow naturally through OS scaling rather than multiplying font scaling twice.
- The sky remains the dominant visual surface.
- HUD elements are overlays and must not force the main layout larger.
- Stage 20 visual changes must remain independent of aircraft/satellite tracking accuracy.

## Current responsive targets

The layout metric tests explicitly cover:

- 1366 × 768 at 100% scaling
- 1920 × 1080 at 100% scaling
- 3840 × 2160 at 200% scaling
- high-DPI intermediate workspaces

The implementation also recalculates its density when the application window size changes.

## Resource contract

- Do not introduce a browser engine or heavyweight 3D renderer for visual polish.
- Prefer Tk Canvas/ttk vector primitives and cached/static visual assets.
- Avoid relayout work on every Configure event; responsive updates are debounced.
- Avoid expensive redraws when only HUD text changes.
- Slow non-essential HUD refresh work when the application is not normally visible.

## Next visual increments

1. Compact selected-object telemetry card.
2. Tracking brackets and refined selection state.
3. Shorter in-sky labels.
4. Fade-weighted projected tracks.
5. Observing-condition HUD.
6. Collapsible activity/contacts presentation without requiring page scroll.
7. Stronger hidden/minimised refresh throttling.
8. Night Vision and alternate astronomy-focused sensor styles.
