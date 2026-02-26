# Resort Logo/Icon Research

**Date:** 2026-02-26
**Goal:** Find logo/icon URLs for 1040 ski resorts in Powder Chaser

## Summary

| Approach | Coverage | Quality | Reliability | Cost |
|----------|----------|---------|-------------|------|
| Google Favicon API | 836/1040 (80%) | 48-256px, varies | Excellent (Google CDN) | Free |
| DuckDuckGo Icons | 41 additional | 16-48px .ico | Good | Free |
| Direct favicon.ico | ~60% | 16-32px | Poor (many 404) | Free |
| Clearbit Logo API | 0% (down) | 128px+ | N/A - service appears defunct | Was free |
| apple-touch-icon | ~30% (manual) | 180px | Variable | Requires HTML parsing |

**Recommended approach: Google Favicon API + DuckDuckGo fallback + initials placeholder**

## Final Coverage

- **773 resorts (74.3%)**: Verified working logo/icon URL
- **104 resorts (10.0%)**: Have URL but unverified (may still work at runtime)
- **163 resorts (15.7%)**: No website, need fallback (initials/generic icon)

## Approach Details

### 1. Google Favicon API (PRIMARY)

URL pattern:
```
https://t3.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON&fallback_opts=TYPE,SIZE,URL&url=http://{domain}&size=128
```

**Pros:**
- Works for 80% of resorts with websites
- Returns the best available icon (apple-touch-icon > favicon > default)
- Served from Google CDN (fast, reliable, cached)
- Sizes range from 48px to 256px depending on what the site provides
- No API key required
- No rate limiting observed

**Cons:**
- Some icons are low quality (48x48) when site only has small favicon
- Occasionally returns wrong icon (e.g., Mammoth returns WordPress "W" because their CMS is WordPress)
- Returns a generic globe for unknown domains (~300 bytes)
- Quality varies significantly per resort

**Visual Quality Samples:**
| Resort | Resolution | Quality |
|--------|-----------|---------|
| Zermatt | 256x256 | Excellent - full color logo with Matterhorn |
| Alta | 180x180 | Good - clear "ALTA" text logo |
| Jackson Hole | 180x180 | Good - iconic cowboy silhouette |
| Courchevel | 256x256+ | Excellent |
| Vail | 48x48 | OK - recognizable blue "V" |
| Whistler | 48x48 | Poor - tiny swoosh, hard to see |
| Breckenridge | 48x48 | OK - "B" letter mark |

### 2. DuckDuckGo Icons API (FALLBACK)

URL pattern:
```
https://icons.duckduckgo.com/ip3/{domain}.ico
```

**Pros:**
- Recovers 41 additional resorts that Google misses
- Simple URL pattern
- No API key required

**Cons:**
- Returns .ico format (multi-resolution container, 16-48px)
- Lower quality than Google in most cases
- Some return generic icons

### 3. Clearbit Logo API (NOT VIABLE)

```
https://logo.clearbit.com/{domain}
```

The Clearbit logo API appears to be non-functional. All requests returned connection errors (HTTP 000). Clearbit was acquired by HubSpot and the free API may have been discontinued.

### 4. Direct favicon.ico (NOT RECOMMENDED)

Many resort websites return 404 for `/apple-touch-icon.png` and have inconsistent favicon paths. Would require parsing each site's HTML to find the actual icon link tags. Not scalable for 1040 resorts.

### 5. skiresort.info (NO LOGOS AVAILABLE)

All 1040 resorts have skiresort.info slugs (from `webcam_url`), but skiresort.info does not expose resort logos. Their pages contain webcam images and generic UI elements but no resort brand logos.

## Implementation Recommendation

### iOS Client-Side Approach

Use `AsyncImage` with a two-tier fallback:

```swift
// Primary: Google Favicon API
let logoURL = "https://t3.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON&fallback_opts=TYPE,SIZE,URL&url=http://\(resort.domain)&size=128"

// Fallback: Initials avatar (first letter of resort name)
```

**Advantages of client-side URL generation:**
- No need to store/update logo URLs in the database
- Google CDN handles caching
- Always returns *something* (generic globe worst case)
- No backend changes needed

