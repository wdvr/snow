"""Open-Meteo weather data service for accurate elevation-aware weather data."""

import logging
import time
from datetime import UTC, datetime, timedelta
from typing import Any

import requests

from models.weather import ConfidenceLevel, SnowQuality, WeatherCondition

logger = logging.getLogger(__name__)


# Retry configuration for API calls
MAX_RETRIES = 3
RETRY_DELAYS = [1, 2, 4]  # Exponential backoff: 1s, 2s, 4s
RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _is_retryable_error(exception: Exception) -> bool:
    """Check if an exception is retryable."""
    if isinstance(exception, requests.exceptions.Timeout):
        return True
    if isinstance(exception, requests.exceptions.ConnectionError):
        return True
    if isinstance(exception, requests.exceptions.HTTPError):
        response = exception.response
        if response is not None and response.status_code in RETRYABLE_STATUS_CODES:
            return True
    return False


def _request_with_retry(
    method: str,
    url: str,
    **kwargs,
) -> requests.Response:
    """Make an HTTP request with retry logic and exponential backoff.

    Args:
        method: HTTP method (GET, POST, etc.)
        url: Request URL
        **kwargs: Additional arguments passed to requests

    Returns:
        Response object

    Raises:
        requests.exceptions.RequestException: If all retries fail
    """
    last_exception = None

    for attempt in range(MAX_RETRIES):
        try:
            response = requests.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            last_exception = e
            if not _is_retryable_error(e) or attempt == MAX_RETRIES - 1:
                raise

            delay = RETRY_DELAYS[attempt]
            logger.warning(
                f"Request to {url} failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}. "
                f"Retrying in {delay}s..."
            )
            time.sleep(delay)

    # This shouldn't be reached, but just in case
    raise last_exception


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
        self,
        latitude: float,
        longitude: float,
        elevation_meters: int,
        last_known_freeze_date: str | None = None,
    ) -> dict[str, Any]:
        """
        Fetch current weather data for a specific location and elevation.

        Args:
            latitude: Location latitude
            longitude: Location longitude
            elevation_meters: Elevation in meters
            last_known_freeze_date: Optional ISO timestamp of last known freeze event
                from the snow summary table. If provided and older than 14 days,
                we use it instead of searching Open-Meteo history.

        Returns a dictionary suitable for creating a WeatherCondition object.
        """
        try:
            # Fetch 14 days of historical data for accurate freeze-thaw detection
            # Ice events can occur up to 2 weeks ago but still affect current snow quality
            params = {
                "latitude": latitude,
                "longitude": longitude,
                "elevation": elevation_meters,
                "current": "temperature_2m,relative_humidity_2m,wind_speed_10m,weather_code",
                "hourly": "temperature_2m,snowfall,snow_depth",
                "daily": "temperature_2m_min,temperature_2m_max,snowfall_sum",
                "past_days": 14,  # Need 14 days for freeze-thaw detection
                "forecast_days": 3,
                "timezone": "GMT",  # Use GMT so timestamps match datetime.now(UTC)
            }

            response = _request_with_retry(
                "GET", self.base_url, params=params, timeout=10
            )

            data = response.json()

            # Process the response
            current = data.get("current", {})
            hourly = data.get("hourly", {})
            daily = data.get("daily", {})

            # Calculate snowfall from daily data
            snowfall_data = self._process_snowfall(
                daily, hourly, last_known_freeze_date
            )

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
                # Current snow depth on ground (total, not just fresh)
                "snow_depth_cm": snowfall_data.get("current_snow_depth"),
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

    def get_timeline_data(
        self,
        latitude: float,
        longitude: float,
        elevation_meters: int,
        elevation_level: str = "mid",
        timezone: str = "GMT",
    ) -> dict[str, Any]:
        """
        Fetch timeline data for a location showing 3 data points per day
        (morning, midday, afternoon) over 7 days past and 7 days forecast.

        Args:
            latitude: Location latitude
            longitude: Location longitude
            elevation_meters: Elevation in meters
            elevation_level: base, mid, or top
            timezone: Timezone string (default GMT)

        Returns a dictionary with timeline points and metadata.
        """
        try:
            params = {
                "latitude": latitude,
                "longitude": longitude,
                "elevation": elevation_meters,
                "hourly": "temperature_2m,snowfall,snow_depth,wind_speed_10m,weather_code",
                "past_days": 7,
                "forecast_days": 7,
                "timezone": timezone,
            }

            response = _request_with_retry(
                "GET", self.base_url, params=params, timeout=10
            )

            data = response.json()
            hourly = data.get("hourly", {})

            hourly_times = hourly.get("time", [])
            hourly_temps = hourly.get("temperature_2m", [])
            hourly_snowfall = hourly.get("snowfall", [])
            hourly_snow_depth = hourly.get("snow_depth", [])
            hourly_wind = hourly.get("wind_speed_10m", [])
            hourly_weather_code = hourly.get("weather_code", [])

            now = datetime.now(UTC)

            # Define the 3 windows per day
            windows = [
                ("morning", 7, 5, 9),
                ("midday", 12, 10, 14),
                ("afternoon", 16, 14, 18),
            ]

            # Build a mapping from (date, hour) -> index for quick lookups
            time_index_map = {}
            for i, t in enumerate(hourly_times):
                # hourly_times are like "2026-02-13T07:00"
                time_index_map[t[:13]] = i  # key: "2026-02-13T07"

            # Collect unique dates
            dates_seen = []
            for t in hourly_times:
                d = t[:10]
                if not dates_seen or dates_seen[-1] != d:
                    dates_seen.append(d)

            # Import SnowQualityService inside method to avoid circular imports
            from services.snow_quality_service import SnowQualityService

            snow_quality_service = SnowQualityService()

            timeline_points = []

            for date_str in dates_seen:
                for time_label, hour, window_start, window_end in windows:
                    # Build the key to find the index
                    key = f"{date_str}T{hour:02d}"
                    idx = time_index_map.get(key)
                    if idx is None:
                        continue

                    # Temperature at that hour
                    temp = (
                        hourly_temps[idx]
                        if idx < len(hourly_temps) and hourly_temps[idx] is not None
                        else 0.0
                    )

                    # Wind speed at that hour
                    wind = (
                        hourly_wind[idx]
                        if idx < len(hourly_wind) and hourly_wind[idx] is not None
                        else None
                    )

                    # Sum snowfall in the surrounding window
                    snowfall_sum = 0.0
                    for h in range(window_start, window_end + 1):
                        window_key = f"{date_str}T{h:02d}"
                        widx = time_index_map.get(window_key)
                        if (
                            widx is not None
                            and widx < len(hourly_snowfall)
                            and hourly_snowfall[widx] is not None
                        ):
                            snowfall_sum += hourly_snowfall[widx]

                    # Snow depth at that hour (convert from meters to cm)
                    snow_depth = None
                    if (
                        idx < len(hourly_snow_depth)
                        and hourly_snow_depth[idx] is not None
                    ):
                        snow_depth = hourly_snow_depth[idx] * 100  # m -> cm

                    # Weather code and description
                    wcode = (
                        hourly_weather_code[idx]
                        if idx < len(hourly_weather_code)
                        and hourly_weather_code[idx] is not None
                        else None
                    )
                    wdesc = (
                        self._weather_code_to_description(wcode)
                        if wcode is not None
                        else None
                    )

                    # Determine if this is forecast (hour is in the future)
                    # Parse the timestamp to compare with now
                    timestamp_str = hourly_times[idx]
                    try:
                        point_time = datetime.fromisoformat(
                            timestamp_str.replace("Z", "+00:00")
                        )
                        # If timezone is not GMT, the timestamps won't have tzinfo
                        # Make them tz-aware for comparison
                        if point_time.tzinfo is None:
                            # Treat as UTC for comparison purposes
                            from datetime import timezone as tz

                            point_time = point_time.replace(tzinfo=UTC)
                        is_forecast = point_time > now
                    except (ValueError, TypeError):
                        is_forecast = False

                    # Calculate snow quality using SnowQualityService
                    weather_condition = WeatherCondition(
                        resort_id="timeline",
                        elevation_level=elevation_level,
                        timestamp=timestamp_str,
                        current_temp_celsius=temp,
                        min_temp_celsius=temp,
                        max_temp_celsius=temp,
                        snowfall_24h_cm=snowfall_sum,
                        snowfall_48h_cm=0.0,
                        snowfall_72h_cm=0.0,
                        snow_depth_cm=snow_depth,
                        snowfall_after_freeze_cm=snowfall_sum,
                        data_source="open-meteo.com",
                        source_confidence=ConfidenceLevel.MEDIUM,
                    )

                    quality, _, _ = snow_quality_service.assess_snow_quality(
                        weather_condition
                    )

                    point = {
                        "date": date_str,
                        "time_label": time_label,
                        "hour": hour,
                        "timestamp": timestamp_str,
                        "temperature_c": temp,
                        "wind_speed_kmh": wind,
                        "snowfall_cm": round(snowfall_sum, 2),
                        "snow_depth_cm": round(snow_depth, 1)
                        if snow_depth is not None
                        else None,
                        "snow_quality": quality.value
                        if hasattr(quality, "value")
                        else str(quality),
                        "weather_code": wcode,
                        "weather_description": wdesc,
                        "is_forecast": is_forecast,
                    }

                    timeline_points.append(point)

            return {
                "timeline": timeline_points,
                "elevation_level": elevation_level,
                "elevation_meters": elevation_meters,
            }

        except requests.exceptions.RequestException as e:
            logger.error(f"Open-Meteo API request failed for timeline: {str(e)}")
            raise Exception(f"Failed to fetch timeline data: {str(e)}")
        except Exception as e:
            logger.error(f"Error processing timeline data: {str(e)}")
            raise Exception(f"Error processing timeline data: {str(e)}")

    def _process_snowfall(
        self, daily: dict, hourly: dict, last_known_freeze_date: str | None = None
    ) -> dict[str, float]:
        """Process snowfall data using hourly data for accurate rolling windows.

        Uses hourly snowfall data to calculate true rolling 24h/48h/72h windows
        instead of calendar-day sums, which is more accurate for detecting recent snowfall.

        Also detects freeze-thaw events up to 14 days back for accurate fresh powder tracking.
        If last_known_freeze_date is provided and is older than 14 days, we use that
        as the freeze reference point instead of searching Open-Meteo history.

        Args:
            daily: Daily weather data from Open-Meteo
            hourly: Hourly weather data from Open-Meteo
            last_known_freeze_date: Optional ISO timestamp of last known freeze from snow summary

        Returns:
            dict containing snowfall metrics and freeze_event_detected flag
        """
        # Maximum hours to look back for freeze-thaw detection (14 days)
        MAX_HISTORICAL_HOURS = 336

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
            # Fields for fresh powder detection (freeze-thaw tracking)
            "snowfall_after_freeze_cm": 0.0,
            "hours_since_last_snowfall": None,
            "last_freeze_thaw_hours_ago": None,
            # New field: indicates if a NEW freeze event was detected in Open-Meteo data
            "freeze_event_detected": False,
            # Store the detected freeze date for updating snow summary
            "detected_freeze_date": None,
        }

        # Parse last_known_freeze_date if provided
        known_freeze_datetime = None
        known_freeze_hours_ago = None
        if last_known_freeze_date:
            try:
                known_freeze_datetime = datetime.fromisoformat(
                    last_known_freeze_date.replace("Z", "+00:00")
                )
                known_freeze_hours_ago = (
                    datetime.now(UTC) - known_freeze_datetime
                ).total_seconds() / 3600
            except (ValueError, TypeError):
                pass  # Invalid date, ignore

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
            # For freeze-thaw detection, look back up to 14 days
            start_historical = max(0, current_index - MAX_HISTORICAL_HOURS)

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
                (3.0, 3),  # 3 hours at +3°C (hard ice fast)
                (2.0, 6),  # 6 hours at +2°C
                (1.0, 8),  # 8 hours at +1°C
                (0.0, 4),  # 4 hours above 0°C (surface crust formation)
            ]

            # Find the last "ice formation event" using multi-threshold detection
            # An ice event occurs when ANY threshold is met
            # Search up to 14 days back for accurate freeze-thaw tracking
            last_ice_event_end_index = None

            # Start from current_index - 1 to only detect COMPLETED ice events.
            # Starting at current_index would detect "ongoing" warming as a freeze
            # event, resetting snowfall_after_freeze to 0 during any warm period
            # and corrupting the persistent snow summary in DynamoDB.
            search_start = max(current_index - 1, start_historical)

            # Track consecutive hours at each threshold level
            for i in range(search_start, start_historical - 1, -1):
                if i >= len(hourly_temps) or hourly_temps[i] is None:
                    continue

                temp = hourly_temps[i]

                # Check each threshold - look backwards for consecutive hours
                for threshold_temp, required_hours in ICE_THRESHOLDS:
                    if temp >= threshold_temp:
                        # Count consecutive hours at or above this threshold
                        consecutive = 0
                        for j in range(
                            i, max(start_historical - 1, i - required_hours - 1), -1
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
                # Found a freeze event in Open-Meteo data (within 14 days)
                detected_freeze_hours_ago = float(
                    current_index - last_ice_event_end_index
                )
                result["last_freeze_thaw_hours_ago"] = detected_freeze_hours_ago

                # Determine the detected freeze date for snow summary updates
                if hourly_times and last_ice_event_end_index < len(hourly_times):
                    result["detected_freeze_date"] = hourly_times[
                        last_ice_event_end_index
                    ]

                # Check if this is a NEW freeze event (more recent than known freeze)
                if (
                    known_freeze_hours_ago is None
                    or detected_freeze_hours_ago < known_freeze_hours_ago
                ):
                    result["freeze_event_detected"] = True
                    logger.debug(
                        f"New freeze event detected {detected_freeze_hours_ago:.0f}h ago "
                        f"(known: {known_freeze_hours_ago}h ago)"
                        if known_freeze_hours_ago
                        else f"New freeze event detected {detected_freeze_hours_ago:.0f}h ago (no prior known)"
                    )

                # Sum snowfall AFTER the ice formation event (this is non-refrozen snow!)
                for i in range(last_ice_event_end_index + 1, current_index + 1):
                    if i < len(hourly_snowfall) and hourly_snowfall[i] is not None:
                        result["snowfall_after_freeze_cm"] += hourly_snowfall[i]
            else:
                # No ice formation event found in Open-Meteo data (last 14 days)
                # Check if we have a known freeze date from snow summary
                if (
                    known_freeze_hours_ago is not None
                    and known_freeze_hours_ago > MAX_HISTORICAL_HOURS
                ):
                    # Known freeze is older than 14 days - use it as reference
                    # All snowfall in our 14-day window is "after freeze"
                    result["last_freeze_thaw_hours_ago"] = known_freeze_hours_ago
                    total_historical_snow = sum(
                        s
                        for s in hourly_snowfall[start_historical : current_index + 1]
                        if s is not None
                    )
                    result["snowfall_after_freeze_cm"] = total_historical_snow
                    # No new freeze detected - use known date
                    result["freeze_event_detected"] = False
                else:
                    # No ice formation event in last 14 days and no known freeze
                    # This means potentially unlimited accumulation!
                    total_historical_snow = sum(
                        s
                        for s in hourly_snowfall[start_historical : current_index + 1]
                        if s is not None
                    )
                    result["snowfall_after_freeze_cm"] = total_historical_snow
                    # Use known freeze hours or max historical if no known freeze
                    result["last_freeze_thaw_hours_ago"] = (
                        known_freeze_hours_ago
                        if known_freeze_hours_ago is not None
                        else float(MAX_HISTORICAL_HOURS)
                    )
                    result["freeze_event_detected"] = False

            # Also track if we're currently in a warming period (ice forming now)
            # Use lowest threshold (1°C) - any temp >= 1°C can form ice given enough time
            WARMING_THRESHOLD = 1.0
            result["currently_warming"] = (
                hourly_temps[current_index] >= WARMING_THRESHOLD
                if current_index < len(hourly_temps)
                and hourly_temps[current_index] is not None
                else False
            )

            # Find hours since last snowfall (search up to 14 days)
            for i in range(current_index, start_historical - 1, -1):
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

        # Get current snow depth from hourly data at current time
        # IMPORTANT: Do NOT use reversed() on the full array - that picks up
        # future forecast values (3 days ahead) instead of current conditions.
        # Search backwards from current hour to find the most recent actual value.
        hourly_snow_depth = hourly.get("snow_depth", [])
        if hourly_snow_depth:
            # Find current hour index for snow depth lookup
            hourly_times_for_depth = hourly.get("time", [])
            depth_current_index = len(hourly_snow_depth) - 1
            if hourly_times_for_depth:
                now_depth = datetime.now(UTC)
                now_depth_str = now_depth.strftime("%Y-%m-%dT%H:00")
                for i, time_str in enumerate(hourly_times_for_depth):
                    if time_str[:13] >= now_depth_str[:13]:
                        depth_current_index = i
                        break

            # Search backwards from current hour (not from end of forecast)
            for i in range(depth_current_index, -1, -1):
                if i < len(hourly_snow_depth) and hourly_snow_depth[i] is not None:
                    result["current_snow_depth"] = (
                        hourly_snow_depth[i] * 100
                    )  # Convert m to cm
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

        for i, t in enumerate(times):
            if t[:13] == now:
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
                "timezone": "GMT",  # Use GMT so timestamps match datetime.now(UTC)
            }

            response = _request_with_retry(
                "GET", self.era5_url, params=params, timeout=15
            )

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
            response = _request_with_retry(
                "GET", self.base_url, params=params, timeout=10
            )
            return True
        except Exception:
            return False
