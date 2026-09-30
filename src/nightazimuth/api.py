from __future__ import annotations

from contextlib import asynccontextmanager
import logging
import os
from datetime import UTC, datetime
from time import perf_counter

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.gzip import GZipMiddleware

from . import __version__
from .aircraft_adsb_lol import close_shared_adsb_http_client, prewarm_shared_adsb_http_client
from .api_aircraft import router as aircraft_router
from .api_airports import _PROVIDER as _AIRPORT_PROVIDER
from .api_airports import router as airports_router
from .api_geojson import router as geojson_router
from .api_observing import _API_CACHE as _OBSERVING_API_CACHE
from .api_observing import router as observing_router
from .api_satellites import _SATELLITE_PIPELINE_LOCK, _build_satellite_snapshot
from .api_satellites import router as satellites_router
from .api_sky import router as sky_router
from .api_weather import router as weather_router
from .observing_planner import _astronomy_resources
from .preload_sky import SKYFIELD_CACHE
from .star_field import _load_static_resources, _prepared_catalogue

API_VERSION = "v1"
MAX_QUERY_STRING_BYTES = 2048
_SKY_LIMITING_MAGNITUDE = 5.5
_LOGGER = logging.getLogger("uvicorn.error")


def _prewarm_sky_runtime() -> None:
    """Load immutable Skyfield data and the default prepared catalogue into memory."""

    cache_directory = str(SKYFIELD_CACHE.resolve())
    started = perf_counter()
    _load_static_resources(cache_directory)
    _prepared_catalogue(cache_directory, _SKY_LIMITING_MAGNITUDE)
    _LOGGER.info(
        "sky_runtime_prewarm total_ms=%.1f",
        (perf_counter() - started) * 1000.0,
    )


def _prewarm_aircraft_http() -> None:
    """Create the reusable ADS-B HTTP connection pool before live traffic arrives."""

    started = perf_counter()
    prewarm_shared_adsb_http_client()
    _LOGGER.info(
        "aircraft_http_prewarm total_ms=%.1f",
        (perf_counter() - started) * 1000.0,
    )


def _prewarm_observing_runtime() -> None:
    """Load immutable observing-planner astronomy resources before requests compete for CPU."""

    started = perf_counter()
    _astronomy_resources(_OBSERVING_API_CACHE)
    _LOGGER.info(
        "observing_runtime_prewarm total_ms=%.1f",
        (perf_counter() - started) * 1000.0,
    )


def _prewarm_airport_runtime() -> None:
    """Parse the deploy-cached global airport catalogue into process memory."""

    started = perf_counter()
    count = _AIRPORT_PROVIDER.preload()
    if count <= 0:
        raise RuntimeError("Airport catalogue was empty during runtime preload")
    _LOGGER.info(
        "airport_runtime_prewarm total_ms=%.1f objects=%d",
        (perf_counter() - started) * 1000.0,
        count,
    )


def _prewarm_satellite_runtime() -> None:
    """Prepare location-independent satellite catalogue/SGP4 caches before live traffic."""

    started = perf_counter()
    timings: dict[str, float] = {}
    # A 90-degree synthetic horizon minimizes response/track construction while
    # still exercising catalogue load/merge and the prepared Satrec generation.
    # Positions themselves are never retained; every real request propagates at
    # its own current time and observer location.
    with _SATELLITE_PIPELINE_LOCK:
        payload = _build_satellite_snapshot(
            latitude=0.0,
            longitude=0.0,
            altitude_m=0.0,
            minimum_elevation_deg=90.0,
            group="ACTIVE",
            identification_detail=True,
            timings=timings,
        )
    _LOGGER.info(
        "satellite_runtime_prewarm total_ms=%.1f catalog_count=%d "
        "catalogue_load_ms=%.1f catalogue_merge_ms=%.1f prepare_ms=%.1f",
        (perf_counter() - started) * 1000.0,
        int(payload.get("catalog_count", 0)),
        timings.get("catalogue_load_ms", 0.0),
        timings.get("catalogue_merge_ms", 0.0),
        timings.get("prepare_ms", 0.0),
    )


def _prewarm_live_sky_runtime() -> None:
    """Warm all location-independent resources used by the initial Live Sky burst."""

    _prewarm_sky_runtime()
    _prewarm_aircraft_http()
    _prewarm_observing_runtime()
    _prewarm_airport_runtime()
    _prewarm_satellite_runtime()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Warm production-only resources before accepting requests."""

    if os.environ.get("NIGHTAZIMUTH_PREWARM_SKY") == "1":
        _prewarm_live_sky_runtime()
    try:
        yield
    finally:
        close_shared_adsb_http_client()


app = FastAPI(
    title="NightAzimuth API",
    version=__version__,
    description="Versioned, read-only HTTP interface for NightAzimuth.",
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
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
        # Render supplies the exact deployed Git commit at runtime. Exposing it
        # is safe for this public repository and lets production probes verify
        # that they are measuring the commit which triggered the workflow.
        "git_commit": os.environ.get("RENDER_GIT_COMMIT", ""),
        "timestamp": datetime.now(UTC).isoformat(),
    }
