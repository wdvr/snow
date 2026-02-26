#!/usr/bin/env python3
"""Fix trail map zoom levels and scrape resort logos from websites.

1. Fix existing trail map URLs: replace level 0 (1x1 pixel) with level 8 (~200px)
2. Scrape actual logo images from resort websites (not favicons)
3. Try to find trail maps for resorts that don't have them yet
"""

import json
import logging
import re
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)

RESORTS_FILE = Path(__file__).parent.parent / "data" / "resorts.json"
REQUEST_DELAY = 0.5  # seconds between requests


def load_resorts() -> dict:
    with open(RESORTS_FILE) as f:
        return json.load(f)


def save_resorts(data: dict) -> None:
    with open(RESORTS_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    # Ensure trailing newline
    with open(RESORTS_FILE, "a") as f:
        f.write("\n")


def fix_trail_map_zoom_levels(resorts: list[dict]) -> int:
    """Fix trail map URLs that use level 0 (1x1 pixel) to use level 8 (~200px)."""
    fixed = 0
    for resort in resorts:
        url = resort.get("trail_map_url")
        if not url:
            continue
        # Fix level 0 URLs: trailmap_XXX_files/0/0_0.jpg -> trailmap_XXX_files/8/0_0.jpg
        if "_files/0/0_0.jpg" in url:
            new_url = url.replace("_files/0/0_0.jpg", "_files/8/0_0.jpg")
            resort["trail_map_url"] = new_url
            fixed += 1
            logger.info(f"  Fixed zoom: {resort['resort_id']}")
    return fixed


def scrape_logo_from_website(url: str, session: requests.Session) -> str | None:
    """Scrape the actual logo image URL from a resort website.

    Looks for:
    1. <img> tags with "logo" in class, id, alt, or src
    2. <link rel="icon"> with larger sizes
    3. Open Graph image (<meta property="og:image">)
    4. SVG logos
    """
    try:
        time.sleep(REQUEST_DELAY)
        resp = session.get(url, timeout=15, allow_redirects=True)
        if resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.text, "html.parser")
        base_url = resp.url  # after redirects
        parsed_base = urlparse(base_url)
        base_origin = f"{parsed_base.scheme}://{parsed_base.netloc}"

        def resolve_url(src: str) -> str | None:
            if not src:
                return None
            src = src.strip()
            if src.startswith("data:"):
                return None
            if src.startswith("//"):
                return f"https:{src}"
            if src.startswith("/"):
                return f"{base_origin}{src}"
            if src.startswith("http"):
                return src
            return f"{base_origin}/{src}"

        candidates: list[tuple[int, str]] = []  # (priority, url)

        # 1. Look for <img> with "logo" in attributes
        for img in soup.find_all("img"):
            src = img.get("src", "")
            alt = img.get("alt", "")
            cls = " ".join(img.get("class", []))
            img_id = img.get("id", "")
            srcset = img.get("srcset", "")

            logo_match = any(
                "logo" in attr.lower() for attr in [src, alt, cls, img_id, srcset]
            )
            if logo_match:
                resolved = resolve_url(src)
                if resolved:
                    # Prefer SVG > PNG > others
                    priority = 10
                    if ".svg" in resolved.lower():
                        priority = 1
                    elif ".png" in resolved.lower():
                        priority = 2
                    elif ".webp" in resolved.lower():
                        priority = 3
                    candidates.append((priority, resolved))

                # Also check srcset for higher-res versions
                if srcset:
                    for part in srcset.split(","):
                        part = part.strip().split(" ")[0]
                        if part:
                            resolved_ss = resolve_url(part)
                            if resolved_ss and "logo" in resolved_ss.lower():
                                candidates.append((5, resolved_ss))

        # 2. Look for <a> or <div> with "logo" class/id containing <img>
        for container in soup.find_all(["a", "div", "span", "header"]):
            cls = " ".join(container.get("class", []))
            container_id = container.get("id", "")
            if "logo" in cls.lower() or "logo" in container_id.lower():
                for img in container.find_all("img"):
                    src = img.get("src")
                    resolved = resolve_url(src)
                    if resolved:
                        priority = 4
                        if ".svg" in resolved.lower():
                            priority = 1
                        elif ".png" in resolved.lower():
                            priority = 2
                        candidates.append((priority, resolved))

        # 3. Look for SVG inline logos
        for svg in soup.find_all("svg"):
            parent = svg.parent
            if parent:
                cls = " ".join(parent.get("class", []))
                parent_id = parent.get("id", "")
                if "logo" in cls.lower() or "logo" in parent_id.lower():
                    # Can't use inline SVG as URL, skip
                    pass

        # 4. Open Graph image (fallback - often a hero image, not logo)
        og_image = soup.find("meta", property="og:image")
        if og_image and og_image.get("content"):
            resolved = resolve_url(og_image["content"])
            if resolved:
                candidates.append((20, resolved))  # Low priority

        # 5. Apple touch icon (better than favicon)
        for link in soup.find_all("link", rel=lambda r: r and "apple-touch-icon" in r):
            href = link.get("href")
            resolved = resolve_url(href)
            if resolved:
                candidates.append((15, resolved))

        # Sort by priority and return best
        candidates.sort(key=lambda x: x[0])
        if candidates:
            return candidates[0][1]

        return None

    except Exception:
        return None


