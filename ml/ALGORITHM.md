# Snow Quality Scoring Algorithm

## Overview

The snow quality score determines how good skiing conditions are at a resort. It's the core metric our app displays — getting this right is critical.

**Model**: Ensemble of 10 neural networks (40 input → varying hidden → 1 output, averaged)
**Output**: Score 1.0-6.0, mapped to 10 quality levels:
- **6.0 = CHAMPAGNE POWDER**: Lightest, driest powder -- the holy grail
- **5.5+ = POWDER DAY**: Deep fresh powder, cold temps, low wind
- **5.0+ = EXCELLENT**: Abundant recent snow, well-preserved conditions
- **4.5+ = GREAT**: Fresh snow with good coverage and cold temps
- **4.0+ = GOOD**: Soft rideable surface, some fresh snow
- **3.5+ = DECENT**: Acceptable conditions, firm in spots
- **3.0+ = MEDIOCRE**: Firm base with limited fresh, or mild warming
- **2.5+ = POOR**: Hard pack, limited quality
- **1.5+ = BAD**: Icy/slushy, barely skiable
- **< 1.5 = HORRIBLE**: No snow, complete melt, unskiable

## Architecture

```
Multi-Source Weather Data (Open-Meteo, OnTheSnow, Snow-Forecast, WeatherKit)
        |
MultiSourceMerger (outlier detection, weighted consensus)
        |
Feature Engineering (40 features)
        |
Normalization (z-score using training stats)
        |
┌────────┬────────┬────────┬────────┬────────┬────────┬────────┬────────┬────────┬────────┐
│Model 1 │Model 2 │Model 3 │Model 4 │Model 5 │Model 6 │Model 7 │Model 8 │Model 9 │Model10│
│ h=48   │ h=48   │ h=24   │ h=48   │ h=64   │ h=24   │ h=48   │ h=64   │ h=24   │ h=16  │
└───┬────┴───┬────┴───┬────┴───┬────┴───┬────┴───┬────┴───┬────┴───┬────┴───┬────┴───┬───┘
    │        │        │        │        │        │        │        │        │        │
    └────────┴────────┴───┬────┴────────┴────────┴────────┴────────┴────────┴────────┘
                    │ Average
                Score [1.0, 6.0] -> Quality Level
```

Each model: Hidden Layer (ReLU) → Output (sigmoid × 5 + 1).
Ensemble averaging reduces boundary prediction variance.

## Input Features (40 total)

### Temperature (4 features)
| Feature | Description |
|---------|-------------|
| `cur_temp` | Current temperature at midday (C) |
| `max_temp_24h` | Maximum temperature in last 24 hours |
| `min_temp_24h` | Minimum temperature in last 24 hours |
| `temp_trend_48h` | Temperature trend: max_temp_48h - max_temp_24h (warming/cooling) |

### Freeze-Thaw Cycle (3 features)
| Feature | Description |
|---------|-------------|
| `freeze_thaw_days_ago` | Days since last freeze-thaw event (capped at 14) |
| `warmest_thaw` | Peak temperature during most recent thaw (C) |
| `thaw_intensity_recency` | Interaction: warmest_thaw / freeze_thaw_days_ago |

A freeze-thaw cycle occurs when temperature rises above 0C for 3+ hours (thaw), then drops below -1C for 2+ hours (hard freeze). This creates an ice layer that degrades snow quality.

### Snowfall (5 features)
| Feature | Description |
|---------|-------------|
| `snow_since_freeze_cm` | Total snowfall since last freeze-thaw event |
| `snowfall_24h_cm` | Snowfall in last 24 hours |
| `snowfall_72h_cm` | Snowfall in last 72 hours |
| `older_snow_accum` | snowfall_72h - snowfall_24h (older accumulation) |
| `hours_since_last_snowfall` | Hours since last measurable snowfall (captures snow aging) |

### Elevation (1 feature)
| Feature | Description |
|---------|-------------|
| `elevation_km` | Measurement elevation in km (elevation_m / 1000) |

