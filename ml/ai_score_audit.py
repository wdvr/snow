#!/usr/bin/env python3
"""
Comprehensive AI-powered score auditing system for snow quality training data.

Uses physics-based snow quality rules to audit all scored training data points,
flagging and correcting scores that violate known physical constraints.

Physics rules encode:
- Temperature + snow freshness matrix
- Freeze-thaw cycle effects
- Snow depth adjustments
- Wind effects on snow quality
"""

import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime

# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

BASE_DIR = "/Users/wouter/dev/snow"
FEATURES_PATH = os.path.join(BASE_DIR, "ml/training_features.json")
SCORES_DIR = os.path.join(BASE_DIR, "ml/scores")
OUTPUT_PATH = os.path.join(SCORES_DIR, "scores_audited.json")

SCORE_FILES = [
    "scores_real.json",
    "scores_new_batch.json",
    "scores_production_collected.json",
    "scores_today_collected.json",
    # Skip scores_synthetic.json (synthetic resorts, no matching features)
    # Skip scores_audited.json (our own output)
]


def load_features():
    """Load training features indexed by (resort_id, date)."""
    with open(FEATURES_PATH) as f:
        raw = json.load(f)
    features_by_key = {}
    for row in raw["data"]:
        key = (row["resort_id"], row["date"])
        features_by_key[key] = row
    print(f"Loaded {len(features_by_key)} feature rows from training_features.json")
    return features_by_key


def load_all_scores():
    """
    Load scores from all score files. Returns list of dicts with unified fields.
    When multiple entries exist for the same (resort_id, date), we keep ALL of them
    as separate audit targets but note their source for deduplication later.
    """
    all_entries = []
    for fname in SCORE_FILES:
        path = os.path.join(SCORES_DIR, fname)
        if not os.path.exists(path):
            print(f"  WARNING: {fname} not found, skipping")
            continue
        with open(path) as f:
            data = json.load(f)
        for entry in data:
            score = entry.get("score", entry.get("quality_score"))
            if score is None:
                continue
            all_entries.append(
                {
                    "resort_id": entry["resort_id"],
                    "date": entry.get("date", ""),
                    "score": float(score),
                    "source": entry.get("source", fname),
                    "source_file": fname,
                    "elevation_level": entry.get("elevation_level", ""),
                }
            )
    print(
        f"Loaded {len(all_entries)} total score entries from {len(SCORE_FILES)} files"
    )
    return all_entries


# ---------------------------------------------------------------------------
# Physics-based scoring algorithm
# ---------------------------------------------------------------------------


