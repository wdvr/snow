"""Collect hourly weather data from Open-Meteo and compute ML features for snow quality scoring.

For each resort, fetches 14 days of hourly data at top elevation and computes:
- Temperature features (cur_temp, max_temp_24h, max_temp_48h, min_temp_24h)
- Freeze-thaw features (days_ago, warmest_thaw, snow_since_freeze)
- Hours above threshold since freeze-thaw (0-6°C)
- Current warm spell hours above threshold (0-6°C)
- Snowfall features (24h, 72h)
- Elevation
- Weather comfort features (cloud cover, wind chill, weather codes)
"""

import asyncio
import json
import math
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aiohttp

OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
RESORTS_FILE = Path(__file__).parent.parent / "backend" / "data" / "resorts.json"
OUTPUT_FILE = Path(__file__).parent / "training_features.json"

# Rate limit: Open-Meteo allows ~600 req/min for free tier
CONCURRENT_REQUESTS = 10
REQUEST_DELAY = 0.15  # seconds between batches

# WMO weather codes that indicate clear/sunny conditions
CLEAR_WEATHER_CODES = {0, 1}  # Clear sky, Mainly clear
PARTLY_CLOUDY_CODES = {2}  # Partly cloudy
PRECIPITATION_CODES = {
    51,
    53,
    55,
    61,
    63,
    65,
    66,
    67,
    71,
    73,
    75,
    77,
    80,
    81,
    82,
    85,
    86,
    95,
    96,
    99,
}


def compute_wind_chill(temp_c: float, wind_kmh: float) -> float:
    """Compute wind chill temperature using the North American formula.

    Valid for temps <= 10C and wind >= 4.8 km/h.
    Returns the effective "feels like" temperature in C.
    """
    if temp_c > 10.0 or wind_kmh < 4.8:
        return temp_c
    wc = (
        13.12
        + 0.6215 * temp_c
        - 11.37 * (wind_kmh**0.16)
        + 0.3965 * temp_c * (wind_kmh**0.16)
    )
    return round(wc, 1)


