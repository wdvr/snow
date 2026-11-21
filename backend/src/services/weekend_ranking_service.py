""" "Best this weekend" ranking: which resort is predicted best over a date window.

Ranks resorts for a ski window (default: the coming Fri-Sun, clipped to today)
from four signals, each normalized to 0-1 with a saturating curve:

    forecast   35%  forecast snowfall summed over the window days
    recent     25%  snowfall over the last 7 days
    base       20%  base depth (base elevation, falling back to mid/top)
    terrain    20%  share of runs open (lifts as fallback)

Missing signals are dropped and the remaining weights renormalized, so a
resort without terrain data is not punished as if nothing were open; the
row is flagged instead.

Access is applied per day: a day is open, passholder_only, closed (before
opening / after closing) or unknown (no season dates). Passholder-only days
count as open when the user holds an eligible pass. The score is scaled by
0.5 + 0.5 * (accessible days / window days), and resorts with no accessible
day in the window are listed after every accessible resort, flagged, instead
of being dropped (Sugar Bowl during its passholder-only opening week).

The ranking functions are pure (no I/O) so they can be tested on recorded
fixtures; fetch_daily_snowfall_forecast is the only network call.
"""

from __future__ import annotations

import json
import logging
import math
import os
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

logger = logging.getLogger(__name__)

WEIGHTS = {"forecast": 0.35, "recent": 0.25, "base": 0.20, "terrain": 0.20}

# Saturation scales (cm): the signal reaches ~63% at the scale value.
FORECAST_SCALE_CM = 25.0
RECENT_SCALE_CM = 40.0
BASE_SCALE_CM = 80.0

POWDER_DAY_CM = 15.0
FRESH_SNOW_CM = 5.0

MAX_WINDOW_DAYS = 10
# Open-Meteo forecasts 16 days ahead; keep the window inside it.
MAX_DAYS_AHEAD = 15

KNOWN_PASSES = ("ikon", "epic", "mountain_collective", "indy")

# Shipped inside the Lambda package (deploy zips src/ only).
_RESTRICTIONS_PATH = os.path.join(os.path.dirname(__file__), "access_restrictions.json")


@dataclass
class AccessRestriction:
    """A date range where a resort is not open to the general public."""

    start: date
    end: date
    kind: str = "passholder_only"
    eligible_passes: list[str] = field(default_factory=list)
    note: str | None = None
    source: str | None = None

    def covers(self, d: date) -> bool:
        return self.start <= d <= self.end


@dataclass
class ResortWeekendInput:
    """Everything the ranking needs about one resort."""

    resort_id: str
    name: str
    region: str | None = None
    state_province: str | None = None
    passes: list[str] = field(default_factory=list)
    opening_date: date | None = None
    closing_date: date | None = None
    season_status: str | None = None
    forecast_daily_cm: dict[date, float] = field(default_factory=dict)
    snowfall_7d_cm: float | None = None
    base_depth_cm: float | None = None
    lifts_open: int | None = None
    lifts_total: int | None = None
    runs_open: int | None = None
    runs_total: int | None = None
    snow_score: int | None = None
    restrictions: list[AccessRestriction] = field(default_factory=list)


@dataclass
class DayOutlook:
    date: date
    access: str  # open | passholder_only | closed | unknown
    forecast_snow_cm: float | None
    powder_cm: float
    note: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "date": self.date.isoformat(),
            "access": self.access,
            "forecast_snow_cm": _round(self.forecast_snow_cm),
            "powder_cm": _round(self.powder_cm),
            "note": self.note,
        }


