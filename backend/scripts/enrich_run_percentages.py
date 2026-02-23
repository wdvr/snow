#!/usr/bin/env python3
"""
Enrich resorts.json with run percentage data (green/blue/black/double-black)
scraped from skiresort.info.

Identifies resorts with placeholder or missing run percentage data and scrapes
the actual difficulty breakdown from skiresort.info resort detail pages.

Phase 1: Builds a name-to-slug mapping from skiresort.info country listing pages
Phase 2: For each resort needing data, tries candidate URLs and parses slope data

Usage:
    python3 backend/scripts/enrich_run_percentages.py
    python3 backend/scripts/enrich_run_percentages.py --dry-run
    python3 backend/scripts/enrich_run_percentages.py --limit 50
    python3 backend/scripts/enrich_run_percentages.py --skip-index
"""

import argparse
import asyncio
import json
import re
import time
from pathlib import Path

import aiohttp
from bs4 import BeautifulSoup

# Configuration
MAX_CONCURRENT = 10
REQUEST_DELAY = 0.5  # seconds between requests
REQUEST_TIMEOUT = 20  # seconds per request
MAX_RETRIES = 2
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
BASE_URL = "https://www.skiresort.info"
RESORTS_JSON = Path(__file__).parent.parent / "data" / "resorts.json"

# Country listing pages on skiresort.info
COUNTRY_URLS = {
    "US": "/ski-resorts/usa",
    "CA": "/ski-resorts/canada",
    "AT": "/ski-resorts/austria",
    "CH": "/ski-resorts/switzerland",
    "FR": "/ski-resorts/france",
    "IT": "/ski-resorts/italy",
    "DE": "/ski-resorts/germany",
    "SI": "/ski-resorts/slovenia",
    "NO": "/ski-resorts/norway",
    "SE": "/ski-resorts/sweden",
    "FI": "/ski-resorts/finland",
    "JP": "/ski-resorts/japan",
    "AU": "/ski-resorts/australia",
    "NZ": "/ski-resorts/new-zealand",
    "CL": "/ski-resorts/chile",
    "AR": "/ski-resorts/argentina",
    "ES": "/ski-resorts/spain",
    "AD": "/ski-resorts/andorra",
    "PL": "/ski-resorts/poland",
    "CZ": "/ski-resorts/czech-republic",
    "SK": "/ski-resorts/slovakia",
    "RO": "/ski-resorts/romania",
    "BG": "/ski-resorts/bulgaria",
    "KR": "/ski-resorts/south-korea",
    "CN": "/ski-resorts/china",
}

SKIP_PATTERNS = [
    "/snow-report",
    "/test-report",
    "/test-result",
    "/reviews",
    "/photos",
    "/events",
    "/webcams",
    "/trail-map",
    "/video",
    "/ski-lifts",
    "/ski-schools",
    "/apres-ski",
    "/accommodation",
]


def needs_enrichment(resort: dict) -> bool:
    """Check if a resort needs run percentage data."""
    green = resort.get("green_runs_pct")
    blue = resort.get("blue_runs_pct")
    black = resort.get("black_runs_pct")

    # Placeholder: only blue_runs_pct=100, no green or black
    if blue == 100 and green is None and black is None:
        return True
    # All null/missing
    if green is None and blue is None and black is None:
        return True
    # Has blue but no green and no black (partial placeholder)
    if green is None and black is None and blue is not None:
        return True
    return False


