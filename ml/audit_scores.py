#!/usr/bin/env python3
"""
Audit training data scores for physical inconsistencies.

Loads training features and all score files, matches them by (resort_id, date),
and flags data points that violate physical rules about snow conditions.
"""

import sys
import json
import glob
import os
from collections import defaultdict

sys.path.insert(0, "src")

FEATURES_PATH = "/Users/wouter/dev/snow/ml/training_features.json"
SCORES_DIR = "/Users/wouter/dev/snow/ml/scores"
OUTPUT_PATH = "/Users/wouter/dev/snow/ml/scores/scores_audited.json"


def load_features():
    """Load training features and index by (resort_id, date)."""
    with open(FEATURES_PATH) as f:
        data = json.load(f)

    features_by_key = {}
    for item in data["data"]:
        key = (item["resort_id"], item["date"])
        features_by_key[key] = item

    print(
        f"Loaded {len(features_by_key)} unique feature records from training_features.json"
    )
    return features_by_key


def load_scores():
    """Load all score files and merge into a list of (resort_id, date, score, source_file)."""
    all_scores = []
    score_files = sorted(glob.glob(os.path.join(SCORES_DIR, "scores_*.json")))

    for filepath in score_files:
        basename = os.path.basename(filepath)
        # Skip audited output file if it exists
        if basename == "scores_audited.json":
            continue

        with open(filepath) as f:
            data = json.load(f)

        if not isinstance(data, list):
            print(f"  Skipping {basename}: not a list")
            continue

        count = 0
        for item in data:
            resort_id = item.get("resort_id")
            date = item.get("date")
            # Score field varies: "score" or "quality_score"
            score = item.get("score") or item.get("quality_score")

            if resort_id and date and score is not None:
                all_scores.append(
                    {
                        "resort_id": resort_id,
                        "date": date,
                        "score": float(score),
                        "source_file": basename,
                        "original_item": item,
                    }
                )
                count += 1

        print(f"  Loaded {count} scores from {basename}")

    print(f"Total scores loaded: {len(all_scores)}")
    return all_scores


def get_feature(features, name, default=None):
    """Safely get a feature value."""
    val = features.get(name, default)
    if val is None:
        return default
    return float(val)


