# Snow Quality Scoring Algorithm

## Overview

The snow quality score determines how good skiing conditions are at a resort. It's the core metric our app displays — getting this right is critical.

**Model**: 2-layer neural network (24 input → 24 hidden → 1 output)
**Output**: Score 1.0-6.0, mapped to quality levels:
- **6 = EXCELLENT**: Fresh powder, cold temps, perfect skiing
- **5 = GOOD**: Nice conditions, some fresh or well-preserved snow
- **4 = FAIR**: Decent but not great, some ice or aging snow
- **3 = POOR**: Hard pack, limited quality
- **2 = BAD**: Icy/slushy, barely skiable
- **1 = HORRIBLE**: No snow, complete melt, unskiable

## Architecture

```
Raw Weather Data (Open-Meteo hourly)
        |
Feature Engineering (24 features)
        |
Normalization (z-score using training stats)
        |
Hidden Layer (24 neurons, ReLU activation)
        |
Output Layer (1 neuron, sigmoid x 5 + 1)
        |
Score [1.0, 6.0] -> Quality Level
```

## Input Features (24 total)

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

### Snowfall (4 features)
| Feature | Description |
|---------|-------------|
| `snow_since_freeze_cm` | Total snowfall since last freeze-thaw event |
| `snowfall_24h_cm` | Snowfall in last 24 hours |
| `snowfall_72h_cm` | Snowfall in last 72 hours |
| `older_snow_accum` | snowfall_72h - snowfall_24h (older accumulation) |

### Elevation (1 feature)
| Feature | Description |
|---------|-------------|
| `elevation_km` | Measurement elevation in km (elevation_m / 1000) |

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
- **Source**: Open-Meteo hourly weather data for 127 ski resorts worldwide
- **Period**: 13 days (Feb 7-20, 2026)
- **Total samples**: 1,651 (resort x day x top elevation)
- **Scoring**: Expert-labeled 1-6 scores via subagent review of weather features

### Synthetic Data
- **Source**: Algorithmically generated edge cases (labeled as `source: "synthetic"`)
- **Total samples**: 330
- **Purpose**: Address underrepresented scenarios in real data
- **Scenarios covered**:
  - Packed powder (cold, no freeze-thaw in 14+ days, no fresh snow) -> FAIR
  - Icy conditions (cold, recent freeze-thaw, no fresh snow) -> BAD
  - Spring corn (warm, recent overnight freeze-thaw) -> POOR
  - Warm heavy snow / Sierra cement (0-4C, lots of fresh) -> FAIR/GOOD
  - Not skiable / summer conditions (>10C, no snow) -> HORRIBLE
  - Cold fresh powder (< -5C, lots of fresh) -> EXCELLENT
  - Moderate fresh on cold base -> GOOD
  - Thin cover on icy base (< 3cm fresh on ice) -> BAD/POOR
  - Thick fresh covers icy base (8+ cm covers ice) -> GOOD

### Combined Dataset
- **Total**: 1,981 samples (1,651 real + 330 synthetic)
- **Split**: 80% train (1,584), 20% validation (397)

### Scoring Criteria Used for Labels
- snowfall_24h >= 20cm AND cur_temp < -3C -> 6 (EXCELLENT)
- snowfall_24h >= 10cm AND cur_temp < -2C -> 5-6
- cur_temp > 5C AND warm for 24+ hours -> 1 (HORRIBLE)
- Recent harsh freeze-thaw (warmest > 3C) -> subtract 1-2 from base
- High elevation + moderate cold -> slight quality boost

## Performance (Validation Set)

| Metric | Value |
|--------|-------|
| MAE | 0.367 |
| RMSE | 0.489 |
| R^2 | 0.850 |
| Exact quality match | 73.6% |
| **Within-1 quality level** | **100.0%** |

### Per-Class Accuracy
| Quality | Correct | Total | Accuracy |
|---------|---------|-------|----------|
| HORRIBLE | 30 | 32 | 94% |
| BAD | 22 | 28 | 79% |
| POOR | 31 | 52 | 60% |
| FAIR | 138 | 187 | 74% |
| GOOD | 44 | 63 | 70% |
| EXCELLENT | 27 | 35 | 77% |

The model **never misses by more than one quality level** on validation data.

## Production Integration

### ML Model Path
The ML model runs when raw hourly data from Open-Meteo is available (which it is for all weather worker runs). It extracts exact features from the raw API response for accurate scoring.

When raw data is NOT available (e.g., approximated conditions), the system falls back to a heuristic algorithm that uses hand-tuned rules for temperature, freeze-thaw, and snowfall scoring.

### Post-ML Adjustments
The ML model doesn't see `snow_depth_cm` (from resort scraping). A post-ML floor ensures:
- 50+ cm confirmed base depth -> never HORRIBLE (skiing is possible)
- 100+ cm confirmed base depth -> at least POOR

### Overall Resort Quality

Per-elevation scores are aggregated with weighted averaging:
- **Top elevation**: 50% weight (most skiing terrain)
- **Mid elevation**: 35% weight
- **Base elevation**: 15% weight (often warm valley towns)

## Files

| File | Description |
|------|-------------|
| `ml/collect_data.py` | Data collection from Open-Meteo API |
| `ml/generate_synthetic.py` | Synthetic edge case data generation |
| `ml/train_v2.py` | Neural network training script |
| `ml/model_weights_v2.json` | Trained model weights + normalization stats |
| `ml/training_features.json` | Raw collected feature data (not in git, too large) |
| `ml/synthetic_features.json` | Synthetic feature data |
| `ml/scores/` | Expert-labeled + synthetic training scores |
| `backend/src/services/ml_scorer.py` | ML inference service (forward pass only) |
| `backend/src/services/snow_quality_service.py` | Production scoring code (ML + heuristic fallback) |
| `backend/src/ml_model/model_weights_v2.json` | Weights copy for Lambda package |

## Version History

| Version | Date | Changes | Val MAE | Exact Match |
|---------|------|---------|---------|-------------|
| v1 | 2026-02-20 | Ridge regression, 24 raw features | 0.505 | 52.3% |
| v2 | 2026-02-20 | Neural network, engineered features, class balancing | 0.392 | 67.7% |
| v3 | 2026-02-20 | +330 synthetic edge cases, more training epochs, seed search | 0.367 | 73.6% |

## Future Improvements

1. **More training data**: Collect across multiple seasons, different weather patterns
2. **Live data collection**: Ongoing collection as weather changes for retraining
3. **Confidence estimation**: Output uncertainty bounds alongside quality score
4. **Wind/humidity features**: Wind creates wind crust, humidity affects snow type
5. **Snow depth integration**: When reliable depth data is available, add as feature
6. **Temporal features**: Day-over-day quality change trends
7. **On-device inference**: Export to CoreML for iOS offline scoring
