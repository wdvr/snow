"""Main FastAPI application handler for Lambda deployment."""

import json
import logging
import os
import re
import time
from datetime import UTC, datetime, timezone
from typing import Annotated, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError
from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from mangum import Mangum
from pydantic import BaseModel, Field

from models.chat import ChatRequest
from models.condition_report import (
    ConditionReportRequest,
    ConditionReportResponse,
)
from models.feedback import Feedback, FeedbackSubmission
from models.resort import Resort
from models.trip import Trip, TripCreate, TripStatus, TripUpdate
from models.user import UserPreferences
from models.weather import SNOW_QUALITY_EXPLANATIONS, SnowQuality, TimelineResponse
from services.auth_service import AuthenticationError, AuthProvider, AuthService
from services.condition_report_service import ConditionReportService
from services.daily_history_service import DailyHistoryService
from services.ml_scorer import raw_score_to_quality
from services.openmeteo_service import OpenMeteoService
from services.quality_explanation_service import (
    generate_overall_explanation,
    generate_quality_explanation,
    generate_score_change_reason,
    generate_timeline_explanation,
    score_to_100,
)
from services.recommendation_service import RecommendationService
from services.resort_service import ResortService
from services.snow_quality_service import SnowQualityService
from services.trip_service import TripService
from services.user_service import UserService
from services.weather_service import WeatherService
from utils.cache import (
    CACHE_CONTROL_PRIVATE,
    CACHE_CONTROL_PUBLIC,
    CACHE_CONTROL_PUBLIC_LONG,
    cached_conditions,
    cached_recommendations,
    cached_resorts,
    cached_snow_quality,
    get_recommendations_cache,
    get_timeline_cache,
)
from utils.constants import DEFAULT_ELEVATION_WEIGHT, ELEVATION_WEIGHTS

logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Snow Quality Tracker API",
    description="API for tracking snow conditions at ski resorts",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# Configure CORS - wildcard is fine since this is a mobile API backend
# (CORS only applies to browsers, not native apps)
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request, call_next):
    """Log all API requests with timing for CloudWatch monitoring."""
    start = time.time()
    response = await call_next(request)
    duration_ms = (time.time() - start) * 1000

    # Log slow requests (>1s) at WARNING level for monitoring
    path = request.url.path
    if duration_ms > 1000:
        logger.warning(
            "[SLOW] %s %s %.0fms status=%d",
            request.method,
            path,
            duration_ms,
            response.status_code,
        )
    elif response.status_code >= 500:
        logger.error(
            "[ERROR] %s %s %.0fms status=%d",
            request.method,
            path,
            duration_ms,
            response.status_code,
        )
    elif response.status_code >= 400:
        logger.info(
            "[CLIENT_ERROR] %s %s %.0fms status=%d",
            request.method,
            path,
            duration_ms,
            response.status_code,
        )

    return response


# Lazy-initialized AWS clients and services
# Required for Lambda SnapStart - connections must be re-established after restore
_dynamodb = None
_resort_service = None
_weather_service = None
_snow_quality_service = None
_user_service = None
_feedback_table = None
_auth_service = None
_recommendation_service = None
_trip_service = None
_trips_table = None
_condition_report_service = None
_chat_service = None
_daily_history_service = None

# Security scheme for bearer token authentication
security = HTTPBearer(auto_error=False)


def reset_services():
    """Reset all lazy-initialized services. Useful for testing.

    Also resets boto3's default session so that subsequent calls to
    boto3.resource() create fresh sessions within the current mock context
    (e.g., moto's mock_aws).
    """
    global _dynamodb, _resort_service, _weather_service, _snow_quality_service
    global _user_service, _feedback_table, _auth_service, _recommendation_service
    global _trip_service, _trips_table, _s3_client, _condition_report_service
    global _chat_service, _daily_history_service
    _dynamodb = None
    _resort_service = None
    _weather_service = None
    _snow_quality_service = None
    _user_service = None
    _feedback_table = None
    _auth_service = None
    _recommendation_service = None
    _trip_service = None
    _trips_table = None
    _condition_report_service = None
    _chat_service = None
    _daily_history_service = None
    _s3_client = None
    # Reset boto3's default session so new clients use the moto mock context
    boto3.DEFAULT_SESSION = None


def get_dynamodb():
    """Get or create DynamoDB resource (lazy init for SnapStart)."""
    global _dynamodb
    if _dynamodb is None:
        region = os.environ.get("AWS_DEFAULT_REGION", "us-west-2")
        _dynamodb = boto3.resource("dynamodb", region_name=region)
    return _dynamodb


# S3 client for fetching static JSON (lazy init)
_s3_client = None


def get_s3_client():
    """Get or create S3 client (lazy init for SnapStart)."""
    global _s3_client
    if _s3_client is None:
        region = os.environ.get("AWS_DEFAULT_REGION", "us-west-2")
        _s3_client = boto3.client("s3", region_name=region)
    return _s3_client


# Cached static JSON data with TTL
_static_resorts_cache = {"data": None, "expires": 0}
_static_snow_quality_cache = {"data": None, "expires": 0}
STATIC_CACHE_TTL_SECONDS = 300  # 5 minute cache for static JSON


def _get_static_resorts_from_s3() -> list[dict] | None:
    """Fetch resorts from static S3 JSON file with caching.

    Returns None if static file is not available (falls back to DynamoDB).
    """
    # Check cache first
    now = time.time()
    if _static_resorts_cache["data"] and now < _static_resorts_cache["expires"]:
        return _static_resorts_cache["data"]

    # Try to fetch from S3
    website_bucket = os.environ.get("WEBSITE_BUCKET")
    if not website_bucket:
        return None

    try:
        response = get_s3_client().get_object(
            Bucket=website_bucket, Key="data/resorts.json"
        )
        data = json.loads(response["Body"].read().decode("utf-8"))

        # Cache the result
        _static_resorts_cache["data"] = data.get("resorts", [])
        _static_resorts_cache["expires"] = now + STATIC_CACHE_TTL_SECONDS

        logger.info(
            "Loaded %d resorts from S3 static JSON", len(_static_resorts_cache["data"])
        )
        return _static_resorts_cache["data"]
    except ClientError as e:
        # File doesn't exist or access denied - fall back to DynamoDB
        if e.response["Error"]["Code"] in ("NoSuchKey", "AccessDenied"):
            logger.info("Static resorts.json not found in S3, falling back to DynamoDB")
            return None
        raise
    except Exception as e:
        logger.warning("Error fetching static resorts from S3: %s", e)
        return None


def _get_static_snow_quality_from_s3() -> dict | None:
    """Fetch snow quality from static S3 JSON file with caching.

    Returns None if static file is not available (falls back to DynamoDB).
    """
    # Check cache first
    now = time.time()
    if (
        _static_snow_quality_cache["data"]
        and now < _static_snow_quality_cache["expires"]
    ):
        return _static_snow_quality_cache["data"]

    # Try to fetch from S3
    website_bucket = os.environ.get("WEBSITE_BUCKET")
    if not website_bucket:
        return None

    try:
        response = get_s3_client().get_object(
            Bucket=website_bucket, Key="data/snow-quality.json"
        )
        data = json.loads(response["Body"].read().decode("utf-8"))

        # Cache the result
        _static_snow_quality_cache["data"] = data.get("results", {})
        _static_snow_quality_cache["expires"] = now + STATIC_CACHE_TTL_SECONDS

        logger.info(
            "Loaded snow quality for %d resorts from S3",
            len(_static_snow_quality_cache["data"]),
        )
        return _static_snow_quality_cache["data"]
    except ClientError as e:
        # File doesn't exist or access denied - fall back to DynamoDB
        if e.response["Error"]["Code"] in ("NoSuchKey", "AccessDenied"):
            return None
        raise
    except Exception as e:
        logger.warning("Error fetching static snow quality from S3: %s", e)
        return None


def get_resort_service():
    """Get or create ResortService (lazy init for SnapStart)."""
    global _resort_service
    if _resort_service is None:
        _resort_service = ResortService(
            get_dynamodb().Table(
                os.environ.get("RESORTS_TABLE", "snow-tracker-resorts-dev")
            )
        )
    return _resort_service


def get_weather_service():
    """Get or create WeatherService (lazy init for SnapStart)."""
    global _weather_service
    if _weather_service is None:
        weather_conditions_table = get_dynamodb().Table(
            os.environ.get(
                "WEATHER_CONDITIONS_TABLE", "snow-tracker-weather-conditions-dev"
            )
        )
        _weather_service = WeatherService(
            api_key=os.environ.get("WEATHER_API_KEY"),
            conditions_table=weather_conditions_table,
        )
    return _weather_service


def get_snow_quality_service():
    """Get or create SnowQualityService (lazy init for SnapStart)."""
    global _snow_quality_service
    if _snow_quality_service is None:
        _snow_quality_service = SnowQualityService()
    return _snow_quality_service


def get_user_service():
    """Get or create UserService (lazy init for SnapStart)."""
    global _user_service
    if _user_service is None:
        _user_service = UserService(
            get_dynamodb().Table(
                os.environ.get(
                    "USER_PREFERENCES_TABLE", "snow-tracker-user-preferences-dev"
                )
            )
        )
    return _user_service


def get_feedback_table():
    """Get or create feedback table (lazy init for SnapStart)."""
    global _feedback_table
    if _feedback_table is None:
        _feedback_table = get_dynamodb().Table(
            os.environ.get("FEEDBACK_TABLE", "snow-tracker-feedback-dev")
        )
    return _feedback_table


def get_trips_table():
    """Get or create trips table (lazy init for SnapStart)."""
    global _trips_table
    if _trips_table is None:
        _trips_table = get_dynamodb().Table(
            os.environ.get("TRIPS_TABLE", "snow-tracker-trips-dev")
        )
    return _trips_table


def get_auth_service():
    """Get or create AuthService (lazy init for SnapStart)."""
    global _auth_service
    if _auth_service is None:
        user_table = get_dynamodb().Table(
            os.environ.get(
                "USER_PREFERENCES_TABLE", "snow-tracker-user-preferences-dev"
            )
        )
        _auth_service = AuthService(
            user_table=user_table,
            jwt_secret=os.environ.get("JWT_SECRET_KEY"),
            apple_team_id=os.environ.get("APPLE_SIGNIN_TEAM_ID"),
            apple_client_id=os.environ.get(
                "APPLE_SIGNIN_CLIENT_ID", "com.snowtracker.app"
            ),
        )
    return _auth_service


def get_recommendation_service():
    """Get or create RecommendationService (lazy init for SnapStart)."""
    global _recommendation_service
    if _recommendation_service is None:
        _recommendation_service = RecommendationService(
            resort_service=get_resort_service(),
            weather_service=get_weather_service(),
        )
    return _recommendation_service


def get_trip_service():
    """Get or create TripService (lazy init for SnapStart)."""
    global _trip_service
    if _trip_service is None:
        _trip_service = TripService(
            table=get_trips_table(),
            resort_service=get_resort_service(),
            weather_service=get_weather_service(),
        )
    return _trip_service


def get_condition_report_service():
    """Get or create ConditionReportService (lazy init for SnapStart)."""
    global _condition_report_service
    if _condition_report_service is None:
        environment = os.environ.get("ENVIRONMENT", "dev")
        table = get_dynamodb().Table(
            os.environ.get(
                "CONDITION_REPORTS_TABLE",
                f"snow-tracker-condition-reports-{environment}",
            )
        )
        _condition_report_service = ConditionReportService(table=table)
    return _condition_report_service


def get_chat_service():
    """Get or create ChatService (lazy init for SnapStart)."""
    global _chat_service
    if _chat_service is None:
        from services.chat_service import ChatService

        environment = os.environ.get("ENVIRONMENT", "dev")
        chat_table = get_dynamodb().Table(
            os.environ.get("CHAT_TABLE", f"snow-tracker-chat-{environment}")
        )
        _chat_service = ChatService(
            chat_table=chat_table,
            resort_service=get_resort_service(),
            weather_service=get_weather_service(),
            snow_quality_service=get_snow_quality_service(),
            recommendation_service=get_recommendation_service(),
            condition_report_service=get_condition_report_service(),
            daily_history_service=get_daily_history_service(),
        )
    return _chat_service


def get_daily_history_service():
    """Get or create DailyHistoryService (lazy init for SnapStart)."""
    global _daily_history_service
    if _daily_history_service is None:
        _daily_history_service = DailyHistoryService(
            get_dynamodb().Table(
                os.environ.get("DAILY_HISTORY_TABLE", "snow-tracker-daily-history-dev")
            )
        )
    return _daily_history_service


# MARK: - Authentication Dependency


