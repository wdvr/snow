"""Weather data service for fetching and processing weather information."""

from typing import Any, Dict, List, Optional

import requests

from models.weather import ConfidenceLevel, WeatherCondition


class WeatherService:
    """Service for fetching weather data from external APIs."""

    def __init__(self, api_key: str):
        """Initialize the weather service with API credentials."""
        self.api_key = api_key
        self.base_url = "https://api.weatherapi.com/v1"

    def get_current_weather(
        self, latitude: float, longitude: float, elevation_meters: int
    ) -> dict[str, Any]:
        """
        Fetch current weather data for a specific location.

        Returns a dictionary suitable for creating a WeatherCondition object.
        """
        try:
            # Construct API request
            url = f"{self.base_url}/current.json"
            params = {"key": self.api_key, "q": f"{latitude},{longitude}", "aqi": "no"}

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()
            current = data["current"]
            location = data["location"]

            # Also fetch forecast for snow data
            forecast_data = self._get_forecast_data(latitude, longitude, days=3)

            # Extract relevant weather information
            weather_data = {
                "current_temp_celsius": current["temp_c"],
                "min_temp_celsius": forecast_data.get(
                    "min_temp_24h", current["temp_c"] - 2
                ),
                "max_temp_celsius": forecast_data.get(
                    "max_temp_24h", current["temp_c"] + 2
                ),
                "snowfall_24h_cm": forecast_data.get("snowfall_24h", 0.0),
                "snowfall_48h_cm": forecast_data.get("snowfall_48h", 0.0),
                "snowfall_72h_cm": forecast_data.get("snowfall_72h", 0.0),
                "hours_above_ice_threshold": self._calculate_ice_hours(forecast_data),
                "max_consecutive_warm_hours": self._calculate_max_warm_hours(
                    forecast_data
                ),
                "humidity_percent": current["humidity"],
                "wind_speed_kmh": current["wind_kph"],
                "weather_description": current["condition"]["text"],
                "data_source": "weatherapi.com",
                "source_confidence": ConfidenceLevel.MEDIUM,
                "raw_data": {
                    "api_response": data,
                    "elevation_meters": elevation_meters,
                    "location_name": location["name"],
                },
            }

            return weather_data

        except requests.exceptions.RequestException as e:
            raise Exception(f"Failed to fetch weather data: {str(e)}")
        except KeyError as e:
            raise Exception(f"Unexpected weather API response format: missing {str(e)}")
        except Exception as e:
            raise Exception(f"Error processing weather data: {str(e)}")

    def _get_forecast_data(
        self, latitude: float, longitude: float, days: int = 3
    ) -> dict[str, Any]:
        """Fetch forecast data for snowfall and temperature analysis."""
        try:
            url = f"{self.base_url}/forecast.json"
            params = {
                "key": self.api_key,
                "q": f"{latitude},{longitude}",
                "days": days,
                "aqi": "no",
                "alerts": "no",
            }

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()
            forecast_days = data["forecast"]["forecastday"]

            # Process forecast data
            snowfall_24h = 0.0
            snowfall_48h = 0.0
            snowfall_72h = 0.0
            min_temp_24h = float("inf")
            max_temp_24h = float("-inf")
            hourly_temps = []

            for i, day in enumerate(forecast_days):
                day_snow = day["day"].get("totalsnow_cm", 0.0)

                if i == 0:  # Today
                    snowfall_24h = day_snow
                    min_temp_24h = min(min_temp_24h, day["day"]["mintemp_c"])
                    max_temp_24h = max(max_temp_24h, day["day"]["maxtemp_c"])

                if i <= 1:  # Today + yesterday
                    snowfall_48h += day_snow

                snowfall_72h += day_snow

                # Collect hourly temperatures for ice analysis
                for hour in day.get("hour", []):
                    hourly_temps.append(hour["temp_c"])

            return {
                "snowfall_24h": snowfall_24h,
                "snowfall_48h": snowfall_48h,
                "snowfall_72h": snowfall_72h,
                "min_temp_24h": min_temp_24h if min_temp_24h != float("inf") else None,
                "max_temp_24h": max_temp_24h if max_temp_24h != float("-inf") else None,
                "hourly_temperatures": hourly_temps,
            }

        except Exception:
            # Return empty forecast data if forecast fails
            return {
                "snowfall_24h": 0.0,
                "snowfall_48h": 0.0,
                "snowfall_72h": 0.0,
                "hourly_temperatures": [],
            }

    def _calculate_ice_hours(
        self, forecast_data: dict[str, Any], threshold_temp: float = 3.0
    ) -> float:
        """Calculate hours spent above ice formation threshold."""
        hourly_temps = forecast_data.get("hourly_temperatures", [])
        if not hourly_temps:
            return 0.0

        # Count hours above threshold in the last 24 hours
        recent_temps = hourly_temps[-24:] if len(hourly_temps) >= 24 else hourly_temps
        hours_above_threshold = sum(
            1 for temp in recent_temps if temp >= threshold_temp
        )

        return float(hours_above_threshold)

    def _calculate_max_warm_hours(
        self, forecast_data: dict[str, Any], threshold_temp: float = 0.0
    ) -> float:
        """Calculate maximum consecutive hours above freezing."""
        hourly_temps = forecast_data.get("hourly_temperatures", [])
        if not hourly_temps:
            return 0.0

        max_consecutive = 0
        current_consecutive = 0

        for temp in hourly_temps[-24:]:  # Last 24 hours
            if temp >= threshold_temp:
                current_consecutive += 1
                max_consecutive = max(max_consecutive, current_consecutive)
            else:
                current_consecutive = 0

        return float(max_consecutive)

    def get_conditions_for_resort(
        self, resort_id: str, hours_back: int = 24
    ) -> list[WeatherCondition]:
        """Get historical conditions for a resort (placeholder for database query)."""
        # TODO: Implement database query to fetch historical conditions
        # This would query the weather_conditions DynamoDB table
        return []

    def get_latest_condition(
        self, resort_id: str, elevation_level: str
    ) -> WeatherCondition | None:
        """Get the latest condition for a specific resort and elevation (placeholder)."""
        # TODO: Implement database query to fetch latest condition
        return None

    def get_weather_forecast(
        self, latitude: float, longitude: float, days: int = 7
    ) -> dict[str, Any]:
        """Get extended weather forecast for planning purposes."""
        try:
            url = f"{self.base_url}/forecast.json"
            params = {
                "key": self.api_key,
                "q": f"{latitude},{longitude}",
                "days": min(days, 10),  # API limit
                "aqi": "no",
                "alerts": "yes",
            }

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()

            data = response.json()
            return {
                "forecast": data["forecast"],
                "location": data["location"],
                "alerts": data.get("alerts", {}),
            }

        except Exception as e:
            raise Exception(f"Failed to fetch weather forecast: {str(e)}")

    def validate_api_key(self) -> bool:
        """Validate that the API key is working."""
        try:
            # Test with a simple request
            url = f"{self.base_url}/current.json"
            params = {
                "key": self.api_key,
                "q": "49.7167,-118.9333",  # Big White coordinates
                "aqi": "no",
            }

            response = requests.get(url, params=params, timeout=10)
            return response.status_code == 200

        except Exception:
            return False