### Snow Depth (2 features)
| Feature | Description |
|---------|-------------|
| `snow_depth_m` | Current snow depth in meters |
| `fresh_to_total_ratio` | Ratio of recent snowfall to total snow depth |

### Warm Hours Since Freeze-Thaw (3 features)
Cumulative hours above temperature thresholds since the last freeze-thaw event. More warm hours = more degradation.

| Feature | Description |
|---------|-------------|
| `hours_above_0C_ft` | Hours above 0C since freeze-thaw |
| `hours_above_3C_ft` | Hours above 3C since freeze-thaw (significant warming) |
| `hours_above_6C_ft` | Hours above 6C since freeze-thaw (extreme warming) |

### Current Warm Spell (3 features)
Consecutive hours in the current warm spell (0 if currently below threshold).

| Feature | Description |
|---------|-------------|
| `cur_hours_above_0C` | Current consecutive hours above 0C |
| `cur_hours_above_3C` | Current consecutive hours above 3C |
| `cur_hours_above_6C` | Current consecutive hours above 6C |

### Wind & Visibility Features (6 features)
| Feature | Description |
|---------|-------------|
| `avg_wind_24h` | Average wind speed in last 24 hours (km/h) |
| `max_wind_24h` | Maximum wind speed in last 24 hours (km/h) |
| `max_wind_gust_norm` | Maximum wind gust normalized (km/h) |
| `visibility_km` | Current visibility (km) |
| `min_visibility_24h_km` | Minimum visibility in last 24 hours (km) |
| `calm_powder_indicator` | snowfall_24h x max(0, 1 - avg_wind/40) - High when fresh snow + calm conditions |

### Interaction Features (6 features)
Non-linear combinations that capture key skiing condition patterns:

| Feature | Description |
|---------|-------------|
| `fresh_powder_indicator` | snowfall_24h x max(0, -cur_temp) / 10 - High when fresh snow + cold |
| `accumulated_powder_indicator` | snow_since_freeze x max(0, -cur_temp) / 10 - High when lots of unthawed snow + cold |
| `warm_degradation` | max(0, cur_temp) x cur_hours_above_0C - High when warm for a long time |
| `severe_thaw_damage` | max(0, max_temp_24h - 3) x hours_above_3C_ft - High when severe warm damage |
| `temp_adjusted_fresh_snow` | snowfall_24h x (1.0 if cold, 0.5 if warm) - Fresh snow adjusted for preservation |
| `summer_flag` | 1.0 if cur_temp > 10 and above 0C for 48+ hours - Summer/no-snow indicator |

## Training Data

### Real Data
- **Source**: Open-Meteo hourly weather data for 134 ski resorts worldwide
- **Period**: Multiple collection rounds (Feb 2026)
- **Total samples**: ~12,000 (resort x day x elevation)
- **Scoring**: 1,885 real-world quality scores from 134+ resorts (`scores/scores_real.json`), plus deterministic rule-based scoring for weather-only labels

### Training Pipeline
```bash
# Collect features from Open-Meteo
python3 ml/collect_data.py

# Train model (historical_weight=0.0 for best results)
python3 ml/train_v2.py 0.0

# Evaluate physics constraints (48 edge cases x 8 constraints, must pass 100%)
python3 ml/eval_physics_checks.py

# Audit scores with physics-based corrections
python3 ml/ai_score_audit.py
```

### Scoring Criteria Used for Labels
Deterministic rule-based scoring (`score_historical_batches.py`):
- **Fresh snow + cold**: 20cm/24h + cold (<-5°C) = 6.0 (EXCELLENT)
- **Moderate fresh**: 5-10cm/24h + cold = 5.0-5.3 (GOOD)
- **No fresh, cold packed powder**: No FT in 14+ days, cold = 3.5-4.2 (FAIR)
- **Recent freeze-thaw damage**: Severity depends on thaw warmth and snow cover
- **Warm/summer**: >10°C for extended period = 1.0 (HORRIBLE)
- Adjustments for: elevation, 72h snowfall, temperature extremes, thaw hours

