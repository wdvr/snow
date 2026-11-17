#!/usr/bin/env python3
"""Build services/onthesnow_season_pages.json: resort_id -> OnTheSnow page.

Two steps, run from a machine with a residential IP (be polite: one pass,
a few concurrent requests):

1. crawl: read OnTheSnow sitemaps (onthesnow.com for North America,
   onthesnow.co.uk for Europe) plus the Japan / southern-hemisphere country
   listings, fetch every resort page once and save the parsed resort records
   as JSON lines.

       python scripts/build_onthesnow_season_mapping.py crawl /tmp/ots.jsonl

2. match: match catalog resorts (data/resorts.json) to OnTheSnow records by
   distance + name similarity and write the mapping.

       python scripts/build_onthesnow_season_mapping.py match /tmp/ots.jsonl

The match is conservative: a resort without a confident match gets no entry
(and therefore no season dates), which is always preferable to showing
another resort's dates.
"""

from __future__ import annotations

import argparse
import difflib
import gzip
import json
import math
import re
import sys
import threading
import time
import unicodedata
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND / "src"))

from services.season_dates import _flight_rows, _resolve  # noqa: E402

CATALOG = BACKEND / "data" / "resorts.json"
OUTPUT = BACKEND / "src" / "services" / "onthesnow_season_pages.json"
USER_AGENT = (
    "Mozilla/5.0 (compatible; PowderChaser/1.0; +https://github.com/snowtracker)"
)
SITEMAPS = [
    "https://www.onthesnow.com/sitemap_website.xml",
    "https://www.onthesnow.co.uk/sitemap_website.xml",
]
EXTRA_LISTINGS = [
    "https://www.onthesnow.com/japan/skireport",
    "https://www.onthesnow.com/new-zealand/skireport",
    "https://www.onthesnow.com/australia/skireport",
    "https://www.onthesnow.com/chile/skireport",
    "https://www.onthesnow.com/argentina/skireport",
]


# ---------------------------------------------------------------------------
# crawl
# ---------------------------------------------------------------------------


def _get(url: str) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept-Language": "en",
            "Accept-Encoding": "gzip",
        },
    )
    with urllib.request.urlopen(req, timeout=40) as r:
        body = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            body = gzip.decompress(body)
        return body.decode("utf-8", "replace")


def page_records(html: str) -> list[dict]:
    """Resort records (with coordinates) from one page's RSC payload."""
    rows = _flight_rows(html)
    found: dict[str, dict] = {}

    def visit(obj):
        if isinstance(obj, dict):
            if "uuid" in obj and "slug" in obj and "status" in obj:
                status = _resolve(obj.get("status"), rows)
                region = _resolve(obj.get("region"), rows)
                if isinstance(status, dict) and "openFlag" in status:
                    found[str(obj["uuid"])] = {
                        "uuid": str(obj["uuid"]),
                        "title": obj.get("title"),
                        "title_original": obj.get("title_original"),
                        "slug": obj.get("slug"),
                        "region_slug": region.get("slug")
                        if isinstance(region, dict)
                        else None,
                        "latitude": obj.get("latitude"),
                        "longitude": obj.get("longitude"),
                        "openFlag": status.get("openFlag"),
                        "openingDate": status.get("openingDate"),
                        "closingDate": status.get("closingDate"),
                    }
            for v in obj.values():
                visit(v)
        elif isinstance(obj, list):
            for v in obj:
                visit(v)

    for row in rows.values():
        visit(row)
    return list(found.values())


def crawl(out_path: str) -> None:
    urls: set[str] = set()
    for sm in SITEMAPS:
        for loc in re.findall(r"<loc>([^<]+)</loc>", _get(sm)):
            if re.fullmatch(
                r"https://www\.onthesnow\.[a-z.]+/[^/]+/[^/]+/skireport", loc
            ):
                urls.add(loc)
    for listing in EXTRA_LISTINGS:
        for href in re.findall(
            r'href="(/[a-z0-9-]+/[a-z0-9-]+/skireport)"', _get(listing)
        ):
            urls.add("https://www.onthesnow.com" + href)
    print(f"{len(urls)} resort pages", flush=True)

    lock = threading.Lock()
    with open(out_path, "w") as out:

        def fetch(url: str) -> None:
            status, recs = None, []
            try:
                recs = page_records(_get(url))
                status = 200
            except urllib.error.HTTPError as e:
                status = e.code
            except Exception as e:  # noqa: BLE001
                status = f"ERR {e}"
            with lock:
                out.write(
                    json.dumps({"page": url, "status": status, "records": recs}) + "\n"
                )
            time.sleep(0.3)

        with ThreadPoolExecutor(4) as pool:
            list(pool.map(fetch, sorted(urls)))


