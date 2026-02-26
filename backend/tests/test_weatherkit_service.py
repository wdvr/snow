"""Tests for Apple WeatherKit service."""

import time
from unittest.mock import MagicMock, patch

import pytest
import requests

from services.weatherkit_service import WeatherKitData, WeatherKitService

# Sample WeatherKit API response
SAMPLE_RESPONSE = {
    "currentWeather": {
        "temperature": -5.2,
        "precipitationType": "snow",
        "humidity": 0.85,
    },
    "forecastHourly": {
        "hours": [
            {
                "precipitationAmount": 2.0,
                "precipitationType": "snow",
            },
            {
                "precipitationAmount": 1.5,
                "precipitationType": "snow",
            },
            {
                "precipitationAmount": 0.0,
                "precipitationType": "clear",
            },
            {
                "precipitationAmount": 3.0,
                "precipitationType": "mixed",
            },
        ],
    },
}

SAMPLE_ENV = {
    "WEATHERKIT_KEY_ID": "TESTKEY123",
    "WEATHERKIT_TEAM_ID": "TEAM456",
    "WEATHERKIT_SERVICE_ID": "com.test.weatherkit",
    "WEATHERKIT_PRIVATE_KEY": "",  # Set in fixtures
}


@pytest.fixture
def mock_env(tmp_path):
    """Set up environment with mock credentials."""
    import base64

    # Generate a fake private key (base64-encoded PEM-like string)
    fake_key = (
        "-----BEGIN EC PRIVATE KEY-----\nfake_key_data\n-----END EC PRIVATE KEY-----"
    )
    fake_key_b64 = base64.b64encode(fake_key.encode()).decode()

    env = SAMPLE_ENV.copy()
    env["WEATHERKIT_PRIVATE_KEY"] = fake_key_b64

    with patch.dict("os.environ", env, clear=False):
        yield env


@pytest.fixture
def unconfigured_env():
    """Set up environment without WeatherKit credentials."""
    env = {
        "WEATHERKIT_KEY_ID": "",
        "WEATHERKIT_TEAM_ID": "",
        "WEATHERKIT_SERVICE_ID": "",
        "WEATHERKIT_PRIVATE_KEY": "",
    }
    with patch.dict("os.environ", env, clear=False):
        yield


class TestWeatherKitData:
    """Tests for WeatherKitData dataclass."""

    def test_snowfall_cm_conversion(self):
        data = WeatherKitData(
            resort_id="test",
            snowfall_24h_mm=100.0,
            precipitation_type="snow",
            temperature_c=-5.0,
        )
        assert data.snowfall_24h_cm == 10.0

    def test_snowfall_cm_conversion_none(self):
        data = WeatherKitData(
            resort_id="test",
            snowfall_24h_mm=None,
            precipitation_type="snow",
            temperature_c=-5.0,
        )
        assert data.snowfall_24h_cm is None

    def test_snowfall_cm_conversion_zero(self):
        data = WeatherKitData(
            resort_id="test",
            snowfall_24h_mm=0.0,
            precipitation_type="clear",
            temperature_c=-2.0,
        )
        assert data.snowfall_24h_cm == 0.0

    def test_default_source_url(self):
        data = WeatherKitData(
            resort_id="test",
            snowfall_24h_mm=50.0,
            precipitation_type="snow",
            temperature_c=-3.0,
        )
        assert data.source_url == "weatherkit.apple.com"

    def test_custom_source_url(self):
        data = WeatherKitData(
            resort_id="test",
            snowfall_24h_mm=50.0,
            precipitation_type="snow",
            temperature_c=-3.0,
            source_url="custom.source.com",
        )
        assert data.source_url == "custom.source.com"


