# Stage 17 — Satellite Brightness and Apparent-Magnitude Estimates

Status: **Phase B in development — not ready for user acceptance**

## Goal

Stage 17 adds honest, source-labelled brightness estimates so NightAzimuth can distinguish favourable orbital geometry from a satellite that is plausibly bright enough to observe.

A magnitude value is never presented as measured photometry unless its source actually contains a measurement. Unknown brightness remains **Unknown** rather than being replaced by an unlabeled guess.

## Scientific boundary

General-purpose CelesTrak GP/OMM orbital elements provide orbit propagation data, not optical brightness. Radar cross-section is not interchangeable with visible reflective area and will not be silently treated as optical magnitude.

Satellite brightness varies with:

- observer-to-satellite range
- Sun-satellite-observer phase angle
- spacecraft shape and reflective materials
- attitude and solar-panel orientation
- diffuse and specular reflection
- short-lived flares or glints
- atmosphere and local observing conditions

Even modern diffuse/specular models leave meaningful scatter because spacecraft attitude and real shape matter. NightAzimuth must therefore display a range, confidence and source rather than false decimal precision.

## Phase A implementation

The first implementation slice adds a tested, provider-independent calculation core:

- Sun-satellite-observer phase angle from satellite-centred 3D vectors
- inverse-square range correction referenced to 1,000 km
- ideal Lambertian diffuse-sphere phase function
- explicit caller-supplied uncertainty
- brighter and fainter estimate bounds
- source and confidence fields carried with every estimate
- validation for invalid vectors, ranges and uncertainty

The calculation core remains separate so empirical catalogues and spacecraft-specific models can be added without coupling them to Tkinter.

## Phase B integration

The live calculation now derives the Sun–satellite–observer phase angle in a common geocentric frame. The selected-satellite panel displays that angle and carries an optional typed brightness estimate. Until a supported calibration is attached, it explicitly displays **Brightness: Unknown**.

This is deliberate. The published OneWeb value of 7.18 is a mean magnitude normalized to 1,000 km, not a full-phase magnitude; applying the generic Lambert correction to it as though it were full-phase would mislabel the model. OneWeb will use its published empirical phase function in the next slice.

## Formula

For an intrinsic full-phase magnitude `M0` at 1,000 km, range `r`, phase angle `alpha`, and Lambertian phase fraction `Phi`:

```text
Phi(alpha) = [sin(alpha) + (pi - alpha) * cos(alpha)] / pi

m = M0 + 5 * log10(r / 1000) - 2.5 * log10(Phi(alpha))
```

Angles are evaluated in radians inside the phase function. This is a baseline diffuse-sphere model, not a spacecraft-attitude or flare predictor.

## Calibration-source policy

Preferred evidence order:

1. current empirical photometry for the specific spacecraft or design generation
2. maintained observed intrinsic-magnitude catalogue keyed by NORAD ID
3. documented family-level photometric model with an explicitly wider uncertainty
4. **Unknown** when none of those is available

The historical QuickSat intrinsic-magnitude catalogue is useful evidence but is not sufficient as NightAzimuth's only source: the public file is old for modern constellations and its magnitude convention must be converted explicitly.

NightAzimuth will not use an assumed one-size-fits-all magnitude or radar cross-section fallback without visibly labelling it as a low-confidence prior.

## Planned Stage 17 UI

For supported satellites, the selected-object details and Live finder should eventually show:

- estimated apparent magnitude range
- phase angle
- estimate source
- confidence
- a warning that attitude-dependent flares are not predicted
- whether cloud/weather information further reduces observing plausibility

Unsupported objects should show **Brightness: Unknown**.

A Bright-only filter will not be enabled until coverage and uncertainty behaviour are good enough that it does not misleadingly hide potentially visible objects.

## Acceptance conditions

Stage 17 is complete only when:

- phase geometry is integrated with live satellite calculations
- empirical or documented calibration data has a clear update/cache policy
- unknown objects remain explicitly unknown
- estimates show a range, source and confidence
- cloud, darkness and brightness remain distinct factors in the explanation
- no paid provider, key or billing account is required
- no saved/test observer location is committed or packaged
- automated tests and the Windows build pass
- local visual testing is complete
- the user explicitly accepts the stage

## Technical references

- [CelesTrak: A New Way to Obtain GP Data](https://celestrak.org/NORAD/documentation/gp-data-formats.php)
- [McCants: Intrinsic Magnitude Definitions](https://www.mmccants.org/tles/intrmagdef.html)
- [Mallama: A Flat-Panel Brightness Model for Starlink Satellites](https://arxiv.org/abs/2003.07805)
- [Mallama: OneWeb Satellite Brightness Characterized from 80,000 Magnitudes](https://arxiv.org/abs/2203.05513)
- [Romero-Colmenares et al.: Diffuse and Specular Brightness Models Applied to LEO Satellites](https://www.aanda.org/articles/aa/full_html/2026/05/aa59054-26/aa59054-26.html)
