"""Season-aware polling utilities.

Pure helper module (no I/O) for determining whether a ski resort is currently
in its active season window. Used to skip out-of-season resorts during weather
polling and to gate most alert types.

Key design decisions (see feature spec):
- Pre-season buffer: 21 days (callers pass explicit value for clarity)
- Default Northern-hemisphere season: Nov 15 -> May 10
- Default Southern-hemisphere season: Jun 1 -> Oct 31
- Resorts within |lat| < 25 (e.g. equatorial or tropical) or with
  `year_round=True` are treated as always-in-season.
- Per-resort overrides via `season_start_month_day` / `season_end_month_day`
  (both in "MM-DD" format). Both must be set for the override to apply.

This module is intentionally free of DynamoDB/filesystem access so it can be
unit-tested trivially and imported cheaply.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

# Default season windows (inclusive). Format: ("MM-DD", "MM-DD").
DEFAULT_NORTHERN_SEASON: tuple[str, str] = ("11-15", "05-10")
DEFAULT_SOUTHERN_SEASON: tuple[str, str] = ("06-01", "10-31")

# Latitude threshold below which we treat a resort as year-round.
# Handles equatorial / tropical edge cases (e.g. Dubai indoor snow, high-altitude
# equatorial peaks). Resorts with |lat| < 25 are always polled.
TROPICAL_LAT_THRESHOLD: float = 25.0


def _get_primary_latitude(resort: Any) -> float | None:
    """Return the latitude of the first elevation point, if available."""
    points = getattr(resort, "elevation_points", None) or []
    if not points:
        return None
    lat = getattr(points[0], "latitude", None)
    if lat is None:
        return None
    try:
        return float(lat)
    except (TypeError, ValueError):
        return None


def hemisphere_for(resort: Any) -> str:
    """Return 'N' or 'S' based on the resort's primary latitude.

    Defaults to 'N' when latitude is missing or unparseable — Northern
    hemisphere is by far the more common case and the safer default (a
    resort polled during its off-season just means extra Open-Meteo calls
    for that resort; the opposite could silently skip an in-season resort).
    """
    lat = _get_primary_latitude(resort)
    if lat is None:
        return "N"
    return "S" if lat < 0 else "N"


def _is_year_round(resort: Any) -> bool:
    """True if the resort should never be filtered by season."""
    if bool(getattr(resort, "year_round", False)):
        return True
    lat = _get_primary_latitude(resort)
    if lat is None:
        return False
    return abs(lat) < TROPICAL_LAT_THRESHOLD


def default_window_for(resort: Any) -> tuple[str, str] | None:
    """Return the default season window for the resort, or None if year-round."""
    if _is_year_round(resort):
        return None
    if hemisphere_for(resort) == "S":
        return DEFAULT_SOUTHERN_SEASON
    return DEFAULT_NORTHERN_SEASON


def _parse_md(md: str) -> tuple[int, int]:
    """Parse a "MM-DD" string into (month, day). Raises ValueError if invalid."""
    if not isinstance(md, str) or len(md) != 5 or md[2] != "-":
        raise ValueError(f"Invalid month-day value {md!r}; expected 'MM-DD'")
    month = int(md[0:2])
    day = int(md[3:5])
    # Validate by constructing a date in a leap year so 02-29 is accepted.
    date(2000, month, day)
    return month, day


def effective_window_for(resort: Any) -> tuple[str, str] | None:
    """Return the effective season window (override if set, else default).

    Returns None for year-round resorts. If one override field is set but not
    the other, we fall back to the default rather than silently using a half
    override — callers that truly want to override a single bound should set
    both fields.
    """
    if _is_year_round(resort):
        return None

    start_override = getattr(resort, "season_start_month_day", None)
    end_override = getattr(resort, "season_end_month_day", None)
    if start_override and end_override:
        # Validate; raise if malformed so operators notice bad data.
        _parse_md(start_override)
        _parse_md(end_override)
        return (start_override, end_override)

    return default_window_for(resort)


def _md_tuple(dt: date) -> tuple[int, int]:
    return (dt.month, dt.day)


def _window_contains(
    md_start: tuple[int, int], md_end: tuple[int, int], md_now: tuple[int, int]
) -> bool:
    """True if md_now is within [md_start, md_end] inclusive, with year wrap.

    If md_start > md_end (e.g. Nov 15 -> May 10), the window wraps across
    the year boundary. We handle the wrap by allowing either side.
    """
    if md_start <= md_end:
        return md_start <= md_now <= md_end
    return md_now >= md_start or md_now <= md_end


def is_in_active_window(resort: Any, now: datetime, pre_season_days: int = 21) -> bool:
    """True if the resort is currently in its (possibly buffered) season window.

    Args:
        resort: Any object with ``elevation_points``, optional
            ``season_start_month_day`` / ``season_end_month_day`` and optional
            ``year_round`` boolean.
        now: Current datetime (used as the reference date).
        pre_season_days: Days to extend the window backward from its start,
            to allow polling just before opening.

    Notes:
        - Year-round resorts always return True.
        - If the effective window spans year-end (Northern default), the
          pre-season buffer is applied by shifting the start date backward
          in the same "MM-DD" space via a real date subtraction, which
          naturally rolls e.g. Nov 15 - 21d -> Oct 25.
    """
    window = effective_window_for(resort)
    if window is None:
        return True

    start_md_str, end_md_str = window
    start_month, start_day = _parse_md(start_md_str)
    end_month, end_day = _parse_md(end_md_str)

    # Compute buffered start (start date shifted backward by pre_season_days).
    # Use an arbitrary non-leap year to convert MM-DD into a concrete date for
    # subtraction. We then re-extract month/day. Year choice doesn't matter
    # except for Feb 29 (which we handle by using a leap year).
    anchor_year = 2001  # non-leap; avoids Feb 29 being accidentally introduced
    try:
        start_date = date(anchor_year, start_month, start_day)
    except ValueError:
        # Feb 29 case; use a leap year for the anchor
        start_date = date(2000, start_month, start_day)
    buffered_start = start_date - timedelta(days=pre_season_days)
    start_md = (buffered_start.month, buffered_start.day)
    end_md = (end_month, end_day)
    now_md = _md_tuple(now.date() if isinstance(now, datetime) else now)

    return _window_contains(start_md, end_md, now_md)