class TestWeatherKitServiceInit:
    """Tests for WeatherKitService initialization."""

    def test_configured_when_all_env_vars_set(self, mock_env):
        service = WeatherKitService()
        assert service.configured is True
        assert service.key_id == "TESTKEY123"
        assert service.team_id == "TEAM456"
        assert service.service_id == "com.test.weatherkit"
        assert service.private_key is not None

    def test_not_configured_when_missing_env_vars(self, unconfigured_env):
        service = WeatherKitService()
        assert service.configured is False

    def test_not_configured_when_partial_env_vars(self):
        env = {"WEATHERKIT_KEY_ID": "key", "WEATHERKIT_TEAM_ID": "team"}
        with patch.dict("os.environ", env, clear=False):
            service = WeatherKitService()
            assert service.configured is False

    def test_invalid_base64_private_key(self):
        env = {
            "WEATHERKIT_KEY_ID": "key",
            "WEATHERKIT_TEAM_ID": "team",
            "WEATHERKIT_SERVICE_ID": "service",
            "WEATHERKIT_PRIVATE_KEY": "not-valid-base64!!!",
        }
        with patch.dict("os.environ", env, clear=False):
            # Should not raise, just log warning
            service = WeatherKitService()
            # private_key may or may not be set depending on base64 decode
            # but the service should initialize without error


class TestJWTGeneration:
    """Tests for JWT token generation and caching."""

    @patch("services.weatherkit_service.jwt.encode")
    def test_jwt_generation(self, mock_encode, mock_env):
        mock_encode.return_value = "test_jwt_token"
        service = WeatherKitService()

        token = service._get_jwt_token()

        assert token == "test_jwt_token"
        mock_encode.assert_called_once()

        # Verify the call arguments
        call_args = mock_encode.call_args
        payload = call_args[0][0]
        assert payload["iss"] == "TEAM456"
        assert payload["sub"] == "com.test.weatherkit"
        assert "iat" in payload
        assert "exp" in payload

        # Check headers
        headers = call_args[1]["headers"]
        assert headers["kid"] == "TESTKEY123"
        assert headers["id"] == "TEAM456.com.test.weatherkit"

        # Check algorithm
        assert call_args[1]["algorithm"] == "ES256"

    @patch("services.weatherkit_service.jwt.encode")
    def test_jwt_caching(self, mock_encode, mock_env):
        mock_encode.return_value = "cached_token"
        service = WeatherKitService()

        # First call generates token
        token1 = service._get_jwt_token()
        assert mock_encode.call_count == 1

        # Second call should return cached token
        token2 = service._get_jwt_token()
        assert mock_encode.call_count == 1  # Not called again
        assert token1 == token2

    @patch("services.weatherkit_service.jwt.encode")
    @patch("services.weatherkit_service.time.time")
    def test_jwt_refresh_when_expired(self, mock_time, mock_encode, mock_env):
        mock_encode.side_effect = ["token1", "token2"]

        service = WeatherKitService()

        # First call at t=1000
        mock_time.return_value = 1000
        token1 = service._get_jwt_token()
        assert token1 == "token1"

        # Second call at t=4600 (past expiry - 60s buffer)
        mock_time.return_value = 4600
        token2 = service._get_jwt_token()
        assert token2 == "token2"
        assert mock_encode.call_count == 2

    @patch("services.weatherkit_service.jwt.encode")
    @patch("services.weatherkit_service.time.time")
    def test_jwt_not_refreshed_within_buffer(self, mock_time, mock_encode, mock_env):
        mock_encode.return_value = "token1"

        service = WeatherKitService()

        # First call at t=1000, expiry = 1000 + 3600 = 4600
        mock_time.return_value = 1000
        service._get_jwt_token()

        # Second call at t=4500 (within 60s buffer: 4600 - 60 = 4540, 4500 < 4540)
        mock_time.return_value = 4500
        service._get_jwt_token()
        assert mock_encode.call_count == 1  # Still cached


