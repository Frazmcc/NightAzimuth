from __future__ import annotations

from typing import Any, Iterable


def merge_orbital_catalogues(*catalogues: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Merge CelesTrak catalogues by NORAD ID, keeping the first occurrence.

    NightAzimuth uses this to combine the ACTIVE catalogue with the smaller
    VISUAL catalogue without calculating the same spacecraft twice.
    """
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()

    for catalogue in catalogues:
        for fields in catalogue:
            norad_id = str(fields.get("NORAD_CAT_ID") or "").strip()
            if not norad_id or norad_id in seen:
                continue
            seen.add(norad_id)
            merged.append(fields)

    return merged


def norad_ids(elements: Iterable[dict[str, Any]]) -> set[str]:
    """Return the non-empty NORAD catalogue identifiers in an element set."""
    return {
        value
        for fields in elements
        if (value := str(fields.get("NORAD_CAT_ID") or "").strip())
    }