# ---------------------------------------------------------------------------
# match
# ---------------------------------------------------------------------------

# Words too generic to identify a resort.
_STOPWORDS = {
    "ski",
    "skiing",
    "skis",
    "area",
    "areas",
    "resort",
    "resorts",
    "the",
    "and",
    "mountain",
    "mount",
    "mt",
    "de",
    "la",
    "le",
    "les",
    "di",
    "del",
    "du",
    "des",
    "am",
    "im",
    "an",
    "der",
    "skigebiet",
    "skicentrum",
    "skiareal",
    "skiarena",
    "skicenter",
    "skicentar",
    "skisenter",
    "skiresort",
    "skipark",
    "osrodek",
    "narciarski",
    "stacja",
    "narciarska",
    "station",
    "centre",
    "center",
    "bergbahnen",
    "lifts",
    "hiihtokeskus",
    "domaine",
    "skiable",
    "areal",
    "sport",
    "sports",
    "club",
    "s",
}


def _tokens(name: str | None) -> list[str]:
    if not name:
        return []
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9 ]+", " ", s.lower())
    return [t for t in s.split() if t not in _STOPWORDS and len(t) > 1]


def _token_match(a: str, b: str) -> bool:
    if a == b:
        return True
    if min(len(a), len(b)) >= 5 and (a.startswith(b) or b.startswith(a)):
        return True
    return (
        min(len(a), len(b)) >= 5 and difflib.SequenceMatcher(None, a, b).ratio() >= 0.85
    )


def name_similarity(a: str | None, b: str | None) -> tuple[float, float]:
    """(share of the shorter name's tokens found in the other, string ratio)."""
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0, 0.0
    short, other = (ta, tb) if len(ta) <= len(tb) else (tb, ta)
    hits = sum(1 for t in short if any(_token_match(t, o) for o in other))
    ratio = difflib.SequenceMatcher(None, " ".join(ta), " ".join(tb)).ratio()
    return hits / len(short), ratio


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def accept(distance_km: float, overlap: float, ratio: float) -> bool:
    """Conservative acceptance: closer resorts need less name agreement."""
    if distance_km <= 3:
        return overlap >= 0.5 or ratio >= 0.7
    if distance_km <= 10:
        return overlap >= 0.5 or ratio >= 0.85
    if distance_km <= 25:
        return overlap == 1.0 and ratio >= 0.85
    return False


# Hand-reviewed corrections (Nov 2026 review of the automatic matches).
# resort_id -> OnTheSnow uuid to force a match, or None to reject one.
MANUAL_OVERRIDES: dict[str, str | None] = {
    # Wrong automatic matches: a different hill in the same town/area
    "oslo-tryvann-skimore": "1843",  # Oslo Vinterpark - Tryvann (not Grefsen)
    "szyndzielnia-bielsko-bia-a": None,  # Debowiec is a different hill
    "folgaria-fiorentini": None,  # Tonezza is a different area
    # Correct matches the distance/name thresholds miss
    "sunshine-village": "448",  # Banff Sunshine (catalog duplicate)
    "gotschen-bischofswiesen": "2969",  # Gotschen (10.1 km)
    "pfelders-moos-in-passeier": "1723",  # Plan Val Passiria / Pfelders
}


def load_ots(jsonl_path: str) -> dict[str, dict]:
    """uuid -> record with the page URL that carries it as its main resort."""
    ots: dict[str, dict] = {}
    for line in open(jsonl_path, encoding="utf-8"):
        row = json.loads(line)
        if row.get("status") != 200:
            continue
        page = row["page"]
        page_slug = page.rstrip("/").split("/")[-2]
        for rec in row["records"]:
            try:
                lat, lon = float(rec["latitude"]), float(rec["longitude"])
            except (TypeError, ValueError, KeyError):
                continue
            entry = ots.setdefault(rec["uuid"], {**rec, "lat": lat, "lon": lon})
            if rec.get("slug") == page_slug:
                entry["url"] = page
    return {u: r for u, r in ots.items() if r.get("url")}


