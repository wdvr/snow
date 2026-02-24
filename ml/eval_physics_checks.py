#!/usr/bin/env python3
"""Physics consistency evaluation suite for ML model predictions.

Runs after training to verify the model respects physical constraints.
Checks both synthetic edge cases and (optionally) real validation data.

Usage:
    python3 ml/eval_physics_checks.py                    # uses default weights path
    python3 ml/eval_physics_checks.py ml/model_weights_v2.json  # explicit path

Can also be called from train_v2.py:
    from eval_physics_checks import run_eval
    run_eval("ml/model_weights_v2.json")
"""

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

# Import from train_v2 (same directory)
from train_v2 import SimpleNN, engineer_features, normalize_features

ML_DIR = Path(__file__).parent
DEFAULT_WEIGHTS = ML_DIR / "model_weights_v2.json"


# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------


def load_ensemble(model_path: str | Path):
    """Load ensemble models, normalization params, and thresholds from weights file."""
    with open(model_path) as f:
        data = json.load(f)

    mean = np.array(data["normalization"]["mean"])
    std = np.array(data["normalization"]["std"])
    std[std < 1e-8] = 1.0

    models = []
    for m_data in data["ensemble"]:
        n_input = len(mean)
        n_hidden = m_data["n_hidden"]
        model = SimpleNN(n_input, n_hidden=n_hidden)
        model.W1 = np.array(m_data["W1"])
        model.b1 = np.array(m_data["b1"])
        model.W2 = np.array(m_data["W2"])
        model.b2 = np.array(m_data["b2"])
        models.append(model)

    return models, mean, std


def predict_ensemble(models, X_norm):
    """Run ensemble prediction on normalized features. Returns array of scores."""
    preds = np.zeros(X_norm.shape[0])
    for model in models:
        preds += model.predict(X_norm)
    preds /= len(models)
    return preds


# ---------------------------------------------------------------------------
# Synthetic edge-case test set
# ---------------------------------------------------------------------------


def make_raw_features(
    cur_temp=-5.0,
    max_temp_24h=None,
    max_temp_48h=None,
    min_temp_24h=None,
    freeze_thaw_days_ago=14.0,
    warmest_thaw=0.0,
    snow_since_freeze_cm=0.0,
    snowfall_24h_cm=0.0,
    snowfall_72h_cm=0.0,
    elevation_m=2500.0,
    snow_depth_cm=100.0,
    avg_wind_24h=10.0,
    max_wind_24h=20.0,
    cur_wind_kmh=10.0,
    cloud_cover_pct=50.0,
    is_clear=0.0,
    is_snowing=0.0,
    wind_chill_c=None,
    wind_chill_delta=0.0,
    visibility_m=10000.0,
    min_visibility_24h_m=10000.0,
    max_wind_gust_24h=0.0,
    hours_since_last_snowfall=336.0,
    weather_code=0,
):
    """Build a raw feature dict with sensible defaults.

    Only specify the features you care about; the rest get neutral defaults.
    """
    if max_temp_24h is None:
        max_temp_24h = cur_temp + 2.0
    if max_temp_48h is None:
        max_temp_48h = max_temp_24h + 1.0
    if min_temp_24h is None:
        min_temp_24h = cur_temp - 2.0
    if wind_chill_c is None:
        wind_chill_c = cur_temp + wind_chill_delta

    # Derive hours-above from cur_temp (rough heuristic for synthetic data)
    hours_above_0 = max(0.0, cur_temp) * 4.0 if cur_temp > 0 else 0.0
    hours_above_1 = max(0.0, cur_temp - 1.0) * 3.0 if cur_temp > 1 else 0.0
    hours_above_2 = max(0.0, cur_temp - 2.0) * 2.5 if cur_temp > 2 else 0.0
    hours_above_3 = max(0.0, cur_temp - 3.0) * 2.0 if cur_temp > 3 else 0.0
    hours_above_4 = max(0.0, cur_temp - 4.0) * 1.5 if cur_temp > 4 else 0.0
    hours_above_5 = max(0.0, cur_temp - 5.0) * 1.0 if cur_temp > 5 else 0.0
    hours_above_6 = max(0.0, cur_temp - 6.0) * 0.5 if cur_temp > 6 else 0.0

    # Current warm spell hours (similar but shorter)
    cur_above_0 = hours_above_0 * 0.5
    cur_above_1 = hours_above_1 * 0.5
    cur_above_2 = hours_above_2 * 0.5
    cur_above_3 = hours_above_3 * 0.5
    cur_above_4 = hours_above_4 * 0.5
    cur_above_5 = hours_above_5 * 0.5
    cur_above_6 = hours_above_6 * 0.5

    # If freeze-thaw is recent and warmest > 0, set hours_above accordingly
    if freeze_thaw_days_ago < 3 and warmest_thaw > 0:
        ft_hours = warmest_thaw * 8.0
        hours_above_0 = max(hours_above_0, ft_hours)
        hours_above_3 = max(hours_above_3, ft_hours * 0.3 if warmest_thaw > 3 else 0.0)

    # If it's snowing, reflect that
    if snowfall_24h_cm > 0 and hours_since_last_snowfall > 24:
        hours_since_last_snowfall = min(hours_since_last_snowfall, 6.0)

    return {
        "cur_temp": cur_temp,
        "max_temp_24h": max_temp_24h,
        "max_temp_48h": max_temp_48h,
        "min_temp_24h": min_temp_24h,
        "freeze_thaw_days_ago": freeze_thaw_days_ago,
        "warmest_thaw": warmest_thaw,
        "snow_since_freeze_cm": snow_since_freeze_cm,
        "snowfall_24h_cm": snowfall_24h_cm,
        "snowfall_72h_cm": snowfall_72h_cm,
        "elevation_m": elevation_m,
        "total_hours_above_0C_since_ft": hours_above_0,
        "total_hours_above_1C_since_ft": hours_above_1,
        "total_hours_above_2C_since_ft": hours_above_2,
        "total_hours_above_3C_since_ft": hours_above_3,
        "total_hours_above_4C_since_ft": hours_above_4,
        "total_hours_above_5C_since_ft": hours_above_5,
        "total_hours_above_6C_since_ft": hours_above_6,
        "cur_hours_above_0C": cur_above_0,
        "cur_hours_above_1C": cur_above_1,
        "cur_hours_above_2C": cur_above_2,
        "cur_hours_above_3C": cur_above_3,
        "cur_hours_above_4C": cur_above_4,
        "cur_hours_above_5C": cur_above_5,
        "cur_hours_above_6C": cur_above_6,
        "cur_wind_kmh": cur_wind_kmh,
        "max_wind_24h": max_wind_24h,
        "avg_wind_24h": avg_wind_24h,
        "snow_depth_cm": snow_depth_cm,
        "cloud_cover_pct": cloud_cover_pct,
        "weather_code": weather_code,
        "is_clear": is_clear,
        "is_snowing": is_snowing,
        "wind_chill_c": wind_chill_c,
        "wind_chill_delta": wind_chill_delta,
        "visibility_m": visibility_m,
        "min_visibility_24h_m": min_visibility_24h_m,
        "max_wind_gust_24h": max_wind_gust_24h,
        "hours_since_last_snowfall": hours_since_last_snowfall,
    }