class TestGetWeather:
    """Tests for the get_weather method."""

    def test_returns_none_when_not_configured(self, unconfigured_env):
        service = WeatherKitService()
        result = service.get_weather(46.0, 7.0, "zermatt")
        assert result is None

    @patch("services.weatherkit_service.jwt.encode")
    def test_successful_weather_fetch(self, mock_encode, mock_env):
        mock_encode.return_value = "test_token"
        service = WeatherKitService()

        mock_response = MagicMock()
        mock_response.json.return_value = SAMPLE_RESPONSE
        mock_response.raise_for_status = MagicMock()

        with patch.object(
            service.session, "get", return_value=mock_response
        ) as mock_get:
            result = service.get_weather(46.0, 7.0, "zermatt")

            assert result is not None
            assert result.resort_id == "zermatt"
            assert result.temperature_c == -5.2
            assert result.precipitation_type == "snow"

            # Verify URL construction
            mock_get.assert_called_once()
            call_args = mock_get.call_args
            assert "/weather/en/46.0/7.0" in call_args[0][0]
            assert call_args[1]["headers"]["Authorization"] == "Bearer test_token"
            assert call_args[1]["timeout"] == 10

    @patch("services.weatherkit_service.jwt.encode")
    def test_network_error_returns_none(self, mock_encode, mock_env):
        mock_encode.return_value = "test_token"
        service = WeatherKitService()

        with patch.object(
            service.session,
            "get",
            side_effect=requests.exceptions.ConnectionError("Connection refused"),
        ):
            result = service.get_weather(46.0, 7.0, "zermatt")
            assert result is None

    @patch("services.weatherkit_service.jwt.encode")
    def test_timeout_returns_none(self, mock_encode, mock_env):
        mock_encode.return_value = "test_token"
        service = WeatherKitService()

        with patch.object(
            service.session,
            "get",
            side_effect=requests.exceptions.Timeout("Request timed out"),
        ):
            result = service.get_weather(46.0, 7.0, "zermatt")
            assert result is None

    @patch("services.weatherkit_service.jwt.encode")
    def test_http_error_returns_none(self, mock_encode, mock_env):
        mock_encode.return_value = "test_token"
        service = WeatherKitService()

        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "401 Unauthorized"
        )

        with patch.object(service.session, "get", return_value=mock_response):
            result = service.get_weather(46.0, 7.0, "zermatt")
            assert result is None

    @patch("services.weatherkit_service.jwt.encode")
    def test_unexpected_error_returns_none(self, mock_encode, mock_env):
        mock_encode.return_value = "test_token"
        service = WeatherKitService()

        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json.side_effect = ValueError("Invalid JSON")

        with patch.object(service.session, "get", return_value=mock_response):
            result = service.get_weather(46.0, 7.0, "zermatt")
            assert result is None

    @patch("services.weatherkit_service.jwt.encode")
    def test_default_resort_id_empty(self, mock_encode, mock_env):
        mock_encode.return_value = "test_token"
        service = WeatherKitService()

        mock_response = MagicMock()
        mock_response.json.return_value = SAMPLE_RESPONSE
        mock_response.raise_for_status = MagicMock()

        with patch.object(service.session, "get", return_value=mock_response):
            result = service.get_weather(46.0, 7.0)
            assert result is not None
            assert result.resort_id == ""


