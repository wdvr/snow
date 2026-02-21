#!/usr/bin/env python3
"""
Snow quality scorer for historical batch data.
Assigns scores from 1.0 to 6.0 based on weather conditions.
"""

import json
import os
import sys


def score_snow_quality(d: dict) -> float:
    """
    Score snow quality from 1.0 to 6.0 based on weather conditions.

    Scoring tiers:
    - 6.0 (EXCELLENT): Fresh powder, cold temps (<-5C), heavy recent snowfall (>10cm/24h), no freeze-thaw
    - 5.0-5.5 (GOOD): Nice conditions, moderate fresh snow (5-10cm), cold temps
    - 4.0-4.5 (FAIR): Packed powder, cold but no fresh snow, or moderate conditions
    - 3.0-3.5 (POOR): Hard pack, thin cover, warm temps degrading snow
    - 2.0-2.5 (BAD): Icy from freeze-thaw, very thin cover, slushy
    - 1.0-1.5 (HORRIBLE): No snow, summer temps, completely melted out
    """
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
    hours_above_0_since_ft = d["total_hours_above_0C_since_ft"]
    hours_above_5_since_ft = d["total_hours_above_5C_since_ft"]
    cur_hours_above_0 = d["cur_hours_above_0C"]
    cur_hours_above_5 = d["cur_hours_above_5C"]

    # ============================================================
    # STEP 1: Check for catastrophic conditions (HORRIBLE 1.0-1.5)
    # ============================================================

    # If cur_temp > 10C with many hours above 0 = likely not skiable
    if cur_temp > 10 and cur_hours_above_0 > 6:
        return 1.0

    # Very warm temps sustained
    if cur_temp > 10:
        return 1.5

    # ============================================================
    # STEP 2: Check for icy conditions from recent freeze-thaw
    # ============================================================

    # Recent freeze-thaw (< 5 days) with NO fresh snow = ICY
    if freeze_thaw_days_ago < 5 and snowfall_24h < 1.0 and snow_since_freeze_cm < 2.0:
        # This is the icy scenario
        base = 2.0

        # Very recent freeze-thaw is worse
        if freeze_thaw_days_ago < 1:
            base = 1.5
        elif freeze_thaw_days_ago < 2:
            base = 1.8
        elif freeze_thaw_days_ago < 3:
            base = 2.0
        else:
            base = 2.3

        # Currently above freezing makes it worse (active thaw)
        if cur_temp > 0:
            base -= 0.3

        # Some fresh snow on top helps a tiny bit
        if snow_since_freeze_cm > 0:
            base += 0.2

        # Higher elevation slightly better
        if elevation_m > 2500:
            base += 0.2

        return round(max(1.0, min(base, 2.5)), 1)

    # Recent freeze-thaw with SOME fresh snow covering it
    if freeze_thaw_days_ago < 5 and (
        snowfall_24h >= 1.0 or snow_since_freeze_cm >= 2.0
    ):
        base = 3.0

        # More fresh snow helps
        if snowfall_24h >= 5:
            base += 1.0
        elif snowfall_24h >= 2:
            base += 0.5

        # Cold temps help preserve the fresh layer
        if cur_temp < -5:
            base += 0.3
        elif cur_temp > 0:
            base -= 0.5

        if elevation_m > 2500:
            base += 0.2

        return round(max(2.0, min(base, 5.0)), 1)

    # ============================================================
    # STEP 3: Moderate freeze-thaw recovery (5-14 days ago)
    # ============================================================

    # freeze_thaw 5-14 days ago: the ice has been around a while
    # Score depends heavily on fresh snow covering it
    if freeze_thaw_days_ago < 14:
        # Base: recovering from freeze-thaw, some time has passed
        # Without fresh snow this is hardpack at best

        if snowfall_24h >= 10:
            # Heavy fresh snow on old base
            base = 5.0
            if cur_temp < -10:
                base += 0.5
            elif cur_temp < -5:
                base += 0.3
            if snowfall_72h >= 20:
                base += 0.3
        elif snowfall_24h >= 5:
            base = 4.5
            if cur_temp < -10:
                base += 0.3
            elif cur_temp < -5:
                base += 0.2
        elif snowfall_24h >= 2:
            base = 4.0
            if cur_temp < -10:
                base += 0.2
        elif snowfall_24h >= 0.5:
            base = 3.5
            if cur_temp < -10:
                base += 0.2
        elif snow_since_freeze_cm >= 20:
            # No fresh today but large accumulation since freeze
            base = 4.0
            if cur_temp < -10:
                base += 0.3
        elif snow_since_freeze_cm >= 10:
            # No fresh today but decent accumulation since freeze
            base = 3.5
            if cur_temp < -10:
                base += 0.3
        elif snow_since_freeze_cm >= 2:
            base = 3.0
            if cur_temp < -10:
                base += 0.2
        else:
            # No fresh snow, old freeze-thaw surface
            base = 2.5
            if cur_temp < -10:
                base += 0.3
            # More days since freeze = slightly more settled
            if freeze_thaw_days_ago >= 10:
                base += 0.2

        # Warm temps degrade
        if cur_temp > 0:
            base -= 0.5
        elif cur_temp > -2:
            base -= 0.2

        # Hours above 0 since freeze-thaw = more melt-refreeze cycles
        if hours_above_0_since_ft > 10:
            base -= 0.3
        elif hours_above_0_since_ft > 5:
            base -= 0.2

        if elevation_m > 2500:
            base += 0.1

        return round(max(1.5, min(base, 5.8)), 1)

    # ============================================================
    # STEP 4: No recent freeze-thaw (>= 14 days) - stable cold
    # ============================================================

    # This is the best baseline: no freeze-thaw for 2+ weeks means
    # stable cold conditions. Score depends on fresh snow amount.

    # --- Heavy fresh powder (EXCELLENT potential) ---
    if snowfall_24h >= 20:
        base = 6.0
        if cur_temp < -10:
            pass  # Perfect
        elif cur_temp < -5:
            base -= 0.1
        elif cur_temp < 0:
            base -= 0.3  # Still good but slightly heavier snow
        else:
            base -= 1.0  # Warm = heavy wet snow, drop a tier

    elif snowfall_24h >= 10:
        base = 5.5
        if cur_temp < -10:
            base += 0.3
        elif cur_temp < -5:
            base += 0.1
        elif cur_temp > 0:
            base -= 0.8  # Wet heavy snow

        # Bonus for extended snowfall
        if snowfall_72h >= 30:
            base += 0.2

    elif snowfall_24h >= 5:
        base = 5.0
        if cur_temp < -10:
            base += 0.3
        elif cur_temp < -5:
            base += 0.1
        elif cur_temp > 0:
            base -= 0.7

        if snowfall_72h >= 15:
            base += 0.2

    elif snowfall_24h >= 2:
        base = 4.5
        if cur_temp < -10:
            base += 0.2
        elif cur_temp < -5:
            base += 0.1
        elif cur_temp > 0:
            base -= 0.5

        if snowfall_72h >= 10:
            base += 0.2

    elif snowfall_24h >= 0.5:
        # Light dusting
        base = 4.0
        if cur_temp < -10:
            base += 0.2
        elif cur_temp > 0:
            base -= 0.3

        if snowfall_72h >= 5:
            base += 0.3
        elif snowfall_72h >= 2:
            base += 0.1

    elif snowfall_24h > 0:
        # Trace snowfall
        base = 3.8
        if cur_temp < -10:
            base += 0.2
        elif cur_temp > 0:
            base -= 0.3

        if snowfall_72h >= 5:
            base += 0.3
        elif snowfall_72h >= 2:
            base += 0.2

    else:
        # No fresh snow at all in the last 24h
        # Score depends on accumulated unrefrozen snow and temperature.
        # Cold temps preserve powder quality even days after snowfall.
        if snow_since_freeze_cm >= 100:
            # Very deep unrefrozen snow — exceptional base
            base = 5.0
            if cur_temp < -15:
                base += 0.3
            elif cur_temp < -10:
                base += 0.2
            elif cur_temp < -5:
                base += 0.1
        elif snow_since_freeze_cm >= 50:
            # Deep unrefrozen snow — great skiing even without fresh
            base = 4.5
            if cur_temp < -15:
                base += 0.3
            elif cur_temp < -10:
                base += 0.2
            elif cur_temp < -5:
                base += 0.1
        elif snow_since_freeze_cm >= 20:
            # Solid unrefrozen snow pack — good preserved conditions
            base = 4.0
            if cur_temp < -15:
                base += 0.3  # Very cold = powder still light
            elif cur_temp < -10:
                base += 0.2
        elif snow_since_freeze_cm >= 10:
            base = 3.8
            if cur_temp < -15:
                base += 0.2
            elif cur_temp < -10:
                base += 0.1
        elif snow_since_freeze_cm >= 5:
            base = 3.5
            if cur_temp < -15:
                base += 0.2
        elif snow_since_freeze_cm > 0:
            base = 3.3
        else:
            # Zero snow since last freeze, no fresh snow
            # But ft >= 14 means it's been stable and cold
            # This is groomed/packed powder at best
            base = 3.5
            if cur_temp < -15:
                base += 0.2
            elif cur_temp < -10:
                base += 0.1

        # Check recent 72h snow - even if 24h is 0, recent snow matters
        if snowfall_72h >= 10:
            base += 0.3
        elif snowfall_72h >= 5:
            base += 0.2
        elif snowfall_72h >= 2:
            base += 0.1

    # ============================================================
    # STEP 5: Global adjustments
    # ============================================================

    # Elevation bonus (high altitude preserves snow better)
    if elevation_m > 3000:
        base += 0.1
    elif elevation_m > 2500:
        base += 0.05

    # Warm current temp penalty (general)
    if cur_temp > 5:
        base -= 0.5

    # Hours above 0 penalty (general, for stable conditions)
    if hours_above_0_since_ft > 15:
        base -= 0.3
    elif hours_above_0_since_ft > 5:
        base -= 0.1

    # Clamp to valid range
    return round(max(1.0, min(base, 6.0)), 1)