def compute_features_for_day(
    hourly_temps: list[float],
    hourly_snowfall: list[float],
    hourly_times: list[str],
    day_index: int,
    elevation_m: float,
    hourly_wind: list[float] | None = None,
    hourly_snow_depth: list[float] | None = None,
    hourly_weather_code: list[int] | None = None,
    hourly_cloud_cover: list[float] | None = None,
) -> dict | None:
    """Compute all ML features for a specific day from hourly data.

    Args:
        hourly_temps: Full array of hourly temperatures (°C)
        hourly_snowfall: Full array of hourly snowfall (cm)
        hourly_times: Full array of ISO timestamps
        day_index: Which day (0 = oldest, each day = 24 hours)
        elevation_m: Elevation in meters
        hourly_wind: Full array of hourly wind speed (km/h), optional
        hourly_snow_depth: Full array of hourly snow depth (cm), optional
        hourly_weather_code: Full array of WMO weather codes, optional
        hourly_cloud_cover: Full array of cloud cover percentage (0-100), optional

    Returns:
        Feature dict or None if insufficient data
    """
    n_hours = len(hourly_temps)
    # The "current" hour is the end of the target day (midday = noon)
    target_hour = day_index * 24 + 12  # midday
    if target_hour >= n_hours or target_hour < 48:  # need 48h lookback minimum
        return None

    # Current temperature (at midday)
    cur_temp = hourly_temps[target_hour]

    # Max/min temp in last 24 hours
    h24_start = max(0, target_hour - 24)
    temps_24h = hourly_temps[h24_start:target_hour]
    max_temp_24h = max(temps_24h) if temps_24h else cur_temp
    min_temp_24h = min(temps_24h) if temps_24h else cur_temp

    # Max temp in last 48 hours
    h48_start = max(0, target_hour - 48)
    temps_48h = hourly_temps[h48_start:target_hour]
    max_temp_48h = max(temps_48h) if temps_48h else cur_temp

    # Snowfall in last 24 hours
    snow_24h = hourly_snowfall[h24_start:target_hour]
    snowfall_24h_cm = sum(snow_24h) if snow_24h else 0.0

    # Snowfall in last 72 hours
    h72_start = max(0, target_hour - 72)
    snow_72h = hourly_snowfall[h72_start:target_hour]
    snowfall_72h_cm = sum(snow_72h) if snow_72h else 0.0

    # --- Freeze-thaw detection ---
    # Scan backwards from target_hour to find the most recent freeze-thaw event.
    # A freeze-thaw = period where temp was above 0°C for 3+ hours,
    # followed by temp dropping below -1°C for 2+ hours (hard freeze).
    freeze_thaw_hour = None
    warmest_thaw = 0.0

    # State machine scanning backwards
    state = "looking_for_freeze"  # Start by looking for a freeze (cold period)
    cold_hours = 0
    warm_hours = 0
    warm_peak = 0.0

    for h in range(target_hour, max(target_hour - 336, -1), -1):  # Up to 14 days back
        if h < 0:
            break
        t = hourly_temps[h]

        if state == "looking_for_freeze":
            if t <= -1.0:
                cold_hours += 1
                if cold_hours >= 2:
                    state = "looking_for_thaw"
                    cold_hours = 0
            else:
                cold_hours = 0

        elif state == "looking_for_thaw":
            if t >= 0.0:
                warm_hours += 1
                warm_peak = max(warm_peak, t)
                if warm_hours >= 3:
                    # Found a thaw period followed by freeze
                    # The freeze happened at h + warm_hours + cold_hours (approx)
                    freeze_thaw_hour = h + warm_hours + 2  # approximate freeze point
                    warmest_thaw = warm_peak
                    break
            else:
                warm_hours = 0
                warm_peak = 0.0

    if freeze_thaw_hour is not None:
        freeze_thaw_days_ago = (target_hour - freeze_thaw_hour) / 24.0
    else:
        freeze_thaw_days_ago = 14.0  # No freeze-thaw found in 14 days

    # Snow since freeze-thaw
    ft_start = freeze_thaw_hour if freeze_thaw_hour is not None else 0
    snow_since_freeze = sum(hourly_snowfall[ft_start:target_hour])

    # Hours above thresholds since freeze-thaw
    since_ft_temps = hourly_temps[ft_start:target_hour]
    hours_above_since_ft = {}
    for threshold in range(7):  # 0, 1, 2, 3, 4, 5, 6
        hours_above_since_ft[threshold] = sum(
            1 for t in since_ft_temps if t >= threshold
        )

    # Current warm spell: consecutive hours above threshold ending at target_hour
    cur_hours_above = {}
    for threshold in range(7):
        count = 0
        for h in range(target_hour, max(target_hour - 168, -1), -1):  # up to 7 days
            if h < 0:
                break
            if hourly_temps[h] >= threshold:
                count += 1
            else:
                break
        cur_hours_above[threshold] = count

    # Wind features
    if hourly_wind and len(hourly_wind) > target_hour:
        wind_24h = [w for w in hourly_wind[h24_start:target_hour] if w is not None]
        cur_wind = (
            hourly_wind[target_hour] if hourly_wind[target_hour] is not None else 0.0
        )
        avg_wind_24h = sum(wind_24h) / len(wind_24h) if wind_24h else 0.0
        max_wind_24h = max(wind_24h) if wind_24h else 0.0
    else:
        cur_wind = 0.0
        avg_wind_24h = 0.0
        max_wind_24h = 0.0

    # Snow depth feature (Open-Meteo returns snow_depth in meters)
    if hourly_snow_depth and len(hourly_snow_depth) > target_hour:
        sd = hourly_snow_depth[target_hour]
        snow_depth_cm = sd * 100.0 if sd is not None else 0.0
    else:
        snow_depth_cm = 0.0

    # --- Weather comfort features ---
    # Cloud cover at midday (0-100%)
    if hourly_cloud_cover and len(hourly_cloud_cover) > target_hour:
        cloud_cover = hourly_cloud_cover[target_hour]
        cloud_cover = cloud_cover if cloud_cover is not None else 50.0
    else:
        cloud_cover = 50.0  # default to partly cloudy

    # Weather code at midday
    if hourly_weather_code and len(hourly_weather_code) > target_hour:
        wcode = hourly_weather_code[target_hour]
        wcode = wcode if wcode is not None else 3
    else:
        wcode = 3  # default to overcast

    # is_clear: 1 if clear or mainly clear sky (WMO codes 0-1)
    is_clear = 1.0 if wcode in CLEAR_WEATHER_CODES else 0.0

    # is_snowing: 1 if actively snowing (helps distinguish fresh powder days)
    is_snowing = 1.0 if wcode in {71, 73, 75, 77, 85, 86} else 0.0

    # Wind chill temperature
    wind_chill = compute_wind_chill(cur_temp, cur_wind)

    # Wind chill delta: how much colder it feels vs actual temp
    # More negative = harsher conditions
    wind_chill_delta = wind_chill - cur_temp

    return {
        "cur_temp": round(cur_temp, 1),
        "max_temp_24h": round(max_temp_24h, 1),
        "max_temp_48h": round(max_temp_48h, 1),
        "min_temp_24h": round(min_temp_24h, 1),
        "freeze_thaw_days_ago": round(freeze_thaw_days_ago, 2),
        "warmest_thaw": round(warmest_thaw, 1),
        "snow_since_freeze_cm": round(snow_since_freeze, 1),
        "snowfall_24h_cm": round(snowfall_24h_cm, 1),
        "snowfall_72h_cm": round(snowfall_72h_cm, 1),
        "elevation_m": elevation_m,
        "total_hours_above_0C_since_ft": hours_above_since_ft[0],
        "total_hours_above_1C_since_ft": hours_above_since_ft[1],
        "total_hours_above_2C_since_ft": hours_above_since_ft[2],
        "total_hours_above_3C_since_ft": hours_above_since_ft[3],
        "total_hours_above_4C_since_ft": hours_above_since_ft[4],
        "total_hours_above_5C_since_ft": hours_above_since_ft[5],
        "total_hours_above_6C_since_ft": hours_above_since_ft[6],
        "cur_hours_above_0C": cur_hours_above[0],
        "cur_hours_above_1C": cur_hours_above[1],
        "cur_hours_above_2C": cur_hours_above[2],
        "cur_hours_above_3C": cur_hours_above[3],
        "cur_hours_above_4C": cur_hours_above[4],
        "cur_hours_above_5C": cur_hours_above[5],
        "cur_hours_above_6C": cur_hours_above[6],
        "cur_wind_kmh": round(cur_wind, 1),
        "max_wind_24h": round(max_wind_24h, 1),
        "avg_wind_24h": round(avg_wind_24h, 1),
        "snow_depth_cm": round(snow_depth_cm, 1),
        "cloud_cover_pct": round(cloud_cover, 1),
        "weather_code": int(wcode),
        "is_clear": is_clear,
        "is_snowing": is_snowing,
        "wind_chill_c": wind_chill,
        "wind_chill_delta": round(wind_chill_delta, 1),
    }


