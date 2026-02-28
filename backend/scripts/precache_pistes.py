#!/usr/bin/env python3
"""
Piste & Lift Precacher

Queries the Overpass API for piste ways and aerial lifts near each resort,
converts them to a compact GeoJSON-like format, and uploads to S3.

The resulting files are used by the iOS app for offline piste map overlays.

Usage:
    python3 backend/scripts/precache_pistes.py                     # Full run
    python3 backend/scripts/precache_pistes.py --dry-run            # Skip S3 upload
    python3 backend/scripts/precache_pistes.py --resort alta        # Single resort
    python3 backend/scripts/precache_pistes.py --resort alta --dry-run
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path

import boto3
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"
RESORTS_FILE = DATA_DIR / "resorts.json"

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
S3_BUCKET = "snow-tracker-website-prod-383757231925"
S3_PREFIX = "data/pistes"
AWS_REGION = "us-west-2"

BBOX_OFFSET = 0.05  # ±0.05° around resort center (~5.5 km)
BATCH_SIZE = 5
BATCH_DELAY = 2  # seconds between batches

# Pass through OSM piste:difficulty values (iOS PisteDifficulty enum matches these)
DIFFICULTY_MAP = {
    "novice": "novice",
    "easy": "easy",
    "intermediate": "intermediate",
    "advanced": "advanced",
    "expert": "expert",
    "freeride": "freeride",
    "extreme": "expert",
}

# Map Overpass aerialway values to our lift type names
LIFT_TYPE_MAP = {
    "cable_car": "cable_car",
    "gondola": "gondola",
    "mixed_lift": "gondola",
    "chair_lift": "chair_lift",
    "drag_lift": "drag_lift",
    "t-bar": "drag_lift",
    "j-bar": "drag_lift",
    "platter": "drag_lift",
    "rope_tow": "drag_lift",
    "magic_carpet": "magic_carpet",
    "funicular": "funicular",
}


def load_resorts(resort_filter: str | None = None) -> list[dict]:
    """Load resorts from resorts.json, optionally filtering to a single resort."""
    with open(RESORTS_FILE) as f:
        data = json.load(f)

    resorts = data["resorts"]

    if resort_filter:
        resorts = [r for r in resorts if r["resort_id"] == resort_filter]
        if not resorts:
            logger.error(f"Resort '{resort_filter}' not found in resorts.json")
            sys.exit(1)

    return resorts


def build_overpass_query(lat: float, lon: float) -> str:
    """Build an Overpass QL query for pistes and lifts within a bounding box."""
    south = lat - BBOX_OFFSET
    north = lat + BBOX_OFFSET
    west = lon - BBOX_OFFSET
    east = lon + BBOX_OFFSET

    bbox = f"{south},{west},{north},{east}"

    query = f"""