async def get_current_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),  # noqa: B008
) -> str:
    """Extract user ID from JWT token.

    Args:
        credentials: Bearer token from Authorization header

    Returns:
        User ID from the token

    Raises:
        HTTPException: If token is missing or invalid
    """
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization header required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = get_auth_service().verify_access_token(credentials.credentials)
        return user_id
    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_optional_user_id(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),  # noqa: B008
) -> str | None:
    """Extract user ID from JWT token if present (optional auth).

    Returns None if no token provided, raises error if token is invalid.
    """
    if not credentials:
        return None

    try:
        return get_auth_service().verify_access_token(credentials.credentials)
    except AuthenticationError:
        return None


# MARK: - Anonymous Chat Rate Limiting

ANON_CHAT_LIMIT = 5
ANON_CHAT_WINDOW_HOURS = 6


def _get_client_ip(request: Request) -> str:
    """Get client IP from request, considering proxy headers."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _check_anonymous_chat_limit(ip_address: str) -> bool:
    """Check if anonymous IP is within chat rate limit. Returns True if allowed."""
    table_name = os.environ.get("CHAT_RATE_LIMIT_TABLE_NAME")
    if not table_name:
        logger.warning("CHAT_RATE_LIMIT_TABLE_NAME not configured, allowing request")
        return True

    try:
        table = get_dynamodb().Table(table_name)

        now = int(time.time())
        window_start = now - (ANON_CHAT_WINDOW_HOURS * 3600)
        expires_at = now + (ANON_CHAT_WINDOW_HOURS * 3600)

        # Get current record
        response = table.get_item(Key={"ip_address": ip_address})
        item = response.get("Item")

        if item:
            # Filter to only timestamps within the window
            timestamps = item.get("timestamps", [])
            recent = [t for t in timestamps if t > window_start]

            if len(recent) >= ANON_CHAT_LIMIT:
                return False

            # Add new timestamp
            recent.append(now)
            table.put_item(
                Item={
                    "ip_address": ip_address,
                    "timestamps": recent,
                    "message_count": len(recent),
                    "expires_at": expires_at,
                }
            )
        else:
            # First message from this IP
            table.put_item(
                Item={
                    "ip_address": ip_address,
                    "timestamps": [now],
                    "message_count": 1,
                    "expires_at": expires_at,
                }
            )

        return True
    except Exception as e:
        logger.error("Rate limit check failed for IP %s: %s", ip_address, e)
        # Fail open - allow the request if rate limit check fails
        return True


def _get_remaining_anonymous_messages(ip_address: str) -> int:
    """Get remaining anonymous messages for an IP address."""
    table_name = os.environ.get("CHAT_RATE_LIMIT_TABLE_NAME")
    if not table_name:
        return ANON_CHAT_LIMIT

    try:
        table = get_dynamodb().Table(table_name)

        now = int(time.time())
        window_start = now - (ANON_CHAT_WINDOW_HOURS * 3600)

        response = table.get_item(Key={"ip_address": ip_address})
        item = response.get("Item")

        if item:
            timestamps = item.get("timestamps", [])
            recent = [t for t in timestamps if t > window_start]
            return max(0, ANON_CHAT_LIMIT - len(recent))
        return ANON_CHAT_LIMIT
    except Exception:
        return ANON_CHAT_LIMIT


# MARK: - Input Validation Helpers

# Resort IDs are alphanumeric with hyphens, max 100 chars (e.g. "whistler-blackcomb")
_VALID_ID_RE = re.compile(r"^[a-zA-Z0-9_-]{1,100}$")


def _validate_resource_id(value: str, name: str = "resource") -> None:
    """Validate a path-parameter ID (resort_id, trip_id, event_id, etc.).

    Prevents long or malicious strings from being echoed in error messages
    or sent to DynamoDB. Raises HTTPException(400) on invalid input.
    """
    if not value or not _VALID_ID_RE.match(value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {name}",
        )


def _sanitize_id_for_message(value: str, max_len: int = 60) -> str:
    """Truncate and sanitize an ID for safe inclusion in log/error messages."""
    if len(value) > max_len:
        return value[:max_len] + "..."
    return value


# MARK: - Health Check


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat(),
        "version": "1.0.0",
    }


@app.get("/api/v1/app-config")
async def get_app_config():
    """Return app configuration including minimum supported version.

    iOS app checks this on launch to determine if a forced update is needed.
    Reads from DynamoDB table snow-tracker-app-config-{env} with fallback
    to hardcoded defaults if the table doesn't exist or the read fails.
    """
    defaults = {
        "minimum_ios_version": "2.1.0",
        "latest_ios_version": "2.1.0",
        "update_message": "A new version of Powder Chaser is available with important improvements. Please update to continue.",
        "update_url": "https://apps.apple.com/app/id6758333173",
        "force_update": False,
    }

    try:
        environment = os.environ.get("ENVIRONMENT", "dev")
        table = get_dynamodb().Table(f"snow-tracker-app-config-{environment}")
        response = table.get_item(Key={"config_id": "ios"})
        item = response.get("Item")
        if item:
            # Merge DynamoDB values over defaults (only known keys)
            for key in defaults:
                if key in item and isinstance(item[key], type(defaults[key])):
                    defaults[key] = item[key]
    except ClientError:
        logger.warning("Failed to read app config from DynamoDB, using defaults")
    except Exception:
        logger.warning(
            "Unexpected error reading app config from DynamoDB, using defaults",
            exc_info=True,
        )

    return defaults


# MARK: - Resort Endpoints


# Valid region codes for filtering
VALID_REGIONS = [
    "na_west",
    "na_rockies",
    "na_east",
    "alps",
    "scandinavia",
    "japan",
    "oceania",
    "south_america",
]


def infer_resort_region(resort: Resort) -> str:
    """Infer the region based on country and longitude."""
    country = resort.country.upper()

    if country in ("CA", "US"):
        # Use longitude to distinguish NA regions
        if resort.elevation_points:
            lon = resort.elevation_points[0].longitude
            if lon < -115:
                return "na_west"
            elif lon < -100:
                return "na_rockies"
            else:
                return "na_east"
        return "na_rockies"  # Default for NA
    elif country in ("FR", "CH", "AT", "IT", "DE"):
        return "alps"
    elif country in ("NO", "SE", "FI"):
        return "scandinavia"
    elif country == "JP":
        return "japan"
    elif country in ("AU", "NZ"):
        return "oceania"
    elif country in ("CL", "AR"):
        return "south_america"
    else:
        return "alps"  # Default


@app.get("/api/v1/regions")
async def get_regions(response: Response):
    """Get list of available ski regions with resort counts."""
    try:
        resorts = _get_all_resorts_cached()

        # Count resorts per region
        region_counts = {}
        for resort in resorts:
            region = infer_resort_region(resort)
            region_counts[region] = region_counts.get(region, 0) + 1

        region_info = {
            "na_west": {
                "name": "North America - West",
                "display_name": "NA West Coast",
            },
            "na_rockies": {
                "name": "North America - Rockies",
                "display_name": "Rockies",
            },
            "na_east": {
                "name": "North America - East",
                "display_name": "NA East Coast",
            },
            "alps": {"name": "European Alps", "display_name": "Alps"},
            "scandinavia": {"name": "Scandinavia", "display_name": "Scandinavia"},
            "japan": {"name": "Japan", "display_name": "Japan"},
            "oceania": {"name": "Australia & New Zealand", "display_name": "Oceania"},
            "south_america": {"name": "South America", "display_name": "South America"},
        }

        regions = []
        for region_id in VALID_REGIONS:
            count = region_counts.get(region_id, 0)
            if count > 0:
                info = region_info.get(
                    region_id, {"name": region_id, "display_name": region_id}
                )
                regions.append(
                    {
                        "id": region_id,
                        "name": info["name"],
                        "display_name": info["display_name"],
                        "resort_count": count,
                    }
                )

        response.headers["Cache-Control"] = CACHE_CONTROL_PUBLIC

        return {"regions": regions}

    except Exception as e:
        logger.error("Regions error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve regions",
        )


def _has_valid_coordinates(resort: Resort) -> bool:
    """Check if a resort has valid (non-zero) coordinates."""
    if not resort.elevation_points:
        return False
    # Check if any elevation point has valid coordinates
    for ep in resort.elevation_points:
        if ep.latitude != 0.0 or ep.longitude != 0.0:
            return True
    return False


VALID_SORT_BY = ["name", "quality_score", "snowfall", "elevation"]
# Default sort order per sort_by field
_DEFAULT_SORT_ORDER = {
    "name": "asc",
    "quality_score": "desc",
    "snowfall": "desc",
    "elevation": "desc",
}


def _sort_resorts(
    resorts: list[Resort],
    sort_by: str,
    sort_order: str,
) -> list[Resort]:
    """Sort resorts by the given field and order.

    For quality_score and snowfall, data is loaded from the S3 static JSON
    (the same file used by the batch snow-quality endpoint).
    Resorts without data sort last regardless of sort order.
    """
    reverse = sort_order == "desc"

    if sort_by == "name":
        return sorted(resorts, key=lambda r: r.name.lower(), reverse=reverse)

    if sort_by == "elevation":
        # Sort by top elevation (meters). Resorts without top elevation sort last.
        def _elev_key(r: Resort) -> tuple[bool, float]:
            top = r.top_elevation
            if top is not None:
                return (
                    False,
                    -top.elevation_meters if reverse else top.elevation_meters,
                )
            return (True, 0)

        return sorted(resorts, key=_elev_key)

    # quality_score or snowfall — need S3 static JSON data
    snow_quality_data = _get_static_snow_quality_from_s3() or {}

    if sort_by == "quality_score":

        def _score_key(r: Resort) -> tuple[bool, float]:
            entry = snow_quality_data.get(r.resort_id)
            if entry and entry.get("snow_score") is not None:
                score = entry["snow_score"]
                return (False, -score if reverse else score)
            return (True, 0)

        return sorted(resorts, key=_score_key)

    if sort_by == "snowfall":

        def _snowfall_key(r: Resort) -> tuple[bool, float]:
            entry = snow_quality_data.get(r.resort_id)
            if entry and entry.get("snowfall_fresh_cm") is not None:
                val = entry["snowfall_fresh_cm"]
                return (False, -val if reverse else val)
            return (True, 0)

        return sorted(resorts, key=_snowfall_key)

    # Fallback (should not reach here due to validation)
    return resorts


@app.get("/api/v1/resorts")
async def get_resorts(
    response: Response,
    country: str | None = Query(
        None, description="Filter by country code (CA, US, FR, etc.)"
    ),
    region: str | None = Query(
        None, description="Filter by region (na_west, alps, japan, etc.)"
    ),
    sort_by: str = Query(
        "name",
        description="Sort field: name, quality_score, snowfall, elevation",
    ),
    sort_order: str | None = Query(
        None,
        description="Sort order: asc or desc. Defaults depend on sort_by "
        "(asc for name, desc for others)",
    ),
    limit: int | None = Query(
        None, ge=1, le=500, description="Maximum number of resorts to return"
    ),
    offset: int = Query(
        0, ge=0, description="Number of resorts to skip (for pagination)"
    ),
    include_no_coords: bool = Query(
        False,
        description="Include resorts without valid coordinates (default: exclude)",
    ),
):
    """Get all ski resorts, optionally filtered by country or region.

    By default, resorts with invalid (0,0) coordinates are excluded.
    Use include_no_coords=true to include them.

    Supports sorting via sort_by and sort_order parameters.
    Supports pagination via limit and offset parameters.
    Sorting is applied before pagination so pages are consistent.
    """
    try:
        # Validate sort_by
        if sort_by not in VALID_SORT_BY:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid sort_by. Must be one of: {VALID_SORT_BY}",
            )

        # Validate sort_order
        effective_sort_order = sort_order or _DEFAULT_SORT_ORDER[sort_by]
        if effective_sort_order not in ("asc", "desc"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid sort_order. Must be 'asc' or 'desc'",
            )

        # Validate region if provided
        if region and region not in VALID_REGIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid region. Must be one of: {VALID_REGIONS}",
            )

        resorts = _get_all_resorts_cached()

        # Filter out resorts with invalid coordinates (unless explicitly included)
        if not include_no_coords:
            resorts = [r for r in resorts if _has_valid_coordinates(r)]

        # Apply region filter
        if region:
            resorts = [r for r in resorts if infer_resort_region(r) == region]

        # Apply country filter
        if country:
            resorts = [r for r in resorts if r.country.upper() == country.upper()]

        # Apply sorting BEFORE pagination
        resorts = _sort_resorts(resorts, sort_by, effective_sort_order)

        # Track total before pagination
        total_count = len(resorts)

        # Apply pagination
        resorts = resorts[offset:]
        if limit is not None:
            resorts = resorts[:limit]

        # Set cache headers - resort data is public and can be cached
        response.headers["Cache-Control"] = CACHE_CONTROL_PUBLIC

        return {"resorts": resorts, "total_count": total_count}

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Resorts error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve resorts",
        )


@cached_resorts
def _get_all_resorts_cached():
    """Get all resorts, preferring static S3 JSON over DynamoDB.

    Tries to fetch from pre-computed S3 static JSON first (faster, cheaper),
    falls back to DynamoDB scan if static file not available.
    """
    # Try static S3 JSON first (pre-computed, cached at edge)
    static_resorts = _get_static_resorts_from_s3()
    if static_resorts is not None:
        # Convert dicts to Resort objects for compatibility
        return [Resort(**r) for r in static_resorts]

    # Fall back to DynamoDB scan
    return get_resort_service().get_all_resorts()


@app.get("/api/v1/resorts/nearby")
async def get_nearby_resorts(
    response: Response,
    lat: float = Query(..., ge=-90, le=90, description="User's latitude"),
    lon: float | None = Query(None, ge=-180, le=180, description="User's longitude"),
    lng: float | None = Query(
        None, ge=-180, le=180, description="User's longitude (alias for lon)"
    ),
    radius: float = Query(
        200, ge=1, le=2000, description="Search radius in kilometers (default 200km)"
    ),
    limit: int = Query(20, ge=1, le=50, description="Maximum results (default 20)"),
):
    """
    Find ski resorts near a given location.

    Returns resorts sorted by distance from the provided coordinates,
    within the specified radius. Each resort includes its distance in
    both kilometers and miles.

    Accepts either `lon` or `lng` for longitude (both are supported).
    """
    # Accept both lon and lng as aliases for longitude
    longitude = lon if lon is not None else lng
    if longitude is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Either 'lon' or 'lng' query parameter is required",
        )

    try:
        nearby = get_resort_service().get_nearby_resorts(
            latitude=lat,
            longitude=longitude,
            radius_km=radius,
            limit=limit,
        )

        # Format response with distances
        results = []
        for resort, distance_km in nearby:
            results.append(
                {
                    "resort": resort,
                    "distance_km": distance_km,
                    "distance_miles": round(distance_km * 0.621371, 1),
                }
            )

        response.headers["Cache-Control"] = CACHE_CONTROL_PUBLIC

        return {
            "resorts": results,
            "count": len(results),
            "search_center": {"latitude": lat, "longitude": longitude},
            "search_radius_km": radius,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Nearby resorts error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to find nearby resorts",
        )


@app.get("/api/v1/resorts/{resort_id}", response_model=Resort)
async def get_resort(resort_id: str, response: Response):
    """Get details for a specific resort."""
    _validate_resource_id(resort_id, "resort_id")
    try:
        resort = _get_resort_cached(resort_id)
        if not resort:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resort not found",
            )

        # Set cache headers
        response.headers["Cache-Control"] = CACHE_CONTROL_PUBLIC

        return resort

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Resort detail error for %s: %s", resort_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve resort",
        )


@cached_resorts
def _get_resort_cached(resort_id: str):
    """Cached wrapper for getting a single resort."""
    return get_resort_service().get_resort(resort_id)


# MARK: - Weather Condition Endpoints


@app.get("/api/v1/conditions/batch")
async def get_batch_conditions(
    response: Response,
    resort_ids: str = Query(..., description="Comma-separated resort IDs (max 50)"),
    hours: int | None = Query(
        24, description="Hours of historical data to retrieve", ge=1, le=168
    ),
):
    """Get conditions for multiple resorts in a single request.

    This endpoint reduces API calls by allowing batch fetching of up to 50 resorts.
    Fetches are done in parallel using ThreadPoolExecutor.
    Returns conditions keyed by resort_id.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    try:
        # Parse and validate resort IDs
        ids = [id.strip() for id in resort_ids.split(",") if id.strip()]

        if not ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No resort IDs provided",
            )

        if len(ids) > 50:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum 50 resorts per batch request",
            )

        # Fetch conditions for all resorts IN PARALLEL using ThreadPoolExecutor
        results = {}

        def fetch_one(resort_id: str):
            try:
                conditions = _get_conditions_cached(resort_id, hours)
                # Convert to lightweight API format (excludes raw_data)
                api_conditions = [c.to_api_response() for c in conditions]
                return resort_id, {"conditions": api_conditions, "error": None}
            except Exception as e:
                return resort_id, {"conditions": [], "error": str(e)}

        # Use ThreadPoolExecutor for true parallel execution
        with ThreadPoolExecutor(max_workers=min(len(ids), 10)) as executor:
            futures = {executor.submit(fetch_one, rid): rid for rid in ids}
            for future in as_completed(futures, timeout=30):
                resort_id, result = future.result()
                results[resort_id] = result

        # Set cache headers
        response.headers["Cache-Control"] = CACHE_CONTROL_PUBLIC

        return {
            "results": results,
            "last_updated": datetime.now(UTC).isoformat(),
            "resort_count": len(results),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Batch conditions error for %d resorts: %s", len(ids), e, exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve batch conditions",
        )


