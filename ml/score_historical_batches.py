#!/usr/bin/env python3
"""
Snow quality scorer for historical batch data.

Scoring scale: 1.0 to 6.0

6.0 (EXCELLENT): Fresh powder, cold temps (<-5C), heavy recent snowfall (>10cm/24h), no freeze-thaw
5.0-5.5 (GOOD): Nice conditions, moderate fresh snow (5-10cm), cold temps
4.0-4.5 (FAIR): Packed powder, cold but no fresh snow, or moderate conditions
3.0-3.5 (POOR): Hard pack, thin cover, warm temps degrading snow
2.0-2.5 (BAD): Icy from freeze-thaw, very thin cover, slushy spring conditions
1.0-1.5 (HORRIBLE): No snow, summer temps, completely melted out
"""

import json
import os


def score_snow_quality(d: dict) -> float:
    """Score a single data point based on weather conditions."""

    cur_temp = d["cur_temp"]
    max_temp_24h = d["max_temp_24h"]
    max_temp_48h = d["max_temp_48h"]
    min_temp_24h = d["min_temp_24h"]
    freeze_thaw_days_ago = d["freeze_thaw_days_ago"]
    warmest_thaw = d["warmest_thaw"]
    snow_since_freeze_cm = d["snow_since_freeze_cm"]
    snowfall_24h = d["snowfall_24h_cm"]
    snowfall_72h = d["snowfall_72h_cm"]
    elevation_m = d["elevation_m"]
    hours_above_0 = d["total_hours_above_0C_since_ft"]
    hours_above_5 = d["total_hours_above_5C_since_ft"]
    cur_hours_above_0 = d["cur_hours_above_0C"]

    # =========================================================================
    # STEP 1: Classify conditions
    # =========================================================================

    # Snowfall thresholds
    has_fresh_snow_24h = snowfall_24h >= 1.0
    has_moderate_snow_24h = snowfall_24h >= 5.0
    has_heavy_snow_24h = snowfall_24h >= 10.0
    has_very_heavy_snow_24h = snowfall_24h >= 20.0

    has_fresh_snow_72h = snowfall_72h >= 2.0
    has_moderate_snow_72h = snowfall_72h >= 10.0
    has_heavy_snow_72h = snowfall_72h >= 20.0

    # Temperature thresholds
    is_cold = cur_temp < -5.0
    is_very_cold = cur_temp < -15.0
    is_moderate_cold = cur_temp < 0.0
    is_cool = cur_temp < 3.0
    is_warm = max_temp_24h > 5.0
    is_very_warm = max_temp_24h > 10.0

    # Freeze-thaw timing
    recent_freeze_thaw = freeze_thaw_days_ago < 5.0
    very_recent_freeze_thaw = freeze_thaw_days_ago < 1.0
    no_recent_freeze_thaw = freeze_thaw_days_ago >= 14.0
    moderate_freeze_thaw_age = 5.0 <= freeze_thaw_days_ago < 14.0

    # Freeze-thaw severity: how warm did it get?
    mild_thaw = warmest_thaw <= 2.0  # barely above freezing
    moderate_thaw = 2.0 < warmest_thaw <= 4.0
    severe_thaw = warmest_thaw > 4.0

    # Thaw hours
    has_significant_thaw_hours = hours_above_0 > 20
    has_heavy_thaw_hours = hours_above_0 > 50
    has_extreme_thaw_hours = hours_above_0 > 100

    # Snow cover
    has_snow_cover = snow_since_freeze_cm > 5.0 or snowfall_72h > 2.0
    has_good_snow_base = snow_since_freeze_cm > 15.0
    has_deep_snow_base = snow_since_freeze_cm > 30.0

    # =========================================================================
    # STEP 2: Score fresh snowfall scenarios first (most impactful factor)
    # =========================================================================

    score = None

    # --- EXCELLENT: Heavy fresh powder ---
    if has_very_heavy_snow_24h and is_cold:
        score = 6.0
    elif has_very_heavy_snow_24h and is_moderate_cold:
        score = 5.7
    elif has_heavy_snow_24h and is_cold:
        score = 5.8
    elif has_heavy_snow_24h and is_moderate_cold:
        score = 5.5
    elif has_very_heavy_snow_24h and is_cool:
        score = 5.2  # heavy but warmer = wet heavy snow
    elif has_heavy_snow_24h and is_cool:
        score = 4.8

    # --- GOOD: Moderate fresh snow ---
    elif has_moderate_snow_24h and is_cold:
        score = 5.3
    elif has_moderate_snow_24h and is_moderate_cold:
        score = 5.0
    elif has_moderate_snow_24h and is_cool:
        score = 4.3  # wet snow, not great
    elif has_moderate_snow_24h:
        score = 3.8  # warm, wet, heavy

    # --- FAIR-GOOD: Small fresh snow ---
    elif has_fresh_snow_24h and is_cold:
        score = 4.5
    elif has_fresh_snow_24h and is_moderate_cold:
        score = 4.2
    elif has_fresh_snow_24h and is_cool:
        score = 3.8
    elif has_fresh_snow_24h:
        score = 3.5  # dusting on warm surface

    # =========================================================================
    # STEP 3: No fresh snow scenarios - determined by freeze-thaw and temp
    # =========================================================================

    if score is None:
        # No fresh snow in last 24h -- base quality depends on surface condition

        # --- HORRIBLE: extreme warmth, no snow ---
        if cur_temp > 10.0 and cur_hours_above_0 > 48:
            score = 1.0
        elif is_very_warm and has_extreme_thaw_hours and snow_since_freeze_cm < 5:
            score = 1.2

        # --- Very recent freeze-thaw with severe thaw = ICY ---
        elif very_recent_freeze_thaw and severe_thaw and snow_since_freeze_cm < 2:
            # Severe thaw (>4C) creates hard ice when it refreezes
            score = 1.5
        elif very_recent_freeze_thaw and severe_thaw and snow_since_freeze_cm < 5:
            score = 1.8

        # --- Very recent freeze-thaw with moderate thaw = hard pack/icy ---
        elif very_recent_freeze_thaw and moderate_thaw and snow_since_freeze_cm < 2:
            score = 2.0
        elif very_recent_freeze_thaw and moderate_thaw and snow_since_freeze_cm < 5:
            score = 2.3

        # --- Very recent freeze-thaw with mild thaw ---
        elif very_recent_freeze_thaw and mild_thaw and snow_since_freeze_cm < 2:
            # Barely thawed - hard pack but not severe ice
            score = 2.5
        elif very_recent_freeze_thaw and mild_thaw and snow_since_freeze_cm < 10:
            score = 2.8

        # --- Spring corn conditions: very recent FT, cold now, warm yesterday ---
        elif (
            very_recent_freeze_thaw
            and is_moderate_cold
            and max_temp_24h > 2.0
            and snow_since_freeze_cm >= 10
        ):
            score = 3.2

        # --- Recent FT (1-5 days), no fresh snow, severity matters ---
        elif recent_freeze_thaw and severe_thaw and snow_since_freeze_cm < 2:
            score = 2.0
        elif recent_freeze_thaw and severe_thaw and snow_since_freeze_cm < 10:
            score = 2.3
        elif recent_freeze_thaw and moderate_thaw and snow_since_freeze_cm < 2:
            score = 2.3
        elif recent_freeze_thaw and moderate_thaw and snow_since_freeze_cm < 10:
            score = 2.5
        elif recent_freeze_thaw and mild_thaw and snow_since_freeze_cm < 2:
            # Mild thaw, 1-5 days ago, very little snow = hard pack
            score = 2.8
        elif recent_freeze_thaw and mild_thaw and snow_since_freeze_cm < 10:
            score = 3.2

        # --- Recent FT with decent snow cover ---
        elif recent_freeze_thaw and snow_since_freeze_cm >= 10 and is_cold:
            score = 3.8
        elif recent_freeze_thaw and snow_since_freeze_cm >= 10:
            score = 3.5

        # --- Warm with heavy thaw hours, no fresh ---
        elif is_warm and has_heavy_thaw_hours and snow_since_freeze_cm < 10:
            score = 2.0
        elif is_warm and has_significant_thaw_hours and snow_since_freeze_cm < 10:
            score = 2.5

        # --- Moderate freeze-thaw age (5-14 days) ---
        elif (
            moderate_freeze_thaw_age
            and has_significant_thaw_hours
            and snow_since_freeze_cm < 5
        ):
            score = 2.8
        elif moderate_freeze_thaw_age and is_cold and snow_since_freeze_cm < 5:
            score = 3.3
        elif moderate_freeze_thaw_age and is_cold and has_good_snow_base:
            score = 4.0
        elif moderate_freeze_thaw_age and is_cold and snow_since_freeze_cm >= 5:
            score = 3.7
        elif moderate_freeze_thaw_age and is_moderate_cold and has_good_snow_base:
            score = 3.5
        elif moderate_freeze_thaw_age and is_moderate_cold:
            score = 3.2

        # --- No recent freeze-thaw (14+ days) = stable snowpack ---
        elif no_recent_freeze_thaw and is_cold and has_deep_snow_base:
            score = 4.2  # packed powder with deep base
        elif no_recent_freeze_thaw and is_cold and has_good_snow_base:
            score = 4.0  # packed powder
        elif no_recent_freeze_thaw and is_cold and snow_since_freeze_cm > 5:
            score = 3.8
        elif no_recent_freeze_thaw and is_cold:
            score = 3.5  # cold but thin cover
        elif no_recent_freeze_thaw and is_moderate_cold and has_deep_snow_base:
            score = 3.9
        elif no_recent_freeze_thaw and is_moderate_cold and has_good_snow_base:
            score = 3.8
        elif no_recent_freeze_thaw and is_moderate_cold and snow_since_freeze_cm > 5:
            score = 3.6
        elif no_recent_freeze_thaw and is_moderate_cold:
            score = 3.3
        elif no_recent_freeze_thaw and is_cool:
            score = 3.0
        elif no_recent_freeze_thaw:
            score = 2.5  # no FT but warm

        # --- Fallback ---
        else:
            score = 3.0

    # =========================================================================
    # STEP 4: Apply adjustments
    # =========================================================================

    # --- 72h snowfall boost when 24h is low ---
    if not has_fresh_snow_24h and has_moderate_snow_72h and is_cold and score < 4.5:
        score = max(score, 4.3)
    elif not has_fresh_snow_24h and has_fresh_snow_72h and is_cold and score < 4.0:
        score = max(score, 3.8)
    elif (
        not has_fresh_snow_24h
        and has_moderate_snow_72h
        and is_moderate_cold
        and score < 4.0
    ):
        score = max(score, 3.8)

    # --- Temperature adjustments ---
    if is_very_cold and score >= 3.5:
        score += 0.2

    # Warm temps degrade snow (reduced penalty if heavy fresh snow covers surface)
    if max_temp_24h > 5.0:
        score -= 0.1 if has_heavy_snow_24h else 0.3
    if max_temp_48h > 8.0:
        score -= 0.1 if has_heavy_snow_24h else 0.2

    # Currently warm
    if cur_temp > 3.0:
        score -= 0.1 if has_heavy_snow_24h else 0.3

    # --- Thaw hours penalty ---
    if has_significant_thaw_hours and not has_heavy_snow_24h:
        score -= 0.2
    if has_heavy_thaw_hours and not has_heavy_snow_24h:
        score -= 0.2  # cumulative with above
    if has_extreme_thaw_hours and not has_heavy_snow_24h:
        score -= 0.3  # cumulative

    # --- Freeze-thaw severity adjustments ---
    if warmest_thaw > 3.0 and freeze_thaw_days_ago < 5.0 and not has_moderate_snow_24h:
        score -= 0.2
    if warmest_thaw > 5.0 and freeze_thaw_days_ago < 3.0 and not has_heavy_snow_24h:
        score -= 0.2

    # --- Snow cover depth bonus ---
    if snow_since_freeze_cm > 30 and is_moderate_cold:
        score += 0.15
    if snow_since_freeze_cm > 50 and is_cold:
        score += 0.15

    # --- Elevation adjustments ---
    if elevation_m > 2500:
        score += 0.1
    if elevation_m > 3000:
        score += 0.1
    if elevation_m < 1800 and 2.5 < score < 4.5 and not has_fresh_snow_24h:
        score -= 0.1

    # --- Sustained heavy snowfall bonus ---
    if snowfall_72h > 40 and is_cold:
        score += 0.15
    if snowfall_72h > 60 and is_cold:
        score += 0.15

    # --- Fresh snow on recent freeze-thaw: the fresh snow helps cover ice ---
    if has_fresh_snow_24h and recent_freeze_thaw and snow_since_freeze_cm < 5:
        # Fresh dusting doesn't fully fix icy base
        score -= 0.3

    # =========================================================================
    # STEP 5: Clamp to valid range
    # =========================================================================
    score = max(1.0, min(6.0, score))

    return round(score, 1)