def safe_float(val, default=0.0):
    """Safely convert to float, handling None."""
    if val is None:
        return default
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def compute_physics_score(feat):
    """
    Compute the physics-based expected score from weather features.
    Returns (score, list_of_reasons).
    """
    reasons = []

    # Extract features with safe defaults
    cur_temp = safe_float(feat.get("cur_temp"), 0.0)
    snow_24h = safe_float(feat.get("snowfall_24h_cm"), 0.0)
    snow_72h = safe_float(feat.get("snowfall_72h_cm"), 0.0)
    snow_depth = safe_float(feat.get("snow_depth_cm"), 0.0)
    freeze_thaw_days_ago = safe_float(feat.get("freeze_thaw_days_ago"), 999.0)
    warmest_thaw = safe_float(feat.get("warmest_thaw"), 0.0)
    snow_since_freeze = safe_float(feat.get("snow_since_freeze_cm"), 0.0)
    avg_wind = safe_float(feat.get("avg_wind_24h"), 0.0)
    max_wind_gust = safe_float(feat.get("max_wind_gust_24h"), 0.0)

    # -----------------------------------------------------------------------
    # Step 1: Base score from freshness
    # -----------------------------------------------------------------------
    if snow_24h >= 20:
        base = 5.5
        reasons.append(f"Base=5.5 (24h snow={snow_24h:.1f}cm >= 20)")
    elif snow_24h >= 10:
        base = 5.0
        reasons.append(f"Base=5.0 (24h snow={snow_24h:.1f}cm >= 10)")
    elif snow_24h >= 5:
        base = 4.5
        reasons.append(f"Base=4.5 (24h snow={snow_24h:.1f}cm >= 5)")
    elif snow_72h >= 20:
        base = 4.0
        reasons.append(
            f"Base=4.0 (72h snow={snow_72h:.1f}cm >= 20, 24h={snow_24h:.1f})"
        )
    elif snow_72h >= 10:
        base = 3.5
        reasons.append(
            f"Base=3.5 (72h snow={snow_72h:.1f}cm >= 10, 24h={snow_24h:.1f})"
        )
    else:
        base = 3.0
        reasons.append(
            f"Base=3.0 (no significant fresh: 24h={snow_24h:.1f}, 72h={snow_72h:.1f})"
        )

    score = base

    # -----------------------------------------------------------------------
    # Step 2: Temperature adjustment
    # -----------------------------------------------------------------------
    temp_adj = 0.0
    if cur_temp < -15:
        if base >= 4.5:
            temp_adj = 0.0
            reasons.append(
                f"Temp adj=0 (extreme cold {cur_temp:.1f}C, fresh snow preserved)"
            )
        else:
            temp_adj = -0.3
            reasons.append(
                f"Temp adj=-0.3 (extreme cold {cur_temp:.1f}C, old snow brittle)"
            )
    elif cur_temp < -5:
        if base >= 4.5:
            temp_adj = 0.0
            reasons.append(f"Temp adj=0 (cold {cur_temp:.1f}C, fresh snow preserved)")
        else:
            temp_adj = 0.0
            reasons.append(f"Temp adj=0 (cold {cur_temp:.1f}C, preserved)")
    elif cur_temp < -3:
        if base >= 4.5:
            temp_adj = -0.2
            reasons.append(
                f"Temp adj=-0.2 (marginal cold {cur_temp:.1f}C, slightly less perfect)"
            )
        else:
            temp_adj = 0.0
            reasons.append(f"Temp adj=0 (marginal cold {cur_temp:.1f}C)")
    elif cur_temp < 0:
        temp_adj = -0.3
        reasons.append(f"Temp adj=-0.3 (transition zone {cur_temp:.1f}C)")
    elif cur_temp <= 3:
        temp_adj = -0.5
        reasons.append(f"Temp adj=-0.5 (warm/softening {cur_temp:.1f}C)")
    else:
        temp_adj = -1.0
        reasons.append(f"Temp adj=-1.0 (active melt {cur_temp:.1f}C)")

    score += temp_adj

    # -----------------------------------------------------------------------
    # Step 3: Snow depth adjustment
    # -----------------------------------------------------------------------
    depth_adj = 0.0
    if snow_depth <= 5:
        depth_adj = -1.0
        reasons.append(f"Depth adj=-1.0 (bare: {snow_depth:.0f}cm)")
    elif snow_depth < 30:
        depth_adj = -0.3
        reasons.append(f"Depth adj=-0.3 (thin: {snow_depth:.0f}cm)")
    elif snow_depth >= 150:
        depth_adj = 0.3
        reasons.append(f"Depth adj=+0.3 (deep base: {snow_depth:.0f}cm)")
    elif snow_depth >= 80:
        depth_adj = 0.2
        reasons.append(f"Depth adj=+0.2 (good base: {snow_depth:.0f}cm)")
    else:
        reasons.append(f"Depth adj=0 (adequate: {snow_depth:.0f}cm)")

    score += depth_adj

    # -----------------------------------------------------------------------
    # Step 4: Freeze-thaw adjustment
    # -----------------------------------------------------------------------
    ft_adj = 0.0
    if freeze_thaw_days_ago < 1:
        ft_adj = -2.0
        reasons.append(
            f"FT adj=-2.0 (just refroze, {freeze_thaw_days_ago:.1f} days ago)"
        )
    elif freeze_thaw_days_ago <= 3:
        ft_adj = -1.0
        reasons.append(f"FT adj=-1.0 (recent ice, {freeze_thaw_days_ago:.1f} days ago)")
    elif freeze_thaw_days_ago <= 7:
        ft_adj = -0.3
        reasons.append(
            f"FT adj=-0.3 (older FT event, {freeze_thaw_days_ago:.1f} days ago)"
        )
    else:
        reasons.append(f"FT adj=0 (no recent FT, {freeze_thaw_days_ago:.1f} days ago)")

    # Modulate FT penalty by snow accumulation since freeze
    if ft_adj < 0 and snow_since_freeze > 0:
        # Every 10cm reduces penalty by 30%
        reduction = min(0.9, (snow_since_freeze / 10.0) * 0.3)
        original_ft = ft_adj
        ft_adj = ft_adj * (1 - reduction)
        reasons.append(
            f"FT modulated: {original_ft:.1f} -> {ft_adj:.2f} "
            f"({snow_since_freeze:.1f}cm snow since freeze, {reduction:.0%} reduction)"
        )

    score += ft_adj

    # -----------------------------------------------------------------------
    # Step 5: Wind adjustment
    # -----------------------------------------------------------------------
    wind_adj = 0.0
    if avg_wind > 50:
        wind_adj = -0.5
        reasons.append(f"Wind adj=-0.5 (high wind: avg={avg_wind:.0f}km/h)")
    elif avg_wind > 30:
        wind_adj = -0.3
        reasons.append(f"Wind adj=-0.3 (moderate wind: avg={avg_wind:.0f}km/h)")
    else:
        reasons.append(f"Wind adj=0 (calm: avg={avg_wind:.0f}km/h)")

    score += wind_adj

    # -----------------------------------------------------------------------
    # Step 6: Clamp to valid range
    # -----------------------------------------------------------------------
    score = max(1.0, min(6.0, score))

    return round(score, 2), reasons


