"""Lambda handler that refreshes per-resort season opening/closing dates.

Fetches the OnTheSnow resort page for every resort in
``services/onthesnow_season_pages.json`` and writes the projected/announced
opening and closing dates to ``data/season-dates.json`` in the website bucket.
The API handler and static JSON generator merge that file into the resort
payload (see services/season_dates.py).

Each OnTheSnow resort page also carries the status of several nearby resorts,
so a resort whose record already arrived with a neighbour's page is not
fetched again. Pages are fetched least-recently-attempted first; a run that
nears the Lambda timeout stops early and keeps earlier entries, so the next
run picks up where this one left off.

Lambda config: 256MB memory, 900s timeout, scheduled every 12 hours.
"""

import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import boto3
import requests
from botocore.config import Config as BotoConfig

from services.season_dates import (
    SEASON_DATES_S3_KEY,
    SEASON_DATES_SOURCE,
    fresh_entries,
    normalize_record,
    parse_onthesnow_records,
)

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
WEBSITE_BUCKET = os.environ.get("WEBSITE_BUCKET", f"snow-tracker-website-{ENVIRONMENT}")
AWS_REGION = os.environ.get("AWS_REGION_NAME", "us-west-2")

MAPPING_PATH = Path(__file__).resolve().parent.parent / (
    "services/onthesnow_season_pages.json"
)

USER_AGENT = (
    "Mozilla/5.0 (compatible; PowderChaser/1.0; +https://github.com/snowtracker)"
)
REQUEST_TIMEOUT_SECONDS = 30
# Pages fetched concurrently per batch, and the pause between batches.
CONCURRENCY = 4
BATCH_DELAY_SECONDS = 1.0
# Stop starting new batches when less than this much time is left.
MIN_TIME_BUFFER_MS = 90000

_boto_config = BotoConfig(retries={"max_attempts": 3})
s3_client = boto3.client("s3", region_name=AWS_REGION, config=_boto_config)


def get_remaining_time_ms(context) -> int:
    """Remaining Lambda execution time in milliseconds."""
    if context and hasattr(context, "get_remaining_time_in_millis"):
        return context.get_remaining_time_in_millis()
    return 600000


def load_mapping(path: Path = MAPPING_PATH) -> dict[str, dict[str, str]]:
    """Load {resort_id: {"url", "uuid"}} for resorts covered by OnTheSnow."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    resorts = data.get("resorts", {}) if isinstance(data, dict) else {}
    return {
        rid: m
        for rid, m in resorts.items()
        if isinstance(m, dict) and m.get("url") and m.get("uuid")
    }


def _load_previous_cache() -> dict[str, Any]:
    try:
        response = s3_client.get_object(Bucket=WEBSITE_BUCKET, Key=SEASON_DATES_S3_KEY)
        data = json.loads(response["Body"].read().decode("utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.info(f"No previous season-dates cache loaded: {e}")
        return {}


def fetch_page(session: requests.Session, url: str) -> dict[str, dict[str, Any]]:
    """Fetch one OnTheSnow page and return its resort status records."""
    response = session.get(url, timeout=REQUEST_TIMEOUT_SECONDS)
    response.raise_for_status()
    return parse_onthesnow_records(response.text)


def season_dates_refresh_handler(event: dict[str, Any], context) -> dict[str, Any]:
    """Refresh season dates for all mapped resorts and write the S3 cache."""
    start = datetime.now(UTC)
    now_iso = start.isoformat()
    today = start.date()
    logger.info(f"Starting season dates refresh at {now_iso}")

    stats: dict[str, Any] = {
        "mapped_resorts": 0,
        "pages_fetched": 0,
        "page_errors": 0,
        "records_seen": 0,
        "resorts_updated": 0,
        "resorts_without_dates": 0,
        "timeout_graceful": False,
    }

    mapping = load_mapping()
    stats["mapped_resorts"] = len(mapping)

    previous = _load_previous_cache()
    entries = {rid: e for rid, e in fresh_entries(previous).items() if rid in mapping}
    last_attempted: dict[str, str] = {
        rid: ts
        for rid, ts in (previous.get("last_attempted") or {}).items()
        if rid in mapping
    }
    stats["carried_over"] = len(entries)

    ordered = sorted(mapping, key=lambda rid: last_attempted.get(rid, ""))
    harvested: dict[str, dict[str, Any]] = {}
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "en"})

    def fetch(rid: str) -> tuple[str, dict[str, dict[str, Any]] | None]:
        try:
            return rid, fetch_page(session, mapping[rid]["url"])
        except Exception as e:
            logger.warning(f"Season dates fetch failed for {rid}: {e}")
            return rid, None

    pending = list(ordered)
    with ThreadPoolExecutor(max_workers=CONCURRENCY) as pool:
        while pending:
            if get_remaining_time_ms(context) < MIN_TIME_BUFFER_MS:
                stats["timeout_graceful"] = True
                logger.warning(
                    f"Approaching timeout; {len(pending)} resorts left for next run"
                )
                break
            batch: list[str] = []
            while pending and len(batch) < CONCURRENCY:
                rid = pending.pop(0)
                # Already covered by a neighbour's page in this run
                if mapping[rid]["uuid"] in harvested:
                    continue
                batch.append(rid)
            if not batch:
                break
            for rid, records in pool.map(fetch, batch):
                last_attempted[rid] = now_iso
                if records is None:
                    stats["page_errors"] += 1
                    continue
                stats["pages_fetched"] += 1
                harvested.update(records)
            if pending:
                time.sleep(BATCH_DELAY_SECONDS)

    stats["records_seen"] = len(harvested)
    for rid, m in mapping.items():
        record = harvested.get(str(m["uuid"]))
        if record is None:
            continue
        last_attempted[rid] = now_iso
        normalized = normalize_record(record, today)
        if normalized is None:
            # Source has no usable dates now: drop rather than serve stale ones
            entries.pop(rid, None)
            stats["resorts_without_dates"] += 1
            continue
        entries[rid] = {
            **normalized,
            "source_url": m["url"],
            "fetched_at": now_iso,
        }
        stats["resorts_updated"] += 1

    output = {
        "generated_at": now_iso,
        "source": SEASON_DATES_SOURCE,
        "count": len(entries),
        "resorts": entries,
        "last_attempted": last_attempted,
    }
    s3_client.put_object(
        Bucket=WEBSITE_BUCKET,
        Key=SEASON_DATES_S3_KEY,
        Body=json.dumps(output, separators=(",", ":")).encode("utf-8"),
        ContentType="application/json",
        CacheControl="public, max-age=3600",
    )

    stats["resorts_with_dates"] = len(entries)
    stats["duration_seconds"] = round((datetime.now(UTC) - start).total_seconds(), 1)
    logger.info(f"Season dates refresh complete: {json.dumps(stats)}")
    return {"statusCode": 200, "body": json.dumps({"stats": stats})}
