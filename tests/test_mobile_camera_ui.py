from pathlib import Path


HTML = Path("web/index.html").read_text(encoding="utf-8")
MOBILE_JS = Path("web/mobile-camera.js").read_text(encoding="utf-8")


def test_mobile_camera_helper_loads_after_primary_camera_settings() -> None:
    camera_index = HTML.index('./camera-settings.js?v=21.11.19')
    mobile_index = HTML.index('./mobile-camera.js?v=21.11.20')
    assert mobile_index > camera_index


def test_mobile_camera_is_settings_only_and_hidden_on_non_mobile_browsers() -> None:
    assert 'const details=document.querySelector("#camera-settings-details")' in MOBILE_JS
    assert 'panel.id="mobile-camera-settings"' in MOBILE_JS
    assert "panel.hidden=!likelyMobile" in MOBILE_JS
    assert 'cameraStatus.insertAdjacentElement("afterend",panel)' in MOBILE_JS
    assert 'id="mobile-camera-settings"' not in HTML.split('id="settings-panel"', 1)[0]


def test_mobile_mode_explicitly_requests_rear_facing_camera() -> None:
    assert 'facingMode:{ideal:"environment"}' in MOBILE_JS
    assert 'startRearButton.addEventListener("click",startRearCamera)' in MOBILE_JS
    assert "startRearCamera();" not in MOBILE_JS
    assert "navigator.mediaDevices.getUserMedia" in MOBILE_JS


def test_mobile_camera_does_not_request_motion_permission_on_page_load() -> None:
    assert 'motionButton.addEventListener("click",enableHandheldTracking)' in MOBILE_JS
    assert 'stableSolveButton.addEventListener("click",captureAndSolveWhenStable)' in MOBILE_JS
    assert 'requestPermission==="function"' in MOBILE_JS
    assert "Promise.all(requests)" in MOBILE_JS

    # The steady-capture button is also an explicit user action, so its handler
    # is allowed to request sensors through waitUntilStable(). What must not
    # exist is an eager top-level invocation after event wiring during page load.
    assert "const sensors=await enableHandheldTracking();" in MOBILE_JS
    runtime_initialisation = MOBILE_JS[MOBILE_JS.index('fovInput.addEventListener("change"'):]
    assert "\nenableHandheldTracking();" not in runtime_initialisation
    assert "\nstartRearCamera();" not in runtime_initialisation
    assert "\ncaptureAndSolveWhenStable();" not in runtime_initialisation


def test_handheld_capture_waits_for_a_stable_window() -> None:
    assert "const STABLE_RATE_DEG_S=1.5" in MOBILE_JS
    assert "const STABLE_DWELL_MS=750" in MOBILE_JS
    assert "const STABLE_WAIT_MS=8000" in MOBILE_JS
    assert "if(stableSince&&Date.now()-stableSince>=STABLE_DWELL_MS)return true" in MOBILE_JS
    assert 'stableSolveButton.textContent="Capture & solve when steady"' in MOBILE_JS
    assert "captureButton.click()" in MOBILE_JS
    assert "solveButton.click()" in MOBILE_JS


def test_handheld_motion_invalidates_stale_plate_alignment() -> None:
    assert "LOCK_INVALIDATION_RATE_DEG_S=5" in MOBILE_JS
    assert "function invalidateMovedHandheldSolution()" in MOBILE_JS
    assert "delete window.NIGHTAZIMUTH_CAMERA_SOLUTION" in MOBILE_JS
    assert "Phone moved after the plate solve" in MOBILE_JS


def test_mobile_solution_carries_handheld_metadata() -> None:
    assert 'window.addEventListener("nightazimuth:camera-solved"' in MOBILE_JS
    assert "event.detail.handheld=true" in MOBILE_JS
    assert "event.detail.motionDegPerSec" in MOBILE_JS
    assert "event.detail.orientationSnapshot" in MOBILE_JS
    assert "window.NIGHTAZIMUTH_HANDHELD_STATE" in MOBILE_JS


def test_mobile_fov_estimate_reuses_existing_plate_solver_geometry() -> None:
    assert 'const DEFAULT_MOBILE_HFOV_DEG=65' in MOBILE_JS
    assert 'const sensor=35.8' in MOBILE_JS
    assert "const focal=sensor/(2*Math.tan(hfov*Math.PI/360))" in MOBILE_JS
    assert 'profileInput.value="Mobile rear camera"' in MOBILE_JS