@app.get("/api/v1/resorts/{resort_id}/conditions")
async def get_resort_conditions(
    resort_id: str,
    response: Response,
    hours: int | None = Query(
        24, description="Hours of historical data to retrieve", ge=1, le=168
    ),
):
    """Get current and recent weather conditions for all elevations at a resort."""
    _validate_resource_id(resort_id, "resort_id")
    try:
        # Verify resort exists
        resort = _get_resort_cached(resort_id)
        if not resort:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resort not found",
            )

        # Get conditions for the specified time range (cached)
        conditions = _get_conditions_cached(resort_id, hours)

        # Convert to lightweight API format (excludes raw_data)
        api_conditions = [c.to_api_response() for c in conditions]

        # Set cache headers - conditions are updated hourly, 60s cache is safe
        response.headers["Cache-Control"] = CACHE_CONTROL_PUBLIC

        return {
            "conditions": api_conditions,
            "last_updated": datetime.now(UTC).isoformat(),
            "resort_id": resort_id,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Conditions error for %s: %s", resort_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve conditions",
        )


@cached_conditions
def _get_conditions_cached(resort_id: str, hours: int):
    """Cached wrapper for getting resort conditions."""
    return get_weather_service().get_conditions_for_resort(resort_id, hours_back=hours)


@app.get("/api/v1/resorts/{resort_id}/conditions/{elevation_level}")
async def get_elevation_condition(
    resort_id: str, elevation_level: str, response: Response
):
    """Get current weather conditions for a specific elevation at a resort."""
    _validate_resource_id(resort_id, "resort_id")
    try:
        # Validate elevation level
        valid_levels = ["base", "mid", "top"]
        if elevation_level not in valid_levels:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid elevation level. Must be one of: {valid_levels}",
            )

        # Verify resort exists
        resort = _get_resort_cached(resort_id)
        if not resort:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resort not found",
            )

        # Get latest condition for the specific elevation (cached)
        condition = _get_latest_condition_cached(resort_id, elevation_level)
        if not condition:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No conditions found for this resort at the specified elevation",
            )

        # Set cache headers
        response.headers["Cache-Control"] = CACHE_CONTROL_PUBLIC

        return condition

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Condition error for %s/%s: %s",
            resort_id,
            elevation_level,
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve condition",
        )


@cached_conditions
def _get_latest_condition_cached(resort_id: str, elevation_level: str):
    """Cached wrapper for getting latest condition at elevation."""
    return get_weather_service().get_latest_condition(resort_id, elevation_level)


@app.get("/api/v1/resorts/{resort_id}/snow-quality")
async def get_snow_quality_summary(resort_id: str, response: Response):
    """Get snow quality summary for all elevations at a resort."""
    _validate_resource_id(resort_id, "resort_id")
    try:
        # Verify resort exists
        resort = _get_resort_cached(resort_id)
        if not resort:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resort not found",
            )

        # Get latest conditions for all elevations in a single query
        conditions = get_weather_service().get_latest_conditions_all_elevations(
            resort_id
        )

        if not conditions:
            return {
                "resort_id": resort_id,
                "elevations": {},
                "overall_quality": SnowQuality.UNKNOWN.value,
                "last_updated": None,
            }

        # Analyze conditions for summary
        elevation_summaries = {}

        for condition in conditions:
            quality = condition.snow_quality
            quality_val = quality.value if hasattr(quality, "value") else str(quality)
            confidence = condition.confidence_level
            confidence_val = (
                confidence.value if hasattr(confidence, "value") else str(confidence)
            )
            # Compute 0-100 snow score from ML model raw score
            raw_score = condition.quality_score
            snow_score = score_to_100(raw_score) if raw_score is not None else None
            # Generate natural language explanation
            explanation = generate_quality_explanation(condition)
            elevation_summaries[condition.elevation_level] = {
                "quality": quality_val,
                "snow_score": snow_score,
                "fresh_snow_cm": condition.fresh_snow_cm,
                "confidence": confidence_val,
                "temperature_celsius": condition.current_temp_celsius,
                "snowfall_24h_cm": condition.snowfall_24h_cm,
                "explanation": explanation,
                "timestamp": condition.timestamp,
            }

        # Find representative condition (mid > top > base) for score, explanation,
        # and temperature/snowfall fields. Using a single elevation's score
        # ensures consistency with the timeline view and explanation text.
        representative = None
        for pref in ["mid", "top", "base"]:
            for c in conditions:
                if c.elevation_level == pref:
                    representative = c
                    break
            if representative:
                break
        if not representative and conditions:
            representative = conditions[0]

        # Use representative elevation's raw score for overall quality
        # (matches timeline default view and explanation text)
        if representative and representative.quality_score is not None:
            overall_raw_score = representative.quality_score
            overall_snow_score = score_to_100(overall_raw_score)
            overall_quality = raw_score_to_quality(overall_raw_score)
        else:
            overall_quality = SnowQualityService.calculate_overall_quality(conditions)
            overall_snow_score = None

        # Get explanation for overall quality
        quality_explanation = SNOW_QUALITY_EXPLANATIONS.get(overall_quality, {})

        # Generate overall explanation matching the representative quality level.
        # Pass representative to ensure explanation temperature matches
        # the elevation used for the score.
        overall_explanation = generate_overall_explanation(
            conditions, overall_quality, representative=representative
        )

        # Set cache headers - 1 hour since weather updates hourly
        response.headers["Cache-Control"] = CACHE_CONTROL_PUBLIC_LONG

        return {
            "resort_id": resort_id,
            "elevations": elevation_summaries,
            "overall_quality": overall_quality.value,
            "overall_snow_score": overall_snow_score,
            "overall_explanation": overall_explanation,
            "quality_info": {
                "title": quality_explanation.get("title", overall_quality.value),
                "description": quality_explanation.get("description", ""),
                "criteria": quality_explanation.get("criteria", ""),
            },
            "last_updated": max(c.timestamp for c in conditions)
            if conditions
            else None,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Snow quality error for %s: %s", resort_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve snow quality summary",
        )


