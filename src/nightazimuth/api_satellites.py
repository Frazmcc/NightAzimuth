from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
import logging

from fastapi import APIRouter, HTTPException, Query

from .celestrak import CelestrakClient, CelestrakError
from .config import ObserverConfig
from .tracker import SatelliteTracker

router = APIRouter(prefix="/api/v1/satellites", tags=["satellites"])
logger = logging.getLogger(__name__)

_API_CACHE = Path("data/cache/api")


@router.get("")
def satellites(
    latitude: float = Query(ge=-90.0, le=90.0),
    longitude: float = Query(ge=-180.0, le=180.0),
    altitude_m: float = Query(default=0.0),
    minimum_elevation_deg: float = Query(default=0.0, ge=0.0, le=90.0),
    group: str = Query(default="ACTIVE", min_length=1, max_length=64),
) -> dict[str, object]:
    """Return current satellites above the observer's requested horizon."""

    observed_at = datetime.now(UTC)
    observer = ObserverConfig(
        latitude=latitude,
        longitude=longitude,
        altitude_m=altitude_m,
    )
    client = CelestrakClient(_API_CACHE)

    try:
        elements = client.load_group(group)
    except (CelestrakError, ValueError) as exc:
        logger.warning("Satellite provider unavailable: %s", exc)
        raise HTTPException(status_code=503, detail="Satellite data is temporarily unavailable") from exc

    tracker = SatelliteTracker(observer)
    positions = tracker.positions_above_horizon(
        elements,
        minimum_elevation_deg=minimum_elevation_deg,
        at=observed_at,
    )

    return {
        "observed_at": observed_at.isoformat(),
        "source": "CelesTrak",
        "group": group.strip().upper(),
        "observer": {
            "latitude_deg": latitude,
            "longitude_deg": longitude,
            "altitude_m": altitude_m,
        },
        "minimum_elevation_deg": minimum_elevation_deg,
        "count": len(positions),
        "satellites": [asdict(position) for position in positions],
    }
