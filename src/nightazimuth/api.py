from __future__ import annotations

from datetime import UTC, datetime

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.gzip import GZipMiddleware

from . import __version__
from .api_aircraft import router as aircraft_router
from .api_airports import router as airports_router
from .api_geojson import router as geojson_router
from .api_observing import router as observing_router
from .api_satellites import router as satellites_router
from .api_sky import router as sky_router
from .api_weather import router as weather_router

API_VERSION = "v1"
MAX_QUERY_STRING_BYTES = 2048

app = FastAPI(
    title="NightAzimuth API",
    version=__version__,
    description="Versioned, read-only HTTP interface for NightAzimuth.",
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://nightazimuth.co.uk"],
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["Accept"],
)
# ACTIVE satellite responses can contain thousands of objects plus predicted
# tracks. Compress JSON at the API boundary rather than sending the full payload
# over the network uncompressed. Small responses such as /health are untouched.
app.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=5)
app.include_router(satellites_router)
app.include_router(aircraft_router)
app.include_router(airports_router)
app.include_router(geojson_router)
app.include_router(weather_router)
app.include_router(observing_router)
app.include_router(sky_router)


@app.middleware("http")
async def reject_oversized_query_strings(request: Request, call_next):
    """Bound unauthenticated public query input before endpoint parsing."""
    if len(request.scope.get("query_string", b"")) > MAX_QUERY_STRING_BYTES:
        return JSONResponse(status_code=414, content={"detail": "Query string too long"})
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
    return response


@app.get(f"/api/{API_VERSION}/health", tags=["system"])
def health() -> dict[str, str]:
    """Return process health without contacting any upstream provider."""

    return {
        "status": "ok",
        "api_version": API_VERSION,
        "application_version": __version__,
        "timestamp": datetime.now(UTC).isoformat(),
    }
