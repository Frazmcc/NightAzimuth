from __future__ import annotations

from datetime import UTC, datetime

from fastapi import FastAPI

from . import __version__
from .api_aircraft import router as aircraft_router
from .api_observing import router as observing_router
from .api_weather import router as weather_router
from .api_satellites import router as satellites_router

API_VERSION = "v1"

app = FastAPI(
    title="NightAzimuth API",
    version=__version__,
    description="Versioned HTTP interface for NightAzimuth.",
)
app.include_router(satellites_router)
app.include_router(aircraft_router)
app.include_router(weather_router)
app.include_router(observing_router)


@app.get(f"/api/{API_VERSION}/health", tags=["system"])
def health() -> dict[str, str]:
    """Return process health without contacting any upstream provider."""

    return {
        "status": "ok",
        "api_version": API_VERSION,
        "application_version": __version__,
        "timestamp": datetime.now(UTC).isoformat(),
    }
