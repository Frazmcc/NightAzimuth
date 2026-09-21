from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, StrEnum


class SquawkPriority(IntEnum):
    NORMAL = 0
    SPECIAL = 10
    IMPORTANT = 20
    CRITICAL = 30


class SquawkCategory(StrEnum):
    EMERGENCY = "emergency"
    SEARCH_RESCUE = "search_rescue"
    AIR_AMBULANCE = "air_ambulance"
    POLICE = "police"
    MILITARY = "military"
    ROYAL = "royal"
    SPECIAL_TASK = "special_task"
    CALIBRATION = "calibration"
    PARACHUTING = "parachuting"
    TOWING_INSPECTION = "towing_inspection"
    MARITIME = "maritime"
    OPEN_SKIES = "open_skies"
    LOST = "lost"
    DANGER_AREA = "danger_area"
    DISPLAY = "display"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class SquawkAlert:
    code: str
    label: str
    category: SquawkCategory
    priority: SquawkPriority

    @property
    def highlighted(self) -> bool:
        return self.priority > SquawkPriority.NORMAL


# UK operational allocations are based on the NATS AIS Secondary Surveillance
# Radar allocation dataset effective 2026-09-03 and current CAA MATS material.
# Routine FMC/ATC/conspicuity codes are deliberately excluded unless the code
# itself identifies a notable operation that is useful to an observer.
_EXACT: dict[str, SquawkAlert] = {
    "0003": SquawkAlert("0003", "AIR AMBULANCE — Surrey/Sussex HEMS", SquawkCategory.AIR_AMBULANCE, SquawkPriority.IMPORTANT),
    "0006": SquawkAlert("0006", "BRITISH TRANSPORT POLICE AIR SUPPORT", SquawkCategory.POLICE, SquawkPriority.IMPORTANT),
    "0014": SquawkAlert("0014", "AIR AMBULANCE — Kent", SquawkCategory.AIR_AMBULANCE, SquawkPriority.IMPORTANT),
    "0015": SquawkAlert("0015", "AIR AMBULANCE — Essex", SquawkCategory.AIR_AMBULANCE, SquawkPriority.IMPORTANT),
    "0016": SquawkAlert("0016", "AIR AMBULANCE — Thames Valley", SquawkCategory.AIR_AMBULANCE, SquawkPriority.IMPORTANT),
    "0017": SquawkAlert("0017", "AIR AMBULANCE — London", SquawkCategory.AIR_AMBULANCE, SquawkPriority.IMPORTANT),
    "0020": SquawkAlert("0020", "AIR AMBULANCE / HEMS", SquawkCategory.AIR_AMBULANCE, SquawkPriority.IMPORTANT),
    "0021": SquawkAlert("0021", "FIXED-WING — SERVICE FROM SHIP", SquawkCategory.MARITIME, SquawkPriority.SPECIAL),
    "0022": SquawkAlert("0022", "HELICOPTER — SERVICE FROM SHIP", SquawkCategory.MARITIME, SquawkPriority.SPECIAL),
    "0023": SquawkAlert("0023", "SEARCH & RESCUE", SquawkCategory.SEARCH_RESCUE, SquawkPriority.IMPORTANT),
    "0024": SquawkAlert("0024", "RADAR FLIGHT EVALUATION / CALIBRATION", SquawkCategory.CALIBRATION, SquawkPriority.SPECIAL),
    "0025": SquawkAlert("0025", "SCOTTISH NON-STANDARD FLIGHT", SquawkCategory.OTHER, SquawkPriority.SPECIAL),
    "0026": SquawkAlert("0026", "SPECIAL TASKS", SquawkCategory.SPECIAL_TASK, SquawkPriority.IMPORTANT),
    "0027": SquawkAlert("0027", "LONDON CONTROL OPS — CROSSING/JOINING CAS", SquawkCategory.OTHER, SquawkPriority.SPECIAL),
    "0030": SquawkAlert("0030", "FIR LOST AIRCRAFT", SquawkCategory.LOST, SquawkPriority.CRITICAL),
    "0031": SquawkAlert("0031", "AIR AMBULANCE — Hertfordshire", SquawkCategory.AIR_AMBULANCE, SquawkPriority.IMPORTANT),
    "0032": SquawkAlert("0032", "POLICE AIR SUPPORT", SquawkCategory.POLICE, SquawkPriority.IMPORTANT),
    "0033": SquawkAlert("0033", "PARACHUTE DROPPING", SquawkCategory.PARACHUTING, SquawkPriority.IMPORTANT),
    "0034": SquawkAlert("0034", "ANTENNA / TARGET / GLIDER TOWING", SquawkCategory.TOWING_INSPECTION, SquawkPriority.SPECIAL),
    "0035": SquawkAlert("0035", "SELECTED HELICOPTER FLIGHT", SquawkCategory.SPECIAL_TASK, SquawkPriority.SPECIAL),
    "0036": SquawkAlert("0036", "PIPELINE / POWERLINE INSPECTION", SquawkCategory.TOWING_INSPECTION, SquawkPriority.IMPORTANT),
    "0037": SquawkAlert("0037", "ROYAL FLIGHT — HELICOPTER", SquawkCategory.ROYAL, SquawkPriority.IMPORTANT),
    "0040": SquawkAlert("0040", "CIVIL HELICOPTER — NORTH SEA", SquawkCategory.MARITIME, SquawkPriority.SPECIAL),
    "7001": SquawkAlert("7001", "MILITARY LOW-LEVEL / CLIMB-OUT", SquawkCategory.MILITARY, SquawkPriority.IMPORTANT),
    "7002": SquawkAlert("7002", "DANGER AREA OPERATION", SquawkCategory.DANGER_AREA, SquawkPriority.SPECIAL),
    "7003": SquawkAlert("7003", "RED ARROWS DISPLAY / TRANSIT", SquawkCategory.DISPLAY, SquawkPriority.IMPORTANT),
    "7004": SquawkAlert("7004", "AEROBATICS / DISPLAY", SquawkCategory.DISPLAY, SquawkPriority.IMPORTANT),
    "7005": SquawkAlert("7005", "MILITARY HIGH-ENERGY MANOEUVRES", SquawkCategory.MILITARY, SquawkPriority.IMPORTANT),
    "7006": SquawkAlert("7006", "MILITARY AUTONOMOUS TRA OPERATION", SquawkCategory.MILITARY, SquawkPriority.IMPORTANT),
    "7007": SquawkAlert("7007", "OPEN SKIES OBSERVATION FLIGHT", SquawkCategory.OPEN_SKIES, SquawkPriority.IMPORTANT),
    "7400": SquawkAlert("7400", "UAS LOST C2 LINK", SquawkCategory.EMERGENCY, SquawkPriority.CRITICAL),
    "7500": SquawkAlert("7500", "UNLAWFUL INTERFERENCE", SquawkCategory.EMERGENCY, SquawkPriority.CRITICAL),
    "7600": SquawkAlert("7600", "RADIO-COMMUNICATION FAILURE", SquawkCategory.EMERGENCY, SquawkPriority.CRITICAL),
    "7700": SquawkAlert("7700", "AIRCRAFT EMERGENCY", SquawkCategory.EMERGENCY, SquawkPriority.CRITICAL),
}


def normalise_squawk(value: str | None) -> str | None:
    if value is None:
        return None
    code = value.strip()
    if len(code) != 4 or any(character not in "01234567" for character in code):
        return None
    return code


def classify_squawk(value: str | None) -> SquawkAlert | None:
    code = normalise_squawk(value)
    if code is None:
        return None

    exact = _EXACT.get(code)
    if exact is not None:
        return exact

    numeric = int(code, 8)
    police_start = int("0041", 8)
    police_end = int("0061", 8)
    if police_start <= numeric <= police_end:
        return SquawkAlert(
            code,
            "POLICE AIR SUPPORT",
            SquawkCategory.POLICE,
            SquawkPriority.IMPORTANT,
        )

    return None


def is_priority_squawk(value: str | None) -> bool:
    alert = classify_squawk(value)
    return alert is not None and alert.highlighted