@app.get("/api/v1/resorts/{resort_id}/history")
async def get_resort_history(
    resort_id: str,
    response: Response,
    start_date: str | None = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: str | None = Query(None, description="End date (YYYY-MM-DD)"),
    season: str | None = Query(
        None, description="Season (e.g. '2025-2026'), overrides start/end dates"
    ),
):
    """Get daily snow history and season summary for a resort.

    Returns daily snowfall history records and season summary statistics.
    If season is provided (e.g. "2025-2026"), computes Oct 1 to Apr 30 range.
    """
    _validate_resource_id(resort_id, "resort_id")
    try:
        # Verify resort exists
        resort = _get_resort_cached(resort_id)
        if not resort:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resort not found",
            )

        # If season is provided, compute date range
        season_start = None
        if season:
            try:
                parts = season.split("-")
                start_year = int(parts[0])
                end_year = int(parts[1])
                start_date = f"{start_year}-10-01"
                end_date = f"{end_year}-04-30"
                season_start = start_date
            except (ValueError, IndexError):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid season format. Expected 'YYYY-YYYY' (e.g. '2025-2026')",
                )

        daily_history_svc = get_daily_history_service()

        # Get history records
        history = daily_history_svc.get_history(
            resort_id=resort_id,
            start_date=start_date,
            end_date=end_date,
        )

        # Get season summary
        if not season_start:
            # Default to current season (Oct of previous year or current year)
            now = datetime.now(UTC)
            if now.month >= 10:
                season_start = f"{now.year}-10-01"
            else:
                season_start = f"{now.year - 1}-10-01"

        season_summary = daily_history_svc.get_season_summary(
            resort_id=resort_id,
            season_start=season_start,
        )

        # Also get the season total from snow_summary table for mid elevation
        try:
            snow_summary_table = get_dynamodb().Table(
                os.environ.get("SNOW_SUMMARY_TABLE", "snow-tracker-snow-summary-dev")
            )
            from services.snow_summary_service import SnowSummaryService

            snow_summary_svc = SnowSummaryService(snow_summary_table)
            mid_summary = snow_summary_svc.get_summary(resort_id, "mid")
            if mid_summary and mid_summary.get("total_season_snowfall_cm"):
                season_summary["total_season_snowfall_cm_accumulated"] = mid_summary[
                    "total_season_snowfall_cm"
                ]
        except Exception as e:
            logger.warning(
                "Failed to get accumulated season total for %s: %s", resort_id, e
            )

        # Set cache headers - 1 hour
        response.headers["Cache-Control"] = CACHE_CONTROL_PUBLIC_LONG

        return {
            "resort_id": resort_id,
            "history": history,
            "season_summary": season_summary,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching history for {resort_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve snow history",
        )


def _overlay_conditions_on_timeline(
    timeline_data: dict,
    resort_id: str,
    elevation: str,
) -> None:
    """Overlay actual conditions/history data onto the Open-Meteo timeline.

    The timeline fetches from Open-Meteo directly, which can disagree with
    the multi-source merged conditions stored in DynamoDB (e.g., Open-Meteo
    says 0cm snowfall while OnTheSnow reports 20cm). This creates wildly
    inconsistent data across the app.

    This function overlays the actual merged data onto today's timeline
    entries and daily history onto past entries, so the timeline is
    consistent with the snow-quality and conditions endpoints.
    """
    try:
        # Get current conditions from DynamoDB (merged multi-source data)
        conditions = get_weather_service().get_latest_conditions_all_elevations(
            resort_id
        )
        condition = next(
            (c for c in conditions if c.elevation_level == elevation), None
        )

        # Get daily history for past days
        history = get_daily_history_service().get_history(resort_id)
        history_by_date = {h["date"]: h for h in history}

        today = datetime.now(UTC).strftime("%Y-%m-%d")
        timeline = timeline_data.get("timeline", [])

        for point in timeline:
            date = point["date"]

            if date == today and condition:
                # Overlay current conditions for today
                if condition.snow_depth_cm is not None:
                    point["snow_depth_cm"] = round(condition.snow_depth_cm, 1)

                # Distribute daily snowfall evenly across 3 time slots
                daily_snow = condition.snowfall_24h_cm or 0
                point["snowfall_cm"] = round(daily_snow / 3, 1)

                # Overlay quality/score from merged conditions
                if condition.quality_score is not None:
                    raw_score = condition.quality_score
                    quality = raw_score_to_quality(raw_score)
                    quality_val = (
                        quality.value if hasattr(quality, "value") else str(quality)
                    )
                    point["quality_score"] = round(raw_score, 2)
                    point["snow_score"] = score_to_100(raw_score)
                    point["snow_quality"] = quality_val
                    point["explanation"] = generate_timeline_explanation(
                        quality=quality_val,
                        temperature_c=point["temperature_c"],
                        snowfall_cm=point["snowfall_cm"],
                        snow_depth_cm=point["snow_depth_cm"],
                        wind_speed_kmh=point.get("wind_speed_kmh"),
                        is_forecast=point.get("is_forecast", False),
                        wind_gust_kmh=point.get("wind_gust_kmh"),
                        visibility_m=point.get("visibility_m"),
                    )

            elif date < today and date in history_by_date:
                # Overlay history data for past days
                h = history_by_date[date]

                if h.get("snow_depth_cm") is not None:
                    point["snow_depth_cm"] = round(h["snow_depth_cm"], 1)

                daily_snow = h.get("snowfall_24h_cm", 0)
                point["snowfall_cm"] = round(daily_snow / 3, 1)

                if h.get("quality_score") is not None:
                    raw_score = h["quality_score"]
                    quality_str = h.get("snow_quality", point["snow_quality"])
                    point["quality_score"] = round(raw_score, 2)
                    point["snow_score"] = score_to_100(raw_score)
                    point["snow_quality"] = quality_str
                    point["explanation"] = generate_timeline_explanation(
                        quality=quality_str,
                        temperature_c=point["temperature_c"],
                        snowfall_cm=point["snowfall_cm"],
                        snow_depth_cm=point["snow_depth_cm"],
                        wind_speed_kmh=point.get("wind_speed_kmh"),
                        is_forecast=False,
                        wind_gust_kmh=point.get("wind_gust_kmh"),
                        visibility_m=point.get("visibility_m"),
                    )

        # Re-run score change reasons after overlay
        for i, point in enumerate(timeline):
            prev = timeline[i - 1] if i > 0 else None
            point["score_change_reason"] = generate_score_change_reason(point, prev)

    except Exception as e:
        # Best-effort overlay — if it fails, return original Open-Meteo data
        logger.warning(
            "Failed to overlay conditions on timeline for %s: %s", resort_id, e
        )


@app.get("/api/v1/resorts/{resort_id}/timeline")
async def get_resort_timeline(
    resort_id: str,
    response: Response,
    elevation: str = Query("mid", description="Elevation level: base, mid, or top"),
):
    """Get conditions timeline for a resort at a given elevation.

    Returns 3 data points per day (morning, midday, afternoon) over
    7 days past and 7 days forecast, including temperature, snowfall,
    snow depth, and snow quality assessment.
    """
    _validate_resource_id(resort_id, "resort_id")
    try:
        # Validate elevation
        valid_levels = ["base", "mid", "top"]
        if elevation not in valid_levels:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid elevation level. Must be one of: {valid_levels}",
            )

        # Look up resort
        resort = _get_resort_cached(resort_id)
        if not resort:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resort not found",
            )

        # Find the matching elevation point
        elevation_point = None
        for ep in resort.elevation_points:
            if ep.level == elevation:
                elevation_point = ep
                break

        if not elevation_point:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Elevation level not found for this resort",
            )

        # Check server-side cache first
        timeline_cache = get_timeline_cache()
        cache_key = f"{resort_id}:{elevation}"
        if cache_key in timeline_cache:
            response.headers["Cache-Control"] = "public, max-age=1800"
            response.headers["X-Cache"] = "HIT"
            return timeline_cache[cache_key]

        # Fetch timeline data from Open-Meteo
        service = OpenMeteoService()
        timeline_data = service.get_timeline_data(
            latitude=elevation_point.latitude,
            longitude=elevation_point.longitude,
            elevation_meters=elevation_point.elevation_meters,
            elevation_level=elevation,
        )

        # Overlay actual conditions/history data from DynamoDB onto the
        # Open-Meteo timeline. Without this, the timeline uses raw Open-Meteo
        # data which can wildly disagree with the multi-source merged
        # conditions (e.g., showing score 22 when snow-quality shows 94).
        _overlay_conditions_on_timeline(timeline_data, resort_id, elevation)

        # Add resort_id to the response
        timeline_data["resort_id"] = resort_id

        # Cache the result (30-min TTL)
        timeline_cache[cache_key] = timeline_data

        # Set cache headers (30 min cache)
        response.headers["Cache-Control"] = "public, max-age=1800"
        response.headers["X-Cache"] = "MISS"

        return timeline_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Timeline error for %s/%s: %s", resort_id, elevation, e, exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve timeline",
        )


@cached_snow_quality
def _get_snow_quality_for_resort(resort_id: str) -> dict | None:
    """Cached helper to get snow quality summary for a single resort."""
    resort = _get_resort_cached(resort_id)
    if not resort:
        return None

    # Single query to get latest condition per elevation (instead of 3 separate queries)
    conditions = get_weather_service().get_latest_conditions_all_elevations(resort_id)

    if not conditions:
        return {
            "resort_id": resort_id,
            "overall_quality": SnowQuality.UNKNOWN.value,
            "last_updated": None,
            "temperature_c": None,
            "snowfall_fresh_cm": None,
            "snowfall_24h_cm": None,
            "snow_depth_cm": None,
            "predicted_snow_48h_cm": None,
        }

    # Get representative condition for temperature/snowfall/score fields (prefer mid)
    # Mid elevation best represents typical skiing conditions and matches
    # the detail endpoint and static JSON generator (timeline default view).
    representative = None
    for pref in ["mid", "top", "base"]:
        for c in conditions:
            if c.elevation_level == pref:
                representative = c
                break
        if representative:
            break
    if not representative:
        representative = conditions[0]

    # Use weighted average across all elevations for overall quality
    # Weights: top 50%, mid 35%, base 15% (matches recommendation service)
    weighted_raw = 0.0
    total_w = 0.0
    for c in conditions:
        if c.quality_score is not None:
            w = ELEVATION_WEIGHTS.get(c.elevation_level, DEFAULT_ELEVATION_WEIGHT)
            weighted_raw += c.quality_score * w
            total_w += w

    if total_w > 0:
        overall_raw = weighted_raw / total_w
        snow_score = score_to_100(overall_raw)
        overall_quality = raw_score_to_quality(overall_raw)
    else:
        overall_quality = SnowQualityService.calculate_overall_quality(conditions)
        snow_score = None

    return {
        "resort_id": resort_id,
        "overall_quality": overall_quality.value,
        "snow_score": snow_score,
        "explanation": generate_overall_explanation(
            conditions, overall_quality, representative=representative
        ),
        "last_updated": max(c.timestamp for c in conditions) if conditions else None,
        "temperature_c": representative.current_temp_celsius
        if representative
        else None,
        "snowfall_fresh_cm": representative.fresh_snow_cm if representative else None,
        "snowfall_24h_cm": representative.snowfall_24h_cm if representative else None,
        "snow_depth_cm": representative.snow_depth_cm if representative else None,
        "predicted_snow_48h_cm": representative.predicted_snow_48h_cm
        if representative
        else None,
    }


