from __future__ import annotations

from dataclasses import dataclass

from .aircraft_live import SkyAircraft


@dataclass(frozen=True, slots=True)
class AircraftDisplayIdentity:
    make_model: str
    capacity: str | None
    role: str | None


# Conservative, observer-facing descriptions for common ICAO type designators.
# Capacity is deliberately expressed as a typical/range value where airline
# cabin configuration varies rather than claiming an exact seat count.
_TYPE_DISPLAY: dict[str, tuple[str, str | None]] = {
    "EC35": ("Airbus Helicopters H135 / EC135", "typically 5–7 seats"),
    "H135": ("Airbus Helicopters H135", "typically 5–7 seats"),
    "A189": ("Leonardo AW189", "typically 16–19 passengers"),
    "AW89": ("Leonardo AW189", "typically 16–19 passengers"),
    "A30B": ("Airbus A300B2/B4", "typically 250–266 seats"),
    "A306": ("Airbus A300-600", "typically 266 seats"),
    "A310": ("Airbus A310", "typically 220–240 seats"),
    "A318": ("Airbus A318", "typically 107–132 seats"),
    "A319": ("Airbus A319", "typically 124–156 seats"),
    "A320": ("Airbus A320", "typically 150–186 seats"),
    "A321": ("Airbus A321", "typically 185–244 seats"),
    "A20N": ("Airbus A320neo", "typically 150–194 seats"),
    "A21N": ("Airbus A321neo", "typically 180–244 seats"),
    "B738": ("Boeing 737-800", "typically 162–189 seats"),
    "B38M": ("Boeing 737 MAX 8", "typically 162–210 seats"),
    "B77W": ("Boeing 777-300ER", "typically 300–396 seats"),
    "B788": ("Boeing 787-8 Dreamliner", "typically 242–248 seats"),
    "B789": ("Boeing 787-9 Dreamliner", "typically 280–296 seats"),
    "E190": ("Embraer E190", "typically 96–114 seats"),
    "E195": ("Embraer E195", "typically 100–124 seats"),
}


def aircraft_display_identity(aircraft: SkyAircraft) -> AircraftDisplayIdentity:
    type_code = (aircraft.type_code or "").strip().upper()
    mapped = _TYPE_DISPLAY.get(type_code)
    if mapped is not None:
        make_model, capacity = mapped
    else:
        make_model = aircraft.type_description or aircraft.type_code or "Unknown aircraft type"
        capacity = None

    role = infer_aircraft_role(aircraft)
    return AircraftDisplayIdentity(make_model=make_model, capacity=capacity, role=role)


def infer_aircraft_role(aircraft: SkyAircraft) -> str | None:
    text = " ".join(
        value.lower()
        for value in (
            aircraft.operator,
            aircraft.callsign,
            aircraft.type_description,
        )
        if value
    )

    if any(token in text for token in ("search and rescue", "search & rescue", "coastguard", "coast guard")):
        return "Coastguard / Search & Rescue"
    if any(token in text for token in ("air ambulance", "ambulance", "hems", "medical")):
        return "Air Ambulance / HEMS"
    if any(token in text for token in ("police", "npas", "constabulary")):
        return "Police Air Support"
    if aircraft.squawk_alert is not None:
        category = aircraft.squawk_alert.category.value
        if category == "search_rescue":
            return "Search & Rescue"
        if category == "air_ambulance":
            return "Air Ambulance / HEMS"
        if category == "police":
            return "Police Air Support"
    if aircraft.military:
        return "Military"
    return None


def squawk_display(aircraft: SkyAircraft) -> str | None:
    if aircraft.squawk is None:
        return None
    if aircraft.squawk_alert is not None:
        return f"{aircraft.squawk_alert.code} — {short_squawk_description(aircraft.squawk_alert.label)}"
    return aircraft.squawk


def short_squawk_description(label: str) -> str:
    replacements = {
        "AIRCRAFT EMERGENCY": "Emergency",
        "RADIO-COMMUNICATION FAILURE": "Radio failure",
        "UNLAWFUL INTERFERENCE": "Unlawful interference",
        "UAS LOST C2 LINK": "UAS lost control link",
        "SEARCH & RESCUE": "Search & Rescue",
        "FIR LOST AIRCRAFT": "Lost aircraft",
        "POLICE AIR SUPPORT": "Police air support",
        "SPECIAL TASKS": "Special tasks",
        "MILITARY HIGH-ENERGY MANOEUVRES": "Military high-energy manoeuvres",
        "MILITARY LOW-LEVEL / CLIMB-OUT": "Military low-level / climb-out",
        "RED ARROWS DISPLAY / TRANSIT": "Red Arrows display / transit",
        "AEROBATICS / DISPLAY": "Aerobatics / display",
        "OPEN SKIES OBSERVATION FLIGHT": "Open Skies observation",
    }
    return replacements.get(label, label.title())
