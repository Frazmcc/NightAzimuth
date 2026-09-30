# Stage 5 — Windows GUI and Saved Locations

## Scope

Stage 5 introduces the first graphical Windows application shell for NightAzimuth and implements persistent saved observing locations.

Implemented in this stage:

- native Windows desktop GUI using Tkinter
- graphical NightAzimuth application shell
- Settings window
- create named observing locations
- edit existing locations
- delete locations
- select the active location
- quick switching from the main-window location dropdown
- remember the most recently selected location
- store latitude, longitude, and altitude per saved location
- validate latitude and longitude ranges
- persist settings under the Windows user application-data area
- package the GUI as a windowed `NightAzimuth.exe` with no console window
- automated tests for saved-location persistence

## Local settings storage

Saved locations are stored per Windows user in:

```text
%APPDATA%\NightAzimuth\locations.json
```

This file is outside the Git repository and is not committed to source control.

## Current limitation

The Stage 5 GUI is an application shell and settings interface. The live satellite table, sky map, pass view, weather, and cloud layers are not yet rendered inside the GUI.

The existing command-line tracking engine remains available separately during development.

## View from source

From `C:\git\NightAzimuth`:

```powershell
git checkout stage-5-gui-settings
git pull
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python -m nightazimuth.gui
```

## Build and run the Windows EXE

```powershell
.\build_windows.ps1
.\dist\NightAzimuth.exe
```

## Acceptance condition

Stage 5 is complete when the user confirms that the GUI launches correctly, saved locations can be added/edited/switched, and the selected location persists between launches.