async def fetch_resort_data(
    session: aiohttp.ClientSession,
    resort: dict,
    semaphore: asyncio.Semaphore,
) -> list[dict]:
    """Fetch hourly data from Open-Meteo for a resort and compute features."""
    async with semaphore:
        resort_id = resort["resort_id"]
        lat = resort["latitude"]
        lon = resort["longitude"]
        elev_top = resort["elevation_top_m"]

        params = {
            "latitude": lat,
            "longitude": lon,
            "elevation": elev_top,
            "hourly": "temperature_2m,snowfall,wind_speed_10m,snow_depth,weather_code,cloud_cover",
            "past_days": 14,
            "forecast_days": 1,
            "timezone": "GMT",
        }

        for attempt in range(3):
            try:
                async with session.get(
                    OPEN_METEO_URL,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    if resp.status == 429:
                        await asyncio.sleep(2**attempt)
                        continue
                    resp.raise_for_status()
                    data = await resp.json()
                    break
            except Exception as e:
                if attempt == 2:
                    print(f"  FAILED {resort_id}: {e}")
                    return []
                await asyncio.sleep(1)

        hourly = data.get("hourly", {})
        temps = hourly.get("temperature_2m", [])
        snowfall = hourly.get("snowfall", [])
        times = hourly.get("time", [])
        wind = hourly.get("wind_speed_10m", [])
        snow_depth = hourly.get("snow_depth", [])
        weather_code = hourly.get("weather_code", [])
        cloud_cover = hourly.get("cloud_cover", [])

        if not temps:
            print(f"  NO DATA {resort_id}")
            return []

        results = []
        n_days = len(temps) // 24

        # Compute features for each full day (skip first 2 days for lookback)
        for day_idx in range(2, n_days):
            features = compute_features_for_day(
                temps,
                snowfall,
                times,
                day_idx,
                elev_top,
                wind,
                snow_depth,
                weather_code,
                cloud_cover,
            )
            if features:
                # Determine the date for this day
                hour_idx = day_idx * 24
                if hour_idx < len(times):
                    date_str = times[hour_idx][:10]
                else:
                    date_str = f"day_{day_idx}"

                features["resort_id"] = resort_id
                features["resort_name"] = resort["name"]
                features["date"] = date_str
                features["country"] = resort["country"]
                features["region"] = resort["region"]
                results.append(features)

        return results


async def collect_all():
    """Collect features for all resorts."""
    with open(RESORTS_FILE) as f:
        data = json.load(f)

    resorts = data["resorts"]
    print(f"Collecting data for {len(resorts)} resorts...")

    semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)
    all_features = []

    async with aiohttp.ClientSession() as session:
        tasks = [fetch_resort_data(session, r, semaphore) for r in resorts]
        results = await asyncio.gather(*tasks)

        for resort_features in results:
            all_features.extend(resort_features)

    print(f"\nCollected {len(all_features)} data points across {len(resorts)} resorts")

    # Save
    output = {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "total_samples": len(all_features),
        "features": list(all_features[0].keys()) if all_features else [],
        "data": all_features,
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Saved to {OUTPUT_FILE}")
    return all_features


if __name__ == "__main__":
    asyncio.run(collect_all())