@app.get("/api/v1/snow-quality/batch")
async def get_batch_snow_quality(
    response: Response,
    resort_ids: str = Query(..., description="Comma-separated list of resort IDs"),
):
    """Get snow quality summaries for multiple resorts in a single request.

    This is optimized for the resort list view where we need quality indicators
    for many resorts at once. Returns lightweight summaries (just overall quality).
    Supports up to 200 resorts per request for efficient bulk loading.

    Uses pre-computed static JSON from S3 when available for faster response.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    try:
        ids = [id.strip() for id in resort_ids.split(",") if id.strip()]

        if not ids:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No resort IDs provided",
            )

        # Increased limit to 200 for efficient bulk loading
        if len(ids) > 200:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum 200 resorts per batch request",
            )

        # Try to use pre-computed static JSON from S3 (much faster)
        static_quality = _get_static_snow_quality_from_s3()
        if static_quality is not None:
            # Filter to only requested IDs
            results = {rid: static_quality[rid] for rid in ids if rid in static_quality}

            # For any missing resorts, fall back to DynamoDB lookup
            missing_ids = [rid for rid in ids if rid not in results]
            if missing_ids:

                def fetch_quality(resort_id: str):
                    try:
                        summary = _get_snow_quality_for_resort(resort_id)
                        return resort_id, summary
                    except Exception as e:
                        return resort_id, {"error": str(e)}

                max_workers = min(len(missing_ids), 10)
                with ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = {
                        executor.submit(fetch_quality, rid): rid for rid in missing_ids
                    }
                    for future in as_completed(futures, timeout=30):
                        resort_id, result = future.result()
                        if result:
                            results[resort_id] = result

            response.headers["Cache-Control"] = CACHE_CONTROL_PUBLIC_LONG
            return {
                "results": results,
                "last_updated": datetime.now(UTC).isoformat(),
                "resort_count": len(results),
                "source": "static",
            }

        # Fall back to DynamoDB lookup for all resorts
        results = {}

        def fetch_quality(resort_id: str):
            try:
                summary = _get_snow_quality_for_resort(resort_id)
                return resort_id, summary
            except Exception as e:
                return resort_id, {"error": str(e)}

        # Fetch all in parallel with more workers for larger batches
        max_workers = min(len(ids), 10)  # Cap at 10 to avoid thread contention
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(fetch_quality, rid): rid for rid in ids}
            for future in as_completed(futures, timeout=30):
                resort_id, result = future.result()
                if result:
                    results[resort_id] = result

        # Use 1-hour cache since weather data updates hourly
        response.headers["Cache-Control"] = CACHE_CONTROL_PUBLIC_LONG

        return {
            "results": results,
            "last_updated": datetime.now(UTC).isoformat(),
            "resort_count": len(results),
            "source": "dynamodb",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Batch snow quality error for %d resorts: %s", len(ids), e, exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve batch snow quality",
        )


@app.get("/api/v1/quality-explanations")
async def get_quality_explanations(response: Response):
    """Get explanations for all snow quality levels.

    Returns descriptions of what each quality level means,
    useful for displaying info tooltips in the UI.
    """
    response.headers["Cache-Control"] = CACHE_CONTROL_PUBLIC

    explanations = {}
    for quality in SnowQuality:
        info = SNOW_QUALITY_EXPLANATIONS.get(quality, {})
        explanations[quality.value] = {
            "title": info.get("title", quality.value.title()),
            "description": info.get("description", ""),
            "criteria": info.get("criteria", ""),
        }

    return {
        "explanations": explanations,
        "algorithm_info": {
            "description": "Quality is predicted by an ML model (ensemble of 10 neural networks) trained on 2200+ real snow conditions across 129 resorts.",
            "features": "27 features including fresh snow, temperature, freeze-thaw history, wind, snowfall trends, and elevation",
            "elevation_weights": "Overall score weighted: 50% summit, 35% mid-mountain, 15% base",
            "note": "Thaw-freeze events (sustained above-freezing temps) reset the fresh snow counter. Snow quality degrades when surface refreezes after warming.",
        },
    }


# MARK: - User Endpoints


@app.get("/api/v1/user/preferences", response_model=UserPreferences)
async def get_user_preferences(
    response: Response, user_id: str = Depends(get_current_user_id)
):
    """Get user preferences."""
    try:
        preferences = get_user_service().get_user_preferences(user_id)
        if not preferences:
            # Return default preferences for new users
            preferences = UserPreferences(
                user_id=user_id,
                favorite_resorts=[],
                notification_preferences={
                    "snow_alerts": True,
                    "condition_updates": True,
                    "weekly_summary": False,
                },
                preferred_units={
                    "temperature": "celsius",
                    "distance": "metric",
                    "snow_depth": "cm",
                },
                quality_threshold="decent",
                created_at=datetime.now(UTC).isoformat(),
                updated_at=datetime.now(UTC).isoformat(),
            )

        # User data is private, don't cache
        response.headers["Cache-Control"] = CACHE_CONTROL_PRIVATE

        return preferences

    except Exception as e:
        logger.error("User preferences error for %s: %s", user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve user preferences",
        )


@app.put("/api/v1/user/preferences")
async def update_user_preferences(
    preferences: UserPreferences, user_id: str = Depends(get_current_user_id)
):
    """Update user preferences."""
    try:
        # Ensure the user_id in the request matches the authenticated user
        preferences.user_id = user_id
        preferences.updated_at = datetime.now(UTC).isoformat()

        get_user_service().save_user_preferences(preferences)

        return {"message": "Preferences updated successfully"}

    except Exception as e:
        logger.error(
            "Update user preferences error for %s: %s", user_id, e, exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update user preferences",
        )


# MARK: - Device Token Endpoints


class DeviceTokenRequest(BaseModel):
    """Request body for registering a device token."""

    device_id: str = Field(..., description="Unique device identifier")
    token: str = Field(..., description="APNs device token")
    platform: str = Field(default="ios", description="Platform (ios, android)")
    app_version: str | None = Field(None, description="App version")


_notification_service = None
_device_tokens_table = None


def get_device_tokens_table():
    """Get or create device tokens table (lazy init for SnapStart)."""
    global _device_tokens_table
    if _device_tokens_table is None:
        _device_tokens_table = get_dynamodb().Table(
            os.environ.get("DEVICE_TOKENS_TABLE", "snow-tracker-device-tokens-dev")
        )
    return _device_tokens_table


def get_notification_service():
    """Get or create NotificationService (lazy init for SnapStart)."""
    global _notification_service
    if _notification_service is None:
        from services.notification_service import NotificationService

        dynamodb = get_dynamodb()
        _notification_service = NotificationService(
            device_tokens_table=get_device_tokens_table(),
            user_preferences_table=dynamodb.Table(
                os.environ.get(
                    "USER_PREFERENCES_TABLE", "snow-tracker-user-preferences-dev"
                )
            ),
            resort_events_table=dynamodb.Table(
                os.environ.get("RESORT_EVENTS_TABLE", "snow-tracker-resort-events-dev")
            ),
            weather_conditions_table=dynamodb.Table(
                os.environ.get(
                    "WEATHER_CONDITIONS_TABLE", "snow-tracker-weather-conditions-dev"
                )
            ),
            resorts_table=dynamodb.Table(
                os.environ.get("RESORTS_TABLE", "snow-tracker-resorts-dev")
            ),
        )
    return _notification_service


@app.post("/api/v1/user/device-tokens", status_code=status.HTTP_201_CREATED)
async def register_device_token(
    request: DeviceTokenRequest,
    user_id: str | None = Depends(get_optional_user_id),
):
    """Register a device token for push notifications.

    This endpoint should be called when the app receives an APNs token.
    Tokens are automatically expired after 90 days if not refreshed.
    Auth is optional - if not authenticated, device_id is used as the user identifier.
    """
    try:
        # Use device_id as fallback user identifier if not authenticated
        effective_user_id = user_id or f"device:{request.device_id}"

        device_token = get_notification_service().register_device_token(
            user_id=effective_user_id,
            device_id=request.device_id,
            token=request.token,
            platform=request.platform,
            app_version=request.app_version,
        )

        return {
            "message": "Device token registered successfully",
            "device_id": device_token.device_id,
        }

    except Exception as e:
        logger.error(
            "Register device token error for %s: %s",
            request.device_id,
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to register device token",
        )


@app.delete(
    "/api/v1/user/device-tokens/{device_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def unregister_device_token(
    device_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Unregister a device token.

    Call this when the user signs out or disables notifications.
    """
    try:
        get_notification_service().unregister_device_token(user_id, device_id)
        return None

    except Exception as e:
        logger.error(
            "Unregister device token error for %s/%s: %s",
            user_id,
            device_id,
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to unregister device token",
        )


@app.get("/api/v1/user/device-tokens")
async def get_device_tokens(
    response: Response,
    user_id: str = Depends(get_current_user_id),
):
    """Get all registered device tokens for the current user."""
    try:
        tokens = get_notification_service().get_user_device_tokens(user_id)

        response.headers["Cache-Control"] = CACHE_CONTROL_PRIVATE

        return {
            "tokens": [
                {
                    "device_id": t.device_id,
                    "platform": t.platform,
                    "app_version": t.app_version,
                    "created_at": t.created_at,
                }
                for t in tokens
            ],
            "count": len(tokens),
        }

    except Exception as e:
        logger.error("Get device tokens error for %s: %s", user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve device tokens",
        )


# MARK: - Notification Settings Endpoints


class NotificationSettingsRequest(BaseModel):
    """Request body for updating notification settings."""

    notifications_enabled: bool | None = Field(
        None, description="Master switch for all notifications"
    )
    fresh_snow_alerts: bool | None = Field(
        None, description="Enable fresh snow notifications"
    )
    event_alerts: bool | None = Field(
        None, description="Enable resort event notifications"
    )
    powder_alerts: bool | None = Field(
        None, description="Enable powder day notifications"
    )
    forecast_alerts: bool | None = Field(
        None, description="Enable forecast/prediction notifications"
    )
    thaw_freeze_alerts: bool | None = Field(
        None, description="Enable thaw/freeze cycle notifications"
    )
    weekly_summary: bool | None = Field(None, description="Enable weekly summary")
    default_snow_threshold_cm: float | None = Field(
        None, description="Default minimum snow in cm to trigger notification"
    )
    powder_snow_threshold_cm: float | None = Field(
        None, description="Fresh snow threshold for powder day alert (cm)"
    )
    forecast_snow_threshold_cm: float | None = Field(
        None, description="Minimum predicted snowfall in cm to trigger forecast alert"
    )
    grace_period_hours: int | None = Field(
        None, description="Minimum hours between notifications for same resort"
    )


class ResortNotificationSettingsRequest(BaseModel):
    """Request body for resort-specific notification settings."""

    fresh_snow_enabled: bool | None = Field(
        None, description="Enable fresh snow notifications for this resort"
    )
    fresh_snow_threshold_cm: float | None = Field(
        None, description="Minimum fresh snow in cm to trigger notification"
    )
    event_notifications_enabled: bool | None = Field(
        None, description="Enable event notifications for this resort"
    )
    powder_alerts_enabled: bool | None = Field(
        None, description="Enable powder alerts for this resort"
    )
    powder_threshold_cm: float | None = Field(
        None, description="Per-resort powder threshold override (cm)"
    )


@app.get("/api/v1/user/notification-settings")
async def get_notification_settings(
    response: Response,
    user_id: str = Depends(get_current_user_id),
):
    """Get the current user's notification settings."""
    try:
        prefs = get_user_service().get_user_preferences(user_id)
        if not prefs:
            # Return default settings
            from models.notification import UserNotificationPreferences

            settings = UserNotificationPreferences()
        else:
            settings = prefs.get_notification_settings()

        response.headers["Cache-Control"] = CACHE_CONTROL_PRIVATE

        return settings.model_dump()

    except Exception as e:
        logger.error(
            "Get notification settings error for %s: %s", user_id, e, exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve notification settings",
        )


