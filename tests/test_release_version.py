from pathlib import Path
import tomllib

from nightazimuth import __version__


def test_runtime_and_package_versions_match() -> None:
    project = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    assert __version__ == project["project"]["version"] == "1.1.0-rc1"


def test_release_notes_exist_for_current_version() -> None:
    assert Path(f"RELEASE_NOTES_v{__version__}.md").is_file()