def check_rules(features, score):
    """
    Check all physical rules. Returns list of (rule_name, description, max/min bound).
    Each entry is a violation.
    """
    violations = []

    cur_temp = get_feature(features, "cur_temp")
    max_temp_24h = get_feature(features, "max_temp_24h")
    snowfall_24h = get_feature(features, "snowfall_24h_cm")
    snowfall_72h = get_feature(features, "snowfall_72h_cm")
    freeze_thaw_days_ago = get_feature(features, "freeze_thaw_days_ago")
    warmest_thaw = get_feature(features, "warmest_thaw")

    # Rule 1: Cold can't be soft
    # If cur_temp <= -5 AND max_temp_24h <= -2, score <= 4.5
    if (
        cur_temp is not None
        and max_temp_24h is not None
        and cur_temp <= -5
        and max_temp_24h <= -2
        and score > 4.5
    ):
        violations.append(
            (
                "Rule 1: Cold can't be soft",
                f"cur_temp={cur_temp:.1f}, max_temp_24h={max_temp_24h:.1f} => max score 4.5",
                {"max": 4.5},
            )
        )

    # Rule 2: Very cold with no fresh snow
    # If cur_temp <= -10 AND snowfall_24h < 1.0 AND snowfall_72h < 5.0, score <= 4.0
    if (
        cur_temp is not None
        and snowfall_24h is not None
        and snowfall_72h is not None
        and cur_temp <= -10
        and snowfall_24h < 1.0
        and snowfall_72h < 5.0
        and score > 4.0
    ):
        violations.append(
            (
                "Rule 2: Very cold, no fresh snow",
                f"cur_temp={cur_temp:.1f}, snowfall_24h={snowfall_24h:.1f}, snowfall_72h={snowfall_72h:.1f} => max score 4.0",
                {"max": 4.0},
            )
        )

    # Rule 3: Recent freeze-thaw is bad
    # If freeze_thaw_days_ago < 2 AND warmest_thaw >= 3.0, score <= 3.5
    if (
        freeze_thaw_days_ago is not None
        and warmest_thaw is not None
        and freeze_thaw_days_ago < 2
        and warmest_thaw >= 3.0
        and score > 3.5
    ):
        violations.append(
            (
                "Rule 3: Recent freeze-thaw",
                f"freeze_thaw_days_ago={freeze_thaw_days_ago:.1f}, warmest_thaw={warmest_thaw:.1f} => max score 3.5",
                {"max": 3.5},
            )
        )

    # Rule 4: Fresh deep snow is good
    # If snowfall_24h >= 15 AND cur_temp <= -2, score >= 4.5
    if (
        snowfall_24h is not None
        and cur_temp is not None
        and snowfall_24h >= 15
        and cur_temp <= -2
        and score < 4.5
    ):
        violations.append(
            (
                "Rule 4: Fresh deep snow is good",
                f"snowfall_24h={snowfall_24h:.1f}, cur_temp={cur_temp:.1f} => min score 4.5",
                {"min": 4.5},
            )
        )

    # Rule 5: Warm with no snow is bad
    # If cur_temp >= 5 AND snowfall_72h < 2, score <= 3.0
    if (
        cur_temp is not None
        and snowfall_72h is not None
        and cur_temp >= 5
        and snowfall_72h < 2
        and score > 3.0
    ):
        violations.append(
            (
                "Rule 5: Warm, no snow",
                f"cur_temp={cur_temp:.1f}, snowfall_72h={snowfall_72h:.1f} => max score 3.0",
                {"max": 3.0},
            )
        )

    # Rule 6: Fresh snow but warm
    # If snowfall_24h >= 5 AND cur_temp >= 3, score between 3.0 and 5.0
    if (
        snowfall_24h is not None
        and cur_temp is not None
        and snowfall_24h >= 5
        and cur_temp >= 3
    ):
        if score < 3.0:
            violations.append(
                (
                    "Rule 6: Fresh snow but warm (too low)",
                    f"snowfall_24h={snowfall_24h:.1f}, cur_temp={cur_temp:.1f} => min score 3.0",
                    {"min": 3.0},
                )
            )
        elif score > 5.0:
            violations.append(
                (
                    "Rule 6: Fresh snow but warm (too high)",
                    f"snowfall_24h={snowfall_24h:.1f}, cur_temp={cur_temp:.1f} => max score 5.0",
                    {"max": 5.0},
                )
            )

    return violations


def clamp_score(score, violations):
    """Apply all violation bounds to clamp the score."""
    corrected = score
    for _, _, bounds in violations:
        if "max" in bounds:
            corrected = min(corrected, bounds["max"])
        if "min" in bounds:
            corrected = max(corrected, bounds["min"])
    return round(corrected, 1)