# ---------------------------------------------------------------------------
# Hard constraint checks (violations that MUST be corrected regardless)
# ---------------------------------------------------------------------------


def check_hard_constraints(feat, assigned_score):
    """
    Check for physics violations that are unambiguously wrong.
    Returns list of violation descriptions (empty = no violations).
    """
    violations = []

    cur_temp = safe_float(feat.get("cur_temp"), 0.0)
    snow_24h = safe_float(feat.get("snowfall_24h_cm"), 0.0)
    snow_72h = safe_float(feat.get("snowfall_72h_cm"), 0.0)
    snow_depth = safe_float(feat.get("snow_depth_cm"), 0.0)
    freeze_thaw_days_ago = safe_float(feat.get("freeze_thaw_days_ago"), 999.0)

    # 1. EXCELLENT (5.5+) with no fresh snow AND cold is impossible
    #    (cold + no fresh = packed powder at BEST = 4.0-4.5)
    if assigned_score >= 5.5 and snow_24h < 5 and snow_72h < 10:
        violations.append(
            f"Score {assigned_score} (EXCELLENT) but no significant fresh snow "
            f"(24h={snow_24h:.1f}cm, 72h={snow_72h:.1f}cm). Max should be ~4.0-4.5"
        )

    # 2. Score > 4.5 with no fresh snow at all (not even 72h)
    if assigned_score > 4.5 and snow_72h < 5:
        violations.append(
            f"Score {assigned_score} > 4.5 but < 5cm in 72h ({snow_72h:.1f}cm). "
            f"Without fresh snow, max is ~4.0"
        )

    # 3. High score with very warm temps and no fresh snow
    if assigned_score >= 4.5 and cur_temp > 3 and snow_24h < 5:
        violations.append(
            f"Score {assigned_score} >= 4.5 but warm ({cur_temp:.1f}C) and no fresh snow "
            f"(24h={snow_24h:.1f}cm). Should be < 3.5 (slush)"
        )

    # 4. High score with very recent freeze-thaw and minimal fresh snow
    if assigned_score >= 4.0 and freeze_thaw_days_ago < 1 and snow_24h < 10:
        violations.append(
            f"Score {assigned_score} >= 4.0 but just refroze ({freeze_thaw_days_ago:.1f} days ago) "
            f"with only {snow_24h:.1f}cm fresh. Should be < 3.0 (ice)"
        )

    # 5. Score >= 3.0 with essentially no snow on ground
    if assigned_score >= 3.0 and snow_depth <= 5 and snow_24h < 5:
        violations.append(
            f"Score {assigned_score} >= 3.0 but almost bare ground "
            f"(depth={snow_depth:.0f}cm, 24h={snow_24h:.1f}cm)"
        )

    # 6. Score <= 2.0 with tons of fresh powder at cold temps
    if assigned_score <= 2.0 and snow_24h >= 15 and cur_temp < -3:
        violations.append(
            f"Score {assigned_score} <= 2.0 but deep fresh powder "
            f"(24h={snow_24h:.1f}cm at {cur_temp:.1f}C). Should be >= 4.5"
        )

    # 7. Score <= 2.5 with significant fresh snow at cold temps
    if assigned_score <= 2.5 and snow_24h >= 10 and cur_temp < -2:
        violations.append(
            f"Score {assigned_score} <= 2.5 but fresh snow "
            f"(24h={snow_24h:.1f}cm at {cur_temp:.1f}C). Should be >= 4.0"
        )

    return violations


