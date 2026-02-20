"""Collect historical hourly weather data from Open-Meteo archive API.

Fetches data for a specified date range (e.g., full month of January 2026)
to create more diverse training data across different weather patterns.
"""

import asyncio
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import aiohttp

# Open-Meteo Archive API (for historical data beyond 16 days)
ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
RESORTS_FILE = Path(__file__).parent.parent / "backend" / "data" / "resorts.json"
OUTPUT_FILE = Path(__file__).parent / "historical_features.json"

CONCURRENT_REQUESTS = 5  # Lower concurrency for archive API
REQUEST_DELAY = 0.3


def compute_features_for_day(
    hourly_temps, hourly_snowfall, hourly_times, day_index, elevation_m
):
    """Compute all ML features for a specific day from hourly data.

    Same logic as collect_data.py but works with archive data.
    """
    n_hours = len(hourly_temps)
    target_hour = day_index * 24 + 12  # midday
    if target_hour >= n_hours or target_hour < 48:
        return None

    cur_temp = hourly_temps[target_hour]
    if cur_temp is None:
        return None

    # Max/min temp in last 24/48 hours
    h24_start = max(0, target_hour - 24)
    h48_start = max(0, target_hour - 48)
    temps_24h = [t for t in hourly_temps[h24_start:target_hour] if t is not None]
    temps_48h = [t for t in hourly_temps[h48_start:target_hour] if t is not None]

    if not temps_24h:
        return None

    max_temp_24h = max(temps_24h)
    min_temp_24h = min(temps_24h)
    max_temp_48h = max(temps_48h) if temps_48h else max_temp_24h

    # Snowfall
    snow_24h = [s for s in hourly_snowfall[h24_start:target_hour] if s is not None]
    snowfall_24h_cm = sum(snow_24h)
    h72_start = max(0, target_hour - 72)
    snow_72h = [s for s in hourly_snowfall[h72_start:target_hour] if s is not None]
    snowfall_72h_cm = sum(snow_72h)

    # Freeze-thaw detection
    freeze_thaw_hour = None
    warmest_thaw = 0.0
    state = "looking_for_freeze"
    cold_hours = 0
    warm_hours = 0
    warm_peak = 0.0

    for h in range(target_hour, max(target_hour - 336, -1), -1):
        if h < 0 or h >= len(hourly_temps) or hourly_temps[h] is None:
            continue
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
                    freeze_thaw_hour = h + warm_hours + 2
                    warmest_thaw = warm_peak
                    break
            else:
                warm_hours = 0
                warm_peak = 0.0

    freeze_thaw_days_ago = (
        (target_hour - freeze_thaw_hour) / 24.0 if freeze_thaw_hour else 14.0
    )
    ft_start = freeze_thaw_hour or 0
    snow_since_freeze = sum(
        s for s in hourly_snowfall[ft_start:target_hour] if s is not None
    )

    since_ft_temps = [t for t in hourly_temps[ft_start:target_hour] if t is not None]
    hours_above_since_ft = {}
    for threshold in range(7):
        hours_above_since_ft[threshold] = sum(
            1 for t in since_ft_temps if t >= threshold
        )

    cur_hours_above = {}
    for threshold in range(7):
        count = 0
        for h in range(target_hour, max(target_hour - 168, -1), -1):
            if h < 0 or h >= len(hourly_temps) or hourly_temps[h] is None:
                break
            if hourly_temps[h] >= threshold:
                count += 1
            else:
                break
        cur_hours_above[threshold] = count

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
    }


async def fetch_resort_archive(
    session: aiohttp.ClientSession,
    resort: dict,
    start_date: str,
    end_date: str,
    semaphore: asyncio.Semaphore,
) -> list[dict]:
    """Fetch historical hourly data from Open-Meteo archive API."""
    async with semaphore:
        resort_id = resort["resort_id"]
        lat = resort["latitude"]
        lon = resort["longitude"]
        elev_top = resort["elevation_top_m"]

        params = {
            "latitude": lat,
            "longitude": lon,
            "elevation": elev_top,
            "hourly": "temperature_2m,snowfall",
            "start_date": start_date,
            "end_date": end_date,
            "timezone": "GMT",
        }

        for attempt in range(3):
            try:
                async with session.get(
                    ARCHIVE_URL,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as resp:
                    if resp.status == 429:
                        await asyncio.sleep(2**attempt + 1)
                        continue
                    if resp.status != 200:
                        text = await resp.text()
                        print(f"  HTTP {resp.status} for {resort_id}: {text[:100]}")
                        if attempt < 2:
                            await asyncio.sleep(2)
                            continue
                        return []
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

        if not temps:
            print(f"  NO DATA {resort_id}")
            return []

        results = []
        n_days = len(temps) // 24

        for day_idx in range(2, n_days):
            features = compute_features_for_day(
                temps, snowfall, times, day_idx, elev_top
            )
            if features:
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
                features["source"] = "historical"
                results.append(features)

        return results


async def collect_historical(start_date: str, end_date: str):
    """Collect historical features for all resorts."""
    with open(RESORTS_FILE) as f:
        data = json.load(f)

    resorts = data["resorts"]
    print(
        f"Collecting historical data ({start_date} to {end_date}) for {len(resorts)} resorts..."
    )

    semaphore = asyncio.Semaphore(CONCURRENT_REQUESTS)
    all_features = []

    async with aiohttp.ClientSession() as session:
        tasks = [
            fetch_resort_archive(session, r, start_date, end_date, semaphore)
            for r in resorts
        ]
        results = await asyncio.gather(*tasks)

        for resort_features in results:
            all_features.extend(resort_features)

    print(f"\nCollected {len(all_features)} data points across {len(resorts)} resorts")

    output = {
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "period": f"{start_date} to {end_date}",
        "source": "historical",
        "total_samples": len(all_features),
        "features": list(all_features[0].keys()) if all_features else [],
        "data": all_features,
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Saved to {OUTPUT_FILE}")
    return all_features


if __name__ == "__main__":
    import sys

    # Default: collect January 2026 data
    start = sys.argv[1] if len(sys.argv) > 1 else "2026-01-01"
    end = sys.argv[2] if len(sys.argv) > 2 else "2026-01-31"
    asyncio.run(collect_historical(start, end))
