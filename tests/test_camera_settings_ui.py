from pathlib import Path


HTML = Path("web/index.html").read_text(encoding="utf-8")
JS = Path("web/camera-settings.js").read_text(encoding="utf-8")
SOLVER_JS = Path("web/camera-plate-solver.js").read_text(encoding="utf-8")
WORKER_JS = Path("web/camera-plate-worker.js").read_text(encoding="utf-8")


def test_camera_configuration_lives_inside_settings_panel() -> None:
    settings_start = HTML.index('id="settings-panel"')
    settings_end = HTML.index('id="forecast-screen"')
    settings_html = HTML[settings_start:settings_end]

    for control_id in (
        "camera-settings-details",
        "camera-device",
        "camera-detect",
        "camera-profile",
        "camera-focal-length",
        "camera-sensor-width",
        "camera-start",
        "camera-stop",
        "camera-capture-frame",
        "camera-preview",
        "camera-frame",
    ):
        assert f'id="{control_id}"' in settings_html

    live_sky_html = HTML[:settings_start]
    for control_id in (
        "camera-device",
        "camera-detect",
        "camera-profile",
        "camera-start",
        "camera-preview",
        "camera-frame",
    ):
        assert f'id="{control_id}"' not in live_sky_html


def test_camera_permission_is_not_requested_on_page_load() -> None:
    assert 'detectButton.addEventListener("click",populateDevices)' in JS
    assert 'startButton.addEventListener("click",startCamera)' in JS
    assert "populateDevices();" not in JS
    assert "startCamera();" not in JS
    assert "getUserMedia({video:true,audio:false})" in JS
    assert "activeStream=await navigator.mediaDevices.getUserMedia" in JS


def test_a7s_profile_is_the_default_camera_profile() -> None:
    assert 'value="Sony A7S Gen 1"' in HTML
    assert '||"Sony A7S Gen 1"' in JS
    assert 'id="camera-sensor-width"' in HTML
    assert 'value="35.8"' in HTML


def test_saved_camera_device_is_restored_without_requesting_permission() -> None:
    assert 'const savedDeviceId=localStorage.getItem(DEVICE_KEY)||""' in JS
    assert 'savedOption.textContent="Saved camera / capture device"' in JS
    assert "savedOption.selected=true" in JS


def test_camera_stream_is_stopped_when_settings_close_without_losing_solution() -> None:
    assert "if(settingsPanel.hidden&&activeStream)stopCamera({preserveSolution:true})" in JS
    assert 'window.addEventListener("beforeunload",()=>stopCamera({preserveSolution:true}))' in JS


def test_restarting_camera_invalidates_old_alignment() -> None:
    assert 'invalidateSolution("Camera started or restarted. Capture and solve a new frame before using alignment.")' in JS


def test_capture_frame_reads_pixels_once_before_plate_matching() -> None:
    assert "function detectBrightPoints(imageData,width,height)" in JS
    assert JS.count("context.getImageData(0,0,width,height)") == 1
    assert "bright point candidate" in JS
    assert "Ready to compare the captured pattern with the live star catalogue." in JS


def test_plate_matching_controls_are_created_inside_existing_camera_settings_flow() -> None:
    assert 'solveButton.id="camera-solve-frame"' in JS
    assert 'solveActions.insertAdjacentElement("afterend",solutionStatus)' in JS
    assert 'solveButton.addEventListener("click",solveCapturedFrame)' in JS
    assert 'script.src="./camera-plate-solver.js?v=21.11.18"' in JS
    assert '/api/v1/sky' in JS
    assert 'window.NIGHTAZIMUTH_CAMERA_SOLUTION' in JS
    assert 'nightazimuth:camera-solved' in JS


def test_plate_solver_uses_saved_observer_not_unsaved_settings_inputs() -> None:
    assert 'const LATITUDE_KEY="nightazimuth.latitude"' in JS
    assert 'const LONGITUDE_KEY="nightazimuth.longitude"' in JS
    assert "const saved=savedObserver()" in JS
    assert "latitudeInput" not in JS
    assert "longitudeInput" not in JS


def test_plate_solver_runs_in_worker_when_available() -> None:
    assert 'new Worker("./camera-plate-worker.js?v=21.11.18")' in JS
    assert 'importScripts("./camera-plate-solver.js?v=21.11.18")' in WORKER_JS
    assert "self.NightAzimuthPlateSolver" in WORKER_JS
    assert "worker.postMessage(payload)" in JS


def test_plate_solver_requires_a_strong_multi_star_match_before_locking() -> None:
    assert "best.matches.length>=5" in SOLVER_JS
    assert "A possible pattern was found but it is not strong enough to lock" in SOLVER_JS
    assert "estimatedHfovDeg" in SOLVER_JS
    assert "azimuthDeg" in SOLVER_JS
    assert "elevationDeg" in SOLVER_JS
    assert "rollDeg" in SOLVER_JS
