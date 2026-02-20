"""Generate synthetic training data for edge cases.

Creates labeled data for scenarios that are underrepresented in the real data
or where the model consistently misjudges. Each synthetic sample is clearly
labeled with source="synthetic" for auditing.

Synthetic data targets these specific weaknesses:
1. Packed powder vs icy distinction (freeze_thaw_days_ago matters!)
2. Warm temperature should degrade even fresh snow quality
3. Spring corn conditions (warm, recent FT) are skiable (POOR, not HORRIBLE)
4. Very warm + no snow = HORRIBLE (not skiable)
5. Fresh snow in cold conditions = EXCELLENT/GOOD
"""

import json
import random
from pathlib import Path

ML_DIR = Path(__file__).parent
OUTPUT_FEATURES = ML_DIR / "synthetic_features.json"
OUTPUT_SCORES = ML_DIR / "scores" / "scores_synthetic.json"

random.seed(42)


def make_sample(
    resort_id: str,
    date: str,
    cur_temp: float,
    max_temp_24h: float,
    min_temp_24h: float,
    max_temp_48h: float,
    freeze_thaw_days_ago: float,
    warmest_thaw: float,
    snow_since_freeze_cm: float,
    snowfall_24h_cm: float,
    snowfall_72h_cm: float,
    elevation_m: float,
    hours_above: dict,
    cur_hours: dict,
    score: float,
    scenario: str,
) -> tuple[dict, dict]:
    """Create a synthetic feature vector and score pair."""
    features = {
        "resort_id": resort_id,
        "date": date,
        "resort_name": f"Synthetic - {scenario}",
        "country": "XX",
        "region": "synthetic",
        "cur_temp": round(cur_temp, 1),
        "max_temp_24h": round(max_temp_24h, 1),
        "max_temp_48h": round(max_temp_48h, 1),
        "min_temp_24h": round(min_temp_24h, 1),
        "freeze_thaw_days_ago": round(freeze_thaw_days_ago, 2),
        "warmest_thaw": round(warmest_thaw, 1),
        "snow_since_freeze_cm": round(snow_since_freeze_cm, 1),
        "snowfall_24h_cm": round(snowfall_24h_cm, 1),
        "snowfall_72h_cm": round(snowfall_72h_cm, 1),
        "elevation_m": elevation_m,
    }
    for th in range(7):
        features[f"total_hours_above_{th}C_since_ft"] = hours_above.get(th, 0)
        features[f"cur_hours_above_{th}C"] = cur_hours.get(th, 0)

    score_entry = {
        "resort_id": resort_id,
        "date": date,
        "score": score,
        "source": "synthetic",
        "scenario": scenario,
    }
    return features, score_entry


def add_noise(val: float, magnitude: float = 0.1) -> float:
    """Add small random noise to a value."""
    return val + random.gauss(0, magnitude)


