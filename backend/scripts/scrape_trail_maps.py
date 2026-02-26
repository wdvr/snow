#!/usr/bin/env python3
"""
Trail Map Scraper

Finds trail map image URLs for all resorts in resorts.json.

Sources:
1. skiresort.info - DZI tiles (highest quality). Resort pages have trail map tabs
   at /ski-resort/{slug}/trail-map/ with JavaScript refs to trailmap_{ID}.
   The tile image is at: /uploads/tx_mgskiresort/trailmapsV2/trailmap_{ID}_files/0/0_0.jpg
2. snow-forecast.com - Direct JPEGs at /pistemaps/{Slug}_pistemap.jpg

Usage:
    python scrape_trail_maps.py                    # Full run
    python scrape_trail_maps.py --resume           # Continue from where it left off
    python scrape_trail_maps.py --limit 10         # Only process 10 resorts
    python scrape_trail_maps.py --resort-id alta   # Process a single resort
"""

import argparse
import json
import logging
import math
import re
import sys
import time
from pathlib import Path

import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"
RESORTS_FILE = DATA_DIR / "resorts.json"
OUTPUT_FILE = DATA_DIR / "resort_trail_maps.json"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
REQUEST_DELAY = 0.5  # Seconds between requests

# Manual slug overrides for resorts where our resort_id doesn't match skiresort.info's slug.
# Format: our_resort_id -> skiresort.info slug
SKIRESORT_INFO_SLUG_OVERRIDES = {
    # Verified overrides: our resort_id -> skiresort.info slug.
    # Only listed when our resort_id does NOT work as a direct slug on skiresort.info.
    # Each mapping has been verified by testing the actual trail-map URL.
    #
    # Many resort IDs in our data already match skiresort.info slugs directly
    # (e.g., whiteface-lake-placid, les-2-alpes, winter-park-resort, etc.)
    # and do NOT need overrides.
    #
    # --- Alps (France) ---
    "chamonix": "brevent-flegere-chamonix",  # Chamonix split into areas; Brevent-Flegere is main
    "courchevel": "les-3-vallees-val-thorens-les-menuires-meribel-courchevel",
    "meribel": "les-3-vallees-val-thorens-les-menuires-meribel-courchevel",
    "val-disere": "tignes-val-disere",
    "tignes": "tignes-val-disere",
    "les-arcs": "les-arcs-peisey-vallandry-paradiski",
    "la-plagne": "la-plagne-paradiski",
    #
    # --- Alps (Switzerland) ---
    "zermatt": "zermatt-breuil-cervinia-valtournenche-matterhorn",
    "verbier": "4-vallees-verbier-la-tzoumaz-nendaz-veysonnaz-thyon",
    #
    # --- Alps (Austria) ---
    "st-anton": "st-anton-st-christoph-stuben-lech-zuers-warth-schroecken-ski-arlberg",
    "lech-zuers": "st-anton-st-christoph-stuben-lech-zuers-warth-schroecken-ski-arlberg",
    "kitzbuehel": "kitzski-kitzbuehel-kirchberg",
    "kitzski-kitzbuhel-kirchberg": "kitzski-kitzbuehel-kirchberg",  # umlaut mismatch
    "saalbach-hinterglemm": "saalbach-hinterglemm-leogang-fieberbrunn-skicircus",
    "solden": "soelden",
    "ischgl": "ischgl-samnaun-silvretta-arena",
    #
    # --- Alps (Italy) ---
    "cortina": "cortina-dampezzo",
    #
    # --- Scandinavia ---
    "are": "aare",  # Swedish Åre -> 'aare' on skiresort.info
    #
    # --- Japan ---
    "niseko": "niseko-united-annupurigrand-hirafuhanazononiseko-village",
    "hakuba": "happo-one-hakuba",  # Our 'hakuba' resort is Happo-One
    #
    # --- North America ---
    "aspen": "aspen-mountain",  # Aspen Snowmass split; use Aspen Mountain
    "big-bear": "bear-mountain-big-bear-lake",
    "revelstoke": "revelstoke-mountain-resort",
    "sunshine-village": "banff-sunshine",
    "sugarbush": "sugarbush-resort",
    "sunday-river": "sunday-river-resort",
    "sugarloaf": "sugarloaf-mountain",
    "stratton": "stratton-mountain",
    "snoqualmie-pass": "the-summit-at-snoqualmie",
}

