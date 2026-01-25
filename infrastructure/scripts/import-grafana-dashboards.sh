#!/bin/bash
# Import Grafana dashboards from JSON files to Amazon Managed Grafana
# Usage: ./import-grafana-dashboards.sh <workspace-url> <api-key>

set -e

WORKSPACE_URL="${1:-$GRAFANA_WORKSPACE_URL}"
API_KEY="${2:-$GRAFANA_API_KEY}"
DASHBOARD_DIR="$(dirname "$0")/../grafana-dashboards"

if [ -z "$WORKSPACE_URL" ] || [ -z "$API_KEY" ]; then
    echo "Usage: $0 <workspace-url> <api-key>"
    echo "  Or set GRAFANA_WORKSPACE_URL and GRAFANA_API_KEY environment variables"
    echo ""
    echo "To get your workspace URL:"
    echo "  aws grafana list-workspaces --query 'workspaces[?name==\`snow-tracker-grafana\`].endpoint' --output text"
    echo ""
    echo "To create an API key (in Grafana UI):"
    echo "  1. Go to Configuration → API Keys"
    echo "  2. Click 'Add API key'"
    echo "  3. Set role to 'Admin' and copy the key"
    exit 1
fi

# Ensure URL has https:// prefix
if [[ ! "$WORKSPACE_URL" =~ ^https?:// ]]; then
    WORKSPACE_URL="https://$WORKSPACE_URL"
fi

echo "Importing dashboards to: $WORKSPACE_URL"

# Import each dashboard JSON file
for dashboard_file in "$DASHBOARD_DIR"/*.json; do
    if [ -f "$dashboard_file" ]; then
        filename=$(basename "$dashboard_file")
        echo -n "  Importing $filename... "

        # Wrap dashboard in import format
        import_payload=$(jq -c '{dashboard: ., overwrite: true, folderId: 0}' "$dashboard_file")

        # POST to Grafana API
        response=$(curl -s -w "\n%{http_code}" \
            -X POST \
            -H "Authorization: Bearer $API_KEY" \
            -H "Content-Type: application/json" \
            -d "$import_payload" \
            "$WORKSPACE_URL/api/dashboards/db")

        http_code=$(echo "$response" | tail -1)
        body=$(echo "$response" | sed '$d')

        if [ "$http_code" = "200" ]; then
            echo "✓"
        else
            echo "✗ (HTTP $http_code)"
            echo "    $body"
        fi
    fi
done

echo "Done!"
