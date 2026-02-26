#!/usr/bin/env python3
"""
Find resort logo/icon URLs for all resorts in Powder Chaser.

Uses a multi-source strategy:
1. Google Favicon API (primary) - returns favicons/apple-touch-icons at up to 256px
2. DuckDuckGo Icon API (fallback) - good coverage, returns .ico files
3. For resorts without websites, generates a fallback placeholder URL

Output: backend/data/resort_logos.json with logo URLs for each resort_id

Usage:
    python3 backend/scripts/find_resort_logos.py [--verify] [--sample N]

    --verify    Actually HEAD-request each URL to verify it works (slow, ~2min)
    --sample N  Only process N resorts (for testing)
"""

import argparse
import json
import os
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RESORTS_JSON = os.path.join(SCRIPT_DIR, "..", "data", "resorts.json")
OUTPUT_JSON = os.path.join(SCRIPT_DIR, "..", "data", "resort_logos.json")


def load_resorts():
    with open(RESORTS_JSON) as f:
        data = json.load(f)
    return data["resorts"]


def extract_domain(website_url: str) -> str | None:
    """Extract clean domain from website URL."""
    if not website_url:
        return None
    # Skip Facebook pages - not useful for logos
    if "facebook.com" in website_url:
        return None
    parsed = urlparse(website_url)
    domain = parsed.netloc or parsed.path
    if domain.startswith("www."):
        domain = domain[4:]
    return domain if domain else None


def google_favicon_url(domain: str, size: int = 128) -> str:
    """Generate Google Favicon API URL."""
    return (
        f"https://t3.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON"
        f"&fallback_opts=TYPE,SIZE,URL&url=http://{domain}&size={size}"
    )


def ddg_icon_url(domain: str) -> str:
    """Generate DuckDuckGo icon URL."""
    return f"https://icons.duckduckgo.com/ip3/{domain}.ico"


def verify_url(url: str, timeout: int = 5) -> dict | None:
    """HEAD-request a URL to check if it works. Returns size info or None."""
    try:
        req = urllib.request.Request(url, method="HEAD")
        req.add_header("User-Agent", "PowderChaser/1.0")
        resp = urllib.request.urlopen(req, timeout=timeout)
        size = int(resp.headers.get("Content-Length", "0"))
        content_type = resp.headers.get("Content-Type", "unknown")
        return {"size": size, "content_type": content_type}
    except Exception:
        return None


def process_resort(resort: dict, do_verify: bool = False) -> dict:
    """Process a single resort and return logo info."""
    resort_id = resort["resort_id"]
    name = resort["name"]
    website = resort.get("website", "")
    domain = extract_domain(website)

    result = {
        "resort_id": resort_id,
        "name": name,
    }

    if not domain:
        result["logo_url"] = None
        result["logo_source"] = "none"
        result["fallback"] = "initials"
        return result

    # Primary: Google Favicon API
    goog_url = google_favicon_url(domain, size=128)
    result["logo_url"] = goog_url
    result["logo_source"] = "google_favicon"
    result["domain"] = domain

    if do_verify:
        info = verify_url(goog_url)
        if info and info["size"] >= 500:
            result["verified"] = True
            result["icon_size_bytes"] = info["size"]
        else:
            # Fallback: DuckDuckGo
            ddg_url = ddg_icon_url(domain)
            ddg_info = verify_url(ddg_url)
            if ddg_info and ddg_info["size"] >= 500:
                result["logo_url"] = ddg_url
                result["logo_source"] = "duckduckgo"
                result["verified"] = True
                result["icon_size_bytes"] = ddg_info["size"]
            else:
                result["logo_url"] = goog_url  # Keep Google URL as best effort
                result["verified"] = False
                result["fallback"] = "initials"

    return result


def main():
    parser = argparse.ArgumentParser(description="Find resort logo URLs")
    parser.add_argument(
        "--verify", action="store_true", help="Verify URLs with HEAD requests"
    )
    parser.add_argument("--sample", type=int, help="Only process N resorts")
    args = parser.parse_args()

    resorts = load_resorts()
    if args.sample:
        resorts = resorts[: args.sample]

    print(f"Processing {len(resorts)} resorts...")

    results = []
    if args.verify:
        # Use thread pool for parallel verification
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(process_resort, r, True): r for r in resorts}
            done = 0
            for future in as_completed(futures):
                result = future.result()
                results.append(result)
                done += 1
                if done % 100 == 0:
                    print(f"  Progress: {done}/{len(resorts)}")
    else:
        # Fast mode - just generate URLs without verification
        for r in resorts:
            results.append(process_resort(r, do_verify=False))

    # Sort by resort_id for consistency
    results.sort(key=lambda x: x["resort_id"])

    # Stats
    with_logo = sum(1 for r in results if r.get("logo_url"))
    no_logo = sum(1 for r in results if not r.get("logo_url"))
    verified_ok = sum(1 for r in results if r.get("verified") is True)
    verified_fail = sum(1 for r in results if r.get("verified") is False)
    google_count = sum(1 for r in results if r.get("logo_source") == "google_favicon")
    ddg_count = sum(1 for r in results if r.get("logo_source") == "duckduckgo")

    print("\n=== Results ===")
    print(f"Total resorts:       {len(results)}")
    print(f"With logo URL:       {with_logo} ({100 * with_logo / len(results):.1f}%)")
    print(f"No logo (fallback):  {no_logo} ({100 * no_logo / len(results):.1f}%)")
    if args.verify:
        print(f"Verified OK:         {verified_ok}")
        print(f"Verified failed:     {verified_fail}")
    print(f"Source: Google:       {google_count}")
    print(f"Source: DuckDuckGo:   {ddg_count}")

    # Build output format
    output = {
        "version": "1.0.0",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "total_resorts": len(results),
        "with_logo": with_logo,
        "without_logo": no_logo,
        "logos": {
            r["resort_id"]: {
                "url": r.get("logo_url"),
                "source": r.get("logo_source"),
                "domain": r.get("domain"),
                "fallback": r.get("fallback"),
            }
            for r in results
        },
    }

    with open(OUTPUT_JSON, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nSaved to: {OUTPUT_JSON}")

    # Also print some samples
    print("\n=== Sample URLs ===")
    samples = [r for r in results if r.get("logo_url")][:15]
    for r in samples:
        print(f"  {r['name']:40} {r['logo_url'][:80]}")


if __name__ == "__main__":
    main()