def generate_all():
    """Generate all synthetic scenarios."""
    all_features = []
    all_scores = []
    idx = 0

    def add(features, score_entry):
        nonlocal idx
        all_features.append(features)
        all_scores.append(score_entry)
        idx += 1

    # === PACKED POWDER: Cold, no freeze-thaw in 14+ days, no/little fresh ===
    # Key: freeze_thaw_days_ago >= 14, cold temps, no fresh snow
    # Score: 3.5-4.5 (FAIR to GOOD) - packed/groomed, not icy
    for i in range(40):
        temp = random.uniform(-15, -2)
        elev = random.uniform(1500, 3000)
        f, s = make_sample(
            resort_id=f"synth-packed-{i}",
            date=f"2026-01-{15 + i % 15:02d}",
            cur_temp=temp,
            max_temp_24h=temp + random.uniform(1, 4),
            min_temp_24h=temp - random.uniform(1, 4),
            max_temp_48h=temp + random.uniform(2, 6),
            freeze_thaw_days_ago=14.0,  # No FT in 14 days
            warmest_thaw=0.0,
            snow_since_freeze_cm=random.uniform(0, 5),
            snowfall_24h_cm=random.uniform(0, 1),
            snowfall_72h_cm=random.uniform(0, 3),
            elevation_m=elev,
            hours_above={},  # All zeros - cold
            cur_hours={},
            score=random.uniform(3.5, 4.3),  # FAIR
            scenario="packed_powder_cold",
        )
        add(f, s)

    # === ICY: Cold, RECENT freeze-thaw, no fresh snow ===
    # Key: freeze_thaw_days_ago < 5, cold, no fresh
    # Score: 1.5-2.5 (BAD) - refrozen icy surface
    for i in range(50):
        temp = random.uniform(-12, -1)
        ft_days = random.uniform(0.5, 5)
        warmest = random.uniform(2, 8)
        ha0 = int(warmest * random.uniform(3, 8))
        ha3 = int(ha0 * 0.6)
        ha6 = int(ha0 * 0.2)
        f, s = make_sample(
            resort_id=f"synth-icy-{i}",
            date=f"2026-01-{10 + i % 20:02d}",
            cur_temp=temp,
            max_temp_24h=temp + random.uniform(1, 3),
            min_temp_24h=temp - random.uniform(1, 3),
            max_temp_48h=max(temp + 3, warmest),
            freeze_thaw_days_ago=ft_days,
            warmest_thaw=warmest,
            snow_since_freeze_cm=random.uniform(0, 2),  # Little/no fresh
            snowfall_24h_cm=random.uniform(0, 0.5),
            snowfall_72h_cm=random.uniform(0, 1),
            elevation_m=random.uniform(1500, 3000),
            hours_above={
                0: ha0,
                1: int(ha0 * 0.85),
                2: int(ha0 * 0.7),
                3: ha3,
                4: int(ha3 * 0.7),
                5: int(ha6 * 1.3),
                6: ha6,
            },
            cur_hours={},  # Currently cold
            score=random.uniform(1.5, 2.4),  # BAD
            scenario="icy_recent_ft",
        )
        add(f, s)

    # === SPRING CORN: Warm, recent overnight FT, no fresh ===
    # Key: warm (1-8°C), recent FT (< 1 day), currently above 0
    # Score: 2.5-3.5 (POOR) - soft but skiable, spring conditions
    for i in range(40):
        temp = random.uniform(1, 8)
        ft_days = random.uniform(0.1, 0.8)  # Overnight freeze
        ha0 = int(temp * random.uniform(2, 5))
        ha3 = int(ha0 * 0.5)
        ca0 = int(random.uniform(2, 8))  # Currently warming
        ca3 = ca0 if temp >= 3 else 0
        f, s = make_sample(
            resort_id=f"synth-corn-{i}",
            date=f"2026-03-{1 + i % 28:02d}",
            cur_temp=temp,
            max_temp_24h=temp + random.uniform(0, 3),
            min_temp_24h=-random.uniform(1, 5),  # Freezing overnight
            max_temp_48h=temp + random.uniform(1, 5),
            freeze_thaw_days_ago=ft_days,
            warmest_thaw=temp + random.uniform(0, 3),
            snow_since_freeze_cm=random.uniform(0, 3),
            snowfall_24h_cm=0.0,
            snowfall_72h_cm=random.uniform(0, 2),
            elevation_m=random.uniform(2000, 3500),
            hours_above={
                0: ha0,
                1: int(ha0 * 0.8),
                2: int(ha0 * 0.6),
                3: ha3,
                4: int(ha3 * 0.6),
                5: int(ha3 * 0.3),
                6: 0,
            },
            cur_hours={
                0: ca0,
                1: int(ca0 * 0.8),
                2: int(ca0 * 0.6),
                3: ca3,
                4: int(ca3 * 0.5),
                5: 0,
                6: 0,
            },
            score=random.uniform(2.5, 3.4),  # POOR
            scenario="spring_corn",
        )
        add(f, s)

    # === WARM HEAVY SNOW: Above freezing with lots of fresh ===
    # Key: temp 0-4°C, lots of fresh snow (Sierra cement)
    # Score: 3.5-4.5 (FAIR to GOOD) - heavy but skiable, not EXCELLENT
    for i in range(35):
        temp = random.uniform(0, 4)
        snow24 = random.uniform(8, 25)
        snow72 = snow24 + random.uniform(0, 15)
        f, s = make_sample(
            resort_id=f"synth-wet-snow-{i}",
            date=f"2026-02-{1 + i % 28:02d}",
            cur_temp=temp,
            max_temp_24h=temp + random.uniform(0, 2),
            min_temp_24h=temp - random.uniform(1, 3),
            max_temp_48h=temp + random.uniform(1, 4),
            freeze_thaw_days_ago=random.uniform(1, 5),
            warmest_thaw=temp + random.uniform(0, 2),
            snow_since_freeze_cm=snow72 * random.uniform(0.8, 1.0),
            snowfall_24h_cm=snow24,
            snowfall_72h_cm=snow72,
            elevation_m=random.uniform(1500, 2500),
            hours_above={
                0: int(random.uniform(10, 40)),
                1: int(random.uniform(5, 25)),
                2: int(random.uniform(2, 15)),
                3: int(random.uniform(0, 10)),
                4: int(random.uniform(0, 5)),
                5: 0,
                6: 0,
            },
            cur_hours={
                0: int(random.uniform(2, 10)),
                1: int(random.uniform(1, 6)),
                2: int(random.uniform(0, 3)),
                3: int(random.uniform(0, 2)),
                4: 0,
                5: 0,
                6: 0,
            },
            score=random.uniform(3.5, 4.5),  # FAIR to GOOD
            scenario="warm_heavy_snow",
        )
        add(f, s)

    # === NOT SKIABLE: Very warm, no snow ===
    # Key: temp > 10°C, no snow, long warm spell
    # Score: 1.0-1.5 (HORRIBLE)
    for i in range(30):
        temp = random.uniform(10, 25)
        ca0 = int(random.uniform(48, 200))
        ha0 = ca0 + int(random.uniform(0, 100))
        f, s = make_sample(
            resort_id=f"synth-summer-{i}",
            date=f"2026-06-{1 + i % 28:02d}",
            cur_temp=temp,
            max_temp_24h=temp + random.uniform(0, 5),
            min_temp_24h=temp - random.uniform(3, 8),
            max_temp_48h=temp + random.uniform(2, 8),
            freeze_thaw_days_ago=random.uniform(0.1, 3),
            warmest_thaw=temp + random.uniform(0, 5),
            snow_since_freeze_cm=0.0,
            snowfall_24h_cm=0.0,
            snowfall_72h_cm=0.0,
            elevation_m=random.uniform(1000, 2500),
            hours_above={i: max(0, ha0 - i * 15) for i in range(7)},
            cur_hours={i: max(0, ca0 - i * 10) for i in range(7)},
            score=random.uniform(1.0, 1.4),  # HORRIBLE
            scenario="not_skiable_summer",
        )
        add(f, s)

    # === EXCELLENT COLD POWDER: Very cold, abundant fresh snow ===
    # Key: temp < -5°C, lots of fresh, no FT or long ago FT
    # Score: 5.5-6.0 (EXCELLENT)
    for i in range(40):
        temp = random.uniform(-20, -5)
        snow24 = random.uniform(5, 30)
        snow72 = snow24 + random.uniform(0, 20)
        f, s = make_sample(
            resort_id=f"synth-powder-{i}",
            date=f"2026-01-{1 + i % 30:02d}",
            cur_temp=temp,
            max_temp_24h=temp + random.uniform(1, 4),
            min_temp_24h=temp - random.uniform(1, 5),
            max_temp_48h=temp + random.uniform(2, 6),
            freeze_thaw_days_ago=random.uniform(7, 14),
            warmest_thaw=0.0,
            snow_since_freeze_cm=snow72 * random.uniform(0.9, 1.0),
            snowfall_24h_cm=snow24,
            snowfall_72h_cm=snow72,
            elevation_m=random.uniform(2000, 3500),
            hours_above={},  # All zeros - very cold
            cur_hours={},
            score=random.uniform(5.5, 6.0),  # EXCELLENT
            scenario="cold_fresh_powder",
        )
        add(f, s)

    # === GOOD: Moderate fresh on cold base ===
    # Key: moderately cold, decent fresh snow (3-8cm)
    # Score: 4.5-5.5 (GOOD to EXCELLENT)
    for i in range(35):
        temp = random.uniform(-10, -2)
        snow24 = random.uniform(2, 8)
        snow72 = snow24 + random.uniform(1, 10)
        ft_days = random.uniform(2, 10)
        ha0 = int(ft_days * random.uniform(0, 3))
        f, s = make_sample(
            resort_id=f"synth-good-{i}",
            date=f"2026-02-{1 + i % 28:02d}",
            cur_temp=temp,
            max_temp_24h=temp + random.uniform(2, 5),
            min_temp_24h=temp - random.uniform(1, 4),
            max_temp_48h=temp + random.uniform(3, 8),
            freeze_thaw_days_ago=ft_days,
            warmest_thaw=random.uniform(0, 3) if ft_days < 10 else 0,
            snow_since_freeze_cm=snow72 * random.uniform(0.7, 1.0),
            snowfall_24h_cm=snow24,
            snowfall_72h_cm=snow72,
            elevation_m=random.uniform(1800, 3000),
            hours_above={
                0: ha0,
                1: int(ha0 * 0.7),
                2: int(ha0 * 0.4),
                3: int(ha0 * 0.2),
                4: 0,
                5: 0,
                6: 0,
            },
            cur_hours={},  # Currently cold
            score=random.uniform(4.5, 5.4),  # GOOD
            scenario="moderate_fresh_cold",
        )
        add(f, s)

    # === THIN COVER ON ICE: Recent FT, thin fresh layer (1-3cm) ===
    # Key: recent FT, thin fresh snow covering icy base
    # Score: 2.0-3.0 (BAD to POOR)
    for i in range(30):
        temp = random.uniform(-8, 0)
        ft_days = random.uniform(0.5, 4)
        snow_af = random.uniform(0.5, 3)
        warmest = random.uniform(2, 6)
        ha0 = int(warmest * random.uniform(3, 8))
        f, s = make_sample(
            resort_id=f"synth-thin-on-ice-{i}",
            date=f"2026-02-{5 + i % 20:02d}",
            cur_temp=temp,
            max_temp_24h=temp + random.uniform(1, 3),
            min_temp_24h=temp - random.uniform(1, 4),
            max_temp_48h=max(temp + 3, warmest),
            freeze_thaw_days_ago=ft_days,
            warmest_thaw=warmest,
            snow_since_freeze_cm=snow_af,
            snowfall_24h_cm=snow_af * random.uniform(0.5, 1.0),
            snowfall_72h_cm=snow_af * random.uniform(1.0, 1.5),
            elevation_m=random.uniform(1500, 3000),
            hours_above={
                0: ha0,
                1: int(ha0 * 0.85),
                2: int(ha0 * 0.7),
                3: int(ha0 * 0.5),
                4: int(ha0 * 0.3),
                5: int(ha0 * 0.1),
                6: 0,
            },
            cur_hours={},  # Currently cold or just above 0
            score=random.uniform(2.0, 3.0),  # BAD to POOR
            scenario="thin_cover_on_ice",
        )
        add(f, s)

    # === FRESH COVERS ICE: Recent FT but thick fresh layer (8+cm) ===
    # Key: recent FT, thick fresh snow (8+cm) that covers the icy base
    # Score: 4.5-5.5 (GOOD) - fresh snow compensates for icy base
    for i in range(30):
        temp = random.uniform(-10, -1)
        ft_days = random.uniform(1, 5)
        snow24 = random.uniform(5, 15)
        snow_af = snow24 + random.uniform(0, 10)
        warmest = random.uniform(2, 6)
        ha0 = int(warmest * random.uniform(3, 6))
        f, s = make_sample(
            resort_id=f"synth-fresh-covers-ice-{i}",
            date=f"2026-02-{1 + i % 28:02d}",
            cur_temp=temp,
            max_temp_24h=temp + random.uniform(1, 3),
            min_temp_24h=temp - random.uniform(1, 5),
            max_temp_48h=max(temp + 3, warmest),
            freeze_thaw_days_ago=ft_days,
            warmest_thaw=warmest,
            snow_since_freeze_cm=snow_af,
            snowfall_24h_cm=snow24,
            snowfall_72h_cm=snow_af,
            elevation_m=random.uniform(1800, 3200),
            hours_above={
                0: ha0,
                1: int(ha0 * 0.85),
                2: int(ha0 * 0.7),
                3: int(ha0 * 0.5),
                4: int(ha0 * 0.3),
                5: int(ha0 * 0.1),
                6: 0,
            },
            cur_hours={},  # Currently cold
            score=random.uniform(4.5, 5.5),  # GOOD
            scenario="fresh_covers_ice",
        )
        add(f, s)

    # Save
    output = {
        "collected_at": "2026-02-20T00:00:00Z",
        "total_samples": len(all_features),
        "source": "synthetic",
        "features": list(all_features[0].keys()) if all_features else [],
        "data": all_features,
    }
    with open(OUTPUT_FEATURES, "w") as f:
        json.dump(output, f, indent=2)
    print(f"Saved {len(all_features)} synthetic feature vectors to {OUTPUT_FEATURES}")

    with open(OUTPUT_SCORES, "w") as f:
        json.dump(all_scores, f, indent=2)
    print(f"Saved {len(all_scores)} synthetic scores to {OUTPUT_SCORES}")

    # Print summary
    from collections import Counter

    scenarios = Counter(s["scenario"] for s in all_scores)
    for scenario, count in sorted(scenarios.items()):
        avg_score = (
            sum(s["score"] for s in all_scores if s["scenario"] == scenario) / count
        )
        print(f"  {scenario:30s}: {count:3d} samples, avg score {avg_score:.2f}")


if __name__ == "__main__":
    generate_all()