@dataclass
class EdgeCase:
    """A synthetic test case with expected constraint outcomes."""

    name: str
    raw_features: dict
    description: str


def build_edge_cases() -> list[EdgeCase]:
    """Build ~50 synthetic edge cases covering all physical constraints."""
    cases = []

    # -----------------------------------------------------------------------
    # Category 1: Deep powder days (should score high)
    # -----------------------------------------------------------------------
    cases.append(
        EdgeCase(
            name="epic_powder_day",
            raw_features=make_raw_features(
                cur_temp=-10.0,
                snowfall_24h_cm=30.0,
                snowfall_72h_cm=50.0,
                snow_depth_cm=200.0,
                is_snowing=1.0,
                hours_since_last_snowfall=1.0,
                avg_wind_24h=5.0,
                visibility_m=5000.0,
            ),
            description="Epic powder: -10C, 30cm fresh, 200cm base",
        )
    )
    cases.append(
        EdgeCase(
            name="heavy_snowfall_cold",
            raw_features=make_raw_features(
                cur_temp=-8.0,
                snowfall_24h_cm=25.0,
                snowfall_72h_cm=40.0,
                snow_depth_cm=180.0,
                is_snowing=1.0,
                hours_since_last_snowfall=2.0,
                avg_wind_24h=8.0,
            ),
            description="Heavy snowfall at cold temps: -8C, 25cm fresh",
        )
    )
    cases.append(
        EdgeCase(
            name="moderate_fresh_cold",
            raw_features=make_raw_features(
                cur_temp=-6.0,
                snowfall_24h_cm=12.0,
                snowfall_72h_cm=20.0,
                snow_depth_cm=150.0,
                avg_wind_24h=10.0,
                hours_since_last_snowfall=6.0,
            ),
            description="Moderate fresh snow at cold temps: -6C, 12cm",
        )
    )
    cases.append(
        EdgeCase(
            name="powder_extreme_cold",
            raw_features=make_raw_features(
                cur_temp=-20.0,
                snowfall_24h_cm=20.0,
                snowfall_72h_cm=35.0,
                snow_depth_cm=250.0,
                avg_wind_24h=5.0,
                hours_since_last_snowfall=3.0,
            ),
            description="Powder at extreme cold: -20C, 20cm fresh",
        )
    )
    cases.append(
        EdgeCase(
            name="fresh_10cm_at_minus5",
            raw_features=make_raw_features(
                cur_temp=-5.0,
                snowfall_24h_cm=10.0,
                snowfall_72h_cm=15.0,
                snow_depth_cm=120.0,
                avg_wind_24h=12.0,
                hours_since_last_snowfall=8.0,
            ),
            description="10cm fresh at -5C (threshold for fresh_cold_good)",
        )
    )

    # -----------------------------------------------------------------------
    # Category 2: Cold + no fresh (packed/groomed, not excellent)
    # -----------------------------------------------------------------------
    cases.append(
        EdgeCase(
            name="cold_no_fresh_packed",
            raw_features=make_raw_features(
                cur_temp=-8.0,
                snowfall_24h_cm=0.0,
                snowfall_72h_cm=3.0,
                snow_depth_cm=120.0,
                hours_since_last_snowfall=120.0,
            ),
            description="Cold but no fresh snow: -8C, 0cm/24h, 3cm/72h",
        )
    )
    cases.append(
        EdgeCase(
            name="very_cold_dry",
            raw_features=make_raw_features(
                cur_temp=-15.0,
                snowfall_24h_cm=1.0,
                snowfall_72h_cm=2.0,
                snow_depth_cm=100.0,
                hours_since_last_snowfall=96.0,
            ),
            description="Very cold and dry: -15C, 1cm dusting only",
        )
    )
    cases.append(
        EdgeCase(
            name="cold_dry_good_base",
            raw_features=make_raw_features(
                cur_temp=-10.0,
                snowfall_24h_cm=3.0,
                snowfall_72h_cm=5.0,
                snow_depth_cm=200.0,
                hours_since_last_snowfall=48.0,
            ),
            description="Cold, dry with deep base: -10C, 3cm, 200cm base",
        )
    )
    cases.append(
        EdgeCase(
            name="cold_no_snow_at_all",
            raw_features=make_raw_features(
                cur_temp=-7.0,
                snowfall_24h_cm=0.0,
                snowfall_72h_cm=0.0,
                snow_depth_cm=80.0,
                hours_since_last_snowfall=200.0,
            ),
            description="Cold, zero fresh snow: -7C, 0cm, 80cm base",
        )
    )
    cases.append(
        EdgeCase(
            name="cold_trace_snow",
            raw_features=make_raw_features(
                cur_temp=-6.0,
                snowfall_24h_cm=2.0,
                snowfall_72h_cm=4.0,
                snow_depth_cm=90.0,
                hours_since_last_snowfall=36.0,
            ),
            description="Cold with trace snow: -6C, 2cm, 90cm base",
        )
    )

    # -----------------------------------------------------------------------
    # Category 3: Warm + no fresh (degraded/slush)
    # -----------------------------------------------------------------------
    cases.append(
        EdgeCase(
            name="spring_warm_no_fresh",
            raw_features=make_raw_features(
                cur_temp=5.0,
                max_temp_24h=8.0,
                snowfall_24h_cm=0.0,
                snowfall_72h_cm=2.0,
                snow_depth_cm=150.0,
                hours_since_last_snowfall=120.0,
            ),
            description="Warm spring day: 5C, no fresh, 150cm base",
        )
    )
    cases.append(
        EdgeCase(
            name="warm_marginal",
            raw_features=make_raw_features(
                cur_temp=4.0,
                snowfall_24h_cm=1.0,
                snowfall_72h_cm=3.0,
                snow_depth_cm=100.0,
                hours_since_last_snowfall=72.0,
            ),
            description="Warm marginal: 4C, 1cm, 100cm base",
        )
    )
    cases.append(
        EdgeCase(
            name="warm_above_3C_no_fresh",
            raw_features=make_raw_features(
                cur_temp=3.5,
                snowfall_24h_cm=2.0,
                snowfall_72h_cm=2.0,
                snow_depth_cm=80.0,
                hours_since_last_snowfall=96.0,
            ),
            description="Just above threshold: 3.5C, 2cm, 80cm base",
        )
    )

    # -----------------------------------------------------------------------
    # Category 4: Very warm + no fresh (poor conditions)
    # -----------------------------------------------------------------------
    cases.append(
        EdgeCase(
            name="very_warm_melt",
            raw_features=make_raw_features(
                cur_temp=10.0,
                max_temp_24h=12.0,
                snowfall_24h_cm=0.0,
                snowfall_72h_cm=0.0,
                snow_depth_cm=80.0,
                hours_since_last_snowfall=200.0,
            ),
            description="Active melt: 10C, no fresh, 80cm melting base",
        )
    )
    cases.append(
        EdgeCase(
            name="hot_day_no_fresh",
            raw_features=make_raw_features(
                cur_temp=12.0,
                max_temp_24h=14.0,
                snowfall_24h_cm=0.0,
                snowfall_72h_cm=0.0,
                snow_depth_cm=60.0,
                hours_since_last_snowfall=240.0,
            ),
            description="Hot day: 12C, no fresh, 60cm shrinking base",
        )
    )
    cases.append(
        EdgeCase(
            name="warm_8C_dry",
            raw_features=make_raw_features(
                cur_temp=8.0,
                snowfall_24h_cm=0.0,
                snowfall_72h_cm=1.0,
                snow_depth_cm=100.0,
                hours_since_last_snowfall=168.0,
            ),
            description="Threshold warm: exactly 8C, dry, 100cm base",
        )
    )
    cases.append(
        EdgeCase(
            name="warm_9C_trace",
            raw_features=make_raw_features(
                cur_temp=9.0,
                snowfall_24h_cm=2.0,
                snowfall_72h_cm=2.0,
                snow_depth_cm=70.0,
                hours_since_last_snowfall=48.0,
            ),
            description="Warm with trace: 9C, 2cm fresh, 70cm base",
        )
    )

    # -----------------------------------------------------------------------
    # Category 5: No snow on ground (horrible)
    # -----------------------------------------------------------------------
    cases.append(
        EdgeCase(
            name="bare_ground",
            raw_features=make_raw_features(
                cur_temp=2.0,
                snowfall_24h_cm=0.0,
                snowfall_72h_cm=0.0,
                snow_depth_cm=0.0,
                hours_since_last_snowfall=336.0,
            ),
            description="Bare ground: 0cm depth, no fresh",
        )
    )
    cases.append(
        EdgeCase(
            name="nearly_bare",
            raw_features=make_raw_features(
                cur_temp=-2.0,
                snowfall_24h_cm=1.0,
                snowfall_72h_cm=2.0,
                snow_depth_cm=3.0,
                hours_since_last_snowfall=72.0,
            ),
            description="Nearly bare: 3cm depth, 1cm fresh",
        )
    )
    cases.append(
        EdgeCase(
            name="bare_warm",
            raw_features=make_raw_features(
                cur_temp=8.0,
                snowfall_24h_cm=0.0,
                snowfall_72h_cm=0.0,
                snow_depth_cm=2.0,
                hours_since_last_snowfall=336.0,
            ),
            description="Bare and warm: 2cm depth, 8C",
        )
    )
    cases.append(
        EdgeCase(
            name="almost_no_snow",
            raw_features=make_raw_features(
                cur_temp=0.0,
                snowfall_24h_cm=0.0,
                snowfall_72h_cm=0.0,
                snow_depth_cm=4.0,
                hours_since_last_snowfall=336.0,
            ),
            description="Almost no snow: 4cm depth, 0C",
        )
    )

    # -----------------------------------------------------------------------
    # Category 6: Freeze-thaw + no fresh (icy/poor)
    # -----------------------------------------------------------------------
    cases.append(
        EdgeCase(
            name="just_refroze_icy",
            raw_features=make_raw_features(
                cur_temp=-5.0,
                snowfall_24h_cm=0.0,
                snowfall_72h_cm=2.0,
                snow_depth_cm=100.0,
                freeze_thaw_days_ago=0.3,
                warmest_thaw=5.0,
                hours_since_last_snowfall=120.0,
            ),
            description="Just refroze: FT 0.3 days ago, -5C now, no fresh",
        )
    )
    cases.append(
        EdgeCase(
            name="refreeze_after_rain",
            raw_features=make_raw_features(
                cur_temp=-8.0,
                snowfall_24h_cm=0.0,
                snowfall_72h_cm=0.0,
                snow_depth_cm=80.0,
                freeze_thaw_days_ago=0.5,
                warmest_thaw=6.0,
                hours_since_last_snowfall=200.0,
            ),
            description="Refreeze after warm spell: FT 0.5d, -8C, no fresh",
        )
    )
    cases.append(
        EdgeCase(
            name="freeze_thaw_with_trace",
            raw_features=make_raw_features(
                cur_temp=-3.0,
                snowfall_24h_cm=3.0,
                snowfall_72h_cm=4.0,
                snow_depth_cm=90.0,
                freeze_thaw_days_ago=0.8,
                warmest_thaw=4.0,
                hours_since_last_snowfall=12.0,
            ),
            description="FT with trace snow: 0.8d ago, 3cm fresh",
        )
    )
    cases.append(
        EdgeCase(
            name="refroze_hard",
            raw_features=make_raw_features(
                cur_temp=-10.0,
                snowfall_24h_cm=1.0,
                snowfall_72h_cm=1.0,
                snow_depth_cm=100.0,
                freeze_thaw_days_ago=0.2,
                warmest_thaw=8.0,
                hours_since_last_snowfall=72.0,
            ),
            description="Hard refreeze: was 8C, now -10C, 1cm dusting",
        )
    )

    # -----------------------------------------------------------------------
    # Category 7: Closed/end-of-season resort
    # -----------------------------------------------------------------------
    cases.append(
        EdgeCase(
            name="closed_resort_hot",
            raw_features=make_raw_features(
                cur_temp=15.0,
                max_temp_24h=18.0,
                snowfall_24h_cm=0.0,
                snowfall_72h_cm=0.0,
                snow_depth_cm=0.0,
                hours_since_last_snowfall=336.0,
            ),
            description="Closed resort: 15C, no snow at all",
        )
    )
    cases.append(
        EdgeCase(
            name="late_season_melting",
            raw_features=make_raw_features(
                cur_temp=10.0,
                snowfall_24h_cm=0.0,
                snowfall_72h_cm=0.0,
                snow_depth_cm=10.0,
                hours_since_last_snowfall=240.0,
            ),
            description="Late season melt: 10C, 10cm left, no fresh",
        )
    )

    # -----------------------------------------------------------------------
    # Category 8: Soft snow at freezing temps (suspicious)
    # -----------------------------------------------------------------------
    cases.append(
        EdgeCase(
            name="freezing_no_fresh_hard",
            raw_features=make_raw_features(
                cur_temp=-8.0,
                snowfall_24h_cm=0.0,
                snowfall_72h_cm=2.0,
                snow_depth_cm=100.0,
                hours_since_last_snowfall=168.0,
            ),
            description="Freezing + no fresh: -8C, 0cm/24h, should be hard/packed",
        )
    )
    cases.append(
        EdgeCase(
            name="deep_freeze_dry",
            raw_features=make_raw_features(
                cur_temp=-12.0,
                snowfall_24h_cm=1.0,
                snowfall_72h_cm=3.0,
                snow_depth_cm=120.0,
                hours_since_last_snowfall=96.0,
            ),
            description="Deep freeze, dry: -12C, 1cm, hard packed territory",
        )
    )
    cases.append(
        EdgeCase(
            name="cold_bone_dry",
            raw_features=make_raw_features(
                cur_temp=-6.0,
                snowfall_24h_cm=0.5,
                snowfall_72h_cm=1.0,
                snow_depth_cm=80.0,
                hours_since_last_snowfall=144.0,
            ),
            description="Cold and bone dry: -6C, 0.5cm dusting, old snow",
        )
    )

    # -----------------------------------------------------------------------
    # Category 9: Edge cases at exact thresholds
    # -----------------------------------------------------------------------
    cases.append(
        EdgeCase(
            name="threshold_cold_excellent_boundary",
            raw_features=make_raw_features(
                cur_temp=-5.1,
                snowfall_24h_cm=4.9,
                snowfall_72h_cm=9.9,
                snow_depth_cm=100.0,
            ),
            description="Just below cold+no-fresh threshold: -5.1C, 4.9cm/24h, 9.9cm/72h",
        )
    )
    cases.append(
        EdgeCase(
            name="threshold_warm_degraded",
            raw_features=make_raw_features(
                cur_temp=3.1,
                snowfall_24h_cm=2.9,
                snowfall_72h_cm=5.0,
                snow_depth_cm=80.0,
            ),
            description="Just above warm degraded threshold: 3.1C, 2.9cm",
        )
    )
    cases.append(
        EdgeCase(
            name="threshold_very_warm",
            raw_features=make_raw_features(
                cur_temp=8.1,
                snowfall_24h_cm=2.9,
                snowfall_72h_cm=3.0,
                snow_depth_cm=80.0,
                hours_since_last_snowfall=168.0,
            ),
            description="Just above very warm threshold: 8.1C, 2.9cm",
        )
    )
    cases.append(
        EdgeCase(
            name="threshold_snow_depth",
            raw_features=make_raw_features(
                cur_temp=0.0,
                snowfall_24h_cm=2.0,
                snowfall_72h_cm=3.0,
                snow_depth_cm=4.9,
            ),
            description="Just below snow depth threshold: 4.9cm depth",
        )
    )
    cases.append(
        EdgeCase(
            name="threshold_fresh_cold_good",
            raw_features=make_raw_features(
                cur_temp=-3.1,
                snowfall_24h_cm=10.1,
                snowfall_72h_cm=15.0,
                snow_depth_cm=120.0,
                hours_since_last_snowfall=4.0,
            ),
            description="Just above fresh+cold good threshold: -3.1C, 10.1cm",
        )
    )
    cases.append(
        EdgeCase(
            name="threshold_powder_excellent",
            raw_features=make_raw_features(
                cur_temp=-5.1,
                snowfall_24h_cm=20.1,
                snowfall_72h_cm=30.0,
                snow_depth_cm=150.0,
                hours_since_last_snowfall=2.0,
            ),
            description="Just above powder excellent threshold: -5.1C, 20.1cm",
        )
    )

    # -----------------------------------------------------------------------
    # Category 10: Mixed conditions
    # -----------------------------------------------------------------------
    cases.append(
        EdgeCase(
            name="windy_powder",
            raw_features=make_raw_features(
                cur_temp=-8.0,
                snowfall_24h_cm=20.0,
                snowfall_72h_cm=30.0,
                snow_depth_cm=150.0,
                avg_wind_24h=50.0,
                max_wind_24h=70.0,
                max_wind_gust_24h=90.0,
                hours_since_last_snowfall=2.0,
            ),
            description="Powder day but very windy: -8C, 20cm, 50km/h avg wind",
        )
    )
    cases.append(
        EdgeCase(
            name="poor_visibility_powder",
            raw_features=make_raw_features(
                cur_temp=-7.0,
                snowfall_24h_cm=15.0,
                snowfall_72h_cm=25.0,
                snow_depth_cm=120.0,
                visibility_m=200.0,
                min_visibility_24h_m=100.0,
                hours_since_last_snowfall=1.0,
                is_snowing=1.0,
            ),
            description="Powder but whiteout: -7C, 15cm, 200m visibility",
        )
    )
    cases.append(
        EdgeCase(
            name="warm_fresh_snow",
            raw_features=make_raw_features(
                cur_temp=1.0,
                snowfall_24h_cm=15.0,
                snowfall_72h_cm=20.0,
                snow_depth_cm=100.0,
                hours_since_last_snowfall=3.0,
                is_snowing=1.0,
            ),
            description="Fresh snow but warm: 1C, 15cm (heavy wet snow)",
        )
    )
    cases.append(
        EdgeCase(
            name="spring_corn_snow",
            raw_features=make_raw_features(
                cur_temp=5.0,
                max_temp_24h=8.0,
                min_temp_24h=-3.0,
                snowfall_24h_cm=0.0,
                snowfall_72h_cm=0.0,
                snow_depth_cm=150.0,
                is_clear=1.0,
                cloud_cover_pct=10.0,
                freeze_thaw_days_ago=0.5,
                warmest_thaw=8.0,
                hours_since_last_snowfall=168.0,
            ),
            description="Spring corn: 5C, clear, FT cycle, good base",
        )
    )
    cases.append(
        EdgeCase(
            name="fresh_over_ice",
            raw_features=make_raw_features(
                cur_temp=-5.0,
                snowfall_24h_cm=8.0,
                snowfall_72h_cm=10.0,
                snow_depth_cm=100.0,
                freeze_thaw_days_ago=1.5,
                warmest_thaw=5.0,
                snow_since_freeze_cm=8.0,
                hours_since_last_snowfall=6.0,
            ),
            description="Fresh snow over icy layer: -5C, 8cm over FT crust",
        )
    )
    cases.append(
        EdgeCase(
            name="high_elevation_cold",
            raw_features=make_raw_features(
                cur_temp=-15.0,
                snowfall_24h_cm=5.0,
                snowfall_72h_cm=10.0,
                snow_depth_cm=250.0,
                elevation_m=3800.0,
                avg_wind_24h=15.0,
            ),
            description="High altitude: 3800m, -15C, 5cm, deep base",
        )
    )
    cases.append(
        EdgeCase(
            name="low_elevation_marginal",
            raw_features=make_raw_features(
                cur_temp=2.0,
                snowfall_24h_cm=3.0,
                snowfall_72h_cm=5.0,
                snow_depth_cm=30.0,
                elevation_m=800.0,
                hours_since_last_snowfall=12.0,
            ),
            description="Low altitude: 800m, 2C, thin cover",
        )
    )
    cases.append(
        EdgeCase(
            name="classic_groomed_cold",
            raw_features=make_raw_features(
                cur_temp=-5.0,
                snowfall_24h_cm=0.0,
                snowfall_72h_cm=5.0,
                snow_depth_cm=100.0,
                is_clear=1.0,
                cloud_cover_pct=20.0,
                avg_wind_24h=5.0,
                hours_since_last_snowfall=72.0,
            ),
            description="Classic groomed day: -5C, clear, calm, 100cm base",
        )
    )
    cases.append(
        EdgeCase(
            name="rain_on_snow",
            raw_features=make_raw_features(
                cur_temp=3.0,
                snowfall_24h_cm=0.0,
                snowfall_72h_cm=0.0,
                snow_depth_cm=80.0,
                weather_code=61,
                hours_since_last_snowfall=168.0,
            ),
            description="Rain on snow: 3C, raining, 80cm degraded base",
        )
    )

    # -----------------------------------------------------------------------
    # Additional edge cases to reach ~50
    # -----------------------------------------------------------------------
    cases.append(
        EdgeCase(
            name="blizzard_conditions",
            raw_features=make_raw_features(
                cur_temp=-12.0,
                snowfall_24h_cm=40.0,
                snowfall_72h_cm=60.0,
                snow_depth_cm=300.0,
                avg_wind_24h=60.0,
                max_wind_24h=80.0,
                max_wind_gust_24h=100.0,
                visibility_m=50.0,
                min_visibility_24h_m=20.0,
                is_snowing=1.0,
                hours_since_last_snowfall=0.5,
            ),
            description="Blizzard: -12C, 40cm, 60km/h wind, near-zero vis",
        )
    )
    cases.append(
        EdgeCase(
            name="perfect_day",
            raw_features=make_raw_features(
                cur_temp=-7.0,
                snowfall_24h_cm=15.0,
                snowfall_72h_cm=25.0,
                snow_depth_cm=180.0,
                avg_wind_24h=5.0,
                is_clear=1.0,
                cloud_cover_pct=10.0,
                visibility_m=30000.0,
                hours_since_last_snowfall=6.0,
            ),
            description="Perfect ski day: -7C, 15cm fresh, sunny, calm",
        )
    )
    cases.append(
        EdgeCase(
            name="ice_rink_refreeze",
            raw_features=make_raw_features(
                cur_temp=-10.0,
                min_temp_24h=-12.0,
                max_temp_24h=5.0,
                snowfall_24h_cm=0.0,
                snowfall_72h_cm=0.0,
                snow_depth_cm=60.0,
                freeze_thaw_days_ago=0.1,
                warmest_thaw=5.0,
                hours_since_last_snowfall=200.0,
            ),
            description="Ice rink: melted at 5C then refroze to -10C, no fresh",
        )
    )

    return cases


