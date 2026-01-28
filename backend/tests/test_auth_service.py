"""Tests for AuthService."""

from datetime import UTC, datetime, timedelta
from unittest.mock import Mock, patch

import pytest
from botocore.exceptions import ClientError
from jose import jwt

from services.auth_service import (
    AuthenticatedUser,
    AuthenticationError,
    AuthProvider,
    AuthService,
)


class TestAuthService:
    """Test cases for AuthService."""

    @pytest.fixture
    def mock_user_table(self):
        """Create a mock DynamoDB user table."""
        table = Mock()
        table.get_item.return_value = {"Item": None}
        table.put_item.return_value = {}
        return table

    @pytest.fixture
    def auth_service(self, mock_user_table):
        """Create an AuthService with mocked dependencies."""
        return AuthService(
            user_table=mock_user_table,
            jwt_secret="test-secret-key-for-testing",
            apple_team_id="TEAM123",
            apple_client_id="com.test.app",
        )

    @pytest.fixture
    def sample_user_data(self):
        """Create sample user data."""
        return {
            "user_id": "test-user-hash-123",
            "email": "test@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "created_at": "2026-01-20T08:00:00Z",
            "last_login": "2026-01-20T10:00:00Z",
            "is_active": True,
            "auth_provider": "apple",
            "external_id": "apple-user-123",
        }

    # ============================================
    # JWT Token Tests
    # ============================================

    def test_create_session_tokens(self, auth_service):
        """Test JWT token creation."""
        tokens = auth_service.create_session_tokens("test-user-123")

        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert tokens["token_type"] == "Bearer"
        assert tokens["expires_in"] > 0

        # Verify tokens are valid JWTs
        access_payload = jwt.decode(
            tokens["access_token"],
            "test-secret-key-for-testing",
            algorithms=["HS256"],
        )
        assert access_payload["sub"] == "test-user-123"
        assert access_payload["type"] == "access"

        refresh_payload = jwt.decode(
            tokens["refresh_token"],
            "test-secret-key-for-testing",
            algorithms=["HS256"],
        )
        assert refresh_payload["sub"] == "test-user-123"
        assert refresh_payload["type"] == "refresh"

    def test_verify_access_token_success(self, auth_service):
        """Test successful access token verification."""
        tokens = auth_service.create_session_tokens("test-user-123")
        user_id = auth_service.verify_access_token(tokens["access_token"])

        assert user_id == "test-user-123"

    def test_verify_access_token_expired(self, auth_service):
        """Test expired access token rejection."""
        # Create an expired token
        expired_payload = {
            "sub": "test-user-123",
            "type": "access",
            "iat": datetime.now(UTC) - timedelta(days=10),
            "exp": datetime.now(UTC) - timedelta(days=1),  # Expired
        }
        expired_token = jwt.encode(
            expired_payload,
            "test-secret-key-for-testing",
            algorithm="HS256",
        )

        with pytest.raises(AuthenticationError, match="expired"):
            auth_service.verify_access_token(expired_token)

    def test_verify_access_token_invalid(self, auth_service):
        """Test invalid access token rejection."""
        with pytest.raises(AuthenticationError, match="Invalid token"):
            auth_service.verify_access_token("not-a-valid-token")

    def test_verify_access_token_wrong_type(self, auth_service):
        """Test refresh token rejected as access token."""
        tokens = auth_service.create_session_tokens("test-user-123")

        with pytest.raises(AuthenticationError, match="Invalid token type"):
            auth_service.verify_access_token(tokens["refresh_token"])

    def test_verify_access_token_wrong_secret(self, auth_service):
        """Test token with wrong secret is rejected."""
        # Create token with different secret
        payload = {
            "sub": "test-user-123",
            "type": "access",
            "iat": datetime.now(UTC),
            "exp": datetime.now(UTC) + timedelta(hours=1),
        }
        wrong_secret_token = jwt.encode(payload, "wrong-secret", algorithm="HS256")

        with pytest.raises(AuthenticationError):
            auth_service.verify_access_token(wrong_secret_token)

    def test_refresh_tokens_success(self, auth_service, mock_user_table, sample_user_data):
        """Test successful token refresh."""
        mock_user_table.get_item.return_value = {"Item": sample_user_data}

        original_tokens = auth_service.create_session_tokens("test-user-hash-123")
        new_tokens = auth_service.refresh_tokens(original_tokens["refresh_token"])

        assert "access_token" in new_tokens
        assert "refresh_token" in new_tokens
        assert "token_type" in new_tokens
        assert new_tokens["token_type"] == "Bearer"
        # Verify the new access token is valid
        user_id = auth_service.verify_access_token(new_tokens["access_token"])
        assert user_id == "test-user-hash-123"

    def test_refresh_tokens_expired(self, auth_service):
        """Test expired refresh token rejection."""
        expired_payload = {
            "sub": "test-user-123",
            "type": "refresh",
            "iat": datetime.now(UTC) - timedelta(days=40),
            "exp": datetime.now(UTC) - timedelta(days=1),
        }
        expired_token = jwt.encode(
            expired_payload,
            "test-secret-key-for-testing",
            algorithm="HS256",
        )

        with pytest.raises(AuthenticationError, match="expired"):
            auth_service.refresh_tokens(expired_token)

    def test_refresh_tokens_wrong_type(self, auth_service):
        """Test access token rejected as refresh token."""
        tokens = auth_service.create_session_tokens("test-user-123")

        with pytest.raises(AuthenticationError, match="Invalid token type"):
            auth_service.refresh_tokens(tokens["access_token"])

    def test_refresh_tokens_inactive_user(self, auth_service, mock_user_table, sample_user_data):
        """Test refresh fails for inactive user."""
        sample_user_data["is_active"] = False
        mock_user_table.get_item.return_value = {"Item": sample_user_data}

        tokens = auth_service.create_session_tokens("test-user-hash-123")

        with pytest.raises(AuthenticationError, match="inactive"):
            auth_service.refresh_tokens(tokens["refresh_token"])

    # ============================================
    # Guest Authentication Tests
    # ============================================

    def test_create_guest_session_new_user(self, auth_service, mock_user_table):
        """Test creating a new guest session."""
        mock_user_table.get_item.return_value = {}  # No existing user

        user = auth_service.create_guest_session("device-uuid-123")

        assert user.provider == AuthProvider.GUEST
        assert user.is_new_user is True
        assert user.email is None
        mock_user_table.put_item.assert_called_once()

    def test_create_guest_session_existing_user(
        self, auth_service, mock_user_table, sample_user_data
    ):
        """Test guest session for existing guest user."""
        sample_user_data["auth_provider"] = "guest"
        mock_user_table.get_item.return_value = {"Item": sample_user_data}

        user = auth_service.create_guest_session("device-uuid-123")

        assert user.is_new_user is False

    def test_guest_user_id_generation(self, auth_service):
        """Test that guest user IDs are consistent."""
        user_id_1 = auth_service._generate_user_id("device-123", AuthProvider.GUEST)
        user_id_2 = auth_service._generate_user_id("device-123", AuthProvider.GUEST)

        # Same device ID should generate same user ID
        assert user_id_1 == user_id_2

        # Different device ID should generate different user ID
        user_id_3 = auth_service._generate_user_id("device-456", AuthProvider.GUEST)
        assert user_id_1 != user_id_3

    def test_user_id_different_providers(self, auth_service):
        """Test user IDs are different for same external ID with different providers."""
        apple_id = auth_service._generate_user_id("user-123", AuthProvider.APPLE)
        guest_id = auth_service._generate_user_id("user-123", AuthProvider.GUEST)

        assert apple_id != guest_id

    # ============================================
    # Apple Sign In Tests (Mocked)
    # ============================================

    @patch.object(AuthService, "_decode_apple_token")
    def test_verify_apple_token_new_user(
        self, mock_decode, auth_service, mock_user_table
    ):
        """Test Apple Sign In creates new user."""
        mock_decode.return_value = {
            "sub": "apple-user-001",
            "email": "user@icloud.com",
            "email_verified": True,
        }
        mock_user_table.get_item.return_value = {}  # No existing user

        user = auth_service.verify_apple_token(
            identity_token="fake-apple-token",
            first_name="Jane",
            last_name="Smith",
        )

        assert user.email == "user@icloud.com"
        assert user.first_name == "Jane"
        assert user.last_name == "Smith"
        assert user.provider == AuthProvider.APPLE
        assert user.is_new_user is True

    @patch.object(AuthService, "_decode_apple_token")
    def test_verify_apple_token_existing_user(
        self, mock_decode, auth_service, mock_user_table, sample_user_data
    ):
        """Test Apple Sign In updates existing user."""
        mock_decode.return_value = {
            "sub": "apple-user-123",
            "email": "user@icloud.com",
            "email_verified": True,
        }
        mock_user_table.get_item.return_value = {"Item": sample_user_data}

        user = auth_service.verify_apple_token(
            identity_token="fake-apple-token",
        )

        assert user.is_new_user is False
        # Should have called put_item to update last_login
        assert mock_user_table.put_item.call_count >= 1

    @patch.object(AuthService, "_decode_apple_token")
    def test_verify_apple_token_unverified_email(
        self, mock_decode, auth_service, mock_user_table
    ):
        """Test Apple Sign In handles unverified email."""
        mock_decode.return_value = {
            "sub": "apple-user-002",
            "email": "user@icloud.com",
            "email_verified": False,  # Not verified
        }
        mock_user_table.get_item.return_value = {}

        user = auth_service.verify_apple_token(identity_token="fake-token")

        # Email should not be stored if not verified
        assert user.email is None

    @patch.object(AuthService, "_decode_apple_token")
    def test_verify_apple_token_missing_sub(
        self, mock_decode, auth_service
    ):
        """Test Apple token without sub claim fails."""
        mock_decode.return_value = {
            "email": "user@icloud.com",
            # Missing "sub" claim
        }

        with pytest.raises(AuthenticationError, match="Missing user ID"):
            auth_service.verify_apple_token(identity_token="bad-token")

    def test_verify_apple_token_invalid(self, auth_service):
        """Test invalid Apple token is rejected."""
        with pytest.raises(AuthenticationError):
            auth_service.verify_apple_token(identity_token="invalid-token")

    # ============================================
    # User Management Tests
    # ============================================

    def test_deactivate_user_success(
        self, auth_service, mock_user_table, sample_user_data
    ):
        """Test successful user deactivation."""
        mock_user_table.get_item.return_value = {"Item": sample_user_data}

        result = auth_service.deactivate_user("test-user-hash-123")

        assert result is True
        # Check that put_item was called with is_active=False
        call_args = mock_user_table.put_item.call_args
        assert call_args is not None

    def test_deactivate_user_not_found(self, auth_service, mock_user_table):
        """Test deactivating non-existent user."""
        mock_user_table.get_item.return_value = {}

        result = auth_service.deactivate_user("non-existent")

        assert result is False

    def test_authenticated_user_to_dict(self):
        """Test AuthenticatedUser serialization."""
        user = AuthenticatedUser(
            user_id="test-123",
            email="test@example.com",
            first_name="John",
            last_name="Doe",
            provider=AuthProvider.APPLE,
            is_new_user=True,
        )

        user_dict = user.to_dict()

        assert user_dict["user_id"] == "test-123"
        assert user_dict["email"] == "test@example.com"
        assert user_dict["provider"] == "apple"
        assert user_dict["is_new_user"] is True

    # ============================================
    # Apple Public Keys Tests (Mocked)
    # ============================================

    @patch("requests.get")
    def test_get_apple_public_keys_success(self, mock_get, auth_service):
        """Test fetching Apple's public keys."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "keys": [
                {"kid": "key-1", "alg": "RS256"},
                {"kid": "key-2", "alg": "RS256"},
            ]
        }
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Clear cache
        auth_service._apple_keys_cache = None

        keys = auth_service._get_apple_public_keys()

        assert "keys" in keys
        assert len(keys["keys"]) == 2
        mock_get.assert_called_once()

    @patch("requests.get")
    def test_get_apple_public_keys_cached(self, mock_get, auth_service):
        """Test Apple public keys are cached."""
        mock_response = Mock()
        mock_response.json.return_value = {"keys": [{"kid": "key-1"}]}
        mock_response.raise_for_status.return_value = None
        mock_get.return_value = mock_response

        # Clear cache first
        auth_service._apple_keys_cache = None
        auth_service._apple_keys_cache_time = 0

        # First call - should fetch
        keys1 = auth_service._get_apple_public_keys()
        # Second call - should use cache
        keys2 = auth_service._get_apple_public_keys()

        # Only one request should have been made
        assert mock_get.call_count == 1
        assert keys1 == keys2

    @patch("services.auth_service.requests.get")
    def test_get_apple_public_keys_error_with_cache(self, mock_get, auth_service):
        """Test fallback to cached keys on error."""
        import requests as req

        # Set up cached keys
        auth_service._apple_keys_cache = {"keys": [{"kid": "cached-key"}]}
        auth_service._apple_keys_cache_time = 0  # Expired cache

        # Make request fail with a requests exception
        mock_get.side_effect = req.RequestException("Network error")

        # Should return cached keys
        keys = auth_service._get_apple_public_keys()

        assert keys == {"keys": [{"kid": "cached-key"}]}

    @patch("services.auth_service.requests.get")
    def test_get_apple_public_keys_error_no_cache(self, mock_get, auth_service):
        """Test error handling when no cache available."""
        import requests as req

        # No cached keys
        auth_service._apple_keys_cache = None
        auth_service._apple_keys_cache_time = 0

        mock_get.side_effect = req.RequestException("Network error")

        with pytest.raises(AuthenticationError, match="Failed to fetch"):
            auth_service._get_apple_public_keys()

    # ============================================
    # Integration-style Tests
    # ============================================

    def test_full_guest_flow(self, auth_service, mock_user_table):
        """Test complete guest authentication flow."""
        mock_user_table.get_item.return_value = {}

        # 1. Create guest session
        user = auth_service.create_guest_session("device-123")
        assert user.is_new_user is True

        # 2. Create tokens
        tokens = auth_service.create_session_tokens(user.user_id)
        assert "access_token" in tokens

        # 3. Verify access token
        verified_user_id = auth_service.verify_access_token(tokens["access_token"])
        assert verified_user_id == user.user_id

        # 4. Simulate user returning later - refresh tokens
        mock_user_table.get_item.return_value = {
            "Item": {
                "user_id": user.user_id,
                "email": None,
                "first_name": None,
                "last_name": None,
                "is_active": True,
                "created_at": datetime.now(UTC).isoformat(),
                "auth_provider": "guest",
            }
        }
        new_tokens = auth_service.refresh_tokens(tokens["refresh_token"])
        # Verify the new access token works
        new_user_id = auth_service.verify_access_token(new_tokens["access_token"])
        assert new_user_id == user.user_id

    def test_authentication_error_messages(self, auth_service):
        """Test that AuthenticationError provides useful messages."""
        # Test expired token error
        expired_payload = {
            "sub": "user",
            "type": "access",
            "exp": datetime.now(UTC) - timedelta(hours=1),
        }
        expired_token = jwt.encode(
            expired_payload, "test-secret-key-for-testing", algorithm="HS256"
        )

        try:
            auth_service.verify_access_token(expired_token)
            assert False, "Should have raised AuthenticationError"
        except AuthenticationError as e:
            assert "expired" in str(e).lower()
