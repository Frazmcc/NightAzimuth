from pathlib import Path


HTML = Path("web/index.html").read_text(encoding="utf-8")
JS = Path("web/camera-settings.js").read_text(encoding="utf-8")


def test_camera_configuration_lives_inside_settings_panel() -> None:
    settings_start = HTML.index('id="settings-panel"')
    settings_end = HTML.index('id="forecast-screen"')
    settings_html = HTML[settings_start:settings_end]

    assert 'id="camera-settings-details"' in settings_html
    assert 'id="camera-device"' in settings_html
    assert 'id="camera-detect"' in settings_html
    assert 'id="camera-profile"' in settings_html
    assert 'id="camera-focal-length"' in settings_html

    live_sky_html = HTML[:settings_start]
    assert 'id="camera-device"' not in live_sky_html
    assert 'id="camera-detect"' not in live_sky_html
    assert 'id="camera-profile"' not in live_sky_html


def test_camera_permission_is_not_requested_on_page_load() -> None:
    assert 'detectButton.addEventListener("click",populateDevices)' in JS
    assert "populateDevices();" not in JS
    assert "getUserMedia({video:true,audio:false})" in JS


def test_a7s_profile_is_the_default_camera_profile() -> None:
    assert 'value="Sony A7S Gen 1"' in HTML
    assert '||"Sony A7S Gen 1"' in JS