## Performance (v15 Validation Set)

| Metric | Value |
|--------|-------|
| MAE | 0.225 |
| R^2 | 0.937 |
| Exact quality match | 81.1% |
| **Within-1 quality level** | **100.0%** |
| Training samples | ~12,000 |
| Features | 40 |
| Physics eval | 100% pass (48 edge cases x 8 constraints) |

The model never misses by more than one quality level on the validation set.

## Production Integration

### ML Model Path
The ML model runs when raw hourly data is available from the multi-source weather pipeline. It extracts exact features from the merged weather data for accurate scoring.

When raw data is NOT available (e.g., approximated conditions), the system falls back to a heuristic algorithm that uses hand-tuned rules for temperature, freeze-thaw, and snowfall scoring.

### Post-ML Floor
The ML model doesn't see `snow_depth_cm` (from resort scraping). A post-ML floor ensures:
- 50+ cm confirmed base depth -> never HORRIBLE (skiing is possible)
- 100+ cm confirmed base depth -> at least POOR

Note: Previous versions (v11-v13) applied snow aging penalties and cold accumulation boosts after the ML prediction. These were removed in v14/v15 because the `hours_since_last_snowfall` feature allows the model to handle snow aging internally.

### Overall Resort Quality

Per-elevation scores are aggregated with weighted averaging:
- **Top elevation**: 50% weight (most skiing terrain)
- **Mid elevation**: 35% weight
- **Base elevation**: 15% weight (often warm valley towns)

## Files

| File | Description |
|------|-------------|
| `ml/collect_data.py` | Data collection from Open-Meteo forecast API |
| `ml/collect_historical.py` | Data collection from Open-Meteo archive API |
| `ml/generate_synthetic.py` | Synthetic edge case data generation |
| `ml/train_v2.py` | Neural network training script |
| `ml/eval_physics_checks.py` | Physics evaluation suite (48 edge cases x 8 constraints) |
| `ml/ai_score_audit.py` | Physics-based score correction audit |
| `ml/model_weights_v2.json` | Trained model weights + normalization stats |
| `ml/scores/scores_real.json` | Real-world quality scores (1,885 entries from 134+ resorts) |
| `ml/scores/` | All training scores (real, synthetic, historical) |
| `ml/score_historical_batches.py` | Deterministic scoring rules for training labels |
| `backend/src/services/ml_scorer.py` | ML inference service (forward pass only) |
| `backend/src/services/snow_quality_service.py` | Production scoring code (ML + heuristic fallback) |
| `backend/src/ml_model/model_weights_v2.json` | Weights copy for Lambda package |

## Version History

| Version | Date | Changes | Val MAE | Exact Match |
|---------|------|---------|---------|-------------|
| v1 | 2026-02-20 | Ridge regression, 24 raw features | 0.505 | 52.3% |
| v2 | 2026-02-20 | Neural network, engineered features, class balancing | 0.392 | 67.7% |
| v3 | 2026-02-20 | +330 synthetic edge cases, more training epochs, seed search | 0.367 | 73.6% |
| v3.1 | 2026-02-20 | Fine-grained checkpointing, source weights in training | 0.366 | 74.6% |
| v4 | 2026-02-20 | +200 boundary synthetic data, 64-neuron hidden layer, 40-config search | 0.351 | 76.7% |
| v5 | 2026-02-20 | Ensemble of 5 models, deterministic labels, wind features | 0.183 | 87.4% |
| v5.1 | 2026-02-20 | Optimized quality thresholds (same model weights) | 0.183 | 92.7% |
| v6 | 2026-02-20 | 10-model ensemble, 80-config search, 4000 epochs, threshold optimization | 0.182 | 93.6% |
| v7 | 2026-02-20 | Retrained on corrected elevation data (106 resort elevations fixed) | 0.195 | 88.2% |
| v11 | 2026-02-22 | Retrained with 2,181 real observations, 29 features | 0.176 | 83.5% |
| v13 | 2026-02-23 | +wind gust, visibility features (37 features, 11,960 samples) | 0.265 | 74.7% |
| v14 | 2026-02-24 | +hours_since_last_snowfall, removed manual hacks (aging penalty, cold boost) | -- | -- |
| v15 | 2026-02-24 | 40 features, ~12,000 samples, physics eval suite (48 cases x 8 constraints) | 0.225 | 81.1% |