class TestParseResponse:
    """Tests for response parsing and snowfall calculation."""

    def setup_method(self):
        """Create a service instance for parsing tests."""
        env = {
            "WEATHERKIT_KEY_ID": "key",
            "WEATHERKIT_TEAM_ID": "team",
            "WEATHERKIT_SERVICE_ID": "service",
            "WEATHERKIT_PRIVATE_KEY": "",
        }
        with patch.dict("os.environ", env, clear=False):
            self.service = WeatherKitService()

    def test_parse_snow_only_hours(self):
        data = {
            "currentWeather": {"temperature": -8.0, "precipitationType": "snow"},
            "forecastHourly": {
                "hours": [
                    {"precipitationAmount": 2.0, "precipitationType": "snow"},
                    {"precipitationAmount": 3.0, "precipitationType": "snow"},
                ]
            },
        }
        result = self.service._parse_response(data, "test-resort")

        assert result.resort_id == "test-resort"
        assert result.temperature_c == -8.0
        assert result.precipitation_type == "snow"
        # 2.0 * 8 + 3.0 * 8 = 40.0 mm
        assert result.snowfall_24h_mm == 40.0
        assert result.snowfall_24h_cm == 4.0

    def test_parse_mixed_precipitation(self):
        data = {
            "currentWeather": {"temperature": 0.5, "precipitationType": "mixed"},
            "forecastHourly": {
                "hours": [
                    {"precipitationAmount": 4.0, "precipitationType": "mixed"},
                ]
            },
        }
        result = self.service._parse_response(data, "test-resort")

        assert result.precipitation_type == "mixed"
        # 4.0 * 4.0 = 16.0 mm (mixed uses half ratio)
        assert result.snowfall_24h_mm == 16.0

    def test_parse_no_snow_hours(self):
        data = {
            "currentWeather": {"temperature": 5.0, "precipitationType": "rain"},
            "forecastHourly": {
                "hours": [
                    {"precipitationAmount": 10.0, "precipitationType": "rain"},
                    {"precipitationAmount": 0.0, "precipitationType": "clear"},
                ]
            },
        }
        result = self.service._parse_response(data, "test-resort")

        assert result.snowfall_24h_mm is None
        assert result.snowfall_24h_cm is None
        assert result.precipitation_type == "rain"

    def test_parse_empty_hourly_data(self):
        data = {
            "currentWeather": {"temperature": -2.0, "precipitationType": "clear"},
            "forecastHourly": {"hours": []},
        }
        result = self.service._parse_response(data, "test-resort")

        assert result.snowfall_24h_mm is None
        assert result.temperature_c == -2.0

    def test_parse_missing_hourly_section(self):
        data = {
            "currentWeather": {"temperature": -3.0, "precipitationType": "snow"},
        }
        result = self.service._parse_response(data, "test-resort")

        assert result.snowfall_24h_mm is None
        assert result.temperature_c == -3.0

    def test_parse_missing_current_weather(self):
        data = {
            "forecastHourly": {
                "hours": [
                    {"precipitationAmount": 1.0, "precipitationType": "snow"},
                ]
            },
        }
        result = self.service._parse_response(data, "test-resort")

        assert result.temperature_c is None
        assert result.precipitation_type == "clear"  # Default
        assert result.snowfall_24h_mm == 8.0

    def test_parse_mixed_snow_and_rain_hours(self):
        data = {
            "currentWeather": {"temperature": -1.0, "precipitationType": "snow"},
            "forecastHourly": {
                "hours": [
                    {"precipitationAmount": 2.0, "precipitationType": "snow"},
                    {"precipitationAmount": 5.0, "precipitationType": "rain"},
                    {"precipitationAmount": 1.0, "precipitationType": "mixed"},
                    {"precipitationAmount": 0.0, "precipitationType": "clear"},
                ]
            },
        }
        result = self.service._parse_response(data, "test-resort")

        # snow: 2.0 * 8 = 16.0, rain: ignored, mixed: 1.0 * 4 = 4.0
        assert result.snowfall_24h_mm == 20.0

    def test_parse_zero_precip_snow_hours(self):
        data = {
            "currentWeather": {"temperature": -10.0, "precipitationType": "snow"},
            "forecastHourly": {
                "hours": [
                    {"precipitationAmount": 0.0, "precipitationType": "snow"},
                ]
            },
        }
        result = self.service._parse_response(data, "test-resort")

        # Zero precip amount even though type is snow - no actual snowfall
        assert result.snowfall_24h_mm is None

    def test_parse_complete_sample_response(self):
        result = self.service._parse_response(SAMPLE_RESPONSE, "sample-resort")

        assert result.resort_id == "sample-resort"
        assert result.temperature_c == -5.2
        assert result.precipitation_type == "snow"
        # snow: 2.0*8 + 1.5*8 = 28.0, clear: 0, mixed: 3.0*4 = 12.0
        assert result.snowfall_24h_mm == 40.0
        assert result.snowfall_24h_cm == 4.0
