#!/usr/bin/env python3
"""End-to-end evaluation of snow quality scores against skier expectations.

Tests the FULL pipeline output (0-100 scores from the API), not just raw ML scores.
Uses skier-oriented quality rules based on how real skiers experience conditions.

Usage:
    python3 ml/eval_e2e.py              # test against prod
    python3 ml/eval_e2e.py staging      # test against staging

Rules are based on:
- External snow reports (OnTheSnow, Snow-Forecast, resort official reports)
- Skier community consensus (what conditions actually feel like on-snow)
- User-submitted condition reports
"""

import json
import sys
import urllib.request
from dataclasses import dataclass

APIS = {
    "prod": "https://api.powderchaserapp.com",
    "staging": "https://staging.api.powderchaserapp.com",
    "dev": "https://dev.api.powderchaserapp.com",
}

arg = sys.argv[1] if len(sys.argv) > 1 else "prod"
API = APIS.get(arg, arg)


@dataclass
class QualityRule:
    """A rule about what score range is acceptable for given conditions."""

    name: str
    description: str
    max_score: int | None = None  # score should be <= this
    min_score: int | None = None  # score should be >= this


def fetch_resort(resort_id: str) -> dict | None:
    url = f"{API}/api/v1/resorts/{resort_id}/snow-quality"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            return json.loads(resp.read())
    except Exception as e:
        print(f"  ERROR fetching {resort_id}: {e}")
        return None


def check_rules(data: dict) -> list[tuple[QualityRule, bool, str]]:
    """Check all quality rules against a resort's data. Returns (rule, passed, detail)."""
    results = []
    score = data.get("overall_snow_score")
    quality = data.get("overall_quality", "")
    explanation = data.get("overall_explanation", "")

    if score is None:
        return results

    elevs = data.get("elevations", {})
    mid = elevs.get("mid", {})
    top = elevs.get("top", {})
    base = elevs.get("base", {})

    mid_temp = mid.get("temperature_celsius")
    top_temp = top.get("temperature_celsius")
    base_temp = base.get("temperature_celsius")
    mid_fresh = mid.get("fresh_snow_cm", 0)
    top_fresh = top.get("fresh_snow_cm", 0)

    # Use best available temp (prefer mid)
    temp = (
        mid_temp
        if mid_temp is not None
        else (top_temp if top_temp is not None else base_temp)
    )

    # Rule 1: Icy conditions should score ≤50
    if "icy" in explanation.lower() or "thaw-freeze" in explanation.lower():
        rule = QualityRule(
            name="icy_max_50",
            description="Icy/thaw-freeze conditions should score ≤50 (mediocre max)",
            max_score=50,
        )
        passed = score <= 50
        results.append(
            (rule, passed, f"score={score}, explanation mentions ice/thaw-freeze")
        )

    # Rule 2: No fresh snow in 7+ days should score ≤75
    if "no new snow in" in explanation.lower():
        # Extract days
        import re

        days_match = re.search(r"no new snow in (\d+) day", explanation.lower())
        if days_match:
            days = int(days_match.group(1))
            if days >= 7:
                rule = QualityRule(
                    name="week_old_max_75",
                    description=f"No fresh snow in {days} days should score ≤75 (great max)",
                    max_score=75,
                )
                passed = score <= 75
                results.append((rule, passed, f"score={score}, {days} days since snow"))

    # Rule 3: Thin base (<30cm at mid) should score ≤30
    mid_depth = mid.get("snow_depth_cm") if mid else None
    if mid_depth is not None and mid_depth < 30:
        rule = QualityRule(
            name="thin_base_max_30",
            description=f"Thin base ({mid_depth:.0f}cm at mid) should score ≤30 (poor max)",
            max_score=30,
        )
        passed = score <= 30
        results.append((rule, passed, f"score={score}, mid depth={mid_depth:.0f}cm"))

    # Rule 4: Fresh powder (>15cm/24h) at cold temps (<-5C) should score ≥70
    # Only trigger if not "aging"/"settled" snow (check all explanations)
    best_fresh = max(mid_fresh or 0, top_fresh or 0)
    all_explanations = " ".join(
        e.get("explanation", "") for e in [mid, top, base, {"explanation": explanation}]
    ).lower()
    is_actually_fresh = (
        best_fresh >= 15
        and "aging" not in all_explanations
        and "settled" not in all_explanations
    )
    if is_actually_fresh and temp is not None and temp < -5:
        rule = QualityRule(
            name="powder_day_min_70",
            description=f"Fresh powder ({best_fresh:.0f}cm) at cold ({temp:.0f}°C) should score ≥70",
            min_score=70,
        )
        passed = score >= 70
        results.append(
            (
                rule,
                passed,
                f"score={score}, fresh={best_fresh:.0f}cm, temp={temp:.0f}°C",
            )
        )

    # Rule 5: Above freezing + no fresh = ≤60
    if temp is not None and temp > 2 and best_fresh < 3:
        rule = QualityRule(
            name="warm_no_fresh_max_60",
            description=f"Warm ({temp:.0f}°C) with no fresh snow should score ≤60",
            max_score=60,
        )
        passed = score <= 60
        results.append(
            (
                rule,
                passed,
                f"score={score}, temp={temp:.0f}°C, fresh={best_fresh:.0f}cm",
            )
        )

    # Rule 6: Deep base (>200cm) + cold (<-3C) should score ≥40 minimum
    # Even with no fresh snow, a deep cold base is skiable
    top_depth = top.get("snow_depth_cm") if top else None
    if top_depth is not None and top_depth > 200 and temp is not None and temp < -3:
        rule = QualityRule(
            name="deep_cold_base_min_40",
            description=f"Deep base ({top_depth:.0f}cm) + cold ({temp:.0f}°C) should score ≥40",
            min_score=40,
        )
        passed = score >= 40
        results.append(
            (rule, passed, f"score={score}, depth={top_depth:.0f}cm, temp={temp:.0f}°C")
        )

    # Rule 7: "Powder day" or "champagne" quality must score ≥80
    if quality in ("powder_day", "champagne_powder"):
        rule = QualityRule(
            name="powder_quality_min_80",
            description=f"'{quality}' quality must score ≥80",
            min_score=80,
        )
        passed = score >= 80
        results.append((rule, passed, f"score={score}, quality={quality}"))

    # Rule 8: "bad" or "horrible" quality must score ≤25
    if quality in ("bad", "horrible"):
        rule = QualityRule(
            name="bad_quality_max_25",
            description=f"'{quality}' quality must score ≤25",
            max_score=25,
        )
        passed = score <= 25
        results.append((rule, passed, f"score={score}, quality={quality}"))

    return results