@app.put("/api/v1/user/notification-settings")
async def update_notification_settings(
    request: NotificationSettingsRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Update the current user's notification settings."""
    try:
        from models.notification import UserNotificationPreferences

        prefs = get_user_service().get_user_preferences(user_id)
        if not prefs:
            # Create new preferences
            prefs = UserPreferences(
                user_id=user_id,
                created_at=datetime.now(UTC).isoformat(),
                updated_at=datetime.now(UTC).isoformat(),
            )

        # Get or create notification settings
        settings = prefs.get_notification_settings()

        # Update only provided fields
        if request.notifications_enabled is not None:
            settings.notifications_enabled = request.notifications_enabled
        if request.fresh_snow_alerts is not None:
            settings.fresh_snow_alerts = request.fresh_snow_alerts
        if request.event_alerts is not None:
            settings.event_alerts = request.event_alerts
        if request.powder_alerts is not None:
            settings.powder_alerts = request.powder_alerts
        if request.forecast_alerts is not None:
            settings.forecast_alerts = request.forecast_alerts
        if request.thaw_freeze_alerts is not None:
            settings.thaw_freeze_alerts = request.thaw_freeze_alerts
        if request.weekly_summary is not None:
            settings.weekly_summary = request.weekly_summary
        if request.default_snow_threshold_cm is not None:
            settings.default_snow_threshold_cm = request.default_snow_threshold_cm
        if request.powder_snow_threshold_cm is not None:
            settings.powder_snow_threshold_cm = request.powder_snow_threshold_cm
        if request.forecast_snow_threshold_cm is not None:
            settings.forecast_snow_threshold_cm = request.forecast_snow_threshold_cm
        if request.grace_period_hours is not None:
            settings.grace_period_hours = request.grace_period_hours

        # Save updated settings
        prefs.notification_settings = settings
        prefs.updated_at = datetime.now(UTC).isoformat()
        get_user_service().save_user_preferences(prefs)

        return {"message": "Notification settings updated successfully"}

    except Exception as e:
        logger.error(
            "Update notification settings error for %s: %s", user_id, e, exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update notification settings",
        )


@app.put("/api/v1/user/notification-settings/resorts/{resort_id}")
async def update_resort_notification_settings(
    resort_id: str,
    request: ResortNotificationSettingsRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Update notification settings for a specific resort.

    This allows users to customize notification thresholds per resort.
    """
    _validate_resource_id(resort_id, "resort_id")
    try:
        from models.notification import ResortNotificationSettings

        prefs = get_user_service().get_user_preferences(user_id)
        if not prefs:
            prefs = UserPreferences(
                user_id=user_id,
                created_at=datetime.now(UTC).isoformat(),
                updated_at=datetime.now(UTC).isoformat(),
            )

        settings = prefs.get_notification_settings()

        # Get or create resort-specific settings
        resort_settings = settings.resort_settings.get(resort_id)
        if resort_settings is None:
            resort_settings = ResortNotificationSettings(
                resort_id=resort_id,
                fresh_snow_enabled=settings.fresh_snow_alerts,
                fresh_snow_threshold_cm=settings.default_snow_threshold_cm,
                event_notifications_enabled=settings.event_alerts,
            )

        # Update only provided fields
        if request.fresh_snow_enabled is not None:
            resort_settings.fresh_snow_enabled = request.fresh_snow_enabled
        if request.fresh_snow_threshold_cm is not None:
            resort_settings.fresh_snow_threshold_cm = request.fresh_snow_threshold_cm
        if request.event_notifications_enabled is not None:
            resort_settings.event_notifications_enabled = (
                request.event_notifications_enabled
            )
        if request.powder_alerts_enabled is not None:
            resort_settings.powder_alerts_enabled = request.powder_alerts_enabled
        if request.powder_threshold_cm is not None:
            resort_settings.powder_threshold_cm = request.powder_threshold_cm

        # Save updated settings
        settings.resort_settings[resort_id] = resort_settings
        prefs.notification_settings = settings
        prefs.updated_at = datetime.now(UTC).isoformat()
        get_user_service().save_user_preferences(prefs)

        return {"message": "Notification settings updated successfully"}

    except Exception as e:
        logger.error(
            "Update resort notification settings error for %s/%s: %s",
            user_id,
            resort_id,
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update resort notification settings",
        )


@app.delete("/api/v1/user/notification-settings/resorts/{resort_id}")
async def delete_resort_notification_settings(
    resort_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Remove resort-specific notification settings (revert to defaults)."""
    _validate_resource_id(resort_id, "resort_id")
    try:
        prefs = get_user_service().get_user_preferences(user_id)
        if not prefs:
            return {"message": "No settings to delete"}

        settings = prefs.get_notification_settings()

        # Remove resort-specific settings
        if resort_id in settings.resort_settings:
            del settings.resort_settings[resort_id]
            prefs.notification_settings = settings
            prefs.updated_at = datetime.now(UTC).isoformat()
            get_user_service().save_user_preferences(prefs)

        return {"message": "Resort-specific settings removed"}

    except Exception as e:
        logger.error(
            "Delete resort notification settings error for %s/%s: %s",
            user_id,
            resort_id,
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete resort notification settings",
        )


# MARK: - Resort Events Endpoints

_resort_events_table = None


def get_resort_events_table():
    """Get or create resort events table (lazy init for SnapStart)."""
    global _resort_events_table
    if _resort_events_table is None:
        _resort_events_table = get_dynamodb().Table(
            os.environ.get("RESORT_EVENTS_TABLE", "snow-tracker-resort-events-dev")
        )
    return _resort_events_table


class CreateResortEventRequest(BaseModel):
    """Request body for creating a resort event."""

    event_type: str = Field(
        ...,
        description="Type of event (e.g., 'free_store', 'special_offer', 'competition')",
    )
    title: str = Field(..., description="Event title")
    description: str | None = Field(None, description="Event description")
    event_date: str = Field(..., description="Date of the event (YYYY-MM-DD)")
    start_time: str | None = Field(None, description="Start time (HH:MM)")
    end_time: str | None = Field(None, description="End time (HH:MM)")
    location: str | None = Field(None, description="Location within resort")
    url: str | None = Field(None, description="URL for more information")


@app.get("/api/v1/resorts/{resort_id}/events")
async def get_resort_events(
    resort_id: str,
    response: Response,
    days_ahead: int = Query(default=30, ge=1, le=90, description="Days to look ahead"),
):
    """Get upcoming events for a resort."""
    _validate_resource_id(resort_id, "resort_id")
    try:
        from datetime import timedelta

        today = datetime.now(UTC).strftime("%Y-%m-%d")
        future_date = (datetime.now(UTC) + timedelta(days=days_ahead)).strftime(
            "%Y-%m-%d"
        )

        result = get_resort_events_table().query(
            IndexName="EventDateIndex",
            KeyConditionExpression="resort_id = :rid AND event_date BETWEEN :start AND :end",
            ExpressionAttributeValues={
                ":rid": resort_id,
                ":start": today,
                ":end": future_date,
            },
        )

        events = result.get("Items", [])
        response.headers["Cache-Control"] = CACHE_CONTROL_PUBLIC

        return {
            "resort_id": resort_id,
            "events": events,
            "count": len(events),
        }

    except Exception as e:
        logger.error("Get resort events error for %s: %s", resort_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve resort events",
        )


@app.post("/api/v1/resorts/{resort_id}/events", status_code=status.HTTP_201_CREATED)
async def create_resort_event(
    resort_id: str,
    request: CreateResortEventRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Create a new event for a resort.

    Note: In production, this should be restricted to admin users.
    For now, any authenticated user can create events.
    """
    _validate_resource_id(resort_id, "resort_id")
    import uuid

    from models.notification import ResortEvent

    try:
        event = ResortEvent.create(
            resort_id=resort_id,
            event_id=str(uuid.uuid4()),
            event_type=request.event_type,
            title=request.title,
            event_date=request.event_date,
            description=request.description,
            start_time=request.start_time,
            end_time=request.end_time,
            location=request.location,
            url=request.url,
        )

        get_resort_events_table().put_item(Item=event.model_dump())

        return {
            "message": "Event created successfully",
            "event_id": event.event_id,
            "resort_id": resort_id,
        }

    except Exception as e:
        logger.error(
            "Create resort event error for %s: %s", resort_id, e, exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create resort event",
        )


@app.delete(
    "/api/v1/resorts/{resort_id}/events/{event_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_resort_event(
    resort_id: str,
    event_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Delete a resort event.

    Note: In production, this should be restricted to admin users.
    """
    _validate_resource_id(resort_id, "resort_id")
    _validate_resource_id(event_id, "event_id")
    try:
        get_resort_events_table().delete_item(
            Key={"resort_id": resort_id, "event_id": event_id}
        )
        return None

    except Exception as e:
        logger.error(
            "Delete resort event error for %s/%s: %s",
            resort_id,
            event_id,
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete resort event",
        )


# MARK: - Feedback Endpoint


@app.post("/api/v1/feedback")
async def submit_feedback(submission: FeedbackSubmission):
    """Submit user feedback."""
    import uuid

    try:
        feedback = Feedback(
            feedback_id=str(uuid.uuid4()),
            user_id=None,  # Anonymous feedback supported
            subject=submission.subject,
            message=submission.message,
            email=submission.email,
            app_version=submission.app_version,
            build_number=submission.build_number,
            device_model=submission.device_model,
            ios_version=submission.ios_version,
            status="new",
            created_at=datetime.now(UTC).isoformat(),
        )

        # Store in DynamoDB
        get_feedback_table().put_item(Item=feedback.model_dump())

        return {
            "id": feedback.feedback_id,
            "status": "received",
            "message": "Thank you for your feedback!",
        }

    except Exception as e:
        logger.error("Submit feedback error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit feedback",
        )


# MARK: - Authentication Endpoints


class AppleSignInRequest(BaseModel):
    """Request body for Apple Sign In."""

    identity_token: str = Field(..., description="JWT from Apple Sign In")
    authorization_code: str | None = Field(None, description="Authorization code")
    first_name: str | None = Field(None, description="User's first name")
    last_name: str | None = Field(None, description="User's last name")


class GuestAuthRequest(BaseModel):
    """Request body for guest authentication."""

    device_id: str = Field(..., description="Unique device identifier")


class RefreshTokenRequest(BaseModel):
    """Request body for token refresh."""

    refresh_token: str = Field(..., description="Refresh token")


@app.post("/api/v1/auth/apple")
async def sign_in_with_apple(request: AppleSignInRequest):
    """Authenticate with Apple Sign In.

    Verifies the Apple identity token, creates or updates the user,
    and returns session tokens.
    """
    try:
        auth_service = get_auth_service()

        # Verify Apple token and get/create user
        user = auth_service.verify_apple_token(
            identity_token=request.identity_token,
            authorization_code=request.authorization_code,
            first_name=request.first_name,
            last_name=request.last_name,
        )

        # Create session tokens
        tokens = auth_service.create_session_tokens(user.user_id)

        # Return user info with tokens at top level (iOS expects flat structure)
        return {
            "user": user.to_dict(),
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "token_type": tokens["token_type"],
            "expires_in": tokens["expires_in"],
            "is_new_user": user.is_new_user,
        }

    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )
    except Exception as e:
        logger.error("Apple Sign In error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Authentication failed",
        )


@app.post("/api/v1/auth/guest")
async def sign_in_as_guest(request: GuestAuthRequest):
    """Create a guest session.

    Guest users have limited functionality but can still use the app.
    """
    try:
        auth_service = get_auth_service()

        # Create guest user/session
        user = auth_service.create_guest_session(request.device_id)

        # Create session tokens
        tokens = auth_service.create_session_tokens(user.user_id)

        # Return user info with tokens at top level (iOS expects flat structure)
        return {
            "user": user.to_dict(),
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "token_type": tokens["token_type"],
            "expires_in": tokens["expires_in"],
            "is_new_user": user.is_new_user,
        }

    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            "Guest auth error for device %s: %s", request.device_id, e, exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Guest authentication failed",
        )


@app.post("/api/v1/auth/refresh")
async def refresh_token(request: RefreshTokenRequest):
    """Refresh access token using refresh token."""
    try:
        auth_service = get_auth_service()
        tokens = auth_service.refresh_tokens(request.refresh_token)
        return tokens

    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )


@app.get("/api/v1/auth/me")
async def get_current_user(user_id: str = Depends(get_current_user_id)):
    """Get current authenticated user info."""
    try:
        auth_service = get_auth_service()
        user = auth_service._get_user(user_id)

        # Get auth_provider from raw DynamoDB item
        provider = None
        try:
            raw_response = auth_service.user_table.get_item(Key={"user_id": user_id})
            raw_item = raw_response.get("Item", {})
            provider = raw_item.get("auth_provider")
        except Exception as e:
            logger.warning("Failed to get auth provider for user %s: %s", user_id, e)

        # Get user preferences
        user_service = get_user_service()
        prefs = user_service.get_user_preferences(user_id)

        return {
            "user_id": user_id,
            "email": user.email if user else None,
            "first_name": user.first_name if user else None,
            "last_name": user.last_name if user else None,
            "provider": provider,
            "is_new_user": False,
            "preferences": prefs.model_dump() if prefs else None,
        }

    except Exception as e:
        logger.error("Get current user error for %s: %s", user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user info",
        )


# MARK: - Recommendations Endpoints


@app.get("/api/v1/recommendations")
async def get_recommendations(
    response: Response,
    lat: float = Query(..., ge=-90, le=90, description="User's latitude"),
    lng: float | None = Query(None, ge=-180, le=180, description="User's longitude"),
    lon: float | None = Query(
        None, ge=-180, le=180, description="User's longitude (alias for lng)"
    ),
    radius: float = Query(500, ge=10, le=2000, description="Search radius in km"),
    limit: int = Query(10, ge=1, le=50, description="Number of recommendations"),
    min_quality: str | None = Query(None, description="Minimum snow quality filter"),
):
    """Get resort recommendations based on location and snow conditions.

    This endpoint combines proximity and snow quality to recommend
    the best resorts for the user to visit.

    The ranking algorithm considers:
    - Distance from user (closer is better, with diminishing returns)
    - Current snow quality (excellent > good > fair > poor)
    - Fresh/predicted snowfall (more snow = higher score)

    Accepts either `lng` or `lon` for longitude (both are supported).
    """
    # Accept both lng and lon as aliases for longitude
    longitude = lng if lng is not None else lon
    if longitude is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Either 'lng' or 'lon' query parameter is required",
        )

    try:
        # Parse min_quality if provided
        quality_filter = None
        if min_quality:
            try:
                quality_filter = SnowQuality(min_quality.lower())
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid quality filter. Must be one of: {[q.value for q in SnowQuality]}",
                )

        # Get recommendations
        recommendations = get_recommendation_service().get_recommendations(
            latitude=lat,
            longitude=longitude,
            radius_km=radius,
            limit=limit,
            min_quality=quality_filter,
        )

        response.headers["Cache-Control"] = CACHE_CONTROL_PUBLIC

        return {
            "recommendations": [r.to_dict() for r in recommendations],
            "count": len(recommendations),
            "search_center": {"latitude": lat, "longitude": longitude},
            "search_radius_km": radius,
            "generated_at": datetime.now(UTC).isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Recommendations error (lat=%s, lng=%s): %s",
            lat,
            longitude,
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate recommendations",
        )


