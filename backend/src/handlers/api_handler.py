"""Main FastAPI application handler for Lambda deployment."""

import json
import os
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
from models.weather import SNOW_QUALITY_EXPLANATIONS, SnowQuality
from services.auth_service import AuthenticationError, AuthProvider, AuthService
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
)

# Initialize FastAPI app
app = FastAPI(
    title="Snow Quality Tracker API",
    description="API for tracking snow conditions at ski resorts",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
)

# Configure CORS
# TODO: For production, replace "*" with specific origins like:
# ["https://your-app-domain.com", "https://api.your-domain.com"]
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


def get_dynamodb():
    """Get or create DynamoDB resource (lazy init for SnapStart)."""
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource("dynamodb")
    return _dynamodb


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
            detail=f"Failed to retrieve regions: {str(e)}",
        )


@app.get("/api/v1/resorts")
async def get_resorts(
    response: Response,
    country: str | None = Query(
        None, description="Filter by country code (CA, US, FR, etc.)"
    ),
    region: str | None = Query(
        None, description="Filter by region (na_west, alps, japan, etc.)"
    ),
):
    """Get all ski resorts, optionally filtered by country or region."""
    try:
        # Validate region if provided
        if region and region not in VALID_REGIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid region. Must be one of: {VALID_REGIONS}",
            )

        resorts = _get_all_resorts_cached()

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
            detail=f"Failed to retrieve resorts: {str(e)}",
        )


@cached_resorts
def _get_all_resorts_cached():
    """Cached wrapper for getting all resorts."""
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
            detail=f"Failed to find nearby resorts: {str(e)}",
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
            detail=f"Failed to retrieve resort: {str(e)}",
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
        with ThreadPoolExecutor(max_workers=min(len(ids), 20)) as executor:
            futures = {executor.submit(fetch_one, rid): rid for rid in ids}
            for future in as_completed(futures):
                resort_id, result = future.result()
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve batch conditions: {str(e)}",
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
            detail=f"Failed to retrieve conditions: {str(e)}",
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
            detail=f"Failed to retrieve condition: {str(e)}",
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

        # Get latest conditions for all elevations IN PARALLEL using cached lookups
        from concurrent.futures import ThreadPoolExecutor, as_completed

        conditions = []
        elevation_levels = [ep.level.value for ep in resort.elevation_points]

        def fetch_condition(level: str):
            return _get_latest_condition_cached(resort_id, level)

        # Fetch all elevations in parallel
        with ThreadPoolExecutor(max_workers=min(len(elevation_levels), 5)) as executor:
            futures = [
                executor.submit(fetch_condition, level) for level in elevation_levels
            ]
            for future in as_completed(futures):
                try:
                    condition = future.result()
                    if condition:
                        conditions.append(condition)
                except Exception:
                    pass  # Skip failed elevations

        if not conditions:
            return {
                "resort_id": resort_id,
                "elevations": {},
                "overall_quality": SnowQuality.UNKNOWN.value,
                "last_updated": None,
            }

        # Analyze conditions for summary
        elevation_summaries = {}
        overall_scores = []

        for condition in conditions:
            # Calculate a numerical score for overall quality
            quality_scores = {
                SnowQuality.EXCELLENT: 5,
                SnowQuality.GOOD: 4,
                SnowQuality.FAIR: 3,
                SnowQuality.POOR: 2,
                SnowQuality.BAD: 1,
                SnowQuality.UNKNOWN: 0,
            }

            score = quality_scores.get(condition.snow_quality, 0)
            overall_scores.append(score)

            elevation_summaries[condition.elevation_level] = {
                "quality": condition.snow_quality.value,
                "fresh_snow_cm": condition.fresh_snow_cm,
                "confidence": condition.confidence_level.value,
                "temperature_celsius": condition.current_temp_celsius,
                "snowfall_24h_cm": condition.snowfall_24h_cm,
                "timestamp": condition.timestamp,
            }

        # Calculate overall quality
        if overall_scores:
            avg_score = sum(overall_scores) / len(overall_scores)
            if avg_score >= 4.5:
                overall_quality = SnowQuality.EXCELLENT
            elif avg_score >= 3.5:
                overall_quality = SnowQuality.GOOD
            elif avg_score >= 2.5:
                overall_quality = SnowQuality.FAIR
            elif avg_score >= 1.5:
                overall_quality = SnowQuality.POOR
            else:
                overall_quality = SnowQuality.BAD
        else:
            overall_quality = SnowQuality.UNKNOWN

        # Get explanation for overall quality
        quality_explanation = SNOW_QUALITY_EXPLANATIONS.get(overall_quality, {})

        # Set cache headers - 1 hour since weather updates hourly
        response.headers["Cache-Control"] = CACHE_CONTROL_PUBLIC_LONG

        return {
            "resort_id": resort_id,
            "elevations": elevation_summaries,
            "overall_quality": overall_quality.value,
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
            detail=f"Failed to retrieve snow quality summary: {str(e)}",
        )