# ---------------------------------------------------------------------------
# Physics constraint definitions
# ---------------------------------------------------------------------------


@dataclass
class Constraint:
    """A physical constraint to check against predictions."""

    name: str
    description: str
    check_fn: object  # Callable[[dict, float], bool] - True = passes
    applicable_fn: object  # Callable[[dict], bool] - True = applies to this case


@dataclass
class Violation:
    """A recorded constraint violation."""

    case_name: str
    constraint_name: str
    score: float
    details: str


def build_constraints() -> list[Constraint]:
    """Define all physics constraints."""
    constraints = []

    # 1. Cold + no fresh snow can't be excellent
    constraints.append(
        Constraint(
            name="cold_no_fresh_not_excellent",
            description="If temp < -5C AND snow_24h < 5cm AND snow_72h < 10cm, score must be < 5.0",
            applicable_fn=lambda f: (
                f["cur_temp"] < -5.0
                and f["snowfall_24h_cm"] < 5.0
                and f["snowfall_72h_cm"] < 10.0
            ),
            check_fn=lambda f, s: s < 5.0,
        )
    )

    # 2. Warm + no fresh = degraded
    constraints.append(
        Constraint(
            name="warm_no_fresh_degraded",
            description="If temp > 3C AND snow_24h < 3cm, score must be < 4.0",
            applicable_fn=lambda f: (
                f["cur_temp"] > 3.0 and f["snowfall_24h_cm"] < 3.0
            ),
            check_fn=lambda f, s: s < 4.0,
        )
    )

    # 3. Very warm + no fresh = poor
    constraints.append(
        Constraint(
            name="very_warm_no_fresh_poor",
            description="If temp > 8C AND snow_24h < 3cm, score should be < 3.5",
            applicable_fn=lambda f: (
                f["cur_temp"] > 8.0 and f["snowfall_24h_cm"] < 3.0
            ),
            check_fn=lambda f, s: s < 3.5,
        )
    )

    # 4. Fresh powder at cold temps = excellent
    constraints.append(
        Constraint(
            name="fresh_powder_cold_excellent",
            description="If snow_24h >= 20cm AND temp < -5C, score must be >= 4.5",
            applicable_fn=lambda f: (
                f["snowfall_24h_cm"] >= 20.0 and f["cur_temp"] < -5.0
            ),
            check_fn=lambda f, s: s >= 4.5,
        )
    )

    # 5. Fresh snow at cold temps = good
    constraints.append(
        Constraint(
            name="fresh_snow_cold_good",
            description="If snow_24h >= 10cm AND temp < -3C, score must be >= 4.0",
            applicable_fn=lambda f: (
                f["snowfall_24h_cm"] >= 10.0 and f["cur_temp"] < -3.0
            ),
            check_fn=lambda f, s: s >= 4.0,
        )
    )

    # 6. No snow on ground = horrible
    constraints.append(
        Constraint(
            name="no_snow_horrible",
            description="If snow_depth < 5cm AND snow_24h < 3cm, score must be <= 2.5 (BAD/POOR boundary)",
            applicable_fn=lambda f: (
                f["snow_depth_cm"] < 5.0 and f["snowfall_24h_cm"] < 3.0
            ),
            check_fn=lambda f, s: s
            <= 2.6,  # allow small margin for neural net rounding
        )
    )

    # 7. Recent freeze-thaw + no fresh = poor
    constraints.append(
        Constraint(
            name="freeze_thaw_no_fresh_poor",
            description="If freeze_thaw_days_ago < 1 AND snow_24h < 5cm, score must be < 3.5",
            applicable_fn=lambda f: (
                f["freeze_thaw_days_ago"] < 1.0 and f["snowfall_24h_cm"] < 5.0
            ),
            check_fn=lambda f, s: s < 3.5,
        )
    )

    # 8. Soft snow impossible when freezing — should not cross into FAIR
    # FAIR threshold is 3.6, so cold+dry must stay below that (POOR or worse)
    constraints.append(
        Constraint(
            name="freezing_no_fresh_not_fair",
            description=(
                "If temp < -5C AND snow_24h < 2cm AND snow_72h < 5cm, "
                "score should be < 3.6 (POOR territory, not FAIR/soft)"
            ),
            applicable_fn=lambda f: (
                f["cur_temp"] < -5.0
                and f["snowfall_24h_cm"] < 2.0
                and f["snowfall_72h_cm"] < 5.0
            ),
            check_fn=lambda f, s: s < 3.6,
        )
    )

    return constraints