@dataclass
class WeekendRanking:
    resort_id: str
    name: str
    region: str | None
    state_province: str | None
    passes: list[str]
    score: int | None
    rank: int
    forecast_window_cm: float | None
    snowfall_7d_cm: float | None
    base_depth_cm: float | None
    terrain_open_pct: float | None
    lifts_open: int | None
    lifts_total: int | None
    runs_open: int | None
    runs_total: int | None
    snow_score: int | None
    accessible_days: int
    window_days: int
    access_status: str  # open | partial | passholder_only | closed
    best_day: str | None
    best_day_label: str | None
    components: dict[str, float]
    flags: list[str]
    reason: str
    days: list[DayOutlook]

    def to_dict(self) -> dict[str, Any]:
        return {
            "resort_id": self.resort_id,
            "name": self.name,
            "region": self.region,
            "state_province": self.state_province,
            "passes": self.passes,
            "rank": self.rank,
            "score": self.score,
            "forecast_window_cm": _round(self.forecast_window_cm),
            "snowfall_7d_cm": _round(self.snowfall_7d_cm),
            "base_depth_cm": _round(self.base_depth_cm),
            "terrain_open_pct": _round(self.terrain_open_pct),
            "lifts_open": self.lifts_open,
            "lifts_total": self.lifts_total,
            "runs_open": self.runs_open,
            "runs_total": self.runs_total,
            "snow_score": self.snow_score,
            "accessible_days": self.accessible_days,
            "window_days": self.window_days,
            "access_status": self.access_status,
            "best_day": self.best_day,
            "best_day_label": self.best_day_label,
            "components": {k: round(v, 3) for k, v in self.components.items()},
            "flags": self.flags,
            "reason": self.reason,
            "days": [d.to_dict() for d in self.days],
        }


def _round(value: float | None) -> float | None:
    return None if value is None else round(value, 1)


# MARK: - Window


def weekend_window(today: date) -> tuple[date, date]:
    """The coming Fri-Sun window, clipped so it never starts in the past.

    Mon-Thu -> the following Fri-Sun. Fri/Sat/Sun -> today through Sunday.
    """
    weekday = today.weekday()  # Mon=0 .. Sun=6
    if weekday >= 4:
        friday = today - timedelta(days=weekday - 4)
    else:
        friday = today + timedelta(days=4 - weekday)
    sunday = friday + timedelta(days=2)
    return max(friday, today), sunday


def resolve_window(
    today: date, start: date | None = None, end: date | None = None
) -> tuple[date, date]:
    """Validate a requested window, defaulting to weekend_window(today).

    Raises ValueError with a user-facing message for invalid ranges.
    """
    if start is None and end is None:
        return weekend_window(today)
    if start is None or end is None:
        raise ValueError("Both start and end are required for a custom range")
    if end < start:
        raise ValueError("end must be on or after start")
    if start < today:
        raise ValueError("start cannot be in the past")
    if (end - start).days + 1 > MAX_WINDOW_DAYS:
        raise ValueError(f"Range cannot exceed {MAX_WINDOW_DAYS} days")
    if (end - today).days > MAX_DAYS_AHEAD:
        raise ValueError(f"end must be within {MAX_DAYS_AHEAD} days of today")
    return start, end


def window_dates(start: date, end: date) -> list[date]:
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


# MARK: - Access


def normalize_passes(passes: list[str] | None) -> set[str]:
    return {p.strip().lower() for p in (passes or []) if p and p.strip()}


def day_access(
    resort: ResortWeekendInput, d: date, user_passes: set[str]
) -> tuple[str, str | None]:
    """Access status for one day plus an optional note for the UI."""
    if resort.season_status == "post_season" or (
        resort.closing_date and d > resort.closing_date
    ):
        return "closed", "Season over"
    if resort.opening_date and d < resort.opening_date:
        return "closed", f"Opens {_short_date(resort.opening_date)}"
    for restriction in resort.restrictions:
        if not restriction.covers(d):
            continue
        if restriction.kind == "closed":
            return "closed", restriction.note
        eligible = normalize_passes(restriction.eligible_passes)
        if eligible & user_passes:
            return "open", "Passholder day - your pass qualifies"
        return "passholder_only", restriction.note or "Passholders only"
    if resort.opening_date is None and resort.season_status is None:
        return "unknown", "Opening date unknown"
    return "open", None


def _short_date(d: date) -> str:
    return f"{d.strftime('%b')} {d.day}"


# MARK: - Scoring


def _saturate(value_cm: float, scale_cm: float) -> float:
    return 1.0 - math.exp(-max(value_cm, 0.0) / scale_cm)


def terrain_share(resort: ResortWeekendInput) -> float | None:
    """Share of terrain open (0-1): runs, falling back to lifts."""
    if resort.runs_total and resort.runs_open is not None:
        return min(resort.runs_open / resort.runs_total, 1.0)
    if resort.lifts_total and resort.lifts_open is not None:
        return min(resort.lifts_open / resort.lifts_total, 1.0)
    return None


def powder_cm(forecast: dict[date, float], d: date) -> float:
    """Skiable new snow on day d: the previous day's snow plus half of d's."""
    return forecast.get(d - timedelta(days=1), 0.0) + 0.5 * forecast.get(d, 0.0)


