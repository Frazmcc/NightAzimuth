# NightAzimuth

Location-based live satellite tracking with directional sky identification and near-real-time cloud awareness.

## Project status

**Stage 2 — Project foundation**

NightAzimuth is being developed using a stage-gated process. Work only progresses to the next stage after the current stage has been reviewed and approved.

No satellite propagation, weather integration, camera support, or user interface is implemented yet.

## Initial goal

NightAzimuth will become a local application that uses an observer's location and current time to determine which satellites are above the horizon, where they are in the sky, and which are realistically likely to be visible.

Visibility will eventually combine orbital geometry, solar illumination, astronomical darkness, and the freshest practical directional cloud information available for the part of the sky being viewed.

## Stage 1 requirements

The approved Stage 1 requirements are recorded in [`docs/STAGE_1_REQUIREMENTS.md`](docs/STAGE_1_REQUIREMENTS.md).

## Planned project layout

```text
NightAzimuth/
├── config/
│   └── nightazimuth.example.toml
├── docs/
│   └── STAGE_1_REQUIREMENTS.md
├── src/
│   └── nightazimuth/
│       └── __init__.py
├── tests/
│   └── __init__.py
├── .gitignore
├── pyproject.toml
└── README.md
```

## Development principles

- Accuracy before features.
- Preserve the distinction between a satellite being geometrically above the horizon and actually being visible.
- Keep external data providers replaceable where practical.
- Never embed API keys or other secrets in source control.
- Make data age and confidence clear when displaying time-sensitive information.
- Add camera integration only after the core satellite tracker is reliable.
- Progress one approved stage at a time.

## Technology baseline

The initial implementation will use Python and a standard `src/` package layout. Specific astronomy, weather, storage, and UI libraries will be selected in a later approved stage.

## Licence

No licence has been selected yet. The repository remains private while the project is under initial development.