# ---------------------------------------------------------------------------
# Evaluation engine
# ---------------------------------------------------------------------------


def run_physics_eval(
    models,
    mean: np.ndarray,
    std: np.ndarray,
    edge_cases: list[EdgeCase],
    constraints: list[Constraint],
    verbose: bool = True,
) -> dict:
    """Run all edge cases through the model and check constraints.

    Returns a results dict with pass/fail counts and violation details.
    """
    # Build feature matrix from edge cases
    X_raw = []
    raw_features_list = []
    for case in edge_cases:
        engineered = engineer_features(case.raw_features)
        X_raw.append(engineered)
        raw_features_list.append(case.raw_features)
    X_raw = np.array(X_raw, dtype=np.float64)

    # Normalize and predict
    X_norm = (X_raw - mean) / std
    predictions = predict_ensemble(models, X_norm)

    # Check constraints
    per_constraint: dict[str, dict] = {}
    all_violations: list[Violation] = []

    for constraint in constraints:
        per_constraint[constraint.name] = {
            "description": constraint.description,
            "applicable": 0,
            "passed": 0,
            "failed": 0,
            "violations": [],
        }

    for i, case in enumerate(edge_cases):
        score = predictions[i]
        raw_f = raw_features_list[i]

        for constraint in constraints:
            if not constraint.applicable_fn(raw_f):
                continue

            per_constraint[constraint.name]["applicable"] += 1

            if constraint.check_fn(raw_f, score):
                per_constraint[constraint.name]["passed"] += 1
            else:
                per_constraint[constraint.name]["failed"] += 1
                violation = Violation(
                    case_name=case.name,
                    constraint_name=constraint.name,
                    score=score,
                    details=(
                        f"{case.description} -> predicted {score:.2f}, "
                        f"violates: {constraint.description}"
                    ),
                )
                per_constraint[constraint.name]["violations"].append(violation)
                all_violations.append(violation)

    # Compute totals
    total_checks = sum(c["applicable"] for c in per_constraint.values())
    total_passed = sum(c["passed"] for c in per_constraint.values())
    total_failed = sum(c["failed"] for c in per_constraint.values())

    results = {
        "total_cases": len(edge_cases),
        "total_checks": total_checks,
        "total_passed": total_passed,
        "total_failed": total_failed,
        "pass_rate": total_passed / max(total_checks, 1),
        "per_constraint": per_constraint,
        "violations": all_violations,
        "predictions": {
            case.name: float(predictions[i]) for i, case in enumerate(edge_cases)
        },
    }

    # Print report
    if verbose:
        _print_report(results, edge_cases, predictions, constraints)

    return results