def process_batch(batch_num: int):
    """Process a single batch file and write scores."""
    input_path = f"/Users/wouter/dev/snow/ml/historical_batches/batch_{batch_num}.json"
    output_path = f"/Users/wouter/dev/snow/ml/scores/scores_historical_{batch_num}.json"

    with open(input_path, "r") as f:
        data = json.load(f)

    scored = []
    for item in data:
        score = score_snow_quality(item)
        scored.append(
            {
                "resort_id": item["resort_id"],
                "date": item["date"],
                "score": score,
                "source": "historical_scored",
            }
        )

    with open(output_path, "w") as f:
        json.dump(scored, f, indent=2)

    # Print distribution summary
    from collections import Counter

    ranges = Counter()
    for s in scored:
        sc = s["score"]
        if sc <= 1.5:
            ranges["1.0-1.5 HORRIBLE"] += 1
        elif sc <= 2.5:
            ranges["2.0-2.5 BAD"] += 1
        elif sc <= 3.5:
            ranges["3.0-3.5 POOR"] += 1
        elif sc <= 4.5:
            ranges["4.0-4.5 FAIR"] += 1
        elif sc <= 5.5:
            ranges["5.0-5.5 GOOD"] += 1
        else:
            ranges["5.6-6.0 EXCELLENT"] += 1

    print(f"\nbatch_{batch_num}: {len(scored)} items scored -> {output_path}")
    for k in sorted(ranges.keys()):
        print(f"  {k}: {ranges[k]}")

    return scored


if __name__ == "__main__":
    total = 0
    for batch_num in range(20, 25):
        scored = process_batch(batch_num)
        total += len(scored)
    print(f"\nTotal items scored: {total}")
