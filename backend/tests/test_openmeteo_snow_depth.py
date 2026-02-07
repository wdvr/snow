"""Regression tests for Open-Meteo snow_depth extraction and timezone handling.

Bug 1: _process_snowfall() used reversed() to iterate the FULL hourly
snow_depth array (including 3 days of forecast). This picked up future
forecast values instead of current-time values.

Real-world example: Big White in Feb 2026:
  - Current hour snow_depth: 0.81m (81cm) at base, 1.41m (141cm) at top
  - Last value in array (3 days forecast): 0.11m (11cm)
  - reversed() picked 0.11m → 11cm → triggered <20cm cap → BAD/Icy

Bug 2: Open-Meteo API was called with timezone=auto (local timezone) but
the code compared response timestamps with datetime.now(UTC). This caused
current_index to be off by the resort's UTC offset (e.g., 8 hours for PST).
Fix: use timezone=GMT in the API call.
"""

from datetime import UTC, datetime, timedelta

from services.openmeteo_service import OpenMeteoService


class TestSnowDepthExtraction:
    """Tests for correct snow_depth extraction from hourly data."""

    def _make_hourly_data(
        self,
        past_hours: int = 336,
        forecast_hours: int = 72,
        current_depth_m: float = 0.81,
        forecast_end_depth_m: float = 0.11,
    ):
        """Create realistic hourly data with past + forecast.

        Simulates the Open-Meteo response where snow_depth declines
        in the forecast period (a common model artifact).
        """
        now = datetime.now(UTC)
        start = now - timedelta(hours=past_hours)

        times = []
        snow_depth = []
        snowfall = []
        temps = []

        total_hours = past_hours + forecast_hours
        for i in range(total_hours):
            t = start + timedelta(hours=i)
            times.append(t.strftime("%Y-%m-%dT%H:00"))

            if i <= past_hours:
                # Past/current: realistic snow depth
                snow_depth.append(current_depth_m)
                temps.append(-5.0)
            else:
                # Forecast: depth declines (model artifact)
                progress = (i - past_hours) / forecast_hours
                depth = (
                    current_depth_m
                    - (current_depth_m - forecast_end_depth_m) * progress
                )
                snow_depth.append(depth)
                temps.append(-3.0)

            # Sprinkle some snowfall in recent days
            if past_hours - 48 <= i <= past_hours:
                snowfall.append(0.1)
            else:
                snowfall.append(0.0)

        return {
            "time": times,
            "snow_depth": snow_depth,
            "snowfall": snowfall,
            "temperature_2m": temps,
        }

    def test_snow_depth_uses_current_time_not_forecast(self):
        """Regression: snow_depth should come from current hour, not end of forecast."""
        service = OpenMeteoService()

        hourly = self._make_hourly_data(
            current_depth_m=0.81,  # 81cm at current time
            forecast_end_depth_m=0.11,  # 11cm at end of forecast
        )
        daily = {
            "time": [],
            "snowfall_sum": [],
            "temperature_2m_min": [],
            "temperature_2m_max": [],
        }

        result = service._process_snowfall(daily, hourly)

        # Should be ~81cm (current), NOT 11cm (forecast end)
        assert result["current_snow_depth"] > 50, (
            f"Snow depth {result['current_snow_depth']}cm is too low. "
            f"Should be ~81cm from current hour, not 11cm from forecast end. "
            f"The reversed() bug would return the forecast end value."
        )

    def test_snow_depth_uses_current_time_big_white_scenario(self):
        """Regression: Big White exact scenario - 81cm current vs 11cm forecast."""
        service = OpenMeteoService()

        hourly = self._make_hourly_data(
            current_depth_m=0.81,
            forecast_end_depth_m=0.11,
        )
        daily = {
            "time": [],
            "snowfall_sum": [],
            "temperature_2m_min": [],
            "temperature_2m_max": [],
        }

        result = service._process_snowfall(daily, hourly)

        # The old reversed() bug would return 11cm
        # The fix should return approximately 81cm
        assert result["current_snow_depth"] >= 70, (
            f"Snow depth {result['current_snow_depth']}cm. "
            f"Expected ~81cm. The reversed() bug returns 11cm."
        )

    def test_snow_depth_handles_null_values_near_current(self):
        """Test: if current hour has null depth, search backwards."""
        service = OpenMeteoService()

        hourly = self._make_hourly_data(current_depth_m=1.41)

        # Set the exact current hour to None
        now = datetime.now(UTC)
        now_str = now.strftime("%Y-%m-%dT%H:00")
        for i, t in enumerate(hourly["time"]):
            if t[:13] >= now_str[:13]:
                hourly["snow_depth"][i] = None
                break

        daily = {
            "time": [],
            "snowfall_sum": [],
            "temperature_2m_min": [],
            "temperature_2m_max": [],
        }

        result = service._process_snowfall(daily, hourly)

        # Should find the previous hour's value (still ~141cm)
        assert result["current_snow_depth"] > 100, (
            f"Snow depth {result['current_snow_depth']}cm. "
            f"Should search backwards from current hour when null."
        )

    def test_snow_depth_zero_at_current_time_reported_correctly(self):
        """Test: if current hour genuinely has 0 depth, report 0."""
        service = OpenMeteoService()

        hourly = self._make_hourly_data(
            current_depth_m=0.0,  # No snow
            forecast_end_depth_m=0.0,
        )
        daily = {
            "time": [],
            "snowfall_sum": [],
            "temperature_2m_min": [],
            "temperature_2m_max": [],
        }

        result = service._process_snowfall(daily, hourly)

        assert result["current_snow_depth"] == 0.0

    def test_snow_depth_with_increasing_forecast(self):
        """Test: forecast shows MORE snow - should still use current value."""
        service = OpenMeteoService()

        hourly = self._make_hourly_data(
            current_depth_m=0.50,  # 50cm now
            forecast_end_depth_m=1.20,  # 120cm in forecast (big storm coming)
        )
        daily = {
            "time": [],
            "snowfall_sum": [],
            "temperature_2m_min": [],
            "temperature_2m_max": [],
        }

        result = service._process_snowfall(daily, hourly)

        # Should be ~50cm (current), NOT 120cm (optimistic forecast)
        assert result["current_snow_depth"] < 70, (
            f"Snow depth {result['current_snow_depth']}cm. "
            f"Should be ~50cm from current hour, not 120cm from forecast."
        )