def match(jsonl_path: str, out_path: Path = OUTPUT, report: bool = True) -> dict:
    ots = list(load_ots(jsonl_path).values())
    catalog = json.load(open(CATALOG, encoding="utf-8"))["resorts"]
    mapping: dict[str, dict] = {}
    rejected = []
    for resort in catalog:
        lat, lon = resort.get("latitude"), resort.get("longitude")
        if lat is None or lon is None or (lat == 0 and lon == 0):
            continue
        best = None
        for rec in ots:
            if abs(rec["lat"] - lat) > 0.4 or abs(rec["lon"] - lon) > 0.6:
                continue
            d = haversine_km(lat, lon, rec["lat"], rec["lon"])
            overlap, ratio = max(
                name_similarity(resort["name"], rec.get("title")),
                name_similarity(resort["name"], rec.get("title_original")),
            )
            ok = accept(d, overlap, ratio)
            key = (ok, overlap + ratio - d / 25)
            if best is None or key > best[0]:
                best = (key, d, overlap, ratio, rec)
        if best is None:
            continue
        (ok, _), d, overlap, ratio, rec = best
        if ok:
            mapping[resort["resort_id"]] = {
                "url": rec["url"],
                "uuid": rec["uuid"],
                "name": rec.get("title"),
                "distance_km": round(d, 1),
                "name_overlap": round(overlap, 2),
            }
        else:
            rejected.append(
                (
                    resort["resort_id"],
                    resort["name"],
                    rec.get("title"),
                    round(d, 1),
                    round(overlap, 2),
                    round(ratio, 2),
                )
            )

    ots_by_uuid = {rec["uuid"]: rec for rec in ots}
    for rid, uuid in MANUAL_OVERRIDES.items():
        if uuid is None:
            mapping.pop(rid, None)
        elif uuid in ots_by_uuid:
            rec = ots_by_uuid[uuid]
            mapping[rid] = {
                "url": rec["url"],
                "uuid": uuid,
                "name": rec.get("title"),
                "distance_km": None,
                "name_overlap": 1.0,
                "manual": True,
            }

    # Several catalog resorts on one OnTheSnow page usually means sub-areas
    # matched to an umbrella resort (e.g. "Aspen Highlands" -> "Aspen
    # Snowmass", "Hakuba Cortina" -> "Hakuba Valley"). Their opening dates
    # differ, so keep only full-name matches on shared pages.
    by_uuid: dict[str, list[str]] = {}
    for rid, m in mapping.items():
        by_uuid.setdefault(m["uuid"], []).append(rid)
    for rids in by_uuid.values():
        if len(rids) < 2:
            continue
        for rid in rids:
            if mapping[rid]["name_overlap"] < 1.0:
                m = mapping.pop(rid)
                rejected.append(
                    (
                        rid,
                        "shared page, partial name",
                        m["name"],
                        m["distance_km"],
                        m["name_overlap"],
                        None,
                    )
                )

    out = {
        "_comment": (
            "resort_id -> OnTheSnow resort page used for season opening/closing "
            "dates. Generated by scripts/build_onthesnow_season_mapping.py; "
            "edit by re-running or by hand (remove wrong matches)."
        ),
        "resorts": dict(sorted(mapping.items())),
    }
    out_path.write_text(
        json.dumps(out, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    if report:
        print(f"matched {len(mapping)} of {len(catalog)} catalog resorts -> {out_path}")
        print(
            "closest rejected candidates (resort, name, ots title, km, overlap, ratio):"
        )
        for r in sorted(rejected, key=lambda x: x[3])[:80]:
            print("  ", r)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("crawl")
    c.add_argument("out")
    m = sub.add_parser("match")
    m.add_argument("jsonl")
    m.add_argument("--out", type=Path, default=OUTPUT)
    args = ap.parse_args()
    if args.cmd == "crawl":
        crawl(args.out)
    else:
        match(args.jsonl, args.out)


if __name__ == "__main__":
    main()
