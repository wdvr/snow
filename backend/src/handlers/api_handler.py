"""Main FastAPI application handler for Lambda deployment."""

import os
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from fastapi import FastAPI, HTTPException, Depends, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from mangum import Mangum
import boto3
from botocore.exceptions import ClientError

from ..models.resort import Resort
from ..models.weather import WeatherCondition, SnowQuality, ConfidenceLevel
from ..models.user import User, UserPreferences
from ..services.resort_service import ResortService
from ..services.weather_service import WeatherService
from ..services.snow_quality_service import SnowQualityService
from ..services.user_service import UserService

# Initialize FastAPI app
app = FastAPI(
    title="Snow Quality Tracker API",
    description="API for tracking snow conditions at ski resorts",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc"
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
dynamodb = boto3.resource('dynamodb')
resort_service = ResortService(
    dynamodb.Table(os.environ.get('RESORTS_TABLE', 'snow-tracker-resorts-dev'))
)
weather_service = WeatherService(api_key=os.environ.get('WEATHER_API_KEY'))
snow_quality_service = SnowQualityService()
user_service = UserService(
    dynamodb.Table(os.environ.get('USER_PREFERENCES_TABLE', 'snow-tracker-user-preferences-dev'))
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
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "1.0.0"
    }


# MARK: - Resort Endpoints

@app.get("/api/v1/resorts", response_model=Dict[str, List[Resort]])
async def get_resorts(
    country: Optional[str] = Query(None, description="Filter by country code (CA, US)")
):
    """Get all ski resorts, optionally filtered by country."""
    try:
        resorts = resort_service.get_all_resorts()

        if country:
            resorts = [r for r in resorts if r.country.upper() == country.upper()]

        return {"resorts": resorts}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve resorts: {str(e)}"
        )


@app.get("/api/v1/resorts/{resort_id}", response_model=Resort)
async def get_resort(resort_id: str):
    """Get details for a specific resort."""
    try:
        resort = resort_service.get_resort(resort_id)
        if not resort:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Resort {resort_id} not found"
            )
        return resort

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve resort: {str(e)}"
        )


# MARK: - Weather Condition Endpoints

@app.get("/api/v1/resorts/{resort_id}/conditions")
async def get_resort_conditions(
    resort_id: str,
    hours: Optional[int] = Query(24, description="Hours of historical data to retrieve", ge=1, le=168)
):
    """Get current and recent weather conditions for all elevations at a resort."""
    try:
        # Verify resort exists
        resort = resort_service.get_resort(resort_id)
        if not resort:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Resort {resort_id} not found"
            )

        # Get conditions for the specified time range
        conditions = weather_service.get_conditions_for_resort(resort_id, hours_back=hours)

        return {
            "conditions": conditions,
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "resort_id": resort_id
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve conditions: {str(e)}"
        )


@app.get("/api/v1/resorts/{resort_id}/conditions/{elevation_level}")
async def get_elevation_condition(resort_id: str, elevation_level: str):
    """Get current weather conditions for a specific elevation at a resort."""
    try:
        # Validate elevation level
        valid_levels = ["base", "mid", "top"]
        if elevation_level not in valid_levels:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid elevation level. Must be one of: {valid_levels}"
            )

        # Verify resort exists
        resort = resort_service.get_resort(resort_id)
        if not resort:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Resort {resort_id} not found"
            )

        # Get latest condition for the specific elevation
        condition = weather_service.get_latest_condition(resort_id, elevation_level)
        if not condition:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No conditions found for {resort_id} at {elevation_level} elevation"
            )

        return condition

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve condition: {str(e)}"
        )


@app.get("/api/v1/resorts/{resort_id}/snow-quality")
async def get_snow_quality_summary(resort_id: str):
    """Get snow quality summary for all elevations at a resort."""
    try:
        # Verify resort exists
        resort = resort_service.get_resort(resort_id)
        if not resort:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Resort {resort_id} not found"
            )

        # Get latest conditions for all elevations
        conditions = []
        for elevation_point in resort.elevation_points:
            condition = weather_service.get_latest_condition(resort_id, elevation_point.level.value)
            if condition:
                conditions.append(condition)

        if not conditions:
            return {
                "resort_id": resort_id,
                "elevations": {},
                "overall_quality": SnowQuality.UNKNOWN.value,
                "last_updated": None
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
                SnowQuality.UNKNOWN: 0
            }

            score = quality_scores.get(condition.snow_quality, 0)
            overall_scores.append(score)

            elevation_summaries[condition.elevation_level] = {
                "quality": condition.snow_quality.value,
                "fresh_snow_cm": condition.fresh_snow_cm,
                "confidence": condition.confidence_level.value,
                "temperature_celsius": condition.current_temp_celsius,
                "snowfall_24h_cm": condition.snowfall_24h_cm,
                "timestamp": condition.timestamp
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

        return {
            "resort_id": resort_id,
            "elevations": elevation_summaries,
            "overall_quality": overall_quality.value,
            "last_updated": max(c.timestamp for c in conditions) if conditions else None
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve snow quality summary: {str(e)}"
        )


# MARK: - User Endpoints

@app.get("/api/v1/user/preferences", response_model=UserPreferences)
async def get_user_preferences(user_id: str = Depends(get_current_user_id)):
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
                    "weekly_summary": False
                },
                preferred_units={
                    "temperature": "celsius",
                    "distance": "metric",
                    "snow_depth": "cm"
                },
                quality_threshold="fair",
                created_at=datetime.now(timezone.utc).isoformat(),
                updated_at=datetime.now(timezone.utc).isoformat()
            )

        return preferences

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve user preferences: {str(e)}"
        )


@app.put("/api/v1/user/preferences")
async def update_user_preferences(
    preferences: UserPreferences,
    user_id: str = Depends(get_current_user_id)
):
    """Update user preferences."""
    try:
        # Ensure the user_id in the request matches the authenticated user
        preferences.user_id = user_id
        preferences.updated_at = datetime.now(timezone.utc).isoformat()

        user_service.save_user_preferences(preferences)

        return {"message": "Preferences updated successfully"}

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update user preferences: {str(e)}"
        )


# MARK: - Error Handlers

@app.exception_handler(ClientError)
async def aws_client_error_handler(request, exc: ClientError):
    """Handle AWS client errors."""
    error_code = exc.response['Error']['Code']
    error_message = exc.response['Error']['Message']

    if error_code == 'ResourceNotFoundException':
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": f"Resource not found: {error_message}"}
        )
    else:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": f"AWS error: {error_message}"}
        )


@app.exception_handler(ValueError)
async def value_error_handler(request, exc: ValueError):
    """Handle value errors."""
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc)}
    )


# MARK: - Lambda Handler

# Create the Lambda handler
api_handler = Mangum(app, lifespan="off")


# For local development
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)