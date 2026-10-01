from pathlib import Path


DEPTH_JS = Path("web/live-sky-depth.js").read_text(encoding="utf-8")
LAYERS_JS = Path("web/layer-defaults.js").read_text(encoding="utf-8")


def test_depth_uses_observer_centred_stereographic_projection() -> None:
    assert "function stereographicCoordinates" in DEPTH_JS
    assert "cameraZ=forward*Math.cos(centre)+up*Math.sin(centre)" in DEPTH_JS
    assert "2*cameraX/denominator" in DEPTH_JS
    assert "skyXY=perceptualXY" in DEPTH_JS


def test_depth_preserves_true_azimuth_elevation_visibility() -> None:
    assert "angularDifference(Number(az),Number(facing))" in DEPTH_JS
    assert "elevation<0||elevation>90" in DEPTH_JS
    assert "FLAT_SKY_XY(az,el,w,h)" in DEPTH_JS
    # Do not invent a second position from object range: range is metadata only.
    assert "rangeKm" in DEPTH_JS
    assert "rangeNearness" in DEPTH_JS
    assert "az+" not in DEPTH_JS
    assert "el+" not in DEPTH_JS


def test_depth_modes_default_to_natural_and_allow_fallback() -> None:
    assert 'return value==="flat"||value==="enhanced"?value:"natural"' in DEPTH_JS
    assert '<option value="natural">Natural</option>' in DEPTH_JS
    assert '<option value="enhanced">Enhanced</option>' in DEPTH_JS
    assert '<option value="flat">Flat</option>' in DEPTH_JS
    assert 'if(!base||depthMode()==="flat")return base' in DEPTH_JS


def test_horizon_airlight_and_peripheral_depth_are_rendered() -> None:
    assert "function drawAtmosphericDepth" in DEPTH_JS
    assert "createLinearGradient" in DEPTH_JS
    assert "createRadialGradient" in DEPTH_JS
    assert "perceptualXY((Number(facing)+off+360)%360,0,w,h)" in DEPTH_JS


def test_depth_metrics_expose_horizon_eccentricity_and_range_cues() -> None:
    assert "eccentricity" in DEPTH_JS
    assert "horizonProximity" in DEPTH_JS
    assert "rangeNearness" in DEPTH_JS
    assert "window.NightAzimuthDepth" in DEPTH_JS


def test_depth_module_loads_after_layout_with_a_versioned_asset() -> None:
    assert 'typeof verticalFovFor!=="function"||typeof skyXY!=="function"' in LAYERS_JS
    assert 'depth.src="./live-sky-depth.js?v=22.2.0"' in LAYERS_JS
    assert 'depth.dataset.nightazimuthDepth="true"' in LAYERS_JS