[out:json][timeout:30];
(
  way["piste:type"="downhill"]({bbox});
  way["aerialway"]({bbox});
);
out body geom;
"""
    return query.strip()


def query_overpass(lat: float, lon: float) -> dict | None:
    """Query the Overpass API and return the raw JSON response."""
    query = build_overpass_query(lat, lon)

    try:
        resp = requests.post(
            OVERPASS_URL,
            data={"data": query},
            timeout=60,
            headers={"User-Agent": "PowderChaser-PisteCacher/1.0"},
        )
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.HTTPError as e:
        if resp.status_code == 429:
            logger.warning("Rate limited by Overpass API, waiting 30s...")
            time.sleep(30)
            return query_overpass(lat, lon)  # Retry once
        logger.error(f"Overpass HTTP error: {e}")
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Overpass request error: {e}")
        return None
    except json.JSONDecodeError as e:
        logger.error(f"Overpass JSON decode error: {e}")
        return None


def parse_overpass_response(data: dict) -> dict:
    """Parse Overpass response into our compact piste/lift format."""
    pistes = []
    lifts = []

    for element in data.get("elements", []):
        if element.get("type") != "way":
            continue

        tags = element.get("tags", {})
        geometry = element.get("geometry", [])

        if not geometry:
            continue

        coords = [[round(pt["lat"], 6), round(pt["lon"], 6)] for pt in geometry]

        # Determine if this is a piste or a lift
        if "piste:type" in tags:
            raw_difficulty = tags.get("piste:difficulty", "unknown")
            difficulty = DIFFICULTY_MAP.get(raw_difficulty, raw_difficulty)
            name = tags.get("piste:name") or tags.get("name") or ""

            pistes.append(
                {
                    "name": name,
                    "difficulty": difficulty,
                    "coords": coords,
                }
            )

        elif "aerialway" in tags:
            raw_type = tags.get("aerialway", "unknown")
            lift_type = LIFT_TYPE_MAP.get(raw_type, raw_type)
            name = tags.get("name") or ""

            lifts.append(
                {
                    "name": name,
                    "type": lift_type,
                    "coords": coords,
                }
            )

    return {"pistes": pistes, "lifts": lifts}


def upload_to_s3(s3_client, resort_id: str, data: dict) -> bool:
    """Upload resort piste data to S3."""
    key = f"{S3_PREFIX}/{resort_id}.json"
    body = json.dumps(data, separators=(",", ":"))  # Compact JSON

    try:
        s3_client.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=body.encode("utf-8"),
            ContentType="application/json",
            CacheControl="public, max-age=604800",
        )
        return True
    except Exception as e:
        logger.error(f"S3 upload failed for {resort_id}: {e}")
        return False


def s3_key_exists(s3_client, resort_id: str) -> bool:
    """Check if a piste file already exists in S3."""
    try:
        s3_client.head_object(Bucket=S3_BUCKET, Key=f"{S3_PREFIX}/{resort_id}.json")
        return True
    except Exception:
        return False


def process_resort(
    resort: dict, s3_client, dry_run: bool, skip_existing: bool = False
) -> dict:
    """Process a single resort. Returns a result dict with status info."""
    resort_id = resort["resort_id"]
    name = resort.get("name", resort_id)
    lat = resort["latitude"]
    lon = resort["longitude"]

    result = {
        "resort_id": resort_id,
        "name": name,
        "pistes": 0,
        "lifts": 0,
        "uploaded": False,
        "skipped": False,
        "error": None,
    }

    # Skip if already cached
    if skip_existing and s3_client and s3_key_exists(s3_client, resort_id):
        result["skipped"] = True
        logger.info(f"  {resort_id} ({name}): already cached, skipping")
        return result

    # Query Overpass
    raw = query_overpass(lat, lon)
    if raw is None:
        result["error"] = "Overpass query failed"
        return result

    # Parse response
    parsed = parse_overpass_response(raw)
    n_pistes = len(parsed["pistes"])
    n_lifts = len(parsed["lifts"])
    result["pistes"] = n_pistes
    result["lifts"] = n_lifts

    # Skip empty results
    if n_pistes == 0 and n_lifts == 0:
        result["skipped"] = True
        logger.info(f"  {resort_id} ({name}): no features found, skipping")
        return result

    size_kb = len(json.dumps(parsed, separators=(",", ":"))) / 1024

    if dry_run:
        logger.info(
            f"  {resort_id} ({name}): {n_pistes} pistes, {n_lifts} lifts, "
            f"{size_kb:.1f} KB [DRY RUN]"
        )
        result["uploaded"] = True  # Would have uploaded
        return result

    # Upload to S3
    if upload_to_s3(s3_client, resort_id, parsed):
        logger.info(
            f"  {resort_id} ({name}): {n_pistes} pistes, {n_lifts} lifts, "
            f"{size_kb:.1f} KB -> s3://{S3_BUCKET}/{S3_PREFIX}/{resort_id}.json"
        )
        result["uploaded"] = True
    else:
        result["error"] = "S3 upload failed"

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Precache piste and lift data from OpenStreetMap for all resorts"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip S3 uploads, just print what would be uploaded",
    )
    parser.add_argument(
        "--resort",
        type=str,
        default=None,
        help="Process a single resort by resort_id (for testing)",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip resorts that already have a file in S3",
    )
    args = parser.parse_args()

    # Load resorts
    resorts = load_resorts(args.resort)
    logger.info(f"Loaded {len(resorts)} resort(s) from {RESORTS_FILE}")

    # Initialize S3 client
    s3_client = None
    if not args.dry_run:
        s3_client = boto3.client("s3", region_name=AWS_REGION)
        logger.info(f"S3 target: s3://{S3_BUCKET}/{S3_PREFIX}/")
    else:
        logger.info("DRY RUN mode — no S3 uploads will be performed")

    # Process in batches
    results = []
    total = len(resorts)

    for batch_start in range(0, total, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, total)
        batch = resorts[batch_start:batch_end]
        batch_num = (batch_start // BATCH_SIZE) + 1
        total_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE

        logger.info(
            f"Batch {batch_num}/{total_batches} "
            f"(resorts {batch_start + 1}-{batch_end} of {total})"
        )

        for resort in batch:
            result = process_resort(resort, s3_client, args.dry_run, args.skip_existing)
            results.append(result)

        # Delay between batches (skip after last batch)
        if batch_end < total:
            time.sleep(BATCH_DELAY)

    # Summary
    uploaded = sum(1 for r in results if r["uploaded"])
    skipped = sum(1 for r in results if r["skipped"])
    errors = sum(1 for r in results if r["error"])
    total_pistes = sum(r["pistes"] for r in results)
    total_lifts = sum(r["lifts"] for r in results)

    logger.info("=" * 60)
    logger.info("SUMMARY")
    logger.info(f"  Total resorts processed: {len(results)}")
    logger.info(f"  Uploaded:  {uploaded}")
    logger.info(f"  Skipped (no features): {skipped}")
    logger.info(f"  Errors:    {errors}")
    logger.info(f"  Total pistes: {total_pistes}")
    logger.info(f"  Total lifts:  {total_lifts}")

    if errors > 0:
        logger.info("  Errors:")
        for r in results:
            if r["error"]:
                logger.info(f"    {r['resort_id']}: {r['error']}")

    logger.info("=" * 60)

    # Exit with error code if there were failures
    if errors > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