def scrape_logos_batch(resorts: list[dict], limit: int = 0) -> int:
    """Scrape logo URLs for resorts that have official websites."""
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
    )

    found = 0
    total = 0
    to_scrape = [r for r in resorts if r.get("website") and not r.get("logo_url")]
    if limit > 0:
        to_scrape = to_scrape[:limit]

    logger.info(f"\nScraping logos for {len(to_scrape)} resorts...")

    for i, resort in enumerate(to_scrape):
        website = resort["website"]
        resort_id = resort["resort_id"]
        total += 1

        if i % 50 == 0 and i > 0:
            logger.info(f"  Progress: {i}/{len(to_scrape)} ({found} found)")

        logo_url = scrape_logo_from_website(website, session)
        if logo_url:
            resort["logo_url"] = logo_url
            found += 1
            logger.info(f"  Logo found: {resort_id} -> {logo_url[:80]}...")

    logger.info(f"  Logos scraped: {found}/{total}")
    return found


def _generate_slugs(resort_name: str, resort_id: str) -> list[str]:
    """Generate multiple slug variations to try on skiresort.info."""
    # Base slug from name
    slug = resort_name.lower()
    # Transliterate common characters
    for src, dst in [
        ("ä", "ae"),
        ("ö", "oe"),
        ("ü", "ue"),
        ("ß", "ss"),
        ("é", "e"),
        ("è", "e"),
        ("ê", "e"),
        ("ë", "e"),
        ("á", "a"),
        ("à", "a"),
        ("â", "a"),
        ("å", "a"),
        ("ó", "o"),
        ("ò", "o"),
        ("ô", "o"),
        ("ø", "oe"),
        ("í", "i"),
        ("ì", "i"),
        ("î", "i"),
        ("ú", "u"),
        ("ù", "u"),
        ("û", "u"),
        ("ñ", "n"),
        ("ç", "c"),
        ("š", "s"),
        ("ž", "z"),
        ("č", "c"),
        ("ř", "r"),
        ("ď", "d"),
        ("ť", "t"),
        ("ň", "n"),
        ("ő", "oe"),
        ("ű", "ue"),
        ("ą", "a"),
        ("ę", "e"),
        ("ł", "l"),
        ("ś", "s"),
        ("ź", "z"),
        ("ż", "z"),
        ("ć", "c"),
    ]:
        slug = slug.replace(src, dst)
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    slug = slug.strip("-")

    slugs = [slug]

    # Also try the resort_id directly
    if resort_id != slug:
        slugs.append(resort_id)

    # Remove common suffixes
    for suffix in [
        "-ski-resort",
        "-resort",
        "-mountain",
        "-ski-area",
        "-ski-center",
        "-ski-centre",
        "-skigebiet",
        "-skicircus",
        "-ski-optimal",
        "-ski-world",
    ]:
        for s in list(slugs):
            if s.endswith(suffix):
                slugs.append(s[: -len(suffix)])

    # Remove country/region suffixes like parenthetical info
    # e.g. "osogovo-" from "Osogovo (Осогово)"
    for s in list(slugs):
        # Try splitting at first dash and using first part
        parts = s.split("-")
        if len(parts) > 2:
            # Try first two words
            slugs.append("-".join(parts[:2]))
            # Try first word only
            slugs.append(parts[0])

    # Remove duplicates while preserving order
    seen = set()
    unique = []
    for s in slugs:
        if s and s not in seen:
            seen.add(s)
            unique.append(s)
    return unique


