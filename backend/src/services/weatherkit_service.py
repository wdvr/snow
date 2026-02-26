"""Apple WeatherKit REST API service for supplementary weather data.

WeatherKit provides snowfall amounts and precipitation type data
as a supplementary source to Open-Meteo's grid-based forecasts.
"""

import base64
import logging
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt  # PyJWT
import requests

logger = logging.getLogger(__name__)


@dataclass
class WeatherKitData:
    """Weather data from Apple WeatherKit."""

    resort_id: str
    snowfall_24h_mm: float | None  # WeatherKit reports in mm
    precipitation_type: str | None  # "snow", "rain", "mixed", etc.
    temperature_c: float | None
    source_url: str = "weatherkit.apple.com"

    @property
    def snowfall_24h_cm(self) -> float | None:
        """Convert mm to cm."""
        return self.snowfall_24h_mm / 10.0 if self.snowfall_24h_mm is not None else None


class WeatherKitService:
    """Apple WeatherKit REST API client."""

    BASE_URL = "https://weatherkit.apple.com/api/v1"

    def __init__(self):
        self.key_id = os.environ.get("WEATHERKIT_KEY_ID")
        self.team_id = os.environ.get("WEATHERKIT_TEAM_ID")
        self.service_id = os.environ.get("WEATHERKIT_SERVICE_ID")
        # Accept WEATHERKIT_PRIVATE_KEY or fall back to APNS_PRIVATE_KEY (same .p8 key)
        private_key_raw = os.environ.get("WEATHERKIT_PRIVATE_KEY") or os.environ.get(
            "APNS_PRIVATE_KEY", ""
        )

        self.private_key = None
        if private_key_raw:
            # Accept both raw PEM and base64-encoded formats
            if private_key_raw.startswith("-----BEGIN"):
                self.private_key = private_key_raw
            else:
                try:
                    self.private_key = base64.b64decode(private_key_raw).decode("utf-8")
                except Exception as e:
                    logger.warning(f"Failed to decode WeatherKit private key: {e}")

        self._jwt_token = None
        self._jwt_expiry = 0
        self.configured = all(
            [self.key_id, self.team_id, self.service_id, self.private_key]
        )

        if not self.configured:
            logger.info("WeatherKit not configured - missing credentials")

        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
            }
        )

    def _get_jwt_token(self) -> str:
        """Generate or return cached ES256 JWT for WeatherKit auth."""
        now = time.time()
        if self._jwt_token and now < self._jwt_expiry - 60:  # 60s buffer
            return self._jwt_token

        # Generate new JWT valid for 1 hour
        expiry = now + 3600
        payload = {
            "iss": self.team_id,
            "iat": int(now),
            "exp": int(expiry),
            "sub": self.service_id,
        }
        headers = {
            "kid": self.key_id,
            "id": f"{self.team_id}.{self.service_id}",
        }

        self._jwt_token = jwt.encode(
            payload, self.private_key, algorithm="ES256", headers=headers
        )
        self._jwt_expiry = expiry
        return self._jwt_token

    def get_weather(
        self, latitude: float, longitude: float, resort_id: str = ""
    ) -> WeatherKitData | None:
        """Fetch weather data from WeatherKit for a location.

        Returns WeatherKitData or None if not configured or on error.
        """
        if not self.configured:
            return None

        try:
            token = self._get_jwt_token()

            # Request current weather + hourly forecast
            url = f"{self.BASE_URL}/weather/en/{latitude}/{longitude}"
            params = {
                "dataSets": "currentWeather,forecastHourly",
                "hourlyStart": (datetime.now(UTC) - timedelta(hours=24)).isoformat(),
                "hourlyEnd": datetime.now(UTC).isoformat(),
            }

            response = self.session.get(
                url,
                params=params,
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()

            return self._parse_response(data, resort_id)

        except requests.exceptions.HTTPError as e:
            body = e.response.text[:200] if e.response is not None else "no body"
            logger.warning(f"WeatherKit request failed for {resort_id}: {e} — {body}")
            return None
        except requests.exceptions.RequestException as e:
            logger.warning(f"WeatherKit request failed for {resort_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"WeatherKit error for {resort_id}: {e}")
            return None

    def _parse_response(self, data: dict, resort_id: str) -> WeatherKitData:
        """Parse WeatherKit API response into WeatherKitData."""
        # Current weather
        current = data.get("currentWeather", {})
        temperature_c = current.get("temperature")
        precip_type = current.get("precipitationType", "clear")

        # Sum snowfall from hourly forecast (past 24h)
        hourly = data.get("forecastHourly", {})
        hours = hourly.get("hours", [])

        total_snowfall_mm = 0.0
        has_snow_data = False

        for hour in hours:
            # WeatherKit provides precipitationAmount in mm
            precip_amount = hour.get("precipitationAmount", 0.0)
            hour_precip_type = hour.get("precipitationType", "clear")

            if hour_precip_type == "snow" and precip_amount > 0:
                # Snow water equivalent - approximate snowfall
                # Typical ratio is 1mm SWE = 10mm snow, but varies
                # Use conservative 1:8 ratio for wet mountain snow
                total_snowfall_mm += precip_amount * 8.0
                has_snow_data = True
            elif hour_precip_type == "mixed" and precip_amount > 0:
                # Mixed precipitation - assume half is snow
                total_snowfall_mm += precip_amount * 4.0
                has_snow_data = True

        return WeatherKitData(
            resort_id=resort_id,
            snowfall_24h_mm=total_snowfall_mm if has_snow_data else None,
            precipitation_type=precip_type,
            temperature_c=temperature_c,
        )