def _best_day(days: list[DayOutlook]) -> tuple[str | None, str | None]:
    usable = [d for d in days if d.access in ("open", "unknown")]
    if not usable:
        return None, None
    best = max(usable, key=lambda d: (d.powder_cm, -d.date.toordinal()))
    if best.powder_cm >= POWDER_DAY_CM:
        label = "powder day"
    elif best.powder_cm >= FRESH_SNOW_CM:
        label = "fresh snow"
    else:
        label = "groomers"
    return best.date.isoformat(), label


def _format_range(dates: list[date]) -> str:
    if len(dates) == 1:
        return dates[0].strftime("%a")
    return f"{dates[0].strftime('%a')}-{dates[-1].strftime('%a')}"


def score_resort(
    resort: ResortWeekendInput,
    start: date,
    end: date,
    user_passes: set[str] | None = None,
) -> WeekendRanking:
    """Score one resort over [start, end]. Rank is filled in by rank_resorts."""
    user_passes = user_passes or set()
    dates = window_dates(start, end)
    has_forecast = bool(resort.forecast_daily_cm)

    days: list[DayOutlook] = []
    for d in dates:
        access, note = day_access(resort, d, user_passes)
        days.append(
            DayOutlook(
                date=d,
                access=access,
                forecast_snow_cm=resort.forecast_daily_cm.get(d)
                if has_forecast
                else None,
                powder_cm=powder_cm(resort.forecast_daily_cm, d),
                note=note,
            )
        )

    forecast_total = (
        sum(resort.forecast_daily_cm.get(d, 0.0) for d in dates)
        if has_forecast
        else None
    )
    share = terrain_share(resort)
    if share == 0 and resort.opening_date and resort.opening_date >= start:
        # Not open yet: "0 of 12 lifts" says nothing about the window.
        share = None

    components: dict[str, float] = {}
    if forecast_total is not None:
        components["forecast"] = _saturate(forecast_total, FORECAST_SCALE_CM)
    if resort.snowfall_7d_cm is not None:
        components["recent"] = _saturate(resort.snowfall_7d_cm, RECENT_SCALE_CM)
    if resort.base_depth_cm is not None:
        components["base"] = _saturate(resort.base_depth_cm, BASE_SCALE_CM)
    if share is not None:
        components["terrain"] = share

    accessible = sum(1 for d in days if d.access in ("open", "unknown"))
    passholder_days = sum(1 for d in days if d.access == "passholder_only")
    closed_days = sum(1 for d in days if d.access == "closed")

    if accessible == len(days):
        access_status = "open"
    elif accessible > 0:
        access_status = "partial"
    elif passholder_days > 0:
        access_status = "passholder_only"
    else:
        access_status = "closed"

    score: int | None = None
    if components:
        total_weight = sum(WEIGHTS[k] for k in components)
        quality = sum(WEIGHTS[k] * v for k, v in components.items()) / total_weight
        access_factor = 0.5 + 0.5 * (accessible / len(days))
        score = round(100 * quality * access_factor)

    flags: list[str] = []
    if passholder_days:
        passes_note = next(
            (
                r.eligible_passes
                for r in resort.restrictions
                if r.kind == "passholder_only" and r.eligible_passes
            ),
            None,
        )
        suffix = f" ({', '.join(passes_note)})" if passes_note else ""
        flags.append(f"Passholders only {passholder_days} of {len(days)} days{suffix}")
    if closed_days:
        first_note = next((d.note for d in days if d.access == "closed"), None)
        flags.append(first_note or f"Closed {closed_days} of {len(days)} days")
    if any(d.access == "unknown" for d in days):
        flags.append("Opening date unknown")
    if resort.season_status == "temporarily_closed":
        flags.append("Temporarily closed")
    for key, label in (
        ("forecast", "No forecast data"),
        ("recent", "No recent snowfall data"),
        ("base", "No base depth data"),
        ("terrain", "No lift/terrain data"),
    ):
        if key not in components:
            flags.append(label)

    best_day, best_label = _best_day(days)

    parts: list[str] = []
    if forecast_total is not None:
        parts.append(f"{forecast_total:.0f} cm forecast {_format_range(dates)}")
    if resort.snowfall_7d_cm is not None:
        parts.append(f"{resort.snowfall_7d_cm:.0f} cm last 7 days")
    if resort.base_depth_cm is not None:
        parts.append(f"{resort.base_depth_cm:.0f} cm base")
    if share is not None:
        parts.append(f"{share * 100:.0f}% terrain open")
    reason = " · ".join(parts) if parts else "Not enough data to rank"

    return WeekendRanking(
        resort_id=resort.resort_id,
        name=resort.name,
        region=resort.region,
        state_province=resort.state_province,
        passes=resort.passes,
        score=score,
        rank=0,
        forecast_window_cm=forecast_total,
        snowfall_7d_cm=resort.snowfall_7d_cm,
        base_depth_cm=resort.base_depth_cm,
        terrain_open_pct=None if share is None else share * 100,
        lifts_open=resort.lifts_open,
        lifts_total=resort.lifts_total,
        runs_open=resort.runs_open,
        runs_total=resort.runs_total,
        snow_score=resort.snow_score,
        accessible_days=accessible,
        window_days=len(days),
        access_status=access_status,
        best_day=best_day,
        best_day_label=best_label,
        components=components,
        flags=flags,
        reason=reason,
        days=days,
    )