def process_batch(batch_idx: int):
    """Process a single batch file and write scored output."""
    input_path = (
        f"/Users/wouter/dev/snow/ml/historical_batches/batch_{batch_idx:02d}.json"
    )
    output_path = f"/Users/wouter/dev/snow/ml/scores/scores_historical_{batch_idx}.json"

    with open(input_path) as f:
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

    return len(scored)


def main():
    total = 0
    for i in range(5):
        count = process_batch(i)
        print(f"Batch {i:02d}: scored {count} items")
        total += count
    print(f"\nTotal: {total} items scored")

    # Print score distribution
    all_scores = []
    for i in range(5):
        output_path = f"/Users/wouter/dev/snow/ml/scores/scores_historical_{i}.json"
        with open(output_path) as f:
            scored = json.load(f)
        all_scores.extend(s["score"] for s in scored)

    print("\nScore distribution:")
    for bucket_lo in [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0, 5.5, 6.0]:
        count = sum(1 for s in all_scores if s == bucket_lo)
        bar = "#" * count
        print(f"  {bucket_lo:.1f}: {count:3d} {bar}")

    import statistics

    print(f"\n  Mean: {statistics.mean(all_scores):.2f}")
    print(f"  Median: {statistics.median(all_scores):.2f}")
    print(f"  Min: {min(all_scores):.1f}, Max: {max(all_scores):.1f}")


if __name__ == "__main__":
    main()
