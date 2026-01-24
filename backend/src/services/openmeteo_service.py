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
                # Past snowfall
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
        """Process snowfall data from daily and hourly responses."""
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
        }

        # Get daily snowfall sums
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
            # Past 3 days: indices before today
            # Today = today_index, yesterday = today_index - 1, etc.

            # Past snowfall (days before today)
            if today_index >= 1 and len(daily_snowfall) > today_index - 1:
                result["snowfall_24h"] = daily_snowfall[today_index - 1] or 0.0
            if today_index >= 2 and len(daily_snowfall) > today_index - 2:
                result["snowfall_48h"] = result["snowfall_24h"] + (
                    daily_snowfall[today_index - 2] or 0.0
                )
            if today_index >= 3 and len(daily_snowfall) > today_index - 3:
                result["snowfall_72h"] = result["snowfall_48h"] + (
                    daily_snowfall[today_index - 3] or 0.0
                )

            # Future predictions (today and after)
            if len(daily_snowfall) > today_index:
                result["predicted_24h"] = daily_snowfall[today_index] or 0.0
            if len(daily_snowfall) > today_index + 1:
                result["predicted_48h"] = result["predicted_24h"] + (
                    daily_snowfall[today_index + 1] or 0.0
                )
            if len(daily_snowfall) > today_index + 2:
                result["predicted_72h"] = result["predicted_48h"] + (
                    daily_snowfall[today_index + 2] or 0.0
                )

            # Temperature range for today
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
