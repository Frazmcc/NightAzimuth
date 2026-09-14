from __future__ import annotations

import json

from nightazimuth.appearance import AppearancePreferenceStore, normalise_appearance_mode
from nightazimuth.gui import configure_supported_options


def test_appearance_mode_normalisation() -> None:
    assert normalise_appearance_mode("dark") == "Dark"
    assert normalise_appearance_mode(" LIGHT ") == "Light"
    assert normalise_appearance_mode("System") == "System"
    assert normalise_appearance_mode("unknown") == "System"


def test_appearance_store_defaults_to_system(tmp_path) -> None:
    store = AppearancePreferenceStore(tmp_path / "preferences.json")

    assert store.load() == "System"


def test_appearance_store_round_trip(tmp_path) -> None:
    path = tmp_path / "preferences.json"
    store = AppearancePreferenceStore(path)

    assert store.save("Dark") == "Dark"
    assert store.load() == "Dark"
    assert json.loads(path.read_text(encoding="utf-8")) == {"appearance": "Dark"}


def test_appearance_store_handles_invalid_json(tmp_path) -> None:
    path = tmp_path / "preferences.json"
    path.write_text("{not valid json", encoding="utf-8")

    assert AppearancePreferenceStore(path).load() == "System"


def test_widget_appearance_skips_unsupported_options() -> None:
    class FakeWidget:
        def __init__(self) -> None:
            self.configured: dict[str, object] = {}

        def keys(self) -> tuple[str, ...]:
            return ("foreground",)

        def configure(self, **options: object) -> None:
            self.configured.update(options)

    widget = FakeWidget()
    configure_supported_options(  # type: ignore[arg-type]
        widget,
        background="#111827",
        foreground="#e5e7eb",
    )

    assert widget.configured == {"foreground": "#e5e7eb"}
