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
        ↓
Feature Engineering (24 features)
        ↓
Normalization (z-score using training stats)
        ↓
Hidden Layer (24 neurons, ReLU activation)
        ↓
Output Layer (1 neuron, sigmoid × 5 + 1)
        ↓
Score [1.0, 6.0] → Quality Level
```

## Input Features (24 total)

### Temperature (4 features)
| Feature | Description |
|---------|-------------|
| `cur_temp` | Current temperature at midday (°C) |
| `max_temp_24h` | Maximum temperature in last 24 hours |
| `min_temp_24h` | Minimum temperature in last 24 hours |
| `temp_trend_48h` | Temperature trend: max_temp_48h - max_temp_24h (warming/cooling) |

### Freeze-Thaw Cycle (3 features)
| Feature | Description |
|---------|-------------|
| `freeze_thaw_days_ago` | Days since last freeze-thaw event (capped at 14) |
| `warmest_thaw` | Peak temperature during most recent thaw (°C) |
| `thaw_intensity_recency` | Interaction: warmest_thaw / freeze_thaw_days_ago |

A freeze-thaw cycle occurs when temperature rises above 0°C for 3+ hours (thaw), then drops below -1°C for 2+ hours (hard freeze). This creates an ice layer that degrades snow quality.

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
| `hours_above_0C_ft` | Hours above 0°C since freeze-thaw |
| `hours_above_3C_ft` | Hours above 3°C since freeze-thaw (significant warming) |
| `hours_above_6C_ft` | Hours above 6°C since freeze-thaw (extreme warming) |

### Current Warm Spell (3 features)
Consecutive hours in the current warm spell (0 if currently below threshold).

| Feature | Description |
|---------|-------------|
| `cur_hours_above_0C` | Current consecutive hours above 0°C |
| `cur_hours_above_3C` | Current consecutive hours above 3°C |
| `cur_hours_above_6C` | Current consecutive hours above 6°C |

### Interaction Features (6 features)
Non-linear combinations that capture key skiing condition patterns:

| Feature | Description |
|---------|-------------|
| `fresh_powder_indicator` | snowfall_24h × max(0, -cur_temp) / 10 — High when fresh snow + cold |
| `accumulated_powder_indicator` | snow_since_freeze × max(0, -cur_temp) / 10 — High when lots of unthawed snow + cold |
| `warm_degradation` | max(0, cur_temp) × cur_hours_above_0C — High when warm for a long time |
| `severe_thaw_damage` | max(0, max_temp_24h - 3) × hours_above_3C_ft — High when severe warm damage |
| `temp_adjusted_fresh_snow` | snowfall_24h × (1.0 if cold, 0.5 if warm) — Fresh snow adjusted for preservation |
| `summer_flag` | 1.0 if cur_temp > 10 and above 0°C for 48+ hours — Summer/no-snow indicator |

## Training Data

- **Source**: Open-Meteo hourly weather data for 127 ski resorts worldwide
- **Period**: 13 days (Feb 7-20, 2026)
- **Total samples**: 1,651 (resort × day × top elevation)
- **Scoring**: Expert-labeled 1-6 scores based on domain knowledge
- **Split**: 80% train (1,320), 20% validation (331)

### Scoring Criteria Used for Labels
- snowfall_24h ≥ 20cm AND cur_temp < -3°C → 6 (EXCELLENT)
- snowfall_24h ≥ 10cm AND cur_temp < -2°C → 5-6
- cur_temp > 5°C AND warm for 24+ hours → 1 (HORRIBLE)
- Recent harsh freeze-thaw (warmest > 3°C) → subtract 1-2 from base
- High elevation + moderate cold → slight quality boost

## Performance (Validation Set)

| Metric | Value |
|--------|-------|
| MAE | 0.392 |
| RMSE | 0.522 |
| R² | 0.791 |
| Exact quality match | 67.7% |
| **Within-1 quality level** | **100.0%** |
| HORRIBLE detection | 91% (20/22) |
| EXCELLENT detection | 65% (17/26) |

The model **never misses by more than one quality level** on validation data.

## Overall Resort Quality

Per-elevation scores are aggregated with weighted averaging:
- **Top elevation**: 50% weight (most skiing terrain)
- **Mid elevation**: 35% weight
- **Base elevation**: 15% weight (often warm valley towns)

## Files

| File | Description |
|------|-------------|
| `ml/collect_data.py` | Data collection from Open-Meteo API |
| `ml/train_v2.py` | Neural network training script |
| `ml/model_weights_v2.json` | Trained model weights + normalization stats |
| `ml/training_features.json` | Raw collected feature data |
| `ml/scores/` | Expert-labeled training scores |
| `backend/src/services/snow_quality_service.py` | Production scoring code |
| `backend/src/services/openmeteo_service.py` | Feature extraction from raw weather data |

## Future Improvements

1. **More training data**: Collect across multiple seasons, different weather patterns
2. **Confidence estimation**: Output uncertainty bounds alongside quality score
3. **Wind/humidity features**: Wind creates wind crust, humidity affects snow type
4. **Snow depth integration**: When reliable depth data is available
5. **Temporal features**: Day-over-day quality change trends
6. **On-device inference**: Export to CoreML for iOS offline scoring