def parse_slopes(html: str) -> dict | None:
    """Parse slope difficulty data from a skiresort.info resort page."""
    soup = BeautifulSoup(html, "html.parser")

    # Strategy 1: Find the run-table with 'distance' cells (most reliable)
    for run_table in soup.find_all("table", class_="run-table"):
        slope_data = {}
        for row in run_table.find_all("tr"):
            desc_cell = row.find("td", class_="desc")
            dist_cell = row.find("td", class_="distance")
            if desc_cell and dist_cell:
                label = desc_cell.get_text(strip=True).lower()
                dist_text = dist_cell.get_text(strip=True)
                km_match = re.search(r"([\d.,]+)\s*km", dist_text)
                if km_match:
                    km_val = float(km_match.group(1).replace(",", "."))
                    if "easy" in label or "beginner" in label or "green" in label:
                        slope_data["green"] = km_val
                    elif (
                        "intermediate" in label or "medium" in label or "blue" in label
                    ):
                        slope_data["blue"] = km_val
                    elif any(
                        w in label
                        for w in ["difficult", "hard", "black", "advanced", "expert"]
                    ):
                        slope_data["black"] = km_val
                    elif "freeride" in label or "route" in label or "extreme" in label:
                        slope_data["double_black"] = km_val

        total_km = sum(slope_data.values())
        if total_km > 0:
            result = {}
            if "green" in slope_data:
                result["green_runs_pct"] = round(slope_data["green"] / total_km * 100)
            if "blue" in slope_data:
                result["blue_runs_pct"] = round(slope_data["blue"] / total_km * 100)
            if "black" in slope_data:
                result["black_runs_pct"] = round(slope_data["black"] / total_km * 100)
            if "double_black" in slope_data:
                result["double_black_runs_pct"] = round(
                    slope_data["double_black"] / total_km * 100
                )

            # Ensure percentages sum to 100
            pct_sum = sum(result.values())
            if pct_sum != 100 and pct_sum > 0:
                max_key = max(result, key=result.get)
                result[max_key] += 100 - pct_sum
            return result

    # Strategy 2: Fallback - look for percentage text patterns
    page_text = soup.get_text()
    slope_pcts = {}
    for label_re, key in [
        (r"Easy[:\s]+.*?(\d+)\s*%", "green_runs_pct"),
        (r"Intermediate[:\s]+.*?(\d+)\s*%", "blue_runs_pct"),
        (r"Difficult[:\s]+.*?(\d+)\s*%", "black_runs_pct"),
    ]:
        match = re.search(label_re, page_text, re.IGNORECASE)
        if match:
            slope_pcts[key] = int(match.group(1))
    if slope_pcts:
        return slope_pcts

    return None


def parse_website(html: str) -> str | None:
    """Extract the resort's official website URL from a skiresort.info page."""
    soup = BeautifulSoup(html, "html.parser")

    # The official website is in a div with class 'resort-logo'
    logo_div = soup.find("div", class_="resort-logo")
    if logo_div:
        link = logo_div.find("a", href=True)
        if link:
            href = link["href"]
            if href.startswith("http") and "skiresort" not in href.lower():
                return href.rstrip("/")

    # Fallback: look for external links with rel containing "external"
    skip_domains = [
        "skiresort",
        "utm_",
        "facebook",
        "twitter",
        "instagram",
        "youtube",
        "hotel",
        "booking",
        "tripadvisor",
    ]
    for a in soup.find_all("a", rel=lambda x: x and "external" in x):
        href = a.get("href", "")
        if href.startswith("http") and not any(d in href.lower() for d in skip_domains):
            return href.rstrip("/")
    return None


def is_resort_page(html: str) -> bool:
    """Check if the HTML is a valid resort detail page (not homepage/redirect)."""
    if len(html) < 1000:
        return False
    if "run-table" in html or "resort-logo" in html or "selBeginner" in html:
        return True
    soup = BeautifulSoup(html[:5000], "html.parser")
    title = soup.find("title")
    if title:
        title_text = title.get_text(strip=True).lower()
        if "ski resort " in title_text:
            return True
    return False


def slugify(text: str) -> str:
    """Convert text to a URL-friendly slug."""
    slug = text.lower()
    slug = re.sub(r"[''`]", "", slug)
    replacements = {
        "ä": "ae",
        "ö": "oe",
        "ü": "ue",
        "ß": "ss",
        "à": "a",
        "á": "a",
        "â": "a",
        "ã": "a",
        "å": "aa",
        "è": "e",
        "é": "e",
        "ê": "e",
        "ë": "e",
        "ì": "i",
        "í": "i",
        "î": "i",
        "ï": "i",
        "ò": "o",
        "ó": "o",
        "ô": "o",
        "õ": "o",
        "ù": "u",
        "ú": "u",
        "û": "u",
        "ñ": "n",
        "ç": "c",
        "æ": "ae",
        "ø": "oe",
        "ð": "d",
        "þ": "th",
        "ý": "y",
    }
    for char, repl in replacements.items():
        slug = slug.replace(char, repl)
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    slug = re.sub(r"-+", "-", slug)
    return slug


def clean_name_for_matching(name: str) -> str:
    """Normalize a name for fuzzy matching."""
    name = name.replace("\u200b", "").replace("\u200c", "").replace("\u200d", "")
    name = slugify(name)
    return name


