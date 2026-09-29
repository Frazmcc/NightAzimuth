from __future__ import annotations

import logging
from dataclasses import asdict
from pathlib import Path
from time import perf_counter

from fastapi import APIRouter, HTTPException, Query, Response

from .config import ObserverConfig
from .star_field import StarFieldEngine

router = APIRouter(prefix="/api/v1/sky", tags=["sky"])
_API_CACHE = Path("data/cache/api")
_LOGGER = logging.getLogger("uvicorn.error")


@router.get("")
def sky(
    response: Response,
    latitude: float = Query(ge=-90.0, le=90.0),
    longitude: float = Query(ge=-180.0, le=180.0),
    altitude_m: float = Query(default=0.0),
) -> dict[str, object]:
    """Return the real celestial sky above an observer."""
    request_started = perf_counter()
    observer = ObserverConfig(latitude=latitude, longitude=longitude, altitude_m=altitude_m)

    try:
        # Share the Skyfield cache with observing guidance so de421.bsp is not
        # downloaded/loaded independently by two hosted API paths.
        engine_started = perf_counter()
        engine = StarFieldEngine(observer, _API_CACHE / "skyfield")
        engine_init_ms = (perf_counter() - engine_started) * 1000.0

        snapshot_started = perf_counter()
        snapshot = engine.snapshot()
        snapshot_ms = (perf_counter() - snapshot_started) * 1000.0
    except (OSError, ValueError, KeyError) as exc:
        elapsed_ms = (perf_counter() - request_started) * 1000.0
        _LOGGER.warning(
            "sky_request_failed total_ms=%.1f error=%s",
            elapsed_ms,
            type(exc).__name__,
        )
        raise HTTPException(status_code=503, detail="Celestial sky is temporarily unavailable") from exc

    serialization_started = perf_counter()
    payload = {
        "calculated_at": snapshot.calculated_at.isoformat(),
        "observer": {"latitude_deg": latitude, "longitude_deg": longitude, "altitude_m": altitude_m},
        "stars": [asdict(item) for item in snapshot.stars],
        "planets": [asdict(item) for item in snapshot.planets],
        "galaxies": [asdict(item) for item in snapshot.galaxies],
        "constellation_lines": [asdict(item) for item in snapshot.constellation_lines],
    }
    serialization_ms = (perf_counter() - serialization_started) * 1000.0
    total_ms = (perf_counter() - request_started) * 1000.0

    response.headers["Server-Timing"] = (
        f"engine_init;dur={engine_init_ms:.1f}, "
        f"snapshot;dur={snapshot_ms:.1f}, "
        f"serialize;dur={serialization_ms:.1f}, "
        f"total;dur={total_ms:.1f}"
    )

    _LOGGER.info(
        "sky_request total_ms=%.1f engine_init_ms=%.1f snapshot_ms=%.1f "
        "serialization_ms=%.1f stars=%d planets=%d galaxies=%d constellation_lines=%d",
        total_ms,
        engine_init_ms,
        snapshot_ms,
        serialization_ms,
        len(snapshot.stars),
        len(snapshot.planets),
        len(snapshot.galaxies),
        len(snapshot.constellation_lines),
    )
    return payload