@cached_snow_quality
def _get_snow_quality_for_resort(resort_id: str) -> dict | None:
    """Cached helper to get snow quality summary for a single resort."""
    resort = _get_resort_cached(resort_id)
    if not resort:
        return None

    from concurrent.futures import ThreadPoolExecutor, as_completed

    conditions = []
    elevation_levels = [ep.level.value for ep in resort.elevation_points]

    def fetch_condition(level: str):
        return _get_latest_condition_cached(resort_id, level)

    with ThreadPoolExecutor(max_workers=min(len(elevation_levels), 5)) as executor:
        futures = [
            executor.submit(fetch_condition, level) for level in elevation_levels
        ]
        for future in as_completed(futures):
            try:
                condition = future.result()
                if condition:
                    conditions.append(condition)
            except Exception:
                pass

    if not conditions:
        return {
            "resort_id": resort_id,
            "overall_quality": SnowQuality.UNKNOWN.value,
            "last_updated": None,
            "temperature_c": None,
            "snowfall_fresh_cm": None,
            "snowfall_24h_cm": None,
        }

    # Calculate overall quality
    quality_scores = {
        SnowQuality.EXCELLENT: 5,
        SnowQuality.GOOD: 4,
        SnowQuality.FAIR: 3,
        SnowQuality.POOR: 2,
        SnowQuality.BAD: 1,
        SnowQuality.UNKNOWN: 0,
    }
    overall_scores = [quality_scores.get(c.snow_quality, 0) for c in conditions]
    avg_score = sum(overall_scores) / len(overall_scores) if overall_scores else 0

    if avg_score >= 4.5:
        overall_quality = SnowQuality.EXCELLENT
    elif avg_score >= 3.5:
        overall_quality = SnowQuality.GOOD
    elif avg_score >= 2.5:
        overall_quality = SnowQuality.FAIR
    elif avg_score >= 1.5:
        overall_quality = SnowQuality.POOR
    else:
        overall_quality = SnowQuality.BAD

    # Get representative condition data (prefer mid elevation, then first available)
    representative = None
    for c in conditions:
        if c.elevation_level == "mid":
            representative = c
            break
    if not representative:
        representative = conditions[0]

    return {
        "resort_id": resort_id,
        "overall_quality": overall_quality.value,
        "last_updated": max(c.timestamp for c in conditions) if conditions else None,
        "temperature_c": representative.current_temp_celsius
        if representative
        else None,
        "snowfall_fresh_cm": representative.snowfall_after_freeze_cm
        if representative
        else None,
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
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    try:
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

        results = {}

        def fetch_quality(resort_id: str):
            try:
                summary = _get_snow_quality_for_resort(resort_id)
                return resort_id, summary
            except Exception as e:
                return resort_id, {"error": str(e)}

        # Fetch all in parallel
        with ThreadPoolExecutor(max_workers=min(len(ids), 20)) as executor:
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
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve batch snow quality: {str(e)}",
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
            "description": "Quality is based on non-refrozen snow - snow that fell after the last ice formation event.",
            "ice_threshold_celsius": 3.0,
            "ice_formation_hours": 4,
            "note": "Ice forms when temperatures stay at or above 3°C for 4+ consecutive hours. Snow that falls after such events is considered 'fresh' and non-refrozen.",
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
            detail=f"Failed to retrieve user preferences: {str(e)}",
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
            detail=f"Failed to update user preferences: {str(e)}",
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
            detail=f"Failed to register device token: {str(e)}",
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
            detail=f"Failed to unregister device token: {str(e)}",
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
            detail=f"Failed to retrieve device tokens: {str(e)}",
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
            detail=f"Failed to retrieve notification settings: {str(e)}",
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
            detail=f"Failed to update notification settings: {str(e)}",
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
            detail=f"Failed to update resort notification settings: {str(e)}",
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
            detail=f"Failed to delete resort notification settings: {str(e)}",
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
            detail=f"Failed to retrieve resort events: {str(e)}",
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
            detail=f"Failed to create resort event: {str(e)}",
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
            detail=f"Failed to delete resort event: {str(e)}",
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
            detail=f"Failed to submit feedback: {str(e)}",
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Authentication failed: {str(e)}",
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
            detail=f"Guest authentication failed: {str(e)}",
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
            detail=f"Failed to get user info: {str(e)}",
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate recommendations: {str(e)}",
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
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get best conditions: {str(e)}",
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
            detail=f"Failed to create trip: {str(e)}",
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
            detail=f"Failed to get trips: {str(e)}",
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
            detail=f"Failed to get trip: {str(e)}",
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
            detail=f"Failed to update trip: {str(e)}",
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
            detail=f"Failed to delete trip: {str(e)}",
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
            detail=f"Failed to refresh conditions: {str(e)}",
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
            detail=f"Failed to mark alerts read: {str(e)}",
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
            detail=f"Failed to trigger notification processor: {str(e)}",
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
            detail=f"Failed to send test notification: {str(e)}",
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