def _build_best_conditions_from_static(
    limit: int, quality_filter: SnowQuality | None
) -> dict | None:
    """Build best conditions response from S3 static JSON files.

    Uses pre-computed snow-quality.json and resorts.json from S3 to avoid
    slow DynamoDB queries that can exceed API Gateway's 29s timeout.

    Returns None if static data is unavailable (caller should fall back).
    """
    static_quality = _get_static_snow_quality_from_s3()
    if static_quality is None:
        return None

    static_resorts = _get_static_resorts_from_s3()
    if static_resorts is None:
        return None

    # Build resort lookup by ID
    resort_by_id = {r["resort_id"]: r for r in static_resorts}

    # Quality rank for filtering
    quality_ranks = {
        "champagne_powder": 10,
        "powder_day": 9,
        "excellent": 8,
        "great": 7,
        "good": 6,
        "decent": 5,
        "mediocre": 4,
        "poor": 3,
        "bad": 2,
        "horrible": 1,
        "unknown": 0,
    }
    min_rank = quality_ranks.get(quality_filter.value, 0) if quality_filter else 0

    # Quality score mapping (same as RecommendationService.QUALITY_SCORES)
    quality_score_map = {
        "champagne_powder": 1.0,
        "powder_day": 0.95,
        "excellent": 0.9,
        "great": 0.8,
        "good": 0.7,
        "decent": 0.6,
        "mediocre": 0.5,
        "poor": 0.4,
        "bad": 0.2,
        "horrible": 0.0,
        "unknown": 0.3,
    }

    # Sort by snow_score descending, then fresh snow
    scored_items = []
    for resort_id, quality_data in static_quality.items():
        overall_quality = quality_data.get("overall_quality", "unknown")
        snow_score = quality_data.get("snow_score")

        # Apply quality filter
        rank = quality_ranks.get(overall_quality, 0)
        if rank < min_rank:
            continue

        resort = resort_by_id.get(resort_id)
        if not resort:
            continue

        fresh_snow = quality_data.get("snowfall_fresh_cm", 0) or 0
        scored_items.append(
            (snow_score or 0, fresh_snow, resort_id, quality_data, resort)
        )

    # Sort by snow_score desc, then fresh snow desc
    scored_items.sort(key=lambda x: (x[0], x[1]), reverse=True)

    # Build recommendation objects
    import math

    recommendations = []
    for _, _, _resort_id, quality_data, resort in scored_items[:limit]:
        overall_quality = quality_data.get("overall_quality", "unknown")
        snow_score = quality_data.get("snow_score")
        fresh_snow_cm = quality_data.get("snowfall_fresh_cm", 0) or 0
        temp_c = quality_data.get("temperature_c", 0) or 0
        predicted_48h = quality_data.get("predicted_snow_48h_cm", 0) or 0
        explanation = quality_data.get("explanation", "")

        q_score = quality_score_map.get(overall_quality, 0.3)

        # Fresh snow score (log scale, same as RecommendationService)
        combined_cm = fresh_snow_cm + (predicted_48h * 0.5)
        if combined_cm <= 0:
            fresh_snow_score = 0.0
        else:
            max_reference = 150.0
            fresh_snow_score = min(
                1.0,
                math.log(1 + combined_cm / 5) / math.log(1 + max_reference / 5),
            )

        combined_score = round(0.7 * q_score + 0.3 * fresh_snow_score, 3)

        # Build reason text
        if overall_quality in ("champagne_powder", "powder_day"):
            reason_parts = ["Epic powder conditions"]
        elif overall_quality == "excellent":
            reason_parts = ["Top-rated powder conditions"]
        elif overall_quality in ("great", "good"):
            reason_parts = ["Good snow conditions"]
        elif overall_quality == "decent":
            reason_parts = ["Decent conditions"]
        else:
            reason_parts = [f"{overall_quality.replace('_', ' ').title()} conditions"]

        if fresh_snow_cm >= 15:
            reason_parts.append(f"{fresh_snow_cm:.0f}cm of fresh snow")
        elif fresh_snow_cm >= 5:
            reason_parts.append(f"{fresh_snow_cm:.0f}cm fresh snow")

        if predicted_48h >= 15:
            reason_parts.append(f"More snow expected ({predicted_48h:.0f}cm)")

        country = resort.get("country", "")
        name = resort.get("name", "")
        location = f"at {name}, {country}"
        reason = ". ".join(reason_parts) + f" {location}."

        rec = {
            "resort": resort,
            "distance_km": 0,
            "distance_miles": 0,
            "snow_quality": overall_quality,
            "snow_score": snow_score,
            "quality_score": round(q_score, 3),
            "distance_score": 1.0,
            "combined_score": combined_score,
            "fresh_snow_cm": round(fresh_snow_cm, 1),
            "predicted_snow_72h_cm": round(predicted_48h, 1),
            "current_temp_celsius": round(temp_c, 1),
            "confidence_level": "medium",
            "reason": reason,
            "elevation_conditions": {},
        }
        recommendations.append(rec)

    return {
        "recommendations": recommendations,
        "count": len(recommendations),
        "generated_at": datetime.now(UTC).isoformat(),
    }


@app.get("/api/v1/recommendations/best")
async def get_best_conditions(
    response: Response,
    limit: int = Query(10, ge=1, le=50, description="Number of results"),
    min_quality: str | None = Query(None, description="Minimum snow quality filter"),
):
    """Get resorts with the best snow conditions globally.

    This endpoint returns the top resorts by snow quality,
    regardless of user location. Useful for planning trips
    to wherever the snow is best.

    Uses pre-computed static JSON from S3 for fast response (avoids
    DynamoDB cold-start timeouts that caused 504 errors via API Gateway).
    Falls back to live DynamoDB queries if static data is unavailable.

    Results are cached in-memory for 1 hour.
    """
    try:
        quality_filter = None
        if min_quality:
            try:
                quality_filter = SnowQuality(min_quality.lower())
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid quality filter.",
                )

        # Check in-memory cache first (1-hour TTL)
        cache_key = f"best_conditions_{limit}_{min_quality or 'none'}"
        cache = get_recommendations_cache()
        if cache_key in cache:
            cached_result = cache[cache_key]
            response.headers["Cache-Control"] = CACHE_CONTROL_PUBLIC_LONG
            response.headers["X-Cache"] = "HIT"
            return cached_result

        # Try fast path: build from S3 static JSON (< 1s vs 20s+ for DynamoDB)
        result = _build_best_conditions_from_static(
            limit=limit, quality_filter=quality_filter
        )

        if result is None:
            # Fall back to live DynamoDB queries (slow, may timeout on cold start)
            logger.info(
                "Static JSON unavailable for best conditions, falling back to DynamoDB"
            )
            recommendations = get_recommendation_service().get_best_conditions_globally(
                limit=limit,
                min_quality=quality_filter,
            )
            result = {
                "recommendations": [r.to_dict() for r in recommendations],
                "count": len(recommendations),
                "generated_at": datetime.now(UTC).isoformat(),
            }

        # Cache the result
        cache[cache_key] = result

        response.headers["Cache-Control"] = CACHE_CONTROL_PUBLIC_LONG
        response.headers["X-Cache"] = "MISS"

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Best conditions error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get best conditions",
        )


# MARK: - Trip Planning Endpoints


@app.post("/api/v1/trips", status_code=status.HTTP_201_CREATED)
async def create_trip(
    trip_data: TripCreate,
    user_id: str = Depends(get_current_user_id),
):
    """Create a new ski trip.

    Creates a planned trip for the authenticated user with
    the specified resort and dates. Automatically captures
    current conditions at the resort.
    """
    try:
        trip = get_trip_service().create_trip(user_id, trip_data)
        return trip.model_dump()

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error("Create trip error for %s: %s", user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create trip",
        )


@app.get("/api/v1/trips")
async def get_user_trips(
    response: Response,
    user_id: str = Depends(get_current_user_id),
    status_filter: str | None = Query(
        None, alias="status", description="Filter by status"
    ),
    include_past: bool = Query(True, description="Include past trips"),
):
    """Get all trips for the authenticated user.

    Returns trips sorted by start date (upcoming first).
    """
    try:
        # Parse status filter
        trip_status = None
        if status_filter:
            try:
                trip_status = TripStatus(status_filter.lower())
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status. Must be one of: {[s.value for s in TripStatus]}",
                )

        trips = get_trip_service().get_user_trips(
            user_id=user_id,
            status=trip_status,
            include_past=include_past,
        )

        response.headers["Cache-Control"] = CACHE_CONTROL_PRIVATE

        return {
            "trips": [t.model_dump() for t in trips],
            "count": len(trips),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Get trips error for %s: %s", user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get trips",
        )


@app.get("/api/v1/trips/{trip_id}")
async def get_trip(
    trip_id: str,
    response: Response,
    user_id: str = Depends(get_current_user_id),
):
    """Get a specific trip by ID."""
    _validate_resource_id(trip_id, "trip_id")
    try:
        trip = get_trip_service().get_trip(trip_id, user_id)
        if not trip:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Trip not found",
            )

        response.headers["Cache-Control"] = CACHE_CONTROL_PRIVATE

        return trip.model_dump()

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Get trip error for %s/%s: %s", user_id, trip_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get trip",
        )


@app.put("/api/v1/trips/{trip_id}")
async def update_trip(
    trip_id: str,
    update_data: TripUpdate,
    user_id: str = Depends(get_current_user_id),
):
    """Update a trip."""
    _validate_resource_id(trip_id, "trip_id")
    try:
        trip = get_trip_service().update_trip(trip_id, user_id, update_data)
        return trip.model_dump()

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            "Update trip error for %s/%s: %s", user_id, trip_id, e, exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update trip",
        )


@app.delete("/api/v1/trips/{trip_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_trip(
    trip_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Delete a trip."""
    _validate_resource_id(trip_id, "trip_id")
    try:
        deleted = get_trip_service().delete_trip(trip_id, user_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Trip not found",
            )
        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Delete trip error for %s/%s: %s", user_id, trip_id, e, exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete trip",
        )


@app.post("/api/v1/trips/{trip_id}/refresh-conditions")
async def refresh_trip_conditions(
    trip_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Refresh the conditions for a trip.

    Updates the latest conditions snapshot and checks for
    significant changes that warrant alerts.
    """
    _validate_resource_id(trip_id, "trip_id")
    try:
        trip = get_trip_service().update_trip_conditions(trip_id, user_id)
        return {
            "trip_id": trip.trip_id,
            "latest_conditions": trip.latest_conditions.model_dump()
            if trip.latest_conditions
            else None,
            "unread_alerts": trip.unread_alert_count,
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            "Refresh trip conditions error for %s/%s: %s",
            user_id,
            trip_id,
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to refresh conditions",
        )


@app.post("/api/v1/trips/{trip_id}/alerts/read")
async def mark_trip_alerts_read(
    trip_id: str,
    user_id: str = Depends(get_current_user_id),
    alert_ids: list[str] | None = None,
):
    """Mark trip alerts as read.

    If alert_ids is not provided, marks all alerts as read.
    """
    _validate_resource_id(trip_id, "trip_id")
    try:
        count = get_trip_service().mark_alerts_read(trip_id, user_id, alert_ids)
        return {"marked_read": count}

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            "Mark trip alerts read error for %s/%s: %s",
            user_id,
            trip_id,
            e,
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark alerts read",
        )


# =============================================================================
# MARK: - Condition Report Endpoints
# =============================================================================


@app.post(
    "/api/v1/resorts/{resort_id}/condition-reports",
    status_code=status.HTTP_201_CREATED,
)
async def submit_condition_report(
    resort_id: str,
    report_request: ConditionReportRequest,
    user_id: str = Depends(get_current_user_id),
):
    """Submit a user condition report for a resort.

    Authenticated users can submit reports about current snow conditions.
    Rate limited to 5 reports per user per resort per day.
    """
    _validate_resource_id(resort_id, "resort_id")
    try:
        # Verify resort exists
        resort = _get_resort_cached(resort_id)
        if not resort:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Resort not found",
            )

        report = get_condition_report_service().submit_report(
            resort_id=resort_id,
            user_id=user_id,
            request=report_request,
        )

        return ConditionReportResponse(
            report_id=report.report_id,
            resort_id=report.resort_id,
            user_id=report.user_id,
            condition_type=report.condition_type,
            score=report.score,
            comment=report.comment,
            elevation_level=report.elevation_level,
            created_at=report.created_at,
        ).model_dump()

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to submit condition report: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit condition report",
        )


@app.get("/api/v1/resorts/{resort_id}/condition-reports")
async def get_resort_condition_reports(
    resort_id: str,
    response: Response,
    limit: int = Query(20, ge=1, le=100, description="Maximum reports to return"),
):
    """Get condition reports for a resort.

    Returns recent user-submitted condition reports along with a summary
    of reports from the last 7 days. This endpoint is public.
    """
    _validate_resource_id(resort_id, "resort_id")
    try:
        service = get_condition_report_service()

        reports = service.get_reports_for_resort(resort_id, limit=limit)
        summary = service.get_report_summary(resort_id)

        response.headers["Cache-Control"] = CACHE_CONTROL_PUBLIC

        return {
            "reports": [
                ConditionReportResponse(
                    report_id=r.report_id,
                    resort_id=r.resort_id,
                    user_id=r.user_id,
                    condition_type=r.condition_type,
                    score=r.score,
                    comment=r.comment,
                    elevation_level=r.elevation_level,
                    created_at=r.created_at,
                ).model_dump()
                for r in reports
            ],
            "summary": summary,
        }

    except Exception as e:
        logger.error(
            "Failed to get condition reports for %s: %s", resort_id, e, exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get condition reports",
        )


@app.get("/api/v1/user/condition-reports")
async def get_user_condition_reports(
    response: Response,
    user_id: str = Depends(get_current_user_id),
    limit: int = Query(50, ge=1, le=200, description="Maximum reports to return"),
):
    """Get condition reports submitted by the authenticated user."""
    try:
        reports = get_condition_report_service().get_reports_by_user(
            user_id, limit=limit
        )

        response.headers["Cache-Control"] = CACHE_CONTROL_PRIVATE

        return {
            "reports": [
                ConditionReportResponse(
                    report_id=r.report_id,
                    resort_id=r.resort_id,
                    user_id=r.user_id,
                    condition_type=r.condition_type,
                    score=r.score,
                    comment=r.comment,
                    elevation_level=r.elevation_level,
                    created_at=r.created_at,
                ).model_dump()
                for r in reports
            ],
            "count": len(reports),
        }

    except Exception as e:
        logger.error("Failed to get user condition reports: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user condition reports",
        )


