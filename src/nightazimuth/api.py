from __future__ import annotations

from datetime import UTC, datetime

from fastapi import FastAPI

from . import __version__

API_VERSION = "v1"

app = FastAPI(
    title="NightAzimuth API",
    version=__version__,
    description="Versioned HTTP interface for NightAzimuth.",
)


@app.get(f"/api/{API_VERSION}/health", tags=["system"])
def health() -> dict[str, str]:
    """Return process health without contacting any upstream provider."""

    return {
        "status": "ok",
        "api_version": API_VERSION,
        "application_version": __version__,
        "timestamp": datetime.now(UTC).isoformat(),
    }