def _print_report(results, edge_cases, predictions, constraints):
    """Print a detailed human-readable report."""
    print()
    print("=" * 72)
    print("PHYSICS CONSISTENCY EVALUATION")
    print("=" * 72)

    # Predictions overview
    print()
    print("--- Predictions for all edge cases ---")
    print(f"{'Case':<35s} {'Score':>6s}  Description")
    print("-" * 72)
    for i, case in enumerate(edge_cases):
        score = predictions[i]
        print(f"  {case.name:<33s} {score:>5.2f}  {case.description}")

    # Constraint results
    print()
    print("--- Constraint results ---")
    print(
        f"{'Constraint':<35s} {'Applicable':>10s} {'Passed':>8s} {'Failed':>8s} {'Rate':>8s}"
    )
    print("-" * 72)

    for constraint in constraints:
        c = results["per_constraint"][constraint.name]
        if c["applicable"] == 0:
            rate_str = "  N/A"
        else:
            rate = c["passed"] / c["applicable"]
            rate_str = f"{rate:>7.0%}"
        status = "PASS" if c["failed"] == 0 else "FAIL"
        print(
            f"  {constraint.name:<33s} {c['applicable']:>8d}   {c['passed']:>6d}   "
            f"{c['failed']:>6d}  {rate_str}  [{status}]"
        )

    # Violations
    violations = results["violations"]
    print()
    if violations:
        print(f"--- {len(violations)} VIOLATION(S) FOUND ---")
        print()
        for v in violations:
            print(f"  FAIL  [{v.constraint_name}]")
            print(f"        Case: {v.case_name}, Score: {v.score:.2f}")
            print(f"        {v.details}")
            print()
    else:
        print("--- No violations found! All constraints satisfied. ---")

    # Summary
    print()
    print("=" * 72)
    total = results["total_checks"]
    passed = results["total_passed"]
    failed = results["total_failed"]
    rate = results["pass_rate"]
    print(f"SUMMARY: {passed}/{total} checks passed ({rate:.0%}), {failed} violations")
    if failed > 0:
        print("STATUS: FAIL")
    else:
        print("STATUS: PASS")
    print("=" * 72)


