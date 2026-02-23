#!/usr/bin/env python3
"""
Enrich resorts.json with elevation data from skiresort.info.

Targets resorts missing elevation_top_m. Uses the same URL matching logic
as enrich_annual_snowfall.py and the fixed "Elevation info" heading parser.

Usage:
    python3 backend/scripts/enrich_elevations.py
    python3 backend/scripts/enrich_elevations.py --dry-run
    python3 backend/scripts/enrich_elevations.py --limit 50
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
MAX_CONCURRENT = 5
REQUEST_DELAY = 0.3  # ~3.3 req/sec to avoid rate limiting
REQUEST_TIMEOUT = 20
MAX_RETRIES = 2
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
BASE_URL = "https://www.skiresort.info"
RESORTS_JSON = Path(__file__).parent.parent / "data" / "resorts.json"


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


class RateLimiter:
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


def parse_elevation(html: str) -> tuple[int | None, int | None]:
    """Extract base and top elevation from a skiresort.info page.

    Returns (base_m, top_m) or (None, None) if not found.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Strategy 1: Find "Elevation info" heading
    elev_heading = soup.find(
        ["h3", "h4", "h2"],
        string=re.compile(r"Elevation\s+info", re.I),
    )
    if elev_heading:
        next_text = ""
        for sibling in elev_heading.next_siblings:
            if hasattr(sibling, "name") and sibling.name in ("h3", "h4", "h2"):
                break
            text = sibling.get_text() if hasattr(sibling, "get_text") else str(sibling)
            next_text += text
            if len(next_text) > 200:
                break

        match = re.search(r"(\d[\d,. ]*)\s*m\s*[-–]\s*(\d[\d,. ]*)\s*m", next_text)
        if match:
            base_str = match.group(1).replace(",", "").replace(".", "").replace(" ", "")
            top_str = match.group(2).replace(",", "").replace(".", "").replace(" ", "")
            try:
                base, top = int(base_str), int(top_str)
                if 50 < base < 5000 and 50 < top < 5000 and top > base:
                    return base, top
            except ValueError:
                pass

    return None, None


def build_candidate_urls(resort: dict) -> list[str]:
    """Build candidate skiresort.info URLs for a resort."""
    seen = set()
    urls = []

    def add(slug: str):
        url = f"{BASE_URL}/ski-resort/{slug}/"
        if url not in seen:
            seen.add(url)
            urls.append(url)

    add(resort["resort_id"])

    name = resort.get("name", "")
    if name:
        add(slugify(name))
        for suffix in [
            " ski resort",
            " resort",
            " mountain resort",
            " ski area",
            " mountain",
        ]:
            if name.lower().endswith(suffix):
                short = slugify(name[: -len(suffix)])
                if short:
                    add(short)

        if " – " in name or " - " in name:
            for part in re.split(r"\s*[–-]\s*", name):
                part_slug = slugify(part.strip())
                if part_slug and len(part_slug) > 2:
                    add(part_slug)

    return urls


async def fetch_elevation(
    session: aiohttp.ClientSession,
    resort: dict,
    semaphore: asyncio.Semaphore,
    rate_limiter: RateLimiter,
) -> tuple[int | None, int | None]:
    """Try to get elevation from skiresort.info for a resort."""
    urls = build_candidate_urls(resort)

    for url in urls:
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
                            break  # Redirected away, not a resort page
                        if resp.status == 200:
                            html = await resp.text()
                            base, top = parse_elevation(html)
                            if base and top:
                                return base, top
                            break  # Found page but no elevation data
                        elif resp.status == 404:
                            break
                        elif resp.status == 429:
                            await asyncio.sleep(5 + attempt * 5)
                        else:
                            if attempt < MAX_RETRIES:
                                await asyncio.sleep(1 + attempt)
                except (TimeoutError, aiohttp.ClientError):
                    if attempt < MAX_RETRIES:
                        await asyncio.sleep(1 + attempt)

    return None, None


async def main_async(args):
    print(f"Loading resorts from {RESORTS_JSON}...")
    with open(RESORTS_JSON) as f:
        data = json.load(f)

    resorts = data["resorts"]
    total = len(resorts)
    has_top = sum(1 for r in resorts if r.get("elevation_top_m") is not None)
    print(f"Total: {total}, Have top elevation: {has_top}, Missing: {total - has_top}")

    to_enrich = [
        (i, r) for i, r in enumerate(resorts) if r.get("elevation_top_m") is None
    ]
    print(f"Resorts needing elevation data: {len(to_enrich)}")

    if args.limit:
        to_enrich = to_enrich[: args.limit]
        print(f"Limited to first {args.limit}")

    if not to_enrich:
        print("No resorts need elevation enrichment. Done!")
        return

    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    rate_limiter = RateLimiter(REQUEST_DELAY)
    connector = aiohttp.TCPConnector(
        limit=MAX_CONCURRENT + 5, limit_per_host=MAX_CONCURRENT
    )
    headers = {"User-Agent": USER_AGENT}

    enriched = 0
    failed = 0
    start_time = time.time()

    async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
        batch_size = 30

        for batch_start in range(0, len(to_enrich), batch_size):
            batch = to_enrich[batch_start : batch_start + batch_size]

            tasks = [
                fetch_elevation(session, resort, semaphore, rate_limiter)
                for _, resort in batch
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for (_idx, resort), result in zip(batch, results, strict=False):
                if isinstance(result, Exception):
                    failed += 1
                    continue
                base, top = result
                if base and top:
                    if not args.dry_run:
                        resort["elevation_base_m"] = base
                        resort["elevation_top_m"] = top
                        resort["elevation_mid_m"] = round((base + top) / 2)
                        resort["vertical_drop_m"] = top - base
                        resort["large_resort"] = (top - base) >= 800
                    enriched += 1
                else:
                    failed += 1

            elapsed = time.time() - start_time
            done = min(batch_start + len(batch), len(to_enrich))
            rate = done / elapsed if elapsed > 0 else 0
            remaining = (len(to_enrich) - done) / rate if rate > 0 else 0
            print(
                f"  [{done}/{len(to_enrich)}] "
                f"Enriched: {enriched}, Failed: {failed} "
                f"({rate:.1f}/sec, ~{remaining:.0f}s left)"
            )

    if not args.dry_run and enriched > 0:
        with open(RESORTS_JSON, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"\nSaved to {RESORTS_JSON}")
    elif args.dry_run:
        print("\nDry run — no changes saved.")

    print(
        f"\nEnriched: {enriched}/{len(to_enrich)} ({enriched / len(to_enrich) * 100:.1f}%)"
    )
    print(f"Failed: {failed}")

    if enriched > 0 and not args.dry_run:
        has_top = sum(1 for r in resorts if r.get("elevation_top_m") is not None)
        print(
            f"Total with top elevation: {has_top}/{total} ({has_top / total * 100:.1f}%)"
        )


def main():
    parser = argparse.ArgumentParser(
        description="Enrich elevation data from skiresort.info"
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
