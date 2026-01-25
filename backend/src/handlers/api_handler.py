"""Main FastAPI application handler for Lambda deployment."""

import os
from datetime import UTC, datetime, timezone
from typing import Dict, List, Optional

import boto3
from botocore.exceptions import ClientError
from fastapi import Depends, FastAPI, HTTPException, Query, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mangum import Mangum

from models.feedback import Feedback, FeedbackSubmission
from models.resort import Resort
from models.user import UserPreferences
from models.weather import SnowQuality
from services.resort_service import ResortService
from services.snow_quality_service import SnowQualityService
from services.user_service import UserService
from services.weather_service import WeatherService
from utils.cache import (
    CACHE_CONTROL_PRIVATE,
    CACHE_CONTROL_PUBLIC,
    cached_conditions,
    cached_resorts,
    cached_snow_quality,
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
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize AWS clients and services
dynamodb = boto3.resource("dynamodb")
resort_service = ResortService(
    dynamodb.Table(os.environ.get("RESORTS_TABLE", "snow-tracker-resorts-dev"))
)
weather_conditions_table = dynamodb.Table(
    os.environ.get("WEATHER_CONDITIONS_TABLE", "snow-tracker-weather-conditions-dev")
)
weather_service = WeatherService(
    api_key=os.environ.get("WEATHER_API_KEY"),
    conditions_table=weather_conditions_table,
)
snow_quality_service = SnowQualityService()
user_service = UserService(
    dynamodb.Table(
        os.environ.get("USER_PREFERENCES_TABLE", "snow-tracker-user-preferences-dev")
    )
)
feedback_table = dynamodb.Table(
    os.environ.get("FEEDBACK_TABLE", "snow-tracker-feedback-dev")
)


# MARK: - Authentication Dependency


def get_current_user_id() -> str:
    """Extract user ID from JWT token."""
    # TODO: Implement JWT token validation
    # For now, return a placeholder
    return "test_user_123"


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

# Region to country mapping for filtering
REGION_COUNTRIES = {
    "na_west": {"CA", "US"},  # Filtered by longitude
    "na_rockies": {"CA", "US"},  # Filtered by longitude
    "na_east": {"CA", "US"},  # Filtered by longitude
    "alps": {"FR", "CH", "AT", "IT", "DE"},
    "scandinavia": {"NO", "SE", "FI"},
    "japan": {"JP"},
    "oceania": {"AU", "NZ"},
    "south_america": {"CL", "AR"},
}


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
    return resort_service.get_all_resorts()


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
    return resort_service.get_resort(resort_id)


# MARK: - Weather Condition Endpoints


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

        # Set cache headers - conditions are updated hourly, 60s cache is safe
        response.headers["Cache-Control"] = CACHE_CONTROL_PUBLIC

        return {
            "conditions": conditions,
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
    return weather_service.get_conditions_for_resort(resort_id, hours_back=hours)


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
    return weather_service.get_latest_condition(resort_id, elevation_level)


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

        # Get latest conditions for all elevations
        conditions = []
        for elevation_point in resort.elevation_points:
            condition = weather_service.get_latest_condition(
                resort_id, elevation_point.level.value
            )
            if condition:
                conditions.append(condition)

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

        # Set cache headers
        response.headers["Cache-Control"] = CACHE_CONTROL_PUBLIC

        return {
            "resort_id": resort_id,
            "elevations": elevation_summaries,
            "overall_quality": overall_quality.value,
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


# MARK: - User Endpoints


@app.get("/api/v1/user/preferences", response_model=UserPreferences)
async def get_user_preferences(
    response: Response, user_id: str = Depends(get_current_user_id)
):
    """Get user preferences."""
    try:
        preferences = user_service.get_user_preferences(user_id)
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

        user_service.save_user_preferences(preferences)

        return {"message": "Preferences updated successfully"}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update user preferences: {str(e)}",
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
        feedback_table.put_item(Item=feedback.model_dump())

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