# Snow-forecast.com slug overrides for resorts where our resort_id doesn't map cleanly.
SNOW_FORECAST_SLUG_OVERRIDES = {
    "whistler-blackcomb": "Whistler-Blackcomb",
    "big-white": "Big-White",
    "revelstoke": "Revelstoke",
    "silver-star": "Silver-Star",
    "sun-peaks": "Sun-Peaks",
    "red-mountain": "Red-Mountain-Resort",
    "chamonix": "Chamonix",
    "val-disere": "Val-dIsere",
    "zermatt": "Zermatt",
    "verbier": "Verbier",
    "st-moritz": "St-Moritz",
    "st-anton": "St-Anton",
    "cortina": "Cortina-dAmpezzo",
    "cortina-d-ampezzo": "Cortina-dAmpezzo",
    "niseko": "Niseko",
    "hakuba": "Hakuba",
    "park-city": "Park-City",
    "jackson-hole": "Jackson-Hole",
    "aspen": "Aspen",
    "mammoth-mountain": "Mammoth",
    "palisades-tahoe": "Squaw-Valley",
    "big-sky": "Big-Sky",
    "are": "Are",
    "thredbo": "Thredbo",
    "the-remarkables": "Remarkables",
    "coronet-peak": "Coronet-Peak",
}


def load_resorts(path: Path) -> list[dict]:
    """Load resorts from resorts.json."""
    with open(path) as f:
        data = json.load(f)
    return data["resorts"]


def load_existing_output(path: Path) -> dict:
    """Load existing output file if it exists."""
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


def save_output(path: Path, data: dict) -> None:
    """Save output to JSON file."""
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def name_to_snow_forecast_slug(name: str) -> str:
    """Convert a resort name to a snow-forecast.com slug.

    snow-forecast uses Title-Case-Hyphens format.
    """
    # Remove parenthetical suffixes and special chars
    slug = re.sub(r"\s*[–—]\s*.*$", "", name)  # Remove " – suffix"
    slug = re.sub(r"\s*\(.*?\)", "", slug)  # Remove (parenthetical)
    slug = re.sub(r"[''`]", "", slug)
    # Handle accented characters
    slug = re.sub(r"[àáâãäå]", "a", slug)
    slug = re.sub(r"[èéêë]", "e", slug)
    slug = re.sub(r"[ìíîï]", "i", slug)
    slug = re.sub(r"[òóôõö]", "o", slug)
    slug = re.sub(r"[ùúûü]", "u", slug)
    slug = re.sub(r"[ñ]", "n", slug)
    slug = re.sub(r"[ç]", "c", slug)

    # Split into words, title case, rejoin with hyphens
    words = slug.split()
    return "-".join(words)


