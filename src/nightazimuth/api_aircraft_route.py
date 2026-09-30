from __future__ import annotations

from fastapi import APIRouter, HTTPException, Path

from .aircraft_routes import AdsbLolRouteProvider, AirportInfo

router = APIRouter(prefix="/api/v1/aircraft", tags=["aircraft"])
_PROVIDER = AdsbLolRouteProvider()


def _airport_payload(airport: AirportInfo | None) -> dict[str, object] | None:
    if airport is None:
        return None
    return {
        "name": airport.name,
        "icao": airport.icao,
        "iata": airport.iata,
        "display_code": airport.display_code,
        "location": airport.location,
        "country_iso2": airport.country_iso2,
        "country_name": airport.country_name,
    }


@router.get("/route/{callsign}")
def aircraft_route(
    callsign: str = Path(min_length=2, max_length=12, pattern=r"^[A-Za-z0-9 ]+$"),
) -> dict[str, object]:
    """Return cached standing route information for one aircraft callsign."""
    route = _PROVIDER.lookup(callsign)
    if route is None:
        raise HTTPException(status_code=404, detail="Route unavailable")
    return {
        "callsign": route.callsign,
        "airline_code": route.airline_code,
        "departure": _airport_payload(route.departure),
        "arrival": _airport_payload(route.arrival),
    }