# Test resorts
RESORTS = [
    "whistler-blackcomb",
    "mammoth-mountain",
    "palisades-tahoe",
    "big-white",
    "vail",
    "park-city",
    "jackson-hole",
    "breckenridge",
    "steamboat",
    "aspen-snowmass",
    "telluride",
    "lake-louise",
    "revelstoke",
    "chamonix",
    "zermatt",
    "st-anton",
    "verbier",
    "val-disere",
    "niseko",
    "hakuba-valley",
]

print(f"\n{'=' * 80}")
print(f"E2E Snow Quality Evaluation — {API}")
print(f"{'=' * 80}\n")

total_rules = 0
total_passed = 0
failures = []

for resort_id in RESORTS:
    data = fetch_resort(resort_id)
    if data is None:
        continue

    score = data.get("overall_snow_score", "?")
    quality = data.get("overall_quality", "?")
    results = check_rules(data)

    passed = sum(1 for _, p, _ in results if p)
    failed = sum(1 for _, p, _ in results if not p)
    total_rules += len(results)
    total_passed += passed

    status = "PASS" if failed == 0 else "FAIL"
    rules_str = f"{passed}/{len(results)}" if results else "no rules"
    print(f"  {status}  {resort_id:<25} {quality:<15} {score:>3}  ({rules_str})")

    for rule, p, detail in results:
        if not p:
            failures.append((resort_id, rule, detail))
            print(f"        FAIL: {rule.description}")
            print(f"              {detail}")

print(f"\n{'=' * 80}")
print(
    f"SUMMARY: {total_passed}/{total_rules} rules passed ({total_passed * 100 // total_rules if total_rules else 0}%)"
)
if failures:
    print(
        f"         {len(failures)} failures across {len(set(r for r, _, _ in failures))} resorts"
    )
    print("\nFailed rules breakdown:")
    from collections import Counter

    rule_counts = Counter(r.name for _, r, _ in failures)
    for name, count in rule_counts.most_common():
        print(f"  {name}: {count} failures")
print(f"{'=' * 80}")
print(f"\nStatus: {'PASS' if not failures else 'FAIL'}")
