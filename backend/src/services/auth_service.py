"""Authentication service for Sign in with Apple and JWT management."""

import hashlib
import os
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

import requests
from botocore.exceptions import ClientError
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError, JWTClaimsError

from models.user import User
from utils.dynamodb_utils import parse_from_dynamodb, prepare_for_dynamodb


class AuthProvider(str, Enum):
    """Supported authentication providers."""

    APPLE = "apple"
    GOOGLE = "google"
    GUEST = "guest"


@dataclass
class AuthenticatedUser:
    """Authenticated user data."""

    user_id: str
    email: str | None
    first_name: str | None
    last_name: str | None
    provider: AuthProvider
    is_new_user: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "user_id": self.user_id,
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "provider": self.provider.value,
            "is_new_user": self.is_new_user,
        }


class AuthenticationError(Exception):
    """Authentication error."""

    pass


class AuthService:
    """Service for handling authentication."""

    # Apple's public keys URL
    APPLE_KEYS_URL = "https://appleid.apple.com/auth/keys"

    # JWT settings
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRATION_HOURS = 24 * 7  # 7 days
    JWT_REFRESH_EXPIRATION_DAYS = 30

    # Cache for Apple's public keys
    _apple_keys_cache: dict[str, Any] | None = None
    _apple_keys_cache_time: float = 0
    APPLE_KEYS_CACHE_DURATION = 3600  # 1 hour

    def __init__(
        self,
        user_table,
        jwt_secret: str | None = None,
        apple_team_id: str | None = None,
        apple_client_id: str | None = None,
    ):
        """Initialize auth service.

        Args:
            user_table: DynamoDB table for users
            jwt_secret: Secret for signing JWTs
            apple_team_id: Apple Developer Team ID
            apple_client_id: Apple App Bundle ID
        """
        self.user_table = user_table
        self.jwt_secret = jwt_secret or os.environ.get(
            "JWT_SECRET_KEY", "dev-secret-change-in-prod"
        )
        self.apple_team_id = apple_team_id or os.environ.get("APPLE_SIGNIN_TEAM_ID")
        self.apple_client_id = apple_client_id or os.environ.get(
            "APPLE_SIGNIN_CLIENT_ID", "com.snowtracker.app"
        )

    # ============================================
    # Apple Sign In
    # ============================================

    def verify_apple_token(
        self,
        identity_token: str,
        authorization_code: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> AuthenticatedUser:
        """Verify an Apple identity token and create/update user.

        Args:
            identity_token: JWT from Apple Sign In
            authorization_code: Authorization code (for token exchange, optional)
            first_name: User's first name (only provided on first sign-in)
            last_name: User's last name (only provided on first sign-in)

        Returns:
            AuthenticatedUser with session info

        Raises:
            AuthenticationError: If token is invalid
        """
        try:
            # Decode and verify the Apple JWT
            claims = self._decode_apple_token(identity_token)

            # Extract user info from claims
            apple_user_id = claims.get("sub")
            email = claims.get("email")
            # Apple may send email_verified as bool or string "true"/"false"
            raw_verified = claims.get("email_verified", False)
            email_verified = raw_verified in (True, "true")

            if not apple_user_id:
                raise AuthenticationError("Missing user ID in Apple token")

            # Generate internal user ID from Apple user ID
            user_id = self._generate_user_id(apple_user_id, AuthProvider.APPLE)

            # Check if user exists
            existing_user = self._get_user(user_id)
            is_new_user = existing_user is None

            # Create or update user
            if is_new_user:
                user = self._create_user(
                    user_id=user_id,
                    email=email if email_verified else None,
                    first_name=first_name,
                    last_name=last_name,
                    provider=AuthProvider.APPLE,
                    external_id=apple_user_id,
                )
            else:
                user = self._update_user_login(
                    user_id=user_id,
                    email=email if email_verified else existing_user.email,
                    first_name=first_name or existing_user.first_name,
                    last_name=last_name or existing_user.last_name,
                )

            return AuthenticatedUser(
                user_id=user_id,
                email=user.email,
                first_name=user.first_name,
                last_name=user.last_name,
                provider=AuthProvider.APPLE,
                is_new_user=is_new_user,
            )

        except JWTError as e:
            raise AuthenticationError(f"Invalid Apple token: {str(e)}")
        except AuthenticationError:
            raise
        except Exception as e:
            raise AuthenticationError(f"Apple authentication failed: {str(e)}")

    def _decode_apple_token(self, token: str) -> dict[str, Any]:
        """Decode and verify an Apple identity token.

        Args:
            token: JWT from Apple

        Returns:
            Token claims

        Raises:
            AuthenticationError: If token is invalid
        """
        # Get Apple's public keys
        apple_keys = self._get_apple_public_keys()

        # Get the key ID from the token header
        try:
            unverified_header = jwt.get_unverified_header(token)
            kid = unverified_header.get("kid")
        except JWTError as e:
            raise AuthenticationError(f"Invalid token header: {str(e)}")

        if not kid:
            raise AuthenticationError("Missing key ID in token header")

        # Find the matching public key
        matching_key = None
        for key in apple_keys.get("keys", []):
            if key.get("kid") == kid:
                matching_key = key
                break

        if not matching_key:
            # Refresh keys and try again
            self._apple_keys_cache = None
            apple_keys = self._get_apple_public_keys()
            for key in apple_keys.get("keys", []):
                if key.get("kid") == kid:
                    matching_key = key
                    break

        if not matching_key:
            raise AuthenticationError("No matching public key found")

        # Verify and decode the token using JWKS
        try:
            claims = jwt.decode(
                token,
                matching_key,
                algorithms=["RS256"],
                audience=self.apple_client_id,
                issuer="https://appleid.apple.com",
                options={
                    "verify_exp": True,
                    "verify_iat": True,
                    "verify_aud": True,
                    "verify_iss": True,
                },
            )
            return claims
        except ExpiredSignatureError:
            raise AuthenticationError("Token has expired")
        except JWTError as e:
            error_msg = str(e).lower()
            if "audience" in error_msg:
                raise AuthenticationError("Invalid token audience")
            elif "issuer" in error_msg:
                raise AuthenticationError("Invalid token issuer")
            raise AuthenticationError(f"Token validation failed: {str(e)}")

    def _get_apple_public_keys(self) -> dict[str, Any]:
        """Get Apple's public keys for JWT verification."""
        # Check cache
        if (
            self._apple_keys_cache
            and time.time() - self._apple_keys_cache_time
            < self.APPLE_KEYS_CACHE_DURATION
        ):
            return self._apple_keys_cache

        # Fetch fresh keys
        try:
            response = requests.get(self.APPLE_KEYS_URL, timeout=10)
            response.raise_for_status()
            self._apple_keys_cache = response.json()
            self._apple_keys_cache_time = time.time()
            return self._apple_keys_cache
        except requests.RequestException as e:
            if self._apple_keys_cache:
                # Return stale cache if fetch fails
                return self._apple_keys_cache
            raise AuthenticationError(f"Failed to fetch Apple public keys: {str(e)}")

    # ============================================
    # JWT Session Management
    # ============================================

    def create_session_tokens(self, user_id: str) -> dict[str, str]:
        """Create access and refresh tokens for a user.

        Args:
            user_id: User ID

        Returns:
            Dict with access_token and refresh_token
        """
        now = datetime.now(UTC)

        # Access token
        access_payload = {
            "sub": user_id,
            "type": "access",
            "iat": now,
            "exp": now + timedelta(hours=self.JWT_EXPIRATION_HOURS),
        }
        access_token = jwt.encode(
            access_payload, self.jwt_secret, algorithm=self.JWT_ALGORITHM
        )

        # Refresh token
        refresh_payload = {
            "sub": user_id,
            "type": "refresh",
            "iat": now,
            "exp": now + timedelta(days=self.JWT_REFRESH_EXPIRATION_DAYS),
        }
        refresh_token = jwt.encode(
            refresh_payload, self.jwt_secret, algorithm=self.JWT_ALGORITHM
        )

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "Bearer",
            "expires_in": self.JWT_EXPIRATION_HOURS * 3600,
        }

    def verify_access_token(self, token: str) -> str:
        """Verify an access token and return the user ID.

        Args:
            token: JWT access token

        Returns:
            User ID

        Raises:
            AuthenticationError: If token is invalid
        """
        try:
            payload = jwt.decode(
                token,
                self.jwt_secret,
                algorithms=[self.JWT_ALGORITHM],
                options={"verify_exp": True},
            )

            if payload.get("type") != "access":
                raise AuthenticationError("Invalid token type")

            user_id = payload.get("sub")
            if not user_id:
                raise AuthenticationError("Missing user ID in token")

            return user_id

        except ExpiredSignatureError:
            raise AuthenticationError("Token has expired")
        except JWTError as e:
            raise AuthenticationError(f"Invalid token: {str(e)}")

    def refresh_tokens(self, refresh_token: str) -> dict[str, str]:
        """Refresh access and refresh tokens.

        Args:
            refresh_token: Current refresh token

        Returns:
            New token pair

        Raises:
            AuthenticationError: If refresh token is invalid
        """
        try:
            payload = jwt.decode(
                refresh_token,
                self.jwt_secret,
                algorithms=[self.JWT_ALGORITHM],
                options={"verify_exp": True},
            )

            if payload.get("type") != "refresh":
                raise AuthenticationError("Invalid token type")

            user_id = payload.get("sub")
            if not user_id:
                raise AuthenticationError("Missing user ID in token")

            # Verify user still exists
            user = self._get_user(user_id)
            if not user or not user.is_active:
                raise AuthenticationError("User not found or inactive")

            # Issue new tokens
            return self.create_session_tokens(user_id)

        except ExpiredSignatureError:
            raise AuthenticationError("Refresh token has expired")
        except JWTError as e:
            raise AuthenticationError(f"Invalid refresh token: {str(e)}")

    # ============================================
    # Guest Authentication
    # ============================================

    def create_guest_session(self, device_id: str) -> AuthenticatedUser:
        """Create a guest session.

        Args:
            device_id: Unique device identifier

        Returns:
            AuthenticatedUser for guest
        """
        user_id = self._generate_user_id(device_id, AuthProvider.GUEST)

        # Check if guest already exists
        existing = self._get_user(user_id)
        if existing:
            self._update_user_login(user_id)
            return AuthenticatedUser(
                user_id=user_id,
                email=None,
                first_name=None,
                last_name=None,
                provider=AuthProvider.GUEST,
                is_new_user=False,
            )

        # Create new guest
        self._create_user(
            user_id=user_id,
            email=None,
            first_name=None,
            last_name=None,
            provider=AuthProvider.GUEST,
            external_id=device_id,
        )

        return AuthenticatedUser(
            user_id=user_id,
            email=None,
            first_name=None,
            last_name=None,
            provider=AuthProvider.GUEST,
            is_new_user=True,
        )

    # ============================================
    # User Management
    # ============================================

    def _generate_user_id(self, external_id: str, provider: AuthProvider) -> str:
        """Generate internal user ID from external ID.

        Creates a stable, unique ID based on provider and external ID.
        """
        combined = f"{provider.value}:{external_id}"
        return hashlib.sha256(combined.encode()).hexdigest()[:32]

    def _get_user(self, user_id: str) -> User | None:
        """Get user by ID."""
        try:
            response = self.user_table.get_item(Key={"user_id": user_id})
            item = response.get("Item")
            if not item:
                return None
            parsed = parse_from_dynamodb(item)
            return User(**parsed)
        except ClientError:
            return None

    def _create_user(
        self,
        user_id: str,
        email: str | None,
        first_name: str | None,
        last_name: str | None,
        provider: AuthProvider,
        external_id: str,
    ) -> User:
        """Create a new user."""
        now = datetime.now(UTC).isoformat()
        user = User(
            user_id=user_id,
            email=email,
            first_name=first_name,
            last_name=last_name,
            created_at=now,
            last_login=now,
            is_active=True,
        )

        try:
            item = user.model_dump()
            # Add provider info
            item["auth_provider"] = provider.value
            item["external_id"] = external_id
            item = prepare_for_dynamodb(item)
            self.user_table.put_item(Item=item)
            return user
        except ClientError as e:
            raise AuthenticationError(f"Failed to create user: {str(e)}")

    def _update_user_login(
        self,
        user_id: str,
        email: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> User:
        """Update user on login."""
        user = self._get_user(user_id)
        if not user:
            raise AuthenticationError("User not found")

        # Update fields
        user.last_login = datetime.now(UTC).isoformat()
        if email:
            user.email = email
        if first_name:
            user.first_name = first_name
        if last_name:
            user.last_name = last_name

        try:
            item = user.model_dump()
            item = prepare_for_dynamodb(item)
            self.user_table.put_item(Item=item)
            return user
        except ClientError as e:
            raise AuthenticationError(f"Failed to update user: {str(e)}")

    def deactivate_user(self, user_id: str) -> bool:
        """Deactivate a user account.

        Args:
            user_id: User ID

        Returns:
            True if deactivated
        """
        user = self._get_user(user_id)
        if not user:
            return False

        user.is_active = False

        try:
            item = user.model_dump()
            item = prepare_for_dynamodb(item)
            self.user_table.put_item(Item=item)
            return True
        except ClientError:
            return False
