"""Per-resort season opening/closing dates.

OnTheSnow publishes a projected (or announced) opening and closing date for
each resort it covers, plus the resort's reported operating state. A scheduled
Lambda (handlers/season_dates_refresh.py) scrapes those pages and writes
``data/season-dates.json`` to the website bucket. Readers (API handler, static
JSON generator) merge the cached dates into the resort payload and derive a
``season_status``.

We never invent dates: a resort without source data gets no dates and no
status. Scoring is untouched; this is display metadata only.

Cache file shape::

    {
      "generated_at": "...",
      "source": "onthesnow",
      "resorts": {
        "kirkwood": {
          "opening_date": "2026-12-04",
          "closing_date": "2027-04-11",
          "open_flag": 2,
          "source_url": "https://www.onthesnow.com/california/kirkwood/skireport",
          "fetched_at": "..."
        }
      },
      "last_attempted": {"kirkwood": "..."}
    }
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

SEASON_DATES_S3_KEY = "data/season-dates.json"
SEASON_DATES_SOURCE = "onthesnow"

# Show "closes <date>" once the closing date is this close.
CLOSING_SOON_DAYS = 45

# Entries not refreshed for this long are dropped rather than served stale.
MAX_ENTRY_AGE_DAYS = 14

# Season status values exposed on the resort payload.
STATUS_PRE_SEASON = "pre_season"
STATUS_OPEN = "open"
STATUS_CLOSING_SOON = "closing_soon"
STATUS_POST_SEASON = "post_season"
STATUS_TEMPORARILY_CLOSED = "temporarily_closed"

# OnTheSnow `status.openFlag` values (as rendered on their resort pages).
OPEN_FLAG_OPEN = 1
OPEN_FLAG_CLOSED = 2
OPEN_FLAG_TEMPORARILY_CLOSED = 3
OPEN_FLAG_WEEKENDS_ONLY = 4
# 6 is used for resorts without a current report (defunct or not reporting);
# their dates are stale years-old values, so we drop them entirely.
OPEN_FLAG_NO_REPORT = 6

_REPORTED_OPEN_FLAGS = {OPEN_FLAG_OPEN, OPEN_FLAG_WEEKENDS_ONLY}

# Resort fields populated from the season-dates cache. They are derived at
# read time and must never be persisted to the resorts table.
SEASON_FIELDS = frozenset(
    {"opening_date", "closing_date", "season_status", "season_dates_source"}
)


# ---------------------------------------------------------------------------
# Parsing OnTheSnow pages
# ---------------------------------------------------------------------------

_FLIGHT_CHUNK_RE = re.compile(r'self\.__next_f\.push\(\[1,"(.*?)"\]\)</script>', re.S)
_FLIGHT_ROW_RE = re.compile(r"^([0-9a-f]+):(\{.*\}|\[.*\])$")
_ISO_DATE_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")


def _flight_rows(html: str) -> dict[str, Any]:
    """Decode the Next.js RSC flight payload into {row_id: parsed JSON}."""
    payload = []
    for chunk in _FLIGHT_CHUNK_RE.findall(html):
        try:
            payload.append(json.loads('"' + chunk + '"'))
        except ValueError:
            continue
    rows: dict[str, Any] = {}
    for line in "".join(payload).split("\n"):
        m = _FLIGHT_ROW_RE.match(line)
        if not m:
            continue
        try:
            rows[m.group(1)] = json.loads(m.group(2))
        except ValueError:
            continue
    return rows


def _resolve(value: Any, rows: dict[str, Any]) -> Any:
    """Follow a "$<row>" reference (at most a few hops)."""
    for _ in range(3):
        if isinstance(value, str) and value.startswith("$") and value[1:] in rows:
            value = rows[value[1:]]
        else:
            break
    return value


def parse_onthesnow_records(html: str) -> dict[str, dict[str, Any]]:
    """Extract resort status records from an OnTheSnow resort/listing page.

    A resort page carries the resort itself plus several nearby resorts.

    Returns:
        {onthesnow_uuid: {"title", "slug", "open_flag", "opening_date",
        "closing_date", "updated_at"}}
    """
    rows = _flight_rows(html)
    found: dict[str, dict[str, Any]] = {}

    def visit(obj: Any) -> None:
        if isinstance(obj, dict):
            if "uuid" in obj and "slug" in obj and "status" in obj:
                status = _resolve(obj.get("status"), rows)
                if isinstance(status, dict) and "openFlag" in status:
                    found[str(obj["uuid"])] = {
                        "title": obj.get("title"),
                        "slug": obj.get("slug"),
                        "open_flag": status.get("openFlag"),
                        "opening_date": status.get("openingDate"),
                        "closing_date": status.get("closingDate"),
                        "updated_at": obj.get("updatedAt"),
                    }
            for v in obj.values():
                visit(v)
        elif isinstance(obj, list):
            for v in obj:
                visit(v)

    for row in rows.values():
        visit(row)
    return found


def _parse_iso_date(value: Any) -> date | None:
    if not isinstance(value, str):
        return None
    m = _ISO_DATE_RE.match(value.strip())
    if not m:
        return None
    try:
        return date.fromisoformat(m.group(1))
    except ValueError:
        return None


def normalize_record(
    record: dict[str, Any], today: date | None = None
) -> dict[str, Any] | None:
    """Validate a scraped record and return cache fields, or None if unusable.

    Drops resorts without a current report, implausible years and inverted
    date pairs. A single valid date is kept on its own.
    """
    today = today or datetime.now(UTC).date()
    flag = record.get("open_flag")
    if flag == OPEN_FLAG_NO_REPORT:
        return None

    opening = _parse_iso_date(record.get("opening_date"))
    closing = _parse_iso_date(record.get("closing_date"))

    def plausible(d: date | None) -> date | None:
        # Season dates are at most ~a year away; anything else is stale junk.
        if d is None or abs((d - today).days) > 550:
            return None
        return d

    opening, closing = plausible(opening), plausible(closing)
    if opening and closing and closing < opening:
        return None
    if not opening and not closing:
        return None

    return {
        "opening_date": opening.isoformat() if opening else None,
        "closing_date": closing.isoformat() if closing else None,
        "open_flag": flag if isinstance(flag, int) else None,
    }


# ---------------------------------------------------------------------------
# Status derivation
# ---------------------------------------------------------------------------


def derive_season_status(
    opening_date: str | None,
    closing_date: str | None,
    today: date,
    open_flag: int | None = None,
) -> str | None:
    """Derive the season status for a resort.

    Date logic (primary):
      - today < opening            -> pre_season
      - today > closing            -> post_season
      - closing within 45 days     -> closing_soon
      - otherwise (opening passed) -> open

    The resort's reported state refines this so a closed resort never looks
    skiable and an early opener isn't shown as "opens <date>":
      - reported open / weekends-only before closing -> open (or closing_soon)
      - reported temporarily closed in season        -> temporarily_closed
      - reported closed after the projected opening  -> pre_season during the
        first half of the season window (opening delayed), post_season
        during the second half (closed early)
    """
    opening = _parse_iso_date(opening_date)
    closing = _parse_iso_date(closing_date)
    if not opening and not closing:
        return None

    if closing and today > closing:
        return STATUS_POST_SEASON

    def in_season_status() -> str:
        if closing and (closing - today).days <= CLOSING_SOON_DAYS:
            return STATUS_CLOSING_SOON
        return STATUS_OPEN

    if open_flag in _REPORTED_OPEN_FLAGS:
        return in_season_status()

    if opening and today < opening:
        return STATUS_PRE_SEASON

    if opening is None:
        # Only a closing date: we can't tell whether the resort opened, so we
        # only speak up once the closing date is near.
        if closing and (closing - today).days <= CLOSING_SOON_DAYS:
            return STATUS_CLOSING_SOON
        return None

    if open_flag == OPEN_FLAG_TEMPORARILY_CLOSED:
        return STATUS_TEMPORARILY_CLOSED

    if open_flag == OPEN_FLAG_CLOSED:
        if closing is None:
            return STATUS_PRE_SEASON
        midpoint = opening + (closing - opening) / 2
        return STATUS_PRE_SEASON if today <= midpoint else STATUS_POST_SEASON

    return in_season_status()


def resort_today(timezone_name: str | None, now: datetime | None = None) -> date:
    """Today's date in the resort's timezone (UTC if unknown)."""
    now = now or datetime.now(UTC)
    if timezone_name:
        try:
            return now.astimezone(ZoneInfo(timezone_name)).date()
        except Exception:
            pass
    return now.astimezone(UTC).date()


def fresh_entries(
    cache: dict[str, Any] | None, now: datetime | None = None
) -> dict[str, dict[str, Any]]:
    """Return cache entries refreshed within MAX_ENTRY_AGE_DAYS."""
    if not isinstance(cache, dict):
        return {}
    entries = cache.get("resorts")
    if not isinstance(entries, dict):
        return {}
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(days=MAX_ENTRY_AGE_DAYS)
    fresh: dict[str, dict[str, Any]] = {}
    for resort_id, entry in entries.items():
        if not isinstance(entry, dict):
            continue
        try:
            fetched = datetime.fromisoformat(entry.get("fetched_at") or "")
        except ValueError:
            continue
        if fetched.tzinfo is None:
            fetched = fetched.replace(tzinfo=UTC)
        if fetched >= cutoff:
            fresh[resort_id] = entry
    return fresh


def season_fields_for(
    entry: dict[str, Any] | None,
    timezone_name: str | None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Resort payload fields for one cache entry (all None without data)."""
    if not entry:
        return dict.fromkeys(SEASON_FIELDS)
    opening = entry.get("opening_date")
    closing = entry.get("closing_date")
    status = derive_season_status(
        opening, closing, resort_today(timezone_name, now), entry.get("open_flag")
    )
    return {
        "opening_date": opening,
        "closing_date": closing,
        "season_status": status,
        "season_dates_source": SEASON_DATES_SOURCE,
    }


