"""Main FastAPI application handler for Lambda deployment."""

import json
import logging
import os
import time
from datetime import UTC, datetime, timezone
from typing import Annotated, Dict, List, Optional

import boto3
from botocore.exceptions import ClientError
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from mangum import Mangum
from pydantic import BaseModel, Field

from models.feedback import Feedback, FeedbackSubmission
from models.resort import Resort
from models.trip import Trip, TripCreate, TripStatus, TripUpdate
from models.user import UserPreferences
from models.weather import SNOW_QUALITY_EXPLANATIONS, SnowQuality, TimelineResponse
from services.auth_service import AuthenticationError, AuthProvider, AuthService
from services.ml_scorer import raw_score_to_quality
from services.openmeteo_service import OpenMeteoService
from services.quality_explanation_service import (
    generate_overall_explanation,
    generate_quality_explanation,
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
    global _trip_service, _trips_table, _s3_client
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


# MARK: - Health Check


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.now(UTC).isoformat(),
        "version": "1.0.0",
    }


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


@app.get("/api/v1/resorts")
async def get_resorts(
    response: Response,
    country: str | None = Query(
        None, description="Filter by country code (CA, US, FR, etc.)"
    ),
    region: str | None = Query(
        None, description="Filter by region (na_west, alps, japan, etc.)"
    ),
    include_no_coords: bool = Query(
        False,
        description="Include resorts without valid coordinates (default: exclude)",
    ),
):
    """Get all ski resorts, optionally filtered by country or region.

    By default, resorts with invalid (0,0) coordinates are excluded.
    Use include_no_coords=true to include them.
    """
    try:
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

        # Set cache headers - resort data is public and can be cached
        response.headers["Cache-Control"] = CACHE_CONTROL_PUBLIC

        return {"resorts": resorts}

    except HTTPException:
        raise
    except Exception as e:
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
    lon: float = Query(..., ge=-180, le=180, description="User's longitude"),
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
    """
    try:
        nearby = get_resort_service().get_nearby_resorts(
            latitude=lat,
            longitude=lon,
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
            "search_center": {"latitude": lat, "longitude": lon},
            "search_radius_km": radius,
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to find nearby resorts",
        )


@app.get("/api/v1/resorts/{resort_id}", response_model=Resort)
async def get_resort(resort_id: str, response: Response):
    """Get details for a specific resort."""
    try:
        resort = _get_resort_cached(resort_id)
        if not resort:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Resort {resort_id} not found",
            )

        # Set cache headers
        response.headers["Cache-Control"] = CACHE_CONTROL_PUBLIC

        return resort

    except HTTPException:
        raise
    except Exception as e:
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
                resort_id, result = future.result(timeout=5)
                results[resort_id] = result

        # Set cache headers
        response.headers["Cache-Control"] = CACHE_CONTROL_PUBLIC

        return {
            "results": results,
            "last_updated": datetime.now(UTC).isoformat(),
            "resort_count": len(ids),
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
    try:
        # Verify resort exists
        resort = _get_resort_cached(resort_id)
        if not resort:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Resort {resort_id} not found",
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
                detail=f"Resort {resort_id} not found",
            )

        # Get latest condition for the specific elevation (cached)
        condition = _get_latest_condition_cached(resort_id, elevation_level)
        if not condition:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No conditions found for {resort_id} at {elevation_level} elevation",
            )

        # Set cache headers
        response.headers["Cache-Control"] = CACHE_CONTROL_PUBLIC

        return condition

    except HTTPException:
        raise
    except Exception as e:
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
    try:
        # Verify resort exists
        resort = _get_resort_cached(resort_id)
        if not resort:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Resort {resort_id} not found",
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

        # Calculate overall quality from weighted raw scores (top 50%, mid 35%, base 15%).
        # This ensures overall_quality and overall_snow_score are always consistent.
        elevation_weights = {"top": 0.50, "mid": 0.35, "base": 0.15}
        weighted_raw_score = 0.0
        total_weight = 0.0
        for cond in conditions:
            raw = cond.quality_score
            if raw is not None:
                w = elevation_weights.get(cond.elevation_level, 0.15)
                weighted_raw_score += raw * w
                total_weight += w
        if total_weight > 0:
            overall_raw_score = weighted_raw_score / total_weight
        else:
            overall_raw_score = None

        # Derive quality label from weighted raw score using model thresholds
        from services.snow_quality_service import SnowQualityService

        if overall_raw_score is not None:
            overall_snow_score = score_to_100(overall_raw_score)
            overall_quality = raw_score_to_quality(overall_raw_score)
        else:
            overall_quality = SnowQualityService.calculate_overall_quality(conditions)
            overall_snow_score = None

        # Get explanation for overall quality
        quality_explanation = SNOW_QUALITY_EXPLANATIONS.get(overall_quality, {})

        # Generate overall explanation matching the weighted quality level.
        # When no elevation matches overall quality (common with weighted
        # averaging), synthesizes a mixed-elevation description.
        overall_explanation = generate_overall_explanation(conditions, overall_quality)

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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve snow quality summary",
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
                detail=f"Resort {resort_id} not found",
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
                detail=f"Elevation level '{elevation}' not found for resort {resort_id}",
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
        }

    # Calculate overall quality from weighted raw scores (consistent with detail endpoint)
    elevation_weights = {"top": 0.50, "mid": 0.35, "base": 0.15}
    weighted_raw = 0.0
    total_w = 0.0
    for c in conditions:
        if c.quality_score is not None:
            w = elevation_weights.get(c.elevation_level, 0.15)
            weighted_raw += c.quality_score * w
            total_w += w

    if total_w > 0:
        overall_raw = weighted_raw / total_w
        snow_score = score_to_100(overall_raw)
        overall_quality = raw_score_to_quality(overall_raw)
    else:
        from services.snow_quality_service import SnowQualityService

        overall_quality = SnowQualityService.calculate_overall_quality(conditions)
        snow_score = None

    # Get representative condition for temperature/snowfall fields (prefer top)
    representative = None
    for pref in ["top", "mid", "base"]:
        for c in conditions:
            if c.elevation_level == pref:
                representative = c
                break
        if representative:
            break
    if not representative:
        representative = conditions[0]

    return {
        "resort_id": resort_id,
        "overall_quality": overall_quality.value,
        "snow_score": snow_score,
        "explanation": generate_overall_explanation(conditions, overall_quality),
        "last_updated": max(c.timestamp for c in conditions) if conditions else None,
        "temperature_c": representative.current_temp_celsius
        if representative
        else None,
        "snowfall_fresh_cm": representative.fresh_snow_cm if representative else None,
        "snowfall_24h_cm": representative.snowfall_24h_cm if representative else None,
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
                    for future in as_completed(futures):
                        resort_id, result = future.result()
                        if result:
                            results[resort_id] = result

            response.headers["Cache-Control"] = CACHE_CONTROL_PUBLIC_LONG
            return {
                "results": results,
                "last_updated": datetime.now(UTC).isoformat(),
                "resort_count": len(ids),
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
            for future in as_completed(futures):
                resort_id, result = future.result()
                if result:
                    results[resort_id] = result

        # Use 1-hour cache since weather data updates hourly
        response.headers["Cache-Control"] = CACHE_CONTROL_PUBLIC_LONG

        return {
            "results": results,
            "last_updated": datetime.now(UTC).isoformat(),
            "resort_count": len(ids),
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
                quality_threshold="fair",
                created_at=datetime.now(UTC).isoformat(),
                updated_at=datetime.now(UTC).isoformat(),
            )

        # User data is private, don't cache
        response.headers["Cache-Control"] = CACHE_CONTROL_PRIVATE

        return preferences

    except Exception as e:
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
    weekly_summary: bool | None = Field(None, description="Enable weekly summary")
    default_snow_threshold_cm: float | None = Field(
        None, description="Default minimum snow in cm to trigger notification"
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
        if request.weekly_summary is not None:
            settings.weekly_summary = request.weekly_summary
        if request.default_snow_threshold_cm is not None:
            settings.default_snow_threshold_cm = request.default_snow_threshold_cm
        if request.grace_period_hours is not None:
            settings.grace_period_hours = request.grace_period_hours

        # Save updated settings
        prefs.notification_settings = settings
        prefs.updated_at = datetime.now(UTC).isoformat()
        get_user_service().save_user_preferences(prefs)

        return {"message": "Notification settings updated successfully"}

    except Exception as e:
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

        # Save updated settings
        settings.resort_settings[resort_id] = resort_settings
        prefs.notification_settings = settings
        prefs.updated_at = datetime.now(UTC).isoformat()
        get_user_service().save_user_preferences(prefs)

        return {
            "message": f"Notification settings for {resort_id} updated successfully"
        }

    except Exception as e:
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

        return {"message": f"Resort-specific settings for {resort_id} removed"}

    except Exception as e:
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
    try:
        get_resort_events_table().delete_item(
            Key={"resort_id": resort_id, "event_id": event_id}
        )
        return None

    except Exception as e:
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

        return {
            "user": user.to_dict(),
            "tokens": tokens,
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

        return {
            "user": user.to_dict(),
            "tokens": tokens,
            "is_new_user": user.is_new_user,
        }

    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )
    except Exception as e:
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
        return {"tokens": tokens}

    except AuthenticationError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )


@app.get("/api/v1/auth/me")
async def get_current_user(user_id: str = Depends(get_current_user_id)):
    """Get current authenticated user info."""
    try:
        # Get user from database
        user_service = get_user_service()
        prefs = user_service.get_user_preferences(user_id)

        return {
            "user_id": user_id,
            "preferences": prefs.model_dump() if prefs else None,
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user info",
        )


# MARK: - Recommendations Endpoints


@app.get("/api/v1/recommendations")
async def get_recommendations(
    response: Response,
    lat: float = Query(..., ge=-90, le=90, description="User's latitude"),
    lng: float = Query(..., ge=-180, le=180, description="User's longitude"),
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
    """
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
            longitude=lng,
            radius_km=radius,
            limit=limit,
            min_quality=quality_filter,
        )

        response.headers["Cache-Control"] = CACHE_CONTROL_PUBLIC

        return {
            "recommendations": [r.to_dict() for r in recommendations],
            "count": len(recommendations),
            "search_center": {"latitude": lat, "longitude": lng},
            "search_radius_km": radius,
            "generated_at": datetime.now(UTC).isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Recommendations error (lat=%s, lng=%s): %s", lat, lng, e, exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate recommendations",
        )


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

    Results are cached for 1 hour since snow quality doesn't change frequently.
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

        # Cache miss - compute recommendations
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
    try:
        trip = get_trip_service().get_trip(trip_id, user_id)
        if not trip:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Trip {trip_id} not found",
            )

        response.headers["Cache-Control"] = CACHE_CONTROL_PRIVATE

        return trip.model_dump()

    except HTTPException:
        raise
    except Exception as e:
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
    try:
        trip = get_trip_service().update_trip(trip_id, user_id, update_data)
        return trip.model_dump()

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
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
    try:
        deleted = get_trip_service().delete_trip(trip_id, user_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Trip {trip_id} not found",
            )
        return None

    except HTTPException:
        raise
    except Exception as e:
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
    try:
        count = get_trip_service().mark_alerts_read(trip_id, user_id, alert_ids)
        return {"marked_read": count}

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to mark alerts read",
        )


