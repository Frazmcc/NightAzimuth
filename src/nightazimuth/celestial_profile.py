from __future__ import annotations


def profile_snapshot_key(owner: object, selected_name: str | None) -> object | None:
    if selected_name is None:
        return None
    location_key = getattr(owner, "_location_key", None)
    if callable(location_key):
        key = location_key(selected_name)
        if key is not None:
            return key
    return selected_name