@app.delete(
    "/api/v1/resorts/{resort_id}/condition-reports/{report_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_condition_report(
    resort_id: str,
    report_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Delete a condition report.

    Only the user who submitted the report can delete it.
    """
    _validate_resource_id(resort_id, "resort_id")
    _validate_resource_id(report_id, "report_id")
    try:
        deleted = get_condition_report_service().delete_report(
            resort_id=resort_id,
            report_id=report_id,
            user_id=user_id,
        )

        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Condition report not found or you are not the author",
            )

        return None

    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to delete condition report: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete condition report",
        )


# =============================================================================
# MARK: - Test/Debug Endpoints (for development and admin users)
# =============================================================================

# SHA256 hashes of admin email addresses (same as iOS Configuration.swift)
ADMIN_EMAIL_HASHES = {
    "6e5c948b6cd14e94776b2abf9d324aa3a6606a3411bf7aefc36d0e74fd15faa0"
}


def _is_admin_user(user_id: str | None) -> bool:
    """Check if the user is an admin based on their email hash."""
    if not user_id:
        return False
    try:
        import hashlib

        user_service = get_user_service()
        user = user_service.get_user(user_id)
        if user and user.email:
            email_hash = hashlib.sha256(user.email.lower().encode("utf-8")).hexdigest()
            return email_hash in ADMIN_EMAIL_HASHES
    except Exception as e:
        logger.warning("Failed to check admin status for user %s: %s", user_id, e)
    return False


def _check_debug_access(environment: str, user_id: str | None):
    """Check if debug endpoints are accessible. Allows staging/dev or admin users in prod."""
    if environment != "prod":
        return  # Always allowed in non-prod
    if _is_admin_user(user_id):
        return  # Admin users can access debug endpoints in prod
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="This endpoint is not available in production",
    )


@app.post("/api/v1/debug/trigger-notifications")
async def trigger_notifications(
    user_id: str | None = Depends(get_optional_user_id),
):
    """
    Manually trigger the notification processor for testing.
    This invokes the notification Lambda asynchronously.
    Available in staging/dev, or for admin users in production.
    """
    import boto3

    environment = os.environ.get("ENVIRONMENT", "dev")

    _check_debug_access(environment, user_id)

    try:
        lambda_client = boto3.client(
            "lambda", region_name=os.environ.get("AWS_REGION_NAME", "us-west-2")
        )

        # Get the notification processor Lambda name
        notification_lambda_name = f"snow-tracker-notification-processor-{environment}"

        # Invoke asynchronously with a test payload
        response = lambda_client.invoke(
            FunctionName=notification_lambda_name,
            InvocationType="Event",  # Async invocation
            Payload=json.dumps(
                {
                    "source": "manual_trigger",
                    "user_id": user_id or "anonymous",
                    "test_mode": True,
                }
            ),
        )

        return {
            "message": "Notification processor triggered",
            "status_code": response.get("StatusCode"),
            "environment": environment,
            "lambda_name": notification_lambda_name,
        }

    except Exception as e:
        logger.error("Trigger notifications error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to trigger notification processor",
        )


@app.post("/api/v1/debug/test-push-notification")
async def test_push_notification(
    user_id: str = Depends(get_current_user_id),
    title: str = "Test Notification",
    body: str = "This is a test push notification from Powder Chaser",
):
    """
    Send a test push notification to the authenticated user's devices.
    Any authenticated user can test notifications on their own devices.
    """
    import boto3

    environment = os.environ.get("ENVIRONMENT", "dev")

    try:
        # Get device tokens
        device_tokens_table = get_dynamodb().Table(
            os.environ.get(
                "DEVICE_TOKENS_TABLE", f"snow-tracker-device-tokens-{environment}"
            )
        )

        # Query for authenticated user's tokens
        result = device_tokens_table.query(
            KeyConditionExpression="user_id = :uid",
            ExpressionAttributeValues={":uid": user_id},
        )
        tokens = result.get("Items", [])

        if not tokens:
            return {
                "message": "No device tokens found for your account. Make sure you've enabled notifications in the app.",
                "user_id": user_id,
                "tokens_found": 0,
            }

        # Send notification via SNS
        sns_client = boto3.client(
            "sns", region_name=os.environ.get("AWS_REGION_NAME", "us-west-2")
        )

        apns_arn = os.environ.get("APNS_PLATFORM_APP_ARN", "")
        if not apns_arn or apns_arn == "not-configured":
            return {
                "message": "APNs not configured - push notifications unavailable",
                "user_id": user_id,
                "tokens_found": len(tokens),
            }

        results = []
        for token_record in tokens:
            device_token = token_record.get("token")
            if not device_token:
                continue

            try:
                # Create endpoint for this device
                endpoint_response = sns_client.create_platform_endpoint(
                    PlatformApplicationArn=apns_arn,
                    Token=device_token,
                )
                endpoint_arn = endpoint_response["EndpointArn"]

                # Send the notification
                apns_payload = {
                    "aps": {
                        "alert": {
                            "title": title,
                            "body": body,
                        },
                        "sound": "default",
                        "badge": 1,
                    },
                    "test": True,
                }

                # Use APNS for prod, APNS_SANDBOX for staging/dev
                apns_key = "APNS" if environment == "prod" else "APNS_SANDBOX"
                sns_client.publish(
                    TargetArn=endpoint_arn,
                    Message=json.dumps({apns_key: json.dumps(apns_payload)}),
                    MessageStructure="json",
                )

                results.append(
                    {
                        "device_id": token_record.get("device_id"),
                        "status": "sent",
                    }
                )

            except Exception as e:
                results.append(
                    {
                        "device_id": token_record.get("device_id"),
                        "status": "failed",
                        "error": str(e),
                    }
                )

        return {
            "message": "Test notification sent",
            "user_id": user_id or "anonymous",
            "tokens_found": len(tokens),
            "results": results,
        }

    except Exception as e:
        logger.error("Test push notification error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send test notification",
        )


# MARK: - Admin Endpoints


@app.post("/api/v1/admin/backfill-geohashes")
async def backfill_geohashes(
    user_id: str | None = Depends(get_optional_user_id),
):
    """
    Backfill geohashes for resorts that don't have them.
    Only available in staging/dev environments, or for admin users in prod.
    """
    environment = os.environ.get("ENVIRONMENT", "dev")

    _check_debug_access(environment, user_id)

    try:
        resort_service = get_resort_service()
        result = resort_service.backfill_geohashes()
        return {
            "message": "Geohash backfill completed",
            "total_resorts": result.get("total_resorts", 0),
            "updated": result.get("updated", 0),
            "already_has_geohash": result.get("already_has_geohash", 0),
            "skipped_no_coords": result.get("skipped_no_coords", 0),
            "errors": result.get("errors", 0),
        }
    except Exception as e:
        logger.error("Backfill geohashes error: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to backfill geohashes",
        )


# MARK: - Chat Endpoints


@app.post("/api/v1/chat")
async def send_chat_message(
    request: ChatRequest,
    fastapi_request: Request,
    user_id: str | None = Depends(get_optional_user_id),
):
    """Send a message to the AI ski conditions assistant.

    Authenticated users have unlimited chat. Anonymous users are limited
    to 5 messages per IP address per 6 hours.
    """
    try:
        remaining_messages = None

        # For anonymous users, enforce IP-based rate limit
        if not user_id:
            client_ip = _get_client_ip(fastapi_request)
            if not _check_anonymous_chat_limit(client_ip):
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Chat limit reached. Sign in for unlimited access, or try again later.",
                )
            # Use IP-based identifier for anonymous conversations
            user_id = f"anon_{client_ip}"
            remaining_messages = _get_remaining_anonymous_messages(client_ip)

        service = get_chat_service()
        result = service.chat(
            request.message,
            request.conversation_id,
            user_id,
            user_lat=request.latitude,
            user_lon=request.longitude,
        )

        # Add remaining messages info for anonymous users
        response_data = result.model_dump() if hasattr(result, "model_dump") else result
        if remaining_messages is not None:
            response_data["remaining_messages"] = remaining_messages

        return response_data
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Chat error for user %s: %s", user_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process chat message",
        )


# Hardcoded fallback suggestions when DynamoDB table is empty or unavailable
_DEFAULT_CHAT_SUGGESTIONS = [
    {
        "id": "s1",
        "text": "What are the snow conditions like today?",
        "category": "general",
    },
    {
        "id": "s2",
        "text": "Which resort has the most fresh snow?",
        "category": "general",
    },
    {"id": "s3", "text": "Compare Whistler and Vail conditions", "category": "general"},
    {
        "id": "s4",
        "text": "What's the snow quality forecast for this week?",
        "category": "general",
    },
    {
        "id": "s5",
        "text": "How's the powder at {resort_name} today?",
        "category": "favorites_aware",
    },
    {
        "id": "s6",
        "text": "Best snow near {nearby_city} this weekend?",
        "category": "location_aware",
    },
    {
        "id": "s7",
        "text": "What's the forecast for {resort_name}?",
        "category": "favorites_aware",
    },
    {
        "id": "s8",
        "text": "Should I go to {resort_name} or {resort_name_2} tomorrow?",
        "category": "favorites_aware",
    },
    {
        "id": "s9",
        "text": "Any fresh snow expected at {resort_name}?",
        "category": "favorites_aware",
    },
    {
        "id": "s10",
        "text": "How deep is the base at {resort_name}?",
        "category": "favorites_aware",
    },
    {
        "id": "s11",
        "text": "What are conditions like in {region}?",
        "category": "location_aware",
    },
    {
        "id": "s12",
        "text": "Best resort for beginners near {nearby_city}?",
        "category": "location_aware",
    },
    {
        "id": "s13",
        "text": "Is {resort_name} worth the trip today?",
        "category": "favorites_aware",
    },
    {
        "id": "s14",
        "text": "Will it snow at {resort_name} this week?",
        "category": "favorites_aware",
    },
    {
        "id": "s15",
        "text": "Hidden gems near {nearby_city} with good powder?",
        "category": "location_aware",
    },
    {
        "id": "s16",
        "text": "How's the weather looking in {region} this weekend?",
        "category": "location_aware",
    },
]


@app.get("/api/v1/chat/suggestions")
async def get_chat_suggestions():
    """Return active chat suggestions for the AI chat empty state.

    Reads from the chat-suggestions DynamoDB table. Falls back to hardcoded
    defaults if the table is empty or unavailable.
    """
    try:
        environment = os.environ.get("ENVIRONMENT", "dev")
        table_name = os.environ.get(
            "CHAT_SUGGESTIONS_TABLE",
            f"snow-tracker-chat-suggestions-{environment}",
        )
        table = get_dynamodb().Table(table_name)
        response = table.scan(
            FilterExpression="active = :active",
            ExpressionAttributeValues={":active": True},
        )
        items = response.get("Items", [])

        if not items:
            logger.info("No active suggestions in DynamoDB, returning defaults")
            return {"suggestions": _DEFAULT_CHAT_SUGGESTIONS}

        # Sort by priority (lower number = higher priority)
        items.sort(key=lambda x: int(x.get("priority", 999)))

        suggestions = [
            {
                "id": item["suggestion_id"],
                "text": item["text"],
                "category": item.get("category", "general"),
            }
            for item in items
        ]
        return {"suggestions": suggestions}

    except Exception as e:
        logger.warning("Failed to fetch chat suggestions from DynamoDB: %s", e)
        return {"suggestions": _DEFAULT_CHAT_SUGGESTIONS}


@app.get("/api/v1/chat/conversations")
async def list_conversations(
    user_id: str = Depends(get_current_user_id),
):
    """List all chat conversations for the authenticated user."""
    try:
        service = get_chat_service()
        conversations = service.list_conversations(user_id)
        return {
            "conversations": [c.model_dump() for c in conversations],
            "count": len(conversations),
        }
    except Exception as e:
        logger.error(
            "List conversations error for user %s: %s", user_id, e, exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list conversations",
        )


@app.get("/api/v1/chat/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Get all messages in a chat conversation."""
    _validate_resource_id(conversation_id, "conversation_id")
    try:
        service = get_chat_service()
        messages = service.get_conversation(conversation_id, user_id)
        return {
            "conversation_id": conversation_id,
            "messages": [m.model_dump() for m in messages],
            "count": len(messages),
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error("Get conversation error %s: %s", conversation_id, e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get conversation",
        )


@app.delete("/api/v1/chat/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """Delete a chat conversation and all its messages."""
    _validate_resource_id(conversation_id, "conversation_id")
    try:
        service = get_chat_service()
        service.delete_conversation(conversation_id, user_id)
        return {"status": "deleted"}
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            "Delete conversation error %s: %s", conversation_id, e, exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete conversation",
        )


# MARK: - Error Handlers


@app.exception_handler(ClientError)
async def aws_client_error_handler(request, exc: ClientError):
    """Handle AWS client errors.

    Logs the full AWS error for debugging but returns a generic message
    to the client to avoid leaking internal infrastructure details.
    """
    error_code = exc.response["Error"]["Code"]
    error_message = exc.response["Error"]["Message"]
    logger.error("AWS ClientError %s: %s", error_code, error_message)

    if error_code == "ResourceNotFoundException":
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": "Resource not found"},
        )
    else:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error"},
        )


@app.exception_handler(ValueError)
async def value_error_handler(request, exc: ValueError):
    """Handle value errors.

    Returns a generic message to avoid leaking internal error details.
    The full error is logged for debugging.
    """
    logger.warning("ValueError in request %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": "Invalid request data"},
    )


# MARK: - Lambda Handler

# Create the Lambda handler
api_handler = Mangum(app, lifespan="off")


# For local development
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
