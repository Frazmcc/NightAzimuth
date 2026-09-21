from __future__ import annotations

import html
import os
from pathlib import Path
import subprocess
import tempfile
import webbrowser


RICKROLL_VIDEO_ID = "dQw4w9WgXcQ"
PRANK_DELAYS_MS = (0, 1400, 3000)
PRANK_DURATION_SECONDS = 22


def prank_delays_ms() -> tuple[int, ...]:
    return PRANK_DELAYS_MS


def _prank_html(instance: int) -> str:
    video_id = html.escape(RICKROLL_VIDEO_ID, quote=True)
    return f"""<!doctype html>
<html>
<head>
<meta charset=\"utf-8\">
<title>DON NOT PRESS</title>
<style>
html,body{{margin:0;width:100%;height:100%;background:#000;overflow:hidden;}}
iframe{{position:absolute;inset:0;width:100%;height:100%;border:0;}}
.warn{{position:fixed;left:50%;bottom:18px;transform:translateX(-50%);z-index:9;
font:700 28px/1.2 Segoe UI,Arial,sans-serif;color:#fff;text-shadow:0 2px 8px #000;
background:rgba(0,0,0,.55);padding:8px 16px;border-radius:7px;white-space:nowrap;}}
</style>
</head>
<body>
<iframe allow=\"autoplay; encrypted-media\"
 src=\"https://www.youtube.com/embed/{video_id}?autoplay=1&mute=0&controls=0&rel=0&start=0&end={PRANK_DURATION_SECONDS}\"></iframe>
<div class=\"warn\">I did warn you</div>
<script>setTimeout(() => window.close(), {PRANK_DURATION_SECONDS * 1000 + 1200});</script>
</body>
</html>"""


def _write_page(instance: int) -> Path:
    directory = Path(tempfile.gettempdir()) / "NightAzimuth" / "easter_egg"
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"do_not_press_{instance}.html"
    path.write_text(_prank_html(instance), encoding="utf-8")
    return path


def _edge_executable() -> str | None:
    candidates = (
        Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("PROGRAMFILES", "")) / "Microsoft/Edge/Application/msedge.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/Edge/Application/msedge.exe",
    )
    for candidate in candidates:
        if str(candidate) and candidate.is_file():
            return str(candidate)
    return None


def open_prank_instance(instance: int) -> None:
    """Open one short hosted-video prank window without bundling copyrighted media."""
    page = _write_page(instance)
    uri = page.as_uri()
    edge = _edge_executable()
    if edge:
        x = 100 + (instance - 1) * 85
        y = 100 + (instance - 1) * 60
        subprocess.Popen(  # noqa: S603
            [
                edge,
                f"--app={uri}",
                "--new-window",
                "--window-size=720,430",
                f"--window-position={x},{y}",
            ],
            close_fds=True,
        )
        return
    webbrowser.open_new(uri)