def rank_resorts(
    resorts: list[ResortWeekendInput],
    start: date,
    end: date,
    user_passes: list[str] | None = None,
) -> list[WeekendRanking]:
    """Score and order resorts: accessible first, then passholder-only, then
    closed; by score (desc) within each group.

    Ties break on forecast snow, then base depth, then name so the order is
    deterministic.
    """
    passes = normalize_passes(user_passes)
    scored = [score_resort(r, start, end, passes) for r in resorts]
    tier = {"open": 0, "partial": 0, "passholder_only": 1, "closed": 2}
    scored.sort(
        key=lambda r: (
            tier[r.access_status],
            0 if r.score is not None else 1,
            -(r.score or 0),
            -(r.forecast_window_cm or 0.0),
            -(r.base_depth_cm or 0.0),
            r.name,
        )
    )
    for i, ranking in enumerate(scored, start=1):
        ranking.rank = i
    return scored


# MARK: - Input assembly


def _parse_date(value: Any) -> date | None:
    if not value:
        return None
    if isinstance(value, date):
        return value
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def resort_passes(resort: Any) -> list[str]:
    """Pass products a resort is on, from the Resort model fields."""
    fields = {
        "ikon": "ikon_pass",
        "epic": "epic_pass",
        "mountain_collective": "mountain_collective",
        "indy": "indy_pass",
    }
    return [p for p in KNOWN_PASSES if getattr(resort, fields[p], None)]


def load_access_restrictions(
    path: str = _RESTRICTIONS_PATH,
) -> dict[str, list[AccessRestriction]]:
    """Load curated access restrictions (services/access_restrictions.json)."""
    try:
        with open(path) as f:
            raw = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("Access restrictions unavailable: %s", e)
        return {}
    result: dict[str, list[AccessRestriction]] = {}
    for resort_id, entries in raw.get("restrictions", {}).items():
        parsed = []
        for entry in entries:
            start = _parse_date(entry.get("start"))
            end = _parse_date(entry.get("end"))
            if not start or not end:
                continue
            parsed.append(
                AccessRestriction(
                    start=start,
                    end=end,
                    kind=entry.get("kind", "passholder_only"),
                    eligible_passes=entry.get("eligible_passes", []),
                    note=entry.get("note"),
                    source=entry.get("source"),
                )
            )
        result[resort_id] = parsed
    return result


def load_opening_overrides(path: str = _RESTRICTIONS_PATH) -> dict[str, date]:
    """Announced opening dates that override the scraped season dates."""
    try:
        with open(path) as f:
            raw = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("Opening date overrides unavailable: %s", e)
        return {}
    result = {}
    for resort_id, entry in raw.get("opening_dates", {}).items():
        d = _parse_date(entry.get("date") if isinstance(entry, dict) else entry)
        if d:
            result[resort_id] = d
    return result


def sum_recent_snowfall(
    history: list[dict[str, Any]], today: date, days: int = 7
) -> float | None:
    """Sum daily-history snowfall over the last `days` days (today included)."""
    since = today - timedelta(days=days - 1)
    values = [
        float(item.get("snowfall_24h_cm") or 0.0)
        for item in history
        if (d := _parse_date(item.get("date"))) and since <= d <= today
    ]
    return sum(values) if values else None