def find_slug_in_index(resort_name: str, slug_index: dict) -> str | None:
    """Find the best matching slug in the index for a resort name.

    slug_index: dict mapping cleaned skiresort.info names to slugs.
    """
    clean = clean_name_for_matching(resort_name)

    # Remove common suffixes for matching
    for suffix in [
        "-ski-resort",
        "-resort",
        "-mountain-resort",
        "-ski-area",
        "-mountain",
    ]:
        if clean.endswith(suffix):
            clean = clean[: -len(suffix)]

    # Exact match
    if clean in slug_index:
        return slug_index[clean]

    # Try each significant word from resort name against all index entries
    words = [w for w in clean.split("-") if len(w) > 2]
    if not words:
        return None

    best_score = 0
    best_slug = None

    for idx_name, slug in slug_index.items():
        idx_words = set(idx_name.split("-"))

        # Count matching words
        matched = sum(1 for w in words if w in idx_words)
        if matched == 0:
            # Try substring match (for single-word resort names like "Courchevel")
            if len(words) == 1 and words[0] in idx_name:
                score = 0.7
            elif len(words) >= 2 and all(w in idx_name for w in words[:2]):
                score = 0.8
            else:
                continue
        else:
            score = matched / len(words)

        # Penalty for matching common words like "ski", "mountain", "resort"
        common = {"ski", "resort", "mountain", "big", "new", "les", "mount"}
        if matched > 0 and all(w in common for w in words if w in idx_words):
            score *= 0.3  # Heavy penalty for only matching common words

        if score > best_score:
            best_score = score
            best_slug = slug

    return best_slug if best_score >= 0.7 else None


class RateLimiter:
    """Token bucket rate limiter for async requests."""

    def __init__(self, rate: float):
        self._rate = rate
        self._last_time = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self):
        async with self._lock:
            now = time.monotonic()
            wait = self._rate - (now - self._last_time)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_time = time.monotonic()


async def fetch_page_raw(
    session: aiohttp.ClientSession,
    url: str,
    rate_limiter: RateLimiter,
) -> str | None:
    """Fetch a page with rate limiting. Returns HTML or None."""
    await rate_limiter.acquire()

    for attempt in range(MAX_RETRIES + 1):
        try:
            async with session.get(
                url,
                timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
                allow_redirects=True,
            ) as resp:
                if resp.status == 200:
                    return await resp.text()
                elif resp.status == 404:
                    return None
                else:
                    if attempt < MAX_RETRIES:
                        await asyncio.sleep(1 + attempt)
        except (TimeoutError, aiohttp.ClientError):
            if attempt < MAX_RETRIES:
                await asyncio.sleep(1 + attempt)
    return None


async def build_slug_index(
    session: aiohttp.ClientSession,
    rate_limiter: RateLimiter,
    countries: set[str],
) -> dict[str, str]:
    """Build a mapping of cleaned resort names to skiresort.info slugs
    by scraping country listing pages.

    Returns dict: {cleaned_name: slug}
    """
    slug_index = {}

    # Only scrape countries we actually need
    relevant_countries = {c for c in countries if c in COUNTRY_URLS}
    print(f"  Building slug index for {len(relevant_countries)} countries...")

    for country in sorted(relevant_countries):
        path = COUNTRY_URLS[country]
        page = 1
        while page <= 20:
            url = f"{BASE_URL}{path}" + (f"/page/{page}" if page > 1 else "")
            html = await fetch_page_raw(session, url, rate_limiter)
            if html is None:
                break

            soup = BeautifulSoup(html, "html.parser")
            found = 0

            for link in soup.select('a[href*="/ski-resort/"]'):
                href = link.get("href", "")
                if any(p in href for p in SKIP_PATTERNS):
                    continue
                match = re.search(r"/ski-resort/([^/]+)/", href)
                if match:
                    slug = match.group(1)
                    name = link.get_text(strip=True)
                    if name and slug and len(name) > 2:
                        name = re.sub(
                            r"^ski resort\s+", "", name, flags=re.IGNORECASE
                        ).strip()
                        clean = clean_name_for_matching(name)
                        if clean and clean not in slug_index:
                            slug_index[clean] = slug
                            found += 1

            # Check for next page
            has_next = soup.select_one('.pagination .next, a[rel="next"]')
            if not has_next:
                break
            page += 1

    print(f"  Built index with {len(slug_index)} resort name-to-slug mappings")
    return slug_index


