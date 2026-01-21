#!/bin/bash
# Run the backend API locally for development
# This allows the iOS app (in simulator) to connect to http://localhost:8000

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"

cd "$BACKEND_DIR"

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    uv venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install dependencies if needed
echo "Checking dependencies..."
uv pip install -r requirements.txt

# Set environment variables for local development
export AWS_DEFAULT_REGION=us-west-2
export RESORTS_TABLE=snow-tracker-resorts-dev
export WEATHER_CONDITIONS_TABLE=snow-tracker-weather-conditions-dev
export USER_PREFERENCES_TABLE=snow-tracker-user-preferences-dev
export WEATHER_API_KEY=${WEATHER_API_KEY:-"test-key"}
export LOG_LEVEL=DEBUG

# Check if using local DynamoDB or real AWS
if [ "$USE_LOCAL_DYNAMODB" = "true" ]; then
    export DYNAMODB_ENDPOINT=http://localhost:8000
    echo "Using local DynamoDB at $DYNAMODB_ENDPOINT"
else
    echo "Using AWS DynamoDB (dev environment tables)"
    echo "Make sure you have AWS credentials configured!"
fi

echo ""
echo "Starting local development server..."
echo "API will be available at: http://localhost:8000"
echo "API docs at: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Run with uvicorn for hot reload
uvicorn src.handlers.api_handler:app --reload --host 0.0.0.0 --port 8000
