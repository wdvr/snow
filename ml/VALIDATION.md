# ML Score Validation Log

Tracks validation runs comparing our API scores against external sources and model retraining results.

---

## Validation Run: 2026-03-01

### Current Model: v15 (Feb 24 2026)
- Neural network ensemble (10 models), 40 features
- Recent pipeline changes: OnTheSnow + Snow-Forecast data sources, merged snowfall in scorer

### Pre-Retrain: Our Scores vs External Sources

| Resort | Our Quality | Score | External Quality | Match? | Key Discrepancy |
|--------|------------|-------|-----------------|--------|-----------------|
| whistler-blackcomb | good | 65 | good | YES | Aligned — 229cm base, 93% open, no fresh |
| mammoth-mountain | bad | 7 | decent | NO | 310cm upper base, 100% open — bad(7) way too low |
| palisades-tahoe | bad | 13 | decent | NO | 173cm summit, 28 lifts — bad(13) too low |
| big-white | good | 66 | good | YES | Aligned — 160cm, 97% open, cold temps |
| vail | poor | 27 | decent | NO | 119cm base, 80% open, groomed — poor too low |
| park-city | bad | 10 | decent | NO | 150cm base, 95% lifts, groomed — bad(10) too low |
| jackson-hole | great | 75 | decent | NO | 0cm fresh (not 3cm), old snow, warm — great too high |
| breckenridge | bad | 15 | decent | NO | 100% lifts, 10in/48h, very cold — bad(15) too low |
| steamboat | poor | 20 | decent-low | ~NO | 152cm summit, 77% open, but warm base |
| aspen-snowmass | poor | 22 | mediocre | NO | 92% terrain, -11 to -19C (our temp: 0C wrong!) |
| telluride | bad | 7 | mediocre | NO | 89% open, all lifts, 104cm base — bad(7) way too low |
| lake-louise | great | 77 | excellent | ~YES | 14-24cm fresh, -20C, all lifts — great fair, maybe excellent |
| revelstoke | great | 80 | great | YES | 289cm base, 931cm season, recent snow — aligned |
| chamonix | decent | 59 | good | ~NO | 360cm summit, 91% open — decent fair, maybe good |
| zermatt | mediocre | 50 | decent | ~YES | 55cm base thin, no fresh — mediocre/decent borderline |
| st-anton | poor | 28 | good | NO | 280cm summit, 99% lifts — poor(28) way too low |
| verbier | poor | 33 | good | NO | 270cm summit, 97% lifts — poor(33) way too low |
| val-disere | mediocre | 55 | good | NO | 261cm summit, 97% slopes — mediocre too low |
| niseko | mediocre | 54 | good | NO | 350cm summit, 100% open, -14C — mediocre too low |
| hakuba-valley | bad | 9 | mediocre | NO | 250cm summit, 90% Happo-One — bad(9) too low |

**Match rate: 4/20 (20%) — POOR**

### Systematic Issues Identified

1. **Over-penalizing 0cm fresh snow**: Resorts with deep bases, full operations, and groomed conditions rated "bad" (7-15) when external sources say "decent" or "mediocre". The model treats no fresh snow as catastrophic.

2. **Not weighting base depth enough**: Mammoth (310cm), St. Anton (280cm), Verbier (270cm), Niseko (350cm) all have massive bases but get poor/bad scores.

3. **Temperature data discrepancies**: Aspen shows 0C in our API vs -11 to -19C externally. Breckenridge shows -1C vs -16 to -21C. We may be reading base elevation temps when mid/top would be more representative.

4. **Jackson Hole over-scored**: great(75) with stale fresh snow data (3cm but actually 0cm in 24h). Old snow, warm, record-low base depth. Should be decent.

5. **Thaw-freeze penalty too harsh**: Many resorts show "Icy: recent thaw-freeze cycle" in explanations even when upper mountain has good frozen packed powder. The penalty seems applied resort-wide rather than per-elevation.

### External Sources Used
- OnTheSnow (onthesnow.com) — official snow reports
- Snow-Forecast (snow-forecast.com) — independent forecasts
- OpenSnow (opensnow.com) — detailed US resort data
- SnowStash (snowstash.com) — aggregated reports
- Resort official snow reports
- Colorado Sun — season analysis articles
- Buckrail — Jackson Hole local reporting

### Post-Retrain Scores (v16)