def build_candidate_urls(resort: dict, slug_index: dict | None = None) -> list[str]:
    """Build a list of candidate skiresort.info URLs for a resort."""
    seen = set()
    urls = []

    def add(slug: str):
        url = f"{BASE_URL}/ski-resort/{slug}/"
        if url not in seen:
            seen.add(url)
            urls.append(url)

    resort_id = resort["resort_id"]
    name = resort.get("name", "")

    # 1. Direct resort_id
    add(resort_id)

    # 2. Slug from full name
    if name:
        name_slug = slugify(name)
        add(name_slug)

        # 3. Remove common suffixes from name
        for suffix in [
            " ski resort",
            " resort",
            " mountain resort",
            " ski area",
            " mountain",
            " ski",
            " ski center",
            " ski centre",
        ]:
            if name.lower().endswith(suffix):
                short = slugify(name[: -len(suffix)])
                if short:
                    add(short)

        # 4. Handle "X - Y" pattern
        if " – " in name or " - " in name:
            parts = re.split(r"\s*[–-]\s*", name)
            for part in parts:
                part_slug = slugify(part.strip())
                if part_slug and len(part_slug) > 2:
                    add(part_slug)

        # 5. Try first word(s) only
        words = name.split()
        if len(words) > 1:
            first = slugify(words[0])
            if first and len(first) > 2 and first != name_slug:
                add(first)

    # 6. Use slug index if available
    if slug_index and name:
        index_slug = find_slug_in_index(name, slug_index)
        if index_slug:
            add(index_slug)

    return urls


async def fetch_resort_page(
    session: aiohttp.ClientSession,
    url: str,
    semaphore: asyncio.Semaphore,
    rate_limiter: RateLimiter,
) -> str | None:
    """Fetch a single URL, returning HTML if it's a valid resort page."""
    async with semaphore:
        await rate_limiter.acquire()

        for attempt in range(MAX_RETRIES + 1):
            try:
                async with session.get(
                    url,
                    timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
                    allow_redirects=True,
                ) as resp:
                    final_url = str(resp.url)
                    if (
                        final_url.rstrip("/") == BASE_URL
                        or "/ski-resort/" not in final_url
                    ):
                        return None
                    if resp.status == 200:
                        html = await resp.text()
                        return html if is_resort_page(html) else None
                    elif resp.status == 404:
                        return None
                    else:
                        if attempt < MAX_RETRIES:
                            await asyncio.sleep(1 + attempt)
            except (TimeoutError, aiohttp.ClientError):
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(1 + attempt)
                else:
                    return None
    return None


async def process_resort(
    resort: dict,
    session: aiohttp.ClientSession,
    semaphore: asyncio.Semaphore,
    rate_limiter: RateLimiter,
    slug_index: dict | None = None,
) -> dict | None:
    """Process a single resort: try candidate URLs and parse slope data."""
    candidate_urls = build_candidate_urls(resort, slug_index)

    for url in candidate_urls:
        html = await fetch_resort_page(session, url, semaphore, rate_limiter)
        if html is None:
            continue

        slopes = parse_slopes(html)
        if slopes:
            updates = dict(slopes)
            if not resort.get("website"):
                website = parse_website(html)
                if website:
                    updates["website"] = website
            return updates

    return None