# ---------------------------------------------------------------------------
# Score correction logic
# ---------------------------------------------------------------------------


def correct_score(assigned_score, physics_score, hard_violations):
    """
    Decide whether to correct and what the new score should be.
    Returns (new_score, correction_reason).
    """
    diff = assigned_score - physics_score

    # Hard violations always get corrected
    if hard_violations:
        # Clamp toward physics score
        if assigned_score > physics_score + 0.5:
            new_score = round(physics_score + 0.5, 1)
            return (
                new_score,
                f"Hard violation: clamped from {assigned_score} to {new_score} (physics={physics_score})",
            )
        elif assigned_score < physics_score - 0.5:
            new_score = round(physics_score - 0.5, 1)
            return (
                new_score,
                f"Hard violation: raised from {assigned_score} to {new_score} (physics={physics_score})",
            )
        else:
            # Within tolerance despite violation flag - still correct slightly
            return round(
                physics_score, 1
            ), f"Hard violation: adjusted to physics={physics_score}"

    # Soft correction: only if diff > 1.0
    if abs(diff) > 1.0:
        if diff > 0:
            new_score = round(physics_score + 0.5, 1)
            return (
                new_score,
                f"Soft correction: reduced from {assigned_score} to {new_score} (physics={physics_score}, diff={diff:+.1f})",
            )
        else:
            new_score = round(physics_score - 0.5, 1)
            return (
                new_score,
                f"Soft correction: raised from {assigned_score} to {new_score} (physics={physics_score}, diff={diff:+.1f})",
            )

    # Within tolerance - preserve original
    return assigned_score, ""


# ---------------------------------------------------------------------------
# Deduplication: pick best score per (resort_id, date)
# ---------------------------------------------------------------------------


def deduplicate_scores(entries):
    """
    When multiple scores exist for the same (resort_id, date), pick
    the one from 'real_scored' source, otherwise the first one seen.
    """
    by_key = defaultdict(list)
    for entry in entries:
        key = (entry["resort_id"], entry["date"])
        by_key[key].append(entry)

    deduped = []
    dup_count = 0
    for key, group in by_key.items():
        if len(group) == 1:
            deduped.append(group[0])
            continue

        dup_count += 1
        # Prefer real_scored entries
        real_entries = [e for e in group if e.get("source") == "real_scored"]
        if real_entries:
            deduped.append(real_entries[0])
        else:
            # Pick the first entry
            deduped.append(group[0])

    if dup_count > 0:
        print(
            f"Deduplicated: {dup_count} resort/date combos had multiple entries, kept best"
        )
    return deduped


# ---------------------------------------------------------------------------
# Main audit pipeline
# ---------------------------------------------------------------------------