v16: 10,530 data points, Val MAE=0.241, R²=0.913, 59.5% exact, 93.8% within-1

| Resort | v15 Quality | v15 Score | v16 Quality | v16 Score | External | Change |
|--------|------------|-----------|-------------|-----------|----------|--------|
| whistler-blackcomb | good | 65 | good | 66 | good | +1, still aligned |
| mammoth-mountain | bad | 7 | bad | 9 | decent | +2, still too low |
| palisades-tahoe | bad | 13 | bad | 13 | decent | =, still too low |
| big-white | good | 66 | mediocre | 55 | good | -11, WORSE — was aligned, now too low |
| vail | poor | 27 | poor | 38 | decent | +11, closer but still low |
| park-city | bad | 10 | bad | 16 | decent | +6, still too low |
| jackson-hole | great | 75 | good | 74 | decent | -1, still too high |
| breckenridge | bad | 15 | bad | 19 | decent | +4, still too low |
| steamboat | poor | 20 | bad | 15 | decent-low | -5, WORSE |
| aspen-snowmass | poor | 22 | bad | 15 | mediocre | -7, WORSE |
| telluride | bad | 7 | bad | 8 | mediocre | +1, still too low |
| lake-louise | great | 77 | powder_day | 92 | excellent | +15, BETTER — now matches external |
| revelstoke | great | 80 | excellent | 87 | great | +7, slightly high now |
| chamonix | decent | 59 | decent | 59 | good | =, slightly low |
| zermatt | mediocre | 50 | mediocre | 41 | decent | -9, WORSE |
| st-anton | poor | 28 | poor | 28 | good | =, still too low |
| verbier | poor | 33 | poor | 33 | good | =, still too low |
| val-disere | mediocre | 55 | mediocre | 55 | good | =, still low |
| niseko | mediocre | 54 | mediocre | 50 | good | -4, slightly worse |
| hakuba-valley | bad | 9 | bad | 9 | mediocre | =, still too low |

**v16 distribution**: 1 powder_day, 1 excellent, 2 good, 1 decent, 4 mediocre, 3 poor, 8 bad

### Comparison & Analysis

**v16 vs v15 changes:**
- **Improved (3)**: Lake Louise (+15, now powder_day — matches external "excellent"), Revelstoke (+7), Vail (+11)
- **Unchanged (9)**: Most stayed the same — the fundamental issues persist
- **Worse (5)**: Big White (-11, was good→mediocre), Steamboat (-5), Aspen (-7), Zermatt (-9), Niseko (-4)
- **Slightly better (3)**: Mammoth (+2), Park City (+6), Breckenridge (+4)

**v16 match rate vs external: ~4/20 (20%) — NO IMPROVEMENT**

### Root Cause: The Problem Is NOT Model Weights

The retrain didn't fix the core issues because the problem is **upstream of the model**:

1. **Thaw-freeze detection is too aggressive**: Most "bad" scores come from "Icy: recent thaw-freeze cycle X hours ago" in the explanation. This pre-model penalty dominates the score, overriding what the ML model predicts. Resorts with deep bases and cold upper elevations get hammered because the BASE elevation had a thaw-freeze cycle.

2. **Temperature input uses wrong elevation**: Our API shows 0°C for Aspen and Breckenridge, but external sources show -11 to -21°C at mountain level. The scorer may be using base elevation temperature for the overall score, not mid/top.

3. **Base depth not weighted enough in scorer**: The ML model never sees "operational status" or "% terrain open." A resort with 300cm base and 0cm fresh gets the same treatment as one with 5cm base and 0cm fresh.

4. **Fresh snow dominance**: The quality explanation service and scorer heavily weight recent snowfall. Resorts in dry spells with excellent groomed conditions get scored as if they're nearly unskiable.

### Recommended Next Steps (NOT model retraining)

1. **Fix thaw-freeze to be elevation-aware**: Only apply thaw-freeze penalty if mid or top elevation experienced it, not just base
2. **Use mid-elevation temperature as representative**: Already documented as a consistency rule in MEMORY.md but may not be applied everywhere
3. **Add base depth floor**: If snow_depth > 100cm, score should never be "bad" regardless of fresh snow
4. **Reduce fresh-snow dominance**: A resort with 0cm fresh but 200cm base and -10°C should score "decent" minimum, not "bad"
