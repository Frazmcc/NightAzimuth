from __future__ import annotations

from pathlib import Path
import re


WEB = Path(__file__).resolve().parents[1] / "web"


def _checkbox_checked(html: str, attribute: str, name: str) -> bool:
    match = re.search(
        rf'<input type="checkbox" {attribute}="{re.escape(name)}"(?P<checked> checked)?>',
        html,
    )
    assert match is not None, f"Missing {attribute}={name} checkbox"
    return match.group("checked") is not None


def test_live_sky_startup_layer_defaults_match_basic_view() -> None:
    html = (WEB / "index.html").read_text(encoding="utf-8")

    assert _checkbox_checked(html, "data-layer", "stars") is True
    assert _checkbox_checked(html, "data-label-layer", "stars") is True
    assert _checkbox_checked(html, "data-layer", "constellations") is False
    assert _checkbox_checked(html, "data-layer", "galaxies") is True
    assert _checkbox_checked(html, "data-label-layer", "galaxies") is False
    assert _checkbox_checked(html, "data-layer", "planets") is True
    assert _checkbox_checked(html, "data-label-layer", "planets") is True
    assert _checkbox_checked(html, "data-layer", "airports") is True
    assert _checkbox_checked(html, "data-label-layer", "airports") is True
    assert _checkbox_checked(html, "data-layer", "aircraft") is True
    assert _checkbox_checked(html, "data-label-layer", "aircraft") is True
    assert _checkbox_checked(html, "data-layer", "satellites") is True
    assert _checkbox_checked(html, "data-label-layer", "satellites") is False

    defaults = (WEB / "layer-defaults.js").read_text(encoding="utf-8")
    assert "constellations:false" in defaults
    assert "galaxies:false" in defaults
    assert "satellites:false" in defaults
    assert '<script src="./layer-defaults.js?v=22.5.4"></script>' in html
