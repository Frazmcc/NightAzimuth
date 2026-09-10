# NightAzimuth

Location-based live satellite tracking with directional sky identification and near-real-time cloud awareness.

## Project status

**Stage 3 — Core satellite tracking implementation**

NightAzimuth is being developed using a stage-gated process. Work only progresses to the next stage after the current stage has been reviewed and approved.

Stage 3 adds the first functional tracking layer: observer coordinates, current time, CelesTrak OMM JSON orbital data, local caching, SGP4 propagation through Skyfield, and calculation of satellites geometrically above the observer's horizon.

Weather, cloud analysis, true visual visibility, pass prediction, graphical sky maps, and camera support are not implemented in this stage.

## Initial goal

NightAzimuth will become a local application that uses an observer's location and current time to determine which satellites are above the horizon, where they are in the sky, and which are realistically likely to be visible.

Visibility will eventually combine orbital geometry, solar illumination, astronomical darkness, and the freshest practical directional cloud information available for the part of the sky being viewed.

## Documentation

- [`docs/STAGE_1_REQUIREMENTS.md`](docs/STAGE_1_REQUIREMENTS.md) — approved product requirements.
- [`docs/STAGE_3_IMPLEMENTATION.md`](docs/STAGE_3_IMPLEMENTATION.md) — current core-tracking implementation and acceptance condition.

## Stage 3 command-line verification

Copy the example configuration to a local file, enter the observer coordinates, install the project, and run:

```bash
python -m pip install -e .
nightazimuth --config config/nightazimuth.toml
```

The output is sorted by elevation and includes satellite name, NORAD catalogue ID, azimuth, elevation, and range.

Being above the horizon does **not** mean the satellite is actually visible. That distinction is intentionally preserved for later stages.

## Project layout

```text
NightAzimuth/
├── config/
│   └── nightazimuth.example.toml
├── docs/
│   ├── STAGE_1_REQUIREMENTS.md
│   └── STAGE_3_IMPLEMENTATION.md
├── src/
│   └── nightazimuth/
│       ├── __init__.py
│       ├── celestrak.py
│       ├── cli.py
│       ├── config.py
│       └── tracker.py
├── tests/
│   ├── __init__.py
│   ├── test_celestrak.py
│   └── test_config.py
├── .gitignore
├── pyproject.toml
└── README.md
```

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

The Stage 3 implementation uses Python 3.11+, Skyfield for satellite propagation/coordinate calculations, and HTTPX for orbital-data retrieval.

## Licence

No licence has been selected yet. The repository remains private while the project is under initial development.