### Backend Enhancement (Optional)

Add `domain` field to resorts.json (extracted from `website`) to make client-side URL generation simpler. The `resort_logos.json` file is already generated with verified data.

### Fallback for No-Logo Resorts (267 resorts)

For resorts without websites or with failed logo lookups, generate a stylish initials avatar:
- Use first letter(s) of resort name
- Color based on hash of resort name (consistent per resort)
- Round/circular shape matching the logo display

## Coverage by Region

| Region | With Logo | Total | Coverage |
|--------|-----------|-------|----------|
| NA West | 38 | 38 | 100% |
| NA East | 35 | 35 | 100% |
| NA Rockies | 42 | 43 | 98% |
| Japan | 51 | 53 | 96% |
| Scandinavia | 134 | 150 | 89% |
| Alps | 306 | 345 | 89% |
| Eastern Europe | 177 | 222 | 80% |
| South America | 30 | 39 | 77% |
| Oceania | 34 | 49 | 69% |
| Asia | 30 | 66 | 45% |

North American and Japanese resorts have near-100% coverage. Asian (China/Korea/India) resorts have the lowest coverage due to many domains being offline or not indexed by Google.

## Sample Working URLs

```
Alta:              https://t3.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON&fallback_opts=TYPE,SIZE,URL&url=http://alta.com&size=128
Vail:              https://t3.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON&fallback_opts=TYPE,SIZE,URL&url=http://vail.com&size=128
Zermatt:           https://t3.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON&fallback_opts=TYPE,SIZE,URL&url=http://zermatt.ch&size=128
Jackson Hole:      https://t3.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON&fallback_opts=TYPE,SIZE,URL&url=http://jacksonhole.com&size=128
Chamonix:          https://t3.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON&fallback_opts=TYPE,SIZE,URL&url=http://chamonix.com&size=128
Courchevel:        https://t3.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON&fallback_opts=TYPE,SIZE,URL&url=http://courchevel.com&size=128
Hakuba Valley:     https://t3.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON&fallback_opts=TYPE,SIZE,URL&url=http://hakubavalley.com&size=128
Coronet Peak:      https://t3.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON&fallback_opts=TYPE,SIZE,URL&url=http://coronetpeak.co.nz&size=128
Portillo:          https://t3.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON&fallback_opts=TYPE,SIZE,URL&url=http://skiportillo.com&size=128
Val d'Isere:       https://t3.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON&fallback_opts=TYPE,SIZE,URL&url=http://valdisere.com&size=128
Whistler:          https://t3.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON&fallback_opts=TYPE,SIZE,URL&url=http://whistlerblackcomb.com&size=128
Breckenridge:      https://t3.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON&fallback_opts=TYPE,SIZE,URL&url=http://breckenridge.com&size=128
Niseko:            https://t3.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON&fallback_opts=TYPE,SIZE,URL&url=http://niseko.ne.jp&size=128
Perisher:          https://t3.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON&fallback_opts=TYPE,SIZE,URL&url=http://perisher.com.au&size=128
Valle Nevado:      https://t3.gstatic.com/faviconV2?client=SOCIAL&type=FAVICON&fallback_opts=TYPE,SIZE,URL&url=http://vallenevado.com&size=128
```

## Generated Files

- **`backend/data/resort_logos.json`** - Pre-computed logo URLs for all 1040 resorts with verification status
- **`backend/scripts/find_resort_logos.py`** - Script to regenerate logo data (run with `--verify` for full validation)

## Known Issues

1. **WordPress false positives**: Some resorts using WordPress get the generic "W" icon instead of their actual logo (e.g., Mammoth Mountain). This affects ~5-10 resorts.
2. **Shared domains**: 38 domains are shared by multiple resorts (e.g., all Aspen resorts share aspensnowmass.com). These resorts get the same logo, which is acceptable.
3. **Small icons**: ~57 resorts return icons under 500 bytes (likely 16x16). These may appear blurry on Retina displays.
4. **Chinese domains**: Most Chinese ski resort domains are offline or not cached by Google/DDG, leading to lowest coverage in the Asia region.