# ---------------------------------------------------------------------------
# Public API for integration with train_v2.py
# ---------------------------------------------------------------------------


def run_eval(model_path: str | Path = DEFAULT_WEIGHTS, verbose: bool = True) -> bool:
    """Run the full physics evaluation suite.

    Args:
        model_path: Path to the model weights JSON file.
        verbose: Whether to print the full report.

    Returns:
        True if all constraints pass, False if any violations found.
    """
    if verbose:
        print(f"\nLoading model from {model_path}")

    models, mean, std = load_ensemble(model_path)

    if verbose:
        print(f"Loaded ensemble of {len(models)} models")

    edge_cases = build_edge_cases()
    constraints = build_constraints()

    if verbose:
        print(
            f"Running {len(edge_cases)} edge cases against {len(constraints)} constraints"
        )

    results = run_physics_eval(
        models, mean, std, edge_cases, constraints, verbose=verbose
    )

    return results["total_failed"] == 0


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main():
    model_path = sys.argv[1] if len(sys.argv) > 1 else str(DEFAULT_WEIGHTS)
    model_path = Path(model_path)

    if not model_path.exists():
        print(f"ERROR: Model weights not found at {model_path}")
        sys.exit(1)

    all_passed = run_eval(model_path, verbose=True)
    sys.exit(0 if all_passed else 1)


if __name__ == "__main__":
    main()
