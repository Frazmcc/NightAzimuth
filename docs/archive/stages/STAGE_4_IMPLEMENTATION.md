# Stage 4 — Astronomical Visibility and Pass Prediction

## Scope

Stage 4 extends the Stage 3 geometric tracker with astronomical visibility checks and upcoming pass prediction.

Implemented in this stage:

- determine whether the observer's sky is dark enough using configurable Sun altitude
- determine whether a satellite is illuminated by the Sun
- mark a satellite as potentially visible when both conditions are true
- preserve the distinction between potentially visible and actually visible to the naked eye
- predict rise, culmination, and set times
- calculate maximum elevation for predicted passes
- configurable prediction horizon and minimum pass elevation
- command-line filters for potentially visible satellites and upcoming passes
- Windows EXE build support through PyInstaller
- safer CelesTrak handling, including VISUAL as the default group and 403-aware caching behaviour

## Important limitation

`potentially_visible` is an astronomical-geometry result only. It does not yet include cloud, haze, local obstruction, satellite magnitude, moonlight, or camera sensitivity.

Weather and directional cloud analysis remain a later stage.

## Current viewing commands

From `C:\git\NightAzimuth`:

```powershell
git checkout stage-4-visibility-passes
git pull
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

## Windows EXE build

Build with:

```powershell
.\build_windows.ps1
```

The executable is produced at:

```text
C:\git\NightAzimuth\dist\NightAzimuth.exe
```

Run it with:

```powershell
.\dist\NightAzimuth.exe --config config\nightazimuth.toml --passes
```

## Acceptance condition

Stage 4 is complete when the user confirms that live satellite loading and the Stage 4 command-line modes operate correctly on their Windows system and approves the stage for merge.