def main():
    print("=" * 80)
    print("SNOW TRAINING DATA AUDIT - Physical Consistency Check")
    print("=" * 80)
    print()

    # Load data
    features_by_key = load_features()
    print()
    all_scores = load_scores()
    print()

    # Match and audit
    matched = 0
    unmatched = 0
    rule_violations = defaultdict(list)
    all_violations = []

    for score_entry in all_scores:
        key = (score_entry["resort_id"], score_entry["date"])
        features = features_by_key.get(key)

        if features is None:
            unmatched += 1
            continue

        matched += 1
        score = score_entry["score"]
        violations = check_rules(features, score)

        if violations:
            for rule_name, desc, bounds in violations:
                violation_info = {
                    "resort_id": score_entry["resort_id"],
                    "date": score_entry["date"],
                    "score": score,
                    "source_file": score_entry["source_file"],
                    "cur_temp": get_feature(features, "cur_temp"),
                    "max_temp_24h": get_feature(features, "max_temp_24h"),
                    "snowfall_24h_cm": get_feature(features, "snowfall_24h_cm"),
                    "snowfall_72h_cm": get_feature(features, "snowfall_72h_cm"),
                    "freeze_thaw_days_ago": get_feature(
                        features, "freeze_thaw_days_ago"
                    ),
                    "warmest_thaw": get_feature(features, "warmest_thaw"),
                    "rule": rule_name,
                    "description": desc,
                }
                rule_violations[rule_name].append(violation_info)
                all_violations.append(violation_info)

    print(f"Matched {matched} score entries with features ({unmatched} unmatched)")
    print()

    # Print violations grouped by rule
    print("=" * 80)
    print("VIOLATIONS BY RULE")
    print("=" * 80)

    for rule_name in sorted(rule_violations.keys()):
        violations_list = rule_violations[rule_name]
        print(f"\n{'─' * 80}")
        print(f"  {rule_name}: {len(violations_list)} violations")
        print(f"{'─' * 80}")
        print(
            f"  {'Resort':<30} {'Date':<12} {'Score':>6} {'Temp':>6} {'Snow24':>7} {'Snow72':>7} {'FT_ago':>7} {'Source'}"
        )
        print(
            f"  {'─' * 30} {'─' * 10}  {'─' * 5} {'─' * 5}  {'─' * 5}  {'─' * 5}  {'─' * 5} {'─' * 25}"
        )

        for v in sorted(violations_list, key=lambda x: (x["resort_id"], x["date"])):
            ft_ago = (
                f"{v['freeze_thaw_days_ago']:.0f}"
                if v["freeze_thaw_days_ago"] is not None
                else "N/A"
            )
            snow24 = (
                f"{v['snowfall_24h_cm']:.1f}"
                if v["snowfall_24h_cm"] is not None
                else "N/A"
            )
            snow72 = (
                f"{v['snowfall_72h_cm']:.1f}"
                if v["snowfall_72h_cm"] is not None
                else "N/A"
            )
            temp = f"{v['cur_temp']:.1f}" if v["cur_temp"] is not None else "N/A"
            print(
                f"  {v['resort_id']:<30} {v['date']:<12} {v['score']:>5.1f}  {temp:>5} {snow24:>6} {snow72:>6}  {ft_ago:>5}  {v['source_file']}"
            )

    # Summary
    total_violations = len(all_violations)
    unique_violations = len(
        {(v["resort_id"], v["date"], v["source_file"]) for v in all_violations}
    )

    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"  Total data points matched:     {matched}")
    print(f"  Total unmatched (no features): {unmatched}")
    print(f"  Total rule violations:         {total_violations}")
    print(f"  Unique data points violated:   {unique_violations}")
    if matched > 0:
        print(
            f"  Violation rate:                {100.0 * unique_violations / matched:.1f}%"
        )
    else:
        print("  Violation rate:                N/A")
    print()
    print("  Violations per rule:")
    for rule_name in sorted(rule_violations.keys()):
        print(f"    {rule_name}: {len(rule_violations[rule_name])}")
    print()

    # Build corrected scores
    corrected_entries = []
    corrections_made = 0

    for score_entry in all_scores:
        key = (score_entry["resort_id"], score_entry["date"])
        features = features_by_key.get(key)
        original_score = score_entry["score"]
        corrected_score = original_score

        if features is not None:
            violations = check_rules(features, original_score)
            if violations:
                corrected_score = clamp_score(original_score, violations)
                if corrected_score != original_score:
                    corrections_made += 1

        entry = {
            "resort_id": score_entry["resort_id"],
            "date": score_entry["date"],
            "score": corrected_score,
            "source": score_entry["source_file"]
            .replace("scores_", "")
            .replace(".json", ""),
            "audited": corrected_score != original_score,
        }
        if corrected_score != original_score:
            entry["original_score"] = original_score
        corrected_entries.append(entry)

    with open(OUTPUT_PATH, "w") as f:
        json.dump(corrected_entries, f, indent=2)

    print(f"  Corrections applied: {corrections_made} scores clamped")
    print(f"  Corrected scores written to: {OUTPUT_PATH}")
    print(f"  Total entries in audited file: {len(corrected_entries)}")
    print()

    # Show some examples of corrections
    corrected_examples = [e for e in corrected_entries if e.get("audited")]
    if corrected_examples:
        print("=" * 80)
        print("SAMPLE CORRECTIONS (first 20)")
        print("=" * 80)
        print(f"  {'Resort':<30} {'Date':<12} {'Original':>9} {'Corrected':>10}")
        print(f"  {'─' * 30} {'─' * 10}  {'─' * 8}  {'─' * 8}")
        for entry in corrected_examples[:20]:
            print(
                f"  {entry['resort_id']:<30} {entry['date']:<12} {entry['original_score']:>8.1f}  {entry['score']:>8.1f}"
            )


if __name__ == "__main__":
    main()