def try_skiresort_info(
    resort_id: str, resort_name: str, session: requests.Session
) -> dict | None:
    """Try to find trail map on skiresort.info.

    Returns dict with trailmap info or None.
    """
    # Determine which slug to use
    slug = SKIRESORT_INFO_SLUG_OVERRIDES.get(resort_id, resort_id)

    url = f"https://www.skiresort.info/ski-resort/{slug}/trail-map/"

    try:
        r = session.get(url, timeout=15, allow_redirects=False)

        # If we got a redirect to homepage, the slug is wrong
        if r.status_code in (301, 302):
            location = r.headers.get("Location", "")
            if location.rstrip("/") == "https://www.skiresort.info":
                return None
            # Follow the redirect and check the new page
            r = session.get(location, timeout=15)

        if r.status_code != 200:
            return None

        # Find trailmap IDs in the page
        trailmap_ids = re.findall(r"init_trailmap_(\d+)", r.text)
        if not trailmap_ids:
            return None

        # Use the first trail map ID (primary map)
        primary_id = int(trailmap_ids[0])
        all_ids = [int(tid) for tid in trailmap_ids]

        # DZI tile base path
        dzi_base = (
            f"https://www.skiresort.info/uploads/tx_mgskiresort/"
            f"trailmapsV2/trailmap_{primary_id}"
        )
        xml_url = f"{dzi_base}.xml"

        # Fetch XML to get dimensions for computing zoom levels
        image_width = None
        image_height = None
        # Default to level 8 which gives ~200px thumbnails for typical trail maps
        # (most trail maps are 3000-10000px wide, level 8 = 254px single tile)
        thumbnail_url = f"{dzi_base}_files/8/0_0.jpg"
        try:
            time.sleep(REQUEST_DELAY)
            xml_r = session.get(xml_url, timeout=10)
            if xml_r.status_code == 200:
                w_match = re.search(r'Width="(\d+)"', xml_r.text)
                h_match = re.search(r'Height="(\d+)"', xml_r.text)
                if w_match and h_match:
                    image_width = int(w_match.group(1))
                    image_height = int(h_match.group(1))

                    # Calculate the zoom level where the image fits in a single
                    # tile (~254px). This gives a useful thumbnail.
                    # DZI max_level = ceil(log2(max(w, h)))
                    # At level L, effective size = ceil(dim / 2^(max_level - L))
                    # We want the highest level where both dims <= 254 (single tile)
                    max_dim = max(image_width, image_height)
                    max_level = math.ceil(math.log2(max_dim))
                    # Find highest single-tile level
                    thumb_level = 8  # default fallback
                    for lv in range(max_level, -1, -1):
                        ew = math.ceil(image_width / (2 ** (max_level - lv)))
                        eh = math.ceil(image_height / (2 ** (max_level - lv)))
                        if ew <= 254 and eh <= 254:
                            thumb_level = lv
                            break
                    thumbnail_url = f"{dzi_base}_files/{thumb_level}/0_0.jpg"
        except requests.RequestException:
            pass  # XML fetch failed; use level-8 default (good for most maps)

        result = {
            "skiresort_info_slug": slug,
            "skiresort_info_trailmap_id": primary_id,
            "skiresort_info_all_trailmap_ids": all_ids,
            "skiresort_info_image_url": thumbnail_url,
            "skiresort_info_xml_url": xml_url,
            "skiresort_info_image_width": image_width,
            "skiresort_info_image_height": image_height,
        }

        return result

    except requests.RequestException as e:
        logger.debug(f"skiresort.info request failed for {resort_id}: {e}")
        return None


def try_snow_forecast(
    resort_id: str, resort_name: str, session: requests.Session
) -> str | None:
    """Try to find trail map on snow-forecast.com.

    Returns the pistemap URL if it exists, or None.
    """
    # Check override first, then generate from name
    if resort_id in SNOW_FORECAST_SLUG_OVERRIDES:
        slug = SNOW_FORECAST_SLUG_OVERRIDES[resort_id]
    else:
        slug = name_to_snow_forecast_slug(resort_name)

    url = f"https://www.snow-forecast.com/pistemaps/{slug}_pistemap.jpg"

    try:
        r = session.head(url, timeout=10, allow_redirects=True)
        if r.status_code == 200:
            return url
        return None
    except requests.RequestException:
        return None


