# NightAzimuth

**Created by Logic Lurker © 2026**

Location-based live satellite tracking with directional sky identification and near-real-time cloud awareness.

## Project status

**Stage 6 — GUI live satellite data**

NightAzimuth is being developed using a stage-gated process. Work only progresses to the next stage after the current stage has been reviewed and approved.

Stage 6 connects the Windows GUI to the existing satellite-tracking engine. The selected saved location now drives live satellite calculations and upcoming pass prediction directly inside the application.

Weather/cloud analysis, radar-style sky maps, camera support, aircraft matching, meteor detection, and unidentified-object classification are not implemented yet.

## Initial goal

NightAzimuth is a local application that uses an observer's location and current time to determine which satellites are above the horizon, where they are in the sky, and which are realistically likely to be visible.

Visibility will eventually combine orbital geometry, solar illumination, astronomical darkness, and the freshest practical directional cloud information available for the part of the sky being viewed.

## Documentation

- [`docs/STAGE_1_REQUIREMENTS.md`](docs/STAGE_1_REQUIREMENTS.md) — approved product requirements.
- [`docs/STAGE_3_IMPLEMENTATION.md`](docs/STAGE_3_IMPLEMENTATION.md) — core-tracking implementation.
- [`docs/STAGE_4_IMPLEMENTATION.md`](docs/STAGE_4_IMPLEMENTATION.md) — astronomical visibility, pass prediction, CelesTrak behaviour, and Windows EXE build support.
- [`docs/STAGE_5_IMPLEMENTATION.md`](docs/STAGE_5_IMPLEMENTATION.md) — Windows GUI shell and saved location profiles.
- [`docs/STAGE_6_IMPLEMENTATION.md`](docs/STAGE_6_IMPLEMENTATION.md) — live satellite and pass data inside the GUI.
- [`CREDITS.md`](CREDITS.md) — creator and third-party credits.

## Windows GUI

From `C:\git\NightAzimuth`:

```powershell
git checkout main
git pull
.\build_windows.ps1
.\dist\NightAzimuth.exe
```

The GUI provides:

- saved observing locations
- quick location switching
- live satellites above the horizon
- azimuth, elevation, and range
- sunlit and dark-sky indicators
- potential astronomical visibility
- upcoming passes for the next 24 hours
- rise, peak, set time, and maximum elevation
- manual refresh

Changing the selected location refreshes the calculations for that observer position.

## Saved application data

Location profiles are stored under:

```text
%APPDATA%\NightAzimuth\locations.json
```

Orbital and Skyfield cache data are stored under:

```text
%APPDATA%\NightAzimuth\cache\
```

## Visibility terminology

`Potential` means the satellite is illuminated by the Sun while the observer's sky is sufficiently dark. It does **not** mean guaranteed naked-eye visibility.

Cloud, haze, brightness/magnitude, local obstructions, moonlight, and camera sensitivity are not yet included in the result.

## Development principles

- Accuracy before features.
- Preserve the distinction between a satellite being geometrically above the horizon and actually being visible.
- Use modern OMM orbital data rather than assuming legacy TLE-only identifiers.
- Keep external data providers replaceable where practical.
- Never embed API keys or other secrets in source control.
- Make data age and confidence clear when displaying time-sensitive information.
- Add camera integration only after the core satellite tracker is reliable.
- Progress one approved stage at a time.

## Technology baseline

The current implementation uses Python 3.11+, Tkinter for the native desktop GUI, Skyfield for satellite propagation and astronomy calculations, HTTPX for orbital-data retrieval, and PyInstaller for Windows EXE packaging.

## Credits

**Created by Logic Lurker © 2026**

See [`CREDITS.md`](CREDITS.md) for project and third-party attribution information.

## Licence

No licence has been selected yet. The repository remains private while the project is under initial development.