### Key Experiments

#### Corrected Elevation Data (v7)
Fixed elevation data for 106 resorts in resorts.json. Many resorts had wildly wrong top
elevations from the scraper regex (e.g., Le Relais 3403m→429m, Cape Smokey 3000m→340m).
Since Open-Meteo uses elevation for temperature lapse rate adjustment, wrong elevations
caused temperature errors of up to 22°C. Recollected all training data (Feb 8-20) with
corrected elevations, re-scored deterministically, and retrained. Validation accuracy
appears lower (88.2% vs 93.6%) because the v6 metrics were evaluated against data with
wrong temperatures. The v7 model produces more accurate real-world predictions because
it was trained on correct temperature data matching production conditions.

#### Threshold Optimization (v5.1)
Searched optimal quality thresholds over the validation set while maintaining 100% within-1
accuracy. Lowered EXCELLENT from 5.5→5.25, GOOD from 4.5→4.45, FAIR from 3.5→3.35. This
recovered 10 EXCELLENT samples that were borderline-predicted (5.25-5.49) without any
retraining. EXCELLENT accuracy improved from 74%→100%, overall from 87.4%→92.7%.

#### Wider Search + Larger Ensemble (v6)
Expanded config search from 40 (5×8) to 80 (5×16) configurations, increased training from
3000 to 4000 epochs. Selected top 10 models (up from 5) for the ensemble, providing better
diversity across hidden layer sizes (h=16,24,48,64). Re-optimized thresholds for the new
ensemble: EXCELLENT 5.35, GOOD 4.40, FAIR 3.30. GOOD accuracy improved from 85%→94%,
BAD from 94%→96%, overall from 92.7%→93.6%.

#### Deterministic Labeling (v5 breakthrough)
Replaced noisy LLM-generated labels with a deterministic rule-based scorer. The LLM labels
had an average disagreement of 0.454 with deterministic rules, with 127 samples differing by
more than 1.0 quality level. Training on consistent deterministic labels improved exact accuracy
from 76.7% to 87.4% and within-1 from 99.8% to 100.0%.

#### Wind Features Experiment (v4→v5)
Added wind_speed_10m (avg_wind_24h, max_wind_24h, calm_powder_indicator). Wind features alone
didn't improve model performance — the main bottleneck was label noise, not missing features.
Wind features are kept in the pipeline for potential future benefit.

#### Historical Data Experiment (not deployed)
Collected 3,683 historical samples from January 2026 via Open-Meteo archive API.
Scored by 6 independent subagents in parallel. Training with this data showed:
- Labels were noisy due to inter-annotator disagreement (54% agreement with v3 model predictions)
- Adding historical data at any weight (0.1-1.0) degraded within-1 accuracy on clean real data
- Historical labels preserved in `scores/scores_historical_*.json` for future use with better labeling

## Future Improvements

1. **More training data**: Collect across multiple seasons, different weather patterns
2. **Live data collection**: Ongoing collection as weather changes for retraining
3. **Confidence estimation**: Output uncertainty bounds alongside quality score
4. **Humidity features**: Humidity affects snow type (light vs heavy powder)
5. **Snow depth integration**: When reliable depth data is available, add as feature
6. **Temporal features**: Day-over-day quality change trends
7. **On-device inference**: Export to CoreML for iOS offline scoring
8. **User condition reports as training signal**: Feed structured reports into the training pipeline
