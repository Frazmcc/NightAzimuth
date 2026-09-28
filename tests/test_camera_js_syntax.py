from __future__ import annotations

import subprocess


def test_camera_javascript_parses() -> None:
    for path in ("web/camera-settings.js", "web/camera-plate-solver.js"):
        completed = subprocess.run(
            ["node", "--check", path],
            check=False,
            capture_output=True,
            text=True,
        )
        assert completed.returncode == 0, completed.stderr or completed.stdout