def apply_season_dates(resorts: list, entries: dict[str, dict[str, Any]]) -> list:
    """Return resorts (pydantic Resort models) with season fields filled in."""
    if not resorts:
        return resorts
    now = datetime.now(UTC)
    out = []
    for resort in resorts:
        fields = season_fields_for(
            entries.get(resort.resort_id), getattr(resort, "timezone", None), now
        )
        out.append(resort.model_copy(update=fields))
    return out


# ---------------------------------------------------------------------------
# Reading the cache from S3 (shared by API handler and static JSON generator)
# ---------------------------------------------------------------------------

_CACHE_TTL_SECONDS = 300
_cache: dict[str, Any] = {"entries": None, "expires": 0.0}


def load_season_dates(s3_client, bucket: str | None = None) -> dict[str, dict]:
    """Load fresh season-date entries from S3, cached for 5 minutes.

    Returns {} when the file is missing or unreadable so callers degrade to
    "no dates" instead of failing the request.
    """
    now = time.time()
    if _cache["entries"] is not None and now < _cache["expires"]:
        return _cache["entries"]

    bucket = bucket or os.environ.get("WEBSITE_BUCKET")
    entries: dict[str, dict] = {}
    if bucket and s3_client is not None:
        try:
            response = s3_client.get_object(Bucket=bucket, Key=SEASON_DATES_S3_KEY)
            data = json.loads(response["Body"].read().decode("utf-8"))
            entries = fresh_entries(data)
        except Exception as e:
            logger.info("Season dates not loaded from S3: %s", e)

    _cache["entries"] = entries
    _cache["expires"] = now + _CACHE_TTL_SECONDS
    return entries


def clear_cache() -> None:
    """Reset the in-memory cache (tests)."""
    _cache["entries"] = None
    _cache["expires"] = 0.0
