from pathlib import Path


VIDEO_JS = Path("web/video-source-integration.js").read_text(encoding="utf-8")
LAYER_JS = Path("web/layer-defaults.js").read_text(encoding="utf-8")


def test_yolobox_uvc_is_a_first_class_video_source() -> None:
    assert 'option value="yolobox">YoloBox UVC' in VIDEO_JS
    assert "yolobox|yololiv|yolo\\s*box" in VIDEO_JS
    assert "preferYoloBox" in VIDEO_JS
    assert 'localStorage.setItem(DEVICE_KEY,preferred.value)' in VIDEO_JS
    assert "preview, frame capture and plate solving local" in VIDEO_JS


def test_video_source_wording_and_direct_camera_mode_are_available() -> None:
    assert 'option value="direct">Direct camera / webcam' in VIDEO_JS
    assert 'detectButton.textContent="Detect video sources"' in VIDEO_JS
    assert "HDMI capture device" in VIDEO_JS


def test_network_bridge_modes_are_configurable_without_claiming_direct_browser_support() -> None:
    for protocol in ("rtsp", "srt", "rtmp", "ndi"):
        assert f'option value="{protocol}"' in VIDEO_JS
    assert 'option value="network">Network stream bridge' in VIDEO_JS
    assert 'return url.protocol==="https:"?url.href:null' in VIDEO_JS
    assert "not browser playback formats" in VIDEO_JS
    assert "For live preview, capture and plate solving today, use YoloBox UVC" in VIDEO_JS
    assert "preview.src=url" not in VIDEO_JS


def test_network_mode_disables_camera_actions_instead_of_bypassing_csp() -> None:
    assert "startButton.disabled=true" in VIDEO_JS
    assert "stopButton.disabled=true" in VIDEO_JS
    assert "captureButton.disabled=true" in VIDEO_JS
    assert "browser bridge saved" in VIDEO_JS


def test_dynamic_video_source_controls_satisfy_dom_contract() -> None:
    for element_id in (
        "video-source-mode",
        "network-protocol-label",
        "network-source-protocol",
        "network-url-label",
        "network-playback-url",
        "video-source-help",
    ):
        assert f'.id="{element_id}"' in VIDEO_JS


def test_video_source_integration_is_loaded_with_a_cache_version() -> None:
    assert 'videoSources.src="./video-source-integration.js?v=21.11.26"' in LAYER_JS