def _extract_trailmap_url(html: str) -> str | None:
    """Extract trail map URL from skiresort.info page HTML."""
    trailmap_ids = re.findall(r"init_trailmap_(\d+)", html)
    if trailmap_ids:
        primary_id = trailmap_ids[0]
        return (
            f"https://www.skiresort.info/uploads/tx_mgskiresort/"
            f"trailmapsV2/trailmap_{primary_id}_files/8/0_0.jpg"
        )
    return None


def try_find_trail_map_skiresort(
    resort_id: str,
    resort_name: str,
    session: requests.Session,
) -> str | None:
    """Try to find trail map on skiresort.info via slug matching."""
    slugs = _generate_slugs(resort_name, resort_id)

    for try_slug in slugs:
        url = f"https://www.skiresort.info/ski-resort/{try_slug}/trail-map/"
        try:
            time.sleep(REQUEST_DELAY)
            resp = session.get(url, timeout=10, allow_redirects=False)
            if resp.status_code in (301, 302):
                location = resp.headers.get("Location", "")
                if location.rstrip("/") == "https://www.skiresort.info":
                    continue
                # Follow redirect to actual resort page
                if "/trail-map/" not in location:
                    location = location.rstrip("/") + "/trail-map/"
                resp = session.get(location, timeout=10)
            if resp.status_code != 200:
                continue

            result = _extract_trailmap_url(resp.text)
            if result:
                return result
        except Exception:
            continue

    return None


def try_find_trail_map_search(
    resort_name: str,
    session: requests.Session,
) -> str | None:
    """Try to find trail map on skiresort.info using their search."""
    # Clean name for search
    search_name = resort_name.split("(")[0].split("–")[0].split("-")[0].strip()
    search_url = f"https://www.skiresort.info/ski-resort/search/?q={search_name}"
    try:
        time.sleep(REQUEST_DELAY)
        resp = session.get(search_url, timeout=10)
        if resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.text, "html.parser")
        # Find first result link
        result_link = soup.select_one(".resort-list-item a[href*='/ski-resort/']")
        if not result_link:
            # Try alternative selector
            result_link = soup.select_one("a[href*='/ski-resort/'][href$='/']")
        if not result_link:
            return None

        href = result_link.get("href", "")
        if not href or "/ski-resort/" not in href:
            return None

        # Follow to trail-map page
        trail_map_url = f"https://www.skiresort.info{href}trail-map/"
        if href.startswith("http"):
            trail_map_url = f"{href.rstrip('/')}trail-map/"

        time.sleep(REQUEST_DELAY)
        resp = session.get(trail_map_url, timeout=10)
        if resp.status_code != 200:
            return None

        return _extract_trailmap_url(resp.text)
    except Exception:
        return None


