# NightAzimuth

Location-based live satellite tracking with directional sky identification and near-real-time cloud awareness.

## Project status

**Stage 4 — Astronomical visibility and pass prediction**

NightAzimuth is being developed using a stage-gated process. Work only progresses to the next stage after the current stage has been reviewed and approved.

Stage 4 extends the geometric tracker with astronomical visibility checks, upcoming pass prediction, safer CelesTrak handling, and reproducible Windows EXE builds.

Weather/cloud analysis, graphical sky maps, saved-location settings UI, camera support, aircraft matching, meteor detection, and unidentified-object classification are not implemented yet.

## Initial goal

NightAzimuth is a local application that uses an observer's location and current time to determine which satellites are above the horizon, where they are in the sky, and which are realistically likely to be visible.

Visibility will eventually combine orbital geometry, solar illumination, astronomical darkness, and the freshest practical directional cloud information available for the part of the sky being viewed.

## Documentation

- [`docs/STAGE_1_REQUIREMENTS.md`](docs/STAGE_1_REQUIREMENTS.md) — approved product requirements.
- [`docs/STAGE_3_IMPLEMENTATION.md`](docs/STAGE_3_IMPLEMENTATION.md) — core-tracking implementation.
- [`docs/STAGE_4_IMPLEMENTATION.md`](docs/STAGE_4_IMPLEMENTATION.md) — visibility, pass prediction, CelesTrak behaviour, and Windows EXE build instructions.

## Current command-line verification

From `C:\git\NightAzimuth`:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m nightazimuth.cli --config config\nightazimuth.toml
```

Potentially visible satellites only:

```powershell
python -m nightazimuth.cli --config config\nightazimuth.toml --visible-only
```

Upcoming passes:

```powershell
python -m nightazimuth.cli --config config\nightazimuth.toml --passes
```

## Windows EXE

Build the current application with:

```powershell
.\build_windows.ps1
```

The executable is written to:

```text
C:\git\NightAzimuth\dist\NightAzimuth.exe
```

Run it with:

```powershell
.\dist\NightAzimuth.exe --config config\nightazimuth.toml
```

or:

```powershell
.\dist\NightAzimuth.exe --config config\nightazimuth.toml --visible-only
.\dist\NightAzimuth.exe --config config\nightazimuth.toml --passes
```

## Current behaviour

The live satellite list includes name, NORAD catalogue ID, azimuth, elevation, range, whether the satellite is sunlit, whether the observer's sky is sufficiently dark, and whether the geometry is potentially favourable for visual observation.

`potentially visible` does **not** mean guaranteed naked-eye visibility. Cloud, haze, brightness/magnitude, local obstructions, moonlight, and other factors are not yet included.

Pass prediction provides rise, culmination, set time, and maximum elevation for upcoming passes within the configured prediction window.

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

The current implementation uses Python 3.11+, Skyfield for satellite propagation and astronomy calculations, HTTPX for orbital-data retrieval, and PyInstaller for Windows EXE packaging.

## Licence

No licence has been selected yet. The repository remains private while the project is under initial development.
