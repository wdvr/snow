#!/bin/bash
# Generate GoogleService-Info.plist from environment variables
# Usage: ./generate-google-service-info.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATE_PATH="$SCRIPT_DIR/../SnowTracker/SnowTracker/Resources/GoogleService-Info.plist.template"
OUTPUT_PATH="$SCRIPT_DIR/../SnowTracker/SnowTracker/Resources/GoogleService-Info.plist"

# Check required environment variables
if [ -z "$FIREBASE_API_KEY" ]; then
    echo "Error: FIREBASE_API_KEY environment variable is not set"
    exit 1
fi

if [ -z "$FIREBASE_GCM_SENDER_ID" ]; then
    echo "Error: FIREBASE_GCM_SENDER_ID environment variable is not set"
    exit 1
fi

if [ -z "$FIREBASE_GOOGLE_APP_ID" ]; then
    echo "Error: FIREBASE_GOOGLE_APP_ID environment variable is not set"
    exit 1
fi

# Generate the plist from template
sed -e "s/\${FIREBASE_API_KEY}/$FIREBASE_API_KEY/g" \
    -e "s/\${FIREBASE_GCM_SENDER_ID}/$FIREBASE_GCM_SENDER_ID/g" \
    -e "s/\${FIREBASE_GOOGLE_APP_ID}/$FIREBASE_GOOGLE_APP_ID/g" \
    "$TEMPLATE_PATH" > "$OUTPUT_PATH"

echo "Generated GoogleService-Info.plist successfully"
