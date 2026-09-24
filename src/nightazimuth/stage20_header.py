from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from timezonefinder import TimezoneFinder


_TIMEZONE_FINDER: TimezoneFinder | None = None


def timezone_name_for_coordinates(latitude_deg: float, longitude_deg: float) -> str:
    """Resolve the local timezone solely from the active observer coordinates."""
    global _TIMEZONE_FINDER
    if _TIMEZONE_FINDER is None:
        _TIMEZONE_FINDER = TimezoneFinder(in_memory=True)
    return _TIMEZONE_FINDER.timezone_at(lng=longitude_deg, lat=latitude_deg) or "UTC"


def format_utc_offset(offset: timedelta | None) -> str:
    total_minutes = 0 if offset is None else int(offset.total_seconds() // 60)
    sign = "+" if total_minutes >= 0 else "-"
    total_minutes = abs(total_minutes)
    hours, minutes = divmod(total_minutes, 60)
    if minutes:
        return f"UTC{sign}{hours}:{minutes:02d}"
    return f"UTC{sign}{hours}"


def local_clock_text(
    timezone_name: str,
    *,
    now_utc: datetime | None = None,
) -> str:
    moment = now_utc or datetime.now(timezone.utc)
    if moment.tzinfo is None or moment.utcoffset() is None:
        raise ValueError("clock time must be timezone-aware")
    local = moment.astimezone(ZoneInfo(timezone_name))
    return f"{local:%H:%M:%S}  {format_utc_offset(local.utcoffset())}"