async def main_async(args):
    """Main async entry point."""
    print(f"Loading resorts from {RESORTS_JSON}...")
    with open(RESORTS_JSON) as f:
        data = json.load(f)

    resorts = data["resorts"]
    print(f"Total resorts: {len(resorts)}")

    # Identify resorts needing enrichment
    to_enrich = [(i, r) for i, r in enumerate(resorts) if needs_enrichment(r)]
    print(f"Resorts needing run percentage data: {len(to_enrich)}")

    if args.limit:
        to_enrich = to_enrich[: args.limit]
        print(f"Limited to first {args.limit} resorts")

    if not to_enrich:
        print("No resorts need enrichment. Done!")
        return

    # Set up async HTTP session
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    rate_limiter = RateLimiter(REQUEST_DELAY)
    connector = aiohttp.TCPConnector(
        limit=MAX_CONCURRENT + 5, limit_per_host=MAX_CONCURRENT
    )
    headers = {"User-Agent": USER_AGENT}

    slug_index = None
    updated_count = 0
    failed_count = 0
    website_count = 0
    failed_resorts = []
    start_time = time.time()

    async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
        # Phase 1: Build slug index from country listing pages
        if not args.skip_index:
            print("\nPhase 1: Building skiresort.info slug index...")
            countries_needed = {r["country"] for _, r in to_enrich}
            slug_index = await build_slug_index(session, rate_limiter, countries_needed)
        else:
            print("\nSkipping slug index build (--skip-index)")

        # Phase 2: Scrape resort detail pages
        print(f"\nPhase 2: Scraping {len(to_enrich)} resort detail pages...")
        batch_size = 50
        for batch_start in range(0, len(to_enrich), batch_size):
            batch = to_enrich[batch_start : batch_start + batch_size]

            tasks = [
                process_resort(resort, session, semaphore, rate_limiter, slug_index)
                for _, resort in batch
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for (idx, resort), result in zip(batch, results, strict=False):
                if isinstance(result, Exception) or result is None:
                    failed_count += 1
                    failed_resorts.append(resort["resort_id"])
                    continue

                # Apply updates
                if not args.dry_run:
                    for key, value in result.items():
                        if key == "website":
                            if not resort.get("website"):
                                resorts[idx]["website"] = value
                                website_count += 1
                        elif key in (
                            "green_runs_pct",
                            "blue_runs_pct",
                            "black_runs_pct",
                            "double_black_runs_pct",
                        ):
                            current = resort.get(key)
                            if current is None or (
                                key == "blue_runs_pct" and current == 100
                            ):
                                resorts[idx][key] = value

                updated_count += 1

            elapsed = time.time() - start_time
            total_done = min(batch_start + len(batch), len(to_enrich))
            rate = total_done / elapsed if elapsed > 0 else 0
            remaining = (len(to_enrich) - total_done) / rate if rate > 0 else 0
            print(
                f"  [{total_done}/{len(to_enrich)}] "
                f"Updated: {updated_count}, Failed: {failed_count}, "
                f"Websites: {website_count} "
                f"({rate:.1f}/sec, ~{remaining:.0f}s left)"
            )

    # Save results
    if not args.dry_run and updated_count > 0:
        print("\nSaving updated resorts.json...")
        with open(RESORTS_JSON, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"Saved to {RESORTS_JSON}")
    elif args.dry_run:
        print("\nDry run - no changes saved.")

    # Print summary
    elapsed = time.time() - start_time
    print(f"\n{'=' * 50}")
    print("ENRICHMENT SUMMARY")
    print(f"{'=' * 50}")
    print(f"Total resorts:              {len(resorts)}")
    print(f"Needed enrichment:          {len(to_enrich)}")
    print(f"Successfully updated:       {updated_count}")
    print(f"Failed (no data found):     {failed_count}")
    print(f"Websites added:             {website_count}")
    print(f"Success rate:               {updated_count / len(to_enrich) * 100:.1f}%")
    print(f"Time elapsed:               {elapsed:.1f}s")
    print(f"{'=' * 50}")

    # Show data coverage
    if updated_count > 0 and not args.dry_run:
        has_green = sum(1 for r in resorts if r.get("green_runs_pct") is not None)
        has_blue = sum(1 for r in resorts if r.get("blue_runs_pct") is not None)
        has_black = sum(1 for r in resorts if r.get("black_runs_pct") is not None)
        has_dbl = sum(1 for r in resorts if r.get("double_black_runs_pct") is not None)
        has_website = sum(1 for r in resorts if r.get("website"))
        still_needs = sum(1 for r in resorts if needs_enrichment(r))

        print("\nData coverage after enrichment:")
        print(f"  green_runs_pct:        {has_green}/{len(resorts)}")
        print(f"  blue_runs_pct:         {has_blue}/{len(resorts)}")
        print(f"  black_runs_pct:        {has_black}/{len(resorts)}")
        print(f"  double_black_runs_pct: {has_dbl}/{len(resorts)}")
        print(f"  website:               {has_website}/{len(resorts)}")
        print(f"  Still needs enrichment: {still_needs}/{len(resorts)}")

    if failed_resorts:
        shown = failed_resorts[:80]
        print(
            f"\nFailed resort IDs ({len(failed_resorts)} total, showing {len(shown)}):"
        )
        for rid in shown:
            print(f"  - {rid}")


def main():
    parser = argparse.ArgumentParser(
        description="Enrich resorts.json with run percentage data from skiresort.info"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't save changes, just show what would be updated",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of resorts to process (for testing)",
    )
    parser.add_argument(
        "--skip-index",
        action="store_true",
        help="Skip building slug index from country listings (faster, lower hit rate)",
    )
    args = parser.parse_args()

    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
