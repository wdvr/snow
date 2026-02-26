# WeatherKit Debug & Setup

Diagnose and fix Apple WeatherKit REST API issues.

## Quick Status Check

1. Check if WeatherKit is returning data on staging:
```bash
curl -s "https://staging.api.powderchaserapp.com/api/v1/resorts/big-white/conditions" | python3 -c "
import json, sys
data = json.load(sys.stdin)
for c in data.get('conditions', []):
    print(f\"{c['elevation_level']}: data_source={c.get('data_source', 'N/A')}\")
"
```
Look for `weatherkit.apple.com` in data_source. If missing, WeatherKit is failing silently.

2. Check CloudWatch for errors (last hour):
```bash
aws logs filter-log-events \
  --log-group-name "/aws/lambda/snow-tracker-weather-worker-staging" \
  --filter-pattern "WeatherKit request failed" \
  --start-time $(python3 -c "import time; print(int((time.time() - 3600) * 1000))") \
  --region us-west-2 --query 'events[*].message' --output text | head -10
```

3. Test JWT auth locally:
```bash
cd backend && PYTHONPATH=src python3 -c "
import time, json, jwt, requests, subprocess
result = subprocess.run(['aws', 'lambda', 'get-function-configuration',
    '--function-name', 'snow-tracker-weather-worker-staging',
    '--region', 'us-west-2', '--query', 'Environment.Variables',
    '--output', 'json'], capture_output=True, text=True)
env = json.loads(result.stdout)
pk = env['WEATHERKIT_PRIVATE_KEY']
token = jwt.encode(
    {'iss': env['WEATHERKIT_TEAM_ID'], 'iat': int(time.time()),
     'exp': int(time.time()) + 3600, 'sub': env['WEATHERKIT_SERVICE_ID']},
    pk, algorithm='ES256',
    headers={'kid': env['WEATHERKIT_KEY_ID'],
             'id': env['WEATHERKIT_TEAM_ID'] + '.' + env['WEATHERKIT_SERVICE_ID']})
resp = requests.get('https://weatherkit.apple.com/api/v1/weather/en/49.0652/-118.4073',
    params={'dataSets': 'currentWeather'},
    headers={'Authorization': f'Bearer {token}'}, timeout=10)
print(f'Status: {resp.status_code}')
print(f'Body: {resp.text[:300]}')
"
```

## Architecture

### JWT Authentication (ES256)
- **Header**: `alg: ES256`, `kid: <key-id>`, `id: <team-id>.<services-id>`, `typ: JWT`
- **Payload**: `iss: <team-id>`, `iat: <now>`, `exp: <now+3600>`, `sub: <services-id>`
- JWT cached for 1 hour with 60s buffer before refresh
- Code: `backend/src/services/weatherkit_service.py`

### Critical: Services ID vs App ID
The `sub` claim MUST be a **Services ID** (registered under Identifiers > Services IDs), NOT the App ID/bundle ID.
- Correct: `com.wouterdevriendt.snowtracker.weatherkit` (Services ID)
- Wrong: `com.wouterdevriendt.snowtracker` (App ID/bundle ID)
Using the App ID returns `{"reason": "NOT_ENABLED"}` (401).

### Apple Developer Portal Requirements
1. **Key** (Certificates, Identifiers & Profiles > Keys): Must have **WeatherKit** capability checked
2. **Services ID** (Identifiers > Services IDs): Just needs to be registered (no capabilities needed on it)
3. **App ID** (Identifiers > App IDs): WeatherKit in Capabilities AND App Services (not strictly required for REST API, but good practice)

### Environment Variables
| Variable | Source | Value |
|----------|--------|-------|
| `WEATHERKIT_KEY_ID` | GitHub Secret | `FM5LVBRMFC` (same .p8 key as APNs) |
| `WEATHERKIT_TEAM_ID` | GitHub Secret | `N324UX8D9M` |
| `WEATHERKIT_SERVICE_ID` | GitHub Secret | `com.wouterdevriendt.snowtracker.weatherkit` |
| `WEATHERKIT_PRIVATE_KEY` | Deploy workflow | Falls back to `APNS_PRIVATE_KEY` secret (same .p8 key) |
| `ENABLE_WEATHERKIT` | GitHub Variable | `true` |

### Data Flow
```
Weather Worker (per resort, per elevation)
  → WeatherKitService.get_weather(lat, lon)
    → Generate/cache ES256 JWT
    → GET weatherkit.apple.com/api/v1/weather/en/{lat}/{lon}
      ?dataSets=currentWeather,forecastHourly
      &hourlyStart=<24h ago>&hourlyEnd=<now>
    → Parse: snowfall (SWE × 8 for snow, × 4 for mixed), temperature, precip type
  → SourceData(source_name="weatherkit", snowfall_24h_cm=X)
  → MultiSourceMerger.merge() with outlier detection
```

### WeatherKit API Limits
- 500,000 calls/month free (included with Apple Developer Program)
- ~1200 resorts × 3 elevations × 24 runs/day = ~86,400 calls/day = ~2.6M/month
- May need to limit to fewer calls or batch resorts

## Common Errors

| Error | Cause | Fix |
|-------|-------|-----|
| `401 {"reason": "NOT_ENABLED"}` | `sub` claim uses App ID instead of Services ID | Set `WEATHERKIT_SERVICE_ID` to the Services ID |
| `401 Unauthorized` (no body) | Key doesn't have WeatherKit capability | Enable WeatherKit on the key in Apple Developer Portal |
| `Read timed out` | WeatherKit API slow (>10s) | Transient; the 10s timeout is reasonable |
| `WeatherKit not configured` | Missing env vars | Check `ENABLE_WEATHERKIT=true` and all `WEATHERKIT_*` vars set |

## Rotating Keys
If the .p8 key is compromised:
1. Create new key in Apple Developer > Keys with WeatherKit + APNs enabled
2. Update GitHub secrets: `APNS_KEY_ID`, `APNS_PRIVATE_KEY`, `WEATHERKIT_KEY_ID`
3. Deploy to all environments
