from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

from .config import ObserverConfig
from .star_field import StarFieldEngine

router = APIRouter(prefix="/api/v1/sky", tags=["sky"])
_API_CACHE = Path("data/cache/api")


@router.get("")
def sky(
    latitude: float = Query(ge=-90.0, le=90.0),
    longitude: float = Query(ge=-180.0, le=180.0),
    altitude_m: float = Query(default=0.0),
) -> dict[str, object]:
    """Return the real celestial sky above an observer."""
    observer = ObserverConfig(latitude=latitude, longitude=longitude, altitude_m=altitude_m)
    try:
        # Share the Skyfield cache with observing guidance so de421.bsp is not
        # downloaded/loaded independently by two hosted API paths.
        snapshot = StarFieldEngine(observer, _API_CACHE / "skyfield").snapshot()
    except (OSError, ValueError, KeyError) as exc:
        raise HTTPException(status_code=503, detail="Celestial sky is temporarily unavailable") from exc
    return {
        "calculated_at": snapshot.calculated_at.isoformat(),
        "observer": {"latitude_deg": latitude, "longitude_deg": longitude, "altitude_m": altitude_m},
        "stars": [asdict(item) for item in snapshot.stars],
        "planets": [asdict(item) for item in snapshot.planets],
        "galaxies": [asdict(item) for item in snapshot.galaxies],
        "constellation_lines": [asdict(item) for item in snapshot.constellation_lines],
    }
