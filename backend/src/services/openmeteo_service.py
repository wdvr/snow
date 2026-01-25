"""Open-Meteo weather data service for accurate elevation-aware weather data."""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import requests

from models.weather import ConfidenceLevel

logger = logging.getLogger(__name__)


class OpenMeteoService:
    """Service for fetching elevation-aware weather data from Open-Meteo API.

    Open-Meteo provides:
    - Free API (no key required)
    - Elevation-aware data
    - Snow depth and snowfall
    - Historical and forecast data (ERA5 reanalysis)
    """

    def __init__(self):
        """Initialize the Open-Meteo service."""
        self.base_url = "https://api.open-meteo.com/v1/forecast"
        self.era5_url = "https://archive-api.open-meteo.com/v1/era5"

    def get_current_weather(
        self, latitude: float, longitude: float, elevation_meters: int
    ) -> dict[str, Any]:
        """
        Fetch current weather data for a specific location and elevation.

        Returns a dictionary suitable for creating a WeatherCondition object.
        """
        try:
            params = {
                "latitude": latitude,
                "longitude": longitude,
                "elevation": elevation_meters,
                "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
                "hourly": "temperature_2m,snowfall,snow_depth",
                "daily": "temperature_2m_min,temperature_2m_max,snowfall_sum",
                "past_days": 3,
                "forecast_days": 3,
                "timezone": "auto",
            }

            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()

            data = response.json()

            # Process the response
            current = data.get("current", {})
            hourly = data.get("hourly", {})
            daily = data.get("daily", {})

            # Calculate snowfall from daily data
            snowfall_data = self._process_snowfall(daily, hourly)

            # Calculate ice hours from hourly temperatures
            ice_hours_data = self._calculate_ice_hours(hourly)

            # Get weather description from weather code
            weather_code = current.get("weather_code", 0)
            weather_description = self._weather_code_to_description(weather_code)

            # Skip ERA5 for now to reduce Lambda execution time
            # TODO: Add ERA5 snow depth fetching as a separate background job
            era5_snow_depth = None

            weather_data = {
                "current_temp_celsius": current.get("temperature_2m", 0.0),
                "min_temp_celsius": snowfall_data.get(
                    "min_temp_24h", current.get("temperature_2m", 0.0) - 2
                ),
                "max_temp_celsius": snowfall_data.get(
                    "max_temp_24h", current.get("temperature_2m", 0.0) + 2
                ),
                # Past snowfall (using rolling windows from hourly data)
                "snowfall_24h_cm": snowfall_data.get("snowfall_24h", 0.0),
                "snowfall_48h_cm": snowfall_data.get("snowfall_48h", 0.0),
                "snowfall_72h_cm": snowfall_data.get("snowfall_72h", 0.0),
                # Future predictions
                "predicted_snow_24h_cm": snowfall_data.get("predicted_24h", 0.0),
                "predicted_snow_48h_cm": snowfall_data.get("predicted_48h", 0.0),
                "predicted_snow_72h_cm": snowfall_data.get("predicted_72h", 0.0),
                # Ice formation factors
                "hours_above_ice_threshold": ice_hours_data.get(
                    "hours_above_threshold", 0.0
                ),
                "max_consecutive_warm_hours": ice_hours_data.get(
                    "max_consecutive", 0.0
                ),
                # Fresh powder tracking (snowfall that occurred after last freeze-thaw)
                "snowfall_after_freeze_cm": snowfall_data.get(
                    "snowfall_after_freeze_cm", 0.0
                ),
                "hours_since_last_snowfall": snowfall_data.get(
                    "hours_since_last_snowfall"
                ),
                "last_freeze_thaw_hours_ago": snowfall_data.get(
                    "last_freeze_thaw_hours_ago"
                ),
                "currently_warming": snowfall_data.get("currently_warming", False),
                # Weather conditions
                "humidity_percent": current.get("relative_humidity_2m", 0.0),
                "wind_speed_kmh": current.get("wind_speed_10m", 0.0),
                "weather_description": weather_description,
                # Data source info
                "data_source": "open-meteo.com",
                "source_confidence": ConfidenceLevel.MEDIUM,
                "raw_data": {
                    "api_response": data,
                    "elevation_meters": elevation_meters,
                    "model_elevation": data.get("elevation", elevation_meters),
                    "snow_depth_cm": era5_snow_depth
                    or snowfall_data.get("current_snow_depth", 0.0),
                },
            }

            return weather_data

        except requests.exceptions.RequestException as e:
            logger.error(f"Open-Meteo API request failed: {str(e)}")
            raise Exception(f"Failed to fetch weather data: {str(e)}")
        except KeyError as e:
            logger.error(f"Unexpected Open-Meteo response format: missing {str(e)}")
            raise Exception(f"Unexpected weather API response format: missing {str(e)}")
        except Exception as e:
            logger.error(f"Error processing Open-Meteo data: {str(e)}")
            raise Exception(f"Error processing weather data: {str(e)}")

    def _process_snowfall(self, daily: dict, hourly: dict) -> dict[str, float]:
        """Process snowfall data using hourly data for accurate rolling windows.

        Uses hourly snowfall data to calculate true rolling 24h/48h/72h windows
        instead of calendar-day sums, which is more accurate for detecting recent snowfall.
        """
        result = {
            "snowfall_24h": 0.0,
            "snowfall_48h": 0.0,
            "snowfall_72h": 0.0,
            "predicted_24h": 0.0,
            "predicted_48h": 0.0,
            "predicted_72h": 0.0,
            "min_temp_24h": None,
            "max_temp_24h": None,
            "current_snow_depth": 0.0,
            # New fields for fresh powder detection
            "snowfall_after_freeze_cm": 0.0,
            "hours_since_last_snowfall": None,
            "last_freeze_thaw_hours_ago": None,
        }

        # Process hourly data for accurate rolling windows
        hourly_snowfall = hourly.get("snowfall", [])
        hourly_temps = hourly.get("temperature_2m", [])
        hourly_times = hourly.get("time", [])

        if hourly_snowfall and hourly_times:
            # Find current hour index
            now = datetime.now(UTC)
            now_str = now.strftime("%Y-%m-%dT%H:00")
            current_index = len(hourly_times) - 1

            for i, time_str in enumerate(hourly_times):
                if time_str[:13] >= now_str[:13]:
                    current_index = i
                    break

            # Calculate rolling snowfall windows from hourly data
            # Hourly snowfall is in cm, sum over the windows
            start_24h = max(0, current_index - 24)
            start_48h = max(0, current_index - 48)
            start_72h = max(0, current_index - 72)

            for i in range(start_72h, current_index + 1):
                if i < len(hourly_snowfall) and hourly_snowfall[i] is not None:
                    snow_cm = hourly_snowfall[i]
                    if i >= start_24h:
                        result["snowfall_24h"] += snow_cm
                    if i >= start_48h:
                        result["snowfall_48h"] += snow_cm
                    result["snowfall_72h"] += snow_cm

            # Calculate predicted snowfall (future hours)
            future_24h = min(len(hourly_snowfall), current_index + 24)
            future_48h = min(len(hourly_snowfall), current_index + 48)
            future_72h = min(len(hourly_snowfall), current_index + 72)

            for i in range(current_index + 1, future_72h):
                if i < len(hourly_snowfall) and hourly_snowfall[i] is not None:
                    snow_cm = hourly_snowfall[i]
                    if i < future_24h:
                        result["predicted_24h"] += snow_cm
                    if i < future_48h:
                        result["predicted_48h"] += snow_cm
                    result["predicted_72h"] += snow_cm

            # Calculate snowfall-after-freeze (key fresh powder metric)
            # Ice formation occurs with multiple temperature/duration thresholds:
            # - 3h at +3°C or higher (warmest = fastest ice)
            # - 6h at +2°C or higher
            # - 8h at +1°C or higher
            # This is the "reset" point - any snow before this is assumed icy

            # Thaw-freeze thresholds: (temp_celsius, required_hours)
            ICE_THRESHOLDS = [
                (3.0, 3),  # 3 hours at +3°C
                (2.0, 6),  # 6 hours at +2°C
                (1.0, 8),  # 8 hours at +1°C
            ]

            # Find the last "ice formation event" using multi-threshold detection
            # An ice event occurs when ANY threshold is met
            last_ice_event_end_index = None

            # Track consecutive hours at each threshold level
            for i in range(current_index, start_72h - 1, -1):
                if i >= len(hourly_temps) or hourly_temps[i] is None:
                    continue

                temp = hourly_temps[i]

                # Check each threshold - look backwards for consecutive hours
                for threshold_temp, required_hours in ICE_THRESHOLDS:
                    if temp >= threshold_temp:
                        # Count consecutive hours at or above this threshold
                        consecutive = 0
                        for j in range(
                            i, max(start_72h - 1, i - required_hours - 1), -1
                        ):
                            if (
                                j < len(hourly_temps)
                                and hourly_temps[j] is not None
                                and hourly_temps[j] >= threshold_temp
                            ):
                                consecutive += 1
                            else:
                                break

                        if consecutive >= required_hours:
                            # Found an ice formation event!
                            last_ice_event_end_index = i
                            break

                if last_ice_event_end_index is not None:
                    break

            if last_ice_event_end_index is not None:
                result["last_freeze_thaw_hours_ago"] = float(
                    current_index - last_ice_event_end_index
                )
                # Sum snowfall AFTER the ice formation event (this is non-refrozen snow!)
                for i in range(last_ice_event_end_index + 1, current_index + 1):
                    if i < len(hourly_snowfall) and hourly_snowfall[i] is not None:
                        result["snowfall_after_freeze_cm"] += hourly_snowfall[i]
            else:
                # No ice formation event in last 72h - all snow is potentially fresh
                result["snowfall_after_freeze_cm"] = result["snowfall_72h"]
                result["last_freeze_thaw_hours_ago"] = 72.0

            # Also track if we're currently in a warming period (ice forming now)
            # Use lowest threshold (1°C) - any temp >= 1°C can form ice given enough time
            WARMING_THRESHOLD = 1.0
            result["currently_warming"] = (
                hourly_temps[current_index] >= WARMING_THRESHOLD
                if current_index < len(hourly_temps)
                and hourly_temps[current_index] is not None
                else False
            )

            # Find hours since last snowfall
            for i in range(current_index, start_72h - 1, -1):
                if (
                    i < len(hourly_snowfall)
                    and hourly_snowfall[i] is not None
                    and hourly_snowfall[i] > 0
                ):
                    result["hours_since_last_snowfall"] = float(current_index - i)
                    break

            # Get min/max temp from last 24 hours
            temps_24h = [
                t for t in hourly_temps[start_24h : current_index + 1] if t is not None
            ]
            if temps_24h:
                result["min_temp_24h"] = min(temps_24h)
                result["max_temp_24h"] = max(temps_24h)

        # Fallback to daily data if hourly is incomplete
        if result["snowfall_24h"] == 0.0 and result["snowfall_48h"] == 0.0:
            daily_snowfall = daily.get("snowfall_sum", [])
            daily_min_temps = daily.get("temperature_2m_min", [])
            daily_max_temps = daily.get("temperature_2m_max", [])
            dates = daily.get("time", [])

            today = datetime.now(UTC).strftime("%Y-%m-%d")
            today_index = None

            for i, date in enumerate(dates):
                if date == today:
                    today_index = i
                    break

            if today_index is not None and daily_snowfall:
                # Include today's snowfall in 24h (it's ongoing)
                if len(daily_snowfall) > today_index:
                    result["snowfall_24h"] = daily_snowfall[today_index] or 0.0
                if today_index >= 1 and len(daily_snowfall) > today_index - 1:
                    result["snowfall_24h"] += daily_snowfall[today_index - 1] or 0.0
                    result["snowfall_48h"] = result["snowfall_24h"]
                if today_index >= 2 and len(daily_snowfall) > today_index - 2:
                    result["snowfall_48h"] += daily_snowfall[today_index - 2] or 0.0
                    result["snowfall_72h"] = result["snowfall_48h"]
                if today_index >= 3 and len(daily_snowfall) > today_index - 3:
                    result["snowfall_72h"] += daily_snowfall[today_index - 3] or 0.0

                # Temperature range
                if len(daily_min_temps) > today_index:
                    result["min_temp_24h"] = daily_min_temps[today_index]
                if len(daily_max_temps) > today_index:
                    result["max_temp_24h"] = daily_max_temps[today_index]

        # Get current snow depth from hourly data (most recent value)
        hourly_snow_depth = hourly.get("snow_depth", [])
        if hourly_snow_depth:
            # Find the most recent non-null value
            for depth in reversed(hourly_snow_depth):
                if depth is not None:
                    result["current_snow_depth"] = depth * 100  # Convert m to cm
                    break

        return result

    def _calculate_ice_hours(
        self, hourly: dict, threshold_temp: float = 3.0
    ) -> dict[str, float]:
        """Calculate ice formation metrics from hourly temperature data."""
        result = {
            "hours_above_threshold": 0.0,
            "max_consecutive": 0.0,
        }

        temps = hourly.get("temperature_2m", [])
        if not temps:
            return result

        # Get current hour index (approximately)
        times = hourly.get("time", [])
        now = datetime.now(UTC).isoformat()[:13]  # Get current hour
        current_index = len(temps) - 1

        for i, time in enumerate(times):
            if time[:13] == now:
                current_index = i
                break

        # Look at last 24 hours
        start_index = max(0, current_index - 24)
        recent_temps = temps[start_index : current_index + 1]

        # Count hours above threshold
        hours_above = sum(
            1 for temp in recent_temps if temp is not None and temp >= threshold_temp
        )
        result["hours_above_threshold"] = float(hours_above)

        # Calculate max consecutive hours above freezing (0°C)
        max_consecutive = 0
        current_consecutive = 0

        for temp in recent_temps:
            if temp is not None and temp >= 0.0:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0

        result["max_consecutive"] = float(max_consecutive)

        return result

    def _weather_code_to_description(self, code: int) -> str:
        """Convert WMO weather code to description."""
        weather_codes = {
            0: "Clear sky",
            1: "Mainly clear",
            2: "Partly cloudy",
            3: "Overcast",
            45: "Fog",
            48: "Depositing rime fog",
            51: "Light drizzle",
            53: "Moderate drizzle",
            55: "Dense drizzle",
            61: "Slight rain",
            63: "Moderate rain",
            65: "Heavy rain",
            66: "Light freezing rain",
            67: "Heavy freezing rain",
            71: "Slight snow fall",
            73: "Moderate snow fall",
            75: "Heavy snow fall",
            77: "Snow grains",
            80: "Slight rain showers",
            81: "Moderate rain showers",
            82: "Violent rain showers",
            85: "Slight snow showers",
            86: "Heavy snow showers",
            95: "Thunderstorm",
            96: "Thunderstorm with slight hail",
            99: "Thunderstorm with heavy hail",
        }
        return weather_codes.get(code, "Unknown")

    def _get_era5_snow_depth(self, latitude: float, longitude: float) -> float | None:
        """Fetch snow depth from ERA5 historical data (more accurate than forecast model)."""
        try:
            # Get data from the last few days
            end_date = datetime.now(UTC).strftime("%Y-%m-%d")
            start_date = (datetime.now(UTC) - timedelta(days=3)).strftime("%Y-%m-%d")

            params = {
                "latitude": latitude,
                "longitude": longitude,
                "start_date": start_date,
                "end_date": end_date,
                "daily": "snow_depth_max",
                "timezone": "auto",
            }

            response = requests.get(self.era5_url, params=params, timeout=15)

            if response.status_code != 200:
                return None

            data = response.json()
            daily = data.get("daily", {})
            snow_depths = daily.get("snow_depth_max", [])

            # Return the most recent non-null snow depth (in cm)
            for depth in reversed(snow_depths):
                if depth is not None:
                    return depth * 100  # Convert m to cm

            return None

        except Exception as e:
            logger.warning(f"Failed to fetch ERA5 snow depth: {str(e)}")
            return None

    def validate_api(self) -> bool:
        """Validate that the API is accessible."""
        try:
            # Test with a simple request
            params = {
                "latitude": 49.72,
                "longitude": -118.93,
                "current": "temperature_2m",
            }
            response = requests.get(self.base_url, params=params, timeout=10)
            return response.status_code == 200
        except Exception:
            return False
