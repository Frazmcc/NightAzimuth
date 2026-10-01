from pathlib import Path
import tomllib

from nightazimuth import __version__


def test_runtime_and_package_versions_match() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    assert __version__ == project["project"]["version"] == "1.1.0-rc1"


def test_release_notes_exist_for_current_version() -> None:
    web_release_notes = Path(f"docs/releases/v{__version__}.md")
    archived_release_notes = Path(
        f"docs/archive/releases/RELEASE_NOTES_v{__version__}.md"
    )
    assert web_release_notes.is_file() or archived_release_notes.is_file()