def _condition_value(conditions: list[Any], attr: str, order: tuple[str, ...]):
    by_level = {getattr(c, "elevation_level", None): c for c in conditions}
    for level in order:
        c = by_level.get(level)
        if c is not None and getattr(c, attr, None) is not None:
            return getattr(c, attr)
    return None


def build_input(
    resort: Any,
    conditions: list[Any],
    history: list[dict[str, Any]],
    forecast_daily_cm: dict[date, float],
    restrictions: list[AccessRestriction],
    today: date,
    snow_score: int | None = None,
    opening_override: date | None = None,
) -> ResortWeekendInput:
    """Assemble ResortWeekendInput from the stored pipeline data.

    An announced opening date (opening_override) wins over the scraped one;
    if it is today or earlier the scraped pre_season status is stale too.
    """
    opening = opening_override or _parse_date(getattr(resort, "opening_date", None))
    season_status = getattr(resort, "season_status", None)
    if opening_override and opening_override <= today and season_status == "pre_season":
        season_status = "open"
    recent = sum_recent_snowfall(history, today)
    if recent is None:
        # No daily history yet: 72h snowfall is a lower bound for 7 days.
        recent = _condition_value(conditions, "snowfall_72h_cm", ("mid", "top"))
    return ResortWeekendInput(
        resort_id=resort.resort_id,
        name=resort.name,
        region=getattr(resort, "region", None),
        state_province=getattr(resort, "state_province", None),
        passes=resort_passes(resort),
        opening_date=opening,
        closing_date=_parse_date(getattr(resort, "closing_date", None)),
        season_status=season_status,
        forecast_daily_cm=forecast_daily_cm,
        snowfall_7d_cm=recent,
        base_depth_cm=_condition_value(
            conditions, "snow_depth_cm", ("base", "mid", "top")
        ),
        lifts_open=_condition_value(conditions, "lifts_open", ("mid", "base", "top")),
        lifts_total=_condition_value(conditions, "lifts_total", ("mid", "base", "top")),
        runs_open=_condition_value(conditions, "runs_open", ("mid", "base", "top")),
        runs_total=_condition_value(conditions, "runs_total", ("mid", "base", "top")),
        snow_score=snow_score,
        restrictions=restrictions,
    )


# MARK: - Forecast fetch


def _forecast_point(resort: Any) -> Any | None:
    points = {
        (p.level.value if hasattr(p.level, "value") else p.level): p
        for p in getattr(resort, "elevation_points", []) or []
    }
    return points.get("mid") or points.get("top") or points.get("base")


def fetch_daily_snowfall_forecast(
    resorts: list[Any], forecast_days: int = 16, timeout: float = 10.0
) -> dict[str, dict[date, float]]:
    """Daily snowfall (cm, resort-local days) for many resorts in one request.

    Open-Meteo accepts comma-separated coordinate lists and returns one
    result per location. Resorts that fail or lack coordinates are omitted;
    the ranking then flags them as missing forecast data.
    """
    from services.openmeteo_service import _request_with_retry

    located = [(r, p) for r in resorts if (p := _forecast_point(r)) is not None]
    located = [
        (r, p) for r, p in located if p.latitude is not None and p.longitude is not None
    ]
    result: dict[str, dict[date, float]] = {}
    for i in range(0, len(located), 50):
        chunk = located[i : i + 50]
        params = {
            "latitude": ",".join(f"{p.latitude:.4f}" for _, p in chunk),
            "longitude": ",".join(f"{p.longitude:.4f}" for _, p in chunk),
            "elevation": ",".join(str(p.elevation_meters) for _, p in chunk),
            "daily": "snowfall_sum",
            "past_days": 1,
            "forecast_days": forecast_days,
            "timezone": "auto",
        }
        try:
            response = _request_with_retry(
                "GET",
                "https://api.open-meteo.com/v1/forecast",
                params=params,
                timeout=timeout,
                max_total_seconds=20,
            )
            payload = response.json()
        except Exception as e:
            logger.warning("Weekend forecast fetch failed for chunk %d: %s", i, e)
            continue
        if isinstance(payload, dict):
            payload = [payload]
        for (resort, _), location in zip(chunk, payload, strict=False):
            daily = (location or {}).get("daily", {})
            series: dict[date, float] = {}
            for t, v in zip(
                daily.get("time", []), daily.get("snowfall_sum", []), strict=False
            ):
                d = _parse_date(t)
                if d is not None and v is not None:
                    series[d] = float(v)
            if series:
                result[resort.resort_id] = series
    return result
