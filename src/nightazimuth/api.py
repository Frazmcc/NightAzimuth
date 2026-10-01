from __future__ import annotations

import asyncio
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
from .api_aircraft_route import router as aircraft_route_router
from .api_airports import _PROVIDER as _AIRPORT_PROVIDER
from .api_airports import router as airports_router
from .api_geojson import router as geojson_router
from .api_observing import _API_CACHE as _OBSERVING_API_CACHE
from .api_observing import router as observing_router
from .api_satellites import _SATELLITE_PIPELINE_LOCK, _build_satellite_snapshot
from .api_satellites_cached import router as satellites_router
from .api_sky import router as sky_router
from .api_weather import router as weather_router
from .observability import OBSERVABILITY
from .observing_planner import _astronomy_resources
from .preload_sky import SKYFIELD_CACHE
from .star_field import _load_static_resources, _prepared_catalogue

API_VERSION = "v1"
MAX_QUERY_STRING_BYTES = 2048
_SKY_LIMITING_MAGNITUDE = 5.5
_LOGGER = logging.getLogger("uvicorn.error")
_ASTRONOMY_REQUEST_GATE = asyncio.Semaphore(1)
_ASTRONOMY_PATHS = frozenset(("/api/v1/sky", "/api/v1/satellites"))


def _prewarm_sky_runtime() -> None:
    cache_directory = str(SKYFIELD_CACHE.resolve())
    started = perf_counter()
    _load_static_resources(cache_directory)
    _prepared_catalogue(cache_directory, _SKY_LIMITING_MAGNITUDE)
    _LOGGER.info("sky_runtime_prewarm total_ms=%.1f", (perf_counter() - started) * 1000.0)


def _prewarm_aircraft_http() -> None:
    started = perf_counter()
    prewarm_shared_adsb_http_client()
    _LOGGER.info("aircraft_http_prewarm total_ms=%.1f", (perf_counter() - started) * 1000.0)


def _prewarm_observing_runtime() -> None:
    started = perf_counter()
    _astronomy_resources(_OBSERVING_API_CACHE)
    _LOGGER.info("observing_runtime_prewarm total_ms=%.1f", (perf_counter() - started) * 1000.0)


def _prewarm_airport_runtime() -> None:
    started = perf_counter()
    count = _AIRPORT_PROVIDER.preload()
    if count <= 0:
        raise RuntimeError("Airport catalogue was empty during runtime preload")
    _LOGGER.info("airport_runtime_prewarm total_ms=%.1f objects=%d", (perf_counter() - started) * 1000.0, count)


def _prewarm_satellite_runtime() -> None:
    started = perf_counter()
    timings: dict[str, float] = {}
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
        "satellite_runtime_prewarm total_ms=%.1f catalog_count=%d catalogue_load_ms=%.1f catalogue_merge_ms=%.1f prepare_ms=%.1f",
        (perf_counter() - started) * 1000.0,
        int(payload.get("catalog_count", 0)),
        timings.get("catalogue_load_ms", 0.0),
        timings.get("catalogue_merge_ms", 0.0),
        timings.get("prepare_ms", 0.0),
    )


def _prewarm_live_sky_runtime() -> None:
    _prewarm_sky_runtime()
    _prewarm_aircraft_http()
    _prewarm_observing_runtime()
    _prewarm_airport_runtime()
    _prewarm_satellite_runtime()


@asynccontextmanager
async def lifespan(_app: FastAPI):
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
    expose_headers=["Server-Timing"],
)
app.add_middleware(GZipMiddleware, minimum_size=1024, compresslevel=5)
app.include_router(satellites_router)
app.include_router(aircraft_router)
app.include_router(aircraft_route_router)
app.include_router(airports_router)
app.include_router(geojson_router)
app.include_router(weather_router)
app.include_router(observing_router)
app.include_router(sky_router)


@app.middleware("http")
async def reject_oversized_query_strings(request: Request, call_next):
    request_started = perf_counter()
    status_code = 500
    if len(request.scope.get("query_string", b"")) > MAX_QUERY_STRING_BYTES:
        status_code = 414
        response = JSONResponse(status_code=414, content={"detail": "Query string too long"})
        OBSERVABILITY.record_request(
            path=request.url.path,
            status_code=status_code,
            duration_ms=(perf_counter() - request_started) * 1000.0,
        )
        return response

    admission_wait_ms = 0.0
    try:
        if request.url.path in _ASTRONOMY_PATHS:
            wait_started = perf_counter()
            async with _ASTRONOMY_REQUEST_GATE:
                admission_wait_ms = (perf_counter() - wait_started) * 1000.0
                response = await call_next(request)
        else:
            response = await call_next(request)
        status_code = response.status_code
    except Exception:
        OBSERVABILITY.record_request(
            path=request.url.path,
            status_code=500,
            duration_ms=(perf_counter() - request_started) * 1000.0,
        )
        raise

    if request.url.path in _ASTRONOMY_PATHS:
        existing_timing = response.headers.get("Server-Timing")
        admission_timing = f"admission_wait;dur={admission_wait_ms:.1f}"
        response.headers["Server-Timing"] = f"{admission_timing}, {existing_timing}" if existing_timing else admission_timing
        _LOGGER.info("astronomy_admission path=%s wait_ms=%.1f", request.url.path, admission_wait_ms)

    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Permissions-Policy"] = "geolocation=(), camera=(), microphone=()"
    OBSERVABILITY.record_request(
        path=request.url.path,
        status_code=status_code,
        duration_ms=(perf_counter() - request_started) * 1000.0,
    )
    return response


@app.get(f"/api/{API_VERSION}/health", tags=["system"])
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "api_version": API_VERSION,
        "application_version": __version__,
        "git_commit": os.environ.get("RENDER_GIT_COMMIT", ""),
        "timestamp": datetime.now(UTC).isoformat(),
    }


@app.get(f"/api/{API_VERSION}/observability", tags=["system"])
def observability() -> dict[str, object]:
    """Return bounded process-local operational telemetry for NightAzimuth."""

    return {
        "status": "ok",
        "application_version": __version__,
        "git_commit": os.environ.get("RENDER_GIT_COMMIT", ""),
        **OBSERVABILITY.snapshot(),
    }