def run_audit():
    print("=" * 80)
    print("SNOW QUALITY SCORE AUDIT")
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print()

    # Load data
    features = load_features()
    all_scores = load_all_scores()

    # Deduplicate scores (prefer real_scored)
    all_scores = deduplicate_scores(all_scores)
    print(f"After dedup: {len(all_scores)} unique score entries")
    print()

    # Match features to scores
    matched = []
    unmatched = 0
    for entry in all_scores:
        key = (entry["resort_id"], entry["date"])
        if key in features:
            entry["features"] = features[key]
            matched.append(entry)
        else:
            unmatched += 1

    print(f"Matched to features: {len(matched)}")
    print(f"No matching features: {unmatched} (skipped from audit, passed through)")
    print()

    # Run physics-based audit
    results = []
    stats = {
        "total": len(matched),
        "within_tolerance": 0,  # |diff| <= 0.5
        "minor_deviation": 0,  # 0.5 < |diff| <= 1.0
        "major_deviation": 0,  # |diff| > 1.0
        "hard_violations": 0,
        "corrected": 0,
        "preserved": 0,
    }

    corrections_by_direction = Counter()  # "raised" or "lowered"
    corrections_by_magnitude = []
    flagged_examples = []

    for entry in matched:
        feat = entry["features"]
        assigned = entry["score"]

        physics_score, reasons = compute_physics_score(feat)
        hard_violations = check_hard_constraints(feat, assigned)
        new_score, correction_reason = correct_score(
            assigned, physics_score, hard_violations
        )

        diff = assigned - physics_score
        abs_diff = abs(diff)

        if abs_diff <= 0.5:
            stats["within_tolerance"] += 1
        elif abs_diff <= 1.0:
            stats["minor_deviation"] += 1
        else:
            stats["major_deviation"] += 1

        if hard_violations:
            stats["hard_violations"] += 1

        was_corrected = abs(new_score - assigned) > 0.01
        if was_corrected:
            stats["corrected"] += 1
            corrections_by_magnitude.append(new_score - assigned)
            if new_score > assigned:
                corrections_by_direction["raised"] += 1
            else:
                corrections_by_direction["lowered"] += 1
        else:
            stats["preserved"] += 1

        result = {
            "resort_id": entry["resort_id"],
            "date": entry["date"],
            "score": round(new_score, 1),
            "source": entry.get("source", ""),
            "audited": True,
        }
        if was_corrected:
            result["original_score"] = assigned
            result["physics_score"] = physics_score
            result["correction_reason"] = correction_reason

        results.append(result)

        # Collect interesting examples for the report
        if hard_violations or abs_diff > 1.5:
            flagged_examples.append(
                {
                    "resort_id": entry["resort_id"],
                    "date": entry["date"],
                    "assigned": assigned,
                    "physics": physics_score,
                    "new": new_score,
                    "diff": round(diff, 2),
                    "hard_violations": hard_violations,
                    "reasons": reasons,
                    "correction": correction_reason,
                    "features_summary": {
                        "cur_temp": feat.get("cur_temp"),
                        "snow_24h": feat.get("snowfall_24h_cm"),
                        "snow_72h": feat.get("snowfall_72h_cm"),
                        "snow_depth": feat.get("snow_depth_cm"),
                        "ft_days_ago": feat.get("freeze_thaw_days_ago"),
                        "avg_wind": feat.get("avg_wind_24h"),
                        "is_snowing": feat.get("is_snowing"),
                    },
                }
            )

    # -----------------------------------------------------------------------
    # Also include unmatched scores (pass-through with audited=True, no correction)
    # -----------------------------------------------------------------------
    unmatched_entries = []
    for entry in all_scores:
        key = (entry["resort_id"], entry["date"])
        if key not in features:
            unmatched_entries.append(
                {
                    "resort_id": entry["resort_id"],
                    "date": entry["date"],
                    "score": entry["score"],
                    "source": entry.get("source", ""),
                    "audited": True,
                    "note": "no_matching_features_passthrough",
                }
            )
    results.extend(unmatched_entries)

    # -----------------------------------------------------------------------
    # Print report
    # -----------------------------------------------------------------------
    print("=" * 80)
    print("AUDIT RESULTS")
    print("=" * 80)
    print()

    print(f"Total scored data points audited:   {stats['total']}")
    print(
        f"  Within tolerance (|diff| <= 0.5): {stats['within_tolerance']} ({stats['within_tolerance'] / max(stats['total'], 1) * 100:.1f}%)"
    )
    print(
        f"  Minor deviation  (0.5 < |d| <= 1): {stats['minor_deviation']} ({stats['minor_deviation'] / max(stats['total'], 1) * 100:.1f}%)"
    )
    print(
        f"  Major deviation  (|diff| > 1.0):  {stats['major_deviation']} ({stats['major_deviation'] / max(stats['total'], 1) * 100:.1f}%)"
    )
    print()
    print(f"Hard constraint violations:          {stats['hard_violations']}")
    print(
        f"Scores corrected:                    {stats['corrected']} ({stats['corrected'] / max(stats['total'], 1) * 100:.1f}%)"
    )
    print(
        f"Scores preserved:                    {stats['preserved']} ({stats['preserved'] / max(stats['total'], 1) * 100:.1f}%)"
    )
    print(f"Unmatched (pass-through):            {len(unmatched_entries)}")
    print()

    if corrections_by_magnitude:
        avg_correction = sum(abs(c) for c in corrections_by_magnitude) / len(
            corrections_by_magnitude
        )
        print("Correction direction:")
        print(f"  Raised:  {corrections_by_direction['raised']}")
        print(f"  Lowered: {corrections_by_direction['lowered']}")
        print(f"  Avg magnitude: {avg_correction:.2f}")
        print()

    # Score distribution before/after
    print("Score distribution (matched data, rounded to integer bucket):")
    print(f"{'Range':<12} {'Before':>8} {'After':>8} {'Change':>8}")
    print("-" * 40)
    before_bins = Counter()
    after_bins = Counter()
    matched_results = results[: len(matched)]
    for entry, result in zip(matched, matched_results):
        before_bins[int(entry["score"])] += 1
        after_bins[int(result["score"])] += 1

    for i in range(1, 7):
        b = before_bins.get(i, 0)
        a = after_bins.get(i, 0)
        change = a - b
        sign = "+" if change > 0 else ""
        print(f"  {i}.0-{i}.9    {b:>6}   {a:>6}   {sign}{change:>5}")
    print()

    # Print flagged examples
    print("=" * 80)
    print(f"FLAGGED EXAMPLES (showing up to 50 of {len(flagged_examples)} flagged)")
    print("=" * 80)

    # Sort by absolute diff descending
    flagged_examples.sort(key=lambda x: abs(x["diff"]), reverse=True)

    for i, ex in enumerate(flagged_examples[:50]):
        print(f"\n--- #{i + 1}: {ex['resort_id']} on {ex['date']} ---")
        print(
            f"  Assigned: {ex['assigned']:.1f}  |  Physics: {ex['physics']:.1f}  |  New: {ex['new']:.1f}  |  Diff: {ex['diff']:+.2f}"
        )
        fs = ex["features_summary"]
        print(
            f"  Weather: temp={fs['cur_temp']}C, snow_24h={fs['snow_24h']}cm, snow_72h={fs['snow_72h']}cm, "
            f"depth={fs['snow_depth']}cm, FT={fs['ft_days_ago']}d ago, wind={fs['avg_wind']}km/h, snowing={fs['is_snowing']}"
        )
        if ex["hard_violations"]:
            for v in ex["hard_violations"]:
                print(f"  VIOLATION: {v}")
        if ex["correction"]:
            print(f"  CORRECTION: {ex['correction']}")
        for r in ex["reasons"]:
            print(f"    - {r}")

    # -----------------------------------------------------------------------
    # Save results
    # -----------------------------------------------------------------------
    with open(OUTPUT_PATH, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved {len(results)} audited scores to {OUTPUT_PATH}")

    # Summary of score changes
    print("\n" + "=" * 80)
    print("TOP CORRECTIONS (largest magnitude changes)")
    print("=" * 80)
    corrected_list = [
        (
            r["resort_id"],
            r["date"],
            r.get("original_score", r["score"]),
            r["score"],
            r.get("physics_score", ""),
        )
        for r in matched_results
        if "original_score" in r
    ]
    corrected_list.sort(key=lambda x: abs(x[2] - x[3]), reverse=True)
    for resort, date, old, new, phys in corrected_list[:30]:
        direction = "UP" if new > old else "DOWN"
        print(
            f"  {resort:<35} {date}  {old:.1f} -> {new:.1f} ({direction} {abs(new - old):.1f})  physics={phys}"
        )

    print(
        f"\nAudit complete. {stats['corrected']} corrections applied out of {stats['total']} data points."
    )
    return stats


if __name__ == "__main__":
    run_audit()