def main():
    parser = argparse.ArgumentParser(description="Scrape trail map URLs for resorts")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from where we left off (skip resorts already in output)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Maximum number of resorts to process (0 = all)",
    )
    parser.add_argument(
        "--resort-id",
        type=str,
        default=None,
        help="Process a single resort by ID",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=RESORTS_FILE,
        help="Input resorts.json path",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_FILE,
        help="Output trail maps JSON path",
    )
    parser.add_argument(
        "--skip-skiresort-info",
        action="store_true",
        help="Skip skiresort.info (only check snow-forecast.com)",
    )
    parser.add_argument(
        "--skip-snow-forecast",
        action="store_true",
        help="Skip snow-forecast.com (only check skiresort.info)",
    )
    args = parser.parse_args()

    # Load resorts
    resorts = load_resorts(args.input)
    logger.info(f"Loaded {len(resorts)} resorts from {args.input}")

    # Filter to single resort if specified
    if args.resort_id:
        resorts = [r for r in resorts if r["resort_id"] == args.resort_id]
        if not resorts:
            logger.error(f"Resort '{args.resort_id}' not found")
            sys.exit(1)
        logger.info(f"Processing single resort: {resorts[0]['name']}")

    # Load existing output for resume
    output = {}
    if args.resume:
        output = load_existing_output(args.output)
        logger.info(f"Loaded {len(output)} existing entries for resume")

    # Set up session
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    # Process resorts
    processed = 0
    skipped = 0
    found_skiresort = 0
    found_snowforecast = 0
    found_none = 0

    for _i, resort in enumerate(resorts):
        rid = resort["resort_id"]

        # Skip if already processed (resume mode)
        if args.resume and rid in output:
            skipped += 1
            continue

        # Check limit
        if args.limit and processed >= args.limit:
            logger.info(f"Reached limit of {args.limit} resorts")
            break

        # Scrape
        result = {
            "name": resort["name"],
            "skiresort_info_trailmap_id": None,
            "skiresort_info_all_trailmap_ids": None,
            "skiresort_info_slug": None,
            "skiresort_info_image_url": None,
            "skiresort_info_xml_url": None,
            "skiresort_info_image_width": None,
            "skiresort_info_image_height": None,
            "snow_forecast_url": None,
            "source": None,
        }

        # Try skiresort.info
        if not args.skip_skiresort_info:
            ski_result = try_skiresort_info(rid, resort["name"], session)
            if ski_result:
                result.update(ski_result)
                result["source"] = "skiresort.info"
                found_skiresort += 1
            time.sleep(REQUEST_DELAY)

        # Try snow-forecast.com
        if not args.skip_snow_forecast:
            sf_url = try_snow_forecast(rid, resort["name"], session)
            if sf_url:
                result["snow_forecast_url"] = sf_url
                if not result["source"]:
                    result["source"] = "snow-forecast.com"
                    found_snowforecast += 1
            time.sleep(REQUEST_DELAY)

        if not result["source"]:
            found_none += 1

        output[rid] = result
        processed += 1

        # Log progress
        source_str = result["source"] or "NONE"
        if processed % 10 == 0 or args.limit or args.resort_id:
            logger.info(f"[{processed}/{len(resorts) - skipped}] {rid}: {source_str}")
        else:
            logger.debug(f"[{processed}] {rid}: {source_str}")

        # Save periodically (every 25 resorts)
        if processed % 25 == 0:
            save_output(args.output, output)
            logger.info(f"Saved progress ({len(output)} entries)")

    # Final save
    save_output(args.output, output)

    # Summary
    logger.info("=" * 60)
    logger.info("Processing complete!")
    logger.info(f"  Total processed: {processed}")
    logger.info(f"  Skipped (resume): {skipped}")
    logger.info(f"  Found on skiresort.info: {found_skiresort}")
    logger.info(f"  Found on snow-forecast.com (only): {found_snowforecast}")
    logger.info(f"  Not found on either: {found_none}")
    logger.info(f"  Total entries in output: {len(output)}")
    logger.info(f"  Output saved to: {args.output}")


if __name__ == "__main__":
    main()