# =============================================================================
# MARK: - Test/Debug Endpoints (for development only)
# =============================================================================


@app.post("/api/v1/debug/trigger-notifications")
async def trigger_notifications(
    user_id: str | None = Depends(get_optional_user_id),
):
    """
    Manually trigger the notification processor for testing.
    This invokes the notification Lambda asynchronously.
    Only available in staging environment. Auth is optional.
    """
    import boto3

    environment = os.environ.get("ENVIRONMENT", "dev")

    # Only allow in staging for testing
    if environment == "prod":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is not available in production",
        )

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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to trigger notification processor",
        )


@app.post("/api/v1/debug/test-push-notification")
async def test_push_notification(
    user_id: str | None = Depends(get_optional_user_id),
    title: str = "Test Notification",
    body: str = "This is a test push notification from Snow Tracker",
):
    """
    Send a test push notification to devices.
    If authenticated, sends to user's devices. Otherwise, sends to all devices.
    Only available in staging environment. Auth is optional.
    """
    import boto3

    environment = os.environ.get("ENVIRONMENT", "dev")

    # Only allow in staging for testing
    if environment == "prod":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is not available in production",
        )

    try:
        # Get device tokens
        device_tokens_table = get_dynamodb().Table(
            os.environ.get(
                "DEVICE_TOKENS_TABLE", f"snow-tracker-device-tokens-{environment}"
            )
        )

        if user_id:
            # Query for specific user's tokens
            result = device_tokens_table.query(
                KeyConditionExpression="user_id = :uid",
                ExpressionAttributeValues={":uid": user_id},
            )
            tokens = result.get("Items", [])
        else:
            # Scan for all tokens (for testing without auth)
            result = device_tokens_table.scan(Limit=10)  # Limit to 10 for safety
            tokens = result.get("Items", [])

        if not tokens:
            return {
                "message": "No device tokens found",
                "user_id": user_id or "anonymous",
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

                sns_client.publish(
                    TargetArn=endpoint_arn,
                    Message=json.dumps({"APNS_SANDBOX": json.dumps(apns_payload)}),
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send test notification",
        )


# MARK: - Admin Endpoints


@app.post("/api/v1/admin/backfill-geohashes")
async def backfill_geohashes():
    """
    Backfill geohashes for resorts that don't have them.
    Only available in staging/dev environments.
    """
    environment = os.environ.get("ENVIRONMENT", "dev")

    # Only allow in staging/dev for admin operations
    if environment == "prod":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This endpoint is not available in production",
        )

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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to backfill geohashes",
        )


# MARK: - Error Handlers


@app.exception_handler(ClientError)
async def aws_client_error_handler(request, exc: ClientError):
    """Handle AWS client errors."""
    error_code = exc.response["Error"]["Code"]
    error_message = exc.response["Error"]["Message"]

    if error_code == "ResourceNotFoundException":
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": f"Resource not found: {error_message}"},
        )
    else:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": f"AWS error: {error_message}"},
        )


@app.exception_handler(ValueError)
async def value_error_handler(request, exc: ValueError):
    """Handle value errors."""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST, content={"detail": str(exc)}
    )


# MARK: - Lambda Handler

# Create the Lambda handler
api_handler = Mangum(app, lifespan="off")


# For local development
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
