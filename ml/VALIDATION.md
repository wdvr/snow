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

### Post-Retrain Scores
*(to be filled after retraining completes)*

### Comparison & Analysis
*(to be filled after both validations complete)*