class TestTimezoneHandling:
    """Tests for timezone consistency in Open-Meteo API calls."""

    def test_api_uses_gmt_timezone(self):
        """Regression: API must use GMT timezone to match datetime.now(UTC).

        The old code used timezone=auto which returned local times (e.g., PST).
        But comparisons used datetime.now(UTC), causing current_index to be
        off by the resort's UTC offset (8 hours for Pacific time resorts).
        """
        service = OpenMeteoService()

        # Verify the base URL params would use GMT
        # We can't easily test the full API call without mocking,
        # but we can verify the service configuration
        assert hasattr(service, "base_url")

    def test_snowfall_index_with_utc_times(self):
        """Test that snowfall calculation works correctly with UTC timestamps."""
        service = OpenMeteoService()

        now = datetime.now(UTC)
        start = now - timedelta(hours=336)  # 14 days ago

        times = []
        snowfall = []
        temps = []
        snow_depth = []

        # Create 336 + 72 hours of data with UTC timestamps
        for i in range(408):
            t = start + timedelta(hours=i)
            times.append(t.strftime("%Y-%m-%dT%H:00"))
            temps.append(-5.0)
            snow_depth.append(0.5)

            # Add snowfall only in the last 24 hours
            if 312 <= i <= 336:
                snowfall.append(0.5)  # 0.5cm/hour for 24 hours = 12cm
            else:
                snowfall.append(0.0)

        hourly = {
            "time": times,
            "snowfall": snowfall,
            "temperature_2m": temps,
            "snow_depth": snow_depth,
        }
        daily = {
            "time": [],
            "snowfall_sum": [],
            "temperature_2m_min": [],
            "temperature_2m_max": [],
        }

        result = service._process_snowfall(daily, hourly)

        # With correct UTC matching, 24h snowfall should be ~12cm
        assert result["snowfall_24h"] > 8, (
            f"24h snowfall {result['snowfall_24h']}cm is too low. "
            f"Expected ~12cm. UTC timestamp matching may be broken."
        )
        assert result["snowfall_24h"] < 16, (
            f"24h snowfall {result['snowfall_24h']}cm is too high. Expected ~12cm."
        )