def try_find_trail_map_on_website(
    website: str,
    session: requests.Session,
) -> str | None:
    """Try to find a trail/piste map image on the resort's own website."""
    # Trail map page path patterns to try
    map_paths = [
        "/trail-map",
        "/trailmap",
        "/trail-maps",
        "/piste-map",
        "/pistemap",
        "/piste-maps",
        "/mountain/trail-map",
        "/the-mountain/trail-map",
        "/mountain/map",
        "/mountain/piste-map",
        "/explore/trail-map",
        "/plan/trail-map",
        "/plan-your-trip/trail-map",
        "/pistenplan",
        "/pistenkarte",
        "/en/trail-map",
        "/en/piste-map",
        "/mountain",
        "/slopes",
        "/pistes",
    ]

    parsed = urlparse(website)
    base = f"{parsed.scheme}://{parsed.netloc}"

    for path in map_paths:
        url = f"{base}{path}"
        try:
            time.sleep(REQUEST_DELAY)
            resp = session.get(url, timeout=10, allow_redirects=True)
            if resp.status_code != 200:
                continue

            soup = BeautifulSoup(resp.text, "html.parser")

            # Look for large images that might be trail maps
            for img in soup.find_all("img"):
                src = img.get("src", "")
                alt = img.get("alt", "").lower()
                cls = " ".join(img.get("class", [])).lower()
                width = img.get("width", "")

                # Check if image seems to be a trail/piste map
                is_map = any(
                    kw in attr
                    for kw in [
                        "trail-map",
                        "trailmap",
                        "trail_map",
                        "piste-map",
                        "pistemap",
                        "piste_map",
                        "pistenplan",
                        "pistenkarte",
                        "pistekaart",
                        "slope-map",
                        "slopemap",
                        "mountain-map",
                    ]
                    for attr in [src.lower(), alt, cls]
                )
                if is_map and src:
                    # Resolve URL
                    if src.startswith("//"):
                        src = f"https:{src}"
                    elif src.startswith("/"):
                        src = f"{base}{src}"
                    elif not src.startswith("http"):
                        src = f"{base}/{src}"
                    # Filter out tiny images
                    if width and width.isdigit() and int(width) < 100:
                        continue
                    return src

        except Exception:
            continue

    return None


def _generate_snow_forecast_slugs(resort_name: str) -> list[str]:
    """Generate slug variations for snow-forecast.com pistemap URLs."""
    # snow-forecast uses Title-Case-Dashes format
    name = resort_name.split("(")[0].split("–")[0].strip()
    # Transliterate
    for src, dst in [
        ("ä", "a"),
        ("ö", "o"),
        ("ü", "u"),
        ("ß", "ss"),
        ("é", "e"),
        ("è", "e"),
        ("ê", "e"),
        ("á", "a"),
        ("à", "a"),
        ("â", "a"),
        ("å", "a"),
        ("ó", "o"),
        ("ô", "o"),
        ("ø", "o"),
        ("í", "i"),
        ("ú", "u"),
        ("ñ", "n"),
        ("ç", "c"),
        ("š", "s"),
        ("ž", "z"),
        ("č", "c"),
        ("ř", "r"),
        ("ő", "o"),
        ("ű", "u"),
        ("ą", "a"),
        ("ę", "e"),
        ("ł", "l"),
        ("ś", "s"),
        ("ź", "z"),
        ("ż", "z"),
        ("ć", "c"),
    ]:
        name = name.replace(src, dst)
        name = name.replace(src.upper(), dst.capitalize())
    # Remove special chars, keep spaces
    name = re.sub(r"[^a-zA-Z0-9\s]", "", name)
    words = name.split()

    slugs = []
    if words:
        # Full name
        slugs.append("-".join(words))
        # Without common suffixes
        filtered = [
            w
            for w in words
            if w.lower() not in ("ski", "resort", "area", "center", "centre")
        ]
        if filtered and filtered != words:
            slugs.append("-".join(filtered))
        # With "Mountain" suffix
        if "Mountain" not in words and len(words) <= 2:
            slugs.append("-".join(words) + "-Mountain")
        # First word only (for multi-word names)
        if len(words) > 2:
            slugs.append("-".join(words[:2]))
            slugs.append(words[0])

    return slugs


def try_find_trail_map_snow_forecast(
    resort_name: str,
    session: requests.Session,
) -> str | None:
    """Try to find piste map on snow-forecast.com."""
    slugs = _generate_snow_forecast_slugs(resort_name)

    for slug in slugs:
        url = f"https://www.snow-forecast.com/pistemaps/{slug}_pistemap.jpg"
        try:
            time.sleep(REQUEST_DELAY)
            resp = session.head(url, timeout=10, allow_redirects=True)
            if resp.status_code == 200:
                content_type = resp.headers.get("Content-Type", "")
                if "image" in content_type:
                    return url
        except Exception:
            continue

    return None


def find_missing_trail_maps(resorts: list[dict], limit: int = 0) -> int:
    """Try to find trail maps for resorts that don't have them using multiple strategies."""
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
    )

    missing = [r for r in resorts if not r.get("trail_map_url")]
    if limit > 0:
        missing = missing[:limit]

    logger.info(f"\nSearching trail maps for {len(missing)} resorts...")
    found = 0
    found_by_strategy = {"slug": 0, "search": 0, "snow_forecast": 0, "website": 0}

    for i, resort in enumerate(missing):
        if i % 50 == 0 and i > 0:
            logger.info(f"  Progress: {i}/{len(missing)} ({found} found)")

        resort_id = resort["resort_id"]
        resort_name = resort["name"]

        # Strategy 1: Improved slug matching on skiresort.info
        url = try_find_trail_map_skiresort(resort_id, resort_name, session)
        if url:
            resort["trail_map_url"] = url
            found += 1
            found_by_strategy["slug"] += 1
            logger.info(f"  Trail map [slug]: {resort_id}")
            continue

        # Strategy 2: snow-forecast.com piste maps
        url = try_find_trail_map_snow_forecast(resort_name, session)
        if url:
            resort["trail_map_url"] = url
            found += 1
            found_by_strategy["snow_forecast"] += 1
            logger.info(f"  Trail map [snow-forecast]: {resort_id}")
            continue

        # Strategy 3: skiresort.info search (slow, JS-rendered so often fails)
        url = try_find_trail_map_search(resort_name, session)
        if url:
            resort["trail_map_url"] = url
            found += 1
            found_by_strategy["search"] += 1
            logger.info(f"  Trail map [search]: {resort_id}")
            continue

        # Strategy 4: Scrape resort website for trail map images
        website = resort.get("website")
        if website:
            url = try_find_trail_map_on_website(website, session)
            if url:
                resort["trail_map_url"] = url
                found += 1
                found_by_strategy["website"] += 1
                logger.info(f"  Trail map [website]: {resort_id}")
                continue

    logger.info(f"  Trail maps found: {found}/{len(missing)}")
    logger.info(f"    By slug: {found_by_strategy['slug']}")
    logger.info(f"    By snow-forecast: {found_by_strategy['snow_forecast']}")
    logger.info(f"    By search: {found_by_strategy['search']}")
    logger.info(f"    By website: {found_by_strategy['website']}")
    return found


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 0

    data = load_resorts()
    resorts = data["resorts"]

    total = len(resorts)
    has_map = sum(1 for r in resorts if r.get("trail_map_url"))
    has_logo = sum(1 for r in resorts if r.get("logo_url"))
    logger.info(f"Total resorts: {total}")
    logger.info(f"With trail map: {has_map} ({has_map * 100 / total:.1f}%)")
    logger.info(f"With logo: {has_logo} ({has_logo * 100 / total:.1f}%)")

    if mode in ("fix-zoom", "all"):
        logger.info("\n--- Fixing trail map zoom levels ---")
        fixed = fix_trail_map_zoom_levels(resorts)
        logger.info(f"Fixed {fixed} trail map URLs (level 0 -> level 8)")

    if mode in ("logos", "all"):
        logger.info("\n--- Scraping logos ---")
        scrape_logos_batch(resorts, limit=limit)

    if mode in ("maps", "all"):
        logger.info("\n--- Finding missing trail maps ---")
        find_missing_trail_maps(resorts, limit=limit)

    # Report final stats
    has_map_after = sum(1 for r in resorts if r.get("trail_map_url"))
    has_logo_after = sum(1 for r in resorts if r.get("logo_url"))
    logger.info("\n--- Final Stats ---")
    logger.info(
        f"Trail maps: {has_map} -> {has_map_after} ({has_map_after * 100 / total:.1f}%)"
    )
    logger.info(
        f"Logos: {has_logo} -> {has_logo_after} ({has_logo_after * 100 / total:.1f}%)"
    )

    save_resorts(data)
    logger.info("Saved to resorts.json")


if __name__ == "__main__":
    main()
